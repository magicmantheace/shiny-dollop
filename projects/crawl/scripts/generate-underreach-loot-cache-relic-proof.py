#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import json
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from livingworld.crawl_persistence import CrawlPersistence  # noqa: E402
from livingworld.runtime_checkpoint import AlphaCheckpointStore, payload_digest  # noqa: E402
from livingworld.underreach_loot_cache_relic import (  # noqa: E402
    METADATA_KEY,
    PROTOCOL,
    LootCacheRelicService,
    build_loot_cache_relic_snapshot,
    validate_loot_cache_relic,
)


PROOF_PROTOCOL = "underreach.loot-cache-relic-proof.v1"
DEFAULT_SEED = "underreach-30a3-loot-cache-relic-proof"


def _route(descent, descender_id: str, target_sector_id: str) -> list[str]:
    participant = descent.participants[descender_id]
    stratum = descent.floors[participant.current_floor]
    start = participant.current_location_id
    if start is None:
        raise RuntimeError("proof Descender has no source Sector")
    parents: dict[str, str | None] = {start: None}
    queue = [start]
    while queue:
        current = queue.pop(0)
        if current == target_sector_id:
            break
        for neighbor in sorted(stratum.locations[current].adjacency):
            if neighbor not in parents:
                parents[neighbor] = current
                queue.append(neighbor)
    if target_sector_id not in parents:
        raise RuntimeError("proof could not route to target Sector")
    result = []
    current: str | None = target_sector_id
    while current is not None:
        result.append(current)
        current = parents[current]
    return list(reversed(result))


def _move(service: LootCacheRelicService, descent, descender_id: str, target_sector_id: str) -> None:
    for sector_id in _route(descent, descender_id, target_sector_id)[1:]:
        service.commit_descender_position(descent, descender_id, sector_id)


def _move_active_to_exit(service: LootCacheRelicService, descent) -> None:
    stratum = descent.floors[descent.current_floor]
    target = sorted(stratum.exit_location_ids)[0]
    for descender_id in sorted(descent.participants):
        participant = descent.participants[descender_id]
        if participant.status.value == "active" and participant.current_floor == descent.current_floor:
            _move(service, descent, descender_id, target)


def _cache(descent, stratum_number: int) -> dict:
    return next(
        cache
        for cache in descent.modifiers[METADATA_KEY]["caches"]
        if cache["stratum_number"] == stratum_number
    )


def _relic_id(cache: dict) -> str:
    return next(item["id"] for item in cache["blueprints"] if item["kind"] == "relic")


