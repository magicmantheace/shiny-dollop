from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess

from sqlalchemy.orm import Session

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.underreach_brain_driven_descent import BrainDrivenDescentService
from livingworld.runtime_checkpoint import canonical_json, payload_digest
from livingworld.underreach_ffmpeg_motion_story import JOB_TYPE as MOTION_STORY_JOB_TYPE
from livingworld.underreach_headless_local_image_production import JOB_TYPE as IMAGE_JOB_TYPE, deterministic_png_bytes
from livingworld.underreach_highlight_story_arc import (
    HighlightScore,
    HighlightStoryArcService,
    MediaHighlight,
    MediaHighlightRow,
    tier_for_score,
    validate_highlight,
)
from livingworld.underreach_local_video_enhancement import (
    DeterministicLocalI2VProvider,
    LocalVideoEnhancementService,
    VideoEnhancementPolicy,
    VideoRenderRequest,
)
from livingworld.underreach_media_foundation import (
    JobStatus,
    MediaPersistence,
    MediaProviderRouter,
    ProviderDescriptor,
    ProviderKind,
    ProviderPolicy,
    ProviderRequest,
)


PROOF_PROTOCOL = "underreach.local-video-enhancement-proof.v1"
WIDTH = 180
HEIGHT = 320
FPS = 10
CHAPTER_ID = "chronicle_chapter_30_5_10_proof"
ENVELOPE_ID = "media_envelope_30_5_10_proof"
EVENT_ID = "crawl_event_30_5_10_proof"
STORY_ID = "motion_story_30_5_10_proof"


def _canonical_snapshot(canonical: CrawlPersistence, descent) -> dict:
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


def _ffmpeg() -> tuple[str, str]:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError("30.5.10 proof requires local ffmpeg and ffprobe")
    return ffmpeg, ffprobe


def _write_mp4(path: Path, image: Path, *, duration_seconds: float = 3.2) -> None:
    ffmpeg, _ = _ffmpeg()
    path.parent.mkdir(parents=True, exist_ok=True)
    process = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-loop",
            "1",
            "-framerate",
            str(FPS),
            "-i",
            str(image),
            "-vf",
            f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,crop={WIDTH}:{HEIGHT},format=yuv420p",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "30",
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(FPS),
            "-threads",
            "1",
            "-map_metadata",
            "-1",
            "-metadata",
            "creation_time=1970-01-01T00:00:00Z",
            "-t",
            f"{duration_seconds:.3f}",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    if process.returncode != 0 or not path.is_file():
        raise RuntimeError(f"30.5.10 proof fallback MP4 generation failed: {process.stderr[-1000:]}")


def _completed_image(media: MediaPersistence, root: Path, index: int, *, prefix: str) -> tuple[str, str]:
    job = media.enqueue_job(job_type=IMAGE_JOB_TYPE, payload={"proof": prefix, "image": index}, priority=100)
    lease = media.claim_next(f"{prefix}-image-{index}")
    if lease is None or lease.job.job_id != job.job_id:
        raise RuntimeError("30.5.10 proof could not claim fixture image job")
    relative = f"fixture/{prefix}/images/scene-{index}.png"
    payload = deterministic_png_bytes(WIDTH, HEIGHT, f"30.5.10:{prefix}:{index}")
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    artifact_id = media.record_artifact(
        job_id=job.job_id,
        artifact_kind="image/png",
        uri=relative,
        digest=sha256(payload).hexdigest(),
        metadata={
            "chapter_id": CHAPTER_ID,
            "source_envelope_id": ENVELOPE_ID,
            "source_event_ids": [EVENT_ID],
            "presentation_only": True,
        },
    )
    media.complete_job(job.job_id, resource_usage={"proof_fixture": True})
    return job.job_id, artifact_id


