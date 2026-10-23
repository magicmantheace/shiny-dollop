from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.crawl_service import CrawlLifecycleService
from livingworld.runtime_checkpoint import canonical_json, payload_digest
from livingworld.underreach_brain_driven_descent import BrainDrivenDescentService
from livingworld.underreach_delver_chronicle_profile import DelverChronicleProfileService
from livingworld.underreach_ffmpeg_motion_story import (
    AutomatedFfmpegMotionStoryService,
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
    SoundAssetKind,
    deterministic_wav_bytes,
    make_sound_asset,
)
from livingworld.underreach_parties_alliances_leadership import PartiesAlliancesLeadershipService
from livingworld.underreach_presentation_identity import PresentationIdentityService
from livingworld.underreach_rivalry_betrayal_social_conflict import RivalryBetrayalSocialConflictService
from livingworld.underreach_social_intent_execution import SocialIntentExecutionService
from livingworld.underreach_social_memory_evolution import SocialMemoryEvolutionService


PROOF_PROTOCOL = "underreach.ffmpeg-motion-story-proof.v1"
IDS = [f"descender_{index:03d}" for index in range(8)]


def _canonical_snapshot(canonical, descent) -> dict:
    return {
        "state": descent.model_dump(mode="json"),
        "fingerprint": descent.fingerprint(),
        "history": list(descent.history_event_ids),
        "ledger": [item.model_dump(mode="json") for item in canonical.replay_events(descent.id)],
    }


def _same_canonical(left: dict, right: dict) -> bool:
    return (
        canonical_json(left["state"]) == canonical_json(right["state"])
        and left["fingerprint"] == right["fingerprint"]
        and left["history"] == right["history"]
        and left["ledger"] == right["ledger"]
    )


