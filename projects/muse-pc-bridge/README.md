# muse-pc-bridge

A small agent the owner runs on his Windows PC so Muse (Nyx) can do
real work on that PC — run shell commands and transfer files — over
**Tailscale**, with **every request written to an audit log** on the
PC. Python standard library only; no third-party dependencies.

## Why

Work on the owner's PC kept needing a human relay (owner or another
assistant) for every command. This bridge removes the relay: Muse
connects from its VM to the agent on the PC through the owner's
tailnet and works directly, while the owner keeps visibility (audit
log) and control (kill switch).

## Safety model

Full shell access is the owner's explicit choice (2026-11-04). Four
things protect it — read `docs/DESIGN.md` before changing any of them:

1. **Token auth** — a 256-bit bearer token, generated on the PC,
   shown once, never committed to git, never written to the audit
   log. Whoever holds it has full shell as the owner; treat it like
   a password.
2. **Tailnet-only** — the agent binds to the PC's Tailscale `100.x`
   address only. It is not reachable from the LAN or the internet.
3. **Audit log** — append-only JSONL on the PC records every
   request (including failed auth), every command, and every file
   transfer. Non-negotiable.
4. **Kill switch** — the console and avatar forms run in a visible
   window: window open = running, close it and access ends
   immediately. The optional v1.1 **boot core** runs headless from
   machine boot (see below); its switches are the Scheduled Task
   controls and `scripts\bridge-core.ps1 -Action stop`, and the
   avatar at logon shows its state.

## Quick start (owner's PC, summary)

Full ordered steps: **`docs/INSTALL_WINDOWS.md`**.

```powershell
cd projects\muse-pc-bridge
python -m unittest discover -s tests -v      # verify on Windows
cd agent
python bridge_agent.py --init                # writes config.json, prints token ONCE
# edit config.json: set "host" to this PC's Tailscale 100.x IP
cd ..
scripts\start-bridge.cmd                     # leave the console open
```

Then, from a second window, set `MUSE_PC_BRIDGE_URL` /
`MUSE_PC_BRIDGE_TOKEN` and verify with
`client\bridge_client.py status`. Finally hand the tailnet IP, port,
and token to Muse **out-of-band** — never via git.

## Layout

