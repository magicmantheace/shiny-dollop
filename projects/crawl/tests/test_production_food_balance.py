from __future__ import annotations

import math

from livingworld.continent_generation import generate_continent_world
from livingworld.production import _run_site, validate_production
from livingworld.production_food_balance import (
    FOODWORKS_THROUGHPUT_PER_CAPITA,
    FOODWORKS_WORKERS_PER_CAPITA,
    GRAIN_NUTRITION,
    HOUSEHOLD_NUTRITION_PER_CAPITA_DAY,
    manage_kingdom_food_and_grain_reserves,
)
from livingworld.world_engine import FinalWorldEngine


def _engine(seed: str) -> FinalWorldEngine:
    return FinalWorldEngine(generate_continent_world(seed, "Eldara"))


def _settlement(engine: FinalWorldEngine):
    return engine.world.settlements[sorted(engine.world.settlements)[0]]


def _site(settlement, kind: str):
    return next(site for site in settlement.production_sites.values() if site.kind == kind)


def _local_nutrition(settlement) -> float:
    return (
        settlement.resources["food"].quantity
        + settlement.resources["meat"].quantity * 0.95
        + settlement.resources["flour"].quantity * 0.82
        + settlement.resources["grain"].quantity * GRAIN_NUTRITION
    )


def test_food_processors_rescale_with_current_population() -> None:
    engine = _engine("production-food-rescale")
    settlement = _settlement(engine)
    settlement.population += 137

    engine.advance_hours(0, ignore_pause=True)

    foodworks = _site(settlement, "foodworks")
    assert foodworks.worker_capacity == max(1, math.ceil(settlement.population * FOODWORKS_WORKERS_PER_CAPITA))
    assert math.isclose(
        foodworks.base_throughput,
        settlement.population * FOODWORKS_THROUGHPUT_PER_CAPITA,
        rel_tol=0.0,
        abs_tol=1e-10,
    )
    assert sum(settlement.labor_allocation.values()) == settlement.population


def test_healthy_foodworks_have_headroom_over_baseline_household_demand() -> None:
    engine = _engine("production-food-headroom")
    settlement = _settlement(engine)
    foodworks = _site(settlement, "foodworks")

    settlement.health = 1.0
    settlement.crime = 0.0
    settlement.infrastructure["roads"] = 1.0
    settlement.resources["tools"].quantity = settlement.resources["tools"].capacity
    settlement.resources["flour"].quantity = settlement.resources["flour"].capacity
    settlement.resources["food"].quantity = 0.0
    foodworks.assigned_workers = foodworks.worker_capacity

    produced = _run_site(engine, settlement, foodworks)

    assert produced > settlement.population * HOUSEHOLD_NUTRITION_PER_CAPITA_DAY
    assert settlement.resources["flour"].quantity < settlement.resources["flour"].capacity
    assert settlement.resources["food"].quantity > 0.0


def test_grain_reserve_stocking_moves_material_without_creating_it() -> None:
    engine = _engine("production-grain-reserve-stocking")
    kingdom = engine.world.kingdoms[sorted(engine.world.kingdoms)[0]]
    settlements = [engine.world.settlements[sid] for sid in kingdom.settlement_ids]
    reserve = kingdom.resource_reserves["grain"]
    reserve.quantity = 0.0
    kingdom.laws.grain_reserve = 1.0

    for settlement in settlements:
        settlement.food_security = 0.80
        settlement.resources["grain"].quantity = settlement.resources["grain"].capacity * 0.90
        kingdom.policy_compliance[settlement.id] = 1.0

    before = reserve.quantity + sum(settlement.resources["grain"].quantity for settlement in settlements)
    manage_kingdom_food_and_grain_reserves(engine, kingdom)
    after = reserve.quantity + sum(settlement.resources["grain"].quantity for settlement in settlements)

    assert reserve.quantity > 0.0
    assert math.isclose(before, after, rel_tol=0.0, abs_tol=1e-8)
    assert validate_production(engine.world) == []


