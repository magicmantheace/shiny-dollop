from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.crawl_service import CrawlLifecycleService
from livingworld.underreach_brain_driven_descent import BrainDrivenDescentService
from livingworld.underreach_delver_chronicle_profile import DelverChronicleProfileService
from livingworld.underreach_ffmpeg_motion_story import (
    AutomatedFfmpegMotionStoryService,
    MotionStoryError,
    MotionStoryPolicy,
)
from livingworld.underreach_group_social_orchestration import GroupSocialOrchestrationService
from livingworld.underreach_headless_local_image_production import (
    DeterministicLocalPngProvider,
    HeadlessLocalImageProductionService,
)
from livingworld.underreach_highlight_story_arc import HighlightStoryArcService
from livingworld.underreach_media_event_export import CanonicalMediaEventExporter
from livingworld.underreach_media_foundation import JobStatus, MediaPersistence
from livingworld.underreach_narrative_claim_verification import (
    ClaimSpec,
    ClaimType,
    NarrativeClaimVerificationService,
    VerificationStatus,
)
from livingworld.underreach_narration_captions_audio import (
    AudioProductionPolicy,
    DeterministicLocalWavProvider,
    NarrationCaptionsAudioService,
    NarrationMode,
    SoundAssetKind,
    deterministic_wav_bytes,
    make_sound_asset,
)
from livingworld.underreach_parties_alliances_leadership import PartiesAlliancesLeadershipService
from livingworld.underreach_presentation_identity import PresentationIdentityService, ReferenceKind
from livingworld.underreach_rivalry_betrayal_social_conflict import RivalryBetrayalSocialConflictService
from livingworld.underreach_social_intent_execution import SocialIntentExecutionService
from livingworld.underreach_social_memory_evolution import SocialMemoryEvolutionService


IDS = [f"descender_{index:03d}" for index in range(8)]


