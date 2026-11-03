"""Dependency-free runtime validation for the v1 scene and asset contracts.

JSON Schema documents in schemas/ are the interchange contract. This module
enforces the security/semantic subset needed before sending commands to Godot.
"""
from __future__ import annotations

import re

VERSION = "1.0.0"
OPS = frozenset({"spawn", "move", "speak", "emote", "camera"})
EMOTIONS = frozenset({"neutral", "happy", "sad", "angry", "nervous", "surprised", "tired", "scared"})
ID = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")

class ValidationError(ValueError):
    pass

def need(ok: bool, message: str) -> None:
    if not ok:
        raise ValidationError(message)

def identifier(value: object, name: str) -> None:
    need(isinstance(value, str) and bool(ID.fullmatch(value)), f"{name}: invalid id")

def vec3(value: object, name: str) -> None:
    need(isinstance(value, list) and len(value) == 3, f"{name}: expected 3-vector")
    for n in value:
        need(type(n) in (int, float) and -1000 <= n <= 1000, f"{name}: out of bounds")

def validate_scene(scene: dict) -> dict:
    need(isinstance(scene, dict), "scene must be object")
    need(scene.get("schema_version") == VERSION, "unsupported scene version")
    identifier(scene.get("scene_id"), "scene_id")
    identifier(scene.get("environment_id"), "environment_id")
    actors = scene.get("actors")
    events = scene.get("events")
    need(isinstance(actors, list) and 1 <= len(actors) <= 32, "actors must contain 1..32 entries")
    need(isinstance(events, list) and 1 <= len(events) <= 2000, "events must contain 1..2000 entries")
    actor_ids = set()
    for actor in actors:
        need(isinstance(actor, dict), "actor must be object")
        identifier(actor.get("id"), "actor.id")
        identifier(actor.get("recipe_id"), "actor.recipe_id")
        need(actor["id"] not in actor_ids, "duplicate actor id")
        need(isinstance(actor.get("color"), str) and HEX.fullmatch(actor["color"]), "invalid actor color")
        actor_ids.add(actor["id"])
    spawned = set()
    last_time = -1
    for n, e in enumerate(events):
        prefix = f"events[{n}]"
        need(isinstance(e, dict), prefix + ": not object")
        t = e.get("at_ms")
        need(type(t) is int and 0 <= t <= 3_600_000 and t >= last_time, prefix + ": invalid ordering/time")
        last_time = t
        op = e.get("op")
        need(isinstance(op, str) and op in OPS, prefix + ": unknown operation")
        if op == "camera":
            need(isinstance(e.get("shot"), str) and e.get("shot") in {"wide", "two_shot", "close_left", "close_right"}, prefix + ": invalid shot")
            continue
        actor_id = e.get("actor_id")
        need(isinstance(actor_id, str) and actor_id in actor_ids, prefix + ": unknown actor")
        if op == "spawn":
            need(actor_id not in spawned, prefix + ": duplicate spawn")
            vec3(e.get("position"), prefix + ".position")
            spawned.add(actor_id)
        else:
            need(actor_id in spawned, prefix + ": actor not spawned")
        if op == "move":
            vec3(e.get("target"), prefix + ".target")
            d = e.get("duration_ms")
            need(type(d) is int and 100 <= d <= 60_000, prefix + ": invalid duration")
        elif op == "speak":
            line = e.get("line")
            need(isinstance(line, str) and 1 <= len(line) <= 500, prefix + ": invalid line")
        elif op == "emote":
            need(isinstance(e.get("emotion"), str) and e.get("emotion") in EMOTIONS, prefix + ": unsupported emotion")
            q = e.get("intensity")
            need(type(q) in (int, float) and 0 <= q <= 1, prefix + ": invalid intensity")
    need(bool(spawned), "scene never spawns an actor")
    return scene

def validate_asset(asset: dict) -> dict:
    need(isinstance(asset, dict), "asset must be object")
    need(asset.get("schema_version") == VERSION, "unsupported asset version")
    identifier(asset.get("asset_id"), "asset_id")
    need(isinstance(asset.get("kind"), str) and asset.get("kind") in {"body", "head", "hair", "outfit", "prop", "motion", "environment", "voice", "material"}, "invalid kind")
    uri = asset.get("uri")
    need(isinstance(uri, str) and len(uri) < 256 and uri.startswith("assets/"), "uri must be assets/ relative path")
    need(".." not in uri.split("/") and "\\" not in uri and not uri.startswith("/"), "unsafe path")
    need(isinstance(asset.get("status"), str) and asset.get("status") in {"candidate", "approved", "retired"}, "invalid asset status")
    tags = asset.get("tags")
    need(isinstance(tags, list) and len(tags) <= 32 and all(isinstance(t, str) and ID.fullmatch(t) for t in tags), "invalid tags")
    rig = asset.get("rig_id")
    need(rig is None or (isinstance(rig, str) and ID.fullmatch(rig)), "invalid rig")
    need(isinstance(asset.get("metadata"), dict), "invalid metadata")
    return asset

def validate_character(data: dict) -> dict:
    need(isinstance(data, dict), "character must be object")
    need(data.get("schema_version") == VERSION, "unsupported character version")
    for key in ("character_id", "rig_id", "body_base", "head", "hair"):
        identifier(data.get(key), key)
    outfits = data.get("outfit")
    need(isinstance(outfits, list) and len(outfits) <= 16, "invalid outfit")
    for item in outfits:
        identifier(item, "outfit[]")
    need(isinstance(data.get("colors"), dict), "colors must be object")
    need(isinstance(data.get("status"), str) and data.get("status") in {"candidate", "approved", "retired"}, "invalid character status")
    return data
