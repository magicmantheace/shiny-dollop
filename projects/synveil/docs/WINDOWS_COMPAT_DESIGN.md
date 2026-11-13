# Windows compatibility (Wine) — design & feasibility

Status: **Accepted (2026-11-07).** Owner
direction (2026-11-06): "If you run out of things you can
try getting the windows game compatibility built in." This
document is the design + feasibility pass for that lane,
accepted by the owner on 2026-11-07 with the answers
recorded under "Owner answers" below; the first proof
slice it scopes is authorized by that acceptance.
No ADR or doc in the project records a prior compatibility
decision; nothing here conflicts with one. All work is
userspace payload through the existing image mechanisms —
no frozen-zone (ADR 0023) changes are needed for the
scoped first slice, and none are proposed.

## Verdict up front

**Feasible for a first proof slice, with a hard scope
line:** Wine running 64-bit GDI-class Windows programs on
the Wayland session is achievable with the project's
existing payload machinery. Direct3D games are **not**
in the first slice: the rootfs ships no Mesa/Vulkan at
all today, so the DXVK/vkd3d path needs a graphics-stack
payload decision first (see Graphics).

## Facts established from the tree (2026-11-07)

- **Architecture**: the rootfs is x86_64 with the project's
  own glibc **2.44**. No emulation layer is needed for x86
  Windows binaries under Wine (Wine is a translator, not
  an emulator, on same-arch).
- **Payload precedent**: `tools/distro_chromium.py` already
  stages a large Debian application suite (217 .debs,
  ~468 MB for Chromium) from a pinned snapshot.debian.org
  snapshot: apt closure resolution, per-package hash/size
  verification against the snapshot index, extraction with
  pruning (the payload runs the project's own glibc, not
  Debian's), and a sealed manifest. Debian trixie's glibc
  is older than 2.44, so Debian-built Wine binaries are
  symbol-compatible with the shipped libc.
- **Kernel**: in-tree kernel builds carry
  `CONFIG_IA32_EMULATION=y` (seen in built configs; the
  frozen kernel fragment does not touch it), so 32-bit
  Windows binaries are not kernel-blocked. They are
  payload-blocked (an i386 library closure roughly doubles
  the payload) and are excluded from slice 1 by scope, not
  by feasibility.
- **Session**: pure Wayland (custom S4 shell on Weston,
  pixman rendering). There is no X server / XWayland in the
  stack, so Wine must use its native Wayland driver
  (`winewayland.drv`, the default driver in Wine 10 for
  Wayland sessions) rather than the X11 driver.
- **Graphics**: the rootfs contains **no Mesa, no libGL /
  libEGL implementation, no Vulkan loader or ICD** (only
  libwayland-egl). Weston composites with pixman.
- **Storage**: the state partition is 128 MiB by design —
  far too small for Wine prefixes or games. The joined
  image's /home is not persistent.

## Design

### Wine build / staging

Follow the Chromium precedent exactly: a
`tools/distro_wine.py` stage that resolves the Debian
trixie **wine64** closure (`wine`, `wine64`, `libwine`
and dependencies) from the pinned snapshot, verifies every
.deb, prunes distro libc out of the payload, and seals a
manifest. Building Wine from source with the Synveil
toolchain (the Weston pattern) was considered and
rejected for slice 1: Wine's build needs a large host
dependency set the Buildroot stage does not have, for no
proven benefit over the sealed-distro route the project
already trusts for Chromium.

To be confirmed at stage time from the sealed manifest:
that Debian's libwine ships `winewayland.drv` (trixie's
Wine 10 builds the Wayland driver; the manifest makes this
checkable rather than assumed).

### Graphics path

