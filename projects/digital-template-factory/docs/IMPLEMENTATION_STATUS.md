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
