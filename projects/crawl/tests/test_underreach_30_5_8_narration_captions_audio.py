from __future__ import annotations

from pathlib import Path

import pytest

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.crawl_service import CrawlLifecycleService
from livingworld.underreach_brain_driven_descent import BrainDrivenDescentService
from livingworld.underreach_delver_chronicle_profile import DelverChronicleProfileService
from livingworld.underreach_group_social_orchestration import GroupSocialOrchestrationService
from livingworld.underreach_highlight_story_arc import HighlightStoryArcService
from livingworld.underreach_media_event_export import CanonicalMediaEventExporter
from livingworld.underreach_media_foundation import (
    JobStatus,
    MediaPersistence,
    ProviderDescriptor,
    ProviderKind,
    ProviderPolicy,
)
from livingworld.underreach_narrative_claim_verification import (
    AssessmentClassification,
    AuxiliaryAssessment,
    ClaimSpec,
    ClaimType,
    NarrativeClaimVerificationService,
    VerificationStatus,
)
from livingworld.underreach_narration_captions_audio import (
    AudioProductionPolicy,
    DeterministicLocalWavProvider,
    NarrationAudioError,
    NarrationCaptionsAudioService,
    NarrationMode,
    SoundAssetKind,
    VoiceSynthesisRequest,
    make_sound_asset,
    render_srt,
    render_vtt,
)
from livingworld.underreach_parties_alliances_leadership import PartiesAlliancesLeadershipService
from livingworld.underreach_rivalry_betrayal_social_conflict import RivalryBetrayalSocialConflictService
from livingworld.underreach_social_intent_execution import SocialIntentExecutionService
from livingworld.underreach_social_memory_evolution import SocialMemoryEvolutionService


IDS = [f"descender_{index:03d}" for index in range(6)]


def _stack(*, seed: str, database_url: str = "sqlite://"):
    canonical = CrawlPersistence("sqlite://")
    canonical.initialize()
    brain = BrainDrivenDescentService(canonical)
    descent = brain.create(seed=seed, descender_ids=IDS, stratum_count=3)
    brain.start(descent)
    memory = SocialMemoryEvolutionService(canonical)
    memory.initialize(descent)
    SocialIntentExecutionService(canonical).initialize(descent)
    PartiesAlliancesLeadershipService(canonical).initialize(descent)
    RivalryBetrayalSocialConflictService(canonical).initialize(descent)
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
    return canonical, descent, memory, lifecycle, exporter, media, detector, chronicle, verifier


