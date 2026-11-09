# TEST_PLAN — Milky Way Colonization Simulator

What was actually run, with results. Last updated 2026-11-08 (S3;
PR #45 reconciliation re-run the same day).
Nothing in this file is aspirational: every claim below was executed
on this VM during the S0/S1/S2/S3 builds.

## S3 — AI races, first contact, disputes

All runs below were executed on this VM on 2026-11-08 against the
final S3 code (branch `milky-way-colonization-sim/s3-ai-races`).

### Sim tests (Rust, `sim/`)

```
cd sim && cargo test          # debug profile
```

Result: **28 passed, 0 failed** (8 unit + 13 S1 integration +
7 S3 integration in `sim/tests/s3.rs`), exit 0. The S1 suites pass
unmodified — solo behavior is preserved by construction.

- **Placement:** same seed → identical placement; 12 AI civs placed
  with pairwise spacing ≥ 200 ly on the synthetic galaxy; every civ
  provisioned identically (15,000 credits, homeworld colony,
  surveyor + colony ship); personalities inside 0..=1.
- **Zero-AI ≡ solo:** `new_game(0 AI)` state hash equals the S1
  `new_default` hash at day 0 **and** after 365 scripted-policy days.
- **Per-civ fog:** an AI civ has surveyed only its own home at
  day 0; the player likewise.
- **AI expansion + catch-up equivalence (headline):** 12 AI civs on
  the synthetic galaxy — advance 1,825 days → save → load → state
  hash **equal**; advance to 3,650 days → hash **equal** to the
  uninterrupted run. After 10 years the galaxy holds more colonies
  than the 13 homeworlds, and every AI colony sits in a system its
  owner surveyed and claimed (the AI plays by the rules).
- **First contact:** surveying a foreign home system records the
  contact pair and emits exactly one `FirstContact` event.
- **Disputes:** contest error order pinned (unsurveyed → not
  foreign-held → duplicate); a contested claim opens a dispute,
  drops the holder's opinion of the challenger below zero via the
  dispute component, and tension grows over 365 days.
- **Save v2:** a hand-built v1 byte string is rejected with
  "unsupported save version 1".

### Bridge tests (Rust, `bridge/`)

```
cd bridge && cargo test       # debug profile
```

Result: **23 passed, 0 failed** (7 unit + 11 S2 integration +
5 S3 integration in `bridge/tests/s3.rs`), exit 0. (As first built
the suite was 20; the PR #45 reconciliation merged into this branch
added PR #45's two S2 tests — overwrite refusal and fractional
catch-up — plus one combined test below, and the whole suite was
re-run green on the merged tree, as were the Godot verifies.)

- **Setup without leaks:** `new` with `ai_races: 3` — the setup
  block names 3 AI civs and contains no home-system field; the view
  roster is the player alone; the galaxy block counts 4 civs and 4
  colonies; the player sees exactly 2 ships and 1 system.
- **Solo default unchanged:** `new` without `ai_races` returns a
  null setup block and the S2 solo view.
- **Catch-up equivalence with AI active (headline):** a 4-civ
  campaign advanced 730 days by exec vs the same save loaded with
  a 730-day elapsed override — **identical state hash**; both paths
  advanced a further ~7.3 years remain identical, with galaxy
  colonies beyond the 4 homeworlds (AI expanded during catch-up).
- **Diplomacy view + event filter:** on a crafted campaign with a
  recorded contact and an open dispute, the roster gains the met
  civ with a negative dispute opinion component and live tension;
  `first_contact` / `claim_contested` events reach the player with
  civ names; the same window's foreign `ship_built` /
  `ship_refuelled` / `specialization_set` events do not.
- **Overwrite guard × AI setup (reconciliation pin):** `new` with
  `ai_races` against an occupied save path is refused and the
  4-civ campaign is intact afterwards; `new` with
  `"overwrite": true` replaces it with the fresh game. The PR #45
  guard sits ahead of campaign creation in `op_new`, so it covers
  solo and multi-civ campaigns alike.

### Godot headless verifies (viewer, Godot 4.7.2, real table)

```
godot --headless --path viewer -- --verify
godot --headless --path viewer -- --verify-s2 --bridge=<release sim-bridge>
godot --headless --path viewer -- --verify-s3 --bridge=<release sim-bridge>
```

Results: `--verify` all-pass (S0 regression); `--verify-s2`
all-pass (S2 regression); **`--verify-s3` all-pass**:
`setup ai=12 homes_hidden=true` · `perspective roster=1
galaxy_civs=13 ships=2 surveyed=1` · `advance day=365
galaxy_surveyed=53 player_surveyed=1` · `contest
refused_cleanly=true` · `catchup galaxy_fields=true`.

### Headless long-run campaigns (release `sim-cli`, real table)

DESIGN §10's S3 verification asks for headless multi-civ campaigns
(300 years, no crashes, no civ breaking the fuel rules — fuel-rule
violations are impossible by construction: the AI dispatches
through the same core commands that refuse them, and the S3 tests
pin surveyed+claimed ownership of every AI colony).

- Seed 42, 12 AI + player, 300 years: completes, no crashes;
  589 colonized / 2,049 claimed / 2,447 surveyed galaxy-wide;
  player 64 colonies; contacts 1 (first contact at year 215);
  disputes 3 open by year 300.
- Seed 42, 39 AI + player, 300 years (~14 min wall on this VM):
  1,104 colonized / 3,188 claimed / 3,895 surveyed galaxy-wide;
  player 64 colonies; contacts 1 (first contact at year 215);
  disputes 3 open by year 300.
- Determinism: repeated identical 2-year runs produce byte-identical
  yearly output and final state hashes.
- (Figures corrected 2026-11-08: an earlier draft of this section
  cited numbers read from in-flight runs; the figures above are
  from the completed run logs.)

### Not run / unverified for S3

- Interactive play: the S2 owner-PC play session (DESIGN §10 gate)
  was **waived by Adam on 2026-11-07 as a precondition for starting
  S3** — it has still not happened; play feel and Adam-facing
  contact/diplomacy play are unverified.
- Windowed Godot interaction with the diplomacy overlay / contest
  button (headless verify covers the bridge contract and script
  compilation, not clicking).
- Overnight real-clock catch-up (the elapsed-override path is
  test-proven; a real overnight wall-clock run is not).
- Windows export build and `sim-bridge.exe` execution on Windows.
- FPS on Adam's RTX 3060 — owner-hardware measurement only, per
  project rules.

## S2 — bridge + Godot game frontend

All runs below were executed on this VM on 2026-11-06 against the
final committed code, and re-run firsthand by the coordinator after
each pass (exit codes recorded).

### Bridge tests (Rust, `bridge/`)

```
cd bridge
cargo test --release
```

Result: **16 passed, 0 failed** (7 unit + 9 integration in
`bridge/tests/s2.rs`), exit 0.

- Unit: hand-rolled JSON round trip / nesting / string escapes /
  malformed-input rejection; envelope write→read round trip (payload
  byte-identical, header fields preserved), bad magic and truncated
  files rejected; atomic replace on rewrite.
- Integration (real sim core, synthetic galaxy), headline first:
  - **Catch-up equivalence:** campaign A advanced 400 days; its save
    reloaded with a +400-day clock offset produces a core state hash
    **identical** to the uninterrupted 400-day run, catch-up day
    count exactly 400.
  - **Catch-up event coverage:** over a 3,650-day catch-up with an
    active scripted policy, the catch-up event list covers the whole
    period — non-empty, every event day inside the window, ends
    within the final month.
  - **Whole-days floor:** +36 h of clock elapsed advances exactly
    1 day; +23 h advances 0 and does not rewrite the save (the
    unplayed partial day is not eaten).
  - **Fractional remainder preserved (2026-11-08):** a load at
    +36 h reaches day 1, and a second load at +48 h reaches day 2 —
    the first load's rewrite banks the unconsumed 12 h instead of
    discarding it; a single uninterrupted load at +48 h lands on
    the identical state hash, and a load at +50 h advances nothing
    further (no double-counting).
  - **Overwrite protection (2026-11-08):** a second `new` against
    an occupied save path is refused (`save already exists`), the
    existing campaign's state hash is unchanged afterwards, and
    `new` with `"overwrite": true` is the explicit replacement
    path, producing a fresh day-0 campaign.
  - **Refusal surfacing:** an illegal command (claim an unsurveyed
    system) returns the core's error, leaves credits/systems
    untouched, the save still loads, and a subsequent legal command
    succeeds.
  - **Full loop at bridge level:** new → survey → claim → colonize →
    build a second surveyor → refuel arrives over ~600 days, ending
    with 2 colonized systems and a second founded-event.
  - **Session continuity:** the frontend's exec cadence — 30
    one-day exec calls vs one exec of 30 days — ends in identical
    core state hashes (saved-at refresh changes nothing).
  - **list_saves:** reports name/day/saved-at for valid saves and
    counts a corrupted file as skipped instead of failing.
  - **Bad inputs:** nonexistent save, unknown op, unknown command —
    all return structured `ok:false` responses, no panics.
- Regressions re-checked in the same pass: pipeline **22/22**,
  sim **19/19** (both exit 0).

### Windows cross-build (build-verified only)

```
cd bridge
cargo build --release --target x86_64-pc-windows-gnu
```

Produces `sim-bridge.exe`, confirmed by `file` as a PE32+ x86-64
Windows executable. **It has never been executed** — there is no
Windows or Wine on this VM. Its first real run is Adam's test
session. (The Linux binary runs the full test suite above.)

### Godot — S0 verify on the game build (regression)

```
godot --headless --path viewer -- --verify
```

Exit 0; the five S0 lines all pass unchanged (star count 113,393,
Sol at origin, TRAPPIST-1's 7 planets, pick-Sol). Load ~100–400 ms
and 70.5 MB static memory on this VM across runs (headless dummy
renderer — load/memory only, no rendering claims).

### Godot — S2 verify (the full loop through the real bridge)

```
godot --headless --path viewer -- --verify-s2 \
  --bridge=<abs path>/bridge/target/release/sim-bridge
```

Exit 0. Output after the S0 lines (verbatim, coordinator's run):

```
S2_VERIFY_PASS new day=0 colonized=1 ships=2
S2_VERIFY_PASS target index=64549 name=Proxima Centauri dist_ly=4.2262
S2_VERIFY_PASS dispatch_surveyor ship=1 to=64549
S2_VERIFY_PASS advance_survey surveyed=2
S2_VERIFY_PASS claim_and_dispatch_colony ship=2 to=64549
S2_VERIFY_PASS advance_colonize colonized=2 colony_founded_event=true
S2_VERIFY_PASS load_catchup days=30 day=600->630
S2_VERIFY_PASS all
```

This drives the game's own `BridgeClient` and the production bridge
binary end to end: new campaign (seed 42) → surveyor dispatched to
the nearest star to Sol (Proxima Centauri, 4.2262 ly — also proving
the table-index ↔ star-id mapping on real data) → survey completes →
claim → colony ship dispatched → colony founded (event present) →
save reloaded with a 30-day elapsed override → catch-up reports
exactly 30 days and the day counter moves exactly +30.
`--verify-s2` without `--bridge=` prints `S2_VERIFY_FAIL bridge not
specified` and exits 1. A plain headless boot (`--quit-after 30`)
exits 0 with the menu up and no script errors.

Additionally during the build (not committed): a temporary UI smoke
harness drove the real UI handlers — new campaign, panel population,
ship selection + range mesh, order buttons, event log, save, menu,
load with a 5-day override, catch-up modal, Begin → still Paused —
and passed; the harness was removed before the final verification
runs. Interactive rendering and mouse feel are **not** covered by
any of this (see §5).

## S1 — sim core (Rust, `sim/`)

```
cd sim
cargo test
```

Result: **19 passed, 0 failed** (6 unit + 13 integration in
`sim/tests/s1.rs`). Environment: same rustup toolchain as §1.

Unit coverage:
- `rng` — same seed → same stream; per-star child streams repeatable
  and star-specific.
- `catalog` — distance/lookup over `StarRecord`s.
- `profile` — real catalog planets stay `RealCatalog` and score by
  measured equilibrium temperature/radius; generated profiles are
  repeatable and every generated planet is labelled `Generated`.
- `save` — save → load round trip preserves the canonical bytes and
  state hash exactly.

Integration coverage (`tests/s1.rs`):
- **Determinism:** advancing 10 years as one `advance(3650)` call vs
  365×`advance(10)` vs 3,650×`advance(1)` produces identical
  canonical bytes and state hash.
- **Save/load continuity:** a scripted-policy campaign saved at year
  5, reloaded, and continued to year 10 ends with the identical state
  hash as the uninterrupted run. Saves reject a different galaxy
  (fingerprint mismatch).
- **Fuel:** dispatch beyond the design range (120 ly vs 75 ly) is
  refused; fuel burn is exactly distance × per-ly rate (10 ly → 20.0);
  dispatch beyond the fuel aboard is refused; refuelling at a colony
  restores a full tank; a deliberate unchecked one-way order strands
  the ship en route at exactly the fuel-exhaustion point (15.0 ly on
  30 fuel); a ship arriving on exactly empty tanks still surveys
  (surveying is local sensor work — otherwise it deadlocks).
- **Colonization rules:** colonizing an unsurveyed system is refused;
  founding before claiming is refused, claiming then founding works;
  colony growth over a year is positive and far below the logistic
  carrying capacity.
- **Construction:** a queued surveyor is delivered after its 90-day
  build.
- **Scripted campaign:** the policy expands from Sol in a synthetic
  two-star galaxy (surveyed ≥ 2, colonized ≥ 2, population grows).
- **Endurance:** `advance(36_500)` (100 years) completes; state hash
  well-formed.

### CLI demo — scripted 25-year campaign on the real table

```
cd sim && cargo run --release --bin sim-cli -- --years 25
```

Seed 42, real 113,393-star table, one summary line per year. Result:
**99 systems surveyed, 13 colonized, population 1,200 → 1,676.56M,
credits positive throughout (5,484.31 at year 25)**, final state hash
`7e64c3223b1604eb9a1ee5f97401edfb3ee10a6741f14d7e554be638c8ea6bad`.
Full verbatim output is reproduced in `docs/MUSE_HANDOFF.md`.

### Performance (measured, this VM, release build)

- Scripted 100-year campaign (`sim-cli --years 100`, daily policy
  decisions + 36,500 ticks + monthly settlements on the real table):
  **~0.78 s wall** end to end; ends at 256 surveyed / 34 colonized.
  This is a VM CPU measurement of the core, not a frame-time claim.
- No wall clock or external RNG in the core: a grep over `sim/src`
  for `std::time`, `SystemTime`, `Instant`, `Utc::now`, `Local::now`,
  `thread_rng`, `rand::` returns no matches.

### S1 regressions found and fixed during the build

- The scripted surveyor marooned itself at Teegarden's Star with
  0.04 fuel by chaining single affordable legs — the policy now
  requires a return-to-nearest-colony reserve before a survey hop
  and falls back on the fuel actually aboard.
- A ship arriving on exactly empty tanks deadlocked (could not
  survey without fuel; nothing could reach it): arrival orders
  (survey/found) now proceed on empty tanks; only departures wait
  for fuel.
- First demo balance ran the treasury deeply negative; colony upkeep
  was rebalanced and the policy keeps a build reserve. The 25-year
  run above is the post-balance result.

## S0 sections (unchanged below)

## 1. Pipeline unit + integration tests (Rust)

```
cd pipeline
cargo test
```

Environment: rustup toolchain `1.99.0-x86_64-unknown-linux-gnu`
(`RUSTUP_HOME`/`CARGO_HOME` under `~/workspace/synveil-tools`).

Result: **22 passed, 0 failed** (20 unit + 2 integration).

Coverage:
- `csv` — RFC 4180 quoted fields, doubled quotes, CRLF, no trailing
  newline.
- `astro` — pc→ly, J2000 rotation preserves distance, galactic-centre
  direction maps to +X, RA/Dec round trip.
- `derive` — spectral parsing (`G2V`, `M5Ve`, `K0III`, `sdM3`, `B9.5V`),
  temperature anchors/ordering/floor, luminosity round trip, Sun-like
  mass/temperature.
- `hyg` — placeholder-distance filter keeps Sol (dist 0), name
  fallback chain (proper → bf → Gliese → HIP → HD → HR → HYG id).
- `exo` — archive row parse incl. quoted fields.
- `merge` — host match by designation, by coordinates (≤1.0 pc),
  insert-missing-host (position from archive RA/Dec/dist, archive
  flag), skip-host-without-position.
- `table` — binary write→read round trip identical, byte-identical
  repeated writes, header/record sizes match the format contract.
- `tests/pipeline_integration.rs` (fixtures in
  `pipeline/tests/fixtures/`, no network) — full parse→merge→write→
  read path over hand-made HYG/archive slices: 5 HYG rows → 4 usable,
  hosts matched 1 by name + 1 by coordinates, 1 inserted with 3
  planets, 1 skipped, 6 planets attached, lossless round trip.

## 2. Live pipeline build

```
cd pipeline
cargo run --release -- build --out ../data --offline   # uses pipeline/cache/
```

(First build downloads into `pipeline/cache/`; `--offline` proves the
cache path.) Build report from 2026-11-04:

```
HYG v4.4 input rows:            119614
  dropped (placeholder distance):  10224
  usable stars:                    109390
  with proper names:               541
Exoplanet Archive planet rows:     6451
  planetary systems:               4847
  hosts matched by designation:    713
  hosts matched by coordinates:    104
  hosts inserted (not in HYG):     4003
  hosts skipped (no position):     27
  planets attached:                6424
Final table: 113393 stars, 6882528 bytes (stars.bin)
Distance from Sol: median 645.9 ly, max 27723.3 ly
Spot-check: Proxima Centauri at 4.226 ly (HYG v4.4 distance; modern value 4.246 ly)
Spot-check: TRAPPIST-1 present with 7 planets (expected 7)
Read-back verification: OK (113393 records round-tripped)
```

Reconciliation against the design doc (§1, verified by hand during
planning): HYG rows 119,614 ✓; placeholders 10,224 ✓; usable 109,390
✓; HYG max usable distance 990.099 pc ✓ (≈3,229 ly). Archive snapshot
(2026-11-04 pull): 6,451 planets / 4,847 systems ✓ — matches the
doc's snapshot exactly; counts drift upward over time.

Notes on the numbers:
- Proper names: 541 of the doc's 549 survive the filter — 8 named
  stars sit on placeholder-distance rows and are dropped by design.
- Final-table max distance 27,723.3 ly is **SWEEPS-4**, an
  archive-inserted host at the archive's own stated 8,500 pc (a
  SWEEPS bulge field estimate) — archive data, flagged with its
  source, not a pipeline error.
- Proxima at 4.226 ly is HYG v4.4's own distance; the catalog value
  is kept, the modern 4.246 ly difference is recorded, not "fixed".
- 6,424 of 6,451 planets attached: the 27 unattached belong to the
  27 skipped hosts (no usable archive position).
- `stars.bin` SHA-256
  `03993d9951e2ad1d550ddddcbe3ded24435ffd4d06258b9b6487ce034cadecc3`;
  a second build produced a byte-identical file (determinism ✓).
  Full provenance: `data/manifest.json`, `data/SOURCES.md`.

## 3. Godot viewer — headless verification

Godot 4.7.2 stable (Linux x86_64), already on this VM from the
ai-animation-studio project (`~/workspace/godot-bin/`).

```
godot --headless --path viewer -- --verify
```

Output (verbatim, 2026-11-04; whole run ~1.4 s):

```
VERIFY_PASS star_count=113393 matches manifest
VERIFY_PASS sol_at_origin dist_ly=0.0000
VERIFY_PASS trappist1_planets=7 names=TRAPPIST-1 b, TRAPPIST-1 c, TRAPPIST-1 d, TRAPPIST-1 e, TRAPPIST-1 f, TRAPPIST-1 g, TRAPPIST-1 h
VERIFY_PASS pick_sol index=0
MEASURE load_ms=96 stars=113393 planets=6424 mem_static_mb=67.5
VERIFY_PASS all
```

Exit code 0. The pick assertion drives the real camera: the camera is
aimed at Sol, Sol is projected to screen coordinates, and the
click-pick code path (`nearest_to_ray`) must return Sol's record.

Measurements (this VM, dummy renderer — load/memory only):
- Shipping table (113,393 stars): load **96 ms**, static memory
  **67.5 MB**.

## 4. ~1M-star extended measurement (Adam's ruling: measure)

Source resolution: the design phase's guessed AT-HYG URL 404'd. The
current location is the Codeberg repo `astronexus/athyg`, file
`data/athyg_40.csv.gz` (note: `athyg_40`, not the `athyg_v40` the
repo README text mentions — that name 404s). The file is Git-LFS
backed; the Codeberg media endpoint serves the real content.

- Download: 199,688,001 bytes gz (~488 MB CSV), 2,558,654 rows,
  2,533,096 with usable distances.
- Harness `pipeline/measure_extended.py` (Python stdlib, measurement
  only — not the shipping pipeline) selected the **1,000,000 nearest**
  usable stars (distance cutoff 468.85 pc) and wrote the same v1
  binary format to `data/extended/stars.bin` (git-ignored):
  **52,014,311 bytes**, build time **81.9 s** (two passes over the
  CSV; a Rust builder would be faster — the number is the harness's).
- Viewer measurement:
  ```
  godot --headless --path viewer -- --measure --data=<abs path>/data/extended/stars.bin
  MEASURE load_ms=739 stars=1000000 planets=0 mem_static_mb=173.8
  MEASURE_DONE
  ```
  So at 1M stars: ~52 MB on disk, **739 ms** load, **173.8 MB**
  static memory in the viewer process — comfortably inside the
  target PC's budget. The extended table is a scale proxy (AT-HYG
  only, no exoplanet merge), not a candidate shipping table; that
  decision belongs to a later slice.

## 5. NOT verified (owner-PC / later gates)

- **FPS / frame pacing on Adam's RTX 3060** — the VM's headless
  dummy renderer says nothing about rendering performance. No FPS
  claim is made anywhere in S0–S2.
- Interactive feel: orbit/fly controls, click picking with a real
  mouse, point-size appearance under the Vulkan renderer.
- Windows build/export of the viewer.
- **S2 additions:** the game has only run headless on this VM.
  Unverified until Adam's PC session: the S2 UI interactively
  (menus, panels, buttons, catch-up modal with a real display and
  mouse); `sim-bridge.exe` executing under Windows 11 at all
  (build-verified only, §S2 above); real-clock catch-up over an
  actual overnight absence (the mechanism is test-proven via clock
  injection and the debug elapsed-days override, not by waiting);
  an exported game build (S2 ships as a Godot project + bridge exe
  by design).
- The pipeline's download path on a cold cache was exercised for the
  catalog fetches themselves (files in `pipeline/cache/` came from
  live downloads this session); `--offline` rebuilds from cache are
  what CI-style runs should use.
