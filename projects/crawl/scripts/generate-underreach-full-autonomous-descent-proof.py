#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
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
    restore_resources_survival,
    serialize_resources_survival,
)
from livingworld.underreach_full_autonomous_descent import (  # noqa: E402
    IMPLEMENTATION_VERSION,
    METADATA_KEY,
    PROTOCOL,
    FullAutonomousDescentService,
    build_full_autonomous_snapshot,
    validate_full_autonomous_descent,
)


PROOF_PROTOCOL = "underreach.full-autonomous-descent-proof.v1"
DEFAULT_SEED = "underreach-30a5-full-autonomous-descent-proof"


def _service() -> FullAutonomousDescentService:
    persistence = CrawlPersistence("sqlite://")
    persistence.initialize()
    return FullAutonomousDescentService(persistence)


def _run_complete(seed: str, ids: list[str], strata: int, max_steps: int):
    service = _service()
    descent = service.create(seed=seed, descender_ids=ids, stratum_count=strata)
    result = service.run(descent, max_steps=max_steps)
    if not result.completed:
        raise RuntimeError(
            f"30A.5 autonomous proof did not complete: outcome={result.outcome} "
            f"steps={result.steps_executed} stratum={result.current_stratum_number}"
        )
    validate_full_autonomous_descent(descent)
    return service, descent, result


def _action_counts(descent) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for record in descent.modifiers[METADATA_KEY]["step_records"]:
        for action in record["actions"]:
            counter[action["action"]] += 1
    return dict(sorted(counter.items()))


