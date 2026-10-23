# Underreach v0.10 — Slice 30C.5: Rivalry, Betrayal & Social Conflict

## Status

Implementation slice following accepted **30C.4 — Parties, Alliances & Leadership**.

## Purpose

30C.5 gives canonical social history meaningful negative consequences without introducing random drama.

The governing rule is:

> **Betrayal must arise from accumulated canonical social state plus a concrete incentive. It must never be selected by a random betrayal roll.**

30C.1 owns relationship values. 30C.2 owns event-linked memory and relationship evolution. 30C.3 owns bounded social interactions. 30C.4 owns parties, alliances, and leadership. 30C.5 consumes those accepted truths to validate and execute bounded social conflict.

The simulation remains authoritative. Proposal providers, Unreal, presentation systems, dialogue systems, and future AI systems cannot directly mutate conflict truth.

## Protocols

- Slice: `underreach.rivalry-betrayal-social-conflict.v1`
- Observation: `underreach.social-conflict-observation.v1`
- Intent: `underreach.social-conflict-intent.v1`
- Decision: `underreach.social-conflict-decision.v1`
- Result: `underreach.social-conflict-result.v1`
- Implementation: `30c5.1`

## Bounded conflict actions

30C.5 supports exactly these canonical conflict operations:

- `refuse_aid`
- `steal_loot`
- `deceive`
- `expose_deception`
- `abandon_party`
- `betray_party`
- `break_alliance`
- `seek_revenge`

This is a bounded data contract, not free-form prose.

## Deterministic conflict observation

A conflict observation is immutable and contains only canonical state available at proposal time:

- source and target Descender IDs,
- current tick / Stratum,
- source and target Sector,
- source and target party membership,
- colocation,
- the source's directed relationship toward the target,
- negative social-memory count,
- major negative-memory count,
- negative-memory pressure,
- positive-memory pressure,
- source Ledger event IDs behind the negative memories,
- relationship pressure,
- bond resistance,
- base grievance,
- relationship / memory / party snapshot digests,
- canonical-state digest.

No random value exists in the observation or eligibility calculation.

## Conflict pressure

The source crawler's conflict pressure is derived from accepted 30C state.

Negative pressure includes:

- resentment,
- rivalry,
- negative trust,
- negative respect,
- fear,
- negative affection,
- event-linked negative memories such as betrayal, abandonment, loot theft, injury, refused aid, broken commitments, and witnessed selfishness.

Resistance includes:

- positive trust,
- respect,
- affection,
- gratitude,
- positive social memories such as rescue, protection, healing, sharing, promise keeping, and fighting together.

An explicit bounded incentive is then applied.

Allowed incentive categories are:

- escape,
- leadership,
- loot,
- resource scarcity,
- revenge,
- safety,
- survival.

Incentive strength is constrained to `[0, 1]`.

## Action thresholds

Each hostile action has a deterministic eligibility threshold.

Lower-impact conflict can occur at lower accumulated pressure. Higher-impact actions require stronger accumulated pressure.

In particular:

- `betray_party` and `break_alliance` are high-impact actions,
- high-impact actions require an incentive strength of at least `0.35`,
- high-impact actions also require canonical negative-memory evidence,
- either at least one major negative memory or at least two negative memory threads must exist,
- the source Ledger event IDs supporting that evidence are carried into the conflict decision and execution trace.

Therefore a neutral crawler cannot betray an ally simply because an incentive is large.

## Advisory proposal boundary

`ConflictIntent` is advisory only.

Proposal generation must not mutate:

- relationships,
- memory,
- parties,
- alliances,
- items,
- deceptions,
- revenge state,
- Ledger history.

Before execution the simulation rebuilds a fresh conflict observation.

If the proposal observation digest is stale, execution is rejected with no mutation.

## Refusing aid

An accepted `refuse_aid` records canonical `AID_REFUSED` history.

30C.2 processes that real event so the affected crawler may accumulate reduced trust and increased resentment.

The conflict layer does not invent the memory separately.

## Loot conflict

`steal_loot` is not an abstract dispute flag.

The target must canonically own the item and both crawlers must be colocated.

Accepted execution:

