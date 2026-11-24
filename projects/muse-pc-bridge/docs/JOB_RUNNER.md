# Durable job runner + bridge additions — design

Built 2026-11-24 on branch `muse-pc-bridge/durable-job-runner`
(from the v1.2.1 production tip). **Nothing here is deployed;
production still runs v1.2.1.** Everything below is verified on
Muse's Linux VM (POSIX) only — every Windows behaviour named
is implemented behind a platform seam and is **UNVERIFIED**
until the owner-PC smoke at deploy time. This release has five
components:

1. the durable job runner (`agent/job_runner.py`),
2. native presence (`agent/presence.py`, `GET /v1/presence`),
3. session-aware spawn with proof of life + raise-window
   (`agent/window_raise.py`, extensions to `POST /v1/processes`),
4. the boot beacon (`agent/boot_beacon.py`),
5. Project Mode (`agent/project_mode.py`).

Why: the consumers that need long PC work — the Wrong House
comic queue, LoRA training runs, the 1,600-stills harvester,
Underreach asset GPU stages — were driven by VM-side scripts
that died whenever the VM/runtime restarted, and the bridge's
own job API caps at `max_timeout_s: 900`. The runner is ONE
general facility for all of them: it owns no knowledge of any
consumer; consumers bring their own stage commands.

---

## 1. Durable job runner

### Job model (generic — zero domain logic)

A job is a JSON manifest:

```json
{
  "id": "optional-explicit-id",
  "name": "human name",
  "workdir": "D:\\path\\to\\work",
  "stages": [
    {"name": "optional", "command": ["exe", "arg", "..."],
     "timeout_s": 3600, "retries": 0},
    {"name": "string form", "command": "some shell line",
     "shell": "powershell"}
  ],
  "gpu": true,
  "gpu_blockers": ["extra-game.exe"],
  "rerun": false
}
```

A stage command is an argv list (no shell) or a string plus a
shell (`powershell` / `cmd` / `posix`, defaulting to the agent
default). `timeout_s` is per-stage and optional — **there is
no runner-level cap**; a stage runs until it exits, its own
timeout fires, or a control flag intervenes. `retries` is the
manifest-declared per-stage retry count (0–10); there are no
other retries, silent or otherwise. Validation is pure
(`validate_manifest`) and rejects unknown shells, shell+argv
mixes, out-of-range retries, and empty stage lists.

### Execution & checkpointing

The runner is its own supervised process — a sibling of the
agent, not a thread in it:

```
python agent/job_runner.py            # supervisor (default)
python agent/job_runner.py --worker   # the engine, supervised
python agent/job_runner.py --status   # print jobs status JSON
```

`RunnerSupervisor` mirrors `agent/supervisor.py`: child worker
process, restart with backoff (2 s base, 30 s cap), fast-crash
counting, status JSON at `<state_dir>/jobs/runner-status.json`;
the worker writes `<state_dir>/jobs/runner-heartbeat.json`.
Because the runner is independent of the agent, jobs survive
bridge-agent restarts, VM restarts (nothing about a job lives
on the VM), and run far past the 900 s bridge job cap.

Jobs run **one at a time, stages sequentially**. After every
stage/attempt boundary the runner atomically writes the job's
checkpoint (`<state_dir>/jobs/state/<id>.json`, tmp +
`os.replace` with the sharing-retry the queue runner uses):
job id, state, `next_stage` resume pointer, per-stage
status/attempts/pid/exit code/timestamps, `pause_kills`,
`waiting_for_gpu`. Stage output (stdout+stderr merged) appends
to `<state_dir>/jobs/logs/<id>.log`.

This is deliberately distinct from the v1.2 `queue_runner.py`:
that runner is an in-agent thread executing hash-pinned script
jobs under the agent's 900 s world, and it *fails* interrupted
jobs on restart. The durable runner is a separate process with
the opposite recovery contract (below). Both keep working;
neither replaces the other.

### Resume

On worker start, `recover()` scans the records. A job left in
state `running` was interrupted mid-flight:

- if the interrupted stage's pid is still alive, it is killed
  (event `orphan_killed`) — an unmonitored duplicate GPU stage
  is the real hazard;
- the stage returns to `pending`, the job returns to `queued`,
  event `resume`; completed stages are **never re-run**;
- `rerun: true` manifests reset all stages to pending instead.

Resumed job ids are also written to the boot log as a
`jobs_resumed` event (component 4), so "what was mid-flight at
shutdown and got resumed" is answerable from the state dir
alone.

### Control surface — file-based, deliberately

