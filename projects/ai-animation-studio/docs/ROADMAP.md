# Roadmap with gates and ordered deliverables

## F0 — Foundation (this PR)
- Versioned scene, asset and character schemas and synthetic fixtures.
- SQLite local registry and CLI for seed/validate/demo.
- Godot procedural stand-in preview.
- Agent rules, specs, tests, safety and acceptance criteria.
**Exit:** code checked into isolated project, CLI/unit tests and Godot import/run validated in a real environment; unverified until evidence exists.

## F1 — First visual vertical slice (highest priority)
- 2 licensed/original stylized 3D humanoid characters on a canonical rig.
- Simple furnished room, walk-to, idle, look-at, speak, basic animated expressions.
- 10–20 clips; 3 cameras; scene scheduler and fallback; owner hardware profiling.
**Exit:** repeatable 60s scene at measured >=30 FPS target, no runtime AI dependency.

## F2 — Persistent configurable cast
- Modular bodies/heads/hair/outfits, per-part compatibility rules, saved recipe editor.
- Asset version pinning, source/license records, import validation, SQLite migrations.
- Structured director-to-engine IPC, approved-asset enforcement.
**Exit:** assemble/save/load/replay 5 distinct character recipes without manual rig changes.

## F3 — Local AI direction & speech
- Small local LLM adapter generating strict intent; bounded planner with rejection/fallback.
- Offline TTS, cached voice clips, phoneme timing and blendshape lip sync.
- Dialogue timing, interrupts, safe event queue, camera cuts.
**Exit:** 2 actors converse autonomously without stalls on owner hardware.

## F4 — Motion + interactions
- AnimationTree layering, gaze, hand/foot IK, prop sockets, pick-up/sit/drink.
- Retargeting and action retrieval based on metadata and compatibility.
**Exit:** characters execute compositional multi-step actions without visible severe clipping.

## F5 — Expandable library workshop
- Background job queue, Blender import/retarget workers, validation previews.
- Missing-action reports, asset provenance + review, quarantined candidate store.
- Optional local generated motions or textures after profiling and licensing.
**Exit:** create and promote a previously missing reusable asset with reproducible test evidence.

## F6 — Autonomous shows (long term)
- Multi-scene continuity, world state, scene memory, pacing, cast consistency.
- Director evaluation, branching stories, archival/export pipelines.
**Exit:** long-form stable playback; not a v1 commitment.

**Build order policy:** do not jump to generated motion or autonomous worldbuilding before F1 hardware acceptance.
