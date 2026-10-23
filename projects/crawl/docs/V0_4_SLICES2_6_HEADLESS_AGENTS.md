# Crawl v0.4 — Slices 2–6 Headless Agent Batch

## Status

Implementation branch: `agent/crawl-v0.4-slices2-6`

Base: `agent/crawl-v0.4-slice1-domain`

This batch deliberately groups the next five tightly coupled roadmap slices so they can be tested as one headless autonomous-crawler milestone.

The batch does **not** add combat, enemies, loot ownership, parties, or the Crawl Director. Those begin in later slices.

---

# Slice 2 — Crawler Identity, Traits, Skills, and Needs

Each crawl participant now persists a deterministic `CrawlerAgentState` containing:

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
- risk tolerance,
- melee/ranged/defense skills,
- perception,
- stealth,
- navigation,
- medicine,
- traps,
- negotiation,
- leadership,
- scavenging,
- ability use,
- stamina,
- hunger,
- stress,
- morale,
- perceived danger,
- equipment readiness,
- preferences/aversions.

Profiles are deterministically generated from crawl seed + persistent NPC ID, so save/reload and replay do not need an LLM or random external service.

The agent state is embedded in `CrawlerParticipation`, so it survives the existing Crawl JSON persistence model.

---

# Slice 3 — Autonomous Decision Engine

`crawler_decision.py` adds a bounded utility scorer.

Current authoritative non-combat actions:

- `seek_exit`,
- `seek_safety`,
- `explore`,
- `recover`,
- `wait`.

Scores respond to crawler-specific traits and changing survival state. The engine records reason components so future spectator/commentary systems can explain why a crawler made a choice.

The decision is recomputed each step, which provides bounded replanning and interruption without an expensive unrestricted planner.

No LLM call is used.

---

# Slice 4 — Perception, Knowledge, and Uncertainty

Crawler knowledge is local and persistent.

A crawler initially knows only its current location and what can be observed from it.

Knowledge records include:

- confidence,
- last-observed tick,
- known neighbors,
- tags,
- observed hazards,
- believed safe state,
- believed exit state,
- visit count.

Hidden shortcuts are filtered through deterministic perception/navigation checks.

The navigation layer operates on crawler-known graph information rather than the complete authoritative floor graph.

This means two crawlers can possess different maps of the same floor.

---

# Slice 5 — Memory, Relationships, and Social Consequences

Crawler agent state now persists event-referenced memories and multidimensional relationships.

Relationship dimensions include:

- trust,
- affection,
- respect,
- fear,
- resentment,
- gratitude,
- rivalry,
- familiarity,
- perceived reliability.

Structured social events can apply bounded relationship consequences for categories such as:

- rescue,
- healing,
- resource sharing,
- abandonment,
- betrayal,
- stolen loot,
- rivalry,
- threats/attacks.

`willingness_to_help()` derives a future social-action signal from both relationship history and crawler personality.

The current headless traversal loop also increases familiarity when crawlers repeatedly occupy the same location.

Full party/help/rescue actions are intentionally deferred until the party and encounter slices exist.

---

# Slice 6 — Floor Generation and Traversal

The fixed five-node Slice 1 bootstrap floor has been replaced for new crawls by a larger deterministic generator.

Current floors contain:

- a guaranteed entrance-to-exit backbone,
- 9+ locations depending on floor/depth,
- one or more safe areas,
- branches,
- loops,
- shortcuts,
- hidden shortcuts,
- hazards,
- encounter slots,
- resource/search nodes,
- floor themes,
- increasing danger,
- bounded traversal costs.

The `CrawlFloor` graph validator remains authoritative and guarantees that at least one exit is reachable.

Crawler traversal uses only discovered/known topology.

---

# Integrated Headless Simulation

`AutonomousCrawlSimulator` ties Slices 2–6 together.

Each simulation step:

1. advances the crawl tick,
2. updates local perception,
3. records discoveries,
4. chooses an action through utility scoring,
5. chooses a destination from crawler-known topology,
6. moves or recovers,
7. updates stamina/hunger/stress,
8. records structured events,
9. creates crawler memories from those events,
10. updates co-location familiarity,
11. waits at the advancement gate once reached,
12. completes the floor after all active crawlers reach the exit.

Survivors then enter the next generated floor through the Slice 1 lifecycle service.

---

# Evening Test

From repository root in PowerShell:

```powershell
.\scripts\run-crawl-slices2-6-validation.ps1
```

That performs three stages:

1. Slice 1 + Slices 2–6 focused tests.
2. A 100-crawler / 3-floor autonomous headless crawl.
3. The entire inherited repository pytest regression suite.

The demo report is written to:

`validation/crawl-v0.4-slices2-6-demo.json`

For a faster first pass:

```powershell
.\scripts\run-crawl-slices2-6-validation.ps1 -Crawlers 25 -Floors 2 -SkipFullRegression
```

For a larger stress pass:

```powershell
.\scripts\run-crawl-slices2-6-validation.ps1 -Crawlers 250 -Floors 5 -MaxSteps 10000
```

The demo exits with a nonzero code if the autonomous crawl does not complete within the configured step budget.

---

# What to Inspect Manually

The JSON report should show:

- crawl status `completed`,
- all configured floors reached,
- different generated themes/room counts,
- nonzero structured history events,
- different crawler goals/traits,
- accumulated location knowledge,
- event memories,
- relationships/familiarity,
- crawler samples with distinct personality profiles.

The most important behavioral question is not whether every crawler chooses the mathematically shortest route. It is whether different deterministic contestants visibly make different choices and still converge on crawl advancement without manual intervention.

---

# Explicitly Deferred

This batch does not yet attempt to fake later systems.

Deferred to upcoming slices:

- individual combat,
- injuries and death from encounters,
- monsters/enemies,
- item ownership and equipment,
- loot decisions,
- progression/builds,
- formal parties and alliance behavior,
- rescue actions,
- betrayal actions inside parties,
- traps/puzzles as authoritative encounters,
- Crawl Director interventions,
- highlight scoring,
- Unreal rendering.

Those systems should consume the crawler brain, knowledge, relationship, and floor contracts established here.
