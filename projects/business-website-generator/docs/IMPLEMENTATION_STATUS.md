# Implementation status — Small Business Website Generator

- **Overall status:** MVP FUNCTIONAL — implemented and verified on Linux; Windows click-through pending
- **Priority:** 10/17
- **Branch:** `business-website-generator/mvp` (isolated to `projects/business-website-generator/` + root index row)
- **Source/code implemented:** Electron 45 + React 19 + TypeScript strict + Vite, `node:sqlite`, zod-validated IPC

## What was built (2026-10-23)

- **4 original responsive themes** (pure deterministic renderers, mobile-first, semantic HTML — skip link, landmarks, aria labels; zero external assets/scripts): `trades` "Ironline" (services grid, service areas, quote CTA), `author` "Folio" (bookshelf from services, newsletter form that posts nowhere and says so), `restaurant` "Hearth" (menu sections with prices, hours table, location), `localbiz` "Mainstreet" (hero, services, hours, contact). Each emits `index.html`, detail page (`services`/`menu`/`books`), `contact.html`, `style.css`, `sitemap.xml` (no lastmod → byte-deterministic), `robots.txt`; SEO title/meta/OG on every page.
- **Validators** (named codes): `FIELD_REQUIRED:*`, `LINK_BROKEN:*`, `ASSET_MISSING:*`, `CONTRAST_FAIL:*`, `HTML_INVALID:*`; export blocked on any error. All shipped color tokens pass WCAG AA at 6.3:1+.
- **Export pipeline:** render → validate → write; refuses non-empty destinations (`EXPORT_DEST_NOT_EMPTY`); nothing written when blocked.
- **Store:** `node:sqlite`, schema v1, explicit transactions, DB under userData.
- **UI:** dashboard + new-site wizard (type → theme), debounced-autosave profile editor with inline validation (email/URL/phone), dynamic lists, restaurant-only menu sections, SEO counters, theme picker, sandboxed iframe preview with Mobile (375px)/Desktop toggle labeled "approximate — export is authoritative", validate-then-export flow (export disabled until validation clean), keyboard-accessible modals with focus trap.
- **IPC contract** (`shared/types.ts`, canonical): flat `window.bwg` — `sites.list/create/get/updateProfile/delete/setTheme`, `themes.list`, `preview.render`, `export.validate → {ok, issues}`, `export.run → ExportResult`, `dialog.pickDirectory`. Failures arrive as `Error("CODE: message")`.
- **Injection safety:** every theme escapes all user content (`escapeHtml`); `<img onerror>` payloads render inert (tested).

## Verification (all actually run, Linux VM, Node 24, 2026-10-23)

- `npx vitest run`: **132/132 pass** (99 backend + 32 renderer + 1 acceptance), incl. MVP acceptance walkthrough (`tests/backend/acceptance.test.ts`): restaurant site → fill profile → validate clean → export 6 files → all internal links resolve → no third-party assets → byte-identical second export → missing name blocks export with `FIELD_REQUIRED` and writes nothing.
- `npm run typecheck` clean (main + renderer), `npm run lint` clean, `npm run build` green, `npm run smoke` PASS (real window under xvfb, export ok).

## Implemented but unverified

- Windows 11 click-through of the built app, native directory picker, portable-zip/NSIS assembly (no Wine here) — pending owner's hardware. See `docs/WINDOWS_INSTALL.md`.

## Planned (not in MVP)

- Import of versioned templates from Digital Product Template Factory (optional integration)
- Image/media asset management UI, multi-page custom layouts, FTP/publish flow

## Acceptance notes

Do not claim Windows validation. No merges; PR left unmerged for owner review.
