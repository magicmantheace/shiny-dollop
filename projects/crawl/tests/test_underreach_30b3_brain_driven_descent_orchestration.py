from collections import deque
from pathlib import Path

from livingworld.crawl_domain import CrawlStatus, ParticipationStatus
from livingworld.crawl_persistence import CrawlPersistence
from livingworld.item_system import drop_all_on_death
from livingworld.runtime_checkpoint import AlphaCheckpointStore, payload_digest
from livingworld.underreach_ai_brain_foundation import (
    AIBrainFoundationService,
    BrainIntent,
)
from livingworld.underreach_brain_driven_descent import (
    METADATA_KEY,
    PROTOCOL,
    BrainDrivenDescentService,
    build_brain_driven_snapshot,
    validate_brain_driven_descent,
)
from livingworld.underreach_full_autonomous_descent import validate_full_autonomous_descent
from livingworld.underreach_resources_survival import validate_resources_survival


SEED = "underreach-30b3-brain-driven-test"
IDS = [f"descender_{index:03d}" for index in range(10)]


class ExplodingProvider:
    provider_id = "exploding-provider-v1"

    def propose(self, observation):
        raise RuntimeError("synthetic provider outage")


class AlwaysWaitProvider:
    provider_id = "always-wait-provider-v1"

    def propose(self, observation):
        proposal_id = "wait_" + payload_digest(
            f"{self.provider_id}:{observation.observation_digest}"
        )[:20]
        return BrainIntent(
            provider_id=self.provider_id,
            proposal_id=proposal_id,
            descender_id=observation.descender_id,
            observation_digest=observation.observation_digest,
            action="wait",
            confidence=1.0,
            reason_codes=("synthetic_wait",),
        )


def _service(seed: str = SEED, *, brain: AIBrainFoundationService | None = None):
    persistence = CrawlPersistence("sqlite://")
    persistence.initialize()
    service = BrainDrivenDescentService(persistence, brain=brain)
    descent = service.create(seed=seed, descender_ids=IDS, stratum_count=3)
    return persistence, service, descent


def _run(seed: str = SEED, *, max_steps: int = 1800):
    _, service, descent = _service(seed)
    result = service.run(descent, max_steps=max_steps)
    return service, descent, result


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


def _move_direct(service: BrainDrivenDescentService, descent, descender_id: str, target: str) -> None:
    participant = descent.participants[descender_id]
    floor = descent.floors[descent.current_floor]
    assert participant.current_location_id is not None
    for sector_id in _path(floor, participant.current_location_id, target)[1:]:
        service.survival.commit_descender_position(descent, descender_id, sector_id)


def test_creation_preserves_accepted_30a5_authority_and_adds_brain_trace():
    _, service, descent = _service()
    metadata = descent.modifiers[METADATA_KEY]
    assert metadata["protocol"] == PROTOCOL
    assert metadata["authoritative"] is True
    assert metadata["brain_provider_can_mutate"] is False
    assert metadata["presentation_feedback_allowed"] is False
    assert metadata["execution_membrane"] == "underreach.brain-intent-execution.v1"
    assert metadata["brain_cadence_steps"] == 1
    assert metadata["run_outcome"] == "planned"
    assert validate_full_autonomous_descent(descent)
    assert validate_brain_driven_descent(descent)
    service.start(descent)
    assert descent.status == CrawlStatus.RUNNING
    assert descent.modifiers[METADATA_KEY]["run_outcome"] == "running"
    assert validate_brain_driven_descent(descent)


def test_one_step_uses_brain_execution_and_keeps_30a5_trace_valid():
    _, service, descent = _service()
    service.start(descent)
    record = service.step(descent)
    metadata = descent.modifiers[METADATA_KEY]
    assert record["step_index"] == 0
    assert metadata["step_count"] == 1
    assert metadata["metrics"]["brain_proposals"] > 0
    assert metadata["metrics"]["brain_executions"] > 0
    assert record["ledger_event_id"] in descent.history_event_ids
    assert record["autonomous_step_event_id"] in descent.history_event_ids
    assert any(
        decision["execution_event_id"] in descent.history_event_ids
        for decision in record["decisions"]
        if decision["execution_event_id"] is not None
    )
    assert validate_full_autonomous_descent(descent)
    assert validate_brain_driven_descent(descent)


def test_provider_errors_fall_back_without_stalling_or_crossing_authority():
    brain = AIBrainFoundationService(provider=ExplodingProvider())
    _, service, descent = _service(SEED + "-provider-error", brain=brain)
    service.start(descent)
    before_tick = descent.current_tick
    record = service.step(descent)
    metadata = descent.modifiers[METADATA_KEY]
    assert descent.current_tick == before_tick + 1
    assert metadata["metrics"]["provider_errors"] == len(record["decisions"])
    assert metadata["metrics"]["fallback_invocations"] == len(record["decisions"])
    assert metadata["metrics"]["brain_executions"] == 0
    assert all(decision["fallback_used"] is True for decision in record["decisions"])
    assert all(decision["outcome"] == "provider_error" for decision in record["decisions"])
    assert validate_brain_driven_descent(descent)


