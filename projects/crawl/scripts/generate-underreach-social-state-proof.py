from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.runtime_checkpoint import AlphaCheckpointStore, canonical_json, payload_digest
from livingworld.underreach_brain_driven_descent import BrainDrivenDescentService
from livingworld.underreach_social_state import (
    METADATA_KEY,
    PROTOCOL,
    SocialStateError,
    SocialStateService,
    build_social_state_snapshot,
    validate_social_state,
)


PROOF_PROTOCOL = "underreach.social-state-proof.v1"


def _stack(seed: str, ids: list[str], strata: int):
    persistence = CrawlPersistence("sqlite://")
    persistence.initialize()
    brain_descent = BrainDrivenDescentService(persistence)
    descent = brain_descent.create(seed=seed, descender_ids=ids, stratum_count=strata)
    social = SocialStateService(persistence)
    social.initialize(descent)
    return persistence, brain_descent, social, descent


def _state_digest(descent) -> str:
    return payload_digest(descent.model_dump(mode="json"))


def _exercise(social: SocialStateService, descent, ids: list[str]) -> list[str]:
    source_event_id = descent.modifiers[METADATA_KEY]["initialized_event_id"]
    event_ids: list[str] = []

    operations = [
        (ids[0], ids[1], "trust", 0.35, "proof.shared_risk", source_event_id),
        (ids[1], ids[0], "respect", 0.2, "proof.observed_skill", None),
        (ids[0], ids[2], "fear", 0.15, "proof.observed_danger", None),
        (ids[2], ids[0], "resentment", 0.25, "proof.resource_dispute", None),
        (ids[3], ids[4], "gratitude", 0.4, "proof.received_help", None),
        (ids[4], ids[3], "familiarity", 0.6, "proof.repeated_contact", None),
    ]
    for source, target, dimension, delta, reason, source_event in operations:
        result = social.adjust_dimension(
            descent,
            source,
            target,
            dimension,
            delta,
            reason_code=reason,
            source_event_id=source_event,
        )
        if not result.changed or not result.ledger_event_id:
            raise RuntimeError("30C.1 proof relationship mutation did not Ledger-bind")
        event_ids.append(result.ledger_event_id)

    before_ensure = len(descent.history_event_ids)
    social.ensure_relationship(
        descent,
        ids[0],
        ids[4],
        reason_code="proof.neutral_contact",
    )
    if len(descent.history_event_ids) != before_ensure + 1:
        raise RuntimeError("30C.1 explicit sparse-edge creation did not append exactly one event")
    event_ids.append(descent.history_event_ids[-1])

    clamp = social.adjust_dimension(
        descent,
        ids[0],
        ids[1],
        "trust",
        2.0,
        reason_code="proof.clamp_upper",
    )
    if not clamp.changed or clamp.resulting_value != 1.0 or not clamp.ledger_event_id:
        raise RuntimeError("30C.1 deterministic upper clamping failed")
    event_ids.append(clamp.ledger_event_id)

    before_noop = _state_digest(descent)
    before_noop_history = list(descent.history_event_ids)
    noop = social.adjust_dimension(
        descent,
        ids[0],
        ids[1],
        "trust",
        0.5,
        reason_code="proof.clamped_noop",
    )
    if noop.changed or noop.ledger_event_id is not None:
        raise RuntimeError("30C.1 clamped no-op unexpectedly mutated relationship state")
    if _state_digest(descent) != before_noop or descent.history_event_ids != before_noop_history:
        raise RuntimeError("30C.1 clamped no-op changed canonical state")

    validate_social_state(descent)
    return event_ids


