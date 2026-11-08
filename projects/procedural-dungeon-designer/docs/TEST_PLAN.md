# Test plan — Procedural Dungeon Designer

**Current test status:** NOT RUN. This document defines future acceptance; no test results are implied.

## Required automated and integration scenarios

- Same seed/config yields identical map
- All mandatory rooms reachable
- No disconnected locked-start traps
- Budgets and bounds enforced
- Export/import preserves topology

## Cross-cutting tests

- Validate malformed, missing, oversized and unauthorized inputs.
- Confirm persistence, restart behavior, schema versioning, and export/import consistency where relevant.
- Exercise cancellation, timeouts, incomplete operations and recovery behavior.
- Confirm tests use temporary fixtures and do not read owner's private or production data.
- Verify deterministic calculations and no accidental state changes in read-only actions.

## End-to-end MVP verification

Generate a seeded connected dungeon, inspect rooms, edit encounter placements, and export the same map deterministically.

Run this workflow against a real application build using disposable data; record actual commands, OS environment, relevant results and any platform-only gaps. If the workflow requires Windows or local AI services unavailable in the worker environment, mark it **implemented but unverified** rather than passing.

## Mandatory verification record

For each run, capture: commit SHA, command, execution environment, passed/failed/skipped counts, observed UI/CLI behavior, defect links, and next action. Keep logs free of credentials and personal data.

No release or owner-acceptance claim before end-to-end demonstration.

## Verification record — MVP run (2026-10-23, coordinator)

- **Environment:** Linux VM, Node 24, Electron 45 under xvfb for smoke.
- **Branch/commits:** `procedural-dungeon-designer/mvp` — scaffold+shared
  core `e48cd2f`, backend `7671930`, renderer `468a9ef`, plus a coordinator
  integration fix to the renderer test fake (`setBudgetLimit` delegation).
- **`npm test`:** 7 files, **38/38 passed** (33 backend + 5 renderer).
  - Determinism: same seed+params -> deep-equal maps and byte-identical
    exports, including after a fresh DB reopen; different seeds differ.
  - Connectivity: validator passes 6+ generated seed/size/theme combos;
    correctly FAILS a hand-broken disconnected fixture, naming the room.
  - Budgets: generation never over budget across difficulties; the
    block-on-over-budget edit rule is enforced (map unchanged on failure);
    table costs/names cannot be forged; unknown keys rejected.
  - Persistence: save/get/list/delete round-trips; edits persist across a
    DB file reopen.
  - Export/import: round-trip reproduces the map exactly; corrupt JSON,
    wrong format, `formatVersion 2.0.0`, oversized input, and disconnected
    maps are each rejected with their named error.
  - Renderer: generate -> inspect -> save -> add/remove placement (budget
    text updates) -> BUDGET_EXCEEDED banner flow -> load/delete round trip,
    all against a fake API backed by the real generator/validators.
  - Preload hygiene: compiled preload loads only `electron`; source test
    asserts type-only shared imports and no `require(`.
- **`npm run typecheck`:** clean. **`npm run lint`:** clean.
- **`npm run build`:** renderer + main green.
- **`npm run smoke`:** SMOKE PASS — the packaged main executes the MVP
  acceptance sequence end-to-end: generate a seeded dungeon -> validator
  confirms connectivity -> save -> add an encounter placement -> export
  twice (byte-identical) -> import (map deep-equals the original) ->
  remove placement.
- **Platform gaps:** Windows 11 execution, real printing, and NSIS
  packaging are implemented per the sibling pattern but **not verified on
  target OS** (no Wine/hardware in this environment). No release or
  owner-acceptance claim is made for Windows yet.
