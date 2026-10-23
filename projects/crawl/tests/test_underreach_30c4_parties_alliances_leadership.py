from __future__ import annotations

from pathlib import Path

import pytest

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.gameplay_domain import LootPolicy
from livingworld.runtime_checkpoint import AlphaCheckpointStore
from livingworld.underreach_brain_driven_descent import BrainDrivenDescentService
from livingworld.underreach_parties_alliances_leadership import (
    METADATA_KEY,
    PartiesAlliancesLeadershipError,
    PartiesAlliancesLeadershipService,
    build_parties_alliances_snapshot,
    deterministic_leader,
    validate_parties_alliances_leadership,
)
from livingworld.underreach_social_intent_execution import SocialIntentExecutionService
from livingworld.underreach_social_memory_evolution import SocialMemoryEvolutionService


def _stack(seed: str = "30c4-party-test", *, count: int = 7, strata: int = 3):
    persistence = CrawlPersistence("sqlite://")
    persistence.initialize()
    brain = BrainDrivenDescentService(persistence)
    ids = [f"descender_{index:03d}" for index in range(count)]
    descent = brain.create(seed=seed, descender_ids=ids, stratum_count=strata)
    brain.start(descent)
    SocialMemoryEvolutionService(persistence).initialize(descent)
    social = SocialIntentExecutionService(persistence)
    social.initialize(descent)
    parties = PartiesAlliancesLeadershipService(persistence)
    parties.initialize(descent)
    return persistence, brain, social, parties, descent, ids


def _accept_recruitment(social, descent, source: str, target: str) -> str:
    offered = social.execute(
        descent,
        social.propose(descent, source, "recruit", target_descender_id=target),
    )
    assert offered.executed and offered.resolved_offer_id is not None
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
    assert accepted.executed
    return offered.resolved_offer_id


def _form_pair(social, parties, descent, source: str, target: str):
    offer_id = _accept_recruitment(social, descent, source, target)
    result = parties.form_from_accepted_recruitment(descent, offer_id)
    return offer_id, result


def test_accepted_recruitment_materializes_real_crawl_party() -> None:
    persistence, _, social, parties, descent, ids = _stack()
    offer_id, result = _form_pair(social, parties, descent, ids[0], ids[1])

    party = descent.parties[result.party_id]
    assert party.active
    assert party.leader_npc_id == ids[0]
    assert party.member_npc_ids == sorted(ids[:2])
    assert descent.participants[ids[0]].current_party_id == party.id
    assert descent.participants[ids[1]].current_party_id == party.id
    assert offer_id in descent.modifiers[METADATA_KEY]["consumed_recruitment_offer_ids"]
    assert validate_parties_alliances_leadership(descent)

    event = persistence.events_by_ids([result.event_id])[0]
    assert event.event_type == "SOCIAL_PARTY_FORMED"
    assert event.data["offer_id"] == offer_id


def test_one_accepted_offer_cannot_materialize_twice() -> None:
    _, _, social, parties, descent, ids = _stack(seed="30c4-offer-once")
    offer_id, _ = _form_pair(social, parties, descent, ids[0], ids[1])
    before = descent.model_dump(mode="json")
    with pytest.raises(PartiesAlliancesLeadershipError, match="already materialized"):
        parties.form_from_accepted_recruitment(descent, offer_id)
    assert descent.model_dump(mode="json") == before


def test_recruitment_can_add_member_to_existing_party() -> None:
    _, _, social, parties, descent, ids = _stack(seed="30c4-join")
    _, formed = _form_pair(social, parties, descent, ids[0], ids[1])
    second_offer = _accept_recruitment(social, descent, ids[0], ids[2])
    joined = parties.form_from_accepted_recruitment(descent, second_offer)

    assert joined.party_id == formed.party_id
    assert joined.action == "joined"
    assert descent.parties[formed.party_id].member_npc_ids == sorted(ids[:3])
    assert descent.participants[ids[2]].current_party_id == formed.party_id


