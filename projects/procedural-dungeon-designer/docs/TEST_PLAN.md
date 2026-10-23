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
