from copy import deepcopy
import json

import pytest

from livingworld.underreach_autonomous_encounters import (
    CANONICAL_PROTOCOL,
    PRESENTATION_PROTOCOL,
    rebuild_digest,
    run_autonomous_encounter,
    validate_autonomous_encounter_proof,
)


def _proof(seed="underreach-29c3-tests"):
    return run_autonomous_encounter(seed, sector_count=12, descender_count=3)


def test_same_input_reproduces_exact_canonical_and_proof_digests():
    first = _proof()
    second = _proof()
    assert first["canonical_digest"] == second["canonical_digest"]
    assert first["digest"] == second["digest"]
    assert first == second


def test_protocol_authority_boundary_is_explicit():
    proof = _proof()
    assert proof["protocol"] == CANONICAL_PROTOCOL
    assert proof["authoritative"] is True
    assert proof["presentation"]["protocol"] == PRESENTATION_PROTOCOL
    assert proof["presentation"]["authoritative"] is False
    assert proof["presentation"]["canonical_digest"] == proof["canonical_digest"]


def test_flow_contains_entry_targeting_movement_and_attacks_over_multiple_ticks():
    proof = _proof()
    truth = proof["canonical_truth"]
    types = {event["event_type"] for event in truth["ledger_events"]}
    assert "UNDERREACH_DESCENDER_ENTERED_ENCOUNTER" in types
    assert "UNDERREACH_MONSTER_TARGET_ACQUIRED" in types
    assert "UNDERREACH_MONSTER_MOVED" in types
    assert "UNDERREACH_MONSTER_ATTACKED" in types
    assert "UNDERREACH_DESCENDER_ATTACKED_MONSTER" in types
    assert len(truth["frames"]) >= 2
    assert len({frame["tick"] for frame in truth["frames"]}) == len(truth["frames"])


def test_monsters_target_only_live_active_descenders():
    proof = _proof()
    truth = proof["canonical_truth"]
    participant_ids = set(truth["participant_final"])
    for frame in truth["frames"]:
        for enemy in frame["enemy_state"].values():
            target = enemy.get("target_id")
            if target is not None:
                assert target in participant_ids


def test_actor_positions_remain_inside_sector_combat_clearance_margin():
    proof = _proof()
    # 29C.3 starts and operates inside the accepted 29B.1 1200x1200
    # combat-clearance convention. Keep a small numeric tolerance for rounding.
    for frame in proof["canonical_truth"]["frames"]:
        for position in frame["positions_cm"].values():
            assert abs(position["x"]) <= 600.001
            assert abs(position["y"]) <= 600.001


def test_feed_focus_never_has_empty_or_stale_actor_reference():
    proof = _proof()
    for frame in proof["presentation"]["frames"]:
        focus = frame["feed_focus_actor_id"]
        assert focus is not None
        assert focus in frame["positions_cm"]
    assert len(proof["presentation"]["feed_focus_schedule"]) == len(proof["canonical_truth"]["frames"])


def test_presentation_is_exact_copy_of_canonical_frame_truth():
    proof = _proof()
    assert proof["presentation"]["frames"] == proof["canonical_truth"]["frames"]
    assert proof["presentation"]["outcome"] == proof["canonical_truth"]["outcome"]
    assert proof["presentation"]["ledger_event_ids"] == [event["id"] for event in proof["canonical_truth"]["ledger_events"]]


def test_presentation_outcome_tamper_is_rejected():
    proof = _proof()
    altered = deepcopy(proof)
    altered["presentation"]["outcome"] = "invented_victory"
    altered["digest"] = rebuild_digest(altered)
    with pytest.raises(ValueError, match="altered canonical outcome"):
        validate_autonomous_encounter_proof(altered)


def test_presentation_frame_tamper_is_rejected():
    proof = _proof()
    altered = deepcopy(proof)
    altered["presentation"]["frames"][0]["positions_cm"]["descender_000"]["x"] += 1.0
    altered["digest"] = rebuild_digest(altered)
    with pytest.raises(ValueError, match="altered canonical frames"):
        validate_autonomous_encounter_proof(altered)


def test_canonical_truth_tamper_is_rejected_even_if_presentation_is_unchanged():
    proof = _proof()
    altered = deepcopy(proof)
    altered["canonical_truth"]["outcome"] = "tampered"
    altered["digest"] = rebuild_digest(altered)
    with pytest.raises(ValueError, match="canonical truth digest mismatch"):
        validate_autonomous_encounter_proof(altered)


def test_json_roundtrip_preserves_validity_and_digest():
    proof = _proof()
    restored = json.loads(json.dumps(proof, sort_keys=True))
    assert restored["digest"] == proof["digest"]
    assert validate_autonomous_encounter_proof(restored)


def test_different_seed_changes_canonical_flow():
    first = _proof("underreach-29c3-a")
    second = _proof("underreach-29c3-b")
    assert first["canonical_digest"] != second["canonical_digest"]


def test_bounded_run_terminates_with_explicit_outcome():
    proof = _proof()
    truth = proof["canonical_truth"]
    assert truth["outcome"] in {"victory", "defeat_or_retreat", "timeout"}
    assert 1 <= len(truth["frames"]) <= 120
    assert truth["ledger_events"][-1]["event_type"] == "UNDERREACH_LIVE_ENCOUNTER_ENDED"


def test_stress_40_independent_encounters_are_valid_and_bounded():
    for index in range(40):
        proof = run_autonomous_encounter(f"underreach-29c3-stress-{index:03d}", sector_count=12, descender_count=3)
        assert validate_autonomous_encounter_proof(proof)
        assert len(proof["canonical_truth"]["frames"]) <= 120
