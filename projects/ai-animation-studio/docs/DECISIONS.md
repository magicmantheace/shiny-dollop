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

## ADR-008: Approved-only, hash-pinned runtime resolution (2026-11-03)

**Accepted.** The Godot preview resolves character and stage assets
only through the exported library state: an asset loads only when its
catalog status is `approved`, the scene-side pin version equals the
library record version, the pin SHA-256 equals the library record, and
the file on disk hashes to that same SHA-256. Any mismatch is named in
the log and the actor/piece falls back (capsule / skipped) — never a
crash, never a silent load. Approval itself is an explicit
`studio promote` step whose machine gates (source presence, hash,
skeleton facts, clip inventory, per-piece pack hashes) are recorded in
`validation_runs`; human gates (visual review, owner-hardware visual /
FPS check) are recorded as pending and are never auto-passed, so an
asset can be `approved` for local playback while those reviews remain
honestly outstanding.

## ADR-009: Speak/camera timing semantics adopted with a tunable rate (2026-11-03)

**Accepted (provisional, owner sign-off 2026-11-03).** The speak/camera
timing semantics in `docs/SCENE_PROTOCOL.md` are adopted: an explicit
`duration_ms` wins; otherwise the speak hold derives from the line at
15 characters/second, clamped to 800–15000 ms; blocking is per-actor
only; camera cuts are instantaneous at `at_ms`; move and emote are
unchanged. Owner condition: the derivation rate and the clamp bounds
are changeable configuration variables with those values as defaults —
not hardcoded constants — so the rate can be increased later without
revisiting this decision. Validator/renderer implementation is a
separate step and has not been done yet.
**Implemented 2026-11-03.** `studio/timing.py` owns the derivation;
`studio/schema.py` and `schemas/scene.schema.json` validate the optional
scene `timing` object and speak `duration_ms` (wire bounds 100–60000 ms);
`godot/main.gd` schedules per-actor holds with the rate and clamps as
exported settings, overridable per scene. Suite 49/49 and headless probe
scenes (delay, explicit duration, both clamps, both scene overrides)
verified the computed times; see `docs/TEST_PLAN.md`.
