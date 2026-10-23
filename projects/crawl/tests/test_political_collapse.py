from __future__ import annotations

from livingworld.continent_generation import generate_continent_world
from livingworld.domain import PoliticalFactionType, WorldState
from livingworld.political_collapse import (
    CRISIS_MONTHS_REQUIRED,
    assess_political_collapse,
    collapse_diagnostics,
    resolve_political_collapse,
    update_political_crisis_state,
)
from livingworld.politics_benchmark import validate_politics
from livingworld.world_engine import FinalWorldEngine


def _engine(seed: str) -> FinalWorldEngine:
    return FinalWorldEngine(generate_continent_world(seed, "Eldara"))


def _target(engine: FinalWorldEngine):
    kingdom = engine.world.kingdoms[sorted(engine.world.kingdoms)[0]]
    faction = engine.world.political_factions[kingdom.faction_ids[0]]
    return kingdom, faction


def _military_faction(engine: FinalWorldEngine, kingdom):
    return next(
        engine.world.political_factions[fid]
        for fid in kingdom.faction_ids
        if engine.world.political_factions[fid].kind == PoliticalFactionType.MILITARY
    )


def _give_regional_base(engine: FinalWorldEngine, kingdom, faction) -> str:
    settlement_id = next(
        sid for sid in kingdom.settlement_ids
        if sid != kingdom.capital_settlement_id
    )
    faction.regional_base_settlement_id = settlement_id
    return settlement_id


def _set_crisis(kingdom, faction, *, legitimacy: float, stability: float, loyalty: float, grievances: int) -> None:
    kingdom.legitimacy = legitimacy
    kingdom.stability = stability
    faction.loyalty = loyalty
    faction.grievances = [f"Crisis grievance {index}" for index in range(grievances)]


def test_crisis_duration_accumulates_and_recovers() -> None:
    engine = _engine("collapse-duration")
    kingdom, faction = _target(engine)
    _set_crisis(kingdom, faction, legitimacy=0.20, stability=0.40, loyalty=0.30, grievances=3)

    for _ in range(CRISIS_MONTHS_REQUIRED):
        update_political_crisis_state(engine, kingdom)

    assert kingdom.political_crisis_months == CRISIS_MONTHS_REQUIRED
    assert any(event.type == "POLITICAL_CRISIS" for event in engine.world.recent_events)

    kingdom.legitimacy = 0.70
    faction.loyalty = 0.72
    faction.grievances = []
    for _ in range(6):
        update_political_crisis_state(engine, kingdom)

    assert kingdom.political_crisis_months == 0
    assert any(event.type == "POLITICAL_CRISIS_EASED" for event in engine.world.recent_events)


def test_single_settlement_failed_state_is_eligible_for_regime_overthrow() -> None:
    engine = _engine("collapse-regime-assessment")
    kingdom, faction = _target(engine)
    kingdom.settlement_ids = [kingdom.capital_settlement_id]
    kingdom.political_crisis_months = 24
    _set_crisis(kingdom, faction, legitimacy=0.08, stability=0.30, loyalty=0.24, grievances=4)

    assessment = assess_political_collapse(engine.world, kingdom)

    assert assessment.eligible
    assert assessment.outcome == "regime_overthrow"
    assert assessment.settlement_id is None


def test_national_military_opposition_targets_regime_not_territory() -> None:
    engine = _engine("collapse-national-overthrow")
    kingdom, _ = _target(engine)
    faction = _military_faction(engine, kingdom)
    faction.regional_base_settlement_id = None
    kingdom.political_crisis_months = 24
    _set_crisis(kingdom, faction, legitimacy=0.08, stability=0.30, loyalty=0.24, grievances=4)

    for faction_id in kingdom.faction_ids:
        other = engine.world.political_factions[faction_id]
        if other.id != faction.id:
            other.loyalty = 0.82
            other.grievances = []

    assessment = assess_political_collapse(engine.world, kingdom)

    assert assessment.eligible
    assert assessment.faction_id == faction.id
    assert assessment.outcome == "regime_overthrow"
    assert assessment.settlement_id is None


def test_regional_crisis_can_resolve_as_secession() -> None:
    engine = _engine("collapse-secession")
    kingdom, faction = _target(engine)
    regional_id = _give_regional_base(engine, kingdom, faction)
    kingdom.political_crisis_months = 14
    _set_crisis(kingdom, faction, legitimacy=0.22, stability=0.45, loyalty=0.35, grievances=2)
    before_kingdoms = set(engine.world.kingdoms)

    assessment = assess_political_collapse(engine.world, kingdom)
    assert assessment.eligible
    assert assessment.outcome == "regional_secession"
    assert assessment.settlement_id == regional_id

    assert resolve_political_collapse(engine, kingdom, assessment)

    new_ids = set(engine.world.kingdoms) - before_kingdoms
    assert len(new_ids) == 1
    new = engine.world.kingdoms[new_ids.pop()]
    assert assessment.settlement_id in new.settlement_ids
    assert assessment.settlement_id not in kingdom.settlement_ids
    assert kingdom.last_political_resolution == "regional_secession"
    assert kingdom.political_crisis_months == 0
    assert any(event.type == "REGIONAL_SECESSION" for event in engine.world.recent_events)
    assert any(event.type == "FACTION_REBELLION" for event in engine.world.recent_events)
    assert validate_politics(engine.world) == []


