# Implementation status — Offline Personal Finance Simulator

- **Overall status:** MVP (Worker B slice: React UI, UI tests, docs) — committed, not PR'd
- **Priority:** 5/17
- **Branch:** `finance-simulator/mvp`
- **Coordination:** Worker A (backend: engine, db, electron, preload) and Worker B (UI + docs) built in the same worktree/branch. A's backend files exist in the worktree but were **uncommitted** at the time of the Worker B commit (see below); B's commit contains only B-owned paths.

## Worker B deliverables (this commit)

**Renderer** (`app/renderer/`, React 19 + TypeScript, inline styles, no CSS framework):
- `src/App.tsx` — tab navigation (Debts / Income / Simulator); permanent header + footer disclaimer: "Scenarios only — not financial advice."
- `src/components/DebtsView.tsx` — debt table (name, balance, APR, minimum) + add/edit/delete with inline field validation (name required; balance ≥ 0; APR 0–100; minimum ≥ 0). Delete is confirm-gated.
- `src/components/IncomeView.tsx` — income table (name, amount, frequency) + add/edit/delete; computed **monthly income total** (monthly ×1, biweekly ×26/12, weekly ×52/12, one-time excluded with a note).
- `src/components/SimulatorView.tsx` — extra-monthly-payment input; "Run comparison" → side-by-side avalanche vs snowball cards (months to payoff or "Never — minimums don't cover interest", total paid, total interest); SVG line chart of total balance per month (both strategies, shared y-axis); monthly aggregate schedule table (first 24 months + final, scrollable); per-debt payoff breakdown table (payoff month, total paid, interest paid); budget-check banner (total minimums vs monthly income → "unaffordable" warning); CSV/JSON export buttons via `sim.report.save`.
- `src/lib/` — pure, tested helpers: `money.ts` (dollars↔cents, USD formatting), `validation.ts` (form validators), `frequency.ts` (monthly math), `chart.ts` (SVG transforms), `report.ts` (CSV layout contract mirror).
- `src/types.ts` — renderer-side copy of the preload contract, aligned to `app/shared/api-types.ts` / `app/engine/simulator.ts` / `app/shared/types.ts` after reading Worker A's implementation.

**UI tests** (`app/tests/ui/`, vitest): 48 tests, all passing — money (14), validation (14), frequency (6), chart (7), report (7).

**Docs:** `docs/IMPLEMENTATION_STATUS.md` (this file, rewritten), `docs/TEST_PLAN.md` (results table appended), `docs/PRODUCT_SPEC.md` (as-built appendix), `docs/WINDOWS_INSTALL.md` (new), `README.md` (PLANNED → MVP), `AGENTS.md` (10 owner rules kept verbatim; implementation notes appended).

## Verification evidence (Worker B)

