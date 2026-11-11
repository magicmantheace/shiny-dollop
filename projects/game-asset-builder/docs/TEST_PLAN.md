# Test plan — Game Asset Builder

## Verified on the build VM (no GPU) — 2026-11-06

- Unit tests: 57/57 pass (`python3 -m pytest tests/`). Count history:
  44 at P1; the P1.1 additions (13) pin the weight-distance veto
  (redistribution + renormalization, radius kept, trunk exemption,
  nearest-bone rescue, endpoint-aware rescue eligibility), the
  torso-share gate, and the per-template trunk chains.
  The original 8 pin the pipeline order, the mesh-before-texture rule,
  and the unload discipline (every model stage is an isolated GPU
  process). The P0 additions pin the rig template's shape (Pip config
  = the proven 14 bones; dragon config swaps ears for arms; parents
  precede children), the pose recipes' math (hop arch, lift peak,
  idle bounds, clip frame counts), the catalog record (sha256
  round-trip + tamper detection), the flood-fill cutout on a synthetic
  image, and the bridge runner's token discipline. The skinning
  additions pin the heat-acceptance policy (healthy result accepted;
  low coverage, an empty bone, and wingtips left to other bones each
  rejected with named reasons; multiple failures all reported).
  The P1 additions pin the quadruped and biped templates' shapes
  (bone counts, parenting, ground contact, template extents), the
  per-template recipe registries (every recipe channel exists in its
  template's channel set; bounce lift and wave envelope shapes), the
  generalized tip labels in the acceptance policy, and the prop
  path's catalog honesty (an unrigged entry has no bones, no actions,
  and `weight_method: null` in provenance — never fabricated rig
  metadata).
- Prep stage on the real Ember Dragon concept: clean cutout
  (foreground 29.6% of frame), visually inspected against the concept.
- Rig + animate + verify chain exercised twice in Blender: on the
  bake-off's Hunyuan Pip GLB as a stand-in (ears config) and on the
  Ember Dragon's own textured GLB (arms config). Both produced a
  14-bone armature, 14 populated vertex groups, weight coverage 1.0,
  embedded `idle` + `hop` clips, and cold-re-import renders showing
  rest pose intact and the hop apex airborne (+0.17–0.19 ground
  clearance) with both wings swept up and no tearing.
- Skinning (P0 state): bone-heat automatic weights produced ZERO
  weights on both Hunyuan meshes (recorded in each rig report); the
  deterministic distance-to-bone fallback skinned both, coverage 1.0.
- Skinning hardening (2026-11-06, same VM): the failure was diagnosed
  by measurement — rig inputs carried 28 (dragon) / 135 (Pip)
  non-manifold edges plus debris shells after the weld, and only
  5/28 template bone endpoints sat inside the dragon mesh (validated
  ray-parity test, controls 6/6 and 0/6). With geometry cleanup +
  endpoint snapping in the rigger, bone heat succeeds on both meshes
  through the shipped code path: dragon — coverage 1.0, wingtip
  dominance 1.0 (fallback: 0.0), distance rescue on 6 verts only;
  Pip — coverage 1.0, wingtip 1.0, no rescue. The dragon was
  re-animated and re-catalogued (catalog-verify MATCH on the new
  sha256); cold re-import shows 14 bones / 14 groups / idle + hop,
  hop apex clearance 0.19 vs 0.025 at rest.
- Stress deformation (`stages/catalog/stress_render.py`): a pose
  beyond the shipped clips (wing.L at 1.25 rad vs the hop's 0.65,
  head turned 0.65 rad, tail curled ~1.75 rad total) rendered from
  two angles and inspected: raised wing intact, no tearing, no joint
  collapse, no candy-wrapper twist at the neck. A belly-centreline
  texture-seam streak grows with deformation (faint at hop apex,
  pronounced in the stress pose, absent at rest); the same artifact
  is present in the P0 fallback rig's hop render, so it predates the
  skinning change.
- CLI `stages` and `benchmark-plan` run and print the registry/protocol.
- CLI `doctor` runs and honestly reports this machine: no GPU, GPU stages
  "CANNOT RUN on this machine". That report is correct for the VM and is
  itself a checked behavior — the tool must never pretend a GPU stage ran
  where it cannot.

## Verified hardware facts (owner's PC, via the PC bridge) — 2026-11-06

- RTX 3060: 12,288 MiB total VRAM, 9,210 MiB free at rest; D: 3.1 TB free.
- These numbers bound the bake-off: any candidate needing more than the
  free VRAM must offload or be recorded as not fitting.

## Verified on the owner's PC (GPU stages) — 2026-11-06

- Bake-off round 1 ran end-to-end (lab at `D:\asset-forge-lab`, per-stage
  venvs, uv-managed Python 3.12): Hunyuan3D-2 shape (305 s, peak
  8,762 MiB) and paint (1,520 s, peak 12,086 MiB) as separate processes
  with VRAM released between; TripoSR (39 s, 6,100 MiB); TRELLIS
  inference (176 s, 12,020 MiB, no OOM). Output meshes were fetched to
  the VM and re-verified (counts + sha256) before scoring.
- Stable Fast 3D did NOT run: its HF repo is gated (401). Recorded as
  BLOCKED in `benchmarks/pip/scores.md`, not as a failure of the model.
- **P0 pipeline proof run (Ember Dragon)**: dispatched through the
  project's own `gpu_bridge.py` + lab stage runner. Shape: exit 0,
  334 s, peak 7,233 MiB, after-exit 790 MiB (≈ baseline 809). Paint:
  exit 0 (stage result JSON; the bridge job wrapper misreported the
  job as failed — artifacts + result JSON are the authority), 909 s,
  peak 12,043 MiB, after-exit 778 MiB (≈ baseline 788). The mesh
  process had fully exited before paint was dispatched — unload
  discipline verified by the runner's VRAM samples, not assumed.
  One transient bridge disconnect killed the first local poller
  mid-paint; the job completed server-side and was reattached.
