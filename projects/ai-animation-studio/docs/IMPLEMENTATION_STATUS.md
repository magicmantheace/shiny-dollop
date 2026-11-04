# Implementation status — 2026-11-03

## Implemented and verified (see "Verified" below for exact evidence)

- Python stdlib CLI: validate, initialize SQLite, seed candidate examples, list assets and export demo scene.
- Runtime input validator for scene, asset and modular character metadata.
- SQLite schema with assets, characters, scenes, validation logs and dependency edges.
- Example JSON Schemas/fixtures.
- Godot 4 procedural preview scene with spawn/move/speak/emote/camera timeline execution — executed headless on a Linux VM (script/timeline proof only; not rendering or owner-hardware evidence).
- Unit tests, documentation and Muse handoff.
- F1 asset adoption (2026-11-03): Quaternius universal rig adopted as `studio_humanoid_v1` (ADR-007); catalog fixture with 9 candidate assets + 2 character recipes registered through a new `studio register` CLI command; Godot preview loads the real GLB characters and plays manifest-mapped clips (idle/walk/speak) when the local asset store is present, with capsule fallback otherwise; tavern scene v2 authored and validated.
- F1 completion pass (2026-11-03): explicit `studio promote` flow (candidate -> approved) with machine-checked gates recorded in `validation_runs` and human gates recorded as pending, never auto-passed; the demo export now attaches library approval state (per-asset status, pinned version, SHA-256) to the manifest and the Godot preview resolves ONLY approved, version-pinned, hash-verified files (ADR-008), with named rejections + capsule fallback; a minimal tavern set (Kenney table, 2 chairs, kitchen bar) is placed from the catalogued Furniture Kit through the same verified path; `hand_l`/`hand_r`/`head` sockets measured from the actual skeletons and recorded in `docs/RIG_CONTRACT.md`.

## Planned / not implemented

