# Test plan — Game Library Metadata Enricher

**Current test status:** RUN 2026-10-23 (Linux VM, Node 24) — **82/82 pass**:
`tests/*` backend (32): scanner, artwork validation, library CRUD, undo, bundle
round-trip/conflict/version rules, **acceptance walkthrough** (import 3-game
fixture → edit title/description/tags/artwork → missing detection without
deletion → export v1.0.0 bundle → wipe → re-import identical);
`renderer/tests/*` (50): search/filters, missing badge, artwork assignment,
tag/collection management, bundle import conflicts display, undo, form
validation, missing-flag merge (`hooks.test.tsx`).
`npm run typecheck` clean (main+preload+renderer), `npm run lint` clean,
`npm run build` green, `npm run smoke` PASS (real window, SMOKE_OK).
Windows click-through not executed here — marked pending, not passing.

## Required automated and integration scenarios

- Import/export round trip
- Duplicate game identifiers and metadata conflicts
- Unavailable artwork sources
- Missing-game labeling without deletion
- Path and image input validation

## Cross-cutting tests

- Validate malformed, missing, oversized and unauthorized inputs.
- Confirm persistence, restart behavior, schema versioning, and export/import consistency where relevant.
- Exercise cancellation, timeouts, incomplete operations and recovery behavior.
- Confirm tests use temporary fixtures and do not read owner's private or production data.
- Verify deterministic calculations and no accidental state changes in read-only actions.

## End-to-end MVP verification

Import a fixture library, edit artwork/title/tags, detect a missing path, and export a reversible metadata bundle.

Run this workflow against a real application build using disposable data; record actual commands, OS environment, relevant results and any platform-only gaps. If the workflow requires Windows or local AI services unavailable in the worker environment, mark it **implemented but unverified** rather than passing.

## Mandatory verification record

For each run, capture: commit SHA, command, execution environment, passed/failed/skipped counts, observed UI/CLI behavior, defect links, and next action. Keep logs free of credentials and personal data.

No release or owner-acceptance claim before end-to-end demonstration.