- **P1 proof runs (2026-11-06)**: three assets through the same
  bridge + lab path. Triceratops — shape: exit 0, 301 s, peak
  7,224 MiB; paint: exit 0, 598 s, peak 12,040 MiB, VRAM back to
  ≈ baseline after each stage. Snow Goblin — shape: exit 0, 296 s,
  peak 7,280 MiB; paint: exit 0, 1,479 s, peak 12,010 MiB.
  Treasure Chest — shape: exit 0, 298 s, peak 7,288 MiB; paint:
  exit 0, 1,986 s, peak 12,002 MiB. Paint peaks sit ~250 MiB under
  the card's 12,288 MiB on all three — the headroom warning from
  the bake-off stands.
- Bridge job-tracking limit, observed twice in P1 (and consistent
  with the P0 disconnect): for the goblin (1,479 s) and chest
  (1,986 s) paint stages, the bridge reported the exec job terminal
  at ~15 minutes and the client's result fetch 404'd, while the
  PC-side stage processes were unharmed and ran to completion
  (worker CPU time climbing steadily throughout; GPU held). Both
  stages were recovered by adopting the lab-side artifacts
  (stage_runner's own result JSON + the textured GLB) once the
  processes finished — the adopted runner records are what the
  catalog provenance carries. The triceratops paint (598 s) stayed
  under the limit and needed no recovery. Mechanism not confirmed
  beyond the timing pattern (~900 s on every affected job).

## Verified on the build VM — 2026-11-06 (scoring)

- The silhouette-IoU scorer (`benchmarks/pip/score_render.py` +
  `iou_sheet.py`) scored all three delivered candidates against the
  Meshy reference: Hunyuan3D-2 RIGGABLE (front IoU 0.84), TRELLIS and
  TripoSR MELTED — full table and method notes in
  `benchmarks/pip/scores.md`. The comparison sheet was inspected
  visually; it overruled TRELLIS's numeric 0.55, per protocol.
- Two scorer defects were caught by that inspection and fixed before
  the recorded scores were produced: importer axis-conversion rotations
  must be baked before transform work, and yaw is orbited by the camera
  because glTF objects in quaternion mode ignore `rotation_euler`
  writes. (Details in `scores.md` method notes.)

## Verified on the build VM — 2026-11-06 (P1 rigging and props)

- **Triceratops (quadruped)**: the Hunyuan mesh arrived SIDEWAYS
  (body axis along X; the template assumes −Y facing). The first
  rig exposed it honestly — bone-heat shipped with coverage 1.0 but
  the head-zone dominance read 0.05 because the "front" strip was
  the creature's flank. Re-rigged with the pipeline's `--rotate-z
  90` facing correction (after fixing the correction itself: glTF
  imports are in quaternion rotation mode, where `rotation_euler`
  writes are silently ignored — the bake-off scorer's lesson; the
  fix applies the rotation through `matrix_world`). Final rig:
  bone-heat, coverage 1.0, feet dominance 1.0 (6,870 verts), head
  zone 0.9998, tail zone 0.49 (evidence only — the rear strip is
  mostly rump on a stubby-tailed creature), 13 endpoints snapped,
  0 failed; 45,001 verts / 89,998 faces, 15 bones, `idle` +
  `bounce`; bounce apex ground clearance +0.042 vs −0.006 at rest.
  Rest, bounce-apex, and stress renders inspected: the stress pose
  (neck stretched + turned, one front leg tucked hard) deforms
  cleanly, no tearing or collapse. Noted texture quality: the
  paint stage left mottled dark patches on the back — a texture
  artifact, present at rest, not a rig defect.
- **Snow Goblin (biped, ears)**: rig input was the messiest mesh
  yet (137 non-manifold edges, 58 shells, 804 debris verts);
  cleanup left 18 residual non-manifold edges and heat still
  shipped: coverage 1.0, hands dominance 1.0 (10,234 verts), feet
  zone 0.90, head zone 0.67 (the zone definition was corrected
  during P1 to count the ear bones as head bones across the full
  width — the inherited centre-strip definition read 0.24 while an
  independent dominant-group histogram of the shipped GLB showed
  the skull zone ~87% head/ear-driven). 49,080 verts / 98,583
  faces, 13 bones, `idle` + `wave`; rest and wave renders
  inspected. Known cosmetic limit: the ruff band between head and
  shoulders is ~75% arm-dominated (heat diffusion over one fused
  fur mass), so the shipped wave (1.9 rad peak) reads as a wave
  with a bulky raised arm, and the beyond-clip stress pose
  (2.2 rad) drags a visible sail of side fur. No tearing at either
  amplitude. A weight-distance veto is the candidate mitigation —
  future work, not attempted in P1. **Mitigated the same day —
  see the P1.1 section below; this paragraph records the pre-fix
  state.**
- **Treasure Chest (prop)**: static path produced a 27,041-vert /
  50,530-face GLB (30,000 target) from a 1,082,755-vert textured
  mesh; cleanup took 109 non-manifold edges to 0. Cold re-import
  in `--static` verify mode proves the honesty contract: no
  armature object, 0 vertex groups, 0 actions, `rigged: false`,
  grounded at z = 0. Beauty and front renders inspected — the
  chest reads exactly as the concept (domed lid, brass bands,
  padlock), facing the camera.
- All three catalog entries pass `catalog-verify` (sha256 MATCH),
  and rigged entries carry the weighting method and (for the
  triceratops) the `rotate_z` correction in provenance.

## Verified on the build VM — 2026-11-06 (P1.1 weight-distance veto)

- **Snow Goblin re-rig** (from the saved `textured.glb`; the mesh
  and texture stages were NOT re-run, and the Ember Dragon,
  Triceratops and Treasure Chest outputs and catalogue entries are
  byte-identical — all re-verified with `catalog-verify`):
  bone-heat + distance veto (factor 0.85, floor 0.19) accepted by
  the policy gate, no fallback. Coverage 1.0; torso-zone arm share
  **0.506 → 0.139** (9,394 zone verts); ruff-band arm share
  0.614 → 0.448; hands (tip) dominance 1.0 → 0.997; head zone
  0.667 → 0.787; feet zone 0.904 → 0.904; all 13 bones populated;
  veto zeroed 101,175 (vertex, bone) entries and rescued 1,485
  weightless verts. New GLB sha256 `86c91cd6…`, catalogue entry
  re-issued and `catalog-verify` MATCH; cold re-import verify:
  coverage 1.0, both clips present, grounded at rest and at the
  wave apex frame.
- Parameter choice was measured on the shipped mesh before any
  code shipped: arm flesh sits at median 0.34 from the arm segment,
  torso bleed at 0.51 (distributions overlap, so no radius is
  clean). A tighter veto (0.7/0.16; torso share 0.065) was run end
  to end and REJECTED on the renders: the raised arm stretched
  into a fin because too much of its own flesh lost arm weight.
  The shipped 0.85/0.19 keeps 86% of arm-dominated verts' arm
  weight. Parameter sweeps and the before/fix renders are kept
  under `outputs/snow-goblin/before-veto/`.
- Visual verdict (rest / wave 1.9 rad / stress 2.2 rad renders
  inspected): the owner's flagged defect — body texture stretching
  with the raised arm, chest fur dragged diagonally — is gone at
  the shipped wave; the ruff and chest stay with the body and the
  raised paw reads as a paw. Residuals, honestly: a taut sheet of
  fur still stretches in the armpit web at full raise (the arm and
  torso are one fused mass geometrically), and the 2.2 rad stress
  pose still sails the flank, reduced but not eliminated versus
  pre-veto. No tearing at either amplitude.

## Verified — 2026-11-06 (P2 cleanup slice: preflight, geodesic veto, segmentation)

Layer 1 — concept pose spec + pre-flight check (VM):

- Spec written into `docs/DESIGN.md` ("Concept pose & separation
  spec", per body plan, with canonical prompt blocks).
  `stages/prep/preflight.py` scores a concept image (pass/warn,
  recorded in the run manifest by `pipeline.py` for rigged runs).
  Calibration, all measured: the new to-spec giraffe concept
  **passes** (4 leg components after erosion, min leg gap 0.035);
  the ORIGINAL snow-goblin concept **warns** (arm-daylight row
  fraction 0.009 — arms fused to the torso, the defect P1.1/P2
  then had to fix downstream); the triceratops v2 concept passes.
  Thresholds are documented in-code as heuristic.

Layer 2 — geodesic weights (VM, Blender rig probes from the saved
textured meshes):

- The veto's reach comparison now uses max(Euclidean, graph-
  geodesic) distance over the mesh surface (`stages/rig/
  geodesic.py`); geodesic ALONE was measured worse (goblin heat
  gate-rejected, torso share 0.268) because arm seed sleeves
  legitimately spread over the flank — the union is the shipped
  semantics. A beyond-TAIL exemption keeps distal flesh (toes,
  fingertips) with its bone; exempting both ends re-broke the
  goblin (ruff past the shoulder: share 0.133 → 0.320, rejected)
  — tail-only is shipped, with the measurements in
  `skin_policy.py`.
- The P1.1-era quadruped belly guard zone was exercised for the
  first time and MISFIRED (it enclosed the leg centrelines and
  read 0.58 on a healthy rig); the zone was redrawn to the belly
  wall between the leg columns (reads 0.204 on the same weights),
  threshold unchanged at 0.25.
- Probes without labels: goblin torso share 0.166, head 0.891;
  triceratops feet 1.0, head 1.0, belly 0.197, coverage 1.0 both.

Layer 3 — segmentation bake-off + stage (PC GPU + VM):

- Bake-off (full record: `benchmarks/segmentation/scores.md`):
  **P3-SAM adopted** — goblin CLEAN (arms split at the shoulder),
  triceratops ROUGH (2 of 4 legs split); 100–188 s/mesh, peak
  9.7 GB, VRAM back to baseline after exit; Tencent Community
  licence permits commercial use in Canada. **PartField rejected
  on licence** (NVIDIA non-commercial-only) despite CLEAN/CLEAN
  quality; SAMesh not run (the bake-off's gating condition never
  triggered).
- The pipeline gained a `segment` stage (registry + orchestrator):
  proxy built on the VM with the bake-off's exact recipe (a
  rig-frame variant collapsed the triceratops draw to ONE part —
  measured and reverted), P3-SAM as its own PC process in its own
  venv, labels transferred in the rig by nearest face centroid
  under the recorded canonical transform, geometry separated at
  part boundaries (+1,803 goblin / +755 triceratops verts), and a
  label-aware veto (foreign-part dominants forbidden on
  non-boundary or beyond-reach pairs; plurality label→bone map).
  Two failure modes were found and fixed during integration:
  mass-summed label dominants emptied the goblin's leg bones
  (heat rejected → plurality voting), and one degenerate proxy
  face silently shifted trimesh's face indexing (make_proxy now
  drops degenerate/duplicate faces; the glue validates counts).