| Path | What |
| --- | --- |
| `agent/bridge_agent.py` | the server (runs on the PC) |
| `agent/supervisor.py` | supervisor core (auto-restart, staged-update apply + health check + auto-rollback, publishes `display-state.json`): visible-console form, or `--headless` boot-core form under pythonw |
| `agent/supervisor_gui.py` | avatar-display form: floating window — Muse's avatar animated by real bridge activity, colour-key transparent so only the character shows on the desktop; owns its supervisor (closing the window is the kill switch) or **attaches display-only** to a running core (closing it then leaves the bridge running, and the menu says so); in attach mode it also hosts the session helper |
| `agent/session_helper.py` | interactive session helper: loopback-only server (same token) serving ONLY the desktop routes from inside the owner's logon session, so a session-0 boot core can broker screenshot/input/UIA/clipboard/GUI-launch to the real desktop; registers in `state/session-helper.json` with a heartbeat |
| `agent/display_state.py` | pure signal→display-state mapping for the avatar (idle / working / session / connecting / celebrate / alert; an active UAC prompt maps to alert with label "Approval needed at PC") |
| `agent/assets/avatar/` | avatar animation loops, one full-frame transparent GIF per display state |
| `agent/bridge_update.py` | self-update mechanics (bundle verify, staged apply, rollback) |
| `agent/queue_runner.py` | resident queue runner (v1.2): a thread in the agent draining `<state_dir>/queue/` — hash-pinned script jobs, PAUSED kill switch, skip-if-likely UAC policy, restart recovery that fails (never re-runs) interrupted jobs |
| `agent/job_runner.py` | durable job runner (built 2026-11-24, NOT deployed): a separate supervised process running generic manifest jobs from `<state_dir>/jobs/` — per-stage checkpoints, resume that never re-runs completed stages, file-based control (queue drop / PAUSED / per-job stop flags), GPU yield via presence; see `docs/JOB_RUNNER.md` |
| `agent/presence.py` | native presence: input idle (Windows), foreground window, game detection (launchers never count), GPU load via nvidia-smi — one implementation behind `GET /v1/presence` and the runner's GPU yield check |
| `agent/window_raise.py` | raise ONE window (by pid or title) to the foreground without minimizing/moving/resizing any other window (`POST /v1/window/raise`); foreground-lock refusal is reported, never worked around |
| `agent/boot_beacon.py` | boot beacon: per-start lines in `<state_dir>/boot-log.jsonl` distinguishing a fresh boot from an agent restart, plus the runner's `jobs_resumed` record |
| `agent/project_mode.py` | Project Mode (built 2026-11-24, NOT deployed): engage/disengage toggle that records exactly what it changed (power plan, Lively, a curated close list, OneDrive, search indexing — each step degrading honestly, WSearch needs elevation) and restores precisely that; presence auto-disengages on owner input or a game launch |
| `agent/helpers/uia.ps1` | fixed UI Automation helper driven by the agent (JSON parameters only) |
| `client/bridge_client.py` | Muse-side library + CLI (jobs, processes incl. `spawn-gui`, sessions, chunked files, screenshot/input/clipboard/uia, `wol`, `audit`, queue commands) |
| `scripts/start-bridge.cmd` | start the agent in a visible console |
| `scripts/start-bridge-service.cmd` | start the supervised agent (v1 service form) |
| `scripts/start-bridge-gui.cmd` | start the avatar-display form (no console window) |
| `scripts/start-bridge-core.cmd` | start the headless core (v1.1 boot form, pythonw, no window) |
| `scripts/bridge-service.ps1` | manage the supervised form as a logon task (install/start/stop/status/uninstall) |
| `scripts/bridge-core.ps1` | manage the boot core task (install/start/stop/status/uninstall; SYSTEM, at startup) |
| `scripts/wol-send.py` | standalone Wake-on-LAN sender (for waking the bridge PC itself from another LAN device — the bridge cannot wake its own host) |
| `scripts/install-autostart.ps1` | OPTIONAL logon autostart (same visible console) |
| `config.example.json` | config shape (real `config.json` is git-ignored) |
| `tests/` | end-to-end suites: boot the real server on loopback (`test_bridge.py` + `test_v1_*.py`) |
| `docs/DESIGN.md` | architecture, wire protocol, threat model |
| `docs/INSTALL_WINDOWS.md` | exact Windows install + verification steps, plus the v1 upgrade path |
| `docs/CHATGPT_INSTALL_HANDOFF.md` | delegated install (D: drive) that stops before the owner's token/final-setup steps |
| `docs/TEST_PLAN.md` | what the tests prove — and what they cannot |
| `docs/JOB_RUNNER.md` | design of the durable job runner release: runner, presence, session spawn + raise-window, boot beacon, Project Mode — incl. the file-based control surface rationale and the deploy-time smoke checklist |
| `docs/MUSE_HANDOFF.md` | current state, decisions, next steps |
| `docs/V1_PLAN.md` | the v1 feature plan (recorded 2026-11-04) |
| `REQUIREMENTS.md` | Python >= 3.11, stdlib only, Tailscale |

## Status — honest version

**v0 foundation (agent 0.1.0), verified on Muse's Linux VM only:**
the suite (10 tests) passes and a client↔agent smoke test succeeded
there. **Not yet verified:** anything on Windows (PowerShell/cmd,
the .cmd launcher), the real Tailscale link, and the autostart task.
Those are owner-PC checks built into the install doc; until they are
done, this project is *implemented and VM-tested*, not *installed*.
See `docs/MUSE_HANDOFF.md`.

**Update (2026-11-04):** installed and live on the owner's PC — see
the state update in `docs/MUSE_HANDOFF.md`. The v1 feature plan is
recorded in `docs/V1_PLAN.md`.

