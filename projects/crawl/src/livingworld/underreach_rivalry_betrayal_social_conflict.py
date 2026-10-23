"""Deterministic rivalry, betrayal, and social conflict for Underreach Slice 30C.5.

30C.1 owns directed relationship truth, 30C.2 owns event-linked social memory,
30C.3 owns bounded social interactions, and 30C.4 owns persistent parties and
alliances. 30C.5 adds deterministic hostile social decisions whose eligibility
must be justified by accumulated canonical social state plus an explicit
bounded incentive. There is no random betrayal roll.

Conflict proposals are advisory. The simulation validates them against a fresh
observation and owns every mutation. Dialogue and autonomous multi-character
social orchestration remain later responsibilities.
"""
from __future__ import annotations

from hashlib import sha256
import math
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .crawl_domain import CrawlEvent, CrawlStatus, ParticipationStatus
from .crawl_persistence import CrawlPersistence
from .crawl_service import CrawlLifecycleService
from .item_system import transfer_item_to_crawler
from .runtime_checkpoint import payload_digest
from .underreach_domain import Descent
from .underreach_parties_alliances_leadership import (
    METADATA_KEY as PARTY_METADATA_KEY,
    PartiesAlliancesLeadershipService,
    build_parties_alliances_snapshot,
    validate_parties_alliances_leadership,
)
from .underreach_social_memory_evolution import (
    SocialMemoryEvolutionService,
    build_social_memory_snapshot,
)
from .underreach_social_state import build_social_state_snapshot, get_relationship


PROTOCOL = "underreach.rivalry-betrayal-social-conflict.v1"
IMPLEMENTATION_VERSION = "30c5.1"
OBSERVATION_PROTOCOL = "underreach.social-conflict-observation.v1"
INTENT_PROTOCOL = "underreach.social-conflict-intent.v1"
DECISION_PROTOCOL = "underreach.social-conflict-decision.v1"
RESULT_PROTOCOL = "underreach.social-conflict-result.v1"
METADATA_KEY = "_rivalry_betrayal_social_conflict"

INITIALIZED_EVENT = "SOCIAL_CONFLICT_SYSTEM_INITIALIZED"
EXECUTED_EVENT = "SOCIAL_CONFLICT_EXECUTED"
DECEPTION_CREATED_EVENT = "DECEPTION_CREATED"
REVENGE_STARTED_EVENT = "REVENGE_SEEKING_STARTED"
ALLIANCE_BETRAYAL_EVENT = "ALLIANCE_BETRAYAL"

ALLOWED_ACTIONS = (
    "refuse_aid",
    "steal_loot",
    "deceive",
    "expose_deception",
    "abandon_party",
    "betray_party",
    "break_alliance",
    "seek_revenge",
)
INCENTIVE_CODES = (
    "escape",
    "leadership",
    "loot",
    "resource_scarcity",
    "revenge",
    "safety",
    "survival",
)
DECEPTION_CLAIMS = (
    "alliance_commitment",
    "danger_level",
    "exit_route",
    "intent_to_share",
    "loot_location",
    "resource_need",
)
ACTION_THRESHOLDS = {
    "refuse_aid": 0.24,
    "steal_loot": 0.38,
    "deceive": 0.33,
    "abandon_party": 0.44,
    "betray_party": 0.58,
    "break_alliance": 0.52,
    "seek_revenge": 0.50,
}
HIGH_IMPACT_ACTIONS = {"betray_party", "break_alliance"}
MIN_HIGH_IMPACT_INCENTIVE = 0.35
VALUE_PRECISION = 6

NEGATIVE_MEMORY_WEIGHTS = {
    "abandoned": 0.26,
    "betrayed": 0.42,
    "caused_injury": 0.20,
    "refused_aid": 0.13,
    "stole_loot": 0.28,
    "violated_promise": 0.24,
    "witnessed_selfishness": 0.10,
}
POSITIVE_MEMORY_WEIGHTS = {
    "fought_beside": 0.07,
    "healed": 0.16,
    "kept_promise": 0.15,
    "protected": 0.19,
    "rescued": 0.28,
    "shared_resource": 0.13,
}
_MAJOR_NEGATIVE_MEMORIES = {"betrayed", "stole_loot", "violated_promise"}
_CODE = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,79}$")


class RivalryBetrayalSocialConflictError(ValueError):
    """Raised when 30C.5 conflict authority or eligibility is violated."""


class ConflictObservation(BaseModel):
    model_config = ConfigDict(frozen=True)

    protocol: str = OBSERVATION_PROTOCOL
    implementation_version: str = IMPLEMENTATION_VERSION
    descender_id: str
    target_descender_id: str
    current_tick: int
    current_stratum_number: int
    source_sector_id: str | None
    target_sector_id: str | None
    source_party_id: str | None
    target_party_id: str | None
    colocated: bool
    trust: float
    respect: float
    affection: float
    fear: float
    resentment: float
    gratitude: float
    rivalry: float
    familiarity: float
    negative_memory_count: int
    major_negative_memory_count: int
    negative_memory_pressure: float
    positive_memory_pressure: float
    negative_basis_event_ids: tuple[str, ...]
    relationship_pressure: float
    bond_resistance: float
    base_grievance: float
    social_state_digest: str
    memory_state_digest: str
    party_state_digest: str
    canonical_state_digest: str
    observation_digest: str


class ConflictIntent(BaseModel):
    model_config = ConfigDict(frozen=True)

    protocol: str = INTENT_PROTOCOL
    implementation_version: str = IMPLEMENTATION_VERSION
    proposal_id: str
    provider_id: str
    descender_id: str
    target_descender_id: str
    observation_digest: str
    action: str
    incentive_code: str
    incentive_strength: float = Field(ge=0.0, le=1.0)
    target_item_id: str | None = None
    alliance_id: str | None = None
    deception_id: str | None = None
    claim_code: str | None = None


class ConflictDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    protocol: str = DECISION_PROTOCOL
    implementation_version: str = IMPLEMENTATION_VERSION
    proposal_id: str
    descender_id: str
    target_descender_id: str
    action: str
    accepted: bool
    reason_code: str
    threshold: float
    conflict_score: float
    incentive_strength: float
    negative_memory_count: int
    major_negative_memory_count: int
    basis_event_ids: tuple[str, ...]
    canonical_state_digest: str
    decision_digest: str


class ConflictExecutionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    protocol: str = RESULT_PROTOCOL
    implementation_version: str = IMPLEMENTATION_VERSION
    proposal_id: str
    action: str
    accepted: bool
    executed: bool
    reason_code: str
    descender_id: str
    target_descender_id: str
    conflict_score: float
    source_event_id: str | None = None
    execution_event_id: str | None = None
    memory_event_ids: tuple[str, ...] = ()
    relationship_event_ids: tuple[str, ...] = ()
    affected_party_id: str | None = None
    affected_alliance_id: str | None = None
    affected_item_id: str | None = None
    deception_id: str | None = None
    revenge_id: str | None = None
    canonical_state_digest_before: str
    canonical_state_digest_after: str
    result_digest: str


def _stable_id(prefix: str, *parts: object) -> str:
    payload = ":".join("" if part is None else str(part) for part in parts)
    return f"{prefix}_{sha256(payload.encode('utf-8')).hexdigest()[:20]}"


def _rounded(value: float) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise RivalryBetrayalSocialConflictError("conflict numeric value must be finite")
    return round(number, VALUE_PRECISION)


def _unit(value: float) -> float:
    return _rounded(max(0.0, min(1.0, float(value))))


def _canonical_state_digest(descent: Descent) -> str:
    return payload_digest(descent.model_dump(mode="json"))


def _metadata(descent: Descent) -> dict[str, Any]:
    value = descent.modifiers.get(METADATA_KEY)
    if not isinstance(value, dict):
        raise RivalryBetrayalSocialConflictError("Descent is missing 30C.5 social-conflict metadata")
    return value


def _party_metadata(descent: Descent) -> dict[str, Any]:
    value = descent.modifiers.get(PARTY_METADATA_KEY)
    if not isinstance(value, dict):
        raise RivalryBetrayalSocialConflictError("30C.5 requires accepted 30C.4 party metadata")
    return value


def _record_body(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key != "digest"}


def _active_current(descent: Descent, npc_id: str) -> bool:
    participant = descent.participants.get(npc_id)
    return bool(
        participant is not None
        and participant.status == ParticipationStatus.ACTIVE
        and participant.current_floor == descent.current_floor
    )


def _same_sector(descent: Descent, left: str, right: str) -> bool:
    if not _active_current(descent, left) or not _active_current(descent, right):
        return False
    left_sector = descent.participants[left].current_location_id
    return left_sector is not None and left_sector == descent.participants[right].current_location_id


def _validate_provider(provider_id: str) -> str:
    if not isinstance(provider_id, str) or not _CODE.fullmatch(provider_id):
        raise RivalryBetrayalSocialConflictError("conflict provider_id must be a bounded structured identifier")
    return provider_id


def _validate_intent_shape(intent: ConflictIntent) -> bool:
    if intent.protocol != INTENT_PROTOCOL or intent.implementation_version != IMPLEMENTATION_VERSION:
        raise RivalryBetrayalSocialConflictError("conflict intent protocol/version mismatch")
    _validate_provider(intent.provider_id)
    if intent.action not in ALLOWED_ACTIONS:
        raise RivalryBetrayalSocialConflictError("conflict intent escaped bounded action vocabulary")
    if intent.incentive_code not in INCENTIVE_CODES:
        raise RivalryBetrayalSocialConflictError("conflict incentive escaped bounded vocabulary")
    if intent.descender_id == intent.target_descender_id:
        raise RivalryBetrayalSocialConflictError("self-directed conflict is invalid")
    if intent.action == "steal_loot":
        if not intent.target_item_id or any(value is not None for value in (intent.alliance_id, intent.deception_id, intent.claim_code)):
            raise RivalryBetrayalSocialConflictError("steal_loot intent shape is invalid")
    elif intent.action == "break_alliance":
        if not intent.alliance_id or any(value is not None for value in (intent.target_item_id, intent.deception_id, intent.claim_code)):
            raise RivalryBetrayalSocialConflictError("break_alliance intent shape is invalid")
    elif intent.action == "deceive":
        if not intent.claim_code or intent.claim_code not in DECEPTION_CLAIMS:
            raise RivalryBetrayalSocialConflictError("deception claim escaped bounded vocabulary")
        if any(value is not None for value in (intent.target_item_id, intent.alliance_id, intent.deception_id)):
            raise RivalryBetrayalSocialConflictError("deceive intent shape is invalid")
    elif intent.action == "expose_deception":
        if not intent.deception_id or any(value is not None for value in (intent.target_item_id, intent.alliance_id, intent.claim_code)):
            raise RivalryBetrayalSocialConflictError("expose_deception intent shape is invalid")
    elif any(value is not None for value in (intent.target_item_id, intent.alliance_id, intent.deception_id, intent.claim_code)):
        raise RivalryBetrayalSocialConflictError("conflict intent contains fields forbidden for its action")
    return True


