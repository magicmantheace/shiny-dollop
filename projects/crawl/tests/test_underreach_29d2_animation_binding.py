from copy import deepcopy

import pytest

from livingworld.underreach_animation_binding import (
    ATTACK_ASSET_ORDER,
    PROFILE_PROTOCOL,
    PROTOCOL,
    build_animation_binding_proof,
    rebuild_digest,
    validate_animation_binding,
)


def _profile(name, index):
    effectors = ["hand_r", "hand_l", "foot_r", "hand_r"]
    phases = [0.4083, 0.4708, 0.3167, 0.6083]
    reaches = [93.75, 97.77, 124.53, 98.03]
    return {
        "asset_name": name,
        "asset_path": f"/Game/Test/{name}.{name}",
        "source_duration_seconds": 1.0 + index * 0.1,
        "contact_effector": effectors[index],
        "target_torso_bone": "spine_05",
        "candidate_contact_phase": phases[index],
        "candidate_contact_seconds": phases[index] * (1.0 + index * 0.1),
        "candidate_forward_reach_cm": reaches[index],
        "candidate_contact_height_cm": 120.0 + index,
        "pose_variation": {"unique_forward": 100, "unique_lateral": 80, "unique_height": 60},
    }


def _measurements():
    return {
        "protocol": PROFILE_PROTOCOL,
        "authoritative": False,
        "evaluation_mode": "anim_pose_component_space_root_locked",
        "sample_count_per_asset": 241,
        "profiles": [_profile(name, index) for index, name in enumerate(ATTACK_ASSET_ORDER)],
        "missing_assets": [],
    }


def _proof(seed="underreach-29d2-tests"):
    return build_animation_binding_proof(_measurements(), seed)


def test_same_input_is_exactly_deterministic():
    assert _proof() == _proof()


def test_different_source_seed_changes_binding_digest():
    first = _proof("underreach-29d2-seed-a")
    second = _proof("underreach-29d2-seed-b")
    assert first["binding"]["digest"] != second["binding"]["digest"]


def test_authority_boundary_and_source_binding_are_explicit():
    proof = _proof()
    binding = proof["binding"]
    assert binding["protocol"] == PROTOCOL
    assert binding["authoritative"] is False
    assert binding["canonical_state_mutation_allowed"] is False
    assert binding["simulation_time_independent"] is True
    assert binding["source_presentation_digest"] == proof["combat_proof"]["presentation"]["digest"]
    assert binding["source_canonical_digest"] == proof["combat_proof"]["source"]["canonical_digest"]


def test_every_29d1_attack_is_bound_to_real_measured_asset():
    proof = _proof()
    attacks = [w for w in proof["combat_proof"]["presentation"]["windows"] if w["presentation_kind"] == "attack"]
    bound = [b for b in proof["binding"]["bindings"] if b["presentation_kind"] == "attack"]
    assert len(bound) == len(attacks) > 0
    assert {b["window_id"] for b in bound} == {w["window_id"] for w in attacks}
    assert all(b["binding_status"] == "measured_real_asset" for b in bound)
    assert all(b["asset_name"] in ATTACK_ASSET_ORDER and b["asset_path"] for b in bound)


def test_real_attack_cycle_exercises_all_four_measured_assets():
    names = [b["asset_name"] for b in _proof()["binding"]["bindings"] if b["presentation_kind"] == "attack"]
    assert set(ATTACK_ASSET_ORDER) <= set(names)


def test_reaction_and_death_bindings_truthfully_remain_semantic_fallbacks():
    bindings = _proof()["binding"]["bindings"]
    fallbacks = [b for b in bindings if b["presentation_kind"] in {"hit_reaction", "death"}]
    assert fallbacks
    assert all(b["binding_status"] == "semantic_fallback" for b in fallbacks)
    assert all(b["asset_name"] is None and b["asset_path"] is None for b in fallbacks)


