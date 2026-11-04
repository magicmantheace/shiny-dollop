"""Speak timing semantics (ADR-009, docs/SCENE_PROTOCOL.md): the deterministic
speak-hold derivation shared by the Python library and the Godot preview.

A `speak` event occupies its actor for a hold window [at_ms, at_ms + hold).
The hold is the event's explicit `duration_ms` when present; otherwise it is
derived from the line at a configurable rate and clamped to a configurable
window. The rate and the clamps are changeable configuration variables —
a scene may carry a top-level `timing` object, and the Godot preview exposes
the same values as exported settings — never constants baked into call sites.
Blocking is per-actor only; this module owns the derivation and the schedule
computation (`compute_schedule`); the preview mirrors both.
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


# Dispatch priority at equal effective times (F3.3, docs/SCENE_PROTOCOL.md):
# camera first, then spawn, then everything else in scene order. Mirrored by
# _dispatch_priority in godot/main.gd.
DISPATCH_PRIORITY = {"camera": 0, "spawn": 1}
DEFAULT_DISPATCH_PRIORITY = 2


def compute_schedule(events: list, timing: TimingConfig = DEFAULT_TIMING) -> list:
    """Precompute the dispatch schedule for a validated scene's events.

    The events are assumed validated (studio.schema.validate_scene); this
    function does not re-validate, and it does not mutate its input. It
    returns one plain-dict record per event in DISPATCH order:

    - ``index``: the event's position in the scene's event array;
    - ``op``, ``actor_id`` (None for camera), ``at_ms``;
    - ``effective_ms``: when the event dispatches;
    - ``priority``: the equal-timestamp dispatch priority (camera 0,
      spawn 1, everything else 2);
    - speak events only: ``hold_ms`` (the ADR-009 hold as authored),
      ``window_start_ms`` / ``window_end_ms`` (the actor-occupancy window
      after any truncation), ``interrupted`` (True when a later interrupt
      cut this event's window) and ``interrupts`` (index of the event this
      one truncated, else None). Non-speak records carry hold 0 and None
      windows.

    Semantics (docs/SCENE_PROTOCOL.md, ADR-009 + F3.3 dialogue runtime):
    camera is never gated; spawn is never gated; any other event for an
    actor is delayed to the end of that actor's current speak window when
    its at_ms falls inside it. A speak with ``interrupt: true`` is the one
    exception: it is never delayed — it starts at its at_ms, and when the
    actor's current window contains that start, the window is truncated
    there (the earlier speak keeps the floor up to the cut, no further).
    An interrupt at or after the window's end changes nothing. Processing
    is a single pass in scene order, exactly as the preview computes it.
    """
    records = []
    hold_until: dict = {}  # actor_id -> end of the actor's current speak window
    open_speak: dict = {}  # actor_id -> record of the actor's latest speak
    for index, e in enumerate(events):
        op = e["op"]
        at = e["at_ms"]
        record = {
            "index": index,
            "op": op,
            "actor_id": None if op == "camera" else e.get("actor_id"),
            "at_ms": at,
            "effective_ms": at,
            "priority": DISPATCH_PRIORITY.get(op, DEFAULT_DISPATCH_PRIORITY),
            "hold_ms": 0,
            "window_start_ms": None,
            "window_end_ms": None,
            "interrupted": False,
            "interrupts": None,
        }
        if op != "camera":
            actor_id = e.get("actor_id")
            interrupting = op == "speak" and e.get("interrupt") is True
            if op != "spawn":
                if interrupting:
                    current = open_speak.get(actor_id)
                    if (
                        current is not None
                        and current["window_start_ms"] <= at < current["window_end_ms"]
                    ):
                        current["window_end_ms"] = at
                        current["interrupted"] = True
                        record["interrupts"] = current["index"]
                elif actor_id in hold_until:
                    record["effective_ms"] = max(at, hold_until[actor_id])
            if op == "speak":
                hold = speak_hold_ms(e.get("line", ""), e.get("duration_ms"), timing)
                start = record["effective_ms"]
                record["hold_ms"] = hold
                record["window_start_ms"] = start
                record["window_end_ms"] = start + hold
                hold_until[actor_id] = start + hold
                open_speak[actor_id] = record
        records.append(record)
    records.sort(key=lambda r: (r["effective_ms"], r["priority"], r["index"]))
    return records