def _negative_memory_summary(descent: Descent, observer_id: str, subject_id: str) -> tuple[int, int, float, float, tuple[str, ...]]:
    memory_service = SocialMemoryEvolutionService()
    memories = [memory for memory in memory_service.memories_for(descent, observer_id) if memory.subject_descender_id == subject_id]
    negative_count = 0
    major_count = 0
    negative_pressure = 0.0
    positive_pressure = 0.0
    basis: set[str] = set()
    for memory in memories:
        if memory.memory_type in NEGATIVE_MEMORY_WEIGHTS:
            negative_count += 1
            if memory.memory_type in _MAJOR_NEGATIVE_MEMORIES:
                major_count += 1
            weight = NEGATIVE_MEMORY_WEIGHTS[memory.memory_type]
            negative_pressure += weight * float(memory.importance) * float(memory.confidence)
            basis.update(memory.source_event_ids)
        elif memory.memory_type in POSITIVE_MEMORY_WEIGHTS:
            weight = POSITIVE_MEMORY_WEIGHTS[memory.memory_type]
            positive_pressure += weight * float(memory.importance) * float(memory.confidence)
    return (
        negative_count,
        major_count,
        _unit(negative_pressure),
        _unit(positive_pressure),
        tuple(sorted(basis)),
    )


def build_conflict_observation(descent: Descent, descender_id: str, target_descender_id: str) -> ConflictObservation:
    validate_rivalry_betrayal_social_conflict(descent)
    if descender_id not in descent.participants or target_descender_id not in descent.participants:
        raise RivalryBetrayalSocialConflictError("conflict observation endpoints must be participating Descenders")
    if descender_id == target_descender_id:
        raise RivalryBetrayalSocialConflictError("conflict observation cannot target self")
    relationship = get_relationship(descent, descender_id, target_descender_id)
    negative_count, major_count, negative_memory, positive_memory, basis = _negative_memory_summary(
        descent, descender_id, target_descender_id
    )
    relationship_pressure = _unit(
        max(0.0, relationship.resentment) * 0.25
        + max(0.0, relationship.rivalry) * 0.20
        + max(0.0, -relationship.trust) * 0.18
        + max(0.0, -relationship.respect) * 0.08
        + max(0.0, relationship.fear) * 0.08
        + max(0.0, -relationship.affection) * 0.06
    )
    bond = _unit(
        max(0.0, relationship.trust) * 0.22
        + max(0.0, relationship.respect) * 0.16
        + max(0.0, relationship.affection) * 0.18
        + max(0.0, relationship.gratitude) * 0.14
        + positive_memory * 0.20
    )
    base_grievance = _unit(relationship_pressure + negative_memory * 0.42)
    social_snapshot = build_social_state_snapshot(descent)
    memory_snapshot = build_social_memory_snapshot(descent)
    party_snapshot = build_parties_alliances_snapshot(descent)
    source = descent.participants[descender_id]
    target = descent.participants[target_descender_id]
    canonical_digest = _canonical_state_digest(descent)
    body = {
        "protocol": OBSERVATION_PROTOCOL,
        "implementation_version": IMPLEMENTATION_VERSION,
        "descender_id": descender_id,
        "target_descender_id": target_descender_id,
        "current_tick": descent.current_tick,
        "current_stratum_number": descent.current_floor,
        "source_sector_id": source.current_location_id,
        "target_sector_id": target.current_location_id,
        "source_party_id": source.current_party_id,
        "target_party_id": target.current_party_id,
        "colocated": _same_sector(descent, descender_id, target_descender_id),
        "trust": relationship.trust,
        "respect": relationship.respect,
        "affection": relationship.affection,
        "fear": relationship.fear,
        "resentment": relationship.resentment,
        "gratitude": relationship.gratitude,
        "rivalry": relationship.rivalry,
        "familiarity": relationship.familiarity,
        "negative_memory_count": negative_count,
        "major_negative_memory_count": major_count,
        "negative_memory_pressure": negative_memory,
        "positive_memory_pressure": positive_memory,
        "negative_basis_event_ids": basis,
        "relationship_pressure": relationship_pressure,
        "bond_resistance": bond,
        "base_grievance": base_grievance,
        "social_state_digest": social_snapshot["relationship_state_digest"],
        "memory_state_digest": memory_snapshot["memory_state_digest"],
        "party_state_digest": party_snapshot["party_digest"],
        "canonical_state_digest": canonical_digest,
    }
    return ConflictObservation(**body, observation_digest=payload_digest(body))


def _intent_body(
    *,
    provider_id: str,
    descender_id: str,
    target_descender_id: str,
    observation_digest: str,
    action: str,
    incentive_code: str,
    incentive_strength: float,
    target_item_id: str | None,
    alliance_id: str | None,
    deception_id: str | None,
    claim_code: str | None,
) -> dict[str, Any]:
    return {
        "provider_id": provider_id,
        "descender_id": descender_id,
        "target_descender_id": target_descender_id,
        "observation_digest": observation_digest,
        "action": action,
        "incentive_code": incentive_code,
        "incentive_strength": _unit(incentive_strength),
        "target_item_id": target_item_id,
        "alliance_id": alliance_id,
        "deception_id": deception_id,
        "claim_code": claim_code,
    }


def propose_conflict_intent(
    descent: Descent,
    descender_id: str,
    target_descender_id: str,
    action: str,
    *,
    incentive_code: str,
    incentive_strength: float,
    provider_id: str = "bounded-conflict-proposer-v1",
    target_item_id: str | None = None,
    alliance_id: str | None = None,
    deception_id: str | None = None,
    claim_code: str | None = None,
) -> ConflictIntent:
    before = _canonical_state_digest(descent)
    history = tuple(descent.history_event_ids)
    observation = build_conflict_observation(descent, descender_id, target_descender_id)
    body = _intent_body(
        provider_id=_validate_provider(provider_id),
        descender_id=descender_id,
        target_descender_id=target_descender_id,
        observation_digest=observation.observation_digest,
        action=str(action),
        incentive_code=str(incentive_code),
        incentive_strength=incentive_strength,
        target_item_id=target_item_id,
        alliance_id=alliance_id,
        deception_id=deception_id,
        claim_code=claim_code,
    )
    intent = ConflictIntent(
        proposal_id=_stable_id("conflict_proposal", *(body[key] for key in body)),
        **body,
    )
    _validate_intent_shape(intent)
    if _canonical_state_digest(descent) != before or tuple(descent.history_event_ids) != history:
        raise RivalryBetrayalSocialConflictError("conflict proposal mutated canonical state")
    return intent


