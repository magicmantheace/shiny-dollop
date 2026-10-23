"""Pure deterministic camera planning for the generated Crawl proof arena.

This module deliberately has no Unreal dependency so the math can be tested before
an expensive editor build/render.  Actor tracks are the presentation transform
keys that are also written to Sequencer; canonical Crawl state is never changed.
"""

import math


CAMERA_PROTOCOL = "crawl.presentation-camera-debug.v1"
HORIZONTAL_FOV_DEGREES = 38.0
ASPECT_RATIO = 16.0 / 9.0
SAFE_FRAME_X = 0.74
SAFE_FRAME_Y = 0.74
CAMERA_AZIMUTH_DEGREES = -125.0
MIN_CAMERA_DISTANCE = 520.0
MAX_CAMERA_DISTANCE = 3000.0
MIN_CAMERA_Z = 380.0
ACTOR_HALF_WIDTH = 70.0
ACTOR_BOTTOM_OFFSET = -100.0
ACTOR_TOP_OFFSET = 125.0
_ENVIRONMENT_MANIFEST = None


def configure_environment(environment_manifest=None):
    """Apply optional presentation-room constraints without changing camera fit."""
    global _ENVIRONMENT_MANIFEST
    _ENVIRONMENT_MANIFEST = environment_manifest


def _finite(value):
    return math.isfinite(float(value))


def _lerp(left, right, alpha):
    return float(left) + (float(right) - float(left)) * alpha


def _deduplicated_track(track):
    by_time = {}
    for key in track:
        seconds = round(float(key["seconds"]), 6)
        by_time[seconds] = {"seconds": seconds, "pose": dict(key["pose"])}
    return [by_time[seconds] for seconds in sorted(by_time)]


def sample_actor_pose(track, seconds):
    """Linearly sample a Sequencer presentation transform track at a cue time."""
    keys = _deduplicated_track(track)
    if not keys:
        raise ValueError("actor transform track has no keys")
    sample_time = float(seconds)
    if sample_time <= keys[0]["seconds"]:
        return dict(keys[0]["pose"])
    if sample_time >= keys[-1]["seconds"]:
        return dict(keys[-1]["pose"])
    for left, right in zip(keys, keys[1:]):
        if left["seconds"] <= sample_time <= right["seconds"]:
            span = max(1e-6, right["seconds"] - left["seconds"])
            alpha = (sample_time - left["seconds"]) / span
            fields = set(left["pose"]) | set(right["pose"])
            return {
                field: _lerp(left["pose"].get(field, 0.0), right["pose"].get(field, 0.0), alpha)
                for field in fields
            }
    raise ValueError(f"could not sample actor track at {sample_time}")


def _sample_times(duration_seconds, beats, interval_seconds=0.4):
    duration = float(duration_seconds)
    times = {0.0, round(duration, 6)}
    cursor = 0.0
    while cursor < duration:
        times.add(round(cursor, 6))
        cursor += interval_seconds
    for beat in beats:
        start = float(beat["start_seconds"])
        end = min(duration, start + float(beat["duration_seconds"]))
        times.update((round(start, 6), round((start + end) * 0.5, 6), round(end, 6)))
    return sorted(time for time in times if 0.0 <= time <= duration)


def _camera_basis(camera, target):
    forward = [target[index] - camera[index] for index in range(3)]
    length = math.sqrt(sum(value * value for value in forward))
    if length <= 1e-6:
        raise ValueError("camera and target positions coincide")
    forward = [value / length for value in forward]
    right = [forward[1], -forward[0], 0.0]
    right_length = math.sqrt(right[0] * right[0] + right[1] * right[1])
    right = [value / max(1e-6, right_length) for value in right]
    up = [
        right[1] * forward[2],
        -right[0] * forward[2],
        right[0] * forward[1] - right[1] * forward[0],
    ]
    return forward, right, up


