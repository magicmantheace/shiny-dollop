"""Deterministic terminal-state rules for non-authoritative presentation.

Canonical Crawl events decide whether an actor died or was defeated. This module
only prevents later presentation animation from visually resurrecting an actor
whose canonical terminal event has already occurred.
"""

from __future__ import annotations

TERMINAL_ROLES = frozenset({"death", "defeat"})
CORPSE_ROOT_DROP_CM = 70.0
CORPSE_ROOT_MIN_Z = 20.0
CORPSE_ROOT_PITCH_DEGREES = -70.0


def corpse_transform_pose(pose: dict) -> dict:
    """Return the deterministic skeletal-root landing pose for terminal fall."""
    corpse = dict(pose)
    corpse["z"] = max(CORPSE_ROOT_MIN_Z, float(pose.get("z", 90.0)) - CORPSE_ROOT_DROP_CM)
    corpse["pitch"] = CORPSE_ROOT_PITCH_DEGREES
    return corpse


def terminal_start_seconds(intents) -> float | None:
    """Return the earliest terminal presentation intent for one actor."""
    starts = [
        float(intent["start_seconds"])
        for intent in intents
        if intent.get("role") in TERMINAL_ROLES
    ]
    return min(starts) if starts else None


def intent_allowed_after_terminal(intent: dict, terminal_start: float | None) -> bool:
    """Terminal intent is allowed; later non-terminal animation is suppressed."""
    if terminal_start is None:
        return True
    if intent.get("role") in TERMINAL_ROLES:
        return float(intent["start_seconds"]) <= float(terminal_start) + 1.0e-9
    return float(intent["start_seconds"]) < float(terminal_start) - 1.0e-9


def corpse_hold_window(
    death_start_seconds: float,
    source_duration_seconds: float,
    sequence_end_seconds: float,
    *,
    play_rate: float = 1.0,
) -> tuple[float, float]:
    """Return the post-animation interval that must hold the final corpse pose."""
    rate = max(1.0e-6, float(play_rate))
    finish = float(death_start_seconds) + float(source_duration_seconds) / rate
    finish = min(max(float(death_start_seconds), finish), float(sequence_end_seconds))
    return finish, max(finish, float(sequence_end_seconds))


def final_pose_sample_seconds(
    source_duration_seconds: float,
    *,
    fps: int = 60,
) -> float:
    """Sample inside the final source frame instead of exactly at looping end."""
    duration = max(0.0, float(source_duration_seconds))
    frame = 1.0 / max(1, int(fps))
    return max(0.0, duration - frame)
