# Project instructions — milky-way-colonization-sim

These rules apply inside `projects/milky-way-colonization-sim/`. The
repository root `AGENTS.md` wins on any conflict.

## Scope

1. Work only inside this folder. Do not modify other projects or the
   repository root beyond registering this project in the root README
   index.
2. **The design document is the spec.** `docs/DESIGN.md` records Adam's
   five founding decisions and seven §11 rulings — they are fixed. If
   implementation reality fights the spec, stop and record the conflict
   in `docs/MUSE_HANDOFF.md`; do not silently redesign.
3. Build in the queue's slices (S0 → S5). A later slice starts only on
   Adam's go-ahead at the previous slice's report.

## Data integrity — hard rules

4. **Catalog data is never hand-edited.** HYG and Exoplanet Archive
   inputs live in `pipeline/cache/` (git-ignored) and are treated as
   read-only. Every game table is a pipeline output: to change the
   table, change the pipeline and re-run it.
5. **Derived values stay flagged.** Temperature/mass the pipeline
   computes (spectral lookup, mass–luminosity relation) carry the
   `derived` flag bits in the binary format forever. Never present a
   derived value as measured, in UI, docs, or tests.
6. **Generated stars are never labelled as real data.** S0's table is
   100% catalog rows (HYG + archive-inserted hosts, the latter flagged
   `source: exoplanet-archive`). The statistical deep-galaxy fill is a
   later slice and must carry the `generated` flag (already reserved in
   the format).
7. Counts in docs and reports must reconcile with the pipeline's own
   stats output for the same run — quote the run, not memory.

## Architecture

8. **Core/frontend split (ruled).** The simulation core is Rust,
   engine-agnostic and headless-testable; the Godot 4 project is a
   replaceable frontend that reads core-produced data and (from S2)
   sends commands. The S0 viewer reads `data/stars.bin` directly — the
   binary format in `pipeline/src/table.rs` is the contract; the
   GDScript reader must mirror it exactly, and a format change updates
   both sides plus the tests in the same commit.
9. Determinism where the design demands it: pipeline outputs are a pure
   function of the cached inputs (same cache → byte-identical table;
   the manifest records the input hashes).

## Verification honesty

10. **No FPS or frame-time claims without owner-hardware measurement.**
    VM/Godot-headless numbers are load-time and memory measurements
    only, labelled as such. Frame budgets (§7.3 of the design) are
    measured on Adam's RTX 3060 PC in S2.
11. After substantive changes: run `cargo test` in `pipeline/` and the
    viewer headless `--verify`, and update this project's README,
    `docs/MUSE_HANDOFF.md`, and `docs/TEST_PLAN.md` with real results,
    separating verified / unverified / planned work.
12. Use project-prefixed branches, commits, and PR titles
    (`milky-way-colonization-sim: ...`). Do not auto-merge or
    force-push.
