from copy import deepcopy

import pytest

from livingworld.underreach_combat_motion_polish import (
    MAX_KNOCKBACK_CM,
    MAX_PAIR_ALIGNMENT_CM,
    PROTOCOL,
    build_combat_motion_polish_proof,
    rebuild_digest,
    validate_combat_motion_polish,
)


def _attack_profiles():
    names = ["MM_Attack_01", "MM_Attack_02", "MM_Attack_03", "MM_ChargedAttack"]
    effectors = ["hand_r", "hand_l", "foot_r", "hand_r"]
    phases = [0.4083, 0.4708, 0.3167, 0.6083]
    reaches = [93.75, 97.77, 124.53, 98.03]
    durations = [1.0, 1.0, 1.667, 1.833]
    profiles = []
    for i, name in enumerate(names):
        profiles.append({
            "asset_name": name,
            "asset_path": f"/Game/Test/{name}.{name}",
            "source_duration_seconds": durations[i],
            "contact_effector": effectors[i],
            "target_torso_bone": "spine_05",
            "candidate_contact_phase": phases[i],
            "candidate_contact_seconds": phases[i] * durations[i],
            "candidate_forward_reach_cm": reaches[i],
            "candidate_contact_height_cm": 120.0 + i,
            "pose_variation": {"unique_forward": 100, "unique_lateral": 90, "unique_height": 80},
        })
    return {
        "protocol": "crawl.presentation-attack-profile-measurements.v3",
        "authoritative": False,
        "evaluation_mode": "anim_pose_component_space_root_locked",
        "sample_count_per_asset": 241,
        "profiles": profiles,
        "missing_assets": [],
    }


def _reaction_profiles():
    return {
        "protocol": "underreach.reaction-death-profile-measurements.v1",
        "authoritative": False,
        "evaluation_mode": "anim_pose_component_space_root_locked",
        "profiles": [
            {"kind": "hit_reaction", "asset_name": "HitReact_Test", "asset_path": "/Game/Test/HitReact_Test.HitReact_Test", "source_duration_seconds": 0.8, "pose_variation": {"unique_pelvis": 6, "unique_spine": 6, "unique_head": 6}, "terminal_pelvis_delta_cm": 4.0, "sample_phases": [0, .2, .4, .6, .8, .999]},
            {"kind": "death", "asset_name": "Death_Test", "asset_path": "/Game/Test/Death_Test.Death_Test", "source_duration_seconds": 1.2, "pose_variation": {"unique_pelvis": 6, "unique_spine": 6, "unique_head": 6}, "terminal_pelvis_delta_cm": 12.0, "sample_phases": [0, .2, .4, .6, .8, .999]},
        ],
        "rejected_candidates": [],
        "candidate_count": 2,
    }


def _proof(seed="underreach-29d4-tests"):
    return build_combat_motion_polish_proof(_attack_profiles(), _reaction_profiles(), seed)


def test_deterministic_proof():
    assert _proof() == _proof()


def test_authority_and_source_chain_are_explicit():
    proof = _proof()
    polish = proof["motion_polish"]
    assert polish["protocol"] == PROTOCOL
    assert polish["authoritative"] is False
    assert polish["canonical_state_mutation_allowed"] is False
    assert polish["simulation_time_independent"] is True


def test_all_real_combat_bindings_receive_motion_directives():
    proof = _proof()
    source = proof["reaction_death_proof"]["reaction_death_binding"]["bindings"]
    expected = {b["binding_id"] for b in source if b["presentation_kind"] in {"attack", "hit_reaction", "death"}}
    actual = {d["binding_id"] for d in proof["motion_polish"]["directives"]}
    assert actual == expected


def test_attack_alignment_and_foot_slide_are_bounded():
    attacks = [d for d in _proof()["motion_polish"]["directives"] if d["presentation_kind"] == "attack"]
    assert attacks
    assert all(0 <= d["contact_alignment_cm"] <= MAX_PAIR_ALIGNMENT_CM for d in attacks)
    assert all(d["foot_slide_budget_cm"] <= 3.0 for d in attacks)


def test_reactions_stay_synchronized_and_bounded():
    reactions = [d for d in _proof()["motion_polish"]["directives"] if d["presentation_kind"] == "hit_reaction"]
    assert reactions
    assert all(d["contact_sync_error_seconds"] <= .001 for d in reactions)
    assert all(0 < d["reaction_displacement_cm"] <= MAX_KNOCKBACK_CM for d in reactions)


def test_deaths_require_terminal_root_lock():
    deaths = [d for d in _proof()["motion_polish"]["directives"] if d["presentation_kind"] == "death"]
    assert deaths
    assert all(d["canonical_death"] and d["terminal_pose_required"] and d["corpse_root_lock"] for d in deaths)


def test_facing_camera_and_real_asset_binding_are_preserved():
    proof = _proof()
    source = {b["binding_id"]: b for b in proof["reaction_death_proof"]["reaction_death_binding"]["bindings"]}
    for d in proof["motion_polish"]["directives"]:
        b = source[d["binding_id"]]
        assert d["asset_path"] == b["asset_path"]
        assert d["facing_yaw_degrees"] == b["facing_yaw_degrees"]
        assert d["camera_shot"] == b["camera_shot"]


def test_tampered_canonical_hit_is_rejected():
    proof = _proof()
    altered = deepcopy(proof["motion_polish"])
    attack = next(d for d in altered["directives"] if d["presentation_kind"] == "attack")
    attack["canonical_hit"] = not attack["canonical_hit"]
    altered["digest"] = rebuild_digest(altered)
    with pytest.raises(ValueError, match="changed canonical hit"):
        validate_combat_motion_polish(altered, proof["reaction_death_proof"], _attack_profiles(), _reaction_profiles())


def test_unbounded_reaction_is_rejected():
    proof = _proof()
    altered = deepcopy(proof["motion_polish"])
    reaction = next(d for d in altered["directives"] if d["presentation_kind"] == "hit_reaction")
    reaction["reaction_displacement_cm"] = MAX_KNOCKBACK_CM + 1
    altered["digest"] = rebuild_digest(altered)
    with pytest.raises(ValueError, match="reaction displacement exceeds"):
        validate_combat_motion_polish(altered, proof["reaction_death_proof"], _attack_profiles(), _reaction_profiles())


def test_wrong_source_digest_is_rejected():
    proof = _proof()
    altered = deepcopy(proof["motion_polish"])
    altered["source_reaction_death_binding_digest"] = "0" * 64
    altered["digest"] = rebuild_digest(altered)
    with pytest.raises(ValueError, match="source binding mismatch"):
        validate_combat_motion_polish(altered, proof["reaction_death_proof"], _attack_profiles(), _reaction_profiles())


def test_stress_40_seeds_are_valid_and_bounded():
    attacks = _attack_profiles(); reactions = _reaction_profiles()
    for i in range(40):
        proof = build_combat_motion_polish_proof(attacks, reactions, f"underreach-29d4-stress-{i:03d}")
        assert validate_combat_motion_polish(proof["motion_polish"], proof["reaction_death_proof"], attacks, reactions)
        assert len(proof["motion_polish"]["directives"]) < 2000
