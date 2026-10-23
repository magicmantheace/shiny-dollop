"""Deterministic autonomous encounter flow for Underreach Slice 29C.3.

29C.2 proved the promotion boundary into canonical combat. 29C.3 stretches that
combat across simulation ticks so monsters and Descenders can acquire targets,
move, attack, retreat, die, and leave the encounter without presentation owning
any outcome. Feed focus is derived afterward from canonical frame truth.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from typing import Any

from .crawl_domain import ParticipationStatus
from .crawl_persistence import CrawlPersistence
from .crawl_service import CrawlLifecycleService
from .gameplay_domain import EncounterStatus
from .monster_encounters import build_encounter_plan
from .stratum_environment import build_stratum_environment_manifest
from .stratum_theme import build_stratum_theme_manifest
from .underreach_live_encounters import promote_encounter

CANONICAL_PROTOCOL = "underreach.autonomous-encounter-flow.v1"
PRESENTATION_PROTOCOL = "underreach.autonomous-encounter-presentation.v1"
GENERATOR_VERSION = "29c3.2"

DESCENDER_SPEED_CM = 180.0
MONSTER_SPEED_CM = 145.0
DESCENDER_RANGE_CM = 185.0
MONSTER_RANGE_CM = 150.0
MAX_TICKS = 120


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def rebuild_digest(proof: dict[str, Any]) -> str:
    payload = dict(proof)
    payload.pop("digest", None)
    return _digest(payload)


def _roll(seed: str, tick: int, actor_id: str, target_id: str, channel: str) -> float:
    value = f"{seed}:{tick}:{actor_id}:{target_id}:{channel}"
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:12], 16) / float(0xFFFFFFFFFFFF)


def _distance(a: dict[str, float], b: dict[str, float]) -> float:
    return math.hypot(float(a["x"]) - float(b["x"]), float(a["y"]) - float(b["y"]))


def _advance(position: dict[str, float], target: dict[str, float], distance_cm: float) -> dict[str, float]:
    dx = float(target["x"]) - float(position["x"])
    dy = float(target["y"]) - float(position["y"])
    distance = math.hypot(dx, dy)
    if distance <= distance_cm or distance == 0.0:
        return {"x": round(float(target["x"]), 3), "y": round(float(target["y"]), 3), "z": 0.0}
    ratio = distance_cm / distance
    return {
        "x": round(float(position["x"]) + dx * ratio, 3),
        "y": round(float(position["y"]) + dy * ratio, 3),
        "z": 0.0,
    }


def _frame(tick, positions, descender_state, enemy_state, actions):
    live_ids = [npc_id for npc_id, state in descender_state.items() if state == "active"]
    living_enemy_ids = [enemy_id for enemy_id, state in enemy_state.items() if state["alive"]]
    priority = {
        "monster_attack": 6,
        "descender_attack": 5,
        "target_acquired": 4,
        "retreated": 3,
        "movement": 2,
        "entered": 1,
    }
    focus = None
    if actions:
        best = max(
            actions,
            key=lambda item: (
                priority.get(item["kind"], 0),
                item["actor_id"],
                item.get("target_id") or "",
            ),
        )
        focus = best.get("target_id") if best["kind"] in {"monster_attack", "descender_attack"} else best["actor_id"]
    if focus is None and positions:
        focus = (living_enemy_ids or live_ids or sorted(positions))[0]
    return {
        "tick": tick,
        "positions_cm": {key: dict(value) for key, value in sorted(positions.items())},
        "descender_state": dict(sorted(descender_state.items())),
        "enemy_state": {key: dict(value) for key, value in sorted(enemy_state.items())},
        "actions": [dict(item) for item in actions],
        "feed_focus_actor_id": focus,
    }


def run_autonomous_encounter(
    seed: str = "underreach-29c3-autonomous-proof",
    *,
    theme: str = "ancient_stoneworks",
    sector_count: int = 12,
    descender_count: int = 3,
    max_ticks: int = MAX_TICKS,
) -> dict[str, Any]:
    if descender_count < 1:
        raise ValueError("descender_count must be positive")
    if max_ticks < 1:
        raise ValueError("max_ticks must be positive")

    environment = build_stratum_environment_manifest(seed, 0, sector_count=sector_count, theme=theme)
    themed = build_stratum_theme_manifest(environment, theme)
    plan = build_encounter_plan(environment, themed)
    source = sorted(plan["encounters"], key=lambda item: item["encounter_id"])[0]
    sector = next(item for item in environment["sectors"] if item["sector_id"] == source["sector_id"])

    persistence = CrawlPersistence("sqlite:///:memory:")
    persistence.initialize()
    lifecycle = CrawlLifecycleService(persistence)
    descender_ids = [f"descender_{index:03d}" for index in range(descender_count)]
    crawl = lifecycle.create_seeded_crawl(seed=seed, crawler_ids=descender_ids, floor_count=1)
    lifecycle.start(crawl)
    for participant in crawl.participants.values():
        participant.health = 1.0
        participant.gameplay.stamina = 1.0

    encounter = promote_encounter(crawl, plan, source, participant_npc_ids=descender_ids)
    encounter.status = EncounterStatus.ACTIVE
    lifecycle._record(
        crawl,
        "UNDERREACH_AUTONOMOUS_ENCOUNTER_STARTED",
        "A promoted Underreach encounter entered autonomous simulation flow.",
        actor_ids=descender_ids + sorted(encounter.enemies),
        location_id=encounter.location_id,
        data={"encounter_id": encounter.id, "source_sector_id": source["sector_id"], "source_plan_digest": plan["digest"]},
    )

    half_x = float(sector["combat_clearance_cm"]["x"]) * 0.5
    positions: dict[str, dict[str, float]] = {}
    descender_state = {npc_id: "approaching" for npc_id in descender_ids}
    for index, npc_id in enumerate(descender_ids):
        positions[npc_id] = {
            "x": round(-half_x + 60.0, 3),
            "y": round((index - (descender_count - 1) / 2.0) * 150.0, 3),
            "z": 0.0,
        }
    for member in source["members"]:
        positions[member["member_id"]] = dict(member["local_offset_cm"])

    enemy_state = {
        enemy_id: {"alive": enemy.alive, "health": enemy.health, "max_health": enemy.max_health, "target_id": None}
        for enemy_id, enemy in sorted(encounter.enemies.items())
    }
    last_targets = {enemy_id: None for enemy_id in encounter.enemies}
    frames: list[dict[str, Any]] = []
    entered: set[str] = set()

    for _ in range(max_ticks):
        crawl.current_tick += 1
        tick = crawl.current_tick
        actions: list[dict[str, Any]] = []

        for npc_id in descender_ids:
            participant = crawl.participants[npc_id]
            if participant.status != ParticipationStatus.ACTIVE or descender_state[npc_id] in {"retreated", "dead"}:
                continue
            if npc_id not in entered:
                entered.add(npc_id)
                descender_state[npc_id] = "active"
                actions.append({"kind": "entered", "actor_id": npc_id, "target_id": None})
                lifecycle._record(
                    crawl,
                    "UNDERREACH_DESCENDER_ENTERED_ENCOUNTER",
                    f"Descender {npc_id} entered the encounter.",
                    actor_ids=[npc_id],
                    location_id=encounter.location_id,
                    data={"encounter_id": encounter.id, "sector_id": source["sector_id"]},
                )

        living_enemies = [enemy_id for enemy_id, state in enemy_state.items() if state["alive"]]
        active_descenders = [
            npc_id
            for npc_id in descender_ids
            if descender_state[npc_id] == "active" and crawl.participants[npc_id].status == ParticipationStatus.ACTIVE
        ]
        if not living_enemies or not active_descenders:
            frames.append(_frame(tick, positions, descender_state, enemy_state, actions))
            break

        for npc_id in sorted(active_descenders):
            participant = crawl.participants[npc_id]
            if participant.health < 0.22 and _roll(seed, tick, npc_id, "exit", "retreat") < 0.55:
                descender_state[npc_id] = "retreated"
                actions.append({"kind": "retreated", "actor_id": npc_id, "target_id": None})
                lifecycle._record(
                    crawl,
                    "UNDERREACH_DESCENDER_RETREATED_FROM_ENCOUNTER",
                    f"Descender {npc_id} left the encounter alive.",
                    actor_ids=[npc_id],
                    location_id=encounter.location_id,
                    data={"encounter_id": encounter.id, "health": participant.health},
                )
                continue

            target_id = min(living_enemies, key=lambda enemy_id: (_distance(positions[npc_id], positions[enemy_id]), enemy_id))
            if _distance(positions[npc_id], positions[target_id]) > DESCENDER_RANGE_CM:
                positions[npc_id] = _advance(positions[npc_id], positions[target_id], DESCENDER_SPEED_CM)
                actions.append({"kind": "movement", "actor_id": npc_id, "target_id": target_id})
                lifecycle._record(
                    crawl,
                    "UNDERREACH_DESCENDER_MOVED_IN_ENCOUNTER",
                    f"Descender {npc_id} closed on {target_id}.",
                    actor_ids=[npc_id, target_id],
                    location_id=encounter.location_id,
                    data={"encounter_id": encounter.id, "position_cm": positions[npc_id]},
                )
            else:
                enemy = encounter.enemies[target_id]
                hit = _roll(seed, tick, npc_id, target_id, "descender_hit") <= 0.78
                damage = 0.0
                if hit:
                    damage = round(0.055 + _roll(seed, tick, npc_id, target_id, "descender_damage") * 0.045, 6)
                    enemy.health = max(0.0, enemy.health - damage)
                    if enemy.health <= 0.0:
                        enemy.alive = False
                    enemy_state[target_id]["health"] = enemy.health
                    enemy_state[target_id]["alive"] = enemy.alive
                actions.append({"kind": "descender_attack", "actor_id": npc_id, "target_id": target_id, "hit": hit, "damage": damage})
                lifecycle._record(
                    crawl,
                    "UNDERREACH_DESCENDER_ATTACKED_MONSTER",
                    f"Descender {npc_id} attacked {target_id}.",
                    actor_ids=[npc_id, target_id],
                    location_id=encounter.location_id,
                    data={"encounter_id": encounter.id, "hit": hit, "damage": damage, "target_health": enemy.health},
                )
                if not enemy.alive:
                    lifecycle._record(
                        crawl,
                        "UNDERREACH_MONSTER_DEFEATED",
                        f"Monster {target_id} was defeated.",
                        actor_ids=[npc_id, target_id],
                        location_id=encounter.location_id,
                        data={"encounter_id": encounter.id},
                    )
                    living_enemies = [enemy_id for enemy_id in living_enemies if enemy_id != target_id]
                    if not living_enemies:
                        break

        active_descenders = [
            npc_id
            for npc_id in descender_ids
            if descender_state[npc_id] == "active" and crawl.participants[npc_id].status == ParticipationStatus.ACTIVE
        ]
        living_enemies = [enemy_id for enemy_id, state in enemy_state.items() if state["alive"]]
        for enemy_id in sorted(living_enemies):
            if not active_descenders:
                break
            target_id = min(
                active_descenders,
                key=lambda npc_id: (crawl.participants[npc_id].health, _distance(positions[enemy_id], positions[npc_id]), npc_id),
            )
            enemy_state[enemy_id]["target_id"] = target_id
            if last_targets[enemy_id] != target_id:
                last_targets[enemy_id] = target_id
                actions.append({"kind": "target_acquired", "actor_id": enemy_id, "target_id": target_id})
                lifecycle._record(
                    crawl,
                    "UNDERREACH_MONSTER_TARGET_ACQUIRED",
                    f"Monster {enemy_id} acquired Descender {target_id}.",
                    actor_ids=[enemy_id, target_id],
                    location_id=encounter.location_id,
                    data={"encounter_id": encounter.id},
                )

            if _distance(positions[enemy_id], positions[target_id]) > MONSTER_RANGE_CM:
                positions[enemy_id] = _advance(positions[enemy_id], positions[target_id], MONSTER_SPEED_CM)
                actions.append({"kind": "movement", "actor_id": enemy_id, "target_id": target_id})
                lifecycle._record(
                    crawl,
                    "UNDERREACH_MONSTER_MOVED",
                    f"Monster {enemy_id} pursued {target_id}.",
                    actor_ids=[enemy_id, target_id],
                    location_id=encounter.location_id,
                    data={"encounter_id": encounter.id, "position_cm": positions[enemy_id]},
                )
                continue

            participant = crawl.participants[target_id]
            hit = _roll(seed, tick, enemy_id, target_id, "monster_hit") <= 0.68
            damage = 0.0
            if hit:
                damage = round(0.035 + _roll(seed, tick, enemy_id, target_id, "monster_damage") * 0.035, 6)
                participant.health = max(0.0, participant.health - damage)
            actions.append({"kind": "monster_attack", "actor_id": enemy_id, "target_id": target_id, "hit": hit, "damage": damage})
            lifecycle._record(
                crawl,
                "UNDERREACH_MONSTER_ATTACKED",
                f"Monster {enemy_id} attacked Descender {target_id}.",
                actor_ids=[enemy_id, target_id],
                location_id=encounter.location_id,
                data={"encounter_id": encounter.id, "hit": hit, "damage": damage, "target_health": participant.health},
            )
            if participant.health <= 0.0:
                lifecycle.eliminate(
                    crawl,
                    target_id,
                    dead=True,
                    summary=f"Descender {target_id} was killed during autonomous encounter {encounter.id}.",
                )
                descender_state[target_id] = "dead"

        frames.append(_frame(tick, positions, descender_state, enemy_state, actions))
        living_enemies = [enemy_id for enemy_id, state in enemy_state.items() if state["alive"]]
        active_descenders = [
            npc_id
            for npc_id in descender_ids
            if descender_state[npc_id] == "active" and crawl.participants[npc_id].status == ParticipationStatus.ACTIVE
        ]
        if not living_enemies or not active_descenders:
            break

    living_enemies = [enemy_id for enemy_id, state in enemy_state.items() if state["alive"]]
    active_descenders = [
        npc_id
        for npc_id in descender_ids
        if descender_state[npc_id] == "active" and crawl.participants[npc_id].status == ParticipationStatus.ACTIVE
    ]
    if not living_enemies:
        outcome = "victory"
        encounter.status = EncounterStatus.RESOLVED
    elif not active_descenders:
        outcome = "defeat_or_retreat"
        encounter.status = EncounterStatus.FAILED
    else:
        outcome = "timeout"
        encounter.status = EncounterStatus.FAILED
    encounter.cleanup_complete = True
    encounter.resolved_tick = crawl.current_tick
    lifecycle._record(
        crawl,
        "UNDERREACH_LIVE_ENCOUNTER_ENDED",
        f"Autonomous encounter ended with {outcome}.",
        actor_ids=descender_ids + sorted(encounter.enemies),
        location_id=encounter.location_id,
        data={"encounter_id": encounter.id, "outcome": outcome, "frames": len(frames)},
    )
    lifecycle._save(crawl)

    # Crawl history_event_ids is the canonical append order. Persistence replay
    # intentionally sorts by (tick,id), which can reorder same-tick events and
    # make the terminal event appear before attacks from the same tick.
    ordered_events = persistence.events_by_ids(crawl.history_event_ids)
    ledger = [
        event.model_dump(mode="json")
        for event in ordered_events
        if event.data.get("encounter_id") == encounter.id
    ]

    participant_final = {
        npc_id: {
            "status": crawl.participants[npc_id].status.value,
            "health": crawl.participants[npc_id].health,
            "flow_state": descender_state[npc_id],
        }
        for npc_id in sorted(descender_ids)
    }
    enemy_final = {
        enemy_id: {"alive": enemy.alive, "health": enemy.health, "target_id": enemy_state[enemy_id]["target_id"]}
        for enemy_id, enemy in sorted(encounter.enemies.items())
    }
    canonical_truth = {
        "source_environment_digest": environment["digest"],
        "source_theme_digest": themed["digest"],
        "source_encounter_plan_digest": plan["digest"],
        "source_sector_id": source["sector_id"],
        "canonical_encounter_id": encounter.id,
        "outcome": outcome,
        "frames": frames,
        "participant_final": participant_final,
        "enemy_final": enemy_final,
        "ledger_events": ledger,
        "crawl_fingerprint": crawl.fingerprint(),
    }
    canonical_digest = _digest(canonical_truth)

    # Presentation receives an independent deep copy. It must never share mutable
    # frame objects with canonical truth; otherwise a presentation mutation could
    # accidentally mutate the proof's authoritative payload in memory.
    presentation_frames = deepcopy(frames)
    presentation = {
        "protocol": PRESENTATION_PROTOCOL,
        "authoritative": False,
        "canonical_digest": canonical_digest,
        "outcome": outcome,
        "frames": presentation_frames,
        "feed_focus_schedule": [
            {"tick": frame["tick"], "actor_id": frame["feed_focus_actor_id"]}
            for frame in presentation_frames
        ],
        "ledger_event_ids": [event["id"] for event in ledger],
    }
    proof = {
        "protocol": CANONICAL_PROTOCOL,
        "generator_version": GENERATOR_VERSION,
        "authoritative": True,
        "seed": seed,
        "canonical_digest": canonical_digest,
        "canonical_truth": canonical_truth,
        "presentation": presentation,
    }
    proof["digest"] = _digest(proof)
    validate_autonomous_encounter_proof(proof)
    return proof


def validate_autonomous_encounter_proof(proof: dict[str, Any]) -> bool:
    if proof.get("protocol") != CANONICAL_PROTOCOL or proof.get("authoritative") is not True:
        raise ValueError("29C.3 canonical flow authority is invalid")

    truth = proof.get("canonical_truth") or {}
    if proof.get("canonical_digest") != _digest(truth):
        raise ValueError("29C.3 canonical truth digest mismatch")

    presentation = proof.get("presentation") or {}
    if presentation.get("protocol") != PRESENTATION_PROTOCOL or presentation.get("authoritative") is not False:
        raise ValueError("29C.3 presentation must remain non-authoritative")
    if presentation.get("canonical_digest") != proof.get("canonical_digest"):
        raise ValueError("29C.3 presentation is not bound to canonical truth")
    if presentation.get("outcome") != truth.get("outcome"):
        raise ValueError("29C.3 presentation altered canonical outcome")
    if presentation.get("frames") != truth.get("frames"):
        raise ValueError("29C.3 presentation altered canonical frames")
    if presentation.get("ledger_event_ids") != [event["id"] for event in truth.get("ledger_events", [])]:
        raise ValueError("29C.3 presentation altered Ledger identity/order")

    frames = truth.get("frames") or []
    if not frames:
        raise ValueError("29C.3 produced no simulation frames")
    if any(frame.get("feed_focus_actor_id") is None for frame in frames):
        raise ValueError("29C.3 produced an empty Feed focus window")
    if len({event["id"] for event in truth.get("ledger_events", [])}) != len(truth.get("ledger_events", [])):
        raise ValueError("29C.3 duplicate Ledger event ids")

    event_types = {event["event_type"] for event in truth.get("ledger_events", [])}
    core_required = {
        "UNDERREACH_AUTONOMOUS_ENCOUNTER_STARTED",
        "UNDERREACH_DESCENDER_ENTERED_ENCOUNTER",
        "UNDERREACH_MONSTER_TARGET_ACQUIRED",
        "UNDERREACH_MONSTER_ATTACKED",
        "UNDERREACH_DESCENDER_ATTACKED_MONSTER",
        "UNDERREACH_LIVE_ENCOUNTER_ENDED",
    }
    if not core_required.issubset(event_types):
        raise ValueError(f"29C.3 missing autonomous flow events: {sorted(core_required - event_types)}")

    # Some deterministic layouts begin with monsters already in attack range.
    # Movement is still required somewhere in the encounter, but it need not be
    # monster movement specifically for every seed.
    movement_types = {"UNDERREACH_MONSTER_MOVED", "UNDERREACH_DESCENDER_MOVED_IN_ENCOUNTER"}
    if not (event_types & movement_types):
        raise ValueError("29C.3 encounter contained no autonomous movement")

    ledger = truth.get("ledger_events", [])
    if not ledger or ledger[-1]["event_type"] != "UNDERREACH_LIVE_ENCOUNTER_ENDED":
        raise ValueError("29C.3 terminal encounter event is not last in canonical append order")

    if proof.get("digest") != rebuild_digest(proof):
        raise ValueError("29C.3 proof digest mismatch")
    return True