def _conflict_score(observation: ConflictObservation, incentive_strength: float) -> float:
    return _unit(
        observation.base_grievance
        + _unit(incentive_strength) * 0.40
        - observation.bond_resistance * 0.25
    )


def _find_alliance(descent: Descent, alliance_id: str) -> dict[str, Any] | None:
    value = _party_metadata(descent)["alliances"].get(alliance_id)
    return value if isinstance(value, dict) else None


def _semantic_rejection(descent: Descent, observation: ConflictObservation, intent: ConflictIntent, score: float) -> str | None:
    if descent.status != CrawlStatus.RUNNING:
        return "descent_not_running"
    if not _active_current(descent, intent.descender_id):
        return "source_not_active_current_stratum"
    if not _active_current(descent, intent.target_descender_id):
        return "target_not_active_current_stratum"

    if intent.action == "expose_deception":
        record = _metadata(descent)["deceptions"].get(intent.deception_id or "")
        if not isinstance(record, dict):
            return "deception_missing"
        if record["status"] != "concealed":
            return "deception_not_concealed"
        if record["target_descender_id"] != intent.descender_id or record["source_descender_id"] != intent.target_descender_id:
            return "deception_endpoint_mismatch"
        return None

    threshold = ACTION_THRESHOLDS[intent.action]
    if score < threshold:
        return "insufficient_accumulated_conflict"
    if intent.action in HIGH_IMPACT_ACTIONS:
        if intent.incentive_strength < MIN_HIGH_IMPACT_INCENTIVE:
            return "high_impact_incentive_too_weak"
        if observation.major_negative_memory_count < 1 and observation.negative_memory_count < 2:
            return "high_impact_negative_evidence_required"

    if intent.action in {"refuse_aid", "steal_loot", "deceive"} and not observation.colocated:
        return "target_not_colocated"
    if intent.action == "steal_loot":
        item = descent.items.get(intent.target_item_id or "")
        if item is None:
            return "loot_item_missing"
        if item.owner_npc_id != intent.target_descender_id:
            return "loot_item_not_owned_by_target"
    elif intent.action in {"abandon_party", "betray_party"}:
        party_id = descent.participants[intent.descender_id].current_party_id
        if party_id is None or party_id != descent.participants[intent.target_descender_id].current_party_id:
            return "shared_active_party_required"
        party = descent.parties.get(party_id)
        if party is None or not party.active:
            return "shared_active_party_required"
    elif intent.action == "break_alliance":
        source_party_id = descent.participants[intent.descender_id].current_party_id
        target_party_id = descent.participants[intent.target_descender_id].current_party_id
        if source_party_id is None or target_party_id is None or source_party_id == target_party_id:
            return "distinct_party_membership_required"
        source_party = descent.parties[source_party_id]
        target_party = descent.parties[target_party_id]
        if source_party.leader_npc_id != intent.descender_id or target_party.leader_npc_id != intent.target_descender_id:
            return "alliance_break_requires_party_leaders"
        alliance = _find_alliance(descent, intent.alliance_id or "")
        if not isinstance(alliance, dict) or alliance.get("status") != "active":
            return "active_alliance_required"
        if sorted(alliance["party_ids"]) != sorted([source_party_id, target_party_id]):
            return "alliance_endpoint_mismatch"
    elif intent.action == "seek_revenge":
        existing = [
            record for record in _metadata(descent)["revenge_records"].values()
            if record["status"] == "active"
            and record["source_descender_id"] == intent.descender_id
            and record["target_descender_id"] == intent.target_descender_id
        ]
        if existing:
            return "revenge_already_active"
    return None


def validate_conflict_intent(descent: Descent, intent: ConflictIntent) -> ConflictDecision:
    validate_rivalry_betrayal_social_conflict(descent)
    before = _canonical_state_digest(descent)
    history = tuple(descent.history_event_ids)
    try:
        _validate_intent_shape(intent)
        observation = build_conflict_observation(descent, intent.descender_id, intent.target_descender_id)
    except (RivalryBetrayalSocialConflictError, KeyError):
        body = {
            "protocol": DECISION_PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "proposal_id": intent.proposal_id,
            "descender_id": intent.descender_id,
            "target_descender_id": intent.target_descender_id,
            "action": intent.action,
            "accepted": False,
            "reason_code": "conflict_intent_contract_rejected",
            "threshold": ACTION_THRESHOLDS.get(intent.action, 1.0),
            "conflict_score": 0.0,
            "incentive_strength": _unit(intent.incentive_strength),
            "negative_memory_count": 0,
            "major_negative_memory_count": 0,
            "basis_event_ids": (),
            "canonical_state_digest": before,
        }
        return ConflictDecision(**body, decision_digest=payload_digest(body))

    if intent.observation_digest != observation.observation_digest:
        rejection = "stale_observation"
    else:
        score = _conflict_score(observation, intent.incentive_strength)
        rejection = _semantic_rejection(descent, observation, intent, score)
    score = _conflict_score(observation, intent.incentive_strength)
    threshold = 0.0 if intent.action == "expose_deception" else ACTION_THRESHOLDS[intent.action]
    body = {
        "protocol": DECISION_PROTOCOL,
        "implementation_version": IMPLEMENTATION_VERSION,
        "proposal_id": intent.proposal_id,
        "descender_id": intent.descender_id,
        "target_descender_id": intent.target_descender_id,
        "action": intent.action,
        "accepted": rejection is None,
        "reason_code": "accepted" if rejection is None else rejection,
        "threshold": threshold,
        "conflict_score": score,
        "incentive_strength": _unit(intent.incentive_strength),
        "negative_memory_count": observation.negative_memory_count,
        "major_negative_memory_count": observation.major_negative_memory_count,
        "basis_event_ids": observation.negative_basis_event_ids,
        "canonical_state_digest": before,
    }
    decision = ConflictDecision(**body, decision_digest=payload_digest(body))
    if _canonical_state_digest(descent) != before or tuple(descent.history_event_ids) != history:
        raise RivalryBetrayalSocialConflictError("conflict validation mutated canonical state")
    return decision


