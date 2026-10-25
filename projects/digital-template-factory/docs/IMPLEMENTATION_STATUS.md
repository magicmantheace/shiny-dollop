# Implementation status — Digital Product Template Factory

- **Overall status:** IN PROGRESS — backend MVP implemented and unit-tested; renderer MVP implemented and unit-tested; end-to-end unverified
- **Priority:** 9/17
- **Source/code implemented:** backend + renderer on branch `digital-template-factory/mvp`
- **Build validated:** Partial — `tsc` clean for main/preload/renderer; `vite build` (renderer bundle) succeeds; full `electron-builder` Windows packaging not yet run
- **Automated tests executed:** Yes — backend 68/68, renderer 49/49 (see `docs/TEST_PLAN.md`)
- **End-to-end MVP verified:** No — needs a real Windows build on the owner's box
- **Owner review:** Pending

## First milestone

Select an original template, edit its data/theme, preview it, and export a functional HTML or printable package with checks.

## Backend section (Worker A — 2026-10-23)

Implemented in `projects/digital-template-factory/app/`, all original code, no copied designs:

- **IPC contract** (`dtf:` prefix, flat `window.dtf` preload API): all 10 channels implemented with zod-validated payloads — `dtf:templates:list|get|import`, `dtf:documents:create|get|update-field|update-tokens|delete`, `dtf:export:generate|save`. Preload exposes only the narrow typed API (context isolation, no raw ipcRenderer).
- **3 bundled templates** (frozen manifests in `electron/main/templates/`): `invoice-1.0.0` (business/client/invoice no/issue date/line items/tax 0–100/notes), `weekly-planner-1.0.0` (week title, 7 prefilled days, focus goal), `checklist-1.0.0` (title, items, footer note). One pure deterministic `render-*.ts` per template; `escapeHtml` applied to every user value.
- **Validators** (`electron/main/validators/`, pure): required-field walker (nested dotted paths), WCAG contrast (≥4.5:1 for text/accent on bg), structure check (required markers, tag balance, no `<script>`).
- **Export pipeline** (`electron/main/export.ts`): validators run in order; named errors `FIELD_REQUIRED:<key>`, `CONTRAST_FAIL:<tokenKey>`, `STRUCTURE_INVALID:<reason>`; success returns byte-deterministic HTML + `licenseRecord` (templateId, templateVersion, manifestVersion, format, sha256 contentHash, exportedAt kept out of the HTML/hash).
- **Persistence** (`node:sqlite` under userData, gitignored): `templates` (imported bundles only), `documents`, `schema_version` migration table; explicit transactions on every write. Imported templates resolve and survive restart (tested).
- **Template import**: `manifestVersion` must be `'1.0.0'` else `TEMPLATE_VERSION_UNSUPPORTED`; malformed bundles → `TEMPLATE_INVALID`; bundled-id collisions and duplicate imports rejected.
- **Tests:** 68/68 passing (`npx vitest run --project backend`); typecheck clean for main + preload.

Deferred / known gaps: imported templates have no renderer → export returns `TEMPLATE_RENDER_UNSUPPORTED` (by design for MVP); `dtf:export:save` dialog path untested headless; full `electron-builder` Windows packaging untested here (no Wine/Windows).

## Renderer UI section (Worker B — 2026-10-23)

Implemented in `projects/digital-template-factory/app/src/`, all original
code and styling, no copied designs. Consumes the `window.dtf` bridge
exactly as defined in `app/shared/types.ts` (namespaced `templates.*`,
`documents.*`, `export.*` with object inputs) via a thin typed wrapper
(`src/api.ts`); `src/dtf-api.d.ts` declares `window.dtf: DtfApi` from the
shared types so there is a single source of truth.

- **Gallery** (`Gallery.tsx`): cards for the bundled templates with name,
  description, version, field count (from `templates.list`, no per-template
  fetch needed) and bundled/imported badge; "New document" per card;
  "Import template" dialog (`ImportDialog.tsx`) for pasted bundle JSON
  showing backend errors verbatim (e.g. `TEMPLATE_INVALID: …`).