- **Slice 1 (GDI)**: Wine's Wayland driver presents GDI
  windows as shared-memory Wayland surfaces; classic Win32
  programs (including Wine's bundled tools) need no GL.
  This works against the pixman compositor as-is.
- **Later (Direct3D)**: DXVK / vkd3d-proton require
  Vulkan. Nothing in the current rootfs provides it. The
  honest options are (a) stage Mesa with lavapipe (software
  Vulkan) via the same distro route, or (b) grow Mesa in
  the Buildroot weston stage. Either is a separate payload
  decision with its own size cost (~100 MB class). Under
  QEMU/TCG any of this is software-rendered: it would
  prove the layer *works*, never real game performance —
  performance is owner-hardware territory and stays
  labelled unverified, the same line the browser proof
  draws.
  **Decision made 2026-11-07 (ADR 0027): option (a).** The
  owner directed the graphics stack be staged via the
  distro route — `tools/distro_graphics.py` seals Mesa
  25.0.7 (lavapipe + llvmpipe) from the same pinned
  snapshot as Wine, woven into the Wine proof image with a
  guest initialization probe. See "Graphics staging
  outcome" below.

### Install / launch model

- Slice 1 launches from the session like the other proof
  apps: a launcher runs the sealed Wine with
  `WINEPREFIX` set (see storage), `WINEARCH=win64`, and
  Gecko/Mono offers disabled (no downloads in the guest).
- Product direction (later slice): an ADR 0025
  marker-gated Start-menu entry ("Windows" or per-app
  entries) following the exact pattern Files/Updates use,
  plus per-app launchers generated when a program is
  installed into a prefix. No shell change is needed for
  slice 1, and none is proposed here.
- **No Steam, no storefronts, no credentials, no library
  downloads** — in the proof or the product direction.
  Programs arrive as files the owner supplies.

### Storage / prefix model

- Slice 1 (proof): the prefix lives on **tmpfs** in the
  guest (RAM-backed; a minimal win64 prefix without
  Mono/Gecko fits) and vanishes at shutdown. That is
  honest for a proof and useless for real use — labelled
  as such.
- Product direction: one prefix per Windows program (the
  Bottles/Proton convention) under a per-user data area.
  Synveil has no such area yet — the state partition is
  128 MiB and homes are not persistent in the joined
  image — so a real prefix store waits on the parked
  installer/storage roadmap. This is an open question
  below, not something this lane should invent alone.

## First proof slice (authorized by the acceptance)

1. `tools/distro_wine.py --build` seals the wine64 payload
   (manifest records whether `winewayland.drv` is present;
   if it is not, the slice stops and reports — the X11
   fallback would need XWayland, a bigger decision).
2. An AB-style proof image (the `native_browser.py`
   pattern) carries the payload; a QEMU acceptance in the
   established style boots, logs in, and launches **Wine's
   own bundled `notepad.exe`** — a real Win32 PE program
   shipped inside the wine packages themselves, so the
   proof needs no downloads and no third-party binary.
   Screenshots under `docs/validation/` show the Notepad
   window open on the S4 desktop and text typed into it;
   the task button reflects it like any other window.
3. Docs record precisely what was proven (Wine runs,
   a Win32 GUI program renders and takes input under the
   custom shell) and what was not (no 3D, no 32-bit, no
   persistence, no performance claim).

Estimated size: the wine64 closure is expected in the
150–350 MB class sealed; the stage + weave + gate work is
comparable to the browser proof pass.

## Owner answers (2026-11-07)

The questions this proposal posed, and the owner's
answers, verbatim in substance:

1. **Distro-staging route: accepted.** Wine is staged from
   the pinned Debian snapshot exactly like Chromium, not
   built from source.
2. **GDI-first scope: accepted.** Bundled/classic Win32
   programs first; Direct3D only after a separate
   Mesa/Vulkan payload decision, which this acceptance
   does not make.
3. **Prefix storage: tied to the storage roadmap.** Proof
   prefixes live on tmpfs and vanish at shutdown; a real
   prefix store is designed with the parked
   installer/storage roadmap, not invented by this lane.
4. **Start-menu presence: later, marker-gated.** No
   Start-menu entry in the proof slice; a marker-gated
   entry following the Files/Updates pattern belongs to a
   later product slice.

## Proof outcome (2026-11-08)

The first proof slice above is **demonstrated at QEMU
scope**: `SYNVEIL_WINE_QEMU_PASS` on the proof image
(sha256 `d4bfb12f…8206c`), evidence in
`docs/validation/wine-proof-b8c10f0/`. The sealed Wine
10.0 (win64) ran its bundled Notepad through
`winewayland.drv` on the S4 shell with a fresh tmpfs
prefix, rendered as a managed window, and accepted typed
input. One build lesson is recorded in the evidence: an
import-only PE closure is insufficient — the session's
by-name programs, the wine.inf ServiceDll set, driver
imports, `apisetschema.dll` and the out-of-tree
`zlib1.dll` are all part of the runtime module set.
Everything outside the proof's scope stays as the owner
answers left it: Direct3D awaits its own Mesa/Vulkan
decision, prefix persistence stays tied to the storage
roadmap, Start-menu presence is a later marker-gated
slice, and 32-bit support is not claimed.

## Graphics staging outcome (2026-11-08, ADR 0027)

The graphics decision was made the same evening
(2026-11-07, ADR 0027) and executed on branch
`synveil/mesa-vulkan-staging`: `tools/distro_graphics.py`
seals Mesa 25.0.7 + the Vulkan loader from the same
pinned snapshot as Wine (54 packages; 97 payload files,
~210 MiB; **lavapipe the only Vulkan ICD**, swrast /
kms_swrast the only GL entry points — Mesa 25's gallium
is one unified library and is sealed whole), woven into
the Wine proof image (sha256 `6c74bec9…4c92`, source
`3015ef6`) with an in-guest initialization probe. The
Wine gate (`SYNVEIL_WINE_QEMU_PASS`, attempt 1) now
also proves the probe report read back off the state
partition: Vulkan device "llvmpipe (LLVM 19.1.7,
128 bits)", API 1.4.305; EGL 1.5 (Mesa Project);
OpenGL 4.5 Compatibility on llvmpipe, Mesa 25.0.7.
The joined and shell gates stayed green on the same
source. Evidence: `docs/validation/graphics-3015ef6/`.

Proven: the payload is present and **Vulkan/GL
initialize in the guest** (software rendering). Still
not proven: Direct3D (DXVK/vkd3d not staged — this is
their prerequisite), any game, real-GPU behaviour or
performance, physical hardware.
