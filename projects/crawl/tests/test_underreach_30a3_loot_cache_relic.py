from copy import deepcopy
from pathlib import Path

import pytest

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.gameplay_domain import ItemCategory, ItemRarity
from livingworld.runtime_checkpoint import AlphaCheckpointStore
from livingworld.underreach_loot_cache_relic import (
    CACHE_COUNT_PER_STRATUM,
    METADATA_KEY,
    ORDINARY_ITEMS_PER_CACHE,
    PROTOCOL,
    RELIC_ITEMS_PER_CACHE,
    LootCacheRelicError,
    LootCacheRelicService,
    build_loot_cache_relic_snapshot,
    validate_loot_cache_relic,
)


SEED = "underreach-30a3-loot-cache-relic-test"
IDS = [f"descender_{index:03d}" for index in range(8)]


def _service() -> LootCacheRelicService:
    persistence = CrawlPersistence("sqlite://")
    persistence.initialize()
    return LootCacheRelicService(persistence)


def _route(descent, descender_id: str, target_sector_id: str) -> list[str]:
    participant = descent.participants[descender_id]
    stratum = descent.floors[participant.current_floor]
    start = participant.current_location_id
    assert start is not None
    parent: dict[str, str | None] = {start: None}
    queue = [start]
    while queue:
        current = queue.pop(0)
        if current == target_sector_id:
            break
        for neighbor in sorted(stratum.locations[current].adjacency):
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


def _move(service: LootCacheRelicService, descent, descender_id: str, target_sector_id: str) -> None:
    for sector_id in _route(descent, descender_id, target_sector_id)[1:]:
        service.commit_descender_position(descent, descender_id, sector_id)


def _move_active_to_exit(service: LootCacheRelicService, descent) -> None:
    stratum = descent.floors[descent.current_floor]
    exit_id = sorted(stratum.exit_location_ids)[0]
    for descender_id in sorted(descent.participants):
        participant = descent.participants[descender_id]
        if participant.status.value != "active" or participant.current_floor != descent.current_floor:
            continue
        _move(service, descent, descender_id, exit_id)


def _cache(descent, stratum_number: int = 1):
    return next(
        cache
        for cache in descent.modifiers[METADATA_KEY]["caches"]
        if cache["stratum_number"] == stratum_number
    )


def _relic_id(cache: dict) -> str:
    return next(blueprint["id"] for blueprint in cache["blueprints"] if blueprint["kind"] == "relic")


def test_creation_is_deterministic_and_sealed_items_are_not_ground_loot():
    left = LootCacheRelicService().create(seed=SEED, descender_ids=IDS, stratum_count=4)
    right = LootCacheRelicService().create(seed=SEED, descender_ids=reversed(IDS), stratum_count=4)
    assert left.model_dump(mode="json") == right.model_dump(mode="json")
    assert build_loot_cache_relic_snapshot(left) == build_loot_cache_relic_snapshot(right)
    metadata = left.modifiers[METADATA_KEY]
    assert metadata["protocol"] == PROTOCOL
    assert metadata["authoritative"] is True
    assert metadata["presentation_feedback_allowed"] is False
    assert metadata["resource_survival_owner_slice"] == "30A.4"
    assert len(metadata["caches"]) == len(left.floors) * CACHE_COUNT_PER_STRATUM
    assert all(cache["status"] == "sealed" for cache in metadata["caches"])
    assert left.items == {}


def test_every_stratum_has_one_cache_with_two_ordinary_items_and_one_relic():
    descent = LootCacheRelicService().create(seed=SEED, descender_ids=IDS, stratum_count=4)
    metadata = descent.modifiers[METADATA_KEY]
    for number in range(1, 5):
        caches = [cache for cache in metadata["caches"] if cache["stratum_number"] == number]
        assert len(caches) == CACHE_COUNT_PER_STRATUM
        for cache in caches:
            ordinary = [item for item in cache["blueprints"] if item["kind"] == "ordinary"]
            relics = [item for item in cache["blueprints"] if item["kind"] == "relic"]
            assert len(ordinary) == ORDINARY_ITEMS_PER_CACHE
            assert len(relics) == RELIC_ITEMS_PER_CACHE
            assert relics[0]["category"] == ItemCategory.TRINKET.value
            assert relics[0]["rarity"] == ItemRarity.EPIC.value
            assert relics[0]["important"] is True
    assert len(metadata["relics"]) == 4 * RELIC_ITEMS_PER_CACHE


