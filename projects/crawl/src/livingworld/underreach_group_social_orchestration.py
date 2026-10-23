"""Autonomous group decision and social orchestration for Underreach Slice 30C.6.

30C.6 is the Phase 30C capstone. It composes the accepted social-state, memory,
interaction, party/alliance, and conflict services into one deterministic social
orchestration cadence. The orchestrator may decide which bounded social action
to attempt, but it never bypasses the service that owns canonical mutation.

No dialogue, commentary, narration, or presentation feedback belongs here.
Those remain Phase 31+ responsibilities.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .crawl_domain import CrawlStatus, ParticipationStatus
from .crawl_persistence import CrawlPersistence
from .crawl_service import CrawlLifecycleService
from .gameplay_domain import ItemCategory
from .runtime_checkpoint import payload_digest
from .underreach_brain_driven_descent import BrainDrivenDescentService
from .underreach_domain import Descent
from .underreach_parties_alliances_leadership import (
    METADATA_KEY as PARTY_METADATA_KEY,
    PartiesAlliancesLeadershipError,
    PartiesAlliancesLeadershipService,
    build_parties_alliances_snapshot,
    deterministic_leader,
    validate_parties_alliances_leadership,
)
from .underreach_rivalry_betrayal_social_conflict import (
    RivalryBetrayalSocialConflictError,
    RivalryBetrayalSocialConflictService,
    build_rivalry_betrayal_social_conflict_snapshot,
    validate_rivalry_betrayal_social_conflict,
)
from .underreach_social_intent_execution import (
    METADATA_KEY as SOCIAL_INTENT_METADATA_KEY,
    SocialIntentExecutionService,
)
from .underreach_social_memory_evolution import SocialMemoryEvolutionService
from .underreach_social_state import build_social_state_snapshot, get_relationship


PROTOCOL = "underreach.group-social-orchestration.v1"
IMPLEMENTATION_VERSION = "30c6.1"
METADATA_KEY = "_group_social_orchestration"

INITIALIZED_EVENT = "GROUP_SOCIAL_ORCHESTRATION_INITIALIZED"
STEP_EVENT = "GROUP_SOCIAL_ORCHESTRATION_STEP_RESOLVED"

STRATEGIES = ("cooperative", "balanced", "selfish")
RECRUIT_AFFINITY_THRESHOLD = 0.37
RECRUIT_ACCEPT_THRESHOLD = 0.36
ALLIANCE_AFFINITY_THRESHOLD = 0.54
VOLUNTARY_LEAVE_THRESHOLD = 0.66
MAX_RECRUITMENTS_PER_STEP = 4
MAX_SHARES_PER_STEP = 4
MAX_CONFLICT_ATTEMPTS_PER_STEP = 4
VALUE_PRECISION = 6


class GroupSocialOrchestrationError(ValueError):
    """Raised when 30C.6 orchestration violates a canonical phase boundary."""


@dataclass(frozen=True)
class GroupSocialRunResult:
    outcome: str
    social_steps: int
    gameplay_steps: int
    current_tick: int
    active_parties: int
    active_alliances: int
    party_formations: int
    party_dissolutions: int
    leadership_changes: int
    alliance_formations: int
    hostile_conflicts: int


def _metadata(descent: Descent) -> dict[str, Any]:
    value = descent.modifiers.get(METADATA_KEY)
    if not isinstance(value, dict):
        raise GroupSocialOrchestrationError("Descent is missing 30C.6 group-social metadata")
    return value


def _record_body(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key != "digest"}


def _active_current(descent: Descent, npc_id: str) -> bool:
    participant = descent.participants.get(npc_id)
    return bool(
        participant is not None
        and participant.status == ParticipationStatus.ACTIVE
        and participant.current_floor == descent.current_floor
    )


def _active_ids(descent: Descent) -> list[str]:
    return sorted(npc_id for npc_id in descent.participants if _active_current(descent, npc_id))


def _same_sector(descent: Descent, left: str, right: str) -> bool:
    if not _active_current(descent, left) or not _active_current(descent, right):
        return False
    location = descent.participants[left].current_location_id
    return location is not None and location == descent.participants[right].current_location_id


def _agent(descent: Descent, npc_id: str):
    participant = descent.participants[npc_id]
    if participant.agent is None:
        raise GroupSocialOrchestrationError("30C.6 requires accepted deterministic crawler agent state")
    return participant.agent


def _unit(value: float) -> float:
    return round(max(0.0, min(1.0, float(value))), VALUE_PRECISION)


def _cooperation_trait(descent: Descent, npc_id: str) -> float:
    traits = _agent(descent, npc_id).traits
    return _unit(
        traits.sociability * 0.26
        + traits.empathy * 0.24
        + traits.loyalty * 0.22
        + traits.patience * 0.08
        + (1.0 - traits.suspicion) * 0.10
        + (1.0 - traits.greed) * 0.05
        + (1.0 - traits.competitiveness) * 0.05
    )


def _selfish_trait(descent: Descent, npc_id: str) -> float:
    traits = _agent(descent, npc_id).traits
    return _unit(
        traits.greed * 0.25
        + traits.competitiveness * 0.20
        + traits.suspicion * 0.18
        + (1.0 - traits.empathy) * 0.14
        + (1.0 - traits.loyalty) * 0.13
        + (1.0 - traits.sociability) * 0.10
    )


def _relationship_cooperation(descent: Descent, source: str, target: str) -> float:
    relation = get_relationship(descent, source, target)
    positive = (
        max(0.0, relation.trust) * 0.28
        + max(0.0, relation.respect) * 0.20
        + max(0.0, relation.affection) * 0.14
        + max(0.0, relation.gratitude) * 0.18
        + relation.familiarity * 0.10
    )
    negative = (
        max(0.0, relation.resentment) * 0.20
        + max(0.0, relation.rivalry) * 0.18
        + max(0.0, -relation.trust) * 0.16
    )
    return max(-1.0, min(1.0, round(positive - negative, VALUE_PRECISION)))


def strategy_for(descent: Descent, npc_id: str) -> str:
    """Classify one crawler from deterministic traits plus current party history."""
    cooperation = _cooperation_trait(descent, npc_id)
    selfish = _selfish_trait(descent, npc_id)
    party_id = descent.participants[npc_id].current_party_id
    if party_id is not None and party_id in descent.parties and descent.parties[party_id].active:
        leader_id = descent.parties[party_id].leader_npc_id
        if leader_id != npc_id:
            social = _relationship_cooperation(descent, npc_id, leader_id)
            cooperation = _unit(cooperation + max(0.0, social) * 0.20)
            selfish = _unit(selfish + max(0.0, -social) * 0.24)
    margin = round(cooperation - selfish, VALUE_PRECISION)
    if cooperation >= 0.56 and margin >= 0.08:
        return "cooperative"
    if selfish >= 0.54 and margin <= -0.06:
        return "selfish"
    return "balanced"


def _pair_affinity(descent: Descent, left: str, right: str) -> float:
    mutual_social = (
        _relationship_cooperation(descent, left, right)
        + _relationship_cooperation(descent, right, left)
    ) / 2.0
    trait_affinity = (_cooperation_trait(descent, left) + _cooperation_trait(descent, right)) / 2.0
    social_component = max(-0.25, min(0.25, mutual_social * 0.35))
    return _unit(trait_affinity * 0.78 + 0.22 + social_component)


def _recruit_acceptance(descent: Descent, source: str, target: str) -> float:
    traits = _agent(descent, target).traits
    affinity = _pair_affinity(descent, source, target)
    return _unit(
        affinity * 0.55
        + traits.sociability * 0.16
        + traits.empathy * 0.10
        + traits.loyalty * 0.09
        + (1.0 - traits.suspicion) * 0.10
    )


def _solitary_drive(descent: Descent, npc_id: str) -> float:
    traits = _agent(descent, npc_id).traits
    return _unit(
        traits.suspicion * 0.30
        + (1.0 - traits.sociability) * 0.27
        + (1.0 - traits.loyalty) * 0.23
        + traits.competitiveness * 0.12
        + traits.greed * 0.08
    )


def _relationship_adjusted_solitary_drive(descent: Descent, npc_id: str, leader_id: str) -> float:
    """Blend solitary traits with the crawler's actual bond to current leadership."""
    base = _solitary_drive(descent, npc_id)
    social = _relationship_cooperation(descent, npc_id, leader_id)
    bond_resistance = max(0.0, social) * 0.70
    conflict_pressure = max(0.0, -social) * 0.35
    return _unit(base + conflict_pressure - bond_resistance)


