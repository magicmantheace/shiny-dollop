import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = (
    Path(__file__).parents[1]
    / "unreal"
    / "CrawlPresentation"
    / "Content"
    / "Python"
    / "camera_planning.py"
)
FOCUS_MODULE_PATH = MODULE_PATH.with_name("camera_focus.py")
BUILDER_PATH = MODULE_PATH.with_name("build_vertical_slice.py")
SPEC = importlib.util.spec_from_file_location("crawl_unreal_camera_planning", MODULE_PATH)
camera_planning = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(camera_planning)

# camera_focus imports camera_planning by module name, so expose the already
# loaded pure planner under that name before loading the focus layer.
import sys
sys.modules["camera_planning"] = camera_planning
FOCUS_SPEC = importlib.util.spec_from_file_location("crawl_unreal_camera_focus", FOCUS_MODULE_PATH)
camera_focus = importlib.util.module_from_spec(FOCUS_SPEC)
FOCUS_SPEC.loader.exec_module(camera_focus)


def pose(x, y, z=90.0):
    return {"x": x, "y": y, "z": z, "roll": 0.0, "pitch": 0.0, "yaw": 0.0}


def track(*keys):
    return [{"seconds": seconds, "pose": value} for seconds, value in keys]


def test_actor_pose_sampling_uses_transform_at_camera_time_not_final_pose():
    actor_track = track((0.0, pose(0.0, 0.0)), (5.0, pose(500.0, -100.0)))

    sampled = camera_planning.sample_actor_pose(actor_track, 2.0)

    assert sampled["x"] == 200.0
    assert sampled["y"] == -40.0
    assert sampled != actor_track[-1]["pose"]


def test_master_camera_fits_complete_staged_cast_through_retreats():
    actor_tracks = {
        "crawler_a": track((0.0, pose(334.0, 63.0)), (10.0, pose(550.0, 103.0)), (16.87, pose(550.0, 103.0))),
        "enemy": track((0.0, pose(-168.0, 157.0)), (16.87, pose(-120.0, 170.0))),
        "crawler_b": track((0.0, pose(-168.0, -296.0)), (8.5, pose(-277.0, -487.0)), (16.87, pose(-277.0, -487.0))),
    }
    beats = [
        {"action": "attack_hit", "start_seconds": 4.54, "duration_seconds": 0.75,
         "performer_id": "crawler_b", "target_id": "enemy"},
        {"action": "retreat", "start_seconds": 7.15, "duration_seconds": 1.35,
         "performer_id": "crawler_b", "target_id": None},
        {"action": "retreat", "start_seconds": 10.36, "duration_seconds": 1.35,
         "performer_id": "crawler_a", "target_id": None},
    ]

    first = camera_planning.plan_master_camera(actor_tracks, beats, 16.87)
    second = camera_planning.plan_master_camera(actor_tracks, beats, 16.87)

    assert first == second
    assert first["validation"]["all_samples_valid"] is True
    assert first["validation"]["max_abs_projected_x"] <= camera_planning.SAFE_FRAME_X
    assert first["validation"]["max_abs_projected_y"] <= camera_planning.SAFE_FRAME_Y
    attack = min(first["camera_shots"], key=lambda shot: abs(shot["seconds"] - 4.54))
    assert set(attack["target_actor_ids"]) == {"crawler_a", "crawler_b", "enemy"}
    ending = first["camera_shots"][-1]
    assert set(ending["target_actor_ids"]) == {"crawler_a", "crawler_b", "enemy"}
    assert all(shot["camera_position"]["z"] >= camera_planning.MIN_CAMERA_Z for shot in first["camera_shots"])


def test_combat_focus_frames_only_active_pair_during_hit_then_returns_to_master():
    actor_tracks = {
        "crawler_a": track((0.0, pose(334.0, 63.0)), (16.87, pose(550.0, 103.0))),
        "enemy": track((0.0, pose(-168.0, 157.0)), (4.54, pose(-120.0, 170.0)), (16.87, pose(-120.0, 170.0))),
        "crawler_b": track((0.0, pose(-168.0, -296.0)), (4.54, pose(-125.0, 45.0)), (16.87, pose(-125.0, 45.0))),
    }
    beats = [
        {"id": "beat-hit", "action": "attack_hit", "start_seconds": 4.54, "duration_seconds": 0.75,
         "performer_id": "crawler_b", "target_id": "enemy"},
    ]

    result = camera_focus.plan_master_camera(actor_tracks, beats, 16.87)
    attack = min(result["camera_shots"], key=lambda shot: abs(shot["seconds"] - 4.54))
    ending = result["camera_shots"][-1]

    assert attack["mode"] == "combat_pair_tracking"
    assert set(attack["target_actor_ids"]) == {"crawler_b", "enemy"}
    assert attack["active_action"] == "attack_hit"
    assert attack["camera_distance"] <= 860.0
    assert camera_planning._inside_wall_geometry(attack["camera_position"]) is False
    assert attack["camera_distance"] < ending["camera_distance"]
    assert attack["framing_profile"]["name"] == "combat_pair"
    assert attack["combat_frame"]["occupied_width_fraction"] >= camera_focus.COMBAT_MIN_OCCUPIED_WIDTH or (
        attack["combat_frame"]["occupied_height_fraction"] >= camera_focus.COMBAT_MIN_OCCUPIED_HEIGHT
    )
    assert attack["combat_frame"]["target_separation"] > 0.0
    assert set(ending["target_actor_ids"]) == {"crawler_a", "crawler_b", "enemy"}
    assert result["validation"]["combat_pair_sample_count"] > 0
    assert result["validation"]["minimum_combat_occupied_height_fraction"] >= 0.35
    focus_start = next(shot for shot in result["camera_shots"] if shot["seconds"] == 4.19)
    focus_end = next(shot for shot in result["camera_shots"] if shot["seconds"] == 5.74)
    assert focus_start["mode"] == "combat_pair_tracking"
    assert focus_end["mode"] == "combat_pair_tracking"


