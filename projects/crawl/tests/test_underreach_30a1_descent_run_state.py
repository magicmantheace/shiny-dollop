from copy import deepcopy
import json
from pathlib import Path

import pytest

from livingworld.crawl_domain import CrawlStatus, ParticipationStatus
from livingworld.crawl_persistence import CrawlPersistence
from livingworld.runtime_checkpoint import AlphaCheckpointStore, CheckpointError
from livingworld.underreach_descent_run_state import (
    IMPLEMENTATION_VERSION,
    PROTOCOL,
    RUN_METADATA_KEY,
    SERIALIZATION_PROTOCOL,
    DescentRunStateError,
    DescentRunStateService,
    build_descent_run_snapshot,
    restore_descent_run,
    serialize_descent_run,
    validate_descent_run,
    validate_descent_run_snapshot,
)
from livingworld.underreach_domain import Descent


SEED = "underreach-30a1-descent-run-state-test"
IDS = [f"descender_{index:03d}" for index in range(8)]


def _service() -> DescentRunStateService:
    persistence = CrawlPersistence("sqlite://")
    persistence.initialize()
    return DescentRunStateService(persistence)


def _route(descent: Descent, descender_id: str) -> list[str]:
    floor = descent.floors[descent.current_floor]
    start = descent.participants[descender_id].current_location_id
    assert start is not None
    targets = set(floor.exit_location_ids)
    parent: dict[str, str | None] = {start: None}
    queue = [start]
    end = None
    while queue:
        current = queue.pop(0)
        if current in targets:
            end = current
            break
        for neighbor in sorted(floor.locations[current].adjacency):
            if neighbor not in parent:
                parent[neighbor] = current
                queue.append(neighbor)
    assert end is not None
    path = []
    current: str | None = end
    while current is not None:
        path.append(current)
        current = parent[current]
    return list(reversed(path))


def _move_all_to_exit(service: DescentRunStateService, descent: Descent) -> None:
    for descender_id in sorted(descent.participants):
        if descent.participants[descender_id].status != ParticipationStatus.ACTIVE:
            continue
        for sector_id in _route(descent, descender_id)[1:]:
            service.commit_descender_position(descent, descender_id, sector_id)


def test_creation_is_deterministic_and_roster_order_independent():
    left = DescentRunStateService().create(seed=SEED, descender_ids=IDS)
    right = DescentRunStateService().create(seed=SEED, descender_ids=reversed(IDS))
    assert left.model_dump(mode="json") == right.model_dump(mode="json")
    assert left.fingerprint() == right.fingerprint()
    assert build_descent_run_snapshot(left) == build_descent_run_snapshot(right)


def test_seed_or_roster_changes_descent_identity():
    service = DescentRunStateService()
    base = service.create(seed=SEED, descender_ids=IDS)
    other_seed = service.create(seed=SEED + "-other", descender_ids=IDS)
    other_roster = service.create(seed=SEED, descender_ids=IDS[:-1])
    assert len({base.id, other_seed.id, other_roster.id}) == 3


def test_planned_run_has_one_initial_stratum_and_canonical_positions():
    descent = DescentRunStateService().create(seed=SEED, descender_ids=IDS)
    metadata = descent.modifiers[RUN_METADATA_KEY]
    snapshot = build_descent_run_snapshot(descent)
    assert metadata["protocol"] == PROTOCOL
    assert metadata["implementation_version"] == IMPLEMENTATION_VERSION
    assert metadata["authoritative"] is True
    assert metadata["presentation_feedback_allowed"] is False
    assert metadata["multi_stratum_progression_enabled"] is False
    assert len(descent.floors) == 1
    assert descent.current_floor == 1
    assert descent.status == CrawlStatus.PLANNED
    assert snapshot["current_stratum_index"] == 0
    assert snapshot["initial_stratum_only"] is True
    entrance = descent.floors[1].entrance_location_id
    assert {item["sector_id"] for item in snapshot["participant_positions"]} == {entrance}


def test_start_and_tick_lifecycle_are_monotonic():
    service = DescentRunStateService()
    descent = service.create(seed=SEED, descender_ids=IDS)
    service.start(descent, tick=11)
    assert descent.status == CrawlStatus.RUNNING
    assert descent.started_at_tick == 11
    assert descent.current_tick == 11
    service.set_tick(descent, 17)
    assert descent.current_tick == 17
    with pytest.raises(ValueError, match="backwards"):
        service.set_tick(descent, 16)


def test_position_commit_requires_active_run_known_adjacent_sector():
    service = _service()
    assert service.persistence is not None
    descent = service.create(seed=SEED, descender_ids=IDS)
    npc = IDS[0]
    floor = descent.floors[1]
    origin = descent.participants[npc].current_location_id
    assert origin is not None
    neighbor = sorted(floor.locations[origin].adjacency)[0]
    with pytest.raises(DescentRunStateError, match="active Descent"):
        service.commit_descender_position(descent, npc, neighbor)
    service.start(descent)
    service.commit_descender_position(descent, npc, neighbor)
    assert descent.participants[npc].current_location_id == neighbor
    event = service.persistence.list_events(descent.id, event_type="DESCENDER_POSITION_CHANGED")[0]
    assert event.location_id == neighbor
    assert event.data["from_sector_id"] == origin
    assert event.data["to_sector_id"] == neighbor
    non_neighbor = next(
        sector_id
        for sector_id in floor.locations
        if sector_id != neighbor
        and sector_id != origin
        and sector_id not in floor.locations[neighbor].adjacency
    )
    with pytest.raises(DescentRunStateError, match="adjacent edge"):
        service.commit_descender_position(descent, npc, non_neighbor)


