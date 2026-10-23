"""Deterministic multi-Sector presentation planning for Underreach 29B.2.

The plan is downstream of the canonical simulation. It provides reproducible
room/corridor placement, an entry-to-exit traversal proof, and camera handoff
windows without deciding whether a Descender is allowed to move.
"""

from __future__ import annotations

from collections import deque
import hashlib
import json
import math

from .stratum_environment import validate_stratum_environment_manifest

MULTISECTOR_PROTOCOL = "underreach.multisector-presentation.v1"
GENERATOR_VERSION = "29b2.1"
CORRIDOR_WIDTH_CM = 900.0
CORRIDOR_HEIGHT_CM = 420.0
DOOR_WIDTH_CM = 420.0
DOOR_HEIGHT_CM = 420.0
TRANSITION_SECONDS = 2.5
SECTOR_HOLD_SECONDS = 4.0


def _digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _adjacency(manifest: dict) -> dict[str, set[str]]:
    result = {sector["sector_id"]: set() for sector in manifest["sectors"]}
    for edge in manifest["connections"]:
        result[edge["a"]].add(edge["b"])
        result[edge["b"]].add(edge["a"])
    return result


def shortest_sector_route(manifest: dict, start_id: str | None = None, end_id: str | None = None) -> list[str]:
    validate_stratum_environment_manifest(manifest)
    start = start_id or manifest["entry_sector_id"]
    end = end_id or manifest["exit_sector_id"]
    adjacency = _adjacency(manifest)
    if start not in adjacency or end not in adjacency:
        raise ValueError("route endpoints must be valid Sector ids")
    parent: dict[str, str | None] = {start: None}
    queue = deque([start])
    while queue:
        current = queue.popleft()
        if current == end:
            break
        for neighbor in sorted(adjacency[current]):
            if neighbor not in parent:
                parent[neighbor] = current
                queue.append(neighbor)
    if end not in parent:
        raise ValueError("no route exists between requested Sectors")
    route = []
    current: str | None = end
    while current is not None:
        route.append(current)
        current = parent[current]
    route.reverse()
    return route


def _portal_for(sector: dict, other: dict) -> dict:
    sx, sy = sector["grid"]["x"], sector["grid"]["y"]
    ox, oy = other["grid"]["x"], other["grid"]["y"]
    dx, dy = ox - sx, oy - sy
    if abs(dx) + abs(dy) != 1:
        raise ValueError("corridor endpoints must be orthogonally adjacent grid cells")
    room_x = float(sector["room_size_cm"]["x"])
    room_y = float(sector["room_size_cm"]["y"])
    origin = sector["world_origin_cm"]
    if dx:
        side = "east" if dx > 0 else "west"
        x = float(origin["x"]) + (room_x * 0.5 if dx > 0 else -room_x * 0.5)
        y = float(origin["y"])
        yaw = 0.0
    else:
        side = "north" if dy > 0 else "south"
        x = float(origin["x"])
        y = float(origin["y"]) + (room_y * 0.5 if dy > 0 else -room_y * 0.5)
        yaw = 90.0
    return {
        "side": side,
        "location_cm": {"x": x, "y": y, "z": DOOR_HEIGHT_CM * 0.5},
        "yaw_degrees": yaw,
        "width_cm": DOOR_WIDTH_CM,
        "height_cm": DOOR_HEIGHT_CM,
    }


def _corridor(edge: dict, by_id: dict[str, dict]) -> dict:
    a, b = by_id[edge["a"]], by_id[edge["b"]]
    ao, bo = a["world_origin_cm"], b["world_origin_cm"]
    ax, ay = float(ao["x"]), float(ao["y"])
    bx, by = float(bo["x"]), float(bo["y"])
    dx, dy = bx - ax, by - ay
    length = abs(dx) + abs(dy)
    horizontal = abs(dx) > 0.0
    return {
        "corridor_id": "corridor_" + hashlib.sha256(f"{edge['a']}:{edge['b']}".encode("utf-8")).hexdigest()[:12],
        "sector_a": edge["a"],
        "sector_b": edge["b"],
        "center_cm": {"x": (ax + bx) * 0.5, "y": (ay + by) * 0.5, "z": CORRIDOR_HEIGHT_CM * 0.5},
        "yaw_degrees": 0.0 if horizontal else 90.0,
        "length_cm": length,
        "width_cm": CORRIDOR_WIDTH_CM,
        "height_cm": CORRIDOR_HEIGHT_CM,
        "portal_a": _portal_for(a, b),
        "portal_b": _portal_for(b, a),
    }


