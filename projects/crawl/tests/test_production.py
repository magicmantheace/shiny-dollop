from __future__ import annotations

import math

from livingworld.continent_generation import generate_continent_world
from livingworld.domain import ResourceStock, Settlement, WorldState
from livingworld.production import (
    _manage_kingdom_food_reserve,
    allocate_labor,
    run_production_day,
    validate_production,
)
from livingworld.world_engine import FinalWorldEngine


def _engine(seed: str) -> FinalWorldEngine:
    return FinalWorldEngine(generate_continent_world(seed, "Eldara"))


def _settlement(engine: FinalWorldEngine):
    return engine.world.settlements[sorted(engine.world.settlements)[0]]


def _site(settlement, kind: str):
    return next(site for site in settlement.production_sites.values() if site.kind == kind)


def test_production_society_initializes_sites_labor_and_reserves() -> None:
    engine = _engine("production-initialize")

    assert validate_production(engine.world) == []
    active = [settlement for settlement in engine.world.settlements.values() if settlement.population > 0]
    assert active
    assert all(settlement.production_initialized for settlement in active)
    assert all(len(settlement.production_sites) >= 18 for settlement in active)
    assert all(sum(settlement.labor_allocation.values()) == settlement.population for settlement in active)
    assert all("food" in kingdom.resource_reserves for kingdom in engine.world.kingdoms.values())
    assert engine.world.metrics["production_sites"] > 0
    assert 0.0 <= engine.world.metrics["average_labor_utilization"] <= 1.0


def test_legacy_raw_materials_are_migrated_into_explicit_chain_inputs() -> None:
    engine = _engine("production-legacy-migration")
    settlement = _settlement(engine)

    assert "logs" in settlement.resources
    assert "iron_ore" in settlement.resources
    assert settlement.resources["timber"].quantity == 0.0
    assert settlement.resources["iron"].production_per_day == 0.0
    assert all("timber" not in route.commodities for route in engine.world.trade_routes.values())


def test_missing_input_stops_processing_without_negative_inventory() -> None:
    engine = _engine("production-input-starvation")
    settlement = _settlement(engine)

    for site in settlement.production_sites.values():
        site.active = site.kind == "mills"
    mill = _site(settlement, "mills")
    mill.assigned_workers = mill.worker_capacity
    settlement.resources["grain"].quantity = 0.0
    settlement.resources["flour"].quantity = 0.0

    run_production_day(engine)

    assert settlement.resources["grain"].quantity == 0.0
    assert settlement.resources["flour"].quantity == 0.0
    assert settlement.production_shortages.get("grain", 0.0) > 0.0
    assert validate_production(engine.world) == []


def test_iron_chain_turns_ore_into_iron_and_tools() -> None:
    engine = _engine("production-iron-chain")
    settlement = _settlement(engine)

    for site in settlement.production_sites.values():
        site.active = site.kind in {"smelters", "toolsmiths"}
        if site.active:
            site.assigned_workers = site.worker_capacity
    settlement.resources["iron_ore"].quantity = min(100.0, settlement.resources["iron_ore"].capacity)
    settlement.resources["lumber"].quantity = min(100.0, settlement.resources["lumber"].capacity)
    settlement.resources["iron"].quantity = 0.0
    settlement.resources["tools"].quantity = 0.0

    before_ore = settlement.resources["iron_ore"].quantity
    run_production_day(engine)

    assert settlement.resources["iron_ore"].quantity < before_ore
    assert settlement.resources["iron"].quantity > 0.0
    assert settlement.resources["tools"].quantity > 0.0
    assert settlement.production_last_day.get("iron", 0.0) > 0.0
    assert settlement.production_last_day.get("tools", 0.0) > 0.0


