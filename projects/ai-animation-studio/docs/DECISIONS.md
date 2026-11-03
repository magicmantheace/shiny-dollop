# Architecture decisions

## ADR-001: Render poses, not video pixels

**Accepted.** Godot renders stylized 3D; AI emits semantic action/scene commands. This avoids full video diffusion costs and allows deterministic playback.

## ADR-002: Offline-first, persistent assets

**Accepted.** SQLite and local files are durable catalog; generated candidates require validation before promotion. No cloud dependence.

## ADR-003: Fixed humanoid rig family

**Accepted for MVP.** A canonical rig permits reusing animations across modular characters. Other creature types use separate rig_id families.

## ADR-004: Separate offline generation from frame loop

**Accepted.** Asset generation cannot stall gameplay/animation; use asynchronous jobs and fallbacks.

## ADR-005: Python stdlib + Godot 4

**Accepted for initial foundation.** Python provides validation/catalog CLI without dependency installation; Godot renders preview. Future local inference adapters can be independent processes.

## ADR-006: Reviewable branch, independent project

**Accepted.** Do not modify other project implementations; root README registration only.

## Open decisions

- Model runtime (llama.cpp/Ollama or another) after resource profiling.
- Voice/TTS engine after licensing/latency/VRAM testing.
- IPC transport once deterministic runtime succeeds.

## ADR-007: First canonical humanoid rig source — Quaternius (2026-11-03)

**Accepted (owner decision, 2026-11-03).** `studio_humanoid_v1` is the
Quaternius universal humanoid rig, adopted from the free Standard (CC0)
packs: Universal Base Characters, Universal Animation Library 1 and
Universal Animation Library 2, plus the Kenney Furniture Kit (CC0) as the
first environment source. Cost $0; CC0 permits redistribution of the raw
files, which the studio's local asset library requires.

- Runner-up: KayKit character packs ($0, CC0) — not adopted because its
  line splits across two rigs (Rig_Medium / Rig_Large), breaking the
  one-rig-many-clips property the contract depends on.
- Rejected: Mixamo — royalty-free for use in projects, but its terms
  prohibit redistributing the raw model/animation files, which the
  studio library would do. Revisit only if the library model changes.
- Recorded limitation: the adopted exports contain **no facial
  blendshapes** (0 morph targets, verified by glTF inspection
  2026-11-03). The contract's preferred blendshape set stays a
  requirement for a future rig revision; F1 expression is body clips
  plus the emote event channel only.
- Media stays in a local asset store outside git (see
  `docs/ASSET_PIPELINE.md` storage policy); git carries the catalog and
  manifest metadata fixtures only.
