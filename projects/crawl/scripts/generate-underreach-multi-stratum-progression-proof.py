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

from livingworld.crawl_domain import ParticipationStatus  # noqa: E402
from livingworld.crawl_persistence import CrawlPersistence  # noqa: E402
from livingworld.runtime_checkpoint import AlphaCheckpointStore, ledger_digest, payload_digest  # noqa: E402
from livingworld.underreach_multi_stratum_progression import (  # noqa: E402
    IMPLEMENTATION_VERSION,
    PROTOCOL,
    MultiStratumProgressionService,
    build_multi_stratum_snapshot,
    restore_multi_stratum_descent,
    serialize_multi_stratum_descent,
    validate_multi_stratum_descent,
)


PROOF_PROTOCOL = "underreach.multi-stratum-progression-proof.v1"
DEFAULT_SEED = "underreach-30a2-multi-stratum-progression-proof"


def _route(descent, descender_id: str) -> list[str]:
    stratum = descent.floors[descent.current_floor]
    start = descent.participants[descender_id].current_location_id
    if start is None:
        raise RuntimeError("proof Descender has no canonical Sector")
    exits = set(stratum.exit_location_ids)
    parents: dict[str, str | None] = {start: None}
    queue = [start]
    end = None
    while queue:
        current = queue.pop(0)
        if current in exits:
            end = current
            break
        for neighbor in sorted(stratum.locations[current].adjacency):
            if neighbor not in parents:
                parents[neighbor] = current
                queue.append(neighbor)
    if end is None:
        raise RuntimeError("proof Stratum has no advancement route")
    result = []
    current: str | None = end
    while current is not None:
        result.append(current)
        current = parents[current]
    return list(reversed(result))


def _move_active_to_exit(service: MultiStratumProgressionService, descent) -> int:
    movement_count = 0
    for descender_id in sorted(descent.participants):
        participant = descent.participants[descender_id]
        if participant.status != ParticipationStatus.ACTIVE or participant.current_floor != descent.current_floor:
            continue
        for sector_id in _route(descent, descender_id)[1:]:
            service.commit_descender_position(descent, descender_id, sector_id)
            movement_count += 1
    return movement_count


