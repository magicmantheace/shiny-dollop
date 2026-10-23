# Unreal Engine 5 Integration Contract

LivingWorld is deliberately not an Unreal subsystem. It is the authoritative persistent-world service that future Unreal dedicated servers consume.

## Ownership

### LivingWorld owns

- world clock and calendar
- kingdom and settlement ownership
- statistical population and persistent NPC identity/life history
- economies, resources, strategic trade, diplomacy, armies, and wars
- world history and historical causality
- strategic geography constraints and procedural seed
- NPC memories/relationships that must survive server restarts

### Unreal/game servers own

- player movement and input
- moment-to-moment NPC movement
- combat/physics/collision
- animation
- ability execution
- local encounter spawning
- visual terrain and World Partition cells
- replication to connected clients

The game server must never ask an LLM to resolve combat or authoritative state.

## Initial bootstrap

A continent/region game server can bootstrap from:

```text
GET /api/world
GET /api/map
GET /api/regions/{region_id}
GET /api/settlements/{settlement_id}
GET /api/npcs?settlement_id={settlement_id}
GET /api/armies
GET /api/wars?active_only=true
```

The region seed plus strategic map positions constrain Unreal's future terrain generator so a town, mine, river crossing, or magical site remains the same location in the persistent simulation even if its physical representation is generated separately.

## Entity identity

Never use an entity's display name as a key. Unreal actors/components should retain their LivingWorld ID, for example:

```text
ULivingWorldIdentityComponent
  EntityId = npc_0000042
  EntityType = npc
```

Names, titles, owners, and even political entities can change. IDs are historical identity.

## Active-area promotion

When a player enters a settlement:

1. Unreal requests authoritative settlement state.
2. Persistent NPCs in that settlement are instantiated as full actors.
3. Statistical population is represented through ambient/generated actors as needed.
4. Important ambient characters can later be promoted to persistent LivingWorld NPCs through a dedicated gameplay-service API.
5. When the area unloads, durable consequences are written back as structured events/commands; transient movement is discarded.

## Gameplay event contract

The future game-server ingress should use a restricted service credential and structured events rather than admin god-mode access.

Suggested envelope:

```json
{
  "event_id": "server-unique-id",
  "player_id": "player_123",
  "type": "NPC_KILLED",
  "target_ids": ["npc_0000042"],
  "location_id": "settlement_00012",
  "parameters": {
    "cause": "player combat",
    "weapon_id": "item_..."
  }
}
```

The LivingWorld service validates the event, applies the durable consequence, and emits immutable history. Player actions that do not produce durable world effects remain entirely inside the game server.

## Player historical identity

Future player records should use persistent player IDs independent of character display names. Historical events can then retain references such as:

```text
PLAYER_DEED
player_123
slayed creature_88
location settlement_12
Year 327
```

A character rename does not rewrite history.

## Event stream

`WS /api/stream` broadcasts world events to monitoring clients today. A future game-server subscription should be scoped by continent/region and entity relevance so dedicated servers receive only events capable of changing their active cells.

## Scaling to continents

The v0.1 service contains one strategic region. At continental scale, use the continent as the primary simulation partition:

```text
World Directory
  ├─ Continent A simulation
  ├─ Continent B simulation
  └─ Continent C simulation
```

Cross-partition operations become asynchronous durable messages for trade, migration, diplomacy, travel, and war. Entity IDs remain globally unique, so partition movement does not change identity.

## Security boundary

The current dashboard admin key is god-mode and must never be embedded in an Unreal client. Production should have separate credentials/scopes for:

- read-only public clients
- game dedicated servers
- operations/admin dashboard
- simulation workers
- AI advisory services

Only trusted dedicated servers should be permitted to submit player-originated durable events.
