from __future__ import annotations

from .advanced_simulation import LivingWorldEngine
from .domain import Kingdom
from . import institutions


NORMAL_RESERVE_PER_CAPITA = 0.12
EMERGENCY_RESERVE_PER_CAPITA = 0.04
NORMAL_REVENUE_SHARE = 0.35
EMERGENCY_REVENUE_SHARE = 0.85
NORMAL_SURPLUS_DRAW_RATE = 0.01
EMERGENCY_SURPLUS_DRAW_RATE = 0.04

_INSTALLED = False


def _kingdom_population(engine: LivingWorldEngine, kingdom: Kingdom) -> int:
    return sum(
        max(0, engine.world.settlements[sid].population)
        for sid in kingdom.settlement_ids
        if sid in engine.world.settlements
    )


def _is_fiscal_emergency(engine: LivingWorldEngine, kingdom: Kingdom) -> bool:
    settlements = [
        engine.world.settlements[sid]
        for sid in kingdom.settlement_ids
        if sid in engine.world.settlements
    ]
    if engine._war_for_kingdom(kingdom.id) is not None:
        return True
    if kingdom.stability < 0.40:
        return True
    if not settlements:
        return False
    average_food = sum(item.food_security for item in settlements) / len(settlements)
    average_crime = sum(item.crime for item in settlements) / len(settlements)
    return average_food < 0.45 or average_crime > 0.30


def fiscal_reserve_floor(engine: LivingWorldEngine, kingdom: Kingdom) -> float:
    """Return the treasury floor protected from discretionary kingdom spending."""
    population = _kingdom_population(engine, kingdom)
    reserve_per_capita = (
        EMERGENCY_RESERVE_PER_CAPITA
        if _is_fiscal_emergency(engine, kingdom)
        else NORMAL_RESERVE_PER_CAPITA
    )
    return population * reserve_per_capita


def spendable_above_fiscal_reserve(
    engine: LivingWorldEngine,
    kingdom: Kingdom,
) -> float:
    """Return cash that can be spent without crossing the active fiscal reserve."""
    return max(0.0, kingdom.treasury - fiscal_reserve_floor(engine, kingdom))


def balanced_policy_budget(
    engine: LivingWorldEngine,
    kingdom: Kingdom,
) -> tuple[float, float]:
    """Fund policy effects without permanently emptying the kingdom treasury.

    Requested spending still comes from population and policy intensity, preserving
    the original model's demand signal. Actual spending is constrained by both a
    revenue share and a reserve floor. Healthy kingdoms protect a larger reserve and
    only draw a small amount of accumulated surplus. During war, famine, severe
    disorder, or low stability they may spend much more aggressively and draw closer
    to a smaller emergency reserve, but never consume that reserve through this
    policy budget.
    """
    population = _kingdom_population(engine, kingdom)
    average_compliance = sum(kingdom.policy_compliance.values()) / max(
        1, len(kingdom.policy_compliance)
    )
    anti = kingdom.laws.anti_bandit_spending * average_compliance
    military = kingdom.laws.military_spending * average_compliance
    grain = kingdom.laws.grain_reserve * average_compliance
    requested = population * (anti * 0.0015 + military * 0.0024 + grain * 0.0012)

    emergency = _is_fiscal_emergency(engine, kingdom)
    revenue_share = EMERGENCY_REVENUE_SHARE if emergency else NORMAL_REVENUE_SHARE
    surplus_draw_rate = (
        EMERGENCY_SURPLUS_DRAW_RATE if emergency else NORMAL_SURPLUS_DRAW_RATE
    )

    reserve_floor = fiscal_reserve_floor(engine, kingdom)
    available_above_reserve = max(0.0, kingdom.treasury - reserve_floor)
    recent_revenue = max(0.0, kingdom.institutional_revenue_last_month)
    sustainable_cap = recent_revenue * revenue_share
    surplus_draw = available_above_reserve * surplus_draw_rate
    spending_cap = min(
        available_above_reserve,
        sustainable_cap + surplus_draw,
    )

    spent = min(requested, max(0.0, spending_cap))
    if spent > 0.0:
        kingdom.treasury -= spent
    kingdom.institutional_spending_last_month = spent
    return requested, 0.0 if requested <= 0.0 else spent / requested


def install_institution_fiscal_balance() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    institutions._policy_budget = balanced_policy_budget
    _INSTALLED = True
