# Concrete Operations Manager — project agent instructions

**ACTIVE PROJECT FOLDER WHEN ASSIGNED:** `projects/concrete-operations-manager/`

Root `AGENTS.md` overrides these instructions on conflict.

1. Work only inside `projects/concrete-operations-manager/` for application code, manifests, scripts, tests, build artifacts, and project documentation. Other projects are off limits, even if an optional integration is mentioned.
2. Use a dedicated branch named `concrete-operations-manager/<milestone>`; never force-push or merge without owner approval.
3. Before writing code, read `docs/PRODUCT_SPEC.md`, `docs/TEST_PLAN.md`, and `docs/IMPLEMENTATION_STATUS.md`.
4. Build working executable functionality with realistic error handling, not mockup-only views. Keep deterministic logic and data handling separately testable.
5. Never commit genuine customer data. Show each invoice charge separately; preserve issued document history; allow overrides with audit trails.
6. Use synthetic or fixture data in tests. Never commit actual saved games, personal data, invoices, receipts, credentials, model files, runtime databases, or generated products.
7. Validate paths, untrusted inputs, and permissions. Make destructive or external actions opt-in; provide rollback when practical.
8. Record commands actually run, observed results and unresolved platform limitations; do not claim Windows/AI/provider tests passed without executing them.
9. Only update this project's status to MVP/verified after a genuine runnable demonstration. Maintain `docs/IMPLEMENTATION_STATUS.md` after substantive work.
10. Leave project-specific code on a reviewable, unmerged PR. Do not modify shared root workflows or utilities without separate permission.

## Implementation notes (MVP, 2026-10-23)

App code lives in `app/` (Electron + React + TypeScript strict + Vite +
electron-builder; SQLite via `node:sqlite`; PDF via pdfkit; zod on every IPC
channel). Layout mirrors the proven `game-save-manager` structure (read-only
reference — no shared code): `electron/main/`, `electron/preload/`,
`shared/` (types, ipc-channels, schemas, pricing, api-types), `src/`,
`tests/` (unit/integration/ui via vitest projects).

Domain conventions — keep these in any future work:
- Money is integer cents everywhere; volumes are integer liters (1 m³ = 1000 L);
  distances are integer tenths of km; tax rates are basis points.
- Rounding is explicit half-up to the cent (`divRoundHalfUp` in
  `shared/pricing.ts`); `computeTotals` is pure and deterministic.
- `quotedLiters` (estimate) and `deliveredLiters` (measured) are separate pour
  fields; invoices are computed from delivered volumes only.
- Mix design IDs are nominal design identifiers only — never present them as
  verified structural performance, in UI, PDFs or docs.
- Quote states: draft → issued → superseded. Invoice states: issued → paid/voided.
  Issued documents are never updated in place; revisions are new rows/versions.
- Every override, state transition, receipt and consumption writes an audit row
  (actor `local-user`, before/after JSON).
- Inventory consistency: consumption that would drive stock negative is rejected.
- Backup validates the candidate file before replacing the live DB and keeps a
  rollback copy. Restore requires the main process to close/reopen its connection.
- Calibration payloads (Project 3 interop) are opaque versioned JSON; the
  contract is `docs/CALIBRATION_EXCHANGE.md` — no shared dependencies.

Verification discipline: typecheck + lint + `vitest run` + `npm run build` +
`npm run smoke` before reporting; record commit SHA, counts and environment in
`docs/IMPLEMENTATION_STATUS.md`. Windows-only checks (installer, portable zip,
real hardware) are labeled pending, never claimed.
