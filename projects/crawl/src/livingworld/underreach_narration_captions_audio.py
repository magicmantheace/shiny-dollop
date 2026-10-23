"""Verified narration, deterministic captions, and optional local voice for 30.5.8.

This media-only slice consumes persisted 30.5.5 REVIEW_READY narrative
verifications. The verified draft prose is the narration script verbatim.
Deterministic caption/package work is a durable job independent from TTS, so a
missing or failed voice provider leaves a valid caption-only package. Optional
voice synthesis runs through the accepted 30.5.2 provider router.

Nothing in this module opens or mutates canonical Crawl state, invokes Unreal,
uses speech recognition, mixes audio, or silently escalates to cloud/paid work.
FFmpeg assembly/mixing belongs to 30.5.9.
"""
from __future__ import annotations

from enum import StrEnum
from hashlib import sha256
from io import BytesIO
from pathlib import Path, PurePosixPath
import math
import struct
from typing import Any, Protocol
import wave

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .runtime_checkpoint import canonical_json, payload_digest
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
from .underreach_narrative_claim_verification import (
    NarrativeClaimVerificationService,
    NarrativeDraft,
    NarrativeVerification,
    VerificationStatus,
    validate_draft,
    validate_verification,
)


PROTOCOL = "underreach.narration-captions-audio.v1"
IMPLEMENTATION_VERSION = "30.5.8"
PHASE = "30.5"
PACKAGE_JOB_TYPE = "underreach.audio.package"
VOICE_JOB_TYPE = "underreach.audio.voice"
CAPTION_FORMAT_VERSION = "underreach.caption-timing.v1"
DEFAULT_SAMPLE_RATE = 22050


class NarrationAudioError(ValueError):
    """Raised when 30.5.8 presentation/audio invariants are violated."""


class SoundAssetKind(StrEnum):
    MUSIC = "music"
    SFX = "sfx"


class NarrationMode(StrEnum):
    CAPTION_ONLY = "caption_only"
    NARRATED = "narrated"


class AudioProductionPolicy(BaseModel):
    """Deterministic local-first policy; paid/cloud are disabled by default."""

    model_config = ConfigDict(frozen=True)

    milliseconds_per_word: int = Field(default=360, ge=120, le=2000)
    minimum_caption_ms: int = Field(default=900, ge=250, le=10000)
    caption_gap_ms: int = Field(default=120, ge=0, le=2000)
    sample_rate: int = Field(default=DEFAULT_SAMPLE_RATE, ge=8000, le=48000)
    max_script_chars: int = Field(default=12000, ge=128, le=100000)
    max_duration_seconds: float = Field(default=300.0, ge=1.0, le=3600.0)
    max_attempts: int = Field(default=2, ge=1, le=10)
    voice_enabled: bool = True
    local_required: bool = True
    paid_allowed: bool = False
    explicit_paid_authorization: bool = False
    min_quality_rank: int = Field(default=0, ge=0, le=100)

    @model_validator(mode="after")
    def validate_policy(self) -> "AudioProductionPolicy":
        if self.explicit_paid_authorization and not self.paid_allowed:
            raise ValueError("explicit paid authorization requires paid_allowed=true")
        return self

    @property
    def digest(self) -> str:
        return payload_digest(self.model_dump(mode="json"))


class CaptionCue(BaseModel):
    model_config = ConfigDict(frozen=True)

    index: int = Field(ge=1)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    text: str
    digest: str


class SoundAssetReference(BaseModel):
    """Optional local royalty-safe library metadata; mixing is deferred to 30.5.9."""

    model_config = ConfigDict(frozen=True)

    asset_id: str
    kind: SoundAssetKind
    relative_uri: str
    license_label: str
    royalty_safe: bool = True
    source_note: str | None = None
    digest: str

    @model_validator(mode="after")
    def validate_asset(self) -> "SoundAssetReference":
        if not self.asset_id.strip() or not self.license_label.strip():
            raise ValueError("sound asset requires ID and license label")
        path = PurePosixPath(self.relative_uri)
        if path.is_absolute() or ".." in path.parts or "://" in self.relative_uri:
            raise ValueError("30.5.8 sound assets must be local relative paths")
        if not self.royalty_safe:
            raise ValueError("30.5.8 accepts only explicitly royalty-safe/local sound assets")
        if self.digest != payload_digest(self.model_dump(mode="json", exclude={"digest"})):
            raise ValueError("sound asset digest mismatch")
        return self


class NarrationPackageSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    protocol: str = PROTOCOL
    implementation_version: str = IMPLEMENTATION_VERSION
    phase: str = PHASE
    package_id: str
    verification_id: str
    verification_digest: str
    draft_id: str
    draft_digest: str
    manifest_id: str
    chapter_id: str
    script: str
    sentences: tuple[str, ...]
    caption_cues: tuple[CaptionCue, ...]
    duration_ms: int = Field(gt=0)
    sound_assets: tuple[SoundAssetReference, ...] = ()
    voice_requested: bool = True
    voice_provider_request: ProviderRequest | None = None
    deterministic_seed: int = Field(ge=0)
    caption_format_version: str = CAPTION_FORMAT_VERSION
    policy_digest: str
    script_is_verified_draft_verbatim: bool = True
    captions_derive_from_verified_script: bool = True
    speech_recognition_used: bool = False
    audio_mixing_performed: bool = False
    canonical_authority: bool = False
    presentation_can_mutate_simulation: bool = False
    unreal_dependency: bool = False
    cloud_api_required: bool = False
    paid_provider_required: bool = False
    digest: str


class VoiceSynthesisRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    spec: NarrationPackageSpec
    job_id: str
    attempt_id: str


class VoiceSynthesisOutput(BaseModel):
    model_config = ConfigDict(frozen=True)

    wav_bytes: bytes
    sample_rate: int = Field(ge=8000, le=48000)
    channels: int = Field(default=1, ge=1, le=2)
    duration_ms: int = Field(gt=0)
    metadata: dict[str, Any] = {}
    actual_gpu_ms: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_output(self) -> "VoiceSynthesisOutput":
        if not self.wav_bytes.startswith(b"RIFF") or b"WAVE" not in self.wav_bytes[:16]:
            raise ValueError("voice provider did not return a WAV payload")
        return self


class AudioPackageResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    package_id: str
    package_job_id: str
    package_status: JobStatus
    caption_only_ready: bool
    mode: NarrationMode
    script_artifact_id: str | None = None
    srt_artifact_id: str | None = None
    vtt_artifact_id: str | None = None
    metadata_artifact_id: str | None = None
    voice_job_id: str | None = None
    voice_status: JobStatus | None = None
    voice_artifact_id: str | None = None
    voice_sidecar_artifact_id: str | None = None
    reason_code: str | None = None
    canonical_authority: bool = False
    presentation_can_mutate_simulation: bool = False


class HeadlessVoiceProvider(Protocol):
    @property
    def descriptor(self) -> ProviderDescriptor: ...

    def synthesize(self, request: VoiceSynthesisRequest) -> VoiceSynthesisOutput: ...


def _stable_id(prefix: str, *parts: object) -> str:
    text = ":".join(str(part) for part in parts)
    return f"{prefix}_{sha256(text.encode('utf-8')).hexdigest()[:24]}"


def _stable_seed(*parts: object) -> int:
    text = ":".join(str(part) for part in parts)
    return int(sha256(text.encode("utf-8")).hexdigest()[:15], 16)


def _body_digest(model: BaseModel) -> str:
    return payload_digest(model.model_dump(mode="json", exclude={"digest"}))


def make_sound_asset(
    *, asset_id: str, kind: SoundAssetKind, relative_uri: str, license_label: str, source_note: str | None = None
) -> SoundAssetReference:
    body = {
        "asset_id": asset_id,
        "kind": kind.value,
        "relative_uri": relative_uri,
        "license_label": license_label,
        "royalty_safe": True,
        "source_note": source_note,
    }
    return SoundAssetReference.model_validate({**body, "digest": payload_digest(body)})


def _caption_cue(index: int, start_ms: int, end_ms: int, text: str) -> CaptionCue:
    body = {"index": index, "start_ms": start_ms, "end_ms": end_ms, "text": text}
    return CaptionCue.model_validate({**body, "digest": payload_digest(body)})


