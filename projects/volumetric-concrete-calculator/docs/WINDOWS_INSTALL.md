# Windows install — Volumetric Concrete Mix Calculator

## Portable build (recommended for testing)

A portable Windows x64 zip is built on every release:

```
Volumetric Concrete Mix Calculator-0.1.0-win-x64.zip
```

1. Download/copy the zip to the Windows 11 PC.
2. Extract it anywhere (e.g. `C:\Apps\VCC`).
3. Run `Volumetric Concrete Mix Calculator.exe`.
4. No installer, no admin rights needed, no registry changes. All data stays
   in `%APPDATA%\volumetric-concrete-calculator\` (SQLite database).

First launch: create a calibration profile (Calibration profiles → New profile),
enter gate calibrations from a scale ticket or test pour, add a mix design,
then run the Calculator.

## Building the portable zip yourself (Windows)

Prerequisites: Node.js 22+, Windows 10/11 x64.

```powershell
cd projects\volumetric-concrete-calculator\app
npm install
npm test          # expect 54/54
npm run build
npx electron-builder --win --x64 -c.win.target=zip
```

Output: `release\Volumetric Concrete Mix Calculator-0.1.0-win-x64.zip`.

## NSIS installer

Not currently produced: assembling an NSIS installer requires Wine (unavailable
on the Linux build VM) or a Windows machine. To build one on Windows:

```powershell
npx electron-builder --win --x64 -c.win.target=nsis
```

## Notes

- No code signing is configured — Windows SmartScreen will warn on first run.
  This is expected for an unsigned test build.
- The app is fully offline; it makes no network requests.
