# UI redesign validation — 2026-11-05

Slices S1–S3 of the ADR 0024 Windows 11 redesign (see `docs/UI_DESIGN.md`).
All dynamic evidence is **QEMU-scoped** (TCG emulation on the build VM);
no physical validation is claimed for anything in this folder
(ADR 0023 keeps physical parked).

## S1 — veil-display reskin

- Source revision: `814aec8` (code), host frames committed at `37e2640`;
  the joined image below was built from `37e2640`.
- Scope: `src/veil-display/src/main.c` rendering only, plus the new
  checked-in glyph atlas `src/veil-display/ui_font_data.h` and its
  generator `tools/generate_ui_font.py`. No authentication logic,
  credential handling, enrollment step order/semantics/wording, seat
  protocol, or input semantics changed; every pre-existing UI string is
  byte-identical. The one new string is the owner-name label "Synveil"
  on the login composition.

### Host verification

- `gcc -O2 -std=c11 -Wall -Wextra -Werror` clean; `--self-test` passes
  (includes the new atlas-decode, text-metric and easing checks and the
  updated click-geometry checks).
- `tests.display-build`: 10 tests OK. `native-rootfs`,
  `graphical-login-fixture`, `desktop-marker-policy` suites OK.
- Full Rust suite: **cargo test 182 passed, 0 failed** (baseline held).
- Host-rendered before/after frames (`s1-before-*` / `s1-after-*` in
  this folder) were produced by driving the real `main.c` renderer
  against a software framebuffer at 1024x768, old frames from the
  pre-change source and new frames from `814aec8`, and visually
  inspected: login, typed login, denied, enrollment, dashboard home,
  status, files, terminal page, settings, and a mid-transition frame.
- **Motion level shipped: level 1** (full 280 ms ease-out slide). The
  host driver printed `SYNVEIL_UI_MOTION_LEVEL 1` at the transition;
  the sticky degradation ladder (half-slide + crossfade, then
  crossfade-only) is implemented per the spec's full-screen cost rule
  and engages automatically when frames run slow. `UI_MOTION=0`
  disables client sliding. In-guest transition timing under TCG was
  not separately measured.

### Joined-image QEMU acceptance

- Image: `tools/native_joined.py --build` (boot target qemu), image
  sha256 `a3b0e7057980d5fdad07b26f7ecc7c9595c60e5e5715df8045830e709657cfc9`.
- `tests/smoke-native-joined.py` (non-root runner, TCG, per-boot
  timeout raised to 1200 s for emulation speed):
  **`SYNVEIL_NATIVE_JOINED_QEMU_ENROLL_LOGIN_WESTON_PASS`** —
  `out/native-joined/guest-validation.json` records
  `source_commit 37e264060e2392182da95b645542f9cce4e116de` with
  graphical enrollment, mismatched-confirmation rejection,
  wrong-password denial after cold reboot, Weston desktop after login,
  pointer move/resize/keyboard exercise, session-end relock, and
  `physical_hardware_tested: false`.
- QEMU frames in this folder (`s1-qemu-*`) come from a separate
  QMP-driven boot of a private copy of the same image with a synthetic
  test account: enrollment, enrollment confirm, login, login denied
  ("LOGIN DENIED" under the field; the 200 ms shake had settled before
  the still was taken), and the post-login Weston desktop (pre-S2/S3
  client and panel appearance, kept as the baseline for those slices).

### Deviations

- **Font:** Selawik is not shipped. It is not part of any tree the
  project pins, and fetching it would put an unpinned artifact in the
  build, so the spec's DejaVu Sans fallback ships instead, rasterized
  from the Buildroot target tree's DejaVu faces (input SHA-256s are
  recorded in `ui_font_data.h`) at the spec's sizes with the spec's
  layout metrics.
- **Build environment (not a product change):** this VM lacked several
  host build tools (cpio, zstd, bc, sgdisk, mtools, dosfstools, gawk,
  libelf headers, QEMU/OVMF). The artifacts were produced with the
  distro's own binaries extracted under `~/host-tools` plus small
  verified shims (the python cpio writer and bc interpreter reproduce
  the reference outputs byte-for-byte; bc's output was diffed against
  the seed-generated `timeconst.h`). Nothing under `~/host-tools` is
  part of the product tree.

## S2 — desktop clients reskin

Source revision: `0cb95fa` (clients + harness pixel identity), plus
three locator-only harness fixes found by the round trip below
(`60dfa96`, `592dc62`, `1ca7aff`; no client code changed after
`0cb95fa`, and no semantic gate changed anywhere).

