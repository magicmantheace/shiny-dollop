# Crawl — Autonomous Crawl & Broadcast Simulation Roadmap

## Status

**Pivot baseline:** `792af88a7c0cea6d8879ca773bf700672e6eaa0f`

**Inherited milestone:** LivingWorld v0.3 Slice 3 complete — deterministic simulation, persistent NPCs, history, save/load, API/dashboard, warfare/politics foundations, production, inventories, labor, and long-horizon validation.

The inherited LivingWorld roadmap is preserved in Git history and indexed at:

`docs/archive/ROADMAP_LIVINGWORLD_PRE_CRAWL.md`

This roadmap intentionally changes the project goal.

Crawl is **not an MMO**. Human users are spectators, followers, and viewers. The stars are autonomous simulated NPC crawlers.

The product goal is a continuously running fantasy crawl in which autonomous NPC contestants enter generated floors, explore, fight, cooperate, betray, adapt, gain equipment and abilities, survive or die, and build persistent histories. Humans can watch specific crawlers, follow the overall crawl, view live statistics, and consume automatically produced highlights, recaps, commentary, and character stories.

The project may take inspiration from the broad structure of serialized dungeon-crawl and reality-show fiction, but all production lore, terminology, characters, floor rules, monsters, visual identity, narration, and mechanics must be original to Crawl.

---

# 1. Product Definition

> **Crawl is an autonomous fantasy competition simulator that can also produce its own watchable entertainment.**

The core loop is:

```text
Create crawl
-> generate/select autonomous crawlers
-> initialize floor
-> crawlers explore and make decisions
-> encounters, combat, alliances, loot, injuries, rescues, betrayal, death
-> floor deadline / completion conditions
-> survivors progress
-> intermission / advancement
-> next floor
-> repeat until crawl resolution
-> archive crawl history
-> begin next crawl
```

Humans do not need to control a crawler for the product to function.

A successful run should be interesting even if nobody is watching live.

A successful viewer experience should allow someone to discover an NPC they care about and follow that NPC as though they were following a contestant, athlete, streamer, or reality-show participant.

---

# 2. Core Architectural Principle

The simulation and the media layer must remain separate.

```text
                    CRAWL ORCHESTRATOR
                           |
              +------------+------------+
              |                         |
        FLOOR / RULE ENGINE         CRAWL DIRECTOR
              |                         |
              +------------+------------+
                           |
                 DETERMINISTIC SIMULATION
                           |
          +----------------+----------------+
          |                |                |
      Crawlers         Encounters        Items/World
          |                |                |
          +----------------+----------------+
                           |
                   STRUCTURED EVENT LEDGER
                           |
          +----------------+----------------+
          |                |                |
      Replay Engine    Story Analysis   Spectator API
          |                |                |
          +----------------+----------------+
                           |
                    PRESENTATION LAYER
              +------------+------------+
              |            |            |
           Unreal       Web/App      Commentary
              |
        Cameras / Replays
              |
        Highlight Production
              |
      Clips / Recaps / Episodes
```

The authoritative simulation decides what actually happened.

The presentation system decides how to show it.

An AI-generated video can dramatize an event, but it must never become the canonical record of the event.

---

# 3. Non-Negotiable Rules

## 3.1 Deterministic authority

Authoritative outcomes must be deterministic or reproducible from a seed and recorded state.

This includes:

- movement,
- combat,
- damage,
- death,
- item ownership,
- progression,
- floor completion,
- party membership,
- spawned encounters,
- director interventions,
- inventory changes,
- relationship-state changes that affect future decisions.

## 3.2 Structured truth before prose

Every important event must exist as structured data before it becomes commentary, a recap, dialogue, or a video.

## 3.3 NPC autonomy first

A crawler should be capable of making meaningful decisions without an LLM call.

LLMs may later enrich:

- dialogue,
- internal monologue for presentation,
- commentary,
- recap prose,
- character interviews,
- flavor descriptions.

They must not be required for the crawler to survive, fight, choose a route, form a party, retreat, use an item, or make other authoritative real-time decisions.

## 3.4 Headless first

Do not begin serious Unreal production until an interesting crawl can happen without graphics.

## 3.5 Render only what must be rendered

The simulator may eventually track thousands or tens of thousands of crawlers, but the presentation layer should render only the crawlers and locations currently being watched, replayed, or promoted to high-detail simulation.

## 3.6 No GitHub Actions dependency

Continue the inherited local-validation approach. The project must not require GitHub Actions minutes for normal development or validation.

---

# 4. What We Keep From LivingWorld

The pivot should reuse proven systems instead of starting from zero.

## Keep and adapt

