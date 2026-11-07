# S4 custom shell — QEMU acceptance evidence

Date: 2026-11-07. Authorization: ADR 0025 (owner authorized the
custom shell 2026-11-06, superseding ADR 0024's "not authorized"
clause for the shell only; boot chain, updater, and authentication
unchanged and frozen per ADR 0023). QEMU evidence only — no
physical hardware is claimed (`physical_hardware_tested: false`
in every receipt here).

## What was built

The pinned Weston 15.0.1 desktop shell is patched in place via the
project's carried-patch mechanism
(`build/native/patches/weston/weston-15.0.1-synveil-shell.patch`,
sha256 `be7dcd1978f312df239c268e309798606176893f3c229954d5f3768e980d04ea`):
the module stays `desktop-shell.so`; no weston.ini, Buildroot
config, or module-set changes; session startup (weston-session,
seat-lease) and authentication mechanics untouched. A private
protocol (`synveil_shell_panel`) is bound only for the shell's own
helper client; the shell publishes top-level windows and the
helper draws, in the ADR 0024 tokens (shell #202020, surface
#2C2C2C, surface-hi #383838, accent #4CC2FF):

- a 48 px bottom panel with an original four-pane Start glyph;
- real task buttons per open window (title text, active fill +
  accent underline; click toggles activate/minimize through the
  compositor's own paths);
- a Start menu (the panel surface grows a card region with stock
  mechanics) listing the apps the image actually carries. The
  menu has no session actions: the session machinery exposes no
  logout/lock to offer, and the no-fake-controls rule forbids
  drawing any;
- the stock clock, unchanged.

Menu gating follows the project's existing marker convention: on
the plain joined image the menu lists exactly **Terminal** and
**Demo window**; Files and Updates entries appear only where
their enablement markers exist (A/B generations), the same rule
that already governed those apps' session autostart. On those
images the apps are exercised by the A/B and browser proofs
below — including launching, focus, refresh, and close against
the new shell — and the Browser proof's menu-independent flows
(files window listing downloads) pass unchanged.

Motion is the stock fade/zoom springs plus a helper-side fade;
a compositor-level slide for map/minimize is not available in
stock Weston and remains a recorded gap (docs/UI_DESIGN.md).

## Acceptance — `tests/smoke-native-shell.py`

Marker: `SYNVEIL_SHELL_QEMU_PASS` on the joined image sha256
`a80e3266948066fb4c2b98c9c8e8843d5f34dd7f2b8cbb9bb6c5696c70fba737`
(built with git HEAD at the shell fix commit `d526e55`; the
stage receipt records the patch sha256 above).
`result.json` (schema `synveil.shell-acceptance/v1`) carries the
step notes; the screenshots are:

- `01-desktop.png` — desktop with the new panel: Start glyph,
  task buttons for the demo window and the terminal, clock.
- `02-demo-minimized.png` — after clicking the demo window's
  task button (window minimized).
- `03-demo-restored.png` — after a second click (window restored
  and marked active).
- `04-start-menu.png` — Start menu open with its app items.
- `05-menu-item-launch.png` — after clicking the Terminal item:
  menu closed, a new terminal window opened with its own task
  button.

The Start button also toggles the menu closed again, and the
session ends with the graphical login relocked.

Harness notes from the smoke's own development (all in the
smoke's source): the accent token reads back composited, so the
glyph check is hue-based; inactive task buttons are transparent
(title text sits directly on the panel), so buttons are located
by their text clusters and the demo's button is identified by
creation order; an unfocused terminal renders navy, which the
session-close sequence accounts for with paired close gestures.

## Regressions on the shell image set — all green

- Joined acceptance: `SYNVEIL_NATIVE_JOINED_QEMU_ENROLL_LOGIN_WESTON_PASS`
  on the same joined image (stock pixel heuristics unchanged).
- Durable audit v2: `SYNVEIL_AUDIT_V2_NATIVE_PASS` re-run against
  this image set (the accepted-format gate; see
  `docs/validation/audit-v2-7431121/`).
- A/B update round trip: `SYNVEIL_AB_QEMU_PROOF_PASS` — all nine
  scenarios on generations built from the new joined baseline
  (`ab-regression-receipt.json`, source commit `2f67f0d`,
  `gate_violations: []`). This also drives the updates GUI and
  the Files window against the new shell on a marker-carrying
  image.
- Browser/files proof: `SYNVEIL_BROWSER_QEMU_PROOF_PASSED`
  (`browser-proof-receipt.json`: `demonstrated: true`, gate
  failures empty). The disk was rebuilt for this pass (fresh
  distro-Chromium stage + `--browser` generations from the new
  baseline).

### Browser proof harness fix (tests-only, commit `e86b6b7`)

The first browser regression run failed with a misleading
cascade (B6/B7 update and digest gates). Root cause was in the
harness, not the guest: the browser smoke's `focus_terminal`
wrapper gave `ab.focus_terminal` a 20 s per-attempt budget —
exactly that function's GUI-free settle (20 s of continuous
update-GUI absence when the GUI was never seen), so a GUI-free
session could never focus; earlier passes had depended on a
stray GUI-rect detection flipping the settle to 3 s. In the
failed run the boot-2 reboot command's focus burned the full
240 s with the terminal topmost and active (the harness's
`browser2-cmd-reboot-focus.ppm` failure frame shows exactly
that), the guest never rebooted, and every later B6/B7 step ran
in the wrong session; the guest-side digest commands starved
identically in all three boots while the downloaded payload
bytes themselves verified from the readbacks. The A/B smoke
calls the same helper with a 240 s budget and passed
unaffected on the same images. The fix raises the wrapper's
per-attempt budget to 60 s; no guest code changed, and the
re-run passed end to end (trial boot `HEALTH_PASSED`, payload2
download in the trial session, generation 2 confirmed, then
rolled back with payload persistence proven).

Environment notes: this pass's builds and smokes were
interrupted twice by VM replacements and re-run; QEMU smokes
here run unprivileged as the harness user with `TMPDIR` on a
short path (the A/B socket-path limit found in the audit pass
applies to this harness family too). The distro-Chromium stage
rebuild printed Debian snapshot GPG warnings in this
environment; the stage's own payload manifest verification
completed and its success marker issued.
