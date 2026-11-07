# Windows compatibility (Wine) — design & feasibility proposal

Status: **Proposal (2026-11-07). Not accepted.** Owner
direction (2026-11-06): "If you run out of things you can
try getting the windows game compatibility built in." This
document is the design + feasibility pass for that lane.
No ADR or doc in the project records a prior compatibility
decision; nothing here conflicts with one, and nothing
here is implemented or authorizes code. All work would be
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

## First proof slice (if accepted)

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

## Open questions for the owner

1. Accept the distro-staging route for Wine (vs holding
   out for a from-source build)?
2. Accept the GDI-first scope — bundled/classic Win32
   programs first, Direct3D only after a Mesa/Vulkan
   payload decision?
3. Where should prefixes live once persistence exists —
   tied to the storage roadmap, or a dedicated data area
   designed with this lane?
4. Is a Start-menu presence wanted at all in the first
   product slice, or terminal-launched only?
