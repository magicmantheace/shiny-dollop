# Implementation status — Volumetric Concrete Mix Calculator

- **Overall status:** MVP FUNCTIONAL (implemented and tested on Linux; Windows execution pending)
- **Priority:** 3/17
- **Branch:** `volumetric-concrete-calculator/mvp`
- **Source/code implemented:** Yes — `app/` (Electron 45 + React 19 + TypeScript strict + Vite, node:sqlite, zod-validated IPC)
- **Build validated:** Yes — `npm run build` (renderer + main + preload) green on Linux
- **Automated tests executed:** Yes — 54/54 pass (`npm test`), typecheck clean, lint clean
- **Window smoke test:** PASS — real Electron window boots under xvfb
- **End-to-end MVP verified:** Engine-level acceptance workflow passes (calibrated mix + 8 m³ → reproducible quantities + remaining stock, byte-identical across runs); full desktop click-through on Windows pending owner hardware
- **Owner review:** Pending (PR left unmerged)

## What was built

| Area | Status | Evidence |
|---|---|---|
| Calculation engine (units, calibrations, quantities, inventory, warnings) | complete+verified | `app/engine/`; 54 vitest tests incl. known-value assertions |
| Versioned calibration profiles (SQLite) | complete+verified | CRUD via zod-validated IPC; migration v1 |
| Calibration exchange v1.0.0 export/import | complete+verified | export validates against the documented contract; every documented validation rule has a test; round-trip preserves calculation results |
| Unit-aware CSV export | complete+verified | headers name units; disclaimer block included |
| Desktop UI (calculator, profiles, history) | complete, UI click-through on Windows pending | builds and boots (smoke PASS); all inputs labelled; estimate/nominal-only labelling throughout |
| Portable Windows zip | complete+verified (builds on Linux) | electron-builder `--win --x64 -c.win.target=zip`; contents verified |
| NSIS installer | not attempted | no Wine on this VM; documented in WINDOWS_INSTALL.md |

## Known limitations (honest)

- Windows-only behaviors unverified here: portable-zip first launch on Windows 11, native file dialogs, real user click-through.
- The v1.0.0 exchange envelope carries `measuredAt` but not the free-text measurement `source` note (no such field in the contract) — source stays in this app's profile.
- Scheduler-style recurring calculations: out of scope for MVP (single calculations + history).
- No code signing (SmartScreen will warn on Windows).

## Next actions

1. Owner runs the portable zip on Windows 11; records click-through of the MVP workflow.
2. Optional follow-ups: admixture dosing curves, multi-truck fleet profiles, calibration history/audit per profile.

## Acceptance notes

MVP acceptance workflow executed at engine level with recorded evidence (see `app/tests/integration/workflow.test.ts`):
8 m³ of mix `NOM-25` (nominal ID only) at 5% waste → cement 2688.0 kg (gate 336.0), sand 6720.0 kg, stone 8820.0 kg, water 1386.0 L, admixture 10.08 L; remaining stock computed from 10000/30000/30000/8000/200 kg starting stock; zero warnings; byte-identical across repeated runs.
