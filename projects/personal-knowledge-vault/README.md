# Personal Knowledge Vault

**Status:** PLANNED — project definition only; no working application is implemented by this intake commit.

**Priority:** 11 of 17 in the approved intake queue.
**Category:** Local knowledge and memory
**Repository workspace:** `projects/personal-knowledge-vault/`

## Purpose

Store searchable source-linked personal knowledge with review, provenance, and corrections.

## First usable release (MVP)

Create unverified notes with sources, approve individual records, search them, correct history, and export a safe backup.

## Full intended capabilities

- Notes and source citations
- Candidate/verified/rejected review statuses
- Revision and correction history
- Search, tagging and linked records
- Source-document pointers and access labels
- JSON export/import with provenance
- Local backups and optional encryption

## Proposed implementation direction

Offline desktop app with SQLite and local full-text index; optional later embedding adapter. Muse must confirm feasibility before committing to framework choices.

## Dependencies and boundaries

Future opt-in, versioned export interface for AthenZ and Local AI Command Center.

No ingestion of owner's private data without authorization; no automatic AthenZ sync or edits to AthenZ.

## Muse start point

Read the repository-root `AGENTS.md`, then [this project's instructions](AGENTS.md) and [development handoff](docs/MUSE_HANDOFF.md). Implement the smallest working end-to-end milestone; document genuine test results. See [specification](docs/PRODUCT_SPEC.md), [test plan](docs/TEST_PLAN.md), and [status](docs/IMPLEMENTATION_STATUS.md).