def _build(seed: str, database_url: str) -> dict:
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
        "30.5.9 proof prior social event.",
        actor_ids=IDS[:2],
        location_id=descent.participants[IDS[0]].current_location_id,
        data={"danger": 0.6, "state_changes": {"prior": True}},
    )
    if not memory.process_event(descent, prior).processed:
        raise RuntimeError("30.5.9 proof prior social memory failed")
    event = lifecycle.record_event(
        descent,
        "NEAR_DEATH_BETRAYAL_RELIC_COMEBACK",
        "30.5.9 proof canonical motion-story source.",
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
    if not memory.process_event(descent, event).processed:
        raise RuntimeError("30.5.9 proof high-signal social memory failed")
    envelope = exporter.export_event(descent, event.id)
    media.register_envelope(envelope)
    evaluation = detector.evaluate(envelope)
    if not evaluation.selected:
        raise RuntimeError("30.5.9 proof source did not become a highlight")
    chronicle.process(envelope)
    profile = chronicle.get_profile(descent.id, IDS[0])
    if profile is None:
        raise RuntimeError("30.5.9 proof profile missing")
    identities.ensure_identity(profile)
    chapter = next(item for item in chronicle.list_chapters(delver_id=IDS[0]) if item.chapter_id in profile.chapter_ids)
    event_type = next(
        fact for fact in envelope.allowed_facts if fact.fact_id in chapter.allowed_fact_ids and fact.predicate == "event_type"
    )
    draft = verifier.register_draft(
        chapter_id=chapter.chapter_id,
        prose="The recorded event was NEAR_DEATH_BETRAYAL_RELIC_COMEBACK. The silence felt heavier afterward.",
        writer_provider_id="local_qwen_proof",
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
    if verification.status != VerificationStatus.REVIEW_READY:
        raise RuntimeError("30.5.9 proof narrative is not REVIEW_READY")
    return {
        "canonical": canonical,
        "descent": descent,
        "media": media,
        "detector": detector,
        "chronicle": chronicle,
        "identities": identities,
        "verifier": verifier,
        "profile": profile,
        "chapter": chapter,
        "draft": draft,
        "verification": verification,
        "event": event,
        "envelope": envelope,
    }


def _image_inputs(stack: dict, root: Path) -> tuple[str, str]:
    service = HeadlessLocalImageProductionService(
        stack["media"],
        identities=stack["identities"],
        providers=[DeterministicLocalPngProvider()],
        output_root=root,
    )
    service.initialize()
    first_job = service.enqueue_scene(stack["profile"], stack["chapter"], priority=150, width=96, height=128)
    first = service.run_next()
    second_job = service.enqueue_scene(stack["profile"], stack["chapter"], priority=145, width=120, height=160)
    second = service.run_next()
    if first is None or second is None or first.status != JobStatus.COMPLETED or second.status != JobStatus.COMPLETED:
        raise RuntimeError("30.5.9 proof scene still generation failed")
    if first.artifact_id is None or second.artifact_id is None:
        raise RuntimeError("30.5.9 proof scene still artifact missing")
    if stack["media"].get_job(first_job.job_id).status != JobStatus.COMPLETED:
        raise RuntimeError("30.5.9 proof first image job not completed")
    if stack["media"].get_job(second_job.job_id).status != JobStatus.COMPLETED:
        raise RuntimeError("30.5.9 proof second image job not completed")
    return first.artifact_id, second.artifact_id


def _motion_policy() -> MotionStoryPolicy:
    return MotionStoryPolicy(
        width=360,
        height=640,
        fps=12,
        minimum_duration_seconds=4.0,
        maximum_duration_seconds=30.0,
        target_shot_seconds=2.0,
        minimum_shots=2,
        maximum_shots=4,
        transition_ms=150,
        video_fade_ms=100,
        audio_fade_in_ms=100,
        audio_fade_out_ms=200,
        preset="ultrafast",
        crf=28,
    )


def _reopen_verifier(media: MediaPersistence):
    detector = HighlightStoryArcService(media)
    detector.initialize()
    chronicle = DelverChronicleProfileService(media, highlights=detector)
    chronicle.initialize()
    verifier = NarrativeClaimVerificationService(media, chronicle=chronicle)
    verifier.initialize()
    return verifier


def generate(output: Path, *, seed: str) -> dict:
    output.parent.mkdir(parents=True, exist_ok=True)
    database_path = output.with_suffix(".sqlite3")
    if database_path.exists():
        database_path.unlink()
    database_url = f"sqlite:///{database_path.as_posix()}"
    media_root = output.parent / f"{output.stem}-media"
    if media_root.exists():
        shutil.rmtree(media_root)
    media_root.mkdir(parents=True, exist_ok=True)

    stack = _build(seed, database_url)
    canonical_before = _canonical_snapshot(stack["canonical"], stack["descent"])
    image_artifact_ids = _image_inputs(stack, media_root)

    music = make_sound_asset(
        asset_id="proof_music_001",
        kind=SoundAssetKind.MUSIC,
        relative_uri="library/music/proof-motion-bed.wav",
        license_label="local-royalty-safe",
    )
    music_path = media_root / music.relative_uri
    music_path.parent.mkdir(parents=True, exist_ok=True)
    music_path.write_bytes(deterministic_wav_bytes(duration_ms=4000, sample_rate=22050, seed=3059))

    narrated_audio = NarrationCaptionsAudioService(
        stack["media"],
        verifier=stack["verifier"],
        providers=[DeterministicLocalWavProvider()],
        output_root=media_root,
        policy=AudioProductionPolicy(voice_enabled=True, milliseconds_per_word=220, minimum_caption_ms=600),
    )
    narrated_audio.initialize()
    narrated_package_spec = narrated_audio.plan(stack["verification"].verification_id, sound_assets=(music,))
    narrated_package_job, narrated_voice_job = narrated_audio.enqueue(
        narrated_package_spec, package_priority=140, voice_priority=135
    )
    if narrated_voice_job is None:
        raise RuntimeError("30.5.9 proof narrated voice job missing")
    package_result = narrated_audio.run_next()
    voice_result = narrated_audio.run_next()
    if package_result is None or package_result.package_status != JobStatus.COMPLETED:
        raise RuntimeError("30.5.9 proof narrated caption package failed")
    if voice_result is None or voice_result.voice_status != JobStatus.COMPLETED:
        raise RuntimeError("30.5.9 proof narrated voice failed")

    policy = _motion_policy()
    motion = AutomatedFfmpegMotionStoryService(stack["media"], media_root=media_root, policy=policy)
    motion.initialize()
    narrated_spec = motion.plan(
        package_job_id=narrated_package_job.job_id,
        image_artifact_ids=image_artifact_ids,
    )
    narrated_job = motion.enqueue(narrated_spec, priority=130)

    crash_lease = stack["media"].claim_next("30-5-9-proof-crashed-ffmpeg-worker")
    if crash_lease is None or crash_lease.job.job_id != narrated_job.job_id:
        raise RuntimeError("30.5.9 proof failed to lease narrated motion-story restart probe")

    reopened_media = MediaPersistence(database_url)
    reopened_media.initialize()
    recovered_count = reopened_media.recover_interrupted_jobs()
    reopened_motion = AutomatedFfmpegMotionStoryService(reopened_media, media_root=media_root, policy=policy)
    reopened_motion.initialize()
    narrated_result = reopened_motion.run_next()
    if narrated_result is None or narrated_result.status != JobStatus.COMPLETED:
        raise RuntimeError("30.5.9 proof recovered narrated motion story did not complete")

    reopened_verifier = _reopen_verifier(reopened_media)
    caption_audio = NarrationCaptionsAudioService(
        reopened_media,
        verifier=reopened_verifier,
        providers=[],
        output_root=media_root,
        policy=AudioProductionPolicy(voice_enabled=False, milliseconds_per_word=240, minimum_caption_ms=620),
    )
    caption_audio.initialize()
    caption_package_spec = caption_audio.plan(stack["verification"].verification_id)
    caption_package_job, caption_voice_job = caption_audio.enqueue(caption_package_spec, package_priority=100)
    if caption_voice_job is not None:
        raise RuntimeError("30.5.9 proof caption-only package unexpectedly created voice job")
    caption_package_result = caption_audio.run_next()
    if caption_package_result is None or caption_package_result.package_status != JobStatus.COMPLETED:
        raise RuntimeError("30.5.9 proof caption-only package failed")

    caption_spec = reopened_motion.plan(
        package_job_id=caption_package_job.job_id,
        image_artifact_ids=image_artifact_ids,
    )
    caption_job = reopened_motion.enqueue(caption_spec, priority=90)
    caption_result = reopened_motion.run_next()
    if caption_result is None or caption_result.status != JobStatus.COMPLETED:
        raise RuntimeError("30.5.9 proof caption-only motion story did not complete")

    before_repeat = reopened_motion.snapshot()
    repeat_job = reopened_motion.enqueue(narrated_spec, priority=130)
    after_repeat = reopened_motion.snapshot()

    final_narrated_job = reopened_media.get_job(narrated_job.job_id)
    final_caption_job = reopened_media.get_job(caption_job.job_id)
    motion_snapshot = reopened_motion.snapshot()
    canonical_after = _canonical_snapshot(stack["canonical"], stack["descent"])

    if narrated_result.output_uri is None or narrated_result.manifest_uri is None:
        raise RuntimeError("30.5.9 proof narrated output paths missing")
    if caption_result.output_uri is None or caption_result.manifest_uri is None:
        raise RuntimeError("30.5.9 proof caption-only output paths missing")
    narrated_video = media_root / narrated_result.output_uri
    caption_video = media_root / caption_result.output_uri
    narrated_manifest = json.loads((media_root / narrated_result.manifest_uri).read_text(encoding="utf-8"))
    caption_manifest = json.loads((media_root / caption_result.manifest_uri).read_text(encoding="utf-8"))

    semantic = {
        "seed": seed,
        "narrated_story_id": narrated_spec.story_id,
        "narrated_spec_digest": narrated_spec.digest,
        "caption_story_id": caption_spec.story_id,
        "caption_spec_digest": caption_spec.digest,
        "narrated_job_id": narrated_job.job_id,
        "caption_job_id": caption_job.job_id,
        "narrated_attempt_count": final_narrated_job.attempt_count if final_narrated_job else None,
        "caption_attempt_count": final_caption_job.attempt_count if final_caption_job else None,
        "motion_job_count": motion_snapshot["job_count"],
        "motion_artifact_count": motion_snapshot["artifact_count"],
        "motion_execution_count": motion_snapshot["provider_execution_count"],
        "narrated_dimensions": [narrated_result.width, narrated_result.height],
        "caption_dimensions": [caption_result.width, caption_result.height],
        "narrated_audio": narrated_result.audio_stream_present,
        "caption_audio": caption_result.audio_stream_present,
        "canonical_unchanged": _same_canonical(canonical_before, canonical_after),
        "restart_recovered": recovered_count,
        "repeat_same_job": repeat_job.job_id == narrated_job.job_id,
        "repeat_snapshot_equal": before_repeat == after_repeat,
    }

    body = {
        "protocol": PROOF_PROTOCOL,
        "slice_protocol": motion_snapshot["protocol"],
        "implementation_version": motion_snapshot["implementation_version"],
        "phase": motion_snapshot["phase"],
        "seed": seed,
        "authority_contract": {
            "authoritative": motion_snapshot["authoritative"],
            "canonical_owner": motion_snapshot["canonical_owner"],
            "presentation_can_mutate_simulation": motion_snapshot["presentation_can_mutate_simulation"],
            "unreal_dependency": motion_snapshot["unreal_dependency"],
            "video_model_dependency": motion_snapshot["video_model_dependency"],
            "video_diffusion_used": motion_snapshot["video_diffusion_used"],
            "required_cloud_api": motion_snapshot["required_cloud_api"],
            "required_paid_provider": motion_snapshot["required_paid_provider"],
            "guaranteed_motion_story_fallback": motion_snapshot["guaranteed_motion_story_fallback"],
        },
        "canonical": {
            "unchanged_during_motion_story_production": _same_canonical(canonical_before, canonical_after),
            "fingerprint": stack["descent"].fingerprint(),
            "state_digest": payload_digest(stack["descent"].model_dump(mode="json")),
            "ledger_digest": payload_digest(
                [item.model_dump(mode="json") for item in stack["canonical"].replay_events(stack["descent"].id)]
            ),
        },
        "inputs": {
            "scene_image_count": len(image_artifact_ids),
            "scene_image_artifact_ids": list(image_artifact_ids),
            "verified_review_ready": stack["verification"].review_ready,
            "source_event_ids": list(narrated_spec.source_event_ids),
            "source_envelope_ids": list(narrated_spec.source_envelope_ids),
            "music_asset_resolved": len(narrated_spec.sound_assets) == 1,
        },
        "narrated": {
            "story_id": narrated_spec.story_id,
            "job_id": narrated_job.job_id,
            "completed": narrated_result.status == JobStatus.COMPLETED,
            "mp4_exists": narrated_video.exists(),
            "mp4_signature": narrated_video.read_bytes()[4:8] == b"ftyp" if narrated_video.exists() else False,
            "output_sha256": narrated_result.output_digest,
            "width": narrated_result.width,
            "height": narrated_result.height,
            "duration_ms": narrated_result.duration_ms,
            "audio_stream_present": narrated_result.audio_stream_present,
            "captions_burned": narrated_manifest["captions_burned"],
            "narration_mode": narrated_manifest["narration_mode"],
            "loudness_normalization": narrated_manifest["loudness_normalization"],
            "music_ducking": narrated_manifest["music_ducking"],
            "audio_fades": narrated_manifest["audio_fades"],
            "audio_mixing": narrated_manifest["audio_mixing"],
            "video_model_dependency": narrated_manifest["video_model_dependency"],
            "ffmpeg_provider_id": narrated_manifest["ffmpeg_provider_id"],
            "ffmpeg_command_plan_digest": narrated_manifest["ffmpeg_command_plan_digest"],
        },
        "caption_only": {
            "story_id": caption_spec.story_id,
            "job_id": caption_job.job_id,
            "completed": caption_result.status == JobStatus.COMPLETED,
            "mp4_exists": caption_video.exists(),
            "mp4_signature": caption_video.read_bytes()[4:8] == b"ftyp" if caption_video.exists() else False,
            "output_sha256": caption_result.output_digest,
            "width": caption_result.width,
            "height": caption_result.height,
            "duration_ms": caption_result.duration_ms,
            "audio_stream_present": caption_result.audio_stream_present,
            "captions_burned": caption_manifest["captions_burned"],
            "narration_mode": caption_manifest["narration_mode"],
            "video_model_dependency": caption_manifest["video_model_dependency"],
            "ffmpeg_provider_id": caption_manifest["ffmpeg_provider_id"],
        },
        "restart": {
            "recovered_count": recovered_count,
            "same_job": narrated_result.job_id == narrated_job.job_id,
            "attempt_count": final_narrated_job.attempt_count if final_narrated_job else None,
            "completed": final_narrated_job is not None and final_narrated_job.status == JobStatus.COMPLETED,
        },
        "idempotency": {
            "repeat_same_job": repeat_job.job_id == narrated_job.job_id,
            "snapshot_equal_after_repeat": before_repeat == after_repeat,
        },
        "media": {
            "job_count": motion_snapshot["job_count"],
            "artifact_count": motion_snapshot["artifact_count"],
            "provider_execution_count": motion_snapshot["provider_execution_count"],
            "job_digest": motion_snapshot["job_digest"],
        },
        "semantic_projection": semantic,
    }
    body["digest"] = payload_digest(semantic)
    output.write_text(json.dumps(body, indent=2, sort_keys=True), encoding="utf-8")
    print(
        json.dumps(
            {
                "digest": body["digest"],
                "motion_jobs": body["media"]["job_count"],
                "artifacts": body["media"]["artifact_count"],
                "executions": body["media"]["provider_execution_count"],
                "restart_attempts": body["restart"]["attempt_count"],
            },
            sort_keys=True,
        )
    )
    return body


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", required=True)
    args = parser.parse_args()
    generate(Path(args.output), seed=args.seed)


if __name__ == "__main__":
    main()
