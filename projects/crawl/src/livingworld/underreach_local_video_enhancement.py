"""Optional local video enhancement and durable GPU scheduling for Phase 30.5.10.

30.5.10 consumes only completed 30.5.9 motion-story artifacts plus persisted
30.5.3 deterministic highlight scores. Eligible score-90+ stories may animate a
bounded set of short storyboard shots through a capability-routed VIDEO
provider. The already-completed 30.5.9 motion-story MP4 is always retained as
the review-ready fallback.

GPU-heavy work is serialized through media-owned SQLite state and charged
against an explicit scheduling-window budget. Provider failure, provider
absence, VRAM rejection, exhausted GPU budget, and process restart affect only
optional enhancement jobs. No code in this module opens canonical Crawl state,
invokes Unreal, requires a paid/cloud provider, or gives generated video any
canonical authority.
"""
from __future__ import annotations

from enum import StrEnum
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
from threading import RLock
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import Integer, String, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from .runtime_checkpoint import canonical_json, payload_digest
from .underreach_ffmpeg_motion_story import JOB_TYPE as MOTION_STORY_JOB_TYPE
from .underreach_headless_local_image_production import JOB_TYPE as IMAGE_JOB_TYPE
from .underreach_highlight_story_arc import HighlightStoryArcService, HighlightTier, MediaHighlight, validate_highlight
from .underreach_media_foundation import (
    JobStatus,
    MediaJob,
    MediaPersistence,
    MediaProviderRouter,
    ProviderDescriptor,
    ProviderKind,
    ProviderPolicy,
    ProviderRequest,
)


PROTOCOL = "underreach.local-video-enhancement.v1"
IMPLEMENTATION_VERSION = "30.5.10"
PHASE = "30.5"
JOB_TYPE = "underreach.video-enhancement.shot"
PROVIDER_PROFILE_VERSION = "underreach.video-enhancement-provider.v1"
DEFAULT_MAX_VRAM_MB = 12 * 1024
DEFAULT_MAX_GPU_HOURS_PER_WINDOW = 8.0
DEFAULT_MINIMUM_HIGHLIGHT_SCORE = 90
DEFAULT_CINEMATIC_SCORE = 95


class VideoEnhancementError(ValueError):
    """Raised when 30.5.10 presentation/scheduling invariants are violated."""


class EnhancementTreatment(StrEnum):
    MOTION_STORY_FALLBACK = "motion_story_fallback"
    PARTIAL_ANIMATION = "partial_animation"
    CINEMATIC_PRIORITY = "cinematic_priority"


class GpuReservationStatus(StrEnum):
    RESERVED = "reserved"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class VideoEnhancementPolicy(BaseModel):
    """Local-first GPU policy from the frozen 30.5 roadmap."""

    model_config = ConfigDict(frozen=True)

    enabled: bool = True
    minimum_highlight_score: int = Field(default=DEFAULT_MINIMUM_HIGHLIGHT_SCORE, ge=0, le=100)
    cinematic_score: int = Field(default=DEFAULT_CINEMATIC_SCORE, ge=0, le=100)
    partial_animation_shots: int = Field(default=1, ge=1, le=3)
    cinematic_animation_shots: int = Field(default=3, ge=1, le=3)
    minimum_shot_seconds: float = Field(default=3.0, ge=1.0, le=5.0)
    maximum_shot_seconds: float = Field(default=5.0, ge=1.0, le=8.0)
    max_vram_mb: int = Field(default=DEFAULT_MAX_VRAM_MB, ge=0, le=65536)
    max_gpu_hours_per_window: float = Field(default=DEFAULT_MAX_GPU_HOURS_PER_WINDOW, ge=0.0, le=24.0)
    max_retries_per_shot: int = Field(default=2, ge=0, le=5)
    local_required: bool = True
    paid_allowed: bool = False
    explicit_paid_authorization: bool = False
    min_quality_rank: int = Field(default=0, ge=0, le=100)

    @model_validator(mode="after")
    def validate_policy(self) -> "VideoEnhancementPolicy":
        if self.minimum_highlight_score >= self.cinematic_score:
            raise ValueError("cinematic score must be above minimum animation score")
        if self.minimum_shot_seconds > self.maximum_shot_seconds:
            raise ValueError("minimum shot duration cannot exceed maximum")
        if self.explicit_paid_authorization and not self.paid_allowed:
            raise ValueError("explicit paid authorization requires paid_allowed=true")
        return self

    @property
    def max_gpu_ms_per_window(self) -> int:
        return int(round(self.max_gpu_hours_per_window * 3_600_000.0))

    @property
    def max_attempts(self) -> int:
        return self.max_retries_per_shot + 1

    @property
    def digest(self) -> str:
        return payload_digest(self.model_dump(mode="json"))


class VideoSourceShot(BaseModel):
    model_config = ConfigDict(frozen=True)

    shot_index: int = Field(ge=0)
    timeline_start_ms: int = Field(ge=0)
    source_duration_ms: int = Field(gt=0)
    animation_duration_ms: int = Field(gt=0)
    source_image_artifact_id: str
    source_image_job_id: str
    source_image_uri: str
    source_image_digest: str
    source_envelope_id: str | None = None
    source_event_ids: tuple[str, ...]
    digest: str


class VideoEnhancementSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    protocol: str = PROTOCOL
    implementation_version: str = IMPLEMENTATION_VERSION
    phase: str = PHASE
    spec_id: str
    story_id: str
    chapter_id: str
    motion_story_job_id: str
    fallback_artifact_id: str
    fallback_uri: str
    fallback_digest: str
    fallback_manifest_artifact_id: str
    fallback_manifest_digest: str
    highlight_ids: tuple[str, ...]
    highlight_score: int = Field(ge=0, le=100)
    highlight_tier: HighlightTier
    treatment: EnhancementTreatment
    source_shot: VideoSourceShot
    source_envelope_ids: tuple[str, ...]
    source_event_ids: tuple[str, ...]
    deterministic_seed: int = Field(ge=0)
    width: int = Field(ge=180, le=2160)
    height: int = Field(ge=320, le=3840)
    fps: int = Field(ge=10, le=60)
    provider_request: ProviderRequest
    provider_profile_version: str = PROVIDER_PROFILE_VERSION
    policy_digest: str
    fallback_motion_story_ready: bool = True
    image_to_video_required: bool = True
    video_diffusion_required: bool = False
    canonical_authority: bool = False
    presentation_can_mutate_simulation: bool = False
    unreal_dependency: bool = False
    cloud_api_required: bool = False
    paid_provider_required: bool = False
    digest: str


class VideoEnhancementPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    story_id: str
    motion_story_job_id: str
    fallback_artifact_id: str
    fallback_uri: str
    fallback_digest: str
    eligible: bool
    reason_code: str
    highlight_score: int = Field(ge=0, le=100)
    treatment: EnhancementTreatment
    selected_shot_count: int = Field(ge=0, le=3)
    specs: tuple[VideoEnhancementSpec, ...] = ()
    fallback_motion_story_ready: bool = True
    canonical_authority: bool = False
    presentation_can_mutate_simulation: bool = False
    digest: str


