import importlib.util
from pathlib import Path


MODULE_PATH = (
    Path(__file__).parents[1]
    / "unreal"
    / "CrawlPresentation"
    / "Content"
    / "Python"
    / "animation_transitions.py"
)
POLISH_PATH = MODULE_PATH.with_name("build_vertical_slice_polish.py")
SPEC = importlib.util.spec_from_file_location("crawl_animation_transitions", MODULE_PATH)
transitions = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(transitions)


def pose(x, y, yaw=0.0):
    return {"x": x, "y": y, "z": 90.0, "roll": 0.0, "pitch": 0.0, "yaw": yaw}


def test_forward_locomotion_root_faces_travel_direction():
    start = pose(0.0, 0.0)
    end = pose(100.0, 0.0)

    oriented = transitions.orient_pose_for_travel(start, end)

    assert oriented["yaw"] == -90.0
    assert oriented["x"] == 100.0


def test_retreat_diagonal_facing_is_deterministic_and_not_sideways():
    start = pose(40.0, 40.0, yaw=33.0)
    end = pose(400.0, 400.0)

    first = transitions.orient_pose_for_travel(start, end)
    second = transitions.orient_pose_for_travel(start, end)

    assert first == second
    assert abs(first["yaw"] - (-45.0)) < 1.0e-9


def test_stationary_pose_preserves_existing_yaw():
    start = pose(10.0, -10.0, yaw=72.0)
    end = pose(10.0, -10.0, yaw=0.0)

    assert transitions.travel_yaw(start, end) == 72.0


def test_blend_windows_are_clamped_for_short_sections():
    assert transitions.blend_seconds(0.5, 1.0) == transitions.MAX_BLEND_SECONDS
    assert transitions.blend_seconds(0.12, 0.2) == 0.05


def test_transition_debug_uses_small_symmetric_windows():
    debug = transitions.transition_debug(60, 120, 60, 0.12, 0.12)

    assert debug["blend_in_frames"] == 7
    assert debug["blend_out_frames"] == 7
    assert debug["duration_seconds"] == 1.0


def test_polish_builder_orients_retreats_and_moves_to_travel_vector():
    source = POLISH_PATH.read_text(encoding="utf-8")

    assert source.count("orient_pose_for_travel(performer,") >= 2
    assert 'SCRIPT_VERSION = "v10"' in source


def test_polish_builder_adds_short_crossfades_without_replacing_contact_solver():
    source = POLISH_PATH.read_text(encoding="utf-8")

    assert "set_ease_in_duration" in source
    assert "set_ease_out_duration" in source
    assert "stage_attack_exchange" not in source or "validated camera/contact" in source
    assert "approach_section_end" in source