**Update (2026-11-04 night): v1 built (agent `1.0.0`).** Async jobs,
detached processes, interactive sessions, in-agent screenshot /
host input / clipboard / UI Automation, chunked resumable transfers
with server-side SHA-256, multi-root files, a supervised service
form with self-update + automatic rollback, audit hardening (§5),
and a real client library — per `docs/V1_PLAN.md`, in five slice
commits on this branch. **Verified on Muse's Linux VM: 63 tests
pass** (1 Windows-only skip) plus a client-CLI smoke run. The first
PC staging run found a screenshot defect (`format=png` → HTTP 500,
undeclared ctypes signatures in the GDI capture); it is fixed on
this branch and VM-verified, and the same signature defect class
has since been fixed in the `pid_alive` process helper and the
clipboard path, with live Windows staging
verification completed the same night (see
`docs/MUSE_HANDOFF.md`). The first suite run under Windows
Python (2026-11-05, during the cutover) found one more
defect — interactive-session output starving behind a 64 KiB
buffered pipe read, plus a Windows-only test-teardown error —
both fixed on this branch, and the **full suite then passed
under Windows Python: 63 tests, OK (4 platform skips)**. The
cutover completed the same morning: the live agent on the PC
now runs **v1.0.0 in the supervised (service) form** — see
`docs/MUSE_HANDOFF.md` for the full record.

**Update (2026-11-08):** the four Codex review findings on the
v1 PR (update-staging path traversal, file/tree symlink escape,
client job-polling output loss, unaudited supervisor stop) are
fixed on branch `codex-fixes/pc-bridge`, each with a regression
test that failed pre-fix. **Verified on Muse's Linux VM:
88 tests, OK (1 skip).** The Windows graceful-stop path
(CTRL_BREAK_EVENT) is implemented but **not yet verified on the
PC**, and this branch is **not deployed** — the production
bridge still runs the pre-fix build. See the 2026-11-08 entry in
`docs/MUSE_HANDOFF.md`.

**Update (2026-11-08, v1.1 — agent `1.1.0`, branch
`muse-pc-bridge/v1-1-features`):** four features, all owner-requested.
(1) **UAC consent signal**: the agent polls for `consent.exe` and
reports `uac_prompt` on `/v1/status`, audits appear/clear, and the
avatar shows "Approval needed at PC". (2) **Boot-surviving core**:
a headless supervisor form started by a SYSTEM boot task
(`scripts\bridge-core.ps1`) brings the bridge up before logon; the
avatar attaches to it display-only. (3) **Wake-on-LAN**:
`POST /v1/wol` sends a magic packet from the PC to wake other LAN
machines, plus the standalone `scripts\wol-send.py` for the other
direction (the bridge cannot wake its own host — stated plainly in
both places). (4) **Detached GUI launch**: `process_spawn` gains a
`gui` mode that spawns the executable directly so the tracked pid
is the app itself. **Verified on Muse's Linux VM: 132 tests,
OK (3 skips)** — baseline was 88; the new skips are the two WoL
live-delivery tests, which need outbound UDP the VM sandbox
refuses. **Not verified on the PC** (no PC contact during this
work, at the owner's direction): the consent.exe probe against a
real prompt, a real GUI app spawn, an actual machine waking, and
the boot-task activation. **Not deployed** — production still runs
the pre-v1.1 build; deploying and activating the boot core are
separate owner-approved steps. See the 2026-11-08 v1.1 entry in
`docs/MUSE_HANDOFF.md` and the checklists in `docs/TEST_PLAN.md`.

**Codex-fix follow-up (2026-11-08, same branch):** Codex's review
of the v1.1 PR found four real defects, all fixed. The boot core
runs in session 0, so desktop routes are now **brokered to a
session helper** in the owner's logon session (and answer an
honest 501 before logon instead of touching the wrong desktop);
the avatar's attach decision no longer races a starting core;
the management scripts stop the bridge through an **audited
graceful stop-request** instead of killing processes; and
display-state publishing follows label changes, not just state
changes. **VM suite: 147 tests, OK (3 skips).**

