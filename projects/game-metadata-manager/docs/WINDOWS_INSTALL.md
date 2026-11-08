# Windows install — Game Library Metadata Enricher

**Status:** buildable from source; portable zip has not been assembled on Windows yet (NSIS/Wine unavailable on the build VM).

## Option A — portable zip (recommended when available)

1. Download `game-metadata-manager-1.0.0-portable-win32-x64.zip` from the release assets.
2. Unzip it anywhere (e.g. `C:\Games\GameMetadataManager\`).
3. Run `electron.exe` in that folder — no installer, no admin rights needed.
4. Your data (library DB + artwork cache) lives in `%APPDATA%\game-metadata-manager\` and is untouched by replacing the folder with a newer release.

## Option B — run from source (developers)

Prerequisites: Windows 10/11, Node.js 22+ (LTS), Git.

```powershell
cd projects\game-metadata-manager\app
npm install
npm run build
npx electron dist\main.js
```

Other useful commands (run in the same folder):

| Command        | What it does                                              |
|----------------|-----------------------------------------------------------|
| `npm test`     | vitest suite (31 backend tests)                           |
| `npm run typecheck` | strict TypeScript check                              |
| `npm run lint` | eslint, zero warnings allowed                             |
| `npm run pack` | builds, then zips a portable release into `release\`     |

## First run / MVP workflow

1. **Import:** point the importer at a folder containing `.exe` files (scan depth ≤ 4; `node_modules`, `.git`, and `Windows` folders are skipped).
2. **Enrich:** select a game → edit title/description, attach artwork (PNG/JPEG/WEBP, ≤ 10 MB), add tags/collections. Every edit is logged and undoable.
3. **Missing detection:** `Rescan` flags executables whose paths no longer exist — nothing is ever deleted automatically.
4. **Bundle:** `Export` writes a versioned JSON bundle (≤ 50 MB). `Import` merges it back: per-field, newest `updatedAt` wins, conflicts are listed, and export → wipe → import restores everything.

## Data locations

- Database: `%APPDATA%\game-metadata-manager\gmm.db` (SQLite, schema v1)
- Artwork cache: `%APPDATA%\game-metadata-manager\artwork-cache\`

## Troubleshooting

- **Blank window:** delete `%APPDATA%\game-metadata-manager\gmm.db` and restart (you lose only local edits — re-import your last exported bundle to restore).
- **Import finds nothing:** the scanner only looks 4 folders deep and only for `*.exe`.
- **Artwork rejected:** only PNG/JPEG/WEBP under 10 MB, verified by file contents, not extension.
- **Bundle import fails:** the bundle must be valid JSON with `formatVersion: "1.x.y"` — major version 2+ bundles are rejected.
