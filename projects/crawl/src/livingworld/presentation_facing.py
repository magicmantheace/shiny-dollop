"""Deterministic presentation-facing math for live Underreach actors."""

from __future__ import annotations

import math


LOCOMOTION_ROOT_YAW_OFFSET_DEGREES = -90.0
FACING_TOLERANCE_DEGREES = 12.0


def normalize_yaw(value: float) -> float:
    return (float(value) + 180.0) % 360.0 - 180.0


def signed_angular_error(current_yaw: float, desired_yaw: float) -> float:
    return normalize_yaw(float(desired_yaw) - float(current_yaw))


def desired_facing_for_movement(
    movement_x: float,
    movement_y: float,
    *,
    current_yaw: float,
    root_yaw_offset_degrees: float = LOCOMOTION_ROOT_YAW_OFFSET_DEGREES,
) -> float:
    if math.hypot(float(movement_x), float(movement_y)) <= 1e-6:
        return normalize_yaw(current_yaw)
    world_direction = math.degrees(math.atan2(float(movement_y), float(movement_x)))
    return normalize_yaw(world_direction + float(root_yaw_offset_degrees))


def plan_turn(current_yaw: float, desired_yaw: float, *, mode: str) -> dict:
    error = signed_angular_error(current_yaw, desired_yaw)
    magnitude = abs(error)
    if magnitude <= FACING_TOLERANCE_DEGREES:
        action = "aligned"
        duration = 0.0
    else:
        action = (
            "turn_45" if magnitude <= 67.5 else
            "turn_90" if magnitude <= 112.5 else
            "turn_135" if magnitude <= 157.5 else
            "turn_180"
        )
        duration = round(max(0.10, min(0.36, magnitude / 500.0)), 6)
    return {
        "current_yaw": normalize_yaw(current_yaw),
        "desired_yaw": normalize_yaw(desired_yaw),
        "angular_error": error,
        "absolute_angular_error": magnitude,
        "facing_mode": mode,
        "turn_action": action,
        "duration_seconds": duration,
    }
