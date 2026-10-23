from __future__ import annotations

from sqlalchemy import inspect

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.crawl_service import CrawlLifecycleService
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
    ClaimStatus,
    ClaimType,
    NarrativeClaimVerificationService,
    VerificationStatus,
)
from livingworld.underreach_parties_alliances_leadership import PartiesAlliancesLeadershipService
from livingworld.underreach_rivalry_betrayal_social_conflict import RivalryBetrayalSocialConflictService
from livingworld.underreach_social_intent_execution import SocialIntentExecutionService
from livingworld.underreach_social_memory_evolution import SocialMemoryEvolutionService


def _stack(seed: str = "30-5-5-claims", *, database_url: str = "sqlite://"):
    canonical = CrawlPersistence("sqlite://")
    canonical.initialize()
    brain = BrainDrivenDescentService(canonical)
    ids = [f"descender_{index:03d}" for index in range(6)]
    descent = brain.create(seed=seed, descender_ids=ids, stratum_count=3)
    brain.start(descent)
    memory = SocialMemoryEvolutionService(canonical)
    memory.initialize(descent)
    social = SocialIntentExecutionService(canonical)
    social.initialize(descent)
    parties = PartiesAlliancesLeadershipService(canonical)
    parties.initialize(descent)
    conflict = RivalryBetrayalSocialConflictService(canonical)
    conflict.initialize(descent)
    GroupSocialOrchestrationService(canonical, brain=brain).initialize(descent)
    lifecycle = CrawlLifecycleService(canonical)
    exporter = CanonicalMediaEventExporter(canonical)
    media = MediaPersistence(database_url)
    media.initialize()
    detector = HighlightStoryArcService(media)
    detector.initialize()
    chronicle = DelverChronicleProfileService(media, highlights=detector)
    chronicle.initialize()
    verifier = NarrativeClaimVerificationService(media, chronicle=chronicle)
    verifier.initialize()
    return canonical, descent, ids, memory, lifecycle, exporter, media, detector, chronicle, verifier


