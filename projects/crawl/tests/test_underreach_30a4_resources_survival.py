from copy import deepcopy
from pathlib import Path

import pytest

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.gameplay_domain import ItemCategory
from livingworld.runtime_checkpoint import AlphaCheckpointStore
from livingworld.underreach_resources_survival import (
    CRITICAL_THRESHOLD,
    METADATA_KEY,
    PROTOCOL,
    SAFE_REST_STAMINA_RECOVERY,
    STABLE_THRESHOLD,
    SUPPLIES_PER_CACHE,
    WARNING_THRESHOLD,
    ResourcesSurvivalError,
    ResourcesSurvivalService,
    build_resources_survival_snapshot,
    restore_resources_survival,
    serialize_resources_survival,
    validate_resources_survival,
)


SEED = "underreach-30a4-resources-survival-test"
IDS = [f"descender_{index:03d}" for index in range(8)]


def _service() -> ResourcesSurvivalService:
    persistence = CrawlPersistence("sqlite://")
    persistence.initialize()
    return ResourcesSurvivalService(persistence)


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
    result = []
    current: str | None = target_sector_id
    while current is not None:
        result.append(current)
        current = parent[current]
    return list(reversed(result))


def _move(service: ResourcesSurvivalService, descent, descender_id: str, target_sector_id: str) -> None:
    for sector_id in _route(descent, descender_id, target_sector_id)[1:]:
        service.commit_descender_position(descent, descender_id, sector_id)


def _move_active_to_exit(service: ResourcesSurvivalService, descent) -> None:
    floor = descent.floors[descent.current_floor]
    exit_id = sorted(floor.exit_location_ids)[0]
    for descender_id in sorted(descent.participants):
        participant = descent.participants[descender_id]
        if participant.status.value == "active" and participant.current_floor == descent.current_floor:
            _move(service, descent, descender_id, exit_id)


def _loot_cache(descent, stratum_number: int = 1) -> dict:
    return next(
        cache
        for cache in descent.modifiers["_loot_cache_relic"]["caches"]
        if cache["stratum_number"] == stratum_number
    )


def _supply_cache(descent, stratum_number: int = 1) -> dict:
    return next(
        cache
        for cache in descent.modifiers[METADATA_KEY]["supply_caches"]
        if cache["stratum_number"] == stratum_number
    )


def _supply_id(cache: dict, kind: str) -> str:
    return next(bp["id"] for bp in cache["blueprints"] if bp["resource_kind"] == kind)


def test_creation_is_deterministic_and_does_not_duplicate_stamina_truth():
    left = ResourcesSurvivalService().create(seed=SEED, descender_ids=IDS, stratum_count=4)
    right = ResourcesSurvivalService().create(seed=SEED, descender_ids=reversed(IDS), stratum_count=4)
    assert left.model_dump(mode="json") == right.model_dump(mode="json")
    assert build_resources_survival_snapshot(left) == build_resources_survival_snapshot(right)
    metadata = left.modifiers[METADATA_KEY]
    assert metadata["protocol"] == PROTOCOL
    assert metadata["authoritative"] is True
    assert metadata["presentation_feedback_allowed"] is False
    assert metadata["full_autonomous_owner_slice"] == "30A.5"
    assert metadata["thresholds"] == {
        "warning": WARNING_THRESHOLD,
        "critical": CRITICAL_THRESHOLD,
        "stable": STABLE_THRESHOLD,
    }
    assert all("stamina" not in state for state in metadata["descenders"].values())
    assert all(0.0 <= participant.gameplay.stamina <= 1.0 for participant in left.participants.values())


def test_each_loot_cache_has_sealed_hydration_and_nutrition_supplies():
    descent = ResourcesSurvivalService().create(seed=SEED, descender_ids=IDS, stratum_count=4)
    supply_caches = descent.modifiers[METADATA_KEY]["supply_caches"]
    assert len(supply_caches) == 4
    assert descent.items == {}
    for cache in supply_caches:
        assert cache["status"] == "sealed"
        assert len(cache["blueprints"]) == SUPPLIES_PER_CACHE
        assert sorted(bp["resource_kind"] for bp in cache["blueprints"]) == ["hydration", "nutrition"]
        assert all(bp["category"] == ItemCategory.RESOURCE.value for bp in cache["blueprints"])


