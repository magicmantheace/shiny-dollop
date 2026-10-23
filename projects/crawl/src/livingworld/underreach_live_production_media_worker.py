"""Live read-only production media sidecar for Underreach Alpha.

The worker tails only checkpointed canonical Ledger history from the Alpha runtime.
It owns a separate media SQLite database and artifact tree. All model output is
presentation-only and can never mutate the canonical Crawl database.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import time
from typing import Any

from .crawl_persistence import CrawlPersistence
from .underreach_delver_chronicle_profile import ChronicleChapter, DelverChronicleProfileService
from .underreach_ffmpeg_motion_story import (
    JOB_TYPE as MOTION_JOB_TYPE,
    AutomatedFfmpegMotionStoryService,
    MotionStoryPolicy,
)
from .underreach_headless_local_image_production import (
    JOB_TYPE as IMAGE_JOB_TYPE,
    HeadlessLocalImageProductionService,
    ImageProductionPolicy,
)
from .underreach_highlight_story_arc import HighlightStoryArcService
from .underreach_local_video_enhancement import (
    JOB_TYPE as VIDEO_JOB_TYPE,
    LocalVideoEnhancementService,
    VideoEnhancementPolicy,
)
from .underreach_media_event_export import CanonicalMediaEventExporter
from .underreach_media_foundation import JobStatus, MediaPersistence
from .underreach_narration_captions_audio import (
    PACKAGE_JOB_TYPE,
    VOICE_JOB_TYPE,
    AudioProductionPolicy,
    NarrationCaptionsAudioService,
)
from .underreach_narrative_claim_verification import NarrativeClaimVerificationService
from .underreach_presentation_identity import PresentationIdentityService
from .underreach_production_provider_stack import ProductionProviderStack, build_production_provider_stack


PROTOCOL = "underreach.live-production-media-worker.v1"
IMPLEMENTATION_VERSION = "1.0"
MOTION_SCORE_FLOOR = 70
WAN_SCORE_FLOOR = 90
MAX_EXPORT_BATCH = 32
COMPOSITE_WINDOW = 24
REQUIRED_PRODUCTION_PROVIDER_IDS = {
    "comfyui_local_image",
    "kokoro_local_tts",
    "comfyui_wan22_ti2v_5b",
}


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


class LiveProductionMediaWorker:
    """Tail checkpointed Ledger truth and build local production media."""

    def __init__(self, *, repo_root: Path, state_directory: Path, poll_seconds: float = 2.0) -> None:
        self.repo_root = repo_root.resolve()
        self.state_directory = state_directory.resolve()
        self.poll_seconds = max(0.25, float(poll_seconds))
        self.canonical_db = self.state_directory / "state" / "underreach.sqlite3"
        self.runtime_state_path = self.state_directory / "state" / "runtime.json"
        self.runtime_lock_path = self.state_directory / "runtime.lock"
        self.media_root = self.state_directory / "media"
        self.artifact_root = self.media_root / "artifacts"
        self.media_db = self.media_root / "underreach_media.sqlite3"
        self.cursor_path = self.media_root / "cursor.json"
        self.status_path = self.media_root / "worker.status.json"
        self.latest_path = self.media_root / "latest-media.json"
        self.stop_request_path = self.media_root / "stop.request"
        self.stop_requested = False
        self.seen_runtime = False
        self.media: MediaPersistence | None = None
        self.highlights: HighlightStoryArcService | None = None
        self.chronicle: DelverChronicleProfileService | None = None
        self.verifier: NarrativeClaimVerificationService | None = None
        self.identities: PresentationIdentityService | None = None
        self.stack: ProductionProviderStack | None = None
        self.image: HeadlessLocalImageProductionService | None = None
        self.audio: NarrationCaptionsAudioService | None = None
        self.motion: AutomatedFfmpegMotionStoryService | None = None
        self.video: LocalVideoEnhancementService | None = None
        self._last_error: str | None = None
        self._processed_events = 0
        self._produced_promotions = 0

    def request_stop(self) -> None:
        self.stop_requested = True

    def _status(self, state: str, **extra: Any) -> None:
        body = {
            "protocol": PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "authoritative": False,
            "canonical_owner": "deterministic_simulation",
            "presentation_can_mutate_simulation": False,
            "state": state,
            "pid": os.getpid(),
            "canonical_database": str(self.canonical_db),
            "media_database": str(self.media_db),
            "artifact_root": str(self.artifact_root),
            "processed_event_count": self._processed_events,
            "produced_promotion_count": self._produced_promotions,
            "last_error": self._last_error,
            "updated_at_unix_ms": int(time.time() * 1000),
            **extra,
        }
        _atomic_json(self.status_path, body)

    def _load_cursor(self, crawl_id: str) -> int:
        if not self.cursor_path.is_file():
            return 0
        try:
            value = json.loads(self.cursor_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return 0
        if value.get("crawl_id") != crawl_id:
            return 0
        return max(0, int(value.get("history_index", 0)))

    def _save_cursor(self, crawl_id: str, history_index: int, last_event_id: str | None) -> None:
        _atomic_json(
            self.cursor_path,
            {
                "protocol": "underreach.live-media-cursor.v1",
                "crawl_id": crawl_id,
                "history_index": int(history_index),
                "last_event_id": last_event_id,
            },
        )

    def _checkpoint_tick(self) -> int | None:
        if not self.runtime_state_path.is_file():
            return None
        try:
            value = json.loads(self.runtime_state_path.read_text(encoding="utf-8-sig"))
            latest = value.get("latest_checkpoint") or {}
            return int(latest["tick"]) if "tick" in latest else None
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return None

    @staticmethod
    def _production_ready(stack: ProductionProviderStack) -> bool:
        descriptors = {item.provider_id for item in stack.descriptors}
        return (
            stack.ollama_writer is not None
            and stack.ollama_verifier is not None
            and REQUIRED_PRODUCTION_PROVIDER_IDS.issubset(descriptors)
        )

    def _initialize_media(self) -> bool:
        if self.media is None:
            self.media_root.mkdir(parents=True, exist_ok=True)
            self.artifact_root.mkdir(parents=True, exist_ok=True)
            self.media = MediaPersistence(f"sqlite:///{self.media_db.as_posix()}")
            self.media.initialize()
            self.media.recover_interrupted_jobs(reason_code="live_media_worker_restart")
            self.highlights = HighlightStoryArcService(self.media)
            self.highlights.initialize()
            self.chronicle = DelverChronicleProfileService(self.media, highlights=self.highlights)
            self.chronicle.initialize()
            self.verifier = NarrativeClaimVerificationService(self.media, chronicle=self.chronicle)
            self.verifier.initialize()
            self.identities = PresentationIdentityService(self.media, chronicle=self.chronicle)
            self.identities.initialize()

        assert self.media is not None
        if self.stack is None:
            candidate = build_production_provider_stack(self.media, media_root=self.artifact_root, probe=True)
            if not self._production_ready(candidate):
                self._status("waiting_for_production_providers", provider_health=candidate.health)
                return False
            self.stack = candidate
            assert self.highlights is not None and self.chronicle is not None
            assert self.verifier is not None and self.identities is not None
            self.image = HeadlessLocalImageProductionService(
                self.media,
                identities=self.identities,
                providers=self.stack.image_providers,
                output_root=self.artifact_root,
                policy=ImageProductionPolicy(
                    default_width=512,
                    default_height=512,
                    scene_width=432,
                    scene_height=768,
                    max_pixels=512 * 768,
                    max_vram_mb=12288,
                ),
            )
            self.image.initialize()
            self.audio = NarrationCaptionsAudioService(
                self.media,
                verifier=self.verifier,
                providers=self.stack.voice_providers,
                output_root=self.artifact_root,
                policy=AudioProductionPolicy(voice_enabled=True),
            )
            self.audio.initialize()
            self.motion = AutomatedFfmpegMotionStoryService(
                self.media,
                media_root=self.artifact_root,
                policy=MotionStoryPolicy(
                    width=432,
                    height=768,
                    fps=16,
                    minimum_duration_seconds=12.0,
                    maximum_duration_seconds=30.0,
                    target_shot_seconds=4.0,
                    minimum_shots=3,
                    maximum_shots=5,
                    transition_ms=250,
                    preset="ultrafast",
                    crf=26,
                    max_attempts=2,
                    ffmpeg_timeout_seconds=600,
                ),
                ffmpeg_path=self.stack.settings.ffmpeg_path,
                ffprobe_path=self.stack.settings.ffprobe_path,
            )
            self.motion.initialize()
            self.video = LocalVideoEnhancementService(
                self.media,
                highlights=self.highlights,
                providers=self.stack.video_providers,
                media_root=self.artifact_root,
                policy=VideoEnhancementPolicy(
                    enabled=True,
                    minimum_highlight_score=WAN_SCORE_FLOOR,
                    cinematic_score=95,
                    partial_animation_shots=1,
                    cinematic_animation_shots=3,
                    minimum_shot_seconds=3.0,
                    maximum_shot_seconds=5.0,
                    max_vram_mb=12288,
                    max_gpu_hours_per_window=8.0,
                ),
                ffprobe_path=self.stack.settings.ffprobe_path,
            )
            self.video.initialize()
            self.video.recover_gpu_scheduler()
        return True

    def _canonical(self):
        if not self.canonical_db.is_file():
            return None, None
        persistence = CrawlPersistence(f"sqlite:///{self.canonical_db.as_posix()}")
        crawls = persistence.list_crawls(limit=1)
        if not crawls:
            return None, None
        return persistence, crawls[0]

    def _ingest_checkpointed_history(self) -> tuple[str | None, int]:
        assert self.media is not None and self.highlights is not None and self.chronicle is not None
        persistence, crawl = self._canonical()
        if persistence is None or crawl is None:
            self._status("waiting_for_canonical_runtime")
            return None, 0
        checkpoint_tick = self._checkpoint_tick()
        if checkpoint_tick is None or checkpoint_tick != crawl.current_tick:
            self._status(
                "waiting_for_checkpoint",
                crawl_id=crawl.id,
                simulation_tick=crawl.current_tick,
                checkpoint_tick=checkpoint_tick,
            )
            return crawl.id, 0

        cursor = self._load_cursor(crawl.id)
        history_ids = list(crawl.history_event_ids)
        if cursor > len(history_ids):
            raise RuntimeError("media cursor is ahead of checkpointed canonical history")
        new_ids = history_ids[cursor : cursor + MAX_EXPORT_BATCH]
        if not new_ids:
            return crawl.id, 0

        exporter = CanonicalMediaEventExporter(persistence)
        envelopes = []
        for event_id in new_ids:
            envelope = exporter.export_event(crawl, event_id)
            self.media.register_envelope(envelope)
            self.highlights.evaluate(envelope)
            self.chronicle.process(envelope)
            envelopes.append(envelope)

        if len(new_ids) > 1:
            composite_ids = new_ids[-COMPOSITE_WINDOW:]
            composite = exporter.export_events(crawl, composite_ids)
            self.media.register_envelope(composite)
            self.highlights.evaluate(composite)
            self.chronicle.process(composite)
            envelopes.append(composite)

        next_cursor = cursor + len(new_ids)
        self._save_cursor(crawl.id, next_cursor, new_ids[-1])
        self._processed_events += len(new_ids)
        self._status(
            "running",
            crawl_id=crawl.id,
            simulation_tick=crawl.current_tick,
            checkpoint_tick=checkpoint_tick,
            history_index=next_cursor,
            envelopes_written=len(envelopes),
        )
        return crawl.id, len(new_ids)

    def _next_runnable_job(self):
        assert self.media is not None
        jobs = list(self.media.list_jobs())
        by_id = {job.job_id: job for job in jobs}
        candidates = []
        for job in jobs:
            if job.status not in {JobStatus.QUEUED, JobStatus.RETRY}:
                continue
            if all(
                dependency in by_id and by_id[dependency].status == JobStatus.COMPLETED
                for dependency in job.dependency_job_ids
            ):
                candidates.append(job)
        if not candidates:
            return None
        candidates.sort(key=lambda item: (-item.priority, item.job_id))
        return candidates[0]

    def _dispatch_one(self) -> bool:
        job = self._next_runnable_job()
        if job is None:
            return False
        assert self.image is not None and self.audio is not None and self.motion is not None and self.video is not None
        if job.job_type == IMAGE_JOB_TYPE:
            self.image.run_next(worker_id="underreach-live-image")
        elif job.job_type in {PACKAGE_JOB_TYPE, VOICE_JOB_TYPE}:
            self.audio.run_next(worker_id="underreach-live-audio")
        elif job.job_type == MOTION_JOB_TYPE:
            self.motion.run_next(worker_id="underreach-live-ffmpeg")
        elif job.job_type == VIDEO_JOB_TYPE:
            self.video.run_next(worker_id="underreach-live-wan")
        else:
            raise RuntimeError(f"live media worker found unsupported runnable job type: {job.job_type}")
        return True

    def _run_job_to_terminal(self, job_id: str):
        assert self.media is not None
        for _ in range(16):
            job = self.media.get_job(job_id)
            if job is None:
                raise RuntimeError(f"media job disappeared: {job_id}")
            if job.status == JobStatus.COMPLETED:
                return job
            if job.status in {JobStatus.FAILED, JobStatus.HELD}:
                return job
            if not self._dispatch_one():
                return job
        return self.media.get_job(job_id)

    def _artifact_for_job(self, job_id: str, artifact_kind: str) -> dict[str, Any] | None:
        assert self.media is not None
        matches = [
            item
            for item in self.media.snapshot()["artifacts"]
            if item["job_id"] == job_id and item["artifact_kind"] == artifact_kind
        ]
        return sorted(matches, key=lambda item: item["artifact_id"])[-1] if matches else None

    def _existing_review_ready_verification(self, chapter_id: str):
        assert self.verifier is not None
        values = [
            item
            for item in self.verifier.list_verifications()
            if item.chapter_id == chapter_id and item.review_ready
        ]
        return sorted(values, key=lambda item: item.verification_id)[-1] if values else None

    def _motion_job_for_chapter(self, chapter_id: str):
        assert self.media is not None
        matches = [
            job
            for job in self.media.list_jobs()
            if job.job_type == MOTION_JOB_TYPE
            and (job.payload.get("spec") or {}).get("chapter_id") == chapter_id
        ]
        return sorted(matches, key=lambda item: item.job_id)[-1] if matches else None

    def _featured_pending_chapter(self, crawl_id: str) -> tuple[ChronicleChapter, Any] | None:
        assert self.chronicle is not None and self.highlights is not None
        chapters = [item for item in self.chronicle.list_chapters(crawl_id=crawl_id) if item.highlight_id]
        by_highlight: dict[str, list[ChronicleChapter]] = {}
        for chapter in chapters:
            by_highlight.setdefault(str(chapter.highlight_id), []).append(chapter)
        candidates = []
        for highlight_id, grouped in by_highlight.items():
            chapter = sorted(grouped, key=lambda item: item.chapter_id)[0]
            highlight = self.highlights.get_highlight(highlight_id)
            if highlight is None or highlight.score.total < MOTION_SCORE_FLOOR:
                continue
            if self._motion_job_for_chapter(chapter.chapter_id) is not None:
                continue
            candidates.append((-highlight.score.total, chapter.canonical_tick, chapter.chapter_id, chapter, highlight))
        if not candidates:
            return None
        candidates.sort(key=lambda item: (item[0], item[1], item[2]))
        return candidates[0][3], candidates[0][4]

    def _promote_one(self, crawl_id: str) -> bool:
        assert self.media is not None and self.stack is not None
        assert self.chronicle is not None and self.verifier is not None and self.identities is not None
        assert self.image is not None and self.audio is not None and self.motion is not None and self.video is not None
        pending = self._featured_pending_chapter(crawl_id)
        if pending is None:
            return False
        chapter, highlight = pending
        profile = self.chronicle.get_profile(chapter.crawl_id, chapter.delver_id)
        if profile is None:
            raise RuntimeError("featured Chronicle chapter lost its Delver profile")

        verification = self._existing_review_ready_verification(chapter.chapter_id)
        if verification is None:
            pipeline = self.stack.build_narrative_pipeline(
                self.media,
                chronicle=self.chronicle,
                verifier=self.verifier,
                use_auxiliary_verifier=True,
            )
            narrative = pipeline.generate_and_verify(chapter.chapter_id)
            if not narrative.review_ready:
                raise RuntimeError("Qwen narrative did not pass deterministic claim verification")
            verification = self._existing_review_ready_verification(chapter.chapter_id)
            if verification is None:
                raise RuntimeError("review-ready narrative verification was not persisted")

        self.identities.ensure_identity(profile)
        scene_spec = self.image.plan_scene(profile, chapter, width=432, height=768)
        image_job = self.image.enqueue(scene_spec, priority=500)
        image_job = self._run_job_to_terminal(image_job.job_id)
        if image_job is None or image_job.status != JobStatus.COMPLETED:
            raise RuntimeError(f"SDXL scene job did not complete: {getattr(image_job, 'status', None)}")
        image_artifact = self._artifact_for_job(image_job.job_id, "image/png")
        if image_artifact is None:
            raise RuntimeError("completed SDXL scene job has no PNG artifact")

        audio_spec = self.audio.plan(verification.verification_id)
        package_job, voice_job = self.audio.enqueue(audio_spec, package_priority=450, voice_priority=440)
        package_job = self._run_job_to_terminal(package_job.job_id)
        if package_job is None or package_job.status != JobStatus.COMPLETED:
            raise RuntimeError("caption package did not complete")
        if voice_job is not None:
            voice_job = self._run_job_to_terminal(voice_job.job_id)
            if voice_job is None or voice_job.status != JobStatus.COMPLETED:
                raise RuntimeError("Kokoro narration did not complete")

        motion_spec = self.motion.plan(
            package_job_id=package_job.job_id,
            image_artifact_ids=(image_artifact["artifact_id"],),
        )
        motion_job = self.motion.enqueue(motion_spec, priority=400)
        motion_job = self._run_job_to_terminal(motion_job.job_id)
        if motion_job is None or motion_job.status != JobStatus.COMPLETED:
            raise RuntimeError("FFmpeg motion story did not complete")
        motion_artifact = self._artifact_for_job(motion_job.job_id, "video/mp4")
        if motion_artifact is None:
            raise RuntimeError("completed FFmpeg story has no MP4 artifact")

        enhanced_artifacts = []
        if highlight.score.total >= WAN_SCORE_FLOOR:
            plan = self.video.plan(motion_story_job_id=motion_job.job_id)
            jobs = self.video.enqueue_plan(plan, gpu_window_key=time.strftime("%Y-%m-%d", time.gmtime()))
            for job in jobs:
                terminal = self._run_job_to_terminal(job.job_id)
                if terminal is not None and terminal.status == JobStatus.COMPLETED:
                    artifact = self._artifact_for_job(job.job_id, "video/mp4")
                    if artifact is not None:
                        enhanced_artifacts.append(artifact)

        self._produced_promotions += 1
        _atomic_json(
            self.latest_path,
            {
                "protocol": "underreach.live-media-latest.v1",
                "crawl_id": crawl_id,
                "highlight_id": highlight.highlight_id,
                "highlight_score": highlight.score.total,
                "highlight_tier": highlight.output_tier.value,
                "chapter_id": chapter.chapter_id,
                "delver_id": chapter.delver_id,
                "source_event_ids": list(highlight.source_event_ids),
                "writer_provider_id": self.stack.ollama_writer.descriptor.provider_id,
                "verifier_provider_id": self.stack.ollama_verifier.descriptor.provider_id,
                "image_provider_id": image_job.selected_provider_id,
                "voice_provider_id": voice_job.selected_provider_id if voice_job is not None else None,
                "motion_story": motion_artifact,
                "wan_enhancements": enhanced_artifacts,
                "review_status": "pending",
                "automatic_publication_allowed": False,
                "canonical_authority": False,
                "presentation_can_mutate_simulation": False,
            },
        )
        self._status(
            "running",
            crawl_id=crawl_id,
            latest_highlight_id=highlight.highlight_id,
            latest_highlight_score=highlight.score.total,
            latest_motion_uri=motion_artifact["uri"],
            latest_wan_count=len(enhanced_artifacts),
        )
        return True

    def _drain_recovered_jobs(self) -> None:
        for _ in range(32):
            if not self._dispatch_one():
                break

    def run(self) -> int:
        self.media_root.mkdir(parents=True, exist_ok=True)
        self.stop_request_path.unlink(missing_ok=True)
        self._status("starting")
        while not self.stop_requested:
            sleep_for = self.poll_seconds
            if self.stop_request_path.exists():
                self.stop_requested = True
                break
            if self.runtime_lock_path.exists():
                self.seen_runtime = True
            try:
                if not self._initialize_media():
                    time.sleep(self.poll_seconds)
                    continue
                self._drain_recovered_jobs()
                crawl_id, ingested = self._ingest_checkpointed_history()
                if crawl_id is not None:
                    self._promote_one(crawl_id)
                if ingested:
                    sleep_for = 0.05
                if self.seen_runtime and not self.runtime_lock_path.exists():
                    final_crawl_id, _ = self._ingest_checkpointed_history()
                    if final_crawl_id is not None:
                        self._promote_one(final_crawl_id)
                    break
                self._last_error = None
            except Exception as exc:
                self._last_error = f"{type(exc).__name__}: {exc}"
                self._status("degraded", error_type=type(exc).__name__)
            time.sleep(sleep_for)
        self._status("stopped")
        return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Tail Underreach Alpha canonical history into local production media")
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--state-directory", type=Path, required=True)
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    args = parser.parse_args()
    worker = LiveProductionMediaWorker(
        repo_root=args.repo_root,
        state_directory=args.state_directory,
        poll_seconds=args.poll_seconds,
    )

    def stop(_signum, _frame):
        worker.request_stop()

    signal.signal(signal.SIGINT, stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, stop)
    raise SystemExit(worker.run())


if __name__ == "__main__":
    main()
