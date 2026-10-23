"""Headless UE 5.8 consumer proof for Underreach Slice 29C.2.

This script reads a canonical JSON artifact created outside Unreal. It never runs
combat and never writes canonical state; it only creates presentation proxies and
proves that displayed outcome metadata is an exact projection of simulation truth.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import unreal

PROJECT_DIR = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
OUTPUT_DIR = PROJECT_DIR / "Generated" / "underreach-29c2"
CANONICAL_PATH = OUTPUT_DIR / "live-encounter-canonical.json"
DEBUG_PATH = OUTPUT_DIR / "live-encounter-unreal-debug.json"


def _hash_bytes(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _cleanup(actor_subsystem):
    for actor in list(actor_subsystem.get_all_level_actors()):
        try:
            if actor.get_actor_label().startswith("Underreach29C2_"):
                actor_subsystem.destroy_actor(actor)
        except Exception:
            continue


def _spawn_proxy(actor_subsystem, label, location, scale, tags):
    mesh = unreal.load_asset("/Engine/BasicShapes/Cube.Cube")
    if mesh is None:
        raise RuntimeError("Engine Cube mesh unavailable")
    actor = actor_subsystem.spawn_actor_from_class(
        unreal.StaticMeshActor,
        unreal.Vector(float(location[0]), float(location[1]), float(location[2])),
        unreal.Rotator(0.0, 0.0, 0.0),
        False,
    )
    if actor is None:
        raise RuntimeError(f"Could not spawn {label}")
    actor.set_actor_label(label)
    actor.set_folder_path("Underreach/29C2/LiveEncounter")
    component = actor.get_component_by_class(unreal.StaticMeshComponent)
    component.set_static_mesh(mesh)
    component.set_world_scale3d(unreal.Vector(float(scale[0]), float(scale[1]), float(scale[2])))
    actor.tags = [unreal.Name(str(tag)) for tag in tags]
    return actor


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if not CANONICAL_PATH.exists():
        raise RuntimeError(f"Canonical 29C.2 artifact is missing: {CANONICAL_PATH}")

    canonical_file_hash_before = _hash_bytes(CANONICAL_PATH)
    proof = json.loads(CANONICAL_PATH.read_text(encoding="utf-8"))
    if proof.get("protocol") != "underreach.live-encounter-canonical.v1" or proof.get("authoritative") is not True:
        raise RuntimeError("29C.2 canonical artifact has unexpected protocol/authority")
    presentation = proof.get("presentation") or {}
    if presentation.get("protocol") != "underreach.live-encounter-presentation.v1" or presentation.get("authoritative") is not False:
        raise RuntimeError("29C.2 presentation contract has unexpected protocol/authority")
    if presentation.get("canonical_digest") != proof.get("canonical_digest"):
        raise RuntimeError("29C.2 presentation is not bound to canonical digest")

    truth = proof["canonical_truth"]
    resolution = truth["resolution"]
    expected_defeated = sorted(resolution["defeated_enemy_ids"])
    expected_dead = sorted(resolution["crawler_deaths"])
    expected_retreated = sorted(resolution["retreated_npc_ids"])

    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    _cleanup(actor_subsystem)
    origin = truth["source_sector"]["world_origin_cm"]
    canonical_digest = proof["canonical_digest"]

    spawned_descenders = []
    participant_ids = sorted(truth["participant_final"])
    spacing = 180.0
    center = (len(participant_ids) - 1) * 0.5
    for index, npc_id in enumerate(participant_ids):
        state = truth["participant_final"][npc_id]
        final_status = state["status"]
        x = float(origin["x"]) - 260.0
        y = float(origin["y"]) + (index - center) * spacing
        z = 90.0
        actor = _spawn_proxy(
            actor_subsystem,
            f"Underreach29C2_Descender_{npc_id}_{final_status}",
            (x, y, z),
            (0.55, 0.55, 1.8),
            [
                "underreach_29c2",
                "role:descender",
                f"canonical:{canonical_digest}",
                f"descender:{npc_id}",
                f"final_status:{final_status}",
                f"dead:{str(npc_id in expected_dead).lower()}",
                f"retreated:{str(npc_id in expected_retreated).lower()}",
            ],
        )
        spawned_descenders.append({
            "actor_name": actor.get_name(),
            "descender_id": npc_id,
            "final_status": final_status,
            "dead": npc_id in expected_dead,
            "retreated": npc_id in expected_retreated,
        })

    spawn_by_id = {item["member_id"]: item for item in presentation["monster_spawns"]}
    spawned_monsters = []
    for enemy_id in sorted(truth["enemy_final"]):
        state = truth["enemy_final"][enemy_id]
        spawn = spawn_by_id[enemy_id]
        offset = spawn["local_offset_cm"]
        defeated = enemy_id in expected_defeated
        x = float(origin["x"]) + float(offset["x"])
        y = float(origin["y"]) + float(offset["y"])
        z = 70.0
        actor = _spawn_proxy(
            actor_subsystem,
            f"Underreach29C2_Monster_{enemy_id}_{'defeated' if defeated else 'alive'}",
            (x, y, z),
            (1.1, 0.9, 1.4),
            [
                "underreach_29c2",
                "role:monster",
                f"canonical:{canonical_digest}",
                f"monster_member:{enemy_id}",
                f"monster:{state['monster_id']}",
                f"defeated:{str(defeated).lower()}",
                f"alive:{str(state['alive']).lower()}",
            ],
        )
        spawned_monsters.append({
            "actor_name": actor.get_name(),
            "member_id": enemy_id,
            "monster_id": state["monster_id"],
            "defeated": defeated,
            "alive": state["alive"],
        })

    presented_defeated = sorted(item["member_id"] for item in spawned_monsters if item["defeated"])
    presented_dead = sorted(item["descender_id"] for item in spawned_descenders if item["dead"])
    presented_retreated = sorted(item["descender_id"] for item in spawned_descenders if item["retreated"])
    canonical_file_hash_after = _hash_bytes(CANONICAL_PATH)

    validation = {
        "canonical_file_unchanged": canonical_file_hash_before == canonical_file_hash_after,
        "canonical_digest_exact": presentation["canonical_digest"] == canonical_digest,
        "presentation_non_authoritative": presentation["authoritative"] is False,
        "outcome_exact": presentation["outcome"] == resolution["outcome"],
        "defeated_enemy_ids_exact": presented_defeated == expected_defeated == sorted(presentation["defeated_enemy_ids"]),
        "dead_descender_ids_exact": presented_dead == expected_dead == sorted(presentation["dead_descender_ids"]),
        "retreated_descender_ids_exact": presented_retreated == expected_retreated == sorted(presentation["retreated_descender_ids"]),
        "descender_actor_set_exact": sorted(item["descender_id"] for item in spawned_descenders) == participant_ids,
        "monster_actor_set_exact": sorted(item["member_id"] for item in spawned_monsters) == sorted(truth["enemy_final"]),
        "ledger_identity_exact": presentation["ledger_event_ids"] == [event["id"] for event in truth["ledger_events"]],
    }
    validation["all_pass"] = all(validation.values())

    debug = {
        "protocol": "underreach.live-encounter-unreal-debug.v1",
        "authoritative": False,
        "engine_version": unreal.SystemLibrary.get_engine_version(),
        "canonical_digest": canonical_digest,
        "canonical_file_sha256_before": canonical_file_hash_before,
        "canonical_file_sha256_after": canonical_file_hash_after,
        "outcome": resolution["outcome"],
        "expected_defeated_enemy_ids": expected_defeated,
        "expected_dead_descender_ids": expected_dead,
        "expected_retreated_descender_ids": expected_retreated,
        "spawned_descenders": spawned_descenders,
        "spawned_monsters": spawned_monsters,
        "ledger_event_count": len(truth["ledger_events"]),
        "validation": validation,
    }
    DEBUG_PATH.write_text(json.dumps(debug, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not validation["all_pass"]:
        raise RuntimeError(f"29C.2 Unreal presentation truth validation failed: {validation}")
    unreal.log(
        f"[Underreach29C2] PASS outcome={debug['outcome']} "
        f"descenders={len(spawned_descenders)} monsters={len(spawned_monsters)}"
    )
    unreal.log(f"[Underreach29C2] Output={DEBUG_PATH}")


main()
