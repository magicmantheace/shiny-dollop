from __future__ import annotations

from livingworld.generation import generate_world
from livingworld.world_engine import FinalWorldEngine


def _assert_political_integrity(engine: FinalWorldEngine) -> None:
    world = engine.world
    for kingdom in world.kingdoms.values():
        assert 0.0 <= kingdom.legitimacy <= 1.0
        assert kingdom.politics_initialized
        active_factions = []
        for faction_id in kingdom.faction_ids:
            assert faction_id in world.political_factions
            faction = world.political_factions[faction_id]
            assert faction.kingdom_id == kingdom.id
            assert 0.0 <= faction.influence <= 1.0
            assert 0.0 <= faction.loyalty <= 1.0
            if faction.active:
                active_factions.append(faction)
            if faction.leader_npc_id:
                assert faction.leader_npc_id in world.npcs
                leader = world.npcs[faction.leader_npc_id]
                assert leader.alive
                assert leader.kingdom_id == kingdom.id
            for npc_id in faction.member_npc_ids:
                assert npc_id in world.npcs
                npc = world.npcs[npc_id]
                assert npc.alive
                assert npc.kingdom_id == kingdom.id
            if faction.regional_base_settlement_id:
                assert faction.regional_base_settlement_id in world.settlements
                assert world.settlements[faction.regional_base_settlement_id].kingdom_id == kingdom.id

        if active_factions:
            assert abs(sum(faction.influence for faction in active_factions) - 1.0) < 1e-6

        ruler_office = kingdom.political_offices.get("ruler")
        assert ruler_office is not None
        assert ruler_office.holder_npc_id == kingdom.ruler_npc_id
        for office in kingdom.political_offices.values():
            if not office.holder_npc_id:
                continue
            assert office.holder_npc_id in world.npcs
            holder = world.npcs[office.holder_npc_id]
            assert holder.alive
            assert holder.kingdom_id == kingdom.id


def test_bootstrap_does_not_leave_memories_of_hidden_events() -> None:
    world = generate_world("politics-bootstrap-memories", "Politics World")
    before = {
        npc.id: [memory.model_dump(mode="json") for memory in npc.memories]
        for npc in world.npcs.values()
    }

    FinalWorldEngine(world)

    after = {
        npc.id: [memory.model_dump(mode="json") for memory in npc.memories]
        for npc in world.npcs.values()
    }
    assert after == before
    assert world.recent_events == []
    assert world.next_event_sequence == 1


def test_political_references_remain_valid_through_multiple_leadership_cycles() -> None:
    world = generate_world(
        "politics-short-horizon",
        "Politics World",
        target_population=4_000,
        persistent_npcs=70,
        towns=4,
        villages=8,
    )
    engine = FinalWorldEngine(world)
    _assert_political_integrity(engine)

    engine.advance_years(8, ignore_pause=True)

    _assert_political_integrity(engine)
    assert world.metrics["political_factions"] >= 4.0
    assert 0.0 <= world.metrics["average_legitimacy"] <= 1.0
    assert 0.0 <= world.metrics["average_faction_loyalty"] <= 1.0
