# Design — Game Asset Builder

## Founding decisions (owner, 2026-11-06)

1. **Fully local. No APIs.** Every generation step runs on the owner's
   hardware. No cloud services, no API keys, no per-asset cost. The only
   permitted network use is the one-time download of open model weights.
2. **Mesh and texture are separate models.** The mesh stage and the texture
   stage use different models, and each stage **unloads before the next
   loads** — separate processes, never two heavy models resident at once.
   The target GPU (RTX 3060, 12 GB) cannot hold them together anyway; the
   split is both the owner's instruction and a hardware necessity.
3. **Test multiple models and keep score.** Candidates are tried on the same
   benchmark and graded honestly. A melted result is a failed candidate.
4. **Pip is the benchmark.** The Drabbit Pet character Pip is the standing
   test case because a high-quality reference already exists: the owner's
   own Meshy-generated Pip (1.12M verts, 2048px texture). Local candidates
   are scored against it.

## Hardware reality (verified 2026-11-06)

- Owner's PC: RTX 3060, 12,288 MiB VRAM, **9,210 MiB free at rest** (desktop
  + pet running), 32 GB RAM, 3.1 TB free on D:. All GPU stages run here.
- Build VM: **no GPU**, 7 GB RAM. Orchestration, Blender rig/animation,
  cataloguing, and scoring run here. Nothing GPU-bound is claimed from VM
  runs.

## Stage architecture

| # | Stage | Runs on | Model / tool | In → Out |
|---|-------|---------|--------------|----------|
| 0 | prep | CPU | flood-fill/feather cutout (+ optional local rembg) | concept image → RGBA cutout |
| 1 | mesh | GPU, own process | candidate mesh model (below) | cutout → untextured mesh |
| 2 | texture | GPU, own process | candidate texture model (below) | mesh + cutout → textured mesh |
| — | *unload checkpoint* | — | orchestrator verifies VRAM released | — |
| 2b | segment | GPU, own process | P3-SAM (Hunyuan3D-Part) — bake-off: `benchmarks/segmentation/scores.md` | textured mesh → per-face part labels (50k-face proxy in the rig frame) |
| 3 | rig | Blender (CPU) | armature templates + automatic weights; mesh separated at part boundaries, label-aware geodesic veto | textured mesh + labels → rigged mesh |
| 4 | animate | Blender (CPU) | procedural pose recipes (from Drabbit Pet) | rigged mesh → baked clips |
| 5 | catalog | CPU | this project | .glb + preview renders + metadata + sha256 |

The orchestrator never imports two model frameworks into one process. Each
model stage is a subprocess with a file-based hand-off, so "unloaded" is
structural, not a promise.

## Candidate models (bake-off, P0)

**Mesh stage**
- **Hunyuan3D-2 shape (DiT)** — Tencent. Designed as a shape/texture pair;
  the shape half is the natural mesh-stage candidate. Low-VRAM mode exists.
- **TripoSR** — Stability/Tripo (MIT). The baseline: fast, untextured, and
  already proven weak on Pip (melted ruffle-blob on CPU). Re-run on GPU for
  a fair score.
- **TRELLIS (structure stage)** — Microsoft (MIT). Excellent reported
  quality; ~16 GB recommended VRAM, so it may not fit in 9.2 GB free.
  Tested with offloading; an OOM is recorded, not worked around silently.
- **InstantMesh** — optional second round if the first three disappoint.

**Texture stage**
- **Hunyuan3D-Paint** — the designed partner to the shape model above.
- **Stable Fast 3D** — Stability AI. Produces a textured mesh in one pass;
  as a combined model it breaks the split, so it competes as a *combined
  stage* candidate and is only adopted if it clearly beats the split pair.
- **Blender camera projection** — zero-model fallback: project the concept
  art onto the mesh from the concept camera. Crude (front only), always
  available, and the floor every learned texture model must beat.

## Benchmark protocol — Pip

- **Input (fixed):** `benchmarks/pip/input-idle.png` — the exact 1240×1240
  RGBA cutout that produced the reference.
- **Reference:** the owner's Meshy Pip OBJ + texture, rendered through the
  same scoring pipeline as the candidates.
