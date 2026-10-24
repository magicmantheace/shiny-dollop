# Windows install guide — Concrete Operations Manager

**Status:** steps below are defined but **PENDING verification on a real Windows
machine**. The installer has not been built on this Linux VM (no Wine here), and
no Windows install has been exercised. Do not treat this as a verified procedure.

## Option A — installer (pending: not yet built)

1. On a Windows 10/11 x64 machine, download
   `Concrete Operations Manager-<version>-win-x64.exe` from the project's
   `app/release/` output (produced by `npm run package:win` on Windows).
2. Run the installer. It offers per-user install, Start Menu shortcut and an
   optional desktop shortcut (NSIS, `oneClick: false`).
3. Launch "Concrete Operations Manager" from the Start Menu.

> Pending: build the NSIS installer on Windows and walk these steps for real,
> including install, launch, uninstall, and shortcut behavior.

## Option B — portable (pending: zip not yet assembled)

1. Unzip the portable build to a folder you own (e.g. `C:\Apps\ConcreteOps\`).
2. Run `Concrete Operations Manager.exe`.

> Pending: assemble and smoke-test the portable zip on Windows.

## First run

- The app creates its database at
  `%APPDATA%\Concrete Operations Manager\ConcreteOps\data\concrete-ops.db`
  (Electron `userData`). Nothing is written to the install folder or the repo.
- Single-instance lock: a second launch focuses the running window.

## Backup

Settings → **Back up database** writes a timestamped `.db` copy wherever you
choose. **Restore from backup…** validates the file (must be a Concrete
Operations database at a supported schema version) and keeps a rollback copy of
the pre-restore database before replacing it.

## Uninstall

Use Windows Settings → Apps to uninstall (installer), or delete the portable
folder. To remove all local data as well, delete
`%APPDATA%\Concrete Operations Manager\`.

## Troubleshooting

- **Blank window:** the renderer is a local file bundle; no network is needed or
  used. If the window is blank, check `%APPDATA%` permissions and relaunch.
- **"Database is locked":** only one instance may run; close the other copy.
- **Restore rejected:** the file failed validation (not a Concrete Operations
  database, or a newer schema version). Nothing was changed; the rollback copy
  from the last successful restore is kept next to the live database.

## Developer notes (Windows)

- Prerequisites: Node.js 22+, npm. `npm install`, `npm run dev` (Vite on
  `:5175`), `npm test`, `npm run build`, `npm run smoke`.
- `npm run package:win` requires Windows (electron-builder NSIS target).
- Code signing is intentionally not configured — no release without owner approval.
