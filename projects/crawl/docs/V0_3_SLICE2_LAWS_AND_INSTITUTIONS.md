# LivingWorld v0.3 Slice 2 — Laws, Policy, and Institutional Capacity

## Status

Implementation branch: `agent/world-v0.3-slice2-laws`

This slice implements roadmap section 6: political decisions become persistent laws, and institutional capacity determines how much of those laws is actually enforced across a kingdom.

The design rule is:

> **A decree is not the same thing as an outcome.**

A kingdom may adopt an aggressive tax, conscription, welfare, or security policy while lacking the bureaucracy, records, communications, enforcement, or local compliance required to carry it out.

---

## 1. Persistent law state

Each kingdom now owns a typed `LawPolicy` object containing:

- tax rate,
- conscription,
- religious tolerance,
- guild privileges,
- land rights,
- inheritance equality,
- trade tariff,
- anti-bandit spending,
- military spending,
- grain-reserve policy,
- magical regulation,
- policy revision number.

Border and refugee policy remain their existing explicit enum-backed kingdom fields.

Not every policy has a complete downstream subsystem yet. Land rights and inheritance equality are deliberately persisted before the later household/property/inheritance slice; magical regulation is persisted before the later magical/Hollow institution work. They are not given fake effects simply to make every field move a number today.

---

## 2. Institutional capacity

Each kingdom now owns a typed `InstitutionalCapacity` object containing:

- administrative reach,
- tax efficiency,
- corruption,
- record keeping,
- communication quality,
- local autonomy,
- enforcement capability.

Government forms start with meaningfully different institutional profiles. For example:

- merchant oligarchies begin with strong records, tax machinery, and communications;
- clan confederacies begin with high local autonomy and weaker centralized administration;
- military regimes begin with stronger enforcement but only moderate civil administration;
- councils begin with relatively good records and lower corruption but more local autonomy.

Institutional values evolve gradually rather than resetting from a government template every month.

---

## 3. Regional policy compliance

Each kingdom calculates policy compliance separately for every settlement.

Compliance depends on:

- administrative reach,
- record keeping,
- communications,
- enforcement,
- corruption,
- local autonomy,
- roads,
- local stability,
- distance from the capital.

The capital receives a small administrative advantage.

This means two settlements under the same law can experience different effective policy.

The kingdom exposes both:

- `policy_compliance[settlement_id]`, and
- `effective_policies`.

---

## 4. Tax collection is now institutional

The old tax collector applied the same nominal tax rate everywhere.

Slice 2 replaces that behavior for `LivingWorldEngine` and descendants.

Actual collection now depends on:

```text
nominal tax
× settlement compliance
× administrative/tax/record quality
× corruption losses
```

Weak institutions therefore leave more nominal tax uncollected.

This is intentionally different from raising the tax rate: a ruler can demand more without possessing the state capacity to receive more.

---

## 5. Policy spending and second-order consequences

The implemented policies with immediate world effects are:

### Anti-bandit spending

Requires budget, compliance, and enforcement capability.

Successful implementation:

- gradually reduces settlement crime,
- contributes to safer trade routes,
- can improve local stability indirectly.

### Military spending and conscription

Effective military spending depends on compliance and available budget.

Together with conscription and enforcement capacity they move:

- kingdom military readiness,
- army readiness.

A law declaring high military spending does not instantly create perfect readiness.

### Grain-reserve policy

When food security is poor, an implemented reserve policy can provide limited relief.

The effect depends on:

- administrative reach,
- settlement compliance,
- budget availability.

It also contributes to the kingdom-level food-reserve state.

### Trade tariffs

Actual tariff income depends on:

- recent trade volume,
- tariff policy,
- policy compliance,
- tax efficiency.

### Guild/security interaction

Guild privileges and anti-bandit enforcement contribute modestly to trade-route safety over time.

---

## 6. Policy conflict

Political factions now have distinct policy preference profiles.

Examples:

- military blocs prefer high conscription and military spending;
- merchants prefer low tariffs, low taxes, strong guild privileges, and secure trade;
- guild coalitions prefer broad economic rights and strong guild privileges;
- commoners prefer low taxes, broad land/inheritance rights, grain reserves, and anti-bandit protection;
- priesthoods prefer stricter religious and magical policy;
- frontier blocs prefer broad land rights, low taxation, security, and local freedom;
- nobility prefer narrower land/inheritance rights and stronger traditional military obligations.

Each month, the gap between actual law and faction preference creates a bounded loyalty effect.

Severe mismatch creates a concrete grievance:

```text
Policy conflict: <policy>
```

This grievance is visible to the existing political-collapse machinery, so policy can become one understandable cause of later instability without creating a separate rebellion system.

---

## 7. Annual policy review

Once per year, the government reviews policy using weighted political influence and material conditions.

Faction influence supplies the baseline target.

World conditions can then override or intensify the target:

- high crime pushes anti-bandit spending upward,
- food insecurity pushes grain reserves upward,
- active war pushes conscription and military spending upward,
- fiscal weakness can push taxation upward while constraining military spending.

Policy changes are rate-limited. Governments cannot flip every law from one extreme to another in one annual review.

A successful revision emits:

```text
LAW_CHANGED
```

with old/new values and the new revision number.

---

## 8. Institutional evolution

Institutional capacity evolves slowly each month.

Examples:

- good roads improve communication quality;
- communication and records support administrative reach;
- administration, records, enforcement, and low corruption improve tax efficiency;
- anti-bandit and military spending can support enforcement capacity;
- weak fiscal conditions can increase corruption pressure;
- high local autonomy limits centralized administrative reach.

This is mean-reverting institutional development, not unlimited linear growth.

---

## 9. Observability

Existing kingdom/world APIs expose the new typed state automatically through Pydantic serialization.

New world metrics include:

- `average_administrative_reach`,
- `average_tax_efficiency`,
- `average_institutional_corruption`,
- `average_policy_compliance`,
- `policy_conflict_factions`,
- `institutional_tax_revenue`,
- `institutional_policy_spending`.

---

## 10. Determinism and authority

All policy decisions and institutional effects remain deterministic and server-authoritative.

No LLM is required to:

- choose a law,
- calculate compliance,
- collect taxes,
- spend policy budgets,
- alter crime/readiness/food support,
- change faction loyalty,
- evolve institutional capacity.

The LLM layer may later explain or narrate these events, but it does not authorize them.

---

## 11. Regression coverage

`tests/test_institutions.py` covers:

- initialization and regional compliance,
- strong-state versus weak-state tax collection,
- security/military/grain second-order effects,
- faction policy conflict,
- annual material-pressure policy review,
- save/load round-trip persistence.

`tests/test_api_institutions.py` covers API visibility and institution metrics.

The existing full backend regression remains the final local gate.

---

## 12. Slice 2 acceptance criteria

Slice 2 is ready to merge only when local validation proves:

1. existing v0.2 and Slice 1 regressions still pass;
2. explicit law and institution state survives save/load;
3. regional compliance is bounded and non-cosmetic;
4. institutional strength materially changes tax collection;
5. security/military/grain policies create measurable second-order effects;
6. faction policy disagreement changes political loyalty/grievances;
7. annual policy review reacts to political and material pressure;
8. API serialization exposes laws, institutions, compliance, and metrics;
9. no GitHub Actions minutes are required.

A later balance/calibration pass may tune policy strengths after local correctness is established. This slice should not pre-empt the later production, household/property, crime, religion, or magic roadmap systems merely to give every law an immediate effect.
