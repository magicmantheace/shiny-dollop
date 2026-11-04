# Test plan and evidence requirements

## Environment-neutral commands (from this project directory)

```powershell
python --version
python -m studio validate
python -m unittest discover -s tests -v
python -m studio init-db --db data/local-smoke.sqlite3
python -m studio seed --db data/local-smoke.sqlite3
python -m studio register --db data/local-smoke.sqlite3
python -m studio promote --db data/local-smoke.sqlite3
python -m studio list-assets --db data/local-smoke.sqlite3
python -m studio demo
python -m studio sockets
```

## Tests committed

- `tests/test_schema.py`: valid contract examples, unknown actor, bad opcode, unsorted timestamps, path traversal, candidate recipe.
- `tests/test_library.py`: create schema, idempotent upsert and approved-only filter.
- `tests/test_conformance.py`: JSON Schema <-> hand validator agreement (ops, emotions, shots, version) plus accept/reject fixture scenes.
- `tests/test_f1_catalog.py`: F1 catalog/manifest consistency (clip inventories, URI cross-references), per-asset version + hash presence, stage-piece validity, register idempotency, and demo export attaching library approval state.
- `tests/test_promotion.py`: promotion gates on synthetic GLB fixtures — success records gates + pending human gates; hash mismatch, missing file, and clip-inventory mismatch are refused; character promotion requires an approved body asset.
- `tests/test_timing.py`: speak-hold derivation (millisecond precision), min/max clamps, explicit-duration override and bounds, rate/clamps as variables, `timing` config resolution and rejection, scene validation of the `timing` object and speak `duration_ms`, and default parity across `studio/timing.py`, `schemas/scene.schema.json` and the exported settings in `godot/main.gd`.
- `tests/test_migrations.py`: migration framework (fresh DB migrates to latest, v1-shaped DB built from `database/schema.sql` upgrades with rows intact, init twice is a no-op, newer-than-code DB raises) and source/license records (validator bounds, JSON Schema license-enum parity, library round-trip with/without the fields, invalid license rejected by validator and library, F1 catalog fixture coverage).
- `tests/test_recipes.py`: recipe composition against a synthetic part catalog — happy-path assembly + save/get round-trip, unknown part (fixed slot and outfit entry), wrong-kind slot fit, rig mismatch, require_approved refusing a candidate part and accepting all-approved, multi-entry outfit lists incl. a rig-agnostic piece, malformed spec, and a CLI assemble round-trip with the non-zero refusal path.
- `tests/test_recipe_editor.py`: saved-recipe editor — slot/outfit/colors edits round-trip, incompatible edits (wrong kind, rig mismatch, unknown part, bad shape, unsupported field, no changes, unknown character) refused with the stored recipe byte-identical; CLI show/edit/export verbs incl. the lossless export -> assemble round-trip; and the F2 exit chain — 5 distinct synthetic recipes (two bodies, varied hair/outfit/colors, one rig) assembled, saved, loaded, and referenced by a validated replay scene.
- `tests/test_ipc.py`: director-to-engine IPC contract — envelope round-trip, unknown ipc_version/kind/key, missing/non-object/invalid payload and bad issued_at refusals (all named `IpcError`s), file helper round-trips and refusals, result document build/validate/write/read round-trip and refusals, demo CLI writing an enveloped runtime scene readable via `read_ipc`, and IPC_VERSION parity with `godot/main.gd`. (Godot-side envelope playback + `scene_result.json` acknowledgement are recorded as headless evidence in `docs/IMPLEMENTATION_STATUS.md`, F2 slice 4.)
- `tests/test_director.py`: F3.1 director — stub scene validation, byte-identical determinism and staging shape; planner first-accept, garbage-then-valid retry with the rejection recorded and fed back, adapter-error accounting, fallback after max attempts with a still-valid scene, and unknown-op refusal; HttpAdapter fenced/bare JSON extraction through a fake transport, `AdapterError` on transport failure / non-JSON / missing fields, non-loopback endpoint refusal, planner end-to-end via the fake transport, and the `plan` CLI writing an enveloped scene readable via `read_ipc`. (No live model: no LLM server exists on the VM.)
- `tests/test_voice.py`: F3.2 voice — stub WAV validity (mono 16-bit 16000 Hz) and sample-exact durations vs `speak_hold_ms` for derived, explicit, min/max-clamped and custom-rate cases, plus byte determinism; external engine through fake runners only (argv/`{voice}` shape, `VoiceError` on runner failure and on garbage or non-bytes output); phoneme table exact partition of the hold (contiguity, first/last bounds, sum, no empty segments) across several lines including one-word and wordless lines, length proportionality, and the documented viseme onset rule; cache record fields, a hit avoiding re-synthesis (counting engine), persistence across cache instances, distinct keys per voice / rate / explicit duration, corrupt-entry re-synthesis, and the `speak` CLI synthesize-then-cache round-trip. (No real engine: no TTS engine exists on the VM.)