def _review_ready(*, seed: str, database_url: str = "sqlite://", ambiguous: bool = False):
    stack = _stack(seed=seed, database_url=database_url)
    canonical, descent, memory, lifecycle, exporter, media, detector, chronicle, verifier = stack
    prior = lifecycle.record_event(
        descent,
        "BETRAYAL",
        "30.5.8 prior canonical social event.",
        actor_ids=IDS[:2],
        location_id=descent.participants[IDS[0]].current_location_id,
        data={"danger": 0.6, "state_changes": {"prior": True}},
    )
    assert memory.process_event(descent, prior).processed
    event = lifecycle.record_event(
        descent,
        "NEAR_DEATH_BETRAYAL_RELIC_COMEBACK",
        "30.5.8 canonical audio source event.",
        actor_ids=IDS[:2],
        location_id=descent.participants[IDS[0]].current_location_id,
        data={
            "danger": 1.0,
            "state_changes": {"30_5_8": True},
            "social_facts": [
                {
                    "observer_descender_id": IDS[1],
                    "subject_descender_id": IDS[0],
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
    chapter = chronicle.list_chapters(delver_id=IDS[0])[0]
    event_type = next(
        fact for fact in envelope.allowed_facts if fact.fact_id in chapter.allowed_fact_ids and fact.predicate == "event_type"
    )
    prose = "The recorded event was NEAR_DEATH_BETRAYAL_RELIC_COMEBACK. The silence felt heavier afterward."
    draft = verifier.register_draft(
        chapter_id=chapter.chapter_id,
        prose=prose,
        writer_provider_id="local_qwen_fixture",
        writer_provider_local=True,
        writer_provider_paid=False,
    )
    assessments = (
        [
            AuxiliaryAssessment(
                sentence_index=0,
                classification=AssessmentClassification.AMBIGUOUS,
                provider_id="local_small_classifier",
                provider_local=True,
                provider_paid=False,
            )
        ]
        if ambiguous
        else []
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
        auxiliary_assessments=assessments,
    )
    verification = verifier.verify(manifest.manifest_id)
    return (*stack, event, envelope, chapter, draft, manifest, verification)


class FailingVoiceProvider:
    def __init__(self) -> None:
        self._descriptor = ProviderDescriptor(
            provider_id="local_failing_voice",
            kind=ProviderKind.VOICE,
            local=True,
            paid=False,
            capability_flags=("headless_voice", "wav_output"),
            deterministic_seed=True,
            max_duration_seconds=300.0,
            quality_rank=5,
        )

    @property
    def descriptor(self) -> ProviderDescriptor:
        return self._descriptor

    def synthesize(self, request: VoiceSynthesisRequest):
        raise RuntimeError("injected local TTS failure")


def test_only_review_ready_narrative_can_be_planned(tmp_path: Path) -> None:
    *_, media, detector, chronicle, verifier, event, envelope, chapter, draft, manifest, result = _review_ready(
        seed="30-5-8-needs-review", ambiguous=True
    )
    assert result.status == VerificationStatus.NEEDS_REVIEW
    service = NarrationCaptionsAudioService(media, verifier=verifier, providers=[], output_root=tmp_path)
    service.initialize()
    with pytest.raises(NarrationAudioError, match="REVIEW_READY"):
        service.plan(result.verification_id)


def test_verified_script_is_verbatim_and_captions_are_direct(tmp_path: Path) -> None:
    *_, media, detector, chronicle, verifier, event, envelope, chapter, draft, manifest, result = _review_ready(
        seed="30-5-8-caption-verbatim"
    )
    assert result.status == VerificationStatus.REVIEW_READY
    service = NarrationCaptionsAudioService(
        media,
        verifier=verifier,
        providers=[],
        output_root=tmp_path,
        policy=AudioProductionPolicy(voice_enabled=False),
    )
    service.initialize()
    spec = service.plan(result.verification_id)
    assert spec.script == draft.prose
    assert spec.sentences == draft.sentences
    assert tuple(item.text for item in spec.caption_cues) == draft.sentences
    assert spec.speech_recognition_used is False
    assert spec.audio_mixing_performed is False
    assert render_srt(spec.caption_cues).count(" --> ") == len(draft.sentences)
    assert render_vtt(spec.caption_cues).startswith("WEBVTT\n")

    package_job, voice_job = service.enqueue(spec)
    assert voice_job is None
    completed = service.run_next()
    assert completed is not None
    assert completed.package_job_id == package_job.job_id
    assert completed.package_status == JobStatus.COMPLETED
    assert completed.caption_only_ready is True
    assert completed.mode == NarrationMode.CAPTION_ONLY
    snapshot = service.snapshot()
    assert snapshot["job_count"] == 1
    assert snapshot["artifact_count"] == 4
    for artifact in snapshot["artifacts"]:
        assert (tmp_path / artifact["uri"]).exists()


def test_local_voice_produces_real_wav_and_keeps_caption_fallback(tmp_path: Path) -> None:
    *_, media, detector, chronicle, verifier, event, envelope, chapter, draft, manifest, result = _review_ready(
        seed="30-5-8-local-wav"
    )
    service = NarrationCaptionsAudioService(
        media,
        verifier=verifier,
        providers=[DeterministicLocalWavProvider()],
        output_root=tmp_path,
    )
    service.initialize()
    spec = service.plan(result.verification_id)
    package_job, voice_job = service.enqueue(spec)
    assert voice_job is not None and voice_job.status == JobStatus.QUEUED
    package_result = service.run_next()
    voice_result = service.run_next()
    assert package_result is not None and package_result.caption_only_ready
    assert voice_result is not None
    assert voice_result.mode == NarrationMode.NARRATED
    assert voice_result.voice_status == JobStatus.COMPLETED
    snapshot = service.snapshot()
    assert snapshot["job_count"] == 2
    assert snapshot["artifact_count"] == 6
    assert snapshot["provider_execution_count"] == 1
    wav = next(item for item in snapshot["artifacts"] if item["artifact_kind"] == "audio/wav")
    payload = (tmp_path / wav["uri"]).read_bytes()
    assert payload.startswith(b"RIFF") and b"WAVE" in payload[:16]
    assert snapshot["caption_only_fallback_guaranteed"] is True


def test_no_voice_provider_holds_voice_job_but_caption_package_completes(tmp_path: Path) -> None:
    *_, media, detector, chronicle, verifier, event, envelope, chapter, draft, manifest, result = _review_ready(
        seed="30-5-8-no-provider"
    )
    service = NarrationCaptionsAudioService(media, verifier=verifier, providers=[], output_root=tmp_path)
    service.initialize()
    spec = service.plan(result.verification_id)
    package_job, voice_job = service.enqueue(spec)
    assert voice_job is not None
    assert voice_job.status == JobStatus.HELD
    completed = service.run_next()
    assert completed is not None and completed.caption_only_ready
    assert completed.package_status == JobStatus.COMPLETED
    persisted_voice = media.get_job(voice_job.job_id)
    assert persisted_voice is not None and persisted_voice.status == JobStatus.HELD
    snapshot = service.snapshot()
    assert sum(item["artifact_kind"] in {"text/plain", "text/srt", "text/vtt"} for item in snapshot["artifacts"]) == 3
    assert snapshot["provider_execution_count"] == 0


def test_voice_failure_never_invalidates_caption_only_package(tmp_path: Path) -> None:
    *_, media, detector, chronicle, verifier, event, envelope, chapter, draft, manifest, result = _review_ready(
        seed="30-5-8-failure"
    )
    service = NarrationCaptionsAudioService(
        media,
        verifier=verifier,
        providers=[FailingVoiceProvider()],
        output_root=tmp_path,
        policy=AudioProductionPolicy(max_attempts=2),
    )
    service.initialize()
    spec = service.plan(result.verification_id)
    package_job, voice_job = service.enqueue(spec)
    assert voice_job is not None
    package_result = service.run_next()
    first_failure = service.run_next()
    second_failure = service.run_next()
    assert package_result is not None and package_result.caption_only_ready
    assert first_failure is not None and first_failure.voice_status == JobStatus.RETRY
    assert second_failure is not None and second_failure.voice_status == JobStatus.FAILED
    assert first_failure.mode == NarrationMode.CAPTION_ONLY
    assert second_failure.mode == NarrationMode.CAPTION_ONLY
    assert len([item for item in service.snapshot()["artifacts"] if item["job_id"] == package_job.job_id]) == 4


def test_paid_voice_provider_is_blocked_without_explicit_global_permission(tmp_path: Path) -> None:
    *_, media, detector, chronicle, verifier, event, envelope, chapter, draft, manifest, result = _review_ready(
        seed="30-5-8-paid-block"
    )
    paid_descriptor = ProviderDescriptor(
        provider_id="remote_paid_voice",
        kind=ProviderKind.VOICE,
        local=False,
        paid=True,
        capability_flags=("headless_voice", "wav_output"),
        deterministic_seed=True,
        max_duration_seconds=300.0,
        estimated_cost_microusd=1000,
        quality_rank=90,
    )
    provider = DeterministicLocalWavProvider(descriptor=paid_descriptor)
    policy = AudioProductionPolicy(local_required=False, paid_allowed=True, explicit_paid_authorization=True)
    service = NarrationCaptionsAudioService(
        media,
        verifier=verifier,
        providers=[provider],
        output_root=tmp_path,
        policy=policy,
        provider_policy=ProviderPolicy(
            local_only=False,
            cloud_allowed=True,
            allow_paid=False,
            daily_paid_budget_microusd=0,
        ),
    )
    service.initialize()
    spec = service.plan(result.verification_id)
    package_job, voice_job = service.enqueue(spec)
    assert voice_job is not None and voice_job.status == JobStatus.HELD
    assert voice_job.selected_provider_id is None


def test_sound_asset_metadata_is_local_royalty_safe_and_not_mixed(tmp_path: Path) -> None:
    *_, media, detector, chronicle, verifier, event, envelope, chapter, draft, manifest, result = _review_ready(
        seed="30-5-8-sound-assets"
    )
    music = make_sound_asset(
        asset_id="music_dungeon_001",
        kind=SoundAssetKind.MUSIC,
        relative_uri="library/music/dungeon-001.wav",
        license_label="local-royalty-safe",
    )
    sfx = make_sound_asset(
        asset_id="sfx_impact_001",
        kind=SoundAssetKind.SFX,
        relative_uri="library/sfx/impact-001.wav",
        license_label="local-royalty-safe",
    )
    service = NarrationCaptionsAudioService(
        media,
        verifier=verifier,
        providers=[],
        output_root=tmp_path,
        policy=AudioProductionPolicy(voice_enabled=False),
    )
    spec = service.plan(result.verification_id, sound_assets=(sfx, music))
    assert tuple(item.asset_id for item in spec.sound_assets) == (music.asset_id, sfx.asset_id)
    assert all(item.royalty_safe for item in spec.sound_assets)
    assert spec.audio_mixing_performed is False


def test_file_backed_voice_restart_recovers_same_job_and_is_idempotent(tmp_path: Path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'media.sqlite3').as_posix()}"
    *_, media, detector, chronicle, verifier, event, envelope, chapter, draft, manifest, result = _review_ready(
        seed="30-5-8-restart", database_url=database_url
    )
    output_root = tmp_path / "outputs"
    service = NarrationCaptionsAudioService(
        media,
        verifier=verifier,
        providers=[DeterministicLocalWavProvider()],
        output_root=output_root,
    )
    service.initialize()
    spec = service.plan(result.verification_id)
    package_job, voice_job = service.enqueue(spec, package_priority=120, voice_priority=110)
    assert voice_job is not None
    package_result = service.run_next()
    assert package_result is not None and package_result.package_status == JobStatus.COMPLETED
    lease = media.claim_next("30-5-8-crashed-worker")
    assert lease is not None and lease.job.job_id == voice_job.job_id

    reopened_media = MediaPersistence(database_url)
    reopened_media.initialize()
    assert reopened_media.recover_interrupted_jobs() == 1
    reopened_detector = HighlightStoryArcService(reopened_media)
    reopened_detector.initialize()
    reopened_chronicle = DelverChronicleProfileService(reopened_media, highlights=reopened_detector)
    reopened_chronicle.initialize()
    reopened_verifier = NarrativeClaimVerificationService(reopened_media, chronicle=reopened_chronicle)
    reopened_verifier.initialize()
    reopened = NarrationCaptionsAudioService(
        reopened_media,
        verifier=reopened_verifier,
        providers=[DeterministicLocalWavProvider()],
        output_root=output_root,
    )
    reopened.initialize()
    voice_result = reopened.run_next()
    assert voice_result is not None and voice_result.voice_status == JobStatus.COMPLETED
    final_voice = reopened_media.get_job(voice_job.job_id)
    assert final_voice is not None and final_voice.attempt_count == 2

    before = reopened.snapshot()
    reopened_spec = reopened.plan(result.verification_id)
    repeat_package, repeat_voice = reopened.enqueue(reopened_spec, package_priority=120, voice_priority=110)
    after = reopened.snapshot()
    assert repeat_package.job_id == package_job.job_id
    assert repeat_voice is not None and repeat_voice.job_id == voice_job.job_id
    assert before == after
