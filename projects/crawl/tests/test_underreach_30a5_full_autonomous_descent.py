from pathlib import Path

import pytest

from livingworld.crawl_domain import CrawlStatus, ParticipationStatus
from livingworld.crawl_persistence import CrawlPersistence
from livingworld.crawler_decision import CrawlerDecision
from livingworld.runtime_checkpoint import AlphaCheckpointStore
from livingworld.underreach_resources_survival import (
    restore_resources_survival,
    serialize_resources_survival,
)
from livingworld.underreach_full_autonomous_descent import (
    CACHE_SEARCH_BUDGET_STEPS,
    METADATA_KEY,
    PROTOCOL,
    FullAutonomousDescentError,
    FullAutonomousDescentService,
    _decision_override,
    build_full_autonomous_snapshot,
    validate_full_autonomous_descent,
)


SEED = "underreach-30a5-full-autonomous-test"
IDS = [f"descender_{index:03d}" for index in range(12)]


def _service() -> FullAutonomousDescentService:
    persistence = CrawlPersistence("sqlite://")
    persistence.initialize()
    return FullAutonomousDescentService(persistence)


def _run(seed: str = SEED, *, count: int = 12, strata: int = 3, max_steps: int = 1500):
    service = _service()
    ids = [f"descender_{index:03d}" for index in range(count)]
    descent = service.create(seed=seed, descender_ids=ids, stratum_count=strata)
    result = service.run(descent, max_steps=max_steps)
    return service, descent, result


def test_creation_is_deterministic_and_encounters_are_preseeded():
    left = FullAutonomousDescentService().create(seed=SEED, descender_ids=IDS, stratum_count=3)
    right = FullAutonomousDescentService().create(seed=SEED, descender_ids=reversed(IDS), stratum_count=3)
    assert left.model_dump(mode="json") == right.model_dump(mode="json")
    metadata = left.modifiers[METADATA_KEY]
    assert metadata["protocol"] == PROTOCOL
    assert metadata["authoritative"] is True
    assert metadata["presentation_feedback_allowed"] is False
    assert metadata["run_outcome"] == "planned"
    assert metadata["decision_policy"] == "deterministic-bounded-v1"
    assert metadata["seeded_encounter_ids"] == sorted(left.encounters)
    assert len(left.encounters) > 0
    assert validate_full_autonomous_descent(left)


def test_one_step_advances_survival_clock_and_records_bounded_actions():
    service = _service()
    descent = service.create(seed=SEED, descender_ids=IDS, stratum_count=3)
    service.start(descent, tick=7)
    before_events = len(descent.history_event_ids)
    record = service.step(descent)
    assert descent.current_tick == 8
    assert record["step_index"] == 0
    assert record["tick"] == 8
    assert record["ledger_event_id"] in descent.history_event_ids
    assert len(descent.history_event_ids) > before_events
    assert all(
        action["action"] in {"explore", "seek_exit", "seek_safety", "recover", "wait"}
        for action in record["actions"]
    )
    assert descent.modifiers[METADATA_KEY]["step_count"] == 1
    assert validate_full_autonomous_descent(descent)


def test_bounded_cache_search_switches_to_exit_phase_and_holds_arrivals():
    service = _service()
    descent = service.create(seed=SEED + "-exit-phase", descender_ids=IDS, stratum_count=3)
    service.start(descent)
    descender_id = IDS[0]
    metadata = descent.modifiers[METADATA_KEY]
    metadata["stratum_step_counts"]["1"] = CACHE_SEARCH_BUDGET_STEPS
    raw = CrawlerDecision("explore", 1.0, {"test": 1.0})

    decision = _decision_override(descent, descender_id, raw)
    assert decision.action == "seek_exit"
    assert decision.reasons == {"bounded_search_complete": 1.0}

    floor = descent.floors[1]
    descent.participants[descender_id].current_location_id = sorted(floor.exit_location_ids)[0]
    decision = _decision_override(descent, descender_id, raw)
    assert decision.action == "wait"
    assert decision.reasons == {"already_at_exit": 1.0}


def test_autonomous_runner_never_accepts_presentation_feedback_flag():
    descent = FullAutonomousDescentService().create(seed=SEED, descender_ids=IDS, stratum_count=3)
    descent.modifiers[METADATA_KEY]["presentation_feedback_allowed"] = True
    with pytest.raises(FullAutonomousDescentError, match="presentation feedback"):
        validate_full_autonomous_descent(descent)