def _directed_conflict_pressure(descent: Descent, source: str, target: str) -> float:
    """Return bounded grievance pressure for one directed social edge."""
    relation = get_relationship(descent, source, target)
    return _unit(
        max(0.0, relation.resentment)
        + max(0.0, relation.rivalry)
        + max(0.0, -relation.trust)
    )


def _alliance_for(descent: Descent, left_party_id: str, right_party_id: str) -> dict[str, Any] | None:
    party_metadata = descent.modifiers.get(PARTY_METADATA_KEY)
    if not isinstance(party_metadata, dict):
        return None
    wanted = sorted([left_party_id, right_party_id])
    for alliance in party_metadata.get("alliances", {}).values():
        if isinstance(alliance, dict) and sorted(alliance.get("party_ids", [])) == wanted:
            return alliance
    return None


def _hostile_break_for_pair(descent: Descent, left_party_id: str, right_party_id: str) -> dict[str, Any] | None:
    """Return unresolved 30C.5 hostile-break provenance for one party pair."""
    conflict_metadata = descent.modifiers.get("_rivalry_betrayal_social_conflict")
    if not isinstance(conflict_metadata, dict):
        return None
    wanted = sorted([left_party_id, right_party_id])
    breaks = conflict_metadata.get("hostile_alliance_breaks", {})
    if not isinstance(breaks, dict):
        return None
    for record in breaks.values():
        if not isinstance(record, dict):
            continue
        pair = [record.get("source_party_id"), record.get("target_party_id")]
        if all(isinstance(value, str) for value in pair) and sorted(pair) == wanted:
            return record
    return None