- **Editor** (`Editor.tsx`): loads document + manifest; left panel =
  schema-generated field editor (`FieldEditor.tsx`: text, number with
  min/max, date, list rows via `ListEditor.tsx` with add/remove honoring
  `minItems` and per-`itemSchema` sub-forms) + design-token editor
  (`TokenEditor.tsx`: colour pickers + hex inputs, system-font-stack
  selects, spacing number; invalid values show inline errors and are never
  sent to the backend). Right panel = live preview: sandboxed
  `<iframe srcDoc>` fed by the pure local renderer `src/preview.ts`,
  clearly labelled "Approximate preview — the exported file is
  authoritative".
- **Export** (`ExportPanel.tsx`): HTML/Print format select → generate →
  license record display (template, manifest version, format, exported-at,
  sha256 content hash from the backend) → "Save file" via native dialog.
  Validation failures list named errors (`FIELD_REQUIRED:clientName`) as
  buttons that scroll-focus the offending field.
- **My documents** (`DocumentsList.tsx`): renderer-local recent-documents
  index in `localStorage` (no backend list endpoint) with template name,
  last-updated date, open, and delete with inline confirmation.
- **Accessibility**: native controls throughout, labelled inputs, visible
  focus, skip link, `role="alert"`/`role="status"` live regions, Escape
  closes the import dialog.
- **Tests:** 49/49 passing (`npx vitest run --project renderer`): gallery
  renders 3 templates from mock; field editor input types; invalid token
  blocks the API call; export failure named errors; list add/remove;
  import verbatim errors; editor integration; preview pure-function tests
  (escaping, token sanitization). All hermetic — `window.dtf` fully
  mocked, never the real backend. `vitest.config.ts` now runs two
  projects (`backend` node + `renderer` jsdom); backend config preserved.

Deferred / known gaps: no real Electron runtime check here (preload/main
owned by Worker A — renderer only tested against mocks); end-to-end MVP
still needs a Windows build on the owner's box.

## First milestone

Select an original template, edit its data/theme, preview it, and export a functional HTML or printable package with checks.

## Next action

Have Muse read `AGENTS.md`, `docs/PRODUCT_SPEC.md` and `docs/MUSE_HANDOFF.md`, implement and validate the first vertical slice on a project-scoped branch.

## Acceptance notes

Record actual commits, tests, blockers and PR links here when implementation begins. Do not infer success from the existence of this planning document.

## Coordinator reconciliation (2026-10-23, Linux VM, Node 24)

**Contract alignment:** both workers converged on `app/shared/types.ts` as the single source of truth. The preload (`electron/preload/index.ts`) exposes exactly the namespaced `DtfApi` shape (`templates.list/get/import`, `documents.*`, `export.*` with object inputs); the renderer's `window.dtf` declaration imports that same interface. No runtime shape mismatch.

**Acceptance test added** (`app/tests/acceptance.test.ts`, coordinator-authored, real engine, no mocks): invoice walkthrough — select `invoice-1.0.0` from catalog → create document → fill fields incl. an `<img onerror>` injection attempt → change accent token → export. Verifies: all validators pass, injection rendered inert (`&lt;img`), `<main>` present, no `<script>`, totals present, license record carries matching sha256 content hash, second export byte-identical. Plus: empty checklist export blocked with `FIELD_REQUIRED:*`; low-contrast theme blocked with `CONTRAST_FAIL:*`.

**Final verification (coordinator, independent):** `npm test` **120/120 pass** (117 workers + 3 acceptance), `npm run typecheck` clean (renderer + main + preload), `npm run lint` clean, `npm run build` green, `npm run smoke` PASS (real window under xvfb, `smoke: OK`).

**Status:** MVP functional. Unverified on real hardware: Windows 11 click-through, native save-dialog flow, portable-zip/NSIS assembly (no Wine here). No code signing. Imported (external) templates list and persist but have no renderer — `export:generate` returns `TEMPLATE_RENDER_UNSUPPORTED` for them by design.

