"""Speak timing semantics (ADR-009, docs/SCENE_PROTOCOL.md): the deterministic
speak-hold derivation shared by the Python library and the Godot preview.

A `speak` event occupies its actor for a hold window [at_ms, at_ms + hold).
The hold is the event's explicit `duration_ms` when present; otherwise it is
derived from the line at a configurable rate and clamped to a configurable
window. The rate and the clamps are changeable configuration variables —
a scene may carry a top-level `timing` object, and the Godot preview exposes
the same values as exported settings — never constants baked into call sites.
Blocking is per-actor only; this module owns the derivation, the preview owns
the scheduling.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

DEFAULT_SPEAK_CHARS_PER_SECOND = 15.0
DEFAULT_SPEAK_MIN_HOLD_MS = 800
DEFAULT_SPEAK_MAX_HOLD_MS = 15000

# Explicit speak durations share the wire bounds of `move` durations
# (schemas/scene.schema.json: integer 100..60000).
EXPLICIT_DURATION_MIN_MS = 100
EXPLICIT_DURATION_MAX_MS = 60000

TIMING_KEYS = frozenset(
    {"speak_chars_per_second", "speak_min_hold_ms", "speak_max_hold_ms"}
)


@dataclass(frozen=True)
class TimingConfig:
    speak_chars_per_second: float = DEFAULT_SPEAK_CHARS_PER_SECOND
    speak_min_hold_ms: int = DEFAULT_SPEAK_MIN_HOLD_MS
    speak_max_hold_ms: int = DEFAULT_SPEAK_MAX_HOLD_MS


DEFAULT_TIMING = TimingConfig()


def resolve_timing(raw: object) -> TimingConfig:
    """Validate a scene-level `timing` object into a TimingConfig.

    `None` yields the defaults. Raises ValueError on unknown keys or
    out-of-range values; callers in schema.py translate that to
    ValidationError.
    """
    if raw is None:
        return DEFAULT_TIMING
    if not isinstance(raw, dict):
        raise ValueError("timing must be an object")
    unknown = set(raw) - TIMING_KEYS
    if unknown:
        raise ValueError(f"timing: unknown keys {sorted(unknown)}")
    rate = raw.get("speak_chars_per_second", DEFAULT_SPEAK_CHARS_PER_SECOND)
    if type(rate) not in (int, float) or not 0 < rate <= 100:
        raise ValueError("timing.speak_chars_per_second must be a number in (0, 100]")
    min_hold = raw.get("speak_min_hold_ms", DEFAULT_SPEAK_MIN_HOLD_MS)
    max_hold = raw.get("speak_max_hold_ms", DEFAULT_SPEAK_MAX_HOLD_MS)
    for name, value in (
        ("speak_min_hold_ms", min_hold),
        ("speak_max_hold_ms", max_hold),
    ):
        if type(value) is not int or not 0 <= value <= EXPLICIT_DURATION_MAX_MS:
            raise ValueError(f"timing.{name} must be an integer in [0, 60000]")
    if min_hold > max_hold:
        raise ValueError("timing.speak_min_hold_ms must not exceed speak_max_hold_ms")
    return TimingConfig(
        speak_chars_per_second=float(rate),
        speak_min_hold_ms=min_hold,
        speak_max_hold_ms=max_hold,
    )


def speak_hold_ms(
    line: str,
    duration_ms: object = None,
    timing: TimingConfig = DEFAULT_TIMING,
) -> int:
    """Hold length for one speak event, in milliseconds.

    An explicit `duration_ms` (integer, wire bounds 100..60000) wins.
    Otherwise the hold derives from the line length at the configured rate,
    rounded up to the next millisecond, and is clamped to the configured
    [min, max] window. Pure function of its inputs: previews are
    deterministic and the future TTS stage reconciles the same number.
    """
    if duration_ms is not None:
        if type(duration_ms) is not int or not (
            EXPLICIT_DURATION_MIN_MS <= duration_ms <= EXPLICIT_DURATION_MAX_MS
        ):
            raise ValueError(
                "speak duration_ms must be an integer in [100, 60000]"
            )
        return duration_ms
    derived = math.ceil(len(line) * 1000 / timing.speak_chars_per_second)
    return max(timing.speak_min_hold_ms, min(timing.speak_max_hold_ms, derived))