def test_breakaway_without_tracked_adults_bootstraps_political_cast() -> None:
    engine = _engine("collapse-empty-breakaway-cast")
    kingdom, faction = _target(engine)
    regional_id = _give_regional_base(engine, kingdom, faction)

    for npc in engine.world.npcs.values():
        if npc.alive and npc.age >= 18 and npc.settlement_id == regional_id:
            npc.settlement_id = kingdom.capital_settlement_id
    assert not any(
        npc.alive and npc.age >= 18 and npc.settlement_id == regional_id
        for npc in engine.world.npcs.values()
    )

    kingdom.political_crisis_months = 14
    _set_crisis(kingdom, faction, legitimacy=0.22, stability=0.45, loyalty=0.35, grievances=2)
    before_kingdoms = set(engine.world.kingdoms)

    assessment = assess_political_collapse(engine.world, kingdom)
    assert assessment.eligible
    assert assessment.outcome == "regional_secession"
    assert resolve_political_collapse(engine, kingdom, assessment)

    new_ids = set(engine.world.kingdoms) - before_kingdoms
    assert len(new_ids) == 1
    new = engine.world.kingdoms[new_ids.pop()]
    adults = [
        npc
        for npc in engine.world.npcs.values()
        if npc.alive and npc.age >= 18 and npc.kingdom_id == new.id
    ]

    assert len(adults) >= 4
    assert new.ruler_npc_id in {npc.id for npc in adults}
    assert len(new.faction_ids) == 4
    assert all(engine.world.political_factions[fid].active for fid in new.faction_ids)
    assert all(
        engine.world.armies[army_id].commander_npc_id in {npc.id for npc in adults}
        for army_id in new.army_ids
    )
    assert any(event.type == "BREAKAWAY_FOUNDERS_ASSEMBLED" for event in engine.world.recent_events)
    assert validate_politics(engine.world) == []


def test_severe_regional_collapse_can_begin_civil_war() -> None:
    engine = _engine("collapse-civil-war")
    kingdom, faction = _target(engine)
    regional_id = _give_regional_base(engine, kingdom, faction)
    kingdom.political_crisis_months = 36
    _set_crisis(kingdom, faction, legitimacy=0.03, stability=0.20, loyalty=0.18, grievances=4)
    parent_id = kingdom.id
    before_kingdoms = set(engine.world.kingdoms)

    assessment = assess_political_collapse(engine.world, kingdom)
    assert assessment.eligible
    assert assessment.forced
    assert assessment.outcome == "civil_war"
    assert assessment.settlement_id == regional_id

    assert resolve_political_collapse(engine, kingdom, assessment)

    new_ids = set(engine.world.kingdoms) - before_kingdoms
    assert len(new_ids) == 1
    new_id = new_ids.pop()
    assert any(
        {war.attacker_kingdom_id, war.defender_kingdom_id} == {parent_id, new_id}
        for war in engine.world.active_wars()
    )
    assert any(event.type == "CIVIL_WAR_STARTED" for event in engine.world.recent_events)
    assert any(
        event.type == "WAR_DECLARED" and event.data.get("goal") == "war of independence"
        for event in engine.world.recent_events
    )
    assert validate_politics(engine.world) == []


def test_forced_collapse_hook_overthrows_regime_instead_of_leaving_failed_state_forever() -> None:
    engine = _engine("collapse-forced-overthrow")
    kingdom, faction = _target(engine)
    kingdom.settlement_ids = [kingdom.capital_settlement_id]
    kingdom.political_crisis_months = 36
    _set_crisis(kingdom, faction, legitimacy=0.02, stability=0.25, loyalty=0.20, grievances=4)
    old_ruler_id = kingdom.ruler_npc_id

    engine._political_fragility()

    assert kingdom.last_political_resolution == "regime_overthrow"
    assert kingdom.last_political_resolution_year == engine.world.date.year
    assert kingdom.political_crisis_months == 0
    assert kingdom.ruler_npc_id != old_ruler_id
    assert kingdom.legitimacy >= 0.30
    assert any(event.type == "REGIME_OVERTHROWN" for event in engine.world.recent_events)


def test_collapse_state_survives_world_round_trip_and_is_instrumented() -> None:
    engine = _engine("collapse-round-trip")
    kingdom, faction = _target(engine)
    kingdom.political_crisis_months = 18
    kingdom.last_political_resolution_year = 7
    kingdom.last_political_resolution = "regime_overthrow"
    _set_crisis(kingdom, faction, legitimacy=0.18, stability=0.35, loyalty=0.30, grievances=3)

    loaded = WorldState.model_validate(engine.world.model_dump(mode="json"))
    restored = loaded.kingdoms[kingdom.id]
    diagnostics = collapse_diagnostics(loaded)

    assert restored.political_crisis_months == 18
    assert restored.last_political_resolution_year == 7
    assert restored.last_political_resolution == "regime_overthrow"
    assert diagnostics["political_crisis_kingdoms"] >= 1
    assert diagnostics["max_political_crisis_months"] >= 18
    assert diagnostics["max_collapse_pressure"] > 0.0
