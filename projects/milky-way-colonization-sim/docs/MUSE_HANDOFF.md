# MUSE_HANDOFF — Milky Way Colonization Simulator

State as of **2026-11-08**, end of slice S4 (built and VM-verified;
see the verified/unverified split at the end of the S4 section).
Branch `milky-way-colonization-sim/s4-trade-diplomacy`, based on
`main` at `eab90ffc` (S3, PR #43, merged by Adam 2026-11-08 with an
S4 green-light). This S4 draft PR targets `main` (never auto-merge).

## What S4 delivered

**Authorization.** Adam merged S3 (PR #43) and green-lit S4 —
trade & diplomacy depth (DESIGN §10 S4, building on §4.3 and
§6.3) — on 2026-11-08. S5 (war, fleet combat, victory,
terraforming) is **not** authorized; peace terms here end
disputes, nothing more.

**The core (`sim/`) — treaties, trade, settlements.**
- **Instruments (§6.3's set):** Trade Agreement, Gate Access,
  Non-Aggression Pact, Alliance, Research Pact — plus embargoes
  and peace settlements. Every command exists in civ-parameterized
  (`*_for`) and player-wrapper forms, under one gate:
  `require_diplomacy` (both civs exist, distinct, in contact, and
  the §6.3 **translation delay** — 90 days after first contact —
  has run; S3 deferred the delay, S4 implements it).
- **Deals are evaluated, with stated reasons** (`diplomacy.rs`):
  the recipient's `DealEvaluation` derives accept/refuse from the
  opinion breakdown, both personalities, and concrete interests
  (best-route throughput for trade, the proposer's colony count
  for gate access, shared dispute-rivals for alliances, the
  partner's research output for pacts, dispute relief + cession
  values + credits for peace). Every evaluation returns legible
  reason strings ending in a verdict; refusals surface verbatim
  in the bridge result detail and the diplomacy screen. Opinion
  gained two S4 components: `trade_volume` (+, from settled route
  earnings with this partner) and `broken_treaties` (−, from the
  breach record) — both shown in the breakdown.
- **Negotiation shapes:** player→AI and AI→AI deals resolve on the
  spot (Signed / Refused{reasons}); anything offered **to** the
  player is filed in a proposal inbox (`Proposal`, 180-day TTL,
  365-day re-offer cooldown per instrument) for the player to
  accept or refuse — the AI never auto-accepts for the player.
  Breaking a treaty records a `TreatyBreach` (reputation input to
  opinion and evaluation); embargoing a trade partner terminates
  the agreement *as* a breach and severs its routes; severing a
  single route is not a breach. An NAP or Alliance bars claim
  contests between the parties until broken.
- **Trade routes (§4.3):** a route links two endpoint colonies
  over a colony-network path — Dijkstra over both parties'
  colonies, legs ≤ `TRADE_LEG_LY` (150, an abstract tanker leg;
  gates are S5). Throughput = `4×(dev_a+dev_b) + 0.02×(pop_a+pop_b)`,
  ×1.25 between allies; monthly income per side = throughput ×
  (1 + path_ly/1000) × 0.25, paid in the monthly settlement into
  both treasuries and the route's own ledger (`earned_a/b`,
  `last_income_*`, `months_active`), with the campaign-wide
  `total_trade_income` alongside. Routes die automatically when
  their agreement ends, an embargo lands, throughput hits zero,
  or a path system stops being a colony of either party.
- **Research:** §4.2's Research specialization produced nothing
  before S4; colonies now accrue a `research_points` stockpile
  monthly, and a Research Pact pays each partner 30% of the
  other's output as bonus points. Points have **no spending
  sink** until the §8 tech tree — recorded as a deliberate
  minimal ledger, not a finished economy.
- **Gate access** takes effect in S4 as **port access**: ships
  may refuel at a treaty partner's colonies (the S3 core already
  deferred foreign refuelling "to S4"). The same treaty will
  govern gate *transit* when gate structures exist (S5, §5.3).
- **Peace settlements** close every dispute between the pair,
  transfer ceded claims (colonies included — the receiver is
  granted survey knowledge of what it receives), move credits,
  and lift pair embargoes. AI planners offer recognition-only
  settlements for disputes ≥ 180 days old when their own
  evaluation accepts; cession deals are player-proposable and
  AI-evaluated (and evaluated AI→AI when offered).
- **AI planner** (`ai.rs diplomacy_step`, monthly, after claims,
  before contests): lifts its embargoes when opinion recovers;
  declares embargoes only when opinion ≤ −35 with aggression
  ≥ 0.55 and honour < 0.6 and no non-trade treaty binds;
  proposes instruments in a fixed kind order when its *own*
  evaluation wants them (one per pair per month, at most one
  offer to the player per AI per month); keeps up to 2 trade
  routes per agreement; breaks treaties at opinion ≤ −45 when
  faithless or itself betrayed (alliances hold to −60).
