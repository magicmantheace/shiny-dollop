from __future__ import annotations

import random

from livingworld.continent_generation import generate_continent_world
from livingworld.domain import GovernmentType, PoliticalFactionType, PoliticalOfficeType, WorldState
from livingworld.politics import (
    _leadership_review,
    apply_faction_pressure_to_goals,
    rebellion_candidate,
    refresh_offices,
    select_successor,
    update_factions,
    update_legitimacy,
)
from livingworld.world_engine import FinalWorldEngine


def _engine(seed: str = "politics-test") -> FinalWorldEngine:
    return FinalWorldEngine(generate_continent_world(seed, "Eldara"))


def test_political_bootstrap_does_not_create_fake_history() -> None:
    world = generate_continent_world("politics-bootstrap-history", "Eldara")
    assert world.recent_events == []
    assert world.next_event_sequence == 1

    FinalWorldEngine(world)

    assert world.recent_events == []
    assert world.next_event_sequence == 1


def test_political_society_initializes_with_factions_and_offices() -> None:
    engine = _engine("politics-initialize")

    assert len(engine.world.political_factions) == len(engine.world.kingdoms) * 4
    for kingdom in engine.world.kingdoms.values():
        assert kingdom.politics_initialized
        assert len(kingdom.faction_ids) == 4
        factions = [engine.world.political_factions[fid] for fid in kingdom.faction_ids]
        assert all(faction.kingdom_id == kingdom.id for faction in factions)
        assert abs(sum(faction.influence for faction in factions) - 1.0) < 1e-9
        assert all(0.0 <= faction.loyalty <= 1.0 for faction in factions)
        ruler_office = kingdom.political_offices[PoliticalOfficeType.RULER.value]
        assert ruler_office.holder_npc_id == kingdom.ruler_npc_id


def test_government_forms_expose_different_office_structures() -> None:
    world = generate_continent_world("politics-government-offices", "Eldara")
    kingdoms = [world.kingdoms[key] for key in sorted(world.kingdoms)[:2]]
    kingdoms[0].government = GovernmentType.THEOCRACY
    kingdoms[1].government = GovernmentType.MERCHANT_OLIGARCHY

    FinalWorldEngine(world)
    first, second = kingdoms

    assert PoliticalOfficeType.HIGH_PRIEST.value in first.political_offices
    assert PoliticalOfficeType.HEIR.value not in first.political_offices
    assert PoliticalOfficeType.GUILD_REPRESENTATIVE.value in second.political_offices
    assert PoliticalOfficeType.HIGH_PRIEST.value not in second.political_offices


def test_factions_shift_kingdom_priorities_instead_of_being_cosmetic() -> None:
    engine = _engine("politics-goal-pressure")
    kingdom = engine.world.kingdoms[sorted(engine.world.kingdoms)[0]]
    factions = [engine.world.political_factions[fid] for fid in kingdom.faction_ids]

    for faction in factions:
        faction.influence = 0.02
        faction.ideology["security"] = 0.10
    military = next(f for f in factions if f.kind == PoliticalFactionType.MILITARY)
    military.influence = 0.94
    military.ideology["security"] = 1.0

    before = kingdom.goals["security"]
    for _ in range(12):
        apply_faction_pressure_to_goals(engine, kingdom)

    assert kingdom.goals["security"] > before + 0.05


def test_food_crisis_creates_faction_grievances_and_erodes_legitimacy() -> None:
    engine = _engine("politics-legitimacy")
    kingdom = engine.world.kingdoms[sorted(engine.world.kingdoms)[0]]
    for sid in kingdom.settlement_ids:
        settlement = engine.world.settlements[sid]
        settlement.food_security = 0.12
        settlement.stability = 0.24
    kingdom.legitimacy = 0.72
    before = kingdom.legitimacy

    for _ in range(18):
        update_factions(engine, kingdom)
        update_legitimacy(engine, kingdom)

    factions = [engine.world.political_factions[fid] for fid in kingdom.faction_ids]
    assert any("Food insecurity" in faction.grievances for faction in factions)
    assert any("Local disorder" in faction.grievances for faction in factions)
    assert kingdom.legitimacy < before


