# Procedural Dungeon Designer — project agent instructions

**ACTIVE PROJECT FOLDER WHEN ASSIGNED:** `projects/procedural-dungeon-designer/`

Root `AGENTS.md` overrides these instructions on conflict.

1. Work only inside `projects/procedural-dungeon-designer/` for application code, manifests, scripts, tests, build artifacts, and project documentation. Other projects are off limits, even if an optional integration is mentioned.
2. Use a dedicated branch named `procedural-dungeon-designer/<milestone>`; never force-push or merge without owner approval.
3. Before writing code, read `docs/PRODUCT_SPEC.md`, `docs/TEST_PLAN.md`, and `docs/IMPLEMENTATION_STATUS.md`.
4. Build working executable functionality with realistic error handling, not mockup-only views. Keep deterministic logic and data handling separately testable.
5. Use original assets and rules; do not depend on proprietary RPG content.
6. Use synthetic or fixture data in tests. Never commit actual saved games, personal data, invoices, receipts, credentials, model files, runtime databases, or generated products.
7. Validate paths, untrusted inputs, and permissions. Make destructive or external actions opt-in; provide rollback when practical.
8. Record commands actually run, observed results and unresolved platform limitations; do not claim Windows/AI/provider tests passed without executing them.
9. Only update this project's status to MVP/verified after a genuine runnable demonstration. Maintain `docs/IMPLEMENTATION_STATUS.md` after substantive work.
10. Leave project-specific code on a reviewable, unmerged PR. Do not modify shared root workflows or utilities without separate permission.

## Implementation notes (MVP, 2026-10-23)

- Stack: Electron + React + TypeScript strict + Vite, `node:sqlite`,
  zod-validated IPC; app code in `app/`. The generator is a pure library in
  `app/shared/` — it must stay free of `Math.random()`/`Date` and of any
  Node/Electron imports so determinism holds everywhere.
- Budget edit rule: placement edits that would exceed the budget are
  BLOCKED with `BUDGET_EXCEEDED`; costs always come from the theme tables
  in `app/shared/themes.ts` (original content only).
- The sandboxed preload (`app/electron/preload/preload.ts`) must remain
  self-contained at runtime: literal channel strings, type-only shared
  imports. Guarded by `tests/backend/preload-hygiene.test.ts`.
- Export contract: `formatVersion "1.0.0"` envelope documented in
  `docs/IMPLEMENTATION_STATUS.md`; exports must stay byte-deterministic
  (stable key-sorted stringify, no timestamps in the envelope).
