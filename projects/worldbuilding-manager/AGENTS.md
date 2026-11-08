# Novel and Worldbuilding Manager — project agent instructions

**ACTIVE PROJECT FOLDER WHEN ASSIGNED:** `projects/worldbuilding-manager/`

Root `AGENTS.md` overrides these instructions on conflict.

1. Work only inside `projects/worldbuilding-manager/` for application code, manifests, scripts, tests, build artifacts, and project documentation. Other projects are off limits, even if an optional integration is mentioned.
2. Use a dedicated branch named `worldbuilding-manager/<milestone>`; never force-push or merge without owner approval.
3. Before writing code, read `docs/PRODUCT_SPEC.md`, `docs/TEST_PLAN.md`, and `docs/IMPLEMENTATION_STATUS.md`.
4. Build working executable functionality with realistic error handling, not mockup-only views. Keep deterministic logic and data handling separately testable.
5. Author retains control and copyright; no external sync by default.
6. Use synthetic or fixture data in tests. Never commit actual saved games, personal data, invoices, receipts, credentials, model files, runtime databases, or generated products.
7. Validate paths, untrusted inputs, and permissions. Make destructive or external actions opt-in; provide rollback when practical.
8. Record commands actually run, observed results and unresolved platform limitations; do not claim Windows/AI/provider tests passed without executing them.
9. Only update this project's status to MVP/verified after a genuine runnable demonstration. Maintain `docs/IMPLEMENTATION_STATUS.md` after substantive work.
10. Leave project-specific code on a reviewable, unmerged PR. Do not modify shared root workflows or utilities without separate permission.

## Implementation notes (appended by the MVP build, 2026-10-23)

- Stack: Electron 45 + React 19 + TypeScript strict + Vite, `node:sqlite` storage, zod-validated IPC, matching the sibling projects' proven pattern. App code lives in `app/`; the engine (`app/db/world.ts`) has no Electron imports and is tested headlessly.
- All five entity types share one `entities` table with type-specific fields (role/born/died for characters, story date/order key for events). Links are a separate table with `ON DELETE CASCADE` — dangling links are impossible by construction and covered by tests.
- Continuity warnings are exactly the two deterministic rules documented in the README (`EVENT_AFTER_DEATH`, `EVENT_BEFORE_BIRTH`). Do not add speculative warning types without tests for both the firing and non-firing case.
- The preload must stay runtime self-contained (type-only imports from `shared/`, literal channel strings): Electron's sandboxed preload loader cannot require sibling modules.
- Revisions are append-only snapshots written on every create/update; there is intentionally no revision-edit or rollback UI in the MVP.
