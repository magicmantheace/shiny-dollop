# Test plan — Concrete Operations Manager

**Current test status:** NOT RUN. This document defines future acceptance; no test results are implied.

## Required automated and integration scenarios

- Price and tax calculations including rounding and exemptions
- Small-load threshold and alternate customer rates
- Quote revisions do not rewrite issued invoices
- Inventory receipt and consumption consistency
- Export/import recovery with synthetic customers

## Cross-cutting tests

- Validate malformed, missing, oversized and unauthorized inputs.
- Confirm persistence, restart behavior, schema versioning, and export/import consistency where relevant.
- Exercise cancellation, timeouts, incomplete operations and recovery behavior.
- Confirm tests use temporary fixtures and do not read owner's private or production data.
- Verify deterministic calculations and no accidental state changes in read-only actions.

## End-to-end MVP verification

Create a customer and job, record one pour, calculate an itemized quote with tax, finalize delivered volume, and export an invoice.

Run this workflow against a real application build using disposable data; record actual commands, OS environment, relevant results and any platform-only gaps. If the workflow requires Windows or local AI services unavailable in the worker environment, mark it **implemented but unverified** rather than passing.

## Mandatory verification record

For each run, capture: commit SHA, command, execution environment, passed/failed/skipped counts, observed UI/CLI behavior, defect links, and next action. Keep logs free of credentials and personal data.

No release or owner-acceptance claim before end-to-end demonstration.
