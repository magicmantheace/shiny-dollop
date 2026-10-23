import random

from livingworld.advanced_simulation import LivingWorldEngine
from livingworld.world_engine import FinalWorldEngine


def test_breakaway_kingdom_can_be_founded(world):
    events = []
    engine = LivingWorldEngine(world, events.append)
    parent = next(k for k in world.kingdoms.values() if len(k.settlement_ids) > 1)
    settlement_id = next(s for s in parent.settlement_ids if s != parent.capital_settlement_id)
    before = len(world.kingdoms)
    rebel = engine._found_breakaway_kingdom(parent, settlement_id, random.Random(4))
    assert len(world.kingdoms) == before + 1
    assert world.settlements[settlement_id].kingdom_id == rebel.id
    assert any(event.type == "KINGDOM_FOUNDED" for event in events)


def test_persistent_children_can_join_family_tree(world):
    engine = FinalWorldEngine(world)

    # Construct the couple explicitly so this unit test measures the birth/family
    # system instead of depending on whether the seeded starting social graph happened
    # to generate a married pair.
    couple = None
    for settlement_id in world.settlements:
        residents = [npc for npc in world.npcs.values() if npc.settlement_id == settlement_id and npc.alive]
        mothers = [npc for npc in residents if npc.sex == "female"]
        fathers = [npc for npc in residents if npc.sex == "male"]
        if mothers and fathers:
            couple = (mothers[0], fathers[0])
            break

    assert couple is not None
    mother, father = couple
    mother.age = 25
    father.age = 27
    mother.spouse_id = father.id
    father.spouse_id = mother.id

    for _ in range(360):
        engine.world.date = engine.world.date.plus_hours(30 * 24)
        engine._persistent_births()
        if mother.child_ids:
            break

    assert mother.child_ids
    assert father.child_ids
    assert set(mother.child_ids) == set(father.child_ids)
    assert all(child_id in world.npcs for child_id in mother.child_ids)
    child = world.npcs[mother.child_ids[0]]
    assert set(child.parent_ids) == {mother.id, father.id}


def test_final_capital_can_end_a_kingdom(world):
    events = []
    engine = LivingWorldEngine(world, events.append)
    attacker, defender = list(world.kingdoms.values())[:2]
    # Reduce defender to a single political holding for this focused conquest case.
    keep = defender.capital_settlement_id
    for sid in list(defender.settlement_ids):
        if sid == keep:
            continue
        defender.settlement_ids.remove(sid)
        attacker.settlement_ids.append(sid)
        world.settlements[sid].kingdom_id = attacker.id
    war = engine.declare_war(attacker.id, defender.id, "test conquest")
    engine._end_war(war, attacker.id, "test victory")
    assert defender.id not in world.kingdoms
    assert world.settlements[keep].kingdom_id == attacker.id
    assert any(event.type == "KINGDOM_DESTROYED" for event in events)
