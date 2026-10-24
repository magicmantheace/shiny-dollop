# Windows install — Offline Personal Finance Simulator

Portable Windows install for the owner's Windows 11 box (i5-10400F, RTX 3060, 32 GB RAM).
This has **not** been run yet — the backend smoke test currently fails on Linux (see
`docs/IMPLEMENTATION_STATUS.md`), so fix that before packaging.

## Prerequisites

- Windows 10/11 64-bit
- Node.js 20 LTS (only needed to build; the portable app itself needs no Node)
- The `finance-simulator/mvp` branch checked out (or the packaged release zip from the owner)

## Build the portable app

From `projects/finance-simulator/app/` in PowerShell:

```powershell
npm install
npm run build:renderer   # vite -> dist/renderer
npm run build            # tsc -> dist/electron (main + preload)
npx electron-builder --win portable --x64
```

> Note: the repo's `package:win` script runs `electron-builder --win --x64` with no
> `build` config in `package.json`, so electron-builder falls back to its default
> Windows target (NSIS installer). The explicit `--win portable` above is what
> produces the portable exe. Consider adding a `build.win.target: ["portable"]`
> section to `package.json` so `npm run package:win` does this by default.

Output lands in `app/dist/` (the exact folder is printed at the end of the run).
Look for the `-portable.exe`.

## Install / run (portable, no installer)

1. Copy the portable `.exe` (or the `win-unpacked` folder) to a folder you own, e.g.
   `C:\Users\<you>\Apps\FinanceSimulator\`. No admin rights needed.
2. Double-click the `.exe` to launch. Your data is stored locally in the app's user-data
   folder — nothing leaves the machine.
3. To "uninstall", just delete the folder. Back up the SQLite database file first if you
   want to keep your scenarios (see below).

## SmartScreen note

The portable build is **unsigned**, so Windows SmartScreen will show a blue
"Windows protected your PC" prompt on first launch. This is expected for unsigned
personal tools. Click **More info → Run anyway**. If that is not acceptable, sign the
build with a code-signing certificate (out of scope for the MVP).

## Backing up your data

The app stores debts/income in a local SQLite file under the Electron `userData`
directory (`%APPDATA%\finance-simulator\` or similar — confirm the exact path in the
running app's docs before relying on it). Copy that file to back up; restore by
putting it back before launch. Exported CSV/JSON scenario reports are separate
files wherever you save them via the in-app Export buttons.

## Troubleshooting

- **App doesn't start:** make sure you extracted the whole folder (portable exe next to
  its resources); run from a local drive, not a network share.
- **Blank window:** the renderer bundle may be stale — rebuild with `npm run build:renderer`
  before `npm run package:win`.
- **SmartScreen blocks silently:** right-click the exe → Properties → check "Unblock"
  if present, then launch again.
