import importlib.util
from pathlib import Path


MODULE_PATH = (
    Path(__file__).parents[1]
    / "unreal"
    / "CrawlPresentation"
    / "Content"
    / "Python"
    / "combat_staging.py"
)
BUILD_PATH = MODULE_PATH.with_name("build_vertical_slice.py")
SPEC = importlib.util.spec_from_file_location("crawl_unreal_combat_staging", MODULE_PATH)
combat_staging = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(combat_staging)


def pose(x, y, z=90.0, yaw=0.0):
    return {"x": x, "y": y, "z": z, "roll": 0.0, "pitch": 0.0, "yaw": yaw}


def test_distant_attack_closes_to_contact_and_stays_engaged():
    attacker = pose(-420.0, -250.0)
    target = pose(180.0, 160.0)

    staged = combat_staging.stage_attack_exchange(attacker, target, 4.5, 0.8)

    assert staged["initial_distance"] > 600.0
    profile = combat_staging.attack_profile_for_slot(staged["asset_slot"])
    expected_ready = (profile.ready_forward_distance_cm ** 2 + profile.lateral_reach_cm ** 2) ** 0.5
    assert abs(staged["ready_distance"] - expected_ready) < 0.001
    assert abs(staged["contact_distance"] - combat_staging.ATTACK_CONTACT_DISTANCE) < 0.001
    assert abs(staged["recover_distance"] - combat_staging.ATTACK_RECOVER_DISTANCE) < 0.001
    assert staged["recover_distance"] < staged["initial_distance"]
    assert staged["expected_contact_error_cm"] < 0.001
    assert staged["authoritative"] is False


def test_attacker_and_target_face_each_other_during_exchange():
    staged = combat_staging.stage_attack_exchange(
        pose(-300.0, 10.0, yaw=170.0),
        pose(120.0, 70.0, yaw=-20.0),
        2.0,
        1.0,
    )

    attacker_ready = staged["attacker_ready"]
    target_ready = staged["target_ready"]
    # The authored hand is slightly off-center, so the torso deliberately
    # remains within a small tolerance while the hand, rather than the root, aims
    # exactly at the target centerline.
    assert staged["attacker_facing_error_degrees"] < 20.0
    assert staged["target_facing_error_degrees"] < 0.001
    assert staged["attack_profile"]["animation_forward_axis"] == "+Y"
    assert staged["attack_profile"]["root_yaw_offset_degrees"] == -90.0


def test_attack_staging_is_deterministic_and_does_not_mutate_inputs():
    attacker = pose(-200.0, -200.0, yaw=35.0)
    target = pose(200.0, 150.0, yaw=-80.0)
    attacker_before = dict(attacker)
    target_before = dict(target)

    first = combat_staging.stage_attack_exchange(attacker, target, 3.0, 0.75)
    second = combat_staging.stage_attack_exchange(attacker, target, 3.0, 0.75)

    assert first == second
    assert attacker == attacker_before
    assert target == target_before


def test_attack_staging_stays_inside_safe_arena_bounds():
    staged = combat_staging.stage_attack_exchange(
        pose(540.0, 540.0),
        pose(560.0, 560.0),
        1.0,
        0.5,
    )

    for key in ("attacker_ready", "attacker_contact", "attacker_recover", "target_hit"):
        value = staged[key]
        assert abs(value["x"]) <= combat_staging.ARENA_SAFE_HALF_SIZE
        assert abs(value["y"]) <= combat_staging.ARENA_SAFE_HALF_SIZE


def test_impact_occurs_after_attack_start_and_before_recovery():
    staged = combat_staging.stage_attack_exchange(pose(0.0, 0.0), pose(300.0, 0.0), 5.0, 1.2)

    assert staged["approach_start_seconds"] < staged["attack_start_seconds"]
    assert staged["attack_start_seconds"] < staged["visual_contact_seconds"] < staged["end_seconds"]
    expected_contact = staged["visual_contact_frame"] / combat_staging.PRESENTATION_FPS
    assert abs(staged["visual_contact_seconds"] - expected_contact) < 1.0e-9
    expected_reaction = expected_contact + 1.0 / combat_staging.PRESENTATION_FPS
    assert abs(staged["reaction_start_seconds"] - expected_reaction) < 1.0e-9
    evaluated_source_phase = (
        staged["contact_frame_offset"]
        / combat_staging.PRESENTATION_FPS
        * staged["attack_animation_play_rate"]
        / staged["attack_profile"]["source_duration_seconds"]
    )
    assert abs(evaluated_source_phase - staged["contact_phase"]) < 1.0e-9


def test_measured_hand_effector_reaches_target_torso_centerline():
    staged = combat_staging.stage_attack_exchange(
        pose(-250.0, -100.0),
        pose(210.0, 180.0),
        4.0,
        0.75,
        attacker_scale=1.18,
        target_scale=1.0,
    )

    effector = staged["estimated_contact_effector"]
    chest = staged["target_chest"]
    assert abs(effector["x"] - chest["x"]) < 0.001
    assert abs(effector["y"] - chest["y"]) < 0.001
    assert staged["expected_contact_error_cm"] < 0.001


