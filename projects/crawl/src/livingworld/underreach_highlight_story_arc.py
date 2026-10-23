"""Deterministic highlight and story-arc detection for Phase 30.5 Slice 3.

30.5.1 established immutable read-only MediaEnvelopes. 30.5.2 established a
separate durable media SQLite store. 30.5.3 consumes only those media-owned
inputs and deterministically decides whether an envelope qualifies as a
highlight. No LLM, provider, Unreal process, network service, or canonical
simulation mutation participates in scoring.
"""
from __future__ import annotations

from enum import StrEnum
from hashlib import sha256
from threading import RLock
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import JSON, Integer, String, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from .runtime_checkpoint import payload_digest
from .underreach_media_event_export import MediaEnvelope, validate_media_envelope
from .underreach_media_foundation import MediaPersistence


PROTOCOL = "underreach.highlight-story-arc.v1"
IMPLEMENTATION_VERSION = "30.5.3"
PHASE = "30.5"

SCORE_MAXIMA = {
    "danger": 20,
    "rarity": 15,
    "social_stakes": 20,
    "character_significance": 15,
    "outcome_reversal": 10,
    "continuity": 15,
    "visual_potential": 5,
}


class HighlightStoryArcError(ValueError):
    """Raised when 30.5.3 deterministic media-analysis invariants fail."""


class HighlightTier(StrEnum):
    ARCHIVE_ONLY = "archive_only"
    CHRONICLE = "chronicle"
    MOTION_STORY = "motion_story"
    ENHANCED_STILLS = "enhanced_stills"
    LOCAL_ANIMATION = "local_animation"
    CINEMATIC = "cinematic"


class StoryArcType(StrEnum):
    SURVIVAL = "survival"
    COMBAT = "combat"
    SOCIAL_CONFLICT = "social_conflict"
    PARTY_ALLIANCE = "party_alliance"
    LOOT_PROGRESSION = "loot_progression"
    STRATUM_PROGRESSION = "stratum_progression"


class StoryArcStatus(StrEnum):
    ACTIVE = "active"
    CLOSED = "closed"


class HighlightPolicy(BaseModel):
    """Deterministic output thresholds from the canonical 30.5 roadmap."""

    model_config = ConfigDict(frozen=True)

    chronicle_min: int = Field(default=50, ge=0, le=100)
    motion_story_min: int = Field(default=70, ge=0, le=100)
    enhanced_stills_min: int = Field(default=80, ge=0, le=100)
    local_animation_min: int = Field(default=90, ge=0, le=100)
    cinematic_min: int = Field(default=95, ge=0, le=100)

    @model_validator(mode="after")
    def validate_thresholds(self) -> "HighlightPolicy":
        values = (
            self.chronicle_min,
            self.motion_story_min,
            self.enhanced_stills_min,
            self.local_animation_min,
            self.cinematic_min,
        )
        if tuple(sorted(values)) != values or len(set(values)) != len(values):
            raise ValueError("highlight thresholds must be strictly increasing")
        return self

    @property
    def digest(self) -> str:
        return payload_digest(self.model_dump(mode="json"))


class HighlightScore(BaseModel):
    model_config = ConfigDict(frozen=True)

    danger: int = Field(ge=0, le=20)
    rarity: int = Field(ge=0, le=15)
    social_stakes: int = Field(ge=0, le=20)
    character_significance: int = Field(ge=0, le=15)
    outcome_reversal: int = Field(ge=0, le=10)
    continuity: int = Field(ge=0, le=15)
    visual_potential: int = Field(ge=0, le=5)
    total: int = Field(ge=0, le=100)

    @model_validator(mode="after")
    def validate_total(self) -> "HighlightScore":
        expected = (
            self.danger
            + self.rarity
            + self.social_stakes
            + self.character_significance
            + self.outcome_reversal
            + self.continuity
            + self.visual_potential
        )
        if self.total != expected:
            raise ValueError("highlight score total diverged from components")
        return self


