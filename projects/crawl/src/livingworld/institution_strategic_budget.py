from __future__ import annotations

from .domain import Kingdom, StrategicDecision
from .institution_fiscal_balance import fiscal_reserve_floor
from .simulation import WorldEngine


_SPENDING_ACTIONS = {
    "improve_food",
    "build_infrastructure",
    "strengthen_military",
}

_ORIGINAL_EXECUTE_KINGDOM_DECISION = WorldEngine._execute_kingdom_decision
_INSTALLED = False


def _execute_kingdom_decision_with_fiscal_reserve(
    self: WorldEngine,
    kingdom: Kingdom,
    decision: StrategicDecision,
) -> None:
    """Keep legacy quarterly investments from bypassing Slice 2 reserves.

    The legacy executor already contains the correct action effects and fixed costs.
    For spending actions, expose only treasury cash above the currently applicable
    fiscal reserve, execute the legacy action unchanged, then restore the protected
    balance. During fiscal emergencies the shared reserve helper automatically uses
    the lower emergency floor.
    """
    if decision.action not in _SPENDING_ACTIONS:
        _ORIGINAL_EXECUTE_KINGDOM_DECISION(self, kingdom, decision)
        return

    original_treasury = max(0.0, kingdom.treasury)
    reserve_floor = max(0.0, fiscal_reserve_floor(self, kingdom))
    protected = min(original_treasury, reserve_floor)
    spendable = max(0.0, original_treasury - protected)

    kingdom.treasury = spendable
    try:
        _ORIGINAL_EXECUTE_KINGDOM_DECISION(self, kingdom, decision)
    finally:
        remaining_spendable = max(0.0, kingdom.treasury)
        kingdom.treasury = protected + remaining_spendable


def install_institution_strategic_budget() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    WorldEngine._execute_kingdom_decision = _execute_kingdom_decision_with_fiscal_reserve
    _INSTALLED = True
