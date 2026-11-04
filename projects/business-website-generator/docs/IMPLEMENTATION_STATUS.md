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

## Verification (all actually run, Linux VM, Node 24; suite re-run 2026-11-04)

- `npx vitest run`: **142/142 pass** (107 backend + 35 renderer, across 16 files), incl. MVP acceptance walkthrough (`tests/backend/acceptance.test.ts`): restaurant site → fill profile → validate clean → export 6 files → all internal links resolve → no third-party assets → byte-identical second export → missing name blocks export with `FIELD_REQUIRED` and writes nothing.
- `npm run typecheck` clean (main + renderer), `npm run lint` clean, `npm run build` green, `npm run smoke` PASS — **backend pipeline only** (open DB → create site → validate → export in a temp dir). The smoke script does not launch Electron; an earlier version of this document incorrectly described it as a real-window check, corrected in the PR #14 fix pass below.
- Manual window-launch check (2026-11-04, one-off, not part of `npm run smoke`): `electron .` under xvfb against the built output — the app booted via the manifest entry point, created its window, loaded the built renderer from `dist/renderer`, and stayed up with the sandboxed preload active (no load errors logged). No visual or click-through inspection was performed.

## PR #14 fix pass (2026-11-04) — Codex round-1 findings

The round-1 Codex review (on the pre-cleanup commit `d60420c9d`) was never answered by the cycle commits, which addressed round 2 only; its six findings were still live and are fixed now:

- `app/package.json` declares `"main": "dist/electron/main/main.js"` (directory/portable launches previously fell back to a nonexistent `index.js`).
- `main.ts` resolves the renderer two levels up (`dist/renderer`, where Vite writes it), not `dist/electron/renderer`.
- The preload no longer imports the main-process IPC module: channel names are inlined in `electron/preload.ts` (a sandboxed preload cannot require local modules; the built `dist/electron/preload.js` now requires only `electron`). A test pins the inlined literals to the canonical `CHANNELS` map.
- `ProfileEditor` flushes pending valid edits on unmount, so switching tabs inside the 800 ms debounce window no longer discards them (invalid drafts are still never persisted).
- Preview pages inline the theme stylesheet in place of the relative `style.css` link, which cannot resolve inside the `srcDoc` iframe; exported files are unchanged.
- This document's smoke-test claim corrected (above).

New coverage: `tests/backend/desktop-launch.test.ts` (launch contract), preview-CSS tests in `tests/backend/exporter.test.ts`, unmount-flush tests in `tests/renderer/profile-editor.test.tsx`.

## Implemented but unverified

- Windows 11 click-through of the built app, native directory picker, portable-zip/NSIS assembly (no Wine here) — pending owner's hardware. See `docs/WINDOWS_INSTALL.md`.
- Visual/click-through inspection of the running app on Linux: the 2026-11-04 launch check was headless (window up, renderer loaded, no errors) — nobody has clicked through the UI in this environment.

## Planned (not in MVP)

- Import of versioned templates from Digital Product Template Factory (optional integration)
- Image/media asset management UI, multi-page custom layouts, FTP/publish flow

## Acceptance notes

Do not claim Windows validation. No merges; PR left unmerged for owner review.
