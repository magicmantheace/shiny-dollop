# Draft integration contract — specification only

This document describes a **future** interoperability interface. It does not imply that the engine, AthenZ, or Synveil currently implement it.

## Separation of responsibilities

- **Developmental AI:** bounded simulation environment, observations, chosen action proposals, outcomes, learned policy checkpoints and evaluation receipts.
- **AthenZ:** verified human-origin identity, consent, durable digital biography, permission scopes, goals, skill approval and interactive presentation.
- **Synveil:** platform telemetry, system policy, typed action authorization, rollback, and AI-disabled operation.

Human-origin memories must never be silently labeled as events experienced by the agent. Likewise, simulated experiences must never be presented as the consenting person's real life.

## Proposed versioned event envelope

```json
{
  "schema": "developmental-ai.event/v1",
  "event_id": "opaque-unique-id",
  "trace_id": "opaque-trace-id",
  "timestamp_utc": "2026-10-13T00:00:00Z",
  "subject_kind": "agent",
  "subject_id": "local-opaque-agent-id",
  "kind": "observation|goal_proposed|action_proposed|outcome|checkpoint",
  "environment_id": "sandbox:transfer-v1",
  "source_kind": "simulation",
  "consent_ref": null,
  "action_scope": "simulation-only",
  "payload": {}
}
```

This is **illustrative only**. The implementation must define bounded size, strict enums, version migration, deduplication/replay guarantees, trusted source attribution, and required fields for each event kind before it is considered a stable API. Do not record sensitive content in generic log fields.

## Memory sources

| Source | Authority | Use |
| --- | --- | --- |
| Human-provided verified record | AthenZ, consent-gated | Source person's historical data |
| Agent experience | Developmental AI with AthenZ provenance | Agent's own past actions and observations |
| Simulator reward signal | Developmental AI | Task success and learning only |
| Synveil telemetry | Synveil, scoped user policy | Machine environment information, not identity |

## Trust boundaries

The developmental learner produces **proposals**, not privileged tool commands. Synveil evaluates any typed requested system action against a deterministic policy, and AthenZ independently applies consent/identity restrictions. Neither text prompts nor learned memories can grant additional privileges. Private profile data, evaluation corpora, and adapters are stored outside every Git repository. All training/model promotions are versioned, attributable and reversible.

## Success criteria for initial bridge

- Standalone Developmental AI works without AthenZ or Synveil running.
- Simulation events are replayable and do not trigger real actions.
- AthenZ can display agent experiences without merging them into the human record.
- Faulting or stopping the learner does not prevent Synveil from booting or performing core desktop tasks.


## Offline simulator event export (experimental, 2026-10-13)

A separate simulation-only exporter now implements a bounded `developmental-ai.sim-ledger/v1` envelope with per-step `developmental-ai.event/v1` records from verified synthetic traces. It supports deterministic replay and optional trace binding, but is NOT an implementation of this document's full illustrative schema, does not include real UTC timestamps, and offers no service, authenticated IPC or integration with an actual AthenZ/Synveil runtime. See [EVENT_LEDGER.md](EVENT_LEDGER.md). Neither a recorded proposal nor a checksum grants authority over hardware or personal memory.