def _caption_timeline(draft: NarrativeDraft, policy: AudioProductionPolicy) -> tuple[CaptionCue, ...]:
    cues: list[CaptionCue] = []
    cursor = 0
    for index, sentence in enumerate(draft.sentences, start=1):
        words = max(1, len(sentence.split()))
        duration = max(policy.minimum_caption_ms, words * policy.milliseconds_per_word)
        cue = _caption_cue(index, cursor, cursor + duration, sentence)
        cues.append(cue)
        cursor = cue.end_ms + policy.caption_gap_ms
    return tuple(cues)


def _format_srt_ms(value: int) -> str:
    hours, remainder = divmod(value, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def _format_vtt_ms(value: int) -> str:
    return _format_srt_ms(value).replace(",", ".")


def render_srt(cues: tuple[CaptionCue, ...]) -> str:
    blocks = []
    for cue in cues:
        blocks.append(f"{cue.index}\n{_format_srt_ms(cue.start_ms)} --> {_format_srt_ms(cue.end_ms)}\n{cue.text}")
    return "\n\n".join(blocks) + "\n"


def render_vtt(cues: tuple[CaptionCue, ...]) -> str:
    blocks = ["WEBVTT"]
    for cue in cues:
        blocks.append(f"{_format_vtt_ms(cue.start_ms)} --> {_format_vtt_ms(cue.end_ms)}\n{cue.text}")
    return "\n\n".join(blocks) + "\n"


def validate_package_spec(spec: NarrationPackageSpec) -> bool:
    if spec.protocol != PROTOCOL or spec.implementation_version != IMPLEMENTATION_VERSION or spec.phase != PHASE:
        raise NarrationAudioError("narration package protocol/version mismatch")
    if not spec.script.strip() or not spec.sentences or not spec.caption_cues:
        raise NarrationAudioError("narration package lacks verified script/captions")
    if tuple(cue.index for cue in spec.caption_cues) != tuple(range(1, len(spec.caption_cues) + 1)):
        raise NarrationAudioError("caption cue indexes are not contiguous")
    if len(spec.sentences) != len(spec.caption_cues):
        raise NarrationAudioError("caption cue count diverged from verified sentences")
    for sentence, cue in zip(spec.sentences, spec.caption_cues, strict=True):
        if cue.text != sentence or cue.end_ms <= cue.start_ms:
            raise NarrationAudioError("captions no longer derive directly from verified script")
        if cue.digest != _body_digest(cue):
            raise NarrationAudioError("caption cue digest mismatch")
    expected_duration = spec.caption_cues[-1].end_ms
    if spec.duration_ms != expected_duration:
        raise NarrationAudioError("narration duration diverged from deterministic caption timeline")
    if spec.voice_requested != (spec.voice_provider_request is not None):
        raise NarrationAudioError("voice request flag diverged from provider request")
    if spec.voice_provider_request is not None and spec.voice_provider_request.kind != ProviderKind.VOICE:
        raise NarrationAudioError("narration package requires voice provider kind")
    for asset in spec.sound_assets:
        SoundAssetReference.model_validate(asset.model_dump(mode="json"))
    if not spec.script_is_verified_draft_verbatim or not spec.captions_derive_from_verified_script:
        raise NarrationAudioError("verified-script/caption provenance flags changed")
    if spec.speech_recognition_used or spec.audio_mixing_performed:
        raise NarrationAudioError("30.5.8 may not use ASR or perform final audio mixing")
    if (
        spec.canonical_authority
        or spec.presentation_can_mutate_simulation
        or spec.unreal_dependency
        or spec.cloud_api_required
        or spec.paid_provider_required
    ):
        raise NarrationAudioError("narration package escaped presentation-only authority")
    if spec.digest != _body_digest(spec):
        raise NarrationAudioError("narration package digest mismatch")
    expected_id = _stable_id(
        "narration_package",
        spec.verification_id,
        spec.draft_digest,
        spec.caption_format_version,
        spec.policy_digest,
        payload_digest([item.model_dump(mode="json") for item in spec.sound_assets]),
    )
    if spec.package_id != expected_id:
        raise NarrationAudioError("narration package deterministic identity mismatch")
    return True


def deterministic_wav_bytes(*, duration_ms: int, sample_rate: int, seed: int) -> bytes:
    """Generate a deterministic mono PCM WAV for the zero-dependency acceptance backend."""
    frame_count = max(1, int(round(sample_rate * duration_ms / 1000.0)))
    frequency = 180.0 + float(seed % 120)
    amplitude = 2200
    output = BytesIO()
    with wave.open(output, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        chunk = bytearray()
        for index in range(frame_count):
            envelope = 0.25 if (index // max(1, sample_rate // 6)) % 2 else 0.12
            value = int(amplitude * envelope * math.sin(2.0 * math.pi * frequency * index / sample_rate))
            chunk.extend(struct.pack("<h", value))
        handle.writeframes(bytes(chunk))
    return output.getvalue()


class DeterministicLocalWavProvider:
    """Zero-dependency local acceptance/fallback voice backend.

    This proves the provider, file, queue, and degradation contracts without
    requiring Kokoro to be installed. A real Kokoro-equivalent executor plugs
    into the same HeadlessVoiceProvider interface.
    """

    def __init__(self, descriptor: ProviderDescriptor | None = None) -> None:
        self._descriptor = descriptor or ProviderDescriptor(
            provider_id="local_deterministic_wav",
            kind=ProviderKind.VOICE,
            local=True,
            paid=False,
            available=True,
            healthy=True,
            capability_flags=("headless_voice", "offline", "wav_output"),
            deterministic_seed=True,
            max_duration_seconds=300.0,
            estimated_vram_mb=0,
            estimated_runtime_seconds=0.05,
            estimated_cost_microusd=0,
            quality_rank=1,
            quality_profile="deterministic_acceptance_fallback",
        )
        if self._descriptor.kind != ProviderKind.VOICE or not self._descriptor.deterministic_seed:
            raise NarrationAudioError("local WAV provider requires deterministic voice capability")

    @property
    def descriptor(self) -> ProviderDescriptor:
        return self._descriptor

    def synthesize(self, request: VoiceSynthesisRequest) -> VoiceSynthesisOutput:
        spec = request.spec
        duration_seconds = spec.duration_ms / 1000.0
        if self.descriptor.max_duration_seconds is not None and duration_seconds > self.descriptor.max_duration_seconds:
            raise NarrationAudioError("voice request exceeds provider duration capability")
        sample_rate = 22050
        wav = deterministic_wav_bytes(duration_ms=spec.duration_ms, sample_rate=sample_rate, seed=spec.deterministic_seed)
        return VoiceSynthesisOutput(
            wav_bytes=wav,
            sample_rate=sample_rate,
            channels=1,
            duration_ms=spec.duration_ms,
            metadata={
                "renderer": "deterministic_wav_v1",
                "quality_profile": self.descriptor.quality_profile,
                "script_digest": sha256(spec.script.encode("utf-8")).hexdigest(),
                "presentation_only": True,
            },
            actual_gpu_ms=0,
        )


class NarrationCaptionsAudioService:
    """Build caption-first packages and optional dependent voice jobs."""

    def __init__(
        self,
        media: MediaPersistence,
        *,
        verifier: NarrativeClaimVerificationService,
        providers: tuple[HeadlessVoiceProvider, ...] | list[HeadlessVoiceProvider],
        output_root: str | Path,
        policy: AudioProductionPolicy | None = None,
        provider_policy: ProviderPolicy | None = None,
        router: MediaProviderRouter | None = None,
    ) -> None:
        self.media = media
        self.verifier = verifier
        self.policy = policy or AudioProductionPolicy()
        self.output_root = Path(output_root)
        self.router = router or MediaProviderRouter()
        self.provider_policy = provider_policy or ProviderPolicy(
            local_only=self.policy.local_required,
            cloud_allowed=not self.policy.local_required,
            allow_paid=self.policy.paid_allowed,
            require_explicit_paid_policy=True,
            daily_paid_budget_microusd=0,
        )
        self._executors: dict[str, HeadlessVoiceProvider] = {}
        for provider in providers:
            descriptor = provider.descriptor
            if descriptor.kind != ProviderKind.VOICE:
                raise NarrationAudioError("30.5.8 accepts only voice executors")
            existing = self._executors.get(descriptor.provider_id)
            if existing is not None and existing is not provider:
                raise NarrationAudioError("duplicate executable voice provider_id")
            self.router.register(descriptor)
            self._executors[descriptor.provider_id] = provider

    def initialize(self) -> None:
        self.output_root.mkdir(parents=True, exist_ok=True)

    def _verification(self, verification_id: str) -> NarrativeVerification:
        matches = [item for item in self.verifier.list_verifications() if item.verification_id == verification_id]
        if len(matches) != 1:
            raise NarrationAudioError("narration requires exactly one persisted NarrativeVerification")
        result = matches[0]
        validate_verification(result)
        if result.status != VerificationStatus.REVIEW_READY or not result.review_ready:
            raise NarrationAudioError("only REVIEW_READY verified narrative may become narration")
        return result

    def _voice_request(self, duration_ms: int) -> ProviderRequest:
        return ProviderRequest(
            kind=ProviderKind.VOICE,
            required_flags=("headless_voice", "wav_output"),
            local_required=self.policy.local_required,
            paid_allowed=self.policy.paid_allowed,
            explicit_paid_authorization=self.policy.explicit_paid_authorization,
            deterministic_seed_required=True,
            min_duration_seconds=duration_ms / 1000.0,
            min_quality_rank=self.policy.min_quality_rank,
        )

    def plan(
        self,
        verification_id: str,
        *,
        sound_assets: tuple[SoundAssetReference, ...] = (),
    ) -> NarrationPackageSpec:
        verification = self._verification(verification_id)
        draft = self.verifier.get_draft(verification.draft_id)
        if draft is None:
            raise NarrationAudioError("review-ready verification lost its narrative draft")
        validate_draft(draft)
        if len(draft.prose) > self.policy.max_script_chars:
            raise NarrationAudioError("verified script exceeds audio policy character limit")
        assets = tuple(sorted(sound_assets, key=lambda item: (item.kind.value, item.asset_id)))
        if len({item.asset_id for item in assets}) != len(assets):
            raise NarrationAudioError("sound asset IDs must be unique")
        for item in assets:
            SoundAssetReference.model_validate(item.model_dump(mode="json"))
        cues = _caption_timeline(draft, self.policy)
        duration_ms = cues[-1].end_ms
        if duration_ms / 1000.0 > self.policy.max_duration_seconds:
            raise NarrationAudioError("verified script exceeds configured narration duration")
        asset_digest = payload_digest([item.model_dump(mode="json") for item in assets])
        package_id = _stable_id(
            "narration_package",
            verification.verification_id,
            draft.digest,
            CAPTION_FORMAT_VERSION,
            self.policy.digest,
            asset_digest,
        )
        body = {
            "protocol": PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "phase": PHASE,
            "package_id": package_id,
            "verification_id": verification.verification_id,
            "verification_digest": verification.digest,
            "draft_id": draft.draft_id,
            "draft_digest": draft.digest,
            "manifest_id": verification.manifest_id,
            "chapter_id": verification.chapter_id,
            "script": draft.prose,
            "sentences": list(draft.sentences),
            "caption_cues": [item.model_dump(mode="json") for item in cues],
            "duration_ms": duration_ms,
            "sound_assets": [item.model_dump(mode="json") for item in assets],
            "voice_requested": self.policy.voice_enabled,
            "voice_provider_request": self._voice_request(duration_ms).model_dump(mode="json") if self.policy.voice_enabled else None,
            "deterministic_seed": _stable_seed(package_id, verification.digest, self.policy.digest),
            "caption_format_version": CAPTION_FORMAT_VERSION,
            "policy_digest": self.policy.digest,
            "script_is_verified_draft_verbatim": True,
            "captions_derive_from_verified_script": True,
            "speech_recognition_used": False,
            "audio_mixing_performed": False,
            "canonical_authority": False,
            "presentation_can_mutate_simulation": False,
            "unreal_dependency": False,
            "cloud_api_required": False,
            "paid_provider_required": False,
        }
        spec = NarrationPackageSpec.model_validate({**body, "digest": payload_digest(body)})
        validate_package_spec(spec)
        return spec

    def enqueue_package(self, spec: NarrationPackageSpec, *, priority: int = 100) -> MediaJob:
        validate_package_spec(spec)
        return self.media.enqueue_job(
            job_type=PACKAGE_JOB_TYPE,
            payload={"protocol": PROTOCOL, "implementation_version": IMPLEMENTATION_VERSION, "phase": PHASE, "spec": spec.model_dump(mode="json")},
            priority=priority,
            max_attempts=self.policy.max_attempts,
        )

    def enqueue_voice(self, spec: NarrationPackageSpec, package_job_id: str, *, priority: int = 90) -> MediaJob | None:
        validate_package_spec(spec)
        if not spec.voice_requested or spec.voice_provider_request is None:
            return None
        job = self.media.enqueue_job(
            job_type=VOICE_JOB_TYPE,
            payload={"protocol": PROTOCOL, "implementation_version": IMPLEMENTATION_VERSION, "phase": PHASE, "spec": spec.model_dump(mode="json")},
            dependencies=(package_job_id,),
            provider_request=spec.voice_provider_request,
            priority=priority,
            max_attempts=self.policy.max_attempts,
        )
        self.media.route_job(job.job_id, self.router, self.provider_policy)
        return self.media.get_job(job.job_id)

    def enqueue(self, spec: NarrationPackageSpec, *, package_priority: int = 100, voice_priority: int = 90) -> tuple[MediaJob, MediaJob | None]:
        package = self.enqueue_package(spec, priority=package_priority)
        voice = self.enqueue_voice(spec, package.job_id, priority=voice_priority)
        return package, voice

    @staticmethod
    def _spec_from_job(job: MediaJob) -> NarrationPackageSpec:
        if job.job_type not in {PACKAGE_JOB_TYPE, VOICE_JOB_TYPE}:
            raise NarrationAudioError("audio worker received unsupported media job")
        payload = job.payload
        if payload.get("protocol") != PROTOCOL or payload.get("implementation_version") != IMPLEMENTATION_VERSION or payload.get("phase") != PHASE:
            raise NarrationAudioError("audio job payload protocol/version mismatch")
        spec = NarrationPackageSpec.model_validate(payload.get("spec"))
        validate_package_spec(spec)
        if job.job_type == VOICE_JOB_TYPE and job.provider_request != spec.voice_provider_request:
            raise NarrationAudioError("durable voice provider request diverged from package spec")
        return spec

    def _base_dir(self, spec: NarrationPackageSpec) -> Path:
        return Path("audio") / spec.chapter_id / spec.package_id

    @staticmethod
    def _write_atomic(path: Path, payload: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f"{path.name}.tmp")
        temporary.write_bytes(payload)
        temporary.replace(path)

    def _write_package(self, lease_job: MediaJob, spec: NarrationPackageSpec) -> AudioPackageResult:
        base = self._base_dir(spec)
        script_rel = (base / "narration.txt").as_posix()
        srt_rel = (base / "captions.srt").as_posix()
        vtt_rel = (base / "captions.vtt").as_posix()
        metadata_rel = (base / "audio-package.json").as_posix()
        script_bytes = spec.script.encode("utf-8")
        srt_bytes = render_srt(spec.caption_cues).encode("utf-8")
        vtt_bytes = render_vtt(spec.caption_cues).encode("utf-8")
        metadata_body = {
            "protocol": PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "phase": PHASE,
            "package_id": spec.package_id,
            "verification_id": spec.verification_id,
            "verification_digest": spec.verification_digest,
            "draft_id": spec.draft_id,
            "draft_digest": spec.draft_digest,
            "manifest_id": spec.manifest_id,
            "chapter_id": spec.chapter_id,
            "script_sha256": sha256(script_bytes).hexdigest(),
            "caption_cues": [item.model_dump(mode="json") for item in spec.caption_cues],
            "duration_ms": spec.duration_ms,
            "sound_assets": [item.model_dump(mode="json") for item in spec.sound_assets],
            "caption_only_ready": True,
            "voice_requested": spec.voice_requested,
            "script_is_verified_draft_verbatim": True,
            "captions_derive_from_verified_script": True,
            "speech_recognition_used": False,
            "audio_mixing_performed": False,
            "canonical_authority": False,
            "presentation_can_mutate_simulation": False,
        }
        metadata_bytes = canonical_json(metadata_body).encode("utf-8")
        payloads = (
            (script_rel, "text/plain", script_bytes),
            (srt_rel, "text/srt", srt_bytes),
            (vtt_rel, "text/vtt", vtt_bytes),
            (metadata_rel, "application/json", metadata_bytes),
        )
        artifacts: dict[str, str] = {}
        for relative, kind, data in payloads:
            self._write_atomic(self.output_root / relative, data)
            digest = sha256(data).hexdigest()
            artifacts[kind] = self.media.record_artifact(
                job_id=lease_job.job_id,
                artifact_kind=kind,
                uri=relative,
                digest=digest,
                metadata={"package_id": spec.package_id, "verification_id": spec.verification_id, "presentation_only": True},
            )
        completed = self.media.complete_job(
            lease_job.job_id,
            resource_usage={"output_bytes": sum(len(item[2]) for item in payloads), "caption_only_ready": True},
        )
        return AudioPackageResult(
            package_id=spec.package_id,
            package_job_id=lease_job.job_id,
            package_status=completed.status,
            caption_only_ready=True,
            mode=NarrationMode.CAPTION_ONLY,
            script_artifact_id=artifacts["text/plain"],
            srt_artifact_id=artifacts["text/srt"],
            vtt_artifact_id=artifacts["text/vtt"],
            metadata_artifact_id=artifacts["application/json"],
        )

    def _run_voice(self, lease_job: MediaJob, attempt_id: str, spec: NarrationPackageSpec) -> AudioPackageResult:
        provider_id = lease_job.selected_provider_id
        provider = self._executors.get(provider_id or "")
        if provider is None:
            failed = self.media.fail_job(lease_job.job_id, reason_code="voice_executor_unavailable", retryable=True)
            return AudioPackageResult(
                package_id=spec.package_id,
                package_job_id=lease_job.dependency_job_ids[0],
                package_status=JobStatus.COMPLETED,
                caption_only_ready=True,
                mode=NarrationMode.CAPTION_ONLY,
                voice_job_id=lease_job.job_id,
                voice_status=failed.status,
                reason_code="voice_executor_unavailable",
            )
        request = VoiceSynthesisRequest(spec=spec, job_id=lease_job.job_id, attempt_id=attempt_id)
        estimated_gpu_ms = int(round(provider.descriptor.estimated_runtime_seconds * 1000)) if provider.descriptor.estimated_vram_mb > 0 else 0
        try:
            output = provider.synthesize(request)
        except Exception as exc:
            self.media.record_provider_execution(
                job_id=lease_job.job_id,
                attempt_id=attempt_id,
                provider_id=provider.descriptor.provider_id,
                status="failed",
                estimated_cost_microusd=provider.descriptor.estimated_cost_microusd,
                actual_cost_microusd=0,
                estimated_gpu_ms=estimated_gpu_ms,
                actual_gpu_ms=0,
                metadata={"reason_code": "voice_synthesis_failed", "error_type": type(exc).__name__, "caption_only_ready": True, "presentation_only": True},
            )
            failed = self.media.fail_job(lease_job.job_id, reason_code="voice_synthesis_failed", retryable=True)
            return AudioPackageResult(
                package_id=spec.package_id,
                package_job_id=lease_job.dependency_job_ids[0],
                package_status=JobStatus.COMPLETED,
                caption_only_ready=True,
                mode=NarrationMode.CAPTION_ONLY,
                voice_job_id=lease_job.job_id,
                voice_status=failed.status,
                reason_code="voice_synthesis_failed",
            )

        base = self._base_dir(spec)
        wav_rel = (base / "narration.wav").as_posix()
        sidecar_rel = (base / "narration.wav.json").as_posix()
        wav_digest = sha256(output.wav_bytes).hexdigest()
        sidecar_body = {
            "protocol": PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "phase": PHASE,
            "package_id": spec.package_id,
            "verification_id": spec.verification_id,
            "voice_job_id": lease_job.job_id,
            "attempt_id": attempt_id,
            "provider_id": provider.descriptor.provider_id,
            "provider_local": provider.descriptor.local,
            "provider_paid": provider.descriptor.paid,
            "sample_rate": output.sample_rate,
            "channels": output.channels,
            "duration_ms": output.duration_ms,
            "wav_sha256": wav_digest,
            "provider_metadata": output.metadata,
            "caption_only_fallback_remains_available": True,
            "canonical_authority": False,
            "presentation_can_mutate_simulation": False,
        }
        sidecar_bytes = canonical_json(sidecar_body).encode("utf-8")
        sidecar_digest = sha256(sidecar_bytes).hexdigest()
        self._write_atomic(self.output_root / wav_rel, output.wav_bytes)
        self._write_atomic(self.output_root / sidecar_rel, sidecar_bytes)
        wav_artifact = self.media.record_artifact(
            job_id=lease_job.job_id,
            artifact_kind="audio/wav",
            uri=wav_rel,
            digest=wav_digest,
            metadata={"package_id": spec.package_id, "verification_id": spec.verification_id, "provider_id": provider.descriptor.provider_id, "presentation_only": True},
        )
        sidecar_artifact = self.media.record_artifact(
            job_id=lease_job.job_id,
            artifact_kind="application/json",
            uri=sidecar_rel,
            digest=sidecar_digest,
            metadata={"package_id": spec.package_id, "voice_artifact_id": wav_artifact, "presentation_only": True},
        )
        self.media.record_provider_execution(
            job_id=lease_job.job_id,
            attempt_id=attempt_id,
            provider_id=provider.descriptor.provider_id,
            status="completed",
            estimated_cost_microusd=provider.descriptor.estimated_cost_microusd,
            actual_cost_microusd=provider.descriptor.estimated_cost_microusd if provider.descriptor.paid else 0,
            estimated_gpu_ms=estimated_gpu_ms,
            actual_gpu_ms=output.actual_gpu_ms,
            metadata={"package_id": spec.package_id, "voice_artifact_id": wav_artifact, "presentation_only": True},
        )
        completed = self.media.complete_job(
            lease_job.job_id,
            resource_usage={"actual_gpu_ms": output.actual_gpu_ms, "output_bytes": len(output.wav_bytes), "provider_id": provider.descriptor.provider_id},
        )
        return AudioPackageResult(
            package_id=spec.package_id,
            package_job_id=lease_job.dependency_job_ids[0],
            package_status=JobStatus.COMPLETED,
            caption_only_ready=True,
            mode=NarrationMode.NARRATED,
            voice_job_id=lease_job.job_id,
            voice_status=completed.status,
            voice_artifact_id=wav_artifact,
            voice_sidecar_artifact_id=sidecar_artifact,
        )

    def run_next(self, *, worker_id: str = "underreach-audio-worker") -> AudioPackageResult | None:
        lease = self.media.claim_next(worker_id)
        if lease is None:
            return None
        job = lease.job
        if job.job_type not in {PACKAGE_JOB_TYPE, VOICE_JOB_TYPE}:
            self.media.fail_job(job.job_id, reason_code="wrong_audio_worker_job_type", retryable=False)
            return AudioPackageResult(
                package_id="unknown",
                package_job_id=job.job_id,
                package_status=JobStatus.FAILED,
                caption_only_ready=False,
                mode=NarrationMode.CAPTION_ONLY,
                reason_code="wrong_audio_worker_job_type",
            )
        try:
            spec = self._spec_from_job(job)
        except Exception:
            self.media.fail_job(job.job_id, reason_code="invalid_audio_job_spec", retryable=False)
            raise
        if job.job_type == PACKAGE_JOB_TYPE:
            return self._write_package(job, spec)
        return self._run_voice(job, lease.attempt_id, spec)

    def snapshot(self) -> dict[str, Any]:
        media_snapshot = self.media.snapshot()
        jobs = [item for item in media_snapshot["jobs"] if item["job_type"] in {PACKAGE_JOB_TYPE, VOICE_JOB_TYPE}]
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
            "speech_recognition_used": False,
            "audio_mixing_performed": False,
            "caption_only_fallback_guaranteed": True,
            "required_cloud_api": False,
            "required_paid_provider": False,
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
    "PACKAGE_JOB_TYPE",
    "VOICE_JOB_TYPE",
    "CAPTION_FORMAT_VERSION",
    "SoundAssetKind",
    "NarrationMode",
    "AudioProductionPolicy",
    "CaptionCue",
    "SoundAssetReference",
    "NarrationPackageSpec",
    "VoiceSynthesisRequest",
    "VoiceSynthesisOutput",
    "AudioPackageResult",
    "HeadlessVoiceProvider",
    "DeterministicLocalWavProvider",
    "NarrationAudioError",
    "NarrationCaptionsAudioService",
    "make_sound_asset",
    "render_srt",
    "render_vtt",
    "validate_package_spec",
    "deterministic_wav_bytes",
]
