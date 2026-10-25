# Universal Game Save Manager — project agent instructions

**ACTIVE PROJECT FOLDER WHEN ASSIGNED:** `projects/game-save-manager/`

Root `AGENTS.md` overrides these instructions on conflict.

1. Work only inside `projects/game-save-manager/` for application code, manifests, scripts, tests, build artifacts, and project documentation. Other projects are off limits, even if an optional integration is mentioned.
2. Use a dedicated branch named `game-save-manager/<milestone>`; never force-push or merge without owner approval.
3. Before writing code, read `docs/PRODUCT_SPEC.md`, `docs/TEST_PLAN.md`, and `docs/IMPLEMENTATION_STATUS.md`.
4. Build working executable functionality with realistic error handling, not mockup-only views. Keep deterministic logic and data handling separately testable.
5. Do not assume storefront installation paths equal game save locations. Do not delete game data, bypass cloud sync, or silently overwrite saves.
6. Use synthetic or fixture data in tests. Never commit actual saved games, personal data, invoices, receipts, credentials, model files, runtime databases, or generated products.
7. Validate paths, untrusted inputs, and permissions. Make destructive or external actions opt-in; provide rollback when practical.
8. Record commands actually run, observed results and unresolved platform limitations; do not claim Windows/AI/provider tests passed without executing them.
9. Only update this project's status to MVP/verified after a genuine runnable demonstration. Maintain `docs/IMPLEMENTATION_STATUS.md` after substantive work.
10. Leave project-specific code on a reviewable, unmerged PR. Do not modify shared root workflows or utilities without separate permission.

## Implementation notes (from the MVP build, 2026-10-23)

Concrete conventions the MVP established; follow them for consistency.

- **Stack:** Electron 45 + React 19 + TypeScript (strict, `exactOptionalPropertyTypes`) + Vite; vitest; zod 4 for IPC validation; `node:sqlite` (zero native builds); electron-builder (NSIS + zip, win x64).
- **IPC contract** lives in `app/shared/` (channels, zod schemas, types). The preload bridge (`window.saveManager`) and main handlers must follow it; every payload is validated with zod in `electron/main/ipc/handlers.ts`. Responses use the `{ ok: true, data } / { ok: false, error: { code, message } }` envelope.
- **Backup engine guarantees:** never deletes or modifies the user's originals. Restore requires `confirmed: true` and always takes a `pre-restore safety` backup first. No deletion features in the MVP.
- **Discovery is read-only and honest:** candidates need real local evidence and an evidence label (`verified-path` | `pattern-match` | `manual`). Never invent a save location.
- **Tests** use real filesystem fixtures under `os.tmpdir()`; no fabricated results. Do not weaken tests to make them pass.
- Use `node:path` everywhere; handle drive letters, long paths, and case-insensitive dedup. Windows-only behavior stays labeled pending in `docs/IMPLEMENTATION_STATUS.md` until validated on real Windows.
- Commits: `game-save-manager: ...` on project branches.
- Never commit secrets, `*.db`/`*.sqlite` files, or `dist/`/`release/` artifacts.
