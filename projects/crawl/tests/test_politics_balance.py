from __future__ import annotations

import livingworld.politics as politics
from livingworld.continent_generation import generate_continent_world
from livingworld.politics import FACTION_TEMPLATES
from livingworld.politics_balance import (
    MAX_ORDINARY_LOYALTY,
    balanced_update_factions,
    faction_loyalty_target,
)
from livingworld.world_engine import FinalWorldEngine


def _engine(seed: str) -> FinalWorldEngine:
    return FinalWorldEngine(generate_continent_world(seed, "Eldara"))


def _first_kingdom_and_faction(engine: FinalWorldEngine):
    kingdom = engine.world.kingdoms[sorted(engine.world.kingdoms)[0]]
    faction = engine.world.political_factions[kingdom.faction_ids[0]]
    return kingdom, faction


def _set_healthy_conditions(engine: FinalWorldEngine, kingdom, faction) -> None:
    for sid in kingdom.settlement_ids:
        settlement = engine.world.settlements[sid]
        settlement.food_security = 0.90
        settlement.stability = 0.88
    kingdom.legitimacy = 0.82
    kingdom.military_readiness = 0.76
    kingdom.treasury = 50_000.0
    kingdom.tax_rate = FACTION_TEMPLATES[faction.kind].preferred_tax_rate
    for relation in kingdom.relations.values():
        relation.trade_access = True

    # Keep this helper focused on political/economic recovery. A priesthood leader
    # with a different religion is a valid separate grievance, but should not make
    # this balance regression depend on the generated seed.
    leader = engine.world.npcs.get(faction.leader_npc_id or "")
    if leader and kingdom.religion_id:
        leader.religion_id = kingdom.religion_id


def _set_crisis_conditions(engine: FinalWorldEngine, kingdom, faction) -> None:
    for sid in kingdom.settlement_ids:
        settlement = engine.world.settlements[sid]
        settlement.food_security = 0.10
        settlement.stability = 0.16
    kingdom.legitimacy = 0.18
    kingdom.military_readiness = 0.18
    kingdom.treasury = 0.0
    kingdom.tax_rate = min(0.35, FACTION_TEMPLATES[faction.kind].preferred_tax_rate + 0.16)
    for relation in kingdom.relations.values():
        relation.trade_access = False


def test_balance_model_is_installed_into_authoritative_political_cycle() -> None:
    assert politics.update_factions is balanced_update_factions


def test_healthy_faction_converges_below_perfect_loyalty() -> None:
    engine = _engine("politics-balance-healthy")
    kingdom, faction = _first_kingdom_and_faction(engine)
    _set_healthy_conditions(engine, kingdom, faction)
    faction.loyalty = 1.0

    for _ in range(60):
        balanced_update_factions(engine, kingdom)

    assert 0.60 < faction.loyalty <= MAX_ORDINARY_LOYALTY
    assert faction.loyalty < 0.95


def test_grievances_directly_lower_faction_loyalty_target() -> None:
    engine = _engine("politics-balance-grievance-target")
    kingdom, faction = _first_kingdom_and_faction(engine)

    calm = faction_loyalty_target(engine, kingdom, faction, 0.80, [])
    angry = faction_loyalty_target(
        engine,
        kingdom,
        faction,
        0.80,
        ["Food insecurity", "Local disorder", "Weak legitimacy"],
    )

    assert calm - angry >= 0.25
    assert angry < calm


def test_sustained_crisis_can_create_genuine_disloyalty() -> None:
    engine = _engine("politics-balance-crisis")
    kingdom, faction = _first_kingdom_and_faction(engine)
    _set_crisis_conditions(engine, kingdom, faction)
    faction.loyalty = 0.82

    for _ in range(36):
        balanced_update_factions(engine, kingdom)

    assert "Food insecurity" in faction.grievances
    assert "Local disorder" in faction.grievances
    assert "Weak legitimacy" in faction.grievances
    assert "Excessive taxation" in faction.grievances
    assert faction.loyalty < 0.35


def test_loyalty_recovers_after_crisis_but_does_not_snap_to_perfection() -> None:
    engine = _engine("politics-balance-recovery")
    kingdom, faction = _first_kingdom_and_faction(engine)
    _set_crisis_conditions(engine, kingdom, faction)
    faction.loyalty = 0.82

    for _ in range(36):
        balanced_update_factions(engine, kingdom)
    crisis_loyalty = faction.loyalty

    _set_healthy_conditions(engine, kingdom, faction)
    for _ in range(72):
        balanced_update_factions(engine, kingdom)

    assert faction.loyalty > crisis_loyalty + 0.30
    assert faction.loyalty > 0.60
    assert faction.loyalty < 0.95
    assert not faction.grievances