def test_cache_cannot_open_before_start_or_from_wrong_sector():
    service = _service()
    descent = service.create(seed=SEED, descender_ids=IDS, stratum_count=3)
    cache = _cache(descent)
    with pytest.raises(LootCacheRelicError, match="active Descent"):
        service.open_cache(descent, cache["cache_id"], IDS[0])
    service.start(descent)
    with pytest.raises(LootCacheRelicError, match="cache Sector"):
        service.open_cache(descent, cache["cache_id"], IDS[0])


def test_open_cache_materializes_every_blueprint_once_and_records_discovery():
    service = _service()
    assert service.persistence is not None
    descent = service.create(seed=SEED, descender_ids=IDS, stratum_count=3)
    service.start(descent, tick=4)
    cache = _cache(descent)
    _move(service, descent, IDS[0], cache["sector_id"])
    before_events = len(descent.history_event_ids)
    item_ids = service.open_cache(descent, cache["cache_id"], IDS[0])
    assert item_ids == sorted(blueprint["id"] for blueprint in cache["blueprints"])
    assert cache["status"] == "opened"
    assert cache["opened_event_id"] in descent.history_event_ids
    assert len(descent.history_event_ids) == before_events + 1
    for item_id in item_ids:
        item = descent.items[item_id]
        assert item.location_id == cache["sector_id"]
        assert item.owner_npc_id is None
        assert item.encounter_id is None
        assert item.provenance_event_ids == [cache["opened_event_id"]]
    relic = descent.modifiers[METADATA_KEY]["relics"][_relic_id(cache)]
    assert relic["discovery_event_id"] == cache["opened_event_id"]
    assert service.open_cache(descent, cache["cache_id"], IDS[0]) == item_ids
    assert len(descent.history_event_ids) == before_events + 1
    assert validate_loot_cache_relic(descent)


def test_item_claim_requires_colocation_and_depletes_cache_after_all_first_claims():
    service = _service()
    descent = service.create(seed=SEED, descender_ids=IDS, stratum_count=3)
    service.start(descent)
    cache = _cache(descent)
    _move(service, descent, IDS[0], cache["sector_id"])
    item_ids = service.open_cache(descent, cache["cache_id"], IDS[0])
    with pytest.raises(LootCacheRelicError, match="occupy the item's Sector"):
        service.claim_ground_item(descent, item_ids[0], IDS[1])
    for item_id in item_ids:
        item = service.claim_ground_item(descent, item_id, IDS[0])
        assert item.owner_npc_id == IDS[0]
        assert item.location_id is None
        assert item_id in descent.participants[IDS[0]].gameplay.inventory_item_ids
    assert cache["status"] == "depleted"
    assert cache["claimed_item_ids"] == sorted(item_ids)
    snapshot = service.snapshot(descent)
    assert snapshot["depleted_cache_count"] == 1
    assert snapshot["owned_item_count"] == len(item_ids)
    assert snapshot["ground_item_count"] == 0


def test_relic_provenance_survives_drop_and_second_owner_reclaim():
    service = _service()
    assert service.persistence is not None
    descent = service.create(seed=SEED, descender_ids=IDS, stratum_count=3)
    service.start(descent, tick=2)
    cache = _cache(descent)
    for descender_id in IDS[:2]:
        _move(service, descent, descender_id, cache["sector_id"])
    service.open_cache(descent, cache["cache_id"], IDS[0])
    relic_id = _relic_id(cache)
    relic = service.claim_ground_item(descent, relic_id, IDS[0])
    first_acquisition = relic.provenance_event_ids[-1]
    service.drop_owned_item(descent, relic_id, IDS[0])
    drop_event = relic.provenance_event_ids[-1]
    service.claim_ground_item(descent, relic_id, IDS[1])
    assert relic.owner_npc_id == IDS[1]
    assert relic_id not in descent.participants[IDS[0]].gameplay.inventory_item_ids
    assert relic_id in descent.participants[IDS[1]].gameplay.inventory_item_ids
    assert len(relic.provenance_event_ids) == 4
    assert relic.provenance_event_ids[0] == cache["opened_event_id"]
    assert first_acquisition in relic.provenance_event_ids
    assert drop_event in relic.provenance_event_ids
    record = descent.modifiers[METADATA_KEY]["relics"][relic_id]
    assert len(record["acquisition_event_ids"]) == 2
    events = service.persistence.events_by_ids(relic.provenance_event_ids)
    assert [event.event_type for event in events] == ["CACHE_OPENED", "ITEM_ACQUIRED", "ITEM_DROPPED", "ITEM_ACQUIRED"]


