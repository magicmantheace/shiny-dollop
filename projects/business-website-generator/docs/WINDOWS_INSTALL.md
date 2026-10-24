# Windows install notes — Small Business Website Generator

**Status:** NOT VERIFIED on Windows — the steps below are the intended flow, executed only on Linux here.

## Prerequisites

- Windows 11 (64-bit), Node.js 24 LTS
- No admin rights needed; no network access needed at runtime

## Build the portable app

```powershell
cd projects\business-website-generator\app
npm ci
npm run build
npx electron-packager . "Business Website Generator" --platform=win32 --arch=x64 --out=release --overwrite
```

Expected output: `release\Business Website Generator-win32-x64\` containing the executable.
Actual result on Windows: **not yet run** — record output here when executed.

## Manual verification checklist (owner's hardware)

1. Launch the executable; dashboard shows with no console errors.
2. New-site wizard: name → pick "Restaurant" → pick "Hearth" theme → site created.
3. Profile editor: fill contact/services/menu/social/SEO; invalid email is blocked inline; autosave shows dirty → saved.
4. Theme tab: switch to another theme; preview re-renders.
5. Preview tab: switch pages; toggle Mobile/Desktop; iframe shows the site.
6. Export tab: Validate → clean; Export → pick an empty folder → 6 files written (`index.html`, `menu.html`, `contact.html`, `style.css`, `sitemap.xml`, `robots.txt`).
7. Open the exported `index.html` in a browser (offline): pages render, nav links work, no external requests (DevTools Network).
8. Wipe the business name → Validate shows `FIELD_REQUIRED`; Export is disabled.

## Known gaps

- No code signing — Windows SmartScreen will warn on first launch.
- NSIS installer not assembled (no Wine in the build environment); portable folder is the deliverable.