def test_labor_shortage_reduces_throughput_and_is_reported() -> None:
    engine = _engine("production-labor-shortage")
    settlement = _settlement(engine)
    mill = _site(settlement, "mills")

    for site in settlement.production_sites.values():
        site.active = site.id == mill.id
    settlement.resources["grain"].quantity = settlement.resources["grain"].capacity
    settlement.resources["flour"].quantity = 0.0

    mill.worker_capacity = max(20, settlement.population)
    allocate_labor(engine, settlement)
    assert mill.assigned_workers < mill.worker_capacity

    run_production_day(engine)

    assert settlement.production_last_day.get("flour", 0.0) > 0.0
    assert settlement.production_shortages.get("labor:crafts", 0.0) > 0.0


def test_kingdom_food_relief_moves_existing_material_instead_of_creating_it() -> None:
    engine = _engine("production-material-relief")
    kingdom = engine.world.kingdoms[sorted(engine.world.kingdoms)[0]]
    settlements = [engine.world.settlements[sid] for sid in kingdom.settlement_ids]
    target = settlements[0]

    for settlement in settlements:
        settlement.resources["food"].quantity = 0.0
        settlement.food_security = 0.80
    # The severity-aware relief model measures all local nutrition before deciding
    # whether aid is needed. Clear alternate foods on the target so this regression
    # specifically exercises prepared-food reserve transfer and conservation.
    target.resources["grain"].quantity = 0.0
    target.resources["flour"].quantity = 0.0
    target.resources["meat"].quantity = 0.0
    target.food_security = 0.10
    reserve = kingdom.resource_reserves["food"]
    reserve.quantity = min(100.0, reserve.capacity)
    kingdom.laws.grain_reserve = 1.0
    kingdom.policy_compliance[target.id] = 1.0

    before = reserve.quantity + sum(s.resources["food"].quantity for s in settlements)
    _manage_kingdom_food_reserve(engine, kingdom)
    after = reserve.quantity + sum(s.resources["food"].quantity for s in settlements)

    assert target.resources["food"].quantity > 0.0
    assert reserve.quantity < min(100.0, reserve.capacity)
    assert math.isclose(before, after, rel_tol=0.0, abs_tol=1e-8)


def test_production_state_survives_world_round_trip() -> None:
    engine = _engine("production-round-trip")
    engine.advance_days(3, ignore_pause=True)

    loaded = WorldState.model_validate(engine.world.model_dump(mode="json"))

    assert validate_production(loaded) == []
    settlement = loaded.settlements[sorted(loaded.settlements)[0]]
    assert settlement.production_initialized
    assert settlement.production_sites
    assert settlement.labor_allocation
    assert loaded.kingdoms[settlement.kingdom_id].resource_reserves


def test_post_advance_sync_initializes_new_settlement() -> None:
    engine = _engine("production-post-advance-sync")
    source = _settlement(engine)
    kingdom = engine.world.kingdoms[source.kingdom_id]
    new_id = "settlement_slice3_sync_test"
    clone = Settlement.model_validate(source.model_dump(mode="json"))
    clone.id = new_id
    clone.name = "New Production Hamlet"
    clone.population = 50
    clone.ancestry_population = {key: 0 for key in clone.ancestry_population}
    dominant = kingdom.dominant_ancestry
    clone.ancestry_population[dominant] = 50
    clone.production_initialized = False
    clone.production_sites = {}
    clone.labor_allocation = {}
    clone.production_shortages = {}
    clone.production_last_day = {}
    clone.consumption_last_day = {}
    engine.world.settlements[new_id] = clone
    kingdom.settlement_ids.append(new_id)

    engine.advance_hours(0, ignore_pause=True)

    assert clone.production_initialized
    assert clone.production_sites
    assert sum(clone.labor_allocation.values()) == clone.population
    assert validate_production(engine.world) == []


def test_ten_day_material_flow_remains_bounded() -> None:
    engine = _engine("production-ten-day-bounds")

    engine.advance_days(10, ignore_pause=True)

    assert validate_production(engine.world) == []
    assert all(
        math.isfinite(stock.quantity) and 0.0 <= stock.quantity <= stock.capacity
        for settlement in engine.world.settlements.values()
        for stock in settlement.resources.values()
    )
    assert engine.world.metrics["production_throughput_last_day"] >= 0.0
