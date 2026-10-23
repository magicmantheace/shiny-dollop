from copy import deepcopy
import json
from pathlib import Path

import pytest

from livingworld.crawl_domain import CrawlStatus, FloorStatus, ParticipationStatus
from livingworld.crawl_persistence import CrawlPersistence
from livingworld.runtime_checkpoint import AlphaCheckpointStore, CheckpointError
from livingworld.underreach_descent_run_state import DescentRunStateService, validate_descent_run
from livingworld.underreach_multi_stratum_progression import (
    IMPLEMENTATION_VERSION,
    METADATA_KEY,
    PROTOCOL,
    SERIALIZATION_PROTOCOL,
    MultiStratumProgressionError,
    MultiStratumProgressionService,
    build_multi_stratum_snapshot,
    restore_multi_stratum_descent,
    serialize_multi_stratum_descent,
    validate_multi_stratum_descent,
    validate_multi_stratum_snapshot,
)
from livingworld.underreach_domain import Descent


SEED = "underreach-30a2-multi-stratum-test"
IDS = [f"descender_{index:03d}" for index in range(8)]


def _service() -> MultiStratumProgressionService:
    persistence = CrawlPersistence("sqlite://")
    persistence.initialize()
    return MultiStratumProgressionService(persistence)


def _route(descent: Descent, descender_id: str) -> list[str]:
    stratum = descent.floors[descent.current_floor]
    start = descent.participants[descender_id].current_location_id
    assert start is not None
    exits = set(stratum.exit_location_ids)
    parent: dict[str, str | None] = {start: None}
    queue = [start]
    end = None
    while queue:
        current = queue.pop(0)
        if current in exits:
            end = current
            break
        for neighbor in sorted(stratum.locations[current].adjacency):
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


def _move_active_to_exit(service: MultiStratumProgressionService, descent: Descent) -> None:
    for descender_id in sorted(descent.participants):
        participant = descent.participants[descender_id]
        if participant.status != ParticipationStatus.ACTIVE or participant.current_floor != descent.current_floor:
            continue
        for sector_id in _route(descent, descender_id)[1:]:
            service.commit_descender_position(descent, descender_id, sector_id)


def test_creation_is_deterministic_and_roster_order_independent():
    left = MultiStratumProgressionService().create(seed=SEED, descender_ids=IDS, stratum_count=4)
    right = MultiStratumProgressionService().create(seed=SEED, descender_ids=reversed(IDS), stratum_count=4)
    assert left.model_dump(mode="json") == right.model_dump(mode="json")
    assert left.fingerprint() == right.fingerprint()
    assert build_multi_stratum_snapshot(left) == build_multi_stratum_snapshot(right)


def test_stratum_count_changes_run_identity_and_requires_two_or_more():
    service = MultiStratumProgressionService()
    four = service.create(seed=SEED, descender_ids=IDS, stratum_count=4)
    five = service.create(seed=SEED, descender_ids=IDS, stratum_count=5)
    assert four.id != five.id
    with pytest.raises(MultiStratumProgressionError, match="at least two Strata"):
        service.create(seed=SEED, descender_ids=IDS, stratum_count=1)


def test_planned_state_has_all_strata_pending_and_canonical_roster():
    descent = MultiStratumProgressionService().create(seed=SEED, descender_ids=IDS, stratum_count=4)
    metadata = descent.modifiers[METADATA_KEY]
    snapshot = build_multi_stratum_snapshot(descent)
    assert metadata["protocol"] == PROTOCOL
    assert metadata["implementation_version"] == IMPLEMENTATION_VERSION
    assert metadata["authoritative"] is True
    assert metadata["presentation_feedback_allowed"] is False
    assert metadata["configured_stratum_count"] == 4
    assert metadata["transitions"] == []
    assert descent.status == CrawlStatus.PLANNED
    assert descent.current_floor == 1
    assert all(floor.status == FloorStatus.PENDING for floor in descent.floors.values())
    assert snapshot["configured_stratum_count"] == 4
    assert snapshot["current_stratum_index"] == 0
    assert snapshot["multi_stratum_progression_enabled"] is True
    assert snapshot["ordered_descender_ids"] == sorted(IDS)


def test_start_activates_only_first_stratum():
    service = MultiStratumProgressionService()
    descent = service.create(seed=SEED, descender_ids=IDS, stratum_count=4)
    service.start(descent, tick=10)
    assert descent.status == CrawlStatus.RUNNING
    assert descent.current_tick == 10
    assert descent.floors[1].status == FloorStatus.ACTIVE
    assert all(descent.floors[number].status == FloorStatus.PENDING for number in (2, 3, 4))
    assert validate_multi_stratum_descent(descent)


