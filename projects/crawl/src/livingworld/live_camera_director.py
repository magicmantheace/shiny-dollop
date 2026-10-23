"""Deterministic bounded-lookahead camera direction for live Underreach presentation.

The director is presentation-only.  It consumes the incremental scheduler's
actor state and command cues, never mutates the Descent, and validates every
placement against the accepted dungeon manifest before emitting a camera cut.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
from time import perf_counter
from typing import Any, Iterable


LIVE_CAMERA_PROTOCOL = "underreach.live-camera.v1"
LIVE_CAMERA_DIRECTOR_VERSION = "29a2.1"
COMBAT_MODES = {"combat_pair", "impact", "reaction"}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class LiveCameraConfig:
    presentation_delay_ticks: int = 3
    camera_lookahead_ticks: int = 2
    minimum_shot_seconds: float = 0.4
    maximum_shot_seconds: float = 5.0
    combat_hold_seconds: float = 1.8
    death_hold_seconds: float = 2.5
    cut_cooldown_seconds: float = 0.35
    horizontal_fov_degrees: float = 40.0
    minimum_combat_width_occupancy: float = 0.35
    minimum_combat_height_occupancy: float = 0.64
    minimum_wall_clearance_cm: float = 80.0

    def __post_init__(self) -> None:
        if self.presentation_delay_ticks < 0 or self.camera_lookahead_ticks < 0:
            raise ValueError("camera delay/lookahead ticks cannot be negative")
        if not 0 < self.minimum_shot_seconds <= self.maximum_shot_seconds:
            raise ValueError("invalid live camera shot duration range")
        if self.cut_cooldown_seconds < 0 or self.death_hold_seconds <= 0:
            raise ValueError("invalid live camera hold/cooldown")


def _point_inside(point: dict[str, float], bounds: dict[str, Any], margin: float = 0.0) -> bool:
    return all(
        float(bounds["min"][axis]) + margin <= float(point[axis]) <= float(bounds["max"][axis]) - margin
        for axis in ("x", "y", "z")
    )


def _segment_intersects_aabb(start: dict[str, float], end: dict[str, float], bounds: dict[str, Any]) -> bool:
    lower, upper = 0.0, 1.0
    for axis in ("x", "y", "z"):
        origin = float(start[axis])
        direction = float(end[axis]) - origin
        if abs(direction) < 1e-9:
            if origin < float(bounds["min"][axis]) or origin > float(bounds["max"][axis]):
                return False
            continue
        first = (float(bounds["min"][axis]) - origin) / direction
        second = (float(bounds["max"][axis]) - origin) / direction
        if first > second:
            first, second = second, first
        lower, upper = max(lower, first), min(upper, second)
        if lower > upper:
            return False
    return upper >= max(lower, 1e-4) and lower <= 0.9999


def _basis(camera: dict[str, float], target: dict[str, float]):
    forward = [target[a] - camera[a] for a in ("x", "y", "z")]
    length = math.sqrt(sum(v * v for v in forward))
    forward = [v / max(length, 1e-6) for v in forward]
    right = [forward[1], -forward[0], 0.0]
    right_length = math.hypot(right[0], right[1])
    right = [v / max(right_length, 1e-6) for v in right]
    up = [
        right[1] * forward[2],
        -right[0] * forward[2],
        right[0] * forward[1] - right[1] * forward[0],
    ]
    return forward, right, up


def _dot(left, right) -> float:
    return sum(a * b for a, b in zip(left, right))


class LiveCameraDirector:
    """Stateful live director which uses only current cues and bounded lookahead."""

    def __init__(
        self,
        descent_id: str,
        *,
        presentation_seed: str,
        environment: dict[str, Any],
        config: LiveCameraConfig | None = None,
    ) -> None:
        self.descent_id = descent_id
        self.presentation_seed = presentation_seed
        self.environment = json.loads(_canonical(environment))
        self.config = config or LiveCameraConfig()
        self.active_shot: dict[str, Any] | None = None
        self.shots: list[dict[str, Any]] = []
        self.command_stream: list[dict[str, Any]] = []
        self.maximum_transient_history = 1024
        self.last_cut_seconds = -math.inf
        self.locked_terminal_until = -math.inf
        self.latest_frame_sequence = 0
        self.latest_event_tick = -1
        self.duplicate_frame_count = 0
        self.reconnect_restore_count = 0
        self.rejections = {"geometry": 0, "los": 0, "occupancy": 0}
        self.candidate_counts: list[int] = []
        self.rejected_counts: list[int] = []
        self.decision_times_ms: list[float] = []
        self.decision_latencies_ticks: list[int] = []
        self.fallback_count = 0
        self.hold_count = 0
        self.pending_focus_transition: dict[str, Any] | None = None
        self.acquisition_records: list[dict[str, Any]] = []
        self.actor_readiness_waits = 0
        self.stale_target_incidents = 0

    def _presentable(self, actor_id: str, actor_states: dict[str, Any]) -> bool:
        state = actor_states.get(actor_id)
        if state is None:
            return False
        value = self._actor_dict(state)
        return bool(value.get("spawned", True))

    @staticmethod
    def _actor_dict(state: Any) -> dict[str, Any]:
        return state.as_dict() if hasattr(state, "as_dict") else dict(state)

    def _targets(self, ids: Iterable[str], actor_states: dict[str, Any]) -> dict[str, dict[str, Any]]:
        result = {}
        for actor_id in ids:
            if actor_id in actor_states:
                result[actor_id] = self._actor_dict(actor_states[actor_id])
        return result

    def _placement(self, mode: str, targets: dict[str, dict[str, Any]]) -> tuple[dict[str, float], dict[str, float]]:
        poses = [item["transform"] for item in targets.values()]
        if poses:
            x = sum(float(p["x"]) for p in poses) / len(poses)
            y = sum(float(p["y"]) for p in poses) / len(poses)
        else:
            x = y = 0.0
        terminal = any(bool(item.get("terminal")) for item in targets.values())
        if mode == "combat_pair":
            return ({"x": x, "y": y - 650.0, "z": 250.0}, {"x": x, "y": y, "z": 120.0})
        if mode == "death_hold":
            return ({"x": x - 420.0, "y": y - 700.0, "z": 260.0}, {"x": x, "y": y, "z": 100.0})
        if mode == "follow":
            return ({"x": x - 500.0, "y": y - 560.0, "z": 260.0}, {"x": x, "y": y, "z": 118.0})
        if mode == "activity_wide":
            return ({"x": 650.0, "y": -850.0, "z": 340.0}, {"x": x, "y": y, "z": 112.0})
        # establishing and fallback_static share the accepted safe axis, with a
        # slightly wider distance than the old QA camera.
        z = 245.0 if terminal else 320.0
        return ({"x": 0.0, "y": -1050.0, "z": z}, {"x": x, "y": y, "z": 112.0})

    def _occupancy(
        self,
        camera: dict[str, float],
        target: dict[str, float],
        targets: dict[str, dict[str, Any]],
    ) -> dict[str, float]:
        forward, right, up = _basis(camera, target)
        tan_h = math.tan(math.radians(self.config.horizontal_fov_degrees) / 2.0)
        tan_v = tan_h / (16.0 / 9.0)
        projected = []
        for item in targets.values():
            pose = item["transform"]
            fallen = bool(item.get("terminal"))
            half_x, half_y = (90.0, 135.0) if fallen else (50.0, 35.0)
            bottom, top = (20.0, 105.0) if fallen else (0.0, 190.0)
            for dx in (-half_x, half_x):
                for dy in (-half_y, half_y):
                    for dz in (bottom, top):
                        point = [float(pose["x"]) + dx, float(pose["y"]) + dy, float(pose.get("z", 0.0)) - 94.0 + dz]
                        relative = [point[i] - camera[a] for i, a in enumerate(("x", "y", "z"))]
                        depth = _dot(relative, forward)
                        if depth <= 1e-3:
                            continue
                        projected.append((_dot(relative, right) / (depth * tan_h), _dot(relative, up) / (depth * tan_v)))
        if not projected:
            return {"width": 0.0, "height": 0.0, "max_abs_x": math.inf, "max_abs_y": math.inf}
        xs, ys = [p[0] for p in projected], [p[1] for p in projected]
        return {
            "width": (max(xs) - min(xs)) / 2.0,
            "height": (max(ys) - min(ys)) / 2.0,
            "max_abs_x": max(abs(v) for v in xs),
            "max_abs_y": max(abs(v) for v in ys),
        }

    def _validate(self, mode: str, camera: dict[str, float], target: dict[str, float], targets: dict[str, dict[str, Any]]):
        valid_region = self.environment.get("valid_camera_region", {
            "min": {"x": -1240, "y": -1740, "z": 80}, "max": {"x": 1240, "y": 1740, "z": 620}
        })
        room = self.environment.get("room_bounds", valid_region)
        obstacles = self.environment.get("camera_forbidden_volumes", [])
        clearance = min(
            camera["x"] - float(room["min"]["x"]), float(room["max"]["x"]) - camera["x"],
            camera["y"] - float(room["min"]["y"]), float(room["max"]["y"]) - camera["y"],
            camera["z"] - float(room["min"]["z"]), float(room["max"]["z"]) - camera["z"],
        )
        inside_obstacle = any(_point_inside(camera, item["bounds"]) for item in obstacles)
        geometry_valid = _point_inside(camera, valid_region) and not inside_obstacle and clearance >= self.config.minimum_wall_clearance_cm
        target_points = {
            actor_id: {
                "x": float(item["transform"]["x"]), "y": float(item["transform"]["y"]),
                "z": 62.0 if item.get("terminal") else 125.0,
            }
            for actor_id, item in targets.items()
        }
        los_hits = {
            actor_id: [volume["id"] for volume in obstacles if _segment_intersects_aabb(camera, point, volume["bounds"])]
            for actor_id, point in target_points.items()
        }
        los_hits = {key: value for key, value in los_hits.items() if value}
        occupancy = self._occupancy(camera, target, targets)
        occupancy_valid = occupancy["max_abs_x"] <= 0.94 and occupancy["max_abs_y"] <= 0.94
        if mode in COMBAT_MODES:
            occupancy_valid = occupancy_valid and (
                occupancy["width"] >= self.config.minimum_combat_width_occupancy
                and occupancy["height"] >= self.config.minimum_combat_height_occupancy
            )
        return {
            "geometry_valid": geometry_valid,
            "los_valid": not los_hits,
            "occupancy_valid": occupancy_valid,
            "occupancy_width": occupancy["width"],
            "occupancy_height": occupancy["height"],
            "minimum_wall_clearance_cm": clearance,
            "los_hits": los_hits,
        }

    def _candidate(self, mode: str, ids: list[str], actor_states: dict[str, Any], reason_ids: list[str], score: float):
        targets = self._targets(ids, actor_states)
        camera, target = self._placement(mode, targets)
        validation = self._validate(mode, camera, target, targets)
        # Population fixtures can place a pair near opposite edges of the
        # compact formation.  The legacy fixed fallback was safe for walls but
        # could still clip one of those bodies.  Pull back along the same
        # accepted sightline in small deterministic steps, stopping at the
        # first fully valid fit.  Combat minimum occupancy remains enforced, so
        # this cannot turn a readable combat shot into a distant overview.
        if not validation["occupancy_valid"]:
            origin = dict(camera)
            delta = {axis: float(origin[axis]) - float(target[axis]) for axis in ("x", "y", "z")}
            fitted_candidates = []
            for scale in (1.03, 1.06, 1.09, 1.12, 1.15, 1.18, 1.21, 1.24):
                fitted_candidates.append({
                    axis: float(target[axis]) + delta[axis] * scale
                    for axis in ("x", "y", "z")
                })

            # If the target spread runs toward the room's near wall, a pure
            # pull-back can exhaust wall clearance before the bodies fit.  Try
            # the same deterministic shot distance from alternate safe axes.
            # This is especially important for the 29A.2 compact formation,
            # where filming across a long row is safer than backing through a
            # wall.  Every alternative still passes the normal geometry, LOS,
            # and occupancy checks.
            distance = 650.0 if mode in COMBAT_MODES else 760.0 if mode == "follow" else 1050.0
            valid_region = self.environment.get("valid_camera_region", {
                "min": {"x": -1240, "y": -1740, "z": 80},
                "max": {"x": 1240, "y": 1740, "z": 620},
            })
            room = self.environment.get("room_bounds", valid_region)
            margin = self.config.minimum_wall_clearance_cm
            lower = {
                axis: max(float(valid_region["min"][axis]), float(room["min"][axis]) + margin)
                for axis in ("x", "y", "z")
            }
            upper = {
                axis: min(float(valid_region["max"][axis]), float(room["max"][axis]) - margin)
                for axis in ("x", "y", "z")
            }
            for dx, dy in ((0.0, -1.0), (0.7071, -0.7071), (-0.7071, -0.7071), (1.0, 0.0), (-1.0, 0.0), (0.0, 1.0)):
                fitted_candidates.append({
                    "x": min(upper["x"], max(lower["x"], float(target["x"]) + dx * distance)),
                    "y": min(upper["y"], max(lower["y"], float(target["y"]) + dy * distance)),
                    "z": min(upper["z"], max(lower["z"], float(origin["z"]))),
                })

            target_offsets = [(0.0, 0.0, 0.0)] + [
                (ox, oy, oz)
                for ox in (-50.0, 50.0, -100.0, 100.0)
                for oy in (0.0, -50.0, 50.0, -100.0, 100.0)
                for oz in (0.0, -25.0, 25.0)
            ]
            found_fit = False
            for fitted in fitted_candidates:
                for ox, oy, oz in target_offsets:
                    fitted_target = {
                        "x": float(target["x"]) + ox,
                        "y": float(target["y"]) + oy,
                        "z": float(target["z"]) + oz,
                    }
                    fitted_validation = self._validate(mode, fitted, fitted_target, targets)
                    if all(fitted_validation[key] for key in ("geometry_valid", "los_valid", "occupancy_valid")):
                        camera, target, validation = fitted, fitted_target, fitted_validation
                        found_fit = True
                        break
                if found_fit:
                    break
        return {
            "mode": mode, "target_actor_ids": sorted(targets), "camera_position": camera,
            "target_center": target, "reason_event_ids": sorted(set(reason_ids)),
            "score": score, **validation,
        }

    def _choose(self, candidates: list[dict[str, Any]]) -> dict[str, Any]:
        valid = []
        rejected = 0
        for item in candidates:
            reasons = []
            if not item["geometry_valid"]:
                reasons.append("geometry")
            if not item["los_valid"]:
                reasons.append("los")
            if not item["occupancy_valid"]:
                reasons.append("occupancy")
            if reasons:
                rejected += 1
                for reason in reasons:
                    self.rejections[reason] += 1
            else:
                valid.append(item)
        self.candidate_counts.append(len(candidates))
        self.rejected_counts.append(rejected)
        if valid:
            return max(valid, key=lambda item: (item["score"], _digest(item)))
        fallback = next((item for item in candidates if item["mode"] == "fallback_static"), None)
        if fallback is None:
            fallback = candidates[-1]
        self.fallback_count += 1
        return fallback

    def _cut(self, candidate: dict[str, Any], seconds: float, frame_sequence: int) -> dict[str, Any]:
        if self.active_shot is not None:
            self.active_shot["end_seconds"] = round(seconds, 6)
            self.active_shot["duration_seconds"] = round(seconds - self.active_shot["start_seconds"], 6)
        shot_body = {
            **candidate,
            "start_seconds": round(seconds, 6),
            "end_seconds": None,
            "frame_sequence": frame_sequence,
        }
        shot_body["shot_id"] = f"shot_{_digest(shot_body)[:20]}"
        self.active_shot = shot_body
        self.shots.append(shot_body)
        if len(self.shots) > self.maximum_transient_history:
            del self.shots[:-self.maximum_transient_history]
        self.last_cut_seconds = seconds
        if candidate["mode"] == "death_hold":
            self.locked_terminal_until = seconds + self.config.death_hold_seconds
            self.hold_count += 1
        payload = {
            "type": "camera_cut", "actor_id": None, "presentation_seconds": round(seconds, 6),
            "shot_id": shot_body["shot_id"], "camera_mode": candidate["mode"],
            "target_actor_ids": candidate["target_actor_ids"], "camera_position": candidate["camera_position"],
            "target_center": candidate["target_center"], "reason_event_ids": candidate["reason_event_ids"],
            "validation": {key: candidate[key] for key in (
                "geometry_valid", "los_valid", "occupancy_valid", "occupancy_width",
                "occupancy_height", "minimum_wall_clearance_cm"
            )},
        }
        if candidate.get("focus_transition_id"):
            payload.update({
                "focus_transition_id": candidate["focus_transition_id"],
                "focus_reason": candidate.get("focus_reason"),
                "focus_mode": candidate.get("focus_mode"),
            })
        command = {"command_id": f"cmd_{_digest(payload)[:20]}", **payload}
        self.command_stream.append(command)
        if len(self.command_stream) > self.maximum_transient_history:
            del self.command_stream[:-self.maximum_transient_history]
        return command

    def direct(
        self,
        *,
        frame_sequence: int,
        current_events: Iterable[Any],
        lookahead_events: Iterable[Any],
        commands: list[dict[str, Any]],
        actor_states: dict[str, Any],
        from_seconds: float,
        to_seconds: float,
        authoritative_tick: int,
        focus_transition: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        started = perf_counter()
        if frame_sequence <= self.latest_frame_sequence:
            self.duplicate_frame_count += 1
            return []
        current = list(current_events)
        future = list(lookahead_events)
        if focus_transition:
            self.pending_focus_transition = json.loads(_canonical(focus_transition))
        focus_transition = self.pending_focus_transition
        current_tick = max([int(item.tick) for item in current] + [self.latest_event_tick])
        if any(int(item.tick) > current_tick + self.config.camera_lookahead_ticks for item in future):
            raise ValueError("live camera attempted to inspect beyond configured lookahead")
        self.latest_event_tick = max(self.latest_event_tick, current_tick)
        self.latest_frame_sequence = frame_sequence
        future_ids = [item.id for item in future]
        emitted: list[dict[str, Any]] = []

        cues: list[tuple[float, str, list[str], list[str], float]] = []
        focus_by_transition: dict[str, dict[str, Any]] = {}
        ready_ids = [
            key for key, state in sorted(actor_states.items())
            if self._presentable(key, actor_states) and not self._actor_dict(state).get("terminal")
        ]
        if self.active_shot is None:
            population_lineup = len(ready_ids) > 4
            ids = ready_ids if population_lineup else ready_ids[:2]
            cues.append((from_seconds, "activity_wide" if population_lineup else "establishing", ids, future_ids[:2], 35.0))
        elif not self.active_shot.get("target_actor_ids") and ready_ids:
            # Replace a startup-safe empty establishing shot immediately when
            # the first presentable actor becomes available.
            cues.append((from_seconds, "follow", ready_ids[:1], ["actor_ready"], 108.0))
        if focus_transition and focus_transition.get("to_descender_id"):
            transition_id = str(focus_transition["transition_id"])
            focus_by_transition[transition_id] = focus_transition
            focus_actor_id = str(focus_transition["to_descender_id"])
            if self._presentable(focus_actor_id, actor_states):
                cues.append((
                    max(from_seconds, float(focus_transition.get("presentation_seconds", from_seconds))),
                    "follow", [focus_actor_id], [transition_id],
                    112.0 if focus_transition.get("mode") == "manual" else 82.0,
                ))
            else:
                self.actor_readiness_waits += 1
                self.acquisition_records.append({
                    "transition_id": transition_id,
                    "requested_actor_id": focus_actor_id,
                    "requested_seconds": float(focus_transition.get("presentation_seconds", from_seconds)),
                    "acquired_seconds": None,
                    "latency_seconds": None,
                    "actor_ready": False,
                    "target_visible": False,
                    "fallback_reason": "presentation_actor_not_ready",
                })
        for command in commands:
            seconds = float(command["presentation_seconds"])
            source = [command.get("source_event_id")] if command.get("source_event_id") else []
            if command["type"] == "play_attack":
                cues.append((seconds, "combat_pair", [command["actor_id"], command["target_actor_id"]], source, 95.0))
            elif command["type"] == "play_terminal":
                context = [
                    key for key, state in sorted(actor_states.items())
                    if key != command["actor_id"] and not self._actor_dict(state).get("terminal")
                ]
                cues.append((seconds, "death_hold", [command["actor_id"], *context[:1]], source, 120.0))
            elif command["type"] == "play_locomotion":
                cues.append((seconds, "follow", [command["actor_id"]], source, 52.0))
        cues.sort(key=lambda item: (item[0], -item[4], item[1]))

        for seconds, mode, ids, reasons, score in cues:
            focus = next((focus_by_transition[item] for item in reasons if item in focus_by_transition), None)
            if self.active_shot is not None:
                deadline = float(self.active_shot["start_seconds"]) + self.config.maximum_shot_seconds
                if seconds > deadline and deadline >= self.locked_terminal_until:
                    alive = [
                        key for key, state in sorted(actor_states.items())
                        if not self._actor_dict(state).get("terminal")
                    ]
                    deadline_ids = alive[:1] or self.active_shot["target_actor_ids"][:1]
                    deadline_mode = "follow" if alive else "activity_wide"
                    deadline_candidates = [
                        self._candidate(deadline_mode, deadline_ids, actor_states, future_ids[:2], 48.0),
                        self._candidate("fallback_static", deadline_ids, actor_states, future_ids[:2], 1.0),
                    ]
                    emitted.append(self._cut(self._choose(deadline_candidates), deadline, frame_sequence))
            if self.active_shot is not None:
                age = seconds - float(self.active_shot["start_seconds"])
                # A viewer-confirmed Follow/Auto transition is an explicit
                # broadcast override. It may leave a death hold; ordinary
                # activity cues still respect the terminal lock.
                manual_focus_override = bool(focus and focus.get("mode") == "manual")
                if (
                    seconds < self.locked_terminal_until
                    and mode != "death_hold"
                    and not manual_focus_override
                ):
                    continue
                if focus is None and (
                    age < self.config.minimum_shot_seconds
                    or seconds - self.last_cut_seconds < self.config.cut_cooldown_seconds
                ):
                    continue
                if self.active_shot["mode"] == mode and self.active_shot["target_actor_ids"] == sorted(ids):
                    if focus:
                        requested_seconds = float(focus.get("presentation_seconds", seconds))
                        self.acquisition_records.append({
                            "transition_id": focus["transition_id"],
                            "requested_actor_id": str(focus["to_descender_id"]),
                            "requested_seconds": requested_seconds,
                            "acquired_seconds": seconds,
                            "latency_seconds": max(0.0, seconds - requested_seconds),
                            "actor_ready": True,
                            "target_visible": True,
                            "shot_id": self.active_shot["shot_id"],
                            "fallback_reason": None,
                            "reused_active_shot": True,
                        })
                        self.pending_focus_transition = None
                    continue
                # Retain a valid shot over low-value movement cuts until it ages.
                if (
                    mode == "follow"
                    and focus is None
                    and self.active_shot["mode"] != "death_hold"
                    and age < self.config.maximum_shot_seconds
                ):
                    continue
            cue_actor_states = actor_states
            if mode in COMBAT_MODES or mode == "death_hold":
                # One incremental delivery can contain an attack followed by a
                # terminal cue. Combat and the beginning of the fall both need
                # upright envelopes; the hold retains enough lower-frame space
                # for the settled corpse.
                cue_actor_states = {
                    key: {**self._actor_dict(value), "terminal": False}
                    for key, value in actor_states.items()
                }
            candidates = [self._candidate(mode, ids, cue_actor_states, reasons, score)]
            if focus:
                candidates[0].update({
                    "focus_transition_id": focus["transition_id"],
                    "focus_reason": focus.get("reason"),
                    "focus_mode": focus.get("mode"),
                })
            if mode == "combat_pair":
                candidates.append(self._candidate("activity_wide", ids, cue_actor_states, reasons, score - 45.0))
            candidates.append(self._candidate("fallback_static", ids, cue_actor_states, reasons, 1.0))
            chosen = self._choose(candidates)
            emitted.append(self._cut(chosen, seconds, frame_sequence))
            if focus:
                requested_actor = str(focus["to_descender_id"])
                target_visible = requested_actor in chosen["target_actor_ids"]
                if not target_visible:
                    self.stale_target_incidents += 1
                requested_seconds = float(focus.get("presentation_seconds", seconds))
                self.acquisition_records.append({
                    "transition_id": focus["transition_id"],
                    "requested_actor_id": requested_actor,
                    "requested_seconds": requested_seconds,
                    "acquired_seconds": seconds,
                    "latency_seconds": max(0.0, seconds - requested_seconds),
                    "actor_ready": True,
                    "target_visible": target_visible,
                    "shot_id": self.active_shot["shot_id"],
                    "fallback_reason": None,
                })
                self.pending_focus_transition = None

        if self.active_shot is not None and to_seconds >= self.locked_terminal_until:
            age = to_seconds - float(self.active_shot["start_seconds"])
            if age >= self.config.maximum_shot_seconds:
                alive = [key for key, state in sorted(actor_states.items()) if not self._actor_dict(state).get("terminal")]
                ids = alive[:1] or self.active_shot["target_actor_ids"][:1]
                mode = "follow" if self.active_shot["mode"] != "follow" and alive else "activity_wide"
                candidates = [
                    self._candidate(mode, ids, actor_states, future_ids[:2], 48.0),
                    self._candidate("fallback_static", ids, actor_states, future_ids[:2], 1.0),
                ]
                deadline = float(self.active_shot["start_seconds"]) + self.config.maximum_shot_seconds
                emitted.append(self._cut(self._choose(candidates), deadline, frame_sequence))

        self.decision_times_ms.append((perf_counter() - started) * 1000.0)
        self.decision_latencies_ticks.append(max(0, authoritative_tick - current_tick))
        self.decision_times_ms = self.decision_times_ms[-self.maximum_transient_history :]
        self.decision_latencies_ticks = self.decision_latencies_ticks[-self.maximum_transient_history :]
        self.candidate_counts = self.candidate_counts[-self.maximum_transient_history :]
        self.rejected_counts = self.rejected_counts[-self.maximum_transient_history :]
        return emitted

    def snapshot(self) -> dict[str, Any]:
        body = {
            "protocol": LIVE_CAMERA_PROTOCOL, "director_version": LIVE_CAMERA_DIRECTOR_VERSION,
            "descent_id": self.descent_id, "latest_frame_sequence": self.latest_frame_sequence,
            "active_shot": json.loads(_canonical(self.active_shot)) if self.active_shot else None,
            "locked_terminal_until": self.locked_terminal_until,
            "pending_focus_transition": json.loads(_canonical(self.pending_focus_transition)) if self.pending_focus_transition else None,
            "acquisition_records": json.loads(_canonical(self.acquisition_records)),
            "actor_readiness_waits": self.actor_readiness_waits,
            "stale_target_incidents": self.stale_target_incidents,
            "maximum_focus_acquisition_seconds": max([
                float(item["latency_seconds"]) for item in self.acquisition_records
                if item.get("latency_seconds") is not None
            ] or [0.0]),
            "command_digest": _digest(self.command_stream),
        }
        return {**body, "digest": _digest(body)}

    def restore(self, snapshot: dict[str, Any]) -> None:
        if snapshot.get("protocol") != LIVE_CAMERA_PROTOCOL or snapshot.get("descent_id") != self.descent_id:
            raise ValueError("invalid live camera reconnect snapshot")
        self.latest_frame_sequence = int(snapshot["latest_frame_sequence"])
        self.active_shot = json.loads(_canonical(snapshot.get("active_shot"))) if snapshot.get("active_shot") else None
        self.locked_terminal_until = float(snapshot.get("locked_terminal_until", -math.inf))
        self.pending_focus_transition = json.loads(_canonical(snapshot.get("pending_focus_transition"))) if snapshot.get("pending_focus_transition") else None
        self.acquisition_records = json.loads(_canonical(snapshot.get("acquisition_records", [])))
        self.actor_readiness_waits = int(snapshot.get("actor_readiness_waits", 0))
        self.stale_target_incidents = int(snapshot.get("stale_target_incidents", 0))
        self.reconnect_restore_count += 1

    def diagnostics(self, presentation_end_seconds: float | None = None) -> dict[str, Any]:
        shots = json.loads(_canonical(self.shots))
        if shots and presentation_end_seconds is not None:
            shots[-1]["end_seconds"] = round(float(presentation_end_seconds), 6)
            shots[-1]["duration_seconds"] = round(float(presentation_end_seconds) - shots[-1]["start_seconds"], 6)
        durations = [float(item.get("duration_seconds", 0.0)) for item in shots if item.get("duration_seconds") is not None]
        valid_shots = [item for item in shots if item["geometry_valid"] and item["los_valid"] and item["occupancy_valid"]]
        combat = [item for item in shots if item["mode"] in COMBAT_MODES]
        times = self.decision_times_ms or [0.0]
        counts = self.candidate_counts or [0]
        rejected = self.rejected_counts or [0]
        body = {
            "protocol": LIVE_CAMERA_PROTOCOL,
            "director_version": LIVE_CAMERA_DIRECTOR_VERSION,
            "descent_id": self.descent_id,
            "configuration": asdict(self.config),
            "shots_generated": len(shots),
            "cuts_generated": len(self.command_stream),
            "holds": self.hold_count,
            "fallback_shots": sum(item["mode"] == "fallback_static" for item in shots),
            "rejected_candidates": sum(self.rejections.values()),
            "rejection_reasons": dict(self.rejections),
            "wall_collisions": sum(not item["geometry_valid"] for item in shots),
            "los_failures": sum(not item["los_valid"] for item in shots),
            "occupancy_failures": sum(not item["occupancy_valid"] for item in shots),
            "minimum_wall_clearance_cm": min([item["minimum_wall_clearance_cm"] for item in valid_shots] or [0.0]),
            "minimum_combat_occupancy_width": min([item["occupancy_width"] for item in combat] or [0.0]),
            "minimum_combat_occupancy_height": min([item["occupancy_height"] for item in combat] or [0.0]),
            "shot_durations": durations,
            "average_shot_duration": sum(durations) / max(1, len(durations)),
            "minimum_shot_duration": min(durations or [0.0]),
            "maximum_shot_duration": max(durations or [0.0]),
            "mode_counts": {mode: sum(item["mode"] == mode for item in shots) for mode in sorted({item["mode"] for item in shots})},
            "death_holds": [item for item in shots if item["mode"] == "death_hold"],
            "reconnect_camera_restorations": self.reconnect_restore_count,
            "duplicate_camera_commands_ignored": self.duplicate_frame_count,
            "pending_focus_transition": json.loads(_canonical(self.pending_focus_transition)) if self.pending_focus_transition else None,
            "acquisition_records": json.loads(_canonical(self.acquisition_records)),
            "actor_readiness_waits": self.actor_readiness_waits,
            "stale_target_incidents": self.stale_target_incidents,
            "maximum_focus_acquisition_seconds": max([
                float(item["latency_seconds"]) for item in self.acquisition_records
                if item.get("latency_seconds") is not None
            ] or [0.0]),
            "command_digest": _digest(self.command_stream),
            "average_camera_decision_ms": sum(times) / len(times),
            "maximum_camera_decision_ms": max(times),
            "average_candidate_count": sum(counts) / len(counts),
            "average_candidates_rejected": sum(rejected) / len(rejected),
            "average_event_to_camera_latency_ticks": sum(self.decision_latencies_ticks or [0]) / max(1, len(self.decision_latencies_ticks)),
            "shots": shots,
        }
        return {**body, "digest": _digest(body)}
