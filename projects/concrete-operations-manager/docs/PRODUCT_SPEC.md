# Product specification — Concrete Operations Manager

**Intake status:** Approved project concept; implementation not started.
**Priority:** 2/17
**Audience/target platform:** Windows desktop / local business

## Problem and outcome

Track concrete delivery customers, jobs, pours, pricing, inventory, quoting, and invoicing in one auditable system.

## MVP user workflow and acceptance contract

Create a customer and job, record one pour, calculate an itemized quote with tax, finalize delivered volume, and export an invoice.

The MVP is accepted only when a tester can complete the workflow using an actual running build, inspect the resulting data/artifact, restart when relevant, and reproduce the result. Showing an interface or a unit test alone is not an MVP.

## Requirements — initial and subsequent milestones

1. **Customer records and purchase orders** — implement with persisted, validated state and meaningful user feedback where relevant.
2. **Job scheduling, dates and delivery locations** — implement with persisted, validated state and meaningful user feedback where relevant.
3. **Mix/strength and ordered versus delivered volume** — implement with persisted, validated state and meaningful user feedback where relevant.
4. **Customer pricing, small-load and flat or mileage delivery fees** — implement with persisted, validated state and meaningful user feedback where relevant.
5. **Canadian tax configuration and separate charge lines** — implement with persisted, validated state and meaningful user feedback where relevant.
6. **Quote, invoice and payment states** — implement with persisted, validated state and meaningful user feedback where relevant.
7. **Cement/aggregate deliveries and stock movements** — implement with persisted, validated state and meaningful user feedback where relevant.
8. **Calibration-linked yield and reconciliation reports** — implement with persisted, validated state and meaningful user feedback where relevant.

## Data model and architecture considerations

Local-first desktop app with SQLite and PDF/CSV exports; choose a scoped Windows-friendly UI stack.

Use a clearly versioned and documented local storage/export format. Define entities and transitions from the MVP workflow, not guessed integrations. Include migration and backup/restore behavior before treating persisted data as production-ready.

## Integration strategy

Can import/export versioned calibration data from the independent Volumetric Concrete Mix Calculator.

No other application's source or database may be modified as part of this project. Where useful, exchange versioned export/import contracts and independently owned fixtures.

## Nonfunctional and safety requirements

Never commit genuine customer data. Show each invoice charge separately; preserve issued document history; allow overrides with audit trails.

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
