# Test plan — Personal Knowledge Vault

**Current test status:** NOT RUN. This document defines future acceptance; no test results are implied.

## Required automated and integration scenarios

- Candidate data never silently becomes verified
- Revision history is immutable/auditable
- Search and source references survive restore
- Nonexistent source handling
- No private records sent to remote services

## Cross-cutting tests

- Validate malformed, missing, oversized and unauthorized inputs.
- Confirm persistence, restart behavior, schema versioning, and export/import consistency where relevant.
- Exercise cancellation, timeouts, incomplete operations and recovery behavior.
- Confirm tests use temporary fixtures and do not read owner's private or production data.
- Verify deterministic calculations and no accidental state changes in read-only actions.

## End-to-end MVP verification

Create unverified notes with sources, approve individual records, search them, correct history, and export a safe backup.

Run this workflow against a real application build using disposable data; record actual commands, OS environment, relevant results and any platform-only gaps. If the workflow requires Windows or local AI services unavailable in the worker environment, mark it **implemented but unverified** rather than passing.

## Mandatory verification record

For each run, capture: commit SHA, command, execution environment, passed/failed/skipped counts, observed UI/CLI behavior, defect links, and next action. Keep logs free of credentials and personal data.

No release or owner-acceptance claim before end-to-end demonstration.
