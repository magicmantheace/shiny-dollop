# Test plan and evidence requirements

## Environment-neutral commands (from this project directory)

```powershell
python --version
python -m studio validate
python -m unittest discover -s tests -v
python -m studio init-db --db data/local-smoke.sqlite3
python -m studio seed --db data/local-smoke.sqlite3
python -m studio list-assets --db data/local-smoke.sqlite3
python -m studio demo
```

## Tests committed

- `tests/test_schema.py`: valid contract examples, unknown actor, bad opcode, unsorted timestamps, path traversal, candidate recipe.
- `tests/test_library.py`: create schema, idempotent upsert and approved-only filter.

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
