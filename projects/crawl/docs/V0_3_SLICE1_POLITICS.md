# LivingWorld v0.3 — Slice 1: Political Society

## Purpose

v0.2 proved that kingdoms can persist, fight, migrate, expand, fracture, and survive long histories. Slice 1 begins the v0.3 world-depth roadmap by replacing the idea of a kingdom as a mostly unified strategic actor with an internal political society.

This slice establishes the causal chain:

```text
Material/social conditions
-> faction satisfaction and grievances
-> faction loyalty and influence
-> legitimacy and kingdom priorities
-> leadership competition
-> political crisis
-> rebellion / secession when pressure becomes severe
```

The intent is not to make politics maximally complex yet. It is to create durable typed political state that later slices—law, economy, religion, the Hollow, Dungeon Lords, organizations, and player actions—can influence.

---

## 1. Government Forms

The simulation supports these government types:

- monarchy,
- elective monarchy,
- council government,
- clan confederacy,
- theocracy,
- merchant oligarchy,
- military regime.

Government type now affects:

- faction composition,
- political office structure,
- ruler title,
- succession preference,
- whether periodic leadership review occurs,
- how a living ruler can be replaced.

This is the beginning of government differentiation, not the final policy/institution system.

---

## 2. Political Offices

Kingdoms persist typed political offices.

Current roles include:

- ruler,
- heir,
- chancellor,
- treasurer,
- marshal,
- high priest,
- councilor,
- guild representative,
- governor and mayor schema hooks for later local-government work.

Office holders are persistent NPCs where candidates exist. Dead, missing, or politically displaced holders can be replaced. The ruler office is kept consistent with `kingdom.ruler_npc_id`.

Different governments expose different office structures. For example, a theocracy has a High Priest while a merchant oligarchy has a Guild Representative.

---

## 3. Political Factions

Every initialized kingdom currently receives four factions selected by government type from these faction families:

- landed nobility,
- merchant league,
- military bloc,
- priesthood,
- guild coalition,
- frontier lords,
- popular assembly.

Each faction persists:

- kingdom ownership,
- leader,
- member NPCs,
- ideology,
- economic interests,
- religious interests,
- influence,
- loyalty,
- grievances,
- preferred policies,
- regional base where relevant,
- future ally/rival hooks,
- creation date and active state.

Faction influence is normalized within a kingdom.

Membership is derived from NPC occupation, social status, values, traits, and wealth. This keeps factions connected to the named population rather than making them free-floating modifiers.

---

## 4. Faction Conditions and Grievances

Faction loyalty reacts to real kingdom conditions.

Current grievance sources include:

- food insecurity,
- local disorder,
- weak legitimacy,
- excessive taxation relative to faction preference,
- military neglect,
- restricted trade,
- religious leadership conflict,
- neglect of a faction's regional base.

War can affect satisfaction differently for military and civilian-oriented factions.

Future slices will extend this with explicit laws, tariffs, property rules, conscription, religious policy, economic class interests, and Hollow-related political pressure.

---

## 5. Legitimacy

Legitimacy is no longer only a mostly isolated kingdom number.

It now trends toward a value influenced by:

- faction support,
- food security,
- local stability,
- taxation burden,
- military readiness,
- vassal status,
- war exhaustion.

Low legitimacy therefore becomes the result of interacting world conditions rather than a purely random political failure trigger.

---

## 6. Factions Influence Kingdom Strategy

Faction ideology slowly pulls existing kingdom goals toward politically supported priorities.

Examples:

- a powerful military bloc raises security and expansion pressure,
- merchants prioritize wealth and peaceful access,
- commoners prioritize food and stability,
- frontier factions prioritize security and expansion.

The existing deterministic kingdom decision system remains authoritative. Factions alter its inputs rather than bypassing it.

---

## 7. Government-Specific Leadership

Succession and leadership review now use government type.

### Monarchy

Adult children of the previous ruler receive strong hereditary preference.

### Elective monarchy

Faction support and elite status matter more; scheduled leadership review occurs.

### Council government

Political/faction support can replace a living ruler through council vote.

### Clan confederacy

Leadership emphasizes family standing and courage, with periodic clan-moot review.

### Theocracy

Clergy, shared state faith, and devotion matter heavily. A severe legitimacy crisis can remove a living ruler through a synod-style process.

### Merchant oligarchy

Wealth, commercial occupation, and faction support matter; periodic oligarchic review occurs.

