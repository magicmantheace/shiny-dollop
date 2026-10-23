# Underreach v0.10 — Slice 30A.3: Loot, Cache & Relic Foundation

## Status

Implementation branch:

`agent/underreach-v0.10-slice30a3-loot-cache-relic-foundation`

Exact accepted base:

`646aa8655c90ab3c1f0dec7830ac21153a372662` — 30A.2 Multi-Stratum Progression

This slice is not accepted until the local validation runner ends with an explicit:

```text
[30A.3] PASS
```

No GitHub Actions are required or used.

---

# Purpose

30A.3 gives an ongoing authoritative Descent a deterministic loot foundation that can survive progression, persistence, replay, and later autonomous gameplay integration.

The slice establishes:

- deterministic cache placement,
- deterministic cache contents,
- sealed/opened/depleted cache state,
- canonical materialization of cache contents,
- one valid owner/location holder for every materialized item,
- stable unique relic identity,
- cache/relic origin metadata,
- Ledger-backed item provenance,
- drop and re-acquisition provenance,
- inventory persistence across Stratum advancement,
- checkpoint-safe loot state.

The simulation remains the only authority.

Unreal, cameras, visual equipment, UI, commentary, sponsors, and other presentation systems cannot decide whether a cache exists, what is inside it, who owns an item, or whether a relic changed hands.

---

# Architectural Position

```text
30A.1 Descent Run State
        ↓
30A.2 Multi-Stratum Progression
        ↓
30A.3 Loot / Cache / Relic Foundation
        ↓
Canonical Descent + Ledger
        ↓
Future gameplay / presentation consumers
```

30A.3 does not create a second inventory database or a second item model.

It reuses the established canonical structures:

- `Crawl.items`
- `CrawlItem`
- participant `inventory_item_ids`
- participant equipment state
- `transfer_item_to_crawler()`
- `drop_item()`
- `AlphaCheckpointStore`
- the canonical structured event Ledger

---

# Existing Item Invariant Reused

The established `CrawlItem` model already requires exactly one authoritative holder:

```text
owner_npc_id
OR
location_id
OR
encounter_id
```

Exactly one must be non-null.

30A.3 preserves this rule.

For cache loot:

```text
sealed cache blueprint
    ↓ open cache
real CrawlItem at cache Sector
    ↓ acquire
real CrawlItem owned by Descender
    ↓ drop
real CrawlItem at current Sector
    ↓ reacquire
real CrawlItem owned by new Descender
```

At no point can a materialized item simultaneously belong to a Descender and exist on the ground.

---

# Why Sealed Caches Use Blueprints

A sealed cache does **not** insert its contents into `Crawl.items`.

This is intentional.

Existing autonomous gameplay already contains a ground-loot collector. If unopened cache items were represented as ordinary ground items, that existing system could collect them before the cache was opened.

Instead:

```text
sealed cache
    └── deterministic item blueprints only

open cache
    └── materialize each blueprint as a real CrawlItem
```

This means unopened cache contents are canonical and deterministic without pretending they are loose world items.

---

# Protocol

Core protocol:

`underreach.loot-cache-relic.v1`

Implementation version:

`30a3.1`

Canonical metadata key:

`_loot_cache_relic`

Authority contract:

```text
authoritative = true
canonical_owner = deterministic_simulation
presentation_feedback_allowed = false
```

---

# Deterministic Cache Generation

The current 30A.3 foundation creates:

- exactly one cache per configured Stratum,
- exactly two ordinary item blueprints per cache,
- exactly one relic blueprint per cache.

Cache placement is chosen deterministically from eligible non-entry/non-exit Sectors containing established loot/resource nodes.

The selected cache location depends only on canonical inputs such as:

- Descent seed,
- Descent identity,
- Stratum number,
- eligible Sector IDs,
- source loot-node identity.

The complete immutable cache/blueprint layout is protected by:

`cache_generation_digest`

Changing a cache Sector, blueprint definition, item ID, relic identity, or origin data invalidates that digest.

---

# Cache Lifecycle

A cache has one of three states.

## sealed

- blueprints exist,
- no cache item is present in `Crawl.items`,
- no opener exists,
- no opened Ledger event exists.

## opened

- every blueprint has been materialized exactly once,
- every materialized item initially exists at the cache Sector,
- at least one item has not yet received its first cache claim.

## depleted

- every materialized cache item has received its first canonical claim.

`depleted` describes the initial cache-claim lifecycle.

If a claimed item is later dropped back into the same Sector, the cache does not become unopened again.

---

# Opening Rules

A cache can only be opened when:

- the Descent is running,
- the cache belongs to the current Stratum,
- the opener is an active Descender,
- the opener is on the current Stratum,
- the opener occupies the exact cache Sector.

Opening emits:

`CACHE_OPENED`

The event records:

- cache ID,
- Stratum number,
- exact item IDs materialized,
- cache state change.

That Ledger event becomes the first provenance event for every materialized item.

Repeated opening of an already opened cache is idempotent and does not create duplicate items or duplicate Ledger events.

---

# Ordinary Loot

Ordinary cache items reuse the established deterministic item generator.

The blueprint freezes the generated item's gameplay definition before materialization, including:

- stable item ID,
- name,
- category,
- rarity,
- equipment slot where applicable,
- stats,
- effects,
- durability,
- requirements,
- important-item flag.

Materialization must exactly match this blueprint.

---

# Relic Foundation

Each cache includes one canonical relic blueprint.

30A.3 relics are intentionally a **foundation**, not a complete relic gameplay system.

Each relic receives:

- a unique stable item ID,
- a unique stable `relic_key`,
- deterministic original name,
- `trinket` item category,
- `epic` rarity,
- `important = true`,
- deterministic bounded stats,
- origin cache ID,
- origin Stratum,
- origin Sector,
- discovery Ledger event,
- ordered acquisition Ledger event IDs.