def build_multisector_presentation_plan(manifest: dict) -> dict:
    """Build deterministic Unreal-ready room/corridor/traversal descriptors."""
    validate_stratum_environment_manifest(manifest)
    by_id = {sector["sector_id"]: sector for sector in manifest["sectors"]}
    route = shortest_sector_route(manifest)
    corridors = [_corridor(edge, by_id) for edge in manifest["connections"]]
    corridors.sort(key=lambda item: item["corridor_id"])

    timeline = []
    seconds = 0.0
    for index, sector_id in enumerate(route):
        sector = by_id[sector_id]
        timeline.append({
            "kind": "sector_hold",
            "sector_id": sector_id,
            "start_seconds": seconds,
            "end_seconds": seconds + SECTOR_HOLD_SECONDS,
            "camera_region_center_cm": dict(sector["world_origin_cm"]),
        })
        seconds += SECTOR_HOLD_SECONDS
        if index < len(route) - 1:
            next_id = route[index + 1]
            corridor = next(item for item in corridors if {item["sector_a"], item["sector_b"]} == {sector_id, next_id})
            timeline.append({
                "kind": "sector_transition",
                "from_sector_id": sector_id,
                "to_sector_id": next_id,
                "corridor_id": corridor["corridor_id"],
                "start_seconds": seconds,
                "end_seconds": seconds + TRANSITION_SECONDS,
                "camera_region_center_cm": dict(corridor["center_cm"]),
            })
            seconds += TRANSITION_SECONDS

    plan = {
        "protocol": MULTISECTOR_PROTOCOL,
        "generator_version": GENERATOR_VERSION,
        "authoritative": False,
        "stratum_environment_digest": manifest["digest"],
        "stratum_index": manifest["stratum_index"],
        "theme": manifest["theme"],
        "rooms": [
            {
                "sector_id": sector["sector_id"],
                "role": sector["role"],
                "world_origin_cm": dict(sector["world_origin_cm"]),
                "room_size_cm": dict(sector["room_size_cm"]),
                "presentation_room_seed": sector["presentation_room_seed"],
            }
            for sector in manifest["sectors"]
        ],
        "corridors": corridors,
        "proof_route_sector_ids": route,
        "timeline": timeline,
        "duration_seconds": seconds,
    }
    validate_multisector_presentation_plan(plan, manifest)
    plan["digest"] = _digest(plan)
    return plan


def validate_multisector_presentation_plan(plan: dict, manifest: dict) -> bool:
    if plan.get("protocol") != MULTISECTOR_PROTOCOL or plan.get("authoritative") is not False:
        raise ValueError("multi-Sector plan must use presentation-only 29B.2 protocol")
    if plan.get("stratum_environment_digest") != manifest.get("digest"):
        raise ValueError("multi-Sector plan does not match Stratum environment digest")
    room_ids = [room["sector_id"] for room in plan.get("rooms", [])]
    expected_ids = [sector["sector_id"] for sector in manifest["sectors"]]
    if room_ids != expected_ids:
        raise ValueError("room list does not cover Stratum Sectors in stable order")
    corridor_pairs = {frozenset((item["sector_a"], item["sector_b"])) for item in plan.get("corridors", [])}
    expected_pairs = {frozenset((edge["a"], edge["b"])) for edge in manifest["connections"]}
    if corridor_pairs != expected_pairs:
        raise ValueError("corridors do not exactly cover Stratum connections")
    for corridor in plan["corridors"]:
        if corridor["length_cm"] <= 0 or corridor["width_cm"] < DOOR_WIDTH_CM:
            raise ValueError("invalid corridor dimensions")
        a = next(sector for sector in manifest["sectors"] if sector["sector_id"] == corridor["sector_a"])
        b = next(sector for sector in manifest["sectors"] if sector["sector_id"] == corridor["sector_b"])
        grid_distance = abs(a["grid"]["x"] - b["grid"]["x"]) + abs(a["grid"]["y"] - b["grid"]["y"])
        if grid_distance != 1:
            raise ValueError("corridor joins non-adjacent Sectors")
    route = plan.get("proof_route_sector_ids") or []
    if not route or route[0] != manifest["entry_sector_id"] or route[-1] != manifest["exit_sector_id"]:
        raise ValueError("proof route must span entry to exit")
    adjacency = _adjacency(manifest)
    for left, right in zip(route, route[1:]):
        if right not in adjacency[left]:
            raise ValueError("proof route contains disconnected hop")
    last_end = 0.0
    for item in plan.get("timeline", []):
        start, end = float(item["start_seconds"]), float(item["end_seconds"])
        if not math.isclose(start, last_end, abs_tol=1e-9) or end <= start:
            raise ValueError("timeline must be contiguous and strictly increasing")
        last_end = end
    if not math.isclose(last_end, float(plan.get("duration_seconds", -1)), abs_tol=1e-9):
        raise ValueError("timeline duration mismatch")
    return True


def rebuild_digest(plan: dict) -> str:
    payload = dict(plan)
    payload.pop("digest", None)
    return _digest(payload)
