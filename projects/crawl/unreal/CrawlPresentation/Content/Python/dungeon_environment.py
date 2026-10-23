"""Deterministic, non-authoritative Slice 28A.5 dungeon presentation plan."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


ENVIRONMENT_PROTOCOL = "crawl.presentation-environment.v1"
ROOM_ARCHETYPE = "modular_stone_combat_room"
ROOM_HALF_X = 1300.0
ROOM_HALF_Y = 1800.0
ROOM_HEIGHT = 700.0
SAFE_HALF_X = 600.0
SAFE_HALF_Y = 600.0
CAMERA_INSET = 60.0
FLOOR_Z = 0.0
SLOT_FALLBACKS = {
    "environment.dungeon.floor.standard": "/Engine/BasicShapes/Cube.Cube",
    "environment.dungeon.wall.standard": "/Engine/BasicShapes/Cube.Cube",
    "environment.dungeon.wall.corner": "/Engine/BasicShapes/Cube.Cube",
    "environment.dungeon.wall.doorway": "/Engine/BasicShapes/Cube.Cube",
    "environment.dungeon.pillar": "/Engine/BasicShapes/Cylinder.Cylinder",
    "environment.dungeon.ceiling": "/Engine/BasicShapes/Cube.Cube",
    "environment.dungeon.arch": "/Engine/BasicShapes/Cube.Cube",
    "environment.dungeon.rubble": "/Engine/BasicShapes/Sphere.Sphere",
    "environment.dungeon.crate": "/Engine/BasicShapes/Cube.Cube",
    "environment.dungeon.barrel": "/Engine/BasicShapes/Cylinder.Cylinder",
    "environment.dungeon.torch": "/Engine/BasicShapes/Cylinder.Cylinder",
}


def resolve_environment_asset_path(slots, slot, asset_exists):
    """Resolve a semantic environment slot with an explicit safe fallback."""
    requested = slots.get(slot)
    if requested and asset_exists(requested):
        return requested, False
    fallback = SLOT_FALLBACKS.get(slot, "/Engine/BasicShapes/Cube.Cube")
    if not asset_exists(fallback):
        raise ValueError(f"environment fallback is missing for {slot}: {fallback}")
    return fallback, True


def _stable_int(*parts: object) -> int:
    payload = ":".join(str(part) for part in parts).encode("utf-8")
    return int(hashlib.sha256(payload).hexdigest()[:16], 16)


def _choice(options, *parts):
    return options[_stable_int(*parts) % len(options)]


def _aabb(center, size):
    return {
        "min": {axis: float(center[index]) - float(size[index]) * 0.5 for index, axis in enumerate(("x", "y", "z"))},
        "max": {axis: float(center[index]) + float(size[index]) * 0.5 for index, axis in enumerate(("x", "y", "z"))},
    }


def _transform(x, y, z, sx, sy, sz, yaw=0.0):
    return {
        "location": {"x": float(x), "y": float(y), "z": float(z)},
        "rotation": {"roll": 0.0, "pitch": 0.0, "yaw": float(yaw)},
        "size": {"x": float(sx), "y": float(sy), "z": float(sz)},
    }


def _module(module_id, slot, transform, *, collision_critical=True, blocks_camera=True, material="wall"):
    center = tuple(transform["location"][axis] for axis in ("x", "y", "z"))
    size = tuple(transform["size"][axis] for axis in ("x", "y", "z"))
    return {
        "id": module_id,
        "asset_slot": slot,
        "transform": transform,
        "bounds": _aabb(center, size),
        "material_profile": material,
        "collision_critical": bool(collision_critical),
        "blocks_camera": bool(blocks_camera),
    }


def _overlaps_xy(left, right):
    return not (
        left["max"]["x"] <= right["min"]["x"]
        or left["min"]["x"] >= right["max"]["x"]
        or left["max"]["y"] <= right["min"]["y"]
        or left["min"]["y"] >= right["max"]["y"]
    )


def build_environment_manifest(presentation_seed: str, room_index: int = 0):
    seed = str(presentation_seed)
    room_id = "room_" + hashlib.sha256(f"{seed}:{ROOM_ARCHETYPE}:{room_index}".encode("utf-8")).hexdigest()[:16]
    room_width = ROOM_HALF_X * 2.0
    room_depth = ROOM_HALF_Y * 2.0
    wall_x = ROOM_HALF_X - 25.0
    wall_y = ROOM_HALF_Y - 25.0
    pillar_x = ROOM_HALF_X - 180.0
    pillar_y = ROOM_HALF_Y - 200.0
    modules = [
        _module("floor", "environment.dungeon.floor.standard", _transform(0, 0, -15, room_width, room_depth, 30), material="floor"),
        _module("wall_west", "environment.dungeon.wall.standard", _transform(-wall_x, 0, 350, 50, room_depth, 700)),
        _module("wall_east", "environment.dungeon.wall.standard", _transform(wall_x, 0, 350, 50, room_depth, 700)),
        _module("wall_south", "environment.dungeon.wall.standard", _transform(0, -wall_y, 350, room_width, 50, 700)),
        _module("doorway_left", "environment.dungeon.wall.doorway", _transform(-740, wall_y, 350, 1120, 50, 700)),
        _module("doorway_right", "environment.dungeon.wall.doorway", _transform(740, wall_y, 350, 1120, 50, 700)),
        _module("doorway_lintel", "environment.dungeon.arch", _transform(0, wall_y, 610, 360, 70, 180)),
        _module("ceiling", "environment.dungeon.ceiling", _transform(0, 0, 715, room_width, room_depth, 30)),
    ]
    for x, y, label in (
        (-850.0, -pillar_y, "southwest"),
        (pillar_x, -pillar_y, "southeast"),
        (-pillar_x, pillar_y, "northwest"),
        (pillar_x, pillar_y, "northeast"),
    ):
        modules.append(
            _module(
                f"pillar_{label}",
                "environment.dungeon.pillar",
                _transform(x, y, 350, 130, 130, 700),
            )
        )

    prop_candidates = (
        (1020.0, 980.0), (-1020.0, 980.0), (1060.0, 420.0),
        (-1060.0, 420.0), (1030.0, -850.0), (950.0, -250.0),
    )
    prop_slots = (
        "environment.dungeon.crate",
        "environment.dungeon.barrel",
    )
    props = []
    for index, (x, y) in enumerate(prop_candidates):
        slot = _choice(prop_slots, seed, ROOM_ARCHETYPE, room_index, "prop", index)
        yaw = float((_stable_int(seed, room_index, "yaw", index) % 8) * 45)
        if slot.endswith("barrel"):
            size, z = (85.0, 85.0, 120.0), 60.0
        elif slot.endswith("rubble"):
            size, z = (150.0, 110.0, 55.0), 27.5
        else:
            size, z = (105.0, 105.0, 105.0), 52.5
        props.append(_module(f"prop_{index:02d}", slot, _transform(x, y, z, *size, yaw=yaw), collision_critical=False, material="prop"))

    lights = []
    for index, (x, y) in enumerate(((-1180, -700), (1180, -700), (-1180, 700), (1180, 700))):
        jitter = (_stable_int(seed, room_index, "light", index) % 401) - 200
        lights.append({
            "id": f"torch_light_{index:02d}",
            "asset_slot": "environment.dungeon.torch",
            "type": "point",
            "location": {"x": float(x), "y": float(y), "z": 430.0},
            "intensity": 650.0 + float(jitter) * 0.15,
            "attenuation_radius": 1600.0,
            "color": {"r": 255, "g": 157 + index * 4, "b": 91 + index * 3},
        })
    lights.append({
        "id": "ambient_fill",
        "type": "sky",
        "location": {"x": 0.0, "y": 0.0, "z": 500.0},
        "intensity": 0.5,
        "color": {"r": 255, "g": 220, "b": 185},
    })

    safe_bounds = _aabb((0.0, 0.0, 175.0), (SAFE_HALF_X * 2.0, SAFE_HALF_Y * 2.0, 350.0))
    forbidden = [
        {"id": item["id"], "bounds": item["bounds"]}
        for item in (*modules, *props)
        if item["blocks_camera"]
    ]
    manifest = {
        "protocol": ENVIRONMENT_PROTOCOL,
        "authoritative": False,
        "presentation_seed": seed,
        "room_id": room_id,
        "room_index": int(room_index),
        "archetype": ROOM_ARCHETYPE,
        "room_bounds": {
            "min": {"x": -ROOM_HALF_X, "y": -ROOM_HALF_Y, "z": FLOOR_Z},
            "max": {"x": ROOM_HALF_X, "y": ROOM_HALF_Y, "z": ROOM_HEIGHT},
        },
        "valid_camera_region": {
            "min": {"x": -ROOM_HALF_X + CAMERA_INSET, "y": -ROOM_HALF_Y + CAMERA_INSET, "z": 80.0},
            "max": {"x": ROOM_HALF_X - CAMERA_INSET, "y": ROOM_HALF_Y - CAMERA_INSET, "z": ROOM_HEIGHT - 80.0},
        },
        "combat_safe_zone_bounds": safe_bounds,
        "modules": modules,
        "props": props,
        "lights": lights,
        "camera_forbidden_volumes": forbidden,
        "asset_slots": sorted({item["asset_slot"] for item in (*modules, *props, *lights) if item.get("asset_slot")}),
        "source_textures": {
            "wall": "SourceAssets/Environment/dungeon_wall_stone.png",
            "floor": "SourceAssets/Environment/dungeon_floor_flagstone.png",
        },
    }
    validate_environment_manifest(manifest)
    digest_payload = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    manifest["digest"] = hashlib.sha256(digest_payload.encode("utf-8")).hexdigest()
    return manifest


def validate_environment_manifest(manifest):
    if manifest.get("protocol") != ENVIRONMENT_PROTOCOL or manifest.get("authoritative") is not False:
        raise ValueError("environment manifest must be presentation-only v1")
    bounds = manifest["room_bounds"]
    if not all(bounds["min"][axis] < bounds["max"][axis] for axis in ("x", "y", "z")):
        raise ValueError("invalid dungeon room bounds")
    module_ids = {module["id"] for module in manifest["modules"]}
    required = {"floor", "wall_west", "wall_east", "wall_south", "doorway_left", "doorway_right", "doorway_lintel", "ceiling"}
    if not required.issubset(module_ids):
        raise ValueError("dungeon room is missing required modules")
    safe = manifest["combat_safe_zone_bounds"]
    for prop in manifest["props"]:
        if _overlaps_xy(prop["bounds"], safe):
            raise ValueError(f"prop overlaps combat-safe zone: {prop['id']}")
    return True


def _point_inside(point, bounds, margin=0.0):
    return all(
        float(bounds["min"][axis]) + margin <= float(point[axis]) <= float(bounds["max"][axis]) - margin
        for axis in ("x", "y", "z")
    )


def _segment_intersects_aabb(start, end, bounds):
    t_min, t_max = 0.0, 1.0
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
        t_min = max(t_min, first)
        t_max = min(t_max, second)
        if t_min > t_max:
            return False
    return t_max >= max(t_min, 1e-4) and t_min <= 0.9999


def camera_environment_diagnostics(camera_debug, manifest):
    room = manifest["room_bounds"]
    valid = manifest["valid_camera_region"]
    obstacle_ids = {item["id"] for item in (*manifest["props"], *manifest["modules"]) if item.get("blocks_camera")}
    volume_by_id = {item["id"]: item["bounds"] for item in manifest["camera_forbidden_volumes"] if item["id"] in obstacle_ids}
    samples = []
    minimum_clearance = float("inf")
    obstruction_hits = 0
    for shot in camera_debug.get("camera_shots", []):
        camera = shot["camera_position"]
        inside_valid = _point_inside(camera, valid)
        inside_geometry = [volume_id for volume_id, volume in volume_by_id.items() if _point_inside(camera, volume)]
        clearance = min(
            float(camera["x"]) - float(room["min"]["x"]),
            float(room["max"]["x"]) - float(camera["x"]),
            float(camera["y"]) - float(room["min"]["y"]),
            float(room["max"]["y"]) - float(camera["y"]),
            float(camera["z"]) - float(room["min"]["z"]),
            float(room["max"]["z"]) - float(camera["z"]),
        )
        minimum_clearance = min(minimum_clearance, clearance)
        los_hits = {}
        for actor_id, target in shot.get("sampled_target_positions", {}).items():
            hits = [volume_id for volume_id, volume in volume_by_id.items() if _segment_intersects_aabb(camera, target, volume)]
            if hits:
                los_hits[actor_id] = hits
                obstruction_hits += len(hits)
        valid_sample = inside_valid and not inside_geometry and not los_hits
        samples.append({
            "seconds": float(shot["seconds"]),
            "inside_valid_region": inside_valid,
            "inside_geometry": inside_geometry,
            "nearest_wall_or_ceiling_distance_cm": clearance,
            "los_valid": not los_hits,
            "obstruction_hits": los_hits,
            "valid": valid_sample,
        })
    return {
        "sample_count": len(samples),
        "all_samples_valid": all(sample["valid"] for sample in samples),
        "minimum_camera_clearance_cm": 0.0 if not samples else minimum_clearance,
        "obstruction_hit_count": obstruction_hits,
        "samples": samples,
    }


def write_environment_manifest(stage_manifest_path, output_path, room_index=0):
    stage_path = Path(stage_manifest_path)
    stage = json.loads(stage_path.read_text(encoding="utf-8"))
    before = hashlib.sha256(stage_path.read_bytes()).hexdigest()
    manifest = build_environment_manifest(stage["presentation_seed"], room_index=room_index)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    after = hashlib.sha256(stage_path.read_bytes()).hexdigest()
    if before != after:
        raise RuntimeError("environment generation mutated canonical staging input")
    return manifest


def main():
    parser = argparse.ArgumentParser(description="Generate deterministic Crawl dungeon presentation environment")
    parser.add_argument("--stage-manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--room-index", type=int, default=0)
    args = parser.parse_args()
    manifest = write_environment_manifest(args.stage_manifest, args.output, args.room_index)
    print(json.dumps({
        "protocol": manifest["protocol"],
        "room_id": manifest["room_id"],
        "archetype": manifest["archetype"],
        "module_count": len(manifest["modules"]),
        "prop_count": len(manifest["props"]),
        "light_count": len(manifest["lights"]),
        "digest": manifest["digest"],
        "output": str(Path(args.output)),
    }, indent=2))


if __name__ == "__main__":
    main()
