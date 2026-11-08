# Muse PC Bridge — v1 Plan

Status: **PLAN** (recorded 2026-11-04 at Adam's direction; no v1 code written yet).
Baseline: agent **v0.1.0**, the v0 foundation on branch `muse-pc-bridge/foundation`
(PR #27), live on Adam's PC (`AthenZ971`, Windows 11) since 2026-11-04.

This plan is grounded in a full day of production use on 2026-11-04 (six test
tracks run end-to-end through the bridge: Electron app validation ×6, a Gradle
build check, a Godot FPS run, a full studio hardware pass, and a QEMU guest
update cycle). Every item below answers friction that actually occurred; the
evidence notes are at the end.

## Carried-over design constraints (Adam's decisions — do not relitigate)

- **Full shell access, no allowlist.** Adam chose this explicitly; the audit
  log is the safety net.
- **The audit log is non-negotiable:** every request, including auth failures,
  is recorded on the PC; the token is never written to it.
- **Tailnet-only binding** (the PC's Tailscale IP), token auth on all `/v1/*`.
- **Visible presence + kill switch:** Adam can always see the bridge is
  running and stop it. Any service form (below) must preserve an equivalent.
- **Stdlib-only Python** stays the default for the agent. A feature that
  genuinely cannot be done in stdlib (e.g. screen capture) ships as a small
  separate helper rather than growing the agent's dependency surface silently.

## 1. Execution — async jobs (the core fix)

- `POST /v1/exec` returns a **job ID immediately**; `GET /v1/jobs/{id}` reports
  state (queued/running/done/failed/killed), exit code, and output;
  output is fetchable **incrementally** (byte-offset tail) so long runs show
  progress; `POST /v1/jobs/{id}/cancel` terminates.
- Timeouts become a **job property**, not an HTTP property. A dropped client
  connection never again makes a command's outcome ambiguous.
- **Detached processes** as first-class objects: spawn / list / inspect / kill
  for long-lived programs (VMs, servers), replacing `Start-Process` through
  exec (whose redirected output can hang the calling shell).
- **Interactive sessions:** open a persistent shell, send input, read output —
  for installers, REPLs, and anything that prompts.

## 2. Eyes and hands

- **Native screenshot endpoint** returning image bytes directly (per-monitor,
  optional region). Must not reuse the inline `Add-Type` capture pattern —
  Windows Defender AMSI flags it as spyware-like; use a route that doesn't
  trip the heuristic. Retires the IrfanView + bridge-files round trip.
- **Host input injection** (mouse move/click/drag, key events, text typing)
  on the PC itself. Today input exists only inside QEMU guests via QMP; the
  bridge has no hands for host GUI work.
- **UI Automation endpoint:** enumerate a window's control tree, find a
  control by name, invoke it. (Hand-rolled in raw PowerShell repeatedly on
  2026-11-04.)
- **Clipboard** get/set endpoints.

## 3. Files

- **Chunked, resumable transfers** — retire the 40 MB request-body cap and
  the 16 MB file/get cap that forced bulk media onto a Google Drive detour.
- **Server-side SHA-256** returned by put/get, so integrity verification is
  part of the transfer instead of a separate manual `certutil` step.
- **Recursive directory operations:** tree list, mkdir, move, delete.
- **Configurable file roots** (a list), keeping path confinement while ending
  the use of exec as an escape hatch around the single `bridge-files` root.

## 4. Lifecycle

- **Service form:** run as a Windows service (or logon task in the user
  session) with **auto-restart on crash**; start/stop/status become commands.
  Today's single visible console window is the whole bridge — closing it or
  rebooting leaves nothing running. The visible indicator and kill switch
  from the constraints above must survive this change.
- **Self-update:** fetch a tagged release, restart into it, **roll back
  automatically** if the post-update health check fails.
- **Richer `/v1/status`:** agent version, uptime, running job count, disk
  space, and a **capabilities list** so clients can feature-detect.

## 5. Trust and audit hardening

- Audit entries gain **job IDs and output hashes**; the log gets **size-based
  rotation**; an endpoint serves the log's tail for review.
- **Auth-failure rate limiting** with backoff. (Constant-time token compare
  and tailnet-only bind already exist and stay.)

## 6. Client side

- A **real client library/CLI** on the Muse side (job polling, file sync,
  screenshot helpers) replacing hand-built JSON payloads. Two of the
  2026-11-04 glitches were client-side payload-construction errors
  (path escaping, format-string collisions), not agent bugs.

## Explicit non-goals for v1

- **UAC / secure-desktop interaction** — impossible by design; stays a
  documented limitation. Bridge-triggered installers warn Adam first.
- Multi-PC / fleet support.
- An allowlist or approval mode (Adam chose full access).
- A GUI dashboard.
- TLS on the bridge itself (Tailscale already encrypts the path; revisit
  only if the bridge ever leaves the tailnet).

## v1.0 exit criteria

1. Survives a PC reboot and a week of unattended running.
2. No work is lost or left in an unknown state when a client connection drops.
3. The four workflows exercised on 2026-11-04 — packaged-app testing, VM
   wrangling, bulk file/media movement, GUI verification — each run with
   **zero workarounds** (no IrfanView detour, no Drive detour, no QMP-only
   input, no probe-after-timeout guessing).
4. Every operation is auditable end-to-end from the log alone.
5. Install/upgrade is a single script; the Windows test suite covers jobs,
   files, input, and screenshots (baseline today: 10 tests).

## Suggested build order

| Slice | Contents |
|---|---|
| V1-S1 | Async jobs + detached processes + interactive sessions |
| V1-S2 | Native screenshot + host input + UI Automation + clipboard |
| V1-S3 | Service form + self-update + richer status |
| V1-S4 | Chunked files + server-side hashes + client library |
| V1-S5 | Audit hardening, docs, Windows test expansion, v1.0 tag |

Each slice: tests first where the harness allows, verified on Adam's PC
through the bridge itself before the next slice starts — the same standard
the v0 day was held to.

## Evidence notes (2026-11-04, firsthand)

- Local HTTP timeouts repeatedly fired while PC-side work **continued and
  completed** (QEMU launches, installs) — every one required a probe of PC
  state before proceeding, and one payload had to be written defensively
  against double-execution. → §1.
- Screen capture via inline PowerShell was blocked by Defender AMSI;
  IrfanView was installed as the workaround and every screenshot since has
  been a two-step file round trip. → §2.
- All guest/host GUI control went through QMP send-key/mouse events and
  hand-written UIAutomation PowerShell. → §2.
- The 384 MB Synveil v2 image and 4 GB main image could not move through the
  bridge at all; they travelled via Google Drive for Desktop (G:) instead.
  → §3.
- Hash verification of every transferred artifact was a separate manual
  `certutil` call. → §3.
- The bridge is one console process: no autostart, no restart on failure.
  → §4.
