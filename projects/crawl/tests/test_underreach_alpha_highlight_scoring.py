from __future__ import annotations

from livingworld import underreach_highlight_story_arc as base
from livingworld.runtime_checkpoint import payload_digest
from livingworld.underreach_alpha_highlight_scoring import (
    ALPHA_SCORING_PROFILE,
    AlphaHighlightPolicy,
    AlphaHighlightStoryArcService,
    score_alpha_envelope,
)
from livingworld.underreach_media_event_export import MediaEnvelope
from livingworld.underreach_media_foundation import MediaPersistence


def _envelope(event_types: tuple[str, ...], *, party: bool = False, rewards: int = 0) -> MediaEnvelope:
    source_ids = tuple(f"event_{index:03d}" for index in range(len(event_types)))
    delvers = ("live_descender_010", "live_descender_011")
    items = tuple(
        {
            "id": f"item_{index:03d}",
            "name": f"Uncommon Reward {index}",
            "rarity": "uncommon",
            "owner_descender_id": delvers[index % len(delvers)],
            "important": False,
        }
        for index in range(rewards)
    )
    body = {
        "schema": "underreach.media-envelope.v1",
        "exporter_version": "30.5.1",
        "phase": "30.5",
        "envelope_id": "media_envelope_alpha_calibration_fixture",
        "idempotency_key": payload_digest([event_types, party, rewards]),
        "crawl_id": "crawl_alpha_calibration_fixture",
        "seed": "alpha-highlight-calibration-test",
        "export_tick": 4,
        "stratum": 1,
        "strata": [1],
        "sector": "sector_fixture",
        "source_event_ids": list(source_ids),
        "source_event_types": list(event_types),
        "source_event_digest": payload_digest(list(event_types)),
        "delver_ids": list(delvers),
        "participant_context": {
            delver_id: {
                "current_stratum": 1,
                "progression": {"level": 1},
                "encounters_survived": 0,
                "kills": 0,
            }
            for delver_id in delvers
        },
        "item_context": list(items),
        "social_context": {},
        "party_context": {
            "parties": ([{"party_id": "party_fixture", "member_ids": list(delvers)}] if party else []),
            "alliances": [],
        },
        "combat_context": {"encounters": ([{"encounter_id": "encounter_fixture"}] if "COMBAT_HIT" in event_types else [])},
        "semantic_context": [],
        "visual_identity_refs": [],
        "allowed_facts": [],
        "canonical_fingerprint": "canonical_fixture",
        "canonical_state_digest": "state_fixture",
        "history_prefix_count": len(source_ids),
        "history_prefix_last_event_id": source_ids[-1],
        "history_prefix_digest": payload_digest(list(source_ids)),
        "context_truncated": False,
        "presentation_can_mutate_simulation": False,
        "unreal_dependency": False,
        "cloud_ai_dependency": False,
        "paid_ai_dependency": False,
    }
    return MediaEnvelope.model_validate({**body, "digest": payload_digest(body)})


def test_alpha_policy_keeps_thresholds_but_has_distinct_scoring_identity() -> None:
    original = base.HighlightPolicy()
    alpha = AlphaHighlightPolicy()

    assert alpha.chronicle_min == original.chronicle_min == 50
    assert alpha.motion_story_min == original.motion_story_min == 70
    assert alpha.enhanced_stills_min == original.enhanced_stills_min == 80
    assert alpha.local_animation_min == original.local_animation_min == 90
    assert alpha.cinematic_min == original.cinematic_min == 95
    assert alpha.scoring_profile == ALPHA_SCORING_PROFILE
    assert alpha.digest != original.digest


def test_alpha_tick4_style_composite_reaches_motion_story_boundary() -> None:
    event_types = (
        "COMBAT_HIT",
        "COMBAT_HIT",
        "ENEMY_DEFEATED",
        "COMBAT_ENDED",
        "ITEM_ACQUIRED",
        "ENCOUNTER_RESOLVED",
        "ITEM_CONSUMED",
        "CRAWLER_MOVED",
        "CRAWLER_MOVED",
        "CRAWLER_MOVED",
        "PARTY_FORMED",
        "ENCOUNTER_TRIGGERED",
        "ITEM_ACQUIRED",
        "CRAWLER_ADVANCED",
        "CRAWLER_ADVANCED",
    )
    envelope = _envelope(event_types, party=True, rewards=2)

    original, _ = base.score_envelope(envelope)
    calibrated, reasons = score_alpha_envelope(envelope)

    assert original.total < 50
    assert calibrated.danger == 16
    assert calibrated.rarity == 8
    assert calibrated.social_stakes == 12
    assert calibrated.character_significance == 14
    assert calibrated.outcome_reversal == 0
    assert calibrated.continuity == 15
    assert calibrated.visual_potential == 5
    assert calibrated.total == 70
    assert base.tier_for_score(calibrated.total, AlphaHighlightPolicy()) == base.HighlightTier.MOTION_STORY
    assert f"scoring_profile:{ALPHA_SCORING_PROFILE}" in reasons


def test_alpha_low_signal_movement_remains_archive_only() -> None:
    envelope = _envelope(("CRAWLER_MOVED",), party=False, rewards=0)

    calibrated, _ = score_alpha_envelope(envelope)

    assert calibrated.total < 50
    assert base.tier_for_score(calibrated.total, AlphaHighlightPolicy()) == base.HighlightTier.ARCHIVE_ONLY


def test_alpha_reindex_promotes_only_previously_unhighlighted_envelopes() -> None:
    event_types = (
        "ENCOUNTER_TRIGGERED",
        "COMBAT_HIT",
        "COMBAT_HIT",
        "ENEMY_DEFEATED",
        "COMBAT_ENDED",
        "ENCOUNTER_RESOLVED",
        "ITEM_ACQUIRED",
        "ITEM_ACQUIRED",
        "PARTY_FORMED",
        "CRAWLER_ADVANCED",
        "CRAWLER_ADVANCED",
    )
    envelope = _envelope(event_types, party=True, rewards=2)
    media = MediaPersistence("sqlite:///:memory:")
    media.initialize()
    media.register_envelope(envelope)
    service = AlphaHighlightStoryArcService(media)
    service.initialize()

    first = service.reindex_unhighlighted(crawl_id=envelope.crawl_id)
    highlights_after_first = service.list_highlights(crawl_id=envelope.crawl_id)
    second = service.reindex_unhighlighted(crawl_id=envelope.crawl_id)
    highlights_after_second = service.list_highlights(crawl_id=envelope.crawl_id)

    assert first == (envelope,)
    assert len(highlights_after_first) == 1
    assert highlights_after_first[0].score.total == 70
    assert highlights_after_first[0].output_tier == base.HighlightTier.MOTION_STORY
    assert second == ()
    assert highlights_after_second == highlights_after_first