- deterministic seeded simulation,
- world/entity IDs,
- save/load persistence,
- structured historical events,
- API architecture,
- administrative dashboard,
- persistent named NPC model,
- aging/identity/family data where useful for backstory,
- relationship foundations,
- combat/warfare concepts that can be reduced to individual-scale combat,
- inventory/resource accounting,
- production/material-flow code where useful for crafting, consumables, food, or floor economies,
- validation/invariant infrastructure,
- long-horizon and fast-forward benchmarking patterns.

## Freeze unless Crawl later proves a need

Do not continue building these simply because they were on the old roadmap:

- deep kingdom treasury simulation,
- full settlement markets,
- trade-route economics,
- property inheritance systems,
- detailed civic institutions,
- full religious institution simulation,
- long-form kingdom lifecycle simulation,
- MMO player networking,
- player login/account gameplay infrastructure.

## Optional future reuse

The inherited continent simulator can later become a **crawler-origin generator** or pre-crawl history generator. A contestant could arrive with a family, homeland, culture, military history, rival, profession, or past trauma generated by the older systems.

That is optional. It must not block the autonomous crawl MVP.

---

# 5. Development Workflow

Every slice should follow this sequence:

1. define authoritative data model,
2. define deterministic rules,
3. implement simulation behavior,
4. emit structured events,
5. expose relevant metrics/API state,
6. add focused regression tests,
7. add invariant checks,
8. run local validation,
9. run targeted multi-seed simulation where emergence matters,
10. merge only after the slice acceptance gate passes.

The project should prefer many small validated slices over giant feature branches.

---

# 6. v0.4 Slice 1 — Crawl Domain Model

Create the first authoritative crawl-specific entities.

## Required entities

### Crawl

Fields should include at minimum:

- crawl ID,
- seed,
- status,
- start time,
- current floor,
- ruleset ID/version,
- starting crawler count,
- surviving crawler count,
- eliminated crawler count,
- crawl-wide modifiers,
- history/event references.

### Floor

Track:

- floor number,
- seed,
- theme/environment,
- start time,
- deadline,
- completion rules,
- advancement rules,
- zones,
- safe areas,
- danger level,
- director budget,
- encounter budget,
- active crawler count,
- floor status.

### Zone / Room / Location

The first implementation can be graph-based instead of physically rendered.

Track:

- adjacency,
- traversal cost,
- visibility,
- hazards,
- exits,
- encounter slots,
- loot/resource nodes,
- environmental tags,
- capacity where relevant.

### Crawler participation state

A persistent NPC may exist outside a crawl, but participation state should track:

- crawl ID,
- current floor,
- current location,
- alive/dead/eliminated/advanced state,
- health/resources,
- progression,
- current party,
- current objective,
- floor-specific statistics.

### Acceptance gate

A seeded crawl with multiple floors can be created, saved, reloaded, advanced, completed, and archived without graphics or manual database edits.

---

# 7. v0.4 Slice 2 — Crawler Identity, Traits, Skills, and Needs

Convert persistent NPCs into contestants capable of distinct behavior.

## Traits

Examples:

- courage,
- caution,
- aggression,
- curiosity,
- greed,
- loyalty,
- empathy,
- patience,
- sociability,
- suspicion,
- competitiveness,
- risk tolerance.

Traits should be continuous values rather than simple labels where practical.

## Core survival state

Track:

- health,
- stamina/energy,
- hunger or resource pressure if enabled by the ruleset,
- injuries,
- status effects,
- morale/stress,
- perceived danger,
- equipment readiness.

## Skills

Initial skills can include:

- melee combat,
- ranged combat,
- defense,
- perception,
- stealth,
- navigation,
- medicine,
- traps,
- negotiation,
- leadership,
- scavenging,
- magic or ability-use categories.

## Preferences and aversions

Crawlers should be capable of preferring or avoiding:

- combat,
- crowds,
- enclosed spaces,
- specific enemy categories,
- darkness,
- magical hazards,
- unknown rooms,
- high-risk loot,
- certain personality types.

### Acceptance gate

Given identical circumstances, crawlers with meaningfully different traits and skills should select measurably different actions across deterministic test scenarios.

---

# 8. v0.4 Slice 3 — Autonomous Decision Engine

This is one of the most important slices in the project.

Crawlers must become authoritative autonomous agents.

## Decision architecture

Start with a bounded utility/goal system rather than an LLM loop.

Possible layers:

```text
Needs / threats
-> candidate goals
-> candidate actions
-> utility scoring
-> feasibility checks
-> action selection
-> execution
-> outcome observation
-> memory update
```

## Initial goals

Examples:

- survive,
- reach an exit,
- find safety,
- obtain healing,
- find food/resources,
- improve equipment,
- explore,
- avoid an enemy,
- kill an enemy,
- help an ally,
- rescue another crawler,
- recruit a companion,
- leave a dangerous party,
- pursue a grudge,
- investigate an unusual event,
- wait for a better opportunity.

