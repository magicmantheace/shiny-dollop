from __future__ import annotations

from livingworld.continent_generation import generate_continent_world
from livingworld.generation import generate_world
from livingworld.world_engine import FinalWorldEngine


def _engine(seed: str = "long-term-balance") -> FinalWorldEngine:
    return FinalWorldEngine(generate_continent_world(seed, "Eldara"))


def _prime_severe_claim_dispute(engine: FinalWorldEngine):
    left, right = [engine.world.kingdoms[key] for key in sorted(engine.world.kingdoms)[:2]]
    left.relations[right.id].opinion = -1.0
    right.relations[left.id].opinion = -1.0
    left.military_readiness = 1.0
    right.military_readiness = 1.0
    left.goals["expansion"] = 1.0
    right.goals["expansion"] = 1.0
    engine.world.cultures[left.culture_id].militarism = 1.0
    engine.world.cultures[right.culture_id].militarism = 1.0

    for index in range(3):
        claim_id = f"test_claim_{index}"
        engine.world.territory_claims[claim_id] = {
            "id": claim_id,
            "kingdom_id": left.id,
            "status": "contested",
            "contested_by_kingdom_ids": [right.id],
        }
    return left, right


def test_crowded_demography_does_not_run_away() -> None:
    engine = _engine("crowded-demography")
    settlement = max(engine.world.settlements.values(), key=lambda item: item.population)
    start = settlement.population
    settlement.housing_capacity = max(1, int(start * 0.96))
    settlement.health = 0.82
    settlement.food_security = 0.82

    for _ in range(12):
        engine._demography()
        engine.world.date = engine.world.date.plus_hours(30 * 24)

    assert settlement.population <= start
    assert sum(settlement.ancestry_population.values()) == settlement.population


def test_dead_spouse_no_longer_blocks_future_marriage() -> None:
    engine = _engine("widow-remarriage")
    adults = [npc for npc in engine.world.npcs.values() if npc.age >= 20]
    survivor = adults[0]
    dead_spouse = adults[1]
    survivor.age = 30
    dead_spouse.age = 31
    survivor.spouse_id = dead_spouse.id
    dead_spouse.spouse_id = survivor.id
    dead_spouse.alive = False
    dead_spouse.health = 0.0

    engine._form_marriages()

    assert survivor.spouse_id != dead_spouse.id


def test_persistent_target_scales_with_world_size() -> None:
    legacy = FinalWorldEngine(generate_world("persistent-target-legacy", "Legacy World"))
    continent = _engine("persistent-target-continent")

    assert legacy._persistent_target() == 110
    assert continent._persistent_target() == 500


def test_persistent_cast_replenishes_before_extinction() -> None:
    engine = _engine("persistent-replenishment")
    living = engine.world.alive_npcs()
    for npc in living[50:]:
        npc.alive = False
        npc.health = 0.0

    before = len(engine.world.alive_npcs())
    population_before = engine.world.total_population
    engine._replenish_persistent_cast()
    after = len(engine.world.alive_npcs())

    assert before == 50
    assert after > before
    assert after <= before + 30
    assert engine.world.total_population == population_before
    assert any(event.type == "NPC_ENTERED_RECORD" for event in engine.world.recent_events)


def test_severe_contested_claim_tension_can_start_war() -> None:
    engine = _engine("organic-war")
    left, right = _prime_severe_claim_dispute(engine)

    engine._political_escalation()

    war = engine._war_between(left.id, right.id)
    assert war is not None
    assert war.goal == "contested frontier claim"
    assert any(event.type == "WAR_DECLARED" for event in engine.world.recent_events)


def test_severe_dispute_waits_for_declaration_window() -> None:
    engine = _engine("organic-war-off-cycle")
    left, right = _prime_severe_claim_dispute(engine)
    engine.world.date = engine.world.date.plus_hours(30 * 24)
    assert engine.world.date.month == 2

    engine._political_escalation()

    assert engine._war_between(left.id, right.id) is None


def test_peace_applies_multi_year_recovery_window() -> None:
    engine = _engine("postwar-recovery")
    left, right = [engine.world.kingdoms[key] for key in sorted(engine.world.kingdoms)[:2]]
    left.relations[right.id].opinion = -0.9
    right.relations[left.id].opinion = -0.9
    war = engine.declare_war(left.id, right.id, "recovery test")
    current_year = engine.world.date.year

    engine._end_war(war, None, "negotiated recovery test")

    assert left.relations[right.id].truce_until_year >= current_year + 8
    assert right.relations[left.id].truce_until_year >= current_year + 8
    assert left.relations[right.id].opinion >= -0.30
    assert right.relations[left.id].opinion >= -0.30
