# Concrete Operations Manager

**Status:** MVP IMPLEMENTED — working local-first Windows desktop app; automated
tests, production build and headless window smoke test all pass on Linux.
Windows-only validation (installer, real hardware) is still pending.

**Priority:** 2 of 17 in the approved intake queue.
**Category:** Windows desktop / local business
**Repository workspace:** `projects/concrete-operations-manager/` (app code in `app/`)

## Purpose

Track concrete delivery customers, jobs, pours, pricing, inventory, quoting, and
invoicing in one auditable system.

## MVP (implemented)

- **Customers** — name, contact, address, tax-exempt flag, customer-specific
  pricing (concrete rate, small-load charge, flat/per-km delivery). Pricing
  changes are audit-trailed.
- **Jobs** — date, delivery location, PO number, one-way distance, status.
- **Pours** — mix design ID (**nominal design identifier only**, never a verified
  structural claim), quoted m³ (**estimate**) kept separate from delivered m³
  (**measured**, finalized after the pour).
- **Quotes** — itemized (concrete m³ × rate, small-load charge under a
  configurable threshold, flat or mileage delivery), each tax its own line
  (GST 5% default, configurable; exempt customers show $0 tax lines).
  States: `draft → issued → superseded`. Issued quotes are immutable —
  revisions create a new version; price overrides on drafts are audited.
- **Invoices** — generated from the issued quote using **finalized delivered**
  volumes only. States: `issued → paid / voided`. Issued invoices are immutable.
- **Inventory** — cement/aggregate receipts (supplier, date, qty, cost) and
  per-pour consumption; stock-on-hand query; consumption beyond stock is blocked.
- **Exports** — invoice PDF (pdfkit, pure JS) and CSV (customers, jobs,
  invoices, inventory); full-database backup/restore with file validation and
  rollback copy.
- **Audit trail** — every override, state transition, receipt and consumption
  writes who/what/when/before/after.
- **Calibration interop** — versioned JSON exchange format with the Volumetric
  Mix Calculator (Project 3): see `docs/CALIBRATION_EXCHANGE.md`. Import/export
  in Settings; payloads treated as opaque.

Money is integer cents everywhere; volumes are integer liters; taxes use
explicit half-up rounding; all calculations are deterministic.

## Running it

```bash
cd projects/concrete-operations-manager/app
npm install
npm run dev      # Vite renderer on :5175 + Electron (needs a display or xvfb on Linux)
npm test         # vitest: backend + UI suites
npm run build    # typecheck + production bundle
npm run smoke    # build, then open the real window headless (xvfb on Linux)
```

Windows install steps: `docs/WINDOWS_INSTALL.md` (pending verification).

## Verification (2026-10-23, Linux VM)

- `npm run typecheck` — clean (renderer, main, preload)
- `npm run lint` — clean
- `npx vitest run` — **57/57 pass** (11 files: pricing, schemas, migrations,
  workflow, inventory, backup/restore, calibration, CSV, PDF, 2 UI suites)
- `npm run build` — production bundle builds
- `npm run smoke` — real Electron window opened (SMOKE_OK)
- Acceptance walkthrough against the **compiled** `dist/` bundle — 17/17 checks
  pass (customer → job → pour → quote → issue → revise → finalize → invoice →
  PDF/CSV export → inventory → backup/restore → restart persistence)

Not verified: Windows installer/NSIS build, portable zip on Windows, real
Windows hardware behaviors (file dialogs exercised only via code paths).

## Full intended capabilities (beyond MVP)

- Customer records and purchase orders ✅ (MVP)
- Job scheduling, dates and delivery locations ✅ (MVP)
- Mix/strength and ordered versus delivered volume ✅ (MVP)
- Customer pricing, small-load and flat or mileage delivery fees ✅ (MVP)
- Canadian tax configuration and separate charge lines ✅ (MVP)
- Quote, invoice and payment states ✅ (MVP)
- Cement/aggregate deliveries and stock movements ✅ (MVP)
- Calibration-linked yield and reconciliation reports — format defined and
  import/export works; yield math lives in Project 3 (planned)

## Dependencies and boundaries

Can import/export versioned calibration data from the independent Volumetric
Concrete Mix Calculator (`docs/CALIBRATION_EXCHANGE.md`).

Never commit genuine customer data. Show each invoice charge separately; preserve
issued document history; allow overrides with audit trails.

## Muse start point

Read the repository-root `AGENTS.md`, then [this project's instructions](AGENTS.md)
and [development handoff](docs/MUSE_HANDOFF.md). See [specification](docs/PRODUCT_SPEC.md),
[test plan](docs/TEST_PLAN.md), and [status](docs/IMPLEMENTATION_STATUS.md).
