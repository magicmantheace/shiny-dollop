# WINDOWS_INSTALL.md — Game Save Manager (MVP, v0.1.0)

Target OS: **Windows 11 x64**. The app is a portable Electron build — no
administrator rights needed to run it, nothing is written to the registry.

## Where the portable build comes from

The portable zip is **built here on Linux** by the owner and copied to the
Windows machine. It is gitignored (`release/`, `*.zip`) and is **not**
committed to the repo.

- Built 2026-10-23 on Linux (Node v24.22.1) with:
  `npx electron-builder --win --x64 -c.win.target=zip` from `app/`
- Output: `projects/game-save-manager/app/release/Game Save Manager-0.1.0-win-x64.zip`
- Size: **154,191,688 bytes (~147 MB)**; 74 entries inside.
- Verified: zip lists `Game Save Manager.exe` (**249,797,632 bytes**, not a
  stub) plus the Electron runtime files, `resources/app.asar` (6,294,859
  bytes, the compiled app), and locale packs.
- Not signed, no installer, no auto-update in the MVP. The NSIS target is
  configured (`electron-builder.yml`) but was **not assembled** on this
  Linux VM (no Wine) — `npm run package:win` is pending on the owner's
  machine (see "Reproducible build" below).

## Run the portable app

1. On the Windows machine, create a folder, e.g. `C:\Apps\GameSaveManager\`.
2. Extract `Game Save Manager-0.1.0-win-x64.zip` into that folder.
3. Double-click `Game Save Manager.exe`. The window opens; the Library
   view lists tracked games.
4. (First run) Click **Add game** → either run **Scan** for Steam/Epic
   candidates or **Browse** to pick a save folder directly.

No install step, no shortcuts are created — this is the portable build.

## Data locations (Windows)

Everything the app stores is per-user under Electron's `userData`
(`%APPDATA%\game-save-manager`):

```
%APPDATA%\game-save-manager\
  data\savemanager.db            # SQLite: games, backups, backup_files, schedules
  SaveManager\backups\          # backup storage root
    <gameId>\
      <ISO-8601-timestamp>\     # one folder per backup version
        manifest.json           # per-file SHA-256 + sizes
        <save files…>           # plain copy of the save-folder tree
```

Original save files are never modified or deleted by the app.

## Uninstall

The portable build is self-contained:

1. Delete the folder you extracted the zip into (e.g.
   `C:\Apps\GameSaveManager\`).
2. (Optional, removes all backups and history) Delete
   `%APPDATA%\game-save-manager\`.

That is the entire uninstall — no registry entries to clean.

## Reproducible build (for the owner, on their machine)

Prerequisites: Windows 10/11 (or Linux for the portable zip; NSIS needs
Windows or Wine), **Node.js ≥ 22** (per `engines` in `app/package.json`),
`npm`.

```cmd
cd projects\game-save-manager\app
npm ci
npm run typecheck && npm run lint && npm run test
npx electron-builder --win --x64 -c.win.target=zip
```

Expected outputs (from `app/`):

- `dist\` — compiled renderer (`index.html`, assets), main process JS,
  preload JS.
- `release\Game Save Manager-0.1.0-win-x64.zip` — the portable app.
  (Reference build on Linux 2026-10-23: **154,191,688 bytes**.)

For the NSIS installer instead (assembles only on Windows/with Wine):

```cmd
npx electron-builder --win --x64
:: or: npm run package:win
```

Expected: `release\Game Save Manager-0.1.0-win-x64.exe` (installer).
**Status:** not yet assembled — pending on the owner's Windows machine.
Code signing is intentionally not configured; a release build needs the
owner's explicit approval and signing decision.