## Bounded planning

The crawler should reason only as far ahead as needed for useful behavior.

Do not begin with expensive unrestricted planning.

Support:

- immediate reactive actions,
- short-horizon plans,
- plan interruption,
- retreat/replanning,
- action cooldowns,
- risk estimation,
- incomplete information.

### Acceptance gate

A headless scenario with at least 100 crawlers must run without manual intervention while crawlers independently explore, seek safety/resources, retreat, cooperate, and make mistakes.

---

# 9. v0.4 Slice 4 — Perception, Knowledge, and Uncertainty

Crawlers should not have omniscient access to simulation state.

## Perception

A crawler may know information because they:

- can currently see it,
- heard it,
- previously visited it,
- were told by another crawler,
- inferred it,
- saw an announcement,
- found a map/item,
- experienced it previously.

## Knowledge state

Track confidence and age where useful.

Examples:

- room believed safe,
- enemy last seen here,
- rumored exit location,
- suspected trap,
- crawler believed trustworthy,
- item believed valuable.

Incorrect beliefs are allowed.

### Acceptance gate

Two crawlers in the same floor can rationally choose different actions because they possess different information.

---

# 10. v0.4 Slice 5 — Memory, Relationships, and Social Consequences

Adapt the old memory/reputation concept directly into contestant drama.

## Event-based memories

Important memories should reference real event IDs.

Suggested fields:

- event ID,
- subject crawler/entity,
- event type,
- emotional interpretation,
- importance,
- confidence,
- timestamp/floor,
- decay rate,
- unresolved/resolved state.

## Relationship dimensions

Avoid a single friendship number.

Possible dimensions:

- trust,
- affection,
- respect,
- fear,
- resentment,
- gratitude,
- rivalry,
- familiarity,
- perceived reliability.

## Social consequences

Relationships should influence actual decisions including:

- helping,
- healing,
- sharing loot,
- forming parties,
- abandoning someone,
- taking risks for someone,
- withholding information,
- forgiving a mistake,
- seeking revenge,
- trusting warnings,
- leadership acceptance.

### Acceptance gate

The simulator must be able to produce a multi-floor relationship arc in which earlier events measurably change later crawler decisions without scripted story logic.

---

# 11. v0.4 Slice 6 — Floor Generation and Traversal

Build procedural crawl spaces as simulation graphs first.

## Floor generation

A floor should generate:

- entrance locations,
- advancement/exit locations,
- safe zones,
- ordinary zones,
- high-danger zones,
- encounter locations,
- resource/loot locations,
- hazards,
- shortcuts,
- chokepoints,
- hidden or conditional paths.

## Themes

Themes should affect rules, not only labels.

Examples:

- visibility,
- environmental damage,
- movement cost,
- healing availability,
- encounter composition,
- resource abundance,
- safe-zone spacing,
- map topology.

## Navigation

Crawlers need deterministic pathfinding constrained by what they actually know.

### Acceptance gate

Multiple seeded floors should generate valid traversable layouts with different strategic properties, and at least one valid advancement path must exist unless the ruleset intentionally allows impossible/failure floors.

---

# 12. v0.4 Slice 7 — Individual Combat, Injury, and Death

The inherited warfare model is strategic; Crawl needs deterministic individual and small-group combat.

## Combat foundation

Track:

- attack timing,
- range,
- accuracy,
- defense/evasion,
- damage,
- armor/resistance,
- stamina/resource costs,
- status effects,
- positioning abstraction,
- retreat feasibility,
- target selection.

## Injury

Not every fight should reduce only a generic HP bar.

Support bounded injuries such as:

- bleeding,
- impaired movement,
- reduced accuracy,
- reduced stamina,
- temporary incapacitation.

## Death

Death must be authoritative, persistent, historically queryable, and replayable.

### Acceptance gate

Combat is deterministic under identical seed/state, supports group encounters and retreat, cannot duplicate or lose items through death handling, and produces complete structured combat events.

---

# 13. v0.4 Slice 8 — Items, Equipment, Loot, and Consumables

Convert the inherited inventory/material accounting into contestant-scale ownership.

## Item model

Track:

- unique/non-unique identity,
- category,
- rarity,
- stats/effects,
- durability if used,
- requirements,
- ownership,
- location,
- provenance/history for important items.

## Loot acquisition

Loot can come from:

- encounters,
- caches,
- exploration,
- crafting,
- trading,
- gifts,
- dead crawlers,
- floor rewards,
- director events.

## Item decisions

Crawlers should evaluate whether to:

- equip,
- consume,
- keep,
- discard,
- trade,
- give away,
- hide,
- save for later.