- **Snow Goblin re-proof** (full stack, from the saved textured
  mesh; prior artifacts under `outputs/snow-goblin/
  before-cleanup/`): 9 parts; heat accepted; coverage 1.0;
  torso arm share **0.139 → 0.079**; head dominance 0.787 →
  0.881; feet 0.904 → 0.831; hands 0.997 → 0.778 (the label
  veto's cost on this draw — arm labels split the arms, and
  interior arm verts lose some forearm weight; the gate is 0.5
  and the wave render is clean). Wave @1.9 rad: chest/ruff stay
  put. Stress @2.2 rad: the flank sail is **materially reduced**
  in the front view (a narrower fin tight to the arm, flank no
  longer bridges) and reduced in three-quarter; the residual is
  the arm part's own webbing rotating with the arm — the fused
  fur had to be assigned somewhere, and at 0.3 rad beyond the
  shipped clip it still shows. New GLB sha256 `e94fb4cb…`,
  catalogue re-issued, cold re-import verify passes.
- **Triceratops re-proof** (full stack): 5 parts — head+frill
  (11,052 faces), body (34,128), two far-side legs as their own
  parts (2,599 + 2,116 faces), one small part (105); the two
  near-side legs remain in the body label (P3-SAM's documented
  weakness, same as the scored bake-off — the leg-separation
  criterion is therefore only half met). Rig: heat accepted,
  coverage 1.0, feet dominance **1.0** (= P1), head **1.0**
  (≥ P1), belly leg share 0.200 (new gate; unvetoed heat
  measures 0.352 and would fail), tail 0.427 (P1: 0.491 — the
  stubby-tail evidence zone, not gated), bounce render clean.
  New GLB sha256 `06c5a1e2…`, catalogue re-issued.
