from __future__ import annotations

import pytest

from livingworld.continent_generation import generate_continent_world
from livingworld.institution_fiscal_balance import (
    EMERGENCY_RESERVE_PER_CAPITA,
    NORMAL_RESERVE_PER_CAPITA,
    balanced_policy_budget,
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


def _maximize_policy_demand(kingdom) -> None:
    kingdom.laws.anti_bandit_spending = 1.0
    kingdom.laws.military_spending = 1.0
    kingdom.laws.grain_reserve = 1.0
    kingdom.policy_compliance = {
        sid: 1.0
        for sid in kingdom.settlement_ids
    }


def test_normal_policy_budget_preserves_reserve_floor() -> None:
    engine = _engine("institution-fiscal-normal")
    kingdom = _kingdom(engine)
    population = _population(engine, kingdom)
    reserve = population * NORMAL_RESERVE_PER_CAPITA
    _maximize_policy_demand(kingdom)
    kingdom.institutional_revenue_last_month = 100.0
    kingdom.treasury = reserve + 1_000.0

    requested, scale = balanced_policy_budget(engine, kingdom)

    assert requested > 0.0
    assert 0.0 < scale < 1.0
    assert kingdom.institutional_spending_last_month == pytest.approx(45.0)
    assert kingdom.treasury >= reserve


def test_depleted_treasury_stops_normal_policy_spending_to_rebuild() -> None:
    engine = _engine("institution-fiscal-rebuild")
    kingdom = _kingdom(engine)
    population = _population(engine, kingdom)
    reserve = population * NORMAL_RESERVE_PER_CAPITA
    _maximize_policy_demand(kingdom)
    kingdom.institutional_revenue_last_month = 100.0
    kingdom.treasury = reserve * 0.75

    requested, scale = balanced_policy_budget(engine, kingdom)

    assert requested > 0.0
    assert scale == 0.0
    assert kingdom.institutional_spending_last_month == 0.0
    assert kingdom.treasury == pytest.approx(reserve * 0.75)


def test_emergency_budget_can_draw_deeper_without_crossing_emergency_floor() -> None:
    engine = _engine("institution-fiscal-emergency")
    kingdom = _kingdom(engine)
    population = _population(engine, kingdom)
    normal_reserve = population * NORMAL_RESERVE_PER_CAPITA
    emergency_reserve = population * EMERGENCY_RESERVE_PER_CAPITA
    _maximize_policy_demand(kingdom)
    for sid in kingdom.settlement_ids:
        engine.world.settlements[sid].food_security = 0.25
    kingdom.institutional_revenue_last_month = 100.0
    kingdom.treasury = normal_reserve

    requested, scale = balanced_policy_budget(engine, kingdom)

    assert requested > 0.0
    assert 0.0 < scale <= 1.0
    assert kingdom.institutional_spending_last_month > 35.0
    assert kingdom.treasury < normal_reserve
    assert kingdom.treasury >= emergency_reserve
