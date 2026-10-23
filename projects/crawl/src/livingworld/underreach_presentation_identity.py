"""Versioned presentation-only Delver identities for Phase 30.5.6.

30.5.6 allocates stable media identities and reusable reference slots for Delvers
that have already become media-relevant through the accepted Chronicle layer.
It does not generate images, invoke providers, enqueue generation work, or mutate
canonical Crawl state. Generated appearance remains presentation state forever
unless a separate canonical system explicitly owns the same fact.
"""
from __future__ import annotations

from enum import StrEnum
from hashlib import sha256
from threading import RLock
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import JSON, Boolean, Integer, String, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from .runtime_checkpoint import payload_digest
from .underreach_delver_chronicle_profile import (
    DelverChronicleProfileService,
    DelverProfile,
    ProfileEquipment,
    validate_profile,
)
from .underreach_media_event_export import MediaEnvelope, validate_media_envelope
from .underreach_media_foundation import MediaPersistence


PROTOCOL = "presentation_identity.v1"
IMPLEMENTATION_VERSION = "30.5.6"
PHASE = "30.5"

STATIC_REFERENCE_KINDS = (
    "portrait",
    "face_reference",
    "three_quarter",
    "full_body_front",
    "full_body_side",
    "combat_reference",
)


class PresentationIdentityError(ValueError):
    """Raised when presentation identity invariants are violated."""


class ReferenceKind(StrEnum):
    PORTRAIT = "portrait"
    FACE_REFERENCE = "face_reference"
    THREE_QUARTER = "three_quarter"
    FULL_BODY_FRONT = "full_body_front"
    FULL_BODY_SIDE = "full_body_side"
    COMBAT_REFERENCE = "combat_reference"
    CURRENT_EQUIPMENT = "current_equipment_reference"


class ReferenceStatus(StrEnum):
    PENDING_GENERATION = "pending_generation"
    GENERATED = "generated"


class PresentationIdentityPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)

    default_visual_profile: str = "underreach_default"
    default_renderer_profile: str = "capability:image_reference_conditioning"
    max_identity_versions: int = Field(default=16, ge=1, le=128)
    require_media_relevance: bool = True

    @property
    def digest(self) -> str:
        return payload_digest(self.model_dump(mode="json"))


class PresentationReferenceSlot(BaseModel):
    model_config = ConfigDict(frozen=True)

    reference_id: str
    kind: ReferenceKind
    relative_path: str
    status: ReferenceStatus = ReferenceStatus.PENDING_GENERATION
    artifact_id: str | None = None
    generated: bool = False
    digest: str


class PresentationIdentity(BaseModel):
    model_config = ConfigDict(frozen=True)

    protocol: str = PROTOCOL
    implementation_version: str = IMPLEMENTATION_VERSION
    phase: str = PHASE
    identity_id: str
    profile_id: str
    crawl_id: str
    delver_id: str
    identity_version: int = Field(ge=1)
    visual_profile: str
    renderer_profile: str
    deterministic_seed: int = Field(ge=0)
    creation_profile_digest: str
    creation_envelope_id: str
    creation_event_ids: tuple[str, ...]
    reference_slots: tuple[PresentationReferenceSlot, ...]
    presentation_traits: dict[str, Any] = {}
    canonical_identity_fields_added: bool = False
    canonical_authority: bool = False
    generated_visuals_used: bool = False
    provider_invocation_used: bool = False
    presentation_can_mutate_simulation: bool = False
    policy_digest: str
    digest: str


class EquipmentReferenceRevision(BaseModel):
    model_config = ConfigDict(frozen=True)

    protocol: str = PROTOCOL
    implementation_version: str = IMPLEMENTATION_VERSION
    phase: str = PHASE
    revision_id: str
    identity_id: str
    profile_id: str
    crawl_id: str
    delver_id: str
    revision_index: int = Field(ge=1)
    equipment_digest: str
    equipment: tuple[ProfileEquipment, ...]
    source_profile_digest: str
    source_envelope_id: str
    source_event_ids: tuple[str, ...]
    reference_slot: PresentationReferenceSlot
    generated_visuals_used: bool = False
    provider_invocation_used: bool = False
    presentation_can_mutate_simulation: bool = False
    digest: str


class PresentationIdentityBinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    protocol: str = PROTOCOL
    implementation_version: str = IMPLEMENTATION_VERSION
    phase: str = PHASE
    profile_id: str
    crawl_id: str
    delver_id: str
    active_identity_id: str
    current_equipment_revision_id: str
    identity_version_count: int = Field(ge=1)
    presentation_can_mutate_simulation: bool = False
    canonical_authority: bool = False
    digest: str


class PresentationIdentityState(BaseModel):
    model_config = ConfigDict(frozen=True)

    identity: PresentationIdentity
    equipment_revision: EquipmentReferenceRevision
    binding: PresentationIdentityBinding


class PresentationIdentityBase(DeclarativeBase):
    """30.5.6-only media tables."""


class PresentationIdentityRow(PresentationIdentityBase):
    __tablename__ = "media_presentation_identities"

    identity_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    profile_id: Mapped[str] = mapped_column(String(96), index=True)
    crawl_id: Mapped[str] = mapped_column(String(96), index=True)
    delver_id: Mapped[str] = mapped_column(String(96), index=True)
    identity_version: Mapped[int] = mapped_column(Integer, index=True)
    visual_profile: Mapped[str] = mapped_column(String(128), index=True)
    renderer_profile: Mapped[str] = mapped_column(String(192), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    digest: Mapped[str] = mapped_column(String(96), nullable=False)


class EquipmentReferenceRevisionRow(PresentationIdentityBase):
    __tablename__ = "media_presentation_equipment_revisions"

    revision_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    identity_id: Mapped[str] = mapped_column(String(96), index=True)
    profile_id: Mapped[str] = mapped_column(String(96), index=True)
    equipment_digest: Mapped[str] = mapped_column(String(96), index=True)
    revision_index: Mapped[int] = mapped_column(Integer, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    digest: Mapped[str] = mapped_column(String(96), nullable=False)


class PresentationIdentityBindingRow(PresentationIdentityBase):
    __tablename__ = "media_presentation_identity_bindings"

    profile_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    crawl_id: Mapped[str] = mapped_column(String(96), index=True)
    delver_id: Mapped[str] = mapped_column(String(96), index=True)
    active_identity_id: Mapped[str] = mapped_column(String(96), index=True)
    current_equipment_revision_id: Mapped[str] = mapped_column(String(96), index=True)
    identity_version_count: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    digest: Mapped[str] = mapped_column(String(96), nullable=False)


def _stable_id(prefix: str, *parts: object) -> str:
    text = ":".join(str(part) for part in parts)
    return f"{prefix}_{sha256(text.encode('utf-8')).hexdigest()[:24]}"


def _stable_seed(*parts: object) -> int:
    text = ":".join(str(part) for part in parts)
    return int(sha256(text.encode("utf-8")).hexdigest()[:15], 16)


def _body_digest(model: BaseModel) -> str:
    return payload_digest(model.model_dump(mode="json", exclude={"digest"}))


def _reference_slot(
    *,
    identity_id: str,
    delver_id: str,
    identity_version: int,
    kind: ReferenceKind,
    suffix: str | None = None,
) -> PresentationReferenceSlot:
    identity_part = f"v{identity_version:03d}"
    filename = {
        ReferenceKind.PORTRAIT: "portrait.png",
        ReferenceKind.FACE_REFERENCE: "face-reference.png",
        ReferenceKind.THREE_QUARTER: "three-quarter.png",
        ReferenceKind.FULL_BODY_FRONT: "full-body-front.png",
        ReferenceKind.FULL_BODY_SIDE: "full-body-side.png",
        ReferenceKind.COMBAT_REFERENCE: "combat-reference.png",
        ReferenceKind.CURRENT_EQUIPMENT: f"current-equipment-reference-{suffix or 'base'}.png",
    }[kind]
    relative_path = f"media/delvers/{delver_id}/{PROTOCOL}/{identity_part}/{filename}"
    reference_id = _stable_id("presentation_reference", identity_id, kind.value, suffix or "static")
    body = {
        "reference_id": reference_id,
        "kind": kind.value,
        "relative_path": relative_path,
        "status": ReferenceStatus.PENDING_GENERATION.value,
        "artifact_id": None,
        "generated": False,
    }
    return PresentationReferenceSlot.model_validate({**body, "digest": payload_digest(body)})


def _normalized_equipment(equipment: tuple[ProfileEquipment, ...]) -> tuple[ProfileEquipment, ...]:
    return tuple(sorted(equipment, key=lambda item: item.item_id))


def _equipment_digest(equipment: tuple[ProfileEquipment, ...]) -> str:
    return payload_digest([item.model_dump(mode="json") for item in _normalized_equipment(equipment)])


def _equipment_from_envelope(
    envelope: MediaEnvelope,
    delver_id: str,
    *,
    max_items: int,
) -> tuple[ProfileEquipment, ...]:
    participant = envelope.participant_context.get(delver_id, {}) if isinstance(envelope.participant_context, dict) else {}
    equipped = participant.get("equipment", {}) if isinstance(participant, dict) else {}
    equipped_ids = {value for value in equipped.values() if isinstance(value, str)} if isinstance(equipped, dict) else set()
    records: dict[str, ProfileEquipment] = {}
    for item in envelope.item_context:
        if not isinstance(item, dict):
            continue
        item_id = item.get("id")
        if not isinstance(item_id, str):
            continue
        owned = item.get("owner_descender_id") == delver_id
        important = bool(item.get("important"))
        if item_id not in equipped_ids and not (owned and important):
            continue
        records[item_id] = ProfileEquipment(
            item_id=item_id,
            name=str(item.get("name") or item_id),
            category=str(item["category"]) if item.get("category") is not None else None,
            rarity=str(item["rarity"]) if item.get("rarity") is not None else None,
            slot=str(item["slot"]) if item.get("slot") is not None else None,
            important=important,
        )
    for item_id in sorted(equipped_ids):
        records.setdefault(item_id, ProfileEquipment(item_id=item_id, name=item_id))
    values = sorted(records.values(), key=lambda item: (0 if item.important else 1, item.slot or "", item.item_id))
    return tuple(values[:max_items])


def validate_reference_slot(slot: PresentationReferenceSlot) -> bool:
    if slot.generated != (slot.status == ReferenceStatus.GENERATED):
        raise PresentationIdentityError("reference generated/status flags diverged")
    if slot.generated and not slot.artifact_id:
        raise PresentationIdentityError("generated reference lacks artifact provenance")
    if not slot.generated and slot.artifact_id is not None:
        raise PresentationIdentityError("pending reference cannot claim an artifact")
    if slot.digest != _body_digest(slot):
        raise PresentationIdentityError("presentation reference digest mismatch")
    return True


def validate_identity(identity: PresentationIdentity) -> bool:
    if identity.protocol != PROTOCOL or identity.implementation_version != IMPLEMENTATION_VERSION or identity.phase != PHASE:
        raise PresentationIdentityError("presentation identity protocol/version mismatch")
    if not identity.visual_profile.strip() or not identity.renderer_profile.strip():
        raise PresentationIdentityError("presentation identity requires visual/renderer profiles")
    if not identity.creation_event_ids:
        raise PresentationIdentityError("presentation identity lacks canonical event provenance")
    kinds = tuple(slot.kind.value for slot in identity.reference_slots)
    if kinds != STATIC_REFERENCE_KINDS:
        raise PresentationIdentityError("presentation identity static reference contract changed")
    if len({slot.reference_id for slot in identity.reference_slots}) != len(identity.reference_slots):
        raise PresentationIdentityError("presentation identity reference IDs are not unique")
    for slot in identity.reference_slots:
        validate_reference_slot(slot)
        if slot.generated:
            raise PresentationIdentityError("30.5.6 cannot contain generated static visuals")
    if identity.presentation_traits:
        raise PresentationIdentityError("30.5.6 cannot invent generated facial/body traits")
    if (
        identity.canonical_identity_fields_added
        or identity.canonical_authority
        or identity.generated_visuals_used
        or identity.provider_invocation_used
        or identity.presentation_can_mutate_simulation
    ):
        raise PresentationIdentityError("presentation identity escaped the 30.5.6 authority boundary")
    if identity.digest != _body_digest(identity):
        raise PresentationIdentityError("presentation identity digest mismatch")
    return True


def validate_equipment_revision(revision: EquipmentReferenceRevision) -> bool:
    if revision.protocol != PROTOCOL or revision.implementation_version != IMPLEMENTATION_VERSION or revision.phase != PHASE:
        raise PresentationIdentityError("equipment reference revision protocol/version mismatch")
    normalized = tuple(sorted(revision.equipment, key=lambda item: item.item_id))
    if revision.equipment != normalized:
        raise PresentationIdentityError("equipment reference payload is not normalized")
    if revision.equipment_digest != payload_digest([item.model_dump(mode="json") for item in revision.equipment]):
        raise PresentationIdentityError("equipment reference digest does not match visible equipment")
    validate_reference_slot(revision.reference_slot)
    if revision.reference_slot.kind != ReferenceKind.CURRENT_EQUIPMENT or revision.reference_slot.generated:
        raise PresentationIdentityError("30.5.6 equipment reference must remain pending generation")
    if revision.generated_visuals_used or revision.provider_invocation_used or revision.presentation_can_mutate_simulation:
        raise PresentationIdentityError("equipment reference escaped presentation-only authority")
    if revision.digest != _body_digest(revision):
        raise PresentationIdentityError("equipment reference revision digest mismatch")
    return True


def validate_binding(binding: PresentationIdentityBinding) -> bool:
    if binding.protocol != PROTOCOL or binding.implementation_version != IMPLEMENTATION_VERSION or binding.phase != PHASE:
        raise PresentationIdentityError("presentation identity binding protocol/version mismatch")
    if binding.presentation_can_mutate_simulation or binding.canonical_authority:
        raise PresentationIdentityError("presentation identity binding gained canonical authority")
    if binding.digest != _body_digest(binding):
        raise PresentationIdentityError("presentation identity binding digest mismatch")
    return True


class PresentationIdentityService:
    """Allocate deterministic media identities without generating media."""

    def __init__(
        self,
        media: MediaPersistence,
        *,
        chronicle: DelverChronicleProfileService,
        policy: PresentationIdentityPolicy | None = None,
    ) -> None:
        self.media = media
        self.chronicle = chronicle
        self.policy = policy or PresentationIdentityPolicy()
        self._lock = RLock()

    def initialize(self) -> None:
        with self._lock:
            PresentationIdentityBase.metadata.create_all(self.media.engine)

    def _require_profile(self, profile: DelverProfile) -> None:
        validate_profile(profile)
        persisted = self.chronicle.get_profile(profile.crawl_id, profile.delver_id)
        if persisted is None or persisted != profile or persisted.digest != profile.digest:
            raise PresentationIdentityError("presentation identity requires exact persisted DelverProfile")
        if self.policy.require_media_relevance and not profile.chapter_ids and not profile.chronicle_closed:
            raise PresentationIdentityError("Delver is not media-relevant yet")

    def _latest_profile_envelope(self, profile: DelverProfile) -> MediaEnvelope:
        candidates: list[MediaEnvelope] = []
        for envelope_id in profile.source_envelope_ids:
            envelope = self.media.get_envelope(envelope_id)
            if envelope is None:
                raise PresentationIdentityError("presentation profile references a missing MediaEnvelope")
            validate_media_envelope(envelope)
            if envelope.crawl_id != profile.crawl_id or profile.delver_id not in envelope.delver_ids:
                raise PresentationIdentityError("presentation profile envelope provenance diverged from Delver identity")
            candidates.append(envelope)
        if not candidates:
            raise PresentationIdentityError("presentation profile lacks MediaEnvelope provenance")
        return max(
            candidates,
            key=lambda envelope: (
                envelope.history_prefix_count,
                envelope.export_tick,
                envelope.envelope_id,
            ),
        )

    @staticmethod
    def _identity_from_row(row: PresentationIdentityRow | None) -> PresentationIdentity | None:
        if row is None:
            return None
        value = PresentationIdentity.model_validate(row.payload)
        validate_identity(value)
        return value

    @staticmethod
    def _revision_from_row(row: EquipmentReferenceRevisionRow | None) -> EquipmentReferenceRevision | None:
        if row is None:
            return None
        value = EquipmentReferenceRevision.model_validate(row.payload)
        validate_equipment_revision(value)
        return value

    @staticmethod
    def _binding_from_row(row: PresentationIdentityBindingRow | None) -> PresentationIdentityBinding | None:
        if row is None:
            return None
        value = PresentationIdentityBinding.model_validate(row.payload)
        validate_binding(value)
        return value

    def _create_identity(
        self,
        session: Session,
        profile: DelverProfile,
        source_envelope: MediaEnvelope,
        *,
        identity_version: int,
        visual_profile: str,
        renderer_profile: str,
    ) -> PresentationIdentity:
        if identity_version > self.policy.max_identity_versions:
            raise PresentationIdentityError("presentation identity version limit reached")
        identity_id = _stable_id(
            "presentation_identity",
            profile.crawl_id,
            profile.delver_id,
            identity_version,
            visual_profile,
            renderer_profile,
        )
        existing = self._identity_from_row(session.get(PresentationIdentityRow, identity_id))
        if existing is not None:
            return existing
        slots = tuple(
            _reference_slot(
                identity_id=identity_id,
                delver_id=profile.delver_id,
                identity_version=identity_version,
                kind=ReferenceKind(kind),
            )
            for kind in STATIC_REFERENCE_KINDS
        )
        body = {
            "protocol": PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "phase": PHASE,
            "identity_id": identity_id,
            "profile_id": profile.profile_id,
            "crawl_id": profile.crawl_id,
            "delver_id": profile.delver_id,
            "identity_version": identity_version,
            "visual_profile": visual_profile,
            "renderer_profile": renderer_profile,
            "deterministic_seed": _stable_seed(identity_id, self.policy.digest),
            "creation_profile_digest": profile.digest,
            "creation_envelope_id": source_envelope.envelope_id,
            "creation_event_ids": list(source_envelope.source_event_ids),
            "reference_slots": [slot.model_dump(mode="json") for slot in slots],
            "presentation_traits": {},
            "canonical_identity_fields_added": False,
            "canonical_authority": False,
            "generated_visuals_used": False,
            "provider_invocation_used": False,
            "presentation_can_mutate_simulation": False,
            "policy_digest": self.policy.digest,
        }
        identity = PresentationIdentity.model_validate({**body, "digest": payload_digest(body)})
        validate_identity(identity)
        session.add(
            PresentationIdentityRow(
                identity_id=identity.identity_id,
                profile_id=identity.profile_id,
                crawl_id=identity.crawl_id,
                delver_id=identity.delver_id,
                identity_version=identity.identity_version,
                visual_profile=identity.visual_profile,
                renderer_profile=identity.renderer_profile,
                payload=identity.model_dump(mode="json"),
                digest=identity.digest,
            )
        )
        return identity

    def _equipment_revision(
        self,
        session: Session,
        profile: DelverProfile,
        identity: PresentationIdentity,
        source_envelope: MediaEnvelope,
    ) -> EquipmentReferenceRevision:
        equipment = _normalized_equipment(
            _equipment_from_envelope(
                source_envelope,
                profile.delver_id,
                max_items=self.chronicle.policy.max_notable_equipment,
            )
        )
        equipment_digest = _equipment_digest(equipment)
        revision_id = _stable_id("presentation_equipment", identity.identity_id, equipment_digest)
        existing = self._revision_from_row(session.get(EquipmentReferenceRevisionRow, revision_id))
        if existing is not None:
            return existing
        rows = session.scalars(
            select(EquipmentReferenceRevisionRow)
            .where(EquipmentReferenceRevisionRow.identity_id == identity.identity_id)
            .order_by(EquipmentReferenceRevisionRow.revision_index)
        ).all()
        revision_index = len(rows) + 1
        slot = _reference_slot(
            identity_id=identity.identity_id,
            delver_id=profile.delver_id,
            identity_version=identity.identity_version,
            kind=ReferenceKind.CURRENT_EQUIPMENT,
            suffix=equipment_digest[:12],
        )
        body = {
            "protocol": PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "phase": PHASE,
            "revision_id": revision_id,
            "identity_id": identity.identity_id,
            "profile_id": profile.profile_id,
            "crawl_id": profile.crawl_id,
            "delver_id": profile.delver_id,
            "revision_index": revision_index,
            "equipment_digest": equipment_digest,
            "equipment": [item.model_dump(mode="json") for item in equipment],
            "source_profile_digest": profile.digest,
            "source_envelope_id": source_envelope.envelope_id,
            "source_event_ids": list(source_envelope.source_event_ids),
            "reference_slot": slot.model_dump(mode="json"),
            "generated_visuals_used": False,
            "provider_invocation_used": False,
            "presentation_can_mutate_simulation": False,
        }
        revision = EquipmentReferenceRevision.model_validate({**body, "digest": payload_digest(body)})
        validate_equipment_revision(revision)
        session.add(
            EquipmentReferenceRevisionRow(
                revision_id=revision.revision_id,
                identity_id=revision.identity_id,
                profile_id=revision.profile_id,
                equipment_digest=revision.equipment_digest,
                revision_index=revision.revision_index,
                payload=revision.model_dump(mode="json"),
                digest=revision.digest,
            )
        )
        return revision

    def _store_binding(
        self,
        session: Session,
        profile: DelverProfile,
        identity: PresentationIdentity,
        revision: EquipmentReferenceRevision,
        *,
        version_count: int,
    ) -> PresentationIdentityBinding:
        body = {
            "protocol": PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "phase": PHASE,
            "profile_id": profile.profile_id,
            "crawl_id": profile.crawl_id,
            "delver_id": profile.delver_id,
            "active_identity_id": identity.identity_id,
            "current_equipment_revision_id": revision.revision_id,
            "identity_version_count": version_count,
            "presentation_can_mutate_simulation": False,
            "canonical_authority": False,
        }
        binding = PresentationIdentityBinding.model_validate({**body, "digest": payload_digest(body)})
        validate_binding(binding)
        payload = binding.model_dump(mode="json")
        row = session.get(PresentationIdentityBindingRow, profile.profile_id)
        if row is None:
            session.add(
                PresentationIdentityBindingRow(
                    profile_id=binding.profile_id,
                    crawl_id=binding.crawl_id,
                    delver_id=binding.delver_id,
                    active_identity_id=binding.active_identity_id,
                    current_equipment_revision_id=binding.current_equipment_revision_id,
                    identity_version_count=binding.identity_version_count,
                    payload=payload,
                    digest=binding.digest,
                )
            )
        else:
            row.active_identity_id = binding.active_identity_id
            row.current_equipment_revision_id = binding.current_equipment_revision_id
            row.identity_version_count = binding.identity_version_count
            row.payload = payload
            row.digest = binding.digest
        return binding

    def ensure_identity(
        self,
        profile: DelverProfile,
        *,
        visual_profile: str | None = None,
        renderer_profile: str | None = None,
    ) -> PresentationIdentityState:
        self._require_profile(profile)
        source_envelope = self._latest_profile_envelope(profile)
        visual = (visual_profile or self.policy.default_visual_profile).strip()
        renderer = (renderer_profile or self.policy.default_renderer_profile).strip()
        if not visual or not renderer:
            raise PresentationIdentityError("visual and renderer profiles cannot be blank")

        with self._lock:
            with Session(self.media.engine) as session:
                binding = self._binding_from_row(session.get(PresentationIdentityBindingRow, profile.profile_id))
                identity: PresentationIdentity | None = None
                version_count = 0
                if binding is not None:
                    version_count = binding.identity_version_count
                    identity = self._identity_from_row(session.get(PresentationIdentityRow, binding.active_identity_id))
                    if identity is None:
                        raise PresentationIdentityError("presentation binding lost active identity")
                    if identity.visual_profile != visual or identity.renderer_profile != renderer:
                        identity = None

                if identity is None:
                    identity_version = version_count + 1
                    identity = self._create_identity(
                        session,
                        profile,
                        source_envelope,
                        identity_version=identity_version,
                        visual_profile=visual,
                        renderer_profile=renderer,
                    )
                    version_count = identity_version

                revision = self._equipment_revision(session, profile, identity, source_envelope)
                binding = self._store_binding(
                    session,
                    profile,
                    identity,
                    revision,
                    version_count=version_count,
                )
                session.commit()
                return PresentationIdentityState(identity=identity, equipment_revision=revision, binding=binding)

    def get_binding(self, profile_id: str) -> PresentationIdentityBinding | None:
        with self._lock:
            with Session(self.media.engine) as session:
                return self._binding_from_row(session.get(PresentationIdentityBindingRow, profile_id))

    def get_identity(self, identity_id: str) -> PresentationIdentity | None:
        with self._lock:
            with Session(self.media.engine) as session:
                return self._identity_from_row(session.get(PresentationIdentityRow, identity_id))

    def get_equipment_revision(self, revision_id: str) -> EquipmentReferenceRevision | None:
        with self._lock:
            with Session(self.media.engine) as session:
                return self._revision_from_row(session.get(EquipmentReferenceRevisionRow, revision_id))

    def list_identities(self, *, profile_id: str | None = None) -> tuple[PresentationIdentity, ...]:
        with self._lock:
            with Session(self.media.engine) as session:
                statement = select(PresentationIdentityRow)
                if profile_id is not None:
                    statement = statement.where(PresentationIdentityRow.profile_id == profile_id)
                rows = session.scalars(statement.order_by(PresentationIdentityRow.profile_id, PresentationIdentityRow.identity_version)).all()
                values = tuple(PresentationIdentity.model_validate(row.payload) for row in rows)
        for value in values:
            validate_identity(value)
        return values

    def list_equipment_revisions(self, *, identity_id: str | None = None) -> tuple[EquipmentReferenceRevision, ...]:
        with self._lock:
            with Session(self.media.engine) as session:
                statement = select(EquipmentReferenceRevisionRow)
                if identity_id is not None:
                    statement = statement.where(EquipmentReferenceRevisionRow.identity_id == identity_id)
                rows = session.scalars(
                    statement.order_by(EquipmentReferenceRevisionRow.identity_id, EquipmentReferenceRevisionRow.revision_index)
                ).all()
                values = tuple(EquipmentReferenceRevision.model_validate(row.payload) for row in rows)
        for value in values:
            validate_equipment_revision(value)
        return values

    def list_bindings(self) -> tuple[PresentationIdentityBinding, ...]:
        with self._lock:
            with Session(self.media.engine) as session:
                rows = session.scalars(select(PresentationIdentityBindingRow).order_by(PresentationIdentityBindingRow.profile_id)).all()
                values = tuple(PresentationIdentityBinding.model_validate(row.payload) for row in rows)
        for value in values:
            validate_binding(value)
        return values

    def snapshot(self) -> dict[str, Any]:
        identities = [item.model_dump(mode="json") for item in self.list_identities()]
        revisions = [item.model_dump(mode="json") for item in self.list_equipment_revisions()]
        bindings = [item.model_dump(mode="json") for item in self.list_bindings()]
        body = {
            "protocol": PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "phase": PHASE,
            "authoritative": False,
            "canonical_owner": "deterministic_simulation",
            "presentation_can_mutate_simulation": False,
            "canonical_identity_fields_added": False,
            "generated_visuals_used": False,
            "provider_invocation_used": False,
            "generation_jobs_created": False,
            "unreal_dependency": False,
            "cloud_api_required": False,
            "paid_provider_required": False,
            "policy": self.policy.model_dump(mode="json"),
            "policy_digest": self.policy.digest,
            "identities": identities,
            "identity_count": len(identities),
            "identity_digest": payload_digest(identities),
            "equipment_revisions": revisions,
            "equipment_revision_count": len(revisions),
            "equipment_revision_digest": payload_digest(revisions),
            "bindings": bindings,
            "binding_count": len(bindings),
            "binding_digest": payload_digest(bindings),
        }
        return {**body, "digest": payload_digest(body)}


__all__ = [
    "PROTOCOL",
    "IMPLEMENTATION_VERSION",
    "PHASE",
    "STATIC_REFERENCE_KINDS",
    "ReferenceKind",
    "ReferenceStatus",
    "PresentationIdentityPolicy",
    "PresentationReferenceSlot",
    "PresentationIdentity",
    "EquipmentReferenceRevision",
    "PresentationIdentityBinding",
    "PresentationIdentityState",
    "PresentationIdentityError",
    "PresentationIdentityService",
    "validate_reference_slot",
    "validate_identity",
    "validate_equipment_revision",
    "validate_binding",
]