def _insert_highlight(detector: HighlightStoryArcService, score_total: int) -> MediaHighlight:
    components = (
        dict(danger=20, rarity=15, social_stakes=20, character_significance=12, outcome_reversal=10, continuity=15, visual_potential=5)
        if score_total == 97
        else dict(danger=20, rarity=15, social_stakes=20, character_significance=10, outcome_reversal=10, continuity=12, visual_potential=5)
    )
    score = HighlightScore(**components, total=score_total)
    policy = detector.policy
    highlight_id = f"media_highlight_{sha256(f'{ENVELOPE_ID}:{policy.digest}'.encode('utf-8')).hexdigest()[:24]}"
    body = {
        "protocol": "underreach.highlight-story-arc.v1",
        "implementation_version": "30.5.3",
        "phase": "30.5",
        "highlight_id": highlight_id,
        "envelope_id": ENVELOPE_ID,
        "crawl_id": "descent_30_5_10_proof",
        "source_event_ids": [EVENT_ID],
        "delver_ids": ["descender_000"],
        "score": score.model_dump(mode="json"),
        "output_tier": tier_for_score(score_total, policy).value,
        "reason_codes": ["proof:30.5.10"],
        "arc_ids": [],
        "policy_digest": policy.digest,
        "presentation_can_mutate_simulation": False,
        "llm_decision_used": False,
        "unreal_dependency": False,
        "provider_invocation_used": False,
    }
    highlight = MediaHighlight.model_validate({**body, "digest": payload_digest(body)})
    validate_highlight(highlight, policy)
    with Session(detector.media.engine) as session:
        session.add(
            MediaHighlightRow(
                highlight_id=highlight.highlight_id,
                envelope_id=highlight.envelope_id,
                crawl_id=highlight.crawl_id,
                policy_digest=highlight.policy_digest,
                total_score=highlight.score.total,
                output_tier=highlight.output_tier.value,
                payload=highlight.model_dump(mode="json"),
                digest=highlight.digest,
            )
        )
        session.commit()
    return highlight


def _fixture(database_url: str, root: Path, *, score_total: int, prefix: str) -> dict:
    media = MediaPersistence(database_url)
    media.initialize()
    detector = HighlightStoryArcService(media)
    detector.initialize()
    pairs = [_completed_image(media, root, index, prefix=prefix) for index in range(3)]
    image_job_ids = [item[0] for item in pairs]
    image_artifact_ids = [item[1] for item in pairs]
    artifacts = {item["artifact_id"]: item for item in media.snapshot()["artifacts"]}

    motion_job = media.enqueue_job(
        job_type=MOTION_STORY_JOB_TYPE,
        payload={"proof": "accepted-30.5.9-surface", "prefix": prefix},
        dependencies=tuple(image_job_ids),
        priority=100,
    )
    lease = media.claim_next(f"{prefix}-motion-story")
    if lease is None or lease.job.job_id != motion_job.job_id:
        raise RuntimeError("30.5.10 proof could not claim motion-story fixture")
    fallback_rel = f"fixture/{prefix}/motion-story/motion-story.mp4"
    fallback_path = root / fallback_rel
    first_image = root / artifacts[image_artifact_ids[0]]["uri"]
    _write_mp4(fallback_path, first_image)
    fallback_bytes = fallback_path.read_bytes()
    fallback_digest = sha256(fallback_bytes).hexdigest()
    shots = [
        {
            "index": index,
            "source_image_artifact_id": artifact_id,
            "pattern": "push_in",
            "timeline_start_ms": index * 3000,
            "duration_ms": 3000,
            "transition_ms": 0,
            "deterministic_seed": index + 1,
            "digest": f"proof-shot-{index}",
        }
        for index, artifact_id in enumerate(image_artifact_ids)
    ]
    manifest_body = {
        "protocol": "underreach.ffmpeg-motion-story.v1",
        "implementation_version": "30.5.9",
        "phase": "30.5",
        "story_id": f"{STORY_ID}_{prefix}",
        "job_id": motion_job.job_id,
        "attempt_id": lease.attempt_id,
        "chapter_id": CHAPTER_ID,
        "image_artifact_ids": image_artifact_ids,
        "source_envelope_ids": [ENVELOPE_ID],
        "source_event_ids": [EVENT_ID],
        "shots": shots,
        "duration_ms": 9000,
        "output_width": WIDTH,
        "output_height": HEIGHT,
        "fps": FPS,
        "video_model_dependency": False,
        "video_diffusion_used": False,
        "output_uri": fallback_rel,
        "output_sha256": fallback_digest,
        "canonical_authority": False,
        "presentation_can_mutate_simulation": False,
        "unreal_dependency": False,
        "cloud_api_required": False,
        "paid_provider_required": False,
    }
    manifest_bytes = canonical_json(manifest_body).encode("utf-8")
    manifest_rel = f"fixture/{prefix}/motion-story/motion-story.json"
    manifest_path = root / manifest_rel
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_bytes(manifest_bytes)
    fallback_artifact_id = media.record_artifact(
        job_id=motion_job.job_id,
        artifact_kind="video/mp4",
        uri=fallback_rel,
        digest=fallback_digest,
        metadata={
            "story_id": manifest_body["story_id"],
            "chapter_id": CHAPTER_ID,
            "source_event_ids": [EVENT_ID],
            "source_envelope_ids": [ENVELOPE_ID],
            "presentation_only": True,
        },
    )
    manifest_artifact_id = media.record_artifact(
        job_id=motion_job.job_id,
        artifact_kind="application/json",
        uri=manifest_rel,
        digest=sha256(manifest_bytes).hexdigest(),
        metadata={"story_id": manifest_body["story_id"], "video_artifact_id": fallback_artifact_id, "presentation_only": True},
    )
    media.complete_job(motion_job.job_id, resource_usage={"proof_fixture": True})
    highlight = _insert_highlight(detector, score_total)
    return {
        "media": media,
        "detector": detector,
        "root": root,
        "motion_job_id": motion_job.job_id,
        "fallback_artifact_id": fallback_artifact_id,
        "manifest_artifact_id": manifest_artifact_id,
        "fallback_path": fallback_path,
        "highlight": highlight,
    }