def build_proof(seed: str, count: int, strata: int) -> dict:
    if count < 4:
        raise ValueError("30A.3 proof requires at least four Descenders")
    if strata < 3:
        raise ValueError("30A.3 proof requires at least three Strata")
    ids = [f"descender_{index:03d}" for index in range(count)]
    persistence = CrawlPersistence("sqlite://")
    persistence.initialize()
    service = LootCacheRelicService(persistence)

    descent = service.create(seed=seed, descender_ids=reversed(ids), stratum_count=strata)
    created = build_loot_cache_relic_snapshot(descent)
    metadata = descent.modifiers[METADATA_KEY]
    cache1 = _cache(descent, 1)
    relic1 = _relic_id(cache1)

    service.start(descent, tick=5)
    for descender_id in ids[:2]:
        _move(service, descent, descender_id, cache1["sector_id"])
    item_ids = service.open_cache(descent, cache1["cache_id"], ids[0])
    for item_id in item_ids:
        service.claim_ground_item(descent, item_id, ids[0])
    service.drop_owned_item(descent, relic1, ids[0])
    service.claim_ground_item(descent, relic1, ids[1])
    after_reclaim = build_loot_cache_relic_snapshot(descent)

    relic1_provenance_before_transition = list(descent.items[relic1].provenance_event_ids)
    relic1_record = metadata["relics"][relic1]
    if len(relic1_record["acquisition_event_ids"]) != 2:
        raise RuntimeError("proof relic did not acquire a two-owner provenance chain")

    _move_active_to_exit(service, descent)
    service.advance(descent, advance_ticks=2)
    if descent.current_floor != 2:
        raise RuntimeError("proof did not advance to Stratum 2")
    if descent.items[relic1].owner_npc_id != ids[1]:
        raise RuntimeError("owned relic did not survive first Stratum transition")
    if descent.items[relic1].provenance_event_ids != relic1_provenance_before_transition:
        raise RuntimeError("Stratum transition mutated relic provenance")
    after_first_transition = build_loot_cache_relic_snapshot(descent)

    events_at_checkpoint = persistence.replay_events(descent.id)
    with tempfile.TemporaryDirectory(prefix="crawl-30a3-checkpoint-") as directory:
        store = AlphaCheckpointStore(Path(directory) / "checkpoints", retention=4)
        written = store.write(
            "30a3-proof-runtime",
            descent,
            events_at_checkpoint,
            simulation_config={
                "protocol": PROTOCOL,
                "seed": seed,
                "descender_ids": sorted(ids),
                "configured_stratum_count": strata,
            },
            reason="30a3-post-transition-proof",
            created_at_unix_ms=3003001,
        )
        loaded = store.load_latest()
        validate_loot_cache_relic(loaded.crawl)
        checkpoint_snapshot = build_loot_cache_relic_snapshot(loaded.crawl)
        if checkpoint_snapshot != after_first_transition:
            raise RuntimeError("30A.3 checkpoint restore diverged from post-transition loot state")
        checkpoint_digest = written.payload["digest"]
        checkpoint_event_count = loaded.payload["canonical"]["ledger_cursor"]["event_count"]
        checkpoint_stratum_index = loaded.crawl.current_floor - 1

    cache2 = _cache(descent, 2)
    _move(service, descent, ids[1], cache2["sector_id"])
    service.open_cache(descent, cache2["cache_id"], ids[1])
    relic2 = _relic_id(cache2)
    service.claim_ground_item(descent, relic2, ids[1])
    after_second_relic = build_loot_cache_relic_snapshot(descent)

    while descent.current_floor < strata:
        _move_active_to_exit(service, descent)
        service.advance(descent, advance_ticks=1)
    _move_active_to_exit(service, descent)
    service.complete(descent)
    completed = build_loot_cache_relic_snapshot(descent)

    if descent.items[relic1].owner_npc_id != ids[1] or descent.items[relic2].owner_npc_id != ids[1]:
        raise RuntimeError("proof relic ownership did not persist to final completion")
    if descent.participants[ids[1]].current_floor != strata:
        raise RuntimeError("relic owner did not reach final Stratum")

    final_events = persistence.replay_events(descent.id)
    event_types = [event.event_type for event in final_events]
    caches = metadata["caches"]
    relic_ids = sorted(metadata["relics"])
    body = {
        "protocol": PROOF_PROTOCOL,
        "implementation_version": "30a3.1",
        "authoritative": True,
        "presentation_feedback_allowed": False,
        "seed": seed,
        "descent_id": descent.id,
        "population_count": count,
        "configured_stratum_count": strata,
        "cache_count": len(caches),
        "cache_generation_digest": metadata["cache_generation_digest"],
        "relic_blueprint_count": len(relic_ids),
        "relic_ids": relic_ids,
        "first_cache_id": cache1["cache_id"],
        "first_cache_item_count": len(item_ids),
        "first_cache_final_status": cache1["status"],
        "first_relic_id": relic1,
        "first_relic_final_owner": descent.items[relic1].owner_npc_id,
        "first_relic_provenance_event_ids": list(descent.items[relic1].provenance_event_ids),
        "first_relic_acquisition_event_ids": list(metadata["relics"][relic1]["acquisition_event_ids"]),
        "second_relic_id": relic2,
        "second_relic_final_owner": descent.items[relic2].owner_npc_id,
        "created_snapshot_digest": created["digest"],
        "after_reclaim_snapshot_digest": after_reclaim["digest"],
        "after_first_transition_snapshot_digest": after_first_transition["digest"],
        "after_second_relic_snapshot_digest": after_second_relic["digest"],
        "completed_snapshot_digest": completed["digest"],
        "completed_cache_status_counts": {
            "sealed": completed["sealed_cache_count"],
            "opened": completed["opened_cache_count"],
            "depleted": completed["depleted_cache_count"],
        },
        "final_materialized_item_count": completed["materialized_item_count"],
        "final_owned_item_count": completed["owned_item_count"],
        "final_owned_relic_count": completed["owned_relic_count"],
        "final_status": descent.status.value,
        "final_current_stratum_index": descent.current_floor - 1,
        "final_event_count": len(final_events),
        "final_event_ids_digest": payload_digest([event.id for event in final_events]),
        "event_types": event_types,
        "alpha_checkpoint_digest": checkpoint_digest,
        "alpha_checkpoint_event_count": checkpoint_event_count,
        "alpha_checkpoint_stratum_index": checkpoint_stratum_index,
        "alpha_checkpoint_snapshot_digest": checkpoint_snapshot["digest"],
        "authority_contract": {
            "simulation_decides_truth": True,
            "unreal_can_mutate": False,
            "presentation_can_mutate": False,
            "sealed_cache_items_are_not_ground_loot": True,
            "single_holder_item_invariant": True,
            "relic_identity_is_canonical": True,
            "resource_survival_owned_by": "30A.4",
        },
    }
    return {**body, "digest": payload_digest(body)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", default=DEFAULT_SEED)
    parser.add_argument("--count", type=int, default=8)
    parser.add_argument("--strata", type=int, default=4)
    args = parser.parse_args()

    proof = build_proof(args.seed, args.count, args.strata)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"[30A.3] output: {output}")
    print(f"[30A.3] digest: {proof['digest']}")
    print(f"[30A.3] descent: {proof['descent_id']}")
    print(f"[30A.3] population: {proof['population_count']}")
    print(f"[30A.3] strata: {proof['configured_stratum_count']}")
    print(f"[30A.3] caches: {proof['cache_count']}")
    print(f"[30A.3] relics: {proof['relic_blueprint_count']}")
    print(f"[30A.3] final status: {proof['final_status']}")
    print(f"[30A.3] checkpoint digest: {proof['alpha_checkpoint_digest']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