def build_proof(seed: str, count: int, stratum_count: int) -> dict:
    if count < 4:
        raise ValueError("30A.2 proof requires at least four Descenders")
    if stratum_count < 3:
        raise ValueError("30A.2 proof requires at least three Strata")
    ids = [f"descender_{index:03d}" for index in range(count)]
    persistence = CrawlPersistence("sqlite://")
    persistence.initialize()
    service = MultiStratumProgressionService(persistence)

    descent = service.create(seed=seed, descender_ids=reversed(ids), stratum_count=stratum_count)
    planned = build_multi_stratum_snapshot(descent)
    service.start(descent, tick=10)
    active = build_multi_stratum_snapshot(descent)

    eliminated_id = sorted(ids)[-1]
    eliminated_origin = descent.participants[eliminated_id].current_location_id
    service.eliminate(
        descent,
        eliminated_id,
        summary="30A.2 proof elimination before first Stratum advancement.",
    )

    movement_counts = []
    transition_snapshots = []
    transition_records = []

    movement_counts.append(_move_active_to_exit(service, descent))
    service.advance(descent, advance_ticks=2)
    first_transition = build_multi_stratum_snapshot(descent)
    transition_snapshots.append(first_transition["digest"])
    transition_records.append(dict(first_transition["transitions"][-1]))

    eliminated = descent.participants[eliminated_id]
    if eliminated.status != ParticipationStatus.ELIMINATED:
        raise RuntimeError("proof eliminated Descender unexpectedly changed status")
    if eliminated.current_floor != 1 or eliminated.current_location_id != eliminated_origin:
        raise RuntimeError("proof eliminated Descender incorrectly advanced")
    survivors = sorted(ids[:-1])
    next_entrance = descent.floors[2].entrance_location_id
    for descender_id in survivors:
        participant = descent.participants[descender_id]
        if participant.status != ParticipationStatus.ACTIVE:
            raise RuntimeError("proof survivor failed to reactivate")
        if participant.current_floor != 2 or participant.current_location_id != next_entrance:
            raise RuntimeError("proof survivor failed to arrive at Stratum 2 entrance")

    events_at_checkpoint = persistence.replay_events(descent.id)
    with tempfile.TemporaryDirectory(prefix="crawl-30a2-checkpoint-") as directory:
        store = AlphaCheckpointStore(Path(directory) / "checkpoints", retention=4)
        written = store.write(
            "30a2-proof-runtime",
            descent,
            events_at_checkpoint,
            simulation_config={
                "protocol": PROTOCOL,
                "implementation_version": IMPLEMENTATION_VERSION,
                "seed": seed,
                "descender_ids": sorted(ids),
                "configured_stratum_count": stratum_count,
            },
            reason="30a2-post-first-transition",
            created_at_unix_ms=3002001,
        )
        loaded = store.load_latest()
        validate_multi_stratum_descent(loaded.crawl)
        if loaded.crawl.model_dump(mode="json") != descent.model_dump(mode="json"):
            raise RuntimeError("30A.2 checkpoint restore diverged after transition")
        checkpoint_digest = written.payload["digest"]
        checkpoint_fingerprint = loaded.crawl.fingerprint()
        checkpoint_event_count = loaded.payload["canonical"]["ledger_cursor"]["event_count"]
        checkpoint_ledger_digest = loaded.payload["canonical"]["ledger_cursor"]["ledger_digest"]
        checkpoint_stratum_index = loaded.crawl.current_floor - 1

    portable = serialize_multi_stratum_descent(descent)
    portable_restored = restore_multi_stratum_descent(portable)
    if portable_restored.model_dump(mode="json") != descent.model_dump(mode="json"):
        raise RuntimeError("30A.2 portable restore diverged after transition")

    while descent.current_floor < stratum_count:
        movement_counts.append(_move_active_to_exit(service, descent))
        service.advance(descent, advance_ticks=1)
        snapshot = build_multi_stratum_snapshot(descent)
        transition_snapshots.append(snapshot["digest"])
        transition_records.append(dict(snapshot["transitions"][-1]))

    final_active = build_multi_stratum_snapshot(descent)
    movement_counts.append(_move_active_to_exit(service, descent))
    service.complete(descent, advance_ticks=1)
    completed = build_multi_stratum_snapshot(descent)

    final_events = persistence.replay_events(descent.id)
    transitions = completed["transitions"]
    expected_pairs = [[number, number + 1] for number in range(1, stratum_count)]
    actual_pairs = [[item["from_stratum_number"], item["to_stratum_number"]] for item in transitions]
    if actual_pairs != expected_pairs:
        raise RuntimeError("30A.2 transition sequence diverged")

    body = {
        "protocol": PROOF_PROTOCOL,
        "implementation_version": IMPLEMENTATION_VERSION,
        "authoritative": True,
        "presentation_feedback_allowed": False,
        "seed": seed,
        "descent_id": descent.id,
        "ordered_descender_ids": sorted(ids),
        "roster_digest": completed["roster_digest"],
        "population_count": count,
        "configured_stratum_count": stratum_count,
        "completed_stratum_count": completed["completed_stratum_count"],
        "transition_count": len(transitions),
        "transition_pairs": actual_pairs,
        "transition_digests": [item["digest"] for item in transitions],
        "transition_ledger_event_ids": [item["ledger_event_id"] for item in transitions],
        "transition_history_digest": completed["transition_history_digest"],
        "transition_snapshot_digests": transition_snapshots,
        "planned_snapshot_digest": planned["digest"],
        "active_snapshot_digest": active["digest"],
        "final_stratum_active_snapshot_digest": final_active["digest"],
        "completed_snapshot_digest": completed["digest"],
        "eliminated_descender_id": eliminated_id,
        "eliminated_descender_stratum_number": descent.participants[eliminated_id].current_floor,
        "survivor_descender_ids": survivors,
        "survivor_count": len(survivors),
        "final_surviving_descender_count": descent.surviving_crawler_count,
        "final_eliminated_descender_count": descent.eliminated_crawler_count,
        "movement_counts_by_stage": movement_counts,
        "portable_serialization_sha256": sha256(portable.encode("utf-8")).hexdigest(),
        "portable_restored_fingerprint": portable_restored.fingerprint(),
        "alpha_checkpoint_digest": checkpoint_digest,
        "alpha_checkpoint_restored_fingerprint": checkpoint_fingerprint,
        "alpha_checkpoint_event_count": checkpoint_event_count,
        "alpha_checkpoint_ledger_digest": checkpoint_ledger_digest,
        "alpha_checkpoint_stratum_index": checkpoint_stratum_index,
        "final_status": descent.status.value,
        "final_current_stratum_index": completed["current_stratum_index"],
        "final_canonical_fingerprint": descent.fingerprint(),
        "final_event_count": len(final_events),
        "final_event_ids_digest": payload_digest([event.id for event in final_events]),
        "final_ledger_digest": ledger_digest(final_events),
        "strata": completed["strata"],
        "authority_contract": {
            "simulation_decides_truth": True,
            "unreal_can_mutate": False,
            "presentation_can_mutate": False,
            "progression_is_sequential": True,
            "survivors_only_advance": True,
            "loot_owned_by": "30A.3",
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

    print(f"[30A.2] output: {output}")
    print(f"[30A.2] digest: {proof['digest']}")
    print(f"[30A.2] descent: {proof['descent_id']}")
    print(f"[30A.2] population: {proof['population_count']}")
    print(f"[30A.2] strata: {proof['configured_stratum_count']}")
    print(f"[30A.2] transitions: {proof['transition_count']}")
    print(f"[30A.2] survivors: {proof['survivor_count']}")
    print(f"[30A.2] final status: {proof['final_status']}")
    print(f"[30A.2] final events: {proof['final_event_count']}")
    print(f"[30A.2] checkpoint digest: {proof['alpha_checkpoint_digest']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
