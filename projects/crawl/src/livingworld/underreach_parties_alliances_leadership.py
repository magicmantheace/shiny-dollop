"""Canonical parties, alliances, and leadership for Underreach Slice 30C.4.

30C.3 established bounded social interactions and accepted recruitment offers.
30C.4 materializes those accepted agreements into persistent CrawlParty state,
adds deterministic leadership transitions, party policies/objectives, bounded
alliance state, and coordinated group movement. Rivalry, betrayal, revenge, and
hostile alliance-breaking remain 30C.5 responsibilities.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any

from pydantic import BaseModel, ConfigDict

from .crawl_domain import ParticipationStatus
from .crawl_persistence import CrawlPersistence
from .crawl_service import CrawlLifecycleService
from .gameplay_domain import CrawlParty, LootPolicy
from .runtime_checkpoint import payload_digest
from .underreach_domain import Descent
from .underreach_resources_survival import ResourcesSurvivalService
from .underreach_social_intent_execution import (
    METADATA_KEY as SOCIAL_INTENT_METADATA_KEY,
    validate_social_intent_execution,
)

PROTOCOL = "underreach.parties-alliances-leadership.v1"
IMPLEMENTATION_VERSION = "30c4.1"
METADATA_KEY = "_parties_alliances_leadership"

INITIALIZED_EVENT = "SOCIAL_PARTY_SYSTEM_INITIALIZED"
PARTY_FORMED_EVENT = "SOCIAL_PARTY_FORMED"
PARTY_MEMBER_JOINED_EVENT = "SOCIAL_PARTY_MEMBER_JOINED"
PARTY_MEMBER_LEFT_EVENT = "SOCIAL_PARTY_MEMBER_LEFT"
PARTY_DISBANDED_EVENT = "SOCIAL_PARTY_DISBANDED"
PARTY_LEADER_CHANGED_EVENT = "SOCIAL_PARTY_LEADER_CHANGED"
PARTY_OBJECTIVE_CHANGED_EVENT = "SOCIAL_PARTY_OBJECTIVE_CHANGED"
PARTY_LOOT_POLICY_CHANGED_EVENT = "SOCIAL_PARTY_LOOT_POLICY_CHANGED"
PARTY_POSTURE_CHANGED_EVENT = "SOCIAL_PARTY_POSTURE_CHANGED"
PARTY_COORDINATED_MOVE_EVENT = "SOCIAL_PARTY_COORDINATED_MOVE"
ALLIANCE_FORMED_EVENT = "SOCIAL_ALLIANCE_FORMED"
ALLIANCE_DISSOLVED_EVENT = "SOCIAL_ALLIANCE_DISSOLVED"

POSTURES = ("advance", "hold", "support", "retreat", "focus_fire")
ALLIANCE_STATUSES = ("active", "dissolved")
NON_HOSTILE_DISSOLUTION_REASONS = ("strategic_separation", "party_disbanded", "crawl_transition")


class PartiesAlliancesLeadershipError(ValueError):
    pass


class PartyMutationResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    party_id: str
    event_id: str
    member_ids: tuple[str, ...]
    leader_id: str
    action: str


class AllianceMutationResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    alliance_id: str
    event_id: str
    party_ids: tuple[str, str]
    status: str


def _stable_id(prefix: str, *parts: object) -> str:
    payload = ":".join(str(part) for part in parts)
    return f"{prefix}_{sha256(payload.encode('utf-8')).hexdigest()[:20]}"


def _metadata(descent: Descent) -> dict[str, Any]:
    value = descent.modifiers.get(METADATA_KEY)
    if not isinstance(value, dict):
        raise PartiesAlliancesLeadershipError("Descent is missing 30C.4 party metadata")
    return value


def _social_intent_metadata(descent: Descent) -> dict[str, Any]:
    value = descent.modifiers.get(SOCIAL_INTENT_METADATA_KEY)
    if not isinstance(value, dict):
        raise PartiesAlliancesLeadershipError("30C.4 requires accepted 30C.3 social-intent state")
    return value


def _active_member(descent: Descent, npc_id: str) -> bool:
    participant = descent.participants.get(npc_id)
    return bool(
        participant is not None
        and participant.status == ParticipationStatus.ACTIVE
        and participant.current_floor == descent.current_floor
    )


def _leadership_score(descent: Descent, npc_id: str) -> tuple[float, str]:
    participant = descent.participants[npc_id]
    agent = participant.agent
    if agent is None:
        return (0.0, npc_id)
    score = (
        float(agent.skills.leadership) * 0.50
        + float(agent.skills.negotiation) * 0.20
        + float(agent.traits.sociability) * 0.10
        + float(agent.traits.loyalty) * 0.10
        + float(agent.traits.courage) * 0.10
    )
    return (round(score, 8), npc_id)


def deterministic_leader(descent: Descent, member_ids: list[str] | tuple[str, ...]) -> str:
    candidates = [npc_id for npc_id in sorted(member_ids) if _active_member(descent, npc_id)]
    if not candidates:
        candidates = sorted(member_ids)
    if not candidates:
        raise PartiesAlliancesLeadershipError("cannot elect leader for an empty party")
    return max(candidates, key=lambda npc_id: (_leadership_score(descent, npc_id)[0], npc_id))


def _active_party(descent: Descent, party_id: str) -> CrawlParty:
    party = descent.parties.get(party_id)
    if party is None or not party.active:
        raise PartiesAlliancesLeadershipError("party must exist and be active")
    return party


def _alliance_body(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key != "digest"}


def _record_body(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key != "digest"}


def validate_parties_alliances_leadership(descent: Descent) -> bool:
    validate_social_intent_execution(descent)
    Descent.model_validate(descent.model_dump(mode="python"))
    metadata = _metadata(descent)
    if metadata.get("protocol") != PROTOCOL or metadata.get("implementation_version") != IMPLEMENTATION_VERSION:
        raise PartiesAlliancesLeadershipError("30C.4 protocol/version mismatch")
    if metadata.get("authoritative") is not True or metadata.get("canonical_owner") != "deterministic_simulation":
        raise PartiesAlliancesLeadershipError("party authority boundary changed")
    if metadata.get("extends_slice") != "30C.3":
        raise PartiesAlliancesLeadershipError("30C.4 source-slice boundary changed")
    if metadata.get("presentation_feedback_allowed") is not False:
        raise PartiesAlliancesLeadershipError("presentation cannot mutate party truth")
    if metadata.get("betrayal_enabled") is not False:
        raise PartiesAlliancesLeadershipError("betrayal belongs to 30C.5")
    initialized = metadata.get("initialized_event_id")
    if initialized not in descent.history_event_ids:
        raise PartiesAlliancesLeadershipError("party system initialization is not Ledger bound")

    consumed = metadata.get("consumed_recruitment_offer_ids")
    if not isinstance(consumed, list) or len(consumed) != len(set(consumed)):
        raise PartiesAlliancesLeadershipError("consumed recruitment offer trace is invalid")
    offers = _social_intent_metadata(descent).get("recruitment_offers", {})
    for offer_id in consumed:
        offer = offers.get(offer_id)
        if not isinstance(offer, dict) or offer.get("status") != "accepted":
            raise PartiesAlliancesLeadershipError("30C.4 consumed a non-accepted recruitment offer")

    party_state = metadata.get("party_state")
    if not isinstance(party_state, dict):
        raise PartiesAlliancesLeadershipError("party state metadata is invalid")
    active_party_ids = {party_id for party_id, party in descent.parties.items() if party.active}
    if set(party_state) != active_party_ids:
        raise PartiesAlliancesLeadershipError("30C.4 active party metadata diverged from Crawl.parties")
    for party_id in sorted(active_party_ids):
        party = descent.parties[party_id]
        state = party_state[party_id]
        if len(party.member_npc_ids) < 2:
            raise PartiesAlliancesLeadershipError("active social party must contain at least two members")
        if party.leader_npc_id not in party.member_npc_ids:
            raise PartiesAlliancesLeadershipError("party leader must remain a member")
        if state.get("posture") not in POSTURES:
            raise PartiesAlliancesLeadershipError("party coordination posture escaped bounded vocabulary")
        if state.get("formed_event_id") not in descent.history_event_ids:
            raise PartiesAlliancesLeadershipError("party formation lacks Ledger provenance")
        if state.get("leader_event_ids") is None or state.get("movement_event_ids") is None:
            raise PartiesAlliancesLeadershipError("party provenance lists are missing")
        for key in ("leader_event_ids", "membership_event_ids", "policy_event_ids", "movement_event_ids"):
            values = state.get(key)
            if not isinstance(values, list) or len(values) != len(set(values)):
                raise PartiesAlliancesLeadershipError("party provenance list is invalid")
            if any(event_id not in descent.history_event_ids for event_id in values):
                raise PartiesAlliancesLeadershipError("party provenance references missing Ledger event")

    alliances = metadata.get("alliances")
    if not isinstance(alliances, dict):
        raise PartiesAlliancesLeadershipError("alliance storage is invalid")
    for alliance_id, alliance in alliances.items():
        if alliance.get("alliance_id") != alliance_id or alliance.get("status") not in ALLIANCE_STATUSES:
            raise PartiesAlliancesLeadershipError("alliance identity/status is invalid")
        party_ids = alliance.get("party_ids")
        if not isinstance(party_ids, list) or len(party_ids) != 2 or party_ids != sorted(set(party_ids)):
            raise PartiesAlliancesLeadershipError("alliance must reference exactly two canonical parties")
        if any(party_id not in descent.parties for party_id in party_ids):
            raise PartiesAlliancesLeadershipError("alliance references missing party")
        if alliance.get("formed_event_id") not in descent.history_event_ids:
            raise PartiesAlliancesLeadershipError("alliance formation lacks Ledger provenance")
        if alliance["status"] == "active":
            if not all(descent.parties[party_id].active for party_id in party_ids):
                raise PartiesAlliancesLeadershipError("active alliance cannot contain inactive party")
            if alliance.get("dissolved_event_id") is not None:
                raise PartiesAlliancesLeadershipError("active alliance has dissolution provenance")
        else:
            if alliance.get("dissolution_reason") not in NON_HOSTILE_DISSOLUTION_REASONS:
                raise PartiesAlliancesLeadershipError("30C.4 alliance dissolution cannot encode betrayal")
            if alliance.get("dissolved_event_id") not in descent.history_event_ids:
                raise PartiesAlliancesLeadershipError("dissolved alliance lacks Ledger provenance")
        if alliance.get("digest") != payload_digest(_alliance_body(alliance)):
            raise PartiesAlliancesLeadershipError("alliance digest mismatch")

    records = metadata.get("coordination_records")
    if not isinstance(records, list):
        raise PartiesAlliancesLeadershipError("coordination trace is invalid")
    for index, record in enumerate(records):
        if record.get("index") != index or record.get("digest") != payload_digest(_record_body(record)):
            raise PartiesAlliancesLeadershipError("coordination trace digest/index mismatch")
        if record.get("event_id") not in descent.history_event_ids:
            raise PartiesAlliancesLeadershipError("coordination record is not Ledger bound")
    return True


def build_parties_alliances_snapshot(descent: Descent) -> dict[str, Any]:
    validate_parties_alliances_leadership(descent)
    metadata = _metadata(descent)
    parties = [descent.parties[party_id].model_dump(mode="json") for party_id in sorted(descent.parties)]
    alliances = [dict(metadata["alliances"][alliance_id]) for alliance_id in sorted(metadata["alliances"])]
    records = [dict(value) for value in metadata["coordination_records"]]
    body = {
        "protocol": PROTOCOL,
        "implementation_version": IMPLEMENTATION_VERSION,
        "authoritative": True,
        "canonical_owner": "deterministic_simulation",
        "presentation_feedback_allowed": False,
        "betrayal_enabled": False,
        "descent_id": descent.id,
        "current_tick": descent.current_tick,
        "current_stratum_number": descent.current_floor,
        "parties": parties,
        "party_digest": payload_digest(parties),
        "active_party_count": sum(party.active for party in descent.parties.values()),
        "alliances": alliances,
        "alliance_digest": payload_digest(alliances),
        "active_alliance_count": sum(value["status"] == "active" for value in alliances),
        "consumed_recruitment_offer_ids": list(metadata["consumed_recruitment_offer_ids"]),
        "coordination_records": records,
        "coordination_trace_digest": payload_digest(records),
        "history_event_ids_digest": payload_digest(list(descent.history_event_ids)),
        "canonical_descent_fingerprint": descent.fingerprint(),
    }
    return {**body, "digest": payload_digest(body)}


class PartiesAlliancesLeadershipService:
    def __init__(self, persistence: CrawlPersistence | None = None) -> None:
        self.persistence = persistence
        self.lifecycle = CrawlLifecycleService(persistence)
        self.survival = ResourcesSurvivalService(persistence)

    def initialize(self, descent: Descent) -> Descent:
        validate_social_intent_execution(descent)
        if METADATA_KEY in descent.modifiers:
            validate_parties_alliances_leadership(descent)
            return descent
        metadata = {
            "protocol": PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "authoritative": True,
            "canonical_owner": "deterministic_simulation",
            "extends_slice": "30C.3",
            "presentation_feedback_allowed": False,
            "betrayal_enabled": False,
            "social_conflict_owner_slice": "30C.5",
            "consumed_recruitment_offer_ids": [],
            "party_state": {},
            "alliances": {},
            "coordination_records": [],
            "initialized_event_id": None,
        }
        descent.modifiers[METADATA_KEY] = metadata
        event = self.lifecycle.record_event(
            descent,
            INITIALIZED_EVENT,
            "Canonical party, alliance, and leadership authority initialized.",
            actor_ids=sorted(descent.participants),
            data={"protocol": PROTOCOL, "betrayal_enabled": False, "state_changes": {"party_system_initialized": True}},
        )
        metadata["initialized_event_id"] = event.id
        self.lifecycle.save(descent)
        validate_parties_alliances_leadership(descent)
        return descent

    def form_from_accepted_recruitment(self, descent: Descent, offer_id: str) -> PartyMutationResult:
        validate_parties_alliances_leadership(descent)
        metadata = _metadata(descent)
        if offer_id in metadata["consumed_recruitment_offer_ids"]:
            raise PartiesAlliancesLeadershipError("accepted recruitment offer was already materialized")
        offer = _social_intent_metadata(descent)["recruitment_offers"].get(offer_id)
        if not isinstance(offer, dict) or offer.get("status") != "accepted":
            raise PartiesAlliancesLeadershipError("party formation requires an accepted 30C.3 recruitment offer")
        source = str(offer["source_descender_id"])
        target = str(offer["target_descender_id"])
        if not _active_member(descent, source) or not _active_member(descent, target):
            raise PartiesAlliancesLeadershipError("recruitment materialization requires active current-Stratum members")
        source_party_id = descent.participants[source].current_party_id
        target_party_id = descent.participants[target].current_party_id
        if target_party_id is not None:
            raise PartiesAlliancesLeadershipError("recruitment target is already in a party")

        if source_party_id is None:
            party_id = _stable_id("party", descent.id, offer_id, source, target)
            members = sorted([source, target])
            party = CrawlParty(
                id=party_id,
                leader_npc_id=source,
                member_npc_ids=members,
                loot_policy=LootPolicy.NEED_BEFORE_GREED,
                cohesion=0.5,
                formed_tick=descent.current_tick,
                active=True,
                shared_goal="survive",
                disagreement=0.0,
            )
            descent.parties[party_id] = party
            for npc_id in members:
                descent.participants[npc_id].current_party_id = party_id
            event_type = PARTY_FORMED_EVENT
            action = "formed"
        else:
            party = _active_party(descent, source_party_id)
            party_id = party.id
            party.member_npc_ids = sorted([*party.member_npc_ids, target])
            descent.participants[target].current_party_id = party_id
            event_type = PARTY_MEMBER_JOINED_EVENT
            action = "joined"

        event = self.lifecycle.record_event(
            descent,
            event_type,
            "Accepted recruitment materialized into canonical party membership.",
            actor_ids=sorted([source, target]),
            location_id=descent.participants[source].current_location_id,
            data={
                "protocol": PROTOCOL,
                "party_id": party_id,
                "offer_id": offer_id,
                "source_descender_id": source,
                "target_descender_id": target,
                "member_ids": list(party.member_npc_ids),
                "leader_id": party.leader_npc_id,
                "state_changes": {"party_membership_materialized": True},
            },
        )
        metadata["consumed_recruitment_offer_ids"].append(offer_id)
        if action == "formed":
            metadata["party_state"][party_id] = {
                "formed_event_id": event.id,
                "source_offer_ids": [offer_id],
                "posture": "advance",
                "leader_event_ids": [],
                "membership_event_ids": [event.id],
                "policy_event_ids": [],
                "movement_event_ids": [],
            }
        else:
            state = metadata["party_state"][party_id]
            state["source_offer_ids"].append(offer_id)
            state["membership_event_ids"].append(event.id)
        self.lifecycle.save(descent)
        validate_parties_alliances_leadership(descent)
        return PartyMutationResult(party_id=party_id, event_id=event.id, member_ids=tuple(party.member_npc_ids), leader_id=party.leader_npc_id, action=action)

    def elect_leader(self, descent: Descent, party_id: str) -> PartyMutationResult:
        validate_parties_alliances_leadership(descent)
        party = _active_party(descent, party_id)
        selected = deterministic_leader(descent, party.member_npc_ids)
        previous = party.leader_npc_id
        if selected == previous:
            raise PartiesAlliancesLeadershipError("deterministic leadership election produced no transition")
        party.leader_npc_id = selected
        event = self.lifecycle.record_event(
            descent,
            PARTY_LEADER_CHANGED_EVENT,
            "Party leadership changed by deterministic member capability election.",
            actor_ids=sorted(party.member_npc_ids),
            data={
                "protocol": PROTOCOL,
                "party_id": party_id,
                "previous_leader_id": previous,
                "leader_id": selected,
                "leadership_scores": {npc_id: _leadership_score(descent, npc_id)[0] for npc_id in sorted(party.member_npc_ids)},
                "state_changes": {"party_leader_id": selected},
            },
        )
        _metadata(descent)["party_state"][party_id]["leader_event_ids"].append(event.id)
        self.lifecycle.save(descent)
        validate_parties_alliances_leadership(descent)
        return PartyMutationResult(party_id=party_id, event_id=event.id, member_ids=tuple(party.member_npc_ids), leader_id=selected, action="leader_changed")

    def set_shared_objective(self, descent: Descent, party_id: str, objective: str) -> PartyMutationResult:
        validate_parties_alliances_leadership(descent)
        party = _active_party(descent, party_id)
        value = str(objective).strip()
        if not value or len(value) > 64 or any(ch in value for ch in "\r\n"):
            raise PartiesAlliancesLeadershipError("party objective must be a bounded structured label")
        previous = party.shared_goal
        if previous == value:
            raise PartiesAlliancesLeadershipError("party objective is already set")
        party.shared_goal = value
        event = self.lifecycle.record_event(
            descent,
            PARTY_OBJECTIVE_CHANGED_EVENT,
            "Party shared objective changed.",
            actor_ids=list(party.member_npc_ids),
            data={"protocol": PROTOCOL, "party_id": party_id, "previous_objective": previous, "objective": value, "state_changes": {"party_shared_goal": value}},
        )
        _metadata(descent)["party_state"][party_id]["policy_event_ids"].append(event.id)
        self.lifecycle.save(descent)
        validate_parties_alliances_leadership(descent)
        return PartyMutationResult(party_id=party_id, event_id=event.id, member_ids=tuple(party.member_npc_ids), leader_id=party.leader_npc_id, action="objective_changed")

    def set_loot_policy(self, descent: Descent, party_id: str, policy: LootPolicy | str) -> PartyMutationResult:
        validate_parties_alliances_leadership(descent)
        party = _active_party(descent, party_id)
        try:
            value = policy if isinstance(policy, LootPolicy) else LootPolicy(str(policy))
        except ValueError as exc:
            raise PartiesAlliancesLeadershipError("unknown canonical party loot policy") from exc
        previous = party.loot_policy
        if previous == value:
            raise PartiesAlliancesLeadershipError("party loot policy is already set")
        party.loot_policy = value
        event = self.lifecycle.record_event(
            descent,
            PARTY_LOOT_POLICY_CHANGED_EVENT,
            "Party loot-sharing policy changed.",
            actor_ids=list(party.member_npc_ids),
            data={"protocol": PROTOCOL, "party_id": party_id, "previous_policy": previous.value, "loot_policy": value.value, "state_changes": {"party_loot_policy": value.value}},
        )
        _metadata(descent)["party_state"][party_id]["policy_event_ids"].append(event.id)
        self.lifecycle.save(descent)
        validate_parties_alliances_leadership(descent)
        return PartyMutationResult(party_id=party_id, event_id=event.id, member_ids=tuple(party.member_npc_ids), leader_id=party.leader_npc_id, action="loot_policy_changed")

    def set_posture(self, descent: Descent, party_id: str, posture: str) -> PartyMutationResult:
        validate_parties_alliances_leadership(descent)
        party = _active_party(descent, party_id)
        if posture not in POSTURES:
            raise PartiesAlliancesLeadershipError("party posture escaped bounded coordination vocabulary")
        state = _metadata(descent)["party_state"][party_id]
        previous = state["posture"]
        if previous == posture:
            raise PartiesAlliancesLeadershipError("party posture is already set")
        state["posture"] = posture
        event = self.lifecycle.record_event(
            descent,
            PARTY_POSTURE_CHANGED_EVENT,
            "Party coordination posture changed.",
            actor_ids=list(party.member_npc_ids),
            data={"protocol": PROTOCOL, "party_id": party_id, "previous_posture": previous, "posture": posture, "combat_resolution_changed": False, "state_changes": {"party_posture": posture}},
        )
        state["policy_event_ids"].append(event.id)
        self.lifecycle.save(descent)
        validate_parties_alliances_leadership(descent)
        return PartyMutationResult(party_id=party_id, event_id=event.id, member_ids=tuple(party.member_npc_ids), leader_id=party.leader_npc_id, action="posture_changed")

    def coordinate_move(self, descent: Descent, party_id: str, destination_sector_id: str) -> PartyMutationResult:
        validate_parties_alliances_leadership(descent)
        party = _active_party(descent, party_id)
        members = [npc_id for npc_id in party.member_npc_ids if _active_member(descent, npc_id)]
        if len(members) < 2:
            raise PartiesAlliancesLeadershipError("coordinated movement requires at least two active members")
        origins = {descent.participants[npc_id].current_location_id for npc_id in members}
        if len(origins) != 1 or None in origins:
            raise PartiesAlliancesLeadershipError("party members must be colocated for coordinated movement")
        origin = next(iter(origins))
        floor = descent.floors[descent.current_floor]
        if destination_sector_id not in floor.locations[origin].adjacency:
            raise PartiesAlliancesLeadershipError("coordinated destination must be adjacent to party origin")
        for npc_id in sorted(members):
            self.survival.commit_descender_position(descent, npc_id, destination_sector_id)
        event = self.lifecycle.record_event(
            descent,
            PARTY_COORDINATED_MOVE_EVENT,
            "Party executed one deterministic coordinated movement step.",
            actor_ids=sorted(members),
            location_id=destination_sector_id,
            data={"protocol": PROTOCOL, "party_id": party_id, "origin_sector_id": origin, "destination_sector_id": destination_sector_id, "posture": _metadata(descent)["party_state"][party_id]["posture"], "state_changes": {"party_sector_id": destination_sector_id}},
        )
        state = _metadata(descent)["party_state"][party_id]
        state["movement_event_ids"].append(event.id)
        record = {"index": len(_metadata(descent)["coordination_records"]), "party_id": party_id, "action": "move", "origin_sector_id": origin, "destination_sector_id": destination_sector_id, "posture": state["posture"], "event_id": event.id, "tick": descent.current_tick}
        record["digest"] = payload_digest(record)
        _metadata(descent)["coordination_records"].append(record)
        self.lifecycle.save(descent)
        validate_parties_alliances_leadership(descent)
        return PartyMutationResult(party_id=party_id, event_id=event.id, member_ids=tuple(party.member_npc_ids), leader_id=party.leader_npc_id, action="coordinated_move")

    def form_alliance(self, descent: Descent, left_party_id: str, right_party_id: str) -> AllianceMutationResult:
        validate_parties_alliances_leadership(descent)
        if left_party_id == right_party_id:
            raise PartiesAlliancesLeadershipError("party cannot ally with itself")
        left = _active_party(descent, left_party_id)
        right = _active_party(descent, right_party_id)
        party_ids = sorted([left.id, right.id])
        alliance_id = _stable_id("alliance", descent.id, *party_ids)
        existing = _metadata(descent)["alliances"].get(alliance_id)
        if isinstance(existing, dict) and existing.get("status") == "active":
            raise PartiesAlliancesLeadershipError("alliance is already active")
        event = self.lifecycle.record_event(
            descent,
            ALLIANCE_FORMED_EVENT,
            "Two canonical parties formed a bounded cooperative alliance.",
            actor_ids=sorted([left.leader_npc_id, right.leader_npc_id]),
            data={"protocol": PROTOCOL, "alliance_id": alliance_id, "party_ids": party_ids, "hostile": False, "state_changes": {"alliance_status": "active"}},
        )
        alliance = {"alliance_id": alliance_id, "party_ids": party_ids, "status": "active", "formed_tick": descent.current_tick, "formed_event_id": event.id, "dissolved_tick": None, "dissolved_event_id": None, "dissolution_reason": None}
        alliance["digest"] = payload_digest(alliance)
        _metadata(descent)["alliances"][alliance_id] = alliance
        self.lifecycle.save(descent)
        validate_parties_alliances_leadership(descent)
        return AllianceMutationResult(alliance_id=alliance_id, event_id=event.id, party_ids=(party_ids[0], party_ids[1]), status="active")

    def dissolve_alliance(self, descent: Descent, alliance_id: str, reason: str = "strategic_separation") -> AllianceMutationResult:
        validate_parties_alliances_leadership(descent)
        if reason not in NON_HOSTILE_DISSOLUTION_REASONS:
            raise PartiesAlliancesLeadershipError("hostile/betrayal alliance dissolution belongs to 30C.5")
        alliance = _metadata(descent)["alliances"].get(alliance_id)
        if not isinstance(alliance, dict) or alliance.get("status") != "active":
            raise PartiesAlliancesLeadershipError("alliance must exist and be active")
        event = self.lifecycle.record_event(
            descent,
            ALLIANCE_DISSOLVED_EVENT,
            "Alliance ended without betrayal or hostile social conflict.",
            actor_ids=sorted(descent.parties[party_id].leader_npc_id for party_id in alliance["party_ids"] if party_id in descent.parties),
            data={"protocol": PROTOCOL, "alliance_id": alliance_id, "party_ids": alliance["party_ids"], "reason": reason, "betrayal": False, "state_changes": {"alliance_status": "dissolved"}},
        )
        alliance["status"] = "dissolved"
        alliance["dissolved_tick"] = descent.current_tick
        alliance["dissolved_event_id"] = event.id
        alliance["dissolution_reason"] = reason
        alliance["digest"] = payload_digest(_alliance_body(alliance))
        self.lifecycle.save(descent)
        validate_parties_alliances_leadership(descent)
        party_ids = tuple(alliance["party_ids"])
        return AllianceMutationResult(alliance_id=alliance_id, event_id=event.id, party_ids=(party_ids[0], party_ids[1]), status="dissolved")

    def leave_party(self, descent: Descent, party_id: str, npc_id: str) -> PartyMutationResult:
        validate_parties_alliances_leadership(descent)
        party = _active_party(descent, party_id)
        if npc_id not in party.member_npc_ids:
            raise PartiesAlliancesLeadershipError("Descender is not a party member")
        if len(party.member_npc_ids) <= 2:
            former_members = list(party.member_npc_ids)
            # Active alliances must be dissolved while both parties are still
            # active. Otherwise dissolve_alliance's validator correctly rejects
            # the transient invalid state of an active alliance containing an
            # already-inactive party.
            for alliance_id, alliance in list(_metadata(descent)["alliances"].items()):
                if alliance["status"] == "active" and party_id in alliance["party_ids"]:
                    self.dissolve_alliance(descent, alliance_id, reason="party_disbanded")
            party.active = False
            for member_id in former_members:
                descent.participants[member_id].current_party_id = None
            event = self.lifecycle.record_event(
                descent,
                PARTY_DISBANDED_EVENT,
                "Party disbanded after membership fell below the active-party minimum.",
                actor_ids=sorted(former_members),
                data={"protocol": PROTOCOL, "party_id": party_id, "departing_descender_id": npc_id, "state_changes": {"party_active": False}},
            )
            del _metadata(descent)["party_state"][party_id]
            self.lifecycle.save(descent)
            validate_parties_alliances_leadership(descent)
            return PartyMutationResult(party_id=party_id, event_id=event.id, member_ids=tuple(former_members), leader_id=party.leader_npc_id, action="disbanded")

        previous_leader = party.leader_npc_id
        party.member_npc_ids = sorted(member for member in party.member_npc_ids if member != npc_id)
        descent.participants[npc_id].current_party_id = None
        if previous_leader == npc_id:
            party.leader_npc_id = deterministic_leader(descent, party.member_npc_ids)
        event = self.lifecycle.record_event(
            descent,
            PARTY_MEMBER_LEFT_EVENT,
            "Descender left canonical party membership.",
            actor_ids=sorted([npc_id, *party.member_npc_ids]),
            data={"protocol": PROTOCOL, "party_id": party_id, "departing_descender_id": npc_id, "member_ids": list(party.member_npc_ids), "leader_id": party.leader_npc_id, "state_changes": {"party_member_left": npc_id}},
        )
        state = _metadata(descent)["party_state"][party_id]
        state["membership_event_ids"].append(event.id)
        if previous_leader != party.leader_npc_id:
            leader_event = self.lifecycle.record_event(
                descent,
                PARTY_LEADER_CHANGED_EVENT,
                "Party leadership transferred after leader departure.",
                actor_ids=list(party.member_npc_ids),
                data={"protocol": PROTOCOL, "party_id": party_id, "previous_leader_id": previous_leader, "leader_id": party.leader_npc_id, "state_changes": {"party_leader_id": party.leader_npc_id}},
            )
            state["leader_event_ids"].append(leader_event.id)
        self.lifecycle.save(descent)
        validate_parties_alliances_leadership(descent)
        return PartyMutationResult(party_id=party_id, event_id=event.id, member_ids=tuple(party.member_npc_ids), leader_id=party.leader_npc_id, action="left")


__all__ = [
    "PROTOCOL", "IMPLEMENTATION_VERSION", "METADATA_KEY", "POSTURES",
    "PartiesAlliancesLeadershipError", "PartyMutationResult", "AllianceMutationResult",
    "PartiesAlliancesLeadershipService", "deterministic_leader",
    "validate_parties_alliances_leadership", "build_parties_alliances_snapshot",
]
