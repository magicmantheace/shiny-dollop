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
| **S3 — Other races + first contact** | **Complete + merged 2026-11-08 (PR #43).** AI civilizations (default 12 + player, setup slider 4–40 total) placed by the §6.1 fairness algorithm on real stars, expanding through the *same* core commands the player uses, under per-civilization fog of war. Survey-based first contact, a diplomacy screen with legible opinion breakdowns, and claim disputes with a tension meter (§6.3). Sim tests 28/28, bridge tests 23/23, Godot `--verify` / `--verify-s2` / `--verify-s3` all-pass; headless 300-year multi-civ campaigns complete (see `docs/TEST_PLAN.md`). |
| **S4 — Trade & diplomacy depth** | **Built + VM-verified 2026-11-08** on branch `milky-way-colonization-sim/s4-trade-diplomacy` (draft PR; not merged). Treaties (trade, gate access, non-aggression, alliance, research pact), embargoes and peace settlements with system cessions — player↔AI and AI↔AI — all evaluated with **stated reasons**; inter-civ trade routes over colony-network paths with throughput-driven income reconciled in a per-route ledger; the §6.3 translation delay; a proposal inbox; the diplomacy screen becomes an action screen (propose / break / embargo / settle / answer offers) and routes render on the map. **Save format is now v3** (v2 saves are rejected explicitly — see `docs/MUSE_HANDOFF.md`). Sim tests 42/42, bridge tests 27/27, Godot `--verify` / `--verify-s2` / `--verify-s3` / `--verify-s4` all-pass; the 300-year seed-42 run completes with expansion figures identical to S3's and two of its three disputes settled by AI peace offers. War, victory and terraforming remain S5. |
| **S5 — War & victory** | **Built + VM-verified 2026-11-28** on branch `milky-way-colonization-sim/s5-war-victory` (for Adam's review; not merged) — the final planned slice, bringing the project to **version 0.9, code-complete**. War declarations that void a pair's instruments (breaches recorded for the solemn ones), daily fleet combat with persistent hull damage and crippled-ship retreat, invasions and occupations with resistance and collapse, blockades on the §6.4 supply schedule, war exhaustion feeding peace evaluation; warp gates (§5.3) — Gate Builder ships, 4-year construction, pairing and re-pairing, 1-day transit at flat fuel with a 3-per-day pair cap, foreign transit under the Gate Access treaty, gate hops doubling trade-route throughput, bombardment and capture by occupation; terraforming (§5.4) as a 30-year project; and the §6.5 victory rules (Hegemony default, Gate Web, First Among Equals, Sandbox) with a winner recorded once and the campaign continuing. AI civilizations declare and conduct wars under fog-of-war honesty and sue for peace on exhaustion. **Save format is now v4** (v3 saves are rejected explicitly — see `docs/MUSE_HANDOFF.md`). Sim tests 56/56, bridge tests 32/32, pipeline 22/22, Godot `--verify` / `--verify-s2` / `--verify-s3` / `--verify-s4` / `--verify-s5` all-pass; the 300-year seed-42 run completes with S5 mechanics active (see `docs/TEST_PLAN.md`). |

S0–S2 merged to `main` via PR #29 (2026-11-07), S3 via PR #43
(2026-11-08), S4 merged 2026-11-12. S5 is a branch for Adam's
review — implemented ≠ shipped. What remains for 1.0 is the
owner-PC gate: a real play session on Adam's PC (open since S2).
FPS on Adam's RTX 3060 is
an owner-PC gate — no frame-rate claims are made from VM runs (see
`docs/TEST_PLAN.md`).

## Layout

- `pipeline/` — Rust CLI that turns the source catalogs into the game
  star table (`data/stars.bin` + `data/manifest.json`). The catalogs are
  never hand-edited; re-running the pipeline regenerates the table.
- `sim/` — the Rust simulation core (S1, generalized in S3,
  diplomacy in S4, war & victory in S5): deterministic, headless,
  step-driven (1 tick = 1 game day, monthly settlement). Galaxy
  state is sparse over the S0 table; multiple civilizations (the
  player plus seeded AI races with personality vectors), ship/fuel
  mechanics, per-civilization fog of war, first contact and claim
  disputes, treaties / embargoes / peace settlements / trade
  routes with evaluated, reason-giving deal logic, fleet combat,
  war, occupation and blockade, warp gates, terraforming, victory
  evaluation, canonical save/load
  (format v4), a scripted policy, and the `sim-cli` demo binary
  (`--ai N` runs a multi-civ campaign). No wall clock and no
  external RNG anywhere in the crate — all randomness derives
  from the campaign seed.
- `bridge/` — the S2 process bridge (crate `mwcs-bridge`, binary
  `sim-bridge`): wraps the core for the frontend — envelope save
  files with a trusted saved-at timestamp, a JSON file-based command
  protocol (new / load / exec / view / inspect / list_saves), and the
  full-catch-up load (advance by elapsed whole days, report what
  happened). S3: `new` accepts an AI-race count, exec gains a
  `contest` command, and the view is **player-perspective** — other
  civilizations appear only after first contact, with opinion
  breakdowns and open disputes; foreign activity is visible only
  where the player has surveyed. S4: exec gains the diplomacy
  commands (treaties, embargoes, peace, proposal answers, trade
  routes) whose results carry the negotiated outcome as a
  `detail`, and the view adds treaty lists, the player's route
  ledgers and the proposal inbox. S5: exec gains the war and
  gate commands (`declare_war`, `invade`, `build_gate`,
  `pair_gates`, `gate_transit`, `start_terraform`), `new` accepts
  a victory rule and end year, and the view adds per-ship hull
  state, colony occupation/terraforming, the roster's war blocks
  with both sides' exhaustion, the visible gates, and the
  victory block. It is the one wall-clock-aware
  component; the core stays wall-clock-free. Cross-compiles to
  Windows (`x86_64-pc-windows-gnu`).
- `viewer/` — Godot 4 project: the S2 game frontend (the S0 star-map
  viewer grown in place). Renders the star table in 3D with
  spectral-class colours, orbit/fly camera, go-to-Sol, click picking;
  adds the main menu (with the S3 AI-race count), HUD, system and
  ships panels with orders (including **Contest Claim** on a foreign
  claim), state markers (surveyed / claimed / colonized), a ship
  range highlight, the event log, a **diplomacy screen** (S3:
  contacted civilizations, opinion breakdowns, open disputes; S4:
  treaties, embargoes, trade routes with earnings, the proposal
  inbox with senders' stated reasons, and action buttons to
  propose / break / settle / answer — plus trade routes drawn on
  the map; S5: Declare War / Sue for Peace actions, AT WAR lines
  with losses and exhaustion, hull percentages in the ships
  panel, gate / occupation / terraforming lines and order
  buttons in the system panel, a victory standing in the HUD,
  and a victory-rule picker on the menu), the catch-up
  review modal (S3: with galaxy-wide AI development deltas), and
  headless `--verify` (S0), `--verify-s2` (full-loop), `--verify-s3`
  (AI-race), `--verify-s4` (diplomacy) and `--verify-s5` (war &
  victory) modes.
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

# 5. Verify the S3 AI-race and S4 diplomacy surfaces the same way
godot --headless --path viewer -- --verify-s3 \
  --bridge=$PWD/bridge/target/release/sim-bridge
godot --headless --path viewer -- --verify-s4 \
  --bridge=$PWD/bridge/target/release/sim-bridge

# 6. Verify the S5 war & victory surface the same way
godot --headless --path viewer -- --verify-s5 \
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
