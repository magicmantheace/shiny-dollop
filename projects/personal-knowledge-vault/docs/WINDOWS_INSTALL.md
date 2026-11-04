# Windows install — Personal Knowledge Vault

The Linux build here validates code, tests, and the backend against compiled
output only. A real Windows 11 run needs the owner's hardware.

## Build the Windows package

On a Windows 11 machine with Node 24+ installed:

1. `cd projects/personal-knowledge-vault/app`
2. `npm ci`
3. `npm run build` — typecheck (main + preload + renderer), compile, renderer bundle
4. `npx electron-builder --win --x64` (or `npm run package:win`)
5. The installer/portable output lands in `dist/` (gitignored).

## First-run checklist

- Launch the app; the SQLite database is created under
  `%APPDATA%/personal-knowledge-vault/` on first run.
- Create a note with a source → it appears as `candidate` with a status badge.
- Approve it → badge flips to `verified`; create a second note and confirm the
  first approval did not touch it.
- Search for a word from the note body → FTS returns it.
- Edit the note with a change summary → revision history shows the new revision
  with a diff; the old revision is unchanged.
- Export a backup (save dialog) → import it into a fresh profile → notes,
  sources, revisions, and statuses restore identically.

## Known gaps

- No code signing — Windows SmartScreen will warn on first launch.
- NSIS/portable assembly was not attempted on Linux (no Wine here).
