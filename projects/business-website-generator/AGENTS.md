# Small Business Website Generator — project agent instructions

**ACTIVE PROJECT FOLDER WHEN ASSIGNED:** `projects/business-website-generator/`

Root `AGENTS.md` overrides these instructions on conflict.

1. Work only inside `projects/business-website-generator/` for application code, manifests, scripts, tests, build artifacts, and project documentation. Other projects are off limits, even if an optional integration is mentioned.
2. Use a dedicated branch named `business-website-generator/<milestone>`; never force-push or merge without owner approval.
3. Before writing code, read `docs/PRODUCT_SPEC.md`, `docs/TEST_PLAN.md`, and `docs/IMPLEMENTATION_STATUS.md`.
4. Build working executable functionality with realistic error handling, not mockup-only views. Keep deterministic logic and data handling separately testable.
5. One-time purchase model; no recurring paid upgrades; do not include copyrighted brand imagery or unlicensed templates.
6. Use synthetic or fixture data in tests. Never commit actual saved games, personal data, invoices, receipts, credentials, model files, runtime databases, or generated products.
7. Validate paths, untrusted inputs, and permissions. Make destructive or external actions opt-in; provide rollback when practical.
8. Record commands actually run, observed results and unresolved platform limitations; do not claim Windows/AI/provider tests passed without executing them.
9. Only update this project's status to MVP/verified after a genuine runnable demonstration. Maintain `docs/IMPLEMENTATION_STATUS.md` after substantive work.
10. Leave project-specific code on a reviewable, unmerged PR. Do not modify shared root workflows or utilities without separate permission.

## Implementation notes (MVP, 2026-10-23)

- Stack: Electron 45 + React 19 + TypeScript strict + Vite, `node:sqlite`, zod-validated IPC, vitest. App code in `app/`; canonical IPC/domain contract in `app/shared/types.ts` — do not fork it.
- Themes are pure deterministic functions (`app/electron/main/themes/`); every theme must escape all user content via `app/shared/escape.ts` and emit zero external assets/scripts.
- Validators live in `app/electron/main/validate.ts` with named `CODE:detail` codes; export is blocked on any error-severity issue.
- Renderer tests are hermetic (`window.bwg` mock in `app/tests/renderer/mock-bwg.ts`); backend tests use synthetic fixtures (`app/tests/backend/fixtures.ts`).
- Windows-only validation (click-through, packaging) is pending the owner's hardware — never claim it here.