class FailingVideoProvider:
    def __init__(self) -> None:
        self._descriptor = ProviderDescriptor(
            provider_id="proof_failing_i2v",
            kind=ProviderKind.VIDEO,
            local=True,
            paid=False,
            capability_flags=("headless_video", "mp4_output", "short_shot"),
            deterministic_seed=True,
            image_to_video=True,
            max_width=1080,
            max_height=1920,
            max_duration_seconds=5.0,
            estimated_vram_mb=2048,
            estimated_runtime_seconds=1.0,
            quality_rank=10,
        )

    @property
    def descriptor(self) -> ProviderDescriptor:
        return self._descriptor

    def animate(self, request: VideoRenderRequest):
        raise RuntimeError("injected proof video failure")


def _routing_probe() -> dict:
    paid = ProviderDescriptor(
        provider_id="proof_paid_i2v",
        kind=ProviderKind.VIDEO,
        local=False,
        paid=True,
        capability_flags=("headless_video", "mp4_output", "short_shot"),
        deterministic_seed=True,
        image_to_video=True,
        max_width=1080,
        max_height=1920,
        max_duration_seconds=5.0,
        estimated_vram_mb=4096,
        estimated_runtime_seconds=2.0,
        estimated_cost_microusd=5000,
        quality_rank=90,
    )
    over_vram = ProviderDescriptor(
        provider_id="proof_16gb_i2v",
        kind=ProviderKind.VIDEO,
        local=True,
        paid=False,
        capability_flags=("headless_video", "mp4_output", "short_shot"),
        deterministic_seed=True,
        image_to_video=True,
        max_width=1080,
        max_height=1920,
        max_duration_seconds=5.0,
        estimated_vram_mb=16 * 1024,
        estimated_runtime_seconds=2.0,
        quality_rank=99,
    )
    request = ProviderRequest(
        kind=ProviderKind.VIDEO,
        required_flags=("headless_video", "mp4_output", "short_shot"),
        paid_allowed=True,
        explicit_paid_authorization=True,
        deterministic_seed_required=True,
        image_to_video_required=True,
        min_width=WIDTH,
        min_height=HEIGHT,
        min_duration_seconds=3.0,
        max_vram_mb=12 * 1024,
    )
    paid_router = MediaProviderRouter()
    paid_router.register(paid)
    blocked = paid_router.select(
        request,
        ProviderPolicy(local_only=False, cloud_allowed=True, allow_paid=False, daily_paid_budget_microusd=0, max_vram_mb=12 * 1024),
    )
    allowed = paid_router.select(
        request,
        ProviderPolicy(
            local_only=False,
            cloud_allowed=True,
            allow_paid=True,
            require_explicit_paid_policy=True,
            daily_paid_budget_microusd=10000,
            max_vram_mb=12 * 1024,
        ),
    )
    vram_router = MediaProviderRouter()
    vram_router.register(over_vram)
    vram = vram_router.select(
        request.model_copy(update={"paid_allowed": False, "explicit_paid_authorization": False, "local_required": True}),
        ProviderPolicy(local_only=True, cloud_allowed=False, allow_paid=False, max_vram_mb=12 * 1024),
    )
    return {
        "paid_blocked_by_default": not blocked.selected,
        "paid_selected_with_all_gates": allowed.selected and allowed.provider_id == paid.provider_id,
        "sixteen_gb_provider_blocked": not vram.selected,
    }