### Acceptance gate

Every item has exactly one valid authoritative location/owner state, and crawler equipment decisions react to build, needs, risk, and relationships.

---

# 14. v0.4 Slice 9 — Progression, Abilities, and Builds

Create an original progression system suited to autonomous contestants.

The exact fiction can change later; the backend should support:

- experience/progression currency,
- skill improvements,
- unlockable abilities,
- passive modifiers,
- equipment synergy,
- build specialization,
- floor rewards,
- meaningful tradeoffs.

Crawlers should choose advancement options according to personality, experience, party needs, and their existing build rather than always selecting the mathematically highest immediate value.

### Acceptance gate

After several floors, crawlers from identical starting templates can diverge into meaningfully different builds because of different experiences and decisions.

---

# 15. v0.4 Slice 10 — Parties, Alliances, and Group Behavior

Parties should be emergent social structures, not static team assignments.

Support:

- invitations,
- joining,
- refusal,
- leadership,
- informal alliances,
- temporary cooperation,
- loot-sharing expectations,
- role selection,
- disagreement,
- splitting,
- expulsion,
- abandonment,
- reunion.

## Group decisions

A party needs bounded methods for:

- selecting routes,
- deciding whether to fight,
- distributing resources,
- choosing who receives healing,
- deciding whether to rescue someone,
- reacting to a dangerous member.

### Acceptance gate

Across multi-seed runs, parties must form and dissolve for explainable reasons and should not converge into one universal optimal party size/strategy.

---

# 16. v0.4 Slice 11 — Encounters, Enemies, Traps, and Hazards

Create a reusable encounter framework.

## Encounter types

- ordinary hostile encounters,
- elite encounters,
- boss encounters,
- traps,
- environmental hazards,
- resource dilemmas,
- social dilemmas,
- timed threats,
- pursuit encounters,
- rescue opportunities,
- optional high-risk/high-reward areas.

## Enemy behavior

Enemies should use deterministic bounded AI appropriate to their type.

The system should support enemy archetypes without requiring bespoke code for every creature.

## Encounter contracts

Each encounter should expose:

- trigger,
- participants,
- difficulty estimate,
- possible outcomes,
- rewards,
- failure consequences,
- event hooks,
- cleanup rules.

### Acceptance gate

A floor can run end-to-end with varied encounter types and no encounter can leave invalid crawler, item, or location state after resolution.

---

# 17. v0.4 Slice 12 — Floor Deadlines, Advancement, and Intermission

Create the actual crawl rhythm.

## Floor lifecycle

```text
prepare
-> open
-> active
-> deadline warning
-> closure
-> advancement resolution
-> intermission
-> next floor
```

## Advancement

Support rules such as:

- reach an exit,
- complete an objective,
- survive until a condition,
- obtain a requirement,
- choose between advancement routes.

## Intermission

Possible actions:

- heal,
- spend progression,
- change equipment,
- inspect results,
- reconnect with allies,
- process floor rewards,
- receive announcements/information.

### Acceptance gate

A headless multi-floor crawl can eliminate non-advancing crawlers, progress survivors, preserve relationships/inventory/history, and enter the next floor without manual repair.

---

# 18. v0.4 Slice 13 — Crawl Director

The Director manages pacing and challenge but does not override simulation truth.

## Director responsibilities

- choose from allowed encounter/event templates,
- spend floor-specific intervention budgets,
- prevent long stagnation,
- respond to population distribution,
- respond to overperforming/underperforming groups,
- create opportunities rather than scripted outcomes,
- vary pacing,
- schedule announcements or rule events,
- promote underused areas,
- maintain floor identity.

## Director restrictions

The Director must not arbitrarily:

- set a crawler's health to zero,
- invent/remove inventory outside defined rules,
- teleport contestants without an allowed event,
- override combat outcomes,
- violate floor constraints.

If an LLM is later used for Director suggestions, its proposals must be validated by deterministic rules before execution.

### Acceptance gate

The Director can alter the shape and pacing of seeded runs while all interventions remain valid, budgeted, event-recorded, and reproducible.

---

# 19. v0.4 Slice 14 — Semantic Event Ledger

This slice is a prerequisite for the future media system and should be treated as core infrastructure.

Every meaningful event should contain enough structured information to answer:

- what happened,
- when,
- where,
- who was involved,
- what caused it,
- what state changed,
- how important it might be,
- what earlier events it references.

## Event classes

Examples:

- location entered,
- item discovered,
- item transferred,
- injury,
- healing,
- combat start/end,
- near death,
- death,
- rescue,
- party join/leave,
- betrayal/abandonment,
- alliance,
- boss encounter,
- rare reward,
- floor advancement,
- deadline elimination,
- major Director event,
- relationship threshold crossing.