def build_proof(seed: str, count: int, strata: int, max_steps: int) -> dict:
    if count < 8:
        raise ValueError("30A.5 proof requires at least eight Descenders")
    if strata < 3:
        raise ValueError("30A.5 proof requires at least three Strata")
    ids = [f"descender_{index:03d}" for index in range(count)]

    baseline_service, baseline, baseline_result = _run_complete(seed, ids, strata, max_steps)
    baseline_snapshot = build_full_autonomous_snapshot(baseline)
    baseline_events = baseline_service.persistence.replay_events(baseline.id) if baseline_service.persistence else []

    # Independent exact reproduction.
    repro_service, repro, repro_result = _run_complete(seed, list(reversed(ids)), strata, max_steps)
    repro_snapshot = build_full_autonomous_snapshot(repro)
    if repro_result != baseline_result:
        raise RuntimeError("30A.5 reproduced run result diverged")
    if repro.model_dump(mode="json") != baseline.model_dump(mode="json"):
        raise RuntimeError("30A.5 reproduced canonical state diverged")
    if repro.history_event_ids != baseline.history_event_ids:
        raise RuntimeError("30A.5 reproduced Ledger sequence diverged")
    if repro_snapshot != baseline_snapshot:
        raise RuntimeError("30A.5 reproduced autonomous snapshot diverged")

    # Third run: stop immediately after the first Stratum transition, prove
    # portable restore, write a durable checkpoint, then resume the loaded state.
    resumed_service = _service()
    if resumed_service.persistence is None:
        raise RuntimeError("30A.5 proof requires persistence")
    resumed = resumed_service.create(seed=seed, descender_ids=ids, stratum_count=strata)
    resumed_service.start(resumed)
    checkpoint_step_count = 0
    while resumed.current_floor < 2 and resumed.modifiers[METADATA_KEY]["run_outcome"] == "running":
        if checkpoint_step_count >= max_steps:
            raise RuntimeError("30A.5 proof could not reach Stratum 2 before step limit")
        resumed_service.step(resumed)
        checkpoint_step_count += 1
    if resumed.current_floor != 2 or resumed.modifiers[METADATA_KEY]["run_outcome"] != "running":
        raise RuntimeError("30A.5 checkpoint state was not an active Stratum-2 run")

    checkpoint_snapshot = build_full_autonomous_snapshot(resumed)
    portable = serialize_resources_survival(resumed)
    portable_restored = restore_resources_survival(portable)
    validate_full_autonomous_descent(portable_restored)
    if portable_restored.model_dump(mode="json") != resumed.model_dump(mode="json"):
        raise RuntimeError("30A.5 portable restore diverged at checkpoint state")
    if build_full_autonomous_snapshot(portable_restored) != checkpoint_snapshot:
        raise RuntimeError("30A.5 portable autonomous snapshot diverged")

    checkpoint_events = resumed_service.persistence.replay_events(resumed.id)
    with tempfile.TemporaryDirectory(prefix="crawl-30a5-checkpoint-") as directory:
        store = AlphaCheckpointStore(Path(directory) / "checkpoints", retention=4)
        written = store.write(
            "30a5-proof-runtime",
            resumed,
            checkpoint_events,
            simulation_config={
                "protocol": PROTOCOL,
                "implementation_version": IMPLEMENTATION_VERSION,
                "seed": seed,
                "descender_ids": sorted(ids),
                "stratum_count": strata,
            },
            reason="30a5-proof",
            created_at_unix_ms=3005001,
        )
        loaded = store.load_latest()
        checkpoint_digest = written.payload["digest"]
        checkpoint_event_count = loaded.payload["canonical"]["ledger_cursor"]["event_count"]
        checkpoint_fingerprint = loaded.crawl.fingerprint()
        if loaded.crawl.model_dump(mode="json") != resumed.model_dump(mode="json"):
            raise RuntimeError("30A.5 durable checkpoint restore diverged")
        validate_full_autonomous_descent(loaded.crawl)
        resumed = loaded.crawl

    resumed_result = resumed_service.run(resumed, max_steps=max_steps, start_if_planned=False)
    if not resumed_result.completed:
        raise RuntimeError("30A.5 checkpoint-resumed run did not complete")
    resumed_snapshot = build_full_autonomous_snapshot(resumed)
    if resumed.model_dump(mode="json") != baseline.model_dump(mode="json"):
        raise RuntimeError("30A.5 checkpoint-resumed final canonical state diverged")
    if resumed.history_event_ids != baseline.history_event_ids:
        raise RuntimeError("30A.5 checkpoint-resumed Ledger diverged")
    if resumed_snapshot != baseline_snapshot:
        raise RuntimeError("30A.5 checkpoint-resumed autonomous snapshot diverged")

    metadata = baseline.modifiers[METADATA_KEY]
    metrics = dict(sorted(metadata["metrics"].items()))
    survival = baseline.modifiers["_resources_survival"]
    risk_counts = Counter(state["risk_band"] for state in survival["descenders"].values())
    loot = baseline.modifiers["_loot_cache_relic"]
    cache_states = Counter(cache["status"] for cache in loot["caches"])
    supply_states = Counter(cache["status"] for cache in survival["supply_caches"])
    event_types = Counter(event.event_type for event in baseline_events)

    body = {
        "protocol": PROOF_PROTOCOL,
        "implementation_version": IMPLEMENTATION_VERSION,
        "authoritative": True,
        "presentation_feedback_allowed": False,
        "seed": seed,
        "descent_id": baseline.id,
        "population_count": count,
        "configured_stratum_count": strata,
        "final_status": baseline.status.value,
        "final_outcome": metadata["run_outcome"],
        "final_current_stratum_index": baseline.current_floor - 1,
        "final_tick": baseline.current_tick,
        "step_count": metadata["step_count"],
        "baseline_steps_executed": baseline_result.steps_executed,
        "surviving_descender_count": baseline.surviving_crawler_count,
        "eliminated_descender_count": baseline.eliminated_crawler_count,
        "metrics": metrics,
        "action_counts": _action_counts(baseline),
        "risk_band_counts": dict(sorted(risk_counts.items())),
        "loot_cache_states": dict(sorted(cache_states.items())),
        "survival_supply_cache_states": dict(sorted(supply_states.items())),
        "encounter_count": len(baseline.encounters),
        "event_type_counts": dict(sorted(event_types.items())),
        "final_snapshot_digest": baseline_snapshot["digest"],
        "step_trace_digest": baseline_snapshot["step_trace_digest"],
        "final_canonical_fingerprint": baseline.fingerprint(),
        "final_event_count": len(baseline_events),
        "final_event_ids_digest": payload_digest([event.id for event in baseline_events]),
        "reproduction_snapshot_digest": repro_snapshot["digest"],
        "reproduction_canonical_fingerprint": repro.fingerprint(),
        "checkpoint_snapshot_digest": checkpoint_snapshot["digest"],
        "checkpoint_step_count": checkpoint_step_count,
        "checkpoint_stratum_index": 1,
        "checkpoint_digest": checkpoint_digest,
        "checkpoint_event_count": checkpoint_event_count,
        "checkpoint_canonical_fingerprint": checkpoint_fingerprint,
        "portable_serialization_sha256": sha256(portable.encode("utf-8")).hexdigest(),
        "portable_restored_canonical_fingerprint": portable_restored.fingerprint(),
        "resumed_final_snapshot_digest": resumed_snapshot["digest"],
        "resumed_final_canonical_fingerprint": resumed.fingerprint(),
        "authority_contract": {
            "simulation_decides_truth": True,
            "unreal_can_mutate": False,
            "presentation_can_mutate": False,
            "resource_clock_owned_by_30a4": True,
            "autonomous_policy_is_bounded": True,
            "checkpoint_resume_must_match_uninterrupted": True,
            "next_phase_owned_by": "30B",
        },
    }
    return {**body, "digest": payload_digest(body)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", default=DEFAULT_SEED)
    parser.add_argument("--count", type=int, default=12)
    parser.add_argument("--strata", type=int, default=4)
    parser.add_argument("--max-steps", type=int, default=2500)
    args = parser.parse_args()

    proof = build_proof(args.seed, args.count, args.strata, args.max_steps)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"[30A.5] output: {output}")
    print(f"[30A.5] digest: {proof['digest']}")
    print(f"[30A.5] descent: {proof['descent_id']}")
    print(f"[30A.5] population: {proof['population_count']}")
    print(f"[30A.5] strata: {proof['configured_stratum_count']}")
    print(f"[30A.5] steps: {proof['step_count']}")
    print(f"[30A.5] survivors: {proof['surviving_descender_count']}")
    print(f"[30A.5] checkpoint digest: {proof['checkpoint_digest']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
