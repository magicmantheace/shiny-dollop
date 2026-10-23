#!/usr/bin/env python3
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from livingworld.crawl_persistence import CrawlPersistence  # noqa: E402
from livingworld.runtime_checkpoint import AlphaCheckpointStore, payload_digest  # noqa: E402
from livingworld.underreach_resources_survival import (  # noqa: E402
    IMPLEMENTATION_VERSION,
    METADATA_KEY,
    PROTOCOL,
    ResourcesSurvivalService,
    build_resources_survival_snapshot,
    restore_resources_survival,
    serialize_resources_survival,
    validate_resources_survival,
)


PROOF_PROTOCOL = "underreach.resources-survival-proof.v1"
DEFAULT_SEED = "underreach-30a4-resources-survival-proof"


def _route(descent, descender_id: str, target_sector_id: str) -> list[str]:
    participant = descent.participants[descender_id]
    floor = descent.floors[participant.current_floor]
    start = participant.current_location_id
    if start is None:
        raise RuntimeError("proof Descender has no canonical Sector")
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
    if target_sector_id not in parent:
        raise RuntimeError("proof could not find deterministic Sector route")
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


def _loot_cache(descent, stratum_number: int) -> dict:
    return next(
        cache
        for cache in descent.modifiers["_loot_cache_relic"]["caches"]
        if cache["stratum_number"] == stratum_number
    )


def _supply_cache(descent, stratum_number: int) -> dict:
    return next(
        cache
        for cache in descent.modifiers[METADATA_KEY]["supply_caches"]
        if cache["stratum_number"] == stratum_number
    )


def _supply_id(cache: dict, kind: str) -> str:
    return next(bp["id"] for bp in cache["blueprints"] if bp["resource_kind"] == kind)