## Event metadata

Add fields suitable for downstream analysis:

- importance score,
- rarity score,
- danger level,
- reversal flag,
- relationship impact,
- audience-interest tags,
- causal parent IDs,
- state snapshot/replay checkpoint reference.

The score should be explainable and recalculable rather than an opaque LLM judgment.

### Acceptance gate

For every crawler death, rescue, major betrayal, boss outcome, or advancement, the event ledger can reconstruct the preceding cause chain and authoritative state changes.

---

# 20. v0.4 Slice 15 — Headless Crawl MVP Gate

**Do not start serious Unreal work before this gate passes.**

The first major project milestone is a completely headless autonomous crawl.

## Required demonstration

Run at least:

- 100 autonomous crawlers,
- 3 or more floors,
- generated layouts,
- exploration,
- combat,
- loot,
- progression,
- parties,
- relationship changes,
- injuries/deaths,
- floor deadlines,
- advancement,
- Director interventions,
- structured event history.

## Success criteria

The run should produce at least several events that are interesting when read as structured history, for example:

- an unexpected rescue,
- a party split,
- a crawler surviving a low-probability situation,
- a meaningful death,
- a rivalry,
- a reunion,
- a notable boss victory or failure.

These do not need to occur in every seed.

The important requirement is that the systems make such events possible without scripts.

---

# 21. v0.5 Slice 16 — Simulation Detail Tiers and Scale

The project cannot afford full high-frequency cognition for every crawler at all times.

Create explicit simulation tiers.

## Suggested tiers

### Tier A — Focused

Used for watched, replayed, or immediately important crawlers.

- highest decision frequency,
- detailed combat/perception,
- presentation-ready state.

### Tier B — Active

Nearby or event-relevant crawlers.

- full authoritative decisions,
- reduced update frequency where safe.

### Tier C — Remote

Important but currently unwatched crawlers.

- abstract movement/encounter resolution,
- lower-frequency planning.

### Tier D — Background

Low-interest population between important interactions.

- coarse travel/activity simulation,
- promotion when an important condition occurs.

Promotion/demotion must preserve continuity.

### Acceptance gate

The same crawler cannot gain or lose impossible resources/state when switching detail tiers, and promotion into detailed simulation produces a valid continuation rather than a regenerated character.

---

# 22. v0.5 Slice 17 — Multi-Seed Crawl Validation and Performance

Move from one interesting seed to statistically useful testing.

## Validation matrix

Start with:

- 20 seeds x 100 crawlers x 3 floors.

Then expand to:

- 20 seeds x 1,000 crawlers x 5 floors.

Later stress targets can move toward 10,000+ crawler populations if hardware permits.

## Track distributions

- survival rate by floor,
- deaths by cause,
- average party size,
- party formation/split frequency,
- encounter completion,
- retreat rate,
- item concentration,
- progression spread,
- build diversity,
- relationship changes,
- rescue frequency,
- Director interventions,
- deadlocks/stagnation,
- simulation time per in-world minute/hour,
- event volume,
- memory growth,
- save/load size and speed.

## Balance principle

Do not tune the simulation to guarantee drama.

Tune it to create conditions where meaningful interactions can emerge while the crawl remains mechanically valid.

### Acceptance gate

No seed may fail structural invariants, deterministic replay checks, or save/reload equivalence because the run became unusual.

---

# 23. v0.5 Slice 18 — Crawl Observatory Dashboard

Repurpose the inherited dashboard into a developer/spectator observatory.

## Required views

- crawl status,
- floor status,
- crawler population/survival,
- map/zone occupancy,
- active encounters,
- parties,
- crawler profile,
- inventory/build,
- relationships,
- memories,
- recent events,
- deaths,
- trending/interesting-event scores,
- Director interventions,
- performance telemetry.

The dashboard remains a debugging tool first.

### Acceptance gate

A developer can diagnose why a crawler made a major decision and trace the events/state that led to it without reading raw database rows.

---

# 24. v0.6 Slice 19 — Spectator API

Create a stable read-oriented API for human viewers and future clients.

## Endpoints/data streams should support

- current crawl,
- current floor,
- crawler directory/search,
- crawler profile,
- crawler current state,
- party state,
- crawler history,
- recent highlights,
- deaths/eliminations,
- leaderboard/statistics,
- trending crawlers,
- event stream,
- current location/encounter,
- replay metadata.

Separate public spectator state from internal authoritative state.

Do not leak hidden crawler knowledge, secret encounters, or Director state unless the viewing mode intentionally allows it.

### Acceptance gate

A completely separate client can follow one crawler in near real time using only documented spectator APIs.

---

# 25. v0.6 Slice 20 — Unreal Spectator Bridge

