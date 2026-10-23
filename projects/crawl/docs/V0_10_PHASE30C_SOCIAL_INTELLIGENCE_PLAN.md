# Crawl v0.10 — Phase 30C Social Intelligence Plan

## Status

**Canonical phase:** 30C — Social Intelligence

**Accepted baseline:** Phase 30B complete at `fad6d557cc5c58adedd597e5b314ccc9fe9dd796`.

**Planned slice count:** 6

This document freezes the Phase 30C slice structure before implementation begins.

Phase 30B established an individual autonomous brain loop:

- 30B.1 — AI Brain Foundation
- 30B.2 — Intent Validation & Execution Bridge
- 30B.3 — Brain-Driven Descent Orchestration

Phase 30C builds deterministic social intelligence on top of that accepted individual-brain foundation.

The core authority rule remains unchanged:

> Social reasoning may observe, score, propose, or influence bounded decisions, but only deterministic simulation services may mutate canonical Crawl truth.

Free-form dialogue, generated conversations, commentator voices, cinematic storytelling, interviews, and narrative prose are explicitly deferred to Phase 31.

---

# 30C.1 — Social State Foundation

## Purpose

Create the authoritative relationship state shared between participating Descenders without introducing dialogue or unbounded social reasoning.

## Canonical relationship dimensions

At minimum, support bounded deterministic values for:

- trust,
- respect,
- affection,
- fear,
- resentment,
- gratitude,
- rivalry,
- familiarity.

The representation may evolve during implementation, but it must remain deterministic, serializable, checkpoint-safe, and independent of presentation systems.

## Requirements

- Canonical pairwise or directed relationship identity.
- Deterministic initialization from accepted Crawl/Descender state.
- Explicit relationship bounds and normalization rules.
- Structured relationship snapshots and digests.
- Ledger provenance for initialization and authoritative changes.
- Save/load/checkpoint round-trip support.
- No Unreal or presentation feedback into social truth.
- No prose treated as relationship state.

## Acceptance gate

Identical seeds and canonical state produce identical social state, relationship values survive serialization/checkpoint round trips, invalid relationship mutations are rejected, and the existing 30A/30B deterministic authority remains intact.

---

# 30C.2 — Social Memory & Relationship Evolution

## Purpose

Make relationships evolve because of actual authoritative events rather than scripted story beats.

## Event-linked social memories

Examples include:

- rescued another Descender,
- abandoned another Descender,
- shared a supply or item,
- stole or contested loot,
- fought beside someone,
- caused or prevented injury,
- protected another Descender,
- accepted or refused aid,
- kept or violated a structured promise,
- witnessed bravery, retreat, sacrifice, or selfish behavior.

Every important social memory must reference real canonical event IDs.

## Requirements

- Structured social-memory records.
- Importance and confidence where useful.
- Deterministic reinforcement and bounded decay.
- Deterministic mapping from qualifying canonical events to relationship deltas.
- Prevention of duplicate processing of the same event.
- Relationship evolution must remain reproducible under replay.
- No generated narrative may create a canonical memory that did not originate from simulation truth.

## Acceptance gate

Earlier authoritative events measurably and reproducibly alter later relationship state across multiple Strata, and replaying the same event history reconstructs the same social memory and relationship outcome.

---

# 30C.3 — Social Intent & Interaction Execution

## Purpose

Extend the accepted 30B proposal/execution membrane with bounded social actions.

## Candidate social actions

Initial bounded actions may include:

- help,
- protect,
- warn,
- share item,
- share survival supply,
- recruit,
- accept recruitment,
- refuse recruitment,
- follow,
- leave,
- support recovery,
- withhold information,
- challenge another Descender.

Implementation may split or rename individual actions as long as the canonical slice purpose remains unchanged.

## Authority flow

```text
Canonical state
    ↓
Bounded social observation
    ↓
Brain/social proposal
    ↓
Deterministic validation
    ↓
Preview / feasibility checks
    ↓
Canonical simulation service execution
    ↓
Structured Ledger event
```

The proposing brain may never mutate party membership, item ownership, relationship state, movement, combat state, or other canonical truth directly.

## Acceptance gate

Valid social proposals execute only through deterministic services, stale/impossible proposals are rejected without mutation, and equivalent inputs produce identical decisions and Ledger events.

---

# 30C.4 — Parties, Alliances & Leadership