def test_elimination_updates_authoritative_counts_without_roster_mutation():
    service = DescentRunStateService()
    descent = service.create(seed=SEED, descender_ids=IDS)
    service.start(descent)
    service.eliminate(descent, IDS[-1])
    snapshot = service.snapshot(descent)
    assert descent.participants[IDS[-1]].status == ParticipationStatus.ELIMINATED
    assert snapshot["starting_descender_count"] == len(IDS)
    assert snapshot["surviving_descender_count"] == len(IDS) - 1
    assert snapshot["eliminated_descender_count"] == 1
    assert snapshot["ordered_descender_ids"] == sorted(IDS)


def test_snapshot_digest_rejects_tampering_and_matches_canonical_state():
    descent = DescentRunStateService().create(seed=SEED, descender_ids=IDS)
    snapshot = build_descent_run_snapshot(descent)
    assert validate_descent_run_snapshot(snapshot, descent)
    altered = deepcopy(snapshot)
    altered["current_tick"] = 999
    with pytest.raises(DescentRunStateError, match="digest"):
        validate_descent_run_snapshot(altered, descent)


def test_portable_serialization_is_canonical_and_exactly_restorable():
    service = DescentRunStateService()
    descent = service.create(seed=SEED, descender_ids=IDS)
    service.start(descent, tick=3)
    first = service.serialize(descent)
    second = serialize_descent_run(descent)
    assert first == second
    assert json.loads(first)["protocol"] == SERIALIZATION_PROTOCOL
    restored = restore_descent_run(first)
    assert restored.model_dump(mode="json") == descent.model_dump(mode="json")
    assert restored.fingerprint() == descent.fingerprint()
    assert build_descent_run_snapshot(restored) == build_descent_run_snapshot(descent)


def test_portable_serialization_rejects_digest_tampering():
    descent = DescentRunStateService().create(seed=SEED, descender_ids=IDS)
    payload = json.loads(serialize_descent_run(descent))
    payload["canonical_state"]["current_tick"] = 99
    with pytest.raises(DescentRunStateError, match="serialization digest"):
        restore_descent_run(payload)


def test_existing_alpha_checkpoint_store_roundtrips_30a1_state(tmp_path: Path):
    service = _service()
    assert service.persistence is not None
    descent = service.create(seed=SEED, descender_ids=IDS)
    service.start(descent, tick=7)
    path = _route(descent, IDS[0])
    service.commit_descender_position(descent, IDS[0], path[1])
    events = service.persistence.replay_events(descent.id)
    store = AlphaCheckpointStore(tmp_path / "checkpoints", retention=4)
    written = store.write(
        "30a1-test-runtime",
        descent,
        events,
        simulation_config={
            "protocol": PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
        },
        reason="30a1-test",
        created_at_unix_ms=123456789,
    )
    loaded = store.load_latest()
    assert loaded.payload["digest"] == written.payload["digest"]
    assert loaded.crawl.model_dump(mode="json") == descent.model_dump(mode="json")
    assert loaded.crawl.fingerprint() == descent.fingerprint()
    assert validate_descent_run(loaded.crawl)


def test_alpha_checkpoint_rejects_tampered_canonical_state(tmp_path: Path):
    service = _service()
    assert service.persistence is not None
    descent = service.create(seed=SEED, descender_ids=IDS)
    service.start(descent)
    events = service.persistence.replay_events(descent.id)
    store = AlphaCheckpointStore(tmp_path / "checkpoints", retention=4)
    written = store.write(
        "30a1-test-runtime",
        descent,
        events,
        simulation_config={"protocol": PROTOCOL},
        created_at_unix_ms=123456789,
    )
    payload = deepcopy(written.payload)
    payload["canonical"]["state"]["current_tick"] += 1
    with pytest.raises(CheckpointError, match="digest mismatch"):
        store.validate(payload)


def test_completion_requires_active_descenders_at_exit():
    service = DescentRunStateService()
    descent = service.create(seed=SEED, descender_ids=IDS)
    service.start(descent)
    with pytest.raises(DescentRunStateError, match="reach an exit"):
        service.complete(descent)


def test_single_stratum_run_can_complete_without_30a2_advancement():
    service = DescentRunStateService()
    descent = service.create(seed=SEED, descender_ids=IDS)
    service.start(descent, tick=5)
    _move_all_to_exit(service, descent)
    service.complete(descent)
    snapshot = service.snapshot(descent)
    assert descent.status == CrawlStatus.COMPLETED
    assert len(descent.floors) == 1
    assert descent.current_floor == 1
    assert snapshot["status"] == "completed"
    assert snapshot["current_stratum_index"] == 0
    assert snapshot["multi_stratum_progression_enabled"] is False
    assert all(
        participant.status == ParticipationStatus.ADVANCED
        for participant in descent.participants.values()
    )


def test_scope_guard_rejects_injected_second_stratum():
    descent = DescentRunStateService().create(seed=SEED, descender_ids=IDS)
    descent.floors[2] = descent.floors[1].model_copy(
        update={"number": 2},
        deep=True,
    )
    with pytest.raises((DescentRunStateError, ValueError)):
        validate_descent_run(descent)
