from livingworld.death_persistence import (
    corpse_transform_pose,
    corpse_hold_window,
    final_pose_sample_seconds,
    intent_allowed_after_terminal,
    terminal_start_seconds,
)


def test_terminal_corpse_root_pose_lowers_and_rotates_deterministically():
    standing = {"x": 10.0, "y": -20.0, "z": 90.0, "pitch": 0.0, "yaw": 35.0}
    first = corpse_transform_pose(standing)
    second = corpse_transform_pose(standing)

    assert first == second
    assert first["x"] == standing["x"]
    assert first["y"] == standing["y"]
    assert first["yaw"] == standing["yaw"]
    assert first["z"] == 20.0
    assert first["pitch"] == -70.0


def test_terminal_start_uses_earliest_death_or_defeat():
    intents = [
        {"role": "move", "start_seconds": 1.0},
        {"role": "death", "start_seconds": 7.5},
        {"role": "defeat", "start_seconds": 8.0},
    ]
    assert terminal_start_seconds(intents) == 7.5


def test_nonterminal_animation_after_death_is_suppressed():
    terminal = 4.0
    assert intent_allowed_after_terminal({"role": "hit_reaction", "start_seconds": 3.9}, terminal)
    assert intent_allowed_after_terminal({"role": "death", "start_seconds": 4.0}, terminal)
    assert not intent_allowed_after_terminal({"role": "idle", "start_seconds": 4.0}, terminal)
    assert not intent_allowed_after_terminal({"role": "move", "start_seconds": 4.1}, terminal)


def test_corpse_hold_begins_after_authored_death_finishes():
    start, end = corpse_hold_window(5.0, 1.2, 10.0, play_rate=1.0)
    assert abs(start - 6.2) < 1.0e-9
    assert end == 10.0


def test_corpse_hold_clamps_to_sequence_end():
    start, end = corpse_hold_window(9.8, 2.0, 10.0)
    assert start == 10.0
    assert end == 10.0


def test_final_pose_sample_stays_inside_last_source_frame():
    sample = final_pose_sample_seconds(1.0, fps=60)
    assert 0.98 < sample < 1.0