def test_valid_wait_provider_cannot_deadlock_non_exit_descenders():
    brain = AIBrainFoundationService(provider=AlwaysWaitProvider())
    persistence = CrawlPersistence("sqlite://")
    persistence.initialize()
    service = BrainDrivenDescentService(persistence, brain=brain)
    descent = service.create(
        seed=SEED + "-wait-fallback",
        descender_ids=IDS,
        stratum_count=2,
    )
    result = service.run(descent, max_steps=1800)
    metadata = descent.modifiers[METADATA_KEY]
    assert result.completed is True
    assert result.step_limit_reached is False
    assert metadata["metrics"]["brain_executions"] > 0
    assert metadata["metrics"]["fallback_invocations"] > 0
    assert metadata["metrics"]["fallback_moves"] > 0
    assert descent.status == CrawlStatus.COMPLETED
    assert validate_brain_driven_descent(descent)


def test_reference_brain_completes_multi_stratum_descent_unattended():
    service, descent, result = _run(max_steps=1800)
    metadata = descent.modifiers[METADATA_KEY]
    assert result.completed is True
    assert result.extinguished is False
    assert result.step_limit_reached is False
    assert descent.status == CrawlStatus.COMPLETED
    assert descent.current_floor == 3
    assert result.brain_proposals > 0
    assert result.brain_executions > 0
    assert metadata["metrics"]["brain_moves"] > 0
    assert descent.modifiers["_full_autonomous_descent"]["metrics"]["strata_advanced"] == 2
    assert validate_brain_driven_descent(descent)


def test_carried_survival_supply_can_drop_on_a_later_stratum():
    _, service, descent = _service(SEED + "-cross-stratum-supply")
    service.start(descent)
    owner = IDS[0]
    first_cache = next(
        cache
        for cache in descent.modifiers["_loot_cache_relic"]["caches"]
        if cache["stratum_number"] == 1
    )
    _move_direct(service, descent, owner, first_cache["sector_id"])
    service.survival.open_cache(descent, first_cache["cache_id"], owner)
    supply_id = service.survival.supply_item_ids_for_cache(descent, first_cache["cache_id"])[0]
    service.survival.claim_supply_item(descent, supply_id, owner)
    assert descent.items[supply_id].owner_npc_id == owner

    floor_one = descent.floors[1]
    exit_id = floor_one.exit_location_ids[0]
    for descender_id, participant in sorted(descent.participants.items()):
        if participant.status == ParticipationStatus.ACTIVE and participant.current_floor == 1:
            _move_direct(service, descent, descender_id, exit_id)
    service.survival.advance(descent, advance_ticks=0)
    assert descent.current_floor == 2
    assert descent.items[supply_id].owner_npc_id == owner

    entrance = descent.floors[2].entrance_location_id
    assert descent.participants[owner].current_location_id == entrance
    dropped = drop_all_on_death(descent, owner)
    assert supply_id in dropped
    assert descent.items[supply_id].owner_npc_id is None
    assert descent.items[supply_id].location_id == entrance
    assert validate_resources_survival(descent)


def test_full_brain_driven_run_is_exactly_deterministic():
    _, left, left_result = _run(SEED + "-deterministic", max_steps=1800)
    _, right, right_result = _run(SEED + "-deterministic", max_steps=1800)
    assert left_result == right_result
    assert left.model_dump(mode="json") == right.model_dump(mode="json")
    assert left.history_event_ids == right.history_event_ids
    assert build_brain_driven_snapshot(left) == build_brain_driven_snapshot(right)


def test_checkpoint_resume_matches_uninterrupted_brain_driven_run(tmp_path: Path):
    seed = SEED + "-resume"

    straight_persistence = CrawlPersistence("sqlite://")
    straight_persistence.initialize()
    straight_service = BrainDrivenDescentService(straight_persistence)
    straight = straight_service.create(seed=seed, descender_ids=IDS, stratum_count=3)
    straight_result = straight_service.run(straight, max_steps=2200)
    assert straight_result.completed

    resumed_persistence = CrawlPersistence("sqlite://")
    resumed_persistence.initialize()
    resumed_service = BrainDrivenDescentService(resumed_persistence)
    resumed = resumed_service.create(seed=seed, descender_ids=IDS, stratum_count=3)
    resumed_service.start(resumed)
    for _ in range(1200):
        if resumed.current_floor >= 2 or resumed.modifiers[METADATA_KEY]["run_outcome"] != "running":
            break
        resumed_service.step(resumed)
    assert resumed.current_floor == 2
    assert resumed.modifiers[METADATA_KEY]["run_outcome"] == "running"

    events = resumed_persistence.replay_events(resumed.id)
    store = AlphaCheckpointStore(tmp_path / "brain-driven-checkpoints", retention=4)
    store.write(
        "30b3-test-runtime",
        resumed,
        events,
        simulation_config={"protocol": PROTOCOL, "seed": seed},
        reason="30b3-resume-test",
        created_at_unix_ms=3003001,
    )
    loaded = store.load_latest().crawl
    assert validate_brain_driven_descent(loaded)

    resumed_result = resumed_service.run(loaded, max_steps=2200, start_if_planned=False)
    assert resumed_result.completed
    assert loaded.model_dump(mode="json") == straight.model_dump(mode="json")
    assert loaded.history_event_ids == straight.history_event_ids
    assert build_brain_driven_snapshot(loaded) == build_brain_driven_snapshot(straight)
