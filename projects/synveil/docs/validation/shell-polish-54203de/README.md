# S4 Shell Polish — Drawn Icons, Tray Status, Menu Slide, Pressed States

Evidence for the polish pass over the ADR 0025 custom shell:
the Start menu's letter tiles and the task buttons' generic
glyphs are replaced by an original geometric icon set drawn
in the shell helper; the panel gains a status tray fed only
by existing read-only surfaces; the Start menu slides at the
UI_DESIGN motion spec; buttons gain pressed states in the
design tokens. All work is in the carried Weston patch
(userspace, unprivileged Wayland client). No frozen-zone
(ADR 0023) surface is touched: the pass's whole diff against
the base is the shell patch plus its QEMU gate.

## Source

- Base: `54203de` (aggregation slice tip).
- `e6e937b` — the polish itself, entirely inside
  `build/native/patches/weston/weston-15.0.1-synveil-shell.patch`
  (patch sha256 after the pass:
  `f7c9a0c5107984f1da90ab0554ba3685d8ac7dbdcb3707e88c5997e72b8f193d`):
  - **Icons** — `sv_draw_icon`, a 24-grid geometric set drawn
    with cairo, original artwork only: Start (existing glyph),
    Terminal (dark tile, green chevron/underscore), Files
    (folder), Updates (download arrow; accent + badge dot
    when an update is pending, ink-faint when current),
    Browser (globe), Demo/first window (window with accent
    dot), a generic window mark for other tasks, and the
    three network states. Menu items draw a 28 px icon
    instead of the letter tile; task buttons draw a 16 px
    icon matched from the window's app_id (title fallback).
  - **Tray** — two slots left of the clock, fed by a
    2-second poll in the shell helper:
    - *Network*: `/sys/class/net/*/operstate` (world-readable
      sysfs). Present + operstate `up` → accent arcs; present
      but not up → grey arcs with a danger-red slash; no
      interface → dim arcs only.
    - *Update*: the A/B agent's existing NDJSON status query
      over `/run/synveil-ab/agent.sock` — the same read-only
      surface the update GUI uses, no new or privileged path.
      The slot is hidden entirely when no agent answers
      (never a faked "up to date"); a staged trial or a
      validly signed attached update shows the pending icon,
      otherwise the current icon.
  - **Menu slide** — the card animates over 200 ms with the
    spec's ease-out cubic, emerging from behind the panel
    strip (the card now draws before the strip); open and
    close both animate; input is never delayed by the
    animation. The stock default-launcher fallback is
    removed: the Start menu owns launching, and Terminal is
    a first-class entry there.
  - **Pressed / hover states** — the previously dormant
    `pressed` fields are wired: press fills with
    accent-pressed `#38A8E8`, hover is surface-hi as before;
    tooltips on Start and the tray slots join the task
    buttons' existing tooltips.
  - Menu content is unchanged in structure: the same
    marker-gated real apps (Files, Updates, Browser) plus
    Terminal and the demo window, launching through the
    proven ADR 0025 mechanism. No session actions: the
    session machinery still exposes no logout/lock to offer.
- `2a9e83b` — the shell gate asserts the polish: per-item
  menu icons (non-surface icon pixels, Terminal green, Demo
  blue, centre pixel not accent — no letter tiles), the demo
  task button's icon, and the tray's network state on the
  joined image; boots the gate guest with user networking
  attached so the interface exists.
- `fdf24cf` — tray network source corrected from `carrier`
  to `operstate` on guest evidence (below), and the gate's
  tray assertion follows the honest state; the live
  link-flip assertion is dropped with its reason recorded
  in the gate.
- `04d5ec4` — the gate waits for the session's second
  window before counting task buttons (the demo window is
  the session's first window; the terminal starts a moment
  later and the count raced it).

Host tests at the final tip: full workspace **230 passed,
0 failed** (veil-core 193 + synctl 10 + 10 integration +
17 across the remaining suites). The Rust tree is untouched
by this pass; the count re-verifies it.

## The carrier → operstate correction

First gate run against the polished image showed the tray
in its "no interface" state although the guest had user
networking. A debug boot's in-guest terminal showed why:
`eth0` exists, but `cat /sys/class/net/eth0/carrier` fails
with EINVAL — carrier is unreadable while an interface is
administratively down, and the session never brings the
unconfigured interface up (bringing it up needs
CAP_NET_ADMIN, which the unprivileged session must not
hold). The poll now reads `operstate`, which is always
readable and reports `up` only when the link is live, so
the tray honestly shows *present but down* on the joined
image. For the same reason the gate cannot induce a live
link flip (QMP `set_link` does not move operstate while
the interface is admin-down), so the up-state rendering is
covered by the shared draw path and the down-state
assertion, and is recorded here as not separately proven
in-guest.

## Acceptance (QEMU only; no hardware claims)

Joined image sha256
`5cb4009288911e5b9c39056d0c4857e1812477c75466559f08dd2e126633be9f`,
built from tip `04d5ec4`. Full regression sweep on this
image, every marker read from its gate log:

- Shell: `SYNVEIL_SHELL_QEMU_PASS` — including: demo task
  button icon (100 blue px); tray network present-but-down
  (34 danger px, no accent) with the update slot hidden (no
  agent on the joined image); menu icons (Terminal green,
  Demo blue); minimize/restore, menu launch, Start toggle,
  relock all intact. Captures 01–05 in this bundle are from
  this run.
- Joined baseline: `SYNVEIL_NATIVE_JOINED_QEMU_ENROLL_LOGIN_WESTON_PASS`
- Audit v2: `SYNVEIL_AUDIT_V2_NATIVE_PASS`
- Observe: `SYNVEIL_OBSERVE_QEMU_PASS` (result passed=true,
  attempt 1)
- A/B round trip: `SYNVEIL_AB_QEMU_PROOF_PASS` — scenarios
  S0–S7 (incl. S6b) all pass, zero gate violations, on a
  proof disk packaged from this lineage.
- Browser/files: `SYNVEIL_BROWSER_QEMU_PROOF_PASSED` —
  receipt `demonstrated: true`, on a proof disk rebuilt
  with the gate's own `--prepare-tls` fixture CA.

## Not proven / dropped, honestly

- Tray network **up** state in-guest (see above): the
  session cannot administratively raise the interface;
  rendering shares the asserted down-state code path.
- Tray update **pending/current** states in-guest: the
  joined image runs no A/B agent, so the gate asserts the
  slot hidden there; the pending/current rendering runs
  only where an agent answers (A/B images), which the A/B
  gate does not screenshot. The query, parse, and state
  mapping are the shipped code; the icon states are drawn
  by the same icon routine the gate does assert.
- The menu slide's timing is implemented to the 200 ms
  spec and visible in the captures' behaviour; the gate
  does not assert frame timing.
- Physical hardware: nothing in this bundle ran on the
  TG01; physical validation remains parked (ADR 0023).