```
submit    write a manifest JSON into <state_dir>/jobs/queue/
status    read <state_dir>/jobs/state/<id>.json
          (or `job_runner.py --status` for the roll-up)
pause-all create <state_dir>/jobs/PAUSED
stop-job  create <state_dir>/jobs/stop/<job-id>
events    <state_dir>/jobs/events.jsonl
```

There are **no HTTP routes for the runner**, by design:

- Submission must keep working while the agent is down or
  restarting — the exact failure this component exists to fix.
  A directory drop cannot be refused by a dead server.
- The existing bridge file/exec API already drives files, so
  the VM side needs no protocol change and no new client code.
- The agent process and the runner process stay decoupled: the
  agent can be updated/restarted without touching job state.

Semantics: a claimed manifest moves to `jobs/manifests/<id>.json`
(the queue file is removed); an invalid manifest becomes a
`failed` state record with reason `invalid_manifest` and the
queue file is renamed `.rejected`; a duplicate explicit id is
renamed `.duplicate` and never clobbers the original. The
**PAUSED** flag kills the running stage's process tree
promptly (event `pause_kill`), returns the job to `queued`
(never failed), and starts nothing new until the flag is
removed — it is the owner's gaming kill switch. A **stop flag**
kills the running job (event `stop_kill`) and marks it
`stopped`; a stop flag on a queued job marks it stopped at the
next tick. Stopped jobs never resume.

### GPU yield

For `gpu: true` jobs, before the job starts and at every stage
boundary the runner calls `presence.gpu_contention()` — the
same single implementation the presence endpoint serves
(component 2). While contended (a known game executable is
running, or GPU utilization is at/over
`job_gpu_util_threshold`, default 90), the job **waits
checkpointed** with the reason recorded in `waiting_for_gpu`
(events `gpu_wait` / `gpu_clear`), polling every
`job_gpu_poll_s` (default 30). Waiting is never failure.
PAUSED and stop flags are honoured during the wait. Per-job
`gpu_blockers` and config `job_gpu_blockers` add exact-name
blockers on top of the built-in game list.

Config keys (all optional): `job_runner_poll_s` (0.25),
`job_gpu_poll_s` (30), `job_gpu_util_threshold` (90),
`job_gpu_blockers` ([]), `job_project_mode_auto` (false —
component 5).

### Failure semantics & audit

A stage exiting non-zero is retried only up to its manifest
`retries`; then the job is `failed` with `failed_stage`,
`exit_code`, and `reason` (`exit_code` / `stage_timeout` /
`spawn_failed` / `workdir_missing`) recorded. Lifecycle events
(submitted, job_started, stage_started, stage_finished,
stage_failed, stage_retry, pause_kill, stop_kill, stopped,
resume, orphan_killed, gpu_wait, gpu_clear, completed, failed,
invalid_manifest, runner_started, runner_stopped,
shutdown_interrupted) append to `jobs/events.jsonl`. Command
text is not duplicated into events (the archived manifest
holds it); no credential is ever written — the runner never
sees the bridge token at all.

### Graceful shutdown vs abrupt kill (found 2026-11-24)

Resume survives an abrupt kill (power loss, force-kill): the
worker dies with its stage, the record is left `running`, and
recover() resumes from the checkpoint — proven on the owner's
PC in the deploy smoke (worker and stage force-killed; the
job resumed from stage 2 and completed).

A graceful shutdown is a different ordering: Windows
terminates the stage processes (console children) seconds
before the runner worker (a console-less pythonw), so the
worker is still alive to watch its stage die with a generic
exit code. In the 2026-11-24 smoke a demo job's sleep stage
exited 1 as the PC rebooted; the worker recorded
`stage_failed` and failed the job, and after the reboot there
was nothing to resume.

Fixed in 1.3.2 (staged on the branch, not deployed): the
runner probes `bridge_agent.system_shutting_down()`
(GetSystemMetrics SM_SHUTTINGDOWN). A shutdown that begins
while a stage runs returns the stage to pending without
killing its tree (the OS reaps it; recover() orphan-kills a
survivor). A non-zero stage exit is arbitrated against the
probe — immediately, then across a grace window (config
`job_shutdown_grace_s`, default 10 s) — before it may be
recorded as a failure; a shutdown found at any point emits
`shutdown_interrupted` and converts the exit into an
interruption. Only a full quiet window lets a genuine
failure through, delayed by at most the grace. Deploy TODO
for the next gap: repeat the demo job across a graceful
reboot and confirm it resumes and completes.

### Completion notification (v1.4.0)