Unreal now enters the roadmap as a **renderer and virtual studio**, not an MMO client.

The first Unreal goal is intentionally small.

## First milestone

1. Unreal connects to the spectator/replay interface.
2. One test room/zone is represented visually.
3. A small set of crawler/enemy archetypes can be spawned.
4. Authoritative backend state drives their positions/actions.
5. Unreal does not decide combat results.
6. A camera can follow a selected crawler.

The backend remains authoritative.

### Acceptance gate

A viewer can watch one crawler traverse and complete a deterministic test encounter in Unreal while backend and rendered outcome remain synchronized.

---

# 26. v0.6 Slice 21 — Replay System

The project should not rely on continuous video recording of every crawler.

Build deterministic/authoritative replay data.

## Replay requirements

Support reconstruction from:

- periodic authoritative checkpoints,
- event/action logs,
- deterministic seeds,
- required animation/presentation hints.

The replay system should be able to request a window such as:

```text
30 seconds before Event 91822
through
60 seconds after Event 91822
```

and reconstruct the event for rendering.

### Acceptance gate

A selected combat/rescue/death sequence can be replayed repeatedly with the same authoritative outcome and relevant character/world state.

---

# 27. v0.6 Slice 22 — Automated Camera Director

Turn replays/live state into watchable footage.

## Camera modes

- crawler follow,
- over-the-shoulder,
- combat tracking,
- wide establishing shot,
- overhead tactical shot,
- party shot,
- enemy reveal,
- reaction close-up where assets permit,
- slow-motion replay for selected moments.

## Camera scoring

Camera choice can consider:

- active threat,
- number of participants,
- event importance,
- line of sight,
- obstruction,
- shot repetition,
- subject continuity.

Do not let camera logic affect simulation behavior.

### Acceptance gate

The system can produce a coherent one-to-three-minute replay of a multi-part event without a human manually placing every camera.

---

# 28. v0.7 Slice 23 — Live Crawler Channels

Create the ability to actively watch simulated NPC crawlers.

## Viewer concept

A crawler channel may show:

- live camera feed,
- name/profile,
- current health/status,
- floor/location,
- party members,
- equipment/build summary,
- current objective if suitable for viewers,
- recent notable events,
- crawl statistics.

## Switching

A viewer should be able to switch between crawlers without changing the simulation.

If a previously background-simulated crawler becomes watched, the detail-tier system should promote their local area cleanly.

### Acceptance gate

Multiple viewers can independently follow different crawlers while the same authoritative crawl continues underneath them.

---

# 29. v0.7 Slice 24 — Story Arc and Highlight Detection

Events are not yet stories. Build a system that groups related events into meaningful sequences.

## Event-sequence patterns

Examples:

- rescue,
- comeback,
- last-second escape,
- underdog victory,
- betrayal,
- revenge,
- reunion,
- sacrifice,
- rivalry escalation,
- party collapse,
- unlikely alliance,
- repeated near-death survival,
- rare-item transformation,
- boss victory,
- notable death.

## Long-running arcs

Track cross-floor relationships such as:

```text
Floor 2: crawler B abandons crawler A
Floor 3: A refuses B's invitation
Floor 5: B saves A
Floor 7: they form a temporary alliance
Floor 9: one dies protecting the other
```

No script is required for that sequence to be recognized as a connected arc.

### Acceptance gate

Given a finished crawl history, the analyzer can identify high-interest event sequences and explain which structured events caused the selection.

---

# 30. v0.7 Slice 25 — Automated Commentary and Recaps

Use the structured event ledger as input rather than raw video.

## Commentary modes

Possible future presentation personalities:

- sports-style play-by-play,
- analytical commentary,
- comedic commentary,
- documentary recap,
- individual crawler recap.

## Grounding rules

Commentary may describe only known authoritative facts unless explicitly framed as speculation.

Generated speech must not invent:

- kills,
- relationships,
- injuries,
- items,
- motivations presented as fact,
- floor outcomes.

### Acceptance gate

A generated recap remains factually consistent with the event ledger and can cite/reference the event IDs used to produce it internally.

---

# 31. v0.7 Slice 26 — Automated Highlight Reels

Connect story detection, replay, cameras, and commentary.

## Pipeline

```text
Structured event ledger
-> importance/story selection
-> select replay window
-> reconstruct event
-> camera director
-> render footage
-> optional commentary/subtitles
-> assemble clip
-> attach crawler/event metadata
-> review/publish queue
```

## Output types

- short single-event clips,
- crawler daily recaps,
- floor recaps,
- rivalry/relationship packages,
- death memorial/profile videos,
- crawl trailers,
- season/crawl documentaries.

### Acceptance gate

The system can automatically produce a playable highlight package from a completed headless event without a human manually re-staging the simulation.