**Update (2026-11-13, v1.2 — SPEC ONLY, branch
`muse-pc-bridge/v1-2-spec`):** the owner specced the next version:
(1) **UAC pre-flight** — an exec/queue submission is assessed for
likely UAC prompts *before* it runs, with an opt-in
`require_no_uac` refusal; (2) **audit read** — a token-authed
`GET /v1/audit` over the agent's own log file only; (3) **resident
queue runner** — a thread in the existing core drains a queue of
hash-pinned, pre-approved jobs while Muse is disconnected, with a
local PAUSED kill switch and skip-if-likely UAC policy. Full design:
`docs/V1_2_SPEC.md`. **Nothing is built or verified; this is planned
work.** Production still runs v1.1.

**Update (2026-11-13, later — v1.2 BUILT, agent `1.2.0`, branch
`muse-pc-bridge/v1-2`):** all three items are implemented in the
spec's build order, each with its tests: audit read (including a
write-time scrub enforcing the "token never appears in the audit
log" invariant — command summaries previously leaked a token that
was seeded into a command), UAC pre-flight on `/v1/exec` and
`/v1/queue` with the 409 `require_no_uac` refusal, and the resident
queue runner. **Verified on Muse's Linux VM only: full suite 234
tests, OK (3 skips).** **NOT deployed — production still runs
v1.1**, and nothing about the owner's PC was touched during the
build (the owner directed VM-only work). Windows behaviour is
explicitly unverified: the §4 Windows smoke on the PC and the
production switch remain owner-gated. See the 2026-11-13 v1.2
entry in `docs/MUSE_HANDOFF.md`.

**Update (2026-11-14 — v1.2 DEPLOYED, production runs `1.2.0`):**
the §4 Windows smoke initially failed (4 failures + 1 error, all
in the new queue tests, plus a GuiSpawn teardown error). Diagnosis
on the PC found three Windows-only defects, all fixed on the
branch: (1) cmd commands passed to `cmd.exe` in subprocess list
form are mangled by `list2cmdline` quoting + cmd `/c` parsing, so
any command containing a quoted argument or redirect target exited
1 without running — cmd invocations now go to Popen as a verbatim
command-line string (`popen_target`); (2) `kill_tree` on Windows
killed only the shell, leaving children holding the job's pipes
and stalling job completion ~10 s — it now uses `taskkill /T /F`,
and the post-exit pipe drain is bounded to a 1 s shared window;
(3) queue record moves lost momentary file-sharing races against
readers, stranding stale record copies — record writes/moves now
retry `PermissionError` briefly. A fourth fix makes
`UacMonitor.check_once` sample its probe under the state lock
(a stale-sample race the Windows status test hits against the
watch thread). **Verified: VM suite 234 tests OK (3 skips);
owner-PC Windows smoke 234 tests OK (9 skips), Python 3.14.2.**
Production was switched the same evening (checkout to
`muse-pc-bridge/v1-2` @ `7fa13fa`; both supervised agents — the
session-0 SYSTEM core and the session-1 avatar agent — restarted
onto the new code and verified: `/v1/status` reports 1.2.0,
`GET /v1/audit` and `GET /v1/queue` answer, the audit log records
the 1.2.0 `server_start`). Rollback is the intact v1.1 checkout
branch (`muse-pc-bridge/v1-1-features`). Still unverified:
`waiting_uac` against a genuine consent prompt, the queue runner
across a real reboot, the classifier against real installer
command lines. See the 2026-11-14 entry in
`docs/MUSE_HANDOFF.md`.