def _owned_resource_ids(descent: Descent, npc_id: str) -> list[str]:
    participant = descent.participants[npc_id]
    return sorted(
        item_id
        for item_id in participant.gameplay.inventory_item_ids
        if item_id in descent.items and descent.items[item_id].category == ItemCategory.RESOURCE
    )


def validate_group_social_orchestration(descent: Descent) -> bool:
    validate_rivalry_betrayal_social_conflict(descent)
    metadata = _metadata(descent)
    if metadata.get("protocol") != PROTOCOL or metadata.get("implementation_version") != IMPLEMENTATION_VERSION:
        raise GroupSocialOrchestrationError("30C.6 protocol/version mismatch")
    if metadata.get("authoritative") is not True or metadata.get("canonical_owner") != "deterministic_simulation":
        raise GroupSocialOrchestrationError("30C.6 authority boundary changed")
    if metadata.get("extends_slice") != "30C.5":
        raise GroupSocialOrchestrationError("30C.6 source-slice boundary changed")
    if metadata.get("presentation_feedback_allowed") is not False:
        raise GroupSocialOrchestrationError("presentation cannot steer autonomous social truth")
    if metadata.get("dialogue_enabled") is not False:
        raise GroupSocialOrchestrationError("30C.6 cannot absorb Phase 31 dialogue")
    if metadata.get("random_social_actions_allowed") is not False:
        raise GroupSocialOrchestrationError("30C.6 social choices must remain deterministic")
    if metadata.get("strategies") != list(STRATEGIES):
        raise GroupSocialOrchestrationError("30C.6 strategy vocabulary changed")
    if metadata.get("initialized_event_id") not in descent.history_event_ids:
        raise GroupSocialOrchestrationError("30C.6 initialization lacks Ledger provenance")
    records = metadata.get("step_records")
    if not isinstance(records, list) or int(metadata.get("step_count", -1)) != len(records):
        raise GroupSocialOrchestrationError("30C.6 step trace/count is invalid")
    history = set(descent.history_event_ids)
    for index, record in enumerate(records):
        if record.get("step_index") != index:
            raise GroupSocialOrchestrationError("30C.6 step indices are not contiguous")
        if record.get("digest") != payload_digest(_record_body(record)):
            raise GroupSocialOrchestrationError("30C.6 step digest mismatch")
        if record.get("ledger_event_id") not in history:
            raise GroupSocialOrchestrationError("30C.6 step is not Ledger bound")
        strategies = record.get("strategies")
        if not isinstance(strategies, dict) or any(value not in STRATEGIES for value in strategies.values()):
            raise GroupSocialOrchestrationError("30C.6 step contains invalid strategy state")
        decisions = record.get("decisions")
        if not isinstance(decisions, list):
            raise GroupSocialOrchestrationError("30C.6 decision trace is invalid")
        for decision in decisions:
            if not isinstance(decision, dict) or not decision.get("decision_type"):
                raise GroupSocialOrchestrationError("30C.6 decision record is invalid")
            event_id = decision.get("event_id")
            if event_id is not None and event_id not in history:
                raise GroupSocialOrchestrationError("30C.6 decision references missing canonical event")
    metrics = metadata.get("metrics")
    required = {
        "party_formations",
        "party_joins",
        "party_dissolutions",
        "leadership_changes",
        "alliance_formations",
        "cooperative_shares",
        "conflict_attempts",
        "hostile_conflicts",
        "voluntary_leaves",
    }
    if not isinstance(metrics, dict) or not required.issubset(metrics):
        raise GroupSocialOrchestrationError("30C.6 metrics are incomplete")
    if any(int(metrics[key]) < 0 for key in required):
        raise GroupSocialOrchestrationError("30C.6 metrics cannot be negative")
    return True