def test_grain_relief_moves_reserve_material_into_starving_settlement() -> None:
    engine = _engine("production-grain-reserve-relief")
    kingdom = engine.world.kingdoms[sorted(engine.world.kingdoms)[0]]
    settlements = [engine.world.settlements[sid] for sid in kingdom.settlement_ids]
    target = settlements[0]
    grain_reserve = kingdom.resource_reserves["grain"]
    food_reserve = kingdom.resource_reserves["food"]

    kingdom.laws.grain_reserve = 1.0
    grain_reserve.quantity = min(250.0, grain_reserve.capacity)
    food_reserve.quantity = 0.0
    for settlement in settlements:
        settlement.food_security = 0.80
        settlement.resources["grain"].quantity = 0.0
        settlement.resources["food"].quantity = 0.0
    target.food_security = 0.10
    kingdom.policy_compliance[target.id] = 1.0

    before = grain_reserve.quantity + sum(settlement.resources["grain"].quantity for settlement in settlements)
    manage_kingdom_food_and_grain_reserves(engine, kingdom)
    after = grain_reserve.quantity + sum(settlement.resources["grain"].quantity for settlement in settlements)

    assert target.resources["grain"].quantity > 0.0
    assert grain_reserve.quantity < min(250.0, grain_reserve.capacity)
    assert math.isclose(before, after, rel_tol=0.0, abs_tol=1e-8)
    # A sufficiently severe settlement may legitimately consume the entire small
    # reserve during relief. Strategic readiness is therefore allowed to reach zero;
    # this regression is about transfer and conservation, not retained stock.
    assert 0.0 <= kingdom.food_reserve <= 1.0
    assert validate_production(engine.world) == []


def test_severe_relief_builds_weeks_of_local_nutrition_when_reserves_exist() -> None:
    engine = _engine("production-severity-relief")
    kingdom = engine.world.kingdoms[sorted(engine.world.kingdoms)[0]]
    settlements = [engine.world.settlements[sid] for sid in kingdom.settlement_ids]
    target = settlements[0]
    grain_reserve = kingdom.resource_reserves["grain"]
    food_reserve = kingdom.resource_reserves["food"]

    kingdom.laws.grain_reserve = 1.0
    grain_reserve.quantity = grain_reserve.capacity
    food_reserve.quantity = food_reserve.capacity
    for settlement in settlements:
        settlement.food_security = 0.80
        settlement.resources["grain"].quantity = 0.0
        settlement.resources["flour"].quantity = 0.0
        settlement.resources["food"].quantity = 0.0
        settlement.resources["meat"].quantity = 0.0
        kingdom.policy_compliance[settlement.id] = 1.0
    target.food_security = 0.10

    before = (
        grain_reserve.quantity * GRAIN_NUTRITION
        + food_reserve.quantity
        + sum(_local_nutrition(settlement) for settlement in settlements)
    )
    manage_kingdom_food_and_grain_reserves(engine, kingdom)
    after = (
        grain_reserve.quantity * GRAIN_NUTRITION
        + food_reserve.quantity
        + sum(_local_nutrition(settlement) for settlement in settlements)
    )

    daily_demand = target.population * HOUSEHOLD_NUTRITION_PER_CAPITA_DAY
    assert _local_nutrition(target) >= daily_demand * 20.0
    assert math.isclose(before, after, rel_tol=0.0, abs_tol=1e-8)
    assert validate_production(engine.world) == []


def test_food_insecure_settlements_are_not_used_as_reserve_donors() -> None:
    engine = _engine("production-protected-donors")
    kingdom = engine.world.kingdoms[sorted(engine.world.kingdoms)[0]]
    settlements = [engine.world.settlements[sid] for sid in kingdom.settlement_ids]
    grain_reserve = kingdom.resource_reserves["grain"]
    food_reserve = kingdom.resource_reserves["food"]

    grain_reserve.quantity = 0.0
    food_reserve.quantity = 0.0
    kingdom.laws.grain_reserve = 1.0
    for settlement in settlements:
        settlement.food_security = 0.60
        settlement.resources["grain"].quantity = settlement.resources["grain"].capacity * 0.90
        settlement.resources["food"].quantity = settlement.resources["food"].capacity * 0.90
        kingdom.policy_compliance[settlement.id] = 1.0

    manage_kingdom_food_and_grain_reserves(engine, kingdom)

    assert grain_reserve.quantity == 0.0
    assert food_reserve.quantity == 0.0
    assert validate_production(engine.world) == []