class VideoRenderRequest(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    spec: VideoEnhancementSpec
    job_id: str
    attempt_id: str
    source_image_path: Path
    output_path: Path


class VideoRenderOutput(BaseModel):
    model_config = ConfigDict(frozen=True)

    duration_ms: int = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    actual_gpu_ms: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class VideoEnhancementResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    spec_id: str
    story_id: str
    job_id: str
    status: JobStatus
    fallback_motion_story_ready: bool = True
    fallback_artifact_id: str
    provider_id: str | None = None
    video_artifact_id: str | None = None
    sidecar_artifact_id: str | None = None
    output_uri: str | None = None
    output_digest: str | None = None
    reason_code: str | None = None
    canonical_authority: bool = False
    presentation_can_mutate_simulation: bool = False


class HeadlessVideoProvider(Protocol):
    @property
    def descriptor(self) -> ProviderDescriptor: ...

    def animate(self, request: VideoRenderRequest) -> VideoRenderOutput: ...


class VideoScheduleBase(DeclarativeBase):
    """30.5.10-only durable GPU scheduling state in the media database."""


class VideoGpuReservationRow(VideoScheduleBase):
    __tablename__ = "media_video_gpu_reservations"

    reservation_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(96), unique=True, index=True)
    window_key: Mapped[str] = mapped_column(String(96), index=True)
    provider_id: Mapped[str] = mapped_column(String(96), index=True)
    estimated_gpu_ms_per_attempt: Mapped[int] = mapped_column(Integer)
    reserved_gpu_ms: Mapped[int] = mapped_column(Integer)
    actual_gpu_ms: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(24), index=True)


class VideoGpuLockRow(VideoScheduleBase):
    __tablename__ = "media_video_gpu_lock"

    lock_name: Mapped[str] = mapped_column(String(48), primary_key=True)
    job_id: Mapped[str | None] = mapped_column(String(96), nullable=True, index=True)


def _stable_id(prefix: str, *parts: object) -> str:
    text = ":".join(str(part) for part in parts)
    return f"{prefix}_{sha256(text.encode('utf-8')).hexdigest()[:24]}"


def _stable_seed(*parts: object) -> int:
    text = ":".join(str(part) for part in parts)
    return int(sha256(text.encode("utf-8")).hexdigest()[:15], 16)


def _body_digest(model: BaseModel) -> str:
    return payload_digest(model.model_dump(mode="json", exclude={"digest"}))


def _safe_relative_uri(uri: str) -> PurePosixPath:
    value = PurePosixPath(uri)
    if value.is_absolute() or ".." in value.parts or "://" in uri:
        raise VideoEnhancementError("video enhancement input URI must be a safe relative media path")
    return value


def validate_source_shot(shot: VideoSourceShot) -> bool:
    if not shot.source_event_ids or tuple(sorted(set(shot.source_event_ids))) != shot.source_event_ids:
        raise VideoEnhancementError("video source shot event provenance is missing or not normalized")
    _safe_relative_uri(shot.source_image_uri)
    if shot.animation_duration_ms > shot.source_duration_ms:
        raise VideoEnhancementError("animated shot may not exceed source storyboard duration")
    if shot.digest != _body_digest(shot):
        raise VideoEnhancementError("video source shot digest mismatch")
    return True


def validate_video_spec(spec: VideoEnhancementSpec) -> bool:
    if spec.protocol != PROTOCOL or spec.implementation_version != IMPLEMENTATION_VERSION or spec.phase != PHASE:
        raise VideoEnhancementError("video enhancement protocol/version mismatch")
    validate_source_shot(spec.source_shot)
    if spec.width * 16 != spec.height * 9:
        raise VideoEnhancementError("video enhancement output must remain exact 9:16")
    if spec.highlight_score < DEFAULT_MINIMUM_HIGHLIGHT_SCORE:
        raise VideoEnhancementError("video enhancement spec fell below frozen score-90 eligibility floor")
    if not spec.highlight_ids or tuple(sorted(set(spec.highlight_ids))) != spec.highlight_ids:
        raise VideoEnhancementError("video enhancement highlight provenance is missing or not normalized")
    if not spec.source_event_ids or tuple(sorted(set(spec.source_event_ids))) != spec.source_event_ids:
        raise VideoEnhancementError("video enhancement source-event provenance is missing or not normalized")
    if tuple(sorted(set(spec.source_envelope_ids))) != spec.source_envelope_ids:
        raise VideoEnhancementError("video enhancement source-envelope provenance is not normalized")
    if spec.provider_request.kind != ProviderKind.VIDEO:
        raise VideoEnhancementError("video enhancement requires provider kind=video")
    if not spec.provider_request.image_to_video_required or not spec.provider_request.deterministic_seed_required:
        raise VideoEnhancementError("30.5.10 requires deterministic image-to-video capability")
    if not spec.fallback_motion_story_ready or not spec.fallback_artifact_id or not spec.fallback_digest:
        raise VideoEnhancementError("video enhancement lost guaranteed motion-story fallback")
    _safe_relative_uri(spec.fallback_uri)
    if spec.provider_profile_version != PROVIDER_PROFILE_VERSION:
        raise VideoEnhancementError("video provider profile version mismatch")
    if (
        not spec.image_to_video_required
        or spec.video_diffusion_required
        or spec.canonical_authority
        or spec.presentation_can_mutate_simulation
        or spec.unreal_dependency
        or spec.cloud_api_required
        or spec.paid_provider_required
    ):
        raise VideoEnhancementError("video enhancement escaped optional presentation-only authority")
    if spec.digest != _body_digest(spec):
        raise VideoEnhancementError("video enhancement spec digest mismatch")
    expected = _stable_id(
        "video_enhancement_spec",
        spec.story_id,
        spec.source_shot.shot_index,
        spec.source_shot.source_image_artifact_id,
        spec.deterministic_seed,
        spec.policy_digest,
    )
    if spec.spec_id != expected:
        raise VideoEnhancementError("video enhancement deterministic identity mismatch")
    return True


def validate_plan(plan: VideoEnhancementPlan) -> bool:
    if not plan.fallback_motion_story_ready:
        raise VideoEnhancementError("video enhancement plan lost accepted 30.5.9 fallback")
    if plan.eligible != bool(plan.specs):
        raise VideoEnhancementError("video enhancement eligibility diverged from selected specs")
    if plan.selected_shot_count != len(plan.specs):
        raise VideoEnhancementError("video enhancement selected shot count mismatch")
    if plan.eligible and plan.highlight_score < DEFAULT_MINIMUM_HIGHLIGHT_SCORE:
        raise VideoEnhancementError("eligible video plan fell below frozen score floor")
    for spec in plan.specs:
        validate_video_spec(spec)
        if spec.story_id != plan.story_id or spec.fallback_artifact_id != plan.fallback_artifact_id:
            raise VideoEnhancementError("video plan spec diverged from fallback/story identity")
    if plan.digest != _body_digest(plan):
        raise VideoEnhancementError("video enhancement plan digest mismatch")
    return True


