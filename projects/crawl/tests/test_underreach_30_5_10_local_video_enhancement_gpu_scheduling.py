from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess

import pytest
from sqlalchemy.orm import Session

from livingworld.runtime_checkpoint import canonical_json, payload_digest
from livingworld.underreach_ffmpeg_motion_story import JOB_TYPE as MOTION_STORY_JOB_TYPE
from livingworld.underreach_headless_local_image_production import JOB_TYPE as IMAGE_JOB_TYPE, deterministic_png_bytes
from livingworld.underreach_highlight_story_arc import (
    HighlightPolicy,
    HighlightScore,
    HighlightStoryArcService,
    MediaHighlight,
    MediaHighlightRow,
    tier_for_score,
    validate_highlight,
)
from livingworld.underreach_local_video_enhancement import (
    DeterministicLocalI2VProvider,
    EnhancementTreatment,
    LocalVideoEnhancementService,
    VideoEnhancementPolicy,
    VideoRenderRequest,
)
from livingworld.underreach_media_foundation import (
    JobStatus,
    MediaPersistence,
    ProviderDescriptor,
    ProviderKind,
    ProviderPolicy,
)


WIDTH = 180
HEIGHT = 320
FPS = 10
CHAPTER_ID = "chronicle_chapter_30_5_10_fixture"
ENVELOPE_ID = "media_envelope_30_5_10_fixture"
EVENT_ID = "crawl_event_30_5_10_fixture"
STORY_ID = "motion_story_30_5_10_fixture"


def _require_ffmpeg() -> tuple[str, str]:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        pytest.skip("30.5.10 focused video tests require ffmpeg/ffprobe")
    return ffmpeg, ffprobe


def _write_mp4(path: Path, image: Path, *, duration_seconds: float = 9.0) -> None:
    ffmpeg, _ = _require_ffmpeg()
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
    assert process.returncode == 0, process.stderr
    assert path.is_file()


def _completed_image(media: MediaPersistence, root: Path, index: int) -> tuple[str, str]:
    job = media.enqueue_job(job_type=IMAGE_JOB_TYPE, payload={"fixture": "30.5.10", "image": index}, priority=100)
    lease = media.claim_next(f"fixture-image-{index}")
    assert lease is not None and lease.job.job_id == job.job_id
    relative = f"fixture/images/scene-{index}.png"
    payload = deterministic_png_bytes(WIDTH, HEIGHT, f"30.5.10:{index}")
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
    media.complete_job(job.job_id, resource_usage={"fixture": True})
    return job.job_id, artifact_id