### Military regime

Military occupation, courage, and faction support matter. A severe crisis can produce an officer coup.

Leadership changes create structured historical events.

---

## 8. Rulers Can Lose Office Without Dying

One explicit v0.3 acceptance requirement is now supported: a living ruler can lose power.

Non-hereditary governments periodically review leadership. Any government can also face crisis removal when legitimacy is extremely low and an influential hostile faction exists.

A displaced living ruler remains a persistent NPC with former-ruler status instead of being deleted.

---

## 9. Faction-Driven Rebellion

The old advanced-simulation rebellion hook used low kingdom stability plus a random probability.

Slice 1 replaces that as the authoritative advanced rebellion path.

A rebellion proposal now depends on:

- low legitimacy,
- low kingdom stability,
- faction influence,
- faction disloyalty,
- accumulated faction grievances,
- a viable non-capital regional base.

Randomness remains seeded and bounded, but it only resolves whether an already severe political crisis crosses into open rebellion. It is no longer the primary explanation for why the rebellion exists.

When secession occurs:

- the existing breakaway-kingdom system creates the new polity,
- moved residents change allegiance,
- parent faction memberships are immediately reconciled,
- a faction cannot keep members or a regional base that moved into the new kingdom,
- the new kingdom receives its own political institutions,
- structured rebellion/founding events preserve causality.

---

## 10. Persistence and API

Political society is part of `WorldState` and therefore uses the existing JSON persistence path.

No database schema migration is required because the authoritative world payload is stored as structured JSON.

Existing endpoints already expose the new state:

- `/api/world/state` includes all political factions,
- `/api/kingdoms` includes offices and faction IDs,
- `/api/kingdoms/{id}` includes the same political fields plus ruler details,
- `/api/world` metrics expose political-faction count, average legitimacy, average faction loyalty, and low-legitimacy kingdom count.

Dedicated political observatory endpoints can be added later with the dashboard work.

---

## 11. Determinism and LLM Boundary

Political initialization and decisions use deterministic seeded logic.

LLMs do not choose:

- faction membership,
- faction loyalty,
- legitimacy,
- succession,
- elections,
- coups,
- rebellion,
- kingdom strategic priorities.

An LLM may later describe political events in prose, but structured simulation state remains authoritative.

---

## 12. Bootstrap History Rule

Generated political institutions are deterministic starting state.

Constructing `FinalWorldEngine` for a fresh world must not consume historical event IDs or leave NPC memories pointing at hidden bootstrap events. The first runtime-generated historical event remains `WORLD_GENERATED`.

Political changes after world creation are historical and should emit normal events.

---

## 13. Slice 1 Tests

Focused tests cover:

- political bootstrap does not create fake history,
- four factions initialize per kingdom,
- faction influence normalization,
- ruler office consistency,
- different government office structures,
- faction pressure changing kingdom goals,
- material crises generating grievances and legitimacy loss,
- hereditary monarchical succession,
- scheduled removal of a living council ruler,
- severe faction crises identifying breakaway territory,
- political state surviving model serialization,
- political state being visible through the API.

The full legacy regression suite must also continue to pass.

---

## 14. Acceptance Criteria

Slice 1 is ready to merge only when local validation proves:

- existing v0.2 tests still pass,
- politics tests pass,
- API/dashboard build remains healthy,
- political references survive persistence,
- a ruler can be removed without dying,
- government forms demonstrate different leadership/office behavior,
- factions measurably influence kingdom strategy,
- severe conditions can create causal rebellion pressure,
- political metrics remain bounded,
- no GitHub Actions are required.

After unit/regression validation, run a dedicated long-horizon politics calibration before final merge. The purpose of that run is not to demand a specific number of rebellions, but to ensure politics creates meaningful variation without collapsing every kingdom into nonstop coups or fragmentation.

---

## 15. Explicitly Deferred to Later v0.3 Slices

Slice 1 does **not** yet attempt to finish:

- explicit law objects,
- policy voting,
- institutional administrative capacity,
- formal faction alliances/rivalries,
- dynastic claim objects,
- multi-settlement civil-war fronts,
- negotiated autonomy,
- taxation classes,
- property politics,
- organization-level cult infiltration,
- Hollow corruption of factions,
- detailed local government,
- political map replay.

The models and causal path introduced here are intended to support those systems rather than pre-implement them superficially.