def test_monarchy_prefers_living_adult_child_for_succession() -> None:
    engine = _engine("politics-monarchy-succession")
    kingdom = engine.world.kingdoms[sorted(engine.world.kingdoms)[0]]
    kingdom.government = GovernmentType.MONARCHY
    ruler = engine.world.npcs[kingdom.ruler_npc_id]
    candidates = [
        npc for npc in engine.world.npcs.values()
        if npc.kingdom_id == kingdom.id and npc.alive and npc.age >= 18 and npc.id != ruler.id
    ]
    assert len(candidates) >= 2
    child, rival = candidates[:2]
    child.parent_ids = [ruler.id]
    if child.id not in ruler.child_ids:
        ruler.child_ids.append(child.id)
    child.social_status = "commoner"
    child.traits["ambition"] = 0.05
    rival.social_status = "elite"
    rival.traits["ambition"] = 1.0
    ruler.alive = False

    successor = select_successor(engine, kingdom, ruler)

    assert successor is not None
    assert successor.id == child.id


def test_council_can_replace_a_living_ruler_at_scheduled_review() -> None:
    engine = _engine("politics-living-ruler-removal")
    kingdom = engine.world.kingdoms[sorted(engine.world.kingdoms)[0]]
    kingdom.government = GovernmentType.COUNCIL
    kingdom.political_offices.clear()
    refresh_offices(engine, kingdom, emit_changes=False)
    ruler = engine.world.npcs[kingdom.ruler_npc_id]
    challengers = [
        npc for npc in engine.world.npcs.values()
        if npc.kingdom_id == kingdom.id and npc.alive and npc.age >= 18 and npc.id != ruler.id
    ]
    challenger = challengers[0]

    ruler.social_status = "commoner"
    ruler.wealth = 0.0
    ruler.traits.update({"ambition": 0.0, "loyalty": 0.0, "empathy": 0.0})
    ruler.values.update({"freedom": 0.0, "status": 0.0})
    challenger.social_status = "elite"
    challenger.wealth = 500.0
    challenger.traits.update({"ambition": 1.0, "loyalty": 1.0, "empathy": 1.0})
    challenger.values.update({"freedom": 1.0, "status": 1.0, "wealth": 1.0})

    for faction_id in kingdom.faction_ids:
        faction = engine.world.political_factions[faction_id]
        faction.member_npc_ids = [challenger.id]
        faction.leader_npc_id = challenger.id
        faction.loyalty = 0.8

    kingdom.last_leadership_review_year = 1
    engine.world.date.year = 6
    previous_id = kingdom.ruler_npc_id

    _leadership_review(engine, kingdom)

    assert previous_id == ruler.id
    assert ruler.alive
    assert kingdom.ruler_npc_id == challenger.id
    assert ruler.social_status == "elite"
    assert any(event.type == "LEADERSHIP_CHANGED" for event in engine.world.recent_events)


def test_severe_faction_crisis_can_identify_a_breakaway_base(monkeypatch) -> None:
    engine = _engine("politics-rebellion")
    kingdom = next(k for k in engine.world.kingdoms.values() if len(k.settlement_ids) > 1)
    faction = engine.world.political_factions[kingdom.faction_ids[0]]
    kingdom.legitimacy = 0.02
    kingdom.stability = 0.05
    faction.influence = 0.85
    faction.loyalty = 0.0
    faction.grievances = ["Weak legitimacy", "Food insecurity", "Regional neglect"]

    monkeypatch.setattr(engine, "_rng", lambda salt="": random.Random(31))
    # Use a deterministic seed whose first rebellion draw falls inside the crisis chance.
    candidate = rebellion_candidate(engine, kingdom)
    if candidate is None:
        monkeypatch.setattr(engine, "_rng", lambda salt="": _AlwaysEscalateRandom())
        candidate = rebellion_candidate(engine, kingdom)

    assert candidate is not None
    rebel_faction, settlement_id = candidate
    assert rebel_faction.id == faction.id
    assert settlement_id in kingdom.settlement_ids
    assert settlement_id != kingdom.capital_settlement_id


class _AlwaysEscalateRandom(random.Random):
    def random(self) -> float:
        return 0.0


def test_political_state_survives_model_round_trip() -> None:
    engine = _engine("politics-round-trip")
    dumped = engine.world.model_dump(mode="json")
    loaded = WorldState.model_validate(dumped)

    assert set(loaded.political_factions) == set(engine.world.political_factions)
    for kingdom in loaded.kingdoms.values():
        assert kingdom.faction_ids
        assert all(fid in loaded.political_factions for fid in kingdom.faction_ids)
        assert kingdom.political_offices[PoliticalOfficeType.RULER.value].holder_npc_id == kingdom.ruler_npc_id
