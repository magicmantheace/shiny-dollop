from __future__ import annotations

import argparse
import json
from pathlib import Path

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.crawl_service import CrawlLifecycleService
from livingworld.runtime_checkpoint import canonical_json, payload_digest
from livingworld.underreach_brain_driven_descent import BrainDrivenDescentService
from livingworld.underreach_delver_chronicle_profile import DelverChronicleProfileService
from livingworld.underreach_group_social_orchestration import GroupSocialOrchestrationService
from livingworld.underreach_highlight_story_arc import HighlightStoryArcService
from livingworld.underreach_media_event_export import CanonicalMediaEventExporter
from livingworld.underreach_media_foundation import MediaPersistence
from livingworld.underreach_narrative_claim_verification import (
    AssessmentClassification,
    AuxiliaryAssessment,
    ClaimSpec,
    ClaimType,
    NarrativeClaimVerificationService,
)
from livingworld.underreach_parties_alliances_leadership import PartiesAlliancesLeadershipService
from livingworld.underreach_rivalry_betrayal_social_conflict import RivalryBetrayalSocialConflictService
from livingworld.underreach_social_intent_execution import SocialIntentExecutionService
from livingworld.underreach_social_memory_evolution import SocialMemoryEvolutionService


PROOF_PROTOCOL = "underreach.narrative-claim-verification-proof.v1"


def _canonical_stack(seed: str):
    canonical = CrawlPersistence("sqlite://")
    canonical.initialize()
    brain = BrainDrivenDescentService(canonical)
    ids = [f"descender_{index:03d}" for index in range(6)]
    descent = brain.create(seed=seed, descender_ids=ids, stratum_count=3)
    brain.start(descent)
    memory = SocialMemoryEvolutionService(canonical)
    memory.initialize(descent)
    SocialIntentExecutionService(canonical).initialize(descent)
    PartiesAlliancesLeadershipService(canonical).initialize(descent)
    RivalryBetrayalSocialConflictService(canonical).initialize(descent)
    GroupSocialOrchestrationService(canonical, brain=brain).initialize(descent)
    lifecycle = CrawlLifecycleService(canonical)
    prior = lifecycle.record_event(
        descent,
        "BETRAYAL",
        "30.5.5 proof prior canonical event.",
        actor_ids=ids[:2],
        location_id=descent.participants[ids[0]].current_location_id,
        data={"danger": 0.6, "state_changes": {"prior": True}},
    )
    if not memory.process_event(descent, prior).processed:
        raise RuntimeError("30.5.5 proof failed prior social memory")
    event = lifecycle.record_event(
        descent,
        "NEAR_DEATH_BETRAYAL_RELIC_COMEBACK",
        "30.5.5 canonical narrative proof source.",
        actor_ids=ids[:2],
        location_id=descent.participants[ids[0]].current_location_id,
        data={
            "danger": 1.0,
            "state_changes": {"30_5_5": True},
            "social_facts": [
                {
                    "observer_descender_id": ids[1],
                    "subject_descender_id": ids[0],
                    "memory_type": "betrayed",
                }
            ],
        },
    )
    if not memory.process_event(descent, event).processed:
        raise RuntimeError("30.5.5 proof failed current social memory")
    envelope = CanonicalMediaEventExporter(canonical).export_event(descent, event.id)
    return canonical, descent, ids, event, envelope