Relic gameplay powers, progression choices, sponsored effects, patron effects, and complex build interactions are outside 30A.3.

---

# Acquisition

A materialized cache item can be acquired only when:

- the Descent is running,
- the item is currently real ground loot,
- the acquiring Descender is active,
- the Descender is on the current Stratum,
- the Descender occupies the item's exact Sector.

Acquisition uses the established canonical transfer helper.

It emits:

`ITEM_ACQUIRED`

The event contains:

- item ID,
- item kind (`ordinary` or `relic`),
- source cache ID,
- origin Stratum,
- whether this was the first cache claim,
- rarity,
- resulting owner.

The new event ID is appended to the item's canonical `provenance_event_ids`.

For relics, it is also appended to the relic registry's acquisition history.

---

# Drop and Re-Acquisition

30A.3 exposes a canonical drop operation for managed cache items.

Dropping emits:

`ITEM_DROPPED`

The same item ID is moved from the owner's inventory to the owner's current Sector.

A different co-located Descender can then acquire that same item through the normal ground-item acquisition path.

This creates a real provenance chain such as:

```text
CACHE_OPENED
ITEM_ACQUIRED       owner A
ITEM_DROPPED        owner A -> ground
ITEM_ACQUIRED       ground -> owner B
```

No copy of the relic is created during transfer.

---

# Progression Compatibility

30A.3 wraps the accepted 30A.2 progression service rather than replacing it.

When an item is owned by a survivor:

```text
Stratum N owner inventory
    ↓ 30A.2 advance
same owner inventory on Stratum N+1
```

The item retains:

- exact item ID,
- exact definition,
- exact relic identity,
- exact provenance event IDs.

A Stratum transition does not rewrite loot history.

Ground items left on an earlier Stratum remain canonically located on that earlier Stratum.

---

# Checkpoint Compatibility

30A.3 continues to use the existing `AlphaCheckpointStore`.

The acceptance proof writes a checkpoint **after the first Stratum transition**, after a relic has already:

1. been discovered in a cache,
2. been acquired by one Descender,
3. been dropped,
4. been acquired by a second Descender,
5. been carried into Stratum 2.

The checkpoint restore must reproduce the complete loot snapshot exactly.

This includes:

- cache states,
- materialized items,
- item holders,
- inventories,
- relic registry,
- provenance chains,
- current Stratum.

---

# Snapshot Contract

`build_loot_cache_relic_snapshot()` exposes deterministic proof data including:

- source 30A.2 progression snapshot digest,
- cache-generation digest,
- cache counts by state,
- total blueprint item count,
- materialized item count,
- owned item count,
- ground item count,
- relic blueprint count,
- materialized relic count,
- owned relic count,
- complete canonical cache state,
- complete relic registry,
- materialized item state,
- materialized-item digest,
- Ledger ID digest,
- canonical Descent fingerprint,
- final snapshot digest.

---

# Acceptance Proof

The formal local proof uses:

- 8 Descenders,
- 4 Strata,
- 4 deterministic caches,
- 4 deterministic relic blueprints.

The proof performs this sequence:

```text
Create four-Stratum Descent
        ↓
Start Stratum 1
        ↓
Move two Descenders to cache 1
        ↓
Open cache 1
        ↓
Materialize 3 items
        ↓
Claim all 3 with Descender 000
        ↓
Drop relic
        ↓
Descender 001 claims same relic
        ↓
Move all survivors to Stratum-1 exit
        ↓
Advance 1 -> 2
        ↓
Verify relic remains owned by Descender 001
        ↓
Write + reload AlphaCheckpointStore checkpoint
        ↓
Verify exact loot snapshot
        ↓
Open cache 2
        ↓
Claim only its relic
        ↓
Advance 2 -> 3 -> 4
        ↓
Complete final Stratum
```

Expected final cache-state mix:

- 1 depleted cache,
- 1 opened cache,
- 2 sealed caches.

Expected materialized loot:

- 6 items total,
- 4 owned,
- 2 still ground loot,
- 2 owned relics.

---

# Scope Boundary

30A.3 does **not** implement 30A.4 survival/resource pressure.

The metadata explicitly records:

`resource_survival_owner_slice = 30A.4`

Deferred to 30A.4:

- hunger,
- thirst,
- fatigue pressure beyond existing legacy state,
- persistent survival supplies,
- resource drain,
- survival consumption schedules,
- replenishment rules,
- resource scarcity,
- survival failure consequences.

Existing ordinary consumable item definitions remain usable, but 30A.3 does not create the authoritative survival loop around them.

---

# Files Added

```text
src/livingworld/underreach_loot_cache_relic.py
tests/test_underreach_30a3_loot_cache_relic.py
scripts/generate-underreach-loot-cache-relic-proof.py
scripts/run-underreach-loot-cache-relic-validation.ps1
docs/V0_10_SLICE30A3_LOOT_CACHE_RELIC_FOUNDATION.md
```

The accepted 30A.1 and 30A.2 implementation files are not modified.

---

# Local Validation

From the test checkout:

```powershell
cd D:\CrawlTesting
git fetch origin
git switch agent/underreach-v0.10-slice30a3-loot-cache-relic-foundation
git pull --ff-only
.\scripts\run-underreach-loot-cache-relic-validation.ps1
```

Acceptance requires the final line:

```text
[30A.3] PASS
```

Until that explicit local result is observed, 30A.3 is not accepted.

---

# Next Canonical Slice After Acceptance

**30A.4 — Resources & Survival**

30A.4 will add deterministic survival-resource state and pressure to the authoritative Descent while reusing 30A.3 ownership/provenance rather than turning item visuals or presentation systems into gameplay authority.