class DeterministicLocalI2VProvider:
    """Zero-model acceptance backend for the I2V provider contract.

    It uses local FFmpeg to turn one accepted still into a short deterministic
    MP4. It is deliberately not a quality AI backend. Wan/ComfyUI/equivalent
    providers can replace it behind the same HeadlessVideoProvider interface.
    The descriptor carries synthetic constrained-GPU estimates so the durable
    scheduler is exercised during acceptance.
    """

    def __init__(
        self,
        descriptor: ProviderDescriptor | None = None,
        *,
        ffmpeg_path: str | Path | None = None,
    ) -> None:
        self._descriptor = descriptor or ProviderDescriptor(
            provider_id="local_deterministic_i2v",
            kind=ProviderKind.VIDEO,
            local=True,
            paid=False,
            capability_flags=("headless_video", "mp4_output", "short_shot"),
            deterministic_seed=True,
            reference_conditioning=True,
            image_to_video=True,
            max_width=1080,
            max_height=1920,
            max_duration_seconds=5.0,
            estimated_vram_mb=1024,
            estimated_runtime_seconds=2.0,
            estimated_cost_microusd=0,
            quality_rank=1,
            quality_profile="deterministic_i2v_acceptance_fallback",
        )
        if self._descriptor.kind != ProviderKind.VIDEO:
            raise VideoEnhancementError("video executor descriptor must have kind=video")
        if not self._descriptor.image_to_video or not self._descriptor.deterministic_seed:
            raise VideoEnhancementError("video executor requires deterministic image-to-video capability")
        self.ffmpeg_path = str(ffmpeg_path) if ffmpeg_path is not None else (shutil.which("ffmpeg") or "ffmpeg")

    @property
    def descriptor(self) -> ProviderDescriptor:
        return self._descriptor

    def animate(self, request: VideoRenderRequest) -> VideoRenderOutput:
        spec = request.spec
        descriptor = self.descriptor
        if descriptor.max_width is not None and spec.width > descriptor.max_width:
            raise VideoEnhancementError("requested video width exceeds provider capability")
        if descriptor.max_height is not None and spec.height > descriptor.max_height:
            raise VideoEnhancementError("requested video height exceeds provider capability")
        duration_seconds = spec.source_shot.animation_duration_ms / 1000.0
        if descriptor.max_duration_seconds is not None and duration_seconds > descriptor.max_duration_seconds:
            raise VideoEnhancementError("requested shot duration exceeds provider capability")
        frames = max(2, int(round(duration_seconds * spec.fps)))
        denom = max(1, frames - 1)
        direction = spec.deterministic_seed % 2
        if direction == 0:
            zoom = f"1+0.05*on/{denom}"
            x = "iw/2-(iw/zoom/2)"
        else:
            zoom = "1.04"
            x = f"(iw-iw/zoom)*(on/{denom})"
        y = "ih/2-(ih/zoom/2)"
        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        command = [
            self.ffmpeg_path,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-loop",
            "1",
            "-framerate",
            str(spec.fps),
            "-i",
            str(request.source_image_path),
            "-vf",
            (
                f"scale={spec.width}:{spec.height}:force_original_aspect_ratio=increase,"
                f"crop={spec.width}:{spec.height},"
                f"zoompan=z='{zoom}':x='{x}':y='{y}':d=1:s={spec.width}x{spec.height}:fps={spec.fps},"
                f"trim=duration={duration_seconds:.3f},setpts=PTS-STARTPTS,setsar=1,format=yuv420p"
            ),
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "28",
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(spec.fps),
            "-threads",
            "1",
            "-flags:v",
            "+bitexact",
            "-map_metadata",
            "-1",
            "-metadata",
            "creation_time=1970-01-01T00:00:00Z",
            "-t",
            f"{duration_seconds:.3f}",
            str(request.output_path),
        ]
        process = subprocess.run(command, capture_output=True, text=True, timeout=120, check=False)
        if process.returncode != 0 or not request.output_path.is_file():
            raise VideoEnhancementError("deterministic local I2V FFmpeg render failed")
        estimated = int(round(descriptor.estimated_runtime_seconds * 1000.0))
        return VideoRenderOutput(
            duration_ms=spec.source_shot.animation_duration_ms,
            width=spec.width,
            height=spec.height,
            actual_gpu_ms=estimated,
            metadata={
                "renderer": "deterministic_ffmpeg_i2v_acceptance_v1",
                "quality_profile": descriptor.quality_profile,
                "synthetic_gpu_accounting": True,
                "video_diffusion_used": False,
                "presentation_only": True,
            },
        )


