# Living World Simulator v0.1 Architecture

## Authority boundary

The simulation service is the source of truth. Unreal Engine, the admin dashboard, automation, and future game servers are clients of the same API/event model.

No AI provider is allowed to mutate state directly. AI can propose structured intent; the command validator and simulation systems decide whether that intent is legal and executable.

## Runtime layers

1. **Domain state** — serializable world, region, kingdom, settlement, NPC, trade, army, war, culture, religion, resource, and history models.
2. **Deterministic simulation** — seeded RNG, world clock, economy, demography, NPC lives, kingdom utility planning, diplomacy, warfare, succession, settlement growth/decline, and event emission.
3. **Persistence** — SQLAlchemy-backed world snapshots, immutable event records, command audit records, and named snapshots. SQLite and PostgreSQL use the same implementation.
4. **Command gateway** — validates admin/player/system commands, applies them through domain methods, and records issuer/source/result.
5. **World API** — read models and authenticated write endpoints designed for the web dashboard and future Unreal service integration.
6. **Dashboard** — React/TypeScript operational UI for observing the world and issuing commands.
7. **AI adapter** — optional OpenAI-compatible strategic adviser/parser. It is not required for simulation progression.

## Simulation cadence

The engine advances in game-hour steps. Systems use their own accumulated cadence:

- hourly: active command effects, caravans/army movement, short-term needs
- daily: production, consumption, prices, trade, health, NPC goals
- monthly: births/deaths, migration, tax, settlement stability, diplomacy
- seasonal: harvest/climate/resource pressure, strategic priorities
- yearly: aging, succession checks, long-term cultural drift and chronicle summaries

Accelerated simulation invokes the same step functions repeatedly. `simulate 100 years` is therefore the same model as normal runtime, merely without wall-clock waiting.

## Procedural geography

v0.1 generates a strategic region, not Unreal geometry. A seed deterministically creates:

- regional elevation/climate/biome/resource descriptors
- landmark coordinates and strategic sites
- kingdom influence centers and territory ownership
- 5 towns and 20 villages
- roads/trade links represented as graph edges
- magic intensity and magical resources

The future Unreal continent generator can consume the strategic seed plus these constraints to build physical terrain while preserving authoritative settlement/resource positions.

## Population fidelity

A settlement tracks statistical population by ancestry. Exactly 100 generated people are promoted to persistent NPCs at v0.1 creation.

Persistent NPCs track identity, ancestry, age, family links, occupation, location, values, traits, goals, wealth, health, reputation, memories, and relationships. Important statistical inhabitants can later be promoted using a deterministic identity seed.

## Decision explainability

Kingdom decisions use scored considerations. Every strategic action includes a rationale structure, for example:

```json
{
  "action": "seek_food_trade",
  "score": 81.4,
  "reasons": {
    "food_pressure": 45,
    "treasury_strength": 18,
    "neighbor_relations": 14,
    "war_penalty": -4
  }
}
```

This makes emergent behavior inspectable without asking an LLM why something happened after the fact.

## Events and history

Significant changes emit immutable events containing event ID, world date, type, subjects, location, data, source, and importance. Current state is persisted separately for fast reads.

The chronicle is a view over real events. Admin intervention is explicitly marked and never disguised as organic simulation history.

## External commands

Commands use an envelope:

```json
{
  "type": "kingdom.set_priority",
  "target_id": "kingdom_0001",
  "parameters": {"priority": "food", "weight": 0.95},
  "issuer": "admin-dashboard"
}
```

The gateway provides queued/accepted/executing/completed/rejected/failed states and stores the result. v0.1 executes accepted commands synchronously inside the authoritative process; the schema is already suitable for moving the queue to Redis/NATS later.

## MMO compatibility

Future Unreal/game-server integration should primarily use:

- `GET /api/world`
- `GET /api/regions/{id}`
- `GET /api/settlements/{id}`
- `GET /api/npcs/{id}`
- `GET /api/events`
- `POST /api/commands`
- WebSocket `/api/stream`

Player actions will enter the same command/event pipeline with player identity and permission scopes instead of admin authority.

## Scaling path

The first scale boundary is the continent. A continent should eventually own its own simulation partition with asynchronous cross-continent trade, migration, diplomacy, and travel events. The v0.1 identifiers and event envelope include world/region ownership so this can be introduced without changing entity identity.
