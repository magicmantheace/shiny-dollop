from __future__ import annotations

import math

from . import production as production_model
from .advanced_simulation import LivingWorldEngine
from .domain import Kingdom, LaborCategory, Settlement, SettlementType


# The first 100-year Slice 3 calibration showed that raw materials remained healthy
# while flour, prepared food, meat, and kingdom food reserves collapsed. The second
# run restored global food supply but showed that small, fixed monthly relief packets
# could leave the same settlements in repeated famine while central reserves stayed
# well supplied. Keep this correction narrow: scale food processors with current
# population, warehouse real grain, and size relief by local reserve-days need.
MILL_THROUGHPUT_PER_CAPITA = 0.016
FOODWORKS_THROUGHPUT_PER_CAPITA = 0.015
BUTCHER_THROUGHPUT_PER_CAPITA = 0.004
MILL_WORKERS_PER_CAPITA = 0.018
FOODWORKS_WORKERS_PER_CAPITA = 0.022
BUTCHER_WORKERS_PER_CAPITA = 0.014
GRAIN_RESERVE_CAPACITY_PER_CAPITA = 0.90
GRAIN_NUTRITION = 0.72
HOUSEHOLD_NUTRITION_PER_CAPITA_DAY = 0.010
RELIEF_TRIGGER_FOOD_SECURITY = 0.55
RELIEF_MIN_TARGET_DAYS = 10.0
RELIEF_MAX_TARGET_DAYS = 30.0
DONOR_MIN_FOOD_SECURITY = 0.65

_INSTALLED = False


def _active_settlements(engine: LivingWorldEngine, kingdom: Kingdom) -> list[Settlement]:
    return [
        engine.world.settlements[settlement_id]
        for settlement_id in kingdom.settlement_ids
        if settlement_id in engine.world.settlements
        and engine.world.settlements[settlement_id].population > 0
        and engine.world.settlements[settlement_id].type != SettlementType.RUIN
    ]


def _retune_food_sites(engine: LivingWorldEngine, settlement: Settlement) -> bool:
    if not settlement.production_initialized or settlement.population <= 0:
        return False

    population = max(1, settlement.population)
    targets = {
        "mills": (MILL_WORKERS_PER_CAPITA, MILL_THROUGHPUT_PER_CAPITA),
        "foodworks": (FOODWORKS_WORKERS_PER_CAPITA, FOODWORKS_THROUGHPUT_PER_CAPITA),
        "butchers": (BUTCHER_WORKERS_PER_CAPITA, BUTCHER_THROUGHPUT_PER_CAPITA),
    }
    changed = False
    for kind, (workers_per_capita, throughput_per_capita) in targets.items():
        site = settlement.production_sites.get(f"production:{settlement.id}:{kind}")
        if site is None:
            continue
        worker_capacity = max(1, math.ceil(population * workers_per_capita))
        base_throughput = max(0.01, population * throughput_per_capita)
        if site.worker_capacity != worker_capacity or abs(site.base_throughput - base_throughput) > 1e-12:
            site.worker_capacity = worker_capacity
            site.base_throughput = base_throughput
            changed = True
    if changed:
        production_model.allocate_labor(engine, settlement)
    return changed


def initialize_kingdom_reserves_with_grain(
    engine: LivingWorldEngine,
    kingdom: Kingdom,
    *,
    original_initializer,
) -> None:
    original_initializer(engine, kingdom)
    population = max(1, production_model._kingdom_population(engine, kingdom))
    production_model._reserve_stock(
        kingdom,
        "grain",
        capacity=max(120.0, population * GRAIN_RESERVE_CAPACITY_PER_CAPITA),
    )


def _local_nutrition(settlement: Settlement) -> float:
    values = {
        "food": 1.0,
        "meat": 0.95,
        "flour": 0.82,
        "grain": GRAIN_NUTRITION,
    }
    return sum(
        settlement.resources[resource].quantity * value
        for resource, value in values.items()
        if resource in settlement.resources
    )


def _relief_target_days(food_security: float) -> float:
    # A settlement just under the trigger receives about ten days of local buffer;
    # one near complete food failure is pushed toward roughly a month. This is a
    # stock target, not a monthly gift, so already-supplied settlements are not
    # repeatedly overfilled.
    severity = production_model._clamp(
        (RELIEF_TRIGGER_FOOD_SECURITY - food_security) / RELIEF_TRIGGER_FOOD_SECURITY
    )
    return RELIEF_MIN_TARGET_DAYS + (
        RELIEF_MAX_TARGET_DAYS - RELIEF_MIN_TARGET_DAYS
    ) * severity