Until 1.4.0, the only way to learn a job had finished was to
poll — a watcher on a timer, or the owner asking for a
progress update. Watchers die with the runtime that hosts
them and schedules can miss the moment. The runner now pushes
the news itself: when a job reaches a terminal state
(`done` or `failed` — no intermediate states in v1), it sends
ONE email to the configured recipient (default
`nyx-adam@muse.ai`, Nyx's Muse Mail inbox, where inbound
mail surfaces on its own — no polling on either side).

- **Transport**: stdlib `smtplib`, STARTTLS, short connection
  timeout (`notify_smtp_timeout_s`, default 15 s). Expected
  provider is Gmail (`smtp.gmail.com:587`); host and port are
  configurable.
- **Config keys** (all optional, in the agent config):
  `notify_email_enabled` (default **false** — unconfigured,
  the runner behaves exactly as before), `notify_smtp_host`,
  `notify_smtp_port`, `notify_smtp_user`,
  `notify_recipient`, `notify_smtp_timeout_s`.
- **The secret rule**: the SMTP app password is NEVER a
  config value and is never committed anywhere. The runner
  reads it only from the environment variable
  **`BRIDGE_NOTIFY_APP_PASSWORD`** (set in the environment of
  the runner supervisor process, so the worker child inherits
  it). Error summaries are scrubbed of the password value
  before they are written anywhere; tests assert it appears
  in no event, record, or email body.
- **Email content**: subject `[pc-bridge] job <id>
  completed` / `... failed`; plain-text body with job id,
  name, outcome, submitted/started/finished times, duration,
  and a per-stage summary (name, status, attempts, exit
  code). Failures add the reason, the failing stage index,
  and the last non-empty line of the job's stage log.
- **Best-effort, exactly once**: the send happens after the
  terminal state is recorded. Any failure (SMTP down, bad
  credentials, no network) is caught, recorded as a
  `notify_failed` event with a non-secret error summary, and
  never fails the job, crashes the runner, or blocks stage
  execution. The job record carries `notified`,
  `notify_pending`, `notify_attempts`, and `notify_given_up`:
  `notified: true` is written after a successful send, so a
  runner restart never re-sends; a failed send is retried at
  most once on the next runner start, then given up
  (`notify_gave_up` event) and never attempted again.
- **Deploy-time setup (Adam, once)**: in the Google account
  used for sending, enable 2-Step Verification and create an
  **App password** for Mail; set `notify_smtp_user` to that
  account's address and `notify_email_enabled` to true in the
  PC's `config.json`; set the `BRIDGE_NOTIFY_APP_PASSWORD`
  environment variable to the app password for the runner
  supervisor's environment; restart the runner supervisor.
  The app password is entered only on the PC — never in chat,
  never in this repository.

The Windows/Gmail path is **UNVERIFIED** until the deploy
smoke: a real send from the PC and its arrival at
nyx-adam@muse.ai. VM tests drive a fake SMTP factory and an
injectable sender only.

---

## 2. Presence

`agent/presence.py` is the single presence implementation; the
endpoint and the runner's yield check are two callers of it.

```
GET /v1/presence        (desktop route — brokered to the
                         session helper like screenshot/input)
```

```json
{
  "observed_at": "...", "input_idle_s": 12.5,
  "foreground": {"pid": 1234, "title": "...", "process": "..."},
  "gaming": false, "games": [],
  "gpu": {"utilization_pct": 12, "memory_used_mib": 2200,
          "memory_total_mib": 12288, "source": "nvidia-smi"},
  "processes_seen": 183, "notes": []
}
```

- **Game detection is pure** (`detect_games`): anchored
  full-name matches against known game binaries (wow,
  wowclassic, ffxiv, eldenring, bg3, cyberpunk2077, witcher3,
  diablo, overwatch, valorant, cs2, dota2, league of legends,
  gta5, rdr2, starfield — seeded from the owner's own
  preflight script). **Launchers never count**: steam.exe,
  steamwebhelper.exe, battle.net.exe, agent.exe,
  epicgameslauncher.exe, leagueclient.exe, ffxivboot.exe, and
  friends are checked first and excluded even if a pattern
  would match.
- Probes are platform seams, injectable in tests:
  `list_process_names` (tasklist CSV on Windows, `ps` on
  POSIX), `gpu_utilization` (nvidia-smi, pure parser),
  `input_idle_seconds` and `foreground_window` (**Windows-only**
  ctypes: GetLastInputInfo with a wrap-safe DWORD diff;
  GetForegroundWindow + QueryFullProcessImageNameW).
