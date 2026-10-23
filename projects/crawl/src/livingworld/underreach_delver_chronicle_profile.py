"""Persistent Delver profiles and structured Chronicles for Phase 30.5 Slice 4.

30.5.4 consumes only registered MediaEnvelopes plus accepted 30.5.3 highlights
and story arcs. It maintains presentation-only public-safe profile state and
structured Chronicle chapters in the media SQLite database. No generated prose,
provider invocation, Unreal process, or canonical simulation mutation is
allowed in this slice.
"""
from __future__ import annotations

from enum import StrEnum
from hashlib import sha256
from threading import RLock
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import JSON, Boolean, Integer, String, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from .runtime_checkpoint import payload_digest
from .underreach_highlight_story_arc import (
    HighlightStoryArcService,
    MediaHighlight,
    MediaStoryArc,
    StoryArcType,
    validate_highlight,
    validate_story_arc,
)
from .underreach_media_event_export import MediaEnvelope, validate_media_envelope
from .underreach_media_foundation import MediaPersistence


PROTOCOL = "underreach.delver-chronicle-profile.v1"
IMPLEMENTATION_VERSION = "30.5.4"
PHASE = "30.5"


class ChronicleProfileError(ValueError):
    """Raised when 30.5.4 presentation-biography invariants fail."""


class ProfileStatus(StrEnum):
    ACTIVE = "ACTIVE"
    RETREATED = "RETREATED"
    DEAD = "DEAD"


class ChapterKind(StrEnum):
    HIGHLIGHT = "highlight"
    QUIET_RECAP = "quiet_recap"
    TERMINAL = "terminal"


class ChroniclePolicy(BaseModel):
    """Deterministic public-profile and quiet-recap policy."""

    model_config = ConfigDict(frozen=True)

    ally_threshold: float = Field(default=0.45, ge=0.0, le=1.0)
    rival_threshold: float = Field(default=0.45, ge=0.0, le=1.0)
    quiet_recap_min_envelopes: int = Field(default=4, ge=2, le=50)
    max_relationships_per_kind: int = Field(default=8, ge=1, le=32)
    max_notable_equipment: int = Field(default=16, ge=1, le=64)

    @property
    def digest(self) -> str:
        return payload_digest(self.model_dump(mode="json"))


class ProfileRelationship(BaseModel):
    model_config = ConfigDict(frozen=True)

    delver_id: str
    strength: float = Field(ge=0.0, le=1.0)
    dimensions: dict[str, float]


class ProfileEquipment(BaseModel):
    model_config = ConfigDict(frozen=True)

    item_id: str
    name: str
    category: str | None = None
    rarity: str | None = None
    slot: str | None = None
    important: bool = False


class ChronicleChapter(BaseModel):
    model_config = ConfigDict(frozen=True)

    protocol: str = PROTOCOL
    implementation_version: str = IMPLEMENTATION_VERSION
    phase: str = PHASE
    chapter_id: str
    profile_id: str
    crawl_id: str
    delver_id: str
    chapter_kind: ChapterKind
    title_code: str
    canonical_tick: int = Field(ge=0)
    source_envelope_ids: tuple[str, ...]
    source_event_ids: tuple[str, ...]
    allowed_fact_ids: tuple[str, ...]
    highlight_id: str | None = None
    arc_ids: tuple[str, ...] = ()
    trigger_codes: tuple[str, ...]
    terminal: bool = False
    structured_only: bool = True
    claim_verification_required: bool = True
    generated_prose_used: bool = False
    presentation_can_mutate_simulation: bool = False
    digest: str


class DelverProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    protocol: str = PROTOCOL
    implementation_version: str = IMPLEMENTATION_VERSION
    phase: str = PHASE
    profile_id: str
    crawl_id: str
    delver_id: str
    public_name: str | None = None
    status: ProfileStatus
    current_stratum: int | None = Field(default=None, ge=1)
    current_sector: str | None = None
    current_party_id: str | None = None
    current_alliance_ids: tuple[str, ...] = ()
    known_allies: tuple[ProfileRelationship, ...] = ()
    known_rivals: tuple[ProfileRelationship, ...] = ()
    notable_equipment: tuple[ProfileEquipment, ...] = ()
    presentation_identity_ref: str | None = None
    as_of_tick: int = Field(ge=0)
    as_of_envelope_id: str
    source_envelope_ids: tuple[str, ...]
    source_event_ids: tuple[str, ...]
    chapter_ids: tuple[str, ...] = ()
    pending_quiet_envelope_ids: tuple[str, ...] = ()
    chronicle_closed: bool = False
    policy_digest: str
    presentation_can_mutate_simulation: bool = False
    generated_prose_used: bool = False
    unreal_dependency: bool = False
    provider_invocation_used: bool = False
    digest: str


class ChronicleBase(DeclarativeBase):
    """30.5.4-only tables stored in the non-authoritative media database."""


class DelverProfileRow(ChronicleBase):
    __tablename__ = "media_delver_profiles"

    profile_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    crawl_id: Mapped[str] = mapped_column(String(96), index=True)
    delver_id: Mapped[str] = mapped_column(String(96), index=True)
    status: Mapped[str] = mapped_column(String(24), index=True)
    as_of_tick: Mapped[int] = mapped_column(Integer, index=True)
    chronicle_closed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    digest: Mapped[str] = mapped_column(String(96), nullable=False)


class ChronicleChapterRow(ChronicleBase):
    __tablename__ = "media_chronicle_chapters"

    chapter_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    profile_id: Mapped[str] = mapped_column(String(96), index=True)
    crawl_id: Mapped[str] = mapped_column(String(96), index=True)
    delver_id: Mapped[str] = mapped_column(String(96), index=True)
    chapter_kind: Mapped[str] = mapped_column(String(32), index=True)
    canonical_tick: Mapped[int] = mapped_column(Integer, index=True)
    terminal: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    digest: Mapped[str] = mapped_column(String(96), nullable=False)


def _stable_id(prefix: str, *parts: object) -> str:
    text = ":".join(str(part) for part in parts)
    return f"{prefix}_{sha256(text.encode('utf-8')).hexdigest()[:24]}"


def _body_digest(model: BaseModel) -> str:
    return payload_digest(model.model_dump(mode="json", exclude={"digest"}))


def _event_types(envelope: MediaEnvelope) -> tuple[str, ...]:
    return tuple(str(value).upper() for value in envelope.source_event_types)


def _contains_any(value: str, markers: Iterable[str]) -> bool:
    return any(marker in value for marker in markers)


def _terminal_status(envelope: MediaEnvelope, delver_id: str) -> ProfileStatus | None:
    types = _event_types(envelope)
    if any(_contains_any(value, ("DEATH", "ELIMINATED")) and "NEAR_DEATH" not in value for value in types):
        return ProfileStatus.DEAD
    if any("RETREATED" in value for value in types):
        return ProfileStatus.RETREATED
    context = envelope.participant_context.get(delver_id, {}) if isinstance(envelope.participant_context, dict) else {}
    status = str(context.get("status", "")).upper()
    if "DEAD" in status or "ELIMINATED" in status:
        return ProfileStatus.DEAD
    if "RETREAT" in status:
        return ProfileStatus.RETREATED
    return None


