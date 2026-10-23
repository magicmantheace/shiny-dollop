"""Deterministic presentation helpers for locomotion facing and clip transitions.

These helpers operate only on presentation transforms/timing. They never alter
canonical Crawl events or outcomes and intentionally have no Unreal dependency.
"""

import math


DEFAULT_BLEND_SECONDS = 0.10
MIN_BLEND_SECONDS = 0.05
MAX_BLEND_SECONDS = 0.18
LOCOMOTION_ROOT_YAW_OFFSET_DEGREES = -90.0


def normalize_angle(angle):
    return (float(angle) + 180.0) % 360.0 - 180.0


def travel_distance(start_pose, end_pose):
    dx = float(end_pose["x"]) - float(start_pose["x"])
    dy = float(end_pose["y"]) - float(start_pose["y"])
    return math.hypot(dx, dy)


def travel_yaw(start_pose, end_pose, root_yaw_offset_degrees=LOCOMOTION_ROOT_YAW_OFFSET_DEGREES):
    """Return actor-root yaw that makes authored +Y locomotion face travel."""
    dx = float(end_pose["x"]) - float(start_pose["x"])
    dy = float(end_pose["y"]) - float(start_pose["y"])
    if math.hypot(dx, dy) <= 1.0e-4:
        return float(start_pose.get("yaw", 0.0))
    world_direction = math.degrees(math.atan2(dy, dx))
    return normalize_angle(world_direction + float(root_yaw_offset_degrees))


def orient_pose_for_travel(start_pose, end_pose, root_yaw_offset_degrees=LOCOMOTION_ROOT_YAW_OFFSET_DEGREES):
    result = dict(end_pose)
    result["yaw"] = travel_yaw(start_pose, end_pose, root_yaw_offset_degrees)
    return result


def blend_seconds(requested=None, duration_seconds=None):
    """Clamp a transition window so short clips cannot be swallowed by easing."""
    value = DEFAULT_BLEND_SECONDS if requested is None else float(requested)
    value = max(MIN_BLEND_SECONDS, min(MAX_BLEND_SECONDS, value))
    if duration_seconds is not None:
        duration = max(0.0, float(duration_seconds))
        value = min(value, duration * 0.25)
    return max(0.0, value)


def blend_frames(fps, requested=None, duration_seconds=None):
    return max(0, int(round(blend_seconds(requested, duration_seconds) * float(fps))))


def transition_debug(start_frame, end_frame, fps, blend_in_seconds=None, blend_out_seconds=None):
    duration_frames = max(1, int(end_frame) - int(start_frame))
    duration_seconds = duration_frames / float(fps)
    return {
        "start_frame": int(start_frame),
        "end_frame": int(end_frame),
        "duration_seconds": duration_seconds,
        "blend_in_frames": blend_frames(fps, blend_in_seconds, duration_seconds),
        "blend_out_frames": blend_frames(fps, blend_out_seconds, duration_seconds),
    }
