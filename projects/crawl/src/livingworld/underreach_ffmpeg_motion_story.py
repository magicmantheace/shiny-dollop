"""Automated headless FFmpeg motion-story production for Underreach Phase 30.5.9.

30.5.9 is the guaranteed no-video-diffusion promotional path. It consumes only
completed media-owned 30.5.7 scene still artifacts plus a completed 30.5.8
verified narration/caption package. The worker assembles deterministic 9:16 MP4
motion stories with still motion, transitions, burned captions, optional verified
narration, optional royalty-safe local music/SFX, loudness normalization,
ducking, fades, and final encoding through a local FFmpeg binary.

This module never opens the canonical Crawl database, never invokes Unreal, never
uses a video-generation model, never silently escalates to cloud/paid work, and
never feeds presentation output back into canonical simulation truth.
"""
from __future__ import annotations

from enum import StrEnum
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .runtime_checkpoint import canonical_json, payload_digest
from .underreach_headless_local_image_production import JOB_TYPE as IMAGE_JOB_TYPE
from .underreach_media_foundation import JobStatus, MediaJob, MediaPersistence
from .underreach_narration_captions_audio import (
    PACKAGE_JOB_TYPE,
    VOICE_JOB_TYPE,
    NarrationMode,
    NarrationPackageSpec,
    SoundAssetKind,
    SoundAssetReference,
    validate_package_spec,
)


PROTOCOL = "underreach.ffmpeg-motion-story.v1"
IMPLEMENTATION_VERSION = "30.5.9"
PHASE = "30.5"
JOB_TYPE = "underreach.motion-story.assemble"
FFMPEG_PROFILE_VERSION = "underreach.ffmpeg-motion-story.v1"
EDITOR_PROVIDER_ID = "local_ffmpeg"
DEFAULT_WIDTH = 1080
DEFAULT_HEIGHT = 1920
DEFAULT_FPS = 30


class MotionStoryError(ValueError):
    """Raised when 30.5.9 media-only assembly invariants are violated."""


class MotionPattern(StrEnum):
    PUSH_IN = "push_in"
    PUSH_OUT = "push_out"
    DRIFT_LEFT = "drift_left"
    DRIFT_RIGHT = "drift_right"


class MotionStoryPolicy(BaseModel):
    """Deterministic 9:16 local FFmpeg assembly policy."""

    model_config = ConfigDict(frozen=True)

    width: int = Field(default=DEFAULT_WIDTH, ge=180, le=2160)
    height: int = Field(default=DEFAULT_HEIGHT, ge=320, le=3840)
    fps: int = Field(default=DEFAULT_FPS, ge=10, le=60)
    minimum_duration_seconds: float = Field(default=10.0, ge=2.0, le=120.0)
    maximum_duration_seconds: float = Field(default=60.0, ge=2.0, le=300.0)
    target_shot_seconds: float = Field(default=4.0, ge=1.0, le=10.0)
    minimum_shots: int = Field(default=3, ge=1, le=12)
    maximum_shots: int = Field(default=9, ge=1, le=20)
    transition_ms: int = Field(default=350, ge=50, le=2000)
    burn_captions: bool = True
    include_voice_when_available: bool = True
    include_sound_assets: bool = True
    music_volume: float = Field(default=0.18, ge=0.0, le=1.0)
    sfx_volume: float = Field(default=0.35, ge=0.0, le=1.0)
    loudness_target_lufs: float = Field(default=-16.0, ge=-30.0, le=-8.0)
    audio_fade_in_ms: int = Field(default=200, ge=50, le=5000)
    audio_fade_out_ms: int = Field(default=500, ge=50, le=5000)
    video_fade_ms: int = Field(default=250, ge=50, le=2000)
    crf: int = Field(default=23, ge=0, le=51)
    preset: str = "veryfast"
    max_attempts: int = Field(default=2, ge=1, le=10)
    ffmpeg_timeout_seconds: int = Field(default=600, ge=10, le=7200)

    @model_validator(mode="after")
    def validate_policy(self) -> "MotionStoryPolicy":
        if self.width * 16 != self.height * 9:
            raise ValueError("motion-story output must be exact 9:16")
        if self.minimum_duration_seconds > self.maximum_duration_seconds:
            raise ValueError("minimum duration cannot exceed maximum duration")
        if self.minimum_shots > self.maximum_shots:
            raise ValueError("minimum shots cannot exceed maximum shots")
        if not self.preset.strip():
            raise ValueError("FFmpeg preset must be non-empty")
        return self

    @property
    def digest(self) -> str:
        return payload_digest(self.model_dump(mode="json"))


class MotionStoryArtifactInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    artifact_id: str
    job_id: str
    artifact_kind: str
    uri: str
    digest: str
    chapter_id: str
    source_envelope_id: str | None = None
    source_event_ids: tuple[str, ...] = ()
    metadata_digest: str


class ResolvedSoundAsset(BaseModel):
    model_config = ConfigDict(frozen=True)

    asset_id: str
    kind: SoundAssetKind
    relative_uri: str
    license_label: str
    source_note: str | None = None
    file_sha256: str
    digest: str


class MotionStoryShot(BaseModel):
    model_config = ConfigDict(frozen=True)

    index: int = Field(ge=0)
    source_image_artifact_id: str
    pattern: MotionPattern
    timeline_start_ms: int = Field(ge=0)
    duration_ms: int = Field(gt=0)
    transition_ms: int = Field(ge=0)
    deterministic_seed: int = Field(ge=0)
    digest: str


class MotionStorySpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    protocol: str = PROTOCOL
    implementation_version: str = IMPLEMENTATION_VERSION
    phase: str = PHASE
    story_id: str
    chapter_id: str
    narration_package_id: str
    verification_id: str
    verification_digest: str
    draft_id: str
    draft_digest: str
    manifest_id: str
    package_job_id: str
    caption_artifact_id: str
    caption_uri: str
    caption_digest: str
    voice_artifact_id: str | None = None
    voice_uri: str | None = None
    voice_digest: str | None = None
    narration_mode: NarrationMode
    image_inputs: tuple[MotionStoryArtifactInput, ...]
    sound_assets: tuple[ResolvedSoundAsset, ...] = ()
    missing_sound_asset_ids: tuple[str, ...] = ()
    source_envelope_ids: tuple[str, ...]
    source_event_ids: tuple[str, ...]
    shots: tuple[MotionStoryShot, ...]
    duration_ms: int = Field(gt=0)
    output_width: int = Field(ge=180, le=2160)
    output_height: int = Field(ge=320, le=3840)
    fps: int = Field(ge=10, le=60)
    transition_ms: int = Field(ge=0)
    burn_captions: bool = True
    audio_present: bool = False
    loudness_normalization: bool = False
    music_ducking: bool = False
    audio_fades: bool = False
    audio_mixing: bool = False
    final_encode: bool = True
    deterministic_seed: int = Field(ge=0)
    ffmpeg_profile_version: str = FFMPEG_PROFILE_VERSION
    policy_digest: str
    video_model_dependency: bool = False
    video_diffusion_used: bool = False
    unreal_dependency: bool = False
    cloud_api_required: bool = False
    paid_provider_required: bool = False
    canonical_authority: bool = False
    presentation_can_mutate_simulation: bool = False
    digest: str


class MotionStoryResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    story_id: str
    job_id: str
    status: JobStatus
    output_artifact_id: str | None = None
    caption_artifact_id: str | None = None
    manifest_artifact_id: str | None = None
    output_uri: str | None = None
    output_digest: str | None = None
    manifest_uri: str | None = None
    manifest_digest: str | None = None
    width: int | None = None
    height: int | None = None
    duration_ms: int | None = None
    audio_stream_present: bool | None = None
    reason_code: str | None = None
    canonical_authority: bool = False
    presentation_can_mutate_simulation: bool = False


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
        raise MotionStoryError("motion-story input URI must be a safe relative media path")
    return value


def _resolved_sound_asset(reference: SoundAssetReference, file_sha256: str) -> ResolvedSoundAsset:
    body = {
        "asset_id": reference.asset_id,
        "kind": reference.kind.value,
        "relative_uri": reference.relative_uri,
        "license_label": reference.license_label,
        "source_note": reference.source_note,
        "file_sha256": file_sha256,
    }
    return ResolvedSoundAsset.model_validate({**body, "digest": payload_digest(body)})


def validate_motion_story_spec(spec: MotionStorySpec) -> bool:
    if spec.protocol != PROTOCOL or spec.implementation_version != IMPLEMENTATION_VERSION or spec.phase != PHASE:
        raise MotionStoryError("motion-story protocol/version mismatch")
    if spec.output_width * 16 != spec.output_height * 9:
        raise MotionStoryError("motion-story output is not exact 9:16")
    if not spec.image_inputs or not spec.shots:
        raise MotionStoryError("motion-story requires completed local still inputs and at least one shot")
    image_ids = tuple(item.artifact_id for item in spec.image_inputs)
    if image_ids != tuple(sorted(set(image_ids))):
        raise MotionStoryError("motion-story image inputs must be normalized")
    for image in spec.image_inputs:
        if image.artifact_kind != "image/png" or image.chapter_id != spec.chapter_id:
            raise MotionStoryError("motion-story image input is not a chapter-scoped PNG still")
        expected_provenance = payload_digest({
            "chapter_id": image.chapter_id,
            "source_envelope_id": image.source_envelope_id,
            "source_event_ids": list(image.source_event_ids),
        })
        if image.metadata_digest != expected_provenance:
            raise MotionStoryError("motion-story image provenance digest mismatch")
        _safe_relative_uri(image.uri)
    if tuple(sorted(set(spec.source_envelope_ids))) != spec.source_envelope_ids:
        raise MotionStoryError("motion-story source envelope provenance is not normalized")
    if tuple(sorted(set(spec.source_event_ids))) != spec.source_event_ids or not spec.source_event_ids:
        raise MotionStoryError("motion-story source event provenance is missing or not normalized")
    if tuple(sorted(set(spec.missing_sound_asset_ids))) != spec.missing_sound_asset_ids:
        raise MotionStoryError("missing sound asset IDs are not normalized")
    sound_ids = tuple(item.asset_id for item in spec.sound_assets)
    if sound_ids != tuple(sorted(set(sound_ids))):
        raise MotionStoryError("resolved sound asset IDs are not normalized")
    for asset in spec.sound_assets:
        _safe_relative_uri(asset.relative_uri)
        expected = payload_digest({
            "asset_id": asset.asset_id,
            "kind": asset.kind.value,
            "relative_uri": asset.relative_uri,
            "license_label": asset.license_label,
            "source_note": asset.source_note,
            "file_sha256": asset.file_sha256,
        })
        if asset.digest != expected:
            raise MotionStoryError("resolved sound asset digest mismatch")
    if not spec.caption_artifact_id or not spec.caption_digest or not spec.caption_uri.endswith(".srt"):
        raise MotionStoryError("motion-story requires completed SRT caption provenance")
    _safe_relative_uri(spec.caption_uri)
    if spec.voice_artifact_id is None:
        if spec.voice_uri is not None or spec.voice_digest is not None or spec.narration_mode != NarrationMode.CAPTION_ONLY:
            raise MotionStoryError("caption-only motion-story voice state is inconsistent")
    else:
        if not spec.voice_uri or not spec.voice_digest or spec.narration_mode != NarrationMode.NARRATED:
            raise MotionStoryError("narrated motion-story voice state is inconsistent")
        _safe_relative_uri(spec.voice_uri)
    if tuple(shot.index for shot in spec.shots) != tuple(range(len(spec.shots))):
        raise MotionStoryError("motion-story shot indexes are not contiguous")
    allowed_images = set(image_ids)
    for shot in spec.shots:
        if shot.source_image_artifact_id not in allowed_images:
            raise MotionStoryError("motion-story shot references an unknown image artifact")
        if shot.digest != _body_digest(shot):
            raise MotionStoryError("motion-story shot digest mismatch")
    if spec.shots[0].timeline_start_ms != 0:
        raise MotionStoryError("motion-story first shot must start at zero")
    for previous, current in zip(spec.shots, spec.shots[1:]):
        expected_start = previous.timeline_start_ms + previous.duration_ms - current.transition_ms
        if current.timeline_start_ms != expected_start:
            raise MotionStoryError("motion-story shot timeline/transition is inconsistent")
    final_end = spec.shots[-1].timeline_start_ms + spec.shots[-1].duration_ms
    if abs(final_end - spec.duration_ms) > 2:
        raise MotionStoryError("motion-story shot plan does not fill target duration")
    has_music = any(item.kind == SoundAssetKind.MUSIC for item in spec.sound_assets)
    expected_audio = spec.voice_artifact_id is not None or bool(spec.sound_assets)
    if spec.audio_present != expected_audio:
        raise MotionStoryError("motion-story audio-present flag diverged from inputs")
    if spec.loudness_normalization != expected_audio or spec.audio_fades != expected_audio:
        raise MotionStoryError("motion-story required audio processing flags diverged from inputs")
    if spec.music_ducking != (spec.voice_artifact_id is not None and has_music):
        raise MotionStoryError("motion-story ducking flag diverged from voice/music inputs")
    source_count = (1 if spec.voice_artifact_id is not None else 0) + len(spec.sound_assets)
    if spec.audio_mixing != (source_count > 1):
        raise MotionStoryError("motion-story mixing flag diverged from audio input count")
    if (
        spec.video_model_dependency
        or spec.video_diffusion_used
        or spec.unreal_dependency
        or spec.cloud_api_required
        or spec.paid_provider_required
        or spec.canonical_authority
        or spec.presentation_can_mutate_simulation
        or not spec.final_encode
    ):
        raise MotionStoryError("motion-story escaped guaranteed presentation-only FFmpeg path")
    if spec.ffmpeg_profile_version != FFMPEG_PROFILE_VERSION:
        raise MotionStoryError("motion-story FFmpeg profile version mismatch")
    if spec.digest != _body_digest(spec):
        raise MotionStoryError("motion-story spec digest mismatch")
    input_digest = payload_digest({
        "images": [item.model_dump(mode="json") for item in spec.image_inputs],
        "caption_artifact_id": spec.caption_artifact_id,
        "caption_digest": spec.caption_digest,
        "voice_artifact_id": spec.voice_artifact_id,
        "voice_digest": spec.voice_digest,
        "sound_assets": [item.model_dump(mode="json") for item in spec.sound_assets],
        "missing_sound_asset_ids": list(spec.missing_sound_asset_ids),
    })
    expected_story_id = _stable_id(
        "motion_story",
        spec.narration_package_id,
        input_digest,
        spec.ffmpeg_profile_version,
        spec.policy_digest,
    )
    if spec.story_id != expected_story_id:
        raise MotionStoryError("motion-story deterministic identity mismatch")
    return True