def test_advance_requires_all_active_survivors_at_exit():
    service = MultiStratumProgressionService()
    descent = service.create(seed=SEED, descender_ids=IDS, stratum_count=3)
    service.start(descent)
    with pytest.raises(MultiStratumProgressionError, match="reach an exit"):
        service.advance(descent)


def test_transition_moves_survivors_to_next_entrance_and_preserves_eliminated_position():
    service = _service()
    assert service.persistence is not None
    descent = service.create(seed=SEED, descender_ids=IDS, stratum_count=4)
    service.start(descent, tick=5)
    eliminated_id = IDS[-1]
    eliminated_location = descent.participants[eliminated_id].current_location_id
    service.eliminate(descent, eliminated_id)
    _move_active_to_exit(service, descent)
    service.advance(descent, advance_ticks=2)

    assert descent.current_floor == 2
    assert descent.current_tick == 7
    assert descent.floors[1].status == FloorStatus.COMPLETED
    assert descent.floors[2].status == FloorStatus.ACTIVE
    assert descent.floors[3].status == FloorStatus.PENDING
    assert descent.floors[4].status == FloorStatus.PENDING
    entrance = descent.floors[2].entrance_location_id
    for descender_id in IDS[:-1]:
        participant = descent.participants[descender_id]
        assert participant.status == ParticipationStatus.ACTIVE
        assert participant.current_floor == 2
        assert participant.current_location_id == entrance
    eliminated = descent.participants[eliminated_id]
    assert eliminated.status == ParticipationStatus.ELIMINATED
    assert eliminated.current_floor == 1
    assert eliminated.current_location_id == eliminated_location

    transition = descent.modifiers[METADATA_KEY]["transitions"][0]
    assert transition["from_stratum_number"] == 1
    assert transition["to_stratum_number"] == 2
    assert transition["tick_before"] == 5
    assert transition["tick_after"] == 7
    assert transition["survivor_descender_ids"] == sorted(IDS[:-1])
    assert transition["survivor_count"] == len(IDS) - 1
    assert transition["eliminated_descender_count"] == 1
    assert transition["arrival_sector_id"] == entrance
    assert transition["ledger_event_id"]
    events = service.persistence.list_events(descent.id, event_type="STRATUM_ADVANCED")
    assert len(events) == 1
    assert events[0].id == transition["ledger_event_id"]
    assert events[0].data["transition_digest"] == transition["digest"]


def test_multiple_transitions_are_sequential_and_previous_strata_stay_completed():
    service = MultiStratumProgressionService()
    descent = service.create(seed=SEED, descender_ids=IDS, stratum_count=4)
    service.start(descent)
    for target_floor in (2, 3, 4):
        _move_active_to_exit(service, descent)
        service.advance(descent)
        assert descent.current_floor == target_floor
        assert [descent.floors[number].status for number in range(1, target_floor)] == [
            FloorStatus.COMPLETED
        ] * (target_floor - 1)
        assert descent.floors[target_floor].status == FloorStatus.ACTIVE
    transitions = descent.modifiers[METADATA_KEY]["transitions"]
    assert [(item["from_stratum_number"], item["to_stratum_number"]) for item in transitions] == [
        (1, 2), (2, 3), (3, 4)
    ]
    assert [item["transition_index"] for item in transitions] == [0, 1, 2]


def test_advance_rejects_final_stratum_and_complete_rejects_nonfinal():
    service = MultiStratumProgressionService()
    descent = service.create(seed=SEED, descender_ids=IDS, stratum_count=2)
    service.start(descent)
    with pytest.raises(MultiStratumProgressionError, match="final Stratum"):
        service.complete(descent)
    _move_active_to_exit(service, descent)
    service.advance(descent)
    _move_active_to_exit(service, descent)
    with pytest.raises(MultiStratumProgressionError, match="final Stratum must use complete"):
        service.advance(descent)


def test_final_completion_preserves_all_completed_strata_and_advanced_survivors():
    service = MultiStratumProgressionService()
    descent = service.create(seed=SEED, descender_ids=IDS, stratum_count=3)
    service.start(descent)
    for _ in range(2):
        _move_active_to_exit(service, descent)
        service.advance(descent)
    _move_active_to_exit(service, descent)
    service.complete(descent)
    snapshot = service.snapshot(descent)
    assert descent.status == CrawlStatus.COMPLETED
    assert descent.current_floor == 3
    assert snapshot["completed_stratum_count"] == 3
    assert all(floor.status == FloorStatus.COMPLETED for floor in descent.floors.values())
    assert all(item.status == ParticipationStatus.ADVANCED for item in descent.participants.values())
    assert len(snapshot["transitions"]) == 2
    assert validate_multi_stratum_descent(descent)