def _public_name(envelope: MediaEnvelope, delver_id: str) -> str | None:
    context = envelope.participant_context.get(delver_id, {}) if isinstance(envelope.participant_context, dict) else {}
    for key in ("public_name", "display_name", "name"):
        value = context.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _relationship_dimensions(record: dict[str, Any]) -> dict[str, float]:
    ignored = {"source_descender_id", "target_descender_id"}
    values: dict[str, float] = {}
    for key in sorted(record):
        if key in ignored:
            continue
        value = record[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        values[key] = max(-1.0, min(1.0, float(value)))
    return values


def _relationship_strengths(envelope: MediaEnvelope, delver_id: str) -> tuple[list[ProfileRelationship], list[ProfileRelationship]]:
    social = envelope.social_context if isinstance(envelope.social_context, dict) else {}
    records = social.get("relationships", [])
    allies: list[ProfileRelationship] = []
    rivals: list[ProfileRelationship] = []
    if not isinstance(records, list):
        return allies, rivals
    for record in records:
        if not isinstance(record, dict) or record.get("source_descender_id") != delver_id:
            continue
        target = record.get("target_descender_id")
        if not isinstance(target, str) or not target or target == delver_id:
            continue
        dims = _relationship_dimensions(record)
        positive = max(
            0.0,
            dims.get("trust", 0.0),
            dims.get("respect", 0.0),
            dims.get("affection", 0.0),
            dims.get("gratitude", 0.0),
        )
        negative = max(
            0.0,
            dims.get("resentment", 0.0),
            dims.get("rivalry", 0.0),
            dims.get("fear", 0.0),
            -dims.get("trust", 0.0),
        )
        if positive > 0.0:
            allies.append(ProfileRelationship(delver_id=target, strength=round(positive, 6), dimensions=dims))
        if negative > 0.0:
            rivals.append(ProfileRelationship(delver_id=target, strength=round(negative, 6), dimensions=dims))
    return allies, rivals


def _profile_relationships(
    envelope: MediaEnvelope,
    delver_id: str,
    policy: ChroniclePolicy,
) -> tuple[tuple[ProfileRelationship, ...], tuple[ProfileRelationship, ...]]:
    allies, rivals = _relationship_strengths(envelope, delver_id)
    allies = [item for item in allies if item.strength >= policy.ally_threshold]
    rivals = [item for item in rivals if item.strength >= policy.rival_threshold]
    allies.sort(key=lambda item: (-item.strength, item.delver_id))
    rivals.sort(key=lambda item: (-item.strength, item.delver_id))
    return (
        tuple(allies[: policy.max_relationships_per_kind]),
        tuple(rivals[: policy.max_relationships_per_kind]),
    )


def _alliance_ids(envelope: MediaEnvelope, party_id: str | None) -> tuple[str, ...]:
    if not party_id:
        return ()
    party = envelope.party_context if isinstance(envelope.party_context, dict) else {}
    alliances = party.get("alliances", [])
    result: list[str] = []
    if isinstance(alliances, list):
        for record in alliances:
            if not isinstance(record, dict):
                continue
            party_ids = record.get("party_ids", [])
            alliance_id = record.get("alliance_id") or record.get("id")
            if isinstance(party_ids, list) and party_id in party_ids and isinstance(alliance_id, str):
                result.append(alliance_id)
    return tuple(sorted(set(result)))


def _equipment(envelope: MediaEnvelope, delver_id: str, policy: ChroniclePolicy) -> tuple[ProfileEquipment, ...]:
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
    return tuple(values[: policy.max_notable_equipment])


def _identity_ref(envelope: MediaEnvelope, delver_id: str) -> str | None:
    participant = envelope.participant_context.get(delver_id, {}) if isinstance(envelope.participant_context, dict) else {}
    value = participant.get("presentation_identity_ref") if isinstance(participant, dict) else None
    if isinstance(value, str) and value:
        return value
    if len(envelope.delver_ids) == 1 and envelope.visual_identity_refs:
        return envelope.visual_identity_refs[0]
    return None


def _chapter_title_code(kind: ChapterKind, envelope: MediaEnvelope) -> str:
    if kind == ChapterKind.QUIET_RECAP:
        return "QUIET_LIFE_RECAP"
    if kind == ChapterKind.TERMINAL:
        if any("DEATH" in value or "ELIMINATED" in value for value in _event_types(envelope)):
            return "TERMINAL_DEATH"
        return "TERMINAL_RETREAT"
    return f"HIGHLIGHT_{_event_types(envelope)[0]}" if envelope.source_event_types else "HIGHLIGHT_EVENT"


def _chapter_trigger_codes(
    kind: ChapterKind,
    envelope: MediaEnvelope,
    highlight: MediaHighlight | None,
    arcs: Iterable[MediaStoryArc],
) -> tuple[str, ...]:
    codes = {f"event:{value}" for value in _event_types(envelope)}
    codes.add(f"chapter:{kind.value}")
    if highlight is not None:
        codes.add(f"highlight:{highlight.output_tier.value}")
        codes.update(f"reason:{value}" for value in highlight.reason_codes)
    codes.update(f"arc:{arc.arc_type.value}" for arc in arcs)
    return tuple(sorted(codes))


def _allowed_fact_ids(envelopes: Iterable[MediaEnvelope]) -> tuple[str, ...]:
    return tuple(sorted({fact.fact_id for envelope in envelopes for fact in envelope.allowed_facts}))


def _source_event_ids(envelopes: Iterable[MediaEnvelope]) -> tuple[str, ...]:
    return tuple(sorted({event_id for envelope in envelopes for event_id in envelope.source_event_ids}))


def _chapter(
    *,
    profile_id: str,
    crawl_id: str,
    delver_id: str,
    kind: ChapterKind,
    envelopes: tuple[MediaEnvelope, ...],
    highlight: MediaHighlight | None,
    arcs: tuple[MediaStoryArc, ...],
    terminal: bool,
) -> ChronicleChapter:
    envelope_ids = tuple(sorted({item.envelope_id for item in envelopes}))
    event_ids = _source_event_ids(envelopes)
    highlight_id = highlight.highlight_id if highlight is not None else None
    chapter_id = _stable_id("chronicle_chapter", profile_id, kind.value, highlight_id or "none", *envelope_ids)
    latest = max(envelopes, key=lambda item: (item.export_tick, item.envelope_id))
    body = {
        "protocol": PROTOCOL,
        "implementation_version": IMPLEMENTATION_VERSION,
        "phase": PHASE,
        "chapter_id": chapter_id,
        "profile_id": profile_id,
        "crawl_id": crawl_id,
        "delver_id": delver_id,
        "chapter_kind": kind.value,
        "title_code": _chapter_title_code(kind, latest),
        "canonical_tick": max(item.export_tick for item in envelopes),
        "source_envelope_ids": list(envelope_ids),
        "source_event_ids": list(event_ids),
        "allowed_fact_ids": list(_allowed_fact_ids(envelopes)),
        "highlight_id": highlight_id,
        "arc_ids": sorted({arc.arc_id for arc in arcs}),
        "trigger_codes": list(_chapter_trigger_codes(kind, latest, highlight, arcs)),
        "terminal": terminal,
        "structured_only": True,
        "claim_verification_required": True,
        "generated_prose_used": False,
        "presentation_can_mutate_simulation": False,
    }
    chapter = ChronicleChapter.model_validate({**body, "digest": payload_digest(body)})
    validate_chapter(chapter)
    return chapter


def validate_chapter(chapter: ChronicleChapter) -> bool:
    if chapter.protocol != PROTOCOL or chapter.implementation_version != IMPLEMENTATION_VERSION or chapter.phase != PHASE:
        raise ChronicleProfileError("Chronicle chapter protocol/version mismatch")
    if not chapter.source_envelope_ids or not chapter.source_event_ids or not chapter.allowed_fact_ids:
        raise ChronicleProfileError("Chronicle chapter provenance/fact support is incomplete")
    if tuple(sorted(set(chapter.source_envelope_ids))) != chapter.source_envelope_ids:
        raise ChronicleProfileError("Chronicle chapter envelope provenance is not normalized")
    if tuple(sorted(set(chapter.source_event_ids))) != chapter.source_event_ids:
        raise ChronicleProfileError("Chronicle chapter event provenance is not normalized")
    if tuple(sorted(set(chapter.allowed_fact_ids))) != chapter.allowed_fact_ids:
        raise ChronicleProfileError("Chronicle chapter allowed-fact provenance is not normalized")
    expected_id = _stable_id(
        "chronicle_chapter",
        chapter.profile_id,
        chapter.chapter_kind.value,
        chapter.highlight_id or "none",
        *chapter.source_envelope_ids,
    )
    if chapter.chapter_id != expected_id:
        raise ChronicleProfileError("Chronicle chapter deterministic identity mismatch")
    if chapter.chapter_kind == ChapterKind.TERMINAL and not chapter.terminal:
        raise ChronicleProfileError("terminal Chronicle chapter lost terminal status")
    if not chapter.structured_only or not chapter.claim_verification_required:
        raise ChronicleProfileError("30.5.4 chapter escaped structured pre-verification boundary")
    if chapter.generated_prose_used or chapter.presentation_can_mutate_simulation:
        raise ChronicleProfileError("30.5.4 chapter gained forbidden prose/simulation authority")
    if chapter.digest != _body_digest(chapter):
        raise ChronicleProfileError("Chronicle chapter digest mismatch")
    return True


def validate_profile(profile: DelverProfile) -> bool:
    if profile.protocol != PROTOCOL or profile.implementation_version != IMPLEMENTATION_VERSION or profile.phase != PHASE:
        raise ChronicleProfileError("Delver profile protocol/version mismatch")
    expected_id = _stable_id("delver_profile", profile.crawl_id, profile.delver_id)
    if profile.profile_id != expected_id:
        raise ChronicleProfileError("Delver profile deterministic identity mismatch")
    if not profile.source_envelope_ids or not profile.source_event_ids:
        raise ChronicleProfileError("Delver profile lacks canonical media provenance")
    for values, message in (
        (profile.source_envelope_ids, "profile envelope provenance"),
        (profile.source_event_ids, "profile event provenance"),
        (profile.chapter_ids, "profile chapter identity"),
        (profile.pending_quiet_envelope_ids, "profile quiet-history identity"),
        (profile.current_alliance_ids, "profile alliance identity"),
    ):
        if tuple(sorted(set(values))) != values:
            raise ChronicleProfileError(f"{message} is not normalized")
    if profile.chronicle_closed and profile.status == ProfileStatus.ACTIVE:
        raise ChronicleProfileError("closed Chronicle cannot have ACTIVE profile status")
    if profile.status in {ProfileStatus.DEAD, ProfileStatus.RETREATED} and not profile.chronicle_closed:
        raise ChronicleProfileError("terminal profile must close the Chronicle")
    if profile.presentation_can_mutate_simulation or profile.generated_prose_used or profile.unreal_dependency or profile.provider_invocation_used:
        raise ChronicleProfileError("30.5.4 authority/dependency boundary changed")
    if profile.digest != _body_digest(profile):
        raise ChronicleProfileError("Delver profile digest mismatch")
    return True


class DelverChronicleProfileService:
    """Builds presentation-only living biographies from accepted media truth."""

    def __init__(
        self,
        media: MediaPersistence,
        *,
        policy: ChroniclePolicy | None = None,
        highlights: HighlightStoryArcService | None = None,
    ) -> None:
        self.media = media
        self.policy = policy or ChroniclePolicy()
        self.highlights = highlights or HighlightStoryArcService(media)
        self._lock = RLock()

    def initialize(self) -> None:
        self.highlights.initialize()
        with self._lock:
            ChronicleBase.metadata.create_all(self.media.engine)

    def _require_envelope(self, envelope: MediaEnvelope) -> None:
        validate_media_envelope(envelope)
        stored = self.media.get_envelope(envelope.envelope_id)
        if stored is None or stored != envelope or stored.digest != envelope.digest:
            raise ChronicleProfileError("Chronicle processing requires the exact registered MediaEnvelope")

    def _highlight_for(self, envelope: MediaEnvelope) -> MediaHighlight | None:
        matches = [item for item in self.highlights.list_highlights(crawl_id=envelope.crawl_id) if item.envelope_id == envelope.envelope_id]
        if len(matches) > 1:
            raise ChronicleProfileError("multiple persisted highlights resolved for one envelope")
        if matches:
            validate_highlight(matches[0], self.highlights.policy)
            return matches[0]
        return None

    def _arcs_for(self, envelope: MediaEnvelope, delver_id: str) -> tuple[MediaStoryArc, ...]:
        values = []
        for arc in self.highlights.list_story_arcs(crawl_id=envelope.crawl_id):
            if envelope.envelope_id in arc.envelope_ids and delver_id in arc.subject_ids:
                validate_story_arc(arc)
                values.append(arc)
        return tuple(sorted(values, key=lambda item: item.arc_id))

    @staticmethod
    def _row_profile(row: DelverProfileRow | None) -> DelverProfile | None:
        if row is None:
            return None
        profile = DelverProfile.model_validate(row.payload)
        validate_profile(profile)
        return profile

    def _store_chapter(self, session: Session, chapter: ChronicleChapter) -> ChronicleChapter:
        validate_chapter(chapter)
        payload = chapter.model_dump(mode="json")
        row = session.get(ChronicleChapterRow, chapter.chapter_id)
        if row is None:
            session.add(
                ChronicleChapterRow(
                    chapter_id=chapter.chapter_id,
                    profile_id=chapter.profile_id,
                    crawl_id=chapter.crawl_id,
                    delver_id=chapter.delver_id,
                    chapter_kind=chapter.chapter_kind.value,
                    canonical_tick=chapter.canonical_tick,
                    terminal=chapter.terminal,
                    payload=payload,
                    digest=chapter.digest,
                )
            )
        elif row.digest != chapter.digest or row.payload != payload:
            raise ChronicleProfileError("Chronicle chapter identity resolved to different immutable payload")
        return chapter

    def _quiet_envelopes(self, ids: Iterable[str]) -> tuple[MediaEnvelope, ...]:
        values = []
        for envelope_id in sorted(set(ids)):
            envelope = self.media.get_envelope(envelope_id)
            if envelope is None:
                raise ChronicleProfileError("quiet-history envelope disappeared from media database")
            values.append(envelope)
        return tuple(values)

    def _process_delver(self, envelope: MediaEnvelope, delver_id: str) -> DelverProfile:
        highlight = self._highlight_for(envelope)
        arcs = self._arcs_for(envelope, delver_id)
        terminal_status = _terminal_status(envelope, delver_id)
        profile_id = _stable_id("delver_profile", envelope.crawl_id, delver_id)

        with self._lock:
            with Session(self.media.engine) as session:
                row = session.get(DelverProfileRow, profile_id)
                existing = self._row_profile(row)
                source_envelopes = tuple(sorted(set(existing.source_envelope_ids if existing else ()) | {envelope.envelope_id}))
                source_events = tuple(sorted(set(existing.source_event_ids if existing else ()) | set(envelope.source_event_ids)))
                chapter_ids = set(existing.chapter_ids if existing else ())
                pending_quiet = set(existing.pending_quiet_envelope_ids if existing else ())
                closed_before = bool(existing and existing.chronicle_closed)

                is_latest = existing is None or (envelope.export_tick, envelope.envelope_id) >= (existing.as_of_tick, existing.as_of_envelope_id)
                context = envelope.participant_context.get(delver_id, {}) if isinstance(envelope.participant_context, dict) else {}
                if not isinstance(context, dict):
                    context = {}

                if existing is None:
                    status = terminal_status or ProfileStatus.ACTIVE
                elif existing.status in {ProfileStatus.DEAD, ProfileStatus.RETREATED}:
                    status = existing.status
                else:
                    status = terminal_status or existing.status

                terminal = status in {ProfileStatus.DEAD, ProfileStatus.RETREATED}
                chronicle_closed = closed_before or terminal

                if highlight is not None or terminal_status is not None:
                    pending_quiet.clear()
                    kind = ChapterKind.TERMINAL if terminal_status is not None else ChapterKind.HIGHLIGHT
                    chapter = _chapter(
                        profile_id=profile_id,
                        crawl_id=envelope.crawl_id,
                        delver_id=delver_id,
                        kind=kind,
                        envelopes=(envelope,),
                        highlight=highlight,
                        arcs=arcs,
                        terminal=terminal_status is not None,
                    )
                    self._store_chapter(session, chapter)
                    chapter_ids.add(chapter.chapter_id)
                elif arcs and not chronicle_closed:
                    pending_quiet.add(envelope.envelope_id)
                    if len(pending_quiet) >= self.policy.quiet_recap_min_envelopes:
                        quiet_envelopes = self._quiet_envelopes(pending_quiet)
                        quiet_arcs = tuple(
                            sorted(
                                {
                                    arc.arc_id: arc
                                    for item in quiet_envelopes
                                    for arc in self._arcs_for(item, delver_id)
                                }.values(),
                                key=lambda item: item.arc_id,
                            )
                        )
                        chapter = _chapter(
                            profile_id=profile_id,
                            crawl_id=envelope.crawl_id,
                            delver_id=delver_id,
                            kind=ChapterKind.QUIET_RECAP,
                            envelopes=quiet_envelopes,
                            highlight=None,
                            arcs=quiet_arcs,
                            terminal=False,
                        )
                        self._store_chapter(session, chapter)
                        chapter_ids.add(chapter.chapter_id)
                        pending_quiet.clear()

                if existing is not None and (closed_before or not is_latest):
                    public_name = existing.public_name
                    current_stratum = existing.current_stratum
                    current_sector = existing.current_sector
                    current_party_id = existing.current_party_id
                    alliance_ids = existing.current_alliance_ids
                    allies = existing.known_allies
                    rivals = existing.known_rivals
                    equipment = existing.notable_equipment
                    identity_ref = existing.presentation_identity_ref
                    as_of_tick = existing.as_of_tick
                    as_of_envelope_id = existing.as_of_envelope_id
                else:
                    public_name = _public_name(envelope, delver_id) or (existing.public_name if existing else None)
                    current_stratum = context.get("current_stratum") if isinstance(context.get("current_stratum"), int) else envelope.stratum
                    current_sector = context.get("current_sector") if isinstance(context.get("current_sector"), str) else envelope.sector
                    current_party_id = context.get("current_party_id") if isinstance(context.get("current_party_id"), str) else None
                    alliance_ids = _alliance_ids(envelope, current_party_id)
                    allies, rivals = _profile_relationships(envelope, delver_id, self.policy)
                    equipment = _equipment(envelope, delver_id, self.policy)
                    identity_ref = _identity_ref(envelope, delver_id) or (existing.presentation_identity_ref if existing else None)
                    as_of_tick = envelope.export_tick
                    as_of_envelope_id = envelope.envelope_id

                body = {
                    "protocol": PROTOCOL,
                    "implementation_version": IMPLEMENTATION_VERSION,
                    "phase": PHASE,
                    "profile_id": profile_id,
                    "crawl_id": envelope.crawl_id,
                    "delver_id": delver_id,
                    "public_name": public_name,
                    "status": status.value,
                    "current_stratum": current_stratum,
                    "current_sector": current_sector,
                    "current_party_id": current_party_id,
                    "current_alliance_ids": list(alliance_ids),
                    "known_allies": [item.model_dump(mode="json") for item in allies],
                    "known_rivals": [item.model_dump(mode="json") for item in rivals],
                    "notable_equipment": [item.model_dump(mode="json") for item in equipment],
                    "presentation_identity_ref": identity_ref,
                    "as_of_tick": as_of_tick,
                    "as_of_envelope_id": as_of_envelope_id,
                    "source_envelope_ids": list(source_envelopes),
                    "source_event_ids": list(source_events),
                    "chapter_ids": sorted(chapter_ids),
                    "pending_quiet_envelope_ids": sorted(pending_quiet),
                    "chronicle_closed": chronicle_closed,
                    "policy_digest": self.policy.digest,
                    "presentation_can_mutate_simulation": False,
                    "generated_prose_used": False,
                    "unreal_dependency": False,
                    "provider_invocation_used": False,
                }
                profile = DelverProfile.model_validate({**body, "digest": payload_digest(body)})
                validate_profile(profile)
                payload = profile.model_dump(mode="json")
                if row is None:
                    session.add(
                        DelverProfileRow(
                            profile_id=profile.profile_id,
                            crawl_id=profile.crawl_id,
                            delver_id=profile.delver_id,
                            status=profile.status.value,
                            as_of_tick=profile.as_of_tick,
                            chronicle_closed=profile.chronicle_closed,
                            payload=payload,
                            digest=profile.digest,
                        )
                    )
                else:
                    row.status = profile.status.value
                    row.as_of_tick = profile.as_of_tick
                    row.chronicle_closed = profile.chronicle_closed
                    row.payload = payload
                    row.digest = profile.digest
                session.commit()
                return profile

    def process(self, envelope: MediaEnvelope) -> tuple[DelverProfile, ...]:
        self._require_envelope(envelope)
        return tuple(self._process_delver(envelope, delver_id) for delver_id in sorted(set(envelope.delver_ids)))

    def process_many(self, envelopes: Iterable[MediaEnvelope]) -> tuple[DelverProfile, ...]:
        touched: set[tuple[str, str]] = set()
        for envelope in sorted(envelopes, key=lambda item: (item.export_tick, item.envelope_id)):
            for profile in self.process(envelope):
                touched.add((profile.crawl_id, profile.delver_id))
        values = [self.get_profile(crawl_id, delver_id) for crawl_id, delver_id in sorted(touched)]
        return tuple(item for item in values if item is not None)

    def get_profile(self, crawl_id: str, delver_id: str) -> DelverProfile | None:
        profile_id = _stable_id("delver_profile", crawl_id, delver_id)
        with self._lock:
            with Session(self.media.engine) as session:
                return self._row_profile(session.get(DelverProfileRow, profile_id))

    def list_profiles(self, *, crawl_id: str | None = None) -> tuple[DelverProfile, ...]:
        with self._lock:
            with Session(self.media.engine) as session:
                statement = select(DelverProfileRow)
                if crawl_id is not None:
                    statement = statement.where(DelverProfileRow.crawl_id == crawl_id)
                rows = session.scalars(statement.order_by(DelverProfileRow.profile_id)).all()
                values = tuple(DelverProfile.model_validate(row.payload) for row in rows)
                for profile in values:
                    validate_profile(profile)
                return values

    def list_chapters(
        self,
        *,
        crawl_id: str | None = None,
        delver_id: str | None = None,
    ) -> tuple[ChronicleChapter, ...]:
        with self._lock:
            with Session(self.media.engine) as session:
                statement = select(ChronicleChapterRow)
                if crawl_id is not None:
                    statement = statement.where(ChronicleChapterRow.crawl_id == crawl_id)
                if delver_id is not None:
                    statement = statement.where(ChronicleChapterRow.delver_id == delver_id)
                rows = session.scalars(
                    statement.order_by(ChronicleChapterRow.canonical_tick, ChronicleChapterRow.chapter_id)
                ).all()
                values = tuple(ChronicleChapter.model_validate(row.payload) for row in rows)
                for chapter in values:
                    validate_chapter(chapter)
                return values

    def snapshot(self) -> dict[str, Any]:
        profiles = [item.model_dump(mode="json") for item in self.list_profiles()]
        chapters = [item.model_dump(mode="json") for item in self.list_chapters()]
        body = {
            "protocol": PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "phase": PHASE,
            "authoritative": False,
            "canonical_owner": "deterministic_simulation",
            "presentation_can_mutate_simulation": False,
            "generated_prose_used": False,
            "claim_verification_required_before_prose": True,
            "unreal_dependency": False,
            "provider_invocation_used": False,
            "policy": self.policy.model_dump(mode="json"),
            "policy_digest": self.policy.digest,
            "profiles": profiles,
            "profile_count": len(profiles),
            "profile_digest": payload_digest(profiles),
            "chapters": chapters,
            "chapter_count": len(chapters),
            "chapter_digest": payload_digest(chapters),
        }
        return {**body, "digest": payload_digest(body)}


__all__ = [
    "PROTOCOL",
    "IMPLEMENTATION_VERSION",
    "PHASE",
    "ProfileStatus",
    "ChapterKind",
    "ChroniclePolicy",
    "ProfileRelationship",
    "ProfileEquipment",
    "ChronicleChapter",
    "DelverProfile",
    "ChronicleProfileError",
    "DelverChronicleProfileService",
    "validate_chapter",
    "validate_profile",
]
