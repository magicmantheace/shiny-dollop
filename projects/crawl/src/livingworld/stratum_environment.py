"""Deterministic Stratum/Sector layout manifests for Underreach presentation.

This module is deliberately non-authoritative. The simulation owns traversal and
outcomes; these manifests give presentation systems a reproducible spatial plan.
The legacy crawl.presentation-environment.v1 room protocol remains untouched.
"""

from __future__ import annotations

from collections import deque
import hashlib
import json
import random
from typing import Iterable

STRATUM_ENVIRONMENT_PROTOCOL = "underreach.stratum-environment.v1"
GENERATOR_VERSION = "29b1.1"
GRID_SPACING_CM = 4200.0
ROOM_SIZE_CM = (2600.0, 3600.0, 700.0)
COMBAT_CLEARANCE_CM = (1200.0, 1200.0, 350.0)
DIRECTIONS = ((0, 1), (1, 0), (0, -1), (-1, 0))
DEFAULT_THEME = "ancient_stoneworks"


def _stable_seed(*parts: object) -> int:
    payload = ":".join(str(part) for part in parts).encode("utf-8")
    return int(hashlib.sha256(payload).hexdigest()[:16], 16)


def _digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _sector_id(stratum_seed: str, index: int) -> str:
    token = hashlib.sha256(f"{stratum_seed}:sector:{index}".encode("utf-8")).hexdigest()[:12]
    return f"sector_{index:02d}_{token}"


def _neighbors(cell: tuple[int, int]) -> Iterable[tuple[int, int]]:
    x, y = cell
    for dx, dy in DIRECTIONS:
        yield x + dx, y + dy


def _generate_cells(seed: str, count: int) -> list[tuple[int, int]]:
    """Grow a connected deterministic set of grid cells."""
    rng = random.Random(_stable_seed(seed, "cells", GENERATOR_VERSION))
    cells = [(0, 0)]
    occupied = {(0, 0)}
    frontier = list(_neighbors((0, 0)))
    while len(cells) < count:
        frontier = sorted(set(frontier) - occupied)
        if not frontier:
            raise RuntimeError("Stratum generator exhausted its connected frontier")
        chosen = frontier[rng.randrange(len(frontier))]
        cells.append(chosen)
        occupied.add(chosen)
        frontier.extend(_neighbors(chosen))
    return cells


def _shortest_distances(cells: list[tuple[int, int]], start: tuple[int, int]) -> dict[tuple[int, int], int]:
    allowed = set(cells)
    distances = {start: 0}
    queue = deque([start])
    while queue:
        current = queue.popleft()
        for neighbor in _neighbors(current):
            if neighbor in allowed and neighbor not in distances:
                distances[neighbor] = distances[current] + 1
                queue.append(neighbor)
    return distances


def _role_for(index: int, count: int, exit_index: int, refuge_index: int | None) -> str:
    if index == 0:
        return "entry"
    if index == exit_index:
        return "exit"
    if refuge_index is not None and index == refuge_index:
        return "refuge"
    return "combat" if index % 3 != 0 else "transit"