## F1 completion evidence (2026-11-03, Linux VM — not owner hardware)

- Fresh DB: `register` -> `promote` promoted all 9 F1 assets + 2 characters, every machine gate PASS, human gates printed as pending.
- Godot 4.7.2 headless, approved path: furniture placement lines (table, 2 chairs, kitchenBar), both character GLBs loaded, full clip sequence, zero errors.
- Tamper probes on the exported manifest (status flip, pin hash corruption, version bump, pin+record hash replacement): each produced its named rejection line + capsule fallback for the affected actor only.
- Empty-store run: furniture skipped, capsule fallback, full dialogue sequence, zero errors. Fresh-clone run: byte-identical output to the F0 baseline.
- Full suite: 32 tests, OK. No FPS or visual-correctness evidence exists yet; both remain owner-hardware items.

## Speak timing evidence (2026-11-03, Linux VM — not owner hardware)

- Full suite: 49 tests, OK (32 prior + 17 timing).
- Godot 4.7.2 headless probe scenes (validated by `studio/schema.py`, run via the runtime-scene slot, logs asserted on the preview's printed logical times): per-actor delay — same-actor emote at 1000 ms inside a 3000 ms derived hold dispatched at 3100 ms while another actor's emote and a camera cut at 1000 ms fired on time; explicit duration — a 5000 ms explicit hold delayed a same-actor emote 2000 -> 5100 ms; clamps — a 2-char line held the 800 ms minimum (delay 5500 -> 6000 ms) and a 500-char line held the 15000 ms maximum (delay 10000 -> 21100 ms); scene variables — `timing` rate 30 halved a 45-char hold to 1500 ms (delay -> 1600 ms), scene min clamp 2000 raised a short line's hold to 2000 ms (delay -> 2100 ms).
- Baseline demo and F1 approved-path runs under the new scheduler: no delays, derived holds 2934 ms (traveler) and 2000 ms (innkeeper), furniture/models/clips unchanged, zero errors. One defect found and fixed during the probes: Godot's JSON parser returns numbers as floats, so integral-value acceptance is shared by the explicit-duration and clamp-override checks.

## Godot manual acceptance

1. Install Godot 4.x; open `godot/project.godot`; run.
2. Confirm visible floor and two differently colored capsule actors.
3. Confirm traveler moves toward innkeeper and dialogue/emotion output prints.
4. Run Python `demo`; confirm generated override is read at next Godot start.
5. Run with malformed plan; failure must be reported without executing arbitrary operations.
6. Record Godot version, errors, FPS on RTX 3060; current code has **not** been run in Godot by this author.

## Future acceptance suites

- Contract: schema version rejection, max event/actor counts, invalid operation and payloads.
- Persistence: restart, migration, bad DB, rollback and concurrent readers.
- Asset security: traversal, symlinks, disallowed formats, unapproved asset, missing rig, provenance.
- Motion: retarget clips, IK foot locking, prop sockets, speech visemes, camera collision.
- Stress: 60s live scene, LLM timeout, asset builder running, VRAM exhaustion.
- Recovery: replay determinism, crash restart, missing assets and corrupted plan.

## Evidence log convention

Record exact command, environment, commit SHA, PASS/FAIL/SKIPPED, observed output and screenshots/frame metrics if applicable. Do **not** change status from unverified merely because tests exist.
