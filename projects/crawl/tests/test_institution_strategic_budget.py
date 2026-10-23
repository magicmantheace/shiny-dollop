from __future__ import annotations

import pytest

from livingworld.continent_generation import generate_continent_world
from livingworld.domain import StrategicDecision
from livingworld.institution_fiscal_balance import (
    EMERGENCY_RESERVE_PER_CAPITA,
    NORMAL_RESERVE_PER_CAPITA,
    fiscal_reserve_floor,
)
from livingworld.world_engine import FinalWorldEngine


def _engine(seed: str) -> FinalWorldEngine:
    return FinalWorldEngine(generate_continent_world(seed, "Eldara"))


def _kingdom(engine: FinalWorldEngine):
    return engine.world.kingdoms[sorted(engine.world.kingdoms)[0]]


def _population(engine: FinalWorldEngine, kingdom) -> int:
    return sum(
        engine.world.settlements[sid].population
        for sid in kingdom.settlement_ids
        if sid in engine.world.settlements
    )


def _decision(engine: FinalWorldEngine, action: str) -> StrategicDecision:
    return StrategicDecision(
        action=action,
        score=100.0,
        reasons={"test": 1.0},
        created_at=engine.world.date.model_copy(deep=True),
    )


def _make_normal(engine: FinalWorldEngine, kingdom) -> None:
    kingdom.stability = 0.8
    for sid in kingdom.settlement_ids:
        settlement = engine.world.settlements[sid]
        settlement.food_security = 0.9
        settlement.crime = 0.05


def test_quarterly_spending_cannot_cross_normal_reserve() -> None:
    engine = _engine("institution-strategic-reserve")
    kingdom = _kingdom(engine)
    _make_normal(engine, kingdom)
    reserve = fiscal_reserve_floor(engine, kingdom)
    kingdom.treasury = reserve
    roads_before = {
        sid: engine.world.settlements[sid].infrastructure.get("roads", 0.0)
        for sid in kingdom.settlement_ids
    }

    engine._execute_kingdom_decision(kingdom, _decision(engine, "build_infrastructure"))

    assert kingdom.treasury == pytest.approx(reserve)
    assert {
        sid: engine.world.settlements[sid].infrastructure.get("roads", 0.0)
        for sid in kingdom.settlement_ids
    } == roads_before


def test_quarterly_food_investment_can_spend_only_surplus_cash() -> None:
    engine = _engine("institution-strategic-surplus")
    kingdom = _kingdom(engine)
    _make_normal(engine, kingdom)
    reserve = fiscal_reserve_floor(engine, kingdom)
    kingdom.treasury = reserve + 200.0
    grain_stocks = [
        engine.world.settlements[sid].resources["grain"]
        for sid in kingdom.settlement_ids
        if "grain" in engine.world.settlements[sid].resources
    ]
    before = [stock.production_per_day for stock in grain_stocks]

    engine._execute_kingdom_decision(kingdom, _decision(engine, "improve_food"))

    assert kingdom.treasury == pytest.approx(reserve)
    assert grain_stocks
    assert all(
        stock.production_per_day == pytest.approx(value * 1.015)
        for stock, value in zip(grain_stocks, before)
    )


def test_quarterly_emergency_spending_uses_lower_reserve_floor() -> None:
    engine = _engine("institution-strategic-emergency")
    kingdom = _kingdom(engine)
    population = _population(engine, kingdom)
    for sid in kingdom.settlement_ids:
        engine.world.settlements[sid].food_security = 0.25
    kingdom.treasury = population * NORMAL_RESERVE_PER_CAPITA
    emergency_floor = population * EMERGENCY_RESERVE_PER_CAPITA
    armies = [engine.world.armies[aid] for aid in kingdom.army_ids if aid in engine.world.armies]
    for army in armies:
        army.readiness = 0.2
        army.supply_days = 10.0
    treasury_before = kingdom.treasury

    engine._execute_kingdom_decision(kingdom, _decision(engine, "strengthen_military"))

    assert armies
    assert treasury_before - kingdom.treasury == pytest.approx(400.0)
    assert kingdom.treasury >= emergency_floor
    assert all(army.readiness == pytest.approx(0.28) for army in armies)
    assert all(army.supply_days == pytest.approx(18.0) for army in armies)
