# Test plan — Game Asset Builder

## Verified on the build VM (no GPU) — 2026-11-06

- Unit tests: 44/44 pass (`python3 -m unittest discover -s tests`).
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
  future work, not attempted in P1.
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

## Not yet verified

- TRELLIS's proper textured export — blocked on the
  `diff_gaussian_rasterization` CUDA build on the PC.
- The catalogued GLB in a game engine (Godot/three.js playback of the
  baked clips) — verified in Blender only; engine hand-off is P3.
- The rig template on non-dragonoid winged creatures (the template's
  proportions were exercised on two Hunyuan outputs with similar
  anatomy: Pip and the Ember Dragon).
- The P1 templates beyond their proof creatures: the quadruped on a
  long-tailed or long-necked animal, the biped on humanoid
  proportions (the goblin is a big-head chibi), and either template
  on a mesh whose facing needs `--rotate-z 180/270` (only 90 is
  exercised so far).
- The biped arm fur-drag mitigation (weight-distance veto or
  equivalent) — documented limit, not yet attempted.
- GLB playback of the P1 assets in a game engine — same P3 caveat
  as P0; Blender-verified only.
- The cleanup's debris-shell rule (< 0.5% of the largest shell) on a
  mesh whose small shells are real anatomy (detached eyes, teeth,
  held props): unexercised — on both current meshes the dropped
  shells were interior floaters, verified by vert counts only.

## Rules

- A result is claimed only from the machine it ran on: GPU results cite PC
  runs, never VM runs.
- Bake-off scores are recorded in `benchmarks/pip/scores.md` in the same
  commit series that produces them, failures included.