## Codex review fix cycle 1 (2026-10-24, PR #13)

- Import validation (`electron/main/template-import.ts`): nested `itemSchema` entries are now fully validated (object shape, non-empty unique key, non-empty label, supported item type, boolean `required`, finite `min`/`max` with min <= max) and `prefill` rows are checked against the schema (declared keys only, required nested fields present, values satisfy type/bounds). Malformed bundles such as `itemSchema: [null]` with `prefill: [{}]` now return `TEMPLATE_INVALID` instead of persisting a template whose documents crash `ListEditor`/`renderPreviewHtml`.
- `ListEditor` new-row defaults: numeric cells initialize to a bounds-aware default (`min` when declared, else 0, clamped to `max`) instead of `''`, which `coerceFieldValue` rejects — previously a later successful save silently dropped the optimistic row.
- Reverted the unrelated `projects/game-save-manager/docs/MUSE_HANDOFF.md` edit on this branch back to main's version (project isolation).
- Tests: 15 regression tests added (12 import validation, 3 ListEditor), each verified failing pre-fix. Full suite 135/135 pass; `npm run typecheck` clean. `npm run lint` cannot run on this branch: no `eslint.config.*` exists in the tree (fails identically on the pre-fix head) — pre-existing gap, not introduced here.

## Codex review fix cycle 2 (2026-10-24, PR #13)

- Documents beyond the recent-entry limit stay reachable: added a backend `documents:list` endpoint (`store.listDocuments`, `dtf:documents:list` IPC channel, preload + `DtfApi.documents.list`, `DocumentSummary` type) returning every persisted document from SQLite; `DocumentsList` now merges that authoritative list with the renderer-local index. The local index (`src/recentDocs.ts`) is also no longer truncated at 50 entries, so it remains a complete index even if the backend is unavailable.
- Schema-less list fields accept string rows on save (`electron/main/validation.ts`): a `list` field with no `itemSchema` (or an empty one) is validated as an array of strings in `coerceFieldValue` before the object-row check — matching import validation (string `prefill` accepted) and `ListEditor` (text inputs). Non-string rows are still rejected with `FIELD_INVALID`. Previously an imported template with `prefill: ['First']` could be created but updating it to `['First', 'Second']` always failed.
- Tests: 4 regression tests added (backend `listDocuments`, schema-less string-list save via an imported template incl. rejection of non-string rows, 51-entry recent index, backend-only document shown in `DocumentsList`), each verified failing pre-fix. Full suite 139/139 pass (20 files; baseline 135); `npm run typecheck` clean. `npm run lint` still cannot run: no `eslint.config.*` exists in the tree (verified failing identically on the pristine pre-fix head) — pre-existing gap, not introduced here.

## Codex review fix cycle 3 (2026-10-24, PR #13)

- Save responses can no longer overwrite newer local edits (`src/components/Editor.tsx`): previously `applyRecord` replaced the whole optimistic document with whatever snapshot an in-flight save returned, so typing `a` then `ab` snapped back to `a` when the first response landed (and the next keystroke then submitted text missing the `b`); token-save responses could likewise revert pending field edits. The editor now tracks the newest local edit per field/token key (with a monotonic sequence and a ref-mirrored document, so rapid edits never close over stale state), applies optimistic updates for token saves too, and merges each response slice-wise: a response is authoritative only for the key(s) its own mutation changed — and only when no newer local edit for that key exists — while every other field/token keeps its local value. `updatedAt`/`version` never regress, responses for a no-longer-open document are ignored, and the Saving indicator now counts in-flight saves instead of clearing when the first of several finishes.
- Tests: 2 regression tests added (earlier field-save response arriving after a newer edit; token-save response carrying a pre-edit data snapshot while field saves are in flight), each verified failing pre-fix (2 failed / 5 passed on the pre-fix Editor) and passing post-fix. Full suite 141/141 pass (20 files; baseline 139); `npm run typecheck` clean. `npm run lint` still cannot run: no `eslint.config.*` exists in the tree — pre-existing gap, not introduced here.
