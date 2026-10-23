# Underreach Canonical Vocabulary

## Purpose

This document defines the product-facing language for the project before Slice 28B expands the live presentation, public API, viewer, media, and community surfaces.

The deterministic simulation predates this vocabulary and contains persisted `crawl`, `crawler`, and `floor` identifiers. Those identifiers remain compatibility details until a separately versioned storage/replay migration is justified. They are **not** the preferred names for new product-facing code.

The migration rule is:

> Preserve simulation truth and replay compatibility underneath; use Underreach vocabulary at every new public boundary.

## Canonical Terms

| Concept | Canonical term | Meaning |
| --- | --- | --- |
| World/system/place | **The Underreach** | The ancient environment/system in which the competition exists. |
| Competition/run | **The Descent** | The organized competition occurring within the Underreach. |
| Contestant | **Descender** | A participant attempting the Descent. |
| Major progression layer | **Stratum** | A major depth/layer of the Underreach. Plural: Strata. |
| Sub-area | **Sector** | A room, region, encounter space, or local area within a Stratum. |
| Season/competition period | **Cycle** | A major organized competition period. |
| Backing organization | **House** | An organization with influence, resources, reputation, and backed Descenders. |
| Individual backer | **Patron** | The person/entity directly backing or managing support for a Descender. |
| Sponsored aid | **Boon** | Bounded support authorized for a Descender. |
| Normal reward/loot package | **Cache** | A normal recoverable reward package. |
| Rare/special item | **Relic** | A rare, exceptional, or historically important item. |
| Safe area | **Refuge** | A recognized safer Sector. |
| Rules/enforcement authority | **The Arbiter** | The deterministic authority that validates/enforces Descent rules. |
| Public broadcast | **The Feed** | The spectator-facing broadcast/data surface. |
| Authoritative/public record | **The Ledger** | The permanent record of events, standings, outcomes, and history. |
| Highlight/story moment | **Echo** | A detected noteworthy sequence grounded in Ledger truth. |
| Rendered highlight package | **Echo Reel** | A finished or render-ready collection built from an Echo. |
| Dead participant label | **Fallen** | Public status for a Descender whose canonical state is dead. |

## Structural Language

The preferred hierarchy is:

```text
THE UNDERREACH
└── Cycle
    └── Descent
        └── Stratum
            └── Sector
                └── Descenders / encounters / Refuges / Caches / Relics
```

A useful public locator is therefore:

```text
Cycle 18 → Descent 04 → Stratum 9 → Sector 9-14
```

## Houses, Patrons, and Boons

These terms are intentionally separate.

- A **House** is the backing organization.
- A **Patron** is the specific backer/manager relationship around a Descender.
- A **Boon** is authorized support sent to a Descender.

Future House systems may include reputation, rivalries, resource claims, Patronage budgets, and Descender relationships. The terms do not imply that a House can purchase canonical victory or alter simulation truth.

## The Arbiter

The Arbiter is the in-universe name for deterministic rule enforcement and validated intervention authority.

The software architecture and lore should align:

```text
Authoritative deterministic simulation
        ↓
The Ledger records truth
        ↓
The Feed presents truth
        ↓
Echoes discover stories in truth
```

Presentation systems may choose cameras, animation, commentary, timing interpolation, and visual staging. They may not change the Ledger.

## Public Event Vocabulary

Historical stored ledger event types are preserved for replay compatibility. Feed projections translate public prefixes without changing event IDs.

Examples:

| Stored compatibility event | Feed event |
| --- | --- |
| `CRAWLER_DIED` | `DESCENDER_DIED` |
| `CRAWLER_DAMAGED` | `DESCENDER_DAMAGED` |
| `CRAWLER_RETREATED` | `DESCENDER_RETREATED` |
| `FLOOR_COMPLETED` | `STRATUM_COMPLETED` |
| `CRAWL_*` | `DESCENT_*` |

Generic concepts such as `COMBAT_HIT`, `ENEMY_DEFEATED`, `RESCUE`, and `NEAR_DEATH` do not need artificial renaming.

## New Code Policy

Starting with this refactor:

1. New public routes use `/api/feed/...`, not new `/api/spectator/crawl...` routes.
2. New public payloads use `descent_id`, `descender_id`, `stratum_number`, and `sector_id`.
3. New viewer-facing features call highlights **Echoes** and rendered packages **Echo Reels**.
4. New domain-facing code should import compatibility aliases from `underreach_domain.py` and `descender_domain.py` when practical.
5. New rule-authority code should use the `Arbiter` facade rather than introduce additional `CrawlDirector` naming.
6. Legacy persistence columns, event strings, seeds, filenames, and protocol names are not mass-renamed solely for cosmetics.
7. Any future storage/protocol rename must be versioned and prove replay/fingerprint compatibility.

## Compatibility Layer

The following aliases intentionally reference the same proven implementations:

- `Descent` → legacy `Crawl`
- `LedgerEvent` → legacy `CrawlEvent`
- `Stratum` → legacy `CrawlFloor`
- `Sector` → legacy `CrawlLocation`
- `DescenderParticipation` → legacy `CrawlerParticipation`
- `DescenderAgentState` → legacy `CrawlerAgentState`
- `Echo` → legacy `StoryArc`
- `EchoReelAssembler` → legacy `HighlightReelAssembler`
- `Arbiter` → current deterministic director implementation

This is deliberate. It changes vocabulary without changing deterministic behavior.

## Deferred Renames

Do **not** mass-rename these yet:

- database columns and serialized field names
- historical event IDs/event strings in storage
- deterministic hash tokens used by existing seeds
- generated artifact paths already used by validation
- established internal protocols whose digests are under test

They may be migrated later behind explicit version boundaries.

## Product Identity Rule

From Slice 28B forward, public copy should treat:

- **The Underreach** as the world/system,
- **The Descent** as the competition,
- **Descenders** as its participants,
- **The Feed** as the spectator surface,
- **The Ledger** as authoritative history,
- **Echoes** as discovered story moments,
- **The Arbiter** as rule enforcement.

The old Crawl-era vocabulary should become increasingly invisible outside compatibility, migration, and historical implementation code.
