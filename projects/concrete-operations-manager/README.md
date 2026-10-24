# Concrete Operations Manager

**Status:** PLANNED — project definition only; no working application is implemented by this intake commit.

**Priority:** 2 of 17 in the approved intake queue.
**Category:** Windows desktop / local business
**Repository workspace:** `projects/concrete-operations-manager/`

## Purpose

Track concrete delivery customers, jobs, pours, pricing, inventory, quoting, and invoicing in one auditable system.

## First usable release (MVP)

Create a customer and job, record one pour, calculate an itemized quote with tax, finalize delivered volume, and export an invoice.

## Full intended capabilities

- Customer records and purchase orders
- Job scheduling, dates and delivery locations
- Mix/strength and ordered versus delivered volume
- Customer pricing, small-load and flat or mileage delivery fees
- Canadian tax configuration and separate charge lines
- Quote, invoice and payment states
- Cement/aggregate deliveries and stock movements
- Calibration-linked yield and reconciliation reports

## Proposed implementation direction

Local-first desktop app with SQLite and PDF/CSV exports; choose a scoped Windows-friendly UI stack. Muse must confirm feasibility before committing to framework choices.

## Dependencies and boundaries

Can import/export versioned calibration data from the independent Volumetric Concrete Mix Calculator.

Never commit genuine customer data. Show each invoice charge separately; preserve issued document history; allow overrides with audit trails.

## Muse start point

Read the repository-root `AGENTS.md`, then [this project's instructions](AGENTS.md) and [development handoff](docs/MUSE_HANDOFF.md). Implement the smallest working end-to-end milestone; document genuine test results. See [specification](docs/PRODUCT_SPEC.md), [test plan](docs/TEST_PLAN.md), and [status](docs/IMPLEMENTATION_STATUS.md).
