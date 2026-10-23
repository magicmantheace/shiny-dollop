# External Command Interface

All state-changing external operations use `POST /api/commands` with `X-Admin-Key` authentication.

```json
{
  "type": "kingdom.set_priority",
  "target_id": "kingdom_0001",
  "parameters": {"priority": "food", "weight": 0.95},
  "issuer": "operations-console"
}
```

Every command receives a command ID and progresses through queued, accepted, executing, completed/rejected/failed states. Completed interventions also create an `ADMIN_COMMAND` history event and retain their original issuer.

## World commands

- `world.pause`
- `world.resume`
- `world.set_speed` — `{ "speed": 100 }`
- `world.advance` — `{ "amount": 10, "unit": "year" }`
- `world.disaster` — `{ "disaster": "famine|plague|earthquake", "severity": 0.0..1.0 }`; target may be a settlement, kingdom, or omitted for the whole region.

## Kingdom commands

Target a kingdom ID.

- `kingdom.set_priority` — `{ "priority": "food|wealth|security|expansion|stability|...", "weight": 0.0..1.0 }`
- `kingdom.set_tax` — `{ "rate": 0.0..0.75 }`
- `kingdom.declare_war` — `{ "target_kingdom_id": "kingdom_0002", "goal": "control the iron pass" }`
- `kingdom.change_ruler` — `{ "npc_id": "npc_0000009" }`
- `kingdom.mobilize` — `{ "destination_settlement_id": "settlement_00012" }`

## Settlement commands

The same interface applies to villages, towns, and future city/capital settlement classes.

- `settlement.add_resource` — `{ "resource": "grain", "amount": 500 }`
- `settlement.set_stability` — `{ "stability": 0.8 }`
- `settlement.build` — `{ "building": "walls", "count": 1 }`
- `settlement.change_kingdom` — `{ "kingdom_id": "kingdom_0002" }`

## NPC commands

- `npc.travel` — `{ "settlement_id": "settlement_00008" }`
- `npc.kill` — `{ "cause": "assassination" }`
- `npc.set_goal` — `{ "goal": "become_mayor" }`
- `npc.set_occupation` — `{ "occupation": "merchant" }`

## War commands

- `war.end` — optional `{ "winner_kingdom_id": "kingdom_0001", "reason": "negotiated surrender" }`

## Offline natural command parser

`POST /api/commands/natural` first tries a deterministic parser, so basic text commands work without an AI provider.

Examples:

```text
pause world
resume world
advance 10 years
kill npc_0000007 assassination
tell npc_0000007 travel settlement_00004
tell kingdom_0001 declare-war kingdom_0002 iron pass claim
give settlement_00001 500 grain
set kingdom_0001 priority food 0.95
```

If the deterministic parser cannot understand the command and an OpenAI-compatible model is configured, the optional AI parser may translate it to the same structured command envelope. The resulting command still passes through normal validation and auditing.

## World generation and snapshots

These use dedicated admin endpoints:

- `POST /api/admin/world/generate`
- `POST /api/admin/snapshots`
- `GET /api/admin/snapshots`
- `POST /api/admin/snapshots/restore`

Regenerating a world intentionally resets mutable world state, command audit history, snapshots, and historical-event storage for that database.