- Ember Dragon and Treasure Chest outputs/catalogue entries
  byte-identical (sha256 re-verified against their catalogue
  entries). Full suite: **79 tests passing** (57 pre-P2 + 7
  preflight + 10 geodesic/exemption + 4 label-veto + registry
  update).

## Verified on the build VM — 2026-11-07 (P2 local UI)

- Unit tests: **92/92 pass** (`python3 -m pytest tests/`): the 79
  pre-P2 tests plus 13 new UI tests pinning the catalog data layer
  (rigged/prop summaries incl. the P0 entry's bones fallback for
  the missing `provenance.rigged` flag, preview-path traversal and
  non-PNG rejection), the run validation (argv mirrors the CLI
  flags; invalid specs raise and spawn nothing), and the HTTP
  surface (index page, catalog endpoint, 404s, traversal 404,
  invalid run POST → 400) against the real server on an ephemeral
  port with fixture catalogs.
- Live server smoke (this VM): `asset_builder.py ui` served the
  real catalog — all four assets with correct rigged flags, bone
  counts (14/13/0/15) and preview counts; the ember-dragon detail
  endpoint returned sha256 MATCH against the on-disk GLB; a preview
  render fetched as image/png (363,713 bytes); index returned 200.
- Honest scope: the UI itself is verified; a pipeline run launched
  FROM the UI was not executed end-to-end (its GPU stages are the
  already-proven CLI path — the UI spawns that CLI verbatim — but
  the spawn-from-browser flow has only the validation tests and the
  run-tracking code behind it, no live run).

## Verified — 2026-11-07 (P3 engine hand-offs: export + playback)

Exporters (VM):

