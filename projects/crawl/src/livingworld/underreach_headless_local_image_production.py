"""Headless local still-image production for Underreach Phase 30.5.7.

30.5.7 consumes accepted media-owned Delver profiles, Chronicle chapters, and
presentation_identity.v1 records. It creates durable image jobs through the
accepted 30.5.2 provider router, invokes only explicitly registered image
executors, writes file-backed artifacts plus sidecar provenance, and records
provider execution metadata.

Generated pixels are presentation state only. This module never opens the
canonical Crawl database, never mutates canonical state/Ledger truth, never
invokes Unreal, and never silently escalates to a paid or cloud provider.
"""
from __future__ import annotations

from enum import StrEnum
from hashlib import sha256
from pathlib import Path
import struct
from typing import Any, Protocol
import zlib

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .runtime_checkpoint import canonical_json, payload_digest
from .underreach_delver_chronicle_profile import (
    ChronicleChapter,
    DelverProfile,
    ProfileEquipment,
    validate_chapter,
    validate_profile,
)
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
from .underreach_presentation_identity import (
    EquipmentReferenceRevision,
    PresentationIdentity,
    PresentationIdentityBinding,
    PresentationIdentityService,
    PresentationReferenceSlot,
    ReferenceKind,
    validate_binding,
    validate_equipment_revision,
    validate_identity,
    validate_reference_slot,
)


PROTOCOL = "underreach.headless-image-production.v1"
IMPLEMENTATION_VERSION = "30.5.7"
PHASE = "30.5"
JOB_TYPE = "underreach.image.generate"
PROMPT_TEMPLATE_VERSION = "underreach.image-prompt.v1"
DEFAULT_MAX_VRAM_MB = 12 * 1024
DEFAULT_MAX_PIXELS = 1024 * 1536


class ImageProductionError(ValueError):
    """Raised when a 30.5.7 image-production invariant is violated."""


class ImagePurpose(StrEnum):
    IDENTITY_REFERENCE = "identity_reference"
    EQUIPMENT_REFERENCE = "equipment_reference"
    SCENE_STILL = "scene_still"


class ImageProductionPolicy(BaseModel):
    """Bounded local-first policy for still-image jobs."""

    model_config = ConfigDict(frozen=True)

    default_width: int = Field(default=512, ge=64, le=2048)
    default_height: int = Field(default=512, ge=64, le=2048)
    scene_width: int = Field(default=768, ge=64, le=2048)
    scene_height: int = Field(default=1024, ge=64, le=2048)
    max_pixels: int = Field(default=DEFAULT_MAX_PIXELS, ge=4096, le=2048 * 2048)
    max_vram_mb: int = Field(default=DEFAULT_MAX_VRAM_MB, ge=0, le=65536)
    max_attempts: int = Field(default=2, ge=1, le=10)
    local_required: bool = True
    paid_allowed: bool = False
    explicit_paid_authorization: bool = False
    min_quality_rank: int = Field(default=0, ge=0, le=100)

    @model_validator(mode="after")
    def validate_policy(self) -> "ImageProductionPolicy":
        if self.default_width * self.default_height > self.max_pixels:
            raise ValueError("default image resolution exceeds max_pixels")
        if self.scene_width * self.scene_height > self.max_pixels:
            raise ValueError("scene image resolution exceeds max_pixels")
        if self.explicit_paid_authorization and not self.paid_allowed:
            raise ValueError("explicit paid authorization requires paid_allowed=true")
        return self

    @property
    def digest(self) -> str:
        return payload_digest(self.model_dump(mode="json"))


class ImageProductionSpec(BaseModel):
    """Immutable semantic specification persisted inside one media job."""

    model_config = ConfigDict(frozen=True)

    protocol: str = PROTOCOL
    implementation_version: str = IMPLEMENTATION_VERSION
    phase: str = PHASE
    spec_id: str
    purpose: ImagePurpose
    crawl_id: str
    profile_id: str
    delver_id: str
    identity_id: str
    identity_version: int = Field(ge=1)
    equipment_revision_id: str | None = None
    source_envelope_id: str
    source_event_ids: tuple[str, ...]
    reference_id: str | None = None
    reference_kind: ReferenceKind | None = None
    chapter_id: str | None = None
    reference_artifact_ids: tuple[str, ...] = ()
    deterministic_seed: int = Field(ge=0)
    width: int = Field(ge=64, le=2048)
    height: int = Field(ge=64, le=2048)
    prompt_template_version: str = PROMPT_TEMPLATE_VERSION
    prompt: str
    negative_prompt: str
    provider_request: ProviderRequest
    policy_digest: str
    canonical_authority: bool = False
    presentation_can_mutate_simulation: bool = False
    unreal_dependency: bool = False
    cloud_api_required: bool = False
    paid_provider_required: bool = False
    digest: str


class ImageRenderRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    spec: ImageProductionSpec
    job_id: str
    attempt_id: str


class ImageRenderOutput(BaseModel):
    model_config = ConfigDict(frozen=True)

    image_bytes: bytes
    extension: str = ".png"
    metadata: dict[str, Any] = {}
    actual_gpu_ms: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_output(self) -> "ImageRenderOutput":
        if not self.image_bytes:
            raise ValueError("image provider returned empty bytes")
        if self.extension.lower() != ".png":
            raise ValueError("30.5.7 acceptance contract currently requires PNG output")
        return self


class ImageProductionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    job_id: str
    status: JobStatus
    provider_id: str | None = None
    artifact_id: str | None = None
    sidecar_artifact_id: str | None = None
    output_uri: str | None = None
    output_digest: str | None = None
    sidecar_uri: str | None = None
    sidecar_digest: str | None = None
    reason_code: str | None = None
    canonical_authority: bool = False
    presentation_can_mutate_simulation: bool = False


class HeadlessImageProvider(Protocol):
    """Executable image backend paired with 30.5.2 provider metadata."""

    @property
    def descriptor(self) -> ProviderDescriptor: ...

    def render(self, request: ImageRenderRequest) -> ImageRenderOutput: ...


def _stable_id(prefix: str, *parts: object) -> str:
    text = ":".join(str(part) for part in parts)
    return f"{prefix}_{sha256(text.encode('utf-8')).hexdigest()[:24]}"


def _stable_seed(*parts: object) -> int:
    text = ":".join(str(part) for part in parts)
    return int(sha256(text.encode("utf-8")).hexdigest()[:15], 16)


def _body_digest(model: BaseModel) -> str:
    return payload_digest(model.model_dump(mode="json", exclude={"digest"}))


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    checksum = zlib.crc32(kind)
    checksum = zlib.crc32(payload, checksum)
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", checksum & 0xFFFFFFFF)


