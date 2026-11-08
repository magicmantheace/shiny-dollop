# ADR 0027: Mesa/Vulkan graphics payload — distro-staged software stack

- Status: Accepted
- Date: 2026-11-07
- Supersedes: none
- Superseded by: none
- Related: [ADR 0023](0023-physical-validation-parked-boot-update-freeze.md)
  (boot/update freeze; this work is userspace payload through
  the existing image mechanisms and stays outside the frozen
  zones), `docs/WINDOWS_COMPAT_DESIGN.md` (the accepted Wine
  design whose Graphics path posed this decision).

## Context

The Wine proof slice (WINDOWS_COMPAT_DESIGN, owner-accepted
2026-11-07) demonstrated a Win32 GDI program running on
Synveil, and deliberately stopped there: the rootfs ships
**no Mesa, no libGL/libEGL implementation, no Vulkan loader
or ICD**, so the Direct3D path (DXVK / vkd3d-proton, which
require Vulkan) was impossible and was left to "a separate
payload decision". The design named the honest options:
(a) stage Mesa with lavapipe (software Vulkan) via the same
distro route as Wine/Chromium, or (b) grow Mesa in the
Buildroot weston stage, at a ~100 MB-class size cost — and
recorded that under QEMU/TCG any of it is software-rendered:
it would prove the layer *works*, never real game
performance.

On 2026-11-07 the owner made that decision ("3A" in the
evening's decision list): **stage the graphics stack now**,
following the Wine proof's staging pattern.

## Decision

1. **Distro-staging route (option (a)).** A new stage,
   `tools/distro_graphics.py`, resolves the Mesa + Vulkan
   closure from the same pinned Debian snapshot
   (20261024T000000Z, trixie) the Wine and Chromium stages
   use, verifies every .deb against the snapshot index and
   the committed pin manifest
   (`build/manifests/distro-graphics.json`), prunes to the
   real payload, and seals it
   (`tools/distro_graphics_assets.py`). No from-source Mesa
   build (option (b) stays unchosen, as it was for Wine),
   and no download ever happens inside the guest.
2. **Software rendering only.** The payload is the QEMU/TCG
   software stack: the Vulkan loader (1.4.309) plus Mesa
   25.0.7's **lavapipe** ICD, and the GLVND dispatchers plus
   Mesa's vendor libraries serving **llvmpipe** through the
   swrast / kms_swrast gallium entry points. Hardware Vulkan
   ICDs are pruned with their loader JSONs. Mesa 25's
   gallium is a single unified library (`libgallium`,
   entered through one dril shim) and cannot be split by
   driver, so it is sealed whole; only the software entry
   points are sealed with it, and no GPU exists in the
   guest for any other driver to bind.
3. **Payload discipline is the established one.** The seal
   keeps the distribution layout (multiarch paths intact),
   the distribution libc is pruned (the image runs the
   project's own glibc), and image builders copy only
   sealed, byte-verified files, never replacing a differing
   baseline file. The stage build FAILS if lavapipe or the
   Mesa GL vendor stack is absent from the seal
   (`SYNVEIL_DISTRO_GRAPHICS_STAGED_NOT_BOOTED` is the
   staging marker).
4. **First consumer is the Wine proof image.** The graphics
   payload is woven into the Wine proof image
   (`tools/native_wine.py`), which gains the marker
   `/etc/synveil/graphics` and a guest probe
   (`/usr/libexec/synveil/gfx-probe`, from
   `src/graphics-probe/gfx-probe.c`) that initializes
   Vulkan (lavapipe device enumerated) and EGL/GL
   (surfaceless platform, llvmpipe renderer) and reports
   `GFX_*` lines. The Wine QEMU gate asserts the probe
   report alongside the Notepad proof.

## What this does and does not prove

Staging + the QEMU gate prove: the payload is present,
byte-verified, and **Vulkan and GL initialize in the guest**
on the software drivers, and the existing desktop/Wine
behaviour is unregressed. They do **not** prove Direct3D
(DXVK/vkd3d are not staged — this payload is their
prerequisite, not their proof), any game, 32-bit support,
persistent prefixes (still tied to the storage roadmap),
or real-GPU behaviour or performance of any kind.
Physical (TG01) validation remains parked under ADR 0023;
all claims here are QEMU-scoped.

## Consequences

- Sealed payload: 97 files, ~210 MB (LLVM 19 for llvmpipe
  is most of it) on top of the Wine proof image.
- A future Direct3D slice can now be scoped honestly:
  stage DXVK/vkd3d against this payload and prove a D3D
  program, with performance still owner-hardware territory.
- If a hardware graphics stack is ever wanted, it is a new
  decision (hardware ICDs, kernel DRM on real hardware,
  physical validation unparked) — nothing here pre-empts it.
