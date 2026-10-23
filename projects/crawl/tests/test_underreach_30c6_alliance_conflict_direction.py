from __future__ import annotations

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.underreach_brain_driven_descent import BrainDrivenDescentService
from livingworld.underreach_group_social_orchestration import GroupSocialOrchestrationService
from livingworld.underreach_parties_alliances_leadership import PartiesAlliancesLeadershipService
from livingworld.underreach_rivalry_betrayal_social_conflict import RivalryBetrayalSocialConflictService
from livingworld.underreach_social_intent_execution import SocialIntentExecutionService
from livingworld.underreach_social_memory_evolution import SocialMemoryEvolutionService
from livingworld.underreach_social_state import SocialStateService


def _accepted_offer(social: SocialIntentExecutionService, descent, source: str, target: str) -> str:
    offered = social.execute(descent, social.propose(descent, source, "recruit", target_descender_id=target))
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


def _seed_directed_grievance(state, memory, descent, source: str, target: str) -> None:
    relation = state.get(descent, source, target)
    for dimension, target_value in {
        "trust": -0.95,
        "respect": -0.75,
        "resentment": 0.92,
        "rivalry": 0.90,
        "familiarity": 0.82,
    }.items():
        current = float(getattr(relation, dimension))
        delta = round(target_value - current, 6)
        if delta:
            state.adjust_dimension(
                descent,
                source,
                target,
                dimension,
                delta,
                reason_code="30c6.test_directed_alliance_grievance",
            )
            relation = state.get(descent, source, target)

    for event_type in ("PROMISE_VIOLATED", "LOOT_STOLEN"):
        event = memory.lifecycle.record_event(
            descent,
            event_type,
            f"30C.6 directed alliance grievance {event_type}.",
            actor_ids=[target, source],
            location_id=descent.participants[source].current_location_id,
            data={"state_changes": {"30c6_directed_alliance_grievance": event_type}},
        )
        memory.lifecycle.save(descent)
        processed = memory.process_event(descent, event)
        assert processed.processed


def test_alliance_conflict_uses_more_aggrieved_directed_leader_edge() -> None:
    persistence = CrawlPersistence("sqlite://")
    persistence.initialize()
    brain = BrainDrivenDescentService(persistence)
    ids = [f"descender_{index:03d}" for index in range(4)]
    descent = brain.create(seed="30c6-directed-alliance-conflict", descender_ids=ids, stratum_count=3)
    brain.start(descent)

    memory = SocialMemoryEvolutionService(persistence)
    memory.initialize(descent)
    social = SocialIntentExecutionService(persistence)
    social.initialize(descent)
    parties = PartiesAlliancesLeadershipService(persistence)
    parties.initialize(descent)
    conflict = RivalryBetrayalSocialConflictService(persistence)
    conflict.initialize(descent)
    orchestration = GroupSocialOrchestrationService(persistence, brain=brain)
    orchestration.initialize(descent)
    state = SocialStateService(persistence)

    first_party = parties.form_from_accepted_recruitment(
        descent, _accepted_offer(social, descent, ids[0], ids[1])
    ).party_id
    second_party = parties.form_from_accepted_recruitment(
        descent, _accepted_offer(social, descent, ids[2], ids[3])
    ).party_id
    alliance = parties.form_alliance(descent, first_party, second_party)

    lower_party_id, higher_party_id = sorted([first_party, second_party])
    target = descent.parties[lower_party_id].leader_npc_id
    source = descent.parties[higher_party_id].leader_npc_id
    _seed_directed_grievance(state, memory, descent, source, target)

    record = orchestration.step(descent)

    party_metadata = descent.modifiers["_parties_alliances_leadership"]
    conflict_metadata = descent.modifiers["_rivalry_betrayal_social_conflict"]
    assert alliance.alliance_id not in party_metadata["alliances"]
    assert alliance.alliance_id in conflict_metadata["hostile_alliance_breaks"]
    decisions = [
        item for item in record["decisions"]
        if item["decision_type"] == "alliance_conflict" and item["alliance_id"] == alliance.alliance_id
    ]
    assert decisions
    assert decisions[0]["actor_id"] == source
    assert decisions[0]["target_id"] == target
    assert decisions[0]["outcome"] == "broken"
