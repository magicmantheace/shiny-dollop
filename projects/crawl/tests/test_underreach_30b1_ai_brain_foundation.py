from __future__ import annotations

import pytest

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.runtime_checkpoint import payload_digest
from livingworld.underreach_ai_brain_foundation import (
    ALLOWED_ACTIONS,
    INTENT_PROTOCOL,
    AIBrainFoundationError,
    AIBrainFoundationService,
    BrainIntent,
    DeterministicReferenceBrain,
    build_brain_observation,
    validate_brain_intent,
)
from livingworld.underreach_full_autonomous_descent import FullAutonomousDescentService


SEED = "underreach-30b1-ai-brain-foundation-test"
IDS = [f"descender_{index:03d}" for index in range(8)]


def _descent():
    persistence = CrawlPersistence("sqlite://")
    persistence.initialize()
    runner = FullAutonomousDescentService(persistence)
    descent = runner.create(seed=SEED, descender_ids=IDS, stratum_count=3)
    runner.start(descent)
    return runner, descent


def test_observation_is_deterministic_and_epistemically_bounded():
    _, descent = _descent()
    service = AIBrainFoundationService()
    left = service.observe(descent, IDS[0])
    right = service.observe(descent, IDS[0])
    assert left == right
    assert left.observation_digest == right.observation_digest
    assert left.descender_id == IDS[0]
    assert left.current_sector_id == descent.participants[IDS[0]].current_location_id
    assert set(left.known_neighbor_sector_ids).issubset(
        descent.floors[descent.current_floor].locations[left.current_sector_id].adjacency
    )
    assert not hasattr(left, "all_sector_ids")
    assert not hasattr(left, "hidden_sector_ids")
    assert not hasattr(left, "encounter_outcomes")


def test_reference_brain_proposal_is_advisory_and_does_not_mutate_canonical_state():
    _, descent = _descent()
    service = AIBrainFoundationService(DeterministicReferenceBrain())
    before = descent.model_dump(mode="json")
    before_history = list(descent.history_event_ids)
    intent = service.propose(descent, IDS[0])
    assert intent.protocol == INTENT_PROTOCOL
    assert intent.action in ALLOWED_ACTIONS
    assert intent.descender_id == IDS[0]
    assert descent.model_dump(mode="json") == before
    assert descent.history_event_ids == before_history


def test_proposal_bundle_is_reproducible_and_non_authoritative():
    _, descent = _descent()
    service = AIBrainFoundationService()
    before = descent.model_dump(mode="json")
    left = service.proposal_bundle(descent)
    right = service.proposal_bundle(descent)
    assert left == right
    assert left["authoritative"] is False
    assert left["advisory_only"] is True
    assert left["simulation_execution_required"] is True
    assert len(left["proposals"]) == len(IDS)
    assert left["digest"] == payload_digest({key: value for key, value in left.items() if key != "digest"})
    assert descent.model_dump(mode="json") == before


def test_intent_cannot_target_unknown_sector():
    _, descent = _descent()
    observation = build_brain_observation(descent, IDS[0])
    intent = BrainIntent(
        provider_id="test-provider",
        proposal_id="proposal-unknown-sector",
        descender_id=IDS[0],
        observation_digest=observation.observation_digest,
        action="explore",
        target_sector_id="definitely-not-observed",
        confidence=0.5,
        reason_codes=("test",),
    )
    with pytest.raises(AIBrainFoundationError, match="outside observed knowledge"):
        validate_brain_intent(intent, observation)


def test_consume_supply_requires_owned_observed_supply():
    _, descent = _descent()
    observation = build_brain_observation(descent, IDS[0])
    with pytest.raises(AIBrainFoundationError, match="does not own"):
        validate_brain_intent(
            BrainIntent(
                provider_id="test-provider",
                proposal_id="proposal-foreign-item",
                descender_id=IDS[0],
                observation_digest=observation.observation_digest,
                action="consume_supply",
                target_item_id="foreign-supply",
                confidence=0.8,
                reason_codes=("test",),
            ),
            observation,
        )


def test_recover_intent_requires_actual_safe_area_observation():
    _, descent = _descent()
    observation = build_brain_observation(descent, IDS[0])
    if observation.at_safe_area:
        pytest.skip("generated entrance is also safe; seed does not exercise unsafe recovery")
    intent = BrainIntent(
        provider_id="test-provider",
        proposal_id="proposal-unsafe-recover",
        descender_id=IDS[0],
        observation_digest=observation.observation_digest,
        action="recover",
        confidence=0.8,
        reason_codes=("test",),
    )
    with pytest.raises(AIBrainFoundationError, match="safe area"):
        validate_brain_intent(intent, observation)


class _MutatingProvider:
    provider_id = "malicious-mutation-test"

    def __init__(self, descent) -> None:
        self.descent = descent

    def propose(self, observation):
        self.descent.current_tick += 1
        return BrainIntent(
            provider_id=self.provider_id,
            proposal_id="malicious-proposal",
            descender_id=observation.descender_id,
            observation_digest=observation.observation_digest,
            action="wait",
            confidence=1.0,
            reason_codes=("malicious",),
        )


def test_gate_rejects_provider_that_mutates_descent_through_out_of_band_reference():
    _, descent = _descent()
    service = AIBrainFoundationService(_MutatingProvider(descent))
    with pytest.raises(AIBrainFoundationError, match="mutated canonical"):
        service.propose(descent, IDS[0])


class _MismatchedObservationProvider:
    provider_id = "bad-observation-test"

    def propose(self, observation):
        return BrainIntent(
            provider_id=self.provider_id,
            proposal_id="bad-observation-proposal",
            descender_id=observation.descender_id,
            observation_digest="wrong-digest",
            action="wait",
            confidence=1.0,
        )


def test_gate_rejects_proposal_not_bound_to_exact_observation():
    _, descent = _descent()
    service = AIBrainFoundationService(_MismatchedObservationProvider())
    with pytest.raises(AIBrainFoundationError, match="not bound"):
        service.propose(descent, IDS[0])
