from __future__ import annotations

import argparse
import json
from pathlib import Path

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.crawl_service import CrawlLifecycleService
from livingworld.runtime_checkpoint import payload_digest
from livingworld.underreach_brain_driven_descent import BrainDrivenDescentService
from livingworld.underreach_group_social_orchestration import GroupSocialOrchestrationService
from livingworld.underreach_media_event_export import (
    IMPLEMENTATION_VERSION,
    PHASE,
    PROTOCOL,
    CanonicalMediaEventExporter,
    validate_media_envelope,
)
from livingworld.underreach_parties_alliances_leadership import PartiesAlliancesLeadershipService
from livingworld.underreach_rivalry_betrayal_social_conflict import RivalryBetrayalSocialConflictService
from livingworld.underreach_social_intent_execution import SocialIntentExecutionService
from livingworld.underreach_social_memory_evolution import SocialMemoryEvolutionService
from livingworld.underreach_social_state import SocialStateService


PROOF_PROTOCOL = "underreach.media-event-export-proof.v1"


def _stack(seed: str, count: int, strata: int):
    persistence = CrawlPersistence("sqlite://")
    persistence.initialize()
    brain = BrainDrivenDescentService(persistence)
    ids = [f"descender_{index:03d}" for index in range(count)]
    descent = brain.create(seed=seed, descender_ids=ids, stratum_count=strata)
    brain.start(descent)
    memory = SocialMemoryEvolutionService(persistence)
    memory.initialize(descent)
    social = SocialIntentExecutionService(persistence)
    social.initialize(descent)
    parties = PartiesAlliancesLeadershipService(persistence)
    parties.initialize(descent)
    conflict = RivalryBetrayalSocialConflictService(persistence)
    conflict.initialize(descent)
    orchestration = GroupSocialOrchestrationService(persistence, brain=brain)
    orchestration.initialize(descent)
    return persistence, memory, descent, ids


def _record_source(persistence, descent, event_type: str, actors: list[str], marker: str):
    lifecycle = CrawlLifecycleService(persistence)
    return lifecycle.record_event(
        descent,
        event_type,
        f"30.5.1 proof canonical event {marker}.",
        actor_ids=actors,
        location_id=descent.participants[actors[0]].current_location_id,
        data={
            "danger": 0.88 if event_type == "RESCUE" else 0.73,
            "reversal": event_type == "RESCUE",
            "state_changes": {"proof_marker": marker},
            "proof_payload": {"marker": marker, "canonical": True},
        },
    )


