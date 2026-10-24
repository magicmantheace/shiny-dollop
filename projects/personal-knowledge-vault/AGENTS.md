# Personal Knowledge Vault — project agent instructions

**ACTIVE PROJECT FOLDER WHEN ASSIGNED:** `projects/personal-knowledge-vault/`

Root `AGENTS.md` overrides these instructions on conflict.

1. Work only inside `projects/personal-knowledge-vault/` for application code, manifests, scripts, tests, build artifacts, and project documentation. Other projects are off limits, even if an optional integration is mentioned.
2. Use a dedicated branch named `personal-knowledge-vault/<milestone>`; never force-push or merge without owner approval.
3. Before writing code, read `docs/PRODUCT_SPEC.md`, `docs/TEST_PLAN.md`, and `docs/IMPLEMENTATION_STATUS.md`.
4. Build working executable functionality with realistic error handling, not mockup-only views. Keep deterministic logic and data handling separately testable.
5. No ingestion of owner's private data without authorization; no automatic AthenZ sync or edits to AthenZ.
6. Use synthetic or fixture data in tests. Never commit actual saved games, personal data, invoices, receipts, credentials, model files, runtime databases, or generated products.
7. Validate paths, untrusted inputs, and permissions. Make destructive or external actions opt-in; provide rollback when practical.
8. Record commands actually run, observed results and unresolved platform limitations; do not claim Windows/AI/provider tests passed without executing them.
9. Only update this project's status to MVP/verified after a genuine runnable demonstration. Maintain `docs/IMPLEMENTATION_STATUS.md` after substantive work.
10. Leave project-specific code on a reviewable, unmerged PR. Do not modify shared root workflows or utilities without separate permission.

## Implementation notes (2026-10-23, MVP)

- Stack: Electron 45 + React 19 + TS strict + Vite, `node:sqlite` (FTS5
  verified compiled in), zod-validated flat `window.pkv` IPC; canonical
  contract in `app/shared/types.ts`.
- Backend owns `app/electron/`, `app/db/`, `app/shared/`; renderer owns
  `app/src/`, `app/tests/ui/`. Shared build/test scripts live in
  `app/package.json` and must cover both sides (`typecheck`: main + preload
  + renderer; `test`: all suites; `build`: all three outputs) — an unwired
  gate let 7 renderer type errors slip through once; keep the gates wired.
- Revisions are append-only enforced by a DB-level trigger; sources are
  write-once at creation; reject requires a reason; approve is per-record.
- Backup format `1.0.0`, byte-deterministic export; import rejects unknown
  major versions and corrupt payloads with named errors.
- DB lives under `app.getPath('userData')`; `*.db*` gitignored.
