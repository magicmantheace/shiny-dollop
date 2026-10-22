# Muse agent instructions — Universal PC Game Launcher

**This is the ACTIVE project.** Follow [global AGENTS.md](../../AGENTS.md). Your scope is exclusively `projects/universal-game-launcher/`.

## Immediate directive

**Build working Windows software.** Do not stop at a product plan, HTML design, UI screenshots, placeholder buttons or unsupported "fully working" claims. Read `docs/MUSE_HANDOFF.md` and execute `docs/IMPLEMENTATION_PLAN.md` starting from the first unfinished milestone.

## Critical rules

1. Keep all project files under this directory. Never alter `projects/github-development-command-center/` — it is parked.
2. Prioritize end-to-end utility: manually register an actual game and launch it before pursuing automation or fancy artwork.
3. No fake library data presented as real, except an explicit demo/test mode.
4. Design each store integration as an adapter with honest detection, capabilities and "unsupported" states; never assume direct-launch protocols without verifying them.
5. Never circumvent DRM, ownership checks, anti-cheat, storefront launchers, access controls or licensing.
6. No credentials or privileged game account logins. Prefer local read-only discovery from manifests/registry when available.
7. Never execute arbitrary paths that arrived from untrusted manifests without validation and direct user action. Do not invoke shell commands from strings.
8. Do not move, delete or modify installed games, storefront manifests, registry entries, drivers or game saves.
9. Honor least privilege: no elevation/admin requirement for normal launching or scanning; only scan selected/known locations; no background network calls without purpose.
10. Avoid unnecessary resource use; do not poll process lists at excessive rates or keep high CPU/GPU usage while games are active.
11. Add automated tests and run them. Distinguish executed tests from unverified claims and Windows-only manual validation.
12. Update the project README/handoff with status and outstanding work after each milestone. Commit incremental working changes in project-prefixed branches.

## Definition of delivered

A clean Windows 11 machine with installed vendor clients and/or local games can install this app, launch it, import at least one real game from each supported source if one is present (or receive an accurate unsupported/unavailable reason), manually add a game, launch it via the validated method, favorite/filter it, observe a tracked play session, close/reopen without data loss, and uninstall cleanly. Tests must cover safe launching, parsing, persistence and edge cases.

**Scope boundary:** No integration with Synveil, AthenZ, Developmental AI, or other repositories. Do not build GitHub features for this project.
