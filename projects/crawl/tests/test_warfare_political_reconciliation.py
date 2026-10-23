from livingworld.continent_generation import generate_continent_world
from livingworld.politics_benchmark import validate_politics
from livingworld.warfare import end_war
from livingworld.world_engine import FinalWorldEngine


def _war_world(seed: str):
    world = generate_continent_world(seed, "Eldara")
    engine = FinalWorldEngine(world)
    attacker_id, defender_id = sorted(world.kingdoms)[:2]
    war = engine.declare_war(attacker_id, defender_id, "political transfer test", source="test")
    return world, engine, war, attacker_id, defender_id


def test_peace_reconciles_ruler_moved_with_ceded_settlement() -> None:
    world, engine, war, attacker_id, defender_id = _war_world("warfare-politics-ruler-transfer")
    defender = world.kingdoms[defender_id]
    old_ruler = world.npcs[defender.ruler_npc_id]
    target = next(
        world.settlements[sid]
        for sid in defender.settlement_ids
        if sid != defender.capital_settlement_id
    )

    # Reproduce the long-horizon failure: the losing ruler happens to reside in a
    # non-capital settlement that is ceded at peace.
    old_ruler.settlement_id = target.id
    target.occupied_by_kingdom_id = attacker_id
    war.occupation_by_settlement[target.id] = attacker_id
    war.occupied_settlement_ids.append(target.id)

    end_war(engine, war, attacker_id, "test peace")

    assert target.kingdom_id == attacker_id
    assert old_ruler.kingdom_id == attacker_id
    assert defender.ruler_npc_id != old_ruler.id
    if defender.ruler_npc_id:
        successor = world.npcs[defender.ruler_npc_id]
        assert successor.alive
        assert successor.kingdom_id == defender_id
    ruler_office = defender.political_offices["ruler"]
    assert ruler_office.holder_npc_id == defender.ruler_npc_id
    assert validate_politics(world) == []


def test_monthly_succession_guard_rejects_alive_foreign_ruler() -> None:
    world = generate_continent_world("politics-foreign-ruler-guard", "Eldara")
    engine = FinalWorldEngine(world)
    kingdom_id, other_id = sorted(world.kingdoms)[:2]
    kingdom = world.kingdoms[kingdom_id]
    old_ruler = world.npcs[kingdom.ruler_npc_id]

    old_ruler.kingdom_id = other_id
    engine._succession_checks()

    assert kingdom.ruler_npc_id != old_ruler.id
    if kingdom.ruler_npc_id:
        successor = world.npcs[kingdom.ruler_npc_id]
        assert successor.alive
        assert successor.kingdom_id == kingdom_id
    assert kingdom.political_offices["ruler"].holder_npc_id == kingdom.ruler_npc_id
    assert validate_politics(world) == []