def build_stratum_environment_manifest(
    descent_seed: str,
    stratum_index: int = 0,
    *,
    sector_count: int = 9,
    theme: str = DEFAULT_THEME,
) -> dict:
    """Build a connected deterministic presentation manifest for one Stratum."""
    if sector_count < 4:
        raise ValueError("29B.1 requires at least four Sectors")
    seed = f"{descent_seed}:stratum:{int(stratum_index)}"
    cells = _generate_cells(seed, int(sector_count))
    distances = _shortest_distances(cells, cells[0])
    exit_cell = max(cells, key=lambda cell: (distances[cell], cell[0], cell[1]))
    exit_index = cells.index(exit_cell)
    refuge_candidates = [
        (distances[cell], index)
        for index, cell in enumerate(cells)
        if index not in (0, exit_index) and distances[cell] >= 2
    ]
    refuge_index = min(refuge_candidates, key=lambda item: (abs(item[0] - max(distances.values()) / 2), item[1]))[1] if refuge_candidates else None

    ids = [_sector_id(seed, index) for index in range(len(cells))]
    index_by_cell = {cell: index for index, cell in enumerate(cells)}
    connections = []
    for index, cell in enumerate(cells):
        for neighbor in _neighbors(cell):
            other = index_by_cell.get(neighbor)
            if other is not None and index < other:
                connections.append({"a": ids[index], "b": ids[other]})
    connections.sort(key=lambda edge: (edge["a"], edge["b"]))

    sectors = []
    for index, (grid_x, grid_y) in enumerate(cells):
        role = _role_for(index, len(cells), exit_index, refuge_index)
        sectors.append({
            "sector_id": ids[index],
            "index": index,
            "role": role,
            "grid": {"x": grid_x, "y": grid_y},
            "world_origin_cm": {"x": grid_x * GRID_SPACING_CM, "y": grid_y * GRID_SPACING_CM, "z": 0.0},
            "room_size_cm": {"x": ROOM_SIZE_CM[0], "y": ROOM_SIZE_CM[1], "z": ROOM_SIZE_CM[2]},
            "combat_clearance_cm": {"x": COMBAT_CLEARANCE_CM[0], "y": COMBAT_CLEARANCE_CM[1], "z": COMBAT_CLEARANCE_CM[2]},
            "presentation_room_seed": f"{seed}:{ids[index]}",
            "markers": {
                "entry": role == "entry",
                "exit": role == "exit",
                "refuge": role == "refuge",
                "encounter": role == "combat",
            },
        })

    manifest = {
        "protocol": STRATUM_ENVIRONMENT_PROTOCOL,
        "generator_version": GENERATOR_VERSION,
        "authoritative": False,
        "descent_seed": str(descent_seed),
        "stratum_index": int(stratum_index),
        "stratum_seed": seed,
        "theme": str(theme),
        "grid_spacing_cm": GRID_SPACING_CM,
        "entry_sector_id": ids[0],
        "exit_sector_id": ids[exit_index],
        "refuge_sector_id": ids[refuge_index] if refuge_index is not None else None,
        "sectors": sectors,
        "connections": connections,
    }
    validate_stratum_environment_manifest(manifest)
    manifest["digest"] = _digest(manifest)
    return manifest


def validate_stratum_environment_manifest(manifest: dict) -> bool:
    if manifest.get("protocol") != STRATUM_ENVIRONMENT_PROTOCOL:
        raise ValueError("unsupported Stratum environment protocol")
    if manifest.get("authoritative") is not False:
        raise ValueError("Stratum environment manifest must be presentation-only")
    sectors = manifest.get("sectors") or []
    if len(sectors) < 4:
        raise ValueError("Stratum must contain at least four Sectors")
    ids = [sector["sector_id"] for sector in sectors]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate Sector ids")
    cells = [(sector["grid"]["x"], sector["grid"]["y"]) for sector in sectors]
    if len(cells) != len(set(cells)):
        raise ValueError("overlapping Sector grid cells")
    id_set = set(ids)
    adjacency = {sector_id: set() for sector_id in ids}
    for edge in manifest.get("connections", []):
        a, b = edge["a"], edge["b"]
        if a not in id_set or b not in id_set or a == b:
            raise ValueError("invalid Sector connection")
        adjacency[a].add(b)
        adjacency[b].add(a)
    entry = manifest.get("entry_sector_id")
    exit_sector = manifest.get("exit_sector_id")
    if entry not in id_set or exit_sector not in id_set or entry == exit_sector:
        raise ValueError("invalid entry/exit Sector")
    visited = {entry}
    queue = deque([entry])
    while queue:
        current = queue.popleft()
        for neighbor in adjacency[current]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    if visited != id_set:
        raise ValueError("all Sectors must be reachable from entry")
    refuge = manifest.get("refuge_sector_id")
    if refuge is not None and refuge not in id_set:
        raise ValueError("invalid Refuge Sector")
    roles = {sector["sector_id"]: sector["role"] for sector in sectors}
    if roles[entry] != "entry" or roles[exit_sector] != "exit":
        raise ValueError("entry/exit markers disagree with Sector roles")
    if refuge is not None and roles[refuge] != "refuge":
        raise ValueError("Refuge marker disagrees with Sector role")
    for sector in sectors:
        clearance = sector["combat_clearance_cm"]
        room = sector["room_size_cm"]
        if any(float(clearance[axis]) > float(room[axis]) for axis in ("x", "y", "z")):
            raise ValueError(f"combat clearance exceeds room bounds: {sector['sector_id']}")
    return True


def rebuild_digest(manifest: dict) -> str:
    """Recalculate the digest without trusting a persisted digest field."""
    payload = dict(manifest)
    payload.pop("digest", None)
    return _digest(payload)
