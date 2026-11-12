# Mesa/Vulkan Graphics Payload (ADR 0027)

Evidence for the graphics-staging slice: the Mesa +
Vulkan software stack, staged by the distro route under
the owner's 2026-11-07 decision (ADR 0027, option (a) of
`docs/WINDOWS_COMPAT_DESIGN.md`'s Graphics path), woven
into the Wine proof image, and proven to **initialize in
the guest** — Vulkan on lavapipe, GL/EGL on llvmpipe.
This is the prerequisite payload for any future Direct3D
slice; it is not itself a Direct3D proof.

## Source

- `e6ea9fc` — `tools/distro_graphics.py` +
  `tools/distro_graphics_assets.py` +
  `build/manifests/distro-graphics.json` +
  ADR 0027: pinned snapshot (`20261024T000000Z`, trixie)
  closure of 54 packages; every .deb sha256-verified
  against the pin manifest and the snapshot index; distro
  libc pruned (baseline glibc is used); the seal keeps the
  distribution layout and the stage build FAILS unless
  lavapipe and the Mesa GL vendor stack are in the seal.
- `3015ef6` — `tools/native_wine.py` (graphics weave +
  marker + receipt block), `src/graphics-probe/gfx-probe.c`
  (guest initialization probe), `tools/qmp_input.py`
  (`gfx-probe` command), `tests/smoke-native-wine.py`
  (probe phase + assertions in the Wine gate).

## Staged payload

Stage marker `SYNVEIL_DISTRO_GRAPHICS_STAGED_NOT_BOOTED`
(`stage-validation.json`): **97 files, 220,473,743 bytes
(~210 MiB)**, from 54 pinned packages:

- Vulkan loader `libvulkan1` 1.4.309.1-1 and Mesa
  25.0.7-2+deb13u1 (`mesa-vulkan-drivers`,
  `libgl1-mesa-dri`, `libglx-mesa0`, `libegl-mesa0`,
  GLVND 1.7.0 dispatchers, `mesa-libgallium`, LLVM 19 —
  most of the bytes — `libdrm2`, X11/xcb client libs).
- **Vulkan ICDs: lavapipe only.** Every hardware ICD
  (Intel, Radeon, Nouveau, virtio, gfxstream) is pruned
  with its loader JSON.
- **GL entry points: swrast + kms_swrast only.** Mesa
  25's gallium is one unified library (`libgallium`,
  entered via the `libdril` shim) and cannot be split by
  driver, so it is sealed whole; no GPU exists in the
  guest for any other driver to bind.
- Loader data sealed: `lvp_icd.json` (lavapipe), the
  GLVND EGL vendor JSON (`50_mesa.json`), Mesa's drirc
  defaults.

## Images

- Wine proof image sha256
  `6c74bec9f6917019db05a530f1565a8b2ec48fd38f07e9cd29121a7006314c92`
  (1,152 MiB), source commit `3015ef6`: the graphics
  weave copied 61 sealed files over the baseline, found
  36 byte-identical to files the baseline already owned,
  and link-checked 29 graphics ELFs against the merged
  baseline+payload tree (`image-validation.json`,
  `graphics` block). Guest marker: `/etc/synveil/graphics`;
  probe: `/usr/libexec/synveil/gfx-probe`.
- Joined baseline rebuilt from the same commit, sha256
  `c7d48cbff31b052e01cdfd444fa65e7d9a02e287013f4a8dbfcb3e089dc0b012`
  (`joined-validation.json`) — its source content is
  unchanged by this slice (no `src/` or joined-builder
  change); it was rebuilt because image identity binds to
  the commit.

## Gates (all run as `svrunner`, QEMU/TCG)

- Joined baseline acceptance:
  `SYNVEIL_NATIVE_JOINED_QEMU_ENROLL_LOGIN_WESTON_PASS`
- S4 shell acceptance on the joined image:
  `SYNVEIL_SHELL_QEMU_PASS`
- Wine + graphics acceptance:
  `SYNVEIL_WINE_QEMU_PASS`, **passed on attempt 1** —
  Notepad rendered and took typed text (pixel diff 550)
  exactly as in the GDI-only proof, then the in-guest
  probe ran and its report was read back off the state
  partition. Receipt: `result.json` (schema
  `synveil.wine-acceptance/v1`, `graphics` block).

## Probe report (in-guest, firsthand)

```text
GFX_VULKAN_DEVICE 0 "llvmpipe (LLVM 19.1.7, 128 bits)" type=4 api=1.4.305
GFX_VULKAN_OK devices=1
GFX_EGL_OK vendor="Mesa Project" version="1.5"
GFX_GL_OK vendor="Mesa" renderer="llvmpipe (LLVM 19.1.7, 128 bits)" version="4.5 (Compatibility Profile) Mesa 25.0.7-2+deb13u1"
GFX_PROBE_OK
```

The probe creates a real Vulkan instance and enumerates
the lavapipe device, and creates a real EGL context on
Mesa's surfaceless platform with a llvmpipe GL renderer —
initialization, not merely file presence.

## Proven

- The sealed Mesa/Vulkan payload is present and
  byte-verified in the proof image.
- Vulkan (lavapipe, API 1.4.305) and OpenGL 4.5 / EGL 1.5
  (llvmpipe) initialize in the guest under QEMU/TCG.
- The existing joined desktop and Wine GDI behaviour is
  unregressed with the payload woven in.

## Not proven / not claimed

- No Direct3D: DXVK / vkd3d-proton are **not** staged —
  this payload is their prerequisite, not their proof.
- No game or 3D workload of any kind was run.
- No real-GPU behaviour or performance: everything above
  is CPU software rendering under QEMU/TCG.
- No 32-bit graphics stack (the payload is x86_64 only).
- No physical hardware validation (TG01 untested; ADR
  0023 park unchanged). The A/B update gate was not
  re-run: this slice changes no joined-image source (the
  frozen boot/update mechanisms are untouched) and is a
  payload change to the proof image only, validated by
  the joined + shell + Wine gates above.