def test_opening_real_loot_cache_reveals_supply_items_once():
    service = _service()
    descent = service.create(seed=SEED, descender_ids=IDS, stratum_count=3)
    service.start(descent, tick=4)
    loot_cache = _loot_cache(descent)
    supply_cache = _supply_cache(descent)
    _move(service, descent, IDS[0], loot_cache["sector_id"])
    service.open_cache(descent, loot_cache["cache_id"], IDS[0])
    assert supply_cache["status"] == "opened"
    assert len(supply_cache["materialized_item_ids"]) == 2
    assert supply_cache["revealed_event_id"] in descent.history_event_ids
    materialized_before = list(supply_cache["materialized_item_ids"])
    service.open_cache(descent, loot_cache["cache_id"], IDS[0])
    assert supply_cache["materialized_item_ids"] == materialized_before
    for item_id in materialized_before:
        item = descent.items[item_id]
        assert item.location_id == loot_cache["sector_id"]
        assert item.provenance_event_ids == [supply_cache["revealed_event_id"]]


def test_supply_claim_requires_colocation_and_preserves_single_holder_invariant():
    service = _service()
    descent = service.create(seed=SEED, descender_ids=IDS, stratum_count=3)
    service.start(descent)
    loot_cache = _loot_cache(descent)
    _move(service, descent, IDS[0], loot_cache["sector_id"])
    service.open_cache(descent, loot_cache["cache_id"], IDS[0])
    supply_cache = _supply_cache(descent)
    item_id = supply_cache["materialized_item_ids"][0]
    with pytest.raises(ResourcesSurvivalError, match="occupy the supply Sector"):
        service.claim_supply_item(descent, item_id, IDS[1])
    item = service.claim_supply_item(descent, item_id, IDS[0])
    assert item.owner_npc_id == IDS[0]
    assert item.location_id is None
    assert item.encounter_id is None
    assert item_id in descent.participants[IDS[0]].gameplay.inventory_item_ids
    assert validate_resources_survival(descent)


def test_survival_time_drain_is_deterministic_and_uses_existing_stamina():
    left = ResourcesSurvivalService().create(seed=SEED, descender_ids=IDS, stratum_count=3)
    right = ResourcesSurvivalService().create(seed=SEED, descender_ids=reversed(IDS), stratum_count=3)
    for descent in (left, right):
        ResourcesSurvivalService().start(descent, tick=5)
        ResourcesSurvivalService().advance_time(descent, 15)
    assert build_resources_survival_snapshot(left) == build_resources_survival_snapshot(right)
    states = left.modifiers[METADATA_KEY]["descenders"]
    for descender_id in IDS:
        assert states[descender_id]["hydration"] < 1.0
        assert states[descender_id]["nutrition"] < 1.0
        assert states[descender_id]["total_ticks_processed"] == 10
        assert 0.0 <= left.participants[descender_id].gameplay.stamina <= 1.0


def test_time_cannot_move_backwards():
    service = ResourcesSurvivalService()
    descent = service.create(seed=SEED, descender_ids=IDS, stratum_count=3)
    service.start(descent, tick=5)
    service.advance_time(descent, 8)
    with pytest.raises(ResourcesSurvivalError, match="backwards"):
        service.advance_time(descent, 7)


def test_deprivation_reaches_critical_and_applies_health_pressure_without_duplicate_death_rule():
    service = _service()
    assert service.persistence is not None
    descent = service.create(seed=SEED, descender_ids=IDS, stratum_count=3)
    service.start(descent)
    health_before = {descender_id: descent.participants[descender_id].health for descender_id in IDS}
    service.advance_time(descent, 70)
    states = descent.modifiers[METADATA_KEY]["descenders"]
    assert any(state["risk_band"] == "critical" for state in states.values())
    assert any(state["total_health_damage"] > 0 for state in states.values())
    assert any(descent.participants[item].health < health_before[item] for item in IDS)
    assert all(descent.participants[item].health >= 0.05 for item in IDS)
    critical_events = service.persistence.list_events(descent.id, event_type="SURVIVAL_THRESHOLD_REACHED")
    assert critical_events


def test_consuming_supply_replenishes_resource_and_deletes_consumed_item():
    service = _service()
    descent = service.create(seed=SEED, descender_ids=IDS, stratum_count=3)
    service.start(descent)
    service.advance_time(descent, 20)
    cache = _loot_cache(descent)
    _move(service, descent, IDS[0], cache["sector_id"])
    service.open_cache(descent, cache["cache_id"], IDS[0])
    supply_cache = _supply_cache(descent)
    hydration_id = _supply_id(supply_cache, "hydration")
    service.claim_supply_item(descent, hydration_id, IDS[0])
    before = descent.modifiers[METADATA_KEY]["descenders"][IDS[0]]["hydration"]
    result = service.consume_supply_item(descent, hydration_id, IDS[0])
    after = descent.modifiers[METADATA_KEY]["descenders"][IDS[0]]["hydration"]
    assert result["resource_kind"] == "hydration"
    assert after > before
    assert hydration_id not in descent.items
    assert hydration_id not in descent.participants[IDS[0]].gameplay.inventory_item_ids
    assert hydration_id in supply_cache["consumed_item_ids"]


