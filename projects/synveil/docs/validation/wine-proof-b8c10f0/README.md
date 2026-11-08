# Wine Proof Slice (Windows compatibility fallback lane)

Evidence for the first proof slice of the accepted Windows
compatibility design (`docs/WINDOWS_COMPAT_DESIGN.md`, owner
answers 2026-11-07): the sealed distribution Wine, staged by
the distro-staging route, runs Wine's bundled `notepad.exe`
on the S4 custom shell through `winewayland.drv` — no X11,
no XWayland (the design's hard gate: the stage build fails
if the winewayland pair is absent from the seal; it was
present).

## Source

- `8f502de` — `tools/distro_wine.py` +
  `tools/distro_wine_assets.py` +
  `build/manifests/distro-wine.json`: pinned snapshot
  (`20261024T000000Z`) closure of 195 packages, Wine
  `10.0~repack-6`; every .deb verified against the pin
  manifest and the snapshot Packages index; distro libc
  pruned (baseline glibc is used); manifest seal records
  `winewayland=present`.
- `30ecaf8` — `tools/native_wine.py` +
  `build/rootfs/wine-notepad`: proof image on the plain
  joined baseline (478 sealed assets overlaid, never
  replacing a differing baseline file); launcher runs the
  sealed Wine with `WINEPREFIX` on tmpfs, `WINEARCH=win64`,
  Gecko/Mono offers disabled (no downloads in the guest),
  graphics driver pinned to `wayland` in the fresh prefix.
- `b8c10f0` — the runtime module-set completion (below) and
  gate robustness (settled-frame task-button baseline,
  300 s notepad poll).

## What the first gate runs found (kept honest)

The import-only PE closure was necessary but not
sufficient. Wine launches a session ecosystem **by name**,
and a missing builtin DLL is silently replaced by an
all-stub placeholder whose exports abort as "unimplemented
function" when called (observed in-guest at
`shell32.dll.SHGetFolderPathW`, and on the host during
diagnosis at `newdev.dll.UpdateDriverForPlugAndPlayDevicesA`).
The completed module set adds: the name-launched session
programs (`start.exe`, `explorer.exe`, `conhost.exe`,
`winedevice.exe`, the `svchost.exe` hosts, `rundll32.exe`,
`winemenubuilder.exe`, …); export-forwarder following; the
`ServiceDll` set parsed from the pinned `wine.inf`;
`.drv`/`.sys` drivers walked for their own imports
(`ndis.sys` needs `iphlpapi.dll`); `apisetschema.dll`
(apiset loads failed `c000000f` without it); and the
out-of-tree `zlib1.dll` (Debian ships it via
`libz-mingw-w64`, not as a Wine builtin) placed in the
module directory by the stage and into the fresh prefix's
`system32` by the launcher — server-started processes
search only there. Final payload: 554 files / 305 MB.

One cosmetic line remains by design: during `wineboot`,
Wine attempts the 32-bit `syswow64\rundll32.exe`
registration and reports `c0000135` — the payload is
win64-only (see Not proven). It does not affect the session.

## Image

Proof image sha256
`d4bfb12ff6eb62c1c0abc963d5f65f79cacf263870893c557620a555e148206c`
(`out/wine-proof/`, 1,152 MiB, ESP 1024 MiB / state
128 MiB), carrying the sealed payload over the joined
baseline rootfs.

## Native gate: SYNVEIL_WINE_QEMU_PASS

`tests/smoke-native-wine.py`, run as `svrunner` with
TMPDIR on the workspace filesystem, **passed on attempt 1**.
The boot enrolls, logs in to the S4 shell, types the
launcher line into the terminal, and asserts from frames
and the state-partition readback:

- the Notepad client window appeared (edit-area rectangle
  731×498 at (513, 61)) — `notepad.png`;
- the panel task buttons increased 2 → 4 with the new
  window (Notepad's button visible and focused in both
  screenshots);
- the text `Synveil wine proof` typed through the input
  channel landed in the edit area (edit-rectangle pixel
  diff 536; the typed screenshot shows the text and the
  status bar at Ln 1, Col 19) — `notepad-typed.png`;
- the session was stopped cleanly (`wineserver -k`, session
  end, graphical login relocked);
- the recorded prefix path is on tmpfs
  (`/tmp/wineprefix.MoNnlX`); `wine.log` is empty
  (`WINEDEBUG=-all`, no errors emitted).

Receipt: `result.json` (schema
`synveil.wine-acceptance/v1`).

## Proven

- The sealed distribution Wine 10.0 (win64) executes on the
  joined native image under the S4 shell.
- A bundled Win32 GUI program (Notepad) renders through
  `winewayland.drv` as a managed window of the custom shell
  and takes keyboard input.
- A fresh prefix is created on tmpfs at launch; no network
  is used; nothing is downloaded in the guest.

## Not proven / not claimed

- No Direct3D or 3D of any kind (deferred to a separate
  Mesa/Vulkan payload decision, per the accepted design).
- No 32-bit (WoW64) execution — the i386 module tree is
  pruned; 32-bit registration noise during wineboot is
  expected.
- No prefix persistence (tmpfs by design; real prefix
  storage is tied to the storage roadmap).
- No Start-menu presence (later, marker-gated, per the
  owner answers).
- No third-party application, no performance claim, and
  no physical hardware validation (QEMU/TCG only).
