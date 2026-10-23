from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.gameplay_domain import LootPolicy
from livingworld.runtime_checkpoint import AlphaCheckpointStore, canonical_json, payload_digest
from livingworld.underreach_brain_driven_descent import BrainDrivenDescentService
from livingworld.underreach_parties_alliances_leadership import (
    METADATA_KEY,
    PROTOCOL,
    PartiesAlliancesLeadershipService,
    build_parties_alliances_snapshot,
)
from livingworld.underreach_social_intent_execution import SocialIntentExecutionService
from livingworld.underreach_social_memory_evolution import SocialMemoryEvolutionService

PROOF_PROTOCOL = "underreach.parties-alliances-leadership-proof.v1"


def _stack(seed: str, ids: list[str], strata: int):
    persistence = CrawlPersistence("sqlite://")
    persistence.initialize()
    brain = BrainDrivenDescentService(persistence)
    descent = brain.create(seed=seed, descender_ids=ids, stratum_count=strata)
    brain.start(descent)
    SocialMemoryEvolutionService(persistence).initialize(descent)
    social = SocialIntentExecutionService(persistence)
    social.initialize(descent)
    parties = PartiesAlliancesLeadershipService(persistence)
    parties.initialize(descent)
    return persistence, brain, social, parties, descent


def _accept(social, descent, source: str, target: str) -> str:
    offered = social.execute(descent, social.propose(descent, source, "recruit", target_descender_id=target))
    accepted = social.execute(
        descent,
        social.propose(
            descent,
            target,
            "accept_recruitment",
            target_descender_id=source,
            recruitment_offer_id=offered.resolved_offer_id,
        ),
    )
    if not offered.executed or not accepted.executed or offered.resolved_offer_id is None:
        raise RuntimeError("30C.4 proof recruitment agreement failed")
    return offered.resolved_offer_id


def _form_pair(social, parties, descent, source: str, target: str):
    offer_id = _accept(social, descent, source, target)
    return parties.form_from_accepted_recruitment(descent, offer_id)


def _execute(seed: str, ids: list[str], strata: int):
    persistence, brain, social, parties, descent = _stack(seed, ids, strata)

    left = _form_pair(social, parties, descent, ids[0], ids[1])
    right = _form_pair(social, parties, descent, ids[3], ids[4])

    third_offer = _accept(social, descent, ids[0], ids[2])
    joined = parties.form_from_accepted_recruitment(descent, third_offer)
    if joined.party_id != left.party_id:
        raise RuntimeError("accepted third member did not join source party")

    left_party = descent.parties[left.party_id]
    for npc_id in left_party.member_npc_ids:
        agent = descent.participants[npc_id].agent
        if agent is None:
            raise RuntimeError("30C.4 proof requires canonical agent state")
        agent.skills.leadership = 0.0
        agent.skills.negotiation = 0.0
        agent.traits.sociability = 0.0
        agent.traits.loyalty = 0.0
        agent.traits.courage = 0.0
    chosen = ids[2]
    chosen_agent = descent.participants[chosen].agent
    if chosen_agent is None:
        raise RuntimeError("chosen leader has no agent state")
    chosen_agent.skills.leadership = 1.0
    chosen_agent.skills.negotiation = 1.0
    chosen_agent.traits.sociability = 1.0
    chosen_agent.traits.loyalty = 1.0
    chosen_agent.traits.courage = 1.0
    leadership = parties.elect_leader(descent, left.party_id)

    parties.set_shared_objective(descent, left.party_id, "reach_exit_together")
    parties.set_loot_policy(descent, left.party_id, LootPolicy.EQUAL_SHARE)
    parties.set_posture(descent, left.party_id, "support")

    origin = descent.participants[ids[0]].current_location_id
    if origin is None:
        raise RuntimeError("party has no canonical movement origin")
    destination = sorted(descent.floors[descent.current_floor].locations[origin].adjacency)[0]
    move = parties.coordinate_move(descent, left.party_id, destination)

    alliance = parties.form_alliance(descent, left.party_id, right.party_id)
    dissolved = parties.dissolve_alliance(descent, alliance.alliance_id, "strategic_separation")

    # Exercise ordinary leave -> leadership/membership preservation, then disband.
    departure_candidate = next(npc_id for npc_id in descent.parties[left.party_id].member_npc_ids if npc_id != chosen)
    left_result = parties.leave_party(descent, left.party_id, departure_candidate)
    remaining_party = descent.parties[left.party_id]
    disband_result = parties.leave_party(descent, left.party_id, remaining_party.member_npc_ids[0])

    snapshot = build_parties_alliances_snapshot(descent)
    events = persistence.replay_events(descent.id)
    return {
        "persistence": persistence,
        "descent": descent,
        "snapshot": snapshot,
        "event_counts": dict(sorted(Counter(event.event_type for event in events).items())),
        "left_party_id": left.party_id,
        "right_party_id": right.party_id,
        "leader_result": leadership,
        "move_result": move,
        "alliance_result": alliance,
        "dissolved_result": dissolved,
        "left_result": left_result,
        "disband_result": disband_result,
        "destination": destination,
    }