class MediaStoryArc(BaseModel):
    model_config = ConfigDict(frozen=True)

    protocol: str = PROTOCOL
    implementation_version: str = IMPLEMENTATION_VERSION
    phase: str = PHASE
    arc_id: str
    crawl_id: str
    arc_type: StoryArcType
    subject_ids: tuple[str, ...]
    envelope_ids: tuple[str, ...]
    source_event_ids: tuple[str, ...]
    first_tick: int = Field(ge=0)
    last_tick: int = Field(ge=0)
    occurrence_count: int = Field(ge=1)
    status: StoryArcStatus
    digest: str


class MediaHighlight(BaseModel):
    model_config = ConfigDict(frozen=True)

    protocol: str = PROTOCOL
    implementation_version: str = IMPLEMENTATION_VERSION
    phase: str = PHASE
    highlight_id: str
    envelope_id: str
    crawl_id: str
    source_event_ids: tuple[str, ...]
    delver_ids: tuple[str, ...]
    score: HighlightScore
    output_tier: HighlightTier
    reason_codes: tuple[str, ...]
    arc_ids: tuple[str, ...]
    policy_digest: str
    presentation_can_mutate_simulation: bool = False
    llm_decision_used: bool = False
    unreal_dependency: bool = False
    provider_invocation_used: bool = False
    digest: str


class HighlightEvaluation(BaseModel):
    model_config = ConfigDict(frozen=True)

    envelope_id: str
    selected: bool
    score: HighlightScore
    output_tier: HighlightTier
    reason_codes: tuple[str, ...]
    arc_ids: tuple[str, ...]
    highlight_id: str | None
    policy_digest: str
    digest: str


class HighlightBase(DeclarativeBase):
    """30.5.3-only tables; kept separate from 30.5.2 MediaBase metadata."""


