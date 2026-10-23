from __future__ import annotations

from collections import deque

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.crawler_navigation import perceive
from livingworld.runtime_checkpoint import payload_digest
from livingworld.underreach_ai_brain_foundation import (
    AIBrainFoundationService,
    BrainIntent,
    INTENT_PROTOCOL,
    IMPLEMENTATION_VERSION as BRAIN_IMPLEMENTATION_VERSION,
)
from livingworld.underreach_brain_intent_execution import (
    BrainIntentExecutionService,
    DECISION_PROTOCOL,
    validate_intent_for_execution,
)
from livingworld.underreach_full_autonomous_descent import FullAutonomousDescentService


SEED = "underreach-30b2-intent-execution-test"
IDS = [f"descender_{index:03d}" for index in range(8)]


def _stack(seed: str = SEED):
    persistence = CrawlPersistence("sqlite://")
    persistence.initialize()
    autonomous = FullAutonomousDescentService(persistence)
    descent = autonomous.create(seed=seed, descender_ids=IDS, stratum_count=3)
    autonomous.start(descent)
    brain = AIBrainFoundationService()
    executor = BrainIntentExecutionService(brain=brain, survival=autonomous.survival)
    return persistence, autonomous, brain, executor, descent


def _path(floor, start: str, target: str) -> list[str]:
    queue = deque([[start]])
    seen = {start}
    while queue:
        path = queue.popleft()
        current = path[-1]
        if current == target:
            return path
        for neighbor in sorted(floor.locations[current].adjacency):
            if neighbor in seen:
                continue
            seen.add(neighbor)
            queue.append([*path, neighbor])
    raise AssertionError(f"no path from {start} to {target}")


def _move_setup(autonomous: FullAutonomousDescentService, descent, descender_id: str, target: str) -> None:
    participant = descent.participants[descender_id]
    floor = descent.floors[descent.current_floor]
    assert participant.current_location_id is not None
    for sector_id in _path(floor, participant.current_location_id, target)[1:]:
        autonomous.survival.commit_descender_position(descent, descender_id, sector_id)


def _manual_intent(observation, *, action: str, target_sector_id: str | None = None, target_item_id: str | None = None):
    body = f"{observation.observation_digest}:{action}:{target_sector_id}:{target_item_id}"
    proposal_id = "manual_" + payload_digest(body)[:20]
    return BrainIntent(
        protocol=INTENT_PROTOCOL,
        implementation_version=BRAIN_IMPLEMENTATION_VERSION,
        provider_id="test-provider-v1",
        proposal_id=proposal_id,
        descender_id=observation.descender_id,
        observation_digest=observation.observation_digest,
        action=action,
        target_sector_id=target_sector_id,
        target_item_id=target_item_id,
        confidence=0.75,
        reason_codes=("test",),
    )


def test_validation_is_side_effect_free_and_accepts_reference_proposal():
    _, _, brain, executor, descent = _stack()
    intent = brain.propose(descent, IDS[0])
    before = descent.model_dump(mode="json")
    before_history = list(descent.history_event_ids)
    decision = executor.validate(descent, intent)
    assert decision.protocol == DECISION_PROTOCOL
    assert decision.accepted is True
    assert decision.reason_code == "accepted"
    assert descent.model_dump(mode="json") == before
    assert descent.history_event_ids == before_history


def test_accepted_navigation_executes_through_canonical_services_and_ledger():
    _, _, brain, executor, descent = _stack()
    descender_id = IDS[0]
    intent = brain.propose(descent, descender_id)
    before_location = descent.participants[descender_id].current_location_id
    before_history = list(descent.history_event_ids)
    result = executor.execute(descent, intent)
    assert result.accepted is True
    assert result.executed is True
    assert result.reason_code == "executed"
    assert result.execution_event_id in descent.history_event_ids
    assert len(descent.history_event_ids) > len(before_history)
    assert descent.history_event_ids[-1] == result.execution_event_id
    assert result.canonical_state_digest_before != result.canonical_state_digest_after
    if result.resolved_sector_id != before_location:
        assert descent.participants[descender_id].current_location_id == result.resolved_sector_id
        assert any(event_id in descent.history_event_ids for event_id in result.source_event_ids)


def test_stale_intent_is_rejected_without_any_canonical_mutation():
    _, autonomous, brain, executor, descent = _stack()
    stale = brain.propose(descent, IDS[0])
    autonomous.survival.advance_time(descent, descent.current_tick + 1)
    before = descent.model_dump(mode="json")
    before_fingerprint = descent.fingerprint()
    before_history = list(descent.history_event_ids)
    rejected = executor.execute(descent, stale)
    assert rejected.accepted is False
    assert rejected.executed is False
    assert rejected.reason_code == "stale_observation"
    assert descent.model_dump(mode="json") == before
    assert descent.fingerprint() == before_fingerprint
    assert descent.history_event_ids == before_history


