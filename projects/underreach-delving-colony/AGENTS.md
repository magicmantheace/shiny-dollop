# Project instructions — underreach-delving-colony

These rules apply inside `projects/underreach-delving-colony/`. The
repository root `AGENTS.md` wins on any conflict.

## Scope

1. Work only inside this folder. Do not modify other projects or the
   repository root beyond registering this project in the root README
   index.
2. **This project is not Crawl.** `projects/crawl/` (The Underreach) is a
   separate, owner-parked project. Do not read from, copy from, or
   modify it.
3. **The design record is the spec.** `docs/MUSE_HANDOFF.md` records
   the owner's decisions (2026-11-09/10) — they are fixed. If
   implementation reality fights the spec, stop and record the conflict
   in the handoff; do not silently redesign.
4. Build in slices (S1 → …). A later slice starts only on the owner's
   go-ahead at the previous slice's report.

## Architecture

5. **Core/frontend split.** The simulation core is Rust,
   engine-agnostic and headless-testable; a Godot 4 frontend is planned
   as a replaceable presentation layer that reads core state and sends
   commands. Sim rules never live in the frontend.
6. **Determinism.** The sim is a pure function of its initial state and
   command sequence: same inputs → identical state hash. Any randomness
   enters through a seeded RNG recorded in the save. Saves are canonical
   JSON plus a SHA-256 state hash; a load must reproduce the hash.
7. **The Deep Ledger is append-only** in-fiction and in code: entries
   are never rewritten or deleted, only added.

## Verification honesty

8. No FPS, frame-time, or performance claims without owner-hardware
   measurement. VM/headless numbers are logic and load measurements
   only, labelled as such.
9. After substantive changes: run `cargo test` in `sim/`, run the
   `scenario` binary, and update this project's README,
   `docs/MUSE_HANDOFF.md`, and `docs/TEST_PLAN.md` with real results,
   separating verified / unverified / planned work.
10. Use project-prefixed branches, commits, and PR titles
    (`underreach-delving-colony: ...`). Do not auto-merge or
    force-push.