def generate(output: Path, *, seed: str, count: int, strata: int) -> dict:
    if count < 7:
        raise ValueError("30C.4 proof requires at least seven Descenders")
    ids = [f"descender_{index:03d}" for index in range(count)]
    first = _execute(seed, ids, strata)
    second = _execute(seed, ids, strata)
    descent = first["descent"]
    twin = second["descent"]

    independent_state_equal = descent.model_dump(mode="json") == twin.model_dump(mode="json")
    independent_snapshot_equal = first["snapshot"] == second["snapshot"]
    independent_event_ids_equal = descent.history_event_ids == twin.history_event_ids
    if not all((independent_state_equal, independent_snapshot_equal, independent_event_ids_equal)):
        raise RuntimeError("independent 30C.4 reproduction diverged")

    persistence = first["persistence"]
    events = persistence.replay_events(descent.id)
    store = AlphaCheckpointStore(output.parent / "checkpoint", retention=4)
    written = store.write(
        "30c4-proof-runtime",
        descent,
        events,
        simulation_config={"protocol": PROTOCOL, "slice": "30C.4"},
        reason="30c4-proof",
        created_at_unix_ms=3004001,
    )
    loaded = store.load_latest().crawl
    checkpoint_state_equal = loaded.model_dump(mode="json") == descent.model_dump(mode="json")
    checkpoint_snapshot_equal = build_parties_alliances_snapshot(loaded) == first["snapshot"]
    if not checkpoint_state_equal or not checkpoint_snapshot_equal:
        raise RuntimeError("30C.4 checkpoint restore diverged")

    metadata = descent.modifiers[METADATA_KEY]
    left_party = descent.parties[first["left_party_id"]]
    right_party = descent.parties[first["right_party_id"]]
    alliance = metadata["alliances"][first["alliance_result"].alliance_id]

    body = {
        "protocol": PROOF_PROTOCOL,
        "slice_protocol": PROTOCOL,
        "authoritative": True,
        "canonical_owner": "deterministic_simulation",
        "presentation_feedback_allowed": False,
        "betrayal_enabled": False,
        "seed": seed,
        "descent_id": descent.id,
        "population_count": count,
        "configured_stratum_count": strata,
        "consumed_recruitment_offer_count": len(metadata["consumed_recruitment_offer_ids"]),
        "total_party_count": len(descent.parties),
        "active_party_count": sum(party.active for party in descent.parties.values()),
        "left_party_active_after_disband": left_party.active,
        "right_party_active": right_party.active,
        "elected_leader_id": first["leader_result"].leader_id,
        "expected_elected_leader_id": ids[2],
        "coordinated_destination": first["destination"],
        "coordination_record_count": len(metadata["coordination_records"]),
        "alliance_status": alliance["status"],
        "alliance_dissolution_reason": alliance["dissolution_reason"],
        "alliance_betrayal_semantics": False,
        "event_type_counts": first["event_counts"],
        "final_snapshot_digest": first["snapshot"]["digest"],
        "party_digest": first["snapshot"]["party_digest"],
        "alliance_digest": first["snapshot"]["alliance_digest"],
        "coordination_trace_digest": first["snapshot"]["coordination_trace_digest"],
        "final_canonical_fingerprint": descent.fingerprint(),
        "independent_state_equal": independent_state_equal,
        "independent_snapshot_equal": independent_snapshot_equal,
        "independent_event_ids_equal": independent_event_ids_equal,
        "checkpoint_digest": written.payload["digest"],
        "checkpoint_event_count": len(events),
        "checkpoint_state_equal": checkpoint_state_equal,
        "checkpoint_snapshot_equal": checkpoint_snapshot_equal,
        "authority_contract": {
            "crawl_party_is_canonical": True,
            "accepted_recruitment_materializes_party": True,
            "accepted_offer_materializes_once": True,
            "leadership_is_deterministic": True,
            "party_policy_is_canonical": True,
            "coordinated_movement_uses_simulation_authority": True,
            "alliances_are_persistent_structured_state": True,
            "betrayal_owned_by_30c5": True,
            "presentation_can_mutate": False,
            "unreal_can_mutate": False,
            "dialogue_owner_phase": "31",
            "next_slice": "30C.5 - Rivalry, Betrayal & Social Conflict",
        },
    }
    proof = {**body, "digest": payload_digest(body)}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(canonical_json(proof) + "\n", encoding="utf-8")
    return proof


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", default="underreach-30c4-parties-proof")
    parser.add_argument("--count", type=int, default=7)
    parser.add_argument("--strata", type=int, default=3)
    args = parser.parse_args()
    proof = generate(Path(args.output), seed=args.seed, count=args.count, strata=args.strata)
    print(
        f"[30C.4] proof digest={proof['digest']} parties={proof['total_party_count']} "
        f"active={proof['active_party_count']} leader={proof['elected_leader_id']}"
    )
    print("[30C.4] Deterministic parties/alliances/leadership proof PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
