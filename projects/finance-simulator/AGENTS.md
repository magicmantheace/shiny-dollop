# Offline Personal Finance Simulator — project agent instructions

**ACTIVE PROJECT FOLDER WHEN ASSIGNED:** `projects/finance-simulator/`

Root `AGENTS.md` overrides these instructions on conflict.

1. Work only inside `projects/finance-simulator/` for application code, manifests, scripts, tests, build artifacts, and project documentation. Other projects are off limits, even if an optional integration is mentioned.
2. Use a dedicated branch named `finance-simulator/<milestone>`; never force-push or merge without owner approval.
3. Before writing code, read `docs/PRODUCT_SPEC.md`, `docs/TEST_PLAN.md`, and `docs/IMPLEMENTATION_STATUS.md`.
4. Build working executable functionality with realistic error handling, not mockup-only views. Keep deterministic logic and data handling separately testable.
5. No bank-account access by default; use synthetic fixtures only; calculations are scenarios, not financial advice.
6. Use synthetic or fixture data in tests. Never commit actual saved games, personal data, invoices, receipts, credentials, model files, runtime databases, or generated products.
7. Validate paths, untrusted inputs, and permissions. Make destructive or external actions opt-in; provide rollback when practical.
8. Record commands actually run, observed results and unresolved platform limitations; do not claim Windows/AI/provider tests passed without executing them.
9. Only update this project's status to MVP/verified after a genuine runnable demonstration. Maintain `docs/IMPLEMENTATION_STATUS.md` after substantive work.
10. Leave project-specific code on a reviewable, unmerged PR. Do not modify shared root workflows or utilities without separate permission.

---

## Implementation notes — Worker B (UI + docs), 2026-10-23

File ownership during the split build: Worker B owns `app/renderer/**`, `app/tests/ui/**`,
`projects/finance-simulator/docs/**`, `README.md`, and these AGENTS.md notes only.
Worker A owns `app/package.json`, configs, `app/electron/**`, `app/engine/**`,
`app/db/**`, `app/shared/**`, `app/scripts/**`, `app/index.html`, `app/tests/engine/**`.

- The 10 rules above are kept verbatim.
- UI codes against the preload contract **as read** in `app/electron/preload.ts` /
  `app/shared/api-types.ts` — not against the task brief. Deviations found (remove vs
  delete, positional `run(extraPaymentCents)`, nullable payoff fields, name-based
  `neverPaysOffDebts`, no per-month interest in MonthlyPoint) are documented in
  `docs/IMPLEMENTATION_STATUS.md` and `docs/PRODUCT_SPEC.md` Appendix A.
- `app/index.html` (Worker A) loads `/renderer/main.tsx`; the UI provides that as a
  thin shim importing `./src/main`. Do not add a second renderer entry.
- Renderer is pure React + inline styles (no CSS framework) so it builds with A's
  existing vite config and dependencies.
- Known gaps referred to Worker A: smoke boot failure (`installSecurityGuards`
  ordering), 2 engine test failures, renderer missing from `npm run typecheck`,
  no electron-builder `build` config for the portable target.