def _insert_highlight(detector: HighlightStoryArcService, score_total: int) -> MediaHighlight:
    policy = detector.policy
    components_by_total = {
        89: dict(danger=20, rarity=15, social_stakes=20, character_significance=9, outcome_reversal=10, continuity=10, visual_potential=5),
        92: dict(danger=20, rarity=15, social_stakes=20, character_significance=10, outcome_reversal=10, continuity=12, visual_potential=5),
        97: dict(danger=20, rarity=15, social_stakes=20, character_significance=12, outcome_reversal=10, continuity=15, visual_potential=5),
    }
    score = HighlightScore(**components_by_total[score_total], total=score_total)
    highlight_id = f"media_highlight_{sha256(f'{ENVELOPE_ID}:{policy.digest}'.encode('utf-8')).hexdigest()[:24]}"
    body = {
        "protocol": "underreach.highlight-story-arc.v1",
        "implementation_version": "30.5.3",
        "phase": "30.5",
        "highlight_id": highlight_id,
        "envelope_id": ENVELOPE_ID,
        "crawl_id": "descent_30_5_10_fixture",
        "source_event_ids": [EVENT_ID],
        "delver_ids": ["descender_000"],
        "score": score.model_dump(mode="json"),
        "output_tier": tier_for_score(score_total, policy).value,
        "reason_codes": ["fixture:30.5.10"],
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


def _fixture(
    tmp_path: Path,
    *,
    score_total: int,
    database_url: str = "sqlite://",
    root: Path | None = None,
) -> dict:
    _require_ffmpeg()
    media_root = root or tmp_path / "media"
    media = MediaPersistence(database_url)
    media.initialize()
    detector = HighlightStoryArcService(media)
    detector.initialize()
    image_pairs = [_completed_image(media, media_root, index) for index in range(3)]
    image_job_ids = [item[0] for item in image_pairs]
    image_artifact_ids = [item[1] for item in image_pairs]
    image_artifacts = {item["artifact_id"]: item for item in media.snapshot()["artifacts"]}

    motion_job = media.enqueue_job(
        job_type=MOTION_STORY_JOB_TYPE,
        payload={"fixture": "accepted-30.5.9-surface"},
        dependencies=tuple(image_job_ids),
        priority=100,
    )
    lease = media.claim_next("fixture-motion-story")
    assert lease is not None and lease.job.job_id == motion_job.job_id
    fallback_rel = "fixture/motion-story/motion-story.mp4"
    fallback_path = media_root / fallback_rel
    source_image = media_root / image_artifacts[image_artifact_ids[0]]["uri"]
    _write_mp4(fallback_path, source_image, duration_seconds=9.0)
    fallback_bytes = fallback_path.read_bytes()
    fallback_digest = sha256(fallback_bytes).hexdigest()

    shots = []
    for index, artifact_id in enumerate(image_artifact_ids):
        shots.append(
            {
                "index": index,
                "source_image_artifact_id": artifact_id,
                "pattern": "push_in",
                "timeline_start_ms": index * 3000,
                "duration_ms": 3000,
                "transition_ms": 0,
                "deterministic_seed": index + 1,
                "digest": f"fixture-shot-{index}",
            }
        )
    manifest_body = {
        "protocol": "underreach.ffmpeg-motion-story.v1",
        "implementation_version": "30.5.9",
        "phase": "30.5",
        "story_id": STORY_ID,
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
    manifest_rel = "fixture/motion-story/motion-story.json"
    manifest_path = media_root / manifest_rel
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_bytes(manifest_bytes)
    fallback_artifact_id = media.record_artifact(
        job_id=motion_job.job_id,
        artifact_kind="video/mp4",
        uri=fallback_rel,
        digest=fallback_digest,
        metadata={
            "story_id": STORY_ID,
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
        metadata={"story_id": STORY_ID, "video_artifact_id": fallback_artifact_id, "presentation_only": True},
    )
    media.complete_job(motion_job.job_id, resource_usage={"fixture": True})
    highlight = _insert_highlight(detector, score_total)
    return {
        "media": media,
        "detector": detector,
        "root": media_root,
        "motion_job": media.get_job(motion_job.job_id),
        "motion_job_id": motion_job.job_id,
        "fallback_artifact_id": fallback_artifact_id,
        "manifest_artifact_id": manifest_artifact_id,
        "highlight": highlight,
    }


def _service(stack: dict, *, providers=None, policy=None, provider_policy=None) -> LocalVideoEnhancementService:
    service = LocalVideoEnhancementService(
        stack["media"],
        highlights=stack["detector"],
        providers=providers if providers is not None else [DeterministicLocalI2VProvider()],
        media_root=stack["root"],
        policy=policy,
        provider_policy=provider_policy,
    )
    service.initialize()
    return service


def test_score_below_90_keeps_motion_story_without_video_jobs(tmp_path: Path) -> None:
    stack = _fixture(tmp_path, score_total=89)
    service = _service(stack)
    plan = service.plan(motion_story_job_id=stack["motion_job_id"])

    assert plan.eligible is False
    assert plan.reason_code == "highlight_below_video_threshold"
    assert plan.highlight_score == 89
    assert plan.treatment == EnhancementTreatment.MOTION_STORY_FALLBACK
    assert plan.specs == ()
    assert plan.fallback_motion_story_ready is True
    assert service.enqueue_plan(plan, gpu_window_key="2026-09-02") == ()
    assert service.snapshot()["job_count"] == 0


def test_score_90_to_94_selects_one_short_local_i2v_shot(tmp_path: Path) -> None:
    stack = _fixture(tmp_path, score_total=92)
    service = _service(stack)
    plan = service.plan(motion_story_job_id=stack["motion_job_id"])

    assert plan.eligible is True
    assert plan.treatment == EnhancementTreatment.PARTIAL_ANIMATION
    assert plan.selected_shot_count == 1
    spec = plan.specs[0]
    assert spec.highlight_score == 92
    assert spec.provider_request.kind == ProviderKind.VIDEO
    assert spec.provider_request.local_required is True
    assert spec.provider_request.paid_allowed is False
    assert spec.provider_request.image_to_video_required is True
    assert spec.provider_request.max_vram_mb == 12 * 1024
    assert spec.source_shot.animation_duration_ms == 3000
    assert spec.fallback_artifact_id == stack["fallback_artifact_id"]


def test_score_95_plus_selects_up_to_three_cinematic_priority_shots(tmp_path: Path) -> None:
    stack = _fixture(tmp_path, score_total=97)
    service = _service(stack)
    plan = service.plan(motion_story_job_id=stack["motion_job_id"])

    assert plan.eligible is True
    assert plan.treatment == EnhancementTreatment.CINEMATIC_PRIORITY
    assert plan.selected_shot_count == 3
    assert tuple(item.source_shot.shot_index for item in plan.specs) == (0, 1, 2)


def test_local_video_worker_writes_real_mp4_and_sidecar_with_fallback(tmp_path: Path) -> None:
    stack = _fixture(tmp_path, score_total=92)
    service = _service(stack)
    plan = service.plan(motion_story_job_id=stack["motion_job_id"])
    jobs = service.enqueue_plan(plan, gpu_window_key="2026-09-02")
    assert len(jobs) == 1 and jobs[0].status == JobStatus.QUEUED
    assert jobs[0].selected_provider_id == "local_deterministic_i2v"

    result = service.run_next()
    assert result is not None and result.status == JobStatus.COMPLETED
    assert result.fallback_motion_story_ready is True
    assert result.fallback_artifact_id == stack["fallback_artifact_id"]
    assert result.output_uri is not None
    output = stack["root"] / result.output_uri
    assert output.is_file() and output.stat().st_size > 100
    snapshot = service.snapshot()
    assert snapshot["artifact_count"] == 2
    assert snapshot["provider_execution_count"] == 1
    assert snapshot["scheduler"]["reservation_count"] == 1
    assert snapshot["scheduler"]["reservations"][0]["status"] == "completed"
    assert snapshot["scheduler"]["active_job_id"] is None
    assert (stack["root"] / "fixture/motion-story/motion-story.mp4").is_file()


def test_gpu_budget_exhaustion_holds_optional_job_and_preserves_fallback(tmp_path: Path) -> None:
    stack = _fixture(tmp_path, score_total=92)
    policy = VideoEnhancementPolicy(max_gpu_hours_per_window=0.001)
    service = _service(stack, policy=policy)
    plan = service.plan(motion_story_job_id=stack["motion_job_id"])
    jobs = service.enqueue_plan(plan, gpu_window_key="tiny-budget-day")

    assert len(jobs) == 1
    held = stack["media"].get_job(jobs[0].job_id)
    assert held is not None and held.status == JobStatus.HELD
    assert held.last_reason_code == "gpu_budget_exhausted"
    assert service.run_next() is None
    assert service.scheduler_snapshot()["reservation_count"] == 0
    assert (stack["root"] / "fixture/motion-story/motion-story.mp4").is_file()


class FailingVideoProvider:
    def __init__(self) -> None:
        self._descriptor = ProviderDescriptor(
            provider_id="local_failing_i2v",
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
        raise RuntimeError("injected local video failure")


def test_video_failure_gets_two_retries_then_falls_back(tmp_path: Path) -> None:
    stack = _fixture(tmp_path, score_total=92)
    service = _service(stack, providers=[FailingVideoProvider()])
    plan = service.plan(motion_story_job_id=stack["motion_job_id"])
    job = service.enqueue_plan(plan, gpu_window_key="failure-day")[0]

    first = service.run_next()
    second = service.run_next()
    third = service.run_next()
    assert first is not None and first.status == JobStatus.RETRY
    assert second is not None and second.status == JobStatus.RETRY
    assert third is not None and third.status == JobStatus.FAILED
    assert all(item.fallback_motion_story_ready for item in (first, second, third))
    final = stack["media"].get_job(job.job_id)
    assert final is not None and final.attempt_count == 3
    assert service.snapshot()["provider_execution_count"] == 3
    assert service.scheduler_snapshot()["active_job_id"] is None
    assert (stack["root"] / "fixture/motion-story/motion-story.mp4").is_file()


def test_restart_recovers_same_job_gpu_reservation_and_lock(tmp_path: Path) -> None:
    database_path = tmp_path / "media.sqlite3"
    database_url = f"sqlite:///{database_path.as_posix()}"
    root = tmp_path / "media"
    stack = _fixture(tmp_path, score_total=92, database_url=database_url, root=root)
    service = _service(stack)
    plan = service.plan(motion_story_job_id=stack["motion_job_id"])
    job = service.enqueue_plan(plan, gpu_window_key="restart-day")[0]

    lease = stack["media"].claim_next("crashed-video-worker")
    assert lease is not None and lease.job.job_id == job.job_id
    assert service._acquire_gpu(job.job_id) is True
    assert service.scheduler_snapshot()["active_job_id"] == job.job_id

    reopened_media = MediaPersistence(database_url)
    reopened_media.initialize()
    reopened_detector = HighlightStoryArcService(reopened_media)
    reopened_detector.initialize()
    reopened = LocalVideoEnhancementService(
        reopened_media,
        highlights=reopened_detector,
        providers=[DeterministicLocalI2VProvider()],
        media_root=root,
        policy=service.policy,
    )
    reopened.initialize()
    assert reopened_media.recover_interrupted_jobs() == 1
    assert reopened.recover_gpu_scheduler() == 1
    recovered_job = reopened_media.get_job(job.job_id)
    assert recovered_job is not None and recovered_job.status == JobStatus.RETRY
    assert reopened.scheduler_snapshot()["active_job_id"] is None

    result = reopened.run_next()
    assert result is not None and result.status == JobStatus.COMPLETED
    final = reopened_media.get_job(job.job_id)
    assert final is not None and final.attempt_count == 2
    assert reopened.scheduler_snapshot()["reservations"][0]["status"] == "completed"


def test_16gb_provider_is_rejected_by_12gb_policy(tmp_path: Path) -> None:
    stack = _fixture(tmp_path, score_total=92)
    descriptor = ProviderDescriptor(
        provider_id="local_16gb_i2v",
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
        estimated_runtime_seconds=1.0,
        quality_rank=99,
    )
    provider = DeterministicLocalI2VProvider(descriptor=descriptor)
    service = _service(stack, providers=[provider])
    plan = service.plan(motion_story_job_id=stack["motion_job_id"])
    job = service.enqueue_plan(plan, gpu_window_key="vram-day")[0]

    persisted = stack["media"].get_job(job.job_id)
    assert persisted is not None and persisted.status == JobStatus.HELD
    assert persisted.selected_provider_id is None
    assert persisted.last_reason_code == "no_eligible_provider"
    assert service.scheduler_snapshot()["reservation_count"] == 0


def test_paid_provider_remains_blocked_without_global_paid_permission(tmp_path: Path) -> None:
    stack = _fixture(tmp_path, score_total=92)
    descriptor = ProviderDescriptor(
        provider_id="remote_paid_i2v",
        kind=ProviderKind.VIDEO,
        local=False,
        paid=True,
        capability_flags=("headless_video", "mp4_output", "short_shot"),
        deterministic_seed=True,
        image_to_video=True,
        max_width=1080,
        max_height=1920,
        max_duration_seconds=5.0,
        estimated_vram_mb=2048,
        estimated_runtime_seconds=1.0,
        estimated_cost_microusd=5000,
        quality_rank=99,
    )
    provider = DeterministicLocalI2VProvider(descriptor=descriptor)
    policy = VideoEnhancementPolicy(local_required=False, paid_allowed=True, explicit_paid_authorization=True)
    service = _service(
        stack,
        providers=[provider],
        policy=policy,
        provider_policy=ProviderPolicy(
            local_only=False,
            cloud_allowed=True,
            allow_paid=False,
            daily_paid_budget_microusd=0,
            max_vram_mb=12 * 1024,
        ),
    )
    plan = service.plan(motion_story_job_id=stack["motion_job_id"])
    job = service.enqueue_plan(plan, gpu_window_key="paid-day")[0]
    persisted = stack["media"].get_job(job.job_id)
    assert persisted is not None and persisted.status == JobStatus.HELD
    assert persisted.selected_provider_id is None
    assert service.scheduler_snapshot()["reservation_count"] == 0


def test_completed_reenqueue_is_idempotent(tmp_path: Path) -> None:
    stack = _fixture(tmp_path, score_total=92)
    service = _service(stack)
    plan = service.plan(motion_story_job_id=stack["motion_job_id"])
    first_job = service.enqueue_plan(plan, gpu_window_key="idempotent-day")[0]
    result = service.run_next()
    assert result is not None and result.status == JobStatus.COMPLETED
    before = service.snapshot()

    second_job = service.enqueue_plan(plan, gpu_window_key="idempotent-day")[0]
    after = service.snapshot()
    assert second_job.job_id == first_job.job_id
    assert second_job.status == JobStatus.COMPLETED
    assert before == after
