# Crawl Live Spectator Desktop — project agent instructions

**ACTIVE PROJECT FOLDER WHEN ASSIGNED:** `projects/crawl-spectator-desktop/`

Root `AGENTS.md` overrides these instructions on conflict.

1. Work only inside `projects/crawl-spectator-desktop/` for application code, manifests, scripts, tests, build artifacts, and project documentation. Other projects are off limits, even if an optional integration is mentioned.
2. Use a dedicated branch named `crawl-spectator-desktop/<milestone>`; never force-push or merge without owner approval.
3. Before writing code, read `docs/PRODUCT_SPEC.md`, `docs/TEST_PLAN.md`, and `docs/IMPLEMENTATION_STATUS.md`.
4. Build working executable functionality with realistic error handling, not mockup-only views. Keep deterministic logic and data handling separately testable.
5. Strictly read-only: never alter canonical Crawl/Underreach data. Do not change `projects/crawl/` during this project.
6. Use synthetic or fixture data in tests. Never commit actual saved games, personal data, invoices, receipts, credentials, model files, runtime databases, or generated products.
7. Validate paths, untrusted inputs, and permissions. Make destructive or external actions opt-in; provide rollback when practical.
8. Record commands actually run, observed results and unresolved platform limitations; do not claim Windows/AI/provider tests passed without executing them.
9. Only update this project's status to MVP/verified after a genuine runnable demonstration. Maintain `docs/IMPLEMENTATION_STATUS.md` after substantive work.
10. Leave project-specific code on a reviewable, unmerged PR. Do not modify shared root workflows or utilities without separate permission.
