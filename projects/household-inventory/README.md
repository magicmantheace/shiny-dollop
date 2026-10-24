# Household Inventory and Warranty Tracker

**Status:** PLANNED — project definition only; no working application is implemented by this intake commit.

**Priority:** 6 of 17 in the approved intake queue.
**Category:** Offline household utility
**Repository workspace:** `projects/household-inventory/`

## Purpose

Maintain a private catalogue of household assets, receipts, warranties, and maintenance history.

## First usable release (MVP)

Add an item and receipt, record purchase and warranty dates, find expiring warranties, and export a backup.

## Full intended capabilities

- Product and location records
- Purchase price, date, serial number and notes
- Warranty dates and reminders
- Receipt/photo attachments
- Maintenance events
- Search, category filters and replacement estimates
- Portable encrypted-export option later

## Proposed implementation direction

Local-first desktop application and SQLite plus app-owned attachment store. Muse must confirm feasibility before committing to framework choices.

## Dependencies and boundaries

Standalone.

Keep real receipts and serial numbers local; no mandatory online accounts.

## Muse start point

Read the repository-root `AGENTS.md`, then [this project's instructions](AGENTS.md) and [development handoff](docs/MUSE_HANDOFF.md). Implement the smallest working end-to-end milestone; document genuine test results. See [specification](docs/PRODUCT_SPEC.md), [test plan](docs/TEST_PLAN.md), and [status](docs/IMPLEMENTATION_STATUS.md).
