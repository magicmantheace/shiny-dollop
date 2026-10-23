from __future__ import annotations

from pathlib import Path

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.crawler_navigation import perceive
from livingworld.runtime_checkpoint import AlphaCheckpointStore
from livingworld.underreach_brain_driven_descent import BrainDrivenDescentService
from livingworld.underreach_social_intent_execution import (
    CHALLENGE_EVENT,
    METADATA_KEY,
    RECRUITMENT_ACCEPTED_EVENT,
    RECRUITMENT_OFFERED_EVENT,
    RECRUITMENT_REFUSED_EVENT,
    SHARED_EVENT,
    WARNING_EVENT,
    SocialIntentExecutionService,
    build_social_intent_snapshot,
    validate_social_intent_execution,
)
from livingworld.underreach_social_memory_evolution import SocialMemoryEvolutionService
from livingworld.underreach_social_state import get_relationship


def _stack(seed: str = "30c3-social-intent-test", *, count: int = 5, strata: int = 3):
    persistence = CrawlPersistence("sqlite://")
    persistence.initialize()
    brain = BrainDrivenDescentService(persistence)
    ids = [f"descender_{index:03d}" for index in range(count)]
    descent = brain.create(seed=seed, descender_ids=ids, stratum_count=strata)
    brain.start(descent)
    memory = SocialMemoryEvolutionService(persistence)
    memory.initialize(descent)
    social = SocialIntentExecutionService(persistence)
    social.initialize(descent)
    return persistence, brain, memory, social, descent, ids


def _route(descent, descender_id: str, target_sector_id: str) -> list[str]:
    participant = descent.participants[descender_id]
    floor = descent.floors[participant.current_floor]
    start = participant.current_location_id
    assert start is not None
    parent: dict[str, str | None] = {start: None}
    queue = [start]
    while queue:
        current = queue.pop(0)
        if current == target_sector_id:
            break
        for neighbor in sorted(floor.locations[current].adjacency):
            if neighbor not in parent:
                parent[neighbor] = current
                queue.append(neighbor)
    assert target_sector_id in parent
    result: list[str] = []
    current: str | None = target_sector_id
    while current is not None:
        result.append(current)
        current = parent[current]
    return list(reversed(result))


def _move(brain: BrainDrivenDescentService, descent, descender_id: str, target_sector_id: str) -> None:
    for sector_id in _route(descent, descender_id, target_sector_id)[1:]:
        brain.autonomous.survival.commit_descender_position(descent, descender_id, sector_id)


def _prepare_owned_loot_and_supply(brain: BrainDrivenDescentService, descent, owner_id: str, target_id: str):
    cache = next(
        cache
        for cache in descent.modifiers["_loot_cache_relic"]["caches"]
        if cache["stratum_number"] == descent.current_floor
    )
    for descender_id in (owner_id, target_id):
        _move(brain, descent, descender_id, cache["sector_id"])
    loot_ids = brain.autonomous.survival.open_cache(descent, cache["cache_id"], owner_id)
    loot_id = sorted(loot_ids)[0]
    brain.autonomous.survival.loot.claim_ground_item(descent, loot_id, owner_id)
    supply_ids = brain.autonomous.survival.supply_item_ids_for_cache(descent, cache["cache_id"])
    supply_id = sorted(supply_ids)[0]
    brain.autonomous.survival.claim_supply_item(descent, supply_id, owner_id)
    return loot_id, supply_id, cache


def test_social_proposal_is_advisory_and_side_effect_free() -> None:
    _, _, _, social, descent, ids = _stack()
    before = descent.model_dump(mode="json")
    before_history = list(descent.history_event_ids)

    intent = social.propose(descent, ids[0], "challenge", target_descender_id=ids[1])

    assert intent.action == "challenge"
    assert intent.target_descender_id == ids[1]
    assert descent.model_dump(mode="json") == before
    assert descent.history_event_ids == before_history


def test_share_item_transfers_real_ownership_and_feeds_social_memory() -> None:
    persistence, brain, memory, social, descent, ids = _stack(seed="30c3-share-item")
    item_id, _, _ = _prepare_owned_loot_and_supply(brain, descent, ids[0], ids[1])
    before_relationship = get_relationship(descent, ids[1], ids[0])

    intent = social.propose(
        descent,
        ids[0],
        "share_item",
        target_descender_id=ids[1],
        target_item_id=item_id,
    )
    result = social.execute(descent, intent)

    assert result.executed
    assert result.interaction_event_id is not None
    assert result.execution_event_id is not None
    assert result.memory_event_ids
    assert result.relationship_event_ids
    assert descent.items[item_id].owner_npc_id == ids[1]
    assert item_id not in descent.participants[ids[0]].gameplay.inventory_item_ids
    assert item_id in descent.participants[ids[1]].gameplay.inventory_item_ids
    assert result.interaction_event_id in descent.items[item_id].provenance_event_ids

    memory_state = memory.get_memory(descent, ids[1], ids[0], "shared_resource")
    assert memory_state is not None
    assert result.interaction_event_id in memory_state.source_event_ids
    after_relationship = get_relationship(descent, ids[1], ids[0])
    assert after_relationship.trust > before_relationship.trust
    assert after_relationship.gratitude > before_relationship.gratitude

    source = persistence.events_by_ids([result.interaction_event_id])[0]
    assert source.event_type == SHARED_EVENT
    assert source.actor_ids == [ids[0], ids[1]]
    assert source.data["item_id"] == item_id
    assert source.data["social_action"] == "share_item"


