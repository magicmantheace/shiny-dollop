from __future__ import annotations

from . import political_collapse as _collapse
from .advanced_simulation import LivingWorldEngine
from .domain import Kingdom


def fixed_update_political_crisis_state(
    engine: LivingWorldEngine,
    kingdom: Kingdom,
) -> None:
    """Track sustained political crisis and emit recovery at the correct boundary.

    A sustained crisis begins when the counter reaches CRISIS_MONTHS_REQUIRED. It
    therefore ends when recovery moves the counter back below that same threshold,
    not only when the counter eventually reaches zero.
    """
    faction = _collapse._opposition_faction(engine.world, kingdom)
    prior = kingdom.political_crisis_months
    crisis_now = bool(
        faction
        and kingdom.legitimacy < _collapse.CRISIS_LEGITIMACY_THRESHOLD
        and (
            faction.loyalty < _collapse.CRISIS_FACTION_LOYALTY_THRESHOLD
            or len(faction.grievances) >= 2
        )
    )

    if crisis_now:
        kingdom.political_crisis_months = min(240, prior + 1)
        if kingdom.political_crisis_months == _collapse.CRISIS_MONTHS_REQUIRED:
            engine.emit(
                "POLITICAL_CRISIS",
                f"A sustained crisis of legitimacy took hold in {kingdom.name}.",
                [kingdom.id] + ([faction.id] if faction else []),
                kingdom.capital_settlement_id,
                data={
                    "legitimacy": kingdom.legitimacy,
                    "faction_loyalty": faction.loyalty if faction else None,
                    "grievances": list(faction.grievances) if faction else [],
                    "crisis_months": kingdom.political_crisis_months,
                },
                importance=0.82,
            )
        return

    decay = 2 if kingdom.legitimacy >= 0.45 else 1
    kingdom.political_crisis_months = max(0, prior - decay)

    # The old implementation waited for the counter to reach zero while also
    # requiring the previous value to still be >= 12. With 1- or 2-month decay those
    # conditions can never be true together. Crossing below the sustained-crisis
    # threshold is the correct transition to emit.
    if (
        prior >= _collapse.CRISIS_MONTHS_REQUIRED
        and kingdom.political_crisis_months < _collapse.CRISIS_MONTHS_REQUIRED
    ):
        engine.emit(
            "POLITICAL_CRISIS_EASED",
            f"The political crisis in {kingdom.name} finally eased.",
            [kingdom.id],
            kingdom.capital_settlement_id,
            data={
                "prior_crisis_months": prior,
                "remaining_crisis_months": kingdom.political_crisis_months,
            },
            importance=0.58,
        )


def install_political_crisis_recovery_fix() -> None:
    """Install the Slice 1C recovery-boundary correction."""
    _collapse.update_political_crisis_state = fixed_update_political_crisis_state