def _budget_probe(base: Path) -> dict:
    database = base / "budget.sqlite3"
    if database.exists():
        database.unlink()
    root = base / "budget-media"
    stack = _fixture(f"sqlite:///{database.as_posix()}", root, score_total=92, prefix="budget")
    service = LocalVideoEnhancementService(
        stack["media"],
        highlights=stack["detector"],
        providers=[DeterministicLocalI2VProvider()],
        media_root=root,
        policy=VideoEnhancementPolicy(max_gpu_hours_per_window=0.001),
    )
    service.initialize()
    plan = service.plan(motion_story_job_id=stack["motion_job_id"])
    jobs = service.enqueue_plan(plan, gpu_window_key="proof-tiny-budget")
    job = stack["media"].get_job(jobs[0].job_id)
    return {
        "fallback_exists": stack["fallback_path"].is_file(),
        "job_held": job is not None and job.status == JobStatus.HELD,
        "reason_code": job.last_reason_code if job is not None else None,
        "reservation_count": service.scheduler_snapshot()["reservation_count"],
    }


def _failure_probe(base: Path) -> dict:
    database = base / "failure.sqlite3"
    if database.exists():
        database.unlink()
    root = base / "failure-media"
    stack = _fixture(f"sqlite:///{database.as_posix()}", root, score_total=92, prefix="failure")
    service = LocalVideoEnhancementService(
        stack["media"],
        highlights=stack["detector"],
        providers=[FailingVideoProvider()],
        media_root=root,
    )
    service.initialize()
    plan = service.plan(motion_story_job_id=stack["motion_job_id"])
    job = service.enqueue_plan(plan, gpu_window_key="proof-failure-day")[0]
    results = [service.run_next(), service.run_next(), service.run_next()]
    final = stack["media"].get_job(job.job_id)
    return {
        "statuses": [item.status.value if item is not None else None for item in results],
        "attempt_count": final.attempt_count if final is not None else None,
        "final_failed": final is not None and final.status == JobStatus.FAILED,
        "fallback_exists": stack["fallback_path"].is_file(),
        "fallback_retained_each_attempt": all(item is not None and item.fallback_motion_story_ready for item in results),
        "provider_execution_count": service.snapshot()["provider_execution_count"],
        "gpu_lock_clear": service.scheduler_snapshot()["active_job_id"] is None,
    }