- Degradation is per-field and honest: anything unobtainable
  is `null` plus a note — never fabricated. Off Windows, idle
  and foreground are null by design.

This retires the ad-hoc staged PowerShell idle scripts
(`gab16r_preflight.ps1` and friends): one call returns idle,
foreground, gaming, and GPU.

---

## 3. Session-aware spawn + raise-window

### Spawn

`POST /v1/processes` gains two fields:

```json
{"session": "interactive", "command": "...", "shell": "powershell",
 "proof_delay_s": 3}
```

- `"session": "interactive"` brokers the spawn to the session
  helper exactly like `"gui": true` does — the process launches
  directly in the user's interactive session, retiring the
  scheduled-task workaround GUI work used to need. (Any other
  `session` value is a 400.)
- **Proof of life**: after `proof_delay_s` (default 3 in
  session mode, otherwise opt-in; 0–30), the response carries
  `proof: {delay_s, alive, exit_code, ok}` — the recorded
  process state at that moment. A process that died inside the
  window returns **201 with `proof.ok: false`** and its exit
  code: an honest report in the spawn response itself, not an
  HTTP error and not a silent success.

Diagnosis of the 2026-11-21 incident (detached powershell
spawn exited 0 without running its command; the same spawn
through cmd worked): list-form argv joining quotes the
`-Command` argument with subprocess list2cmdline rules, and
PowerShell then parses a different string than the one
submitted. `popen_target` (commit f69fa8f) already gives cmd
the verbatim-string form for exactly this class of reason;
powershell never got it. **Suspect, not proven** — it cannot
be proven from the VM. Mitigation shipped: in session mode on
Windows, a powershell string command takes the verbatim
command-line form (`"<exe>" -NoProfile -NonInteractive
-Command <verbatim>`), scoped so every pre-existing spawn
path is byte-identical to before; and proof of life now makes
a recurrence visible immediately instead of hours later.

### Raise-window

```
POST /v1/window/raise   {"pid": 1234}  or  {"title": "substring"}
```
(desktop route, brokered like presence). Selection is pure
(`pick_window`): exactly one selector, exact pid or
case-insensitive title substring, visible windows preferred.
The raise itself obeys the hard rule from the 2026-11-12
incident — **no other window is ever minimized, moved, or
resized**: the implementation only ever touches the target
(SW_RESTORE *on the target alone* if the target itself is
minimized, SetForegroundWindow, verified by a
GetForegroundWindow read-back; fallback SetWindowPos
HWND_TOP with SWP_NOMOVE|SWP_NOSIZE on the target alone).

Documented limit: Windows foreground-lock may refuse
SetForegroundWindow from a background process. The response
then reports `foreground: false` honestly (with
`set_foreground_granted` and the method used) instead of
claiming success or escalating to tricks that would disturb
other windows. Off Windows the route answers 501.

---

## 4. Boot beacon

`agent/boot_beacon.py` appends one line per process start to
`<state_dir>/boot-log.jsonl` and tracks the last boot in
`<state_dir>/boot-beacon.json`:

```json
{"ts": "...", "event": "supervisor_start", "source": "supervisor",
 "boot_time": 1732..., "fresh_boot": true}
```

`system_boot_time()` is the seam: Windows derives boot time
from GetTickCount64 (now − tickcount), POSIX reads
`/proc/stat` `btime`, anything else returns None and
`fresh_boot` is recorded as **null — unknown, not guessed**.
A start is a *fresh boot* when the boot time differs from the
last recorded one by more than 30 s (tolerance exists because
the Windows derivation drifts with clock corrections); the
same boot time means a mere agent/supervisor restart. Hooks:
the supervisor at `run()` start, the agent (and session
helper) in `create_server`, and the runner's `jobs_resumed`
event after recovery. All hooks are guarded — a beacon failure
never takes a writer down. This passively answers the
long-held reboot-survival question: after a real reboot, the
boot log shows the fresh boot, the agent healthy start, and
exactly which jobs were resumed.

---

## 5. Project Mode

A bridge-side PC mode toggle that hands the desktop's
headroom (measured ~2.2 GB VRAM at idle on the owner's RTX
3060: Lively rendering, hardware-accelerated apps, launcher
helpers) to GPU jobs on demand — and gives the desktop back
untouched afterwards.

```
GET  /v1/project-mode
POST /v1/project-mode/engage
POST /v1/project-mode/disengage     (desktop routes, brokered)
```

State lives in `<state_dir>/project-mode.json` and records
**exactly what engage changed**; step events append to
`<state_dir>/project-mode-events.jsonl`, and API toggles are
also written to the bridge audit log. Disengage restores
precisely the recorded state — nothing more, nothing less.