What was exercised:

- All three clients compile clean with the build's exact flags
  (`-std=c11 -Wall -Wextra -Werror`). Host suites: smoke-gates 30 OK,
  native-first-window 5, first-window-probe 7, native-weston 4,
  qmp-input 16, graphical-login-fixture 14, graphical-onboard-fixture
  14, desktop-marker-policy 3. Rust suite unchanged: 182 passed.
- **Update round trip (QEMU, TCG): PASS.**
  `tests/smoke-native-ab-gui.py` against the A/B proof images built
  from `0cb95fa` (disk sha256
  `c7a5561d9ebd451933c15e2b46b1a6a175db3037486040c91ec757022f6d3fa5`):
  G0 provision/enroll/GUI-present PASS, G1 GUI stage → restart →
  trial boot → confirm PASS, G2 GUI rollback → confirm PASS,
  G3 bad-signature media refused PASS —
  `SYNVEIL_AB_GUI_QEMU_PROOF_PASS`, receipt at
  `out/ab-proof/gui-smoke-receipt.json`. Every action was driven by
  pointer clicks on the reskinned window; the five actions, their
  order, confirmations and audit wording are byte-identical to
  before (presentation-only diff).
- **Joined acceptance (QEMU, TCG): PASS** —
  `SYNVEIL_NATIVE_JOINED_QEMU_ENROLL_LOGIN_WESTON_PASS` against the
  joined image rebuilt from the same revision.
- Screenshots in this folder: `s2-qemu-updates-window.png` (updates
  window on the confirmed generation, update media attached) and
  `s2-qemu-updates-staged.png` (staged banner, Restart enabled) —
  real guest frames from a diagnostic boot of the A/B image; the
  first window (gradient body, glyph title bar) and terminal are
  visible behind the updates window in both.
- Not run: `tests/smoke-native-browser.py` (the files window's
  end-to-end QEMU exercise) needs its own TLS-fixture proof disk
  (`tools/native_ab.py --build --browser …`), a separate multi-hour
  build that was not practical in this run. The files window is
  covered by the host build, the updated harness identity constants
  (title block `0x345160`, button geometry unchanged), and the
  joined session, in which `synveil-files` is marker-gated off (it
  runs on A/B generations; `build/rootfs/weston-session`). Its
  reskin shares the S2 chrome code pattern verified in the frames
  above. This acceptance remains unrun and is stated as such.

Deviations and findings:

- **No minimize button on any client** (spec caption order lists
  min/max/close "real behavior only"): Weston desktop-shell has no
  in-session minimize/restore affordance for these surfaces, so no
  minimize glyph is drawn. Maximize is drawn only where real
  (files window, first window — both exercise
  set/unset_maximized); the updates window has none (its max size
  equals its initial 720×520).
- **First window's title is glyph-only**: it has no title string of
  record, so its title bar carries the app glyph and caption glyphs
  only — no new text was invented.
- **Launcher icon recolor** (`tools/native_ab.py`): the generated
  browser launcher icon's field color follows the files window's
  new title identity (`0x345160`, white disc) so the smoke's icon
  probe still matches the window it launches.
- **Locator fixes (harness, not product):** the round trip's first
  runs failed in the *locator*, not the client — root-caused from
  captured guest frames each time: (1) `gui_window_rect` measured
  window height by walking a pixel column at `start+2`, which now
  lands on the accent app glyph, truncating the height to 10 px and
  putting every derived button click above the window; the probe
  column moved to `start+w-4`. (2) The banner sampler's single
  centre point is crossed by the 20 px banner head's glyphs;
  (3) a single point at either end can be covered by a neighbouring
  window. The banner check now classifies by the band row (≥200 px
  of one banner kind). All pass/fail semantics — click markers in
  the GUI's own log, banner state sequence, confirmed generation,
  strict survival — are unchanged.
- Two G0 failures during the runs were the harness's documented
  window-find flake under host CPU contention (in one, the GUI's
  own log proved it had started while no frame showed it
  uncovered); the passing run above is on a quiet host.
- The em-dash in banner head strings ("Update staged — restart to
  try it") renders as a gap: the pinned DejaVu atlas covers ASCII
  32–126 (see S1), and the string itself is unchanged. Pre-S2 the
  5×7 font had the same coverage limit.

## S3 — weston.ini presentation

Pending.