def test_snapshot_digest_rejects_tampering():
    descent = MultiStratumProgressionService().create(seed=SEED, descender_ids=IDS, stratum_count=3)
    snapshot = build_multi_stratum_snapshot(descent)
    assert validate_multi_stratum_snapshot(snapshot, descent)
    altered = deepcopy(snapshot)
    altered["configured_stratum_count"] = 99
    with pytest.raises(MultiStratumProgressionError, match="digest"):
        validate_multi_stratum_snapshot(altered, descent)


def test_portable_serialization_roundtrips_after_real_transition():
    service = MultiStratumProgressionService()
    descent = service.create(seed=SEED, descender_ids=IDS, stratum_count=3)
    service.start(descent, tick=4)
    _move_active_to_exit(service, descent)
    service.advance(descent)
    first = service.serialize(descent)
    second = serialize_multi_stratum_descent(descent)
    assert first == second
    assert json.loads(first)["protocol"] == SERIALIZATION_PROTOCOL
    restored = restore_multi_stratum_descent(first)
    assert restored.model_dump(mode="json") == descent.model_dump(mode="json")
    assert restored.fingerprint() == descent.fingerprint()
    assert build_multi_stratum_snapshot(restored) == build_multi_stratum_snapshot(descent)


def test_portable_serialization_rejects_tampering():
    descent = MultiStratumProgressionService().create(seed=SEED, descender_ids=IDS, stratum_count=3)
    payload = json.loads(serialize_multi_stratum_descent(descent))
    payload["canonical_state"]["current_tick"] = 99
    with pytest.raises(MultiStratumProgressionError, match="serialization digest"):
        restore_multi_stratum_descent(payload)


def test_alpha_checkpoint_roundtrips_after_advancement(tmp_path: Path):
    service = _service()
    assert service.persistence is not None
    descent = service.create(seed=SEED, descender_ids=IDS, stratum_count=4)
    service.start(descent, tick=7)
    _move_active_to_exit(service, descent)
    service.advance(descent, advance_ticks=2)
    events = service.persistence.replay_events(descent.id)
    store = AlphaCheckpointStore(tmp_path / "checkpoints", retention=4)
    written = store.write(
        "30a2-test-runtime",
        descent,
        events,
        simulation_config={
            "protocol": PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "configured_stratum_count": 4,
        },
        reason="30a2-post-transition",
        created_at_unix_ms=3002001,
    )
    loaded = store.load_latest()
    assert loaded.payload["digest"] == written.payload["digest"]
    assert loaded.crawl.model_dump(mode="json") == descent.model_dump(mode="json")
    assert loaded.crawl.current_floor == 2
    assert validate_multi_stratum_descent(loaded.crawl)


def test_alpha_checkpoint_rejects_tampered_transition_state(tmp_path: Path):
    service = _service()
    assert service.persistence is not None
    descent = service.create(seed=SEED, descender_ids=IDS, stratum_count=3)
    service.start(descent)
    _move_active_to_exit(service, descent)
    service.advance(descent)
    events = service.persistence.replay_events(descent.id)
    store = AlphaCheckpointStore(tmp_path / "checkpoints", retention=4)
    written = store.write(
        "30a2-test-runtime",
        descent,
        events,
        simulation_config={"protocol": PROTOCOL},
        created_at_unix_ms=3002002,
    )
    payload = deepcopy(written.payload)
    payload["canonical"]["state"]["current_floor"] = 1
    with pytest.raises(CheckpointError, match="digest mismatch"):
        store.validate(payload)


def test_transition_metadata_tampering_is_rejected():
    service = MultiStratumProgressionService()
    descent = service.create(seed=SEED, descender_ids=IDS, stratum_count=3)
    service.start(descent)
    _move_active_to_exit(service, descent)
    service.advance(descent)
    descent.modifiers[METADATA_KEY]["transitions"][0]["survivor_descender_ids"] = [IDS[0]]
    with pytest.raises(MultiStratumProgressionError, match="survivor"):
        validate_multi_stratum_descent(descent)


def test_30a1_single_stratum_contract_remains_unchanged():
    descent = DescentRunStateService().create(seed=SEED, descender_ids=IDS)
    assert len(descent.floors) == 1
    assert validate_descent_run(descent)
    assert METADATA_KEY not in descent.modifiers
