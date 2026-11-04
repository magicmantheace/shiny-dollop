> **Provenance:** copied 2026-11-04 from the planning-phase design document
> (`workspace/goals/milky-way-colonization-simulator-planning/files/milky-way-sim-design.md`)
> so the spec travels with the code. §11.7 (default to Sol) was ruled by Adam
> on 2026-11-04 and is recorded in §11 of this copy. The planning original
> remains the historical record; this copy is the build spec.

# Milky Way Colonization Simulator — Design Document

Status: **planning only** (Adam's direction, 2026-11-04). No code, no repo
project yet. This document is the thing Adam reviews and tears apart before
any build starts.

## The five founding decisions (Adam, 2026-11-04 — fixed)

1. The player runs a civilization colonizing the entire known Milky Way
   while other races do the same; contact leads to trade and war.
2. Travel is free FTL bounded by each ship's designed **fuel range**; **warp
   gates** are buildable structures linking systems for quicker travel.
3. Simulation depth is **system-level**: colonized systems carry population,
   output, specialization, construction, supply, defence; uncolonized
   systems are inert data until surveyed.
4. Planets are **real exoplanets where known** (~6,000), generated
   deterministically from the host star's real properties elsewhere.
5. The map is **full 3D** — the real galaxy, flown.

Everything below designs *within* those decisions. Where this document
proposes something Adam has not yet ruled on, it is marked
**DECISION FOR ADAM** and collected in §11.

---

## §1 Data foundation (verified 2026-11-04)

Every number in this section was checked against a live source on
2026-11-04; the URL is cited beside the claim. Two claims are flagged
**UNVERIFIED** where a live check failed — S0 must re-verify them before
relying on them.

### 1.1 HYG — the default game catalog

- **What it is.** HYG merges the Hipparcos, Yale Bright Star, and
  Gliese-Jahreiss catalogs into one table of positions, distances,
  magnitudes, spectral types, and designations.
  (https://codeberg.org/astronexus/hyg)
- **Current home: Codeberg, not GitHub.** Maintainer David Nash
  (Astronexus). The old GitHub repo `astronexus/HYG-Database` was archived
  2025-02-14 and is stale; all v4.x releases live at
  https://codeberg.org/astronexus/hyg. The project page is
  https://www.astronexus.com/projects/hyg.
- **Current version v4.4: 119,614 stars.** (Repo front page, fetched
  2026-11-04: https://codeberg.org/astronexus/hyg — "Directory /data/hyg -
  Currently 119,614 stars".)
- **File.** `hyg_v44.csv.gz` — gzipped CSV, **13,636,362 bytes (13.6 MB)**
  compressed (HTTP content-length, checked 2026-11-04), **37 columns**.
  Download:
  https://codeberg.org/astronexus/hyg/media/branch/main/data/hyg/CURRENT/hyg_v44.csv.gz
- **License: CC BY-SA 4.0** (v4.0+; v3.x was CC BY-SA 2.5). Attribution
  required; a shipped derived star table must carry the same license and
  credit "HYG Database (astronexus)".
- **Fields the game needs** (from the catalog README, fetched 2026-11-04:
  https://codeberg.org/astronexus/hyg/raw/branch/main/data/hyg/README.md):
  `id`, `hip`/`hd`/`hr`/`gl` catalog ids, `bf` Bayer/Flamsteed, `proper`
  (proper name), `ra`/`dec` (J2000), `dist` (pc), `mag`, `absmag`, `spect`
  (spectral type), `ci` (B−V colour index), **`x`,`y`,`z` Cartesian
  coordinates in parsecs** (equatorial frame: +X toward vernal equinox,
  +Z toward north celestial pole), `vx`,`vy`,`vz`, `con` constellation,
  `comp`/`base` multiple-system links, `lum` (luminosity, × solar).
  Note: **no mass and no temperature column** — the pipeline derives both
  from spectral type (see §1.6).

#### What the real file actually contains (counted 2026-11-04)

The v4.4 file was downloaded and counted directly for this document:

| Measure | Value |
|---|---|
| Rows | 119,614 |
| Rows with a proper name | 549 |
| Rows with a spectral type | 116,566 (97.5%) |
| Rows with placeholder distance (≥ 100,000 pc = indeterminate) | 10,224 |
| Rows with a usable distance | 109,390 |
| Median usable distance | 194 pc (633 ly) |
| 90th percentile distance | 513 pc |
| 99th percentile distance | 885 pc |
| **Maximum usable distance** | **990 pc (3,230 ly)** |
| Stars within 10 pc / 25 pc / 50 pc / 100 pc | 323 / 3,071 / 8,738 / 24,693 |

**The honest headline: HYG's real 3D positions live entirely inside a
~1 kpc (3,260 ly) sphere around the Sun.** That is the "entire known map"
in the sense of named, measured, individual stars — and it is roughly
3% of the galaxy's diameter. Everything outside that sphere has to come
from Gaia queries or statistical generation (§1.4, §1.6). This is a data
fact, not a design problem: the design (§3, §6) turns it into a feature —
everyone starts in the real neighbourhood; the deep galaxy is frontier.

### 1.2 AT-HYG — the Gaia-updated successor (the ~1M-star option)

- **What it is.** Astronexus' AT-HYG merges Augmented Tycho (Tycho-2) with
  Gaia DR3 and the HYG sources. Per the project page (fetched 2026-11-04,
  https://codeberg.org/astronexus/athyg): **over 2.5 million stars**,
  complete to about V = 11–11.5; **~99% have Gaia DR3 distances, ~92%
  have full 3D velocities**. Current version v4.0. License CC BY-SA 4.0.
- **HYGLike subset:** 118,971 stars — the HYG star set with Gaia DR3
  distances/velocities folded in. This is the drop-in upgrade path if
  HYG's Hipparcos-era distances are judged too rough. (HYG repo front
  page, https://codeberg.org/astronexus/hyg)
- **UNVERIFIED:** the AT-HYG full-file size and exact row count. The
  repo names the file `data/athyg_40.csv`; the direct download URL tried
  for this document returned 404, so no size is claimed here. S0 must
  fetch the real file and count it before the 1M-star mode is scoped.

### 1.3 Gaia DR3 — the deep source

- **Scale.** Gaia DR3 (released 13 June 2022) covers **≈ 1.8 billion
  sources**. (ESA/DLR release coverage:
  https://www.dlr.de/en/latest/news/2022/02/20220613_one-step-closer-to-understanding-the-milky-way ;
  catalogue overview: https://en.wikipedia.org/wiki/Gaia_DR3)
- **Access.** Free, no key, via the Gaia Archive TAP service
  (ADQL queries, CSV/VOTable out) at https://gea.esac.esa.int — the same
  TAP pattern as the Exoplanet Archive below. Bulk subsets are a query,
  not a download of the whole release.
- **The verified nearby subset — GCNS.** The Gaia Catalogue of Nearby
  Stars (from EDR3) is a cleaned sample of **331,312 objects within
  100 pc**, estimated ≥ 92% complete down to spectral type M9, ~9%
  contamination from beyond 100 pc handled probabilistically.
  (Gaia Collaboration et al. 2021, A&A 649, A6:
  https://www.researchgate.net/publication/346879729_Gaia_Early_Data_Release_3_The_Gaia_Catalogue_of_Nearby_Stars ;
  also https://en.wikipedia.org/wiki/Gaia_DR3)
- **Mid-range anchor.** A published Gaia DR3 kinematic study counts
  **24,789,061 stars within 4 kpc of the Sun with full six-dimensional
  (position + velocity) data** — i.e. tens of millions of real stars exist
  in Gaia within a few kpc, far more than any game table needs.
  (https://arxiv.org/html/2412.14236v1)
- **Precision reality.** Gaia is an optical astrometry mission with
  parallax precision of order ~20 microarcsec for bright stars
  (https://vectree.io/pdf/c/astrometry). Distance error grows linearly
  with distance: even for bright tracers, parallax uncertainty stays
  ≤ 10% only out to ~3 kpc in the galactic plane
  (https://resolve-he.cambridge.org/core/services/aop-cambridge-core/content/view/06805CAD8AD37D7700D4ACB48F0E14C9/S1743921323002545a.pdf/galactic_astrometry_with_vlbi.pdf).
  Faint stars are worse — a G ≈ 20 star reaches 10% distance error within
  a few hundred pc. Rule of thumb used in this design: **individual-star
  positions are trustworthy to ~1 kpc for the full population, usable to
  ~3 kpc for bright stars, and statistical beyond that.**
- **UNVERIFIED:** the exact row count of a "stars within 1 kpc" TAP
  query. It is certainly in the millions (interpolating GCNS's 331k
  within 100 pc and the 24.8M within-4-kpc sample), but no verified count
  is stated here; S0 runs the query and records the real number.

### 1.4 How far the real map actually reaches — and where fill begins

Three separate limits, stated plainly:

1. **Parallax limit (above).** Beyond ~1–3 kpc, individual distances get
   fuzzy fast. There is no catalog — Gaia included — with good
   star-by-star 3D positions across the whole 30 kpc disk.
2. **Dust obscuration.** Gaia observes in optical light. In the galactic
   plane, and especially toward the galactic centre, dust dims and
   reddens stars below detection, so Gaia DR3 is measurably incomplete
   exactly where the galaxy is densest
   (https://arxiv.org/html/2412.14236v1). NASA's own framing for the
   Roman telescope's galactic-plane survey: we have "a very incomplete
   view of what the other half of that Milky Way looks like beyond the
   galactic center," and Gaia mapped its ~1 billion+ stars in 3D
   "largely within about 10,000 light-years" (~3 kpc)
   (https://www.scienceaq.com/Article/Astronomy/156633.html).
3. **The far side is unmapped, full stop.** The galactic centre is
   ~8.2 kpc (~26,700 ly) away; the disk is ~100,000 ly (~30 kpc) across.
   Star-by-star positions on the far side of the centre effectively do
   not exist in any public catalog. Any game claiming otherwise is
   inventing them — which is fine, as long as it's honest generation
   (§1.6), not dressed up as data.

**Working scale model for the game:**

| Zone | Radius from Sun | Content | Source |
|---|---|---|---|
| The Neighbourhood | 0–100 pc (326 ly) | Complete real stars incl. faint dwarfs | GCNS / HYG |
| The Mapped Region | 100 pc – 1 kpc | Real stars, good positions | HYG (109,390 usable) |
| The Bright Frontier | 1–3 kpc | Real bright stars, rougher distances | AT-HYG / Gaia TAP subset |
| The Deep Galaxy | beyond ~3 kpc to the disk edge (~15 kpc from centre) | Statistical fill: density field + on-demand deterministic generation | Galaxy model (§1.6) |

### 1.5 NASA Exoplanet Archive — the real planets

- **Current counts (snapshot 2026-10-27, the freshest dated third-party
  count found): 6,451 confirmed planets in 4,847 planetary systems**,
  tabulated from the archive's Planetary Systems Composite Parameters
  table (`pscomppars`). (https://exoplanets.vallis.info/en/index.html)
  Corroborating snapshots: 6,366 planets on 2026-09-16 and 6,445 table
  entries on 2026-10-08
  (https://theuniverseepisodes.com/how-do-astronomers-find-exoplanets/ ,
  https://martianalpha.com/blog/naked-eye-stars-with-exoplanets).
  Treat "~6,400–6,500 and growing ~250/yr" as the planning number; S0
  pulls the live count.
- **Access.** Public, no API key. IVOA **TAP service**:
  `https://exoplanetarchive.ipac.caltech.edu/TAP/sync?query=...&format=csv`
  with ADQL (SQL-like) queries; also interactive-table CSV downloads.
  (Endpoint and example queries:
  https://www.aiobservatory.me/exo-terminal/index.html ; archive
  architecture paper: https://www.alphaxiv.org/audio/2506.03299v1)
- **Tables.** `ps` (Planetary Systems — one row per planet, default
  parameter set, ~36,000 rows including all published solutions) and
  `pscomppars` (Composite — one row per planet, best/composite values).
  **The game uses `pscomppars`, filtered to one row per planet.**
- **Fields the game needs.** Host: `hostname`, `sy_snum` (stars in
  system), `sy_pnum` (planets), `sy_dist` (pc), host `ra`/`dec`,
  `st_spectype`, `st_teff`, `st_mass`, `st_rad`. Planet: `pl_name` /
  `pl_letter`, `pl_orbper` (days), `pl_orbsmax` (AU), `pl_rade` /
  `pl_radj` (radius), `pl_bmasse` / `pl_masse` (mass), `pl_eqt`
  (equilibrium temperature), `pl_insol` (insolation), `disc_year`,
  `discoverymethod`. Caveat carried into the design: many fields are
  null for many planets (mass is often a minimum, M·sin i); the import
  fills gaps from the deterministic generator, flagged per-planet as
  *measured* vs *filled*.
- **Matching caveat (honest).** Most exoplanet hosts are faint Kepler /
  TESS field stars that are **not in HYG**. The pipeline therefore does
  not rely on name matching: hosts are placed from the archive's own
  `ra`/`dec`/`sy_dist`, cross-matched to the star table by position
  (nearest within a small tolerance), and any unmatched host is *added*
  to the star table as a real row sourced from the archive. Every real
  planetary system ends up in the game at its real location; no real
  system is dropped for failing to cross-match.

### 1.6 Recommended data pipeline

An offline build step (run once per data refresh, not at game launch)
producing one versioned game star table:

1. **Ingest HYG v4.4** (CSV). Drop the 10,224 placeholder-distance rows.
   Rotate equatorial XYZ → galactic XYZ with the standard J2000 rotation
   matrix; convert pc → ly (× 3.26156). Sun at origin.
2. **Optionally upgrade to AT-HYG / HYGLike** for Gaia DR3 distances on
   the same star set (same pipeline, better `dist`). Decide at S0 after
   both are in hand — the game table schema is identical either way.
3. **Derive missing physics.** HYG has luminosity and spectral type but
   no mass/temperature: derive effective temperature from spectral class
   via a fixed lookup (O 30,000 K … M 2,400 K, interpolated by subclass),
   mass from a main-sequence mass–luminosity relation (L ∝ M^3.5).
   Every derived value is flagged `derived`, never presented as measured.
4. **Merge exoplanets.** TAP-pull `pscomppars` → group by host →
   position-match or insert host rows → attach planet lists to star ids.
5. **Galaxy model for the deep field.** Beyond the catalog volume the
   game does **not** store stars. It stores a density model: exponential
   disk (scale length ~2.6 kpc, thin-disk scale height ~300 pc, thick
   disk ~900 pc), central bulge/bar, spiral-arm density modulation, and
   a metallicity gradient (centre richer). When a region is first
   surveyed, its systems are generated deterministically from
   (galactic coordinates, game seed) so every player and every reload
   sees the same far side. Generated stars get spectral types drawn from
   a standard initial mass function, so the fill is statistically the
   same galaxy the catalogs sample nearby.
6. **Output format.** One binary table (little-endian struct-of-arrays)
   + a JSON sidecar for names/designations. Versioned and hashed; the
   build records catalog versions and pull dates in a `SOURCES.md`.

**Game star record (48 bytes/star, fixed):**

| Field | Type | Bytes |
|---|---|---|
| id | u32 | 4 |
| x, y, z (ly, galactic frame) | 3 × f32 | 12 |
| abs. magnitude | f32 | 4 |
| B−V colour | f32 | 4 |
| effective temp (K, measured or derived) | f32 | 4 |
| mass (solar, measured or derived) | f32 | 4 |
| spectral class (enum O B A F G K M + other) | u8 | 1 |
| flags (named / has-real-planets / generated / multiple) | u8 | 1 |
| exoplanet list offset (0 = none) | u32 | 4 |
| name string-table offset | u32 | 4 |
| padding / reserved | — | 6 |

**Table sizes (estimates from the 48 B record above):**

| Stars | Binary table | + names sidecar (typical) |
|---|---|---|
| 119,614 (HYG) | ≈ 5.7 MB | + ~2 MB |
| 331,312 (GCNS volume) | ≈ 15.9 MB | + ~4 MB |
| 1,000,000 | ≈ 48 MB | + ~12 MB |
| 2,500,000 (AT-HYG full) | ≈ 120 MB | + ~30 MB |

All trivially shippable. The default game ships the HYG table (~120k);
the ~1M mode is a data option, not a different game (§7).

---

## §2 Core loop & time model

**The loop, in one sentence:** survey real star systems within reach →
found colonies where the planets allow → build each system up and keep it
supplied (above all with fuel) → extend your range with depots and gates →
meet the other civilizations doing the same → trade or fight over the
systems that matter → repeat at a larger radius, for centuries of game
time.

### Time model — RULED: real-time with pause, 1× = real time (Adam, 2026-11-04)

**Adam's ruling:** real-time-with-pause, and at **1× speed one
real-world day equals one in-game day**; time scales up from there.
The galaxy at base speed is a slow, persistent place — voyages,
construction, and terraforming span real days to months unless the
player accelerates. Fleets crawl across real light-years while you
manage systems, and you pause exactly when a decision needs you.

- **Calendar.** In-game date in years + day-of-year. **1 tick = 1 game
  day.** A game year = 365 ticks. A starting campaign is expected to run
  150–400 game years.
- **Speeds.** Pause / **1× = 1 game day per real day** (Adam's ruling),
  then scaling up: ~1 day per real hour, ~1 day per real minute,
  ~1 day per real second (a game year in ~6 minutes), and a top gear
  (~10 days per second, a game year in ~37 s) for long waits. Speed is
  a UI control only; the sim is a pure function of elapsed ticks, so
  saves and replays are exact. Campaigns are played by moving up and
  down this ladder — 1× is the ambient, living-galaxy speed.
- **Offline progression — RULED by Adam 2026-11-04: full catch-up.**
  The galaxy lives while the game is closed. On load, a save advances
  by the **full** real elapsed time since it was saved — one game day
  per real day at the 1× baseline — with **no cap**, however long the
  absence. History happens unwatched: fleets arrive, colonies settle
  their months, and (from S3 on) AI civs expand and fight without the
  player present. Capped catch-up and frozen-while-closed were the
  alternatives considered and not chosen. No S1 code embodies this
  yet — the core is step-driven; the policy lands in S2 when save/load
  is wired into the frontend, which must also give the player a way
  to review what happened during the catch-up.
- **What a daily tick simulates** (only for *active* systems — colonized,
  owned, or contested; uncolonized systems cost nothing):
  - fleet movement along routes (position = departure + speed × days),
    fuel burn, arrivals and their orders;
  - construction queues advance (buildings, ships, gates);
  - colony growth accrues daily but **settles monthly** (see below);
  - supply consumption accrues daily (fuel stock draw-down), deliveries
    land on arrival ticks.
- **Monthly settlement (every 30 ticks).** Population growth applied,
  production and upkeep tallied, credits/energy/resource balances
  posted, supply-route efficiency recomputed, AI civs re-plan. Monthly
  settlement is where the economy's numbers move; the daily tick is
  where ships and construction move. This two-rate design is what keeps
  a 1,000-colony endgame cheap: ~1,000 monthly settlements is nothing;
  1,000 daily economy sims would also be fine, but monthly reads better
  in UI (budgets are monthly statements).
- **Events interrupt.** First contacts, declarations of war, colonies
  starving, gates completing: auto-pause (configurable per event class)
  at 1× and above.

Turn-based was considered and set aside by Adam's ruling (fleet
movement across real distances turns coarse, expansion races resolve
by turn order instead of arrival, and the map feels static).

## §3 Colonization & systems

### The pipeline: unknown → surveyed → claimed → colonized

1. **Unknown.** Every star exists on the map as a point. Unsurveyed, you
   see only what telescopes give for free: spectral class, magnitude —
   data the real catalog actually has. No planets shown.
2. **Surveyed.** A survey ship (or long-range sensor array, §8) spends
   time in range; on completion the system is revealed: planets (real
   ones per §1.5, generated ones per decision 4 — generated from the
   star's real spectral type/mass/temperature with the game seed, so a
   system's planets are fixed forever once generated), habitability per
   planet, resource traits. Survey state *is* the fog of war (§7).
3. **Claimed.** Surveyed systems within your logistics reach can be
   claimed (a flag, a beacon, a small upkeep). Claims are visible to
   other civs once they survey the same system — the raw material of
   border friction (§6).
4. **Colonized.** A colony ship (consumed on arrival) founds a colony on
   the system's best habitable planet. Colonizing an unclaimed system
   claims it; colonizing someone else's claim is a diplomatic incident
   or an act of war, their choice.

### The system-level model (decision 3)

One colonized system = one management unit. Planets appear as the
system's *traits*, not as separately managed colonies.

- **Population** (in millions, one number per system). Grows monthly:
  base rate × habitability × (food/supply satisfaction) × development
  modifier. Emigration drift toward your better systems when a system
  is miserable and a better one has room.
- **Habitability** (0–100%): the best planet's score, computed from its
  type, temperature band, atmosphere/gravity class — for real planets
  from measured radius/insolation/equilibrium temperature where the
  archive has them, generator-filled otherwise (flagged). Habitability
  caps comfortable population and scales growth and upkeep.
- **Development level** (0–10): the system's built-up-ness. Gates what
  can be built (a level-1 outpost cannot raise a shipyard or a gate),
  scales all output, and is raised by completed construction + time +
  population thresholds.
- **Specializations** (pick 1 primary at development 3, a second at 7):
  Industrial, Agricultural, Refinery (fuel), Research, Fortress,
  Trade Hub, Shipyard. Specialization multiplies the matching output
  and unlocks the matching top-tier buildings. This is the main
  per-system decision: with hundreds of systems, "what is this system
  *for*" must be answerable in one click and changeable at a cost.
- **Build queue.** Per-system queue (default length 3 + development
  bonus): buildings (one per slot class), orbital works (depot,
  shipyard, defence platforms, gate — §5), and ship construction at
  shipyard systems. Build costs in credits + strategic resources,
  durations in days.
- **Supply.** Every colony consumes supplies monthly; the binding one is
  **fuel** (§4). A system is supplied if a route (§4.3) connects it to a
  net-producing system within tanker range or gate reach. Unsupplied
  systems: growth stops, then population declines, then (at zero
  stored buffer) the colony is abandoned — abandonment is slow
  (months), telegraphed, and pausable-by-event, never a sudden death.
- **Storage buffers.** Each system stores a few months of each consumed
  resource, so a cut route is a crisis with a deadline, not an instant
  kill — and blockades become a real war tool (§6).

### Terraforming — RULED: late-game megaproject (Adam, 2026-11-04)

**DECISION FOR ADAM — recommendation: defer terraforming out of the
first playable game; include it in the design as a late-game technology
line (§8).** Rationale: habitability is the main thing that makes real
systems differ from each other and drives expansion choices; a
terraforming system that erases bad habitability erases that pressure.
As a *late, slow, expensive* project (decades per planet, top-tier tech)
it becomes a victory-lap reward instead of a bypass. The data model
supports it from day one (habitability is a mutable per-planet value
with a `natural` baseline stored beside it), so deferring costs nothing
later.

## §4 Economy & resources

Deliberately tight. Two currencies, five strategic resources, fuel first.

### 4.1 Currencies

- **Credits** — the universal medium: construction, upkeep, trade,
  diplomacy. Earned from population (taxes/trade) and exports; spent on
  everything.
- **Energy** — a *per-system* flow, not a stockpile: each system's
  generation (stars are good at this) vs consumption (buildings, gates,
  shipyards). A system in energy deficit runs its buildings at reduced
  efficiency; there is no galaxy-wide energy market in v1. (Keeps the
  economy legible: credits global, energy local.)

### 4.2 Strategic resources (stockpiled per system, moved by routes)

| Resource | Produced by | Consumed by | Why it exists |
|---|---|---|---|
| **Fuel** | Refinery systems (from gas giants / nebula traits), some planet traits | Every ship movement; gate operation upkeep | The resource the whole travel model turns on (decision 2) |
| **Alloys** | Industrial systems (mining traits) | Ship + gate + orbital construction | The build-stuff resource |
| **Supplies** | Agricultural systems | Colony upkeep/growth everywhere | The eat-stuff resource; blockades bite here |
| **Electronics** | Industrial + high-development systems | Research, sensors, gates, late ships | The advanced-goods gate on high tech |
| **Exotics** | Rare planet traits only (few % of systems) | Top-tier drives, gates, weapons | The resource worth fighting a war over — deliberately scarce and unevenly placed by the real/generated planet data |

### 4.3 Trade and supply routes

- **Internal supply routes.** Automatic once both endpoints are yours: a
  route is a path over (a) free-flight legs within tanker range or
  (b) gate hops. The route solver is a graph search over *your*
  infrastructure, recomputed monthly and on infrastructure change.
  Routes have a capacity (tankers/freighters assigned per system pair,
  abstracted as a route-level number) and move resources from surplus
  systems to deficit systems in priority order: fuel to fleets' home
  bases first, supplies to starving colonies before stockpiles.
- **Tankers are implied, not micro-managed.** You build *freight
  capacity* at shipyard systems and assign it to systems; the route
  layer moves abstract tonnage. (A visible-ships toggle for major
  routes is a polish item, not v1.)
- **Inter-civilization trade.** A trade agreement (§6) opens routes
  between named systems of the two civs — drawn on the map as real
  lines along the actual path (free-flight legs and gate hops). Both
  sides earn credits monthly proportional to route throughput × distance
  factor; **gate hops count double throughput** (gates multiply trade,
  per decision 2's "quicker travel"). Trade routes are severed by war
  and raidable (§6): a trade partner's gates become your supply lines'
  single points of failure, which is the intended tension.
- **Open markets.** At a Trade Hub system you may simply *buy* a
  resource deficit away with credits at a fluctuating galactic price —
  the pressure valve that keeps a bad map roll from ending a run, at a
  price that makes self-sufficiency (or a trade partner) clearly
  better.

## §5 Ships & fuel

### 5.1 Ship design — the range / payload / armament triangle

Ships are designed, not bought off a shelf (decision 2 says "a ship's
*designed* fuel range" — design is a game system, not flavour).

- **Hull classes:** Surveyor, Colony Ship, Freighter/Tanker, Frigate,
  Cruiser, Capital, Gate Builder (a one-purpose industrial ship).
  Classes fix slot budgets and base costs; designs are yours within a
  class.
- **Every design allocates its mass/volume budget across three pulls:**
  - **Fuel & drive** — tank capacity + drive efficiency together set
    the ship's **range in light-years** (the number that decides where
    it can go) and its **speed in ly/day** (how fast).
  - **Payload** — colony modules, cargo/tanker capacity, survey gear,
    troop/occupation modules, gate components.
  - **Armament & defence** — weapons, armour, shields, point defence.
- A design that maxes all three is impossible by construction (budget
  math, not a soft cap). Long-range explorers are fragile; warships are
  short-legged and live off depots and gates; colony ships are slow,
  huge, and helpless. **This triangle is the game's central strategic
  object** — it is what fuel range *means* as a mechanic.
- Designs are saved, named, versioned (refits upgrade a hull to a newer
  design at a shipyard, at cost and time). The AI designs by template +
  personality-weighted tweaks (§6), under identical budget rules.

### 5.2 Fuel mechanics

- **Consumption.** A ship burns fuel per light-year travelled, by design
  (drive efficiency). Moving *within* range of its current fuel load is
  free of micro-management: you order a destination; the UI shows the
  path (direct leg, or hops via your depots/gates/fuel stations), total
  burn, and arrival fuel. Orders beyond current fuel require a routed
  path through refuel points — the map answers "can it get there, and
  by what hops," not just "is it in range" (§7, range bubble + route
  preview).
- **Refuelling points.** Colonies with a depot building, dedicated
  fuel-station systems (a colony whose job is a tank farm), gates
  (gate stations stock fuel), and tanker ships (mobile refuel —
  rendezvous transfers, the expensive emergency option).
- **Stranded ships.** A ship that ends a leg with empty tanks (only
  possible via combat damage, a lost depot mid-route, or a deliberate
  one-way order the UI makes you confirm twice) is *stranded*: it can
  be refuelled by a tanker rendezvous, towed home at sublight-fiction
  speed (very slow, always possible, humiliating), or scuttled. Never
  silently deleted.
- **Fleets.** Ships group into fleets; a fleet moves at its slowest
  ship's speed and its effective range is its shortest-legged ship's
  range unless tankers are attached (tankers extend fleet range by
  sharing — the standard way war fleets operate away from gates).

### 5.3 Warp gates

- **Structure.** A gate is an orbital structure built at a developed
  system (development ≥ 6 + Gate Builder ship + large alloy/electronics
  cost + build time in years, not days — gates are megaprojects).
- **Pairing.** A gate has exactly one paired partner gate. The pair is
  chosen at completion of the second gate. Re-pairing is possible
  (months of downtime) — networks are designed, not automatic.
- **Transit.** Gate-to-gate travel takes 1 day regardless of distance,
  plus queueing: each gate pair has a **throughput capacity** (mass per
  day). A capital fleet may take days to trickle through; a colony
  convoy longer. Both gates burn fuel per transit from the *departing*
  system's stock (gates are fast, not free) and draw heavy energy.
- **Whose gates.** Your fleets may use an ally's gates only under a
  gate-access treaty (§6); neutral gates are closed gates. Trade routes
  (§4.3) may route through treaty partners' gates.
- **In war.** Gates are capturable (take the system, take the gate —
  intact if the system surrenders/occupied without a ground fight,
  §6) and destructible (orbital bombardment/sabotage — destroying a
  gate strands whatever depended on it, and the AI knows this). A gate
  whose partner is destroyed becomes an unpaired gate: useless until
  re-paired. Gate pairs are the map's arteries and its hostages.

---

## §6 Other races

### 6.1 How many, and where they start

**DECISION FOR ADAM — recommendation: 12 AI civilizations + the player
= 13, configurable 4–40 at game setup.** At galaxy scale fewer than ~8
makes the map feel empty for the first century; more than ~20 makes
early contact a lottery and dilutes diplomacy (you cannot have a
relationship with 35 empires). 12 is the default the design is tuned
around; the slider exists because Adam will want to try 40 once.

- **Homeworlds on real stars.** Every civ starts on a habitable planet
  around a real catalog star inside the Mapped Region (§1.4), with a
  generated-or-real habitable world guaranteed by setup (if the star's
  real/generated planets lack one, setup adjusts the best planet to
  habitable — flagged in setup notes; the galaxy's first lie, told
  openly, in service of everyone getting a fair start).
- **Placement fairness.** Homeworlds are chosen by a spacing algorithm:
  candidate G/K/M stars with habitable planets, minimum pairwise
  distance ≥ 250 ly, no homeworld within 100 ly of another, comparable
  local star density (nobody starts in a void or a cluster core).
  Everyone starts inside the ~1 kpc real-data sphere, so the early game
  is played entirely on *real* stars; the generated deep galaxy is
  where late-game expansion goes. The player's start is chosen by the
  same algorithm — no hand-placed Sol advantage (Sol is in the catalog
  and can be drawn like any other star; a "play from Sol" toggle is a
  setup option, default off... or on. Setup option either way).
- **Same rules.** AI civs survey, claim, colonize, design ships, burn
  fuel, and starve under identical mechanics (§§3–5). The only AI
  advantages are explicit difficulty knobs (e.g. +X% production,
  cheaper claims), listed in setup, defaulting to **zero at Normal**.
  No teleporting fleets, no free resources, no knowledge of unsurveyed
  systems (the AI's fog of war is simulated, not performed).

### 6.2 Personalities and agendas

Each race gets: a name/species generated from the seed (plus a
hand-written set of archetypes), and a personality vector — expansion,
aggression, trade affinity, xenophobia, honour (treaty-keeping) — drawn
from archetypes (Merchant League, Hive Expansionist, Honourable
Warriors, Isolationist Gardeners, Opportunist Raiders…) with per-game
jitter. Personality drives: what it claims, what it offers, when it
goes to war, and whether its treaties hold. Agendas are legible: the
diplomacy screen states *why* a civ likes/dislikes you in plain numbers
(border friction, competing claims, trade volume, shared enemies,
broken treaties). No hidden opinion black box.

### 6.3 Contact and diplomacy

- **First contact** happens when either side surveys a system the other
  owns, or fleets meet. Contact opens a channel: translation delay (a
  few months of research-flavoured waiting at first contact only), then
  full diplomacy.
- **The diplomacy set (v1, complete):** trade agreement (§4.3), gate
  access treaty, non-aggression pact, defensive alliance, research
  pact (small mutual research bonus while both honour it), claim
  recognition (settle a disputed system), tribute/demand, declare war,
  sue for peace (with terms: systems, credits, gate access, humiliate).
  Embargo is the midpoint: trade war without shooting.
- **Claims diplomacy.** Overlapping claims create *disputes* with a
  visible tension meter per pair of civs; disputes are the on-ramp to
  most AI wars, and settling them (cede, swap, pay) is the peacetime
  game at the border.

### 6.4 War at system level

- **Fleet combat (abstracted, resolved in-system).** When opposing
  fleets occupy a system and at least one is hostile: combat resolves
  in daily rounds while both remain — ship designs' armament/defence,
  numbers, admiral-less, deterministic from the game seed (replays
  agree). Outcomes: ships destroyed/damaged/retreated (retreat burns
  emergency fuel — a retreating fleet may strand itself, §5.2);
  orbital structures (depots, platforms, gates) can be targeted once
  the defending fleet is gone. The player watches a battle report and a
  map animation, not a tactical minigame — this is a management sim.
- **Invasion and occupation.** Ground strength is abstracted into the
  invading fleet's troop payload vs the system's garrison (development
  + Fortress specialization + defence buildings). Occupied systems
  produce at reduced output for the occupier, cost occupation upkeep,
  and generate resistance events until ceded in a peace treaty or held
  for a long integration period. Annexation is a peace-treaty act, not
  a capture act — occupation is leverage, treaties are law.
- **Gate warfare.** The intended strategic texture: cut a gate pair and
  an empire's rich core can be severed from its frontier; defend yours,
  raid theirs. Raiders without a declaration (privateers) exist as a
  deniable-aggression tool under embargo-level hostility, with
  attribution risk.
- **War exhaustion & peace.** Both sides accrue exhaustion from losses,
  occupations, and blockaded (unsupplied) colonies; exhaustion forces
  the AI to accept reasonable peace and pressures the player via
  stability penalties. Wars end in treaties, not annihilation —
  elimination is possible but should be a campaign's climax, not its
  default verb.

### 6.5 Victory — options for Adam

**DECISION FOR ADAM — pick a primary (the others stay as tracked
scores/achievements):**

| Option | Condition | Character |
|---|---|---|
| **A. Hegemony** | Control (own or allied) ≥ 40% of *colonized* systems galaxy-wide | Expansionist, clear end |
| **B. Gate Web** | Your gate network connects ≥ 60% of colonized systems; hold for 10 years | Infrastructure/builder win, fits decision 2 |
| **C. First Among Equals** | Highest score (population, development, tech, trade volume) at a fixed end year (default 300 years) | Sandbox-with-a-finish-line |
| **D. No victory — pure sandbox** | Play until you stop; score tracked | The colony-sim answer |

Recommendation: **ship all four as setup choices, default A**, because
different campaigns want different endings and the tracking code is the
same either way.

## §7 The 3D map

### 7.1 Rendering the galaxy

- **Stars are points, not models.** All stars render as GPU point
  sprites in one (or a few) instanced draw(s): position buffer =
  §1.6's struct-of-arrays. **119,614 stars = one draw call, ~6 MB of
  position/colour data.** The RTX 3060 will not notice this load; the
  CPU never touches per-star data per frame.
- **Appearance.** Point size from absolute magnitude (brighter =
  larger, with distance attenuation clamped so nearby stars don't
  balloon), colour from spectral class/B−V (blue-white O/B through
  orange K to red M), named stars get labels at local zoom. A soft
  galactic glow backdrop (the density field rendered as a faint volume
  sprite layer) makes the *generated* galaxy visible as structure
  without pretending individual far stars are real.
- **LOD tiers.**
  - *Catalog mode (default, ~120k):* all stars always drawn; labels
    and picking via spatial index.
  - *Survey-detail mode:* within the local camera region, surveyed
    systems gain icons (colony, gate, fleet, dispute markers).
  - *Extended mode (~1M, data option):* same pipeline, bigger buffer
    (~48 MB), plus magnitude-cutoff culling by zoom (at galactic zoom
    only stars above a brightness percentile draw — invisible
    individually anyway); 2.5M AT-HYG full remains a stretch goal, not
    a promise (its file is UNVERIFIED, §1.2).
- **Picking.** GPU-free: a uniform grid / k-d tree over star positions
  in the sim core answers "nearest star to this ray within tolerance"
  in microseconds. Selection shows the system card (survey state
  permitting).

### 7.2 Camera and overlays

- **Camera model: two regimes, one control scheme.** *Galactic view* —
  orbit/target/zoom around the galactic centre or any focus point,
  logarithmic zoom from 100,000 ly across down to ~50 ly. *Local view*
  (below ~50 ly across) — the same camera, now among individual systems
  with icons, routes, and fleets. No mode switch, no loading: zoom is
  continuous, LOD cross-fades. Bookmarks (Home, Capital, Front, custom)
  + "jump to system" search by real star name — searching "Tau Ceti"
  and flying there is a feature this game can offer and no fictional-map
  game can.
- **Overlays (toggleable layers):**
  - **Fuel-range bubble:** select a fleet → translucent sphere of its
    range from its current position *and* a reachable-set highlight
    (systems reachable with current fuel via your refuel network,
    computed by graph search — the honest version of a range ring).
  - **Gate network:** lines between gate pairs (yours solid, treaty
    partners' dashed, enemy gates appear when scouted), coloured by
    throughput saturation.
  - **Trade/supply routes:** animated flow lines along actual route
    paths (§4.3); red pulse on a route that is failing (deficit at the
    far end).
  - **Territory:** soft volumetric tint around clusters of owned
    systems (convex-ish blobs, not hard borders — space has no
    borders, only logistics), per-civ colour.
  - **Fog of war = survey state:** unsurveyed = bare star point;
    surveyed = planets known; owned/observed = live icons. Enemy
    movements are only shown where your sensors reach (§8) — otherwise
    last-known markers with an age stamp.

### 7.3 Performance budget (Adam's PC: RTX 3060 12 GB, i5-10400F, 32 GB)

| Load | Budget | Why it's fine |
|---|---|---|
| Star rendering, 120k | 1 draw call, ~6 MB VRAM, < 1 ms/frame | Point sprites; GPU-trivial |
| Star rendering, 1M extended | ~48 MB VRAM, magnitude-culled at zoom-out | Still one buffer |
| Sim daily tick (200 active systems) | < 5 ms | System-level aggregates only (§2) |
| Sim daily tick (2,000 active systems, late game) | < 50 ms, off the render thread | Monthly settlement carries the economy |
| Route/graph recompute (monthly or on change) | < 100 ms for a 2,000-system network | Graph search over owned infra only |
| Total RAM (1M-star mode, big save) | < 2 GB of the 32 GB | Tables are small; saves are deltas + state |

The binding constraint is **UI clarity at galactic scale**, not
performance. The budget above is the design's promise to itself; S0/S2
measure against it (§10).

## §8 Technology

Five fields, each tied to a decided system. ~4–6 techs per tier,
3 tiers sketched — a sketch, not a tree (the full tree is a balancing
document of its own, written during S2/S3, not now).

| Field | Drives | Example techs |
|---|---|---|
| **Propulsion & Fuel** | §5's triangle | Efficient Drives (+range), High-Energy Fuel R refining (+speed), Tanker Logistics (fleet fuel sharing), Antimatter Candle (late: range ×3, exotics-hungry) |
| **Gates & Infrastructure** | §§4–5 | Gate Construction, High-Throughput Gates, Rapid Re-Pairing, Orbital Industry (build speed), Deep-Space Depots |
| **Colonization & Life Support** | §3 | Orbital Habitats (colonize marginal worlds), Atmospheric Adaptation, **Terraforming I–III** (§3's deferred line lives here), Population Arcologies |
| **Sensors & Survey** | §§3, 7 | Fast Survey Arrays, Long-Range Telescopes (survey from adjacent systems), Stealth Detection, Deep-Field Mapping (reveal generated-region traits remotely) |
| **Weapons & Defence** | §6 | Point Defence, Capital Hulls, Planetary Shields, Gate Defence Grids, Occupation Pacification |

Research is per-civ, point-based, monthly: research output from
Research-specialized systems and scientists-as-buildings, spent down a
chosen tech. AI researches by personality-weighted priorities under the
same costs.

---

## §9 Engine / platform recommendation

**DECISION FOR ADAM — recommendation: an engine-agnostic simulation
core in Rust + a Godot 4 frontend. PC/Windows first.** The reasoning by
candidate:

- **The game's shape.** A data-heavy deterministic simulation (the real
  game), a point-cloud renderer (a solved problem everywhere), and a
  lot of list/panel UI. No physics, no skeletal animation, no
  bleeding-edge rendering features. Anything that makes the *engine*
  the risk is wasted risk.
- **Custom core + frontend split (recommended pattern, whichever
  languages).** The sim core — star table, economy, fleets, AI,
  save/load — is a standalone library with a headless CLI runner: a
  whole campaign can be simulated, balanced, and regression-tested
  with no graphics at all, exactly like Adam's other projects
  (Developmental-AI's protocol discipline, the drabbit pet's
  deterministic core). The frontend is a replaceable shell that renders
  core state and sends commands. This split is non-negotiable in this
  design; engines below are judged as *frontends + integration cost*.
- **Rust for the core (recommended).** Adam works in Rust already. The
  core wants: deterministic fixed-order math across a whole campaign
  (save/replay integrity), struct-of-arrays tables (cache-friendly,
  matches §1.6's binary format directly), and raw tick speed headroom
  for the 2,000-system endgame (§7.3). Rust gives all three with no
  garbage collector pausing a monthly settlement. Cost: slowest
  iteration speed of the options, and the Godot bridge is via GDExtension
  or a C ABI — real but bounded work.
- **Godot 4 as frontend (recommended).** Adam has current, verified
  Godot 4 experience (the animation studio: headless runs, real
  projects). Point-sprite rendering of 120k–1M stars is a shader +
  MultiMesh/RenderingServer exercise Godot handles fine; its Control
  UI system is well suited to management panels; it exports to Windows
  trivially; it's free with no royalties or account risk. Cost:
  GDScript is the path of least resistance for UI glue (fine — UI glue
  is not the sim), and very large Control trees need care.
- **Unity (the credible alternative).** C# core + Unity frontend in one
  language is the lowest-friction split, and Unity's point-cloud and UI
  story is strong. Against: engine licensing/account history, heavier
  editor, and Adam has less current Unity time than Godot. If Adam
  prefers one-language development, this is the honest second choice:
  C# core (still headless-testable via a console runner) + Unity.
- **Unreal 5 (not recommended).** Adam's UE5/C++ is real, but its
  strengths (cinematic rendering, physics, replication) are unused
  here, while its costs (editor weight, build times, UMG/Slate fighting
  spreadsheet-style UI) are paid daily. A point-cloud galaxy is custom
  work in every engine anyway. Wrong tool for a data game.
- **TypeScript/Electron (not recommended beyond prototyping).** Would
  prototype the map in a weekend (WebGL points are easy), but a
  centuries-long deterministic sim plus a possible 1M-star mode
  deserves a compiled core. Fallback only — the core split would let
  the Rust core compile to WASM behind it someday. Not v1.

**Platform:** Windows PC first (Adam's machine is the reference,
§7.3). The core split keeps Linux/Mac ports a frontend problem, not a
rewrite. **Single-player only in v1** — multiplayer is a different
game's worth of netcode and determinism constraints; the door is noted,
not opened.

## §10 Sliced build plan

House style: vertical slices, each independently verifiable, each
ending with something runnable and a written record. No slice starts
until Adam approves the plan (and, per §9, the engine ruling).

- **S0 — Data pipeline proof.**
  *Exists at the end:* the §1.6 pipeline as a runnable tool; the star
  table built from the real HYG v4.4 (+ live `pscomppars` pull with the
  day's real planet count recorded); a minimal viewer that renders the
  table in 3D and can **find and fly to Sol, list its neighbour stars
  with real names/distances, and click TRAPPIST-1 to show its real
  planets**. *Verified by:* row counts and spot-checks against the
  source catalogs (e.g. Proxima at 4.246 ly, 549 named stars present,
  placeholder rows excluded), the §7.3 frame budget measured on Adam's
  PC, and a `SOURCES.md` recording catalog versions, pull dates, and
  the previously UNVERIFIED items (AT-HYG file, 1 kpc Gaia count)
  resolved one way or the other.
- **S1 — Sim core: one civilization, headless.**
  *Exists:* the Rust core simulating a single civ end-to-end — survey,
  claim, colonize, grow, build, design ships within the §5 triangle,
  burn fuel, run out of fuel, starve a colony by cutting its route —
  driven entirely by a scripted/CLI harness, no graphics. AI hooks are
  stubs; the map is data only. *Verified by:* a scripted 200-year
  campaign completing deterministically (same seed → byte-identical
  final state hash), unit tests per system (§§3–5), tick-performance
  measured against §7.3 at 2,000 synthetic active systems.
- **S2 — Map + UI: the playable colonizer.**
  *Exists:* the Godot frontend on the S1 core — full 3D map (§7),
  system cards, build queues, ship designer UI, route/range overlays,
  save/load. One civ, no AI yet: a complete solo colonization game
  against distance and logistics. *Verified by:* Adam playing a real
  session on his PC (the first owner-hardware gate), save/reload
  mid-campaign integrity, frame budget re-measured in the real UI.
- **S3 — Other races + first contact.**
  *Exists:* AI civs (default 12, §6) placed by the fairness algorithm,
  expanding under identical rules; survey-based contact, diplomacy
  screen with legible opinion numbers, disputes over claims.
  *Verified by:* headless multi-civ campaigns (all-AI, 300 years,
  no crashes, no civ breaking the fuel rules in the logs), plus
  Adam-facing contact/diplomacy play in the S2 shell.
- **S4 — Trade & diplomacy depth.**
  *Exists:* inter-civ trade routes on the map (§4.3), gate-access
  treaties, alliances, embargoes, research pacts, peace terms with
  system cessions. *Verified by:* scripted treaty lifecycle tests
  (sign → honour → break → consequences), trade income reconciling
  against route throughput in a save's ledger, AI accepting/refusing
  deals for stated reasons.
- **S5 — War, gates, victory.**
  *Exists:* fleet combat, invasion/occupation, blockade effects,
  gate construction in anger (capture/destruction/re-pairing), war
  exhaustion and peace conferences, the §6.5 victory conditions as
  setup options, terraforming tech line (§3) if Adam approved it.
  *Verified by:* scripted war scenarios (gate cut isolates a region —
  assert its colonies begin starving on schedule), a full AI-vs-AI
  war concluding in a treaty, and Adam playing a war campaign.
- **Beyond S5 (named, not planned):** balance passes, extended 1M-star
  mode hardening, mod/save-sharing polish, the WASM toy. Each gets its
  own plan when it is real.

## §11 Open decisions for Adam

Everything in this document that is Adam's call, in one list, with the
document's recommendation beside each. The five founding decisions are
**not** here — those are made.

| # | Decision | Recommendation |
|---|---|---|
| 1 | Time model: real-time-with-pause vs turn-based (§2) | ~~**RTWP**, 1 tick = 1 day, monthly economy settlement~~ **RULED by Adam 2026-11-04: real-time with pause; at 1× speed one real-world day = one in-game day; time scales up from there.** |
| 2 | Terraforming: in the game at all, and when (§3) | ~~**Yes but late** — top-tier tech, decades per planet; data model supports it from day one~~ **RULED by Adam 2026-11-04: in the game as a late-game megaproject.** |
| 3 | AI race count default (§6.1) | ~~**12 AI + player**, slider 4–40~~ **RULED by Adam 2026-11-04: 12 AI + player default, slider 4–40.** |
| 4 | Victory condition default (§6.5) | ~~**Hegemony**, with Gate Web / score-at-end-year / pure sandbox as setup options~~ **RULED by Adam 2026-11-04: Hegemony default; Gate Web / timed score / pure sandbox as setup options.** |
| 5 | Engine & core language (§9) | ~~**Rust core + Godot 4 frontend**; Unity/C# the fallback if one language is preferred~~ **RULED by Adam 2026-11-04: Rust sim core + Godot 4 frontend.** |
| 6 | Starting data tier (§§1, 7): ship HYG ~120k only, or also build the ~1M extended table at S0 | ~~**HYG default**; pull the Gaia/AT-HYG subset during S0 anyway so the option is measured, not guessed~~ **RULED by Adam 2026-11-04: ship on HYG ~120k; build and measure the ~1M table during S0.** |
| 7 | "Play from Sol" toggle default (§6.1) | ~~Setup option either way; recommendation: default **on** for the first campaign experience (your first system should be *home*), random for later ones~~ **RULED by Adam 2026-11-04: default to Sol — the first campaign starts at home.** |

## What this document did not decide (deliberately)

- The full technology tree (§8 is a sketch) — a balancing document,
  written during S2/S3 against a playable economy.
- Ship-class numbers, build costs, decay/growth rates — all balance
  values are placeholders for S1's scripted campaigns to tune.
- Art direction beyond §7's functional rendering (star colours are
  data; UI skin is a later pass).
- Multiplayer — out of scope for v1 (§9), noted so its absence is a
  decision and not an oversight.

*Prepared 2026-11-04. Data claims verified against live sources on that
date and cited in §1; estimates are labelled as estimates, and the two
items that could not be verified are flagged UNVERIFIED in place rather
than smoothed over.*
