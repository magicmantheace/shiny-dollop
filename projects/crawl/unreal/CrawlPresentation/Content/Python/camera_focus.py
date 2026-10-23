"""Action-aware camera targeting layered over the proven safe master solver.

The base camera planner remains the reliability fallback. During paired combat
beats this module narrows the target set to the active performer/target so the
fight is readable instead of shrinking to fit unrelated staged actors.
"""

from __future__ import annotations

import math

import camera_planning as base

FOCUS_ACTIONS = {
    "attack_hit",
    "injury_reaction",
    "near_death",
    "death",
    "defeat",
    "rescue",
}
FOCUS_PRE_ROLL_SECONDS = 0.35
FOCUS_POST_ROLL_SECONDS = 0.45
TERMINAL_FOCUS_POST_ROLL_SECONDS = 3.0
COMBAT_HORIZONTAL_FOV_DEGREES = 50.0
COMBAT_SAFE_FRAME_X = 0.78
COMBAT_SAFE_FRAME_Y = 0.78
COMBAT_MIN_CAMERA_DISTANCE = 420.0
COMBAT_MAX_CAMERA_DISTANCE = 1800.0
COMBAT_MIN_CAMERA_Z = 345.0
COMBAT_CAMERA_HEIGHT_OFFSET = 120.0
COMBAT_CAMERA_AZIMUTH_DEGREES = -125.0
COMBAT_MIN_OCCUPIED_WIDTH = 0.30
COMBAT_MIN_OCCUPIED_HEIGHT = 0.35
COMBAT_BODY_HORIZONTAL_RADIUS = 75.0
COMBAT_BODY_CENTER_Z_OFFSET = 10.0
COMBAT_BODY_VERTICAL_EXTENT = 110.0

MASTER_PROFILE = {
    "name": "master",
    "horizontal_fov_degrees": base.HORIZONTAL_FOV_DEGREES,
    "safe_frame_x": base.SAFE_FRAME_X,
    "safe_frame_y": base.SAFE_FRAME_Y,
    "min_camera_distance": base.MIN_CAMERA_DISTANCE,
    "max_camera_distance": base.MAX_CAMERA_DISTANCE,
    "min_camera_z": base.MIN_CAMERA_Z,
    "camera_height_offset": 165.0,
    "camera_azimuth_degrees": base.CAMERA_AZIMUTH_DEGREES,
}

COMBAT_PROFILE = {
    "name": "combat_pair",
    "horizontal_fov_degrees": COMBAT_HORIZONTAL_FOV_DEGREES,
    "safe_frame_x": COMBAT_SAFE_FRAME_X,
    "safe_frame_y": COMBAT_SAFE_FRAME_Y,
    "min_camera_distance": COMBAT_MIN_CAMERA_DISTANCE,
    "max_camera_distance": COMBAT_MAX_CAMERA_DISTANCE,
    "min_camera_z": COMBAT_MIN_CAMERA_Z,
    "camera_height_offset": COMBAT_CAMERA_HEIGHT_OFFSET,
    "camera_azimuth_degrees": COMBAT_CAMERA_AZIMUTH_DEGREES,
    "visual_bounds_source": "upright_combat_envelope",
}


def _active_beat(beats, seconds):
    t = float(seconds)
    candidates = []
    for beat in beats:
        if beat.get("action") not in FOCUS_ACTIONS:
            continue
        start = float(beat["start_seconds"]) - FOCUS_PRE_ROLL_SECONDS
        post_roll = (
            TERMINAL_FOCUS_POST_ROLL_SECONDS
            if beat.get("action") in {"death", "defeat"}
            else FOCUS_POST_ROLL_SECONDS
        )
        end = float(beat["start_seconds"]) + float(beat["duration_seconds"]) + post_roll
        if start <= t <= end:
            candidates.append(beat)
    if not candidates:
        return None
    candidates.sort(key=lambda beat: (abs(t - float(beat["start_seconds"])), float(beat["start_seconds"])))
    return candidates[0]


def _target_ids(actor_ids, beats, seconds):
    beat = _active_beat(beats, seconds)
    if beat is None:
        return list(actor_ids), "safe_master_tracking", None
    pair = []
    for actor_id in (beat.get("performer_id"), beat.get("target_id")):
        if actor_id in actor_ids and actor_id not in pair:
            pair.append(actor_id)
    if len(pair) < 2:
        return list(actor_ids), "safe_master_tracking", beat
    return pair, "combat_pair_tracking", beat


def _sample_times(duration_seconds, beats):
    times = set(base._sample_times(duration_seconds, beats))
    duration = float(duration_seconds)
    for beat in beats:
        if beat.get("action") not in FOCUS_ACTIONS:
            continue
        focus_start = max(0.0, float(beat["start_seconds"]) - FOCUS_PRE_ROLL_SECONDS)
        post_roll = (
            TERMINAL_FOCUS_POST_ROLL_SECONDS
            if beat.get("action") in {"death", "defeat"}
            else FOCUS_POST_ROLL_SECONDS
        )
        focus_end = min(
            duration,
            float(beat["start_seconds"]) + float(beat["duration_seconds"]) + post_roll,
        )
        times.update((round(focus_start, 6), round(focus_end, 6)))
    return sorted(times)


def _target_separation(sampled):
    poses = list(sampled.values())
    if len(poses) < 2:
        return 0.0
    return math.hypot(
        float(poses[1]["x"]) - float(poses[0]["x"]),
        float(poses[1]["y"]) - float(poses[0]["y"]),
    )


