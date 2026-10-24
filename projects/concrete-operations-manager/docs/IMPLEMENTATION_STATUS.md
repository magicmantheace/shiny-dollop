# Implementation status — Concrete Operations Manager

- **Overall status:** MVP IMPLEMENTED (2026-10-23)
- **Priority:** 2/17
- **Branch:** `concrete-operations-manager/mvp`
  (commits `104c0bd` foundation, `9bbc6af` tests)
- **Build validated:** Yes — `npm run build` clean; `npm run smoke` opened a
  real Electron window under xvfb (SMOKE_OK)
- **Automated tests executed:** Yes — **57/57 pass** (`npx vitest run`, 11 files)
- **End-to-end MVP verified:** Yes — scripted walkthrough against the compiled
  `dist/` production bundle, 17/17 checks pass (see below)
- **Owner review:** Pending (PR to be opened by parent)

## First milestone — DONE

Create a customer and job, record one pour, calculate an itemized quote with
tax, finalize delivered volume, and export an invoice.

Acceptance walkthrough (2026-10-23, Linux VM, script `/tmp/com-accept-walkthrough.cjs`
run against compiled `app/dist/` with synthetic data) — all 17 checks passed:

- create customer / job / pour (quoted 2.500 m³ estimate, delivered unset)
- draft quote v1: concrete $450.00 + small-load $150.00 + flat delivery $75.00 =
  $675.00 subtotal, GST 5% $33.75, total **$708.75** — each charge its own line
- issue quote; revise → new draft v2 with rate override; issued v1 byte-identical
- finalize delivered 2.480 m³; invoice `INV-000001` from measured volumes:
  $446.40 + $150.00 + $75.00 = $671.40, GST $33.57, total **$704.97**
- mark paid; PDF exported (valid `%PDF-` magic); CSV exported
- inventory: receipt 2000 kg, consumption 800 kg → stock on hand 1200 kg
- backup validates; data survives close/reopen

Full unit/integration/UI suite: 57/57 (pricing incl. rounding & exemptions,
small-load threshold, alternate customer rates, quote-revision immutability,
inventory receipt/consumption consistency, export/import recovery, malformed &
oversized input rejection, persistence across restart, calibration envelope
validation, CSV/PDF rendering, UI charge-line and estimate/measured labeling).

## Implemented and verified

- Customer/job/pour CRUD with zod-validated IPC and actionable errors
- Itemized quotes (concrete/small-load/delivery), per-tax lines, GST 5% default,
  tax-exempt handling, draft → issued → superseded with audited overrides
- Invoices from finalized delivered volumes, issued → paid/voided, immutable
- Inventory receipts/consumption/stock with oversell protection
- Invoice PDF (pdfkit) and CSV exports; backup/restore with validation + rollback
- Audit trail UI with before → after detail
- Calibration exchange format v1.0.0 documented (`docs/CALIBRATION_EXCHANGE.md`)
  with working import/export and schema validation

## Implemented but NOT verified (Windows-only)

- NSIS installer build (`npm run package:win` configured, never run — needs Windows)
- Portable zip assembly and launch on Windows
- Real Windows hardware: file dialogs, install/uninstall, shortcuts
- See `docs/WINDOWS_INSTALL.md` — every Windows step labeled pending

## Unfinished features / known limitations

- No demo/seed data loader in the app (synthetic fixtures exist in tests only).
- No quote/invoice email sending, no payment processing — out of MVP scope.
- Delivery "mileage" mode needs the job distance entered manually; no mapping integration.
- Multi-user / network sync: none by design (local-first, single instance).
- Mix IDs are nominal labels only; yield/reconciliation math belongs to Project 3.
- Settings support one company profile; no multi-branch support.
- PDF is a single invoice layout; no batch printing or custom templates.
- Restore replaces the live DB file; the app must restart its DB connection
  (handled in-process; a failed restore reopens the original).

## Codex review fix cycle 2 (2026-10-24)

Two P1 findings from the re-review of `1a6086e`, both verified against the
code and fixed with regression tests:

- **Sandboxed preload could not load its IPC channel constants.** The
  preload is built with `sandbox: true`, and sandboxed preloads cannot
  `require()` local files — but `build:preload` was a plain `tsc` emit, so
  the compiled preload contained `require('../../shared/ipc-channels')` and
  threw before exposing `window.concreteOps`. `build:preload` now bundles
  the preload into a single self-contained script with Vite
  (`vite.config.preload.ts`); the built output's only `require` is
  `electron`, the channel constants are inlined, and the sandbox stays on.
  `scripts/dev.mjs` watches the same Vite bundle instead of a tsc preload
  emit. Regression tests: `tests/integration/preload-bundle.test.ts`
  (rebuilds the preload and asserts the require set; fails on the old tsc
  build).
- **Invoice PDF charges overlapped multi-line descriptions.** In
  `electron/main/export/pdf.ts` the amount was drawn back at the row top,
  resetting `doc.y` to the single-line amount's bottom, so the following
  `moveDown(0.35)` started the next charge inside a two-line description.
  The row advance now preserves the description bottom and moves below the
  taller of description/amount. Regression test in
  `tests/integration/pdf.test.ts` renders a three-line charge row and
  asserts the next charge's position in the PDF content stream is below
  the description's last line (fails on the old code).

Verification: **67/67 tests pass** (`npx vitest run`, 14 files; was 64),
`npm run typecheck` and `npm run lint` clean, `npm run build` clean, and
`npm run smoke` passed (production bundle opened a real Electron window
under xvfb, SMOKE_OK) — which also exercises the bundled sandboxed preload
end to end.

## Next action

Owner review of the PR; Windows-side validation (installer, portable zip,
real dialogs) on Adam's Windows box; then milestone 2 scoping.
