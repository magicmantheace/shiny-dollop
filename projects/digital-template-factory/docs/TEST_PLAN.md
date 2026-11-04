# Test plan — Digital Product Template Factory

**Current test status:** BACKEND UNIT TESTS PASSING (68/68, 2026-10-23). Renderer UI tests and end-to-end MVP verification are Worker B / coordinator scope — see run records below.

## Required automated and integration scenarios

- Generated HTML opens and links resolve
- Escaped input prevents injection
- Missing fields show actionable validation
- Repeatable build hashes for same input
- Exports contain no hidden customer data

## Cross-cutting tests

- Validate malformed, missing, oversized and unauthorized inputs.
- Confirm persistence, restart behavior, schema versioning, and export/import consistency where relevant.
- Exercise cancellation, timeouts, incomplete operations and recovery behavior.
- Confirm tests use temporary fixtures and do not read owner's private or production data.
- Verify deterministic calculations and no accidental state changes in read-only actions.

## End-to-end MVP verification

Select an original template, edit its data/theme, preview it, and export a functional HTML or printable package with checks.

Run this workflow against a real application build using disposable data; record actual commands, OS environment, relevant results and any platform-only gaps. If the workflow requires Windows or local AI services unavailable in the worker environment, mark it **implemented but unverified** rather than passing.

## Mandatory verification record

For each run, capture: commit SHA, command, execution environment, passed/failed/skipped counts, observed UI/CLI behavior, defect links, and next action. Keep logs free of credentials and personal data.

No release or owner-acceptance claim before end-to-end demonstration.

## Run records

### 2026-10-23 — backend unit tests (Worker A)

- **Commit:** `9733ada` (branch `digital-template-factory/mvp`)
- **Command:** `npx vitest run --project backend` in `projects/digital-template-factory/app`
- **Environment:** Linux VM, Node v24.22.1, vitest 5.0.5
- **Result:** 8 files, **68/68 tests passed**, 0 failed
- **Coverage:**
  - `tests/manifests.test.ts` (5) — shape/frozen manifests for all 3 bundled templates
  - `tests/required.test.ts` (6) — required-field validation incl. nested list dotted paths
  - `tests/contrast.test.ts` (9) — WCAG contrast; asserts #000 on #fff = 21:1
  - `tests/structure.test.ts` (8) — balanced/unbalanced/missing-marker/script-tag cases
  - `tests/escape.test.ts` (6) — escapeHtml + `<img onerror>` injection rendered inert in invoice/checklist output
  - `tests/template-import.test.ts` (10) — version mismatch → `TEMPLATE_VERSION_UNSUPPORTED`; malformed bundles → `TEMPLATE_INVALID`
  - `tests/export.test.ts` (6) — byte-identical HTML + identical contentHash across two runs; missing fields blocked with `FIELD_REQUIRED:*`; low contrast blocked with `CONTRAST_FAIL:*`
  - `tests/store.test.ts` (18) — SQLite CRUD round-trip on `:memory:`; field coercion/validation; token validation; import persistence **survives database close/reopen** (temp-file DB)
- **Typecheck:** `tsc --noEmit` clean for `tsconfig.main.json` and `tsconfig.preload.json`
- **Not covered here:** renderer UI tests (Worker B, `src/**/*.test.tsx` — 24 failures observed 2026-10-23, Worker B scope), end-to-end MVP on a real Windows build (unverified — needs owner's Windows box; Electron cannot launch headless in this VM)

### 2026-10-23 — renderer UI tests (Worker B)

- **Commit:** branch `digital-template-factory/mvp` (renderer commit to be recorded on push)
- **Commands:** `npx tsc --noEmit -p tsconfig.renderer.json` (clean), `npm test` → `npx vitest run` (both projects) in `projects/digital-template-factory/app`
- **Environment:** Linux VM, Node v24.22.1, vitest 5.0.5, jsdom
- **Result:** renderer project — 10 files, **49/49 tests passed**, 0 failed; full suite (backend + renderer) **117/117 passed** across 18 files
- **Coverage:**
  - `src/preview.test.ts` (10) — `escapeHtml` neutralises `<script>`/`<img onerror>`; token sanitizer falls back on bad colours/fonts and clamps spacing 0–64; preview HTML is labelled approximate
  - `src/components/Gallery.test.tsx` (4) — 3 template cards from mock (name/description/version/field count); "New document" calls `documents.create` and opens the doc; load error + retry; import dialog opens
  - `src/components/ImportDialog.test.tsx` (3) — backend error shown verbatim (`TEMPLATE_INVALID: …`); success notifies parent; Import disabled on empty input
  - `src/components/FieldEditor.test.tsx` (4) — correct input types per schema (text/number/date/list), number min/max attributes, required markers, text/number changes forwarded with field key
  - `src/components/ListEditor.test.tsx` (5) — add row with empty sub-fields; remove by index; removal disabled at `minItems`; sub-field edits; plain-text rows without `itemSchema`
  - `src/components/TokenEditor.test.tsx` (6) — invalid hex shows inline error and blocks `documents.updateTokens`; valid hex/colour-picker/spacing forwarded; font selects are system stacks only
  - `src/components/ExportPanel.test.tsx` (5) — named validation errors (`FIELD_REQUIRED:clientName`) each link to the field; format forwarded; license record + sha256 content hash shown verbatim; save flow; cancelled save reported; transport failure verbatim
  - `src/components/DocumentsList.test.tsx` (5) — recent docs with template name + updated date; open; delete with inline confirmation calls backend; delete failure keeps the entry; empty state
  - `src/components/Editor.test.tsx` (5) — loads doc + manifest, fields + preview iframe; field edits call `updateField`; export panel toggle; load error; back navigation
  - `src/App.test.tsx` (2) — gallery/documents nav; new-document flow opens the editor
- **Build:** `npm run build:renderer` (vite) succeeds → `dist/renderer/` (gitignored)
- **Test doubles:** `window.dtf` fully mocked per test (`src/test-utils.tsx`); no test touches the real backend. Explicit `cleanup()` in `src/test-setup.ts` (vitest runs without globals, so RTL auto-cleanup does not register).
- **Not covered here:** real Electron runtime (preload/main owned by Worker A); end-to-end MVP on a real Windows build (unverified — needs owner's Windows box)

## RUN 2026-10-23 (coordinator, Linux VM, Node 24) — 120/120 pass
- `npm test`: **120/120** across 19 files (71 backend incl. 3 new acceptance + 49 renderer).
- New: `tests/acceptance.test.ts` (3) — full MVP walkthrough against the real engine (no mocks): invoice select → fill fields (incl. injection) → theme edit → export; injection inert; byte-identical determinism + matching content hash; missing-field and contrast-failure blocking with named errors.
- `npm run typecheck` clean (renderer + main + preload), `npm run lint` clean, `npm run build` green, `npm run smoke` PASS (real window, `smoke: OK`).
- Unverified: Windows 11 click-through, native save-dialog flow, packaging (no Windows/Wine here).
