# Crawl v0.4 Slice 1 — Crawl Domain Model

## Status

Implementation branch: `agent/crawl-v0.4-slice1-domain`

Base roadmap branch: `roadmap/autonomous-crawl-pivot`

Slice 1 is the first code milestone after the LivingWorld-to-Crawl pivot. It creates an authoritative, graph-based crawl state that can exist, advance, persist, complete, and archive without Unreal, player input, or an LLM.

The implementation is intentionally isolated from the inherited continent simulation. Crawl-specific state currently lives in separate domain and persistence modules so the new architecture can mature without destabilizing the proven LivingWorld systems.

---

## 1. Authoritative entities

`src/livingworld/crawl_domain.py` adds:

- `Crawl`
- `CrawlFloor`
- `CrawlLocation`
- `CrawlerParticipation`
- `CrawlEvent`
- crawl/floor/participation/location status enums

### Crawl state

The crawl tracks:

- deterministic ID and seed
- planned/running/completed/archived status
- simulation tick and start/archive ticks
- current floor
- ruleset ID/version
- starting/surviving/eliminated counts
- crawl-wide modifiers
- floor collection
- crawler participation state
- structured crawl event references

### Floor state

Each floor tracks:

- deterministic floor seed
- theme
- start/deadline ticks
- completion/advancement rules
- graph locations
- entrance/exits/safe areas
- danger level
- director and encounter budgets
- active crawler count
- lifecycle status

### Location state

The first floor representation is a graph rather than rendered geometry. Locations track:

- adjacency and traversal cost
- visibility
- hazards
- exits
- encounter slots
- loot/resource nodes
- environmental tags
- optional capacity

The floor validator rejects broken references and verifies that at least one advancement exit is reachable from the entrance.

### Crawler participation

A persistent NPC remains conceptually separate from its crawl participation state. Participation tracks:

- NPC ID
- crawl ID
- current floor/location
- active/dead/eliminated/advanced state
- health/resources
- progression
- current party/objective hooks
- floor-specific statistics

Later slices can expand this state without forcing crawl-only fields into the inherited NPC model.

---

## 2. Deterministic floor bootstrap

`src/livingworld/crawl_service.py` provides the temporary Slice 1 graph generator.

Each floor currently contains a small but valid topology:

```text
Arrival Gate
    |
 Splitway
  /     \
Refuge  Trial Chamber
  \       |
   \------|
           \
        Advancement Gate
```

The exact topology is not intended to survive the later floor-generation milestone. Its purpose is to prove the domain contract now.

Seeds deterministically control:

- floor seed
- theme
- danger level
- location IDs
- traversal costs
- encounter budget
- director budget

---

## 3. Crawl lifecycle service

`CrawlLifecycleService` currently supports:

1. create a seeded crawl
2. assign a unique crawler roster
3. generate multiple floors
4. start the crawl
5. activate a floor and establish its deadline
6. eliminate or kill a crawler
7. update authoritative survivor/elimination counts
8. complete a floor
9. advance surviving crawlers to the next floor
10. complete the final floor
11. archive the crawl
12. record structured lifecycle events
13. validate state before persistence

This is deliberately not the crawler decision engine. Slice 1 can move crawlers between lifecycle states, but autonomous movement, perception, combat, and goal selection belong to later slices.

---

## 4. Persistence

`src/livingworld/crawl_persistence.py` adds separate SQLAlchemy tables:

- `crawls`
- `crawl_events`

The persistence layer supports:

- schema initialization
- save/update crawl state
- load crawl state
- list/filter crawls
- append idempotent structured crawl events
- list/filter crawl events
- test/reset support

The tables intentionally coexist with the inherited LivingWorld database without changing the existing `world_state`, history, command, or snapshot tables.

---

## 5. Structured events already emitted

Slice 1 begins the future broadcast/history pipeline with authoritative events:

- `CRAWL_CREATED`
- `CRAWL_STARTED`
- `FLOOR_STARTED`
- `FLOOR_COMPLETED`
- `CRAWLER_ELIMINATED`
- `CRAWLER_DIED`
- `CRAWL_COMPLETED`
- `CRAWL_ARCHIVED`

These are simulation facts, not generated prose. Later replay, commentary, story-analysis, and highlight systems can consume the same event stream.

---

## 6. Invariants

The current models reject or catch:

- missing floors
- non-contiguous floor numbering
- invalid current floor
- participant/crawl ID mismatch
- participant locations that do not exist
- stale survivor/elimination counts at persistence boundaries
- floor location IDs that do not match dictionary keys
- locations assigned to the wrong floor
- adjacency references to nonexistent locations
- invalid safe-area/exit references
- non-positive traversal costs
- floor graphs with no reachable advancement exit
- duplicate crawler IDs during crawl creation

---

## 7. Focused validation

`tests/test_crawl_domain.py` covers:

- deterministic seeded generation
- graph validity and reachable exits
- rejection of malformed graphs
- SQLite save/load equivalence
- multi-floor advancement
- final completion
- archive persistence
- crawler death/elimination accounting
- structured event persistence
- duplicate roster rejection

Initial focused validation was reproduced in an isolated Python environment against the exact new modules:

```text
6 passed
```

The complete inherited repository regression suite still needs to be run from a normal project checkout before merge.

Use:

```powershell
.\scripts\run-crawl-slice1-validation.ps1
```

For only the focused Slice 1 tests:

```powershell
.\scripts\run-crawl-slice1-validation.ps1 -FocusedOnly
```

No GitHub Actions minutes are required.

---

## 8. Slice 1 acceptance gate mapping

Roadmap requirement:

> A seeded crawl with multiple floors can be created, saved, reloaded, advanced, completed, and archived without graphics or manual database edits.

Implemented coverage:

- seeded creation: yes
- multiple floors: yes
- save: yes
- reload: yes
- advance: yes
- complete: yes
- archive: yes
- graphics required: no
- LLM required: no
- manual database edits required: no

The slice should remain **in progress** until the full inherited regression suite is run on the branch and any integration issues are resolved.

---

## 9. Explicitly deferred

Slice 1 does not yet implement:

- crawler traits/skills/needs
- autonomous decision making
- perception/knowledge uncertainty
- social memory expansion
- procedural floor-generation depth
- individual combat
- equipment/loot ownership
- progression/builds
- parties
- encounter AI
- director interventions
- spectator API/UI
- Unreal rendering
- replay/camera systems
- highlight generation

Those belong to later roadmap slices and should build on this authoritative state instead of creating parallel crawl models.