def test_deterministic_leadership_election_uses_canonical_agent_capability() -> None:
    persistence, _, social, parties, descent, ids = _stack(seed="30c4-leader")
    _, formed = _form_pair(social, parties, descent, ids[0], ids[1])
    offer = _accept_recruitment(social, descent, ids[0], ids[2])
    parties.form_from_accepted_recruitment(descent, offer)
    party = descent.parties[formed.party_id]

    for npc_id in party.member_npc_ids:
        agent = descent.participants[npc_id].agent
        assert agent is not None
        agent.skills.leadership = 0.0
        agent.skills.negotiation = 0.0
        agent.traits.sociability = 0.0
        agent.traits.loyalty = 0.0
        agent.traits.courage = 0.0
    chosen = ids[2]
    agent = descent.participants[chosen].agent
    assert agent is not None
    agent.skills.leadership = 1.0
    agent.skills.negotiation = 1.0
    agent.traits.sociability = 1.0
    agent.traits.loyalty = 1.0
    agent.traits.courage = 1.0

    assert deterministic_leader(descent, party.member_npc_ids) == chosen
    result = parties.elect_leader(descent, party.id)
    assert result.leader_id == chosen
    assert party.leader_npc_id == chosen
    event = persistence.events_by_ids([result.event_id])[0]
    assert event.event_type == "SOCIAL_PARTY_LEADER_CHANGED"
    assert event.data["previous_leader_id"] == ids[0]


def test_party_policy_objective_and_coordination_posture_are_canonical() -> None:
    _, _, social, parties, descent, ids = _stack(seed="30c4-policy")
    _, formed = _form_pair(social, parties, descent, ids[0], ids[1])
    party_id = formed.party_id

    parties.set_shared_objective(descent, party_id, "reach_exit_together")
    parties.set_loot_policy(descent, party_id, LootPolicy.EQUAL_SHARE)
    parties.set_posture(descent, party_id, "support")

    party = descent.parties[party_id]
    assert party.shared_goal == "reach_exit_together"
    assert party.loot_policy == LootPolicy.EQUAL_SHARE
    assert descent.modifiers[METADATA_KEY]["party_state"][party_id]["posture"] == "support"
    assert validate_parties_alliances_leadership(descent)


def test_coordinated_move_moves_all_active_members_through_canonical_movement() -> None:
    persistence, _, social, parties, descent, ids = _stack(seed="30c4-move")
    _, formed = _form_pair(social, parties, descent, ids[0], ids[1])
    party = descent.parties[formed.party_id]
    origin = descent.participants[ids[0]].current_location_id
    assert origin is not None
    destination = sorted(descent.floors[descent.current_floor].locations[origin].adjacency)[0]

    result = parties.coordinate_move(descent, party.id, destination)

    assert all(descent.participants[npc_id].current_location_id == destination for npc_id in party.member_npc_ids)
    event = persistence.events_by_ids([result.event_id])[0]
    assert event.event_type == "SOCIAL_PARTY_COORDINATED_MOVE"
    assert event.data["origin_sector_id"] == origin
    assert event.data["destination_sector_id"] == destination
    assert len(descent.modifiers[METADATA_KEY]["coordination_records"]) == 1


def test_coordinated_move_rejects_split_party_without_mutation() -> None:
    _, brain, social, parties, descent, ids = _stack(seed="30c4-split")
    _, formed = _form_pair(social, parties, descent, ids[0], ids[1])
    origin = descent.participants[ids[1]].current_location_id
    assert origin is not None
    neighbor = sorted(descent.floors[descent.current_floor].locations[origin].adjacency)[0]
    brain.autonomous.survival.commit_descender_position(descent, ids[1], neighbor)
    before = descent.model_dump(mode="json")

    with pytest.raises(PartiesAlliancesLeadershipError, match="colocated"):
        parties.coordinate_move(descent, formed.party_id, neighbor)
    assert descent.model_dump(mode="json") == before


