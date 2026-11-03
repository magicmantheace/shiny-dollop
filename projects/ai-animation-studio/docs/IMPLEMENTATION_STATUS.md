# Implementation status — 2026-11-03

## Implemented and verified (see "Verified" below for exact evidence)

- Python stdlib CLI: validate, initialize SQLite, seed candidate examples, list assets and export demo scene.
- Runtime input validator for scene, asset and modular character metadata.
- SQLite schema with assets, characters, scenes, validation logs and dependency edges.
- Example JSON Schemas/fixtures.
- Godot 4 procedural preview scene with spawn/move/speak/emote/camera timeline execution — executed headless on a Linux VM (script/timeline proof only; not rendering or owner-hardware evidence).
- Unit tests, documentation and Muse handoff.

## Planned / not implemented

- Genuine rigged and animated stylized characters; retargeting, AnimationTree, IK and modular wardrobe rendering.
- LLM, reasoning, text-to-speech, phoneme timing, audio and blendshape lip sync.
- Live streaming IPC, dynamic camera behavior, persistent scene playback, asset generation and automation.
- Full runtime JSON Schema enforcement or production approved-asset resolution.
- Real performance profiling and Windows packaging.
- Speak/camera timing semantics: proposed in `docs/SCENE_PROTOCOL.md` (2026-11-03, marked PROPOSED); awaiting owner sign-off before any validator or renderer implementation.

## Verified

### At initial authoring (2026-11-03)

- Repository structure, README/AGENTS conventions and target branch were inspected before writing.
- JSON fixture/schema source was serialized syntactically by the authoring tool.

### F0 verification pass (2026-11-03, Linux VM — NOT owner hardware)

Environment: Linux VM, Python 3.12.3, Godot 4.7.2.stable.official (official Linux x86_64 build). All commands run in `projects/ai-animation-studio/` unless noted.

- **Automated Python tests:** `python3 -m unittest discover -s tests` → `Ran 8 tests in 0.005s`, `OK`, exit 0.
- **CLI exercise** (scratch DB/output under `/tmp/anim-f0/`, nothing written into the project):
  - `python3 -m studio validate` → `Validated scene, asset, character examples`, exit 0.
  - `python3 -m studio init-db --db /tmp/anim-f0/studio.db` → `Initialized /tmp/anim-f0/studio.db`, exit 0.
  - `python3 -m studio seed --db /tmp/anim-f0/studio.db` → `Seeded candidate examples; no production media files supplied`, exit 0.
  - `python3 -m studio list-assets --db /tmp/anim-f0/studio.db` → `mug_wood_01 [candidate] assets/props/mug_wood_01.glb`, exit 0.
  - `python3 -m studio demo --out /tmp/anim-f0/scene_runtime.json` → `Saved 7 validated events`, exit 0.
  - Re-running `seed` against the same DB exits 0 with no duplicate-asset error (idempotent seed write).
- **Godot import:** `Godot_v4.7.2-stable_linux.x86_64 --headless --path godot --import` → filesystem scan and editor layout load completed, exit 0, no errors or warnings.
- **Godot scene playback (headless):** `timeout 18 Godot_v4.7.2-stable_linux.x86_64 --headless --path godot` ran the main scene (`tavern_meeting_demo`, timeline ends at 9500 ms) to completion of all events; stdout contained exactly the expected log lines and no errors/warnings:
  - `AI Animation Studio preview: tavern_meeting_demo`
  - `traveler emotion: nervous intensity: 0.65`
  - `traveler: Excuse me, do you have a room for the night?`
  - `innkeeper: We have one upstairs. Come in.`
  - `Camera request: wide`
  - Boundary: headless uses a dummy rendering driver. This proves GDScript parsing, scene load and timeline/event execution; it does **not** prove rendering, editor/visual behavior, or performance.
- **Owner-hardware FPS:** not run. 30 FPS remains an untested goal until measured on owner hardware.

### F1 prep verification (same pass, 2026-11-03, Linux VM)

- **Schema/validator conformance tests:** `tests/test_conformance.py` added (stdlib only) asserting the JSON Schemas and `studio/schema.py` agree on schema_version, op set, emotion set and camera shot set, plus accept/reject fixture scenes for `validate_scene`. Full suite after the addition: `python3 -m unittest discover -s tests` → `Ran 17 tests`, `OK`, exit 0. Drift guard proven by negative check: adding a rogue op to `scene.schema.json` in a scratch copy fails exactly the op-set conformance test (1 failure, as designed).
- **Godot-side scene re-validation** (`godot/main.gd`): load now refuses unsupported `schema_version`, type-checks the actors/events containers and actor entries, skips events with unknown ops or malformed spawn/move vectors with an indexed `push_error`, and parses vectors through a checked helper instead of indexing blindly. Evidence (same Godot 4.7.2 headless setup as above):
  - Unmodified demo scene re-run after the change: stdout identical to the pre-change run (same five lines, no errors) — valid-scene behavior unchanged.
  - Rejection probes in a scratch copy (via `data/scene_runtime.json` variants): `schema_version: "9.9.9"` → `ERROR: Unsupported schema_version (expected 1.0.0)`, playback refused. Injected unknown op `explode` plus a 2-element spawn position → `ERROR: events[2]: unknown op 'explode'; event skipped` and `ERROR: events[1]: spawn position is not an array of exactly 3 numbers; event skipped`; the scene then completed without crashing (the unspawned actor's later events produced only the pre-existing "Actor not spawned" warnings).

## Known technical follow-ups

- Godot import + headless playback verified on Godot 4.7.2 (Linux); editor/visual rendering compatibility on owner hardware still to confirm.
- Wire actual rigged character assets through a pinned/approved asset resolver instead of demo capsules.
- Add DB migrations, schema validators or proven equivalent, metadata provenance, integrity verification and command/event queues.
- ~~Tighten preview command rejection on the Godot side~~ — addressed 2026-11-03: the preview now re-validates schema version, container types, op whitelist and vector shapes at load and fails closed per event (see F1 prep verification above). Full semantic validation (ordering, spawn state, bounds) still lives only in `studio/schema.py`.
- Godot 4.7 import generates `godot/main.gd.uid` (script UID file); currently untracked — commit or ignore per owner preference.
