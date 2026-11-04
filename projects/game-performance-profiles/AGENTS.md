# Windows Game Performance Profiles — project agent instructions

**ACTIVE PROJECT FOLDER WHEN ASSIGNED:** `projects/game-performance-profiles/`

Root `AGENTS.md` overrides these instructions on conflict.

1. Work only inside `projects/game-performance-profiles/` for application code, manifests, scripts, tests, build artifacts, and project documentation. Other projects are off limits, even if an optional integration is mentioned.
2. Use a dedicated branch named `game-performance-profiles/<milestone>`; never force-push or merge without owner approval.
3. Before writing code, read `docs/PRODUCT_SPEC.md`, `docs/TEST_PLAN.md`, and `docs/IMPLEMENTATION_STATUS.md`.
4. Build working executable functionality with realistic error handling, not mockup-only views. Keep deterministic logic and data handling separately testable.
5. Read-only recommendations by default. No overclocking, driver patching, security-service shutdown, or anti-cheat interference.
6. Use synthetic or fixture data in tests. Never commit actual saved games, personal data, invoices, receipts, credentials, model files, runtime databases, or generated products.
7. Validate paths, untrusted inputs, and permissions. Make destructive or external actions opt-in; provide rollback when practical.
8. Record commands actually run, observed results and unresolved platform limitations; do not claim Windows/AI/provider tests passed without executing them.
9. Only update this project's status to MVP/verified after a genuine runnable demonstration. Maintain `docs/IMPLEMENTATION_STATUS.md` after substantive work.
10. Leave project-specific code on a reviewable, unmerged PR. Do not modify shared root workflows or utilities without separate permission.

## Implementation notes (added 2026-10-23 — the 10 rules above are unchanged)

- **Two-worker split, one branch.** Worker A owns `app/electron/`, `app/tests/`, `app/shared/gpp-types.ts`, `app/src/gpp-api.d.ts`; Worker B owns `app/src/` (renderer), `app/index.html`, `app/tests-ui/`, and the docs. `app/package.json`, `app/vite.config.ts`, and `app/tsconfig.json` are shared — edit cooperatively and say so in the commit message. Nothing is pushed; the coordinator reconciles.
- **The contract is `app/shared/gpp-types.ts`.** Twelve `gpp:*` channels plus `gpp:activation-progress`, exposed to the renderer as camelCase `window.gpp` methods by the preload script. Worker B never invents channel names; Worker A never renames them.
- **Renderer test setup that bit us:** vitest needs `globals: true` in `vitest.ui.config.ts` or `@testing-library/react` auto-cleanup never runs and DOM accumulates across tests. UI tests mock `window.gpp` (see `tests-ui/mocks.ts`) — no real IPC in `tests-ui/` ever.
- **Strictness is split:** backend `tsconfig.json` (exactOptionalPropertyTypes, noUncheckedIndexedAccess) intentionally excludes `src/` and `tests-ui/`; renderer strictness lives in `tsconfig.renderer.json`. Keep it that way.
- **No Windows box on the build VM.** `WindowsOsLayer` compiles everywhere but executes on win32 only; capability probing reports unsupported off-Windows. Never claim a Windows-only path works without running it on Adam's machine — see `docs/WINDOWS_INSTALL.md` for the runbook.
- **Safety invariants (both layers):** activation requires `approved === true`; realtime priority is not representable; the protected-process denylist (System, Registry, smss.exe, csrss.exe, …) is enforced in both layers; snapshots are labeled "approximate — point-in-time estimate, not a benchmark".
