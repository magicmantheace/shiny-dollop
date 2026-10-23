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
from livingworld.runtime_checkpoint import AlphaCheckpointStore, payload_digest  # noqa: E402
from livingworld.underreach_descent_run_state import (  # noqa: E402
    IMPLEMENTATION_VERSION,
    PROTOCOL,
    DescentRunStateService,
    build_descent_run_snapshot,
    restore_descent_run,
    serialize_descent_run,
    validate_descent_run,
)


PROOF_PROTOCOL = "underreach.descent-run-state-proof.v1"
DEFAULT_SEED = "underreach-30a1-descent-run-state-proof"


def _route(descent, descender_id: str) -> list[str]:
    stratum = descent.floors[descent.current_floor]
    start = descent.participants[descender_id].current_location_id
    if start is None:
        raise RuntimeError("proof Descender has no source Sector")
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
        raise RuntimeError("proof Stratum has no route to an exit")
    result = []
    current: str | None = end
    while current is not None:
        result.append(current)
        current = parents[current]
    return list(reversed(result))


def build_proof(seed: str, count: int) -> dict:
    if count < 4:
        raise ValueError("30A.1 proof requires at least four Descenders")
    ids = [f"descender_{index:03d}" for index in range(count)]
    persistence = CrawlPersistence("sqlite://")
    persistence.initialize()
    service = DescentRunStateService(persistence)

    descent = service.create(seed=seed, descender_ids=reversed(ids))
    planned = build_descent_run_snapshot(descent)

    service.start(descent, tick=5)
    active = build_descent_run_snapshot(descent)

    first_id = sorted(descent.participants)[0]
    first_route = _route(descent, first_id)
    if len(first_route) < 2:
        raise RuntimeError("30A.1 proof route did not contain a traversal edge")
    service.commit_descender_position(descent, first_id, first_route[1])
    service.set_tick(descent, 6)
    moved = build_descent_run_snapshot(descent)

    portable = serialize_descent_run(descent)
    portable_restored = restore_descent_run(portable)
    if portable_restored.model_dump(mode="json") != descent.model_dump(mode="json"):
        raise RuntimeError("30A.1 portable serialization restore diverged")

    events_at_checkpoint = persistence.replay_events(descent.id)
    with tempfile.TemporaryDirectory(prefix="crawl-30a1-checkpoint-") as directory:
        store = AlphaCheckpointStore(Path(directory) / "checkpoints", retention=4)
        written = store.write(
            "30a1-proof-runtime",
            descent,
            events_at_checkpoint,
            simulation_config={
                "protocol": PROTOCOL,
                "implementation_version": IMPLEMENTATION_VERSION,
                "seed": seed,
                "descender_ids": sorted(ids),
                "initialized_stratum_count": 1,
            },
            reason="30a1-proof",
            created_at_unix_ms=3001001,
        )
        loaded = store.load_latest()
        checkpoint_digest = written.payload["digest"]
        checkpoint_fingerprint = loaded.crawl.fingerprint()
        checkpoint_event_count = loaded.payload["canonical"]["ledger_cursor"]["event_count"]
        if loaded.crawl.model_dump(mode="json") != descent.model_dump(mode="json"):
            raise RuntimeError("30A.1 durable checkpoint restore diverged")
        validate_descent_run(loaded.crawl)

    for descender_id in sorted(descent.participants):
        participant = descent.participants[descender_id]
        if participant.status != ParticipationStatus.ACTIVE:
            continue
        for sector_id in _route(descent, descender_id)[1:]:
            service.commit_descender_position(descent, descender_id, sector_id)
    service.set_tick(descent, 7)
    service.complete(descent)
    completed = build_descent_run_snapshot(descent)

    final_events = persistence.replay_events(descent.id)
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
        "initialized_stratum_count": len(descent.floors),
        "current_stratum_index": completed["current_stratum_index"],
        "multi_stratum_progression_enabled": completed["multi_stratum_progression_enabled"],
        "planned_snapshot_digest": planned["digest"],
        "active_snapshot_digest": active["digest"],
        "moved_snapshot_digest": moved["digest"],
        "completed_snapshot_digest": completed["digest"],
        "portable_serialization_sha256": sha256(portable.encode("utf-8")).hexdigest(),
        "portable_restored_fingerprint": portable_restored.fingerprint(),
        "alpha_checkpoint_digest": checkpoint_digest,
        "alpha_checkpoint_restored_fingerprint": checkpoint_fingerprint,
        "alpha_checkpoint_event_count": checkpoint_event_count,
        "final_canonical_fingerprint": descent.fingerprint(),
        "final_status": descent.status.value,
        "final_event_count": len(final_events),
        "final_event_ids_digest": payload_digest([event.id for event in final_events]),
        "event_types": [event.event_type for event in final_events],
        "authority_contract": {
            "simulation_decides_truth": True,
            "unreal_can_mutate": False,
            "presentation_can_mutate": False,
            "multi_stratum_advancement_owned_by": "30A.2",
        },
    }
    return {**body, "digest": payload_digest(body)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", default=DEFAULT_SEED)
    parser.add_argument("--count", type=int, default=8)
    args = parser.parse_args()

    proof = build_proof(args.seed, args.count)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"[30A.1] output: {output}")
    print(f"[30A.1] digest: {proof['digest']}")
    print(f"[30A.1] descent: {proof['descent_id']}")
    print(f"[30A.1] population: {proof['population_count']}")
    print(f"[30A.1] final status: {proof['final_status']}")
    print(f"[30A.1] final events: {proof['final_event_count']}")
    print(f"[30A.1] checkpoint digest: {proof['alpha_checkpoint_digest']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