class LocalVideoEnhancementService:
    """Select, schedule, and execute optional short local video enhancements."""

    _GPU_LOCK_NAME = "underreach-video-gpu"

    def __init__(
        self,
        media: MediaPersistence,
        *,
        highlights: HighlightStoryArcService,
        providers: tuple[HeadlessVideoProvider, ...] | list[HeadlessVideoProvider],
        media_root: str | Path,
        policy: VideoEnhancementPolicy | None = None,
        provider_policy: ProviderPolicy | None = None,
        router: MediaProviderRouter | None = None,
        ffprobe_path: str | Path | None = None,
    ) -> None:
        self.media = media
        self.highlights = highlights
        self.media_root = Path(media_root)
        self.policy = policy or VideoEnhancementPolicy()
        self.router = router or MediaProviderRouter()
        self.provider_policy = provider_policy or ProviderPolicy(
            local_only=self.policy.local_required,
            cloud_allowed=not self.policy.local_required,
            allow_paid=self.policy.paid_allowed,
            require_explicit_paid_policy=True,
            daily_paid_budget_microusd=0,
            max_vram_mb=self.policy.max_vram_mb,
        )
        self.ffprobe_path = str(ffprobe_path) if ffprobe_path is not None else (shutil.which("ffprobe") or "ffprobe")
        self._lock = RLock()
        self._executors: dict[str, HeadlessVideoProvider] = {}
        self._descriptors: dict[str, ProviderDescriptor] = {}
        for provider in providers:
            descriptor = provider.descriptor
            if descriptor.kind != ProviderKind.VIDEO:
                raise VideoEnhancementError("30.5.10 accepts only VIDEO executors")
            if not descriptor.image_to_video:
                raise VideoEnhancementError("30.5.10 executable provider must support image-to-video")
            existing = self._executors.get(descriptor.provider_id)
            if existing is not None and existing is not provider:
                raise VideoEnhancementError("duplicate executable video provider_id")
            self.router.register(descriptor)
            self._executors[descriptor.provider_id] = provider
            self._descriptors[descriptor.provider_id] = descriptor

    def initialize(self) -> None:
        self.media_root.mkdir(parents=True, exist_ok=True)
        with self._lock:
            VideoScheduleBase.metadata.create_all(self.media.engine)
            with Session(self.media.engine) as session:
                if session.get(VideoGpuLockRow, self._GPU_LOCK_NAME) is None:
                    session.add(VideoGpuLockRow(lock_name=self._GPU_LOCK_NAME, job_id=None))
                    session.commit()

    def _artifact(self, artifact_id: str) -> dict[str, Any]:
        matches = [item for item in self.media.snapshot()["artifacts"] if item["artifact_id"] == artifact_id]
        if len(matches) != 1:
            raise VideoEnhancementError("video enhancement requires exactly one persisted artifact")
        return matches[0]

    def _verify_file(self, uri: str, digest: str) -> Path:
        relative = _safe_relative_uri(uri)
        path = self.media_root.joinpath(*relative.parts)
        if not path.is_file():
            raise VideoEnhancementError("video enhancement input artifact file is missing")
        if sha256(path.read_bytes()).hexdigest() != digest:
            raise VideoEnhancementError("video enhancement artifact digest no longer matches file")
        return path

    def _probe_video(self, path: Path, *, width: int | None = None, height: int | None = None, duration_ms: int | None = None) -> dict[str, Any]:
        process = subprocess.run(
            [
                self.ffprobe_path,
                "-v",
                "error",
                "-show_entries",
                "format=format_name,duration:stream=codec_type,width,height",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if process.returncode != 0:
            raise VideoEnhancementError("ffprobe could not validate video artifact")
        try:
            payload = json.loads(process.stdout)
        except json.JSONDecodeError as exc:
            raise VideoEnhancementError("ffprobe returned invalid JSON") from exc
        videos = [item for item in payload.get("streams", []) if item.get("codec_type") == "video"]
        if len(videos) != 1:
            raise VideoEnhancementError("video enhancement artifact must have exactly one video stream")
        video = videos[0]
        actual_width = int(video.get("width", 0))
        actual_height = int(video.get("height", 0))
        actual_duration_ms = int(round(float((payload.get("format") or {}).get("duration", 0.0)) * 1000.0))
        if width is not None and actual_width != width:
            raise VideoEnhancementError("video enhancement width diverged from spec")
        if height is not None and actual_height != height:
            raise VideoEnhancementError("video enhancement height diverged from spec")
        if duration_ms is not None and abs(actual_duration_ms - duration_ms) > 1200:
            raise VideoEnhancementError("video enhancement duration diverged materially from spec")
        return {
            "format_name": str((payload.get("format") or {}).get("format_name", "")),
            "width": actual_width,
            "height": actual_height,
            "duration_ms": actual_duration_ms,
        }

    def _fallback_context(self, motion_story_job_id: str) -> dict[str, Any]:
        job = self.media.get_job(motion_story_job_id)
        if job is None or job.job_type != MOTION_STORY_JOB_TYPE or job.status != JobStatus.COMPLETED:
            raise VideoEnhancementError("video enhancement requires a completed 30.5.9 motion-story job")
        artifacts = [item for item in self.media.snapshot()["artifacts"] if item["job_id"] == motion_story_job_id]
        videos = [item for item in artifacts if item["artifact_kind"] == "video/mp4"]
        manifests = [item for item in artifacts if item["artifact_kind"] == "application/json"]
        if len(videos) != 1 or len(manifests) != 1:
            raise VideoEnhancementError("completed motion story must expose one MP4 and one manifest")
        fallback = videos[0]
        manifest_artifact = manifests[0]
        fallback_path = self._verify_file(fallback["uri"], fallback["digest"])
        manifest_path = self._verify_file(manifest_artifact["uri"], manifest_artifact["digest"])
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise VideoEnhancementError("30.5.9 motion-story manifest is unreadable") from exc
        if (
            manifest.get("protocol") != "underreach.ffmpeg-motion-story.v1"
            or manifest.get("implementation_version") != "30.5.9"
            or manifest.get("phase") != "30.5"
            or manifest.get("job_id") != motion_story_job_id
        ):
            raise VideoEnhancementError("motion-story manifest protocol/version provenance changed")
        if manifest.get("output_uri") != fallback["uri"] or manifest.get("output_sha256") != fallback["digest"]:
            raise VideoEnhancementError("motion-story manifest no longer matches fallback MP4")
        if manifest.get("canonical_authority") or manifest.get("presentation_can_mutate_simulation"):
            raise VideoEnhancementError("motion-story fallback escaped presentation-only authority")
        source_events = tuple(sorted(set(str(value) for value in manifest.get("source_event_ids", []) if value)))
        source_envelopes = tuple(sorted(set(str(value) for value in manifest.get("source_envelope_ids", []) if value)))
        if not source_events:
            raise VideoEnhancementError("motion-story fallback lacks canonical event provenance")
        shots = manifest.get("shots")
        if not isinstance(shots, list) or not shots:
            raise VideoEnhancementError("motion-story fallback lacks storyboard shots")
        width = int(manifest.get("output_width") or 0)
        height = int(manifest.get("output_height") or 0)
        fps = int(manifest.get("fps") or 0)
        if width <= 0 or height <= 0 or fps <= 0 or width * 16 != height * 9:
            raise VideoEnhancementError("motion-story fallback output geometry is invalid")
        self._probe_video(fallback_path, width=width, height=height)
        return {
            "job": job,
            "fallback": fallback,
            "fallback_path": fallback_path,
            "manifest_artifact": manifest_artifact,
            "manifest": manifest,
            "story_id": str(manifest.get("story_id") or (fallback.get("metadata") or {}).get("story_id") or ""),
            "chapter_id": str(manifest.get("chapter_id") or ""),
            "source_event_ids": source_events,
            "source_envelope_ids": source_envelopes,
            "shots": shots,
            "width": width,
            "height": height,
            "fps": fps,
        }

    def _highlight_context(self, source_envelopes: tuple[str, ...], source_events: tuple[str, ...]) -> tuple[tuple[MediaHighlight, ...], int, HighlightTier]:
        envelope_set = set(source_envelopes)
        event_set = set(source_events)
        matches = []
        for highlight in self.highlights.list_highlights():
            validate_highlight(highlight, self.highlights.policy)
            if highlight.envelope_id in envelope_set or event_set.intersection(highlight.source_event_ids):
                matches.append(highlight)
        ordered = tuple(sorted(matches, key=lambda item: item.highlight_id))
        if not ordered:
            return (), 0, HighlightTier.ARCHIVE_ONLY
        best = max(ordered, key=lambda item: (item.score.total, item.highlight_id))
        return ordered, best.score.total, best.output_tier

    def _image_for_shot(self, shot: dict[str, Any], chapter_id: str, story_events: tuple[str, ...]) -> VideoSourceShot:
        artifact_id = str(shot.get("source_image_artifact_id") or "")
        if not artifact_id:
            raise VideoEnhancementError("motion-story shot lacks source image artifact")
        artifact = self._artifact(artifact_id)
        if artifact["artifact_kind"] != "image/png":
            raise VideoEnhancementError("video enhancement source must be a 30.5.7 PNG")
        image_job = self.media.get_job(artifact["job_id"])
        if image_job is None or image_job.job_type != IMAGE_JOB_TYPE or image_job.status != JobStatus.COMPLETED:
            raise VideoEnhancementError("video enhancement source image job is not completed 30.5.7 work")
        metadata = dict(artifact.get("metadata") or {})
        if metadata.get("chapter_id") != chapter_id:
            raise VideoEnhancementError("video enhancement source image belongs to wrong chapter")
        source_events = tuple(sorted(set(str(value) for value in metadata.get("source_event_ids", []) if value)))
        if not source_events or not set(source_events).intersection(story_events):
            raise VideoEnhancementError("video enhancement source image lacks story event provenance")
        self._verify_file(artifact["uri"], artifact["digest"])
        source_duration = int(shot.get("duration_ms") or 0)
        minimum_ms = int(round(self.policy.minimum_shot_seconds * 1000.0))
        maximum_ms = int(round(self.policy.maximum_shot_seconds * 1000.0))
        if source_duration < minimum_ms:
            raise VideoEnhancementError("storyboard shot is shorter than configured local-animation minimum")
        animation_duration = min(source_duration, maximum_ms)
        body = {
            "shot_index": int(shot.get("index") or 0),
            "timeline_start_ms": int(shot.get("timeline_start_ms") or 0),
            "source_duration_ms": source_duration,
            "animation_duration_ms": animation_duration,
            "source_image_artifact_id": artifact_id,
            "source_image_job_id": artifact["job_id"],
            "source_image_uri": artifact["uri"],
            "source_image_digest": artifact["digest"],
            "source_envelope_id": metadata.get("source_envelope_id"),
            "source_event_ids": list(source_events),
        }
        value = VideoSourceShot.model_validate({**body, "digest": payload_digest(body)})
        validate_source_shot(value)
        return value

    def _provider_request(self, *, width: int, height: int, duration_ms: int) -> ProviderRequest:
        return ProviderRequest(
            kind=ProviderKind.VIDEO,
            required_flags=("headless_video", "mp4_output", "short_shot"),
            local_required=self.policy.local_required,
            paid_allowed=self.policy.paid_allowed,
            explicit_paid_authorization=self.policy.explicit_paid_authorization,
            deterministic_seed_required=True,
            reference_conditioning_required=False,
            image_to_video_required=True,
            min_width=width,
            min_height=height,
            min_duration_seconds=duration_ms / 1000.0,
            max_vram_mb=self.policy.max_vram_mb,
            min_quality_rank=self.policy.min_quality_rank,
        )

    def plan(self, *, motion_story_job_id: str) -> VideoEnhancementPlan:
        context = self._fallback_context(motion_story_job_id)
        highlights, score, tier = self._highlight_context(context["source_envelope_ids"], context["source_event_ids"])
        fallback = context["fallback"]
        if not self.policy.enabled:
            body = {
                "story_id": context["story_id"],
                "motion_story_job_id": motion_story_job_id,
                "fallback_artifact_id": fallback["artifact_id"],
                "fallback_uri": fallback["uri"],
                "fallback_digest": fallback["digest"],
                "eligible": False,
                "reason_code": "video_enhancement_disabled",
                "highlight_score": score,
                "treatment": EnhancementTreatment.MOTION_STORY_FALLBACK.value,
                "selected_shot_count": 0,
                "specs": [],
                "fallback_motion_story_ready": True,
                "canonical_authority": False,
                "presentation_can_mutate_simulation": False,
            }
            plan = VideoEnhancementPlan.model_validate({**body, "digest": payload_digest(body)})
            validate_plan(plan)
            return plan
        if score < self.policy.minimum_highlight_score:
            body = {
                "story_id": context["story_id"],
                "motion_story_job_id": motion_story_job_id,
                "fallback_artifact_id": fallback["artifact_id"],
                "fallback_uri": fallback["uri"],
                "fallback_digest": fallback["digest"],
                "eligible": False,
                "reason_code": "highlight_below_video_threshold" if highlights else "no_persisted_highlight",
                "highlight_score": score,
                "treatment": EnhancementTreatment.MOTION_STORY_FALLBACK.value,
                "selected_shot_count": 0,
                "specs": [],
                "fallback_motion_story_ready": True,
                "canonical_authority": False,
                "presentation_can_mutate_simulation": False,
            }
            plan = VideoEnhancementPlan.model_validate({**body, "digest": payload_digest(body)})
            validate_plan(plan)
            return plan

        treatment = (
            EnhancementTreatment.CINEMATIC_PRIORITY
            if score >= self.policy.cinematic_score
            else EnhancementTreatment.PARTIAL_ANIMATION
        )
        desired = self.policy.cinematic_animation_shots if treatment == EnhancementTreatment.CINEMATIC_PRIORITY else self.policy.partial_animation_shots
        candidates: list[VideoSourceShot] = []
        for shot in context["shots"]:
            try:
                candidates.append(self._image_for_shot(shot, context["chapter_id"], context["source_event_ids"]))
            except VideoEnhancementError as exc:
                if "shorter than configured" in str(exc):
                    continue
                raise
        candidates.sort(key=lambda item: (-item.animation_duration_ms, item.shot_index, item.source_image_artifact_id))
        selected = tuple(sorted(candidates[:desired], key=lambda item: item.shot_index))
        if not selected:
            body = {
                "story_id": context["story_id"],
                "motion_story_job_id": motion_story_job_id,
                "fallback_artifact_id": fallback["artifact_id"],
                "fallback_uri": fallback["uri"],
                "fallback_digest": fallback["digest"],
                "eligible": False,
                "reason_code": "no_eligible_short_shots",
                "highlight_score": score,
                "treatment": EnhancementTreatment.MOTION_STORY_FALLBACK.value,
                "selected_shot_count": 0,
                "specs": [],
                "fallback_motion_story_ready": True,
                "canonical_authority": False,
                "presentation_can_mutate_simulation": False,
            }
            plan = VideoEnhancementPlan.model_validate({**body, "digest": payload_digest(body)})
            validate_plan(plan)
            return plan

        highlight_ids = tuple(sorted(item.highlight_id for item in highlights))
        specs: list[VideoEnhancementSpec] = []
        for source_shot in selected:
            seed = _stable_seed(
                context["story_id"],
                source_shot.shot_index,
                source_shot.source_image_digest,
                score,
                self.policy.digest,
            )
            spec_id = _stable_id(
                "video_enhancement_spec",
                context["story_id"],
                source_shot.shot_index,
                source_shot.source_image_artifact_id,
                seed,
                self.policy.digest,
            )
            body = {
                "protocol": PROTOCOL,
                "implementation_version": IMPLEMENTATION_VERSION,
                "phase": PHASE,
                "spec_id": spec_id,
                "story_id": context["story_id"],
                "chapter_id": context["chapter_id"],
                "motion_story_job_id": motion_story_job_id,
                "fallback_artifact_id": fallback["artifact_id"],
                "fallback_uri": fallback["uri"],
                "fallback_digest": fallback["digest"],
                "fallback_manifest_artifact_id": context["manifest_artifact"]["artifact_id"],
                "fallback_manifest_digest": context["manifest_artifact"]["digest"],
                "highlight_ids": list(highlight_ids),
                "highlight_score": score,
                "highlight_tier": tier.value,
                "treatment": treatment.value,
                "source_shot": source_shot.model_dump(mode="json"),
                "source_envelope_ids": list(context["source_envelope_ids"]),
                "source_event_ids": list(context["source_event_ids"]),
                "deterministic_seed": seed,
                "width": context["width"],
                "height": context["height"],
                "fps": context["fps"],
                "provider_request": self._provider_request(
                    width=context["width"], height=context["height"], duration_ms=source_shot.animation_duration_ms
                ).model_dump(mode="json"),
                "provider_profile_version": PROVIDER_PROFILE_VERSION,
                "policy_digest": self.policy.digest,
                "fallback_motion_story_ready": True,
                "image_to_video_required": True,
                "video_diffusion_required": False,
                "canonical_authority": False,
                "presentation_can_mutate_simulation": False,
                "unreal_dependency": False,
                "cloud_api_required": False,
                "paid_provider_required": False,
            }
            spec = VideoEnhancementSpec.model_validate({**body, "digest": payload_digest(body)})
            validate_video_spec(spec)
            specs.append(spec)
        plan_body = {
            "story_id": context["story_id"],
            "motion_story_job_id": motion_story_job_id,
            "fallback_artifact_id": fallback["artifact_id"],
            "fallback_uri": fallback["uri"],
            "fallback_digest": fallback["digest"],
            "eligible": True,
            "reason_code": "eligible_local_video_enhancement",
            "highlight_score": score,
            "treatment": treatment.value,
            "selected_shot_count": len(specs),
            "specs": [item.model_dump(mode="json") for item in specs],
            "fallback_motion_story_ready": True,
            "canonical_authority": False,
            "presentation_can_mutate_simulation": False,
        }
        plan = VideoEnhancementPlan.model_validate({**plan_body, "digest": payload_digest(plan_body)})
        validate_plan(plan)
        return plan

    def _estimate_gpu_ms(self, descriptor: ProviderDescriptor) -> int:
        return max(1, int(round(descriptor.estimated_runtime_seconds * 1000.0)))

    def _budget_used_ms(self, session: Session, window_key: str) -> int:
        rows = session.scalars(
            select(VideoGpuReservationRow).where(VideoGpuReservationRow.window_key == window_key)
        ).all()
        total = 0
        for row in rows:
            if row.status in {GpuReservationStatus.COMPLETED.value, GpuReservationStatus.FAILED.value}:
                total += row.actual_gpu_ms
            else:
                total += row.reserved_gpu_ms
        return total

    def _reserve_gpu(self, job_id: str, *, window_key: str, provider_id: str) -> bool:
        if not window_key.strip():
            raise VideoEnhancementError("GPU scheduling window key must be non-empty")
        descriptor = self._descriptors.get(provider_id)
        if descriptor is None:
            raise VideoEnhancementError("GPU reservation references unknown executable provider")
        estimated = self._estimate_gpu_ms(descriptor)
        reserved = estimated * self.policy.max_attempts
        reservation_id = _stable_id("video_gpu_reservation", job_id)
        with self._lock:
            with Session(self.media.engine) as session:
                existing = session.get(VideoGpuReservationRow, reservation_id)
                if existing is not None:
                    if existing.job_id != job_id or existing.provider_id != provider_id:
                        raise VideoEnhancementError("GPU reservation identity conflict")
                    return True
                used = self._budget_used_ms(session, window_key)
                if used + reserved > self.policy.max_gpu_ms_per_window:
                    return False
                session.add(
                    VideoGpuReservationRow(
                        reservation_id=reservation_id,
                        job_id=job_id,
                        window_key=window_key,
                        provider_id=provider_id,
                        estimated_gpu_ms_per_attempt=estimated,
                        reserved_gpu_ms=reserved,
                        actual_gpu_ms=0,
                        status=GpuReservationStatus.RESERVED.value,
                    )
                )
                session.commit()
                return True

    def enqueue_spec(self, spec: VideoEnhancementSpec, *, gpu_window_key: str, priority: int | None = None) -> MediaJob:
        validate_video_spec(spec)
        effective_priority = priority if priority is not None else 1000 + spec.highlight_score * 10 - spec.source_shot.shot_index
        job = self.media.enqueue_job(
            job_type=JOB_TYPE,
            payload={
                "protocol": PROTOCOL,
                "implementation_version": IMPLEMENTATION_VERSION,
                "phase": PHASE,
                "spec": spec.model_dump(mode="json"),
            },
            dependencies=(spec.motion_story_job_id, spec.source_shot.source_image_job_id),
            provider_request=spec.provider_request,
            priority=effective_priority,
            max_attempts=self.policy.max_attempts,
        )
        selection = self.media.route_job(job.job_id, self.router, self.provider_policy)
        refreshed = self.media.get_job(job.job_id)
        if refreshed is None:
            raise VideoEnhancementError("video enhancement job disappeared after routing")
        if not selection.selected or refreshed.selected_provider_id is None:
            return refreshed
        if not self._reserve_gpu(refreshed.job_id, window_key=gpu_window_key, provider_id=refreshed.selected_provider_id):
            self.media.hold_job(refreshed.job_id, reason_code="gpu_budget_exhausted")
        final = self.media.get_job(refreshed.job_id)
        if final is None:
            raise VideoEnhancementError("video enhancement job disappeared after GPU scheduling")
        return final

    def enqueue_plan(self, plan: VideoEnhancementPlan, *, gpu_window_key: str) -> tuple[MediaJob, ...]:
        validate_plan(plan)
        if not plan.eligible:
            return ()
        return tuple(self.enqueue_spec(spec, gpu_window_key=gpu_window_key) for spec in plan.specs)

    def reschedule_held(self, job_id: str, *, gpu_window_key: str) -> MediaJob:
        job = self.media.get_job(job_id)
        if job is None or job.job_type != JOB_TYPE or job.status != JobStatus.HELD:
            raise VideoEnhancementError("only a held video-enhancement job can be rescheduled")
        if job.selected_provider_id is None:
            self.media.route_job(job_id, self.router, self.provider_policy)
            job = self.media.get_job(job_id)
            if job is None or job.selected_provider_id is None:
                return job  # type: ignore[return-value]
        if not self._reserve_gpu(job_id, window_key=gpu_window_key, provider_id=job.selected_provider_id):
            self.media.hold_job(job_id, reason_code="gpu_budget_exhausted")
            return self.media.get_job(job_id)  # type: ignore[return-value]
        return self.media.release_held(job_id)

    @staticmethod
    def _spec_from_job(job: MediaJob) -> VideoEnhancementSpec:
        if job.job_type != JOB_TYPE:
            raise VideoEnhancementError("video enhancement worker received wrong job type")
        payload = job.payload
        if payload.get("protocol") != PROTOCOL or payload.get("implementation_version") != IMPLEMENTATION_VERSION or payload.get("phase") != PHASE:
            raise VideoEnhancementError("video enhancement job payload protocol/version mismatch")
        spec = VideoEnhancementSpec.model_validate(payload.get("spec"))
        validate_video_spec(spec)
        if job.provider_request != spec.provider_request:
            raise VideoEnhancementError("video enhancement durable provider request diverged from spec")
        expected_dependencies = tuple(sorted(set((spec.motion_story_job_id, spec.source_shot.source_image_job_id))))
        if job.dependency_job_ids != expected_dependencies:
            raise VideoEnhancementError("video enhancement durable dependencies diverged from provenance")
        return spec

    def _gpu_busy(self) -> bool:
        with self._lock:
            with Session(self.media.engine) as session:
                lock = session.get(VideoGpuLockRow, self._GPU_LOCK_NAME)
                return lock is not None and lock.job_id is not None

    def _acquire_gpu(self, job_id: str) -> bool:
        reservation_id = _stable_id("video_gpu_reservation", job_id)
        with self._lock:
            with Session(self.media.engine) as session:
                reservation = session.get(VideoGpuReservationRow, reservation_id)
                lock = session.get(VideoGpuLockRow, self._GPU_LOCK_NAME)
                if reservation is None or lock is None:
                    return False
                if lock.job_id not in {None, job_id}:
                    return False
                lock.job_id = job_id
                reservation.status = GpuReservationStatus.RUNNING.value
                session.commit()
                return True

    def _release_gpu(self, job_id: str, *, terminal: bool, success: bool, consumed_gpu_ms: int) -> None:
        reservation_id = _stable_id("video_gpu_reservation", job_id)
        with self._lock:
            with Session(self.media.engine) as session:
                reservation = session.get(VideoGpuReservationRow, reservation_id)
                lock = session.get(VideoGpuLockRow, self._GPU_LOCK_NAME)
                if reservation is None or lock is None:
                    raise VideoEnhancementError("video GPU scheduler lost reservation/lock state")
                reservation.actual_gpu_ms += max(0, int(consumed_gpu_ms))
                reservation.status = (
                    GpuReservationStatus.COMPLETED.value
                    if terminal and success
                    else GpuReservationStatus.FAILED.value
                    if terminal
                    else GpuReservationStatus.RESERVED.value
                )
                if lock.job_id == job_id:
                    lock.job_id = None
                session.commit()

    def recover_gpu_scheduler(self) -> int:
        """Clear a stale GPU lock after MediaPersistence recovers interrupted jobs."""
        recovered = 0
        with self._lock:
            with Session(self.media.engine) as session:
                lock = session.get(VideoGpuLockRow, self._GPU_LOCK_NAME)
                if lock is None or lock.job_id is None:
                    return 0
                job = self.media.get_job(lock.job_id)
                if job is not None and job.status == JobStatus.RUNNING:
                    return 0
                reservation = session.scalar(
                    select(VideoGpuReservationRow).where(VideoGpuReservationRow.job_id == lock.job_id)
                )
                if reservation is not None and reservation.status == GpuReservationStatus.RUNNING.value:
                    if job is not None and job.status == JobStatus.FAILED:
                        reservation.status = GpuReservationStatus.FAILED.value
                    elif job is not None and job.status == JobStatus.COMPLETED:
                        reservation.status = GpuReservationStatus.COMPLETED.value
                    else:
                        reservation.status = GpuReservationStatus.RESERVED.value
                lock.job_id = None
                session.commit()
                recovered = 1
        return recovered

    def _relative_paths(self, spec: VideoEnhancementSpec) -> tuple[str, str]:
        base = Path("video-enhancements") / spec.story_id
        stem = f"shot-{spec.source_shot.shot_index:02d}-{spec.spec_id}"
        return (base / f"{stem}.mp4").as_posix(), (base / f"{stem}.json").as_posix()

    @staticmethod
    def _write_atomic(path: Path, payload: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f"{path.name}.tmp")
        temporary.write_bytes(payload)
        temporary.replace(path)

    def run_next(self, *, worker_id: str = "underreach-local-video-worker") -> VideoEnhancementResult | None:
        if self._gpu_busy():
            return None
        lease = self.media.claim_next(worker_id)
        if lease is None:
            return None
        job = lease.job
        if job.job_type != JOB_TYPE:
            self.media.fail_job(job.job_id, reason_code="wrong_video_worker_job_type", retryable=False)
            return None
        try:
            spec = self._spec_from_job(job)
        except Exception:
            self.media.fail_job(job.job_id, reason_code="invalid_video_enhancement_spec", retryable=False)
            raise
        if not self._acquire_gpu(job.job_id):
            failed = self.media.fail_job(job.job_id, reason_code="gpu_reservation_missing_or_busy", retryable=True)
            return VideoEnhancementResult(
                spec_id=spec.spec_id,
                story_id=spec.story_id,
                job_id=job.job_id,
                status=failed.status,
                fallback_artifact_id=spec.fallback_artifact_id,
                reason_code="gpu_reservation_missing_or_busy",
            )
        provider_id = job.selected_provider_id
        provider = self._executors.get(provider_id or "")
        descriptor = self._descriptors.get(provider_id or "")
        estimated_gpu_ms = self._estimate_gpu_ms(descriptor) if descriptor is not None else 1
        if provider is None or descriptor is None:
            current = self.media.get_job(job.job_id)
            terminal = current is not None and current.attempt_count >= current.max_attempts
            self._release_gpu(job.job_id, terminal=terminal, success=False, consumed_gpu_ms=estimated_gpu_ms)
            failed = self.media.fail_job(job.job_id, reason_code="video_executor_unavailable", retryable=True)
            return VideoEnhancementResult(
                spec_id=spec.spec_id,
                story_id=spec.story_id,
                job_id=job.job_id,
                status=failed.status,
                fallback_artifact_id=spec.fallback_artifact_id,
                provider_id=provider_id,
                reason_code="video_executor_unavailable",
            )
        source_image = self._verify_file(spec.source_shot.source_image_uri, spec.source_shot.source_image_digest)
        video_rel, sidecar_rel = self._relative_paths(spec)
        video_path = self.media_root / video_rel
        sidecar_path = self.media_root / sidecar_rel
        work_path = video_path.with_suffix(".render.mp4")
        if work_path.exists():
            work_path.unlink()
        request = VideoRenderRequest(
            spec=spec,
            job_id=job.job_id,
            attempt_id=lease.attempt_id,
            source_image_path=source_image,
            output_path=work_path,
        )
        try:
            output = provider.animate(request)
            if not work_path.is_file():
                raise VideoEnhancementError("video provider returned without file-backed MP4")
            probe = self._probe_video(
                work_path,
                width=spec.width,
                height=spec.height,
                duration_ms=spec.source_shot.animation_duration_ms,
            )
        except Exception as exc:
            self.media.record_provider_execution(
                job_id=job.job_id,
                attempt_id=lease.attempt_id,
                provider_id=descriptor.provider_id,
                status="failed",
                estimated_cost_microusd=descriptor.estimated_cost_microusd,
                actual_cost_microusd=0,
                estimated_gpu_ms=estimated_gpu_ms,
                actual_gpu_ms=estimated_gpu_ms,
                metadata={
                    "reason_code": "video_enhancement_failed",
                    "error_type": type(exc).__name__,
                    "fallback_motion_story_ready": True,
                    "fallback_artifact_id": spec.fallback_artifact_id,
                    "presentation_only": True,
                },
            )
            will_be_terminal = job.attempt_count >= job.max_attempts
            self._release_gpu(job.job_id, terminal=will_be_terminal, success=False, consumed_gpu_ms=estimated_gpu_ms)
            failed = self.media.fail_job(job.job_id, reason_code="video_enhancement_failed", retryable=True)
            return VideoEnhancementResult(
                spec_id=spec.spec_id,
                story_id=spec.story_id,
                job_id=job.job_id,
                status=failed.status,
                fallback_artifact_id=spec.fallback_artifact_id,
                provider_id=descriptor.provider_id,
                reason_code="video_enhancement_failed",
            )

        video_path.parent.mkdir(parents=True, exist_ok=True)
        work_path.replace(video_path)
        video_bytes = video_path.read_bytes()
        video_digest = sha256(video_bytes).hexdigest()
        sidecar_body = {
            "protocol": PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "phase": PHASE,
            "spec_id": spec.spec_id,
            "story_id": spec.story_id,
            "job_id": job.job_id,
            "attempt_id": lease.attempt_id,
            "provider_id": descriptor.provider_id,
            "provider_local": descriptor.local,
            "provider_paid": descriptor.paid,
            "highlight_ids": list(spec.highlight_ids),
            "highlight_score": spec.highlight_score,
            "highlight_tier": spec.highlight_tier.value,
            "treatment": spec.treatment.value,
            "source_shot": spec.source_shot.model_dump(mode="json"),
            "source_envelope_ids": list(spec.source_envelope_ids),
            "source_event_ids": list(spec.source_event_ids),
            "fallback_motion_story_ready": True,
            "fallback_artifact_id": spec.fallback_artifact_id,
            "fallback_uri": spec.fallback_uri,
            "fallback_digest": spec.fallback_digest,
            "deterministic_seed": spec.deterministic_seed,
            "output_uri": video_rel,
            "output_sha256": video_digest,
            "ffprobe": probe,
            "provider_metadata": output.metadata,
            "estimated_gpu_ms": estimated_gpu_ms,
            "actual_gpu_ms": output.actual_gpu_ms,
            "video_diffusion_required": False,
            "canonical_authority": False,
            "presentation_can_mutate_simulation": False,
            "unreal_dependency": False,
            "cloud_api_required": False,
            "paid_provider_required": False,
        }
        sidecar_bytes = canonical_json(sidecar_body).encode("utf-8")
        sidecar_digest = sha256(sidecar_bytes).hexdigest()
        self._write_atomic(sidecar_path, sidecar_bytes)
        video_artifact = self.media.record_artifact(
            job_id=job.job_id,
            artifact_kind="video/mp4",
            uri=video_rel,
            digest=video_digest,
            metadata={
                "spec_id": spec.spec_id,
                "story_id": spec.story_id,
                "shot_index": spec.source_shot.shot_index,
                "fallback_artifact_id": spec.fallback_artifact_id,
                "source_event_ids": list(spec.source_event_ids),
                "provider_id": descriptor.provider_id,
                "presentation_only": True,
            },
        )
        sidecar_artifact = self.media.record_artifact(
            job_id=job.job_id,
            artifact_kind="application/json",
            uri=sidecar_rel,
            digest=sidecar_digest,
            metadata={
                "spec_id": spec.spec_id,
                "video_artifact_id": video_artifact,
                "fallback_artifact_id": spec.fallback_artifact_id,
                "presentation_only": True,
            },
        )
        self.media.record_provider_execution(
            job_id=job.job_id,
            attempt_id=lease.attempt_id,
            provider_id=descriptor.provider_id,
            status="completed",
            estimated_cost_microusd=descriptor.estimated_cost_microusd,
            actual_cost_microusd=descriptor.estimated_cost_microusd if descriptor.paid else 0,
            estimated_gpu_ms=estimated_gpu_ms,
            actual_gpu_ms=output.actual_gpu_ms,
            metadata={
                "spec_id": spec.spec_id,
                "video_artifact_id": video_artifact,
                "fallback_artifact_id": spec.fallback_artifact_id,
                "fallback_motion_story_ready": True,
                "presentation_only": True,
            },
        )
        self._release_gpu(job.job_id, terminal=True, success=True, consumed_gpu_ms=output.actual_gpu_ms)
        completed = self.media.complete_job(
            job.job_id,
            resource_usage={
                "actual_gpu_ms": output.actual_gpu_ms,
                "output_bytes": len(video_bytes),
                "provider_id": descriptor.provider_id,
                "fallback_artifact_id": spec.fallback_artifact_id,
            },
        )
        return VideoEnhancementResult(
            spec_id=spec.spec_id,
            story_id=spec.story_id,
            job_id=job.job_id,
            status=completed.status,
            fallback_artifact_id=spec.fallback_artifact_id,
            provider_id=descriptor.provider_id,
            video_artifact_id=video_artifact,
            sidecar_artifact_id=sidecar_artifact,
            output_uri=video_rel,
            output_digest=video_digest,
        )

    def scheduler_snapshot(self) -> dict[str, Any]:
        with self._lock:
            with Session(self.media.engine) as session:
                rows = session.scalars(
                    select(VideoGpuReservationRow).order_by(VideoGpuReservationRow.window_key, VideoGpuReservationRow.job_id)
                ).all()
                lock = session.get(VideoGpuLockRow, self._GPU_LOCK_NAME)
                reservations = [
                    {
                        "reservation_id": row.reservation_id,
                        "job_id": row.job_id,
                        "window_key": row.window_key,
                        "provider_id": row.provider_id,
                        "estimated_gpu_ms_per_attempt": row.estimated_gpu_ms_per_attempt,
                        "reserved_gpu_ms": row.reserved_gpu_ms,
                        "actual_gpu_ms": row.actual_gpu_ms,
                        "status": row.status,
                    }
                    for row in rows
                ]
        body = {
            "protocol": PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "phase": PHASE,
            "max_gpu_ms_per_window": self.policy.max_gpu_ms_per_window,
            "max_retries_per_shot": self.policy.max_retries_per_shot,
            "serialized_gpu_work": True,
            "active_job_id": lock.job_id if lock is not None else None,
            "reservations": reservations,
            "reservation_count": len(reservations),
            "reservation_digest": payload_digest(reservations),
        }
        return {**body, "digest": payload_digest(body)}

    def snapshot(self) -> dict[str, Any]:
        media_snapshot = self.media.snapshot()
        jobs = [item for item in media_snapshot["jobs"] if item["job_type"] == JOB_TYPE]
        job_ids = {item["job_id"] for item in jobs}
        artifacts = [item for item in media_snapshot["artifacts"] if item["job_id"] in job_ids]
        executions = [item for item in media_snapshot["provider_executions"] if item["job_id"] in job_ids]
        schedule = self.scheduler_snapshot()
        body = {
            "protocol": PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "phase": PHASE,
            "authoritative": False,
            "canonical_owner": "deterministic_simulation",
            "presentation_can_mutate_simulation": False,
            "unreal_dependency": False,
            "required_cloud_api": False,
            "required_paid_provider": False,
            "motion_story_fallback_guaranteed": True,
            "minimum_highlight_score": self.policy.minimum_highlight_score,
            "cinematic_score": self.policy.cinematic_score,
            "max_gpu_hours_per_window": self.policy.max_gpu_hours_per_window,
            "max_retries_per_shot": self.policy.max_retries_per_shot,
            "policy": self.policy.model_dump(mode="json"),
            "policy_digest": self.policy.digest,
            "providers": [item.model_dump(mode="json") for item in self.router.providers()],
            "jobs": jobs,
            "job_count": len(jobs),
            "job_digest": payload_digest(jobs),
            "artifacts": artifacts,
            "artifact_count": len(artifacts),
            "artifact_digest": payload_digest(artifacts),
            "provider_executions": executions,
            "provider_execution_count": len(executions),
            "provider_execution_digest": payload_digest(executions),
            "scheduler": schedule,
        }
        return {**body, "digest": payload_digest(body)}


__all__ = [
    "PROTOCOL",
    "IMPLEMENTATION_VERSION",
    "PHASE",
    "JOB_TYPE",
    "PROVIDER_PROFILE_VERSION",
    "EnhancementTreatment",
    "GpuReservationStatus",
    "VideoEnhancementPolicy",
    "VideoSourceShot",
    "VideoEnhancementSpec",
    "VideoEnhancementPlan",
    "VideoRenderRequest",
    "VideoRenderOutput",
    "VideoEnhancementResult",
    "VideoEnhancementError",
    "HeadlessVideoProvider",
    "DeterministicLocalI2VProvider",
    "LocalVideoEnhancementService",
    "validate_source_shot",
    "validate_video_spec",
    "validate_plan",
]
