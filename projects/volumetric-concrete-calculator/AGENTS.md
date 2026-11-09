# Volumetric Concrete Mix Calculator — project agent instructions

**ACTIVE PROJECT FOLDER WHEN ASSIGNED:** `projects/volumetric-concrete-calculator/`

Root `AGENTS.md` overrides these instructions on conflict.

1. Work only inside `projects/volumetric-concrete-calculator/` for application code, manifests, scripts, tests, build artifacts, and project documentation. Other projects are off limits, even if an optional integration is mentioned.
2. Use a dedicated branch named `volumetric-concrete-calculator/<milestone>`; never force-push or merge without owner approval.
3. Before writing code, read `docs/PRODUCT_SPEC.md`, `docs/TEST_PLAN.md`, and `docs/IMPLEMENTATION_STATUS.md`.
4. Build working executable functionality with realistic error handling, not mockup-only views. Keep deterministic logic and data handling separately testable.
5. Do not assert structural concrete strength, code compliance, legal truck payload, or tested mix adequacy from estimates. Mark assumptions and measurement sources.
6. Use synthetic or fixture data in tests. Never commit actual saved games, personal data, invoices, receipts, credentials, model files, runtime databases, or generated products.
7. Validate paths, untrusted inputs, and permissions. Make destructive or external actions opt-in; provide rollback when practical.
8. Record commands actually run, observed results and unresolved platform limitations; do not claim Windows/AI/provider tests passed without executing them.
9. Only update this project's status to MVP/verified after a genuine runnable demonstration. Maintain `docs/IMPLEMENTATION_STATUS.md` after substantive work.
10. Leave project-specific code on a reviewable, unmerged PR. Do not modify shared root workflows or utilities without separate permission.

---

## Implementation notes (added 2026-10-23, MVP branch `volumetric-concrete-calculator/mvp`)

The 10 rules above are the owner's verbatim instructions and take precedence.

- Stack: Electron 45 + React 19 + TypeScript (strict) + Vite + vitest + zod; `node:sqlite` for local profiles. Engine (`app/engine/`) is pure functions with no I/O so it is unit-testable without Electron.
- IPC channels are zod-validated in `app/electron/main/ipc/handlers.ts`; the renderer only sees the narrow `window.vcc` bridge.
- Mass/volume basis convention for the calibration exchange: water and admixture are volume-basis, everything else mass-basis (documented in `docs/CALIBRATION_EXCHANGE_FORMAT.md`).
- DB transactions use explicit `BEGIN IMMEDIATE`/`COMMIT`/`ROLLBACK` — `node:sqlite`'s `DatabaseSync` has no `transaction()` helper.
- Build outputs: main/preload compile to `dist/` with `rootDir: "."` so `dist/electron/main/index.js` and `dist/electron/preload/index.js` land flat; the renderer builds to `dist/renderer`.
- Smoke test (`npm run smoke`) needs `xvfb-run` on Linux and `--no-sandbox` when running as root; the app quits itself in `VCC_SMOKE=1` mode.
- Windows packaging: `npm run package:win` produces a portable zip (NSIS needs Wine/Windows; not attempted here).