def test_owned_relic_moves_with_survivor_across_stratum_transition():
    service = _service()
    descent = service.create(seed=SEED, descender_ids=IDS, stratum_count=3)
    service.start(descent, tick=5)
    cache = _cache(descent, 1)
    _move(service, descent, IDS[0], cache["sector_id"])
    service.open_cache(descent, cache["cache_id"], IDS[0])
    relic_id = _relic_id(cache)
    service.claim_ground_item(descent, relic_id, IDS[0])
    provenance_before = list(descent.items[relic_id].provenance_event_ids)
    _move_active_to_exit(service, descent)
    service.advance(descent, advance_ticks=2)
    owner = descent.participants[IDS[0]]
    assert descent.current_floor == 2
    assert owner.current_floor == 2
    assert descent.items[relic_id].owner_npc_id == IDS[0]
    assert relic_id in owner.gameplay.inventory_item_ids
    assert descent.items[relic_id].provenance_event_ids == provenance_before
    assert validate_loot_cache_relic(descent)


def test_future_stratum_cache_cannot_open_early():
    service = _service()
    descent = service.create(seed=SEED, descender_ids=IDS, stratum_count=3)
    service.start(descent)
    future = _cache(descent, 2)
    with pytest.raises(LootCacheRelicError, match="current Stratum"):
        service.open_cache(descent, future["cache_id"], IDS[0])


def test_checkpoint_roundtrip_preserves_open_cache_item_and_relic_provenance(tmp_path: Path):
    service = _service()
    assert service.persistence is not None
    descent = service.create(seed=SEED, descender_ids=IDS, stratum_count=3)
    service.start(descent, tick=7)
    cache = _cache(descent, 1)
    _move(service, descent, IDS[0], cache["sector_id"])
    service.open_cache(descent, cache["cache_id"], IDS[0])
    relic_id = _relic_id(cache)
    service.claim_ground_item(descent, relic_id, IDS[0])
    expected = build_loot_cache_relic_snapshot(descent)
    events = service.persistence.replay_events(descent.id)
    store = AlphaCheckpointStore(tmp_path / "checkpoints", retention=4)
    written = store.write(
        "30a3-test-runtime",
        descent,
        events,
        simulation_config={"protocol": PROTOCOL, "slice": "30A.3"},
        reason="30a3-test",
        created_at_unix_ms=3003001,
    )
    loaded = store.load_latest()
    assert loaded.payload["digest"] == written.payload["digest"]
    assert loaded.crawl.model_dump(mode="json") == descent.model_dump(mode="json")
    assert build_loot_cache_relic_snapshot(loaded.crawl) == expected


def test_snapshot_digest_changes_with_real_loot_state_but_is_stable_for_copy():
    service = LootCacheRelicService()
    descent = service.create(seed=SEED, descender_ids=IDS, stratum_count=3)
    original = build_loot_cache_relic_snapshot(descent)
    clone = deepcopy(descent)
    assert build_loot_cache_relic_snapshot(clone) == original
    service.start(descent)
    cache = _cache(descent)
    _move(service, descent, IDS[0], cache["sector_id"])
    service.open_cache(descent, cache["cache_id"], IDS[0])
    assert build_loot_cache_relic_snapshot(descent)["digest"] != original["digest"]


def test_validator_rejects_blueprint_tampering():
    descent = LootCacheRelicService().create(seed=SEED, descender_ids=IDS, stratum_count=3)
    cache = _cache(descent)
    cache["blueprints"][0]["name"] = "Tampered Item"
    with pytest.raises(LootCacheRelicError, match="digest"):
        validate_loot_cache_relic(descent)


def test_validator_rejects_relic_registry_origin_tampering():
    descent = LootCacheRelicService().create(seed=SEED, descender_ids=IDS, stratum_count=3)
    cache = _cache(descent)
    relic_id = _relic_id(cache)
    descent.modifiers[METADATA_KEY]["relics"][relic_id]["origin_sector_id"] = "not-a-sector"
    with pytest.raises(LootCacheRelicError, match="origin provenance"):
        validate_loot_cache_relic(descent)