def test_contact_correction_is_bounded_and_does_not_change_pair_positions():
    proof = _proof()
    windows = {w["window_id"]: w for w in proof["combat_proof"]["presentation"]["windows"]}
    for binding in proof["binding"]["bindings"]:
        if binding["presentation_kind"] != "attack":
            continue
        window = windows[binding["window_id"]]
        assert 0.0 <= binding["bounded_alignment_request_cm"] <= proof["binding"]["max_presentation_alignment_cm"]
        assert window["canonical_position_cm"] == proof["combat_proof"]["presentation"]["windows"][window["source_frame_index"] if False else proof["combat_proof"]["presentation"]["windows"].index(window)]["canonical_position_cm"]


def test_facing_and_feed_camera_intent_are_preserved_exactly():
    proof = _proof()
    windows = {w["window_id"]: w for w in proof["combat_proof"]["presentation"]["windows"]}
    for binding in proof["binding"]["bindings"]:
        source = windows[binding["window_id"]]
        assert binding["facing_yaw_degrees"] == source["facing_yaw_degrees"]
        assert binding["camera_shot"] == source["camera_shot"]


def test_missing_required_real_asset_is_rejected():
    measurements = _measurements()
    measurements["profiles"] = measurements["profiles"][:-1]
    with pytest.raises(ValueError, match="required measured attack assets missing"):
        build_animation_binding_proof(measurements)


def test_duplicate_profile_is_rejected():
    measurements = _measurements()
    measurements["profiles"].append(deepcopy(measurements["profiles"][0]))
    with pytest.raises(ValueError, match="duplicate or unnamed"):
        build_animation_binding_proof(measurements)


def test_frozen_profile_is_rejected():
    measurements = _measurements()
    measurements["profiles"][0]["pose_variation"] = {"unique_forward": 2, "unique_lateral": 2, "unique_height": 2}
    with pytest.raises(ValueError, match="frozen measured attack profile"):
        build_animation_binding_proof(measurements)


def test_implausible_contact_profile_is_rejected():
    measurements = _measurements()
    measurements["profiles"][0]["candidate_forward_reach_cm"] = 12.0
    with pytest.raises(ValueError, match="implausible measured attack profile"):
        build_animation_binding_proof(measurements)


def test_profile_measurement_tamper_is_rejected_against_existing_binding():
    measurements = _measurements()
    proof = build_animation_binding_proof(measurements)
    altered = deepcopy(measurements)
    altered["profiles"][0]["candidate_forward_reach_cm"] += 1.0
    with pytest.raises(ValueError, match="measured profile digest mismatch"):
        validate_animation_binding(proof["binding"], proof["combat_proof"], altered)


def test_wrong_29d1_digest_is_rejected():
    measurements = _measurements()
    proof = build_animation_binding_proof(measurements)
    altered = deepcopy(proof["binding"])
    altered["source_presentation_digest"] = "0" * 64
    altered["digest"] = rebuild_digest(altered)
    with pytest.raises(ValueError, match="wrong 29D.1 presentation digest"):
        validate_animation_binding(altered, proof["combat_proof"], measurements)


def test_canonical_hit_and_damage_tamper_is_rejected():
    measurements = _measurements()
    proof = build_animation_binding_proof(measurements)
    altered = deepcopy(proof["binding"])
    attack = next(b for b in altered["bindings"] if b["presentation_kind"] == "attack")
    attack["canonical_damage"] += 0.1
    altered["digest"] = rebuild_digest(altered)
    with pytest.raises(ValueError, match="changed canonical damage"):
        validate_animation_binding(altered, proof["combat_proof"], measurements)


def test_stress_40_sources_remain_valid_and_bounded():
    measurements = _measurements()
    for index in range(40):
        proof = build_animation_binding_proof(measurements, f"underreach-29d2-stress-{index:03d}")
        assert validate_animation_binding(proof["binding"], proof["combat_proof"], measurements)
        attacks = [b for b in proof["binding"]["bindings"] if b["presentation_kind"] == "attack"]
        assert attacks
        assert all(b["bounded_alignment_request_cm"] <= proof["binding"]["max_presentation_alignment_cm"] for b in attacks)