def _ffmpeg_ready() -> bool:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        return False
    try:
        filters = subprocess.run([ffmpeg, "-hide_banner", "-filters"], capture_output=True, text=True, timeout=10, check=False)
        encoders = subprocess.run([ffmpeg, "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=10, check=False)
    except Exception:
        return False
    text = filters.stdout + filters.stderr
    return filters.returncode == 0 and encoders.returncode == 0 and "subtitles" in text and "xfade" in text and "libx264" in (encoders.stdout + encoders.stderr)


def _stack(*, seed: str, database_url: str = "sqlite://") -> dict:
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
    identities = PresentationIdentityService(media, chronicle=chronicle)
    identities.initialize()
    verifier = NarrativeClaimVerificationService(media, chronicle=chronicle)
    verifier.initialize()

    prior = lifecycle.record_event(
        descent,
        "BETRAYAL",
        "30.5.9 prior canonical social event.",
        actor_ids=IDS[:2],
        location_id=descent.participants[IDS[0]].current_location_id,
        data={"danger": 0.6, "state_changes": {"prior": True}},
    )
    assert memory.process_event(descent, prior).processed
    event = lifecycle.record_event(
        descent,
        "NEAR_DEATH_BETRAYAL_RELIC_COMEBACK",
        "30.5.9 canonical motion-story source event.",
        actor_ids=IDS[:2],
        location_id=descent.participants[IDS[0]].current_location_id,
        data={
            "danger": 1.0,
            "state_changes": {"30_5_9": True},
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
    profile = chronicle.get_profile(descent.id, IDS[0])
    assert profile is not None
    identity_state = identities.ensure_identity(profile)
    chapter = next(item for item in chronicle.list_chapters(delver_id=IDS[0]) if item.chapter_id in profile.chapter_ids)

    event_type = next(
        fact for fact in envelope.allowed_facts if fact.fact_id in chapter.allowed_fact_ids and fact.predicate == "event_type"
    )
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
    verification = verifier.verify(manifest.manifest_id)
    assert verification.status == VerificationStatus.REVIEW_READY
    return {
        "canonical": canonical,
        "descent": descent,
        "media": media,
        "detector": detector,
        "chronicle": chronicle,
        "identities": identities,
        "verifier": verifier,
        "profile": profile,
        "identity_state": identity_state,
        "chapter": chapter,
        "draft": draft,
        "verification": verification,
    }


def _produce_scene(stack: dict, root: Path, *, portrait: bool = False) -> str:
    service = HeadlessLocalImageProductionService(
        stack["media"],
        identities=stack["identities"],
        providers=[DeterministicLocalPngProvider()],
        output_root=root,
    )
    service.initialize()
    if portrait:
        job = service.enqueue_reference(stack["profile"], ReferenceKind.PORTRAIT, width=96, height=128)
    else:
        job = service.enqueue_scene(stack["profile"], stack["chapter"], width=96, height=128)
    result = service.run_next()
    assert result is not None and result.status == JobStatus.COMPLETED
    assert result.artifact_id is not None
    assert stack["media"].get_job(job.job_id).status == JobStatus.COMPLETED
    return result.artifact_id


def _produce_audio(
    stack: dict,
    root: Path,
    *,
    voice: bool,
    sound_assets=(),
) -> tuple[str, object]:
    service = NarrationCaptionsAudioService(
        stack["media"],
        verifier=stack["verifier"],
        providers=[DeterministicLocalWavProvider()] if voice else [],
        output_root=root,
        policy=AudioProductionPolicy(voice_enabled=voice, milliseconds_per_word=220, minimum_caption_ms=600),
    )
    service.initialize()
    spec = service.plan(stack["verification"].verification_id, sound_assets=tuple(sound_assets))
    package_job, voice_job = service.enqueue(spec, package_priority=120, voice_priority=110)
    package_result = service.run_next()
    assert package_result is not None and package_result.package_status == JobStatus.COMPLETED
    if voice:
        assert voice_job is not None
        voice_result = service.run_next()
        assert voice_result is not None and voice_result.voice_status == JobStatus.COMPLETED
    return package_job.job_id, spec


def _canonical_snapshot(stack: dict) -> tuple[dict, str, list[dict]]:
    return (
        stack["descent"].model_dump(mode="json"),
        stack["descent"].fingerprint(),
        [item.model_dump(mode="json") for item in stack["canonical"].replay_events(stack["descent"].id)],
    )


def _small_policy(**changes) -> MotionStoryPolicy:
    values = {
        "width": 360,
        "height": 640,
        "fps": 12,
        "minimum_duration_seconds": 4.0,
        "maximum_duration_seconds": 30.0,
        "target_shot_seconds": 2.0,
        "minimum_shots": 2,
        "maximum_shots": 4,
        "transition_ms": 150,
        "video_fade_ms": 100,
        "audio_fade_in_ms": 100,
        "audio_fade_out_ms": 200,
        "preset": "ultrafast",
    }
    values.update(changes)
    return MotionStoryPolicy(**values)


def test_plan_is_deterministic_and_uses_completed_scene_and_verified_caption_package(tmp_path: Path) -> None:
    stack = _stack(seed="30-5-9-plan")
    image_id = _produce_scene(stack, tmp_path)
    package_job_id, _ = _produce_audio(stack, tmp_path, voice=False)
    service = AutomatedFfmpegMotionStoryService(stack["media"], media_root=tmp_path, policy=_small_policy())
    service.initialize()

    first = service.plan(package_job_id=package_job_id, image_artifact_ids=(image_id,))
    second = service.plan(package_job_id=package_job_id, image_artifact_ids=(image_id,))

    assert first == second
    assert first.output_width * 16 == first.output_height * 9
    assert first.narration_mode == NarrationMode.CAPTION_ONLY
    assert first.voice_artifact_id is None
    assert first.burn_captions is True
    assert first.video_model_dependency is False
    assert first.video_diffusion_used is False
    assert first.canonical_authority is False
    assert first.presentation_can_mutate_simulation is False
    assert len(first.shots) >= 2


def test_identity_reference_cannot_masquerade_as_scene_still(tmp_path: Path) -> None:
    stack = _stack(seed="30-5-9-wrong-image")
    portrait_id = _produce_scene(stack, tmp_path, portrait=True)
    package_job_id, _ = _produce_audio(stack, tmp_path, voice=False)
    service = AutomatedFfmpegMotionStoryService(stack["media"], media_root=tmp_path, policy=_small_policy())
    with pytest.raises(MotionStoryError, match="narration chapter"):
        service.plan(package_job_id=package_job_id, image_artifact_ids=(portrait_id,))


def test_completed_voice_and_local_music_enable_mix_ducking_and_loudness(tmp_path: Path) -> None:
    stack = _stack(seed="30-5-9-audio-mix")
    image_id = _produce_scene(stack, tmp_path)
    music = make_sound_asset(
        asset_id="music_001",
        kind=SoundAssetKind.MUSIC,
        relative_uri="library/music/test-bed.wav",
        license_label="local-royalty-safe",
    )
    music_path = tmp_path / music.relative_uri
    music_path.parent.mkdir(parents=True, exist_ok=True)
    music_path.write_bytes(deterministic_wav_bytes(duration_ms=3000, sample_rate=22050, seed=991))
    package_job_id, _ = _produce_audio(stack, tmp_path, voice=True, sound_assets=(music,))
    service = AutomatedFfmpegMotionStoryService(stack["media"], media_root=tmp_path, policy=_small_policy())
    spec = service.plan(package_job_id=package_job_id, image_artifact_ids=(image_id,))

    assert spec.narration_mode == NarrationMode.NARRATED
    assert spec.voice_artifact_id is not None
    assert len(spec.sound_assets) == 1
    assert spec.audio_present is True
    assert spec.audio_mixing is True
    assert spec.music_ducking is True
    assert spec.loudness_normalization is True
    assert spec.audio_fades is True


def test_missing_optional_sound_asset_degrades_without_blocking_motion_story(tmp_path: Path) -> None:
    stack = _stack(seed="30-5-9-missing-music")
    image_id = _produce_scene(stack, tmp_path)
    missing = make_sound_asset(
        asset_id="missing_music",
        kind=SoundAssetKind.MUSIC,
        relative_uri="library/music/not-installed.wav",
        license_label="local-royalty-safe",
    )
    package_job_id, _ = _produce_audio(stack, tmp_path, voice=False, sound_assets=(missing,))
    service = AutomatedFfmpegMotionStoryService(stack["media"], media_root=tmp_path, policy=_small_policy())
    spec = service.plan(package_job_id=package_job_id, image_artifact_ids=(image_id,))

    assert spec.missing_sound_asset_ids == ("missing_music",)
    assert spec.sound_assets == ()
    assert spec.audio_present is False
    assert spec.narration_mode == NarrationMode.CAPTION_ONLY


def test_ffmpeg_failure_retries_and_retains_working_directory(tmp_path: Path) -> None:
    stack = _stack(seed="30-5-9-failure")
    image_id = _produce_scene(stack, tmp_path)
    package_job_id, _ = _produce_audio(stack, tmp_path, voice=False)
    service = AutomatedFfmpegMotionStoryService(
        stack["media"],
        media_root=tmp_path,
        policy=_small_policy(max_attempts=2),
        ffmpeg_path=tmp_path / "missing-ffmpeg.exe",
        ffprobe_path=tmp_path / "missing-ffprobe.exe",
    )
    spec = service.plan(package_job_id=package_job_id, image_artifact_ids=(image_id,))
    job = service.enqueue(spec)

    first = service.run_next()
    second = service.run_next()

    assert first is not None and first.status == JobStatus.RETRY
    assert second is not None and second.status == JobStatus.FAILED
    persisted = stack["media"].get_job(job.job_id)
    assert persisted is not None and persisted.attempt_count == 2
    work = tmp_path / "motion-stories" / spec.chapter_id / spec.story_id / "work"
    assert work.exists()
    assert (work / "captions.srt").exists()
    snapshot = service.snapshot()
    assert snapshot["provider_execution_count"] == 2
    assert all(item["status"] == "failed" for item in snapshot["provider_executions"])


def test_completed_reenqueue_reuses_same_durable_job_spec(tmp_path: Path) -> None:
    stack = _stack(seed="30-5-9-idempotent-plan")
    image_id = _produce_scene(stack, tmp_path)
    package_job_id, _ = _produce_audio(stack, tmp_path, voice=False)
    service = AutomatedFfmpegMotionStoryService(stack["media"], media_root=tmp_path, policy=_small_policy())
    spec = service.plan(package_job_id=package_job_id, image_artifact_ids=(image_id,))
    first = service.enqueue(spec, priority=125)
    second = service.enqueue(spec, priority=125)
    assert first.job_id == second.job_id
    assert service.snapshot()["job_count"] == 1


@pytest.mark.skipif(not _ffmpeg_ready(), reason="requires full local FFmpeg + ffprobe with subtitles/xfade/libx264")
def test_real_ffmpeg_builds_valid_vertical_caption_first_mp4_without_video_model(tmp_path: Path) -> None:
    stack = _stack(seed="30-5-9-real-ffmpeg")
    image_id = _produce_scene(stack, tmp_path)
    package_job_id, _ = _produce_audio(stack, tmp_path, voice=False)
    before = _canonical_snapshot(stack)
    service = AutomatedFfmpegMotionStoryService(stack["media"], media_root=tmp_path, policy=_small_policy())
    service.initialize()
    spec = service.plan(package_job_id=package_job_id, image_artifact_ids=(image_id,))
    job = service.enqueue(spec, priority=130)
    result = service.run_next()

    assert result is not None and result.status == JobStatus.COMPLETED
    assert result.job_id == job.job_id
    assert result.width == 360 and result.height == 640
    assert result.audio_stream_present is False
    assert result.output_uri is not None and (tmp_path / result.output_uri).is_file()
    assert (tmp_path / result.output_uri).read_bytes()[4:8] == b"ftyp"
    snapshot = service.snapshot()
    assert snapshot["job_count"] == 1
    assert snapshot["artifact_count"] == 3
    assert snapshot["provider_execution_count"] == 1
    assert snapshot["video_model_dependency"] is False
    assert snapshot["guaranteed_motion_story_fallback"] is True
    assert _canonical_snapshot(stack) == before