- Retargeting, AnimationTree blending, IK and modular wardrobe rendering (F1 loads the rigged characters and plays whole clips; no blending or wardrobe yet). Facial blendshapes: the adopted Quaternius exports contain none (see F1 evidence), so expression work needs a future rig revision.
- A fully dressed 3D room: a minimal tavern set (table, two chairs, bar counter) is placed through the verified resolver path (see F1 completion evidence); walls, set dressing and per-piece scale/orientation review remain open and need the owner-hardware visual check.
- LLM, reasoning, text-to-speech, phoneme timing, audio and blendshape lip sync.
- Live streaming IPC, dynamic camera behavior, persistent scene playback, asset generation and automation.
- Full runtime JSON Schema enforcement or production approved-asset resolution.
- Real performance profiling and Windows packaging.
- Speak/camera timing semantics: adopted by the owner 2026-11-03 (provisional; ADR-009) as canonical in `docs/SCENE_PROTOCOL.md` and **implemented the same day** — derivation in `studio/timing.py`, optional scene `timing` object validated on the Python side and in `schemas/scene.schema.json`, per-actor hold scheduling in the Godot preview with the rate (default 15 chars/sec) and clamps (default 800–15000 ms) as changeable variables (scene `timing` object or the preview's exported settings). Headless probe evidence in `docs/TEST_PLAN.md`; visual pacing remains an owner-hardware check.

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

### F1 asset adoption pass (2026-11-03, Linux VM — NOT owner hardware)

Owner decision (2026-11-03): adopt Quaternius as `studio_humanoid_v1` (ADR-007 in `docs/DECISIONS.md`; rig facts in `docs/RIG_CONTRACT.md`).

- **Downloads** (all CC0, $0, into the local store `~/workspace/ai-animation-studio-assets/`, outside git): Universal Base Characters [Standard].zip 128,968,391 B and Universal Animation Library [Standard].zip 15,904,933 B and Universal Animation Library 2 [Standard].zip 18,735,003 B from the packs' itch.io pages (quaternius.itch.io), plus Kenney Furniture Kit 5,130,729 B (140 GLB models) from kenney.nl. Paid Source tiers were not downloaded.
- **glTF inspection** (Python stdlib parser over the actual files): both base bodies share one **65-joint** skeleton with identical bone names; male bind-pose height ≈ 1.81 m; **morph targets: 0** on both bodies, eyebrows, hair and mannequin — the adopted exports have no facial blendshapes. Each animation GLB (UAL1/UAL2, in-place and `_RM` root-motion variants) contains **43 clips** (86 unique across the two libraries) — the advertised 120+/130+ figures do not match the Godot GLB contents; the earlier third-party count of ~46 was closest. 18 reusable animation tags are mapped to verified clip names in `examples/asset_manifest.json` (idle, walk, walk_formal, jog, carry_walk, crouch_idle, sit_enter, sit_idle, sit_exit, sit_talk, speak, interact, pickup, consume, dance, emote_yes, emote_no, emote_wave).
- **Library registration:** `python3 -m studio register` catalogues the 9 assets + 2 characters from `examples/quaternius_f1_catalog.json` as `status=candidate` in the local SQLite DB (gitignored; verified `git check-ignore`). Register is idempotent (covered by tests). `python3 -m studio validate` now also validates the v2 scene and the catalog. Full suite: `python3 -m unittest discover -s tests` → `Ran 24 tests`, `OK` (17 prior + 7 new F1 tests).
- **Godot preview upgrade** (`godot/main.gd`): the hardened load-time validation is unchanged. When `godot/data/asset_manifest.json` exists (written by `python3 -m studio demo`, which now also accepts `--scene`) and `AI_ANIMATION_ASSET_ROOT` points at the asset store, spawn loads the recipe's GLB via `GLTFDocument`, merges the UAL1+UAL2 clips into one `AnimationPlayer`, and plays the manifest tags: idle on spawn, walk during move, speak gesture during speak lines, back to idle afterwards. Clip selection only — the adopted speak/camera timing semantics (ADR-009) remain unimplemented.
- **Headless evidence** (Godot 4.7.2, same VM; logs captured in full, zero errors/warnings in each):
  - Assets present (`AI_ANIMATION_ASSET_ROOT` = the store, v2 scene exported via CLI): `AI Animation Studio preview: tavern_meeting_v2`; `Loaded character model for innkeeper: …/Superhero_Female_FullBody.gltf` and `… traveler: …/Superhero_Male_FullBody.gltf`; `traveler animation walk -> Walk_Loop` during the approach; `traveler animation speak -> Idle_Talking_Loop` and `innkeeper animation speak -> Idle_Talking_Loop` on the dialogue lines; idle resumed after moves and lines; camera lines for `two_shot` and `wide`.
  - Asset root pointed at an empty directory: `Capsule fallback for innkeeper: model unavailable at …` (same for traveler), then the plain dialogue/emote/camera lines — fallback works.
  - No manifest present (fresh-clone configuration, in-git `demo_scene.json`): output byte-identical to the F0 baseline five lines. The in-git demo is behaviorally unchanged.
  - `Godot … --headless --path godot --import` → exit 0 with the upgraded script.
  - Boundary: headless proves script execution, GLB loading and clip scheduling. It does **not** prove visual correctness (orientation, scale on screen, materials), rendering, or performance; no FPS claim is made. Owner-hardware/editor check is still outstanding.
- **Vendor quirk recorded:** the character `.gltf` files reference two textures by names absent from the zip (`T_Hair_1_Normal_png.png`, `T_Eye_Normal_png.png`); the identical shipped PNGs were copied under the referenced names inside the asset store so all external references resolve. Store layout and provenance are documented in the store's own `README.md`.
- One real defect found and fixed during the pass: Godot 4.7 renamed the no-loop constant — `Animation.LOOP_DISABLED` no longer parses; the loader uses `Animation.LOOP_NONE` (verified by direct probe against the 4.7.2 binary).

### F1 completion pass (2026-11-03, Linux VM — NOT owner hardware)

- **Promotion flow** (`studio/promotion.py`, CLI `python3 -m studio promote`): machine gates per asset — status is candidate, source media present under the asset root, SHA-256 matches the catalog, skeleton facts (skin joint count vs the catalog declaration, parsed from the glTF document by `studio/gltf.py`), clip inventory for motion assets (names + durations vs the catalog), and per-piece hashes for the furniture pack directory. Character gates: body asset approved, rig match, hair asset approved when catalogued. Gate results are written to `validation_runs`; human gates (`visual_review`, `owner_hardware_visual`) are printed and recorded as pending on every promotion — they are not passed by this flow.
- **End-to-end proof on the F1 catalog** (fresh DB at `/tmp/anim-f1c/proof.db`): `register` -> `promote` promoted all **9 assets + 2 characters** with every machine gate PASS (exit 0); `list-assets` then shows all `[approved]`. Catalog fixture gained per-asset `version` (metadata), SHA-256 + joints for the two hair GLBs, and per-piece SHA-256 digests for all 14 furniture pieces (all values computed from the store files).
- **Resolver hardening** (ADR-008): `studio demo` now enriches the exported manifest from the library DB — an `assets` map (uri -> asset_id/status/version/sha256), per-recipe `files` pins, and stage-piece status/version/sha256. `godot/main.gd` verifies status (approved in both pin and record), version pin equality, pin-vs-record hash equality, and the on-disk file SHA-256 (HashingContext) before loading; failures print a named rejection and fall back.
- **Approved-path headless run** (Godot 4.7.2, store set, tavern v2 exported from the promoted DB): `Placed furniture: table.glb at (0.0, 0.0, 1.7)`, `chair.glb` at (-0.85, 0.0, 1.7) and (0.85, 0.0, 1.7), `kitchenBar.glb at (3.6, 0.0, -2.0)`; both character models loaded; full idle/walk/speak/emote/camera sequence; zero errors/warnings.
- **Tamper probes** (exported manifest edited in place, one fault each, restored after): status flipped to candidate -> `Capsule fallback for traveler: asset rejected — assets/characters/Superhero_Male_FullBody.gltf status is 'candidate' (approved required)`; one pin hash character corrupted -> `… UAL1_Standard.glb catalog hash mismatch (pin vs library record)`; pin version bumped -> `… Superhero_Female_FullBody.gltf version mismatch (pin 9.9.9 vs library 1.0.0)`; pin+record hash replaced -> `… sha256 mismatch (file does not match the approved record)`. In each probe the unaffected actor still loaded and nothing crashed.
- **Fallback runs**: empty asset root -> furniture skipped lines, capsule fallback for both actors, full dialogue/camera sequence, zero errors. Fresh-clone configuration (no manifest, in-git demo scene) -> output identical to the F0 baseline five lines.
- **Sockets measured** (`python3 -m studio sockets`): male `hand_l` [0.706, 1.455, -0.065], `hand_r` [-0.706, 1.455, -0.065], `Head` [0.0, 1.600, -0.017]; female `hand_l` [0.641, 1.418, -0.052], `hand_r` [-0.641, 1.418, -0.052], `Head` [0.0, 1.550, -0.011] — recorded with method in `docs/RIG_CONTRACT.md`.
- **Tests:** full suite `python3 -m unittest discover -s tests` -> `Ran 32 tests`, `OK` (24 prior + 5 promotion-gate tests on synthetic GLB fixtures + 3 catalog/manifest state tests). No FPS or visual-correctness claim is made.
- **Speak timing implementation** (ADR-009, later on 2026-11-03): `studio/timing.py` owns the deterministic derivation (explicit `duration_ms` wins at wire bounds 100–60000 ms; otherwise `ceil(len(line) * 1000 / rate)` clamped to the configured window); `studio/schema.py` + `schemas/scene.schema.json` validate the optional scene `timing` object and speak `duration_ms`; `godot/main.gd` precomputes effective dispatch times at load (per-actor gating only, camera never gated, spawn never gated; dispatch order is (effective time, scene order)), drives the speak gesture for the hold instead of the clip length, and logs the effective timing configuration, every hold, and every delay. The variables live in three surfaces with one set of defaults — the scene `timing` object, the preview's exported settings, and `studio/timing.py` — with a parity test holding them together. Evidence: suite 49/49 OK; headless probes for delay, explicit duration, both clamps, and both scene overrides all produced the computed times; baseline demo and approved-path runs unchanged apart from the new timing log lines (full record in `docs/TEST_PLAN.md`).

## Known technical follow-ups

- Godot import + headless playback verified on Godot 4.7.2 (Linux); editor/visual rendering compatibility on owner hardware still to confirm.
- ~~Wire actual rigged character assets through a pinned/approved asset resolver instead of demo capsules~~ — addressed 2026-11-03 (F1 completion, ADR-008): promotion flow, approved-status/version pinning and SHA-256 verification at load are implemented and probe-tested. The promotion lives in the local library DB; the committed catalog fixture intentionally stays `candidate` (registration is the intake state, promotion is a local explicit act).
- ~~Place the catalogued Kenney furniture in the preview stage; measure/define hand/head sockets on `studio_humanoid_v1`~~ — addressed 2026-11-03 (F1 completion): minimal tavern set placed through the verified path; sockets measured and recorded in `docs/RIG_CONTRACT.md`. Still open: visual review of furniture scale/orientation and a blendshape-capable head for expressions (the adopted rig has none).
- Visual check of the loaded characters (orientation, on-screen scale, materials/textures) in the editor on owner hardware; the headless pass could not see them.
- Add DB migrations, schema validators or proven equivalent, metadata provenance, integrity verification and command/event queues.
- ~~Tighten preview command rejection on the Godot side~~ — addressed 2026-11-03: the preview now re-validates schema version, container types, op whitelist and vector shapes at load and fails closed per event (see F1 prep verification above). Full semantic validation (ordering, spawn state, bounds) still lives only in `studio/schema.py`.
- Godot 4.7 import generates `godot/main.gd.uid` (script UID file); currently untracked — commit or ignore per owner preference.