def manage_kingdom_food_and_grain_reserves(engine: LivingWorldEngine, kingdom: Kingdom) -> None:
    # The installer replaces production.initialize_kingdom_reserves with a wrapper
    # that preserves the legacy prepared-food bootstrap and adds the grain reserve.
    production_model.initialize_kingdom_reserves(engine, kingdom)
    settlements = _active_settlements(engine, kingdom)
    if not settlements:
        return

    population = max(1, sum(settlement.population for settlement in settlements))
    policy = production_model._clamp(kingdom.laws.grain_reserve)
    grain_reserve = kingdom.resource_reserves["grain"]
    food_reserve = kingdom.resource_reserves["food"]

    # A grain-reserve law now has a literal material target. Only settlements that
    # are already comfortably food-secure may donate to the central stockpile.
    grain_target = grain_reserve.capacity * (0.25 + policy * 0.45)
    grain_needed = max(0.0, grain_target - grain_reserve.quantity)
    if grain_needed > 0:
        for settlement in sorted(settlements, key=lambda item: item.id):
            if settlement.food_security < DONOR_MIN_FOOD_SECURITY:
                continue
            stock = settlement.resources.get("grain")
            if stock is None:
                continue
            local_floor = max(settlement.population * 0.30, stock.capacity * 0.20)
            surplus = max(0.0, stock.quantity - local_floor)
            compliance = production_model._clamp(kingdom.policy_compliance.get(settlement.id, 0.5))
            take = min(grain_needed, surplus * policy * compliance * 0.08)
            if take <= 0:
                continue
            stock.quantity -= take
            grain_reserve.quantity += take
            grain_needed -= take
            if grain_needed <= 0:
                break

    # Prepared food remains a small ready-to-eat buffer. As with grain, only healthy
    # donor settlements can contribute so centralization never deepens an existing
    # local food-security problem.
    prepared_target = food_reserve.capacity * (0.05 + policy * 0.10)
    prepared_needed = max(0.0, prepared_target - food_reserve.quantity)
    if prepared_needed > 0:
        for settlement in sorted(settlements, key=lambda item: item.id):
            if settlement.food_security < DONOR_MIN_FOOD_SECURITY:
                continue
            stock = settlement.resources.get("food")
            if stock is None:
                continue
            local_floor = stock.capacity * 0.30
            surplus = max(0.0, stock.quantity - local_floor)
            compliance = production_model._clamp(kingdom.policy_compliance.get(settlement.id, 0.5))
            take = min(prepared_needed, surplus * policy * compliance * 0.04)
            if take <= 0:
                continue
            stock.quantity -= take
            food_reserve.quantity += take
            prepared_needed -= take
            if prepared_needed <= 0:
                break

    # Relief is a physical transfer. Prioritize the most food-insecure settlements,
    # then top their *local nutrition stock* toward a severity-aware reserve-days
    # target. Policy and compliance still matter, but emergency administration has a
    # baseline ability to deliver aid so a weak policy cannot strand stocked food in
    # the capital while subjects repeatedly starve.
    relief_candidates = sorted(
        (
            settlement
            for settlement in settlements
            if settlement.food_security < RELIEF_TRIGGER_FOOD_SECURITY
        ),
        key=lambda item: (item.food_security, item.id),
    )
    for settlement in relief_candidates:
        compliance = production_model._clamp(kingdom.policy_compliance.get(settlement.id, 0.5))
        target_days = _relief_target_days(settlement.food_security)
        daily_demand = max(
            0.01,
            settlement.population * HOUSEHOLD_NUTRITION_PER_CAPITA_DAY,
        )
        delivery_factor = (0.70 + policy * 0.30) * (0.75 + compliance * 0.25)
        target_nutrition = daily_demand * target_days * delivery_factor
        desired_nutrition = max(0.0, target_nutrition - _local_nutrition(settlement))
        if desired_nutrition <= 0:
            continue

        food_stock = settlement.resources.get("food")
        if food_stock is not None and food_reserve.quantity > 0:
            moved_food = min(
                desired_nutrition,
                food_reserve.quantity,
                max(0.0, food_stock.capacity - food_stock.quantity),
            )
            if moved_food > 0:
                food_reserve.quantity -= moved_food
                food_stock.quantity += moved_food
                desired_nutrition -= moved_food

        grain_stock = settlement.resources.get("grain")
        if desired_nutrition > 0 and grain_stock is not None and grain_reserve.quantity > 0:
            grain_needed_for_relief = desired_nutrition / GRAIN_NUTRITION
            moved_grain = min(
                grain_needed_for_relief,
                grain_reserve.quantity,
                max(0.0, grain_stock.capacity - grain_stock.quantity),
            )
            if moved_grain > 0:
                grain_reserve.quantity -= moved_grain
                grain_stock.quantity += moved_grain

    # Preserve the old abstract food_reserve signal as a normalized strategic-food
    # readiness measure. The denominator intentionally matches the old per-capita
    # prepared-food capacity so adding a grain store does not artificially halve the
    # inherited reserve ratio during migration.
    nutrition_available = food_reserve.quantity + grain_reserve.quantity * GRAIN_NUTRITION
    strategic_target = max(1.0, population * 0.45)
    kingdom.food_reserve = production_model._clamp(nutrition_available / strategic_target)


def install_production_food_balance() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    original_initializer = production_model.initialize_kingdom_reserves
    original_ensure = production_model.ensure_production_society

    def initialize_with_grain(engine: LivingWorldEngine, kingdom: Kingdom) -> None:
        initialize_kingdom_reserves_with_grain(
            engine,
            kingdom,
            original_initializer=original_initializer,
        )

    def ensure_with_food_balance(engine: LivingWorldEngine) -> None:
        original_ensure(engine)
        for settlement in engine.world.settlements.values():
            _retune_food_sites(engine, settlement)
        production_model.refresh_production_metrics(engine)

    production_model.initialize_kingdom_reserves = initialize_with_grain
    production_model._manage_kingdom_food_reserve = manage_kingdom_food_and_grain_reserves
    production_model.ensure_production_society = ensure_with_food_balance
    _INSTALLED = True
