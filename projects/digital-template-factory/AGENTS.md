# Digital Product Template Factory — project agent instructions

**ACTIVE PROJECT FOLDER WHEN ASSIGNED:** `projects/digital-template-factory/`

Root `AGENTS.md` overrides these instructions on conflict.

1. Work only inside `projects/digital-template-factory/` for application code, manifests, scripts, tests, build artifacts, and project documentation. Other projects are off limits, even if an optional integration is mentioned.
2. Use a dedicated branch named `digital-template-factory/<milestone>`; never force-push or merge without owner approval.
3. Before writing code, read `docs/PRODUCT_SPEC.md`, `docs/TEST_PLAN.md`, and `docs/IMPLEMENTATION_STATUS.md`.
4. Build working executable functionality with realistic error handling, not mockup-only views. Keep deterministic logic and data handling separately testable.
5. Use original assets, legal licenses, and one-time purchase compatible outputs; avoid paid-service requirements.
6. Use synthetic or fixture data in tests. Never commit actual saved games, personal data, invoices, receipts, credentials, model files, runtime databases, or generated products.
7. Validate paths, untrusted inputs, and permissions. Make destructive or external actions opt-in; provide rollback when practical.
8. Record commands actually run, observed results and unresolved platform limitations; do not claim Windows/AI/provider tests passed without executing them.
9. Only update this project's status to MVP/verified after a genuine runnable demonstration. Maintain `docs/IMPLEMENTATION_STATUS.md` after substantive work.
10. Leave project-specific code on a reviewable, unmerged PR. Do not modify shared root workflows or utilities without separate permission.

## Implementation notes (MVP, 2026-10-23)

- Canonical IPC contract lives in `app/shared/types.ts` (`DtfApi`, namespaced: `templates.*`, `documents.*`, `export.*` with object inputs). The preload exposes exactly this shape; the renderer declares `window.dtf` from the same interface. Do not redefine the contract in task briefs — point at `shared/types.ts`.
- Backend store functions (`electron/main/store.ts`) use positional args; the IPC layer wraps them into the object-input API.
- Tests run as two vitest projects (`backend` node + `renderer` jsdom) via `app/vitest.config.ts`; `npm test` runs both (120 tests at MVP).
- Export pipeline order: required-field validation → render → contrast → structure. `exportedAt` is returned in the license record but never hashed; contentHash = sha256 of the HTML bytes.
- Imported (external) templates persist in SQLite but have no renderer — `export:generate` returns `TEMPLATE_RENDER_UNSUPPORTED` for them. This is by design, not a bug.
