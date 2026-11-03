# Muse handoff — AI Animation Studio

**Project folder:** `projects/ai-animation-studio/`.
**Branch family:** `ai-animation-studio/<milestone>`. **Current delivery:** documentation + executable foundation + F1 asset adoption (Quaternius rig, catalogued assets, GLB playback in preview); NOT a finished animation platform.
**Priority:** finish F0 verification then F1 visual vertical slice; do not expand to local AI before a clean animation baseline.

## Read first

Root `AGENTS.md`, project `AGENTS.md`, `docs/PRODUCT_SPEC.md`, `docs/ARCHITECTURE.md`, `docs/SCENE_PROTOCOL.md`, `docs/RIG_CONTRACT.md`, `docs/ROADMAP.md`, `docs/TEST_PLAN.md`, `docs/IMPLEMENTATION_STATUS.md`.

## Immediate work order

1. Inspect PR/branch and any concurrent main changes. Keep other projects untouched.
2. Run Python unit tests and CLI; fix genuine failures in this folder; record exact evidence.
3. Run Godot import and procedural scene on actual hardware; remove runtime/parser failures; measure baseline render FPS.
4. ~~Replace capsules with **original/licensed** two stylized rigged characters on `studio_humanoid_v1`~~ — done 2026-11-03 for characters (Quaternius CC0, ADR-007; preview loads GLBs when the local asset store is present, capsules otherwise). Still open from this step: a simple modular room — the Kenney Furniture Kit is downloaded and catalogued but not yet placed in the preview stage.
5. Add AnimationTree locomotion, idle, look-at and simple gesture layers. Preserve command format; write tests for timing and state transitions.
6. Implement validated production asset resolver enforcing approved status/version/rig compatibility; no untrusted path loads.
7. Update docs with proven behaviors and start F1 acceptance measurements.
8. Open/maintain reviewable PR; do not auto-merge or modify other repos.

## Boundaries

The runtime should never block on the LLM or asset generation. No AthenZ, Developmental-AI, Synveil, Crawl or existing project integrations. Use local/offline defaults. Do not commit model weights or media. Prototype dialogue logs are not speech synthesis. 30 FPS remains an untested goal until measured.

## Definition of done for first playable

Two independently spawned identifiable stylized characters, a room, transitions between several motions, dialogue beat timing, stable camera, rerunnable test/demo commands, and documented frame metrics on owner hardware. If unavailable, report blockers explicitly and keep work reviewable.