---

# 32. v0.7 Slice 27 — Optional AI Video Dramatization

AI video generation is an optional secondary output path.

Use it for:

- trailers,
- stylized character introductions,
- historical flashbacks,
- promotional clips,
- cinematic reinterpretations.

The canonical simulation replay remains separate and should be clearly distinguishable internally from AI-dramatized media.

## Required safeguards

Every generated scene prompt must be grounded in structured event data.

Store:

- source event IDs,
- generated prompt/scene spec,
- model/provider metadata where allowed,
- generation timestamp,
- relationship to canonical replay.

### Acceptance gate

A dramatized clip can always be traced back to the authoritative events it represents.

---

# 33. v0.8 Slice 28 — Public Spectator Experience

Build a viewer-facing web/app experience around the crawl.

## Core views

### Crawl home

- floor number,
- survivors,
- time remaining,
- major active events,
- trending crawlers,
- recent deaths,
- top clips.

### Crawler page

- biography,
- portrait/model,
- current status,
- stats/build,
- party,
- relationships,
- crawl history,
- recent highlights,
- follow/watch action.

### Live discovery

- crawlers in combat,
- boss encounters,
- near-death events,
- high-interest parties,
- trending relationship arcs.

### Archive

- past crawls,
- past floors,
- eliminated crawlers,
- historic highlights,
- statistics.

### Acceptance gate

A user who knows nothing about the simulation can discover a crawler, understand who they are, watch them, and review their history without using developer tools.

---

# 34. v0.8 Slice 29 — Follow, Trending, and Notification Systems

Allow the audience to form attachments to NPC contestants.

## Follow state

Users may follow:

- individual crawlers,
- parties,
- crawl-wide events.

## Possible notifications

- followed crawler entered a major encounter,
- followed crawler was injured,
- followed crawler advanced,
- followed crawler died/eliminated,
- new highlight available,
- major relationship/party change.

## Trending

Trending should combine signals such as:

- current dramatic score,
- unusual event rarity,
- sustained viewer attention,
- recent relationship arcs,
- high-stakes encounter involvement.

Audience attention must not automatically change authoritative game outcomes unless a future ruleset intentionally introduces a bounded viewer-interaction mechanic.

### Acceptance gate

Viewer demand can change what is rendered/promoted for presentation without changing what the simulation says happened.

---

# 35. v0.9 Slice 30 — Crawl Seasons, Persistence, and Resets

A completed crawl should become permanent history while the next crawl can start cleanly.

## Persistent between crawls

Potentially preserve:

- crawl archive,
- crawler history,
- statistics,
- notable items as historical records,
- hall-of-fame style achievements,
- relationships for returning contestants if rules allow,
- Director analytics,
- viewer follows/history.

## Crawl-local state

Usually reset/archive:

- current floors,
- temporary encounter state,
- temporary floor resources,
- floor maps,
- floor-specific buffs/debuffs,
- transient enemy populations.

## Returning crawlers

The system should support rulesets where some NPCs may appear in later crawls without requiring that every crawl share continuity.

### Acceptance gate

A crawl can conclude, be archived, and a new seeded crawl can begin without deleting or corrupting historical queryability.

---

# 36. v0.9 Slice 31 — Production Hardening and Operations

Before public continuous operation, harden the system.

## Required areas

- crash recovery,
- deterministic checkpoint recovery,
- replay integrity,
- database migration strategy,
- event retention/archival,
- media storage policy,
- observability,
- performance profiling,
- runaway-agent detection,
- stuck encounter detection,
- Director budget validation,
- backup/restore,
- safe admin intervention,
- versioned crawl rulesets.

## Admin intervention

If an operator must repair a broken simulation, the intervention itself should be recorded as an authoritative admin event.

### Acceptance gate

The server can recover from an intentional mid-crawl process termination using the latest valid checkpoint without duplicating deaths, items, advancements, or event IDs.

---

# 37. Critical Data Contracts

These contracts should remain stable enough that backend, Unreal, web clients, and media tooling can evolve independently.

## Crawler snapshot

Must include enough state for presentation and replay without exposing hidden internal knowledge to public clients.

## Action/event contract

Every authoritative action should be identifiable by:

- crawl/floor,
- simulation time/tick,
- actor,
- targets,
- location,
- action type,
- inputs,
- outcome,
- state delta,
- causal references.

## Replay contract

Replay should specify:

- checkpoint,
- start simulation time,
- end simulation time,
- required entities,
- event range,
- deterministic configuration version.

## Media-story contract

A highlight/story candidate should reference:

- crawler/event IDs,
- time range,
- story category,
- score components,
- beginning/context event,
- climax event,
- resolution event,
- suggested replay range.

---

