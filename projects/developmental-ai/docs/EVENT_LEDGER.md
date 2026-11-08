# Simulation event ledger v1 — experimental export format

`developmental_ai.event_ledger` exports strictly **simulation-only** events from verified `curriculum`, `delayed_choice`, or `occluded_navigation` traces. It has no socket listener, privileged executor, persistent queue, network transport or identity store. It is a building block for future AthenZ/Synveil integration and is not a stable cross-project API.

## Data contract

A ledger contains `schema=developmental-ai.sim-ledger/v1`, `source_kind=simulation`, `scope=simulation-only`, `subject_id` (short, opaque slug), `trace_sha256`, and a list of events. Each event has `schema=developmental-ai.event/v1`, deterministic `event_id`, `trace_id`, integer sequence, source/subject/scope, a kind and small payload, a `previous_sha256` link, and its own SHA-256. Kinds are `observation`, `action_proposed`, `outcome`, and `episode_complete`. Every simulated action generates a triplet and the episode concludes with one completion event.

The default `subject_id=local-agent` is not a person's name. The trace records no human memories. All observation contents are from a bounded synthetic task; the API deliberately has no user-data import route. It rejects unknown fields, duplicate/missing/reordered events, oversized payloads, untrusted source/authority labels, and incorrect chains.

## Commands

```bash
python -m developmental_ai.curriculum trace --policy oracle --task collect --index 0 > trace.json
python -m developmental_ai.event_ledger export --trace-file trace.json > ledger.json
python -m developmental_ai.event_ledger verify --ledger-file ledger.json --trace-file trace.json
```

Passing `--trace-file` to ledger verification **also independently replays the source trace**, which detects a ledger whose hashes have been recomputed after the individual event contents were modified. Verification without the source trace checks only the internal ledger structure/hash chain. Neither path authenticates a publisher: anyone can generate a new valid trace or recompute all ledger hashes. Hashes are integrity markers, not signatures or independent attestation.

## Integration rule

AthenZ may eventually display these events as **agent simulation history**, never as a consenting human's autobiographical memory. Synveil may eventually read them as simulation telemetry, but neither a recorded `action_proposed` nor a text field authorizes a real-world action. Any future real action requires a separate deterministic policy and explicitly scoped owner permission. A versioned authenticated transport, replay-safe receipts, retention/erasure design, and privacy review are required before exposing this as a production IPC interface.


## Occluded navigation trace normalization

For `developmental-ai.occluded-trace/v1` traces, the exporter reads the
`outcome.events` list. Observation payloads contain both the visible wall/cue
observation and the internally estimated working-memory state; outcome payloads
contain the following observation, memory estimate, reward and event. The final
`episode_complete` payload contains only the summary and never embeds the
complete event list again. The same event count, payload and size limits apply.
The exporter first verifies every simulated transition, then verifies the event
chain against the original trace on request. It still does **not** authenticate
policy origin, user identity, or access rights.

## Experimental `uncertain-ring/v1` source

The exporter now accepts independently replayable `developmental-ai.uncertain-trace/v1` traces, with observation payloads showing noisy odometry/landmark signals, `memory` carrying a compressed estimator state and `outcome` carrying the next estimator state. Neither the filter nor the learned policy becomes authoritative. Like other trace schemas, the only permitted scope remains `simulation-only`; checksum chains do not authenticate physical events or the source of an identity.