def generate(output: Path, *, seed: str) -> dict:
    output.parent.mkdir(parents=True, exist_ok=True)
    database_path = output.with_suffix(".sqlite3")
    if database_path.exists():
        database_path.unlink()

    canonical, descent, ids, event, envelope = _canonical_stack(seed)
    canonical_before = descent.model_dump(mode="json")
    fingerprint_before = descent.fingerprint()
    history_before = list(descent.history_event_ids)
    ledger_before = [item.model_dump(mode="json") for item in canonical.replay_events(descent.id)]

    database_url = f"sqlite:///{database_path.as_posix()}"
    media = MediaPersistence(database_url)
    media.initialize()
    media.register_envelope(envelope)
    detector = HighlightStoryArcService(media)
    detector.initialize()
    evaluation = detector.evaluate(envelope)
    if not evaluation.selected:
        raise RuntimeError("30.5.5 proof source failed accepted highlight gate")
    chronicle = DelverChronicleProfileService(media, highlights=detector)
    chronicle.initialize()
    chronicle.process(envelope)
    chapter = chronicle.list_chapters(delver_id=ids[0])[0]
    facts = {fact.predicate: fact for fact in envelope.allowed_facts if fact.fact_id in chapter.allowed_fact_ids}
    event_type = facts["event_type"]
    stratum = facts["stratum"]

    verifier = NarrativeClaimVerificationService(media, chronicle=chronicle)
    verifier.initialize()

    valid_draft = verifier.register_draft(
        chapter_id=chapter.chapter_id,
        prose="The recorded event was NEAR_DEATH_BETRAYAL_RELIC_COMEBACK. The silence felt heavier afterward.",
        writer_provider_id="local_qwen_proof",
        writer_provider_local=True,
        writer_provider_paid=False,
    )
    valid_manifest = verifier.register_manifest(
        draft_id=valid_draft.draft_id,
        claim_specs=[
            ClaimSpec(
                claim_type=ClaimType.FACTUAL,
                sentence_index=0,
                subject=event.id,
                predicate="event_type",
                target_or_value=event_type.value,
                supporting_allowed_fact_ids=(event_type.fact_id,),
            ),
            ClaimSpec(claim_type=ClaimType.STYLISTIC, sentence_index=1),
        ],
    )
    valid_result = verifier.verify(valid_manifest.manifest_id)

    wrong_stratum = 99 if stratum.value != 99 else 98
    wrong_draft = verifier.register_draft(
        chapter_id=chapter.chapter_id,
        prose=f"The event occurred on Stratum {wrong_stratum}.",
    )
    wrong_manifest = verifier.register_manifest(
        draft_id=wrong_draft.draft_id,
        claim_specs=[
            ClaimSpec(
                claim_type=ClaimType.FACTUAL,
                sentence_index=0,
                subject=event.id,
                predicate="stratum",
                target_or_value=wrong_stratum,
                supporting_allowed_fact_ids=(stratum.fact_id,),
            )
        ],
        auxiliary_assessments=[
            AuxiliaryAssessment(
                sentence_index=0,
                classification=AssessmentClassification.STYLISTIC,
                provider_id="local_small_classifier",
                provider_local=True,
                provider_paid=False,
                reason_code="cannot_override_wrong_stratum",
            )
        ],
    )
    wrong_result = verifier.verify(wrong_manifest.manifest_id)

    style_draft = verifier.register_draft(
        chapter_id=chapter.chapter_id,
        prose="He died alone in Sector alpha.",
    )
    style_manifest = verifier.register_manifest(
        draft_id=style_draft.draft_id,
        claim_specs=[ClaimSpec(claim_type=ClaimType.STYLISTIC, sentence_index=0)],
    )
    style_result = verifier.verify(style_manifest.manifest_id)

    ambiguous_draft = verifier.register_draft(
        chapter_id=chapter.chapter_id,
        prose="The recorded event was NEAR_DEATH_BETRAYAL_RELIC_COMEBACK.",
        writer_provider_id="local_qwen_proof",
        writer_provider_local=True,
        writer_provider_paid=False,
    )
    ambiguous_manifest = verifier.register_manifest(
        draft_id=ambiguous_draft.draft_id,
        claim_specs=[
            ClaimSpec(
                claim_type=ClaimType.FACTUAL,
                sentence_index=0,
                subject=event.id,
                predicate="event_type",
                target_or_value=event_type.value,
                supporting_allowed_fact_ids=(event_type.fact_id,),
            )
        ],
        auxiliary_assessments=[
            AuxiliaryAssessment(
                sentence_index=0,
                classification=AssessmentClassification.AMBIGUOUS,
                provider_id="local_small_classifier",
                provider_local=True,
                provider_paid=False,
                reason_code="proof_ambiguity",
            )
        ],
    )
    ambiguous_result = verifier.verify(ambiguous_manifest.manifest_id)

    snapshot = verifier.snapshot()
    media_snapshot = media.snapshot()

    reopened_media = MediaPersistence(database_url)
    reopened_media.initialize()
    reopened_detector = HighlightStoryArcService(reopened_media)
    reopened_detector.initialize()
    reopened_chronicle = DelverChronicleProfileService(reopened_media, highlights=reopened_detector)
    reopened_chronicle.initialize()
    reopened = NarrativeClaimVerificationService(reopened_media, chronicle=reopened_chronicle)
    reopened.initialize()
    reopened_snapshot = reopened.snapshot()
    repeated_valid = reopened.verify(valid_manifest.manifest_id)
    after_repeat = reopened.snapshot()

    canonical_after = descent.model_dump(mode="json")
    ledger_after = [item.model_dump(mode="json") for item in canonical.replay_events(descent.id)]

    body = {
        "protocol": PROOF_PROTOCOL,
        "slice_protocol": snapshot["protocol"],
        "implementation_version": snapshot["implementation_version"],
        "phase": snapshot["phase"],
        "seed": seed,
        "authority_contract": {
            "authoritative": snapshot["authoritative"],
            "canonical_owner": snapshot["canonical_owner"],
            "presentation_can_mutate_simulation": snapshot["presentation_can_mutate_simulation"],
            "writer_self_certification_trusted": snapshot["writer_self_certification_trusted"],
            "auxiliary_model_can_override_deterministic_checks": snapshot["auxiliary_model_can_override_deterministic_checks"],
            "local_model_required": snapshot["local_model_required"],
            "cloud_api_required": snapshot["cloud_api_required"],
            "paid_provider_required": snapshot["paid_provider_required"],
            "provider_invocation_used": snapshot["provider_invocation_used"],
        },
        "canonical": {
            "state_unchanged": canonical_json(canonical_before) == canonical_json(canonical_after),
            "fingerprint_unchanged": fingerprint_before == descent.fingerprint(),
            "history_unchanged": history_before == descent.history_event_ids,
            "ledger_rows_unchanged": ledger_before == ledger_after,
            "fingerprint": descent.fingerprint(),
            "state_digest": payload_digest(canonical_after),
            "ledger_digest": payload_digest(ledger_after),
        },
        "review_ready": {
            "status": valid_result.status.value,
            "review_ready": valid_result.review_ready,
            "all_sentences_covered": valid_result.all_sentences_covered,
            "contradictions": valid_result.deterministic_contradiction_count,
            "unsupported": valid_result.unsupported_claim_count,
            "claim_statuses": sorted(item.status.value for item in valid_result.claim_results),
            "writer_provider_local": valid_draft.writer_provider_local,
            "writer_provider_paid": valid_draft.writer_provider_paid,
            "repeat_equal": repeated_valid == valid_result,
        },
        "wrong_stratum": {
            "status": wrong_result.status.value,
            "review_ready": wrong_result.review_ready,
            "contradictions": wrong_result.deterministic_contradiction_count,
            "reason_codes": list(wrong_result.reason_codes),
            "auxiliary_used": wrong_result.auxiliary_assessment_used,
            "auxiliary_override_allowed": wrong_result.auxiliary_model_can_override_deterministic_checks,
        },
        "style_guard": {
            "status": style_result.status.value,
            "review_ready": style_result.review_ready,
            "unsupported": style_result.unsupported_claim_count,
            "claim_reason_codes": [list(item.reason_codes) for item in style_result.claim_results],
        },
        "ambiguous": {
            "status": ambiguous_result.status.value,
            "review_ready": ambiguous_result.review_ready,
            "contradictions": ambiguous_result.deterministic_contradiction_count,
            "auxiliary_used": ambiguous_result.auxiliary_assessment_used,
            "reason_codes": list(ambiguous_result.reason_codes),
        },
        "media": {
            "draft_count": snapshot["draft_count"],
            "manifest_count": snapshot["manifest_count"],
            "verification_count": snapshot["verification_count"],
            "draft_digest": snapshot["draft_digest"],
            "manifest_digest": snapshot["manifest_digest"],
            "verification_digest": snapshot["verification_digest"],
            "snapshot_digest": snapshot["digest"],
            "snapshot_equal_after_reopen": reopened_snapshot == snapshot,
            "snapshot_equal_after_repeat": after_repeat == snapshot,
            "media_job_count": len(reopened_media.list_jobs()),
            "provider_execution_count": len(media_snapshot["provider_executions"]),
        },
    }
    proof = {**body, "digest": payload_digest(body)}
    output.write_text(json.dumps(proof, indent=2, sort_keys=True), encoding="utf-8")
    return proof


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", default="underreach-30-5-5-narrative-proof")
    args = parser.parse_args()
    proof = generate(Path(args.output), seed=args.seed)
    print(
        json.dumps(
            {
                "digest": proof["digest"],
                "ready": proof["review_ready"]["status"],
                "wrong": proof["wrong_stratum"]["status"],
                "ambiguous": proof["ambiguous"]["status"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