- **Per candidate:** run the stage(s) → normalize in Blender (center,
  ground, scale to reference height) → render front / side / back /
  three-quarter at the matched scoring camera → record:
  - silhouette IoU vs the reference render, per view (0–1)
  - vertex / face counts of the raw output
  - wall-clock time and peak VRAM per stage
  - whether the process exited cleanly and VRAM was released
- **Verdicts:** RIGGABLE (clean silhouette; ears, wings, tail distinct;
  front IoU ≥ 0.75) / ROUGH (recognizably the character, needs cleanup) /
  MELTED (fail). The numeric score never overrules the visual sheet: a
  side-by-side render sheet goes to the owner for every bake-off round.
- The reference is a *target*, not ground truth — Meshy's Pip has its own
  inventions (e.g. crest and tail details). Scores measure closeness to the
  reference the owner approved, which is the point of the benchmark.

## Rig templates

- `winged-creature` — Pip's proven 14-bone layout (root, spine, head,
  ear.L/R, wing.L/R + wing2.L/R, leg.L/R, tail.1–3). Lands with P0.
- `quadruped` — 15 bones: a spine/hips pair splitting the root so the
  front and rear can pitch independently, neck + head at the front,
  two-segment legs at all four corners, tail.1–2. Recipes: `idle`,
  `bounce` (a two-hop happy bounce). P1 considered and rejected a
  walk cycle — without ground-truth footfall timing it would be
  invented motion, while the bounce's honesty is checkable in a
  still. **Superseded by P4 (2026-11-08) at the owner's direction:**
  the builder now produces game locomotion from a stated phase
  model whose invariants (loop closure, phase offsets, fold timing)
  are checkable mathematically and in playback — see "Locomotion
  (P4)" below. Landed with P1.
- `biped` — 11 bones (13 with `--ears`): vertical root/spine/head,
  two-segment arms and legs. The arm bones use a horizontal roll —
  measured in Blender, that is what makes local +X the symmetric
  raise axis a wave needs. Recipes: `idle`, `wave` (plus P4
  locomotion — see below). Landed with P1.
- Props — not a template: a pipeline mode (`--prop`) that runs
  prep → mesh → texture → clean static export → catalog with no rig
  or animate stage, and catalog provenance that records the asset as
  unrigged (`rigged: false`, no bones, no actions, no weight method).
  Landed with P1.
- Facing is a per-run input, not a template assumption: Hunyuan does
  not always emit the canonical facing, so the rig stage accepts
  `--rotate-z {0,90,180,270}`, recorded in the rig report and the
  catalog provenance. (The first quadruped mesh arrived sideways;
  the correction is how the template was proven on it.)

## Locomotion (P4)

Added 2026-11-08 at the owner's direction: the builder produces
walking animations and the other animation a game needs, starting
with a standard locomotion set — `walk` and `run` for every rig
template, baked by the same animate stage from the same pose-recipe
machinery as `idle`/`hop`/`wave`/`bounce` (no new stage, no new
meshes, no GPU work).

