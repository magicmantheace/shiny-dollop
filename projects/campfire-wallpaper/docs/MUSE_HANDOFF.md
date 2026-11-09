# Handoff — Campfire Companions

**State (2026-11-08): initial build complete on branch
`campfire-wallpaper/initial-build`, draft PR open, NOT merged, NOT
deployed to the owner's PC.** Deployment (installing Lively and
adding the wallpaper) is a later step done with the owner.

## What it is

A Lively Wallpaper (web type) live desktop background: a field at
dusk where Game Asset Builder creatures wander in, gather around a
campfire, and wander off. Entry point `index.html`; scene and
creature director in `js/wallpaper.js`; no build step, no runtime
network access, three.js r180 vendored in `vendor/three/`
(`three.module.js` + `three.core.js` — r180 splits its build — plus
the `GLTFLoader`, `BufferGeometryUtils` and `SkeletonUtils` addons).

## Assets (copied verbatim from the Game Asset Builder catalog)

| File | Bytes | sha256 | Clips |
| --- | --- | --- | --- |
| ember-dragon.glb | 20,671,744 | `2837c6b2969f0bf628314b19c8230c92fb3bc8480b045f8462bd1f1540ef6bb2` | hop, idle, run, walk |
| snow-goblin.glb | 22,227,900 | `c4ba135bcb26a85dde5012b367dd7c5417c99ba8a3ee60dbc1fe51a985721670` | idle, run, walk, wave |
| triceratops.glb | 20,330,868 | `39b5f934eb2e1943a11208c43141fcb99ab49606812d1003bfba4d9b8eb3acc6` | bounce, idle, run, walk |
| treasure-chest.glb | 11,249,652 | `2b6e51cc0d8273e318e6e2dad64d8b03cc0c3da029fe132463055f1b060125b1` | — (static) |

Assets total 74,480,164 bytes; whole project ≈ 76.7 MB.

**History worth knowing:** the build started with the pre-P4 GLBs
(idle + signature only). Mid-build, the Game Asset Builder's P4
animation slice landed (branch `game-asset-builder/p4-game-animations`,
tip `57fab45`) and regenerated the catalog with walk + run clips;
the three creature GLBs were re-copied from the regenerated outputs
and the hashes above are the post-P4 ones. The chest is unchanged.

## Director behaviour (as built)

- Max 3 concurrent creatures; 5 fire spots on the camera side of
  the fire, never double-booked.
- Travel clip: `walk` when the GLB provides one (all three do);
  fallback per-creature gait from the signature clip (dragon hop /
  trike bounce surge-and-lift synced to the clip cycle; goblin
  glides on idle).
- Dwell 16–42 s on idle; signature clip (hop/wave/bounce) plays
  once every 7–16 s; then the creature walks to a random edge and
  despawns. Respawn cadence 6–14 s (2.5 s if the field is empty).
- The scene opens mid-moment: one creature already dwelling, one
  walking in from mid-field.
- Models are auto-normalized at load (bounding-box height →
  per-creature target height, feet at y=0), so future GAB exports
  at other scales drop in safely.
- Wallpaper manners: pixel ratio ≤ 1.5, ~136 fire particles, blob
  shadows (no shadow maps), render loop fully stopped while the
  page is hidden.

## Verification (see docs/TEST_PLAN.md for the full record)

Headless Chromium (Chrome-for-Testing headless shell 157,
SwiftShader) on the build VM, CDP-driven, serving the shipped
folder over HTTP:

- All templates load, no console errors, scene renders with fire,
  glow, chest, and creatures at their spots.
- The entering creature's status reports clip `"walk"` — the P4
  walk preference engages with the shipped GLBs.
- Proof of life via the page's `?harness=1` step seam
  (`window.__campfireStep(steps, dt)` — deterministic fixed-step
  simulation, harness-only; Lively never passes the flag): a goblin
  photographed at the field's edge is photographed at its fire
  spot 420 steps (14 scene-seconds) later, beside the dwelling
  triceratops.
- Not directly observed in the VM runs: leave/despawn and a
  signature clip firing (observation windows were short; recorded
  honestly in TEST_PLAN). Real-GPU frame rate is unverified —
  SwiftShader numbers on the shared VM are a floor distorted by
  the dt cap, not a measurement of the owner's RTX 3060.

Screenshots live outside the repo in the build worktree:
`~/workspace/_build-wallpaper-verification/shot-a.png` /
`shot-b.png` (the stepped proof-of-life pair). `preview.jpg` in
the project is a downscaled shot B, used as the Lively thumbnail.

## Harness notes for the next verifier

- This VM's bundled Chromium (`/opt/meta-chromium/chrome`) is the
  Muse browser and refuses scripted launch ("Hatch WebGL domain
  policy is required") — use a Chrome-for-Testing headless shell.
- Node on this VM honours the egress proxy env
  (`NODE_USE_ENV_PROXY=1`); the CDP driver must clear proxy vars
  or loopback DevTools calls vanish into the proxy.
- Headless Chromium composites frames only on demand; expect
  ~0.5–3 s per software frame of this scene on a busy VM. Use the
  `?harness=1` step seam for behaviour checks and treat fps
  readings as artifacts.
- The reference driver used for this build is in
  `~/workspace/_build-wallpaper-verification/run_verify.mjs`.

## Next steps (not done here)

1. Owner deploys with assistance: install Lively on the PC, add
   this folder, set the wallpaper. (UAC warning applies to the
   Lively installer step.)
2. Possible v2: Lively properties (creature toggles, fire size),
   the commissioned weird-roster creatures as the GAB makes them
   (drop-in: new GLB + one config row in `CREATURES`).