class MediaHighlightRow(HighlightBase):
    __tablename__ = "media_highlights"

    highlight_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    envelope_id: Mapped[str] = mapped_column(String(96), index=True)
    crawl_id: Mapped[str] = mapped_column(String(96), index=True)
    policy_digest: Mapped[str] = mapped_column(String(96), index=True)
    total_score: Mapped[int] = mapped_column(Integer, index=True)
    output_tier: Mapped[str] = mapped_column(String(32), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    digest: Mapped[str] = mapped_column(String(96), nullable=False)


class MediaStoryArcRow(HighlightBase):
    __tablename__ = "media_story_arcs"

    arc_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    crawl_id: Mapped[str] = mapped_column(String(96), index=True)
    arc_type: Mapped[str] = mapped_column(String(40), index=True)
    subject_key: Mapped[str] = mapped_column(String(512), index=True)
    first_tick: Mapped[int] = mapped_column(Integer, index=True)
    last_tick: Mapped[int] = mapped_column(Integer, index=True)
    status: Mapped[str] = mapped_column(String(24), index=True)
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


def _numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _clamp_component(value: int, component: str) -> int:
    return max(0, min(SCORE_MAXIMA[component], int(value)))


def _danger_score(envelope: MediaEnvelope) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    for semantic in envelope.semantic_context:
        payload = semantic.get("semantic", {}) if isinstance(semantic, dict) else {}
        if isinstance(payload, dict):
            danger = _numeric(payload.get("danger_level"))
            if danger is not None:
                candidate = int(round(max(0.0, min(1.0, danger)) * 20))
                if candidate > score:
                    score = candidate
                    reasons = ["danger:semantic"]
    weights = {
        "DEATH": 20,
        "NEAR_DEATH": 18,
        "BOSS": 17,
        "CRITICAL": 16,
        "ELITE": 14,
        "INJURY": 12,
        "COMBAT": 10,
        "ATTACK": 8,
        "HAZARD": 8,
    }
    for event_type in _event_types(envelope):
        for marker, weight in weights.items():
            if marker in event_type and weight > score:
                score = weight
                reasons = [f"danger:event:{marker.lower()}"]
    return _clamp_component(score, "danger"), reasons


def _rarity_score(envelope: MediaEnvelope) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    rarity_weights = {"common": 1, "uncommon": 6, "rare": 12, "epic": 15}
    for item in envelope.item_context:
        rarity = str(item.get("rarity", "")).lower()
        candidate = rarity_weights.get(rarity, 0)
        if bool(item.get("important")):
            candidate = max(candidate, 13)
        if candidate > score:
            score = candidate
            reasons = [f"rarity:item:{rarity or 'important'}"]
    for event_type in _event_types(envelope):
        if "RELIC" in event_type:
            score, reasons = max(score, 15), ["rarity:event:relic"] if score < 15 else reasons
        elif "LEGENDARY" in event_type or "EPIC" in event_type:
            if score < 14:
                score, reasons = 14, ["rarity:event:epic"]
        elif "RARE" in event_type and score < 12:
            score, reasons = 12, ["rarity:event:rare"]
        elif "BOSS" in event_type and score < 10:
            score, reasons = 10, ["rarity:event:boss"]
        elif "CACHE" in event_type and score < 7:
            score, reasons = 7, ["rarity:event:cache"]
    return _clamp_component(score, "rarity"), reasons


def _social_stakes_score(envelope: MediaEnvelope) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    weighted_markers = (
        ("ALLIANCE_BETRAYAL", 20),
        ("BETRAY", 20),
        ("SACRIFICE", 19),
        ("RESCUE", 18),
        ("ABANDON", 17),
        ("REVENGE", 16),
        ("DECEPTION", 15),
        ("LOOT_STOLEN", 14),
        ("PROMISE_VIOLATED", 13),
        ("AID_REFUSED", 12),
        ("ALLIANCE", 11),
        ("PARTY_LEADER", 10),
        ("PARTY", 8),
        ("PROTECTED", 8),
        ("SHARED_RESOURCE", 6),
    )
    for event_type in _event_types(envelope):
        for marker, weight in weighted_markers:
            if marker in event_type and weight > score:
                score = weight
                reasons = [f"social:event:{marker.lower()}"]
                break
    return _clamp_component(score, "social_stakes"), reasons


def _character_significance_score(envelope: MediaEnvelope) -> tuple[int, list[str]]:
    best = 0
    best_actor: str | None = None
    for actor_id in sorted(envelope.participant_context):
        participant = envelope.participant_context[actor_id]
        stratum = int(participant.get("current_stratum") or 0)
        progression = participant.get("progression", {})
        level = int(progression.get("level", 1)) if isinstance(progression, dict) else 1
        encounters = int(participant.get("encounters_survived") or 0)
        kills = int(participant.get("kills") or 0)
        score = (
            min(5, max(0, stratum))
            + min(4, max(0, level - 1))
            + min(3, max(0, encounters))
            + min(3, max(0, kills))
        )
        score = _clamp_component(score, "character_significance")
        if score > best or (score == best and best_actor is not None and actor_id < best_actor):
            best = score
            best_actor = actor_id
    return best, ([f"character:canonical_history:{best_actor}"] if best > 0 and best_actor else [])


def _outcome_reversal_score(envelope: MediaEnvelope) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    weighted_markers = (
        ("COMEBACK", 10),
        ("NEAR_DEATH", 10),
        ("ESCAPE", 9),
        ("SURVIVED", 8),
        ("RESCUE", 8),
        ("RETREAT", 6),
        ("REVERSAL", 10),
        ("UNEXPECTED_DEFEAT", 9),
    )
    for event_type in _event_types(envelope):
        for marker, weight in weighted_markers:
            if marker in event_type and weight > score:
                score = weight
                reasons = [f"reversal:event:{marker.lower()}"]
    for fact in envelope.allowed_facts:
        if "outcome" not in fact.predicate.lower():
            continue
        value = str(fact.value).lower()
        if any(marker in value for marker in ("comeback", "escape", "survived")) and score < 8:
            score, reasons = 8, ["reversal:canonical_outcome"]
    return _clamp_component(score, "outcome_reversal"), reasons


def _continuity_score(envelope: MediaEnvelope) -> tuple[int, list[str]]:
    source_ids = set(envelope.source_event_ids)
    actor_ids = set(envelope.delver_ids)
    score = 0
    reasons: list[str] = []
    memories = envelope.social_context.get("memories", []) if isinstance(envelope.social_context, dict) else []
    if isinstance(memories, list):
        for memory in memories:
            if not isinstance(memory, dict):
                continue
            endpoints = {memory.get("observer_descender_id"), memory.get("subject_descender_id")}
            if not actor_ids.intersection(value for value in endpoints if isinstance(value, str)):
                continue
            memory_sources = set(value for value in memory.get("source_event_ids", []) if isinstance(value, str))
            reinforcement_count = int(memory.get("reinforcement_count") or len(memory_sources))
            if source_ids.intersection(memory_sources) and reinforcement_count >= 2:
                return 15, ["continuity:reinforced_memory_payoff"]
            if source_ids.intersection(memory_sources) and score < 10:
                score, reasons = 10, ["continuity:event_linked_memory"]
            elif reinforcement_count >= 2 and score < 7:
                score, reasons = 7, ["continuity:established_social_thread"]
    party_context = envelope.party_context if isinstance(envelope.party_context, dict) else {}
    types = _event_types(envelope)
    if any(_contains_any(item, ("PARTY", "ALLIANCE")) for item in types):
        if (party_context.get("parties") or party_context.get("alliances")) and score < 6:
            score, reasons = 6, ["continuity:party_alliance_context"]
    if len(types) > 1 and len(set(types)) < len(types) and score < 5:
        score, reasons = 5, ["continuity:repeated_event_thread"]
    return _clamp_component(score, "continuity"), reasons


def _visual_potential_score(envelope: MediaEnvelope) -> tuple[int, list[str]]:
    combat = envelope.combat_context if isinstance(envelope.combat_context, dict) else {}
    if combat.get("encounters"):
        return 5, ["visual:encounter_scene"]
    visual_markers = ("BOSS", "COMBAT", "DEATH", "RESCUE", "BETRAY", "RELIC", "SACRIFICE")
    if envelope.sector and envelope.delver_ids and any(
        _contains_any(event_type, visual_markers) for event_type in _event_types(envelope)
    ):
        return 5, ["visual:located_action"]
    if envelope.sector and envelope.delver_ids:
        return 4, ["visual:located_characters"]
    if envelope.delver_ids:
        return 2, ["visual:character_subject"]
    if envelope.sector:
        return 1, ["visual:location_only"]
    return 0, []


def score_envelope(envelope: MediaEnvelope) -> tuple[HighlightScore, tuple[str, ...]]:
    """Score one immutable envelope using only deterministic Python rules."""
    validate_media_envelope(envelope)
    components: dict[str, int] = {}
    reasons: list[str] = []
    scorers = (
        ("danger", _danger_score),
        ("rarity", _rarity_score),
        ("social_stakes", _social_stakes_score),
        ("character_significance", _character_significance_score),
        ("outcome_reversal", _outcome_reversal_score),
        ("continuity", _continuity_score),
        ("visual_potential", _visual_potential_score),
    )
    for name, scorer in scorers:
        value, codes = scorer(envelope)
        components[name] = value
        reasons.extend(codes)
    total = sum(components.values())
    return HighlightScore(**components, total=total), tuple(sorted(set(reasons)))


def tier_for_score(total: int, policy: HighlightPolicy | None = None) -> HighlightTier:
    effective = policy or HighlightPolicy()
    if total >= effective.cinematic_min:
        return HighlightTier.CINEMATIC
    if total >= effective.local_animation_min:
        return HighlightTier.LOCAL_ANIMATION
    if total >= effective.enhanced_stills_min:
        return HighlightTier.ENHANCED_STILLS
    if total >= effective.motion_story_min:
        return HighlightTier.MOTION_STORY
    if total >= effective.chronicle_min:
        return HighlightTier.CHRONICLE
    return HighlightTier.ARCHIVE_ONLY


_SOCIAL_MARKERS = (
    "BETRAY",
    "ABANDON",
    "REVENGE",
    "DECEPTION",
    "LOOT_STOLEN",
    "PROMISE_VIOLATED",
    "AID_REFUSED",
)
_PARTY_MARKERS = ("PARTY", "ALLIANCE")
_SURVIVAL_MARKERS = ("DEATH", "NEAR_DEATH", "RESCUE", "PROTECTED", "HEALED", "INJURY", "RETREAT", "SURVIV")
_COMBAT_MARKERS = ("COMBAT", "BOSS", "ELITE", "ATTACK", "DAMAGE", "KILL", "VICTORY")
_LOOT_MARKERS = ("LOOT", "RELIC", "CACHE", "ITEM", "EQUIP", "PROGRESSION", "LEVEL", "ABILITY")
_STRATUM_MARKERS = ("STRATUM", "FLOOR_COMPLETED", "FLOOR_ADVANCED", "ADVANCEMENT")


def _arc_specs(envelope: MediaEnvelope) -> tuple[tuple[StoryArcType, tuple[str, ...]], ...]:
    types = tuple(value for value in _event_types(envelope) if "INITIALIZED" not in value)
    actors = tuple(sorted(set(envelope.delver_ids)))
    specs: set[tuple[StoryArcType, tuple[str, ...]]] = set()
    if actors and any(_contains_any(event_type, _SOCIAL_MARKERS) for event_type in types):
        specs.add((StoryArcType.SOCIAL_CONFLICT, actors[:4]))
    if actors and any(_contains_any(event_type, _PARTY_MARKERS) for event_type in types):
        specs.add((StoryArcType.PARTY_ALLIANCE, actors[:8]))
    for actor_id in actors:
        subject = (actor_id,)
        if any(_contains_any(event_type, _SURVIVAL_MARKERS) for event_type in types):
            specs.add((StoryArcType.SURVIVAL, subject))
        if any(_contains_any(event_type, _COMBAT_MARKERS) for event_type in types):
            specs.add((StoryArcType.COMBAT, subject))
        if any(_contains_any(event_type, _LOOT_MARKERS) for event_type in types):
            specs.add((StoryArcType.LOOT_PROGRESSION, subject))
        if any(_contains_any(event_type, _STRATUM_MARKERS) for event_type in types):
            specs.add((StoryArcType.STRATUM_PROGRESSION, subject))
    return tuple(sorted(specs, key=lambda item: (item[0].value, item[1])))


def _terminal_arc(arc_type: StoryArcType, envelope: MediaEnvelope) -> bool:
    types = _event_types(envelope)
    if arc_type == StoryArcType.SURVIVAL:
        return any(_contains_any(value, ("DEATH", "ELIMINATED", "RETREATED")) and "NEAR_DEATH" not in value for value in types)
    if arc_type == StoryArcType.PARTY_ALLIANCE:
        return any(_contains_any(value, ("PARTY_DISBANDED", "ALLIANCE_DISSOLVED", "ALLIANCE_BETRAYAL")) for value in types)
    return False


def validate_story_arc(arc: MediaStoryArc) -> bool:
    if arc.protocol != PROTOCOL or arc.implementation_version != IMPLEMENTATION_VERSION or arc.phase != PHASE:
        raise HighlightStoryArcError("story arc protocol/version mismatch")
    if not arc.subject_ids or not arc.envelope_ids or not arc.source_event_ids:
        raise HighlightStoryArcError("story arc provenance is incomplete")
    if tuple(sorted(set(arc.subject_ids))) != arc.subject_ids:
        raise HighlightStoryArcError("story arc subject identity is not normalized")
    if tuple(sorted(set(arc.envelope_ids))) != arc.envelope_ids:
        raise HighlightStoryArcError("story arc envelope provenance is not normalized")
    if tuple(sorted(set(arc.source_event_ids))) != arc.source_event_ids:
        raise HighlightStoryArcError("story arc event provenance is not normalized")
    if arc.first_tick > arc.last_tick or arc.occurrence_count != len(arc.envelope_ids):
        raise HighlightStoryArcError("story arc timeline/count is invalid")
    expected_id = _stable_id("media_arc", arc.crawl_id, arc.arc_type.value, *arc.subject_ids)
    if arc.arc_id != expected_id:
        raise HighlightStoryArcError("story arc deterministic identity mismatch")
    if arc.digest != _body_digest(arc):
        raise HighlightStoryArcError("story arc digest mismatch")
    return True


def validate_highlight(highlight: MediaHighlight, policy: HighlightPolicy | None = None) -> bool:
    effective = policy or HighlightPolicy()
    if highlight.protocol != PROTOCOL or highlight.implementation_version != IMPLEMENTATION_VERSION or highlight.phase != PHASE:
        raise HighlightStoryArcError("highlight protocol/version mismatch")
    if highlight.output_tier == HighlightTier.ARCHIVE_ONLY or highlight.score.total < effective.chronicle_min:
        raise HighlightStoryArcError("archive-only evaluation cannot be persisted as MediaHighlight")
    if highlight.output_tier != tier_for_score(highlight.score.total, effective):
        raise HighlightStoryArcError("highlight output tier does not match deterministic score")
    expected_id = _stable_id("media_highlight", highlight.envelope_id, highlight.policy_digest)
    if highlight.highlight_id != expected_id:
        raise HighlightStoryArcError("highlight deterministic identity mismatch")
    if highlight.presentation_can_mutate_simulation or highlight.llm_decision_used or highlight.unreal_dependency or highlight.provider_invocation_used:
        raise HighlightStoryArcError("30.5.3 authority/dependency boundary changed")
    if highlight.digest != _body_digest(highlight):
        raise HighlightStoryArcError("highlight digest mismatch")
    return True


class HighlightStoryArcService:
    """Deterministic detector backed only by the non-authoritative media database."""

    def __init__(self, media: MediaPersistence, *, policy: HighlightPolicy | None = None) -> None:
        self.media = media
        self.policy = policy or HighlightPolicy()
        self._lock = RLock()

    def initialize(self) -> None:
        with self._lock:
            HighlightBase.metadata.create_all(self.media.engine)

    def _require_envelope(self, envelope: MediaEnvelope) -> None:
        validate_media_envelope(envelope)
        registered = self.media.get_envelope(envelope.envelope_id)
        if registered is None:
            raise HighlightStoryArcError("highlight analysis requires a registered MediaEnvelope")
        if registered.digest != envelope.digest or registered != envelope:
            raise HighlightStoryArcError("registered MediaEnvelope does not match analysis payload")

    def _upsert_arc(self, session: Session, envelope: MediaEnvelope, arc_type: StoryArcType, subject_ids: tuple[str, ...]) -> MediaStoryArc:
        normalized_subjects = tuple(sorted(set(subject_ids)))
        arc_id = _stable_id("media_arc", envelope.crawl_id, arc_type.value, *normalized_subjects)
        row = session.get(MediaStoryArcRow, arc_id)
        if row is None:
            body = {
                "protocol": PROTOCOL,
                "implementation_version": IMPLEMENTATION_VERSION,
                "phase": PHASE,
                "arc_id": arc_id,
                "crawl_id": envelope.crawl_id,
                "arc_type": arc_type.value,
                "subject_ids": list(normalized_subjects),
                "envelope_ids": [envelope.envelope_id],
                "source_event_ids": sorted(set(envelope.source_event_ids)),
                "first_tick": envelope.export_tick,
                "last_tick": envelope.export_tick,
                "occurrence_count": 1,
                "status": StoryArcStatus.CLOSED.value if _terminal_arc(arc_type, envelope) else StoryArcStatus.ACTIVE.value,
            }
            arc = MediaStoryArc.model_validate({**body, "digest": payload_digest(body)})
            validate_story_arc(arc)
            payload = arc.model_dump(mode="json")
            session.add(
                MediaStoryArcRow(
                    arc_id=arc.arc_id,
                    crawl_id=arc.crawl_id,
                    arc_type=arc.arc_type.value,
                    subject_key="|".join(arc.subject_ids),
                    first_tick=arc.first_tick,
                    last_tick=arc.last_tick,
                    status=arc.status.value,
                    payload=payload,
                    digest=arc.digest,
                )
            )
            return arc

        existing = MediaStoryArc.model_validate(row.payload)
        validate_story_arc(existing)
        envelope_ids = tuple(sorted(set(existing.envelope_ids) | {envelope.envelope_id}))
        source_event_ids = tuple(sorted(set(existing.source_event_ids) | set(envelope.source_event_ids)))
        status = StoryArcStatus.CLOSED if existing.status == StoryArcStatus.CLOSED or _terminal_arc(arc_type, envelope) else StoryArcStatus.ACTIVE
        body = {
            "protocol": PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "phase": PHASE,
            "arc_id": existing.arc_id,
            "crawl_id": existing.crawl_id,
            "arc_type": existing.arc_type.value,
            "subject_ids": list(existing.subject_ids),
            "envelope_ids": list(envelope_ids),
            "source_event_ids": list(source_event_ids),
            "first_tick": min(existing.first_tick, envelope.export_tick),
            "last_tick": max(existing.last_tick, envelope.export_tick),
            "occurrence_count": len(envelope_ids),
            "status": status.value,
        }
        arc = MediaStoryArc.model_validate({**body, "digest": payload_digest(body)})
        validate_story_arc(arc)
        row.first_tick = arc.first_tick
        row.last_tick = arc.last_tick
        row.status = arc.status.value
        row.payload = arc.model_dump(mode="json")
        row.digest = arc.digest
        return arc

    def evaluate(self, envelope: MediaEnvelope) -> HighlightEvaluation:
        self._require_envelope(envelope)
        score, reason_codes = score_envelope(envelope)
        tier = tier_for_score(score.total, self.policy)
        with self._lock:
            with Session(self.media.engine) as session:
                arcs = [self._upsert_arc(session, envelope, arc_type, subjects) for arc_type, subjects in _arc_specs(envelope)]
                arc_ids = tuple(sorted(arc.arc_id for arc in arcs))
                selected = score.total >= self.policy.chronicle_min
                highlight_id: str | None = None
                if selected:
                    highlight_id = _stable_id("media_highlight", envelope.envelope_id, self.policy.digest)
                    body = {
                        "protocol": PROTOCOL,
                        "implementation_version": IMPLEMENTATION_VERSION,
                        "phase": PHASE,
                        "highlight_id": highlight_id,
                        "envelope_id": envelope.envelope_id,
                        "crawl_id": envelope.crawl_id,
                        "source_event_ids": list(envelope.source_event_ids),
                        "delver_ids": list(envelope.delver_ids),
                        "score": score.model_dump(mode="json"),
                        "output_tier": tier.value,
                        "reason_codes": list(reason_codes),
                        "arc_ids": list(arc_ids),
                        "policy_digest": self.policy.digest,
                        "presentation_can_mutate_simulation": False,
                        "llm_decision_used": False,
                        "unreal_dependency": False,
                        "provider_invocation_used": False,
                    }
                    highlight = MediaHighlight.model_validate({**body, "digest": payload_digest(body)})
                    validate_highlight(highlight, self.policy)
                    row = session.get(MediaHighlightRow, highlight_id)
                    payload = highlight.model_dump(mode="json")
                    if row is None:
                        session.add(
                            MediaHighlightRow(
                                highlight_id=highlight.highlight_id,
                                envelope_id=highlight.envelope_id,
                                crawl_id=highlight.crawl_id,
                                policy_digest=highlight.policy_digest,
                                total_score=highlight.score.total,
                                output_tier=highlight.output_tier.value,
                                payload=payload,
                                digest=highlight.digest,
                            )
                        )
                    elif row.digest != highlight.digest or row.payload != payload:
                        raise HighlightStoryArcError("highlight identity resolved to different deterministic payload")
                session.commit()

        eval_body = {
            "envelope_id": envelope.envelope_id,
            "selected": selected,
            "score": score.model_dump(mode="json"),
            "output_tier": tier.value,
            "reason_codes": list(reason_codes),
            "arc_ids": list(arc_ids),
            "highlight_id": highlight_id,
            "policy_digest": self.policy.digest,
        }
        return HighlightEvaluation.model_validate({**eval_body, "digest": payload_digest(eval_body)})

    def evaluate_many(self, envelopes: Iterable[MediaEnvelope]) -> tuple[HighlightEvaluation, ...]:
        ordered = sorted(envelopes, key=lambda item: (item.export_tick, item.envelope_id))
        return tuple(self.evaluate(envelope) for envelope in ordered)

    def get_highlight(self, highlight_id: str) -> MediaHighlight | None:
        with self._lock:
            with Session(self.media.engine) as session:
                row = session.get(MediaHighlightRow, highlight_id)
                if row is None:
                    return None
                highlight = MediaHighlight.model_validate(row.payload)
                validate_highlight(highlight, self.policy)
                return highlight

    def list_highlights(self, *, crawl_id: str | None = None) -> tuple[MediaHighlight, ...]:
        with self._lock:
            with Session(self.media.engine) as session:
                statement = select(MediaHighlightRow)
                if crawl_id is not None:
                    statement = statement.where(MediaHighlightRow.crawl_id == crawl_id)
                rows = session.scalars(statement.order_by(MediaHighlightRow.highlight_id)).all()
                values = tuple(MediaHighlight.model_validate(row.payload) for row in rows)
                for value in values:
                    validate_highlight(value, self.policy)
                return values

    def list_story_arcs(self, *, crawl_id: str | None = None) -> tuple[MediaStoryArc, ...]:
        with self._lock:
            with Session(self.media.engine) as session:
                statement = select(MediaStoryArcRow)
                if crawl_id is not None:
                    statement = statement.where(MediaStoryArcRow.crawl_id == crawl_id)
                rows = session.scalars(statement.order_by(MediaStoryArcRow.arc_id)).all()
                values = tuple(MediaStoryArc.model_validate(row.payload) for row in rows)
                for value in values:
                    validate_story_arc(value)
                return values

    def snapshot(self) -> dict[str, Any]:
        highlights = [item.model_dump(mode="json") for item in self.list_highlights()]
        arcs = [item.model_dump(mode="json") for item in self.list_story_arcs()]
        body = {
            "protocol": PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "phase": PHASE,
            "authoritative": False,
            "canonical_owner": "deterministic_simulation",
            "presentation_can_mutate_simulation": False,
            "llm_decision_used": False,
            "unreal_dependency": False,
            "provider_invocation_used": False,
            "policy": self.policy.model_dump(mode="json"),
            "policy_digest": self.policy.digest,
            "highlights": highlights,
            "highlight_count": len(highlights),
            "highlight_digest": payload_digest(highlights),
            "story_arcs": arcs,
            "story_arc_count": len(arcs),
            "story_arc_digest": payload_digest(arcs),
        }
        return {**body, "digest": payload_digest(body)}


__all__ = [
    "PROTOCOL",
    "IMPLEMENTATION_VERSION",
    "PHASE",
    "SCORE_MAXIMA",
    "HighlightTier",
    "StoryArcType",
    "StoryArcStatus",
    "HighlightPolicy",
    "HighlightScore",
    "MediaStoryArc",
    "MediaHighlight",
    "HighlightEvaluation",
    "HighlightStoryArcError",
    "HighlightStoryArcService",
    "score_envelope",
    "tier_for_score",
    "validate_story_arc",
    "validate_highlight",
]
