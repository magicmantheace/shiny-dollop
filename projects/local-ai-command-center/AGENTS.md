# Local AI Command Center — project agent instructions

**ACTIVE PROJECT FOLDER WHEN ASSIGNED:** `projects/local-ai-command-center/`

Root `AGENTS.md` overrides these instructions on conflict.

1. Work only inside `projects/local-ai-command-center/` for application code, manifests, scripts, tests, build artifacts, and project documentation. Other projects are off limits, even if an optional integration is mentioned.
2. Use a dedicated branch named `local-ai-command-center/<milestone>`; never force-push or merge without owner approval.
3. Before writing code, read `docs/PRODUCT_SPEC.md`, `docs/TEST_PLAN.md`, and `docs/IMPLEMENTATION_STATUS.md`.
4. Build working executable functionality with realistic error handling, not mockup-only views. Keep deterministic logic and data handling separately testable.
5. No autonomous unrestricted write access, credentials, shell or network privileges; no paid inference by default.
6. Use synthetic or fixture data in tests. Never commit actual saved games, personal data, invoices, receipts, credentials, model files, runtime databases, or generated products.
7. Validate paths, untrusted inputs, and permissions. Make destructive or external actions opt-in; provide rollback when practical.
8. Record commands actually run, observed results and unresolved platform limitations; do not claim Windows/AI/provider tests passed without executing them.
9. Only update this project's status to MVP/verified after a genuine runnable demonstration. Maintain `docs/IMPLEMENTATION_STATUS.md` after substantive work.
10. Leave project-specific code on a reviewable, unmerged PR. Do not modify shared root workflows or utilities without separate permission.

## Implementation notes (appended 2026-10-23, MVP)

- App lives in `app/` (Electron + React + TS strict + Vite, `node:sqlite`, zod-validated IPC), mirroring the sibling queue apps. The frozen contract is `app/shared/types.ts` (flat `window.lacc` API) + `app/shared/errors.ts` (named codes).
- The ONLY network caller is `electron/main/adapter.ts`'s `OllamaAdapter`, constructed solely from the validated, loopback-only endpoint config. `MockAdapter` is the deterministic offline/test adapter (`[mock:fail]`, `[mock:hang]` prompt markers are test fixtures).
- Model output may contain a ```propose path=…``` block; the engine turns it into a pending `Proposal`. Approval is the only path that ever writes a proposed file, always containment-checked against the workspace root. Rejection must never write.
- The audit table is append-only by SQLite trigger; do not add update/delete paths.
- Verify with: `npm test` (backend + renderer), `npm run typecheck`, `npm run lint`, `npm run build`, `npm run smoke` (exercises the full acceptance workflow in the packaged main, prints `SMOKE_OK`).