def test_execution_semantics_reject_wrong_exit_target_even_when_sector_is_known():
    _, _, brain, executor, descent = _stack()
    descender_id = IDS[0]
    participant = descent.participants[descender_id]
    floor = descent.floors[descent.current_floor]
    perceive(participant, floor, descent.current_tick)
    observation = brain.observe(descent, descender_id)
    candidate = next(
        (
            sector_id
            for sector_id in observation.known_neighbor_sector_ids
            if sector_id not in observation.known_exit_sector_ids
        ),
        None,
    )
    if candidate is None:
        return
    intent = _manual_intent(observation, action="seek_exit", target_sector_id=candidate)
    before = descent.model_dump(mode="json")
    decision = validate_intent_for_execution(descent, intent)
    assert decision.accepted is False
    assert decision.reason_code == "seek_exit_target_not_known_exit"
    result = executor.execute(descent, intent)
    assert result.executed is False
    assert descent.model_dump(mode="json") == before


def test_wait_execution_preserves_gameplay_state_and_records_execution_history():
    _, autonomous, brain, executor, descent = _stack()
    descender_id = IDS[0]
    floor = descent.floors[descent.current_floor]
    exit_id = floor.exit_location_ids[0]
    _move_setup(autonomous, descent, descender_id, exit_id)
    observation = brain.observe(descent, descender_id)
    intent = _manual_intent(observation, action="wait")
    before_gameplay_state = descent.model_dump(
        mode="json",
        exclude={"history_event_ids", "modifiers"},
    )
    before_history_count = len(descent.history_event_ids)
    result = executor.execute(descent, intent)
    assert result.executed is True
    assert result.resolved_sector_id == exit_id
    assert descent.participants[descender_id].current_location_id == exit_id
    assert descent.model_dump(
        mode="json",
        exclude={"history_event_ids", "modifiers"},
    ) == before_gameplay_state
    assert result.canonical_state_digest_before != result.canonical_state_digest_after
    assert len(descent.history_event_ids) == before_history_count + 1
    assert descent.history_event_ids[-1] == result.execution_event_id


def test_owned_supply_can_be_consumed_only_through_accepted_survival_service():
    _, autonomous, brain, executor, descent = _stack()
    descender_id = IDS[0]
    loot = descent.modifiers["_loot_cache_relic"]
    cache = next(cache for cache in loot["caches"] if cache["stratum_number"] == descent.current_floor)
    _move_setup(autonomous, descent, descender_id, cache["sector_id"])
    autonomous.survival.open_cache(descent, cache["cache_id"], descender_id)
    supply_id = autonomous.survival.supply_item_ids_for_cache(descent, cache["cache_id"])[0]
    autonomous.survival.claim_supply_item(descent, supply_id, descender_id)
    observation = brain.observe(descent, descender_id)
    assert supply_id in observation.owned_supply_item_ids
    intent = _manual_intent(observation, action="consume_supply", target_item_id=supply_id)
    result = executor.execute(descent, intent)
    assert result.executed is True
    assert supply_id not in descent.items
    assert supply_id not in descent.participants[descender_id].gameplay.inventory_item_ids
    assert result.source_event_ids
    assert result.execution_event_id in descent.history_event_ids


def test_execution_is_exactly_deterministic_for_same_canonical_state():
    _, _, left_brain, left_executor, left = _stack(SEED + "-determinism")
    _, _, right_brain, right_executor, right = _stack(SEED + "-determinism")
    left_intent = left_brain.propose(left, IDS[0])
    right_intent = right_brain.propose(right, IDS[0])
    assert left_intent == right_intent
    left_result = left_executor.execute(left, left_intent)
    right_result = right_executor.execute(right, right_intent)
    assert left_result == right_result
    assert left.model_dump(mode="json") == right.model_dump(mode="json")
    assert left.history_event_ids == right.history_event_ids


def test_propose_and_execute_keeps_brain_advisory_and_simulation_authoritative():
    _, _, _, executor, descent = _stack()
    before = descent.model_dump(mode="json")
    result = executor.propose_and_execute(descent, IDS[0])
    assert result.accepted is True
    assert result.executed is True
    assert descent.model_dump(mode="json") != before
    event = descent.history_event_ids[-1]
    assert event == result.execution_event_id
