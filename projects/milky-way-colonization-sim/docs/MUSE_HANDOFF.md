# MUSE_HANDOFF — Milky Way Colonization Simulator

State as of **2026-11-08**, end of slice S3 (built and VM-verified;
see the verified/unverified split at the end of the S3 section).
Branch `milky-way-colonization-sim/s3-ai-races`, based on the S2
foundation tip; PR #29 (foundation) merged to `main` on 2026-11-07,
so the S3 draft PR targets `main` (never auto-merge).

## What S3 delivered

**Authorization and the §10 gate.** Adam, 2026-11-07 (direction pick
"4A"): start S3 now. DESIGN §10 makes S3's start conditional on the
S2 verification gate — Adam playing a real session on his PC. **Adam
explicitly waived that gate as a precondition on 2026-11-07.** The
waiver starts the work; it does not complete the gate: no owner play
session has happened yet, and S2/S3 interactive play feel remains
unverified (see the split below). S3's own §10 verification —
"headless multi-civ campaigns (all-AI, 300 years, no crashes)" — is
met on this VM (below); its "Adam-facing contact/diplomacy play"
half is the same still-open owner gate.

**The core (`sim/`) — multi-civilization generalization.**
- `Campaign` holds `civs: Vec<Civilization>` (index = id; civ 0 is
  the player). Ships carry an owner; colonies pay their owner;
  claims are per-civ. Every S1 command gained a civ-parameterized
  form (`claim_system_for`, `dispatch_ship_for`, …); the player
  wrappers keep the exact S1 signatures, and a zero-AI campaign is
  **hash-identical** to the S1/S2 solo game, including under the
  scripted policy (test-pinned).
- **Placement (§6.1/§6.2, `race.rs`):** seeded species names and
  personality vectors (expansion / aggression / trade affinity /
  xenophobia / honour) drawn from six archetypes with jitter.
  Homeworlds are real G/K/M catalog stars within 1,000 ly of Sol,
  habitability ≥ 40 (guaranteed ≥ 60 via the flagged
  `homeworld_named` adjustment — the design's "first lie", recorded
  on the profile), local density within 0.4–2.5× the regional
  median, minimum pairwise spacing 250 ly with a documented
  relaxation ladder for galaxies that cannot satisfy it. Default
  12 AI + player; setup accepts 4–40 civilizations total (§11.3).
  Every civ starts identically provisioned; the player still starts
  at Sol (§11.7 ruling).
- **Fog of war is per-civilization** (`surveyed_by` sets). The AI
  plans only from its own surveyed systems — no back door: it calls
  the same public commands, pays the same costs, and its dispatches
  are refused by the same fuel rules.
- **AI planning (`ai.rs`):** a monthly planner inside the daily
  advance (so chunking invariance and catch-up equivalence hold by
  construction): refuel → specialize → build → claim/contest →
  dispatch, personality-weighted (claim/credit reserves scale with
  expansion; only aggression ≥ 0.55 contests claims). Surveyors
  only hop when they can provably get home: outbound leg + the
  shortest hop-by-hop return path (one shared Dijkstra return-cost
  field per civ per month) must fit the fuel aboard.
- **Contact & diplomacy (§6.3, `diplomacy.rs`):** surveying a system
  another civ holds — or arriving at one — records first contact
  (idempotent, both directions). Opinions are a pure function of
  state: disposition from the observer's personality, a penalty per
  open dispute, border friction from colony proximity; dispute
  tension grows monthly with the challenger's aggression. The
  diplomacy view counts only colonies the observer has surveyed —
  no omniscience. Disputes are opened by the new `contest_claim`
  command; in S3 they are records with opinion effects — settling
  them (cede/swap/pay), treaties, trade and war are S4/S5 per §10.
  The §6.3 translation delay is deferred with the S4 treaty set.
- **Save format v2.** v1 (S1/S2) saves are rejected with an explicit
  "unsupported save version 1" error — S2 saves do not carry into
  S3 builds. The state hash covers the full multi-civ state.
- **Perf:** `Galaxy` gained a spatial grid (`stars_within`), which
  also replaced the per-call 113k-star scan behind neighbor lookups.
  Solo speed is unchanged (~0.5 s per 2 years, release, this VM);
  a 13-civ campaign runs ≈ 0.4–1.3 s/year.