## Purpose

Create persistent authoritative group structures so Descenders can behave as coordinated teams rather than independent agents occupying nearby Sectors.

## Requirements

- Party identity and membership.
- Alliance or cooperation state where distinct from party membership.
- Deterministic join/leave rules.
- Leadership state.
- Leadership acceptance and replacement.
- Shared or negotiated objectives.
- Coordinated movement where appropriate.
- Coordinated retreat and support behavior.
- Resource/item sharing rules through canonical services.
- Group membership must survive Stratum progression and checkpoint/replay.
- Group structures must not create a second copy of participant truth.

## Acceptance gate

Autonomous Descenders can form, maintain, alter, and dissolve groups based on canonical social state, and those groups measurably change movement, survival, resource, and encounter behavior without scripted story logic.

---

# 30C.5 — Rivalry, Betrayal & Social Conflict

## Purpose

Support adversarial social arcs that emerge from accumulated relationship state, incentives, memory, and current circumstances.

## Candidate behaviors

- grudge formation,
- rivalry escalation,
- refusal of aid,
- abandonment,
- alliance breaking,
- party departure under conflict,
- loot disputes,
- structured deception state where justified,
- betrayal,
- revenge-seeking,
- unwillingness to trust warnings or leadership.

Betrayal must not be implemented as a context-free random action. It should require deterministic eligibility and scoring based on canonical state.

## Requirements

- Explicit betrayal/conflict preconditions.
- Relationship and memory consequences.
- Clear Ledger provenance.
- No hidden mutation through generated text.
- Deterministic conflict outcomes where simulation rules own the result.
- Social conflict must remain compatible with the accepted combat/item/death systems.

## Acceptance gate

Multi-Stratum simulations can produce reproducible rivalry and betrayal arcs whose causes can be traced back to prior canonical events, relationship state, and bounded decisions.

---

# 30C.6 — Group Decision & Autonomous Social Orchestration

## Purpose

Complete Phase 30C by integrating all prior social slices into unattended multi-character Descent orchestration.

This is the social equivalent of 30B.3.

## Required behavior

During an unattended Descent:

- Descenders evaluate one another through bounded social state.
- Parties can form and dissolve.
- Leadership can emerge and change.
- Trust and memory affect cooperation.
- Resource sharing can occur.
- Rivalries can alter decisions.
- Betrayal can occur only when deterministic preconditions support it.
- Selfish and cooperative strategies may both emerge.
- Existing individual brain execution remains authoritative only through the deterministic execution membrane.
- Social state persists across Strata.
- Checkpoint/resume produces the same final result as uninterrupted execution.

## Proof expectations

The acceptance proof should include:

- multiple Strata,
- multiple autonomous Descenders,
- at least one cooperative social arc,
- at least one meaningful relationship-state divergence,
- party formation or alliance behavior,
- social influence on canonical decisions,
- multi-seed or targeted deterministic tests for rivalry/conflict,
- checkpoint/replay equivalence,
- deterministic rerun equality,
- full repository regression suite.

The proof should report useful structured social metrics such as party formations, party dissolutions, aid/share events, leadership changes, relationship changes, rivalry events, betrayal events when present, and surviving social-history digests.

## Acceptance gate

A full autonomous multi-Stratum Descent produces deterministic, replayable, checkpoint-safe social history without human intervention and without allowing social reasoning, presentation, Unreal, or generated prose to become canonical authority.

---

# Phase Boundary

After 30C.6 passes acceptance:

**Phase 30C — Social Intelligence is complete.**

The 30-series is complete.

The next canonical phase is:

**Phase 31 — Dialogue / Commentary**

Phase 31 may translate canonical events, memories, relationships, group state, and brain decisions into watchable or listenable presentation content. It may enrich expression, but it must remain downstream of deterministic simulation truth.

---

# Frozen Slice Order

1. **30C.1 — Social State Foundation**
2. **30C.2 — Social Memory & Relationship Evolution**
3. **30C.3 — Social Intent & Interaction Execution**
4. **30C.4 — Parties, Alliances & Leadership**
5. **30C.5 — Rivalry, Betrayal & Social Conflict**
6. **30C.6 — Group Decision & Autonomous Social Orchestration**

Do not add, remove, renumber, or rename Phase 30C slices without explicitly updating this canonical planning document first.