def build_group_social_orchestration_snapshot(descent: Descent) -> dict[str, Any]:
    validate_group_social_orchestration(descent)
    metadata = _metadata(descent)
    records = [dict(record) for record in metadata["step_records"]]
    strategies = {npc_id: strategy_for(descent, npc_id) for npc_id in sorted(descent.participants)}
    counts = {strategy: sum(value == strategy for value in strategies.values()) for strategy in STRATEGIES}
    party_snapshot = build_parties_alliances_snapshot(descent)
    conflict_snapshot = build_rivalry_betrayal_social_conflict_snapshot(descent)
    body = {
        "protocol": PROTOCOL,
        "implementation_version": IMPLEMENTATION_VERSION,
        "authoritative": True,
        "canonical_owner": "deterministic_simulation",
        "presentation_feedback_allowed": False,
        "dialogue_enabled": False,
        "random_social_actions_allowed": False,
        "descent_id": descent.id,
        "seed": descent.seed,
        "current_tick": descent.current_tick,
        "current_stratum_number": descent.current_floor,
        "step_count": metadata["step_count"],
        "step_records": records,
        "step_trace_digest": payload_digest(records),
        "metrics": dict(sorted(metadata["metrics"].items())),
        "current_strategies": strategies,
        "strategy_counts": counts,
        "strategy_digest": payload_digest(strategies),
        "active_party_count": party_snapshot["active_party_count"],
        "active_alliance_count": party_snapshot["active_alliance_count"],
        "party_snapshot_digest": party_snapshot["digest"],
        "conflict_snapshot_digest": conflict_snapshot["digest"],
        "relationship_state_digest": build_social_state_snapshot(descent)["relationship_state_digest"],
        "history_event_ids_digest": payload_digest(list(descent.history_event_ids)),
        "canonical_descent_fingerprint": descent.fingerprint(),
        "initialized_event_id": metadata["initialized_event_id"],
    }
    return {**body, "digest": payload_digest(body)}