- Suite **101/101** (9 new hand-off tests): exports copy only
  catalog-verified bytes (a tampered GLB is refused before and
  after copying), the Godot wrapper references the documented
  `res://assets/<slug>/` path, the three.js manifest/snippet carry
  the real clips and bones, and the studio record obeys the intake
  rules (candidate status, GAB rig_id — never `studio_humanoid_v1`,
  id/URI patterns from the studio's schema).
- All four catalogued assets exported to all three targets.
  The four studio records were additionally validated against the
  animation studio's actual `schemas/asset.schema.json` with
  jsonschema — all VALID. (The studio export was run against a
  scratch asset root; writing into the studio's live store and its
  register/promote flow remain the studio side's step.)

Godot playback (owner's PC, Godot 4.7.2 console, headless):

- Scratch project from `handoff/godot/`: `--import` exit 0, then
  `verify_handoff.gd` — **GODOT_VERIFY_DONE ok=true**, exit 0.
  Every wrapper scene instanced; skeleton bone sets equal the
  catalog's; every clip exists and moves the skeleton (bone global
  poses, t=0 vs mid-clip): Ember Dragon hop 1.25 s Δ0.085 /
  idle 4.79 s Δ0.0062; Snow Goblin wave 2.42 s Δ1.69 / idle
  Δ0.035; Triceratops bounce Δ0.096 / idle Δ0.156; Treasure Chest
  confirmed static (mesh, 0 bones, 0 animations).

three.js playback (owner's PC, Chrome headless + SwiftShader,
three 0.180.0):

- `handoff/threejs/run_verify.mjs` — **THREE_VERIFY_DONE ok=true**,
  exit 0. GLTFLoader + AnimationMixer: bone counts match the
  catalog (14/13/15/0); every clip plays with world-space bone
  motion: dragon hop Δ0.074 / idle Δ0.0029; goblin wave Δ0.70 /
  idle Δ0.017; triceratops bounce Δ0.030 / idle Δ0.040; chest
  static. Clip durations agree with Godot's to the digit
  (1.25 / 4.7917 / 2.4167 s) — the same baked clips, two engines.

Harness defects found and fixed during this proof (all in the
verification tooling, none in the shipped assets): the Godot
script's first mesh check searched by node NAME (`find_child`)
where glTF mesh nodes carry asset names — replaced with a
type-walk; three ≥ 0.170 splits its module build, so
`three.core.js` must sit beside `three.module.js` or the import
graph 404s silently; Chrome `--dump-dom` snapshots while the GLB
load is still in flight (with and without virtual-time budgets),
so the driver polls the result element over the DevTools
protocol instead.

## Verified — 2026-11-08 (P4 game animations: walk/run gaits)

Gait model + regeneration (build VM, Blender 4.2.3 headless):

- Suite **113/113** under pytest (101 baseline + 12 new in
  `tests/test_game_animations.py`): every template registers
  `walk` + `run` at the documented durations; gait recipes return
  exactly their template's channel set; loop closure holds
  (pose(0) == pose(period) per channel, and the baked last frame
  wraps to the first with no jump); biped/winged legs are exactly
  anti-phase with arms counter-swinging; the quadruped walk
  matches the lateral-sequence offsets (FL 0, HR 0.25, FR 0.5,
  HL 0.75) and its run moves front/hind pairs together in
  anti-phase; the fold curve is zero through mid-stance and
  non-negative everywhere; each run is shorter-period and
  larger-amplitude than its walk. A synthetic-GLB test covers the
  new stdlib clip reader (`stages/animate/glb_clips.py`)
  hermetically.
- New drivers axis-probed on the shipped rigged GLBs before use
  (+0.5 rad, bone-tail world displacement vs facing): legs swing
  forward on +local X on all templates (dragon +0.22, goblin
  +0.145, trike FL +0.216); the goblin's fore-aft arm swing is
  local Z, mirrored (+Z: .L hand back −0.21, .R hand forward
  +0.21). One false start recorded: a root→head facing heuristic
  misread the goblin's facing by 90°; the probe values only make
  sense against the −Y facing the other two rigs share, which the
  wave axis (+X raise, up + outward) confirms.
- The three creatures were re-animated from their existing
  `rigged.glb` files (mesh/texture/rig untouched; the previous
  finals are kept under `outputs/<slug>/before-p4/`). New clip
  sets, from the animate reports: Ember Dragon hop 1.25 / idle
  4.79 / **walk 1.5 (36 f)** / **run 1.0 (24 f)**; Snow Goblin
  idle 4.79 / wave 2.42 / **walk 1.5** / **run 1.0**;
  Triceratops bounce 1.25 / idle 4.79 / **walk 2.0 (48 f)** /
  **run 1.0**. Catalog entries updated (actions, per-clip
  durations in a new `clips` map, provenance
  `animation_revision`) — `catalog-verify` MATCH on all three new
  sha256 (dragon `2837c6b2…`, goblin `c4ba135b…`, trike
  `39b5f934…`). The GLB-level test re-reads the exported files
  and confirms clip presence + durations independently of the
  Blender reports.
- Ground check (evaluated-mesh minimum Z across each walk cycle,
  vs rest): dragon never reaches its rest minimum (lowest point
  rises up to +0.107 during the cycle); goblin and triceratops
  dip ≤ 0.007 units below rest on a 2-unit character — no
  material ground penetration. Swing-peak stills (Cycles renders)
  show a readable mid-stride on goblin and triceratops with no
  visible limb interpenetration; the dragon's walk reads as a
  shuffle-step on its seated body plan.

three.js playback (build VM, Electron Chromium + SwiftShader,
three 0.180, the project's `handoff/threejs/verify.html` harness
page; the VM's managed Chrome refuses standalone launch, so an
Electron driver polled the result element the same way
`run_verify.mjs` does over CDP):

- **THREE_VERIFY_DONE ok=true** for all three creatures: bone
  counts match the catalog (14/13/15), all four clips per
  creature present with duration > 0 and real skeleton motion.
  Project-standard sampling (t=0 vs mid-clip) max bone deltas
  for the NEW clips: dragon walk Δ0.016 / run Δ0.032; goblin
  walk Δ0.030 / run Δ0.066; triceratops walk Δ0.330 / run
  Δ0.120. Note the method's blind spot: at mid-cycle an
  anti-phase gait passes through neutral, so biped-plan deltas
  read small; a second pass at quarter-cycle (legs at full
  swing) gives dragon walk Δ0.078 / run Δ0.083, goblin walk
  Δ0.146 / run Δ0.174, triceratops walk Δ0.182 / run Δ0.336 —
  in line with the established clips' deltas (dragon hop
  0.074–0.085).
- Not covered by this run: Godot playback of the new clips (the
  P3 Godot proof predates them; the GLBs differ only in added
  actions), rendered pixels in an engine, and any judgement of
  gait quality beyond the stills + deltas above. Foot-slip is
  not measurable in an in-place cycle — it depends on the
  consuming game's root-motion speed matching.

## P5 campfire creatures (2026-11-09, branch game-asset-builder/p5-campfire-creatures)

Infrastructure tests: `tests/test_p5_campfire.py` (21 tests —
snail + winged-quadruped templates, signature registry and
recipe selection, session-0 bridge transport). Full suite
**134 passed** (pytest), including the UI catalog test updated
to the ten-asset catalog (the P5 completion added toasty,
lantern-snail, axolotl-capybara, geode-tortoise, crow-postman
with bone counts).

Moth-Hart (winged-quadruped, `--ears`, signature `fan`) — full
pipeline, all stages on the owner's PC / build VM as designed:

- mesh (PC): exit 0, 334.11 s; shape 318,606 verts / 637,172
  faces; peak VRAM 8,654 MiB.
- texture (PC): exit 0, runner 1,330.41 s (texturing 1,192.2 s);
  textured 487,742 verts; peak VRAM 11,870 MiB of the 12 GB
  card. (One earlier dispatch of this stage was killed by the
  owner's stop order and one duplicate dispatch pair was
  tree-killed by hand — see the P5 section of
  `docs/MUSE_HANDOFF.md` for the operational record; the
  numbers here are the single clean run's.)
- segment (PC): exit 0, 136.74 s; P3-SAM 12 parts.
- rig (VM Blender): 21 bones (root/spine/hips/neck/head, ear
  pair, wing + wing2 pairs, 8 leg bones, tail pair); weights
  bone-heat + geodesic veto + label-aware veto (25,087 entries
  vetoed) + distance rescue on 2,759 verts; 893 separated
  verts added; rigged 45,637 verts / 89,496 faces.
- animate: idle 4.79 s, fan 2.79 s, walk 2.0 s, run 1.0 s —
  the full P4 locomotion set + the P5 signature.
- catalog: GLB 20,692,592 bytes, sha256
  `0616e52aaeed63badd7f47c1340cb094e77ee54ac2ed9bc5276f423a880e06fa`;
  `catalog-verify` **MATCH**.
- three.js playback (build VM, Chrome headless shell +
  SwiftShader, project harness page, three 0.180): ok=true,
  21 bones, 1 mesh. Mid-cycle max bone deltas: fan 0.627,
  idle 0.047, run 0.138, walk 0.121. Quarter-cycle (the
  meaningful sample for anti-phase gaits): fan 0.666,
  run 0.308, walk 0.170, idle 0.030 — in line with the P4
  creatures (triceratops quarter walk 0.182 / run 0.336).
- Renders (rest + fan showcase): the creature reads
  immediately as the concept — four patterned wings, feather
  antennae, antlers, four distinct legs; the fan pose sweeps
  both foreground wings vertical. Verdict: **RIGGABLE**.
  The concept preflight verdict was "warn" (leg band fuses
  under erosion); segmentation + separation produced four
  separately weighted legs anyway.

The remaining five builds ran 2026-11-09 after the bridge
route was rebuilt; all stages on the owner's PC / build VM as
designed, single-flight throughout. Per creature (three.js =
the project harness page, mid-cycle / quarter-cycle max bone
deltas; renders = rest + signature, eyeballed):

- **Toasty** (biped, `bounce`): mesh exit 0, 332.32 s
  (498,688 raw verts); texture exit 0, runner 1,573.17 s
  (762,980 verts / 997,542 faces; peak VRAM 12,045 MiB);
  segment exit 0, 219.01 s (7 parts). Rig 11 bones, coverage
  1.0; torso arm share 0.104, head zone 0.998, hands tip
  0.803, feet zone 0.390 (weak, disclosed). Clips: bounce
  1.25 s, idle 4.79 s, walk 1.5 s, run 1.0 s. GLB 21,960,832
  bytes, sha256 `62289b927b6c161b968726fb8455987de5ca397a3947f812f93de719c59d043e`, catalog-verify **MATCH**. three.js
  ok=true; quarter deltas bounce 0.270 / run 0.183 / walk
  0.152 / idle 0.009; mid 0.055 / 0.067 / 0.030 / 0.002.
  Renders clean; the bounce-peak frame splays the fused
  bottom rim (fused-mass class); a mid-body texture seam is
  visible. Verdict: **RIGGABLE**.
- **Lantern Snail** (snail, `retract`): mesh exit 0, 353.37 s
  (769,509 verts / 988,234 faces); texture exit 0, runner
  948.83 s. Rig 9 bones, coverage 1.0; head tip 0.959, shell
  zone 0.747, distance rescue 3,351, label veto 0. Clips:
  glide 3.0 s, idle 4.79 s, retract 3.21 s. GLB 21,410,520
  bytes, sha256 `240dbfafbdfded9a255b9ea441904979051aba284ba73f5d760a59dc5727af14`, catalog-verify **MATCH**; the
  catalog `material_notes` carry the emissive-shell note.
  three.js ok=true; mid glide 0.456 / retract 0.264 / idle
  0.009; quarter 0.166 / 0.264 / 0.053. Disclosed: the
  retract pose dips the evaluated mesh 0.035 below the
  ground plane; the head/face reads blobby in renders.
  Verdict: **RIGGABLE**. (This also closes the earlier open
  item "the snail template on a real mesh".)
- **Axolotl-Capybara** (quadruped, `wiggle`): mesh exit 0,
  295.48 s (548,677 verts / 691,694 faces); texture exit 0,
  763.33 s — the pack's only end-to-end client run. Rig 15
  bones, coverage 1.0; feet tip 0.865, head zone 0.658, tail
  zone 0.389 (thin fin, disclosed), label veto 14,755.
  Clips: idle 4.79 s, walk 2.0 s, run 1.0 s, wiggle 2.42 s.
  GLB 19,525,868 bytes, sha256 `7658b7db08dec348fdf04747fd211a53232421bd59e841102548351e96688adc`, catalog-verify
  **MATCH**. three.js ok=true; mid walk 0.376 / wiggle 0.202
  / run 0.117 / idle 0.039; quarter run 0.321 / walk 0.194 /
  wiggle 0.158 / idle 0.020. Renders excellent. Verdict:
  **RIGGABLE**.
- **Geode Tortoise** (quadruped, `shiver`): final sample —
  mesh exit 0, 324.21 s (821,719 verts / **1,643,448 faces**);
  texture exit 0, runner 2,523.98 s (texture_s 2,399.67 s;
  1,279,034 textured verts; peak VRAM 12,032 MiB) — the
  longest legitimate paint in project history, completed
  under the corrected kill criteria after two earlier
  attempts were stopped on a memory-level criterion the
  pack's evidence disproved (full saga in
  `outputs/geode-tortoise/attempt1-texture-note.txt` and the
  manifest's `stage_record_note`). Rig 15 bones, coverage
  1.0; feet tip 1.0, head zone 0.775, tail zone 0.231 (stub
  tail / shell rear), label veto 14,732. Clips: idle 4.79 s,
  walk 2.0 s, run 1.0 s, shiver 1.58 s. GLB 21,575,096 bytes,
  sha256 `0475366d287cbaa7ba0f063b788887aff383087b48dfe1d0775105e3203e95c1`, catalog-verify **MATCH**. three.js
  ok=true; mid walk 0.374 / run 0.103 / shiver 0.039 / idle
  0.034; quarter run 0.314 / walk 0.192 / idle 0.017 /
  shiver 0.014 (the shiver is a high-frequency tremble around
  neutral, so its bone-position deltas are small by design).
  Renders: stone shell + amethyst geode, reads exactly as
  the concept. Verdict: **RIGGABLE**.
- **Crow Postman** (biped, `bow`): mesh exit 0, 314.45 s
  (341,956 verts / 684,162 faces); texture exit 0, runner
  1,230.4 s (texture_s 1,092.48 s; 534,328 verts; peak VRAM
  11,996 MiB). Rig 11 bones, coverage 1.0; hands tip 0.886,
  head zone 0.937, feet zone 0.807; weights are the
  **distance-to-bone fallback** (bone-heat rejected by the
  skin policy) and torso arm share is 0.60 — coat mass
  follows the arm bones, disclosed as a quality limit; the
  bow render is clean (the concept's arms are sleeves fused
  to the torso). Clips: bow 2.58 s, idle 4.79 s, walk 1.5 s,
  run 1.0 s. GLB 21,106,560 bytes, sha256 `310942604e8623a07185e6bc03458a83ecf77eb7ca7181304a1d605c2be637a5`,
  catalog-verify **MATCH**. three.js ok=true; quarter deltas
  bow 0.189 / run 0.175 / walk 0.142 / idle 0.009; mid bow
  0.189 / run 0.064 / walk 0.029 / idle 0.002. Renders dark
  but unmistakable. Verdict: **RIGGABLE** (fallback weights
  disclosed).

Texture-stage failures, verified as failures (stage logs +
result files preserved under each `outputs/<slug>/`):

- **Ember Owl-Cat** (winged-creature + `--ears`, `headturn`):
  mesh exit 0 twice (328.12 s / 646,434 verts; 338.44 s /
  703,035 verts). Attempt 1's paint grew memory without
  plateauing and was killed at 2h33m / 8,797 CPU-s; attempt 2
  was killed at ~60 min on the same growth signature. Not
  catalogued. Record: `outputs/ember-owl-cat/attempt1-texture-note.txt`.
- **Mandrake Toddler** (biped, `scream`): mesh exit 0 twice
  (321.65 s / 676,636 faces; 319.34 s / 710,866 faces).
  Attempt 1's texture was operator-killed at 701.92 s on the
  since-disproved memory-level criterion (disclosed in its
  note as an operator error). The retry's paint died on its
  own mid-bake under corrected criteria — stage log ends
  after the input-mesh line, no traceback, no result, no
  textured GLB. Not catalogued. Record:
  `outputs/mandrake-toddler/attempt1-texture-note.txt`.

Paint-memory envelope established by the pack (completed
paints): runner 763–2,524 s; bake private-memory plateau
~17.2–17.7 GB on large meshes is the fixed pool, not a
runaway; kill criteria corrected to free RAM < 5 GB /
private > 26 GB / extreme duration with continued growth.

Not verified for P5: Godot playback of the six new GLBs
(three.js verification only); campfire-wallpaper roster
integration (separate step); the Owl-Cat / Mandrake paint
root cause (unproven — face count excluded as the sole
cause: 676,636-face Mandrake died while the 691,698-face
Axolotl-Capybara completed the same night and the
1,643,448-face Tortoise completed outright); real-GPU frame
cost of the new creatures in the wallpaper scene.

## Environment proof: pine tree (2026-11-09, branch game-asset-builder/env-pine-proof)

- Shape stage on the owner's PC: exit 0, 476.53 s, peak VRAM
  9,209 MiB; output 243,514 verts / 487,126 faces, 13 components
  (verified by re-import: 730,674 edges — a welded mesh, not soup).
- Prop finish on the VM: 39,956 -> 4,961 verts / 9,940 faces at the
  5,000-vert target; vertex colours survive the prop decimation;
  `catalog-verify --slug pine-tree` = sha256 MATCH.
- Painted-asset renders (Blender Cycles, real material): the
  4,961-vert catalogued GLB reads as a stylized pine — deep-green
  clustered canopy, visible tapered trunk (palette v2; v1 was
  rejected as pale under AgX and re-authored deeper).
- three.js load proof (VM, Chrome headless, SwiftShader, the
  wallpaper project's own vendored three 0.180 + GLTFLoader): five
  clones of the catalogued GLB at scene-scale heights (4.7-6.3)
  beside the catalogued treasure chest — all load, vertex colours
  render, real-time shadows cast/receive. Status gate was the
  page's own load callback (PINES_READY), not a timer.
- Paint stage failures (owner's PC, recorded not hidden): attempt
  1 exit 1 after 10,801 s (killed at an owner-approved cap, flat
  memory plateau throughout); attempt 2 invalid (vertex-split
  export defect, see HANDOFF) killed at 3,243 s; attempt 3 on the
  corrected welded 80k-face mesh exit 1 after 7,728.62 s (killed
  at the 23:30 deadline; peak VRAM 12,021 MiB, same plateau). The
  paint stage log stayed 0 bytes in every attempt; no textured
  output was ever produced (lab output dir holds only the shape
  inputs).

## Not yet verified

- TRELLIS's proper textured export — blocked on the
  `diff_gaussian_rasterization` CUDA build on the PC.
- The rig template on non-dragonoid winged creatures (the template's
  proportions were exercised on two Hunyuan outputs with similar
  anatomy: Pip and the Ember Dragon).
- The P1 templates beyond their proof creatures: the quadruped on a
  long-tailed or long-necked animal, the biped on humanoid
  proportions (the goblin is a big-head chibi), and either template
  on a mesh whose facing needs `--rotate-z 180/270` (only 90 is
  exercised so far).
- The weight-distance veto's radius defaults were calibrated on
  one fused-fur biped; the winged torso guard zone is still
  defined but unexercised, and the Ember Dragon's shipped rig
  still predates the veto (deliberately untouched). The
  quadruped belly guard zone WAS exercised in P2 (and redrawn —
  see the P2 section).
- A fully clean 2.2 rad stress pose for the goblin: P2 reduced
  the sail materially (front view) but the arm part's own web
  still sweeps as a fin at that amplitude (see the P2 section).
- The segment stage on any creature beyond the two re-proofs,
  and P3-SAM's draw variance across tessellations: two draws on
  near-identical goblin proxies gave 5 and 9 parts. The stage
  accepts whatever multi-part draw it gets; a single-part draw
  (seen once, on a non-scored proxy recipe) degrades the rig to
  the Layer-2 stack rather than failing.
- The label-aware veto on the winged-creature template
  (unexercised), and separation's coincident-vertex seams under
  engine RENDERING: P3 proved engine playback by sampling bone
  poses (Godot headless, three.js under SwiftShader) — no pixels
  were rendered in either engine, so seam behaviour under a real
  renderer is still open.
- Engine playback scope, stated plainly: all four catalogued
  assets play in Godot 4.7.2 (headless console import + pose
  sampling) and in three.js 0.180 (Chrome headless, software
  WebGL). Not covered: visual/rendered output in either engine,
  the Godot editor GUI import path, a shipped-game integration,
  and the animation studio's register/promote flow (the P3 studio
  export is files in its intake format, status candidate —
  promotion is the studio's own gated process and was not run).
- The Hunyuan paint stage on ANY environment/foliage subject:
  three attempts on the pine produced no result (see above);
  whether a further-reduced mesh, a different concept, or a
  paint-pipeline change unblocks it is untested.
- Builder environment assets in the full campfire scene: the
  harness's creature-ready screenshot races static GLB loads
  (baseline chest included), so in-scene blending at production
  scale is unjudged; only the gated mini-scene proof exists.
- The cleanup's debris-shell rule (< 0.5% of the largest shell) on a
  mesh whose small shells are real anatomy (detached eyes, teeth,
  held props): unexercised — on both current meshes the dropped
  shells were interior floaters, verified by vert counts only.

## Rules

- A result is claimed only from the machine it ran on: GPU results cite PC
  runs, never VM runs.
- Bake-off scores are recorded in `benchmarks/pip/scores.md` in the same
  commit series that produces them, failures included.

## Environment pack (2026-11-10)

- Suite on branch `game-asset-builder/env-pack`: **134 passed** (the
  catalog-set test now expects the seven pack props alongside the ten
  proven assets, all unrigged).
- `catalog-verify` MATCH for all seven: pine-tree, boulder, bush,
  fern, mushroom-cluster, fallen-log, stump.
- Each painter export was re-imported and verified before the finish
  (vertex count, connected components, `Color` attribute present);
  the first boulder attempt caught the split-vertex failure mode this
  way (89,955 components) and was repainted welded.
- Per-asset Cycles renders inspected (in the goal workspace):
  boulder v2, bush, fern, mushroom-cluster v2 (cap field fix),
  fallen-log v2, stump — all read as their subjects.
- Not verified: Godot playback of the pack GLBs; in-scene wallpaper
  captures (integration step, gated-load caveat in MUSE_HANDOFF).

## Mandrake Toddler finish (2026-11-10)

- Resumed from the recovered textured.glb (see the correction in
  `docs/PAINT_STALL.md`): segment → rig → animate → catalog in
  380 s. Catalog-verify sha256 MATCH.
- Rig: biped template, 11 bones, bone-heat weights with the
  label-aware veto; weight coverage 1.0, unweighted 0.0%.
- Clips in the final GLB: idle, walk, run, scream.
- Renders inspected: rest pose reads as the character; the
  scream pose tears at the papery shell skirt (disclosed).
- Suite: 134 passed (test_ui catalog set + bone count updated).


## Paint fix + Ember Owl-Cat finish (2026-11-10)

- Root-cause probes (owner's PC, bridge-dispatched): standalone
  VAE batch-6 encode OK (~1.9 s); cudnn.benchmark=True slower
  (11–12 s), not a fix; full-pipeline batch-1 ×6 OK (3.67 s);
  full-pipeline batch-6 STALLS in the VAE encoder's first
  down-block conv (faulthandler); full-pipeline batch-6 with
  `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` OK in 2.63 s.
- Fix in `stages/texture/hunyuan_paint.py`: the variable is set
  via `os.environ.setdefault` at import, before CUDA init.
- Production proof: Ember Owl-Cat texture stage exit 0 —
  texturing 6,202.2 s on the 1,405,816-face mesh, peak VRAM
  11,910 MiB. Textured GLB verified in Blender (1,092,321 verts,
  UVMap, 2048×2048 texture).
- Finish (`--resume`): segment → rig → animate → catalog.
  Catalog-verify sha256 MATCH (`f5a642353fa8…`). Rig:
  winged-creature, 14 bones, distance-fallback weights (bone-heat
  rejected by skin policy, disclosed), coverage 1.0. Clips:
  idle, walk, run, headturn.
- Renders inspected: rest pose reads as the character (ember
  plumage, glowing heart chest marking, curled tail); headturn
  pose turns the head without tearing.
- Suite: 134 passed (test_ui catalog set + owl-cat bone count).
- Not verified: Godot playback of the owl-cat GLB.


## Headturn rework (2026-11-10)

- `winged_headturn` reshaped from a 0.55 rad sine to ±1.05 rad
  plateaus with holds (owner: the sine read as "a tilt").
- Animate-only regeneration from the catalogued rig; verify
  re-run: coverage 1.0, clips idle/walk/run/headturn, apex frame
  27 (mid-hold), action ground −0.024.
- Apex render inspected: clear side-look, no neck tearing.
- Catalog-verify sha256 MATCH (`2bd78ce04579…`); suite 135
  passed (new plateau test added).


## Headturn correction — world-axis yaw (2026-11-10)

- Owner rejected the plateau version as still a tilt. Landmark
  measurement (beak-tip vertex in world space) on the baked
  clip: yaw +92°/−66° but beak dip −0.25/−0.30 — the canted
  bone-local Z axis sweeps a cone. Pitch compensation sweep:
  dip is euler-uncancellable (stays ≈ −0.24…−0.34 at all
  pitch values).
- Fix: `head_yaw` for winged-creature now uses a `world_z`
  driver (animate stage conjugates the armature-vertical
  rotation by the bone's rest orientation).
- Re-measured on the re-baked clip: yaw −55.0° / +57.7°,
  beak height Δ +0.001 / −0.005. Apex render: near-profile,
  level head. Catalog-verify MATCH (`98bc4f3f5c25…`); suite
  135 passed.

## Underreach asset queue (2026-11-10 night)
- Arm-separation hard gate (owner requirement, this session):
  delver concept replaced pre-GPU (warn 0.227 → A-pose pass
  0.5955); gloam concept replaced pre-GPU (0 leg components →
  pass, 3 components, gap 0.0322). Delver posed (bounce) render
  inspected: arms clear, no tearing.
- Delver: catalog-verify MATCH (`7ab7262b7eeb…`); 11 bones;
  clips bounce/idle/walk/run; distance-fallback weights disclosed
  (bone heat rejected, torso arm share 0.4165); coverage 1.0.
- Gloam Lurker: NOT catalogued. Texture attempt 1 spun ~7,400 s
  (stall signature; private memory stable 14,383 MB — not a
  runaway), killed with log preserved. Attempt 2 crashed natively
  (0xC0000005) at 103 s in the second model-load phase. Root
  cause unproven; mesh intact for a future retry.
- Lantern: catalog-verify MATCH (`5dffb6360730…`), 4,505 verts,
  procedural vertex-colour paint (Hunyuan texture killed at the
  2,400 s success-curve top). Cot: MATCH (`67e070f2012f…`),
  4,983 verts, procedural paint (texture stage stood down by
  design). Both renders inspected on Cycles CPU.
- Suite: 135 passed. Not verified: Godot playback of the new
  GLBs; no claim made.
