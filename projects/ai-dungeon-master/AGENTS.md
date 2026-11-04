# AI Dungeon Master — project agent instructions

**ACTIVE PROJECT FOLDER WHEN ASSIGNED:** `projects/ai-dungeon-master/`

Root `AGENTS.md` overrides these instructions on conflict.

1. Work only inside `projects/ai-dungeon-master/` for application code, manifests, scripts, tests, build artifacts, and project documentation. Other projects are off limits, even if an optional integration is mentioned.
2. Use a dedicated branch named `ai-dungeon-master/<milestone>`; never force-push or merge without owner approval.
3. Before writing code, read `docs/PRODUCT_SPEC.md`, `docs/TEST_PLAN.md`, and `docs/IMPLEMENTATION_STATUS.md`.
4. Build working executable functionality with realistic error handling, not mockup-only views. Keep deterministic logic and data handling separately testable.
5. No unlicensed proprietary rulebooks; AI flavor is never the authoritative rules engine.
6. Use synthetic or fixture data in tests. Never commit actual saved games, personal data, invoices, receipts, credentials, model files, runtime databases, or generated products.
7. Validate paths, untrusted inputs, and permissions. Make destructive or external actions opt-in; provide rollback when practical.
8. Record commands actually run, observed results and unresolved platform limitations; do not claim Windows/AI/provider tests passed without executing them.
9. Only update this project's status to MVP/verified after a genuine runnable demonstration. Maintain `docs/IMPLEMENTATION_STATUS.md` after substantive work.
10. Leave project-specific code on a reviewable, unmerged PR. Do not modify shared root workflows or utilities without separate permission.

## Implementation notes (MVP, 2026-10-23)

- Stack: Electron + React + TypeScript strict + Vite, `node:sqlite`,
  zod-validated IPC; app code in `app/`. The dice engine and house
  ruleset in `app/shared/` are pure and deterministic — no
  `Math.random()`/`Date` in roll paths; the campaign row persists the
  PRNG stream state and every roll logs its full breakdown for replay.
- The session log is append-only: no update/delete path exists for log
  rows. The single exception is `attachNarration` in the store, which
  may only fill an entry's narration fields. Narrators (mock / loopback
  HTTP) receive a read-only view and can never mutate rules state;
  endpoint failure falls back to mock text.
- The sandboxed preload (`app/electron/preload/preload.ts`) must remain
  self-contained at runtime: literal channel strings, type-only shared
  imports. Guarded by `tests/backend/preload-hygiene.test.ts`.
- Export contract: `ai-dungeon-master/campaign` formatVersion "1.0.0"
  envelope, byte-deterministic (stable key-sorted stringify, no
  timestamps). Consumed contracts: `worldbuilding-manager.project` v1
  and `procedural-dungeon-designer/map` v1; unknown majors rejected
  with `IMPORT_VERSION_UNSUPPORTED`.
- Rules content is the original house ruleset in `app/shared/ruleset.ts`
  only. Do not add published-rulebook material.