class GroupSocialOrchestrationService:
    """Simulation-owned deterministic social director for multiple crawlers."""

    def __init__(
        self,
        persistence: CrawlPersistence | None = None,
        *,
        brain: BrainDrivenDescentService | None = None,
    ) -> None:
        self.persistence = persistence
        self.lifecycle = CrawlLifecycleService(persistence)
        self.brain = brain or BrainDrivenDescentService(persistence)
        self.memory = SocialMemoryEvolutionService(persistence)
        self.social = SocialIntentExecutionService(persistence)
        self.parties = PartiesAlliancesLeadershipService(persistence)
        self.conflict = RivalryBetrayalSocialConflictService(persistence)

    def initialize(self, descent: Descent) -> Descent:
        if "_social_memory_evolution" not in descent.modifiers:
            self.memory.initialize(descent)
        if SOCIAL_INTENT_METADATA_KEY not in descent.modifiers:
            self.social.initialize(descent)
        if PARTY_METADATA_KEY not in descent.modifiers:
            self.parties.initialize(descent)
        if "_rivalry_betrayal_social_conflict" not in descent.modifiers:
            self.conflict.initialize(descent)
        validate_rivalry_betrayal_social_conflict(descent)
        if METADATA_KEY in descent.modifiers:
            validate_group_social_orchestration(descent)
            return descent
        metadata = {
            "protocol": PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "authoritative": True,
            "canonical_owner": "deterministic_simulation",
            "extends_slice": "30C.5",
            "presentation_feedback_allowed": False,
            "dialogue_enabled": False,
            "dialogue_owner_phase": "31",
            "random_social_actions_allowed": False,
            "strategies": list(STRATEGIES),
            "step_count": 0,
            "step_records": [],
            "metrics": {
                "party_formations": 0,
                "party_joins": 0,
                "party_dissolutions": 0,
                "leadership_changes": 0,
                "alliance_formations": 0,
                "cooperative_shares": 0,
                "conflict_attempts": 0,
                "hostile_conflicts": 0,
                "voluntary_leaves": 0,
            },
            "initialized_event_id": None,
        }
        descent.modifiers[METADATA_KEY] = metadata
        event = self.lifecycle.record_event(
            descent,
            INITIALIZED_EVENT,
            "Deterministic autonomous group-social orchestration initialized.",
            actor_ids=_active_ids(descent),
            data={
                "protocol": PROTOCOL,
                "strategies": list(STRATEGIES),
                "random_social_actions_allowed": False,
                "dialogue_enabled": False,
                "state_changes": {"group_social_orchestration_initialized": True},
            },
        )
        metadata["initialized_event_id"] = event.id
        self.lifecycle.save(descent)
        validate_group_social_orchestration(descent)
        return descent

    def _decision(
        self,
        decisions: list[dict[str, Any]],
        decision_type: str,
        *,
        actor_id: str | None = None,
        target_id: str | None = None,
        party_id: str | None = None,
        alliance_id: str | None = None,
        outcome: str,
        event_id: str | None = None,
        detail: str | None = None,
    ) -> None:
        decisions.append(
            {
                "decision_type": decision_type,
                "actor_id": actor_id,
                "target_id": target_id,
                "party_id": party_id,
                "alliance_id": alliance_id,
                "outcome": outcome,
                "event_id": event_id,
                "detail": detail,
            }
        )

    def _auto_recruit(self, descent: Descent, decisions: list[dict[str, Any]]) -> None:
        metadata = _metadata(descent)
        recruited = 0
        active = _active_ids(descent)
        candidates: list[tuple[float, str, str]] = []
        for index, left in enumerate(active):
            if descent.participants[left].current_party_id is not None:
                continue
            for right in active[index + 1 :]:
                if descent.participants[right].current_party_id is not None or not _same_sector(descent, left, right):
                    continue
                affinity = _pair_affinity(descent, left, right)
                candidates.append((affinity, left, right))
        for affinity, left, right in sorted(candidates, key=lambda value: (-value[0], value[1], value[2])):
            if recruited >= MAX_RECRUITMENTS_PER_STEP:
                break
            if descent.participants[left].current_party_id is not None or descent.participants[right].current_party_id is not None:
                continue
            if affinity < RECRUIT_AFFINITY_THRESHOLD:
                self._decision(decisions, "recruitment", actor_id=left, target_id=right, outcome="skipped", detail="affinity_below_threshold")
                continue
            left_rank = (_agent(descent, left).traits.sociability + _agent(descent, left).skills.leadership, left)
            right_rank = (_agent(descent, right).traits.sociability + _agent(descent, right).skills.leadership, right)
            source, target = (left, right) if left_rank >= right_rank else (right, left)
            try:
                offered = self.social.execute(
                    descent,
                    self.social.propose(descent, source, "recruit", target_descender_id=target),
                )
            except Exception as exc:
                self._decision(decisions, "recruitment", actor_id=source, target_id=target, outcome="error", detail=type(exc).__name__)
                continue
            if not offered.executed or offered.resolved_offer_id is None:
                self._decision(decisions, "recruitment", actor_id=source, target_id=target, outcome="rejected", detail=offered.reason_code)
                continue
            acceptance = _recruit_acceptance(descent, source, target)
            response_action = "accept_recruitment" if acceptance >= RECRUIT_ACCEPT_THRESHOLD else "refuse_recruitment"
            response = self.social.execute(
                descent,
                self.social.propose(
                    descent,
                    target,
                    response_action,
                    target_descender_id=source,
                    recruitment_offer_id=offered.resolved_offer_id,
                ),
            )
            if response_action == "accept_recruitment" and response.executed:
                materialized = self.parties.form_from_accepted_recruitment(descent, offered.resolved_offer_id)
                if materialized.action == "formed":
                    metadata["metrics"]["party_formations"] += 1
                else:
                    metadata["metrics"]["party_joins"] += 1
                recruited += 1
                self._decision(
                    decisions,
                    "recruitment",
                    actor_id=source,
                    target_id=target,
                    party_id=materialized.party_id,
                    outcome="accepted_materialized",
                    event_id=materialized.event_id,
                    detail=f"affinity={affinity:.6f};acceptance={acceptance:.6f}",
                )
            else:
                self._decision(
                    decisions,
                    "recruitment",
                    actor_id=source,
                    target_id=target,
                    outcome="refused",
                    event_id=response.interaction_event_id,
                    detail=f"acceptance={acceptance:.6f}",
                )

    def _auto_leadership_and_policy(self, descent: Descent, decisions: list[dict[str, Any]]) -> None:
        metadata = _metadata(descent)
        for party_id in sorted(descent.parties):
            party = descent.parties[party_id]
            if not party.active:
                continue
            expected = deterministic_leader(descent, party.member_npc_ids)
            if expected != party.leader_npc_id:
                changed = self.parties.elect_leader(descent, party_id)
                metadata["metrics"]["leadership_changes"] += 1
                self._decision(decisions, "leadership", actor_id=changed.leader_id, party_id=party_id, outcome="changed", event_id=changed.event_id)
            member_strategies = [strategy_for(descent, npc_id) for npc_id in party.member_npc_ids]
            cooperative = member_strategies.count("cooperative")
            selfish = member_strategies.count("selfish")
            desired_posture = "support" if cooperative > selfish else "advance"
            state = descent.modifiers[PARTY_METADATA_KEY]["party_state"].get(party_id)
            if isinstance(state, dict) and state.get("posture") != desired_posture:
                changed = self.parties.set_posture(descent, party_id, desired_posture)
                self._decision(decisions, "party_posture", party_id=party_id, outcome=desired_posture, event_id=changed.event_id)

    def _auto_share(self, descent: Descent, decisions: list[dict[str, Any]]) -> None:
        metadata = _metadata(descent)
        shares = 0
        for party_id in sorted(descent.parties):
            party = descent.parties[party_id]
            if not party.active:
                continue
            members = [npc_id for npc_id in party.member_npc_ids if _active_current(descent, npc_id)]
            for source in sorted(members):
                if shares >= MAX_SHARES_PER_STEP or strategy_for(descent, source) != "cooperative":
                    continue
                resources = _owned_resource_ids(descent, source)
                if not resources:
                    continue
                targets = [
                    target for target in sorted(members)
                    if target != source
                    and _same_sector(descent, source, target)
                    and not _owned_resource_ids(descent, target)
                ]
                if not targets:
                    continue
                target = targets[0]
                result = self.social.execute(
                    descent,
                    self.social.propose(
                        descent,
                        source,
                        "share_supply",
                        target_descender_id=target,
                        target_item_id=resources[0],
                    ),
                )
                if result.executed:
                    metadata["metrics"]["cooperative_shares"] += 1
                    shares += 1
                    self._decision(decisions, "cooperative_share", actor_id=source, target_id=target, party_id=party_id, outcome="executed", event_id=result.interaction_event_id)

    def _auto_voluntary_departures(self, descent: Descent, decisions: list[dict[str, Any]]) -> None:
        metadata = _metadata(descent)
        for party_id in sorted(list(descent.parties)):
            party = descent.parties[party_id]
            if not party.active:
                continue
            leader = party.leader_npc_id
            for npc_id in sorted(party.member_npc_ids):
                if npc_id == leader or strategy_for(descent, npc_id) != "selfish":
                    continue
                drive = _relationship_adjusted_solitary_drive(descent, npc_id, leader)
                if drive < VOLUNTARY_LEAVE_THRESHOLD:
                    continue
                result = self.parties.leave_party(descent, party_id, npc_id)
                metadata["metrics"]["voluntary_leaves"] += 1
                if result.action == "disbanded":
                    metadata["metrics"]["party_dissolutions"] += 1
                self._decision(
                    decisions,
                    "voluntary_departure",
                    actor_id=npc_id,
                    target_id=leader,
                    party_id=party_id,
                    outcome=result.action,
                    event_id=result.event_id,
                    detail=f"relationship_adjusted_drive={drive:.6f}",
                )
                break

    def _auto_alliances(self, descent: Descent, decisions: list[dict[str, Any]]) -> None:
        metadata = _metadata(descent)
        active_parties = [party for party in descent.parties.values() if party.active]
        active_parties.sort(key=lambda value: value.id)
        for index, left in enumerate(active_parties):
            for right in active_parties[index + 1 :]:
                hostile_break = _hostile_break_for_pair(descent, left.id, right.id)
                if hostile_break is not None:
                    self._decision(
                        decisions,
                        "alliance",
                        actor_id=left.leader_npc_id,
                        target_id=right.leader_npc_id,
                        alliance_id=hostile_break.get("alliance_id"),
                        outcome="skipped",
                        detail="hostile_break_unresolved",
                    )
                    continue
                existing = _alliance_for(descent, left.id, right.id)
                if isinstance(existing, dict) and existing.get("status") == "active":
                    continue
                affinity = _pair_affinity(descent, left.leader_npc_id, right.leader_npc_id)
                if affinity < ALLIANCE_AFFINITY_THRESHOLD:
                    continue
                try:
                    formed = self.parties.form_alliance(descent, left.id, right.id)
                except PartiesAlliancesLeadershipError:
                    continue
                metadata["metrics"]["alliance_formations"] += 1
                self._decision(decisions, "alliance", actor_id=left.leader_npc_id, target_id=right.leader_npc_id, alliance_id=formed.alliance_id, outcome="formed", event_id=formed.event_id, detail=f"affinity={affinity:.6f}")

    def _auto_conflict(self, descent: Descent, decisions: list[dict[str, Any]]) -> None:
        metadata = _metadata(descent)
        attempts = 0
        for party_id in sorted(descent.parties):
            party = descent.parties[party_id]
            if not party.active:
                continue
            leader = party.leader_npc_id
            for npc_id in sorted(party.member_npc_ids):
                if attempts >= MAX_CONFLICT_ATTEMPTS_PER_STEP or npc_id == leader:
                    continue
                pressure = _directed_conflict_pressure(descent, npc_id, leader)
                if pressure < 0.22:
                    continue
                attempts += 1
                metadata["metrics"]["conflict_attempts"] += 1
                action = "betray_party" if pressure >= 0.58 and strategy_for(descent, npc_id) == "selfish" else "abandon_party"
                try:
                    result = self.conflict.execute(
                        descent,
                        self.conflict.propose(
                            descent,
                            npc_id,
                            leader,
                            action,
                            incentive_code="survival" if action == "abandon_party" else "revenge",
                            incentive_strength=max(0.45, pressure),
                            provider_id="group-social-orchestrator-v1",
                        ),
                    )
                except (RivalryBetrayalSocialConflictError, KeyError):
                    continue
                if result.executed:
                    metadata["metrics"]["hostile_conflicts"] += 1
                    if not descent.parties[party_id].active:
                        metadata["metrics"]["party_dissolutions"] += 1
                    self._decision(decisions, "party_conflict", actor_id=npc_id, target_id=leader, party_id=party_id, outcome=action, event_id=result.source_event_id, detail=f"score={result.conflict_score:.6f}")
                else:
                    self._decision(decisions, "party_conflict", actor_id=npc_id, target_id=leader, party_id=party_id, outcome="rejected", detail=result.reason_code)

        party_metadata = descent.modifiers.get(PARTY_METADATA_KEY)
        if not isinstance(party_metadata, dict):
            return
        for alliance_id, alliance in sorted(list(party_metadata.get("alliances", {}).items())):
            if attempts >= MAX_CONFLICT_ATTEMPTS_PER_STEP or not isinstance(alliance, dict) or alliance.get("status") != "active":
                continue
            left_id, right_id = alliance["party_ids"]
            left = descent.parties[left_id]
            right = descent.parties[right_id]
            left_leader = left.leader_npc_id
            right_leader = right.leader_npc_id
            candidates = [
                (_directed_conflict_pressure(descent, left_leader, right_leader), left_leader, right_leader),
                (_directed_conflict_pressure(descent, right_leader, left_leader), right_leader, left_leader),
            ]
            pressure, source, target = sorted(candidates, key=lambda value: (-value[0], value[1], value[2]))[0]
            if pressure < 0.28:
                continue
            attempts += 1
            metadata["metrics"]["conflict_attempts"] += 1
            try:
                result = self.conflict.execute(
                    descent,
                    self.conflict.propose(
                        descent,
                        source,
                        target,
                        "break_alliance",
                        incentive_code="leadership",
                        incentive_strength=max(0.55, pressure),
                        alliance_id=alliance_id,
                        provider_id="group-social-orchestrator-v1",
                    ),
                )
            except (RivalryBetrayalSocialConflictError, KeyError):
                continue
            if result.executed:
                metadata["metrics"]["hostile_conflicts"] += 1
                self._decision(decisions, "alliance_conflict", actor_id=source, target_id=target, alliance_id=alliance_id, outcome="broken", event_id=result.source_event_id, detail=f"score={result.conflict_score:.6f};directed_pressure={pressure:.6f}")
            else:
                self._decision(decisions, "alliance_conflict", actor_id=source, target_id=target, alliance_id=alliance_id, outcome="rejected", detail=f"{result.reason_code};directed_pressure={pressure:.6f}")

    def step(self, descent: Descent) -> dict[str, Any]:
        validate_group_social_orchestration(descent)
        if descent.status != CrawlStatus.RUNNING:
            raise GroupSocialOrchestrationError("30C.6 social step requires a running Descent")
        metadata = _metadata(descent)
        step_index = int(metadata["step_count"])
        strategies = {npc_id: strategy_for(descent, npc_id) for npc_id in _active_ids(descent)}
        decisions: list[dict[str, Any]] = []
        self._auto_recruit(descent, decisions)
        self._auto_conflict(descent, decisions)
        self._auto_leadership_and_policy(descent, decisions)
        self._auto_share(descent, decisions)
        self._auto_voluntary_departures(descent, decisions)
        self._auto_alliances(descent, decisions)
        party_snapshot = build_parties_alliances_snapshot(descent)
        conflict_snapshot = build_rivalry_betrayal_social_conflict_snapshot(descent)
        record = {
            "step_index": step_index,
            "tick": descent.current_tick,
            "stratum_number": descent.current_floor,
            "strategies": strategies,
            "strategy_counts": {strategy: sum(value == strategy for value in strategies.values()) for strategy in STRATEGIES},
            "decisions": decisions,
            "active_party_count": party_snapshot["active_party_count"],
            "active_alliance_count": party_snapshot["active_alliance_count"],
            "party_snapshot_digest": party_snapshot["digest"],
            "conflict_snapshot_digest": conflict_snapshot["digest"],
        }
        record["digest"] = payload_digest(record)
        event = self.lifecycle.record_event(
            descent,
            STEP_EVENT,
            f"Autonomous group-social orchestration step {step_index} resolved deterministically.",
            actor_ids=_active_ids(descent),
            data={
                "protocol": PROTOCOL,
                "step_index": step_index,
                "step_digest": record["digest"],
                "decision_count": len(decisions),
                "active_party_count": party_snapshot["active_party_count"],
                "active_alliance_count": party_snapshot["active_alliance_count"],
                "state_changes": {"group_social_step_resolved": step_index},
            },
        )
        record["ledger_event_id"] = event.id
        record["digest"] = payload_digest(_record_body(record))
        metadata["step_records"].append(record)
        metadata["step_count"] = step_index + 1
        self.lifecycle.save(descent)
        validate_group_social_orchestration(descent)
        return record

    def run(self, descent: Descent, *, max_gameplay_steps: int = 64) -> GroupSocialRunResult:
        validate_group_social_orchestration(descent)
        gameplay_steps = 0
        while descent.status == CrawlStatus.RUNNING and gameplay_steps < max_gameplay_steps:
            self.step(descent)
            brain_metadata = descent.modifiers.get("_brain_driven_descent")
            if not isinstance(brain_metadata, dict) or brain_metadata.get("run_outcome") != "running":
                break
            self.brain.step(descent)
            gameplay_steps += 1
            if brain_metadata.get("run_outcome") in {"completed", "extinguished"}:
                break
        metadata = _metadata(descent)
        party_snapshot = build_parties_alliances_snapshot(descent)
        outcome = str(descent.modifiers.get("_brain_driven_descent", {}).get("run_outcome", descent.status.value))
        return GroupSocialRunResult(
            outcome=outcome,
            social_steps=int(metadata["step_count"]),
            gameplay_steps=gameplay_steps,
            current_tick=descent.current_tick,
            active_parties=int(party_snapshot["active_party_count"]),
            active_alliances=int(party_snapshot["active_alliance_count"]),
            party_formations=int(metadata["metrics"]["party_formations"]),
            party_dissolutions=int(metadata["metrics"]["party_dissolutions"]),
            leadership_changes=int(metadata["metrics"]["leadership_changes"]),
            alliance_formations=int(metadata["metrics"]["alliance_formations"]),
            hostile_conflicts=int(metadata["metrics"]["hostile_conflicts"]),
        )


__all__ = [
    "PROTOCOL",
    "IMPLEMENTATION_VERSION",
    "METADATA_KEY",
    "STRATEGIES",
    "GroupSocialOrchestrationError",
    "GroupSocialRunResult",
    "GroupSocialOrchestrationService",
    "strategy_for",
    "validate_group_social_orchestration",
    "build_group_social_orchestration_snapshot",
]