def _dot(left, right):
    return sum(a * b for a, b in zip(left, right))


def _visual_geometry(actor_id, pose, actor_visual_profiles):
    profile = (actor_visual_profiles or {}).get(actor_id, {})
    offset = profile.get("center_offset", {"x": 0.0, "y": 0.0, "z": 12.5})
    extent = profile.get(
        "extent",
        {"x": ACTOR_HALF_WIDTH, "y": ACTOR_HALF_WIDTH,
         "z": (ACTOR_TOP_OFFSET - ACTOR_BOTTOM_OFFSET) * 0.5},
    )
    yaw_delta = math.radians(float(pose.get("yaw", 0.0)) - float(profile.get("root_yaw", 0.0)))
    cos_yaw = math.cos(yaw_delta)
    sin_yaw = math.sin(yaw_delta)
    rotated_offset_x = float(offset.get("x", 0.0)) * cos_yaw - float(offset.get("y", 0.0)) * sin_yaw
    rotated_offset_y = float(offset.get("x", 0.0)) * sin_yaw + float(offset.get("y", 0.0)) * cos_yaw
    return {
        "center": {
            "x": float(pose["x"]) + rotated_offset_x,
            "y": float(pose["y"]) + rotated_offset_y,
            "z": float(pose["z"]) + float(offset.get("z", 12.5)),
        },
        # A horizontal radius remains conservative as actors turn during attacks.
        "horizontal_radius": max(
            ACTOR_HALF_WIDTH,
            math.hypot(float(extent.get("x", ACTOR_HALF_WIDTH)), float(extent.get("y", ACTOR_HALF_WIDTH))),
        ),
        "vertical_extent": max(1.0, float(extent.get("z", 112.5))),
    }


def _actor_sample_points(sampled_positions, actor_visual_profiles):
    points = []
    geometries = {}
    for actor_id, pose in sampled_positions.items():
        geometry = _visual_geometry(actor_id, pose, actor_visual_profiles)
        geometries[actor_id] = geometry
        center = geometry["center"]
        radius = geometry["horizontal_radius"]
        for index in range(8):
            angle = math.radians(index * 45.0)
            lateral_x = math.cos(angle) * radius
            lateral_y = math.sin(angle) * radius
            points.append((center["x"] + lateral_x, center["y"] + lateral_y,
                           center["z"] - geometry["vertical_extent"]))
            points.append((center["x"] + lateral_x, center["y"] + lateral_y,
                           center["z"] + geometry["vertical_extent"]))
    return points, geometries


def project_points(camera_position, target_center, points, horizontal_fov_degrees=HORIZONTAL_FOV_DEGREES,
                   aspect_ratio=ASPECT_RATIO):
    camera = [float(camera_position[axis]) for axis in ("x", "y", "z")]
    target = [float(target_center[axis]) for axis in ("x", "y", "z")]
    forward, right, up = _camera_basis(camera, target)
    tan_half_horizontal = math.tan(math.radians(horizontal_fov_degrees) * 0.5)
    tan_half_vertical = tan_half_horizontal / aspect_ratio
    projected = []
    for point in points:
        relative = [float(point[index]) - camera[index] for index in range(3)]
        depth = _dot(relative, forward)
        if depth <= 1e-3:
            projected.append({"x": float("inf"), "y": float("inf"), "depth": depth})
            continue
        projected.append({
            "x": _dot(relative, right) / (depth * tan_half_horizontal),
            "y": _dot(relative, up) / (depth * tan_half_vertical),
            "depth": depth,
        })
    return projected