### Engage steps (each recorded: applied / skipped / failed /
not_applicable, with detail)

| Step | Action | Elevation |
| --- | --- | --- |
| `power_plan` | record active scheme GUID; set High Performance (`8c5e7fda-…`) | not normally required |
| `lively` | gracefully close Lively processes (rendering stops); exe path recorded | no (owner's process) |
| `close_list` | gracefully close processes named in config `project_mode_close_list` | no (owner's processes) |
| `onedrive` | quit the OneDrive client (sync pauses while closed; relaunch resumes) | no |
| `search_indexing` | stop the WSearch service | **requires administrator** — under the bridge's usual contexts this step records `skipped: needs elevation` |

Rules that do not bend:

- **Graceful only.** Closing is a window close request
  (WM_CLOSE; polite `taskkill` without `/F` for windowless
  helpers; SIGTERM on POSIX) plus a grace wait. If a process
  is still alive afterwards it is **left running and the step
  says so**. Nothing is ever force-killed — an app may hold
  unsaved work — and nothing not on the list is ever touched.
- **Conservative defaults.** The shipped close list is
  launcher background helpers only: `steamwebhelper.exe`,
  `epicwebhelper.exe`. Browsers and chat apps are NOT
  defaults; the owner curates the list.
- **No silent partial success.** Every step's outcome is in
  the response, the state file, and the events log. A step
  that cannot apply (platform, elevation, stubborn process)
  degrades individually; the toggle itself still succeeds.

Disengage restores in reverse order, from the record only:
restart WSearch *iff* engage stopped it, relaunch OneDrive
*iff* engage closed it, relaunch precisely the closed
processes by recorded exe path, restore the recorded power
scheme GUID.

### Presence integration & the runner

While Project Mode is engaged, the agent's
`ProjectModeMonitor` (main agent only, poll
`project_mode_watch_s`, default 15 s) watches presence: a
**game launch**, or **fresh owner input** (idle seconds
dropping between polls — idle only grows while nobody touches
the machine), auto-disengages. A 15 s settle window after
engage prevents the owner's own engage action from instantly
undoing itself. The owner's use always wins — the same ethic
as the runner's GPU yield. The runner may auto-engage before
a `gpu: true` job only behind config `job_project_mode_auto`,
which **defaults OFF**; when it does engage, it disengages
afterwards only if it was the one that engaged (an owner/API
engagement is left exactly as found).

Windows operations sit behind the `Ops` seam
(`project_mode.WindowsOps` / `PosixOps`); off Windows the
machine steps report skipped/not-applicable rather than
pretending. The Windows implementation is **UNVERIFIED** —
see the deploy checklist.

---

## Deploy-time TODOs (owner-PC smoke, in order)

1. Run the full suite under Windows Python on the PC
   (`python -m unittest discover -s tests`) — expect the
   POSIX-only worker-kill test to skip and everything else to
   pass; investigate any cmd/powershell path failures before
   proceeding.
2. Start the runner supervisor beside the agent; submit a
   trivial demo job through the file root; watch it complete;
   reboot the PC mid-job and confirm the boot log shows
   `fresh_boot: true`, a `jobs_resumed` event, and the job
   finishing without re-running completed stages. This is the
   first real proof of the reboot-survival claim.
3. `GET /v1/presence` from the core (brokered) and confirm
   real idle seconds, the real foreground app, gaming
   flipping with a game launch, and launchers not counting.
4. Session spawn: spawn a powershell string command with
   `"session": "interactive"` and confirm proof-of-life plus
   actual side effects (this also tests the verbatim-command
   diagnosis for the 2026-11-21 powershell no-run incident);
   raise a window by title and confirm no other window moved.
5. Project Mode: engage with the default close list while
   Lively runs; confirm the recorded state file, the VRAM
   drop, per-step outcomes (expect `search_indexing` skipped
   unless elevated); type on the keyboard / launch a game and
   confirm auto-disengage restores the desktop.
6. Only after 1–5: move the first real consumer (the comic
   queue) onto the runner.
7. Completion notification (1.4.0): complete the one-time
   Gmail app-password setup (see "Completion notification"
   above), enable `notify_email_enabled` with
   `BRIDGE_NOTIFY_APP_PASSWORD` set for the runner
   supervisor, run a trivial job to `done` and one to
   `failed`, and confirm both emails arrive at
   nyx-adam@muse.ai with the right subjects, the events log
   shows `notify_sent` for each, and no second email arrives
   after a runner restart.