def test_combat_focus_rejects_microscopic_pair_occupancy():
    sample = {
        "seconds": 5.0,
        "combat_frame": {
            "occupied_width_fraction": 0.12,
            "occupied_height_fraction": 0.18,
        },
    }

    with pytest.raises(ValueError, match="combat pair is too small"):
        camera_focus._validate_combat_occupancy(sample)


def test_terminal_focus_holds_corpse_pair_for_three_seconds_after_fall_beat():
    actor_tracks = {
        "crawler": track((0.0, pose(-100.0, 0.0)), (12.0, pose(-100.0, 0.0))),
        "enemy": track((0.0, pose(100.0, 0.0)), (12.0, pose(100.0, 0.0, 20.0))),
        "bystander": track((0.0, pose(500.0, 300.0)), (12.0, pose(500.0, 300.0))),
    }
    beats = [{
        "id": "beat-defeat",
        "action": "defeat",
        "start_seconds": 5.0,
        "duration_seconds": 1.25,
        "performer_id": "crawler",
        "target_id": "enemy",
    }]

    result = camera_focus.plan_master_camera(actor_tracks, beats, 12.0)
    hold_end = next(shot for shot in result["camera_shots"] if shot["seconds"] == 9.25)
    ending = result["camera_shots"][-1]

    assert hold_end["mode"] == "combat_pair_tracking"
    assert hold_end["active_action"] == "defeat"
    assert set(hold_end["target_actor_ids"]) == {"crawler", "enemy"}
    assert ending["mode"] == "safe_master_tracking"


def test_duplicate_sequencer_times_use_last_written_pose():
    actor_track = track(
        (0.0, pose(0.0, 0.0)),
        (2.0, pose(100.0, 0.0)),
        (2.0, pose(150.0, 25.0)),
        (4.0, pose(200.0, 50.0)),
    )

    assert camera_planning.sample_actor_pose(actor_track, 2.0)["x"] == 150.0


def test_master_camera_targets_real_visual_bounds_instead_of_actor_roots():
    actor_tracks = {
        "low_body": track((0.0, pose(300.0, 50.0))),
        "high_body": track((0.0, pose(-170.0, 160.0))),
    }
    visual_profiles = {
        "low_body": {
            "center_offset": {"x": 16.0, "y": 8.0, "z": -89.0},
            "extent": {"x": 74.0, "y": 22.0, "z": 100.0},
            "root_yaw": 0.0,
        },
        "high_body": {
            "center_offset": {"x": 73.0, "y": 8.0, "z": 78.0},
            "extent": {"x": 120.0, "y": 25.0, "z": 122.0},
            "root_yaw": 0.0,
        },
    }

    result = camera_planning.plan_master_camera(
        actor_tracks, [], 1.0, actor_visual_profiles=visual_profiles
    )
    first = result["camera_shots"][0]

    assert first["sampled_visual_geometry"]["low_body"]["center"]["z"] == 1.0
    assert first["sampled_visual_geometry"]["high_body"]["center"]["z"] == 168.0
    assert first["target_bounds"]["min_z"] == -99.0
    assert first["target_bounds"]["max_z"] == 290.0
    assert first["target_center"]["z"] == 95.5
    assert first["framing"]["max_abs_x"] <= camera_planning.SAFE_FRAME_X
    assert first["framing"]["max_abs_y"] <= camera_planning.SAFE_FRAME_Y


def test_unreal_builder_reuses_seeded_transform_track():
    source = BUILDER_PATH.read_text(encoding="utf-8")

    assert "for track in binding.get_tracks()" in source
    assert "track = transform_tracks[0] if transform_tracks else binding.add_track" in source
    assert "channel.remove_key(key)" in source


def test_unreal_builder_persists_camera_and_binds_camera_cut_directly():
    source = BUILDER_PATH.read_text(encoding="utf-8")

    assert "spawn_actor_from_class(\n        unreal.CineCameraActor" in source
    assert "camera_actor.set_actor_label(\"Crawl_MasterCamera\")" in source
    assert "camera_binding_id.set_editor_property(\"Guid\", camera_binding.get_id())" in source
    assert "camera_cut_section.set_camera_binding_id(camera_binding_id)" in source
