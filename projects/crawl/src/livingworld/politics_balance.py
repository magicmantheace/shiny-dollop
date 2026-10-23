from __future__ import annotations

from typing import TYPE_CHECKING

from . import politics as _politics
from .domain import GovernmentType, Kingdom, PoliticalFaction, PoliticalFactionType
from .politics import FACTION_TEMPLATES, GOVERNMENT_FACTIONS, _faction_conditions

if TYPE_CHECKING:
    from .world_engine import FinalWorldEngine


# Slice 1B political-balance constants. Loyalty is an equilibrium, not a meter that
# increases forever. A stable faction should usually live in the broad 0.65-0.90
# range; perfect 1.0 loyalty is intentionally unreachable through ordinary politics.
MAX_ORDINARY_LOYALTY = 0.94
MIN_ORDINARY_LOYALTY = 0.03
LOYALTY_FALL_RATE = 0.10
LOYALTY_RECOVERY_RATE = 0.055


_GRIEVANCE_WEIGHTS: dict[str, float] = {
    "Food insecurity": 0.085,
    "Local disorder": 0.085,
    "Weak legitimacy": 0.095,
    "Excessive taxation": 0.065,
    "Military neglect": 0.060,
    "Restricted trade": 0.055,
    "Religious leadership dispute": 0.075,
}


def _grievance_penalty(grievances: list[str]) -> float:
    penalty = 0.0
    for grievance in grievances:
        if grievance.startswith("Neglect of "):
            penalty += 0.055
        else:
            penalty += _GRIEVANCE_WEIGHTS.get(grievance, 0.05)
    return min(0.36, penalty)


def _institutional_alignment(kingdom: Kingdom, faction: PoliticalFaction) -> float:
    """Small bonus for the bloc most structurally favored by the government form."""
    ordered = GOVERNMENT_FACTIONS.get(kingdom.government)
    if not ordered:
        return 0.0
    if faction.kind == ordered[0]:
        return 0.035
    return 0.0


def _regime_stake(engine: FinalWorldEngine, kingdom: Kingdom, faction: PoliticalFaction) -> float:
    """Factions with leaders inside government have something tangible to lose."""
    leader_id = faction.leader_npc_id
    if not leader_id:
        return 0.0
    if leader_id == kingdom.ruler_npc_id:
        return 0.060
    if any(office.holder_npc_id == leader_id for office in kingdom.political_offices.values()):
        return 0.040
    return 0.0


def faction_loyalty_target(
    engine: FinalWorldEngine,
    kingdom: Kingdom,
    faction: PoliticalFaction,
    satisfaction: float,
    grievances: list[str],
) -> float:
    """Return the political equilibrium this faction currently tends toward.

    Satisfaction supplies the bulk of support, while concrete grievances directly
    subtract from it. Institutional access and leader disposition matter at the
    margins, which lets two factions facing the same kingdom conditions react
    differently without adding arbitrary random drift.
    """
    leader = engine.world.npcs.get(faction.leader_npc_id or "")
    leader_disposition = 0.0
    if leader:
        leader_disposition = (leader.traits.get("loyalty", 0.5) - 0.5) * 0.08

    target = 0.14 + max(0.0, min(1.0, satisfaction)) * 0.72
    target += _institutional_alignment(kingdom, faction)
    target += _regime_stake(engine, kingdom, faction)
    target += leader_disposition
    target -= _grievance_penalty(grievances)
    return max(MIN_ORDINARY_LOYALTY, min(MAX_ORDINARY_LOYALTY, target))


def balanced_update_factions(engine: FinalWorldEngine, kingdom: Kingdom) -> None:
    """Update faction loyalty and influence using the Slice 1B balance model."""
    active = [
        engine.world.political_factions[fid]
        for fid in kingdom.faction_ids
        if fid in engine.world.political_factions
        and engine.world.political_factions[fid].active
    ]
    if not active:
        return

    raw_influence: dict[str, float] = {}
    for faction in active:
        satisfaction, grievances = _faction_conditions(engine, kingdom, faction)
        target_loyalty = faction_loyalty_target(
            engine,
            kingdom,
            faction,
            satisfaction,
            grievances,
        )
        response_rate = (
            LOYALTY_FALL_RATE
            if target_loyalty < faction.loyalty
            else LOYALTY_RECOVERY_RATE
        )
        faction.loyalty = max(
            MIN_ORDINARY_LOYALTY,
            min(
                MAX_ORDINARY_LOYALTY,
                faction.loyalty + (target_loyalty - faction.loyalty) * response_rate,
            ),
        )
        faction.grievances = grievances

        leader = engine.world.npcs.get(faction.leader_npc_id or "")
        leader_factor = (
            0.5
            if not leader or not leader.alive
            else 0.65 + leader.traits.get("ambition", 0.5) * 0.45
        )
        institutional = {
            PoliticalFactionType.NOBILITY: (
                1.06
                if kingdom.government
                in {GovernmentType.MONARCHY, GovernmentType.ELECTIVE_MONARCHY}
                else 0.92
            ),
            PoliticalFactionType.MERCHANTS: (
                1.12 if kingdom.government == GovernmentType.MERCHANT_OLIGARCHY else 1.0
            ),
            PoliticalFactionType.MILITARY: (
                1.15 if kingdom.government == GovernmentType.MILITARY_REGIME else 1.0
            ),
            PoliticalFactionType.PRIESTHOOD: (
                1.18 if kingdom.government == GovernmentType.THEOCRACY else 1.0
            ),
            PoliticalFactionType.GUILDS: (
                1.08 if kingdom.government == GovernmentType.COUNCIL else 0.96
            ),
            PoliticalFactionType.FRONTIER: (
                1.08 if kingdom.government == GovernmentType.CLAN_CONFEDERACY else 0.96
            ),
            PoliticalFactionType.COMMONERS: (
                1.04 if kingdom.government == GovernmentType.COUNCIL else 0.92
            ),
        }[faction.kind]

        # Grievances can increase a faction's political salience even while they make
        # it less loyal. Angry blocs should become more influential, not disappear.
        grievance_pressure = min(0.22, len(faction.grievances) * 0.05)
        raw_influence[faction.id] = max(
            0.04,
            faction.influence * 0.72
            + leader_factor * institutional * 0.24
            + grievance_pressure * 0.10,
        )

    total = sum(raw_influence.values())
    if total:
        for faction in active:
            faction.influence = raw_influence[faction.id] / total


def install_political_balance_model() -> None:
    """Install Slice 1B into the existing political cadence.

    run_political_cycle resolves update_factions from the politics module at runtime,
    so replacing that one strategy function keeps the rest of Slice 1 authoritative
    and avoids duplicating the political cadence or rebellion logic.
    """
    _politics.update_factions = balanced_update_factions
