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
| 3 | rig | Blender (CPU) | armature templates + automatic weights | textured mesh → rigged mesh |
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
  `bounce` (a two-hop happy bounce; a walk cycle was considered and
  rejected — without ground-truth footfall timing it would be
  invented motion, while the bounce's honesty is checkable in a
  still). Landed with P1.
- `biped` — 11 bones (13 with `--ears`): vertical root/spine/head,
  two-segment arms and legs. The arm bones use a horizontal roll —
  measured in Blender, that is what makes local +X the symmetric
  raise axis a wave needs. Recipes: `idle`, `wave`. Landed with P1.
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

## Out of scope for P0

UI (P2), engine integrations (P3), text-to-image concept generation (the
builder accepts a supplied or separately generated image), and any cloud
fallback — there is none, by decision 1.
