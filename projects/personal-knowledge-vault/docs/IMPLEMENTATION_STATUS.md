# Implementation status — Personal Knowledge Vault

- **Overall status:** MVP FUNCTIONAL / REVIEW READY (2026-10-23)
- **Priority:** 11/17
- **Source/code implemented:** Full vertical slice. Backend (commit 3fef7ea):
  SQLite schema v1, FTS5 full-text index (sync triggers), review workflow
  (candidate/verified/rejected), immutable revision history (DB-level trigger
  rejects direct UPDATEs), versioned backup export/import (`formatVersion
  1.0.0`), typed `window.pkv` IPC contract with zod validation. Renderer
  (commit 6c85195): React 19 + TS strict + Vite UI — notes list with FTS
  search + status/tag filters, note detail (source citation block, linked
  records, revision history with line diffs, edit form requiring a change
  summary, approve + reject-requires-reason), new-note form (source fields +
  link picker), backup view (export/import + validation errors). Status badge
  + source label on every displayed record; accessible labels/keyboard; no
  network. Coordinator reconciliation: fixed 7 renderer type errors that had
  slipped past the unwired gate; wired renderer into `npm run typecheck`,
  `npm test` (all suites), and `npm run build`.
- **Build validated:** Yes — `npm run build` (main + preload + renderer) clean
  on Linux; `npm run smoke` PASS (backend checks against compiled dist).
- **Automated tests executed:** Yes — **69/69 green** (38 backend + 31 UI,
  hermetic `window.pkv` mock), 2026-10-23, Linux VM, Node 24. Re-run by the
  coordinator after reconciliation.
- **End-to-end MVP verified:** Backend workflow verified (create → approve →
  search → revise → export → import round-trip, byte-deterministic export);
  real-window UI flow on Windows 11 pending — labeled, never claimed.
- **Owner review:** Pending

## Sandboxed preload fix (2026-11-04)

The preload could never load in a real window: `electron/main.ts` runs it
with `sandbox: true`, and the plain-tsc `build:preload` preserved its value
import of the channel constants as `require("../shared/types")` — a
sandboxed preload may only require `electron`/builtins, so it threw before
`contextBridge.exposeInMainWorld` ran and `window.pkv` never existed (same
defect proven live on the Universal Game Launcher the same day; invisible
to the test suite, which mocks `window.pkv`, and to the boot smoke).
`build:preload` now bundles the preload with Vite
(`app/vite.preload.config.ts`, mirroring finance-simulator), electron
external, emitted at `dist/electron/preload.js` where main already loads
it; `shared/types.ts` is self-contained (only runtime export is the
`PkvChannels` const), so the bundle's only `require` is `electron` —
verified by grepping the emitted bundle. Re-verified on Linux VM:
`npm test` 69/69, `npm run build` clean, `npm run smoke` PASS. Real-window
UI flow on Windows 11 still pending — labeled, never claimed.

## First milestone

Create unverified notes with sources, approve individual records, search them, correct history, and export a safe backup.

## Next action

Package for Windows and run the end-to-end MVP workflow on real hardware.

## Contract reconciliation (Worker B, 2026-10-23)

`app/shared/types.ts` landed while the renderer was being built; `app/src/types.ts`
is now a thin re-export adapter over the canonical types (no mirror drift).
Renderer-visible contract deltas vs the original brief, all conformed to:
- `Note.links` is `LinkedNote[]` (id/title/status), not `string[]` — detail view
  renders linked records directly, no extra fetch; update sends link ids.
- `NoteUpdateInput` has no `source` — sources are write-once at creation; the
  edit form covers title/body/tags and notes this in the UI.
- `backup.export()` returns the JSON payload string (main shows the save
  dialog); the export summary counts notes from the payload.
- `backup.import()` returns `{ imported, skipped }`; validation problems
  surface as thrown errors, shown in the UI. The result panel also renders an
  `errors` array if a backend ever returns one (forward-compatible).

## Acceptance notes

Record actual commits, tests, blockers and PR links here when implementation begins. Do not infer success from the existence of this planning document.
