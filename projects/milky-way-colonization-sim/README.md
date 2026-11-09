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
| **S1 — Sim core (headless)** | **Complete 2026-11-04.** Deterministic Rust core in `sim/`: one civilization surveys → claims → colonizes from Sol under fuel-range rules, monthly economy settlement, canonical save/load. Sim tests 19/19; a scripted 25-year campaign reaches 99 surveyed / 13 colonized systems; 100 game-years tick in ~0.8 s on this VM. Offline progression is **ruled by Adam (2026-11-04): full catch-up** — the galaxy lives while the game is closed; S2 implements it in save/load (see `docs/MUSE_HANDOFF.md`). |
| **S2 — Playable colonizer** | **Built + VM-verified 2026-11-06; owner-PC play session pending** (the slice's own verification gate per DESIGN §10 — Adam waived it as a *precondition* for S3 on 2026-11-07; the gate itself remains unmet). Godot game frontend over the core via the `sim-bridge` process bridge: main menu, HUD, system/ships panels, the survey → claim → colonize loop, real-time-with-pause clock, save/load with **full catch-up + a "while you were away" review modal**. Bridge tests 18/18; Godot `--verify` and `--verify-s2` all-pass (see `docs/TEST_PLAN.md`). A Windows test package (`sim-bridge.exe` + project) was assembled for Adam's PC; the .exe is build-verified only — never executed on Windows yet. |
| **S3 — Other races + first contact** | **Built + VM-verified 2026-11-08** on branch `milky-way-colonization-sim/s3-ai-races` (draft PR; not merged). AI civilizations (default 12 + player, setup slider 4–40 total) placed by the §6.1 fairness algorithm on real stars, expanding through the *same* core commands the player uses, under per-civilization fog of war. Survey-based first contact, a diplomacy screen with legible opinion breakdowns, and claim disputes with a tension meter (§6.3). Sim tests 28/28, bridge tests 23/23, Godot `--verify` / `--verify-s2` / `--verify-s3` all-pass; headless 300-year multi-civ campaigns complete (see `docs/TEST_PLAN.md`). Treaties, war and victory conditions are S4/S5 per DESIGN §10 — disputes in S3 are records with opinion effects, not yet resolvable. |
| S4–S5 — Trade/diplomacy depth, war/victory | Not started |

S0–S2 merged to `main` via PR #29 (2026-11-07). S3 is a draft branch
for Adam's review — implemented ≠ shipped. FPS on Adam's RTX 3060 is
an owner-PC gate — no frame-rate claims are made from VM runs (see
`docs/TEST_PLAN.md`).

## Layout

- `pipeline/` — Rust CLI that turns the source catalogs into the game
  star table (`data/stars.bin` + `data/manifest.json`). The catalogs are
  never hand-edited; re-running the pipeline regenerates the table.
- `sim/` — the Rust simulation core (S1, generalized in S3):
  deterministic, headless, step-driven (1 tick = 1 game day, monthly
  settlement). Galaxy state is sparse over the S0 table; multiple
  civilizations (the player plus seeded AI races with personality
  vectors), ship/fuel mechanics, per-civilization fog of war, first
  contact and claim disputes, canonical save/load (format v2), a
  scripted policy, and the `sim-cli` demo binary (`--ai N` runs a
  multi-civ campaign). No wall clock and no external RNG anywhere in
  the crate — all randomness derives from the campaign seed.
- `bridge/` — the S2 process bridge (crate `mwcs-bridge`, binary
  `sim-bridge`): wraps the core for the frontend — envelope save
  files with a trusted saved-at timestamp, a JSON file-based command
  protocol (new / load / exec / view / inspect / list_saves), and the
  full-catch-up load (advance by elapsed whole days, report what
  happened). S3: `new` accepts an AI-race count, exec gains a
  `contest` command, and the view is **player-perspective** — other
  civilizations appear only after first contact, with opinion
  breakdowns and open disputes; foreign activity is visible only
  where the player has surveyed. It is the one wall-clock-aware
  component; the core stays wall-clock-free. Cross-compiles to
  Windows (`x86_64-pc-windows-gnu`).
- `viewer/` — Godot 4 project: the S2 game frontend (the S0 star-map
  viewer grown in place). Renders the star table in 3D with
  spectral-class colours, orbit/fly camera, go-to-Sol, click picking;
  adds the main menu (with the S3 AI-race count), HUD, system and
  ships panels with orders (including **Contest Claim** on a foreign
  claim), state markers (surveyed / claimed / colonized), a ship
  range highlight, the event log, a **diplomacy screen** (contacted
  civilizations, opinion breakdowns, open disputes), the catch-up
  review modal (S3: with galaxy-wide AI development deltas), and
  headless `--verify` (S0), `--verify-s2` (full-loop) and
  `--verify-s3` (AI-race) modes.
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
cd ../bridge && cargo test

# 2b. Run a headless scripted campaign (25 game-years from Sol)
cd sim && cargo run --release --bin sim-cli -- --years 25

# 3. Verify the viewer headlessly (prints VERIFY_PASS lines; the
#    viewer finds ../data/stars.bin relative to the project by default,
#    or pass --data=<absolute path>)
godot --headless --path viewer -- --verify

# 4. Verify the S2 game loop headlessly (needs the bridge built:
#    cd bridge && cargo build --release)
godot --headless --path viewer -- --verify-s2 \
  --bridge=$PWD/bridge/target/release/sim-bridge
```

## Data sources & license

HYG Database v4.4 © astronexus, **CC BY-SA 4.0** — the derived star table
carries the same license and credits HYG (see `data/SOURCES.md`).
Exoplanet data: NASA Exoplanet Archive (public domain-style courtesy
credit in `data/SOURCES.md`). Fields the pipeline *derives* (temperature
and mass for HYG rows) are flagged `derived` in the table format and are
never presented as measured values; stars inserted from the exoplanet
archive are flagged with their source.