def test_portable_30a4_serialization_preserves_30a5_trace_and_validates_after_restore():
    service = _service()
    descent = service.create(seed=SEED, descender_ids=IDS, stratum_count=3)
    service.start(descent)
    for _ in range(4):
        if descent.modifiers[METADATA_KEY]["run_outcome"] != "running":
            break
        service.step(descent)
    payload = serialize_resources_survival(descent)
    restored = restore_resources_survival(payload)
    assert restored.model_dump(mode="json") == descent.model_dump(mode="json")
    assert build_full_autonomous_snapshot(restored) == build_full_autonomous_snapshot(descent)
    assert validate_full_autonomous_descent(restored)


def test_checkpoint_roundtrip_preserves_autonomous_trace(tmp_path: Path):
    service = _service()
    assert service.persistence is not None
    descent = service.create(seed=SEED, descender_ids=IDS, stratum_count=3)
    service.start(descent)
    for _ in range(6):
        if descent.modifiers[METADATA_KEY]["run_outcome"] != "running":
            break
        service.step(descent)
    expected = build_full_autonomous_snapshot(descent)
    events = service.persistence.replay_events(descent.id)
    store = AlphaCheckpointStore(tmp_path / "checkpoints", retention=4)
    written = store.write(
        "30a5-test-runtime",
        descent,
        events,
        simulation_config={"protocol": PROTOCOL, "slice": "30A.5"},
        reason="30a5-test",
        created_at_unix_ms=3005001,
    )
    loaded = store.load_latest()
    assert loaded.payload["digest"] == written.payload["digest"]
    assert loaded.crawl.model_dump(mode="json") == descent.model_dump(mode="json")
    assert build_full_autonomous_snapshot(loaded.crawl) == expected
    assert validate_full_autonomous_descent(loaded.crawl)


def test_full_autonomous_descent_completes_multiple_strata_unattended():
    service, descent, result = _run(strata=3, max_steps=1500)
    assert result.completed is True
    assert result.extinguished is False
    assert result.step_limit_reached is False
    assert result.outcome == "completed"
    assert descent.status == CrawlStatus.COMPLETED
    assert descent.current_floor == 3
    assert descent.modifiers[METADATA_KEY]["run_outcome"] == "completed"
    assert descent.modifiers[METADATA_KEY]["metrics"]["moves"] > 0
    assert descent.modifiers[METADATA_KEY]["metrics"]["encounters_resolved"] > 0
    assert descent.modifiers[METADATA_KEY]["metrics"]["strata_advanced"] == 2
    assert descent.surviving_crawler_count > 0
    assert any(
        participant.status == ParticipationStatus.ADVANCED
        for participant in descent.participants.values()
    )
    assert validate_full_autonomous_descent(descent)


def test_full_run_is_bitwise_deterministic_for_same_seed_and_roster():
    _, left, left_result = _run(strata=3, max_steps=1500)
    _, right, right_result = _run(strata=3, max_steps=1500)
    assert left_result == right_result
    assert left.model_dump(mode="json") == right.model_dump(mode="json")
    assert left.history_event_ids == right.history_event_ids
    assert build_full_autonomous_snapshot(left) == build_full_autonomous_snapshot(right)


def test_checkpoint_resume_matches_uninterrupted_final_state(tmp_path: Path):
    ids = list(IDS)

    straight_service = _service()
    straight = straight_service.create(seed=SEED + "-resume", descender_ids=ids, stratum_count=4)
    straight_result = straight_service.run(straight, max_steps=2000)
    assert straight_result.completed

    resumed_service = _service()
    assert resumed_service.persistence is not None
    resumed = resumed_service.create(seed=SEED + "-resume", descender_ids=ids, stratum_count=4)
    resumed_service.start(resumed)
    for _ in range(1000):
        if resumed.current_floor >= 2 or resumed.modifiers[METADATA_KEY]["run_outcome"] != "running":
            break
        resumed_service.step(resumed)
    assert resumed.current_floor == 2
    assert resumed.modifiers[METADATA_KEY]["run_outcome"] == "running"

    checkpoint_events = resumed_service.persistence.replay_events(resumed.id)
    store = AlphaCheckpointStore(tmp_path / "resume-checkpoints", retention=4)
    store.write(
        "30a5-resume-runtime",
        resumed,
        checkpoint_events,
        simulation_config={"protocol": PROTOCOL, "seed": SEED + "-resume"},
        reason="30a5-resume-test",
        created_at_unix_ms=3005002,
    )
    loaded = store.load_latest().crawl
    assert validate_full_autonomous_descent(loaded)
    resumed_result = resumed_service.run(loaded, max_steps=2000, start_if_planned=False)
    assert resumed_result.completed
    assert loaded.model_dump(mode="json") == straight.model_dump(mode="json")
    assert loaded.history_event_ids == straight.history_event_ids
    assert build_full_autonomous_snapshot(loaded) == build_full_autonomous_snapshot(straight)
