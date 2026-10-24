# Implementation status — Household Inventory and Warranty Tracker

- **Overall status:** MVP FUNCTIONAL — implemented and verified on Linux; Windows click-through pending owner hardware
- **Priority:** 6/17
- **Branch:** `household-inventory/mvp`
- **Source/code implemented:** `projects/household-inventory/app/` — Electron 45 + React 19 + TypeScript strict + Vite, `node:sqlite`, zod-validated IPC, `fflate` (pure-JS zip) for backups
- **Build validated:** Yes — `npm run build` green (main + preload + renderer), `npm run smoke` PASS (real window under xvfb, SMOKE_OK), portable Windows zip built (`Household Inventory-0.1.0-win-x64.zip`, ~154 MB, 74 entries, exe + app.asar verified; gitignored)
- **Automated tests executed:** Yes — **59/59 pass** (47 backend: engine/db/backup incl. tamper-rejection cases; 11 UI: hermetic `window.inv` mocks; 1 integration: full MVP walkthrough)
- **End-to-end MVP verified:** Yes, scripted against the real backend — add item + receipt attachment (sha256-verified), warranty dates, expiring-warranty finder (expiring + expired, sorted), maintenance log, backup export → import into a fresh directory with byte-identical attachments and identical rows
- **Owner review:** Pending (PR to be opened by coordinator)

## What the MVP does

- **Items:** CRUD with name, category, location, purchase price (integer cents), purchase date, serial number, notes, warranty start/end (end ≥ start enforced both sides)
- **Attachments:** receipt/photo/manual images + PDFs, 20 MiB cap, mime allowlist, filename sanitization, sha256 write-verified, app-owned store under `<userData>/attachments/`; missing files tolerated on read/delete; files cleaned up on item delete
- **Maintenance log:** per-item events (date, description, optional cost), newest-first
- **Warranty finder:** configurable window (30/60/90/365 days, default 90); expired + expiring sections sorted by days left; pure UTC date math (leap-day correct)
- **Backup:** portable zip — `manifest.json` (format `household-inventory-backup` v1, per-file sha256/size) + `inventory.db` snapshot via `VACUUM INTO` (consistent under WAL) + `attachments/`; import validates format/version, verifies every checksum, rejects tampered/missing/zip-slip payloads, keeps a `rollback-<timestamp>` copy of the previous data
- **Search & filters:** free-text search (name/category/location/serial/notes) + category dropdown + location filter

## Verification record (2026-10-23, Linux VM, Node 24)

| Command | Result |
|---|---|
| `npx vitest run` | **59/59 pass** (10 files: engine, db, ui, integration) |
| `npm run typecheck` | clean (main + preload + renderer) |
| `npm run lint` | clean |
| `npm run build` | green |
| `npm run smoke` | PASS — real Electron window opened (SMOKE_OK) |
| `npm run package:win` | portable zip built; contents verified |
| MVP walkthrough (`tests/integration/acceptance.test.ts`) | pass — 2 items, 1 attachment, 1 maintenance event, warranty finder correct, backup round-trip byte-identical |

## Known limitations (all labeled, never claimed)

- Windows 11 click-through of the built app not executed here — pending owner's hardware
- NSIS installer not attempted (no Wine here); portable zip is the Windows deliverable
- No code signing (SmartScreen will warn)
- `node:sqlite` has no `backup()` API on Node 24 — snapshots use `VACUUM INTO` (same point-in-time guarantee, verified)
- UI tests are hermetic mocks; UI verified against the live backend only via the scripted walkthrough, not a human click-through
- Out of scope for MVP: encrypted export, replacement-cost estimates, reminders/notifications, scheduled scans, cloud sync

## Next action

Owner reviews the PR on his Windows 11 PC: install from the portable zip, run the MVP workflow (add item + receipt, set warranty dates, check the warranty tab, export/import a backup), and report back.