| Check | Command / env | Result |
|---|---|---|
| UI tests (standalone) | vitest 3.2.7 in scratch dir, `--dir app/tests/ui` | **48/48 pass** (5 files) |
| UI tests (project suite) | `npm test` in `app/` (A's vitest config) | my 5 files pass; 98/100 total pass — 2 failures are in A's `tests/engine/simulator.test.ts` (see open issues) |
| Renderer typecheck | `tsc --noEmit --strict --jsx react-jsx` on `app/renderer/**` (scratch TS 5 + React 19 types) | **clean, 0 errors** |
| Renderer build | `npm run build:renderer` (vite, Worker A's config) | **succeeds** → `dist/renderer/` |
| Smoke | `npm run smoke` (A's script, xvfb) | **FAILS — in A's backend code**, not the UI (see open issues) |

## Contract deviations found in Worker A's preload (UI aligned to actual, not brief)

1. `sim.debts.delete(id)` → actual is **`sim.debts.remove(id)`**.
2. `sim.income.delete(id)` → actual is **`sim.income.remove(id)`**.
3. `sim.simulate.run({ extraPaymentCents })` → actual is **`run(extraPaymentCents: number)`** (positional).
4. `SimulationResult.monthsToPayoff` is `number | null` (not `number`); UI treats `null` as never-pays-off.
5. Per-debt result fields are `debtId`, `payoffMonth: number | null`, `interestPaidCents` (not `id`/`totalInterestCents`).
6. Monthly series points are `{ month, totalBalanceCents, totalPaidCents }` — **no per-month interest field**; schedule table shows balance + cumulative paid only.
7. `neverPaysOffDebts` contains debt **names**, not ids (per `engine/simulator.ts`); UI displays them as names.
8. Report CSV layout is per-debt per-month in cents: `strategy,debt,month,balance_cents,interest_cents,payment_cents` (authoritative in `app/electron/report.ts`); renderer `lib/report.ts` mirrors this contract for tests/docs.
9. Entry wiring: A's `app/index.html` loads `/renderer/main.tsx`; UI provides that as a thin shim re-exporting `./src/main`.

## Open issues (Worker A domain — not touched)

1. **`npm run smoke` fails:** `dist/electron/main.js` → `installSecurityGuards` calls `session.defaultSession` before app is ready → `TypeError: Session can only be received when app is ready`. Backend bug; window never boots here.
2. **2 engine test failures:** `tests/engine/simulator.test.ts` — "snowballing freed minimums / rolls paid-off minimums into the extra pool" (expected 3, got 5) and "target ordering / snowball breaks balance ties by highest APR" (expected 9 < 4). Engine semantics vs test expectations; needs A's call.
3. **`npm run typecheck` does not cover the renderer** (only `tsconfig.main.json` + `tsconfig.preload.json`). Recommend adding a renderer tsconfig to the typecheck chain.
4. **A's backend commit:** at Worker B commit time, `app/electron/**`, `app/engine/**`, `app/db/**`, `app/shared/**`, `app/tests/engine/**`, configs, and scripts existed in the worktree **uncommitted**. UI was verified against those files as read.

## Not verified (honest gaps)

- No end-to-end run of the packaged app on Windows (or anywhere) — smoke is blocked on issue #1 above.
- Renderer components were typechecked and built, but not exercised against the live preload bridge (needs the Electron shell).
- Portable Windows zip not produced (blocked on smoke + Windows hardware).

## Next actions

1. Worker A: fix `installSecurityGuards` ordering; resolve the 2 engine test failures; commit backend.
2. Worker A: add renderer typecheck to `npm run typecheck`.
3. Re-run `npm run smoke` after (1); then `npm run package:win` on Windows hardware and follow `docs/WINDOWS_INSTALL.md`.
4. Owner review via PR (do not merge without approval).

---

## Codex PR #8 fix pass — 2026-11-04 (Nyx PR fix queue, item 11)

**Ground truth (GitHub API, checked first):** 3 Codex reviews, 8 inline findings. The
summary comment's review of the current head has been stuck at "running" since
2026-10-24 — the cycle-2 head was never re-reviewed — so each finding was checked
against the current code individually:

| Round (review) | Findings | State at head `3c96d94` |
|---|---|---|
| 1 — `5633182139` on `ac72f4519` | Preload sandbox bundling (P1); chart shared month axis (P2); root index must not advertise MVP status (P1) | First two **live** — fixed in this pass. Root-index item already satisfied: the root README lists this project as "Planned", and this document + the project README state "MVP — not end-to-end verified". |
| 2 — `5638224349` on `b4c4af504` | Revert cross-project handoff edit; wire dev runner to Vite via `FS_DEV_SERVER`; zero-balance debts render as already paid | Already fixed by `8bd8544` (verified in history + current `dev.mjs` / `formatPayoffMonth`). |
| 3 — `5638520323` on `8bd85444a` | Windows-safe dev launch (no `.cmd` shims, child `error` handler); horizon banner wording | Already fixed by `3c96d94` (verified in current `dev.mjs` / `formatUnpaidWithinHorizon`). |

**Fixes in this pass:**

1. **Preload bundled for the sandbox (P1).** `app/electron/main.ts` sets
   `sandbox: true`; a sandboxed preload cannot `require` relative modules, but the
   plain-tsc build emitted `require("../shared/ipc-channels")` into
   `dist/electron/preload.js` (reproduced at the old head), so the preload died
   before exposing `window.sim`. New `app/vite.preload.config.ts` bundles the
   preload + its local imports into a single `dist/electron/preload.js` with
   `electron` external; `build:preload` uses it; `tsconfig.main.json` excludes
   `electron/preload.ts` so the main tsc build no longer emits a competing
   unbundled copy; the dev runner rebuilds the preload with the same config in
   watch mode (`vitePreloadWatchCommand`). New `app/tests/preload-bundle.test.ts`
   builds the real artifact and executes it with only a stub `electron`
   resolvable — the sandbox environment — asserting `window.sim` is exposed,
   channels are inlined, and error envelopes surface.
2. **Comparison chart shares a month axis (P2).** `balancePolyline` plotted each
   strategy by point index against its own series length, so a 3-month and a
   5-month payoff both ended at the right edge. It now plots each point's `month`
   against a shared maximum (new `chartMaxMonth`, mirroring `chartMaxBalance`);
   `BalanceChart` passes the shared max for both strategies. Downsampled points
   keep their real months, so spacing stays truthful.

**Verification (Linux VM, this pass):** `npm test` **127/127** (14 files; baseline
118/13 — +5 chart, +1 dev-commands, +3 preload-bundle), typecheck clean, lint
clean, `npm run build` clean (final `dist/electron/preload.js` contains exactly
one `require`: `"electron"`), `npm run smoke` **PASS** (SMOKE_OK). Negative
checks: exactly the 5 new chart tests fail with the chart fix stashed; all 3
preload-bundle tests fail with `build:preload` reverted to tsc.

**Note on the Worker-B sections above:** their "open issues" (smoke session
ordering, 2 engine failures, renderer missing from typecheck) predate the
cycle-1/2 commits — at this head the suite is fully green, typecheck covers the
renderer, and smoke passes. Still unverified, unchanged: packaged-app run on
Windows hardware.
