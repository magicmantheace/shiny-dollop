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
    - ``look_at``: the event's gaze intent (F4.1) passed through unchanged
      (None when absent), with ``gaze_window_start_ms`` /
      ``gaze_window_end_ms`` giving the window the gaze applies to: the
      occupancy window for speak (after any truncation), the duration
      window for move, and for emote the span from its effective time to
      the same actor's next event (or the end of the schedule). Gaze
      never changes any scheduling value. Both are None without look_at.
    - interact events only (F4.2): ``action`` and ``prop_id`` passed
      through, the occupancy ``window_start_ms`` / ``window_end_ms`` set
      like a speak's, ``phases`` (the composite's phase windows — see
      below), ``attach_ms`` (pick_up: when the prop reaches the hand) and
      ``release_ms`` (put_down: when the prop leaves the hand). Every
      non-camera record also carries ``holding_after`` (the prop the
      actor holds once this event has run, else None) and
      ``seated_after`` (True from a sit until the actor's next move).

    Semantics (docs/SCENE_PROTOCOL.md, ADR-009 + F3.3 dialogue runtime):
    camera is never gated; spawn is never gated; any other event for an
    actor is delayed to the end of that actor's current speak window when
    its at_ms falls inside it. A speak with ``interrupt: true`` is the one
    exception: it is never delayed — it starts at its at_ms, and when the
    actor's current window contains that start, the window is truncated
    there (the earlier speak keeps the floor up to the cut, no further).
    An interrupt at or after the window's end changes nothing. Processing
    is a single pass in scene order, exactly as the preview computes it.

    Interact composites (F4.2) occupy their actor for the event's
    ``duration_ms`` exactly like a speak hold: the window gates later
    same-actor events (including speaks) and is itself gated by an open
    speak/interact window. The phases inside the window are fixed:
    pick_up is ``reach`` for the first half, then the prop attaches at
    the midpoint (``attach_ms``) and the ``hold`` phase runs to the
    window end — the attachment itself persists past the window until a
    put_down; drink is a single ``consume`` phase; put_down is a single
    ``lower`` phase with the release at the window end (``release_ms``);
    sit is a single ``enter`` phase (the actor is seated from the window
    end until its next move). An interrupting speak truncates speak
    windows only: one landing inside an interact window starts at its
    at_ms and runs concurrently with the composite.
    """
    records = []
    hold_until: dict = {}  # actor_id -> end of the actor's current occupancy window
    open_speak: dict = {}  # actor_id -> record of the actor's latest speak
    held_now: dict = {}  # actor_id -> prop_id currently held (F4.2)
    seated_now: dict = {}  # actor_id -> True while seated (F4.2)
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
            "look_at": e.get("look_at"),
            "gaze_window_start_ms": None,
            "gaze_window_end_ms": None,
            "action": None,
            "prop_id": None,
            "phases": [],
            "attach_ms": None,
            "release_ms": None,
            "holding_after": None,
            "seated_after": False,
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
            if op == "interact":
                # Composite expansion (F4.2): the actor is occupied for
                # duration_ms (gated above like any non-spawn event), and
                # the window gates later same-actor events via hold_until.
                action = e.get("action")
                start = record["effective_ms"]
                duration = int(e.get("duration_ms", 0))
                end = start + duration
                record["action"] = action
                record["prop_id"] = e.get("prop_id")
                record["window_start_ms"] = start
                record["window_end_ms"] = end
                hold_until[actor_id] = end
                if action == "pick_up":
                    attach = start + duration // 2
                    record["attach_ms"] = attach
                    record["phases"] = [
                        {"name": "reach", "start_ms": start, "end_ms": attach},
                        {"name": "hold", "start_ms": attach, "end_ms": end},
                    ]
                    held_now[actor_id] = e.get("prop_id")
                elif action == "drink":
                    record["phases"] = [
                        {"name": "consume", "start_ms": start, "end_ms": end},
                    ]
                elif action == "put_down":
                    record["release_ms"] = end
                    record["phases"] = [
                        {"name": "lower", "start_ms": start, "end_ms": end},
                    ]
                    held_now.pop(actor_id, None)
                elif action == "sit":
                    record["phases"] = [
                        {"name": "enter", "start_ms": start, "end_ms": end},
                    ]
                    seated_now[actor_id] = True
            if op == "move":
                seated_now.pop(actor_id, None)
            record["holding_after"] = held_now.get(actor_id)
            record["seated_after"] = bool(seated_now.get(actor_id))
        records.append(record)
    # Gaze windows (F4.1, docs/SCENE_PROTOCOL.md): gaze follows the event's
    # scheduled window and never changes it. Computed after the main pass
    # so a speak's window already reflects any interrupt truncation.
    scene_end = 0
    for record in records:
        end = record["effective_ms"]
        if record["window_end_ms"] is not None:
            end = max(end, record["window_end_ms"])
        if record["op"] == "move":
            event = events[record["index"]]
            end = max(end, record["effective_ms"] + int(event.get("duration_ms", 0)))
        scene_end = max(scene_end, end)
    pending_emote: dict = {}  # actor_id -> emote record awaiting its gaze end
    for record in records:
        actor_id = record["actor_id"]
        if actor_id in pending_emote:
            pending_emote[actor_id]["gaze_window_end_ms"] = record["effective_ms"]
            del pending_emote[actor_id]
        if record["look_at"] is None:
            continue
        event = events[record["index"]]
        if record["op"] == "speak":
            record["gaze_window_start_ms"] = record["window_start_ms"]
            record["gaze_window_end_ms"] = record["window_end_ms"]
        elif record["op"] == "move":
            record["gaze_window_start_ms"] = record["effective_ms"]
            record["gaze_window_end_ms"] = (
                record["effective_ms"] + int(event.get("duration_ms", 0))
            )
        elif record["op"] == "emote":
            record["gaze_window_start_ms"] = record["effective_ms"]
            pending_emote[actor_id] = record
    for record in pending_emote.values():
        record["gaze_window_end_ms"] = scene_end
    records.sort(key=lambda r: (r["effective_ms"], r["priority"], r["index"]))
    return records