def build_proof(seed: str, count: int, strata: int) -> dict:
    if count < 4:
        raise ValueError("30A.4 proof requires at least four Descenders")
    if strata < 3:
        raise ValueError("30A.4 proof requires at least three Strata")
    ids = [f"descender_{index:03d}" for index in range(count)]
    persistence = CrawlPersistence("sqlite://")
    persistence.initialize()
    service = ResourcesSurvivalService(persistence)

    descent = service.create(seed=seed, descender_ids=reversed(ids), stratum_count=strata)
    planned = build_resources_survival_snapshot(descent)
    service.start(descent, tick=5)
    active = build_resources_survival_snapshot(descent)

    # Establish meaningful pressure before the first cache is reached.
    service.advance_time(descent, 30)
    pressure = build_resources_survival_snapshot(descent)
    pressure_health_damage_count = sum(
        state["total_health_damage"] > 0
        for state in descent.modifiers[METADATA_KEY]["descenders"].values()
    )

    # Open Stratum 1 cache. One Descender drinks immediately; another carries a
    # ration across the first Stratum transition for checkpoint proof.
    first_cache = _loot_cache(descent, 1)
    for descender_id in ids[:2]:
        _move(service, descent, descender_id, first_cache["sector_id"])
    service.open_cache(descent, first_cache["cache_id"], ids[0])
    first_supply = _supply_cache(descent, 1)
    water_id = _supply_id(first_supply, "hydration")
    ration_id = _supply_id(first_supply, "nutrition")
    service.claim_supply_item(descent, water_id, ids[0])
    water_before = descent.modifiers[METADATA_KEY]["descenders"][ids[0]]["hydration"]
    water_result = service.consume_supply_item(descent, water_id, ids[0])
    service.claim_supply_item(descent, ration_id, ids[1])

    # Prove safe recovery uses the existing stamina field rather than a duplicate.
    # Pick the most depleted active Descender deterministically so the proof never
    # depends on a particular ID crossing the warning threshold for this seed.
    recovery_id = min(
        ids,
        key=lambda descender_id: (descent.participants[descender_id].gameplay.stamina, descender_id),
    )
    safe_id = sorted(descent.floors[1].safe_area_ids)[0]
    _move(service, descent, recovery_id, safe_id)
    stamina_before_recovery = descent.participants[recovery_id].gameplay.stamina
    if stamina_before_recovery >= 1.0:
        raise RuntimeError("30A.4 pressure window did not create recoverable stamina loss")
    recovery = service.recover_at_safe_area(descent, recovery_id)

    _move_active_to_exit(service, descent)
    service.advance(descent, advance_ticks=2)
    after_first_transition = build_resources_survival_snapshot(descent)
    if descent.current_floor != 2 or descent.items[ration_id].owner_npc_id != ids[1]:
        raise RuntimeError("30A.4 carried supply did not survive first Stratum transition")

    portable = serialize_resources_survival(descent)
    portable_restored = restore_resources_survival(portable)
    if portable_restored.model_dump(mode="json") != descent.model_dump(mode="json"):
        raise RuntimeError("30A.4 portable restore diverged")

    checkpoint_events = persistence.replay_events(descent.id)
    with tempfile.TemporaryDirectory(prefix="crawl-30a4-checkpoint-") as directory:
        store = AlphaCheckpointStore(Path(directory) / "checkpoints", retention=4)
        written = store.write(
            "30a4-proof-runtime",
            descent,
            checkpoint_events,
            simulation_config={
                "protocol": PROTOCOL,
                "implementation_version": IMPLEMENTATION_VERSION,
                "seed": seed,
                "descender_ids": sorted(ids),
                "stratum_count": strata,
            },
            reason="30a4-proof",
            created_at_unix_ms=3004001,
        )
        loaded = store.load_latest()
        checkpoint_digest = written.payload["digest"]
        checkpoint_fingerprint = loaded.crawl.fingerprint()
        checkpoint_event_count = loaded.payload["canonical"]["ledger_cursor"]["event_count"]
        checkpoint_stratum_index = loaded.crawl.current_floor - 1
        if loaded.crawl.model_dump(mode="json") != descent.model_dump(mode="json"):
            raise RuntimeError("30A.4 durable checkpoint restore diverged")
        validate_resources_survival(loaded.crawl)

    # Consume the carried ration after checkpoint and open Stratum 2 supplies.
    ration_before = descent.modifiers[METADATA_KEY]["descenders"][ids[1]]["nutrition"]
    ration_result = service.consume_supply_item(descent, ration_id, ids[1])
    second_cache = _loot_cache(descent, 2)
    _move(service, descent, ids[2], second_cache["sector_id"])
    service.open_cache(descent, second_cache["cache_id"], ids[2])
    second_supply = _supply_cache(descent, 2)
    second_water_id = _supply_id(second_supply, "hydration")
    service.claim_supply_item(descent, second_water_id, ids[2])

    # Apply another pressure window to prove critical resource/health coupling.
    service.advance_time(descent, descent.current_tick + 25)
    second_pressure = build_resources_survival_snapshot(descent)
    final_health_pressure_count = sum(
        state["total_health_damage"] > 0
        for state in descent.modifiers[METADATA_KEY]["descenders"].values()
    )

    # Finish the remaining deterministic Strata without inventing autonomous
    # resource choices; 30A.5 will own that orchestration.
    transition_snapshot_digests = [after_first_transition["digest"]]
    while descent.current_floor < strata:
        _move_active_to_exit(service, descent)
        service.advance(descent, advance_ticks=1)
        transition_snapshot_digests.append(build_resources_survival_snapshot(descent)["digest"])
    _move_active_to_exit(service, descent)
    service.complete(descent, advance_ticks=1)
    completed = build_resources_survival_snapshot(descent)

    final_events = persistence.replay_events(descent.id)
    event_types = [event.event_type for event in final_events]
    body = {
        "protocol": PROOF_PROTOCOL,
        "implementation_version": IMPLEMENTATION_VERSION,
        "authoritative": True,
        "presentation_feedback_allowed": False,
        "seed": seed,
        "descent_id": descent.id,
        "population_count": count,
        "configured_stratum_count": strata,
        "supply_cache_count": completed["supply_cache_count"],
        "planned_snapshot_digest": planned["digest"],
        "active_snapshot_digest": active["digest"],
        "pressure_snapshot_digest": pressure["digest"],
        "second_pressure_snapshot_digest": second_pressure["digest"],
        "transition_snapshot_digests": transition_snapshot_digests,
        "completed_snapshot_digest": completed["digest"],
        "pressure_risk_band_counts": pressure["risk_band_counts"],
        "second_pressure_risk_band_counts": second_pressure["risk_band_counts"],
        "pressure_health_damage_count": pressure_health_damage_count,
        "final_health_pressure_count": final_health_pressure_count,
        "water_resource_before": round(water_before, 6),
        "water_resource_after": water_result["after"],
        "ration_resource_before": round(ration_before, 6),
        "ration_resource_after": ration_result["after"],
        "safe_recovery_descender_id": recovery_id,
        "safe_recovery_stamina_before": stamina_before_recovery,
        "safe_recovery_stamina_after": recovery["after"],
        "carried_supply_item_id": ration_id,
        "post_checkpoint_live_supply_item_id": second_water_id,
        "portable_serialization_sha256": sha256(portable.encode("utf-8")).hexdigest(),
        "portable_restored_fingerprint": portable_restored.fingerprint(),
        "alpha_checkpoint_digest": checkpoint_digest,
        "alpha_checkpoint_restored_fingerprint": checkpoint_fingerprint,
        "alpha_checkpoint_event_count": checkpoint_event_count,
        "alpha_checkpoint_stratum_index": checkpoint_stratum_index,
        "final_status": descent.status.value,
        "final_current_stratum_index": descent.current_floor - 1,
        "revealed_supply_cache_count": completed["revealed_supply_cache_count"],
        "depleted_supply_cache_count": completed["depleted_supply_cache_count"],
        "materialized_supply_count": completed["materialized_supply_count"],
        "claimed_supply_count": completed["claimed_supply_count"],
        "consumed_supply_count": completed["consumed_supply_count"],
        "final_risk_band_counts": completed["risk_band_counts"],
        "survival_state_digest": completed["survival_state_digest"],
        "final_canonical_fingerprint": descent.fingerprint(),
        "final_event_count": len(final_events),
        "final_event_ids_digest": payload_digest([event.id for event in final_events]),
        "event_types": event_types,
        "authority_contract": {
            "simulation_decides_truth": True,
            "unreal_can_mutate": False,
            "presentation_can_mutate": False,
            "hydration_nutrition_are_canonical": True,
            "stamina_reuses_existing_gameplay_state": True,
            "autonomous_survival_choices_owned_by": "30A.5",
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

    print(f"[30A.4] output: {output}")
    print(f"[30A.4] digest: {proof['digest']}")
    print(f"[30A.4] descent: {proof['descent_id']}")
    print(f"[30A.4] population: {proof['population_count']}")
    print(f"[30A.4] strata: {proof['configured_stratum_count']}")
    print(f"[30A.4] supply caches: {proof['supply_cache_count']}")
    print(f"[30A.4] final status: {proof['final_status']}")
    print(f"[30A.4] checkpoint digest: {proof['alpha_checkpoint_digest']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