def test_adjacent_exchange_shares_approach_without_absurd_play_rate():
    staged = combat_staging.stage_attack_exchange(
        pose(-450.0, 0.0),
        pose(450.0, 0.0),
        5.0,
        0.75,
        attacker_available_seconds=4.85,
        target_available_seconds=4.25,
    )
    profile = combat_staging.attack_profile_for_slot(staged["asset_slot"])

    assert staged["approach_distance"] > 0.0
    assert staged["target_approach_distance"] > 0.0
    assert 0.0 < staged["approach_speed_cm_s"] < float("inf")
    assert 0.0 < staged["target_approach_speed_cm_s"] < float("inf")
    assert profile.minimum_locomotion_play_rate <= staged["locomotion_play_rate"] <= profile.maximum_locomotion_play_rate
    assert profile.minimum_locomotion_play_rate <= staged["target_locomotion_play_rate"] <= profile.maximum_locomotion_play_rate


def test_recovery_persists_in_engagement_instead_of_snapping_to_initial_pose():
    staged = combat_staging.stage_attack_exchange(
        pose(-500.0, -300.0),
        pose(300.0, 250.0),
        3.0,
        0.75,
    )

    assert staged["attacker_recover"] != staged["attacker_initial"]
    assert staged["recover_distance"] < staged["initial_distance"]


def test_enemy_and_humanoid_slots_have_explicit_deterministic_profiles():
    humanoid = combat_staging.attack_profile_for_slot("humanoid.combat.attack.default")
    enemy = combat_staging.attack_profile_for_slot("enemy.biped.combat.attack.default")

    assert humanoid.contact_phase == enemy.contact_phase == 0.4083333333333333
    assert humanoid.contact_frame_offset == enemy.contact_frame_offset == 18
    assert humanoid.contact_effector == enemy.contact_effector == "hand_r"
    assert abs(humanoid.forward_reach_cm - 93.75389138214155) < 1e-9
    assert humanoid.forward_reach_cm == enemy.forward_reach_cm
    assert humanoid.asset_path.endswith("MM_Attack_01.MM_Attack_01")
    assert humanoid.target_knockback_cm == 45.0
    assert humanoid.minimum_locomotion_play_rate == 0.25
    assert humanoid.maximum_evaluated_planar_error_cm == 30.0
    assert humanoid.maximum_evaluated_contact_error_cm == 45.0
    assert humanoid.force_root_lock is True
    assert enemy.force_root_lock is True


def test_unreal_sections_force_cinematic_animation_evaluation():
    source = BUILD_PATH.read_text(encoding="utf-8")

    assert "unreal.AnimationMode.ANIMATION_CUSTOM_MODE" in source
    assert 'params.set_editor_property("force_custom_mode", True)' in source
    assert '"MovieSceneControlRigParameterTrack"' in source
    assert "binding.remove_track(track)" in source


def test_every_active_attack_profile_has_complete_measured_contact_data():
    required = {
        "asset_slot",
        "asset_path",
        "source_duration_seconds",
        "contact_phase",
        "contact_frame_offset",
        "contact_effector",
        "forward_reach_cm",
        "lateral_reach_cm",
        "contact_height_cm",
        "target_chest_height_cm",
        "ready_forward_distance_cm",
        "recovery_forward_distance_cm",
        "target_knockback_cm",
        "approach_lead_seconds",
        "reaction_latency_seconds",
        "root_yaw_offset_degrees",
        "animation_forward_axis",
        "locomotion_reference_speed_cm_s",
        "minimum_locomotion_play_rate",
        "maximum_locomotion_play_rate",
        "force_root_lock",
        "maximum_evaluated_planar_error_cm",
        "maximum_evaluated_contact_error_cm",
    }
    for slot, profile in combat_staging.ATTACK_PRESENTATION_PROFILES.items():
        data = combat_staging.attack_profile_debug(profile)
        assert required <= data.keys(), slot
        assert 0.0 < profile.contact_phase < 1.0
        assert profile.contact_frame_offset > 0
        assert profile.contact_effector in {"hand_r", "hand_l", "foot_r", "foot_l"}
        assert profile.forward_reach_cm > 60.0


def test_all_profile_contact_frames_and_reactions_are_deterministic():
    for slot in combat_staging.ATTACK_PRESENTATION_PROFILES:
        first = combat_staging.stage_attack_exchange(
            pose(-300.0, -75.0),
            pose(250.0, 110.0),
            4.0,
            0.75,
            asset_slot=slot,
        )
        second = combat_staging.stage_attack_exchange(
            pose(-300.0, -75.0),
            pose(250.0, 110.0),
            4.0,
            0.75,
            asset_slot=slot,
        )
        assert first == second
        assert first["expected_contact_error_cm"] < 0.001
        assert first["reaction_start_seconds"] >= first["visual_contact_seconds"]
        evaluated_phase = (
            first["contact_frame_offset"]
            / combat_staging.PRESENTATION_FPS
            * first["attack_animation_play_rate"]
            / first["attack_profile"]["source_duration_seconds"]
        )
        assert abs(evaluated_phase - first["contact_phase"]) < 1.0e-9