def _memory_result(service: SocialMemoryEvolutionService, descent: Descent, event: CrawlEvent) -> tuple[tuple[str, ...], tuple[str, ...]]:
    result = service.process_event(descent, event)
    return tuple(result.memory_event_ids), tuple(result.relationship_event_ids)


def validate_rivalry_betrayal_social_conflict(descent: Descent) -> bool:
    validate_parties_alliances_leadership(descent)
    metadata = _metadata(descent)
    if metadata.get("protocol") != PROTOCOL or metadata.get("implementation_version") != IMPLEMENTATION_VERSION:
        raise RivalryBetrayalSocialConflictError("30C.5 protocol/version mismatch")
    if metadata.get("authoritative") is not True or metadata.get("canonical_owner") != "deterministic_simulation":
        raise RivalryBetrayalSocialConflictError("30C.5 authority boundary changed")
    if metadata.get("extends_slice") != "30C.4":
        raise RivalryBetrayalSocialConflictError("30C.5 source-slice boundary changed")
    if metadata.get("random_betrayal_allowed") is not False:
        raise RivalryBetrayalSocialConflictError("random betrayal must remain forbidden")
    if metadata.get("presentation_feedback_allowed") is not False:
        raise RivalryBetrayalSocialConflictError("presentation cannot mutate social conflict truth")
    if metadata.get("allowed_actions") != list(ALLOWED_ACTIONS):
        raise RivalryBetrayalSocialConflictError("30C.5 bounded conflict action vocabulary changed")
    if metadata.get("initialized_event_id") not in descent.history_event_ids:
        raise RivalryBetrayalSocialConflictError("30C.5 initialization is not Ledger bound")

    history = set(descent.history_event_ids)
    records = metadata.get("conflict_records")
    if not isinstance(records, list):
        raise RivalryBetrayalSocialConflictError("conflict trace is invalid")
    for index, record in enumerate(records):
        if record.get("index") != index or record.get("digest") != payload_digest(_record_body(record)):
            raise RivalryBetrayalSocialConflictError("conflict trace index/digest mismatch")
        if record.get("action") not in ALLOWED_ACTIONS:
            raise RivalryBetrayalSocialConflictError("conflict trace escaped bounded action vocabulary")
        if record.get("source_event_id") not in history or record.get("execution_event_id") not in history:
            raise RivalryBetrayalSocialConflictError("conflict trace lacks Ledger provenance")
        if record.get("action") in HIGH_IMPACT_ACTIONS:
            if float(record.get("incentive_strength", 0.0)) < MIN_HIGH_IMPACT_INCENTIVE:
                raise RivalryBetrayalSocialConflictError("high-impact conflict trace lacks sufficient incentive")
            if not record.get("basis_event_ids"):
                raise RivalryBetrayalSocialConflictError("high-impact conflict trace lacks accumulated negative evidence")

    deceptions = metadata.get("deceptions")
    if not isinstance(deceptions, dict):
        raise RivalryBetrayalSocialConflictError("deception storage is invalid")
    for deception_id, record in deceptions.items():
        if record.get("deception_id") != deception_id or record.get("status") not in {"concealed", "exposed"}:
            raise RivalryBetrayalSocialConflictError("deception identity/status is invalid")
        if record.get("claim_code") not in DECEPTION_CLAIMS:
            raise RivalryBetrayalSocialConflictError("deception claim escaped bounded vocabulary")
        if record.get("created_event_id") not in history:
            raise RivalryBetrayalSocialConflictError("deception creation lacks Ledger provenance")
        if record["status"] == "exposed" and record.get("exposed_event_id") not in history:
            raise RivalryBetrayalSocialConflictError("exposed deception lacks Ledger provenance")
        if record.get("digest") != payload_digest(_record_body(record)):
            raise RivalryBetrayalSocialConflictError("deception digest mismatch")

    revenge = metadata.get("revenge_records")
    if not isinstance(revenge, dict):
        raise RivalryBetrayalSocialConflictError("revenge storage is invalid")
    for revenge_id, record in revenge.items():
        if record.get("revenge_id") != revenge_id or record.get("status") != "active":
            raise RivalryBetrayalSocialConflictError("30C.5 revenge record status is invalid")
        if record.get("started_event_id") not in history or not record.get("basis_event_ids"):
            raise RivalryBetrayalSocialConflictError("revenge state lacks canonical grievance provenance")
        if record.get("digest") != payload_digest(_record_body(record)):
            raise RivalryBetrayalSocialConflictError("revenge record digest mismatch")

    hostile_breaks = metadata.get("hostile_alliance_breaks")
    if not isinstance(hostile_breaks, dict):
        raise RivalryBetrayalSocialConflictError("hostile alliance-break archive is invalid")
    for alliance_id, record in hostile_breaks.items():
        if record.get("alliance_id") != alliance_id or record.get("break_event_id") not in history:
            raise RivalryBetrayalSocialConflictError("hostile alliance break lacks canonical provenance")
        if alliance_id in _party_metadata(descent)["alliances"]:
            raise RivalryBetrayalSocialConflictError("hostile-broken alliance remained active in 30C.4 registry")
        if record.get("digest") != payload_digest(_record_body(record)):
            raise RivalryBetrayalSocialConflictError("hostile alliance-break digest mismatch")
    return True