**Update (2026-11-21 — v1.2.1 DEPLOYED, production runs
`1.2.1`):** the owner reported that bridge work flashes a
terminal window on his desktop for every command — the agent
runs under pythonw (no console of its own), so Windows created
a fresh console for every console child it spawned. v1.2.1
passes `CREATE_NO_WINDOW` at every agent spawn site (jobs,
sessions, detached shell spawns, `taskkill`, the UIA helper)
and in the supervisor's agent child when the supervisor itself
has no console (the console service form is unchanged — its
shared console is the kill switch). Work that is supposed to
be visible stays visible: GUI spawns (`"gui": true`) are
untouched, and exec/jobs/processes payloads accept
`"visible": true` to opt a shell spawn back into a console.
**Verified: VM suite 242 tests OK (3 skips), including 8 new
tests in `tests/test_v1_2_1_no_window.py`; and on the owner's
PC the same day** — the release bundle was staged through the
bridge's own self-update (`update_applied` / `update_healthy`
in both supervisors' logs, all three files backed up), both
agents report `1.2.1`, a session-1 job created no window
(UIA window diff + a mid-job screenshot over the owner's
fullscreen game), a `"gui": true` Notepad launch opened a
real window, and an exec with `"visible": true` produced a
console window on demand. The console service form is not
run in production, so its behaviour is verified by code
inspection only. See the 2026-11-21 entries in
`docs/MUSE_HANDOFF.md`.

**Update (2026-11-24): durable job runner release — BUILT,
VM-verified, NOT deployed.** On branch
`muse-pc-bridge/durable-job-runner`: a general-purpose durable
job runner (its own supervised process; manifest jobs with
per-stage checkpoints and resume that never re-runs completed
stages; file-based control — queue drop, PAUSED kill switch,
per-job stop flags; GPU yield for `gpu: true` jobs), a native
presence endpoint (`GET /v1/presence`: input idle, foreground
app, game detection with launchers excluded, GPU load),
session-aware spawn with proof of life plus a raise-window
call that never disturbs other windows, a boot beacon that
records fresh boots and resumed jobs, and Project Mode (a
recorded, exactly-reversible toggle that frees the desktop's
GPU headroom for jobs and auto-disengages when the owner uses
the PC). Design: `docs/JOB_RUNNER.md`. **Verified on Muse's
Linux VM: full suite 302 tests, OK (3 pre-existing skips)** —
60 new tests across `test_job_runner.py`, `test_presence.py`,
`test_boot_beacon.py`, `test_window_raise.py`,
`test_project_mode.py`, and `test_v1_3_bridge_additions.py`,
including a real worker process SIGKILLed mid-job and resumed
from its checkpoint. **NOT verified: everything Windows** —
the presence ctypes probes, session-1 spawn behaviour, the
raise, Project Mode's Windows operations, and a real reboot
resume are owner-PC smokes listed in `docs/JOB_RUNNER.md`.
Production still runs v1.2.1.

**Update (2026-11-24, later): 1.3.0/1.3.1 DEPLOYED; 1.3.2
staged.** The release (plus the SIGTERM audit-race root fix)
was deployed to the owner's PC the same day and the deploy
smokes passed: full suite under Windows Python, presence,
session spawns, raise-window, and an abrupt-kill job resume
after a real reboot. Two defects were found and fixed along
the way: 1.3.1 removed DETACHED_PROCESS from detached spawns
(it makes Windows PowerShell exit 0 without running), and the
graceful-reboot leg of the resume smoke exposed that a
graceful shutdown kills a job's stage before the runner, so
the stage's exit was recorded as a failure instead of an
interruption. 1.3.2 fixes that: the runner probes
SM_SHUTTINGDOWN and arbitrates non-zero stage exits against
it (config `job_shutdown_grace_s`, default 10), returning the
stage to pending for resume. **Verified on Muse's Linux VM:
full suite 313 tests, OK (3 skips)**, including 7 new tests in
`test_v1_3_2_shutdown_resume.py`. 1.3.2 is committed on the
branch but NOT deployed; production runs 1.3.1, and the
graceful-reboot resume re-test is an owner-PC smoke for the
next deploy gap.