def deterministic_png_bytes(width: int, height: int, seed_material: str) -> bytes:
    """Create a valid deterministic RGB PNG using only the Python standard library.

    This is a zero-dependency acceptance/fallback renderer, not a quality art
    backend. Production-quality local engines such as ComfyUI plug into the same
    HeadlessImageProvider contract.
    """
    if width < 1 or height < 1 or width > 2048 or height > 2048:
        raise ImageProductionError("deterministic PNG dimensions are out of bounds")
    basis = sha256(seed_material.encode("utf-8")).digest()
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        yv = (y * 255) // max(1, height - 1)
        for x in range(width):
            xv = (x * 255) // max(1, width - 1)
            rows.extend(
                (
                    (basis[0] + xv + yv // 3) & 0xFF,
                    (basis[1] + yv + xv // 5) & 0xFF,
                    (basis[2] + (xv ^ yv)) & 0xFF,
                )
            )
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return signature + _png_chunk(b"IHDR", ihdr) + _png_chunk(b"IDAT", zlib.compress(bytes(rows), 9)) + _png_chunk(b"IEND", b"")


class DeterministicLocalPngProvider:
    """Executable zero-dependency provider used as the guaranteed local acceptance path."""

    def __init__(self, descriptor: ProviderDescriptor | None = None) -> None:
        self._descriptor = descriptor or ProviderDescriptor(
            provider_id="local_deterministic_png",
            kind=ProviderKind.IMAGE,
            local=True,
            paid=False,
            available=True,
            healthy=True,
            capability_flags=("headless_image", "offline", "png_output"),
            deterministic_seed=True,
            reference_conditioning=False,
            max_width=2048,
            max_height=2048,
            estimated_vram_mb=0,
            estimated_runtime_seconds=0.05,
            estimated_cost_microusd=0,
            quality_rank=1,
            quality_profile="deterministic_acceptance_fallback",
        )
        if self._descriptor.kind != ProviderKind.IMAGE:
            raise ImageProductionError("image executor descriptor must have kind=image")
        if not self._descriptor.deterministic_seed:
            raise ImageProductionError("deterministic local PNG provider requires seed capability")

    @property
    def descriptor(self) -> ProviderDescriptor:
        return self._descriptor

    def render(self, request: ImageRenderRequest) -> ImageRenderOutput:
        spec = request.spec
        if self.descriptor.max_width is not None and spec.width > self.descriptor.max_width:
            raise ImageProductionError("requested image width exceeds provider capability")
        if self.descriptor.max_height is not None and spec.height > self.descriptor.max_height:
            raise ImageProductionError("requested image height exceeds provider capability")
        material = payload_digest(
            {
                "provider": self.descriptor.provider_id,
                "spec_digest": spec.digest,
                "seed": spec.deterministic_seed,
                "references": list(spec.reference_artifact_ids),
            }
        )
        image = deterministic_png_bytes(spec.width, spec.height, material)
        return ImageRenderOutput(
            image_bytes=image,
            extension=".png",
            metadata={
                "renderer": "deterministic_png_v1",
                "semantic_render_digest": material,
                "quality_profile": self.descriptor.quality_profile,
                "presentation_only": True,
            },
            actual_gpu_ms=0,
        )


def validate_image_spec(spec: ImageProductionSpec) -> bool:
    if spec.protocol != PROTOCOL or spec.implementation_version != IMPLEMENTATION_VERSION or spec.phase != PHASE:
        raise ImageProductionError("image production protocol/version mismatch")
    if not spec.source_event_ids:
        raise ImageProductionError("image production spec lacks canonical event provenance")
    if tuple(sorted(set(spec.source_event_ids))) != spec.source_event_ids:
        raise ImageProductionError("image source event provenance is not normalized")
    if tuple(sorted(set(spec.reference_artifact_ids))) != spec.reference_artifact_ids:
        raise ImageProductionError("reference artifact provenance is not normalized")
    if spec.purpose == ImagePurpose.IDENTITY_REFERENCE:
        if spec.reference_id is None or spec.reference_kind in {None, ReferenceKind.CURRENT_EQUIPMENT}:
            raise ImageProductionError("identity reference spec lacks a static reference slot")
        if spec.equipment_revision_id is not None or spec.chapter_id is not None:
            raise ImageProductionError("identity reference must not be coupled to equipment/chapter state")
    if spec.purpose == ImagePurpose.EQUIPMENT_REFERENCE:
        if spec.reference_id is None or spec.reference_kind != ReferenceKind.CURRENT_EQUIPMENT:
            raise ImageProductionError("equipment reference spec lacks current-equipment slot")
        if spec.equipment_revision_id is None or spec.chapter_id is not None:
            raise ImageProductionError("equipment reference requires equipment revision and no chapter")
    if spec.purpose == ImagePurpose.SCENE_STILL:
        if spec.chapter_id is None or spec.equipment_revision_id is None:
            raise ImageProductionError("scene still requires Chronicle and equipment provenance")
        if spec.reference_id is not None or spec.reference_kind is not None:
            raise ImageProductionError("scene still cannot masquerade as an identity reference slot")
    if spec.provider_request.kind != ProviderKind.IMAGE:
        raise ImageProductionError("image spec requires image provider kind")
    if not spec.provider_request.deterministic_seed_required:
        raise ImageProductionError("30.5.7 image jobs require deterministic seed support")
    if (
        spec.canonical_authority
        or spec.presentation_can_mutate_simulation
        or spec.unreal_dependency
        or spec.cloud_api_required
        or spec.paid_provider_required
    ):
        raise ImageProductionError("image spec escaped presentation-only authority")
    if spec.digest != _body_digest(spec):
        raise ImageProductionError("image production spec digest mismatch")
    expected_id = _stable_id(
        "image_spec",
        spec.purpose.value,
        spec.identity_id,
        spec.equipment_revision_id or "identity-static",
        spec.reference_id or spec.chapter_id or "none",
        spec.deterministic_seed,
        spec.width,
        spec.height,
        spec.prompt_template_version,
        spec.policy_digest,
    )
    if spec.spec_id != expected_id:
        raise ImageProductionError("image production deterministic identity mismatch")
    return True


class HeadlessLocalImageProductionService:
    """Plan, route, and execute durable still-image jobs without simulation authority."""

    def __init__(
        self,
        media: MediaPersistence,
        *,
        identities: PresentationIdentityService,
        providers: tuple[HeadlessImageProvider, ...] | list[HeadlessImageProvider],
        output_root: str | Path,
        policy: ImageProductionPolicy | None = None,
        provider_policy: ProviderPolicy | None = None,
        router: MediaProviderRouter | None = None,
    ) -> None:
        self.media = media
        self.identities = identities
        self.policy = policy or ImageProductionPolicy()
        self.output_root = Path(output_root)
        self.router = router or MediaProviderRouter()
        self.provider_policy = provider_policy or ProviderPolicy(
            local_only=self.policy.local_required,
            cloud_allowed=not self.policy.local_required,
            allow_paid=self.policy.paid_allowed,
            require_explicit_paid_policy=True,
            daily_paid_budget_microusd=0,
            max_vram_mb=self.policy.max_vram_mb,
        )
        self._executors: dict[str, HeadlessImageProvider] = {}
        for provider in providers:
            descriptor = provider.descriptor
            if descriptor.kind != ProviderKind.IMAGE:
                raise ImageProductionError("30.5.7 accepts only image providers")
            existing = self._executors.get(descriptor.provider_id)
            if existing is not None and existing is not provider:
                raise ImageProductionError("duplicate executable provider_id")
            self.router.register(descriptor)
            self._executors[descriptor.provider_id] = provider

    def initialize(self) -> None:
        self.output_root.mkdir(parents=True, exist_ok=True)

    def _state(
        self, profile: DelverProfile
    ) -> tuple[PresentationIdentityBinding, PresentationIdentity, EquipmentReferenceRevision]:
        validate_profile(profile)
        persisted = self.identities.chronicle.get_profile(profile.crawl_id, profile.delver_id)
        if persisted is None or persisted != profile:
            raise ImageProductionError("image production requires exact persisted DelverProfile")
        binding = self.identities.get_binding(profile.profile_id)
        if binding is None:
            raise ImageProductionError("image production requires an accepted presentation identity binding")
        validate_binding(binding)
        identity = self.identities.get_identity(binding.active_identity_id)
        revision = self.identities.get_equipment_revision(binding.current_equipment_revision_id)
        if identity is None or revision is None:
            raise ImageProductionError("presentation identity binding references missing identity/equipment state")
        validate_identity(identity)
        validate_equipment_revision(revision)
        if identity.profile_id != profile.profile_id or revision.profile_id != profile.profile_id:
            raise ImageProductionError("presentation identity state diverged from Delver profile")
        if revision.identity_id != identity.identity_id:
            raise ImageProductionError("equipment revision does not belong to active identity")
        return binding, identity, revision

    @staticmethod
    def _slot(
        identity: PresentationIdentity,
        revision: EquipmentReferenceRevision,
        kind: ReferenceKind,
    ) -> PresentationReferenceSlot:
        if kind == ReferenceKind.CURRENT_EQUIPMENT:
            slot = revision.reference_slot
        else:
            matches = [item for item in identity.reference_slots if item.kind == kind]
            if len(matches) != 1:
                raise ImageProductionError("presentation identity reference slot is missing or duplicated")
            slot = matches[0]
        validate_reference_slot(slot)
        return slot

    def _provider_request(self, *, width: int, height: int) -> ProviderRequest:
        return ProviderRequest(
            kind=ProviderKind.IMAGE,
            required_flags=("headless_image", "png_output"),
            local_required=self.policy.local_required,
            paid_allowed=self.policy.paid_allowed,
            explicit_paid_authorization=self.policy.explicit_paid_authorization,
            deterministic_seed_required=True,
            reference_conditioning_required=False,
            min_width=width,
            min_height=height,
            max_vram_mb=self.policy.max_vram_mb,
            min_quality_rank=self.policy.min_quality_rank,
        )

    def _static_reference_prompt(
        self,
        *,
        profile: DelverProfile,
        identity: PresentationIdentity,
        kind: ReferenceKind,
    ) -> str:
        return (
            "Underreach presentation-only character reference. "
            f"Stable Delver ID {profile.delver_id}. "
            f"Visual profile {identity.visual_profile}. "
            f"Reference view {kind.value}. "
            "Maintain one consistent media identity. Generated facial and body details are noncanonical presentation state. "
            "Do not imply equipment, injury, status, or gameplay outcomes. No text, watermark, or interface."
        )

    def _equipment_prompt(
        self,
        *,
        profile: DelverProfile,
        identity: PresentationIdentity,
        revision: EquipmentReferenceRevision,
    ) -> str:
        equipment_names = ", ".join(item.name for item in revision.equipment) or "no notable visible equipment"
        return (
            "Underreach presentation-only current equipment reference. "
            f"Stable Delver ID {profile.delver_id}. "
            f"Visual profile {identity.visual_profile}. "
            f"Canonical-backed visible equipment context: {equipment_names}. "
            "Keep the established media identity consistent. Generated styling is noncanonical. No text or watermark."
        )

    def _scene_prompt(
        self,
        *,
        profile: DelverProfile,
        identity: PresentationIdentity,
        revision: EquipmentReferenceRevision,
        chapter: ChronicleChapter,
    ) -> str:
        equipment_names = ", ".join(item.name for item in revision.equipment) or "no notable visible equipment"
        triggers = ", ".join(chapter.trigger_codes)
        return (
            "Underreach presentation-only Chronicle scene still. "
            f"Stable Delver ID {profile.delver_id}. "
            f"Visual profile {identity.visual_profile}. "
            f"Structured chapter code {chapter.title_code}. "
            f"Canonical-backed trigger codes: {triggers}. "
            f"Canonical-backed equipment context: {equipment_names}. "
            "Depict atmosphere and action without adding a new gameplay fact. "
            "Generated appearance and staging remain noncanonical presentation state. No text or watermark."
        )

    def _build_spec(
        self,
        *,
        purpose: ImagePurpose,
        profile: DelverProfile,
        identity: PresentationIdentity,
        equipment_revision_id: str | None,
        equipment_digest: str,
        source_envelope_id: str,
        source_event_ids: tuple[str, ...],
        reference_id: str | None,
        reference_kind: ReferenceKind | None,
        chapter_id: str | None,
        reference_artifact_ids: tuple[str, ...],
        width: int,
        height: int,
        prompt: str,
    ) -> ImageProductionSpec:
        if width * height > self.policy.max_pixels:
            raise ImageProductionError("requested image exceeds bounded max_pixels policy")
        seed = _stable_seed(
            identity.deterministic_seed,
            equipment_digest,
            purpose.value,
            reference_id or chapter_id or "none",
            width,
            height,
            PROMPT_TEMPLATE_VERSION,
        )
        spec_id = _stable_id(
            "image_spec",
            purpose.value,
            identity.identity_id,
            equipment_revision_id or "identity-static",
            reference_id or chapter_id or "none",
            seed,
            width,
            height,
            PROMPT_TEMPLATE_VERSION,
            self.policy.digest,
        )
        body = {
            "protocol": PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "phase": PHASE,
            "spec_id": spec_id,
            "purpose": purpose.value,
            "crawl_id": profile.crawl_id,
            "profile_id": profile.profile_id,
            "delver_id": profile.delver_id,
            "identity_id": identity.identity_id,
            "identity_version": identity.identity_version,
            "equipment_revision_id": equipment_revision_id,
            "source_envelope_id": source_envelope_id,
            "source_event_ids": list(sorted(set(source_event_ids))),
            "reference_id": reference_id,
            "reference_kind": reference_kind.value if reference_kind is not None else None,
            "chapter_id": chapter_id,
            "reference_artifact_ids": list(sorted(set(reference_artifact_ids))),
            "deterministic_seed": seed,
            "width": width,
            "height": height,
            "prompt_template_version": PROMPT_TEMPLATE_VERSION,
            "prompt": prompt,
            "negative_prompt": "text, watermark, logo, UI, unsupported gameplay claims",
            "provider_request": self._provider_request(width=width, height=height).model_dump(mode="json"),
            "policy_digest": self.policy.digest,
            "canonical_authority": False,
            "presentation_can_mutate_simulation": False,
            "unreal_dependency": False,
            "cloud_api_required": False,
            "paid_provider_required": False,
        }
        spec = ImageProductionSpec.model_validate({**body, "digest": payload_digest(body)})
        validate_image_spec(spec)
        return spec

    def plan_reference(
        self,
        profile: DelverProfile,
        kind: ReferenceKind,
        *,
        width: int | None = None,
        height: int | None = None,
    ) -> ImageProductionSpec:
        _, identity, revision = self._state(profile)
        slot = self._slot(identity, revision, kind)
        if kind == ReferenceKind.CURRENT_EQUIPMENT:
            return self._build_spec(
                purpose=ImagePurpose.EQUIPMENT_REFERENCE,
                profile=profile,
                identity=identity,
                equipment_revision_id=revision.revision_id,
                equipment_digest=revision.equipment_digest,
                source_envelope_id=revision.source_envelope_id,
                source_event_ids=tuple(revision.source_event_ids),
                reference_id=slot.reference_id,
                reference_kind=kind,
                chapter_id=None,
                reference_artifact_ids=(),
                width=width or self.policy.default_width,
                height=height or self.policy.default_height,
                prompt=self._equipment_prompt(profile=profile, identity=identity, revision=revision),
            )
        return self._build_spec(
            purpose=ImagePurpose.IDENTITY_REFERENCE,
            profile=profile,
            identity=identity,
            equipment_revision_id=None,
            equipment_digest="identity-static",
            source_envelope_id=identity.creation_envelope_id,
            source_event_ids=tuple(identity.creation_event_ids),
            reference_id=slot.reference_id,
            reference_kind=kind,
            chapter_id=None,
            reference_artifact_ids=(),
            width=width or self.policy.default_width,
            height=height or self.policy.default_height,
            prompt=self._static_reference_prompt(profile=profile, identity=identity, kind=kind),
        )

    def plan_scene(
        self,
        profile: DelverProfile,
        chapter: ChronicleChapter,
        *,
        reference_artifact_ids: tuple[str, ...] = (),
        width: int | None = None,
        height: int | None = None,
    ) -> ImageProductionSpec:
        validate_chapter(chapter)
        if chapter.profile_id != profile.profile_id or chapter.crawl_id != profile.crawl_id or chapter.delver_id != profile.delver_id:
            raise ImageProductionError("scene chapter does not belong to Delver profile")
        persisted = {
            item.chapter_id: item
            for item in self.identities.chronicle.list_chapters(crawl_id=profile.crawl_id, delver_id=profile.delver_id)
        }.get(chapter.chapter_id)
        if persisted is None or persisted != chapter:
            raise ImageProductionError("scene production requires exact persisted Chronicle chapter")
        _, identity, revision = self._state(profile)
        candidates = []
        for envelope_id in chapter.source_envelope_ids:
            envelope = self.media.get_envelope(envelope_id)
            if envelope is None:
                raise ImageProductionError("scene chapter references a missing MediaEnvelope")
            candidates.append(envelope)
        source = max(candidates, key=lambda item: (item.history_prefix_count, item.export_tick, item.envelope_id))
        return self._build_spec(
            purpose=ImagePurpose.SCENE_STILL,
            profile=profile,
            identity=identity,
            equipment_revision_id=revision.revision_id,
            equipment_digest=revision.equipment_digest,
            source_envelope_id=source.envelope_id,
            source_event_ids=tuple(chapter.source_event_ids),
            reference_id=None,
            reference_kind=None,
            chapter_id=chapter.chapter_id,
            reference_artifact_ids=tuple(sorted(set(reference_artifact_ids))),
            width=width or self.policy.scene_width,
            height=height or self.policy.scene_height,
            prompt=self._scene_prompt(profile=profile, identity=identity, revision=revision, chapter=chapter),
        )

    def enqueue(self, spec: ImageProductionSpec, *, priority: int = 100) -> MediaJob:
        validate_image_spec(spec)
        job = self.media.enqueue_job(
            job_type=JOB_TYPE,
            payload={
                "protocol": PROTOCOL,
                "implementation_version": IMPLEMENTATION_VERSION,
                "phase": PHASE,
                "spec": spec.model_dump(mode="json"),
            },
            envelope_id=spec.source_envelope_id,
            provider_request=spec.provider_request,
            priority=priority,
            max_attempts=self.policy.max_attempts,
        )
        self.media.route_job(job.job_id, self.router, self.provider_policy)
        refreshed = self.media.get_job(job.job_id)
        if refreshed is None:
            raise ImageProductionError("image job disappeared after provider routing")
        return refreshed

    def enqueue_reference(
        self,
        profile: DelverProfile,
        kind: ReferenceKind,
        *,
        priority: int = 100,
        width: int | None = None,
        height: int | None = None,
    ) -> MediaJob:
        return self.enqueue(self.plan_reference(profile, kind, width=width, height=height), priority=priority)

    def enqueue_scene(
        self,
        profile: DelverProfile,
        chapter: ChronicleChapter,
        *,
        reference_artifact_ids: tuple[str, ...] = (),
        priority: int = 100,
        width: int | None = None,
        height: int | None = None,
    ) -> MediaJob:
        return self.enqueue(
            self.plan_scene(
                profile,
                chapter,
                reference_artifact_ids=reference_artifact_ids,
                width=width,
                height=height,
            ),
            priority=priority,
        )

    @staticmethod
    def _spec_from_job(job: MediaJob) -> ImageProductionSpec:
        if job.job_type != JOB_TYPE:
            raise ImageProductionError("image worker received a non-image media job")
        payload = job.payload
        if payload.get("protocol") != PROTOCOL or payload.get("implementation_version") != IMPLEMENTATION_VERSION or payload.get("phase") != PHASE:
            raise ImageProductionError("image job payload protocol/version mismatch")
        spec = ImageProductionSpec.model_validate(payload.get("spec"))
        validate_image_spec(spec)
        if job.provider_request != spec.provider_request:
            raise ImageProductionError("durable job provider request diverged from image spec")
        return spec

    def _relative_paths(self, spec: ImageProductionSpec) -> tuple[str, str]:
        identity_part = f"v{spec.identity_version:03d}"
        basename = f"{spec.purpose.value}-{spec.spec_id}.png"
        relative_image = (Path("images") / spec.crawl_id / spec.delver_id / identity_part / basename).as_posix()
        return relative_image, f"{relative_image}.json"

    @staticmethod
    def _write_atomic(path: Path, payload: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f"{path.name}.tmp")
        temporary.write_bytes(payload)
        temporary.replace(path)

    def run_next(self, *, worker_id: str = "underreach-local-image-worker") -> ImageProductionResult | None:
        lease = self.media.claim_next(worker_id)
        if lease is None:
            return None
        job = lease.job
        if job.job_type != JOB_TYPE:
            self.media.fail_job(job.job_id, reason_code="wrong_worker_job_type", retryable=False)
            return ImageProductionResult(job_id=job.job_id, status=JobStatus.FAILED, reason_code="wrong_worker_job_type")
        try:
            spec = self._spec_from_job(job)
        except Exception:
            self.media.fail_job(job.job_id, reason_code="invalid_image_job_spec", retryable=False)
            raise

        provider_id = job.selected_provider_id
        provider = self._executors.get(provider_id or "")
        if provider is None:
            failed = self.media.fail_job(job.job_id, reason_code="provider_executor_unavailable", retryable=True)
            return ImageProductionResult(
                job_id=job.job_id,
                status=failed.status,
                provider_id=provider_id,
                reason_code="provider_executor_unavailable",
            )

        request = ImageRenderRequest(spec=spec, job_id=job.job_id, attempt_id=lease.attempt_id)
        estimated_gpu_ms = (
            int(round(provider.descriptor.estimated_runtime_seconds * 1000))
            if provider.descriptor.estimated_vram_mb > 0
            else 0
        )
        try:
            output = provider.render(request)
        except Exception as exc:
            self.media.record_provider_execution(
                job_id=job.job_id,
                attempt_id=lease.attempt_id,
                provider_id=provider.descriptor.provider_id,
                status="failed",
                estimated_cost_microusd=provider.descriptor.estimated_cost_microusd,
                actual_cost_microusd=0,
                estimated_gpu_ms=estimated_gpu_ms,
                actual_gpu_ms=0,
                metadata={
                    "reason_code": "provider_render_failed",
                    "error_type": type(exc).__name__,
                    "presentation_only": True,
                },
            )
            failed = self.media.fail_job(job.job_id, reason_code="provider_render_failed", retryable=True)
            return ImageProductionResult(
                job_id=job.job_id,
                status=failed.status,
                provider_id=provider.descriptor.provider_id,
                reason_code="provider_render_failed",
            )

        image_digest = sha256(output.image_bytes).hexdigest()
        relative_image, relative_sidecar = self._relative_paths(spec)
        image_path = self.output_root / relative_image
        sidecar_path = self.output_root / relative_sidecar
        self._write_atomic(image_path, output.image_bytes)

        sidecar_body = {
            "protocol": PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "phase": PHASE,
            "job_id": job.job_id,
            "attempt_id": lease.attempt_id,
            "provider_id": provider.descriptor.provider_id,
            "provider_local": provider.descriptor.local,
            "provider_paid": provider.descriptor.paid,
            "spec_id": spec.spec_id,
            "spec_digest": spec.digest,
            "purpose": spec.purpose.value,
            "crawl_id": spec.crawl_id,
            "profile_id": spec.profile_id,
            "delver_id": spec.delver_id,
            "identity_id": spec.identity_id,
            "equipment_revision_id": spec.equipment_revision_id,
            "source_envelope_id": spec.source_envelope_id,
            "source_event_ids": list(spec.source_event_ids),
            "reference_id": spec.reference_id,
            "reference_kind": spec.reference_kind.value if spec.reference_kind is not None else None,
            "chapter_id": spec.chapter_id,
            "reference_artifact_ids": list(spec.reference_artifact_ids),
            "deterministic_seed": spec.deterministic_seed,
            "width": spec.width,
            "height": spec.height,
            "prompt_template_version": spec.prompt_template_version,
            "output_uri": relative_image,
            "output_sha256": image_digest,
            "provider_metadata": output.metadata,
            "canonical_authority": False,
            "presentation_can_mutate_simulation": False,
        }
        sidecar_bytes = canonical_json(sidecar_body).encode("utf-8")
        sidecar_digest = sha256(sidecar_bytes).hexdigest()
        self._write_atomic(sidecar_path, sidecar_bytes)

        artifact_id = self.media.record_artifact(
            job_id=job.job_id,
            artifact_kind="image/png",
            uri=relative_image,
            digest=image_digest,
            metadata={
                "spec_id": spec.spec_id,
                "identity_id": spec.identity_id,
                "equipment_revision_id": spec.equipment_revision_id,
                "reference_id": spec.reference_id,
                "chapter_id": spec.chapter_id,
                "source_envelope_id": spec.source_envelope_id,
                "source_event_ids": list(spec.source_event_ids),
                "provider_id": provider.descriptor.provider_id,
                "presentation_only": True,
            },
        )
        sidecar_artifact_id = self.media.record_artifact(
            job_id=job.job_id,
            artifact_kind="application/json",
            uri=relative_sidecar,
            digest=sidecar_digest,
            metadata={"image_artifact_id": artifact_id, "spec_id": spec.spec_id, "presentation_only": True},
        )
        self.media.record_provider_execution(
            job_id=job.job_id,
            attempt_id=lease.attempt_id,
            provider_id=provider.descriptor.provider_id,
            status="completed",
            estimated_cost_microusd=provider.descriptor.estimated_cost_microusd,
            actual_cost_microusd=(provider.descriptor.estimated_cost_microusd if provider.descriptor.paid else 0),
            estimated_gpu_ms=estimated_gpu_ms,
            actual_gpu_ms=output.actual_gpu_ms,
            metadata={
                "artifact_id": artifact_id,
                "sidecar_artifact_id": sidecar_artifact_id,
                "spec_digest": spec.digest,
                "presentation_only": True,
            },
        )
        completed = self.media.complete_job(
            job.job_id,
            resource_usage={
                "actual_gpu_ms": output.actual_gpu_ms,
                "output_bytes": len(output.image_bytes),
                "provider_id": provider.descriptor.provider_id,
            },
        )
        return ImageProductionResult(
            job_id=job.job_id,
            status=completed.status,
            provider_id=provider.descriptor.provider_id,
            artifact_id=artifact_id,
            sidecar_artifact_id=sidecar_artifact_id,
            output_uri=relative_image,
            output_digest=image_digest,
            sidecar_uri=relative_sidecar,
            sidecar_digest=sidecar_digest,
        )

    def snapshot(self) -> dict[str, Any]:
        media_snapshot = self.media.snapshot()
        image_jobs = [job for job in media_snapshot["jobs"] if job["job_type"] == JOB_TYPE]
        image_job_ids = {job["job_id"] for job in image_jobs}
        artifacts = [artifact for artifact in media_snapshot["artifacts"] if artifact["job_id"] in image_job_ids]
        executions = [execution for execution in media_snapshot["provider_executions"] if execution["job_id"] in image_job_ids]
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
            "policy": self.policy.model_dump(mode="json"),
            "policy_digest": self.policy.digest,
            "providers": [provider.model_dump(mode="json") for provider in self.router.providers()],
            "jobs": image_jobs,
            "job_count": len(image_jobs),
            "job_digest": payload_digest(image_jobs),
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
    "PROMPT_TEMPLATE_VERSION",
    "ImagePurpose",
    "ImageProductionPolicy",
    "ImageProductionSpec",
    "ImageRenderRequest",
    "ImageRenderOutput",
    "ImageProductionResult",
    "ImageProductionError",
    "HeadlessImageProvider",
    "DeterministicLocalPngProvider",
    "HeadlessLocalImageProductionService",
    "deterministic_png_bytes",
    "validate_image_spec",
]
