"""Deterministic social proposal and interaction execution for Underreach 30C.3.

30C.1 owns directed relationship truth. 30C.2 owns event-linked social memory.
30C.3 adds bounded advisory social proposals plus a deterministic validation and
execution membrane. Persistent parties, alliances, leadership, social conflict,
and dialogue remain later-slice responsibilities.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any

from pydantic import BaseModel, ConfigDict

from .crawl_domain import CrawlEvent, CrawlStatus, ParticipationStatus
from .crawl_persistence import CrawlPersistence
from .crawl_service import CrawlLifecycleService
from .crawler_domain import LocationKnowledge
from .gameplay_domain import ItemCategory
from .item_system import transfer_item_to_crawler
from .runtime_checkpoint import payload_digest
from .underreach_domain import Descent
from .underreach_social_memory_evolution import (
    METADATA_KEY as SOCIAL_MEMORY_METADATA_KEY,
    SocialMemoryEvolutionService,
    build_social_memory_snapshot,
    validate_social_memory_evolution,
)
from .underreach_social_state import build_social_state_snapshot, get_relationship


PROTOCOL = "underreach.social-intent-execution.v1"
IMPLEMENTATION_VERSION = "30c3.1"
OBSERVATION_PROTOCOL = "underreach.social-observation.v1"
INTENT_PROTOCOL = "underreach.social-intent.v1"
DECISION_PROTOCOL = "underreach.social-intent-decision.v1"
RESULT_PROTOCOL = "underreach.social-intent-result.v1"
METADATA_KEY = "_social_intent_execution"

INITIALIZED_EVENT = "SOCIAL_INTENT_EXECUTION_INITIALIZED"
EXECUTED_EVENT = "SOCIAL_INTENT_EXECUTED"
WARNING_EVENT = "SOCIAL_WARNING_ISSUED"
RECRUITMENT_OFFERED_EVENT = "SOCIAL_RECRUITMENT_OFFERED"
RECRUITMENT_ACCEPTED_EVENT = "SOCIAL_RECRUITMENT_ACCEPTED"
RECRUITMENT_REFUSED_EVENT = "SOCIAL_RECRUITMENT_REFUSED"
CHALLENGE_EVENT = "SOCIAL_CHALLENGE_ISSUED"
SHARED_EVENT = "SHARED_RESOURCE"

ALLOWED_ACTIONS = (
    "share_item",
    "share_supply",
    "warn",
    "recruit",
    "accept_recruitment",
    "refuse_recruitment",
    "challenge",
)
RECRUITMENT_STATUSES = ("pending", "accepted", "refused")
SECOND_HAND_KNOWLEDGE_FACTOR = 0.85
MAX_SECOND_HAND_CONFIDENCE = 0.95


class SocialIntentExecutionError(ValueError):
    """Raised when a 30C.3 social proposal or execution contract is violated."""


class SocialTargetObservation(BaseModel):
    model_config = ConfigDict(frozen=True)

    target_descender_id: str
    trust: float
    respect: float
    affection: float
    fear: float
    resentment: float
    gratitude: float
    rivalry: float
    familiarity: float


class SocialObservation(BaseModel):
    model_config = ConfigDict(frozen=True)

    protocol: str = OBSERVATION_PROTOCOL
    implementation_version: str = IMPLEMENTATION_VERSION
    descender_id: str
    current_tick: int
    current_stratum_number: int
    current_sector_id: str | None
    colocated_descender_ids: tuple[str, ...]
    transferable_item_ids: tuple[str, ...]
    transferable_supply_ids: tuple[str, ...]
    known_sector_ids: tuple[str, ...]
    pending_recruitment_offer_ids: tuple[str, ...]
    targets: tuple[SocialTargetObservation, ...]
    relationship_state_digest: str
    memory_state_digest: str
    canonical_state_digest: str
    observation_digest: str


class SocialIntent(BaseModel):
    model_config = ConfigDict(frozen=True)

    protocol: str = INTENT_PROTOCOL
    implementation_version: str = IMPLEMENTATION_VERSION
    proposal_id: str
    provider_id: str
    descender_id: str
    observation_digest: str
    action: str
    target_descender_id: str | None = None
    target_item_id: str | None = None
    target_sector_id: str | None = None
    recruitment_offer_id: str | None = None


class SocialIntentExecutionDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    protocol: str = DECISION_PROTOCOL
    implementation_version: str = IMPLEMENTATION_VERSION
    proposal_id: str
    provider_id: str
    descender_id: str
    observation_digest: str
    canonical_state_digest: str
    accepted: bool
    reason_code: str
    action: str
    target_descender_id: str | None = None
    target_item_id: str | None = None
    target_sector_id: str | None = None
    recruitment_offer_id: str | None = None
    resolved_offer_id: str | None = None
    decision_digest: str


class SocialIntentExecutionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    protocol: str = RESULT_PROTOCOL
    implementation_version: str = IMPLEMENTATION_VERSION
    proposal_id: str
    provider_id: str
    descender_id: str
    accepted: bool
    executed: bool
    reason_code: str
    action: str
    target_descender_id: str | None = None
    target_item_id: str | None = None
    target_sector_id: str | None = None
    recruitment_offer_id: str | None = None
    resolved_offer_id: str | None = None
    interaction_event_id: str | None = None
    execution_event_id: str | None = None
    memory_event_ids: tuple[str, ...] = ()
    relationship_event_ids: tuple[str, ...] = ()
    canonical_state_digest_before: str
    canonical_state_digest_after: str
    canonical_fingerprint_before: str
    canonical_fingerprint_after: str
    result_digest: str


def _stable_id(prefix: str, *parts: object) -> str:
    payload = ":".join("" if part is None else str(part) for part in parts)
    return f"{prefix}_{sha256(payload.encode('utf-8')).hexdigest()[:20]}"


def _canonical_state_digest(descent: Descent) -> str:
    return payload_digest(descent.model_dump(mode="json"))


def _metadata(descent: Descent) -> dict[str, Any]:
    value = descent.modifiers.get(METADATA_KEY)
    if not isinstance(value, dict):
        raise SocialIntentExecutionError("Descent is missing 30C.3 social-intent metadata")
    return value


def _offer_body(offer: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in offer.items() if key != "digest"}


def _record_body(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key != "digest"}


def _active_current(descent: Descent, descender_id: str) -> bool:
    participant = descent.participants.get(descender_id)
    return bool(
        participant is not None
        and participant.status == ParticipationStatus.ACTIVE
        and participant.current_floor == descent.current_floor
    )


def _same_sector(descent: Descent, left: str, right: str) -> bool:
    return bool(
        _active_current(descent, left)
        and _active_current(descent, right)
        and descent.participants[left].current_location_id is not None
        and descent.participants[left].current_location_id
        == descent.participants[right].current_location_id
    )


def _validate_provider_id(provider_id: str) -> str:
    value = str(provider_id)
    if not value or len(value) > 96:
        raise SocialIntentExecutionError("social intent provider_id must be a bounded non-empty identifier")
    return value


def _intent_body(
    *,
    provider_id: str,
    descender_id: str,
    observation_digest: str,
    action: str,
    target_descender_id: str | None,
    target_item_id: str | None,
    target_sector_id: str | None,
    recruitment_offer_id: str | None,
) -> dict[str, Any]:
    return {
        "provider_id": provider_id,
        "descender_id": descender_id,
        "observation_digest": observation_digest,
        "action": action,
        "target_descender_id": target_descender_id,
        "target_item_id": target_item_id,
        "target_sector_id": target_sector_id,
        "recruitment_offer_id": recruitment_offer_id,
    }


def _expected_proposal_id(intent: SocialIntent) -> str:
    body = _intent_body(
        provider_id=intent.provider_id,
        descender_id=intent.descender_id,
        observation_digest=intent.observation_digest,
        action=intent.action,
        target_descender_id=intent.target_descender_id,
        target_item_id=intent.target_item_id,
        target_sector_id=intent.target_sector_id,
        recruitment_offer_id=intent.recruitment_offer_id,
    )
    return _stable_id("social_proposal", *(body[key] for key in body))


def validate_social_intent_contract(intent: SocialIntent) -> bool:
    if intent.protocol != INTENT_PROTOCOL or intent.implementation_version != IMPLEMENTATION_VERSION:
        raise SocialIntentExecutionError("social intent protocol or version mismatch")
    _validate_provider_id(intent.provider_id)
    if intent.action not in ALLOWED_ACTIONS:
        raise SocialIntentExecutionError("social intent escaped the bounded action vocabulary")
    if not intent.descender_id or not intent.observation_digest:
        raise SocialIntentExecutionError("social intent is missing canonical identity")
    if intent.proposal_id != _expected_proposal_id(intent):
        raise SocialIntentExecutionError("social intent proposal identity mismatch")

    target = intent.target_descender_id
    item = intent.target_item_id
    sector = intent.target_sector_id
    offer = intent.recruitment_offer_id
    if intent.action in {"share_item", "share_supply"}:
        if not target or not item or sector is not None or offer is not None:
            raise SocialIntentExecutionError("share intent shape is invalid")
    elif intent.action == "warn":
        if not target or not sector or item is not None or offer is not None:
            raise SocialIntentExecutionError("warning intent shape is invalid")
    elif intent.action in {"recruit", "challenge"}:
        if not target or any(value is not None for value in (item, sector, offer)):
            raise SocialIntentExecutionError(f"{intent.action} intent shape is invalid")
    elif intent.action in {"accept_recruitment", "refuse_recruitment"}:
        if not target or not offer or item is not None or sector is not None:
            raise SocialIntentExecutionError("recruitment response intent shape is invalid")
    return True


def validate_social_intent_execution(descent: Descent) -> bool:
    """Validate 30C.3 while preserving the complete accepted 30C.2 contract."""
    validate_social_memory_evolution(descent)
    metadata = _metadata(descent)
    if metadata.get("protocol") != PROTOCOL or metadata.get("implementation_version") != IMPLEMENTATION_VERSION:
        raise SocialIntentExecutionError("social-intent protocol or version mismatch")
    if metadata.get("authoritative") is not True or metadata.get("canonical_owner") != "deterministic_simulation":
        raise SocialIntentExecutionError("social-intent authority boundary changed")
    if metadata.get("extends_slice") != "30C.2":
        raise SocialIntentExecutionError("30C.3 source-slice boundary changed")
    if metadata.get("proposal_can_mutate") is not False or metadata.get("provider_can_mutate") is not False:
        raise SocialIntentExecutionError("social proposal/provider cannot own canonical mutation")
    if metadata.get("presentation_feedback_allowed") is not False:
        raise SocialIntentExecutionError("presentation feedback cannot mutate social interaction truth")
    if metadata.get("party_mutation_enabled") is not False:
        raise SocialIntentExecutionError("30C.3 cannot own persistent party mutation")
    if metadata.get("allowed_actions") != list(ALLOWED_ACTIONS):
        raise SocialIntentExecutionError("30C.3 social action vocabulary changed")

    history = set(descent.history_event_ids)
    initialized = metadata.get("initialized_event_id")
    if not isinstance(initialized, str) or initialized not in history:
        raise SocialIntentExecutionError("social-intent initialization is not Ledger bound")

    interaction_ids = metadata.get("interaction_event_ids")
    execution_ids = metadata.get("execution_event_ids")
    records = metadata.get("interaction_records")
    if not isinstance(interaction_ids, list) or not isinstance(execution_ids, list) or not isinstance(records, list):
        raise SocialIntentExecutionError("social interaction traces are invalid")
    if len(interaction_ids) != len(set(interaction_ids)) or len(execution_ids) != len(set(execution_ids)):
        raise SocialIntentExecutionError("social interaction traces contain duplicate event IDs")
    if len(records) != len(interaction_ids) or len(records) != len(execution_ids):
        raise SocialIntentExecutionError("social interaction record/event counts diverged")
    if int(metadata.get("execution_count", -1)) != len(records):
        raise SocialIntentExecutionError("social interaction execution count diverged")
    if any(event_id not in history for event_id in [*interaction_ids, *execution_ids]):
        raise SocialIntentExecutionError("social interaction event is missing from canonical Ledger history")
    for index, record in enumerate(records):
        if not isinstance(record, dict) or int(record.get("execution_index", -1)) != index:
            raise SocialIntentExecutionError("social interaction record index is invalid")
        if record.get("action") not in ALLOWED_ACTIONS:
            raise SocialIntentExecutionError("social interaction record escaped bounded actions")
        if record.get("interaction_event_id") != interaction_ids[index] or record.get("execution_event_id") != execution_ids[index]:
            raise SocialIntentExecutionError("social interaction record event binding diverged")
        if record.get("digest") != payload_digest(_record_body(record)):
            raise SocialIntentExecutionError("social interaction record digest mismatch")

    offers = metadata.get("recruitment_offers")
    if not isinstance(offers, dict):
        raise SocialIntentExecutionError("recruitment offer storage is invalid")
    for offer_id, offer in offers.items():
        if not isinstance(offer, dict) or offer.get("offer_id") != offer_id:
            raise SocialIntentExecutionError("recruitment offer identity is invalid")
        if offer.get("status") not in RECRUITMENT_STATUSES:
            raise SocialIntentExecutionError("recruitment offer status is invalid")
        source = offer.get("source_descender_id")
        target = offer.get("target_descender_id")
        if source == target or source not in descent.participants or target not in descent.participants:
            raise SocialIntentExecutionError("recruitment offer endpoints are invalid")
        if int(offer.get("offered_tick", -1)) < 0 or offer.get("offered_event_id") not in history:
            raise SocialIntentExecutionError("recruitment offer lacks canonical provenance")
        resolved_event = offer.get("resolved_event_id")
        if offer["status"] == "pending":
            if offer.get("resolved_tick") is not None or resolved_event is not None:
                raise SocialIntentExecutionError("pending recruitment offer has resolution state")
        else:
            if int(offer.get("resolved_tick", -1)) < int(offer["offered_tick"]) or resolved_event not in history:
                raise SocialIntentExecutionError("resolved recruitment offer lacks canonical resolution")
        if offer.get("digest") != payload_digest(_offer_body(offer)):
            raise SocialIntentExecutionError("recruitment offer digest mismatch")
    return True


def build_social_observation(descent: Descent, descender_id: str) -> SocialObservation:
    validate_social_intent_execution(descent)
    participant = descent.participants.get(descender_id)
    if participant is None:
        raise SocialIntentExecutionError("social observation Descender is not participating")
    current_sector = participant.current_location_id
    colocated = tuple(
        sorted(
            other_id
            for other_id in descent.participants
            if other_id != descender_id
            and current_sector is not None
            and _same_sector(descent, descender_id, other_id)
        )
    )
    inventory = sorted(participant.gameplay.inventory_item_ids)
    transferable_items = tuple(
        item_id
        for item_id in inventory
        if item_id in descent.items and descent.items[item_id].category != ItemCategory.RESOURCE
    )
    transferable_supplies = tuple(
        item_id
        for item_id in inventory
        if item_id in descent.items and descent.items[item_id].category == ItemCategory.RESOURCE
    )
    known = tuple(sorted(participant.agent.knowledge)) if participant.agent is not None else ()
    pending_offers = tuple(
        sorted(
            offer_id
            for offer_id, offer in _metadata(descent)["recruitment_offers"].items()
            if offer["status"] == "pending" and offer["target_descender_id"] == descender_id
        )
    )

    targets: list[SocialTargetObservation] = []
    for target_id in colocated:
        relationship = get_relationship(descent, descender_id, target_id)
        targets.append(
            SocialTargetObservation(
                target_descender_id=target_id,
                trust=relationship.trust,
                respect=relationship.respect,
                affection=relationship.affection,
                fear=relationship.fear,
                resentment=relationship.resentment,
                gratitude=relationship.gratitude,
                rivalry=relationship.rivalry,
                familiarity=relationship.familiarity,
            )
        )

    social_snapshot = build_social_state_snapshot(descent)
    memory_snapshot = build_social_memory_snapshot(descent)
    canonical_digest = _canonical_state_digest(descent)
    body = {
        "protocol": OBSERVATION_PROTOCOL,
        "implementation_version": IMPLEMENTATION_VERSION,
        "descender_id": descender_id,
        "current_tick": descent.current_tick,
        "current_stratum_number": descent.current_floor,
        "current_sector_id": current_sector,
        "colocated_descender_ids": colocated,
        "transferable_item_ids": transferable_items,
        "transferable_supply_ids": transferable_supplies,
        "known_sector_ids": known,
        "pending_recruitment_offer_ids": pending_offers,
        "targets": tuple(target.model_dump(mode="json") for target in targets),
        "relationship_state_digest": social_snapshot["relationship_state_digest"],
        "memory_state_digest": memory_snapshot["memory_state_digest"],
        "canonical_state_digest": canonical_digest,
    }
    return SocialObservation(
        **{key: value for key, value in body.items() if key != "targets"},
        targets=tuple(targets),
        observation_digest=payload_digest(body),
    )


def propose_social_intent(
    descent: Descent,
    descender_id: str,
    action: str,
    *,
    provider_id: str = "bounded-social-proposer-v1",
    target_descender_id: str | None = None,
    target_item_id: str | None = None,
    target_sector_id: str | None = None,
    recruitment_offer_id: str | None = None,
) -> SocialIntent:
    """Build one immutable advisory proposal without mutating canonical state."""
    before = _canonical_state_digest(descent)
    before_history = tuple(descent.history_event_ids)
    observation = build_social_observation(descent, descender_id)
    provider = _validate_provider_id(provider_id)
    body = _intent_body(
        provider_id=provider,
        descender_id=descender_id,
        observation_digest=observation.observation_digest,
        action=str(action),
        target_descender_id=target_descender_id,
        target_item_id=target_item_id,
        target_sector_id=target_sector_id,
        recruitment_offer_id=recruitment_offer_id,
    )
    intent = SocialIntent(
        proposal_id=_stable_id("social_proposal", *(body[key] for key in body)),
        **body,
    )
    validate_social_intent_contract(intent)
    if _canonical_state_digest(descent) != before or tuple(descent.history_event_ids) != before_history:
        raise SocialIntentExecutionError("social intent proposal mutated canonical state")
    return intent


def _semantic_rejection(
    descent: Descent,
    observation: SocialObservation,
    intent: SocialIntent,
) -> tuple[str | None, str | None]:
    if descent.status != CrawlStatus.RUNNING:
        return "descent_not_running", None
    if not _active_current(descent, intent.descender_id):
        return "source_not_active_current_stratum", None
    if descent.participants[intent.descender_id].current_location_id != observation.current_sector_id:
        return "observation_location_mismatch", None

    target = intent.target_descender_id
    if target is None or target not in descent.participants:
        return "target_missing", None
    if target == intent.descender_id:
        return "self_interaction_forbidden", None
    if not _active_current(descent, target):
        return "target_not_active_current_stratum", None
    if not _same_sector(descent, intent.descender_id, target):
        return "target_not_colocated", None

    if intent.action in {"share_item", "share_supply"}:
        item = descent.items.get(intent.target_item_id or "")
        if item is None:
            return "item_missing", None
        if item.owner_npc_id != intent.descender_id:
            return "item_not_owned", None
        if intent.action == "share_supply" and item.category != ItemCategory.RESOURCE:
            return "item_not_survival_supply", None
        if intent.action == "share_item" and item.category == ItemCategory.RESOURCE:
            return "survival_supply_requires_share_supply", None
    elif intent.action == "warn":
        source_agent = descent.participants[intent.descender_id].agent
        target_agent = descent.participants[target].agent
        if source_agent is None or target_agent is None:
            return "warning_requires_agent_state", None
        if intent.target_sector_id not in source_agent.knowledge:
            return "warning_sector_not_known", None
    elif intent.action == "recruit":
        for offer_id, offer in _metadata(descent)["recruitment_offers"].items():
            if (
                offer["status"] == "pending"
                and offer["source_descender_id"] == intent.descender_id
                and offer["target_descender_id"] == target
            ):
                return "pending_recruitment_offer_exists", offer_id
        return None, _stable_id("recruit_offer", descent.id, intent.proposal_id)
    elif intent.action in {"accept_recruitment", "refuse_recruitment"}:
        offer = _metadata(descent)["recruitment_offers"].get(intent.recruitment_offer_id or "")
        if not isinstance(offer, dict):
            return "recruitment_offer_missing", None
        if offer["status"] != "pending":
            return "recruitment_offer_not_pending", offer["offer_id"]
        if offer["target_descender_id"] != intent.descender_id:
            return "recruitment_offer_wrong_recipient", offer["offer_id"]
        if offer["source_descender_id"] != target:
            return "recruitment_offer_source_mismatch", offer["offer_id"]
        return None, offer["offer_id"]
    return None, None


def _build_decision(
    descent: Descent,
    observation: SocialObservation,
    intent: SocialIntent,
    *,
    accepted: bool,
    reason_code: str,
    resolved_offer_id: str | None = None,
) -> SocialIntentExecutionDecision:
    body = {
        "protocol": DECISION_PROTOCOL,
        "implementation_version": IMPLEMENTATION_VERSION,
        "proposal_id": intent.proposal_id,
        "provider_id": intent.provider_id,
        "descender_id": intent.descender_id,
        "observation_digest": observation.observation_digest,
        "canonical_state_digest": _canonical_state_digest(descent),
        "accepted": accepted,
        "reason_code": reason_code,
        "action": intent.action,
        "target_descender_id": intent.target_descender_id,
        "target_item_id": intent.target_item_id,
        "target_sector_id": intent.target_sector_id,
        "recruitment_offer_id": intent.recruitment_offer_id,
        "resolved_offer_id": resolved_offer_id,
    }
    return SocialIntentExecutionDecision(**body, decision_digest=payload_digest(body))


def validate_intent_for_execution(
    descent: Descent,
    intent: SocialIntent,
) -> SocialIntentExecutionDecision:
    """Evaluate a social proposal without mutating canonical state."""
    validate_social_intent_execution(descent)
    before_digest = _canonical_state_digest(descent)
    before_fingerprint = descent.fingerprint()
    before_history = tuple(descent.history_event_ids)

    try:
        validate_social_intent_contract(intent)
    except SocialIntentExecutionError:
        body = {
            "protocol": DECISION_PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "proposal_id": intent.proposal_id,
            "provider_id": intent.provider_id,
            "descender_id": intent.descender_id,
            "observation_digest": intent.observation_digest,
            "canonical_state_digest": before_digest,
            "accepted": False,
            "reason_code": "social_intent_contract_rejected",
            "action": intent.action,
            "target_descender_id": intent.target_descender_id,
            "target_item_id": intent.target_item_id,
            "target_sector_id": intent.target_sector_id,
            "recruitment_offer_id": intent.recruitment_offer_id,
            "resolved_offer_id": None,
        }
        return SocialIntentExecutionDecision(**body, decision_digest=payload_digest(body))

    try:
        observation = build_social_observation(descent, intent.descender_id)
    except (SocialIntentExecutionError, KeyError):
        body = {
            "protocol": DECISION_PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "proposal_id": intent.proposal_id,
            "provider_id": intent.provider_id,
            "descender_id": intent.descender_id,
            "observation_digest": intent.observation_digest,
            "canonical_state_digest": before_digest,
            "accepted": False,
            "reason_code": "current_social_observation_unavailable",
            "action": intent.action,
            "target_descender_id": intent.target_descender_id,
            "target_item_id": intent.target_item_id,
            "target_sector_id": intent.target_sector_id,
            "recruitment_offer_id": intent.recruitment_offer_id,
            "resolved_offer_id": None,
        }
        decision = SocialIntentExecutionDecision(**body, decision_digest=payload_digest(body))
    else:
        if intent.observation_digest != observation.observation_digest:
            decision = _build_decision(
                descent,
                observation,
                intent,
                accepted=False,
                reason_code="stale_observation",
            )
        else:
            rejection, offer_id = _semantic_rejection(descent, observation, intent)
            decision = _build_decision(
                descent,
                observation,
                intent,
                accepted=rejection is None,
                reason_code="accepted" if rejection is None else rejection,
                resolved_offer_id=offer_id,
            )

    if (
        _canonical_state_digest(descent) != before_digest
        or descent.fingerprint() != before_fingerprint
        or tuple(descent.history_event_ids) != before_history
    ):
        raise SocialIntentExecutionError("social intent validation mutated canonical state")
    return decision


def _merge_warning_knowledge(
    descent: Descent,
    source_descender_id: str,
    target_descender_id: str,
    sector_id: str,
) -> tuple[bool, str, str]:
    source_agent = descent.participants[source_descender_id].agent
    target_agent = descent.participants[target_descender_id].agent
    if source_agent is None or target_agent is None or sector_id not in source_agent.knowledge:
        raise SocialIntentExecutionError("accepted warning lost canonical knowledge state")
    source = source_agent.knowledge[sector_id]
    before = target_agent.knowledge.get(sector_id)
    before_payload = before.model_dump(mode="json") if before is not None else None
    transferred_confidence = round(
        min(MAX_SECOND_HAND_CONFIDENCE, float(source.confidence) * SECOND_HAND_KNOWLEDGE_FACTOR),
        6,
    )
    if before is None:
        target_agent.knowledge[sector_id] = LocationKnowledge(
            location_id=sector_id,
            last_observed_tick=source.last_observed_tick,
            confidence=transferred_confidence,
            known_neighbors=dict(sorted(source.known_neighbors.items())),
            tags=sorted(set(source.tags)),
            hazard_tags=sorted(set(source.hazard_tags)),
            believed_safe=source.believed_safe,
            believed_exit=source.believed_exit,
            visits=0,
        )
    else:
        before.last_observed_tick = max(before.last_observed_tick, source.last_observed_tick)
        before.confidence = round(max(float(before.confidence), transferred_confidence), 6)
        before.known_neighbors = dict(sorted({**before.known_neighbors, **source.known_neighbors}.items()))
        before.tags = sorted(set(before.tags) | set(source.tags))
        before.hazard_tags = sorted(set(before.hazard_tags) | set(source.hazard_tags))
        before.believed_safe = bool(before.believed_safe or source.believed_safe)
        before.believed_exit = bool(before.believed_exit or source.believed_exit)
    after_payload = target_agent.knowledge[sector_id].model_dump(mode="json")
    return (
        before_payload != after_payload,
        payload_digest(before_payload),
        payload_digest(after_payload),
    )


def build_social_intent_snapshot(descent: Descent) -> dict[str, Any]:
    validate_social_intent_execution(descent)
    metadata = _metadata(descent)
    offers = [dict(metadata["recruitment_offers"][offer_id]) for offer_id in sorted(metadata["recruitment_offers"])]
    records = [dict(record) for record in metadata["interaction_records"]]
    body = {
        "protocol": PROTOCOL,
        "implementation_version": IMPLEMENTATION_VERSION,
        "authoritative": True,
        "canonical_owner": "deterministic_simulation",
        "provider_can_mutate": False,
        "proposal_can_mutate": False,
        "presentation_feedback_allowed": False,
        "party_mutation_enabled": False,
        "descent_id": descent.id,
        "seed": descent.seed,
        "current_tick": descent.current_tick,
        "current_stratum_number": descent.current_floor,
        "execution_count": metadata["execution_count"],
        "interaction_records": records,
        "interaction_trace_digest": payload_digest(records),
        "recruitment_offers": offers,
        "recruitment_offer_digest": payload_digest(offers),
        "interaction_event_ids": list(metadata["interaction_event_ids"]),
        "execution_event_ids": list(metadata["execution_event_ids"]),
        "social_memory_snapshot_digest": build_social_memory_snapshot(descent)["digest"],
        "relationship_state_digest": build_social_state_snapshot(descent)["relationship_state_digest"],
        "history_event_ids_digest": payload_digest(list(descent.history_event_ids)),
        "canonical_descent_fingerprint": descent.fingerprint(),
        "initialized_event_id": metadata["initialized_event_id"],
    }
    return {**body, "digest": payload_digest(body)}


class SocialIntentExecutionService:
    """Simulation-owned validator and executor for bounded 30C.3 social proposals."""

    def __init__(self, persistence: CrawlPersistence | None = None) -> None:
        self.persistence = persistence
        self.lifecycle = CrawlLifecycleService(persistence)
        self.memory = SocialMemoryEvolutionService(persistence)

    def initialize(self, descent: Descent) -> Descent:
        if SOCIAL_MEMORY_METADATA_KEY not in descent.modifiers:
            self.memory.initialize(descent)
        validate_social_memory_evolution(descent)
        if METADATA_KEY in descent.modifiers:
            validate_social_intent_execution(descent)
            return descent
        metadata = {
            "protocol": PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "authoritative": True,
            "canonical_owner": "deterministic_simulation",
            "extends_slice": "30C.2",
            "social_memory_protocol": "underreach.social-memory-evolution.v1",
            "provider_can_mutate": False,
            "proposal_can_mutate": False,
            "presentation_feedback_allowed": False,
            "party_mutation_enabled": False,
            "persistent_party_owner_slice": "30C.4",
            "allowed_actions": list(ALLOWED_ACTIONS),
            "recruitment_offers": {},
            "interaction_event_ids": [],
            "execution_event_ids": [],
            "interaction_records": [],
            "execution_count": 0,
            "initialized_event_id": None,
        }
        descent.modifiers[METADATA_KEY] = metadata
        event = self.lifecycle.record_event(
            descent,
            INITIALIZED_EVENT,
            "Deterministic social intent validation and execution membrane initialized.",
            actor_ids=sorted(descent.participants),
            data={
                "protocol": PROTOCOL,
                "implementation_version": IMPLEMENTATION_VERSION,
                "allowed_actions": list(ALLOWED_ACTIONS),
                "party_mutation_enabled": False,
                "state_changes": {"social_intent_execution_initialized": True},
            },
        )
        metadata["initialized_event_id"] = event.id
        self.lifecycle.save(descent)
        validate_social_intent_execution(descent)
        return descent

    def observe(self, descent: Descent, descender_id: str) -> SocialObservation:
        return build_social_observation(descent, descender_id)

    def propose(self, descent: Descent, descender_id: str, action: str, **kwargs: Any) -> SocialIntent:
        return propose_social_intent(descent, descender_id, action, **kwargs)

    def validate(self, descent: Descent, intent: SocialIntent) -> SocialIntentExecutionDecision:
        return validate_intent_for_execution(descent, intent)

    def _process_share_memory(self, descent: Descent, event: CrawlEvent):
        return self.memory.process_event(descent, event)

    def execute(self, descent: Descent, intent: SocialIntent) -> SocialIntentExecutionResult:
        before_digest = _canonical_state_digest(descent)
        before_fingerprint = descent.fingerprint()
        before_history = tuple(descent.history_event_ids)
        decision = self.validate(descent, intent)
        if not decision.accepted:
            body = {
                "protocol": RESULT_PROTOCOL,
                "implementation_version": IMPLEMENTATION_VERSION,
                "proposal_id": intent.proposal_id,
                "provider_id": intent.provider_id,
                "descender_id": intent.descender_id,
                "accepted": False,
                "executed": False,
                "reason_code": decision.reason_code,
                "action": intent.action,
                "target_descender_id": intent.target_descender_id,
                "target_item_id": intent.target_item_id,
                "target_sector_id": intent.target_sector_id,
                "recruitment_offer_id": intent.recruitment_offer_id,
                "resolved_offer_id": decision.resolved_offer_id,
                "interaction_event_id": None,
                "execution_event_id": None,
                "memory_event_ids": (),
                "relationship_event_ids": (),
                "canonical_state_digest_before": before_digest,
                "canonical_state_digest_after": before_digest,
                "canonical_fingerprint_before": before_fingerprint,
                "canonical_fingerprint_after": before_fingerprint,
            }
            result = SocialIntentExecutionResult(**body, result_digest=payload_digest(body))
            if (
                _canonical_state_digest(descent) != before_digest
                or descent.fingerprint() != before_fingerprint
                or tuple(descent.history_event_ids) != before_history
            ):
                raise SocialIntentExecutionError("rejected social intent mutated canonical state")
            return result

        metadata = _metadata(descent)
        actor = intent.descender_id
        target = intent.target_descender_id
        assert target is not None
        location_id = descent.participants[actor].current_location_id
        memory_event_ids: tuple[str, ...] = ()
        relationship_event_ids: tuple[str, ...] = ()
        resolved_offer_id = decision.resolved_offer_id

        if intent.action in {"share_item", "share_supply"}:
            item_id = intent.target_item_id or ""
            item = transfer_item_to_crawler(descent, item_id, target)
            interaction = self.lifecycle.record_event(
                descent,
                SHARED_EVENT,
                f"Descender {actor} shared a canonical item with Descender {target}.",
                actor_ids=[actor, target],
                location_id=location_id,
                data={
                    "protocol": PROTOCOL,
                    "social_action": intent.action,
                    "item_id": item_id,
                    "item_category": item.category.value,
                    "source_descender_id": actor,
                    "target_descender_id": target,
                    "state_changes": {"item_owner_descender_id": target},
                },
            )
            item.provenance_event_ids.append(interaction.id)
            self.lifecycle.save(descent)
            processed = self._process_share_memory(descent, interaction)
            memory_event_ids = tuple(processed.memory_event_ids)
            relationship_event_ids = tuple(processed.relationship_event_ids)
        elif intent.action == "warn":
            changed, knowledge_before, knowledge_after = _merge_warning_knowledge(
                descent,
                actor,
                target,
                intent.target_sector_id or "",
            )
            interaction = self.lifecycle.record_event(
                descent,
                WARNING_EVENT,
                f"Descender {actor} shared bounded canonical Sector knowledge with Descender {target}.",
                actor_ids=[actor, target],
                location_id=location_id,
                data={
                    "protocol": PROTOCOL,
                    "target_sector_id": intent.target_sector_id,
                    "knowledge_changed": changed,
                    "knowledge_digest_before": knowledge_before,
                    "knowledge_digest_after": knowledge_after,
                    "second_hand_confidence_factor": SECOND_HAND_KNOWLEDGE_FACTOR,
                    "state_changes": {"shared_sector_knowledge": intent.target_sector_id},
                },
            )
        elif intent.action == "recruit":
            offer_id = resolved_offer_id or _stable_id("recruit_offer", descent.id, intent.proposal_id)
            offer = {
                "offer_id": offer_id,
                "source_descender_id": actor,
                "target_descender_id": target,
                "status": "pending",
                "offered_tick": descent.current_tick,
                "resolved_tick": None,
                "offered_event_id": None,
                "resolved_event_id": None,
            }
            metadata["recruitment_offers"][offer_id] = offer
            interaction = self.lifecycle.record_event(
                descent,
                RECRUITMENT_OFFERED_EVENT,
                f"Descender {actor} issued a structured recruitment offer to Descender {target}.",
                actor_ids=[actor, target],
                location_id=location_id,
                data={
                    "protocol": PROTOCOL,
                    "offer_id": offer_id,
                    "party_created": False,
                    "state_changes": {"recruitment_offer_status": "pending"},
                },
            )
            offer["offered_event_id"] = interaction.id
            offer["digest"] = payload_digest(_offer_body(offer))
            resolved_offer_id = offer_id
        elif intent.action in {"accept_recruitment", "refuse_recruitment"}:
            offer_id = resolved_offer_id or intent.recruitment_offer_id or ""
            offer = metadata["recruitment_offers"][offer_id]
            accepted = intent.action == "accept_recruitment"
            offer["status"] = "accepted" if accepted else "refused"
            offer["resolved_tick"] = descent.current_tick
            interaction = self.lifecycle.record_event(
                descent,
                RECRUITMENT_ACCEPTED_EVENT if accepted else RECRUITMENT_REFUSED_EVENT,
                (
                    f"Descender {actor} accepted a structured recruitment offer."
                    if accepted
                    else f"Descender {actor} refused a structured recruitment offer."
                ),
                actor_ids=[actor, target],
                location_id=location_id,
                data={
                    "protocol": PROTOCOL,
                    "offer_id": offer_id,
                    "party_created": False,
                    "state_changes": {"recruitment_offer_status": offer["status"]},
                },
            )
            offer["resolved_event_id"] = interaction.id
            offer["digest"] = payload_digest(_offer_body(offer))
            resolved_offer_id = offer_id
        elif intent.action == "challenge":
            interaction = self.lifecycle.record_event(
                descent,
                CHALLENGE_EVENT,
                f"Descender {actor} issued a structured challenge to Descender {target}.",
                actor_ids=[actor, target],
                location_id=location_id,
                data={
                    "protocol": PROTOCOL,
                    "combat_started": False,
                    "rivalry_mutated": False,
                    "conflict_owner_slice": "30C.5",
                    "state_changes": {"challenge_issued": True},
                },
            )
        else:
            raise SocialIntentExecutionError("accepted social intent escaped execution vocabulary")

        execution = self.lifecycle.record_event(
            descent,
            EXECUTED_EVENT,
            f"Simulation executed validated social intent {intent.action}.",
            actor_ids=[actor, target],
            location_id=location_id,
            data={
                "protocol": PROTOCOL,
                "proposal_id": intent.proposal_id,
                "provider_id": intent.provider_id,
                "action": intent.action,
                "target_descender_id": target,
                "target_item_id": intent.target_item_id,
                "target_sector_id": intent.target_sector_id,
                "recruitment_offer_id": intent.recruitment_offer_id,
                "resolved_offer_id": resolved_offer_id,
                "interaction_event_id": interaction.id,
                "memory_event_ids": list(memory_event_ids),
                "relationship_event_ids": list(relationship_event_ids),
                "state_changes": {"social_intent_executed": True},
            },
        )
        metadata["interaction_event_ids"].append(interaction.id)
        metadata["execution_event_ids"].append(execution.id)
        record = {
            "execution_index": len(metadata["interaction_records"]),
            "proposal_id": intent.proposal_id,
            "provider_id": intent.provider_id,
            "descender_id": actor,
            "target_descender_id": target,
            "action": intent.action,
            "target_item_id": intent.target_item_id,
            "target_sector_id": intent.target_sector_id,
            "recruitment_offer_id": intent.recruitment_offer_id,
            "resolved_offer_id": resolved_offer_id,
            "interaction_event_id": interaction.id,
            "execution_event_id": execution.id,
            "memory_event_ids": list(memory_event_ids),
            "relationship_event_ids": list(relationship_event_ids),
            "tick": descent.current_tick,
            "stratum_number": descent.current_floor,
        }
        record["digest"] = payload_digest(record)
        metadata["interaction_records"].append(record)
        metadata["execution_count"] = len(metadata["interaction_records"])
        self.lifecycle.save(descent)
        validate_social_intent_execution(descent)

        after_digest = _canonical_state_digest(descent)
        after_fingerprint = descent.fingerprint()
        body = {
            "protocol": RESULT_PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "proposal_id": intent.proposal_id,
            "provider_id": intent.provider_id,
            "descender_id": actor,
            "accepted": True,
            "executed": True,
            "reason_code": "executed",
            "action": intent.action,
            "target_descender_id": target,
            "target_item_id": intent.target_item_id,
            "target_sector_id": intent.target_sector_id,
            "recruitment_offer_id": intent.recruitment_offer_id,
            "resolved_offer_id": resolved_offer_id,
            "interaction_event_id": interaction.id,
            "execution_event_id": execution.id,
            "memory_event_ids": memory_event_ids,
            "relationship_event_ids": relationship_event_ids,
            "canonical_state_digest_before": before_digest,
            "canonical_state_digest_after": after_digest,
            "canonical_fingerprint_before": before_fingerprint,
            "canonical_fingerprint_after": after_fingerprint,
        }
        return SocialIntentExecutionResult(**body, result_digest=payload_digest(body))


__all__ = [
    "PROTOCOL",
    "IMPLEMENTATION_VERSION",
    "OBSERVATION_PROTOCOL",
    "INTENT_PROTOCOL",
    "DECISION_PROTOCOL",
    "RESULT_PROTOCOL",
    "METADATA_KEY",
    "ALLOWED_ACTIONS",
    "INITIALIZED_EVENT",
    "EXECUTED_EVENT",
    "WARNING_EVENT",
    "RECRUITMENT_OFFERED_EVENT",
    "RECRUITMENT_ACCEPTED_EVENT",
    "RECRUITMENT_REFUSED_EVENT",
    "CHALLENGE_EVENT",
    "SHARED_EVENT",
    "SocialIntentExecutionError",
    "SocialTargetObservation",
    "SocialObservation",
    "SocialIntent",
    "SocialIntentExecutionDecision",
    "SocialIntentExecutionResult",
    "SocialIntentExecutionService",
    "validate_social_intent_contract",
    "validate_social_intent_execution",
    "build_social_observation",
    "propose_social_intent",
    "validate_intent_for_execution",
    "build_social_intent_snapshot",
]