def generate(output: Path, *, seed: str, count: int, strata: int) -> dict:
    if count < 5:
        raise ValueError("30C.1 proof requires at least five Descenders")
    ids = [f"descender_{index:03d}" for index in range(count)]

    persistence, _, social, descent = _stack(seed, ids, strata)

    before_read = _state_digest(descent)
    before_read_history = list(descent.history_event_ids)
    neutral = social.get(descent, ids[0], ids[1])
    if neutral.trust != 0.0 or neutral.familiarity != 0.0:
        raise RuntimeError("30C.1 absent relationship did not read as neutral")
    if _state_digest(descent) != before_read or descent.history_event_ids != before_read_history:
        raise RuntimeError("30C.1 neutral read allocated canonical social state")

    mutation_event_ids = _exercise(social, descent, ids)
    snapshot = build_social_state_snapshot(descent)

    if social.get(descent, ids[0], ids[1]).trust != 1.0:
        raise RuntimeError("30C.1 forward relationship state is wrong")
    if social.get(descent, ids[1], ids[0]).trust != 0.0:
        raise RuntimeError("30C.1 directed edge independence failed")

    before_invalid = _state_digest(descent)
    before_invalid_history = list(descent.history_event_ids)
    try:
        social.adjust_dimension(
            descent,
            ids[0],
            ids[0],
            "trust",
            0.1,
            reason_code="proof.invalid_self",
        )
    except SocialStateError:
        pass
    else:
        raise RuntimeError("30C.1 self-relationship was not rejected")
    if _state_digest(descent) != before_invalid or descent.history_event_ids != before_invalid_history:
        raise RuntimeError("30C.1 rejected social mutation changed canonical state")

    saved = persistence.load_crawl(descent.id)
    if saved is None or saved.model_dump(mode="json") != descent.model_dump(mode="json"):
        raise RuntimeError("30C.1 persistence round-trip changed canonical social state")
    if build_social_state_snapshot(saved) != snapshot:
        raise RuntimeError("30C.1 persistence round-trip changed social snapshot")

    # Independent identical stack and ordered social operations must converge
    # to the exact same canonical model and digest.
    _, _, twin_social, twin = _stack(seed, ids, strata)
    twin_mutation_event_ids = _exercise(twin_social, twin, ids)
    twin_snapshot = build_social_state_snapshot(twin)
    independent_state_equal = twin.model_dump(mode="json") == descent.model_dump(mode="json")
    if not independent_state_equal or twin_snapshot != snapshot:
        raise RuntimeError("independent 30C.1 social-state reproduction diverged")
    if twin_mutation_event_ids != mutation_event_ids:
        raise RuntimeError("independent 30C.1 social Ledger IDs diverged")

    events = persistence.replay_events(descent.id)
    checkpoint_dir = output.parent / "checkpoint"
    store = AlphaCheckpointStore(checkpoint_dir, retention=4)
    written = store.write(
        "30c1-proof-runtime",
        descent,
        events,
        simulation_config={"protocol": PROTOCOL, "slice": "30C.1"},
        reason="30c1-proof",
        created_at_unix_ms=3003001,
    )
    loaded = store.load_latest().crawl
    checkpoint_state_equal = loaded.model_dump(mode="json") == descent.model_dump(mode="json")
    checkpoint_snapshot_equal = build_social_state_snapshot(loaded) == snapshot
    if not checkpoint_state_equal or not checkpoint_snapshot_equal:
        raise RuntimeError("30C.1 checkpoint restore changed canonical social state")

    event_counts = Counter(event.event_type for event in events)
    metadata = descent.modifiers[METADATA_KEY]
    body = {
        "protocol": PROOF_PROTOCOL,
        "slice_protocol": PROTOCOL,
        "authoritative": True,
        "canonical_owner": "deterministic_simulation",
        "social_reasoning_can_mutate": False,
        "presentation_feedback_allowed": False,
        "sparse_storage": True,
        "seed": seed,
        "descent_id": descent.id,
        "population_count": count,
        "configured_stratum_count": strata,
        "relationship_count": metadata["relationship_count"],
        "mutation_count": metadata["mutation_count"],
        "mutation_event_ids_digest": payload_digest(mutation_event_ids),
        "social_snapshot_digest": snapshot["digest"],
        "relationship_state_digest": snapshot["relationship_state_digest"],
        "canonical_state_digest": _state_digest(descent),
        "canonical_fingerprint": descent.fingerprint(),
        "neutral_read_side_effect_free": True,
        "rejected_mutation_side_effect_free": True,
        "directed_relationships_independent": True,
        "deterministic_clamping": True,
        "independent_state_equal": independent_state_equal,
        "independent_snapshot_equal": twin_snapshot == snapshot,
        "independent_event_ids_equal": twin_mutation_event_ids == mutation_event_ids,
        "persistence_state_equal": saved.model_dump(mode="json") == descent.model_dump(mode="json"),
        "checkpoint_digest": written.payload["digest"],
        "checkpoint_event_count": len(events),
        "checkpoint_state_equal": checkpoint_state_equal,
        "checkpoint_snapshot_equal": checkpoint_snapshot_equal,
        "event_type_counts": dict(sorted(event_counts.items())),
        "authority_contract": {
            "single_canonical_descent_tree": True,
            "relationship_state_is_directed": True,
            "absent_relationship_reads_neutral": True,
            "absent_read_does_not_allocate": True,
            "simulation_owns_social_mutation": True,
            "social_reasoning_can_mutate": False,
            "presentation_can_mutate": False,
            "unreal_can_mutate": False,
            "mutation_is_ledger_bound": True,
            "source_event_provenance_is_structured": True,
            "free_form_dialogue_is_deferred_to_phase31": True,
            "next_slice": "30C.2 — Social Memory & Relationship Evolution",
        },
    }
    proof = {**body, "digest": payload_digest(body)}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(canonical_json(proof) + "\n", encoding="utf-8")
    return proof


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", default="underreach-30c1-social-state-proof")
    parser.add_argument("--count", type=int, default=8)
    parser.add_argument("--strata", type=int, default=3)
    args = parser.parse_args()
    proof = generate(Path(args.output), seed=args.seed, count=args.count, strata=args.strata)
    print(
        f"[30C.1] proof digest={proof['digest']} relationships={proof['relationship_count']} "
        f"mutations={proof['mutation_count']} checkpoint={proof['checkpoint_digest']}"
    )
    print("[30C.1] Deterministic social state proof PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
