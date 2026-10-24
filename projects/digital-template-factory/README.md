# Digital Product Template Factory

**Status:** PLANNED — project definition only; no working application is implemented by this intake commit.

**Priority:** 9 of 17 in the approved intake queue.
**Category:** Digital publishing tool
**Repository workspace:** `projects/digital-template-factory/`

## Purpose

Generate editable, quality-checked downloadable templates from original reusable designs.

## First usable release (MVP)

Select an original template, edit its data/theme, preview it, and export a functional HTML or printable package with checks.

## Full intended capabilities

- Template catalog and metadata
- Editable design tokens and content fields
- Batch generation
- Preview and output validation
- Accessible HTML export
- Document/spreadsheet/planner package types in later milestones
- Versioned templates and license records

## Proposed implementation direction

Local application with deterministic template manifests, validators, preview and exporters. Muse must confirm feasibility before committing to framework choices.

## Dependencies and boundaries

Provide documented export manifest for Business Website Generator.

Use original assets, legal licenses, and one-time purchase compatible outputs; avoid paid-service requirements.

## Muse start point

Read the repository-root `AGENTS.md`, then [this project's instructions](AGENTS.md) and [development handoff](docs/MUSE_HANDOFF.md). Implement the smallest working end-to-end milestone; document genuine test results. See [specification](docs/PRODUCT_SPEC.md), [test plan](docs/TEST_PLAN.md), and [status](docs/IMPLEMENTATION_STATUS.md).

## Renderer UI (Worker B scope)

The Electron renderer lives in `app/src/` and talks to the backend only
through the `window.dtf` bridge declared in `app/src/dtf-api.d.ts` (shape
defined once in `app/shared/types.ts`; a thin wrapper in `app/src/api.ts`).

- **Templates view** — gallery cards (name, description, version, field
  count, bundled/imported badge) with "New document" per card, plus an
  "Import template" dialog that accepts pasted bundle JSON and shows
  backend error codes verbatim (e.g. `TEMPLATE_INVALID: …`).
- **Editor view** — left panel: schema-generated field editor (text,
  number with min/max, date, list row editor with add/remove honoring
  `minItems`) and a design-token editor (colour pickers + hex inputs,
  system-font-stack selects, spacing number). Invalid token values show
  inline errors and are never sent to the backend. Right panel: live
  preview in a sandboxed `<iframe>`, rendered by the pure local function
  `src/preview.ts` — **the preview is approximate; the exported file is
  authoritative**.
- **Export panel** — pick HTML or Print, generate, inspect the backend's
  license record (template, manifest version, format, exported-at, sha256
  content hash), then save via the native dialog. Validation failures
  list named errors (`FIELD_REQUIRED:clientName`) as buttons that focus
  the offending field.
- **My documents** — renderer-local recent-documents index
  (`localStorage`, since the backend exposes no list endpoint) with
  template name, last-updated date, open, and delete with inline
  confirmation.

Run UI checks: `npm run typecheck` and `npm test` (vitest `renderer`
project: jsdom + fully mocked `window.dtf`; hermetic, no backend).
`npm run build:renderer` produces `dist/renderer/`.