def build_rivalry_betrayal_social_conflict_snapshot(descent: Descent) -> dict[str, Any]:
    validate_rivalry_betrayal_social_conflict(descent)
    metadata = _metadata(descent)
    records = [dict(record) for record in metadata["conflict_records"]]
    deceptions = [dict(metadata["deceptions"][key]) for key in sorted(metadata["deceptions"])]
    revenge = [dict(metadata["revenge_records"][key]) for key in sorted(metadata["revenge_records"])]
    hostile_breaks = [dict(metadata["hostile_alliance_breaks"][key]) for key in sorted(metadata["hostile_alliance_breaks"])]
    body = {
        "protocol": PROTOCOL,
        "implementation_version": IMPLEMENTATION_VERSION,
        "authoritative": True,
        "canonical_owner": "deterministic_simulation",
        "random_betrayal_allowed": False,
        "presentation_feedback_allowed": False,
        "descent_id": descent.id,
        "current_tick": descent.current_tick,
        "current_stratum_number": descent.current_floor,
        "execution_count": len(records),
        "conflict_records": records,
        "conflict_trace_digest": payload_digest(records),
        "deceptions": deceptions,
        "deception_digest": payload_digest(deceptions),
        "active_revenge_records": revenge,
        "revenge_digest": payload_digest(revenge),
        "hostile_alliance_breaks": hostile_breaks,
        "hostile_alliance_break_digest": payload_digest(hostile_breaks),
        "relationship_state_digest": build_social_state_snapshot(descent)["relationship_state_digest"],
        "social_memory_snapshot_digest": build_social_memory_snapshot(descent)["digest"],
        "party_snapshot_digest": build_parties_alliances_snapshot(descent)["digest"],
        "history_event_ids_digest": payload_digest(list(descent.history_event_ids)),
        "canonical_descent_fingerprint": descent.fingerprint(),
        "initialized_event_id": metadata["initialized_event_id"],
    }
    return {**body, "digest": payload_digest(body)}