def _inside_wall_geometry(camera_position):
    if _ENVIRONMENT_MANIFEST is not None:
        valid = _ENVIRONMENT_MANIFEST["valid_camera_region"]
        if not all(
            float(valid["min"][axis]) <= float(camera_position[axis]) <= float(valid["max"][axis])
            for axis in ("x", "y", "z")
        ):
            return True
        for volume in _ENVIRONMENT_MANIFEST.get("camera_forbidden_volumes", []):
            bounds = volume["bounds"]
            if all(
                float(bounds["min"][axis]) <= float(camera_position[axis]) <= float(bounds["max"][axis])
                for axis in ("x", "y", "z")
            ):
                return True
        return False
    x = abs(float(camera_position["x"]))
    y = abs(float(camera_position["y"]))
    z = float(camera_position["z"])
    if not 0.0 <= z <= 330.0:
        return False
    return (abs(x - 650.0) <= 45.0 and y <= 720.0) or (abs(y - 650.0) <= 45.0 and x <= 720.0)


def _projected_bounds(projections):
    return {
        "min_x": min(item["x"] for item in projections),
        "max_x": max(item["x"] for item in projections),
        "min_y": min(item["y"] for item in projections),
        "max_y": max(item["y"] for item in projections),
    }


def _solve_camera(
    sampled_positions,
    actor_visual_profiles,
    horizontal_fov_degrees=HORIZONTAL_FOV_DEGREES,
    safe_frame_x=SAFE_FRAME_X,
    safe_frame_y=SAFE_FRAME_Y,
    min_camera_distance=MIN_CAMERA_DISTANCE,
    max_camera_distance=MAX_CAMERA_DISTANCE,
    min_camera_z=MIN_CAMERA_Z,
    camera_height_offset=165.0,
    camera_azimuth_degrees=CAMERA_AZIMUTH_DEGREES,
):
    points, geometries = _actor_sample_points(sampled_positions, actor_visual_profiles)
    min_x = min(item["center"]["x"] - item["horizontal_radius"] for item in geometries.values())
    max_x = max(item["center"]["x"] + item["horizontal_radius"] for item in geometries.values())
    min_y = min(item["center"]["y"] - item["horizontal_radius"] for item in geometries.values())
    max_y = max(item["center"]["y"] + item["horizontal_radius"] for item in geometries.values())
    min_z = min(item["center"]["z"] - item["vertical_extent"] for item in geometries.values())
    max_z = max(item["center"]["z"] + item["vertical_extent"] for item in geometries.values())
    target = {
        "x": (min_x + max_x) * 0.5,
        "y": (min_y + max_y) * 0.5,
        "z": (min_z + max_z) * 0.5,
    }
    azimuth = math.radians(float(camera_azimuth_degrees))
    distance = float(min_camera_distance)
    framing = None
    while distance <= max_camera_distance:
        camera = {
            "x": target["x"] + math.cos(azimuth) * distance,
            "y": target["y"] + math.sin(azimuth) * distance,
            "z": max(float(min_camera_z), target["z"] + float(camera_height_offset)),
        }
        if _inside_wall_geometry(camera):
            distance += 20.0
            continue
        projections = project_points(
            camera,
            target,
            points,
            horizontal_fov_degrees=float(horizontal_fov_degrees),
        )
        projected_bounds = _projected_bounds(projections)
        framing = {
            "max_abs_x": max(abs(item["x"]) for item in projections),
            "max_abs_y": max(abs(item["y"]) for item in projections),
            "min_depth": min(item["depth"] for item in projections),
            "projected_bounds": projected_bounds,
            "occupied_width_fraction": (projected_bounds["max_x"] - projected_bounds["min_x"]) * 0.5,
            "occupied_height_fraction": (projected_bounds["max_y"] - projected_bounds["min_y"]) * 0.5,
        }
        if framing["max_abs_x"] <= safe_frame_x and framing["max_abs_y"] <= safe_frame_y:
            break
        distance += 20.0
    if distance > max_camera_distance:
        raise ValueError(f"could not fit actors in camera frame: {framing}")
    planar = math.hypot(target["x"] - camera["x"], target["y"] - camera["y"])
    rotation = {
        "roll": 0.0,
        "pitch": math.degrees(math.atan2(target["z"] - camera["z"], max(1.0, planar))),
        "yaw": math.degrees(math.atan2(target["y"] - camera["y"], target["x"] - camera["x"])),
    }
    return target, camera, rotation, distance, framing, geometries, {
        "min_x": min_x, "max_x": max_x,
        "min_y": min_y, "max_y": max_y,
        "min_z": min_z, "max_z": max_z,
    }


