"""Deterministic validation/execution bridge for Underreach Slice 30B.2.

30B.1 made brain output advisory-only. This slice is the authority membrane
between an advisory ``BrainIntent`` and canonical gameplay state. A provider
still cannot mutate a Descent. The simulation independently rebuilds the
current observation, validates the proposal, previews execution on a cloned
Descent, and only then performs accepted canonical operations.

Rejected or stale proposals are side-effect free. Accepted execution is bound
to the structured Ledger with a ``BRAIN_INTENT_EXECUTED`` event. Time cadence,
encounter orchestration, cache opening, group/social reasoning, and model-backed
providers remain outside this slice.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .crawl_domain import CrawlStatus, ParticipationStatus
from .crawler_decision import CrawlerDecision
from .crawler_navigation import choose_destination, perceive
from .runtime_checkpoint import payload_digest
from .underreach_ai_brain_foundation import (
    AIBrainFoundationError,
    AIBrainFoundationService,
    BrainIntent,
    BrainObservation,
    build_brain_observation,
    validate_brain_intent,
)
from .underreach_domain import Descent
from .underreach_full_autonomous_descent import _movement_cost
from .underreach_resources_survival import (
    ResourcesSurvivalService,
    validate_resources_survival,
)


PROTOCOL = "underreach.brain-intent-execution.v1"
IMPLEMENTATION_VERSION = "30b2.1"
DECISION_PROTOCOL = "underreach.brain-intent-execution-decision.v1"
RESULT_PROTOCOL = "underreach.brain-intent-execution-result.v1"


class BrainIntentExecutionError(ValueError):
    """Raised when the deterministic execution membrane itself is misused."""


class BrainIntentExecutionDecision(BaseModel):
    """Immutable, side-effect-free simulation decision about one proposal."""

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
    origin_sector_id: str | None = None
    resolved_sector_id: str | None = None
    target_item_id: str | None = None
    decision_digest: str


class BrainIntentExecutionResult(BaseModel):
    """Canonical result returned after an accepted intent is executed."""

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
    origin_sector_id: str | None = None
    resolved_sector_id: str | None = None
    target_item_id: str | None = None
    source_event_ids: tuple[str, ...] = ()
    execution_event_id: str | None = None
    canonical_state_digest_before: str
    canonical_state_digest_after: str
    canonical_fingerprint_before: str
    canonical_fingerprint_after: str
    result_digest: str


def _canonical_state_digest(descent: Descent) -> str:
    return payload_digest(descent.model_dump(mode="json"))


def _stable_id(prefix: str, *parts: object) -> str:
    payload = ":".join(str(part) for part in parts)
    return f"{prefix}_{sha256(payload.encode('utf-8')).hexdigest()[:20]}"


def _current_cache(descent: Descent) -> dict[str, Any] | None:
    loot = descent.modifiers.get("_loot_cache_relic")
    if not isinstance(loot, dict):
        return None
    caches = [
        cache
        for cache in loot.get("caches", [])
        if int(cache.get("stratum_number", 0)) == descent.current_floor
    ]
    return min(caches, key=lambda value: value.get("cache_id", "")) if caches else None


def _known_path(descent: Descent, descender_id: str, target_sector_id: str) -> list[str] | None:
    participant = descent.participants[descender_id]
    if participant.agent is None or participant.current_location_id is None:
        return None
    start = participant.current_location_id
    if target_sector_id == start:
        return [start]
    frontier: list[tuple[float, str, list[str]]] = [(0.0, start, [start])]
    best: dict[str, float] = {start: 0.0}
    while frontier:
        frontier.sort(key=lambda value: (value[0], value[1], tuple(value[2])))
        cost, current, path = frontier.pop(0)
        if current == target_sector_id:
            return path
        knowledge = participant.agent.knowledge.get(current)
        if knowledge is None:
            continue
        for neighbor, edge_cost in sorted(knowledge.known_neighbors.items()):
            candidate = cost + float(edge_cost)
            if candidate >= best.get(neighbor, float("inf")):
                continue
            best[neighbor] = candidate
            frontier.append((candidate, neighbor, [*path, neighbor]))
    return None


def _semantic_rejection(
    descent: Descent,
    observation: BrainObservation,
    intent: BrainIntent,
) -> str | None:
    """Tighten 30B.1 proposal shape into deterministic execution legality."""
    participant = descent.participants.get(intent.descender_id)
    if descent.status != CrawlStatus.RUNNING:
        return "descent_not_running"
    if participant is None:
        return "descender_missing"
    if participant.status != ParticipationStatus.ACTIVE or participant.current_floor != descent.current_floor:
        return "descender_not_active_current_stratum"
    if participant.current_location_id != observation.current_sector_id:
        return "observation_location_mismatch"

    target = intent.target_sector_id
    if intent.action == "explore" and target is not None:
        if target not in observation.known_neighbor_sector_ids:
            return "explore_target_not_known_neighbor"
    elif intent.action == "seek_exit" and target is not None:
        if target not in observation.known_exit_sector_ids:
            return "seek_exit_target_not_known_exit"
    elif intent.action == "seek_safety" and target is not None:
        if target not in observation.known_safe_sector_ids:
            return "seek_safety_target_not_known_safe_area"
    elif intent.action == "seek_cache" and target is not None:
        # 30B.1 intentionally does not expose the cache Sector ID. Keep that
        # information boundary intact instead of allowing target guessing.
        return "seek_cache_cannot_target_sector"

    if intent.action == "consume_supply":
        item = descent.items.get(intent.target_item_id or "")
        if item is None:
            return "supply_item_missing"
        if item.owner_npc_id != intent.descender_id:
            return "supply_item_not_owned"
    if intent.action == "recover" and not observation.at_safe_area:
        return "recover_requires_safe_area"
    return None


def _resolve_navigation_on_clone(
    descent: Descent,
    intent: BrainIntent,
) -> tuple[str, str]:
    """Preview canonical navigation on a cloned Descent only."""
    clone = Descent.model_validate(descent.model_dump(mode="python"))
    participant = clone.participants[intent.descender_id]
    if participant.current_location_id is None or participant.agent is None:
        raise BrainIntentExecutionError("navigation requires canonical location and agent state")
    floor = clone.floors[clone.current_floor]
    origin = participant.current_location_id

    # Perception is canonical mutable knowledge, so preview it only on the clone.
    perceive(participant, floor, clone.current_tick)

    if intent.target_sector_id is not None:
        path = _known_path(clone, intent.descender_id, intent.target_sector_id)
        if not path:
            raise BrainIntentExecutionError("target Sector is not reachable through known navigation state")
        return origin, path[1] if len(path) > 1 else origin

    if intent.action == "seek_cache":
        cache = _current_cache(clone)
        if cache is not None and isinstance(cache.get("sector_id"), str):
            cache_sector = cache["sector_id"]
            if cache_sector in participant.agent.knowledge:
                path = _known_path(clone, intent.descender_id, cache_sector)
                if path:
                    return origin, path[1] if len(path) > 1 else origin
        decision = CrawlerDecision("explore", 1.0, {"brain_seek_cache_search": 1.0})
    elif intent.action == "seek_exit":
        decision = CrawlerDecision("seek_exit", 1.0, {"brain_seek_exit": 1.0})
    elif intent.action == "seek_safety":
        decision = CrawlerDecision("seek_safety", 1.0, {"brain_seek_safety": 1.0})
    elif intent.action == "explore":
        decision = CrawlerDecision("explore", 1.0, {"brain_explore": 1.0})
    else:
        raise BrainIntentExecutionError(f"{intent.action!r} is not a navigation intent")

    destination = choose_destination(participant, floor, decision)
    return origin, destination or origin


def _build_decision(
    descent: Descent,
    observation: BrainObservation,
    intent: BrainIntent,
    *,
    accepted: bool,
    reason_code: str,
    origin_sector_id: str | None = None,
    resolved_sector_id: str | None = None,
) -> BrainIntentExecutionDecision:
    canonical_digest = _canonical_state_digest(descent)
    body = {
        "protocol": DECISION_PROTOCOL,
        "implementation_version": IMPLEMENTATION_VERSION,
        "proposal_id": intent.proposal_id,
        "provider_id": intent.provider_id,
        "descender_id": intent.descender_id,
        "observation_digest": observation.observation_digest,
        "canonical_state_digest": canonical_digest,
        "accepted": accepted,
        "reason_code": reason_code,
        "action": intent.action,
        "origin_sector_id": origin_sector_id,
        "resolved_sector_id": resolved_sector_id,
        "target_item_id": intent.target_item_id,
    }
    return BrainIntentExecutionDecision(**body, decision_digest=payload_digest(body))


def validate_intent_for_execution(
    descent: Descent,
    intent: BrainIntent,
) -> BrainIntentExecutionDecision:
    """Evaluate one proposal without mutating canonical state."""
    validate_resources_survival(descent)
    before_digest = _canonical_state_digest(descent)
    before_fingerprint = descent.fingerprint()
    before_history = tuple(descent.history_event_ids)

    try:
        observation = build_brain_observation(descent, intent.descender_id)
    except (AIBrainFoundationError, KeyError) as exc:
        # No valid current observation means execution cannot proceed. Construct
        # a minimal immutable surrogate only for the deterministic rejection.
        reason = "current_observation_unavailable"
        if _canonical_state_digest(descent) != before_digest or descent.fingerprint() != before_fingerprint:
            raise BrainIntentExecutionError("observation failure mutated canonical state") from exc
        if tuple(descent.history_event_ids) != before_history:
            raise BrainIntentExecutionError("observation failure appended Ledger state") from exc
        body = {
            "protocol": DECISION_PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "proposal_id": intent.proposal_id,
            "provider_id": intent.provider_id,
            "descender_id": intent.descender_id,
            "observation_digest": intent.observation_digest,
            "canonical_state_digest": before_digest,
            "accepted": False,
            "reason_code": reason,
            "action": intent.action,
            "origin_sector_id": None,
            "resolved_sector_id": None,
            "target_item_id": intent.target_item_id,
        }
        return BrainIntentExecutionDecision(**body, decision_digest=payload_digest(body))

    if intent.observation_digest != observation.observation_digest:
        decision = _build_decision(
            descent,
            observation,
            intent,
            accepted=False,
            reason_code="stale_observation",
            origin_sector_id=observation.current_sector_id,
        )
    else:
        try:
            validate_brain_intent(intent, observation)
        except (AIBrainFoundationError, ValueError):
            decision = _build_decision(
                descent,
                observation,
                intent,
                accepted=False,
                reason_code="brain_intent_contract_rejected",
                origin_sector_id=observation.current_sector_id,
            )
        else:
            rejection = _semantic_rejection(descent, observation, intent)
            if rejection is not None:
                decision = _build_decision(
                    descent,
                    observation,
                    intent,
                    accepted=False,
                    reason_code=rejection,
                    origin_sector_id=observation.current_sector_id,
                )
            elif intent.action in {"explore", "seek_cache", "seek_exit", "seek_safety"}:
                try:
                    origin, destination = _resolve_navigation_on_clone(descent, intent)
                except BrainIntentExecutionError:
                    decision = _build_decision(
                        descent,
                        observation,
                        intent,
                        accepted=False,
                        reason_code="navigation_unresolvable",
                        origin_sector_id=observation.current_sector_id,
                    )
                else:
                    decision = _build_decision(
                        descent,
                        observation,
                        intent,
                        accepted=True,
                        reason_code="accepted",
                        origin_sector_id=origin,
                        resolved_sector_id=destination,
                    )
            else:
                decision = _build_decision(
                    descent,
                    observation,
                    intent,
                    accepted=True,
                    reason_code="accepted",
                    origin_sector_id=observation.current_sector_id,
                    resolved_sector_id=observation.current_sector_id,
                )

    if _canonical_state_digest(descent) != before_digest:
        raise BrainIntentExecutionError("intent validation mutated canonical Descent state")
    if descent.fingerprint() != before_fingerprint:
        raise BrainIntentExecutionError("intent validation mutated canonical Descent fingerprint")
    if tuple(descent.history_event_ids) != before_history:
        raise BrainIntentExecutionError("intent validation appended canonical Ledger state")
    return decision


class BrainIntentExecutionService:
    """Simulation-owned executor for accepted 30B.1 advisory proposals."""

    def __init__(
        self,
        *,
        brain: AIBrainFoundationService | None = None,
        survival: ResourcesSurvivalService | None = None,
    ) -> None:
        self.brain = brain or AIBrainFoundationService()
        self.survival = survival or ResourcesSurvivalService()
        self.lifecycle = self.survival.lifecycle

    def validate(self, descent: Descent, intent: BrainIntent) -> BrainIntentExecutionDecision:
        return validate_intent_for_execution(descent, intent)

    def propose_and_execute(self, descent: Descent, descender_id: str) -> BrainIntentExecutionResult:
        intent = self.brain.propose(descent, descender_id)
        return self.execute(descent, intent)

    def execute(self, descent: Descent, intent: BrainIntent) -> BrainIntentExecutionResult:
        """Execute an accepted proposal through canonical simulation operations.

        Rejected proposals return a deterministic result without mutating the
        Descent or its Ledger.
        """
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
                "origin_sector_id": decision.origin_sector_id,
                "resolved_sector_id": decision.resolved_sector_id,
                "target_item_id": intent.target_item_id,
                "source_event_ids": (),
                "execution_event_id": None,
                "canonical_state_digest_before": before_digest,
                "canonical_state_digest_after": before_digest,
                "canonical_fingerprint_before": before_fingerprint,
                "canonical_fingerprint_after": before_fingerprint,
            }
            result = BrainIntentExecutionResult(**body, result_digest=payload_digest(body))
            if _canonical_state_digest(descent) != before_digest or descent.fingerprint() != before_fingerprint:
                raise BrainIntentExecutionError("rejected intent mutated canonical state")
            if tuple(descent.history_event_ids) != before_history:
                raise BrainIntentExecutionError("rejected intent mutated canonical Ledger")
            return result

        source_event_ids: list[str] = []
        origin = decision.origin_sector_id
        resolved = decision.resolved_sector_id

        if intent.action in {"explore", "seek_cache", "seek_exit", "seek_safety"}:
            participant = descent.participants[intent.descender_id]
            if participant.agent is None or participant.current_location_id is None:
                raise BrainIntentExecutionError("accepted navigation lost canonical agent/location state")
            floor = descent.floors[descent.current_floor]

            # Repeat the preview resolution on real state. The plan must match
            # before any position commit is allowed.
            perceive(participant, floor, descent.current_tick)
            actual_origin = participant.current_location_id
            if intent.target_sector_id is not None:
                path = _known_path(descent, intent.descender_id, intent.target_sector_id)
                actual_destination = path[1] if path and len(path) > 1 else actual_origin
            elif intent.action == "seek_cache":
                cache = _current_cache(descent)
                actual_destination = None
                if cache is not None and isinstance(cache.get("sector_id"), str):
                    cache_sector = cache["sector_id"]
                    if cache_sector in participant.agent.knowledge:
                        path = _known_path(descent, intent.descender_id, cache_sector)
                        if path:
                            actual_destination = path[1] if len(path) > 1 else actual_origin
                if actual_destination is None:
                    actual_destination = choose_destination(
                        participant,
                        floor,
                        CrawlerDecision("explore", 1.0, {"brain_seek_cache_search": 1.0}),
                    ) or actual_origin
            else:
                action_map = {
                    "explore": "explore",
                    "seek_exit": "seek_exit",
                    "seek_safety": "seek_safety",
                }
                actual_destination = choose_destination(
                    participant,
                    floor,
                    CrawlerDecision(action_map[intent.action], 1.0, {f"brain_{intent.action}": 1.0}),
                ) or actual_origin

            if actual_origin != origin or actual_destination != resolved:
                raise BrainIntentExecutionError("real navigation resolution diverged from deterministic preview")
            if resolved is not None and resolved != actual_origin:
                event_count = len(descent.history_event_ids)
                self.survival.commit_descender_position(descent, intent.descender_id, resolved)
                if len(descent.history_event_ids) > event_count:
                    source_event_ids.extend(descent.history_event_ids[event_count:])
                _movement_cost(descent, intent.descender_id, actual_origin, resolved)
                self.lifecycle.save(descent)
        elif intent.action == "consume_supply":
            event_count = len(descent.history_event_ids)
            self.survival.consume_supply_item(descent, intent.target_item_id or "", intent.descender_id)
            source_event_ids.extend(descent.history_event_ids[event_count:])
        elif intent.action == "recover":
            event_count = len(descent.history_event_ids)
            self.survival.recover_at_safe_area(descent, intent.descender_id)
            source_event_ids.extend(descent.history_event_ids[event_count:])
        elif intent.action == "wait":
            pass
        else:
            raise BrainIntentExecutionError("accepted intent escaped deterministic execution vocabulary")

        validate_resources_survival(descent)
        execution_event = self.lifecycle.record_event(
            descent,
            "BRAIN_INTENT_EXECUTED",
            f"Simulation executed validated brain intent {intent.action}.",
            actor_ids=[intent.descender_id],
            location_id=descent.participants[intent.descender_id].current_location_id,
            data={
                "protocol": PROTOCOL,
                "proposal_id": intent.proposal_id,
                "provider_id": intent.provider_id,
                "observation_digest": intent.observation_digest,
                "decision_digest": decision.decision_digest,
                "action": intent.action,
                "origin_sector_id": origin,
                "resolved_sector_id": resolved,
                "target_item_id": intent.target_item_id,
                "source_event_ids": list(source_event_ids),
                "state_changes": {
                    "brain_intent_executed": True,
                    "resolved_sector_id": resolved,
                },
            },
        )
        self.lifecycle.save(descent)
        validate_resources_survival(descent)

        after_digest = _canonical_state_digest(descent)
        after_fingerprint = descent.fingerprint()
        body = {
            "protocol": RESULT_PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "proposal_id": intent.proposal_id,
            "provider_id": intent.provider_id,
            "descender_id": intent.descender_id,
            "accepted": True,
            "executed": True,
            "reason_code": "executed",
            "action": intent.action,
            "origin_sector_id": origin,
            "resolved_sector_id": resolved,
            "target_item_id": intent.target_item_id,
            "source_event_ids": tuple(source_event_ids),
            "execution_event_id": execution_event.id,
            "canonical_state_digest_before": before_digest,
            "canonical_state_digest_after": after_digest,
            "canonical_fingerprint_before": before_fingerprint,
            "canonical_fingerprint_after": after_fingerprint,
        }
        return BrainIntentExecutionResult(**body, result_digest=payload_digest(body))
