# Test plan — Universal Game Save Manager

**Current test status:** NOT RUN. This document defines future acceptance; no test results are implied.

## Required automated and integration scenarios

- Create and verify a snapshot of a fixture save folder
- Alter fixture files and restore byte-for-byte
- Deny restoration without explicit confirmation
- Handle missing locations, locked files, and interrupted writes
- Never modify a save during discovery or backup

## Cross-cutting tests

- Validate malformed, missing, oversized and unauthorized inputs.
- Confirm persistence, restart behavior, schema versioning, and export/import consistency where relevant.
- Exercise cancellation, timeouts, incomplete operations and recovery behavior.
- Confirm tests use temporary fixtures and do not read owner's private or production data.
- Verify deterministic calculations and no accidental state changes in read-only actions.

## End-to-end MVP verification

Register a manual save folder, produce a dated, checksum-verified snapshot, list backups, and restore one with a safety copy and explicit confirmation.

Run this workflow against a real application build using disposable data; record actual commands, OS environment, relevant results and any platform-only gaps. If the workflow requires Windows or local AI services unavailable in the worker environment, mark it **implemented but unverified** rather than passing.

## Mandatory verification record

For each run, capture: commit SHA, command, execution environment, passed/failed/skipped counts, observed UI/CLI behavior, defect links, and next action. Keep logs free of credentials and personal data.

No release or owner-acceptance claim before end-to-end demonstration.
