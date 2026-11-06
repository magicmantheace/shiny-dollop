# Game Asset Builder

**Status: P0 pipeline built and proven end-to-end (2026-11-06). The
Hunyuan3D-2 shape+paint pair won the Pip bake-off (RIGGABLE, front
silhouette IoU 0.84 vs the Meshy reference; `benchmarks/pip/scores.md`),
and the full pipeline — cutout → mesh → texture → rig → animate →
catalog — ran a brand-new creature (the Ember Dragon) from concept
image to a rigged, animated, catalogued .glb. Run it with
`python3 asset_builder.py run --concept <image> --name "<Name>"`.
Catalogue record: `catalog/ember-dragon/metadata.json` (the .glb
itself lives in the local `outputs/` area, pinned by sha256).**

A fully local, no-API pipeline that builds game assets — creatures included —
on the owner's own hardware:

```
concept image → cutout → [mesh model] → [texture model] → rig → animate → catalogued .glb
```

Mesh generation and texturing are **different local models**, each run as its
own stage in its own process, unloaded before the next stage loads. Rigging
and animation are procedural (Blender, headless), reusing the armature
templates and pose recipes proven on Pip, the Drabbit Pet character.

## Why

The Drabbit Pet's hero asset (Pip) was built by hand across a chain of
one-off tools, and its best mesh came from a cloud service. This project
turns that chain into one repeatable local tool, scored honestly: Pip is the
standing benchmark, and every local candidate is compared against the
cloud-generated reference Pip the owner already has.

## Hardware target

- Owner's PC: Windows 11, RTX 3060 **12 GB VRAM** (~9.2 GB free at rest),
  32 GB RAM. All heavy stages run here.
- The build VM has **no GPU** (7 GB RAM): orchestration, Blender work,
  cataloguing, and scoring only.

## Layout

- `docs/DESIGN.md` — founding decisions, stage architecture, candidate
  models, and the Pip benchmark protocol.
- `docs/TEST_PLAN.md` — what is verified, where, and what is not.
- `docs/MUSE_HANDOFF.md` — current state for the next working session.
- `stages/` — one folder per pipeline stage as they land.
- `catalog/` — the finished-asset catalog (lands with P0).
- `benchmarks/` — benchmark inputs, scores, and comparison sheets.

## Slices

- **P0** — model bake-off on Pip + the winning creature pipeline end-to-end
  (image → rigged, animated .glb + catalog entry).
- **P1** — more rig templates (quadruped, biped) + the unrigged prop path.
- **P2** — a simple local UI over the catalog and pipeline.
- **P3** — hand-off integrations (animation studio library, Godot projects).
