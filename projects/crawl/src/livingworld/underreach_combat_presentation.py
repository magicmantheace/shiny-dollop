"""Deterministic combat-presentation schedule for Underreach Slice 29D.1.

The simulation remains authoritative. This module consumes accepted 29C.3
canonical frame truth and derives presentation timing, facing, semantic animation
slots, hit reactions, death transitions, and Feed shot intent. Presentation time
may stretch a canonical tick, but it can never change simulation state or outcome.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from typing import Any

from .underreach_autonomous_encounters import run_autonomous_encounter

PROTOCOL = "underreach.combat-presentation.v1"
GENERATOR_VERSION = "29d1.1"
SOURCE_PROTOCOL = "underreach.autonomous-encounter-flow.v1"

TICK_SECONDS = 0.90
MOVE_DURATION_SECONDS = 0.46
TURN_DURATION_SECONDS = 0.16
ATTACK_WINDUP_SECONDS = 0.18
ATTACK_CONTACT_SECONDS = 0.12
ATTACK_RECOVERY_SECONDS = 0.24
REACTION_DURATION_SECONDS = 0.28
DEATH_DURATION_SECONDS = 0.72


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def rebuild_digest(manifest: dict[str, Any]) -> str:
    payload = dict(manifest)
    payload.pop("digest", None)
    return _digest(payload)


def _yaw(from_pos: dict[str, Any], to_pos: dict[str, Any]) -> float:
    dx = float(to_pos["x"]) - float(from_pos["x"])
    dy = float(to_pos["y"]) - float(from_pos["y"])
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return 0.0
    return round(math.degrees(math.atan2(dy, dx)), 3)


def _actor_kind(actor_id: str) -> str:
    return "descender" if actor_id.startswith("descender_") else "monster"


def _attack_slot(actor_id: str) -> str:
    return "humanoid.combat.attack.default" if _actor_kind(actor_id) == "descender" else "enemy.biped.combat.attack.default"


def _reaction_slot(actor_id: str) -> str:
    return "humanoid.reaction.hit.default" if _actor_kind(actor_id) == "descender" else "enemy.biped.reaction.hit.default"


def _death_slot(actor_id: str) -> str:
    return "humanoid.death.default" if _actor_kind(actor_id) == "descender" else "enemy.biped.death.default"


def _state_dead(frame: dict[str, Any], actor_id: str) -> bool:
    if actor_id.startswith("descender_"):
        return frame["descender_state"].get(actor_id) == "dead"
    enemy = frame["enemy_state"].get(actor_id)
    return bool(enemy is not None and not enemy.get("alive", True))


def _camera_for_action(action: dict[str, Any]) -> str:
    kind = action["kind"]
    if kind in {"descender_attack", "monster_attack"}:
        return "combat_pair"
    if kind == "target_acquired":
        return "threat_reveal"
    if kind == "movement":
        return "follow_action"
    if kind in {"retreated", "entered"}:
        return "wide_context"
    return "follow_action"


def _base_window(
    *,
    sequence: int,
    frame_index: int,
    action_index: int,
    frame: dict[str, Any],
    action: dict[str, Any],
    actor_id: str,
    target_id: str | None,
) -> dict[str, Any]:
    positions = frame["positions_cm"]
    actor_pos = positions.get(actor_id)
    target_pos = positions.get(target_id) if target_id else None
    facing = _yaw(actor_pos, target_pos) if actor_pos is not None and target_pos is not None else None
    return {
        "window_id": f"presentation_{sequence:04d}",
        "source_tick": int(frame["tick"]),
        "source_frame_index": frame_index,
        "source_action_index": action_index,
        "source_action_kind": str(action["kind"]),
        "actor_id": actor_id,
        "target_id": target_id,
        "actor_kind": _actor_kind(actor_id),
        "canonical_position_cm": deepcopy(actor_pos),
        "canonical_target_position_cm": deepcopy(target_pos),
        "facing_yaw_degrees": facing,
        "camera_shot": _camera_for_action(action),
        "feed_focus_actor_id": frame["feed_focus_actor_id"],
    }


def build_combat_presentation(source_proof: dict[str, Any]) -> dict[str, Any]:
    """Project canonical 29C.3 truth into presentation-only action windows."""
    if source_proof.get("protocol") != SOURCE_PROTOCOL or source_proof.get("authoritative") is not True:
        raise ValueError("29D.1 requires accepted authoritative 29C.3 source truth")
    truth = source_proof.get("canonical_truth") or {}
    frames = truth.get("frames") or []
    if not frames:
        raise ValueError("29D.1 source contains no canonical frames")

    windows: list[dict[str, Any]] = []
    actor_tracks: dict[str, list[str]] = {}
    previous_positions: dict[str, dict[str, float]] | None = None
    death_scheduled: set[str] = set()
    sequence = 0

    def append(window: dict[str, Any]) -> None:
        nonlocal sequence
        windows.append(window)
        actor_tracks.setdefault(window["actor_id"], []).append(window["window_id"])
        sequence += 1

    for frame_index, frame in enumerate(frames):
        tick_start = round(frame_index * TICK_SECONDS, 3)
        positions = frame["positions_cm"]
        for action_index, action in enumerate(frame.get("actions", [])):
            kind = str(action["kind"])
            actor_id = str(action["actor_id"])
            target_id = action.get("target_id")
            action_start = round(tick_start + min(0.08 * action_index, 0.26), 3)
            base = _base_window(
                sequence=sequence,
                frame_index=frame_index,
                action_index=action_index,
                frame=frame,
                action=action,
                actor_id=actor_id,
                target_id=target_id,
            )

            if kind == "movement":
                actor_pos = positions.get(actor_id)
                start_pos = (previous_positions or {}).get(actor_id, actor_pos)
                append({
                    **base,
                    "presentation_kind": "locomotion",
                    "animation_slot": "humanoid.locomotion.forward" if _actor_kind(actor_id) == "descender" else "enemy.biped.locomotion.forward",
                    "start_seconds": action_start,
                    "end_seconds": round(action_start + MOVE_DURATION_SECONDS, 3),
                    "from_position_cm": deepcopy(start_pos),
                    "to_position_cm": deepcopy(actor_pos),
                    "turn_duration_seconds": TURN_DURATION_SECONDS,
                })
                continue

            if kind in {"descender_attack", "monster_attack"}:
                hit = bool(action.get("hit", False))
                damage = float(action.get("damage", 0.0))
                attack = {
                    **base,
                    "presentation_kind": "attack",
                    "animation_slot": _attack_slot(actor_id),
                    "start_seconds": action_start,
                    "windup_end_seconds": round(action_start + ATTACK_WINDUP_SECONDS, 3),
                    "contact_seconds": round(action_start + ATTACK_WINDUP_SECONDS + ATTACK_CONTACT_SECONDS, 3),
                    "end_seconds": round(action_start + ATTACK_WINDUP_SECONDS + ATTACK_CONTACT_SECONDS + ATTACK_RECOVERY_SECONDS, 3),
                    "canonical_hit": hit,
                    "canonical_damage": damage,
                }
                append(attack)

                if hit and target_id is not None:
                    reaction_base = _base_window(
                        sequence=sequence,
                        frame_index=frame_index,
                        action_index=action_index,
                        frame=frame,
                        action=action,
                        actor_id=str(target_id),
                        target_id=actor_id,
                    )
                    reaction_start = attack["contact_seconds"]
                    reaction = {
                        **reaction_base,
                        "presentation_kind": "hit_reaction",
                        "animation_slot": _reaction_slot(str(target_id)),
                        "start_seconds": reaction_start,
                        "end_seconds": round(reaction_start + REACTION_DURATION_SECONDS, 3),
                        "canonical_hit": True,
                        "canonical_damage": damage,
                        "reaction_offset_cm": 18.0 if damage >= 0.055 else 10.0,
                    }
                    append(reaction)

                    if _state_dead(frame, str(target_id)) and str(target_id) not in death_scheduled:
                        death_scheduled.add(str(target_id))
                        death_base = _base_window(
                            sequence=sequence,
                            frame_index=frame_index,
                            action_index=action_index,
                            frame=frame,
                            action=action,
                            actor_id=str(target_id),
                            target_id=actor_id,
                        )
                        death_start = reaction["end_seconds"]
                        append({
                            **death_base,
                            "presentation_kind": "death",
                            "animation_slot": _death_slot(str(target_id)),
                            "start_seconds": death_start,
                            "end_seconds": round(death_start + DEATH_DURATION_SECONDS, 3),
                            "camera_shot": "aftermath_hold",
                            "canonical_death": True,
                        })
                continue

            semantic = {
                "target_acquired": "threat_focus",
                "entered": "encounter_entry",
                "retreated": "encounter_exit",
            }.get(kind, "event_hold")
            duration = 0.30 if kind == "target_acquired" else 0.24
            append({
                **base,
                "presentation_kind": semantic,
                "animation_slot": None,
                "start_seconds": action_start,
                "end_seconds": round(action_start + duration, 3),
            })

        previous_positions = deepcopy(positions)

    manifest = {
        "protocol": PROTOCOL,
        "generator_version": GENERATOR_VERSION,
        "authoritative": False,
        "source_protocol": SOURCE_PROTOCOL,
        "source_canonical_digest": source_proof["canonical_digest"],
        "source_proof_digest": source_proof["digest"],
        "source_outcome": truth["outcome"],
        "simulation_time_independent": True,
        "canonical_state_mutation_allowed": False,
        "presentation_duration_seconds": round(max((w["end_seconds"] for w in windows), default=0.0), 3),
        "windows": windows,
        "actor_tracks": {actor_id: ids for actor_id, ids in sorted(actor_tracks.items())},
        "source_frame_digest": _digest(frames),
    }
    manifest["digest"] = _digest(manifest)
    validate_combat_presentation(manifest, source_proof)
    return manifest


def validate_combat_presentation(manifest: dict[str, Any], source_proof: dict[str, Any]) -> bool:
    if manifest.get("protocol") != PROTOCOL or manifest.get("authoritative") is not False:
        raise ValueError("29D.1 combat presentation authority/protocol invalid")
    if manifest.get("canonical_state_mutation_allowed") is not False or manifest.get("simulation_time_independent") is not True:
        raise ValueError("29D.1 presentation violated simulation-time authority boundary")
    if manifest.get("source_canonical_digest") != source_proof.get("canonical_digest"):
        raise ValueError("29D.1 presentation is bound to wrong canonical digest")
    if manifest.get("source_proof_digest") != source_proof.get("digest"):
        raise ValueError("29D.1 presentation is bound to wrong source proof")
    truth = source_proof["canonical_truth"]
    if manifest.get("source_outcome") != truth.get("outcome"):
        raise ValueError("29D.1 presentation changed canonical outcome")
    if manifest.get("source_frame_digest") != _digest(truth.get("frames") or []):
        raise ValueError("29D.1 source frame digest mismatch")

    frames = truth["frames"]
    windows = manifest.get("windows") or []
    ids = [window["window_id"] for window in windows]
    if len(ids) != len(set(ids)):
        raise ValueError("29D.1 duplicate presentation window ids")
    for window in windows:
        frame_index = int(window["source_frame_index"])
        action_index = int(window["source_action_index"])
        if not 0 <= frame_index < len(frames):
            raise ValueError("29D.1 window references invalid canonical frame")
        actions = frames[frame_index].get("actions", [])
        if not 0 <= action_index < len(actions):
            raise ValueError("29D.1 window references invalid canonical action")
        source = actions[action_index]
        if window["source_action_kind"] != source["kind"]:
            raise ValueError("29D.1 window changed source action kind")
        if float(window["end_seconds"]) < float(window["start_seconds"]):
            raise ValueError("29D.1 presentation window ends before it starts")
        if window["presentation_kind"] == "hit_reaction":
            if not source.get("hit", False):
                raise ValueError("29D.1 invented hit reaction for canonical miss")
            if window["actor_id"] != source.get("target_id"):
                raise ValueError("29D.1 hit reaction applied to wrong canonical target")
        if window["presentation_kind"] == "death":
            if not source.get("hit", False) or window["actor_id"] != source.get("target_id") or not _state_dead(frames[frame_index], window["actor_id"]):
                raise ValueError("29D.1 invented death presentation")
        expected_pos = frames[frame_index]["positions_cm"].get(window["actor_id"])
        if window.get("canonical_position_cm") != expected_pos:
            raise ValueError("29D.1 presentation actor position does not match canonical frame")
    for actor_id, track in (manifest.get("actor_tracks") or {}).items():
        for window_id in track:
            matching = [window for window in windows if window["window_id"] == window_id]
            if len(matching) != 1 or matching[0]["actor_id"] != actor_id:
                raise ValueError("29D.1 actor track references wrong presentation window")
    if manifest.get("digest") != rebuild_digest(manifest):
        raise ValueError("29D.1 presentation digest mismatch")
    return True


def build_combat_presentation_proof(seed: str = "underreach-29d1-combat-presentation-proof") -> dict[str, Any]:
    source = run_autonomous_encounter(seed, sector_count=12, descender_count=3)
    presentation = build_combat_presentation(source)
    return {"source": source, "presentation": presentation}
