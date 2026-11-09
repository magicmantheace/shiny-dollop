# Windows install — Digital Product Template Factory (DRAFT)

> Draft written 2026-10-23 from the backend milestone. Steps marked
> **[unverified]** have not been executed on a real Windows machine yet —
> the build environment here is Linux and cannot assemble or run the
> Windows installer (no Wine).

## Requirements

- Windows 10/11 x64
- Node.js 22+ (LTS recommended) — only needed if building from source
- No admin rights required for the portable build; admin required for the NSIS installer

## Option A — installer (recommended, [unverified])

1. Download `Digital Product Template Factory Setup 0.1.0.exe` from the release.
2. Run it, choose an install folder, finish the wizard.
3. Launch "Digital Product Template Factory" from the Start menu.
4. First launch creates the local database at
   `%APPDATA%\digital-product-template-factory\data\template-factory.db`.
   No account, no network calls.

## Option B — build from source ([unverified] end-to-end)

1. Install Node.js 22+ from https://nodejs.org.
2. Open PowerShell in `projects\digital-template-factory\app` and run:
   ```powershell
   npm install
   npm run build
   ```
   Expected: `dist/` contains `electron/`, `preload/` and `renderer/`.
3. Package the installer:
   ```powershell
   npm run package:win
   ```
   Expected: `release\Digital Product Template Factory Setup 0.1.0.exe`.
4. For development with hot reload:
   ```powershell
   npm run dev
   ```
   Expected: Vite on http://localhost:5175, Electron window opens against it.

## Verify the install

1. Open the app → the template gallery should list **Simple Invoice**,
   **Weekly Planner Page** and **Checklist**.
2. Create a document from Simple Invoice, fill business/client/invoice
   number/issue date and one line item, then export → you should get a
   valid `.html` file that opens in a browser.
3. Export with an empty required field → the app must report a
   `FIELD_REQUIRED:<key>` error instead of writing a file.
4. Close and reopen the app → documents and imported templates persist.

## Troubleshooting

- **Blank window:** the renderer bundle may not have built — rerun `npm run build:renderer` and check `dist/renderer/index.html` exists.
- **Database errors on launch:** delete `%APPDATA%\digital-product-template-factory\data\`
  and relaunch; migrations re-apply automatically (documents will be lost — this folder is local-only).
- **SmartScreen warning:** expected for an unsigned build; choose "More info → Run anyway" on a self-built binary.

## Uninstall

- Installer build: Windows Settings → Apps → uninstall.
- User data (documents, imported templates) is **not** removed automatically;
  delete `%APPDATA%\digital-product-template-factory\` to clear it.