def test_two_parties_can_form_and_non_hostilely_dissolve_alliance() -> None:
    persistence, _, social, parties, descent, ids = _stack(seed="30c4-alliance")
    _, left = _form_pair(social, parties, descent, ids[0], ids[1])
    _, right = _form_pair(social, parties, descent, ids[2], ids[3])

    formed = parties.form_alliance(descent, left.party_id, right.party_id)
    alliance = descent.modifiers[METADATA_KEY]["alliances"][formed.alliance_id]
    assert alliance["status"] == "active"

    dissolved = parties.dissolve_alliance(descent, formed.alliance_id, "strategic_separation")
    assert dissolved.status == "dissolved"
    assert alliance["status"] == "dissolved"
    events = persistence.events_by_ids([formed.event_id, dissolved.event_id])
    assert [event.event_type for event in events] == ["SOCIAL_ALLIANCE_FORMED", "SOCIAL_ALLIANCE_DISSOLVED"]
    assert events[1].data["betrayal"] is False


def test_betrayal_labeled_alliance_dissolution_is_reserved_for_30c5() -> None:
    _, _, social, parties, descent, ids = _stack(seed="30c4-no-betrayal")
    _, left = _form_pair(social, parties, descent, ids[0], ids[1])
    _, right = _form_pair(social, parties, descent, ids[2], ids[3])
    alliance = parties.form_alliance(descent, left.party_id, right.party_id)
    before = descent.model_dump(mode="json")
    with pytest.raises(PartiesAlliancesLeadershipError, match="30C.5"):
        parties.dissolve_alliance(descent, alliance.alliance_id, "betrayal")
    assert descent.model_dump(mode="json") == before


def test_member_leave_transfers_leadership_and_two_member_party_disbands() -> None:
    _, _, social, parties, descent, ids = _stack(seed="30c4-leave")
    _, formed = _form_pair(social, parties, descent, ids[0], ids[1])
    offer = _accept_recruitment(social, descent, ids[0], ids[2])
    parties.form_from_accepted_recruitment(descent, offer)
    party = descent.parties[formed.party_id]
    leader = party.leader_npc_id

    left = parties.leave_party(descent, party.id, leader)
    assert left.action == "left"
    assert descent.participants[leader].current_party_id is None
    assert party.active and len(party.member_npc_ids) == 2
    assert party.leader_npc_id in party.member_npc_ids

    disbanded = parties.leave_party(descent, party.id, party.member_npc_ids[0])
    assert disbanded.action == "disbanded"
    assert party.active is False
    assert all(descent.participants[npc_id].current_party_id is None for npc_id in party.member_npc_ids)
    assert party.id not in descent.modifiers[METADATA_KEY]["party_state"]
    assert validate_parties_alliances_leadership(descent)


def test_persistence_checkpoint_and_independent_reproduction(tmp_path: Path) -> None:
    def run_once(seed: str):
        persistence, _, social, parties, descent, ids = _stack(seed=seed)
        _, left = _form_pair(social, parties, descent, ids[0], ids[1])
        _, right = _form_pair(social, parties, descent, ids[2], ids[3])
        parties.set_shared_objective(descent, left.party_id, "reach_exit_together")
        parties.set_posture(descent, left.party_id, "support")
        parties.form_alliance(descent, left.party_id, right.party_id)
        return persistence, parties, descent, build_parties_alliances_snapshot(descent)

    persistence, _, descent, snapshot = run_once("30c4-determinism")
    _, _, twin, twin_snapshot = run_once("30c4-determinism")
    assert descent.model_dump(mode="json") == twin.model_dump(mode="json")
    assert snapshot == twin_snapshot

    saved = persistence.load_crawl(descent.id)
    assert saved is not None
    assert saved.model_dump(mode="json") == descent.model_dump(mode="json")
    assert build_parties_alliances_snapshot(saved) == snapshot

    store = AlphaCheckpointStore(tmp_path / "checkpoint", retention=4)
    store.write(
        "30c4-test-runtime",
        descent,
        persistence.replay_events(descent.id),
        simulation_config={"slice": "30C.4"},
        reason="30c4-test",
        created_at_unix_ms=3004001,
    )
    loaded = store.load_latest().crawl
    assert loaded.model_dump(mode="json") == descent.model_dump(mode="json")
    assert build_parties_alliances_snapshot(loaded) == snapshot