class RivalryBetrayalSocialConflictService:
    """Simulation-owned 30C.5 conflict validator/executor."""

    def __init__(self, persistence: CrawlPersistence | None = None) -> None:
        self.persistence = persistence
        self.lifecycle = CrawlLifecycleService(persistence)
        self.memory = SocialMemoryEvolutionService(persistence)
        self.parties = PartiesAlliancesLeadershipService(persistence)

    def initialize(self, descent: Descent) -> Descent:
        validate_parties_alliances_leadership(descent)
        if METADATA_KEY in descent.modifiers:
            validate_rivalry_betrayal_social_conflict(descent)
            return descent
        metadata = {
            "protocol": PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "authoritative": True,
            "canonical_owner": "deterministic_simulation",
            "extends_slice": "30C.4",
            "random_betrayal_allowed": False,
            "presentation_feedback_allowed": False,
            "allowed_actions": list(ALLOWED_ACTIONS),
            "action_thresholds": dict(ACTION_THRESHOLDS),
            "conflict_records": [],
            "deceptions": {},
            "revenge_records": {},
            "hostile_alliance_breaks": {},
            "initialized_event_id": None,
        }
        descent.modifiers[METADATA_KEY] = metadata
        event = self.lifecycle.record_event(
            descent,
            INITIALIZED_EVENT,
            "Deterministic rivalry, betrayal, and social-conflict authority initialized.",
            actor_ids=sorted(descent.participants),
            data={
                "protocol": PROTOCOL,
                "random_betrayal_allowed": False,
                "high_impact_actions_require_negative_evidence": True,
                "state_changes": {"social_conflict_initialized": True},
            },
        )
        metadata["initialized_event_id"] = event.id
        self.lifecycle.save(descent)
        validate_rivalry_betrayal_social_conflict(descent)
        return descent

    def observe(self, descent: Descent, descender_id: str, target_descender_id: str) -> ConflictObservation:
        return build_conflict_observation(descent, descender_id, target_descender_id)

    def propose(self, descent: Descent, descender_id: str, target_descender_id: str, action: str, **kwargs: Any) -> ConflictIntent:
        return propose_conflict_intent(descent, descender_id, target_descender_id, action, **kwargs)

    def validate(self, descent: Descent, intent: ConflictIntent) -> ConflictDecision:
        return validate_conflict_intent(descent, intent)

    def _record_social_source(
        self,
        descent: Descent,
        *,
        event_type: str,
        actor_ids: list[str],
        summary: str,
        data: dict[str, Any],
        location_id: str | None,
    ) -> tuple[CrawlEvent, tuple[str, ...], tuple[str, ...]]:
        event = self.lifecycle.record_event(
            descent,
            event_type,
            summary,
            actor_ids=actor_ids,
            location_id=location_id,
            data=data,
        )
        self.lifecycle.save(descent)
        memory_events, relationship_events = _memory_result(self.memory, descent, event)
        return event, memory_events, relationship_events

    def execute(self, descent: Descent, intent: ConflictIntent) -> ConflictExecutionResult:
        before = _canonical_state_digest(descent)
        decision = self.validate(descent, intent)
        if not decision.accepted:
            body = {
                "protocol": RESULT_PROTOCOL,
                "implementation_version": IMPLEMENTATION_VERSION,
                "proposal_id": intent.proposal_id,
                "action": intent.action,
                "accepted": False,
                "executed": False,
                "reason_code": decision.reason_code,
                "descender_id": intent.descender_id,
                "target_descender_id": intent.target_descender_id,
                "conflict_score": decision.conflict_score,
                "source_event_id": None,
                "execution_event_id": None,
                "memory_event_ids": (),
                "relationship_event_ids": (),
                "affected_party_id": None,
                "affected_alliance_id": None,
                "affected_item_id": None,
                "deception_id": None,
                "revenge_id": None,
                "canonical_state_digest_before": before,
                "canonical_state_digest_after": before,
            }
            result = ConflictExecutionResult(**body, result_digest=payload_digest(body))
            if _canonical_state_digest(descent) != before:
                raise RivalryBetrayalSocialConflictError("rejected conflict intent mutated canonical state")
            return result

        actor = intent.descender_id
        target = intent.target_descender_id
        location_id = descent.participants[actor].current_location_id
        memory_event_ids: tuple[str, ...] = ()
        relationship_event_ids: tuple[str, ...] = ()
        affected_party_id: str | None = None
        affected_alliance_id: str | None = None
        affected_item_id: str | None = None
        deception_id: str | None = None
        revenge_id: str | None = None

        if intent.action == "refuse_aid":
            source_event, memory_event_ids, relationship_event_ids = self._record_social_source(
                descent,
                event_type="AID_REFUSED",
                actor_ids=[actor, target],
                summary="A Descender refused aid under accumulated social conflict.",
                location_id=location_id,
                data={"protocol": PROTOCOL, "incentive_code": intent.incentive_code, "conflict_score": decision.conflict_score, "state_changes": {"aid_refused": True}},
            )
        elif intent.action == "steal_loot":
            item_id = intent.target_item_id or ""
            item = transfer_item_to_crawler(descent, item_id, actor)
            source_event, memory_event_ids, relationship_event_ids = self._record_social_source(
                descent,
                event_type="LOOT_STOLEN",
                actor_ids=[actor, target],
                summary="A Descender seized another Descender's canonical loot after a social conflict threshold was met.",
                location_id=location_id,
                data={"protocol": PROTOCOL, "item_id": item_id, "incentive_code": intent.incentive_code, "conflict_score": decision.conflict_score, "state_changes": {"item_owner_descender_id": actor}},
            )
            item.provenance_event_ids.append(source_event.id)
            affected_item_id = item_id
        elif intent.action == "deceive":
            deception_id = _stable_id("deception", descent.id, intent.proposal_id, actor, target)
            source_event = self.lifecycle.record_event(
                descent,
                DECEPTION_CREATED_EVENT,
                "A structured bounded deception was created; no social memory is invented until it is exposed.",
                actor_ids=[actor, target],
                location_id=location_id,
                data={"protocol": PROTOCOL, "deception_id": deception_id, "claim_code": intent.claim_code, "incentive_code": intent.incentive_code, "conflict_score": decision.conflict_score, "state_changes": {"deception_status": "concealed"}},
            )
            record = {
                "deception_id": deception_id,
                "source_descender_id": actor,
                "target_descender_id": target,
                "claim_code": intent.claim_code,
                "status": "concealed",
                "created_tick": descent.current_tick,
                "created_event_id": source_event.id,
                "exposed_tick": None,
                "exposed_event_id": None,
            }
            record["digest"] = payload_digest(record)
            _metadata(descent)["deceptions"][deception_id] = record
            self.lifecycle.save(descent)
        elif intent.action == "expose_deception":
            deception_id = intent.deception_id or ""
            record = _metadata(descent)["deceptions"][deception_id]
            deceiver = record["source_descender_id"]
            victim = record["target_descender_id"]
            source_event, memory_event_ids, relationship_event_ids = self._record_social_source(
                descent,
                event_type="PROMISE_VIOLATED",
                actor_ids=[deceiver, victim],
                summary="A previously structured deception was exposed as a canonical broken social commitment.",
                location_id=descent.participants[victim].current_location_id,
                data={"protocol": PROTOCOL, "deception_id": deception_id, "claim_code": record["claim_code"], "state_changes": {"deception_status": "exposed"}},
            )
            record["status"] = "exposed"
            record["exposed_tick"] = descent.current_tick
            record["exposed_event_id"] = source_event.id
            record["digest"] = payload_digest(_record_body(record))
            self.lifecycle.save(descent)
        elif intent.action in {"abandon_party", "betray_party"}:
            party_id = descent.participants[actor].current_party_id
            assert party_id is not None
            former_members = list(descent.parties[party_id].member_npc_ids)
            remaining = [npc_id for npc_id in former_members if npc_id != actor]
            self.parties.leave_party(descent, party_id, actor)
            memory_type = "betrayed" if intent.action == "betray_party" else "abandoned"
            event_type = "BETRAYAL" if intent.action == "betray_party" else "ABANDONED"
            source_event, memory_event_ids, relationship_event_ids = self._record_social_source(
                descent,
                event_type=event_type,
                actor_ids=[actor, target],
                summary="A Descender broke from a party under accumulated canonical social conflict.",
                location_id=location_id,
                data={
                    "protocol": PROTOCOL,
                    "party_id": party_id,
                    "incentive_code": intent.incentive_code,
                    "conflict_score": decision.conflict_score,
                    "social_facts": [
                        {"observer_descender_id": npc_id, "subject_descender_id": actor, "memory_type": memory_type}
                        for npc_id in sorted(remaining)
                    ],
                    "state_changes": {"departed_party_id": party_id},
                },
            )
            affected_party_id = party_id
        elif intent.action == "break_alliance":
            alliance_id = intent.alliance_id or ""
            party_metadata = _party_metadata(descent)
            alliance = party_metadata["alliances"].pop(alliance_id)
            source_party_id = descent.participants[actor].current_party_id
            target_party_id = descent.participants[target].current_party_id
            assert source_party_id is not None and target_party_id is not None
            victim_members = list(descent.parties[target_party_id].member_npc_ids)
            source_event, memory_event_ids, relationship_event_ids = self._record_social_source(
                descent,
                event_type=ALLIANCE_BETRAYAL_EVENT,
                actor_ids=[actor, target],
                summary="A party leader broke a canonical alliance as an evidence-backed betrayal.",
                location_id=location_id,
                data={
                    "protocol": PROTOCOL,
                    "alliance_id": alliance_id,
                    "source_party_id": source_party_id,
                    "target_party_id": target_party_id,
                    "incentive_code": intent.incentive_code,
                    "conflict_score": decision.conflict_score,
                    "social_facts": [
                        {"observer_descender_id": npc_id, "subject_descender_id": actor, "memory_type": "betrayed"}
                        for npc_id in sorted(victim_members) if npc_id != actor
                    ],
                    "state_changes": {"alliance_active": False, "hostile_break": True},
                },
            )
            archive = {
                "alliance_id": alliance_id,
                "original_alliance": alliance,
                "source_party_id": source_party_id,
                "target_party_id": target_party_id,
                "source_descender_id": actor,
                "target_descender_id": target,
                "break_tick": descent.current_tick,
                "break_event_id": source_event.id,
                "basis_event_ids": list(decision.basis_event_ids),
                "conflict_score": decision.conflict_score,
            }
            archive["digest"] = payload_digest(archive)
            _metadata(descent)["hostile_alliance_breaks"][alliance_id] = archive
            self.lifecycle.save(descent)
            affected_alliance_id = alliance_id
        elif intent.action == "seek_revenge":
            revenge_id = _stable_id("revenge", descent.id, actor, target, intent.proposal_id)
            source_event = self.lifecycle.record_event(
                descent,
                REVENGE_STARTED_EVENT,
                "A Descender entered bounded revenge-seeking state from accumulated canonical grievance evidence.",
                actor_ids=[actor, target],
                location_id=location_id,
                data={"protocol": PROTOCOL, "revenge_id": revenge_id, "basis_event_ids": list(decision.basis_event_ids), "conflict_score": decision.conflict_score, "combat_started": False, "state_changes": {"revenge_status": "active"}},
            )
            record = {
                "revenge_id": revenge_id,
                "source_descender_id": actor,
                "target_descender_id": target,
                "status": "active",
                "started_tick": descent.current_tick,
                "started_event_id": source_event.id,
                "basis_event_ids": list(decision.basis_event_ids),
                "conflict_score": decision.conflict_score,
            }
            record["digest"] = payload_digest(record)
            _metadata(descent)["revenge_records"][revenge_id] = record
            self.lifecycle.save(descent)
        else:
            raise RivalryBetrayalSocialConflictError("accepted conflict intent escaped execution vocabulary")

        execution_event = self.lifecycle.record_event(
            descent,
            EXECUTED_EVENT,
            "Simulation executed one validated deterministic social-conflict intent.",
            actor_ids=[actor, target],
            location_id=location_id,
            data={
                "protocol": PROTOCOL,
                "proposal_id": intent.proposal_id,
                "action": intent.action,
                "conflict_score": decision.conflict_score,
                "threshold": decision.threshold,
                "incentive_code": intent.incentive_code,
                "incentive_strength": intent.incentive_strength,
                "basis_event_ids": list(decision.basis_event_ids),
                "source_event_id": source_event.id,
                "memory_event_ids": list(memory_event_ids),
                "relationship_event_ids": list(relationship_event_ids),
                "state_changes": {"social_conflict_executed": True},
            },
        )
        record = {
            "index": len(_metadata(descent)["conflict_records"]),
            "proposal_id": intent.proposal_id,
            "action": intent.action,
            "source_descender_id": actor,
            "target_descender_id": target,
            "incentive_code": intent.incentive_code,
            "incentive_strength": intent.incentive_strength,
            "conflict_score": decision.conflict_score,
            "threshold": decision.threshold,
            "basis_event_ids": list(decision.basis_event_ids),
            "source_event_id": source_event.id,
            "execution_event_id": execution_event.id,
            "memory_event_ids": list(memory_event_ids),
            "relationship_event_ids": list(relationship_event_ids),
            "affected_party_id": affected_party_id,
            "affected_alliance_id": affected_alliance_id,
            "affected_item_id": affected_item_id,
            "deception_id": deception_id,
            "revenge_id": revenge_id,
            "tick": descent.current_tick,
        }
        record["digest"] = payload_digest(record)
        _metadata(descent)["conflict_records"].append(record)
        self.lifecycle.save(descent)
        validate_rivalry_betrayal_social_conflict(descent)
        after = _canonical_state_digest(descent)
        body = {
            "protocol": RESULT_PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "proposal_id": intent.proposal_id,
            "action": intent.action,
            "accepted": True,
            "executed": True,
            "reason_code": "executed",
            "descender_id": actor,
            "target_descender_id": target,
            "conflict_score": decision.conflict_score,
            "source_event_id": source_event.id,
            "execution_event_id": execution_event.id,
            "memory_event_ids": memory_event_ids,
            "relationship_event_ids": relationship_event_ids,
            "affected_party_id": affected_party_id,
            "affected_alliance_id": affected_alliance_id,
            "affected_item_id": affected_item_id,
            "deception_id": deception_id,
            "revenge_id": revenge_id,
            "canonical_state_digest_before": before,
            "canonical_state_digest_after": after,
        }
        return ConflictExecutionResult(**body, result_digest=payload_digest(body))


__all__ = [
    "PROTOCOL", "IMPLEMENTATION_VERSION", "OBSERVATION_PROTOCOL", "INTENT_PROTOCOL",
    "DECISION_PROTOCOL", "RESULT_PROTOCOL", "METADATA_KEY", "ALLOWED_ACTIONS",
    "INCENTIVE_CODES", "DECEPTION_CLAIMS", "ACTION_THRESHOLDS",
    "RivalryBetrayalSocialConflictError", "ConflictObservation", "ConflictIntent",
    "ConflictDecision", "ConflictExecutionResult", "RivalryBetrayalSocialConflictService",
    "build_conflict_observation", "propose_conflict_intent", "validate_conflict_intent",
    "validate_rivalry_betrayal_social_conflict", "build_rivalry_betrayal_social_conflict_snapshot",
]
