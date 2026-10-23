# LivingWorld v0.3 — Slice 1C: Political Collapse Resolution

## Purpose

Slice 1A created governments, offices, factions, leadership changes, legitimacy, and faction-driven rebellion pressure.

Slice 1B replaced runaway faction loyalty with an equilibrium model so real political opposition could form.

The 200-year calibration then exposed the remaining gap: kingdoms could sit near zero legitimacy for many years with deeply unhappy factions and still never resolve the crisis.

Slice 1C closes that causal chain.

```text
bad conditions / political failure
        ↓
faction grievances
        ↓
faction disloyalty
        ↓
legitimacy collapse
        ↓
sustained political crisis
        ↓
organized opposition
        ↓
regime overthrow / regional secession / civil war
```

## Persistent crisis state

Each kingdom now persists:

- `political_crisis_months`
- `last_political_resolution_year`
- `last_political_resolution`

Old saved worlds remain compatible because these fields have defaults.

A political crisis begins accumulating when legitimacy is below `0.30` and the strongest opposition faction is either sufficiently disloyal or carrying multiple grievances.

The crisis must persist for at least 12 months before extraordinary collapse resolution becomes eligible.

If conditions improve, crisis duration decays instead of disappearing instantly.

## Collapse pressure

Collapse pressure deliberately gives legitimacy the largest weight:

- 50% legitimacy failure
- 20% kingdom instability
- 20% opposition-faction disloyalty
- up to 10% concrete faction grievances

This prevents the previous failure mode where a kingdom at roughly `0.02` legitimacy could remain politically inert simply because aggregate settlement stability was still reasonable.

## Resolution types

### Regime overthrow

A collapse can replace the government without splitting the kingdom.

This is favored when:

- the kingdom has only one settlement;
- there is no meaningful non-capital regional base; or
- the leading opposition is fundamentally national, such as a military, priesthood, nobility, or broad popular faction.

The opposition supplies a replacement ruler. The victorious faction can also reshape the government form:

- military → military regime
- priesthood → theocracy
- merchants → merchant oligarchy
- guilds/commoners → council
- frontier bloc → clan confederacy
- nobility → elective monarchy

Events:

- `REGIME_OVERTHROWN`
- `GOVERNMENT_REFORMED` when the government form actually changes
- existing `LEADERSHIP_CHANGED`

### Regional secession

A faction with a real regional power base can split a non-capital settlement away from the parent kingdom.

The existing breakaway-kingdom machinery is reused so the new state receives:

- sovereign settlement ownership
- resident allegiance transfer
- a ruler
- an army
- diplomacy
- its own political factions and offices

Events:

- `REGIONAL_SECESSION`
- `FACTION_REBELLION`
- existing `REBELLION`
- existing `KINGDOM_FOUNDED`

### Civil war

A severe or prolonged regional collapse can begin as an independence civil war instead of a clean secession.

Civil war requires a regional breakaway and is avoided when the parent is already in another active war, because the current warfare layer is not yet designed for reliable multi-war army allocation.

The breakaway state is created and immediately enters a `war of independence` against its former parent.

Events:

- `CIVIL_WAR_STARTED`
- `FACTION_REBELLION`
- `WAR_DECLARED`
- `REBELLION`
- `KINGDOM_FOUNDED`

## Timing and inevitability

Collapse does not fire immediately when it becomes eligible.

The monthly trigger chance grows with:

- collapse pressure;
- months spent in sustained crisis.

However, a failed state cannot remain unresolved forever.

Resolution becomes deterministic when either:

- the crisis has persisted for at least 36 months; or
- legitimacy reaches `0.04` or lower.

A four-year post-resolution cooldown prevents repeated collapse events from chaining immediately after a successful overthrow or breakaway.

## Crisis history events

When crisis duration first reaches one year:

- `POLITICAL_CRISIS`

When a sustained crisis later fully decays:

- `POLITICAL_CRISIS_EASED`

This lets history distinguish a government that flirted with collapse and recovered from one that actually fell.

## Calibration instrumentation

The political calibration now records annually:

- number of kingdoms in sustained political crisis;
- maximum crisis duration;
- number of collapse-eligible kingdoms;
- number eligible for each outcome type;
- maximum collapse pressure.

The Markdown report therefore tells us not only whether a rebellion happened, but whether the political state was actually eligible for one.

## Validation expectations

Slice 1C should demonstrate all of the following before Slice 1 is considered complete:

1. Existing Slice 1/1B tests remain green.
2. Crisis duration persists through world serialization.
3. Healthy recovery can clear a political crisis.
4. A one-settlement failed state can resolve by regime overthrow.
5. A regional crisis can create a secession.
6. Severe regional collapse can create an independence civil war.
7. Forced resolution prevents near-zero-legitimacy states from surviving indefinitely.
8. Breakaway political references remain structurally valid.
9. A 200-year political calibration has zero base-world and political invariant failures.
10. Long-history politics avoids both permanent universal loyalty and continuous civil war.

## Deferred

Slice 1C does not yet attempt to model full multi-front civil wars with multiple rebel provinces, competing claimants, negotiated constitutional settlements, foreign intervention, or simultaneous loyalist/rebel army splitting.

Those are appropriate later expansions after the core collapse-resolution path proves stable over long horizons.
