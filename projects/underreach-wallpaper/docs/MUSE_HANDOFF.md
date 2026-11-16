# Underreach Wallpaper — handoff

## Status

- **v1 built and verified on the build VM (2026-11-16). NOT
  deployed.** Deployment to Lively on the owner's PC is a later
  step that needs the owner's go (the PC was busy with ComfyUI +
  a Synveil test; the Game Asset Builder queue pause was left
  untouched, as ordered).
- Branch: `underreach-wallpaper/v1`. Project folder:
  `projects/underreach-wallpaper/` (self-contained).
- Sibling project: `projects/campfire-wallpaper/` — architectural
  template only; never edited by this project.

## What it is

A Lively (web type) wallpaper: a town-scale Underreach cavern.
The Surface Gate (#26) stands in the north wall; the founding
settlement (Deep Ledger civic heart, stations, cots, cart) is
threaded by the lantern network; named expansion zones of open
ground surround the core. Four catalogue creatures walk the
network (node-to-node graph travel, obstacle-routed legs),
dwell in the light playing signature clips, and leave through
the gate or into the dark.

Key files:

| File | Role |
|---|---|
| `index.html` | Page shell, importmap, `#status` seam |
| `js/wallpaper.js` | Scene, routing planner, creature director, loop |
| `js/roster.js` | **What exists** — the asset roster (roster rule) |
| `js/layout.js` | **Where it stands** — zones, plots, network, town state |
| `assets/*.glb` | Catalogue copies, byte-for-byte (table below) |
| `vendor/three/` | three.js r180, vendored from the campfire project |
| `docs/TEST_PLAN.md` | Verification method + measured results |

## Design decisions worth knowing

- **Classic campfire lighting discipline, not the AAA chain:**
  no shadow maps, no postprocessing, real-light budget of 5
  (hemisphere + 4 point lights: town heart, gate, crystal
  relay, thermal corner). Every other lantern is emissive
  geometry + additive glow sprite + light-pool decal with
  per-lantern flicker. Rationale + measurements in TEST_PLAN.
- **Town state shape:** `TOWN_STATE = { version, era, plots:
  { plotId: slug|null } }` over `PLOTS`/`ZONES`/`NETWORK` in
  `js/layout.js`. A future living-world feed (phase 2,
  discussed, NOT commissioned) drives growth by changing plot
  assignments; scene code does not change.
- **Routing:** the campfire build's planner carried over
  (grid A* at 0.5 pitch over [-48,48]² + string-pulling with
  exact segment-vs-obstacle validation). Creatures plan per
  graph leg, not per trip.
- **Graceful degradation:** a failed GLB load leaves its plot
  empty (or its creature unspawned) and records the error in
  the `#status` JSON; the town still renders.

## Asset roster — catalogue copies (sha256)

Copied byte-for-byte from the Game Asset Builder catalogue
(`catalog/<slug>/` outputs on branch
`game-asset-builder/underreach-assets`; gloam-rat and
frontier-bearer from the queue's UR outputs worktree) and
hash-verified against catalogue metadata at build time
(COPY-MATCH on all 39). Gate status per the asset-queue ledger:
all listed assets are gate-PASS / catalogue-verified. #29 and
#31 are parked and deliberately absent.

| slug | queue | bytes | sha256 |
|---|---|---|---|
| gloam-rat | 1 | 20,107,080 | aec00e60646eefefbfe9bb7b30e33645cc6141bdb087ea341b0777dc66f11488 |
| frontier-bearer | 2 | 55,164,516 | 02622dd54d81c04edda6eb5c1a9a150ee114761f6c74105dc0923b20a7e7ccb0 |
| delver | pre | 20,417,188 | 7ab7262b7eeb5716c23bd0494f133a7674a0f858cd4a839bd80c8ca7e8b7edc4 |
| gloam-lurker | pre | 20,084,700 | f0c881cb9bd39e0b2223f3d20be45fd46e18fd220de64ae4ed7d9ce05d8ff4c3 |
| torch-on-a-stand | 11 | — | bcba2c67765663fdee6815a6944c633e46d851db2a85e4b3f7d894b1d85b9a9f |
| lantern | pre | 215,672 | 5dffb6360730c30d9a0a3c928afd89f5f9148c4a1ecf732b8ffbc71f426cf900 |
| fungal-oil-lantern | 12 | — | aebb0ea65d559dacdf353b263258e5189590d7bb75b1eb4c78bf643186cefa8b |
| sealed-pressure-lantern | 13 | — | 0223518581cb7c101811a085447a05dc911c7d4c0becaa3c787067366d9b38b2 |
| crystal-heart-lantern | 14 | — | 0b3894f5e7ceb68cfd432bf1645d78e68c0db8cfbab419614659ebbd0389ab4e |
| thermal-lamp | 15 | — | 99fef953c4c16d2c7976c6f662df5ec5d4cc209435f890b353afe7e6dfde1b4b |
| piped-light-spine-segment | 16 | — | 572ff8f83d144c7488ce98ffbf9d4db37eedabb913243a582733fb613e8f7bcc |
| crystal-relay | 17 | — | d0bfd19510f9699597ecb9a86e236df6d18eada71ac7b163094fb818c256f359 |
| heat-pipe-relay | 18 | — | 3eb947d363537fcd9ab305d1cf965131559a8e4d768a8b5c0acc35e9512f3d0d |
| converter-forge | 19 | — | fef3e81bbd14537356ac6872d9a29f5b1efc7f363966ed141a1826fc55a7346d |
| chandlery-bench | 20 | — | 700d1c9e3c168a08ced2350bb951e9fd68df6a95425f64a08f7e6409ae61a1fd |
| charcoal-kiln | 21 | — | 4106b836efe8343ad31f0b3443cb1a2249d67f08962eac4b918f103f8d923967 |
| herbalist-bench | 22 | — | 42e19d330fa643887c7fa7cae5bdf97849cef09695f04276df9ad5de3227746e |
| tailor-bench | 23 | — | 632f4cf59cc0ad18dbcf44a70f2981bff1fd7c68ac604e4d7dff7596620ab6c2 |
| sealed-food-store | 24 | — | e210e4541768a1b5256b35b12e8337f9c9e9088e6d1346e2e3cd598b79bd9728 |
| deep-ledger | 25 | — | 7f0a50a07950a18b84cc42ed9d8c82b0188e59e08e1c3c49b4a01b5011502093 |
| surface-gate | 26 | — | 954f7b067fda9818b2465ec408783ccdba6d919cb9425f70b20490b4c4f82d05 |
| timber-support-set | 27 | — | 50fc438aeb245aaaf4f8c939c7cc13ea04f1548891646018f34f5e981ab2ac92 |
| ventilation-pieces | 28 | — | 0889b35a4e22ac38d6848e52955597da3df9c888326bce9174f0753f0594d24f |
| fungal-node | 30 | — | cc75a873704a035c9d2dbd6fe199aa09b1e945305930533c7335f206efbc2e49 |
| cart | extra | 12,121,024 | ae07e9a6b52c5b2209a85730c2982443fd932fc1990701345af0aa1847aeb804 |
| cot | pre | 239,740 | 67e070f2012f416f96b202fe0cb419255b5f57a72b83053f916ba22ca1659ef7 |
| miner-pickaxe | 3 | — | aaba8c8e9c0762ef73b746c33e3de8db1ea2af49910d807b6e8bdaf1da437be5 |
| miner-helmet-lamp | 3 | — | 389dded42eecdb86c76490302a127e9cd4084b6498f0aec8863365f406b62902 |
| hauler-ore-basket | 4 | — | 076c73f4e7e67cfe854b246e9e0c3bdf7b5196a0779c12d9b2b258284a933b23 |
| farmer-sickle | 5 | — | 0c7a2177d7061e09968916852084e82ea7c91c8f437c191ac94271f912a2a652 |
| farmer-pouch | 5 | — | effbd49507ed4bae50090ec42ce9b24108495178cb312fcc7aa51f6846547084 |
| herbalist-herb-bundle | 6 | — | 0aad75f6e27187ed8c77c507d8463def2a8289e27e5aadf7513bf06547f1e60c |
| herbalist-satchel | 6 | — | 5ae94948dce16b569e47867f48d990b6e97d042c876317ca9f1acc8f6fa2e180 |
| spore-mask | 7 | — | adf3774f06d6b7bde9f411993af6016b97b650d4dcf284be45ab2e00733f87d8 |
| harness-and-rope | 8 | — | c88cebdfeaf3a16f79576e9ab43796886a19de5eb0e98352ca3f446722c20a31 |
| quiet-gear-boot-wraps | 9 | — | 34b0a84e1d5249a1f5cc2e9039b3d8ba3c58d092cf5bff2cbe9df85fe182a638 |
| quiet-gear-arm-wraps | 9 | — | d2186ec01e549cd2bc3435829b9acffca065ed41d1f1fac463a28ad9ec6219f8 |
| cooling-gear-vest | 10 | — | a08014fa778d110a7f0bd3d01c24862f966198521aea7ed0ace7c6bcad49f34d |
| cooling-gear-gauntlets | 10 | — | 5a9541205404f8df47cfa9087ecd944046e1965822c6c4d693e2289afcae9ab7 |

Total: 495,356,764 bytes (472.4 MiB) of GLBs. Creature clip sets:
gloam-rat (bite/idle/run/walk), frontier-bearer
(idle/plant/run/walk), delver (bounce/idle/run/walk),
gloam-lurker (idle/run/shiver/walk).

## Deploy steps (when the owner says go)

1. Sync `projects/underreach-wallpaper/` to the PC (pull branch
   `underreach-wallpaper/v1` in the PC checkout).
2. Lively → Add Wallpaper → drop the project folder (the one
   containing `LivelyInfo.json`) into the library; apply.
3. Confirm the roster on the real GPU: the headless bench is a
   SwiftShader number — the RTX 3060 figure is expected to be
   far better, but it is **unmeasured** until this step runs.

## Known gaps / honest notes

- Real-GPU frame cost is unmeasured (VM has no GPU; headless
  numbers are SwiftShader-only — see TEST_PLAN).
- Small-prop dressing offsets (bench-top items at y≈1.08, cot-top
  items at y≈0.58, food-store sickle at y≈1.24) are estimates
  from normalized heights, sanity-checked against headless
  screenshots, not measured against the source meshes.
- The frontier-bearer's GLB is 55 MB (the catalogue's largest);
  it loads once as a template and clones via SkeletonUtils.