- **Events:** nine new kinds (treaty signed/broken, embargo
  declared/lifted, route established/severed, peace settled,
  proposal received, deal refused) flow through the log and the
  catch-up snapshot (which now also carries treaties, trade
  routes and research points).

**Save format v3 (a bump, flagged).** The payload is strictly
sequential with an exact trailing-bytes check and no extension
point, so the S4 state (research points per civ; treaties,
embargoes, routes, breaches, proposals, cooldowns, id counters,
total trade income) could not ride along invisibly. Per the v2
precedent: `SAVE_VERSION = 3`, the format history is documented
in `save.rs`, and **v2 saves are rejected explicitly**
("unsupported save version 2" — unit-test pinned). The bridge
envelope is unchanged (still v1) and catch-up equivalence holds
with diplomacy active (test-pinned by hash over 730 days).

**The bridge (`bridge/`).** New exec commands: `propose_treaty`,
`break_treaty`, `declare_embargo`, `lift_embargo`,
`propose_peace` (player-chair orientation: `cede_to_me`,
`cede_to_them`, `credits` positive = the player pays),
`accept_proposal`, `refuse_proposal`, `establish_route`
(endpoints optional — omitted means the core's suggested best
route), `sever_route`. Exec results gained a `detail` field
carrying the negotiated outcome (`signed`, `refused: <reasons>`,
`proposal #N is awaiting an answer`, `declined`). The view adds
per-civ treaty lists, embargo flags, `diplomacy_ready` +
translation day, the player's routes with full ledgers, the
proposal inbox with reasons verbatim, and galaxy/snapshot
treaty + route totals. `new` also accepts
`ai_region_radius_ly` (mirrors S3's `ai_min_spacing_ly` override;
the S4 headless verify uses a tight region so contact is years
away — real games leave it alone).

**The viewer (`viewer/`).** The diplomacy screen is now an
action screen: per contacted civilization it shows treaties,
embargo state, translation readiness, the extended opinion
breakdown (trade volume, broken treaties), the player's routes
with earnings, and research points (also in the HUD) — plus
buttons to propose/break every instrument, declare/lift
embargoes, open the suggested route, close individual routes,
propose settlements (recognition, or per-dispute one-click
cession terms), and answer inbox offers with the sender's
stated reasons printed above the Accept/Refuse buttons. Command
outcomes (including refusal reasons) surface in the message
line. Player trade routes render on the map as cyan lines along
their star paths; the catch-up modal reports treaty/route/
research deltas. `--verify-s4` joins the headless verify family.

**The route-search stall (found by the long run, fixed).** The
first S4 long run **stalled at first contact** (year 215): pace
collapsed ~100× and the run sat at year 215 for 10+ minutes.
Root cause: `suggest_trade_route` ran a full Dijkstra for every
colony pair (≈3,600 pairs at year-215 colony counts, each
Dijkstra re-scanning all pairs per settle step) — and deal
evaluation + planner route upkeep call it monthly per contacted
pair. Fixes, behaviour-preserving: `trade_path` precomputes
adjacency once (identical graph, identical relaxation order,
identical chosen paths); `suggest_trade_route` weighs candidates
in the established preference order (throughput, then endpoint
ids) and path-checks in that order — the winner is unchanged
whenever the best pair connects — stopping after
`SUGGEST_PATH_CHECK_CAP` (24) checks. Explicit-endpoint route
commands still path-check exactly. A regression test
(`trade_paths_chain_colony_legs_and_suggestions_follow`) pins
multi-leg chaining against an independent test-side Dijkstra.
Post-fix, the same 300-year run completes with expansion figures
**identical to S3's** (589 colonized / 2,049 claimed / 2,447
surveyed; player 64 colonies; first contact year 215) and one
diplomacy delta: disputes peaked at 3 but only **1 remained open
at year 300** (S3: 3 open) — two were closed by AI recognition
settlements. No treaties were signed in that harness: the single
contact pair's deals never cleared evaluation, and the scripted
player never proposes (AI offers to it lapse unanswered) — the
treaty machinery itself is proven by the test suites below.

**Design tensions recorded (not silently redesigned).**
(1) Save v3 bump — unavoidable, above. (2) Gate Access = port
access until S5 builds gates. (3) Research points have no sink
until §8. (4) Opinion's "shared enemies" component remains
absent (no war until S5); alliance evaluation uses shared
*dispute rivals* as the S4 proxy. (5) Trade legs use the
abstract tanker range, no gate hops (S5). (6) The
Non-Aggression Pact ships in S4: §6.3 lists it among the
negotiable instruments even though the S4 tasking enumerated
the other four. (7) The seed-42 balance question from S3 (2 AI
civs stalling at 2–4 colonies) is **untouched** — no fuel or
placement retuning; S4's run reproduces S3's expansion exactly.