def test_safe_area_recovery_restores_existing_stamina_only():
    service = ResourcesSurvivalService()
    descent = service.create(seed=SEED, descender_ids=IDS, stratum_count=3)
    service.start(descent)
    floor = descent.floors[1]
    safe_id = sorted(floor.safe_area_ids)[0]
    _move(service, descent, IDS[0], safe_id)
    descent.participants[IDS[0]].gameplay.stamina = 0.30
    before_resources = deepcopy(descent.modifiers[METADATA_KEY]["descenders"][IDS[0]])
    result = service.recover_at_safe_area(descent, IDS[0])
    assert result["after"] == pytest.approx(0.30 + SAFE_REST_STAMINA_RECOVERY)
    state = descent.modifiers[METADATA_KEY]["descenders"][IDS[0]]
    assert state["hydration"] == before_resources["hydration"]
    assert state["nutrition"] == before_resources["nutrition"]


def test_survival_state_and_owned_supply_carry_across_stratum_transition():
    service = _service()
    descent = service.create(seed=SEED, descender_ids=IDS, stratum_count=3)
    service.start(descent, tick=2)
    service.advance_time(descent, 12)
    cache = _loot_cache(descent)
    _move(service, descent, IDS[0], cache["sector_id"])
    service.open_cache(descent, cache["cache_id"], IDS[0])
    supply_cache = _supply_cache(descent)
    ration_id = _supply_id(supply_cache, "nutrition")
    service.claim_supply_item(descent, ration_id, IDS[0])
    state_before = deepcopy(descent.modifiers[METADATA_KEY]["descenders"][IDS[0]])
    _move_active_to_exit(service, descent)
    service.advance(descent, advance_ticks=2)
    assert descent.current_floor == 2
    assert descent.items[ration_id].owner_npc_id == IDS[0]
    assert ration_id in descent.participants[IDS[0]].gameplay.inventory_item_ids
    state_after = descent.modifiers[METADATA_KEY]["descenders"][IDS[0]]
    assert state_after["hydration"] <= state_before["hydration"]
    assert state_after["nutrition"] <= state_before["nutrition"]
    assert validate_resources_survival(descent)


def test_portable_serialization_roundtrip_is_exact():
    service = ResourcesSurvivalService()
    descent = service.create(seed=SEED, descender_ids=IDS, stratum_count=3)
    service.start(descent, tick=3)
    service.advance_time(descent, 14)
    encoded = serialize_resources_survival(descent)
    restored = restore_resources_survival(encoded)
    assert restored.model_dump(mode="json") == descent.model_dump(mode="json")
    assert build_resources_survival_snapshot(restored) == build_resources_survival_snapshot(descent)


def test_checkpoint_roundtrip_after_transition_preserves_survival_and_supply_state(tmp_path: Path):
    service = _service()
    assert service.persistence is not None
    descent = service.create(seed=SEED, descender_ids=IDS, stratum_count=3)
    service.start(descent, tick=4)
    service.advance_time(descent, 16)
    cache = _loot_cache(descent)
    _move(service, descent, IDS[0], cache["sector_id"])
    service.open_cache(descent, cache["cache_id"], IDS[0])
    supply_cache = _supply_cache(descent)
    item_id = _supply_id(supply_cache, "hydration")
    service.claim_supply_item(descent, item_id, IDS[0])
    _move_active_to_exit(service, descent)
    service.advance(descent, advance_ticks=2)
    expected = build_resources_survival_snapshot(descent)
    events = service.persistence.replay_events(descent.id)
    store = AlphaCheckpointStore(tmp_path / "checkpoints", retention=4)
    written = store.write(
        "30a4-test-runtime",
        descent,
        events,
        simulation_config={"protocol": PROTOCOL, "slice": "30A.4"},
        reason="30a4-test",
        created_at_unix_ms=3004001,
    )
    loaded = store.load_latest()
    assert loaded.payload["digest"] == written.payload["digest"]
    assert loaded.crawl.model_dump(mode="json") == descent.model_dump(mode="json")
    assert build_resources_survival_snapshot(loaded.crawl) == expected


def test_validator_rejects_resource_pool_tampering():
    descent = ResourcesSurvivalService().create(seed=SEED, descender_ids=IDS, stratum_count=3)
    descent.modifiers[METADATA_KEY]["descenders"][IDS[0]]["hydration"] = 1.5
    with pytest.raises(ResourcesSurvivalError, match="invalid hydration"):
        validate_resources_survival(descent)


def test_validator_rejects_supply_blueprint_tampering():
    descent = ResourcesSurvivalService().create(seed=SEED, descender_ids=IDS, stratum_count=3)
    cache = _supply_cache(descent)
    cache["blueprints"][0]["name"] = "Tampered Supply"
    with pytest.raises(ResourcesSurvivalError, match="generation digest|blueprint digest"):
        validate_resources_survival(descent)
