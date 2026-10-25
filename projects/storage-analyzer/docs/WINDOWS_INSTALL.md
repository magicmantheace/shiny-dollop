# Windows install — PC Storage and Duplicate Finder

## Portable run (recommended for review)

No installer is produced on the Linux build VM (no Wine). On a Windows 10/11
machine with Node 22+:

```powershell
cd projects\storage-analyzer\app
npm install
npm run build
npx electron-builder --win --x64 --dir
```

`--dir` produces an unpacked portable folder under `release\win-unpacked\`; run
`Storage Analyzer.exe` from there. This exercises the real main process, the
preload bridge, and the React renderer against the live filesystem scanner.

For a real installer instead of the portable folder, drop `--dir`:

```powershell
npx electron-builder --win --x64
```

This produces the NSIS installer in `release\` (configured in
`electron-builder.yml`). Code signing is intentionally not configured — no
release without owner approval.

## Reproducible build

1. Check out branch `storage-analyzer/mvp` at the reviewed commit.
2. `npm install` (lockfile: `app/package-lock.json`).
3. `npm run typecheck` — main + preload + renderer must all pass.
4. `npx vitest run` — UI (35 tests) and backend suites must all pass.
5. `npm run build` — emits `dist/` (main, preload, renderer).
6. `npx electron-builder --win --x64` — emits the installer/zip in `release\`.

## Smoke checklist (on Windows)

1. Launch the app; the New scan view appears.
2. Choose a small test folder (NOT a drive root); confirm no protected-path banner.
3. Choose `C:\` (or `C:\Windows`); confirm the protected-path warning banner.
4. Start a scan; confirm live file/folder/byte counters and the current path update.
5. Cancel mid-scan; confirm the cancelled state and "View results".
6. Re-scan to completion; confirm folder sizes, largest files, type summary.
7. Copy a file twice into the test folder, rescan; confirm one duplicate group with
   the SHA-256, both paths, and savings = size × (copies − 1).
8. Export CSV and JSON to a chosen path; open both and confirm content.
9. History: confirm the scan appears with a `complete` badge; open its results.
10. Confirm there is **no** delete/remove affordance anywhere in the UI.

## Notes

- The app is read-only by design: scanning never writes, moves, or deletes files.
  The export step is the only disk write, to the path the user supplies.
- Exclusion defaults: `node_modules`, `$RECYCLE.BIN`, `System Volume Information`.
- Large system folders may hit permission-denied entries; the scanner skips them
  and reports the skipped count in the scan view rather than failing.
