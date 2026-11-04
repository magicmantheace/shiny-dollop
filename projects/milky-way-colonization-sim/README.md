# Milky Way Colonization Simulator

A space management simulator played on the **real** Milky Way: the player
runs a civilization colonizing real star systems while AI races do the
same, on a full-3D map built from real catalogs (HYG v4.4 + the NASA
Exoplanet Archive), with travel bounded by ship fuel range and buildable
warp gates. The complete game design — every founding decision and §11
ruling is Adam's (2026-11-04) — lives in [`docs/DESIGN.md`](docs/DESIGN.md).

**Stack (ruled):** Rust simulation core + Godot 4 frontend.

## Status

| Slice | State |
|---|---|
| **S0 — Data pipeline proof** | **Complete 2026-11-04.** 113,393-star table built from live catalogs; cargo tests 22/22; Godot `--verify` all-pass (see `docs/TEST_PLAN.md`). The ~1M-star AT-HYG option was measured (52 MB table, 739 ms load). |
| **S1 — Sim core (headless)** | **Complete 2026-11-04** (awaiting Nyx firsthand verification). Deterministic Rust core in `sim/`: one civilization surveys → claims → colonizes from Sol under fuel-range rules, monthly economy settlement, canonical save/load. Sim tests 19/19; a scripted 25-year campaign reaches 99 surveyed / 13 colonized systems; 100 game-years tick in ~0.8 s on this VM. Offline progression is **ruled by Adam (2026-11-04): full catch-up** — the galaxy lives while the game is closed; S2 implements it in save/load (see `docs/MUSE_HANDOFF.md`). |
| S2 — Playable colonizer | Not started |
| S3–S5 — AI races, trade/diplomacy, war/victory | Not started |

Implemented ≠ shipped: nothing here is merged; this branch is a draft for
Adam's review. FPS on Adam's RTX 3060 is an owner-PC gate — no frame-rate
claims are made from VM runs (see `docs/TEST_PLAN.md`).

## Layout

- `pipeline/` — Rust CLI that turns the source catalogs into the game
  star table (`data/stars.bin` + `data/manifest.json`). The catalogs are
  never hand-edited; re-running the pipeline regenerates the table.
- `sim/` — the Rust simulation core (S1): deterministic, headless,
  step-driven (1 tick = 1 game day, monthly settlement). Galaxy state
  is sparse over the S0 table; one civilization, ship/fuel mechanics,
  canonical save/load, a scripted policy, and the `sim-cli` demo
  binary. No wall clock and no external RNG anywhere in the crate —
  all randomness derives from the campaign seed.
- `viewer/` — Godot 4 project: renders the star table in 3D with
  spectral-class colours, orbit/fly camera, go-to-Sol, click picking
  with an info panel (name, spectral class, distance from Sol, real
  planets), and a headless `--verify` mode.
- `data/` — build outputs. `stars.bin` is a regenerable artifact
  (git-ignored); the manifest and `SOURCES.md` are committed.
- `docs/` — `DESIGN.md` (the spec), `TEST_PLAN.md`, `MUSE_HANDOFF.md`.

## Quick start

```sh
# 1. Build the star table (downloads catalogs into pipeline/cache/ on
#    first run; --offline reuses the cache)
cd pipeline && cargo run --release -- build --out ../data
cd ..

# 2. Run the tests
cd pipeline && cargo test
cd ../sim && cargo test

# 2b. Run a headless scripted campaign (25 game-years from Sol)
cd sim && cargo run --release --bin sim-cli -- --years 25

# 3. Verify the viewer headlessly (prints VERIFY_PASS lines; the
#    viewer finds ../data/stars.bin relative to the project by default,
#    or pass --data=<absolute path>)
godot --headless --path viewer -- --verify
```

## Data sources & license

HYG Database v4.4 © astronexus, **CC BY-SA 4.0** — the derived star table
carries the same license and credits HYG (see `data/SOURCES.md`).
Exoplanet data: NASA Exoplanet Archive (public domain-style courtesy
credit in `data/SOURCES.md`). Fields the pipeline *derives* (temperature
and mass for HYG rows) are flagged `derived` in the table format and are
never presented as measured values; stars inserted from the exoplanet
archive are flagged with their source.
