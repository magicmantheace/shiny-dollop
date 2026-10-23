# Product specification — Personal Knowledge Vault

**Intake status:** Approved project concept; implementation not started.
**Priority:** 11/17
**Audience/target platform:** Local knowledge and memory

## Problem and outcome

Store searchable source-linked personal knowledge with review, provenance, and corrections.

## MVP user workflow and acceptance contract

Create unverified notes with sources, approve individual records, search them, correct history, and export a safe backup.

The MVP is accepted only when a tester can complete the workflow using an actual running build, inspect the resulting data/artifact, restart when relevant, and reproduce the result. Showing an interface or a unit test alone is not an MVP.

## Requirements — initial and subsequent milestones

1. **Notes and source citations** — implement with persisted, validated state and meaningful user feedback where relevant.
2. **Candidate/verified/rejected review statuses** — implement with persisted, validated state and meaningful user feedback where relevant.
3. **Revision and correction history** — implement with persisted, validated state and meaningful user feedback where relevant.
4. **Search, tagging and linked records** — implement with persisted, validated state and meaningful user feedback where relevant.
5. **Source-document pointers and access labels** — implement with persisted, validated state and meaningful user feedback where relevant.
6. **JSON export/import with provenance** — implement with persisted, validated state and meaningful user feedback where relevant.
7. **Local backups and optional encryption** — implement with persisted, validated state and meaningful user feedback where relevant.

## Data model and architecture considerations

Offline desktop app with SQLite and local full-text index; optional later embedding adapter.

Use a clearly versioned and documented local storage/export format. Define entities and transitions from the MVP workflow, not guessed integrations. Include migration and backup/restore behavior before treating persisted data as production-ready.

## Integration strategy

Future opt-in, versioned export interface for AthenZ and Local AI Command Center.

No other application's source or database may be modified as part of this project. Where useful, exchange versioned export/import contracts and independently owned fixtures.

## Nonfunctional and safety requirements

No ingestion of owner's private data without authorization; no automatic AthenZ sync or edits to AthenZ.

- Prefer offline operation and no paid API dependency.
- Optimize for a Windows 11 desktop (i5-10400F, RTX 3060 12 GB, 32 GB RAM), where relevant.
- Avoid destructive defaults, unapproved network calls, or hidden data collection.
- Make errors actionable; provide accessible keyboard navigation and recovery paths.
- Use original/licensed assets and scrub private example data.

## Completion criteria

1. Runnable build and reproducible install or launch instructions.
2. End-to-end MVP workflow exercised with recorded evidence.
3. Focused automated tests and relevant platform manual tests executed.
4. Clear distinction between implemented, verified, planned and blocked features.
5. Scoped pull request left unmerged for review.
