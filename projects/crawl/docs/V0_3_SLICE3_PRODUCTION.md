# LivingWorld v0.3 Slice 3 — Production, Inventories, and Labor

## Status

Implementation branch: `agent/world-v0.3-slice3-production`

Slice 3 replaces the legacy economy's independent per-resource daily growth with an explicit material-flow model.

The governing rule is:

> **A material must come from a documented source process, move from an existing inventory, or already exist as bootstrap state.**

The slice deliberately does **not** build the full market, price, trade-logistics, or monetary circulation system. Those belong to Slice 4.

---

## 1. Persistent production state

Each settlement now persists:

- explicit `production_sites`,
- statistical `labor_allocation`,
- `production_initialized`,
- daily production telemetry,
- daily consumption telemetry,
- material/labor shortage telemetry.

Each production site persists:

- settlement ownership,
- site kind,
- labor category,
- worker capacity,
- assigned workers,
- material inputs,
- material outputs,
- base throughput,
- efficiency,
- active state.

Production-site IDs are deterministic embedded IDs rather than world entity-sequence allocations. Initializing production therefore does not consume historical/world entity IDs.

---

## 2. Labor categories

Statistical population is allocated among:

- agriculture,
- extraction,
- crafts,
- trade,
- administration,
- religion,
- military,
- services,
- dependent/unemployed population.

The labor ledger always sums back to settlement population.

The working population is intentionally smaller than total population. Government conscription and administrative reach alter the non-production share of the workforce.

Production labor is then distributed across actual active site capacity.

If a settlement has more production capacity than available workers, sites receive fewer workers and throughput falls. Labor shortage is therefore a real material constraint rather than a descriptive label.

---

## 3. Explicit production chains

The initial material graph includes:

```text
Grain
  -> Flour
  -> Food

Livestock
  -> Meat
  -> Leather

Forest / logging capacity
  -> Logs
  -> Lumber

Iron Ore
  -> Iron
  -> Tools
  -> Weapons

Stone
  -> Masonry
  -> Fortification Materials

Fiber
  -> Cloth
  -> Clothing

Mana Crystal
  -> Refined Mana
  -> Magical Goods
```

Raw extraction sites are the documented source processes for new material.

Processed goods cannot be produced when their required inputs are unavailable.

---

## 4. Migration from the v0.2/v0.3 legacy stocks

Pre-Slice-3 generated worlds used `timber` and `iron` as directly produced raw stocks.

Slice 3 migrates those semantics once when production is initialized:

- legacy `timber` inventory becomes `logs`,
- legacy raw `iron` inventory becomes `iron_ore`,
- processed `iron` becomes a separate inventory produced by smelters,
- old direct `production_per_day` and `consumption_per_day` rates are disabled.

Existing trade-route commodity names are migrated from:

- `timber` -> `logs`,
- legacy `iron` -> `iron_ore`.

This avoids leaving a second hidden material source active after the new production model starts.

---

## 5. Production factors

Daily site throughput depends on:

- assigned labor versus worker capacity,
- settlement health,
- road/infrastructure quality,
- local crime/security,
- siege/occupation state,
- tool availability,
- site efficiency,
- season for agricultural sites,
- available inputs,
- available output storage capacity.

A bottleneck in any required input limits the whole production run.

No production operation is allowed to drive an inventory below zero or above capacity.

---

## 6. Household consumption and sinks

The slice adds explicit material sinks.

Households consume food through a fallback hierarchy:

```text
prepared food
-> meat
-> flour
-> grain
```

Food security now trends toward actual daily fulfillment plus remaining reserve depth.

Other sinks include:

- tool wear from productive labor,
- clothing wear,
- food/meat/flour/grain spoilage,
- existing trade movement,
- future construction/military sinks in later slices.

Spoilage removes inventory explicitly and appears in daily consumption telemetry.

---

## 7. Kingdom strategic reserves

Kingdoms now persist explicit strategic `resource_reserves`.

Initial reserve categories include:

- food,
- tools,
- weapons,
- masonry.

The old abstract `kingdom.food_reserve` value is converted once into physical starting food reserve inventory. This preserves existing world state rather than adding a second hidden reserve.

The grain-reserve policy can then:

- draw limited real surplus food from compliant settlements into the kingdom reserve,
- release real reserve food to a settlement suffering severe food insecurity.

Reserve transfers conserve total material. Relief does not create food.

Tools, weapons, and masonry reserves are explicit schema hooks for later procurement, construction, and warfare integration. Slice 3 does not invent automatic state procurement ahead of Slice 4.

---

## 8. Prices and money are intentionally not rebuilt here

The old lightweight scarcity-derived `ResourceStock.price` signal remains temporarily for backward compatibility with the existing trade routine.

It is **not** the final market model.

Slice 3 does not add:

- bids/offers,
- market clearing,
- monetary wages,
- business profits,
- new settlement wealth creation,
- transport-price calculation,
- tariff-aware market routing,
- state purchasing,
- monetary circulation.

Those are Slice 4 responsibilities.

This means the long-horizon decline in the pre-Slice-4 taxable monetary base is not considered solved by Slice 3. Slice 3 fixes material causality first; Slice 4 must connect material production to money and trade.

---

## 9. Legacy seasonal harvest removal

The old engine added a separate seasonal grain pulse on top of daily resource production.

Slice 3 disables that pulse because agricultural sites already carry seasonal throughput modifiers.

Keeping both would create unexplained grain outside the material-flow ledger.

---

## 10. New-settlement synchronization

Production installs around the complete Slice 1/2 engine wrapper stack.

After a public simulation advance, any newly founded frontier/breakaway settlement that lacks Slice 3 state is initialized with:

- inventories,
- production sites,
- labor allocation.

Population changes also trigger labor reallocation when the persisted labor ledger no longer sums to the settlement population.

---

## 11. Observability

New world metrics include:

- `production_sites`,
- `average_labor_utilization`,
- `labor_shortage_settlements`,
- `material_shortage_settlements`,
- `production_throughput_last_day`,
- `total_food_inventory`,
- `total_tools_inventory`,
- `kingdom_food_reserves`.

Existing `/api/world/state` serialization exposes production sites, labor state, inventories, shortages, and kingdom reserves automatically.

---

## 12. Production validator

`validate_production()` checks:

- every active non-ruin settlement is initialized,
- labor allocation equals population,
- all inventory quantities are finite and nonnegative,
- no inventory exceeds capacity,
- production-site ownership is valid,
- assigned workers stay within site capacity,
- every recipe input/output references an actual settlement inventory,
- every kingdom has an explicit food reserve,
- reserve quantities remain finite, nonnegative, and within capacity.

This validator is intended to become part of the long-horizon Slice 3 calibration after local regression correctness is established.

---

## 13. Regression coverage

`tests/test_production.py` covers:

- production/labor/reserve initialization,
- legacy raw-stock migration,
- input starvation stopping a processing chain,
- iron ore -> iron -> tools material flow,
- labor shortage reducing throughput,
- material-conserving kingdom food relief,
- save/load round-trip persistence,
- post-advance new-settlement synchronization,
- bounded ten-day material flow.

`tests/test_api_production.py` covers API visibility and production metrics.

---

## 14. Slice 3 acceptance gate

Before merge, local validation should prove:

1. all existing v0.2, Slice 1, and Slice 2 regressions remain green;
2. production state survives save/load;
3. every active settlement has explicit labor and production capacity;
4. labor shortages measurably reduce output;
5. missing recipe inputs prevent output rather than creating material;
6. no inventory becomes negative or exceeds capacity;
7. the minimum roadmap production chains are represented;
8. food consumption and spoilage are explicit sinks;
9. kingdom food-reserve transfers conserve material;
10. new settlements receive Slice 3 state after creation;
11. API state exposes production/labor/reserve state;
12. a dedicated long-horizon material calibration passes before final merge;
13. no GitHub Actions minutes are required.

---

## 15. Explicitly deferred to Slice 4 and later

Slice 3 does not finish:

- real markets and price discovery,
- actual-goods trade optimization,
- transport costs,
- tariffs in market routing,
- state procurement,
- monetary wages/businesses,
- circular settlement wealth generation,
- army equipment consumption,
- construction material consumption by infrastructure projects,
- household/property-level consumption,
- disaster/harvest shock system,
- strategic settlement specialization.

Those systems should consume the explicit production/inventory/labor foundation created here instead of creating parallel material models.