1. transfers the real `CrawlItem` through canonical item ownership,
2. records `LOOT_STOLEN`,
3. adds provenance to the item,
4. lets 30C.2 create/evolve the victim's social memory and relationship state.

## Structured deception

Deception is deliberately structured rather than textual.

Allowed claim classes are bounded identifiers such as:

- alliance commitment,
- danger level,
- exit route,
- intent to share,
- loot location,
- resource need.

Creating a deception stores a concealed canonical record and `DECEPTION_CREATED` Ledger event.

A concealed lie does **not** create a fake social memory merely because it exists.

When the victim later exposes the deception, the simulation records a canonical broken-commitment event (`PROMISE_VIOLATED`). Only then does 30C.2 update memory and relationship state.

Free-form lying dialogue remains outside this slice and belongs to later dialogue/presentation work.

## Party abandonment and betrayal

`abandon_party` and `betray_party` both use 30C.4's canonical party-membership authority to remove the departing crawler.

They are not equivalent social facts:

- abandonment creates `abandoned` memories,
- betrayal creates `betrayed` memories.

Every remaining affected party member receives an explicit structured social fact sourced from the single canonical event.

Party validity, leader transfer, and minimum-size disband rules remain owned by 30C.4.

## Hostile alliance breaking

30C.4 intentionally permits only non-hostile alliance dissolution.

30C.5 does not weaken that API.

Instead, an evidence-backed hostile break:

1. requires the acting and target crawlers to be the leaders of two allied parties,
2. validates accumulated conflict evidence and incentive,
3. removes the active alliance from the 30C.4 active alliance registry,
4. archives the original alliance plus break provenance under 30C.5,
5. records `ALLIANCE_BETRAYAL`,
6. produces explicit `betrayed` social facts for the affected allied party.

This keeps 30C.4's non-hostile contract intact while making 30C.5 the sole owner of hostile alliance breaking.

## Revenge seeking

`seek_revenge` creates a persistent structured revenge target backed by the source event IDs that produced the grievance.

30C.5 revenge state does **not** start combat or force movement.

It is a canonical motivation/state input for later autonomous social orchestration.

## Rivalry escalation

30C.5 does not directly write arbitrary rivalry values.

Actions such as betrayal and loot theft produce real Ledger events. 30C.2 then applies its accepted deterministic memory rules, which can increase:

- resentment,
- rivalry,
- fear,
- negative trust,
- other existing relationship dimensions.

This preserves one relationship-authority path instead of creating a second conflict-only relationship system.

## Persistence and deterministic replay

All 30C.5 state lives inside canonical `Descent` state:

- conflict execution records,
- deception records,
- revenge records,
- hostile alliance-break archive.

Existing persistence and checkpoint systems therefore carry it automatically.

The acceptance proof must establish:

- independent identical runs produce identical canonical state,
- snapshot digests match,
- Ledger IDs match,
- checkpoint restore is exact,
- stale/rejected proposals are side-effect free.

## Explicit exclusions

30C.5 does **not** add:

- random betrayal rolls,
- free-form deception dialogue,
- generated conversations,
- autonomous social scheduling across all crawlers,
- group-level unattended decision orchestration,
- revenge combat execution,
- cinematic narration,
- presentation feedback into simulation truth.

## Acceptance gate

The local validation gate must end with:

```text
[30C.5] PASS
```

Acceptance requires:

1. accepted 30A.1 through 30C.4 regressions pass,
2. focused 30C.5 tests pass,
3. neutral state cannot betray from incentive alone,
4. high-impact conflict is backed by real negative evidence,
5. party betrayal preserves canonical party invariants,
6. hostile alliance break is archived under 30C.5,
7. real loot ownership changes during loot theft,
8. deception memory appears only after exposure,
9. revenge state remains non-combat,
10. deterministic proof reproduces exactly,
11. checkpoint restore reproduces exactly,
12. full repository regression suite passes.

## Next canonical slice

**30C.6 — Group Decision & Autonomous Social Orchestration**

30C.6 will connect the accepted individual brain, social state, social memory, social interaction, group structure, and social-conflict systems into unattended multi-crawler social behavior while preserving deterministic simulation authority.