def _chapter(seed: str = "30-5-5-chapter", *, database_url: str = "sqlite://"):
    stack = _stack(seed, database_url=database_url)
    canonical, descent, ids, memory, lifecycle, exporter, media, detector, chronicle, verifier = stack
    prior = lifecycle.record_event(
        descent,
        "BETRAYAL",
        "30.5.5 prior canonical social event.",
        actor_ids=ids[:2],
        location_id=descent.participants[ids[0]].current_location_id,
        data={"danger": 0.6, "state_changes": {"prior": True}},
    )
    assert memory.process_event(descent, prior).processed
    event = lifecycle.record_event(
        descent,
        "NEAR_DEATH_BETRAYAL_RELIC_COMEBACK",
        "30.5.5 canonical narrative source event.",
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
    assert memory.process_event(descent, event).processed
    envelope = exporter.export_event(descent, event.id)
    media.register_envelope(envelope)
    evaluation = detector.evaluate(envelope)
    assert evaluation.selected
    chronicle.process(envelope)
    chapter = chronicle.list_chapters(delver_id=ids[0])[0]
    fact_by_predicate = {fact.predicate: fact for fact in envelope.allowed_facts if fact.fact_id in chapter.allowed_fact_ids}
    return (*stack, event, envelope, chapter, fact_by_predicate)


def test_exact_allowed_fact_and_bounded_style_become_review_ready() -> None:
    *_, verifier, event, _, chapter, facts = _chapter(seed="30-5-5-ready")
    event_type = facts["event_type"]
    draft = verifier.register_draft(
        chapter_id=chapter.chapter_id,
        prose="The recorded event was NEAR_DEATH_BETRAYAL_RELIC_COMEBACK. The silence felt heavier afterward.",
        writer_provider_id="local_qwen_fixture",
        writer_provider_local=True,
        writer_provider_paid=False,
    )
    manifest = verifier.register_manifest(
        draft_id=draft.draft_id,
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
    result = verifier.verify(manifest.manifest_id)

    assert result.status == VerificationStatus.REVIEW_READY
    assert result.review_ready is True
    assert result.all_sentences_covered is True
    assert result.deterministic_contradiction_count == 0
    assert result.unsupported_claim_count == 0
    assert {item.status for item in result.claim_results} == {ClaimStatus.VERIFIED, ClaimStatus.STYLE_SAFE}
    assert result.presentation_can_mutate_simulation is False
    assert result.canonical_authority is False


def test_wrong_stratum_is_deterministic_contradiction() -> None:
    *_, verifier, event, _, chapter, facts = _chapter(seed="30-5-5-wrong-stratum")
    fact = facts["stratum"]
    wrong = 99 if fact.value != 99 else 98
    draft = verifier.register_draft(chapter_id=chapter.chapter_id, prose=f"The event occurred on Stratum {wrong}.")
    manifest = verifier.register_manifest(
        draft_id=draft.draft_id,
        claim_specs=[
            ClaimSpec(
                claim_type=ClaimType.FACTUAL,
                sentence_index=0,
                subject=event.id,
                predicate="stratum",
                target_or_value=wrong,
                supporting_allowed_fact_ids=(fact.fact_id,),
            )
        ],
    )
    result = verifier.verify(manifest.manifest_id)
    assert result.status == VerificationStatus.REJECTED
    assert result.review_ready is False
    assert result.deterministic_contradiction_count == 1
    assert "deterministic_contradiction" in result.reason_codes


def test_invented_item_ownership_is_unsupported_even_with_unrelated_allowed_fact() -> None:
    *_, verifier, _, _, chapter, facts = _chapter(seed="30-5-5-invented-owner")
    support = facts["event_type"]
    draft = verifier.register_draft(chapter_id=chapter.chapter_id, prose="The relic belonged to descender_999.")
    manifest = verifier.register_manifest(
        draft_id=draft.draft_id,
        claim_specs=[
            ClaimSpec(
                claim_type=ClaimType.FACTUAL,
                sentence_index=0,
                subject="invented_item",
                predicate="owner_descender_id",
                target_or_value="descender_999",
                supporting_allowed_fact_ids=(support.fact_id,),
            )
        ],
    )
    result = verifier.verify(manifest.manifest_id)
    assert result.status == VerificationStatus.REJECTED
    assert result.unsupported_claim_count == 1
    assert "unsupported_claim" in result.reason_codes


def test_factual_language_cannot_be_hidden_as_stylistic_claim() -> None:
    *_, verifier, _, _, chapter, _ = _chapter(seed="30-5-5-style-guard")
    draft = verifier.register_draft(chapter_id=chapter.chapter_id, prose="He died alone in Sector alpha.")
    manifest = verifier.register_manifest(
        draft_id=draft.draft_id,
        claim_specs=[ClaimSpec(claim_type=ClaimType.STYLISTIC, sentence_index=0)],
    )
    result = verifier.verify(manifest.manifest_id)
    assert result.status == VerificationStatus.REJECTED
    assert result.unsupported_claim_count == 1
    assert result.claim_results[0].reason_codes == ("stylistic_sentence_contains_factual_signal",)


def test_every_sentence_requires_manifest_coverage() -> None:
    *_, verifier, event, _, chapter, facts = _chapter(seed="30-5-5-coverage")
    fact = facts["event_type"]
    draft = verifier.register_draft(
        chapter_id=chapter.chapter_id,
        prose="The recorded event was NEAR_DEATH_BETRAYAL_RELIC_COMEBACK. The moment lingered.",
    )
    manifest = verifier.register_manifest(
        draft_id=draft.draft_id,
        claim_specs=[
            ClaimSpec(
                claim_type=ClaimType.FACTUAL,
                sentence_index=0,
                subject=event.id,
                predicate="event_type",
                target_or_value=fact.value,
                supporting_allowed_fact_ids=(fact.fact_id,),
            )
        ],
    )
    result = verifier.verify(manifest.manifest_id)
    assert result.status == VerificationStatus.REJECTED
    assert result.all_sentences_covered is False
    assert "uncovered_draft_sentence" in result.reason_codes


def test_auxiliary_model_cannot_override_deterministic_contradiction() -> None:
    *_, verifier, event, _, chapter, facts = _chapter(seed="30-5-5-no-override")
    fact = facts["stratum"]
    wrong = 99 if fact.value != 99 else 98
    draft = verifier.register_draft(chapter_id=chapter.chapter_id, prose=f"The event occurred on Stratum {wrong}.")
    manifest = verifier.register_manifest(
        draft_id=draft.draft_id,
        claim_specs=[
            ClaimSpec(
                claim_type=ClaimType.FACTUAL,
                sentence_index=0,
                subject=event.id,
                predicate="stratum",
                target_or_value=wrong,
                supporting_allowed_fact_ids=(fact.fact_id,),
            )
        ],
        auxiliary_assessments=[
            AuxiliaryAssessment(
                sentence_index=0,
                classification=AssessmentClassification.STYLISTIC,
                provider_id="local_small_classifier",
                provider_local=True,
                provider_paid=False,
                reason_code="model_thought_style",
            )
        ],
    )
    result = verifier.verify(manifest.manifest_id)
    assert result.status == VerificationStatus.REJECTED
    assert result.deterministic_contradiction_count == 1
    assert result.auxiliary_assessment_used is True
    assert result.auxiliary_model_can_override_deterministic_checks is False


def test_auxiliary_ambiguity_can_only_downgrade_valid_result() -> None:
    *_, verifier, event, _, chapter, facts = _chapter(seed="30-5-5-ambiguous")
    fact = facts["event_type"]
    draft = verifier.register_draft(chapter_id=chapter.chapter_id, prose="The recorded event was NEAR_DEATH_BETRAYAL_RELIC_COMEBACK.")
    manifest = verifier.register_manifest(
        draft_id=draft.draft_id,
        claim_specs=[
            ClaimSpec(
                claim_type=ClaimType.FACTUAL,
                sentence_index=0,
                subject=event.id,
                predicate="event_type",
                target_or_value=fact.value,
                supporting_allowed_fact_ids=(fact.fact_id,),
            )
        ],
        auxiliary_assessments=[
            AuxiliaryAssessment(
                sentence_index=0,
                classification=AssessmentClassification.AMBIGUOUS,
                provider_id="local_small_classifier",
                provider_local=True,
                provider_paid=False,
            )
        ],
    )
    result = verifier.verify(manifest.manifest_id)
    assert result.status == VerificationStatus.NEEDS_REVIEW
    assert result.review_ready is False
    assert result.deterministic_contradiction_count == 0


def test_narrative_tables_are_media_only_and_canonical_state_is_unchanged() -> None:
    canonical, descent, *_, verifier, event, _, chapter, facts = _chapter(seed="30-5-5-separation")
    fact = facts["event_type"]
    before_state = descent.model_dump(mode="json")
    before_fingerprint = descent.fingerprint()
    before_rows = [item.model_dump(mode="json") for item in canonical.replay_events(descent.id)]
    draft = verifier.register_draft(chapter_id=chapter.chapter_id, prose="The recorded event was NEAR_DEATH_BETRAYAL_RELIC_COMEBACK.")
    manifest = verifier.register_manifest(
        draft_id=draft.draft_id,
        claim_specs=[
            ClaimSpec(
                claim_type=ClaimType.FACTUAL,
                sentence_index=0,
                subject=event.id,
                predicate="event_type",
                target_or_value=fact.value,
                supporting_allowed_fact_ids=(fact.fact_id,),
            )
        ],
    )
    verifier.verify(manifest.manifest_id)
    assert descent.model_dump(mode="json") == before_state
    assert descent.fingerprint() == before_fingerprint
    assert [item.model_dump(mode="json") for item in canonical.replay_events(descent.id)] == before_rows
    canonical_tables = set(inspect(canonical.engine).get_table_names())
    media_tables = set(inspect(verifier.media.engine).get_table_names())
    assert canonical_tables.isdisjoint(media_tables)
    assert {"media_narrative_drafts", "media_claim_manifests", "media_narrative_verifications"}.issubset(media_tables)


def test_file_backed_restart_is_idempotent(tmp_path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'media.sqlite3').as_posix()}"
    *prefix, verifier, event, envelope, chapter, facts = _chapter(seed="30-5-5-restart", database_url=database_url)
    fact = facts["event_type"]
    draft = verifier.register_draft(chapter_id=chapter.chapter_id, prose="The recorded event was NEAR_DEATH_BETRAYAL_RELIC_COMEBACK.")
    manifest = verifier.register_manifest(
        draft_id=draft.draft_id,
        claim_specs=[
            ClaimSpec(
                claim_type=ClaimType.FACTUAL,
                sentence_index=0,
                subject=event.id,
                predicate="event_type",
                target_or_value=fact.value,
                supporting_allowed_fact_ids=(fact.fact_id,),
            )
        ],
    )
    first = verifier.verify(manifest.manifest_id)
    first_snapshot = verifier.snapshot()

    media = MediaPersistence(database_url)
    media.initialize()
    detector = HighlightStoryArcService(media)
    detector.initialize()
    chronicle = DelverChronicleProfileService(media, highlights=detector)
    chronicle.initialize()
    reopened = NarrativeClaimVerificationService(media, chronicle=chronicle)
    reopened.initialize()
    second = reopened.verify(manifest.manifest_id)
    second_snapshot = reopened.snapshot()

    assert second == first
    assert second_snapshot == first_snapshot
    assert len(reopened.list_drafts()) == 1
    assert len(reopened.list_manifests()) == 1
    assert len(reopened.list_verifications()) == 1
