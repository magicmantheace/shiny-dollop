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

Pending.

## S3 — weston.ini presentation

Pending.