**Verified (this VM, 2026-11-08; detail in TEST_PLAN.md).**
Cargo suites: pipeline 22, sim 42 (incl. 13 S4 tests: a
sign→honour→break lifecycle per treaty type, month-by-month
trade-ledger reconciliation, stated-reason refusal tests, the
path-chaining regression), bridge 27 (incl. 4 S4 tests over the
real binary). Godot `--verify`, `--verify-s2`, `--verify-s3`,
`--verify-s4` all pass (`--verify-s4`: contact at year 6 in the
tight setup, proposal refused *with reasons* end-to-end, embargo
round-trip). All-AI 300-year run completes, above.

**Unverified / owner gates (unchanged in kind).** Interactive
diplomacy play on Adam's PC (the S2 play-session gate is still
open); windowed clicking of the diplomacy actions; Windows
export; overnight real-clock catch-up; FPS on the RTX 3060.

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

**Reconciliation with PR #45 (2026-11-08):** main (tip `822083c`)
was merged into this branch. PR #45's overwrite guard and
fractional catch-up landed after S3 was built and overlapped it in
`bridge/src/main.rs`, `viewer/scripts/main.gd` and the README;
the resolutions compose rather than choose a side — the overwrite
guard sits in `op_new` ahead of the S3 setup path (so it protects
multi-civ campaigns too) and ahead of the viewer's confirm-dialog
retry, which now also carries `ai_races`; the fractional-anchor
logic operates on the save envelope, unchanged by save format v2.
Both changesets' regression tests pass together, plus a new
combined pin (`new_with_ai_races_respects_the_overwrite_guard`).
Re-verified on the merged tree (this VM, 2026-11-08): pipeline
22/22, sim 28/28, bridge **23/23**, Godot `--verify` /
`--verify-s2` / `--verify-s3` all-pass. PR #43 stays a draft for
Adam's merge decision; no save-format semantics changed.

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
  `saved_at` is the catch-up anchor: an advancing load moves it
  forward by exactly the consumed whole days — never to the write
  moment — so the unconsumed partial day stays banked for the next
  load (Codex fix, 2026-11-08; see the section at the end of this
  file); other bridge writes stamp their write time, and a load
  whose elapsed time floors to 0 days does **not** rewrite the
  file (a partial unplayed day is never eaten).
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

**S5 — war & victory**, only on Adam's direction: fleet combat,
blockades (the combat counterpart of S4's embargoes), gate
construction and transit (S4's Gate Access treaty then governs
transit, §5.3), victory conditions, terraforming. S4's peace
terms, breach records and opinion components are the diplomatic
substrate S5 builds on.

## 2026-11-08 — Codex review fixes (findings on PR #29, fixed on main)

Two Codex findings against the merged S2 work, both verified against
the code before fixing:

- **`new` could silently overwrite a campaign (P1).** `op_new`
  wrote unconditionally, and the viewer's default save name is
  `campaign1` on every launch. Fix, bridge-first: `op_new` refuses
  an occupied save path (`save already exists: ...`) unless the
  request carries `"overwrite": true` — silent overwrite is now
  impossible for any bridge caller. The viewer treats that refusal
  as a question: a confirmation dialog ("permanently replace it")
  and only the player's explicit Overwrite click retries with the
  flag. Regression test `new_refuses_to_overwrite_existing_save`
  (refusal leaves the state hash untouched; the flagged request
  produces a fresh day-0 campaign).
- **Catch-up ate the fractional day (P2).** `op_load` floored the
  elapsed time to whole days but rewrote the envelope with `now`,
  discarding the partial day on every advancing load (new at T,
  load at T+36 h → day 1, load at T+48 h → still day 1, violating
  the full-catch-up rule). Fix, no format change: the rewrite
  anchor is `saved_at + elapsed × 86400`, so the remainder stays
  banked; the sequence above now reaches day 2, hash-identical to
  one uninterrupted +48 h load. The `elapsed_override_days` path
  keeps its old anchor-at-`now` behaviour (no wall-clock remainder
  exists to preserve). Envelope format unchanged (still v1).
  Regression test `catchup_fractional_remainder_preserved`.

Suites re-run on this VM 2026-11-08: bridge **18/18** (was 16),
sim **19/19**, pipeline **22/22** — all green. The viewer dialog
code follows the menu's existing code-built UI pattern but was
**not** run under Godot on this VM (no Godot binary here); the
bridge behaviour it depends on is fully covered by the cargo
tests. Note: the S3 draft (PR #43) also touches
`bridge/src/main.rs` and `viewer/scripts/main.gd`; expect a
textual merge reconciliation when one of the two lands second.
