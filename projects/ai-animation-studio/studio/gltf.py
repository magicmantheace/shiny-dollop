"""Minimal glTF inspection helpers (Python stdlib only).

Used by the promotion gates and the socket measurement: joint counts,
animation clip inventories and bind-pose bone world positions, read from
the glTF document itself. For .glb files the JSON chunk is parsed; for
.gltf files the JSON document is parsed (external buffers are not needed
for document-level facts). Hashing always covers the document file the
catalog records (for .gltf, its referenced buffers stay store-managed).
"""
from __future__ import annotations

import hashlib
import json
import math
import struct
from pathlib import Path


def load_gltf_json(path: Path) -> dict:
    data = Path(path).read_bytes()
    if data[:4] == b"glTF":
        if len(data) < 20:
            raise ValueError(f"{path}: truncated GLB header")
        length = struct.unpack("<I", data[12:16])[0]
        return json.loads(data[20:20 + length])
    return json.loads(data)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def joint_count(doc: dict) -> int:
    skins = doc.get("skins") or []
    if not skins:
        return 0
    return len(skins[0].get("joints") or [])


def clip_durations(doc: dict) -> dict[str, float]:
    """Animation name -> duration in seconds, from sampler input maxima."""
    clips: dict[str, float] = {}
    accessors = doc.get("accessors") or []
    for animation in doc.get("animations") or []:
        duration = 0.0
        for sampler in animation.get("samplers") or []:
            accessor = accessors[sampler["input"]]
            duration = max(duration, float((accessor.get("max") or [0])[0]))
        clips[animation.get("name", "")] = duration
    return clips


def _local_matrix(node: dict) -> list[list[float]]:
    if "matrix" in node:
        m = node["matrix"]
        return [[m[4 * r + c] for c in range(4)] for r in range(4)]
    tx, ty, tz = node.get("translation", [0.0, 0.0, 0.0])
    qx, qy, qz, qw = node.get("rotation", [0.0, 0.0, 0.0, 1.0])
    sx, sy, sz = node.get("scale", [1.0, 1.0, 1.0])
    # Rotation matrix from a unit quaternion (glTF uses x, y, z, w order).
    rot = [
        [1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy - qz * qw), 2 * (qx * qz + qy * qw)],
        [2 * (qx * qy + qz * qw), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz - qx * qw)],
        [2 * (qx * qz - qy * qw), 2 * (qy * qz + qx * qw), 1 - 2 * (qx * qx + qy * qy)],
    ]
    mat = [[rot[r][c] * (sx, sy, sz)[c] for c in range(3)] + [0.0] for r in range(3)]
    mat[0][3], mat[1][3], mat[2][3] = tx, ty, tz
    mat.append([0.0, 0.0, 0.0, 1.0])
    return mat


def _multiply(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [[sum(a[r][k] * b[k][c] for k in range(4)) for c in range(4)] for r in range(4)]


def node_world_positions(doc: dict) -> dict[str, tuple[float, float, float]]:
    """Bind-pose world position of every named node, from the node tree."""
    nodes = doc.get("nodes") or []
    scenes = doc.get("scenes") or [{}]
    roots = scenes[doc.get("scene", 0)].get("nodes") or []
    identity = [[1.0 if r == c else 0.0 for c in range(4)] for r in range(4)]
    positions: dict[str, tuple[float, float, float]] = {}

    def walk(index: int, parent: list[list[float]]) -> None:
        node = nodes[index]
        world = _multiply(parent, _local_matrix(node))
        name = node.get("name")
        if name:
            positions[name] = (world[0][3], world[1][3], world[2][3])
        for child in node.get("children") or []:
            walk(child, world)

    for root in roots:
        walk(root, identity)
    return positions


def joint_world_positions(doc: dict) -> dict[str, tuple[float, float, float]]:
    """World positions restricted to the first skin's joint nodes."""
    positions = node_world_positions(doc)
    nodes = doc.get("nodes") or []
    skins = doc.get("skins") or []
    if not skins:
        return {}
    result = {}
    for joint in skins[0].get("joints") or []:
        name = nodes[joint].get("name")
        if name in positions:
            result[name] = positions[name]
    return result


def round3(point: tuple[float, float, float]) -> list[float]:
    return [round(component, 3) for component in point]


def distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))