def _single_run(seed: str, count: int, strata: int) -> dict:
    persistence, memory, descent, ids = _stack(seed, count, strata)
    social_state = SocialStateService(persistence)
    social_state.adjust_dimension(
        descent,
        ids[1],
        ids[0],
        "trust",
        0.31,
        reason_code="30_5_1.proof_social_basis",
    )

    rescue = _record_source(persistence, descent, "RESCUE", ids[:2], "rescue")
    rescue_processed = memory.process_event(descent, rescue)
    if not rescue_processed.processed:
        raise RuntimeError("30.5.1 proof failed to create canonical rescue memory")

    stolen = _record_source(persistence, descent, "LOOT_STOLEN", [ids[2], ids[0]], "loot_stolen")
    stolen_processed = memory.process_event(descent, stolen)
    if not stolen_processed.processed:
        raise RuntimeError("30.5.1 proof failed to create canonical theft memory")

    exporter = CanonicalMediaEventExporter(persistence)
    state_before = descent.model_dump(mode="json")
    fingerprint_before = descent.fingerprint()
    history_before = list(descent.history_event_ids)
    state_digest_before = payload_digest(state_before)
    ledger_before = [event.model_dump(mode="json") for event in persistence.replay_events(descent.id)]
    ledger_digest_before = payload_digest(ledger_before)

    first = exporter.export_events(descent, [stolen.id, rescue.id])
    second = exporter.export_events(descent, [rescue.id, stolen.id])
    validate_media_envelope(first)
    validate_media_envelope(second)

    state_after = descent.model_dump(mode="json")
    history_after = list(descent.history_event_ids)
    ledger_after = [event.model_dump(mode="json") for event in persistence.replay_events(descent.id)]

    if first != second:
        raise RuntimeError("30.5.1 export is not deterministic under equivalent source-event requests")
    if state_before != state_after:
        raise RuntimeError("30.5.1 export mutated canonical state")
    if fingerprint_before != descent.fingerprint():
        raise RuntimeError("30.5.1 export changed canonical fingerprint")
    if history_before != history_after:
        raise RuntimeError("30.5.1 export changed canonical Ledger history")
    if ledger_before != ledger_after:
        raise RuntimeError("30.5.1 export changed durable Ledger rows")

    fact_predicates = sorted({fact.predicate for fact in first.allowed_facts})
    return {
        "seed": seed,
        "population_count": count,
        "configured_stratum_count": strata,
        "descent_id": descent.id,
        "source_event_ids": list(first.source_event_ids),
        "source_event_types": list(first.source_event_types),
        "source_event_order_normalized": list(first.source_event_ids) == [rescue.id, stolen.id],
        "envelope": first.model_dump(mode="json"),
        "envelope_digest": first.digest,
        "idempotency_key": first.idempotency_key,
        "allowed_fact_count": len(first.allowed_facts),
        "allowed_fact_predicates": fact_predicates,
        "relationship_context_count": len(first.social_context["relationships"]),
        "memory_context_count": len(first.social_context["memories"]),
        "participant_context_count": len(first.participant_context),
        "canonical_fingerprint_before": fingerprint_before,
        "canonical_fingerprint_after": descent.fingerprint(),
        "canonical_state_digest_before": state_digest_before,
        "canonical_state_digest_after": payload_digest(state_after),
        "history_digest_before": payload_digest(history_before),
        "history_digest_after": payload_digest(history_after),
        "ledger_digest_before": ledger_digest_before,
        "ledger_digest_after": payload_digest(ledger_after),
        "ledger_event_count_before": len(ledger_before),
        "ledger_event_count_after": len(ledger_after),
        "repeat_export_equal": first == second,
        "presentation_can_mutate_simulation": first.presentation_can_mutate_simulation,
        "unreal_dependency": first.unreal_dependency,
        "cloud_ai_dependency": first.cloud_ai_dependency,
        "paid_ai_dependency": first.paid_ai_dependency,
    }


def generate(output: Path, seed: str, count: int, strata: int) -> dict:
    run = _single_run(seed, count, strata)
    authority_contract = {
        "simulation_is_authoritative": True,
        "export_is_read_only": True,
        "export_writes_ledger": False,
        "export_writes_canonical_state": False,
        "presentation_can_mutate_simulation": False,
        "unreal_required": False,
        "cloud_ai_required": False,
        "paid_ai_required": False,
        "media_database_in_slice": False,
        "provider_router_in_slice": False,
        "generated_prose_in_slice": False,
        "image_generation_in_slice": False,
        "video_generation_in_slice": False,
        "next_slice": "30.5.2 - Media DB, Durable Queue & Provider Router",
    }
    body = {
        "protocol": PROOF_PROTOCOL,
        "slice_protocol": PROTOCOL,
        "implementation_version": IMPLEMENTATION_VERSION,
        "phase": PHASE,
        "accepted_baseline_sha": "729570fb6b8d517a3976cbc660b55059157f258e",
        "roadmap_commit_sha": "d9a70aef3548352a38f2e612aa1212321e45914d",
        "run": run,
        "authority_contract": authority_contract,
    }
    proof = {**body, "digest": payload_digest(body)}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return proof


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic Underreach 30.5.1 media export proof")
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", default="underreach-30-5-1-media-export-proof")
    parser.add_argument("--count", type=int, default=6)
    parser.add_argument("--strata", type=int, default=3)
    args = parser.parse_args()
    if args.count < 3:
        raise SystemExit("--count must be at least 3")
    if args.strata < 1:
        raise SystemExit("--strata must be at least 1")
    proof = generate(Path(args.output), args.seed, args.count, args.strata)
    print(
        f"[30.5.1] proof digest={proof['digest']} envelope={proof['run']['envelope_digest']} "
        f"facts={proof['run']['allowed_fact_count']} ledger={proof['run']['ledger_event_count_after']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