def _combat_visual_profiles(target_ids, sampled):
    # The mesh bounds captured before Sequencer evaluation describe the rigs'
    # reference poses. Some variants are horizontal or offset from their roots,
    # which substantially overstates the rendered upright combat envelope. The
    # animated presentation roots are authoritative for staging, so combat shots
    # use a deterministic full-body envelope with attack-motion margin.
    return {
        actor_id: {
            "center_offset": {
                "x": 0.0,
                "y": 0.0,
                "z": COMBAT_BODY_CENTER_Z_OFFSET,
            },
            "extent": {
                "x": COMBAT_BODY_HORIZONTAL_RADIUS,
                "y": COMBAT_BODY_HORIZONTAL_RADIUS,
                "z": COMBAT_BODY_VERTICAL_EXTENT,
            },
            "root_yaw": float(sampled[actor_id].get("yaw", 0.0)),
        }
        for actor_id in target_ids
    }


def _combat_frame(target_ids, sampled, framing, camera, distance):
    bounds = framing["projected_bounds"]
    return {
        "target_actor_ids": list(target_ids),
        "pair_projected_min_x": bounds["min_x"],
        "pair_projected_max_x": bounds["max_x"],
        "pair_projected_min_y": bounds["min_y"],
        "pair_projected_max_y": bounds["max_y"],
        "occupied_width_fraction": framing["occupied_width_fraction"],
        "occupied_height_fraction": framing["occupied_height_fraction"],
        "camera_distance": distance,
        "camera_height": camera["z"],
        "target_separation": _target_separation(sampled),
    }


def _validate_combat_occupancy(sample):
    combat = sample["combat_frame"]
    if (
        combat["occupied_width_fraction"] < COMBAT_MIN_OCCUPIED_WIDTH
        and combat["occupied_height_fraction"] < COMBAT_MIN_OCCUPIED_HEIGHT
    ):
        raise ValueError(
            "combat pair is too small in frame at "
            f"{sample['seconds']}: width={combat['occupied_width_fraction']:.3f}, "
            f"height={combat['occupied_height_fraction']:.3f}"
        )


def plan_master_camera(actor_tracks, beats, duration_seconds, original_cues=None, actor_visual_profiles=None):
    actor_ids = sorted(actor_tracks)
    if not actor_ids:
        raise ValueError("cannot plan a camera without actor tracks")

    samples = []
    for seconds in _sample_times(duration_seconds, beats):
        target_ids, mode, active_beat = _target_ids(actor_ids, beats, seconds)
        sampled = {
            actor_id: base.sample_actor_pose(actor_tracks[actor_id], seconds)
            for actor_id in target_ids
        }
        profile = COMBAT_PROFILE if mode == "combat_pair_tracking" else MASTER_PROFILE
        fit_visual_profiles = (
            _combat_visual_profiles(target_ids, sampled)
            if mode == "combat_pair_tracking"
            else actor_visual_profiles
        )
        target, camera, rotation, distance, framing, visual_geometries, target_bounds = base._solve_camera(
            sampled,
            fit_visual_profiles,
            horizontal_fov_degrees=profile["horizontal_fov_degrees"],
            safe_frame_x=profile["safe_frame_x"],
            safe_frame_y=profile["safe_frame_y"],
            min_camera_distance=profile["min_camera_distance"],
            max_camera_distance=profile["max_camera_distance"],
            min_camera_z=profile["min_camera_z"],
            camera_height_offset=profile["camera_height_offset"],
            camera_azimuth_degrees=profile["camera_azimuth_degrees"],
        )
        sample = {
            "mode": mode,
            "seconds": seconds,
            "target_actor_ids": target_ids,
            "sampled_target_positions": sampled,
            "sampled_visual_geometry": visual_geometries,
            "target_center": target,
            "target_bounds": target_bounds,
            "camera_position": camera,
            "camera_rotation": rotation,
            "camera_distance": distance,
            "framing": framing,
            "framing_profile": dict(profile),
            "active_beat_id": active_beat.get("id") if active_beat else None,
            "active_action": active_beat.get("action") if active_beat else None,
        }
        if mode == "combat_pair_tracking":
            sample["combat_frame"] = _combat_frame(target_ids, sampled, framing, camera, distance)
            _validate_combat_occupancy(sample)
        base._validate_sample(sample)
        samples.append(sample)

    return {
        "protocol": base.CAMERA_PROTOCOL,
        "authoritative": False,
        "architecture": "time_aware_safe_master_tracking",
        "targeting_policy": "active_pair_with_full_cast_fallback",
        "horizontal_fov_degrees": base.HORIZONTAL_FOV_DEGREES,
        "aspect_ratio": base.ASPECT_RATIO,
        "safe_frame": {"x": base.SAFE_FRAME_X, "y": base.SAFE_FRAME_Y},
        "framing_profiles": {
            "master": dict(MASTER_PROFILE),
            "combat_pair": dict(COMBAT_PROFILE),
        },
        "actor_visual_profiles": dict(actor_visual_profiles or {}),
        "original_camera_cues": list(original_cues or []),
        "camera_shots": samples,
        "validation": {
            "sample_count": len(samples),
            "all_samples_valid": True,
            "max_abs_projected_x": max(sample["framing"]["max_abs_x"] for sample in samples),
            "max_abs_projected_y": max(sample["framing"]["max_abs_y"] for sample in samples),
            "combat_pair_sample_count": sum(sample["mode"] == "combat_pair_tracking" for sample in samples),
            "minimum_combat_occupied_width_fraction": min(
                (
                    sample["combat_frame"]["occupied_width_fraction"]
                    for sample in samples if sample["mode"] == "combat_pair_tracking"
                ),
                default=0.0,
            ),
            "minimum_combat_occupied_height_fraction": min(
                (
                    sample["combat_frame"]["occupied_height_fraction"]
                    for sample in samples if sample["mode"] == "combat_pair_tracking"
                ),
                default=0.0,
            ),
        },
    }
