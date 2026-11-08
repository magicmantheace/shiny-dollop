# Desktop Automation Builder — project agent instructions

**ACTIVE PROJECT FOLDER WHEN ASSIGNED:** `projects/desktop-automation-builder/`

Root `AGENTS.md` overrides these instructions on conflict.

1. Work only inside `projects/desktop-automation-builder/` for application code, manifests, scripts, tests, build artifacts, and project documentation. Other projects are off limits, even if an optional integration is mentioned.
2. Use a dedicated branch named `desktop-automation-builder/<milestone>`; never force-push or merge without owner approval.
3. Before writing code, read `docs/PRODUCT_SPEC.md`, `docs/TEST_PLAN.md`, and `docs/IMPLEMENTATION_STATUS.md`.
4. Build working executable functionality with realistic error handling, not mockup-only views. Keep deterministic logic and data handling separately testable.
5. No unrestricted shell execution or invisible background persistence; no privileged/destructive actions without separate explicit approval.
6. Use synthetic or fixture data in tests. Never commit actual saved games, personal data, invoices, receipts, credentials, model files, runtime databases, or generated products.
7. Validate paths, untrusted inputs, and permissions. Make destructive or external actions opt-in; provide rollback when practical.
8. Record commands actually run, observed results and unresolved platform limitations; do not claim Windows/AI/provider tests passed without executing them.
9. Only update this project's status to MVP/verified after a genuine runnable demonstration. Maintain `docs/IMPLEMENTATION_STATUS.md` after substantive work.
10. Leave project-specific code on a reviewable, unmerged PR. Do not modify shared root workflows or utilities without separate permission.

## Implementation notes (2026-10-23, MVP)

- The 10 rules above are kept verbatim from the owner's scaffold; these notes are appended implementation detail, not changes to the rules.
- App lives in `app/` (Electron 45 + React 19 + TS strict + Vite, `node:sqlite`, zod-validated IPC). Canonical contract: `app/shared/types.ts` (flat `window.dab` API, 17 `dab:` channels) + `app/shared/errors.ts` (named error codes). Both workers converged on it unchanged.
- Sandbox: every step path is resolved against the workflow's `sandboxRoot` and rejected (`PATH_OUTSIDE_SANDBOX`) if it escapes. Trash is the sandbox's `.dab-trash/` folder — files are moved, never deleted.
- Scripts run only from the user-registered allowlist (`approved_scripts` table), spawned `shell: false` with a 60s timeout; cancel kills the process group on POSIX.
- `workflowsUpdate` archives the previous state into `workflow_versions` and bumps `version` on every update (including no-op patches — deliberate MVP choice).
- DB at `userData/dab.sqlite` (gitignored). Export envelope `formatVersion: '1.0.0'`; imports never auto-run.
- Windows validation is pending the owner's hardware: script kill path and NSIS packaging are implemented but unverified on Windows 11.
