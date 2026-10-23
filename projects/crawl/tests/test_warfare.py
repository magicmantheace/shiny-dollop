from livingworld.continent_generation import generate_continent_world
from livingworld.domain import SettlementType
from livingworld.warfare import end_war, refresh_fronts, update_army_supply, update_sieges_and_occupations
from livingworld.world_engine import FinalWorldEngine


def _war_world(seed: str = "warfare-test"):
    world = generate_continent_world(seed, "Eldara")
    engine = FinalWorldEngine(world)
    kingdom_ids = sorted(world.kingdoms)
    attacker_id, defender_id = kingdom_ids[:2]
    war = engine.declare_war(attacker_id, defender_id, "territorial test", source="test")
    return world, engine, war, attacker_id, defender_id


def test_fronts_and_supply_are_persistent_and_bounded() -> None:
    world, engine, war, attacker_id, defender_id = _war_world("front-supply")
    fronts = refresh_fronts(engine, war)
    assert fronts
    assert len(fronts) <= 6
    assert all(settlement_id in world.settlements for settlement_id in fronts)

    update_army_supply(engine, war)
    for kingdom_id in (attacker_id, defender_id):
        armies = [world.armies[aid] for aid in world.kingdoms[kingdom_id].army_ids]
        assert armies
        for army in armies:
            assert 0.05 <= army.supply_efficiency <= 1.0
            if army.supply_source_settlement_id:
                assert army.supply_source_settlement_id in world.settlements


def test_isolated_army_loses_supply_efficiency_and_morale() -> None:
    world, engine, war, attacker_id, defender_id = _war_world("isolated-supply")
    army = world.armies[world.kingdoms[attacker_id].army_ids[0]]
    remote = next(s for s in world.settlements.values() if s.kingdom_id == defender_id)
    army.location_settlement_id = remote.id
    army.destination_settlement_id = None
    for route in world.trade_routes.values():
        route.active = False
    before_morale = army.morale
    update_army_supply(engine, war)
    assert army.supply_efficiency <= 0.28
    assert army.morale < before_morale


def test_fort_resists_siege_more_than_weak_settlement() -> None:
    world, engine, war, attacker_id, defender_id = _war_world("fort-siege")
    attacker_army = world.armies[world.kingdoms[attacker_id].army_ids[0]]
    attacker_army.troop_count = 4_000
    attacker_army.readiness = 1.0
    attacker_army.morale = 1.0
    attacker_army.supply_efficiency = 1.0

    targets = [s for s in world.settlements.values() if s.kingdom_id == defender_id and s.id != world.kingdoms[defender_id].capital_settlement_id]
    weak, fort = targets[:2]
    weak.population = fort.population = 50
    weak.infrastructure["defenses"] = 0.10
    weak.type = SettlementType.HAMLET
    fort.infrastructure["defenses"] = 0.95
    fort.type = SettlementType.FORT

    attacker_army.location_settlement_id = weak.id
    update_sieges_and_occupations(engine, war)
    weak_progress = weak.siege_progress
    weak.siege_progress = 0.0
    war.siege_progress.clear()
    attacker_army.location_settlement_id = fort.id
    update_sieges_and_occupations(engine, war)
    assert weak_progress > fort.siege_progress


def test_siege_can_create_occupation_and_mark_claim() -> None:
    world, engine, war, attacker_id, defender_id = _war_world("occupation")
    attacker_army = world.armies[world.kingdoms[attacker_id].army_ids[0]]
    target = next(s for s in world.settlements.values() if s.kingdom_id == defender_id and s.id != world.kingdoms[defender_id].capital_settlement_id)
    target.population = 20
    target.infrastructure["defenses"] = 0.05
    attacker_army.location_settlement_id = target.id
    attacker_army.troop_count = 8_000
    attacker_army.readiness = 1.0
    attacker_army.morale = 1.0
    attacker_army.supply_efficiency = 1.0

    for _ in range(20):
        update_sieges_and_occupations(engine, war)
        if target.occupied_by_kingdom_id:
            break

    assert target.occupied_by_kingdom_id == attacker_id
    assert war.occupation_by_settlement[target.id] == attacker_id
    assert target.id in war.occupied_settlement_ids


def test_peace_transfers_occupied_noncapital_and_preserves_population() -> None:
    world, engine, war, attacker_id, defender_id = _war_world("peace-transfer")
    target = next(s for s in world.settlements.values() if s.kingdom_id == defender_id and s.id != world.kingdoms[defender_id].capital_settlement_id)
    target.occupied_by_kingdom_id = attacker_id
    war.occupation_by_settlement[target.id] = attacker_id
    war.occupied_settlement_ids.append(target.id)
    before_population = world.total_population

    end_war(engine, war, attacker_id, "test peace")

    assert target.kingdom_id == attacker_id
    assert target.id in world.kingdoms[attacker_id].settlement_ids
    assert target.id not in world.kingdoms[defender_id].settlement_ids
    assert target.id in war.peace_terms["ceded_settlement_ids"]
    assert world.total_population == before_population


def test_decisive_peace_can_vassalize_small_exhausted_loser() -> None:
    world, engine, war, attacker_id, defender_id = _war_world("vassal")
    defender = world.kingdoms[defender_id]
    noncapital = [sid for sid in defender.settlement_ids if sid != defender.capital_settlement_id]
    for sid in noncapital[4:]:
        defender.settlement_ids.remove(sid)
    war.attacker_score = 70
    war.defender_exhaustion = 0.95

    end_war(engine, war, attacker_id, "decisive test peace")

    assert defender.overlord_kingdom_id == attacker_id
    assert war.peace_terms["vassalized_kingdom_id"] == defender_id