def _validate_sample(sample):
    profile = sample.get("framing_profile", {})
    safe_frame_x = float(profile.get("safe_frame_x", SAFE_FRAME_X))
    safe_frame_y = float(profile.get("safe_frame_y", SAFE_FRAME_Y))
    min_camera_distance = float(profile.get("min_camera_distance", MIN_CAMERA_DISTANCE))
    max_camera_distance = float(profile.get("max_camera_distance", MAX_CAMERA_DISTANCE))
    for group in (sample["target_center"], sample["camera_position"], sample["camera_rotation"]):
        if not all(_finite(value) for value in group.values()):
            raise ValueError(f"non-finite camera value at {sample['seconds']}: {group}")
    if sample["camera_position"]["z"] <= 0.0:
        raise ValueError(f"camera below floor at {sample['seconds']}")
    if _inside_wall_geometry(sample["camera_position"]):
        raise ValueError(f"camera inside temporary wall geometry at {sample['seconds']}")
    if not min_camera_distance <= sample["camera_distance"] <= max_camera_distance:
        raise ValueError(f"camera distance out of range at {sample['seconds']}")
    if not sample["target_actor_ids"]:
        raise ValueError(f"camera has no target actors at {sample['seconds']}")
    if sample["framing"]["max_abs_x"] > safe_frame_x + 1e-6:
        raise ValueError(f"horizontal camera fit failed at {sample['seconds']}")
    if sample["framing"]["max_abs_y"] > safe_frame_y + 1e-6:
        raise ValueError(f"vertical camera fit failed at {sample['seconds']}")


def plan_master_camera(actor_tracks, beats, duration_seconds, original_cues=None, actor_visual_profiles=None):
    """Return a stable time-aware camera track and diagnostic payload."""
    actor_ids = sorted(actor_tracks)
    if not actor_ids:
        raise ValueError("cannot plan a camera without actor tracks")
    samples = []
    for seconds in _sample_times(duration_seconds, beats):
        # Proof-stage reliability rule: keep the complete staged cast in frame.
        # A retreat changes presentation transforms but does not create a sudden
        # reframing discontinuity or make the remaining fight harder to follow.
        target_ids = actor_ids
        sampled = {
            actor_id: sample_actor_pose(actor_tracks[actor_id], seconds)
            for actor_id in target_ids
        }
        if len(sampled) != len(target_ids):
            raise ValueError(f"could not resolve every target actor at {seconds}")
        target, camera, rotation, distance, framing, visual_geometries, target_bounds = _solve_camera(
            sampled, actor_visual_profiles
        )
        sample = {
            "mode": "safe_master_tracking",
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
        }
        _validate_sample(sample)
        samples.append(sample)
    return {
        "protocol": CAMERA_PROTOCOL,
        "authoritative": False,
        "architecture": "time_aware_safe_master_tracking",
        "horizontal_fov_degrees": HORIZONTAL_FOV_DEGREES,
        "aspect_ratio": ASPECT_RATIO,
        "safe_frame": {"x": SAFE_FRAME_X, "y": SAFE_FRAME_Y},
        "actor_visual_profiles": dict(actor_visual_profiles or {}),
        "original_camera_cues": list(original_cues or []),
        "camera_shots": samples,
        "validation": {
            "sample_count": len(samples),
            "all_samples_valid": True,
            "max_abs_projected_x": max(sample["framing"]["max_abs_x"] for sample in samples),
            "max_abs_projected_y": max(sample["framing"]["max_abs_y"] for sample in samples),
        },
    }
