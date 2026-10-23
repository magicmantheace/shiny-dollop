# Crawl v0.6 — Slices 19–21
## Spectator API, Unreal Bridge, and Authoritative Replay

## Purpose

Batch 5 turns the validated headless crawl into something an external presentation client can safely follow without giving that client authority over simulation truth.

The boundary is:

```text
AUTHORITATIVE CRAWL
  -> persisted Crawl state
  -> canonical CrawlEvent ledger
       |
       +-> spectator-safe projection
       |     -> REST spectator client
       |     -> web/mobile viewer later
       |
       +-> Unreal bridge frames
       |     -> spawn/interpolate/render only
       |
       +-> replay archive
             -> ordered canonical events
             -> deterministic digest
             -> causal event chains
```

The simulation remains authoritative. The API, Unreal, cameras, commentary, and replay UI are consumers.

---

# Slice 19 — Spectator API

`livingworld.spectator_state` uses explicit public allow-lists instead of serializing authoritative models directly.

This is intentional. Public payloads must not silently begin exposing new internal fields when authoritative models grow.

## Publicly excluded state

The spectator projection does not expose:

- crawler private `knowledge`,
- crawler `memories`,
- full personality traits/preferences,
- crawl `modifiers`,
- `_crawl_director` control state,
- `_semantic_ledger` internal indexes,
- dormant encounter definitions,
- encounter triggers/failure internals,
- raw event `data` payloads.

Semantic event metadata is projected through a separate public allow-list.

## Read-only API

`livingworld.spectator_api.create_spectator_app()` exposes a separate FastAPI application. It has no mutation endpoints.

Core endpoints:

| Endpoint | Purpose |
|---|---|
| `GET /health` | service/crawl heartbeat |
| `GET /api/spectator/crawl` | current crawl summary |
| `GET /api/spectator/floor` | renderable floor state |
| `GET /api/spectator/crawlers` | crawler directory |
| `GET /api/spectator/crawlers/{npc_id}` | crawler profile/build/current state |
| `GET /api/spectator/crawlers/{npc_id}/history` | public crawler event history |
| `GET /api/spectator/parties` | public party state |
| `GET /api/spectator/encounters` | non-dormant encounters only |
| `GET /api/spectator/events` | recent public event stream |
| `GET /api/spectator/deaths` | dead crawlers |
| `GET /api/spectator/leaderboard` | deterministic standings |
| `GET /api/spectator/trending` | semantic-interest ranking |
| `GET /api/spectator/replay` | replay manifest |
| `GET /api/spectator/replay/events` | replay event window/scrub data |
| `GET /api/spectator/replay/events/{event_id}/causes` | causal event chain |
| `GET /api/spectator/unreal/bootstrap` | Unreal bridge contract/bootstrap |
| `GET /api/spectator/unreal/frame` | current render frame + public event delta |

A separate client can follow a crawler by polling the profile/history/event endpoints with `after_tick` on the event stream. WebSocket transport can be added later without changing public state semantics.

---

# Slice 20 — Unreal Spectator Bridge Contract

`livingworld.unreal_spectator_bridge` defines protocol:

```text
crawl.unreal-spectator.v1
```

The first bridge is deliberately logical rather than spatial. The backend currently owns graph locations, not final 3D transforms.

Each frame contains:

- crawl ID,
- authoritative tick,
- floor number,
- active crawler IDs,
- authoritative logical location IDs,
- health/status/objective/party presentation hints,
- visible encounter state,
- public canonical events since an optional tick.

## Unreal is allowed to

- spawn visual representations,
- map logical locations to scene anchors,
- interpolate between authoritative frames,
- choose cameras,
- play presentational animation.

## Unreal must not

- resolve combat,
- change health,
- change inventory,
- change progression,
- teleport authoritative crawlers,
- create canonical events.

When physical coordinates/animation state are added, they should extend this protocol without moving authority into Unreal.

---

# Slice 21 — Authoritative Replay

`livingworld.replay_engine.ReplayArchive` builds a read-only replay package from:

1. the final authoritative Crawl state,
2. the complete persisted `CrawlEvent` ledger.

The previous persistence read cap of 1,000 events was widened to 10,000 because validated 100-crawler crawls already produce roughly 4,000–5,000 canonical events.

## Replay manifest

A manifest contains:

- crawl ID,
- seed,
- ruleset ID/version,
- first/last tick,
- event count,
- SHA-256 digest of the full authoritative event ledger,
- final Crawl fingerprint,
- floor count.

The event digest is independent of query ordering because events are canonically sorted by `(tick, event_id)` before hashing.

## Replay windows

Clients can request bounded replay windows by:

- start tick,
- end tick,
- actor/crawler ID,
- limit.

Public replay events use the same spectator-safe projection as live events.

## Cause chains

Replay can walk `semantic.causal_parent_ids` backward from a notable event. This provides a structured explanation path without inventing prose or making an LLM authoritative.

## Important limitation

This slice is an event-ledger replay interface, not yet full state-at-every-tick materialization.

The authoritative record is sufficient for presentation clients to replay the known sequence of canonical events and verify archive identity. Later replay work can add periodic state checkpoints and exact state reconstruction/scrubbing between checkpoints without changing this archive contract.

---

# Validation

Focused Batch 5 tests require:

1. public projections do not leak known private fields,
2. a separate TestClient can discover and follow a crawler through public endpoints,
3. replay contains the complete persisted event ledger,
4. replay event digest is stable regardless of input order,
5. replay final fingerprint equals the Crawl fingerprint,
6. semantic causal chains resolve parent events,
7. Unreal bridge calls do not mutate Crawl state,
8. Unreal bootstrap explicitly declares backend authority.

Local command:

```powershell
.\scripts\run-crawl-slices19-21-validation.ps1
```

Small checkpoint:

```powershell
.\scripts\run-crawl-slices19-21-validation.ps1 `
  -Crawlers 25 `
  -Floors 2 `
  -MaxSteps 5000 `
  -SkipFullRegression
```

Generated acceptance report:

```text
validation/crawl-v0.6-slices19-21-spectator.json
```

No GitHub Actions are required or used.

---

# Carry-forward technical debt

## BALANCE-001

The validated Batch 4 20 x 100 x 3 matrix had 100% survival. Mortality/deadline/combat tuning remains a product-balance issue, not a structural blocker for spectator infrastructure.

## SCALE-001

Detail-tier scheduling is validated and reduces scheduled cognition slots, but C/D abstract execution has not replaced the full authoritative Batch 3 gameplay path yet.

## REPLAY-001

Add periodic authoritative state checkpoints so a replay client can reconstruct exact state at arbitrary ticks instead of relying on final state + ordered event history alone.
