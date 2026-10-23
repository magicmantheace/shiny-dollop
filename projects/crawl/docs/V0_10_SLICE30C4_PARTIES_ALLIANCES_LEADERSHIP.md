# Underreach v0.10 Slice 30C.4 — Parties, Alliances & Leadership

## Status
Implementation slice. Acceptance requires the local validation gate to end in explicit `[30C.4] PASS`.

## Baseline
Accepted 30C.3 — Social Intent & Interaction Execution.

## Purpose
30C.4 converts accepted structured social agreements into persistent group truth. The simulation remains the sole canonical authority.

30C.3 answers: can one crawler propose and execute bounded social interactions?

30C.4 answers: can accepted cooperation become durable parties and alliances with deterministic leadership, policy, objectives, and coordinated movement?

## Canonical state
The existing `CrawlParty` domain object is the party source of truth. 30C.4 does not invent a parallel party model.

Canonical party fields include:
- party id
- leader
- member ids
- loot policy
- cohesion
- formed tick
- active state
- shared goal
- disagreement

Each participant mirrors active membership through `current_party_id`, and the existing Crawl domain validator continues to enforce that mirror.

30C.4 metadata stores only slice-specific provenance and coordination state:
- consumed accepted recruitment offer ids
- active party provenance
- bounded party posture
- leadership/membership/policy/movement Ledger traces
- alliance registry
- coordination records

## Recruitment materialization
Only a 30C.3 recruitment offer with status `accepted` may create or extend a party.

Rules:
1. Each accepted offer can be materialized exactly once.
2. Both endpoints must still be active in the current Stratum.
3. A free recruiter + free target creates a new party.
4. A recruiter already in an active party may add a free accepted target to that party.
5. A target already in another party is rejected in 30C.4; party switching is not implied by recruitment acceptance.
6. The recruiter is initial leader when a party is first materialized.

## Leadership
30C.4 provides deterministic capability-based leader election.

Election score is derived only from canonical crawler state:
- leadership skill 50%
- negotiation skill 20%
- sociability 10%
- loyalty 10%
- courage 10%

Stable crawler id resolves exact ties.

Leader departure triggers deterministic replacement when at least two members remain.

## Party lifecycle
An active social party must have at least two members.

A member may leave voluntarily. When departure would reduce an active party below two members, the party is disbanded and all remaining `current_party_id` mirrors are cleared.

30C.4 does not interpret ordinary leaving as betrayal.

## Shared policy and objectives
30C.4 owns structured party-level cooperation settings:
- `shared_goal`
- canonical `LootPolicy`
- bounded coordination posture

Postures are:
- `advance`
- `hold`
- `support`
- `retreat`
- `focus_fire`

A posture is structured canonical intent for later orchestration. It does not bypass or rewrite deterministic combat resolution.

## Coordinated movement
A party may execute one coordinated movement step when:
- at least two active current-Stratum members participate
- all participating party members are colocated
- the destination is adjacent to the shared origin

Each member moves through the accepted canonical movement/survival service. 30C.4 records a group movement Ledger event and deterministic coordination record after the canonical moves succeed.

The group system never teleports crawlers or writes presentation-only position truth.

## Alliances
Two distinct active parties may form a persistent cooperative alliance.

Alliance truth records:
- deterministic alliance id
- exactly two canonical party ids
- active/dissolved status
- formation tick/event
- dissolution tick/event
- bounded dissolution reason

30C.4 allows only non-hostile alliance dissolution:
- `strategic_separation`
- `party_disbanded`
- `crawl_transition`

Betrayal, hostile alliance-breaking, revenge, rivalry escalation, and social conflict remain 30C.5.

## Authority boundary
The following remain absolute:
- simulation owns party membership
- simulation owns leadership
- simulation owns alliances
- simulation owns objectives/policies/postures
- simulation owns movement
- Unreal/presentation cannot mutate group truth
- social proposal providers cannot directly mutate group truth
- 30C.4 cannot create betrayal or rivalry consequences
- dialogue remains Phase 31

## Persistence and determinism
Party/alliance state must survive:
- Crawl persistence
- runtime checkpoint save/load
- canonical serialization
- independent deterministic reproduction

All mutation paths require canonical Ledger provenance.

## Acceptance proof
The deterministic proof must demonstrate:
- two parties formed from accepted 30C.3 recruitment
- one party expanded by a second accepted offer
- deterministic leadership transition
- shared objective, loot policy, and posture mutation
- coordinated group movement
- alliance formation and non-hostile dissolution
- voluntary leave/disband lifecycle
- zero betrayal semantics
- checkpoint equality
- independent reproduction equality
- full repository regressions

## Phase boundary
If 30C.4 passes, the next canonical slice is:

**30C.5 — Rivalry, Betrayal & Social Conflict**

30C.5 will add grudges, rivalry escalation, refusing aid, abandonment, alliance breaking, loot disputes, betrayal, and revenge-seeking from accumulated canonical state and incentives rather than arbitrary random betrayal.