The gait model (`stages/animate/poses.py`, P4 section) is one pair
of curves per leg over a step-cycle phase φ ∈ [0, 1):
`gait_swing(φ) = sin(2πφ)` (+1 foot fully forward) and
`gait_fold(φ) = max(0, sin(2π(φ + 0.12)))³` — the lower-leg fold,
zero through stance and peaking just after the leg passes vertical
into swing-through. Rig classes differ only in phase pattern:
biped-plan templates (biped, winged-creature) run an anti-phase
pair (L 0.0, R 0.5) with arms counter-swinging; the quadruped walk
is a lateral sequence (FL 0.0, HR 0.25, FR 0.5, HL 0.75) and its
run is a bounding gallop (front pair 0.0, hind pair 0.5, spine
rocking, once-per-cycle body bounce). Runs use the same patterns
at a shorter period with larger swing/fold amplitudes and a
forward lean. Every term is periodic in the cycle, so loops close
exactly by construction. New drivers (legs on all templates, the
biped's fore-aft arm swing on local Z with mirrored signs) were
axis-probed on the shipped rigged GLBs before use, the same
empirical discipline as P0/P1; the probe numbers are recorded in
`stages/animate/animate_blender.py`.

Honest limits: these are procedural gaits — functional game
locomotion, not mocap. There is no IK and no ground-truth footfall
data behind the phase model (the P1 reservation stands as a
description of what the model is not); foot placement is
approximate, and foot-slip against ground speed is a property of
the consuming game's root-motion matching, not measurable in an
in-place cycle. The winged template's legs are single-segment, so
its gaits have no knee fold, and on the Ember Dragon's seated
upright body plan the walk reads as a shuffle-step rather than a
stride. Ground clearance was measured across the walk cycles
(evaluated-mesh minimum Z vs rest): no material penetration
(worst case ≈ 0.007 units on a 2-unit character, Snow Goblin and
Triceratops; the dragon's lowest point never reaches its rest
minimum).

## Out of scope for P0

UI (P2), engine integrations (P3), text-to-image concept generation (the
builder accepts a supplied or separately generated image), and any cloud
fallback — there is none, by decision 1.

## Concept pose & separation spec

Added 2026-11-06 with the P2 cleanup slice. This is concept-art
direction, decided before generation — not a rigging pose. It exists
because of a measured failure, not a preference: the Snow Goblin's
concept rests its arms in one fused fur mass with the torso, the mesh
stage faithfully built that mass, and the skinning stage then had no
boundary to respect — the shipped wave dragged the torso with the
arm. Rig poses (A-pose, T-pose) are applied to a mesh that already
exists; they cannot separate limbs the concept fused, and they say
nothing useful about quadrupeds at all. Separation has to be in the
silhouette the mesh is built from.

The rule underneath every body plan below is the same: wherever two
body parts will need different bones, the concept must show
background — visible daylight — between them. If a rigger looking at
the silhouette cannot draw the boundary, the automatic weights will
not find it either.

### Bipeds

- A-pose stance: arms angled down and away from the body, not
  hanging straight against it and not raised.
- Visible daylight between each arm and the torso along the arm's
  whole length, shoulder to hand. The shoulder join itself touches;
  everything below it must not.
- Legs separated, with daylight between them.
- Nothing resting against the torso: no arm, hand, tail, prop, or
  clothing mass lying on the body.
- No crossed limbs. Hands clear of the hips, not overlapping the
  pelvis silhouette.

### Quadrupeds

- Standing square, weight on all four legs; no sitting, crouching,
  or lying poses.
- Legs vertical and separated: daylight between the front pair,
  between the rear pair, and between every leg and the belly. In a
  three-quarter view the far-side legs must still read as their own
  silhouettes, not as a widening of the near-side legs.
- Belly clear of the ground — a low-slung body whose underside
  nearly touches the floor fuses with the legs in the mesh.
- Neck and head up, clear of the shoulders.
- Tail hanging or held away from the body, touching neither the
  legs nor the flank.

### Winged creatures

- Wings raised or folded clear of the arms and torso where the
  design allows; a wing membrane that drapes over an arm fuses the
  two exactly as fur does.
- Arms, if the design has them, follow the biped rule: away from
  the body, daylight along the whole arm.
- Wing fingers and tail clear of the legs.

### All body plans

- Full body in frame, head to feet; nothing cropped.
- Plain background, no scenery, no ground shadow mass under the
  body.
- No props touching the body.
- No limb occluding another limb against the torso — a far arm
  hidden directly behind the body is a fused arm for mesh purposes.

### Canonical prompt blocks

Paste-ready, with the subject description in front. The giraffe
concept that the pre-flight check (stage 0,
`stages/prep/preflight.py`) was calibrated against was generated
with the quadruped block and is its worked example: four separated
legs, belly clear, tail away from the legs.

Biped:

> Full-body character concept, standing in a relaxed A-pose on a
> plain white background: arms angled away from the torso with
> clear empty space between each arm and the body along the whole
> arm, hands clear of the hips, legs slightly apart with empty
> space between them, no crossed limbs, nothing touching or resting
> against the torso, no props, whole body inside the frame.

Quadruped:

> Full-body animal concept, standing square on a plain white
> background: all four legs straight, vertical, and clearly
> separated, with empty space between the front legs, between the
> back legs, and between the legs and the belly; belly well clear
> of the ground; neck and head held up; tail hanging away from the
> body, touching neither the legs nor the flank; no props, whole
> body inside the frame.

Winged:

> Full-body winged character concept on a plain white background:
> wings raised and folded clear of the arms and torso, each wing
> separated from the body by visible empty space where the design
> allows; arms angled away from the body with clear empty space
> between each arm and the torso along the whole arm; legs slightly
> apart; tail clear of the legs; no props, whole body inside the
> frame.
