from livingworld.domain import SettlementType
from livingworld.generation import generate_world


def test_v01_generation_contract(world):
    assert world.total_population == 10_000
    assert len(world.kingdoms) == 2
    assert len(world.settlements) == 25
    assert sum(s.type == SettlementType.TOWN for s in world.settlements.values()) == 5
    assert sum(s.type == SettlementType.VILLAGE for s in world.settlements.values()) == 20
    assert len(world.npcs) == 100
    assert len(world.armies) == 2
    assert len(world.trade_routes) > 25
    assert all(k.capital_settlement_id in world.settlements for k in world.kingdoms.values())
    assert all(k.ruler_npc_id in world.npcs for k in world.kingdoms.values())


def test_seeded_generation_is_reproducible():
    a = generate_world("same-seed", "A")
    b = generate_world("same-seed", "A")
    assert a.model_dump(mode="json") == b.model_dump(mode="json")


def test_different_seed_changes_world():
    a = generate_world("alpha", "World")
    b = generate_world("beta", "World")
    assert [s.name for s in a.settlements.values()] != [s.name for s in b.settlements.values()]