def test_share_supply_uses_resource_only_contract_and_preserves_survival_validation() -> None:
    _, brain, memory, social, descent, ids = _stack(seed="30c3-share-supply")
    item_id, supply_id, _ = _prepare_owned_loot_and_supply(brain, descent, ids[0], ids[1])

    wrong = social.propose(
        descent,
        ids[0],
        "share_supply",
        target_descender_id=ids[1],
        target_item_id=item_id,
    )
    wrong_result = social.execute(descent, wrong)
    assert not wrong_result.executed
    assert wrong_result.reason_code == "item_not_survival_supply"

    intent = social.propose(
        descent,
        ids[0],
        "share_supply",
        target_descender_id=ids[1],
        target_item_id=supply_id,
    )
    result = social.execute(descent, intent)

    assert result.executed
    assert descent.items[supply_id].owner_npc_id == ids[1]
    assert memory.get_memory(descent, ids[1], ids[0], "shared_resource") is not None
    assert validate_social_intent_execution(descent)


def test_warning_shares_bounded_canonical_sector_knowledge() -> None:
    persistence, _, _, social, descent, ids = _stack(seed="30c3-warning")
    actor = descent.participants[ids[0]]
    target = descent.participants[ids[1]]
    assert actor.agent is not None and target.agent is not None
    floor = descent.floors[descent.current_floor]
    perceive(actor, floor, descent.current_tick)
    sector_id = actor.current_location_id
    assert sector_id is not None and sector_id in actor.agent.knowledge
    target.agent.knowledge.pop(sector_id, None)

    intent = social.propose(
        descent,
        ids[0],
        "warn",
        target_descender_id=ids[1],
        target_sector_id=sector_id,
    )
    result = social.execute(descent, intent)

    assert result.executed
    assert sector_id in target.agent.knowledge
    shared = target.agent.knowledge[sector_id]
    source = actor.agent.knowledge[sector_id]
    assert shared.confidence <= 0.95
    assert shared.confidence <= source.confidence
    assert set(shared.known_neighbors) == set(source.known_neighbors)
    event = persistence.events_by_ids([result.interaction_event_id])[0]
    assert event.event_type == WARNING_EVENT
    assert event.data["target_sector_id"] == sector_id


def test_recruitment_offer_acceptance_is_structured_but_does_not_form_party() -> None:
    persistence, _, _, social, descent, ids = _stack(seed="30c3-recruit-accept")

    offer_intent = social.propose(descent, ids[0], "recruit", target_descender_id=ids[1])
    offer_result = social.execute(descent, offer_intent)
    offer_id = offer_result.resolved_offer_id
    assert offer_result.executed and offer_id is not None
    assert descent.modifiers[METADATA_KEY]["recruitment_offers"][offer_id]["status"] == "pending"

    duplicate = social.propose(descent, ids[0], "recruit", target_descender_id=ids[1])
    duplicate_result = social.execute(descent, duplicate)
    assert not duplicate_result.executed
    assert duplicate_result.reason_code == "pending_recruitment_offer_exists"

    response = social.propose(
        descent,
        ids[1],
        "accept_recruitment",
        target_descender_id=ids[0],
        recruitment_offer_id=offer_id,
    )
    response_result = social.execute(descent, response)

    assert response_result.executed
    offer = descent.modifiers[METADATA_KEY]["recruitment_offers"][offer_id]
    assert offer["status"] == "accepted"
    assert offer["resolved_event_id"] == response_result.interaction_event_id
    assert descent.parties == {}
    assert all(participant.current_party_id is None for participant in descent.participants.values())

    events = persistence.events_by_ids([offer_result.interaction_event_id, response_result.interaction_event_id])
    assert [event.event_type for event in events] == [RECRUITMENT_OFFERED_EVENT, RECRUITMENT_ACCEPTED_EVENT]