class AutomatedFfmpegMotionStoryService:
    """Plan and execute durable local FFmpeg motion-story assembly jobs."""

    def __init__(
        self,
        media: MediaPersistence,
        *,
        media_root: str | Path,
        policy: MotionStoryPolicy | None = None,
        ffmpeg_path: str | Path | None = None,
        ffprobe_path: str | Path | None = None,
    ) -> None:
        self.media = media
        self.media_root = Path(media_root)
        self.policy = policy or MotionStoryPolicy()
        self.ffmpeg_path = str(ffmpeg_path) if ffmpeg_path is not None else (shutil.which("ffmpeg") or "ffmpeg")
        self.ffprobe_path = str(ffprobe_path) if ffprobe_path is not None else (shutil.which("ffprobe") or "ffprobe")

    def initialize(self) -> None:
        self.media_root.mkdir(parents=True, exist_ok=True)

    def _snapshot_artifact(self, artifact_id: str) -> dict[str, Any]:
        matches = [item for item in self.media.snapshot()["artifacts"] if item["artifact_id"] == artifact_id]
        if len(matches) != 1:
            raise MotionStoryError("motion-story input requires exactly one persisted media artifact")
        return matches[0]

    def _job(self, job_id: str, *, expected_type: str | None = None, completed: bool = False) -> MediaJob:
        job = self.media.get_job(job_id)
        if job is None:
            raise MotionStoryError("motion-story input references an unknown media job")
        if expected_type is not None and job.job_type != expected_type:
            raise MotionStoryError("motion-story input job type mismatch")
        if completed and job.status != JobStatus.COMPLETED:
            raise MotionStoryError("motion-story input job must be completed")
        return job

    def _verify_file(self, uri: str, digest: str) -> Path:
        relative = _safe_relative_uri(uri)
        path = self.media_root.joinpath(*relative.parts)
        if not path.is_file():
            raise MotionStoryError("motion-story input artifact file is missing")
        actual = sha256(path.read_bytes()).hexdigest()
        if actual != digest:
            raise MotionStoryError("motion-story input artifact digest no longer matches file")
        return path

    def _image_input(self, artifact_id: str, chapter_id: str) -> MotionStoryArtifactInput:
        artifact = self._snapshot_artifact(artifact_id)
        if artifact["artifact_kind"] != "image/png":
            raise MotionStoryError("motion-story still input must be image/png")
        self._job(artifact["job_id"], expected_type=IMAGE_JOB_TYPE, completed=True)
        metadata = dict(artifact.get("metadata") or {})
        if metadata.get("chapter_id") != chapter_id:
            raise MotionStoryError("motion-story still does not belong to narration chapter")
        source_event_ids = tuple(sorted(set(metadata.get("source_event_ids") or [])))
        if not source_event_ids:
            raise MotionStoryError("motion-story still lacks canonical event provenance")
        source_envelope_id = metadata.get("source_envelope_id")
        self._verify_file(artifact["uri"], artifact["digest"])
        provenance = {
            "chapter_id": chapter_id,
            "source_envelope_id": source_envelope_id,
            "source_event_ids": list(source_event_ids),
        }
        return MotionStoryArtifactInput(
            artifact_id=artifact["artifact_id"],
            job_id=artifact["job_id"],
            artifact_kind=artifact["artifact_kind"],
            uri=artifact["uri"],
            digest=artifact["digest"],
            chapter_id=chapter_id,
            source_envelope_id=source_envelope_id,
            source_event_ids=source_event_ids,
            metadata_digest=payload_digest(provenance),
        )

    def _package(self, package_job_id: str) -> tuple[MediaJob, NarrationPackageSpec]:
        job = self._job(package_job_id, expected_type=PACKAGE_JOB_TYPE, completed=True)
        spec = NarrationPackageSpec.model_validate(job.payload.get("spec"))
        validate_package_spec(spec)
        return job, spec

    def _package_caption_artifact(self, package_job_id: str, package_id: str) -> dict[str, Any]:
        matches = [
            item
            for item in self.media.snapshot()["artifacts"]
            if item["job_id"] == package_job_id
            and item["artifact_kind"] == "text/srt"
            and (item.get("metadata") or {}).get("package_id") == package_id
        ]
        if len(matches) != 1:
            raise MotionStoryError("completed narration package must expose exactly one SRT artifact")
        self._verify_file(matches[0]["uri"], matches[0]["digest"])
        return matches[0]

    def _completed_voice_artifact(self, package_id: str, package_job_id: str) -> dict[str, Any] | None:
        if not self.policy.include_voice_when_available:
            return None
        jobs = [
            item
            for item in self.media.list_jobs()
            if item.job_type == VOICE_JOB_TYPE
            and package_job_id in item.dependency_job_ids
            and (item.payload.get("spec") or {}).get("package_id") == package_id
        ]
        completed_jobs = [item for item in jobs if item.status == JobStatus.COMPLETED]
        if len(completed_jobs) > 1:
            raise MotionStoryError("narration package resolved multiple completed voice jobs")
        if not completed_jobs:
            return None
        voice_job = completed_jobs[0]
        matches = [
            item
            for item in self.media.snapshot()["artifacts"]
            if item["job_id"] == voice_job.job_id
            and item["artifact_kind"] == "audio/wav"
            and (item.get("metadata") or {}).get("package_id") == package_id
        ]
        if len(matches) != 1:
            raise MotionStoryError("completed voice job must expose exactly one WAV artifact")
        self._verify_file(matches[0]["uri"], matches[0]["digest"])
        return matches[0]

    def _sound_assets(self, spec: NarrationPackageSpec) -> tuple[tuple[ResolvedSoundAsset, ...], tuple[str, ...]]:
        if not self.policy.include_sound_assets:
            return (), ()
        resolved: list[ResolvedSoundAsset] = []
        missing: list[str] = []
        for asset in sorted(spec.sound_assets, key=lambda item: item.asset_id):
            SoundAssetReference.model_validate(asset.model_dump(mode="json"))
            relative = _safe_relative_uri(asset.relative_uri)
            path = self.media_root.joinpath(*relative.parts)
            if not path.is_file():
                missing.append(asset.asset_id)
                continue
            digest = sha256(path.read_bytes()).hexdigest()
            resolved.append(_resolved_sound_asset(asset, digest))
        return tuple(sorted(resolved, key=lambda item: item.asset_id)), tuple(sorted(set(missing)))

    def _shots(
        self,
        *,
        story_basis: str,
        image_inputs: tuple[MotionStoryArtifactInput, ...],
        duration_ms: int,
    ) -> tuple[MotionStoryShot, ...]:
        target_ms = max(1, int(round(self.policy.target_shot_seconds * 1000.0)))
        desired = (duration_ms + target_ms - 1) // target_ms
        count = max(self.policy.minimum_shots, min(self.policy.maximum_shots, desired))
        transition = min(self.policy.transition_ms, max(50, duration_ms // max(2, count * 4)))
        total_raw = duration_ms + transition * (count - 1)
        base = total_raw // count
        remainder = total_raw % count
        cursor = 0
        patterns = tuple(MotionPattern)
        shots: list[MotionStoryShot] = []
        for index in range(count):
            length = base + (1 if index < remainder else 0)
            image = image_inputs[index % len(image_inputs)]
            seed = _stable_seed(story_basis, image.artifact_id, index)
            body = {
                "index": index,
                "source_image_artifact_id": image.artifact_id,
                "pattern": patterns[seed % len(patterns)].value,
                "timeline_start_ms": cursor,
                "duration_ms": length,
                "transition_ms": 0 if index == 0 else transition,
                "deterministic_seed": seed,
            }
            shot = MotionStoryShot.model_validate({**body, "digest": payload_digest(body)})
            shots.append(shot)
            cursor += length - transition
        final_end = shots[-1].timeline_start_ms + shots[-1].duration_ms
        if final_end != duration_ms:
            delta = duration_ms - final_end
            last = shots[-1]
            body = last.model_dump(mode="json", exclude={"digest"})
            body["duration_ms"] += delta
            shots[-1] = MotionStoryShot.model_validate({**body, "digest": payload_digest(body)})
        return tuple(shots)

    def plan(
        self,
        *,
        package_job_id: str,
        image_artifact_ids: tuple[str, ...],
    ) -> MotionStorySpec:
        _, narration = self._package(package_job_id)
        if not image_artifact_ids:
            raise MotionStoryError("motion-story planning requires at least one completed scene still")
        normalized_ids = tuple(sorted(set(image_artifact_ids)))
        images = tuple(self._image_input(artifact_id, narration.chapter_id) for artifact_id in normalized_ids)
        images = tuple(sorted(images, key=lambda item: item.artifact_id))
        caption = self._package_caption_artifact(package_job_id, narration.package_id)
        voice = self._completed_voice_artifact(narration.package_id, package_job_id)
        sounds, missing = self._sound_assets(narration)
        narration_seconds = narration.duration_ms / 1000.0
        if narration_seconds > self.policy.maximum_duration_seconds:
            raise MotionStoryError("verified narration exceeds motion-story maximum duration")
        target_seconds = max(self.policy.minimum_duration_seconds, narration_seconds)
        duration_ms = int(round(target_seconds * 1000.0))
        source_envelopes = tuple(sorted(set(
            item.source_envelope_id for item in images if item.source_envelope_id is not None
        )))
        source_events = tuple(sorted(set(
            event_id for item in images for event_id in item.source_event_ids
        )))
        input_digest = payload_digest({
            "images": [item.model_dump(mode="json") for item in images],
            "caption_artifact_id": caption["artifact_id"],
            "caption_digest": caption["digest"],
            "voice_artifact_id": voice["artifact_id"] if voice else None,
            "voice_digest": voice["digest"] if voice else None,
            "sound_assets": [item.model_dump(mode="json") for item in sounds],
            "missing_sound_asset_ids": list(missing),
        })
        story_id = _stable_id(
            "motion_story",
            narration.package_id,
            input_digest,
            FFMPEG_PROFILE_VERSION,
            self.policy.digest,
        )
        shots = self._shots(story_basis=story_id, image_inputs=images, duration_ms=duration_ms)
        has_music = any(item.kind == SoundAssetKind.MUSIC for item in sounds)
        audio_source_count = (1 if voice else 0) + len(sounds)
        effective_transition = shots[1].transition_ms if len(shots) > 1 else 0
        body = {
            "protocol": PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "phase": PHASE,
            "story_id": story_id,
            "chapter_id": narration.chapter_id,
            "narration_package_id": narration.package_id,
            "verification_id": narration.verification_id,
            "verification_digest": narration.verification_digest,
            "draft_id": narration.draft_id,
            "draft_digest": narration.draft_digest,
            "manifest_id": narration.manifest_id,
            "package_job_id": package_job_id,
            "caption_artifact_id": caption["artifact_id"],
            "caption_uri": caption["uri"],
            "caption_digest": caption["digest"],
            "voice_artifact_id": voice["artifact_id"] if voice else None,
            "voice_uri": voice["uri"] if voice else None,
            "voice_digest": voice["digest"] if voice else None,
            "narration_mode": NarrationMode.NARRATED.value if voice else NarrationMode.CAPTION_ONLY.value,
            "image_inputs": [item.model_dump(mode="json") for item in images],
            "sound_assets": [item.model_dump(mode="json") for item in sounds],
            "missing_sound_asset_ids": list(missing),
            "source_envelope_ids": list(source_envelopes),
            "source_event_ids": list(source_events),
            "shots": [item.model_dump(mode="json") for item in shots],
            "duration_ms": duration_ms,
            "output_width": self.policy.width,
            "output_height": self.policy.height,
            "fps": self.policy.fps,
            "transition_ms": effective_transition,
            "burn_captions": self.policy.burn_captions,
            "audio_present": audio_source_count > 0,
            "loudness_normalization": audio_source_count > 0,
            "music_ducking": bool(voice and has_music),
            "audio_fades": audio_source_count > 0,
            "audio_mixing": audio_source_count > 1,
            "final_encode": True,
            "deterministic_seed": _stable_seed(story_id, narration.deterministic_seed, self.policy.digest),
            "ffmpeg_profile_version": FFMPEG_PROFILE_VERSION,
            "policy_digest": self.policy.digest,
            "video_model_dependency": False,
            "video_diffusion_used": False,
            "unreal_dependency": False,
            "cloud_api_required": False,
            "paid_provider_required": False,
            "canonical_authority": False,
            "presentation_can_mutate_simulation": False,
        }
        result = MotionStorySpec.model_validate({**body, "digest": payload_digest(body)})
        validate_motion_story_spec(result)
        return result

    def enqueue(self, spec: MotionStorySpec, *, priority: int = 100) -> MediaJob:
        validate_motion_story_spec(spec)
        return self.media.enqueue_job(
            job_type=JOB_TYPE,
            payload={
                "protocol": PROTOCOL,
                "implementation_version": IMPLEMENTATION_VERSION,
                "phase": PHASE,
                "spec": spec.model_dump(mode="json"),
            },
            dependencies=(spec.package_job_id,) + tuple(item.job_id for item in spec.image_inputs),
            priority=priority,
            max_attempts=self.policy.max_attempts,
        )

    @staticmethod
    def _spec_from_job(job: MediaJob) -> MotionStorySpec:
        if job.job_type != JOB_TYPE:
            raise MotionStoryError("motion-story worker received a non-motion-story job")
        payload = job.payload
        if payload.get("protocol") != PROTOCOL or payload.get("implementation_version") != IMPLEMENTATION_VERSION or payload.get("phase") != PHASE:
            raise MotionStoryError("motion-story job payload protocol/version mismatch")
        spec = MotionStorySpec.model_validate(payload.get("spec"))
        validate_motion_story_spec(spec)
        expected_dependencies = tuple(sorted(set((spec.package_job_id,) + tuple(item.job_id for item in spec.image_inputs))))
        if job.dependency_job_ids != expected_dependencies:
            raise MotionStoryError("motion-story durable dependencies diverged from input provenance")
        return spec

    def _base_dir(self, spec: MotionStorySpec) -> Path:
        return Path("motion-stories") / spec.chapter_id / spec.story_id

    @staticmethod
    def _write_atomic(path: Path, payload: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f"{path.name}.tmp")
        temporary.write_bytes(payload)
        temporary.replace(path)

    def _video_filter(self, spec: MotionStorySpec) -> list[str]:
        filters: list[str] = []
        for index, shot in enumerate(spec.shots):
            frames = max(2, int(round(shot.duration_ms * spec.fps / 1000.0)))
            denom = max(1, frames - 1)
            if shot.pattern == MotionPattern.PUSH_IN:
                zoom = f"1+0.08*on/{denom}"
                x = "iw/2-(iw/zoom/2)"
                y = "ih/2-(ih/zoom/2)"
            elif shot.pattern == MotionPattern.PUSH_OUT:
                zoom = f"1.08-0.08*on/{denom}"
                x = "iw/2-(iw/zoom/2)"
                y = "ih/2-(ih/zoom/2)"
            elif shot.pattern == MotionPattern.DRIFT_LEFT:
                zoom = "1.05"
                x = f"(iw-iw/zoom)*(1-on/{denom})"
                y = "ih/2-(ih/zoom/2)"
            else:
                zoom = "1.05"
                x = f"(iw-iw/zoom)*(on/{denom})"
                y = "ih/2-(ih/zoom/2)"
            duration = shot.duration_ms / 1000.0
            filters.append(
                f"[{index}:v]scale={spec.output_width}:{spec.output_height}:force_original_aspect_ratio=increase,"
                f"crop={spec.output_width}:{spec.output_height},"
                f"zoompan=z='{zoom}':x='{x}':y='{y}':d=1:s={spec.output_width}x{spec.output_height}:fps={spec.fps},"
                f"trim=duration={duration:.3f},setpts=PTS-STARTPTS,settb=AVTB,setsar=1,format=yuv420p[v{index}]"
            )
        current = "v0"
        accumulated_ms = spec.shots[0].duration_ms
        for index in range(1, len(spec.shots)):
            transition_ms = spec.shots[index].transition_ms
            offset_ms = accumulated_ms - transition_ms
            filters.append(
                f"[{current}][v{index}]xfade=transition=fade:duration={transition_ms / 1000.0:.3f}:"
                f"offset={offset_ms / 1000.0:.3f}[vx{index}]"
            )
            current = f"vx{index}"
            accumulated_ms += spec.shots[index].duration_ms - transition_ms
        video_end = max(0.0, spec.duration_ms / 1000.0 - self.policy.video_fade_ms / 1000.0)
        chain = (
            f"[{current}]fade=t=in:st=0:d={self.policy.video_fade_ms / 1000.0:.3f},"
            f"fade=t=out:st={video_end:.3f}:d={self.policy.video_fade_ms / 1000.0:.3f}"
        )
        if spec.burn_captions:
            font_size = max(18, int(round(spec.output_height * 0.04)))
            margin_v = max(24, int(round(spec.output_height * 0.06)))
            chain += (
                f",subtitles=filename='captions.srt':force_style='FontSize={font_size},Alignment=2,"
                f"MarginV={margin_v},Outline=2,Shadow=0'"
            )
        chain += "[vout]"
        filters.append(chain)
        return filters

    def _audio_filter(self, spec: MotionStorySpec, first_audio_index: int) -> tuple[list[str], str | None]:
        if not spec.audio_present:
            return [], None
        filters: list[str] = []
        index = first_audio_index
        voice_main: str | None = None
        voice_side: str | None = None
        if spec.voice_artifact_id is not None:
            if spec.music_ducking:
                filters.append(f"[{index}:a]aresample=48000,asetpts=PTS-STARTPTS,asplit=2[voice_main][voice_side]")
                voice_main = "voice_main"
                voice_side = "voice_side"
            else:
                filters.append(f"[{index}:a]aresample=48000,asetpts=PTS-STARTPTS[voice]")
                voice_main = "voice"
            index += 1
        music_labels: list[str] = []
        sfx_labels: list[str] = []
        sfx_index = 0
        transition_points = [shot.timeline_start_ms for shot in spec.shots[1:]] or [0]
        for asset in spec.sound_assets:
            if asset.kind == SoundAssetKind.MUSIC:
                label = f"music{len(music_labels)}"
                filters.append(
                    f"[{index}:a]aresample=48000,volume={self.policy.music_volume:.4f},"
                    f"atrim=0:{spec.duration_ms / 1000.0:.3f},asetpts=PTS-STARTPTS[{label}]"
                )
                music_labels.append(label)
            else:
                label = f"sfx{sfx_index}"
                delay = transition_points[sfx_index % len(transition_points)]
                filters.append(
                    f"[{index}:a]aresample=48000,volume={self.policy.sfx_volume:.4f},"
                    f"adelay={delay}|{delay},asetpts=PTS-STARTPTS[{label}]"
                )
                sfx_labels.append(label)
                sfx_index += 1
            index += 1

        music_base: str | None = None
        if music_labels:
            if len(music_labels) == 1:
                music_base = music_labels[0]
            else:
                refs = "".join(f"[{label}]" for label in music_labels)
                filters.append(f"{refs}amix=inputs={len(music_labels)}:duration=longest:dropout_transition=0[musicmix]")
                music_base = "musicmix"

        base: str | None
        if voice_main is not None and music_base is not None:
            assert voice_side is not None
            filters.append(
                f"[{music_base}][{voice_side}]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=250[ducked]"
            )
            filters.append(f"[{voice_main}][ducked]amix=inputs=2:duration=longest:dropout_transition=0[baseaudio]")
            base = "baseaudio"
        elif voice_main is not None:
            base = voice_main
        else:
            base = music_base

        mix_labels: list[str] = []
        if base is not None:
            mix_labels.append(base)
        mix_labels.extend(sfx_labels)
        if not mix_labels:
            return filters, None
        if len(mix_labels) == 1:
            current = mix_labels[0]
        else:
            refs = "".join(f"[{label}]" for label in mix_labels)
            filters.append(f"{refs}amix=inputs={len(mix_labels)}:duration=longest:dropout_transition=0[allmix]")
            current = "allmix"

        duration = spec.duration_ms / 1000.0
        fade_out_start = max(0.0, duration - self.policy.audio_fade_out_ms / 1000.0)
        filters.append(
            f"[{current}]apad=pad_dur={duration:.3f},atrim=0:{duration:.3f},"
            f"loudnorm=I={self.policy.loudness_target_lufs:.1f}:TP=-1.5:LRA=11,"
            f"afade=t=in:st=0:d={self.policy.audio_fade_in_ms / 1000.0:.3f},"
            f"afade=t=out:st={fade_out_start:.3f}:d={self.policy.audio_fade_out_ms / 1000.0:.3f}[aout]"
        )
        return filters, "aout"

    def _runtime_inputs(self, spec: MotionStorySpec) -> tuple[list[str], list[Path]]:
        by_artifact = {item.artifact_id: item for item in spec.image_inputs}
        args: list[str] = []
        ordered_paths: list[Path] = []
        for shot in spec.shots:
            image = by_artifact[shot.source_image_artifact_id]
            path = self._verify_file(image.uri, image.digest)
            duration = shot.duration_ms / 1000.0
            args.extend(["-loop", "1", "-framerate", str(spec.fps), "-t", f"{duration:.3f}", "-i", str(path)])
            ordered_paths.append(path)
        if spec.voice_artifact_id is not None:
            assert spec.voice_uri is not None and spec.voice_digest is not None
            path = self._verify_file(spec.voice_uri, spec.voice_digest)
            args.extend(["-i", str(path)])
            ordered_paths.append(path)
        for asset in spec.sound_assets:
            path = self._verify_file(asset.relative_uri, asset.file_sha256)
            if asset.kind == SoundAssetKind.MUSIC:
                args.extend(["-stream_loop", "-1", "-i", str(path)])
            else:
                args.extend(["-i", str(path)])
            ordered_paths.append(path)
        return args, ordered_paths

    def _ffmpeg_command(self, spec: MotionStorySpec, output_path: Path) -> tuple[list[str], dict[str, Any]]:
        input_args, input_paths = self._runtime_inputs(spec)
        video_filters = self._video_filter(spec)
        audio_filters, audio_label = self._audio_filter(spec, len(spec.shots))
        filter_complex = ";".join(video_filters + audio_filters)
        command = [
            self.ffmpeg_path,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-fflags",
            "+bitexact",
            *input_args,
            "-filter_complex",
            filter_complex,
            "-map",
            "[vout]",
        ]
        if audio_label is not None:
            command.extend(["-map", f"[{audio_label}]", "-c:a", "aac", "-b:a", "160k", "-flags:a", "+bitexact"])
        command.extend([
            "-c:v",
            "libx264",
            "-preset",
            self.policy.preset,
            "-crf",
            str(self.policy.crf),
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
            "-movflags",
            "+faststart",
            "-t",
            f"{spec.duration_ms / 1000.0:.3f}",
            str(output_path),
        ])
        semantic = {
            "ffmpeg_profile_version": FFMPEG_PROFILE_VERSION,
            "input_artifact_ids": [shot.source_image_artifact_id for shot in spec.shots]
            + ([spec.voice_artifact_id] if spec.voice_artifact_id else [])
            + [item.asset_id for item in spec.sound_assets],
            "filter_complex": filter_complex,
            "video_encoder": "libx264",
            "audio_encoder": "aac" if audio_label is not None else None,
            "preset": self.policy.preset,
            "crf": self.policy.crf,
            "fps": spec.fps,
            "width": spec.output_width,
            "height": spec.output_height,
            "duration_ms": spec.duration_ms,
            "burn_captions": spec.burn_captions,
            "input_file_digests": [sha256(path.read_bytes()).hexdigest() for path in input_paths],
        }
        return command, semantic

    def _probe_runtime(self, spec: MotionStorySpec) -> dict[str, Any]:
        version = subprocess.run(
            [self.ffmpeg_path, "-version"], capture_output=True, text=True, timeout=15, check=False
        )
        if version.returncode != 0:
            raise MotionStoryError("ffmpeg executable is unavailable")
        version_line = (version.stdout or version.stderr).splitlines()[0].strip()
        filters = subprocess.run(
            [self.ffmpeg_path, "-hide_banner", "-filters"], capture_output=True, text=True, timeout=20, check=False
        )
        if filters.returncode != 0:
            raise MotionStoryError("ffmpeg filter capability probe failed")
        available_filters = filters.stdout + filters.stderr
        required = {"zoompan", "fade"}
        if len(spec.shots) > 1:
            required.add("xfade")
        if spec.burn_captions:
            required.add("subtitles")
        if spec.audio_present:
            required.update({"loudnorm", "afade", "atrim", "apad"})
        if spec.audio_mixing:
            required.add("amix")
        if spec.music_ducking:
            required.update({"sidechaincompress", "asplit"})
        missing = sorted(name for name in required if name not in available_filters)
        if missing:
            raise MotionStoryError(f"ffmpeg build lacks required filters: {','.join(missing)}")
        encoders = subprocess.run(
            [self.ffmpeg_path, "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=20, check=False
        )
        if encoders.returncode != 0 or "libx264" not in (encoders.stdout + encoders.stderr):
            raise MotionStoryError("ffmpeg build lacks required libx264 encoder")
        return {"version_line": version_line, "required_filters": sorted(required), "video_encoder": "libx264"}

    def _probe_output(self, path: Path, spec: MotionStorySpec) -> dict[str, Any]:
        probe = subprocess.run(
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
        if probe.returncode != 0:
            raise MotionStoryError("ffprobe could not validate assembled MP4")
        try:
            payload = json.loads(probe.stdout)
        except json.JSONDecodeError as exc:
            raise MotionStoryError("ffprobe returned invalid JSON") from exc
        video_streams = [item for item in payload.get("streams", []) if item.get("codec_type") == "video"]
        audio_streams = [item for item in payload.get("streams", []) if item.get("codec_type") == "audio"]
        if len(video_streams) != 1:
            raise MotionStoryError("motion-story output must contain exactly one video stream")
        video = video_streams[0]
        if int(video.get("width", 0)) != spec.output_width or int(video.get("height", 0)) != spec.output_height:
            raise MotionStoryError("motion-story output dimensions diverged from spec")
        if spec.audio_present and not audio_streams:
            raise MotionStoryError("motion-story expected an audio stream but FFmpeg output has none")
        if not spec.audio_present and audio_streams:
            raise MotionStoryError("caption-only silent story unexpectedly contains audio")
        format_name = str((payload.get("format") or {}).get("format_name", ""))
        if "mp4" not in format_name and "mov" not in format_name:
            raise MotionStoryError("FFmpeg output is not an MP4-compatible container")
        duration_seconds = float((payload.get("format") or {}).get("duration", 0.0))
        if abs(duration_seconds * 1000.0 - spec.duration_ms) > 1200:
            raise MotionStoryError("FFmpeg output duration diverged materially from spec")
        return {
            "format_name": format_name,
            "duration_ms": int(round(duration_seconds * 1000.0)),
            "width": spec.output_width,
            "height": spec.output_height,
            "video_stream_count": len(video_streams),
            "audio_stream_count": len(audio_streams),
        }

    def run_next(self, *, worker_id: str = "underreach-ffmpeg-motion-story-worker") -> MotionStoryResult | None:
        lease = self.media.claim_next(worker_id)
        if lease is None:
            return None
        job = lease.job
        if job.job_type != JOB_TYPE:
            self.media.fail_job(job.job_id, reason_code="wrong_motion_story_worker_job_type", retryable=False)
            return MotionStoryResult(
                story_id="unknown",
                job_id=job.job_id,
                status=JobStatus.FAILED,
                reason_code="wrong_motion_story_worker_job_type",
            )
        try:
            spec = self._spec_from_job(job)
        except Exception:
            self.media.fail_job(job.job_id, reason_code="invalid_motion_story_job_spec", retryable=False)
            raise

        base = self._base_dir(spec)
        work_dir = self.media_root / base / "work"
        final_rel = (base / "motion-story.mp4").as_posix()
        caption_rel = (base / "captions.srt").as_posix()
        manifest_rel = (base / "motion-story.json").as_posix()
        final_path = self.media_root / final_rel
        caption_path = self.media_root / caption_rel
        manifest_path = self.media_root / manifest_rel
        work_dir.mkdir(parents=True, exist_ok=True)
        temp_output = work_dir / "motion-story.render.mp4"
        error_path = work_dir / "ffmpeg-last-error.txt"
        if temp_output.exists():
            temp_output.unlink()

        source_caption = self._verify_file(spec.caption_uri, spec.caption_digest)
        caption_bytes = source_caption.read_bytes()
        self._write_atomic(work_dir / "captions.srt", caption_bytes)

        try:
            runtime = self._probe_runtime(spec)
            command, semantic_command = self._ffmpeg_command(spec, temp_output)
            process = subprocess.run(
                command,
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=self.policy.ffmpeg_timeout_seconds,
                check=False,
            )
            if process.returncode != 0:
                error_text = (process.stderr or process.stdout or "ffmpeg failed")[-12000:]
                self._write_atomic(error_path, error_text.encode("utf-8", errors="replace"))
                raise MotionStoryError("ffmpeg assembly failed")
            probe = self._probe_output(temp_output, spec)
        except Exception as exc:
            self.media.record_provider_execution(
                job_id=job.job_id,
                attempt_id=lease.attempt_id,
                provider_id=EDITOR_PROVIDER_ID,
                status="failed",
                estimated_cost_microusd=0,
                actual_cost_microusd=0,
                estimated_gpu_ms=0,
                actual_gpu_ms=0,
                metadata={
                    "reason_code": "ffmpeg_assembly_failed",
                    "error_type": type(exc).__name__,
                    "intermediates_retained": True,
                    "video_model_dependency": False,
                    "presentation_only": True,
                },
            )
            failed = self.media.fail_job(
                job.job_id,
                reason_code="ffmpeg_assembly_failed",
                retryable=True,
                resource_usage={"intermediates_retained": True},
            )
            return MotionStoryResult(
                story_id=spec.story_id,
                job_id=job.job_id,
                status=failed.status,
                reason_code="ffmpeg_assembly_failed",
            )

        final_path.parent.mkdir(parents=True, exist_ok=True)
        temp_output.replace(final_path)
        self._write_atomic(caption_path, caption_bytes)
        output_bytes = final_path.read_bytes()
        output_digest = sha256(output_bytes).hexdigest()
        caption_digest = sha256(caption_bytes).hexdigest()
        command_digest = payload_digest(semantic_command)
        manifest_body = {
            "protocol": PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "phase": PHASE,
            "story_id": spec.story_id,
            "job_id": job.job_id,
            "attempt_id": lease.attempt_id,
            "chapter_id": spec.chapter_id,
            "narration_package_id": spec.narration_package_id,
            "verification_id": spec.verification_id,
            "verification_digest": spec.verification_digest,
            "draft_id": spec.draft_id,
            "draft_digest": spec.draft_digest,
            "manifest_id": spec.manifest_id,
            "image_artifact_ids": [item.artifact_id for item in spec.image_inputs],
            "caption_source_artifact_id": spec.caption_artifact_id,
            "voice_artifact_id": spec.voice_artifact_id,
            "sound_assets": [item.model_dump(mode="json") for item in spec.sound_assets],
            "missing_sound_asset_ids": list(spec.missing_sound_asset_ids),
            "source_envelope_ids": list(spec.source_envelope_ids),
            "source_event_ids": list(spec.source_event_ids),
            "shots": [item.model_dump(mode="json") for item in spec.shots],
            "duration_ms": spec.duration_ms,
            "output_width": spec.output_width,
            "output_height": spec.output_height,
            "fps": spec.fps,
            "narration_mode": spec.narration_mode.value,
            "captions_burned": spec.burn_captions,
            "caption_sidecar_uri": caption_rel,
            "audio_present": spec.audio_present,
            "loudness_normalization": spec.loudness_normalization,
            "music_ducking": spec.music_ducking,
            "audio_fades": spec.audio_fades,
            "audio_mixing": spec.audio_mixing,
            "video_model_dependency": False,
            "video_diffusion_used": False,
            "ffmpeg_provider_id": EDITOR_PROVIDER_ID,
            "ffmpeg_profile_version": spec.ffmpeg_profile_version,
            "ffmpeg_version_line": runtime["version_line"],
            "ffmpeg_required_filters": runtime["required_filters"],
            "ffmpeg_command_plan_digest": command_digest,
            "ffprobe": probe,
            "output_uri": final_rel,
            "output_sha256": output_digest,
            "caption_sha256": caption_digest,
            "canonical_authority": False,
            "presentation_can_mutate_simulation": False,
            "unreal_dependency": False,
            "cloud_api_required": False,
            "paid_provider_required": False,
        }
        manifest_bytes = canonical_json(manifest_body).encode("utf-8")
        manifest_digest = sha256(manifest_bytes).hexdigest()
        self._write_atomic(manifest_path, manifest_bytes)

        output_artifact = self.media.record_artifact(
            job_id=job.job_id,
            artifact_kind="video/mp4",
            uri=final_rel,
            digest=output_digest,
            metadata={
                "story_id": spec.story_id,
                "chapter_id": spec.chapter_id,
                "source_event_ids": list(spec.source_event_ids),
                "source_envelope_ids": list(spec.source_envelope_ids),
                "narration_package_id": spec.narration_package_id,
                "presentation_only": True,
            },
        )
        caption_artifact = self.media.record_artifact(
            job_id=job.job_id,
            artifact_kind="text/srt",
            uri=caption_rel,
            digest=caption_digest,
            metadata={
                "story_id": spec.story_id,
                "source_caption_artifact_id": spec.caption_artifact_id,
                "presentation_only": True,
            },
        )
        manifest_artifact = self.media.record_artifact(
            job_id=job.job_id,
            artifact_kind="application/json",
            uri=manifest_rel,
            digest=manifest_digest,
            metadata={
                "story_id": spec.story_id,
                "video_artifact_id": output_artifact,
                "caption_artifact_id": caption_artifact,
                "presentation_only": True,
            },
        )
        self.media.record_provider_execution(
            job_id=job.job_id,
            attempt_id=lease.attempt_id,
            provider_id=EDITOR_PROVIDER_ID,
            status="completed",
            estimated_cost_microusd=0,
            actual_cost_microusd=0,
            estimated_gpu_ms=0,
            actual_gpu_ms=0,
            metadata={
                "story_id": spec.story_id,
                "video_artifact_id": output_artifact,
                "manifest_artifact_id": manifest_artifact,
                "ffmpeg_command_plan_digest": command_digest,
                "ffmpeg_version_line": runtime["version_line"],
                "video_model_dependency": False,
                "presentation_only": True,
            },
        )
        completed = self.media.complete_job(
            job.job_id,
            resource_usage={
                "output_bytes": len(output_bytes),
                "caption_bytes": len(caption_bytes),
                "ffmpeg_provider_id": EDITOR_PROVIDER_ID,
                "video_model_dependency": False,
            },
        )
        return MotionStoryResult(
            story_id=spec.story_id,
            job_id=job.job_id,
            status=completed.status,
            output_artifact_id=output_artifact,
            caption_artifact_id=caption_artifact,
            manifest_artifact_id=manifest_artifact,
            output_uri=final_rel,
            output_digest=output_digest,
            manifest_uri=manifest_rel,
            manifest_digest=manifest_digest,
            width=probe["width"],
            height=probe["height"],
            duration_ms=probe["duration_ms"],
            audio_stream_present=bool(probe["audio_stream_count"]),
        )

    def snapshot(self) -> dict[str, Any]:
        media_snapshot = self.media.snapshot()
        jobs = [item for item in media_snapshot["jobs"] if item["job_type"] == JOB_TYPE]
        job_ids = {item["job_id"] for item in jobs}
        artifacts = [item for item in media_snapshot["artifacts"] if item["job_id"] in job_ids]
        executions = [item for item in media_snapshot["provider_executions"] if item["job_id"] in job_ids]
        body = {
            "protocol": PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "phase": PHASE,
            "authoritative": False,
            "canonical_owner": "deterministic_simulation",
            "presentation_can_mutate_simulation": False,
            "unreal_dependency": False,
            "video_model_dependency": False,
            "video_diffusion_used": False,
            "required_cloud_api": False,
            "required_paid_provider": False,
            "guaranteed_motion_story_fallback": True,
            "ffmpeg_profile_version": FFMPEG_PROFILE_VERSION,
            "policy": self.policy.model_dump(mode="json"),
            "policy_digest": self.policy.digest,
            "jobs": jobs,
            "job_count": len(jobs),
            "job_digest": payload_digest(jobs),
            "artifacts": artifacts,
            "artifact_count": len(artifacts),
            "artifact_digest": payload_digest(artifacts),
            "provider_executions": executions,
            "provider_execution_count": len(executions),
            "provider_execution_digest": payload_digest(executions),
        }
        return {**body, "digest": payload_digest(body)}


__all__ = [
    "PROTOCOL",
    "IMPLEMENTATION_VERSION",
    "PHASE",
    "JOB_TYPE",
    "FFMPEG_PROFILE_VERSION",
    "EDITOR_PROVIDER_ID",
    "MotionPattern",
    "MotionStoryPolicy",
    "MotionStoryArtifactInput",
    "ResolvedSoundAsset",
    "MotionStoryShot",
    "MotionStorySpec",
    "MotionStoryResult",
    "MotionStoryError",
    "AutomatedFfmpegMotionStoryService",
    "validate_motion_story_spec",
]
