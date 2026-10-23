# Underreach v0.10 — Slice 30C.6

## Group Decision & Autonomous Social Orchestration

### Status

Implementation slice for local acceptance.

### Accepted baseline

- 30C.5 — Rivalry, Betrayal & Social Conflict
- Accepted SHA: `09247d00c83f1d57cc94eb9df65335a9aab15acf`

### Purpose

30C.6 is the capstone of Phase 30C — Social Intelligence.

The accepted social stack already owns:

- 30C.1 — canonical directed relationship state
- 30C.2 — event-linked social memory and relationship evolution
- 30C.3 — bounded social intent validation/execution
- 30C.4 — persistent parties, alliances, leadership, and coordination
- 30C.5 — rivalry, betrayal, deception, alliance breaking, and revenge state

30C.6 connects those systems into an unattended deterministic social cadence so multiple crawlers can reason around one another over time without a human issuing social commands.

The fundamental architecture remains:

```text
Deterministic Crawl Simulation
        ↓
Authoritative Event Ledger / canonical state
        ↓
Presentation manifests
        ↓
Unreal Engine 5.8
```

The simulation still decides what actually happens.

---

## Authority boundary

30C.6 may decide **which bounded social action to attempt**.

30C.6 may not directly mutate relationship, memory, party, alliance, item, conflict, gameplay, or presentation truth.

Every canonical mutation continues through the service that already owns it:

- recruitment / sharing → 30C.3
- party membership / leadership / alliance state → 30C.4
- betrayal / abandonment / hostile alliance breaking → 30C.5
- ordinary gameplay movement / encounters / survival / progression → accepted 30B.3 / 30A stack

Therefore:

```text
Social observation + traits + canonical history
        ↓
30C.6 deterministic strategy / choice
        ↓
Existing bounded social service
        ↓
Simulation validation
        ↓
Canonical mutation + Ledger event
```

No presentation or Unreal state may feed back into this process.

---

## Protocol

- Slice protocol: `underreach.group-social-orchestration.v1`
- Implementation version: `30c6.1`
- Metadata key: `_group_social_orchestration`

### Canonical orchestration events

- `GROUP_SOCIAL_ORCHESTRATION_INITIALIZED`
- `GROUP_SOCIAL_ORCHESTRATION_STEP_RESOLVED`

The underlying accepted services continue emitting their own canonical social events.

---

## Strategy vocabulary

30C.6 defines only three bounded deterministic social strategy labels:

- `cooperative`
- `balanced`
- `selfish`

A strategy is derived from accepted deterministic crawler traits plus current canonical relationship history.

It is not a random personality roll at runtime.

The strategy label is advisory orchestration context. It does not itself mutate canonical state.

---

## Autonomous recruitment and party formation

At each social step, currently active and colocated unpartied crawlers may be considered for recruitment.

Candidate ordering is deterministic.

Recruitment is influenced by:

- sociability
- empathy
- loyalty
- suspicion
- pair affinity
- current relationship state

The 30C.6 orchestrator does not create a party directly.

It must:

1. propose recruitment through 30C.3;
2. execute the recruitment offer through 30C.3;
3. deterministically evaluate acceptance/refusal;
4. execute the response through 30C.3;
5. materialize an accepted offer through 30C.4.

This preserves the complete accepted recruitment contract.

---

## Autonomous leadership

For every active party, 30C.6 compares the current leader with the accepted 30C.4 deterministic leader calculation.

If another member is the deterministic best leader, 30C.6 asks 30C.4 to perform the transition.

30C.6 does not write `leader_npc_id` directly.

Leadership history therefore remains Ledger bound and replayable.

---

## Group policy / posture

30C.6 may use the current strategy mix of a party to select an existing bounded 30C.4 posture.

Initial orchestration policy:

- cooperative majority → `support`
- otherwise → `advance`

This does not change combat resolution authority.

It is canonical group intent only.

---

## Cooperative resource behavior

A cooperative party member may autonomously share one owned survival resource with a colocated party member that has no survival resource.

The actual transfer must execute through 30C.3 `share_supply`.

Therefore:

- item ownership remains canonical;
- 30A.4 resource validation remains authoritative;
- 30C.2 automatically receives the real sharing event;
- trust / gratitude history can evolve from what actually happened.

No artificial “helpfulness” memory may be invented.

---

## Voluntary party departure

A crawler with a sufficiently strong deterministic solitary drive may leave a party without betrayal.

The drive is based on accepted traits such as:

- suspicion
- low sociability
- low loyalty
- competitiveness
- greed

The departure executes through 30C.4.

If the party falls below the accepted minimum active size, 30C.4 owns disbanding.

This allows parties to dissolve unattended without treating every departure as betrayal.

---

## Rivalry and hostile conflict

30C.6 may notice that a party member or allied leader has accumulated sufficient negative relationship pressure to justify a conflict attempt.

30C.6 may then propose:

- `abandon_party`
- `betray_party`
- `break_alliance`

But 30C.5 remains the sole authority for deciding whether that action is legal.

The accepted 30C.5 rules remain unchanged:

- no random betrayal roll;
- high-impact betrayal requires canonical negative evidence;
- incentive alone cannot create betrayal;
- rejected conflict proposals are side-effect free.

This is how rivalry affects autonomous group decisions without bypassing the conflict membrane.

---

## Autonomous alliances

Two active parties may form an alliance when their leaders have sufficient deterministic social affinity.

The actual alliance mutation executes through 30C.4.

If later canonical rivalry and negative memories make hostile breaking eligible, the break executes through 30C.5.

30C.6 therefore coordinates the decision sequence but owns neither alliance storage nor betrayal semantics.

---

## Social cadence and gameplay cadence

`GroupSocialOrchestrationService.run()` performs one 30C.6 social step before each accepted 30B.3 gameplay step.

The social layer does not replace the brain-driven descent runner.

30B.3 remains responsible for:

- crawler navigation proposals
- deterministic gameplay fallback
- survival-clock advancement
- encounters
- caches
- loot collection
- survival consumption
- Stratum progression
- completion / extinction

30C.6 adds social context around that runtime instead of forking gameplay authority.

---

## Persistence and replay

30C.6 metadata lives inside the canonical `Descent` state tree.

The accepted persistence and checkpoint systems therefore serialize:

- social step count
- deterministic strategy labels at each step
- social decisions and outcomes
- active party/alliance state through their owning layers
- social conflict history through 30C.5
- all referenced Ledger event IDs

A restored checkpoint must reproduce the same 30C.6 snapshot exactly.

---

## Determinism requirements

30C.6 forbids runtime random social actions.

Given identical:

- crawl seed
- canonical state
- crawler traits
- relationship state
- social memories
- parties / alliances
- gameplay state

30C.6 must produce the same social strategy classifications and action ordering.

The acceptance proof runs multiple independent seeds and then repeats the full proof so the resulting proof digest must be identical.

---

## Acceptance proof

The deterministic proof must cover at least three seeds.

Across the proof it must demonstrate:

- unattended party formation;
- unattended party dissolution;
- deterministic leadership changes;
- unattended alliance formation;
- evidence-gated hostile party/alliance conflict;
- cooperative / balanced / selfish strategy observation;
- continued accepted 30B.3 gameplay progression;
- canonical Ledger provenance;
- exact checkpoint restore;
- exact repeated multi-seed proof digest.

The proof intentionally seeds canonical positive and negative social history in controlled places so the orchestrator is forced to respond to both cooperation and grievance conditions. The resulting actions themselves remain autonomous 30C.6 choices executed through accepted services.

---

## Explicit non-goals

30C.6 does **not** add:

- free-form dialogue
- generated conversations
- interviews
- narration
- commentary
- cinematic storytelling
- speech synthesis
- presentation-authoritative social behavior
- Unreal-authoritative decision making

These remain Phase 31+ concerns.

---

## Phase boundary

Phase 30C asks:

> Can multiple autonomous crawlers build meaningful social history together?

After 30C.6 acceptance, the answer must be yes at the deterministic simulation layer.

The next canonical phase is:

**Phase 31 — Dialogue / Commentary**

Phase 31 may express the social history created by 30C, but it may not rewrite that history.
