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
from livingworld.underreach_media_foundation import (
    JobStatus,
    MediaPersistence,
    MediaProviderRouter,
    ProviderDescriptor,
    ProviderKind,
    ProviderPolicy,
    ProviderRequest,
)
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
    make_sound_asset,
)
from livingworld.underreach_parties_alliances_leadership import PartiesAlliancesLeadershipService
from livingworld.underreach_rivalry_betrayal_social_conflict import RivalryBetrayalSocialConflictService
from livingworld.underreach_social_intent_execution import SocialIntentExecutionService
from livingworld.underreach_social_memory_evolution import SocialMemoryEvolutionService


PROOF_PROTOCOL = "underreach.narration-captions-audio-proof.v1"
IDS = [f"descender_{index:03d}" for index in range(6)]


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


def _build(seed: str, database_url: str):
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

    prior = lifecycle.record_event(
        descent,
        "BETRAYAL",
        "30.5.8 proof prior social event.",
        actor_ids=IDS[:2],
        location_id=descent.participants[IDS[0]].current_location_id,
        data={"danger": 0.6, "state_changes": {"prior": True}},
    )
    if not memory.process_event(descent, prior).processed:
        raise RuntimeError("30.5.8 proof prior social memory failed")
    event = lifecycle.record_event(
        descent,
        "NEAR_DEATH_BETRAYAL_RELIC_COMEBACK",
        "30.5.8 proof canonical narrative source.",
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
    if not memory.process_event(descent, event).processed:
        raise RuntimeError("30.5.8 proof high-signal social memory failed")
    envelope = exporter.export_event(descent, event.id)
    media.register_envelope(envelope)
    evaluation = detector.evaluate(envelope)
    if not evaluation.selected:
        raise RuntimeError("30.5.8 proof source did not become a highlight")
    chronicle.process(envelope)
    chapter = chronicle.list_chapters(delver_id=IDS[0])[0]
    event_type = next(
        fact for fact in envelope.allowed_facts if fact.fact_id in chapter.allowed_fact_ids and fact.predicate == "event_type"
    )
    prose = "The recorded event was NEAR_DEATH_BETRAYAL_RELIC_COMEBACK. The silence felt heavier afterward."
    draft = verifier.register_draft(
        chapter_id=chapter.chapter_id,
        prose=prose,
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
        raise RuntimeError("30.5.8 proof narrative is not REVIEW_READY")
    return canonical, descent, media, detector, chronicle, verifier, draft, verification


def _paid_probe(duration_seconds: float) -> dict:
    paid = ProviderDescriptor(
        provider_id="proof_paid_voice",
        kind=ProviderKind.VOICE,
        local=False,
        paid=True,
        capability_flags=("headless_voice", "wav_output"),
        deterministic_seed=True,
        max_duration_seconds=300.0,
        estimated_cost_microusd=1000,
        quality_rank=90,
    )
    request = ProviderRequest(
        kind=ProviderKind.VOICE,
        required_flags=("headless_voice", "wav_output"),
        paid_allowed=True,
        explicit_paid_authorization=True,
        deterministic_seed_required=True,
        min_duration_seconds=duration_seconds,
    )
    blocked_router = MediaProviderRouter()
    blocked_router.register(paid)
    blocked = blocked_router.select(
        request,
        ProviderPolicy(local_only=False, cloud_allowed=True, allow_paid=False, daily_paid_budget_microusd=0),
    )
    allowed_router = MediaProviderRouter()
    allowed_router.register(paid)
    allowed = allowed_router.select(
        request,
        ProviderPolicy(
            local_only=False,
            cloud_allowed=True,
            allow_paid=True,
            require_explicit_paid_policy=True,
            daily_paid_budget_microusd=5000,
        ),
    )
    return {
        "paid_blocked_by_default": not blocked.selected,
        "paid_selected_with_all_gates": allowed.selected and allowed.provider_id == paid.provider_id,
    }


def generate(output: Path, *, seed: str) -> dict:
    output.parent.mkdir(parents=True, exist_ok=True)
    database_path = output.with_suffix(".sqlite3")
    if database_path.exists():
        database_path.unlink()
    database_url = f"sqlite:///{database_path.as_posix()}"
    output_root = output.parent / "audio-output"

    canonical, descent, media, detector, chronicle, verifier, draft, verification = _build(seed, database_url)
    canonical_before = _canonical_snapshot(canonical, descent)

    music = make_sound_asset(
        asset_id="proof_music_001",
        kind=SoundAssetKind.MUSIC,
        relative_uri="library/music/proof-dungeon.wav",
        license_label="local-royalty-safe",
    )
    success_policy = AudioProductionPolicy(milliseconds_per_word=300, minimum_caption_ms=800)
    service = NarrationCaptionsAudioService(
        media,
        verifier=verifier,
        providers=[DeterministicLocalWavProvider()],
        output_root=output_root,
        policy=success_policy,
    )
    service.initialize()
    spec = service.plan(verification.verification_id, sound_assets=(music,))
    package_job, voice_job = service.enqueue(spec, package_priority=120, voice_priority=110)
    if voice_job is None:
        raise RuntimeError("30.5.8 proof did not create voice job")
    package_result = service.run_next()
    if package_result is None or not package_result.caption_only_ready:
        raise RuntimeError("30.5.8 proof did not create caption-first package")

    crash_lease = media.claim_next("30-5-8-proof-crashed-worker")
    if crash_lease is None or crash_lease.job.job_id != voice_job.job_id:
        raise RuntimeError("30.5.8 proof failed to claim voice restart probe")

    reopened_media = MediaPersistence(database_url)
    reopened_media.initialize()
    recovered_count = reopened_media.recover_interrupted_jobs()
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
        policy=success_policy,
    )
    reopened.initialize()
    voice_result = reopened.run_next()
    if voice_result is None or voice_result.voice_status != JobStatus.COMPLETED:
        raise RuntimeError("30.5.8 proof voice recovery did not complete")

    degrade_policy = AudioProductionPolicy(
        milliseconds_per_word=340,
        minimum_caption_ms=850,
        voice_enabled=True,
    )
    degraded = NarrationCaptionsAudioService(
        reopened_media,
        verifier=reopened_verifier,
        providers=[],
        output_root=output_root,
        policy=degrade_policy,
    )
    degraded.initialize()
    degrade_spec = degraded.plan(verification.verification_id)
    degrade_package, degrade_voice = degraded.enqueue(degrade_spec, package_priority=100, voice_priority=90)
    if degrade_voice is None or degrade_voice.status != JobStatus.HELD:
        raise RuntimeError("30.5.8 proof no-provider voice job was not held")
    degrade_result = degraded.run_next()
    if degrade_result is None or not degrade_result.caption_only_ready or degrade_result.package_status != JobStatus.COMPLETED:
        raise RuntimeError("30.5.8 proof caption-only degradation did not complete")

    snapshot_before_repeat = reopened.snapshot()
    reopened_spec = reopened.plan(verification.verification_id, sound_assets=(music,))
    repeat_package, repeat_voice = reopened.enqueue(reopened_spec, package_priority=120, voice_priority=110)
    snapshot_after_repeat = reopened.snapshot()

    media_snapshot = reopened_media.snapshot()
    audio_snapshot = reopened.snapshot()
    package_artifacts = [item for item in audio_snapshot["artifacts"] if item["job_id"] == package_job.job_id]
    voice_artifacts = [item for item in audio_snapshot["artifacts"] if item["job_id"] == voice_job.job_id]
    degrade_artifacts = [item for item in audio_snapshot["artifacts"] if item["job_id"] == degrade_package.job_id]
    wav = next(item for item in voice_artifacts if item["artifact_kind"] == "audio/wav")
    wav_path = output_root / wav["uri"]
    final_voice_job = reopened_media.get_job(voice_job.job_id)
    final_degrade_voice = reopened_media.get_job(degrade_voice.job_id)
    canonical_after = _canonical_snapshot(canonical, descent)

    body = {
        "protocol": PROOF_PROTOCOL,
        "slice_protocol": audio_snapshot["protocol"],
        "implementation_version": audio_snapshot["implementation_version"],
        "phase": audio_snapshot["phase"],
        "seed": seed,
        "authority_contract": {
            "authoritative": audio_snapshot["authoritative"],
            "canonical_owner": audio_snapshot["canonical_owner"],
            "presentation_can_mutate_simulation": audio_snapshot["presentation_can_mutate_simulation"],
            "unreal_dependency": audio_snapshot["unreal_dependency"],
            "speech_recognition_used": audio_snapshot["speech_recognition_used"],
            "audio_mixing_performed": audio_snapshot["audio_mixing_performed"],
            "caption_only_fallback_guaranteed": audio_snapshot["caption_only_fallback_guaranteed"],
            "required_cloud_api": audio_snapshot["required_cloud_api"],
            "required_paid_provider": audio_snapshot["required_paid_provider"],
        },
        "canonical": {
            "unchanged_during_audio_production": _same_canonical(canonical_before, canonical_after),
            "fingerprint": descent.fingerprint(),
            "state_digest": payload_digest(descent.model_dump(mode="json")),
            "ledger_digest": payload_digest([item.model_dump(mode="json") for item in canonical.replay_events(descent.id)]),
        },
        "verified_input": {
            "verification_id": verification.verification_id,
            "review_ready": verification.review_ready,
            "script_verbatim": spec.script == draft.prose,
            "captions_match_sentences": tuple(item.text for item in spec.caption_cues) == draft.sentences,
            "caption_count": len(spec.caption_cues),
            "sound_assets_royalty_safe": all(item.royalty_safe for item in spec.sound_assets),
            "sound_assets_not_mixed": spec.audio_mixing_performed is False,
        },
        "narrated": {
            "package_job_id": package_job.job_id,
            "voice_job_id": voice_job.job_id,
            "package_artifact_count": len(package_artifacts),
            "voice_artifact_count": len(voice_artifacts),
            "wav_exists": wav_path.exists(),
            "wav_signature": wav_path.read_bytes().startswith(b"RIFF") and b"WAVE" in wav_path.read_bytes()[:16] if wav_path.exists() else False,
            "provider_local": all(item["provider_id"] == "local_deterministic_wav" for item in audio_snapshot["provider_executions"]),
            "caption_fallback_retained": voice_result.caption_only_ready,
        },
        "degraded": {
            "package_job_id": degrade_package.job_id,
            "voice_job_id": degrade_voice.job_id,
            "package_completed": degrade_result.package_status == JobStatus.COMPLETED,
            "caption_only_ready": degrade_result.caption_only_ready,
            "caption_artifact_count": len(degrade_artifacts),
            "voice_held": final_degrade_voice is not None and final_degrade_voice.status == JobStatus.HELD,
            "voice_artifact_absent": not any(item["job_id"] == degrade_voice.job_id for item in audio_snapshot["artifacts"]),
        },
        "restart": {
            "recovered_count": recovered_count,
            "same_voice_job": voice_result.voice_job_id == voice_job.job_id,
            "attempt_count": final_voice_job.attempt_count if final_voice_job is not None else None,
            "completed": final_voice_job is not None and final_voice_job.status == JobStatus.COMPLETED,
        },
        "idempotency": {
            "repeat_package_same_job": repeat_package.job_id == package_job.job_id,
            "repeat_voice_same_job": repeat_voice is not None and repeat_voice.job_id == voice_job.job_id,
            "snapshot_equal_after_repeat": snapshot_before_repeat == snapshot_after_repeat,
        },
        "routing": _paid_probe(spec.duration_ms / 1000.0),
        "media": {
            "job_count": audio_snapshot["job_count"],
            "artifact_count": audio_snapshot["artifact_count"],
            "provider_execution_count": audio_snapshot["provider_execution_count"],
            "snapshot_digest": audio_snapshot["digest"],
            "job_digest": audio_snapshot["job_digest"],
            "artifact_digest": audio_snapshot["artifact_digest"],
            "provider_execution_digest": audio_snapshot["provider_execution_digest"],
            "media_snapshot_digest": media_snapshot["digest"],
        },
    }
    proof = {**body, "digest": payload_digest(body)}
    output.write_text(json.dumps(proof, indent=2, sort_keys=True), encoding="utf-8")
    return proof


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", default="underreach-30-5-8-narration-captions-audio-proof")
    args = parser.parse_args()
    proof = generate(Path(args.output), seed=args.seed)
    print(
        json.dumps(
            {
                "digest": proof["digest"],
                "jobs": proof["media"]["job_count"],
                "artifacts": proof["media"]["artifact_count"],
                "executions": proof["media"]["provider_execution_count"],
                "restart_attempts": proof["restart"]["attempt_count"],
                "caption_only": proof["degraded"]["caption_only_ready"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