# 38. AI Usage Policy for the Architecture

AI can be extremely valuable to Crawl, but it belongs in specific layers.

## Good uses

- dialogue generation from authoritative intent/state,
- voice performance,
- commentator scripts,
- recap writing,
- title/caption generation,
- character interviews framed from known memories,
- semantic clustering of already-recorded events,
- optional Director proposals,
- optional cinematic scene planning,
- optional video dramatization.

## Do not make AI authoritative for

- damage,
- death,
- item creation/ownership,
- movement validity,
- advancement,
- floor deadlines,
- inventory accounting,
- combat resolution,
- simulation invariants,
- canonical event history.

The system must remain capable of running a full crawl if every external AI provider is unavailable.

---

# 39. Deferred Systems

Do not let these block the first watchable crawl:

- photorealistic character assets,
- hundreds of enemy models,
- voice conversations for every crawler,
- AI video production,
- viewer voting that affects gameplay,
- monetization,
- mobile native apps,
- huge public-scale streaming infrastructure,
- sophisticated crafting economy,
- inherited kingdom simulation expansion,
- complete pre-crawl civilization histories,
- physically simulated every-object environments.

Build them only after the core autonomous entertainment loop works.

---

# 40. Recommended Implementation Order

```text
COMPLETED INHERITED FOUNDATION
LivingWorld v0.2
v0.3 Slice 1 politics
v0.3 Slice 2 laws/institutions
v0.3 Slice 3 production/inventories/labor

CRAWL PIVOT
Slice 1   Crawl domain model
Slice 2   Crawler traits/skills/needs
Slice 3   Autonomous decision engine
Slice 4   Perception/knowledge/uncertainty
Slice 5   Memory/relationships/social consequences
Slice 6   Floor generation/traversal
Slice 7   Individual combat/injury/death
Slice 8   Items/equipment/loot
Slice 9   Progression/abilities/builds
Slice 10  Parties/alliances/group behavior
Slice 11  Encounters/enemies/traps/hazards
Slice 12  Deadlines/advancement/intermission
Slice 13  Crawl Director
Slice 14  Semantic event ledger
Slice 15  Headless Crawl MVP gate

SCALING
Slice 16  Simulation detail tiers
Slice 17  Multi-seed/performance validation
Slice 18  Crawl observatory dashboard

WATCHABLE CRAWL
Slice 19  Spectator API
Slice 20  Unreal spectator bridge
Slice 21  Replay system
Slice 22  Automated camera director
Slice 23  Live crawler channels

AUTOMATED ENTERTAINMENT
Slice 24  Story/highlight detection
Slice 25  Commentary/recaps
Slice 26  Automated highlight reels
Slice 27  Optional AI video dramatization

PUBLIC PRODUCT
Slice 28  Viewer web/app experience
Slice 29  Follow/trending/notifications
Slice 30  Crawl seasons/archive/reset
Slice 31  Production hardening/operations
```

---

# 41. Major Readiness Gates

## Gate A — Autonomous Crawler

One crawler can perceive, decide, travel, fight, use items, remember events, and survive/die without scripts or LLM calls.

## Gate B — Headless Crawl

100 crawlers can complete a multi-floor crawl with emergent parties, deaths, progression, relationships, and structured event history.

## Gate C — Scalable Crawl

1,000+ crawlers can run practically using simulation detail tiers while preserving authoritative continuity.

## Gate D — Watchable Crawler

A human can select one crawler and watch a synchronized Unreal representation of their live/replayed actions.

## Gate E — Automatic Highlight

A major event can be detected from structured data, replayed, automatically filmed, and assembled into a clip.

## Gate F — Autonomous Entertainment Product

A full crawl can run continuously while users discover/follow NPCs and the system produces live viewing, recaps, and highlights without requiring a human game master or video editor for every event.

---

# 42. Definition of Success

Crawl reaches the intended product vision when the system can run a season in which thousands of autonomous contestants produce individual histories and relationships, and a viewer can ask questions such as:

- Who is this crawler?
- Why are they traveling with these people?
- Why do they distrust that crawler?
- Where did that weapon come from?
- Why did they choose this route?
- Why did they retreat from that encounter?
- Who saved them earlier in the crawl?
- Why was this death important?
- What happened between these two crawlers across several floors?
- What are the best moments happening right now?
- Can I watch this crawler live?
- Can I watch the replay of the event everyone is talking about?
- Can I see a recap of this crawler's entire run?

The answers should come from actual simulation state and recorded events, not from a narrator inventing a story after the fact.

The defining test is:

> **If we turn off the cameras, commentary, and generative AI, does an interesting autonomous crawl still happen?**

If yes, the simulation foundation is working.

Then the presentation stack turns that simulation into something people can watch.