**The bridge (`bridge/`) — player perspective.** `new` accepts
`ai_races` (absent = the exact S2 solo behavior); the setup response
names the AI civs but **never their home systems** (an early draft
leaked them; removed and test-pinned). Exec gains `contest`. The
view shows only the player's ships and surveyed systems; a
`civilizations` roster lists the player plus **contacted** civs
with opinion breakdowns both ways and open disputes; a `galaxy`
block carries map-wide totals. Event visibility: your events
always; contact/dispute events involving you always; foreign
presence events only in systems you have surveyed; foreign internal
events never. Catch-up snapshots gained the galaxy totals, so the
"while you were away" review (§11.1) reports AI expansion, new
contacts and new disputes alongside your own deltas.

**The viewer (`viewer/`).** Menu gains the AI-race count (0–39,
default 12). New **Diplomacy** overlay (contacted civs, opinion
components, dispute tension). **Contest Claim** button on foreign
claims in the system panel. Event log names actors ("First contact
— A × B"); the catch-up modal adds the galaxy section. New
`--verify-s3` headless mode; `--verify` and `--verify-s2` unchanged
and still passing.

**Long-run behaviour (release sim-cli, real 113,393-star table,
seed 42; evidence for §10's headless-campaign verification):**
- 13 civs × 300 years: completes, no crashes; 589 systems
  colonized galaxy-wide (player 64), 2,049 claimed, 2,447
  surveyed. Contact comes late at the default count — homes sit
  250–1,000 ly apart — but it comes: first contact at year 215,
  and 3 claim disputes open by year 300.
- 40 civs × 300 years: 1,104 colonized, 3,188 claimed, 3,895
  surveyed; first contact also at year 215 (1 contact pair by
  year 300), 3 disputes open by year 300.
  (Long-run figures corrected 2026-11-08 to the completed run
  logs; an earlier draft cited in-flight numbers.)
- Two of the twelve seed-42 AI civs stall at 2–4 colonies: their
  home neighbourhoods have no prudently-reachable unsurveyed stars
  under the S1 fuel numbers. Recorded as an emergent outcome of the
  §6.1 density band + fuel rules, not patched over in S3; a balance
  question for Adam (ship range vs placement density), not a defect
  claim either way.

**Verified (this VM, 2026-11-08, final code):** pipeline tests
22/22; sim tests 28/28 (incl. zero-AI ≡ solo hash equality,
per-civ fog, disputes, v1-save rejection, and **catch-up
equivalence with AI active**: advance 5 y → save/load → hash equal;
10 y total ≡ uninterrupted); bridge tests 20/20 (incl. bridge-level
catch-up equivalence with AI active and the no-leak perspective
rules); Godot `--verify`, `--verify-s2`, `--verify-s3` all-pass.
**Unverified:** interactive play feel and the owner-PC play session
(S2 gate, waived as a precondition, still unmet); windowed Godot
interaction with the new diplomacy UI; overnight real-clock
catch-up; the Windows export build / `sim-bridge.exe` on Windows;
FPS on Adam's RTX 3060 (owner-hardware gate, as always).

---

State as of **2026-11-06**, end of slice S2 (built and VM-verified;
Adam's owner-PC play session is the slice's remaining gate).
Branch `milky-way-colonization-sim/foundation`, tracked by draft
PR #29 (never auto-merge).

## What S2 delivered

**Authorization.** Adam, 2026-11-06: "Queue up the colony sim game
again" and "Have the production work on it until it's in a testable
state for me." That is the S2 go-ahead this slice ran under.

**Architecture — process bridge, not GDExtension.** The frontend
talks to the core through a new crate, **`bridge/`** (binary
`sim-bridge`): the Godot project spawns it per call with a JSON
request/response file pair. Why: DESIGN §9 mentions a
GDExtension/C-ABI binding only inside the engine-choice comparison;
the §11.5 ruling fixed "Rust core + Godot 4 frontend", and project
AGENTS rule 8 is mechanism-agnostic (frontend reads core data,
sends commands). The process bridge keeps `sim/` completely
untouched (the S1 wall-clock-free grep invariant still holds), is
the one designated wall-clock-aware component, adds zero
third-party dependencies, and cross-compiles to Windows cleanly.
GDExtension remains possible later without core changes. **Flag
for Adam:** if you wanted the in-process binding specifically,
say so — the swap is frontend-side only.

- **Envelope saves (`.mwsb`):** `MWSB` magic + version +
  `saved_at_unix` (the trustworthy timestamp the 2026-11-04
  offline-progression ruling requires) + game day + the untouched
  core `save_bytes()` payload. Atomic writes (tmp + rename);
  `saved_at` refreshes on every bridge write, but a load whose
  elapsed time floors to 0 days does **not** rewrite the file (a
  partial unplayed day is never eaten).
- **Catch-up on load:** elapsed whole days =
  `floor((now − saved_at) / 86400)` (a request may inject `now` or
  an explicit elapsed override — the frontend exposes the override
  as a debug field for testing); the core advances by the full
  amount, **no cap** (the ruling). The response carries the
  catch-up block: days, monthly settlements crossed, before/after
  snapshots, and the core's own events for exactly the catch-up
  window — the review surface's data.
- **Protocol ops:** `new`, `load`, `exec` (command list applied in
  order, stops at first failure, per-command results, events since
  a cursor, persists either way), `view` (full UI state incl. the
  core state hash), `inspect` (one system: catalog facts with
  derived flags, profile with per-planet source labels, colony,
  ships present), `list_saves` (header-only scan, corrupt files
  counted as skipped). Commands mirror the core API 1:1 (advance,
  survey, dispatch, claim, found, build, refuel, specialize).
  Core refusals travel back as structured errors and change
  nothing.

**Frontend (`viewer/` grown in place into the game).** Main menu
(new campaign with seed + save name; load list from the saves
directory; debug elapsed-days field), HUD (date, credits, counts,
total population/fuel), the speed ladder per §2 (Paused, 1× =
1 day/real-day, 1 day/hour, 1 day/min, 1 day/sec, 10 days/sec;
sessions always start Paused), throttled real-time clock (bridge
call at most every 0.25 s, whole days only — proven by test to be
state-identical to batched advance), system panel driven by
`inspect` (facts with "(derived)" markers, planets labelled
real/generated, colony block incl. construction queue), ships
panel, order buttons with core refusals surfaced in the message
line, state markers on the map (surveyed pale / claimed gold /
colonized green), a magenta direct-range highlight for the
selected ship, an event log (last 300), auto-pause on colony
abandonment and ship stranding, and the **catch-up review modal**:
days passed, settlements, before→after deltas, and the full event
list for the away period (or "the galaxy ticked quietly") —
unwatched time never lands silently.

**Scope notes (deferred, not dropped).**

- *Ship designer UI:* DESIGN §5.3's designer needs custom
  engine/tank designs; the S1 core ships fixed designs and has no
  design-registration API. S2 exposes the two fixed designs
  (build buttons, costs from the core). A design API is a core
  addition for a later slice.
- *Range overlay:* §7.2's reachable-set overlay is graph-based
  (multi-hop over the refuel network). S2 ships the honest
  direct-leg version (stars within range of the selected ship's
  system, limited by fuel aboard). The graph version slots into
  the same layer later.

**Test state (all run 2026-11-06 on this VM, coordinator re-ran
each firsthand; detail in `docs/TEST_PLAN.md`).**

- `bridge`: `cargo test --release` **16/16** — incl. the headline
  catch-up equivalence test (save at T, load at T+400d ⇒ state
  hash identical to an uninterrupted 400-day run), catch-up event
  coverage over 10 years, whole-days flooring, refusal atomicity,
  exec-cadence equivalence.
- `sim` **19/19** and `pipeline` **22/22** — unchanged, re-run.
- Godot `--verify` (S0) all-pass, exit 0; `--verify-s2` all-pass,
  exit 0 — the full loop through the real bridge to Proxima
  Centauri plus a +30-day catch-up load.
- Windows: `sim-bridge.exe` cross-builds (PE32+ x86-64, confirmed
  by `file`); a full `new`+`inspect` cycle against the real
  113k-star table takes ~0.17 s on this VM, so the per-call
  process model is not a latency problem at these call rates.

**Owner test package.** Assembled outside the repo (release
artifacts are never committed): Godot project + Windows
`sim-bridge.exe` + star table + `README-TEST.md` with exact
click-by-click instructions, including the debug elapsed-days
load for testing catch-up without waiting. Location recorded in
the goal workspace (`mwcs-s2-test/` + `.zip`).

**S2 gotchas.**

- GDScript cannot define a method named `call` (it collides with
  `Object.call()` and Godot 4.7 treats it as a hard error) — the
  bridge client entry point is `call_bridge()`.
- Godot 4.7 project-scope `@onready` initialization inside if/else
  branches does not run reliably; build UI nodes unconditionally
  and toggle visibility.
- The star table's record index equals the core's star id
  (asserted in tests and cross-checked at runtime in the panel);
  frontend code relies on it openly rather than hiding a mapping.
- The VM lacked mingw initially; the windows-gnu cross-build now
  works (gcc 13-win32). The `.exe` remains **build-verified
  only** — never executed on Windows.

## What S1 delivered

The headless Rust sim core in **`sim/`** (crate `mwcs-sim`, zero
third-party dependencies of its own; it path-depends on the S0
pipeline crate for the star-table reader and SHA-256):

- `src/catalog.rs` — in-memory view of the S0 table (`Galaxy`,
  `StaticStar`, `StaticPlanet`) plus a canonical catalog fingerprint
  used to bind saves to their galaxy.
- `src/state.rs` — the simulation itself: `Campaign` with sparse
  per-system state (`BTreeMap<StarId, SystemState>`) over the inert
  catalog; survey state unknown → surveyed, claims, colonies
  (population, development, specialization slot, five strategic
  stockpiles, energy flow, defence placeholder, construction queue);
  ships as state machines (at system / surveying / en route /
  stranded en route / stranded at system); the daily tick with a
  monthly settlement every 30 days.
- `src/profile.rs` — the profile revealed by a survey. Real catalog
  planets stay real (habitability from measured eq. temperature and
  radius); systems without catalog planets get a generated profile
  from the star's real properties + campaign seed, with every
  generated planet explicitly labelled `Generated`.
- `src/rng.rs` — SplitMix64 seeded RNG owned by the core. Profile
  generation uses per-star child streams derived from
  `(campaign seed, star id)`, so decision order cannot leak into a
  system's fixed contents.
- `src/save.rs` — canonical binary serialization (sorted maps, raw
  float bits, length-prefixed strings) → SHA-256 state hash; the
  save format is that payload behind a `MWSS` header, verified
  against the galaxy fingerprint + star count on load.
- `src/policy.rs` — the deterministic scripted policy (the S1 test
  harness driver, **not** the §6 AI — that is S3).
- `src/main.rs` — `sim-cli`: starts a campaign at Sol (ruling
  §11.7), runs the scripted policy, prints one summary line per
  game year.

Rules implemented from the design: 1 tick = 1 game day (§2);
colonization pipeline survey → claim → found, colony ship consumed
(§3); credits global + energy as a per-system flow, five strategic
resources stockpiled per system with fuel first-class (§4); ship
range = tank ÷ burn, movement burns fuel by distance, orders beyond
range or beyond the fuel aboard are refused, refuelling at colonies,
stranded ships per §5.2 (only via a deliberate unchecked one-way
order in S1 — no combat/lost-depot causes exist yet).

## Model choices where the design left room

- **Economy constants** (design §4 gives structure, not numbers):
  population income `pop × 0.045 × (0.7 + dev × 0.08)`/month,
  upkeep `2 + dev + pop × 0.004`/month; production formulas keyed
  to development, habitability, and profile traits, with
  specialization multipliers (Refinery ×3 fuel, Industrial ×2.5
  alloys, Agricultural ×2.2 supplies, Trade Hub ×1.4 income).
  Supplies are the binding upkeep: production + stored buffer first,
  growth stops when unsupplied, decline after 3 unsupplied months,
  abandonment after 12 (design §3's slow, telegraphed loss).
- **Growth:** logistic toward capacity
  `100 + habitability% × 25 + development × 400` (millions).
- **Development** rises one level per supplied year (to a S1 cap of
  5) when population exceeds `development × 150`M; specialization
  unlocks at development 3, one slot in S1 (the second slot at 7 is
  a later-slice concern).
- **Starting position:** homeworld population 1,200M, development 3,
  15,000 credits, one surveyor (75 ly range) and one colony ship
  (75 ly range) in orbit. Ship construction is a per-colony queue
  (surveyor 90 days / 400 credits / 12 alloys; colony ship 240 days
  / 1,500 credits / 45 alloys).
- **Survey duration:** deterministic 24–37 days + 2 per known
  catalog planet, derived from the seed and star.
- **Stranding in S1:** normal dispatch can never strand a ship.
  `dispatch_ship_unchecked` is the explicit one-way order of §5.2;
  a ship arriving on exactly empty tanks can still survey/found
  (local work) but cannot depart until refuelled; a ship stranded
  en route awaits tanker mechanics from a later slice.
- **No routes/trade/gates/AI/diplomacy/war** — S3–S5 by design.
  Colonies are self-supplied from local production + buffers in S1;
  the route layer (§4.3) arrives with trade in S4.

## Test state (all run 2026-11-04 on this VM)

- `sim`: `cargo test` **19/19** (6 unit + 13 integration,
  `sim/tests/s1.rs`) — determinism across advance chunking,
  save/load-at-year-5 continuity, range/fuel refusals, exact fuel
  burn, stranding, claim-before-founding, bounded growth,
  construction, scripted expansion, 100-year endurance. Detail in
  `docs/TEST_PLAN.md`.
- `pipeline`: `cargo test` **22/22** (unchanged by S1).
- Viewer: Godot `--verify` still all-pass (unchanged by S1).
- No wall clock / external RNG in `sim/src` (grep-verified, see
  TEST_PLAN).

## Demo — scripted 25-year campaign (verbatim)

`cargo run --release --bin sim-cli -- --years 25`, seed 42, real
113,393-star table:

```text
campaign_start seed=42 stars=113393 home=0 
year=1 day=365 surveyed=8 colonized=3 population_millions=1214.64 fuel_stock=1039.27 credits=12286.58 ships=1
year=2 day=730 surveyed=16 colonized=4 population_millions=1230.56 fuel_stock=1207.87 credits=11041.47
year=3 day=1095 surveyed=24 colonized=5 population_millions=1248.02 fuel_stock=1258.53 credits=9797.66
year=4 day=1460 surveyed=29 colonized=7 population_millions=1266.14 fuel_stock=1439.54 credits=7100.39
year=5 day=1825 surveyed=29 colonized=8 population_millions=1284.17 fuel_stock=1642.80 credits=5986.90
year=6 day=2190 surveyed=34 colonized=9 population_millions=1303.84 fuel_stock=1876.14 credits=4744.48
year=7 day=2555 surveyed=42 colonized=10 population_millions=1322.18 fuel_stock=2129.47 credits=4864.60
year=8 day=2920 surveyed=46 colonized=10 population_millions=1340.41 fuel_stock=2165.29 credits=5082.65
year=9 day=3285 surveyed=55 colonized=10 population_millions=1358.79 fuel_stock=2331.53 credits=5185.70
year=10 day=3650 surveyed=59 colonized=10 population_millions=1377.31 fuel_stock=2356.33 credits=5423.81
year=11 day=4015 surveyed=63 colonized=11 population_millions=1396.22 fuel_stock=2615.88 credits=4172.06
year=12 day=4380 surveyed=72 colonized=11 population_millions=1416.59 fuel_stock=2810.06 credits=4296.96
year=13 day=4745 surveyed=78 colonized=11 population_millions=1435.54 fuel_stock=2848.25 credits=4480.68
year=14 day=5110 surveyed=84 colonized=11 population_millions=1454.62 fuel_stock=2883.49 credits=4674.77
year=15 day=5475 surveyed=91 colonized=11 population_millions=1473.83 fuel_stock=3062.73 credits=4854.30
year=16 day=5840 surveyed=91 colonized=11 population_millions=1493.17 fuel_stock=3179.73 credits=5219.35
year=17 day=6205 surveyed=91 colonized=11 population_millions=1512.64 fuel_stock=3334.22 credits=4094.99
year=18 day=6570 surveyed=91 colonized=12 population_millions=1534.12 fuel_stock=3603.71 credits=4496.00
year=19 day=6935 surveyed=91 colonized=12 population_millions=1553.84 fuel_stock=3768.14 credits=4858.00
year=20 day=7300 surveyed=97 colonized=12 population_millions=1573.69 fuel_stock=3957.33 credits=5080.79
year=21 day=7665 surveyed=97 colonized=12 population_millions=1593.65 fuel_stock=4101.13 credits=5464.45
year=22 day=8030 surveyed=97 colonized=13 population_millions=1613.97 fuel_stock=4361.55 credits=4359.02
year=23 day=8395 surveyed=97 colonized=13 population_millions=1634.16 fuel_stock=4551.30 credits=4728.67
year=24 day=8760 surveyed=97 colonized=13 population_millions=1656.15 fuel_stock=4758.92 credits=5141.59
year=25 day=9125 surveyed=99 colonized=13 population_millions=1676.56 fuel_stock=4956.91 credits=5484.31
final_state_hash=7e64c3223b1604eb9a1ee5f97401edfb3ee10a6741f14d7e554be638c8ea6bad
```

(The year lines above omit the trailing `ships=1` field for width;
the binary prints it. The hash is over the exact run.)

Performance: the same harness at `--years 100` completes in
**~0.78 s wall** on this VM (release), ending at 256 surveyed /
34 colonized. VM CPU number for the core only — no frame claims.

## Gotchas found in S1 (don't rediscover these)

- A surveyor that chains single affordable legs away from colonies
  *will* maroon itself (found at Teegarden's Star, 0.04 fuel). The
  scripted policy's return-reserve rule is load-bearing; a future
  AI/frontend needs the same prudence or tanker support (§5.2).
- Arrival on exactly empty tanks must not block the arrival order
  itself (survey/found), or the ship deadlocks permanently.
- `cargo` needs the full synveil-tools env
  (`RUSTUP_HOME`/`CARGO_HOME`/`RUSTUP_TOOLCHAIN=1.99.0-...`); a bare
  `cargo` invocation fails with a rustup toolchain error.
- The sim depends on the pipeline crate by path; the binary star
  format contract (`pipeline/src/table.rs`) is unchanged in S1.

## Offline progression — RULED BY ADAM 2026-11-04: FULL CATCH-UP

Adam's ruling, in his words: **"Full catch-up — the galaxy lives
while I'm away."** On load, a save advances by the full real
elapsed time since it was saved (one game day per real day at the
1× baseline), with **no cap**. Capped catch-up (the builder's
recorded recommendation, ~30 days) and frozen-while-closed were
considered and not chosen.

**No code in S1 embodies this yet** — the core is step-driven and
only advances when a driver calls `advance()`; its determinism
makes the policy implementable without a redesign. Implementation
belongs to S2, when save/load is wired into the frontend:

**Update 2026-11-06: implemented in S2** — the bridge envelope
carries the trusted saved-at timestamp, load applies the full
uncapped catch-up, and the frontend's review modal presents the
period's events and deltas before the player takes control (see
"What S2 delivered" above). The bullets below are the original
implementation contract, kept for the record:

- Saves need a trustworthy saved-at timestamp; on load, the S2
  driver advances the core by the elapsed whole days before handing
  control to the player.
- The player must be able to review what happened during the
  catch-up (event history/summary) — unwatched months or years of
  arrivals, settlements, and (S3+) AI expansion and wars cannot
  land silently.
- Long absences mean long catch-up runs; the measured tick rate
  (100 game-years ≈ 0.78 s on this VM, release build) makes even
  multi-year absences cheap to simulate.

## Unverified / owner-PC gates

- FPS and rendering feel on Adam's RTX 3060 (no FPS claims made).
- Interactive picking/orbit with a real mouse; Windows export.
- **S2's own gate (DESIGN §10): Adam playing a real session on his
  PC** — the interactive UI, the Windows `sim-bridge.exe` executing
  at all, and a real overnight catch-up are unverified until then.
  The S2 test package is built and waiting on that session.

## Next slice

**S3 — AI races**, only on Adam's go-ahead after his S2 play
session: 8–15 AI civilizations expanding under the same rules with
weaker information, contact and border friction (§6), feeding the
same event log / catch-up review surface S2 built.