def generate(output: Path, *, seed: str) -> dict:
    _ffmpeg()
    output.parent.mkdir(parents=True, exist_ok=True)
    database = output.with_suffix(".sqlite3")
    if database.exists():
        database.unlink()
    root = output.parent / "video-output"

    canonical = CrawlPersistence("sqlite://")
    canonical.initialize()
    brain = BrainDrivenDescentService(canonical)
    descent = brain.create(seed=seed, descender_ids=[f"descender_{index:03d}" for index in range(6)], stratum_count=3)
    brain.start(descent)
    canonical_before = _canonical_snapshot(canonical, descent)

    stack = _fixture(f"sqlite:///{database.as_posix()}", root, score_total=97, prefix="main")
    policy = VideoEnhancementPolicy(max_gpu_hours_per_window=0.01)
    provider = DeterministicLocalI2VProvider()
    service = LocalVideoEnhancementService(
        stack["media"],
        highlights=stack["detector"],
        providers=[provider],
        media_root=root,
        policy=policy,
    )
    service.initialize()
    plan = service.plan(motion_story_job_id=stack["motion_job_id"])
    jobs = service.enqueue_plan(plan, gpu_window_key="proof-main-day")
    if len(jobs) != 3:
        raise RuntimeError("30.5.10 cinematic proof did not schedule three short shots")

    crash = stack["media"].claim_next("30-5-10-proof-crashed-worker")
    if crash is None or crash.job.job_id != jobs[0].job_id:
        raise RuntimeError("30.5.10 proof failed to claim restart target")
    if not service._acquire_gpu(crash.job.job_id):
        raise RuntimeError("30.5.10 proof failed to acquire GPU lock before simulated crash")

    reopened_media = MediaPersistence(f"sqlite:///{database.as_posix()}")
    reopened_media.initialize()
    reopened_detector = HighlightStoryArcService(reopened_media)
    reopened_detector.initialize()
    reopened = LocalVideoEnhancementService(
        reopened_media,
        highlights=reopened_detector,
        providers=[DeterministicLocalI2VProvider()],
        media_root=root,
        policy=policy,
    )
    reopened.initialize()
    recovered_media_jobs = reopened_media.recover_interrupted_jobs()
    recovered_gpu_locks = reopened.recover_gpu_scheduler()
    results = []
    while True:
        item = reopened.run_next()
        if item is None:
            break
        results.append(item)
    if len(results) != 3 or any(item.status != JobStatus.COMPLETED for item in results):
        raise RuntimeError("30.5.10 proof did not complete all scheduled local video shots")

    snapshot_before_repeat = reopened.snapshot()
    repeat_plan = reopened.plan(motion_story_job_id=stack["motion_job_id"])
    repeat_jobs = reopened.enqueue_plan(repeat_plan, gpu_window_key="proof-main-day")
    snapshot_after_repeat = reopened.snapshot()

    snapshot = reopened.snapshot()
    scheduler = reopened.scheduler_snapshot()
    video_artifacts = [item for item in snapshot["artifacts"] if item["artifact_kind"] == "video/mp4"]
    sidecars = [item for item in snapshot["artifacts"] if item["artifact_kind"] == "application/json"]
    output_files_exist = all((root / item["uri"]).is_file() for item in video_artifacts)
    fallback_still_exists = stack["fallback_path"].is_file()
    first_final = reopened_media.get_job(jobs[0].job_id)
    canonical_after = _canonical_snapshot(canonical, descent)

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
            "unreal_dependency": snapshot["unreal_dependency"],
            "required_cloud_api": snapshot["required_cloud_api"],
            "required_paid_provider": snapshot["required_paid_provider"],
            "motion_story_fallback_guaranteed": snapshot["motion_story_fallback_guaranteed"],
        },
        "canonical": {
            "unchanged_during_video_enhancement": _same_canonical(canonical_before, canonical_after),
            "fingerprint": descent.fingerprint(),
            "state_digest": payload_digest(descent.model_dump(mode="json")),
            "ledger_digest": payload_digest([item.model_dump(mode="json") for item in canonical.replay_events(descent.id)]),
        },
        "selection": {
            "eligible": plan.eligible,
            "highlight_score": plan.highlight_score,
            "treatment": plan.treatment.value,
            "selected_shot_count": plan.selected_shot_count,
            "shot_indexes": [item.source_shot.shot_index for item in plan.specs],
            "durations_ms": [item.source_shot.animation_duration_ms for item in plan.specs],
            "fallback_artifact_id": plan.fallback_artifact_id,
        },
        "production": {
            "completed_count": len(results),
            "video_artifact_count": len(video_artifacts),
            "sidecar_artifact_count": len(sidecars),
            "output_files_exist": output_files_exist,
            "fallback_still_exists": fallback_still_exists,
            "provider_local": all(item["provider_id"] == "local_deterministic_i2v" for item in snapshot["provider_executions"]),
            "provider_execution_count": snapshot["provider_execution_count"],
        },
        "restart": {
            "recovered_media_jobs": recovered_media_jobs,
            "recovered_gpu_locks": recovered_gpu_locks,
            "same_first_job": results[0].job_id == jobs[0].job_id,
            "first_attempt_count": first_final.attempt_count if first_final is not None else None,
            "gpu_lock_clear": scheduler["active_job_id"] is None,
        },
        "scheduler": {
            "serialized_gpu_work": scheduler["serialized_gpu_work"],
            "max_gpu_ms_per_window": scheduler["max_gpu_ms_per_window"],
            "max_retries_per_shot": scheduler["max_retries_per_shot"],
            "reservation_count": scheduler["reservation_count"],
            "all_completed": all(item["status"] == "completed" for item in scheduler["reservations"]),
            "reservation_digest": scheduler["reservation_digest"],
        },
        "idempotency": {
            "repeat_same_job_ids": [item.job_id for item in repeat_jobs] == [item.job_id for item in jobs],
            "snapshot_equal_after_repeat": snapshot_before_repeat == snapshot_after_repeat,
        },
        "budget": _budget_probe(output.parent),
        "failure": _failure_probe(output.parent),
        "routing": _routing_probe(),
        "media": {
            "job_count": snapshot["job_count"],
            "job_digest": snapshot["job_digest"],
            "artifact_count": snapshot["artifact_count"],
            "artifact_digest": snapshot["artifact_digest"],
            "provider_execution_count": snapshot["provider_execution_count"],
            "provider_execution_digest": snapshot["provider_execution_digest"],
            "snapshot_digest": snapshot["digest"],
        },
    }
    proof = {**body, "digest": payload_digest(body)}
    output.write_text(canonical_json(proof) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "digest": proof["digest"],
                "jobs": proof["media"]["job_count"],
                "clips": proof["production"]["video_artifact_count"],
                "gpu_reservations": proof["scheduler"]["reservation_count"],
                "restart_attempts": proof["restart"]["first_attempt_count"],
            },
            sort_keys=True,
        )
    )
    return proof


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", default="underreach-30-5-10-local-video-enhancement-proof")
    args = parser.parse_args()
    generate(Path(args.output), seed=args.seed)


if __name__ == "__main__":
    main()