def test_recruitment_offer_can_be_refused_without_party_mutation() -> None:
    persistence, _, _, social, descent, ids = _stack(seed="30c3-recruit-refuse")
    offered = social.execute(
        descent,
        social.propose(descent, ids[0], "recruit", target_descender_id=ids[2]),
    )
    offer_id = offered.resolved_offer_id
    assert offer_id is not None

    refused = social.execute(
        descent,
        social.propose(
            descent,
            ids[2],
            "refuse_recruitment",
            target_descender_id=ids[0],
            recruitment_offer_id=offer_id,
        ),
    )

    assert refused.executed
    assert descent.modifiers[METADATA_KEY]["recruitment_offers"][offer_id]["status"] == "refused"
    assert descent.parties == {}
    event = persistence.events_by_ids([refused.interaction_event_id])[0]
    assert event.event_type == RECRUITMENT_REFUSED_EVENT


def test_challenge_is_ledger_bound_signal_not_combat_or_rivalry_mutation() -> None:
    persistence, _, _, social, descent, ids = _stack(seed="30c3-challenge")
    before_relationship = get_relationship(descent, ids[0], ids[1])
    before_encounters = descent.model_dump(mode="json")["encounters"]

    result = social.execute(
        descent,
        social.propose(descent, ids[0], "challenge", target_descender_id=ids[1]),
    )

    assert result.executed
    assert get_relationship(descent, ids[0], ids[1]) == before_relationship
    assert descent.model_dump(mode="json")["encounters"] == before_encounters
    event = persistence.events_by_ids([result.interaction_event_id])[0]
    assert event.event_type == CHALLENGE_EVENT
    assert event.data["combat_started"] is False
    assert event.data["rivalry_mutated"] is False
    assert event.data["conflict_owner_slice"] == "30C.5"


def test_stale_social_proposal_is_rejected_without_mutation() -> None:
    _, brain, _, social, descent, ids = _stack(seed="30c3-stale")
    intent = social.propose(descent, ids[0], "challenge", target_descender_id=ids[1])
    brain.autonomous.survival.advance_time(descent, descent.current_tick + 1)
    before = descent.model_dump(mode="json")
    before_history = list(descent.history_event_ids)

    result = social.execute(descent, intent)

    assert not result.executed
    assert result.reason_code == "stale_observation"
    assert descent.model_dump(mode="json") == before
    assert descent.history_event_ids == before_history


def test_non_colocated_social_intent_is_rejected_without_mutation() -> None:
    _, brain, _, social, descent, ids = _stack(seed="30c3-not-colocated")
    floor = descent.floors[descent.current_floor]
    origin = descent.participants[ids[1]].current_location_id
    assert origin is not None
    neighbor = sorted(floor.locations[origin].adjacency)[0]
    brain.autonomous.survival.commit_descender_position(descent, ids[1], neighbor)

    intent = social.propose(descent, ids[0], "challenge", target_descender_id=ids[1])
    before = descent.model_dump(mode="json")
    before_history = list(descent.history_event_ids)
    result = social.execute(descent, intent)

    assert not result.executed
    assert result.reason_code == "target_not_colocated"
    assert descent.model_dump(mode="json") == before
    assert descent.history_event_ids == before_history


def test_persistence_and_checkpoint_restore_social_interaction_state_exactly(tmp_path: Path) -> None:
    persistence, _, _, social, descent, ids = _stack(seed="30c3-checkpoint")
    social.execute(descent, social.propose(descent, ids[0], "recruit", target_descender_id=ids[1]))
    social.execute(descent, social.propose(descent, ids[2], "challenge", target_descender_id=ids[3]))
    expected_state = descent.model_dump(mode="json")
    expected_snapshot = build_social_intent_snapshot(descent)

    saved = persistence.load_crawl(descent.id)
    assert saved is not None
    assert saved.model_dump(mode="json") == expected_state
    assert build_social_intent_snapshot(saved) == expected_snapshot

    events = persistence.replay_events(descent.id)
    store = AlphaCheckpointStore(tmp_path / "checkpoint", retention=4)
    store.write(
        "30c3-test-runtime",
        descent,
        events,
        simulation_config={"slice": "30C.3"},
        reason="30c3-test",
        created_at_unix_ms=3003001,
    )
    loaded = store.load_latest().crawl
    assert loaded.model_dump(mode="json") == expected_state
    assert build_social_intent_snapshot(loaded) == expected_snapshot


def test_independent_identical_social_interactions_are_deterministic() -> None:
    def run_once():
        _, _, _, social, descent, ids = _stack(seed="30c3-determinism")
        offered = social.execute(
            descent,
            social.propose(descent, ids[0], "recruit", target_descender_id=ids[1]),
        )
        social.execute(
            descent,
            social.propose(
                descent,
                ids[1],
                "accept_recruitment",
                target_descender_id=ids[0],
                recruitment_offer_id=offered.resolved_offer_id,
            ),
        )
        social.execute(
            descent,
            social.propose(descent, ids[2], "challenge", target_descender_id=ids[3]),
        )
        return descent.model_dump(mode="json"), build_social_intent_snapshot(descent)

    first_state, first_snapshot = run_once()
    second_state, second_snapshot = run_once()
    assert first_state == second_state
    assert first_snapshot == second_snapshot
