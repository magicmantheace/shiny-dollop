#!/usr/bin/env python3
"""Deterministic procedural lantern prop generator (F5.3).

Builds a minimal, valid binary glTF (GLB) of a small tavern lantern —
hexagonal frame (base, six pillars, top cap, knob), an emissive core
and a tube handle — from fixed geometry constants, Python stdlib only.
The output is byte-identical on every run AND on every platform: no
timestamps, no random seeds, no environment input; vertex data is
packed from the same float computations and the JSON chunk is
serialized with fixed separators. "Every platform" is load-bearing:
CPython's math.sin / math.cos delegate to the platform C library,
whose last-bit rounding differs between libcs (glibc vs the Windows
CRT), and the ADR-008 hash gate caught this generator producing a
different SHA-256 on Windows than on Linux — the hexagon flat normals
subtract two nearly equal sines, so the residual is pure libm
rounding noise. The trigonometry below is therefore pure Python over
+, -, * and / (IEEE 754 correctly rounded, identical bits everywhere);
see ADR-010. That determinism is what lets the asset catalog pin a
SHA-256 for the generated file
(examples/lantern_procedural_catalog.json) and the ADR-008 promotion
gates verify it, exactly like a hand-authored asset.

The lantern is an original procedural model, CC0-1.0 by construction.
It has no skeleton and no animations: it is a `prop` — scenes attach it
to an actor's hand socket (F4.2) and carry it.

Usage: python3 tools/generate_lantern.py --out <path.glb>
"""
from __future__ import annotations

import argparse
import json
import math
import struct
import sys
from pathlib import Path

# --- Lantern dimensions (metres, origin at the base centre, +Y up) ---
HEX_RADIUS = 0.062          # base / top cap hexagon circumradius
HEX_SIDES = 6
BASE_Y0, BASE_Y1 = 0.0, 0.014
CORE_RADIUS = 0.030
CORE_Y0, CORE_Y1 = 0.014, 0.104
PILLAR_RADIUS = 0.052       # hexagon corner radius the pillars sit on
PILLAR_HALF = 0.005         # pillar box half-extent (square section)
PILLAR_Y0, PILLAR_Y1 = 0.014, 0.104
TOP_Y0, TOP_Y1 = 0.104, 0.118
KNOB_RADIUS = 0.012
KNOB_Y0, KNOB_Y1 = 0.118, 0.128
HANDLE_CENTER_Y = 0.128
HANDLE_RADIUS = 0.038
HANDLE_TUBE = 0.0055
HANDLE_ARC_STEPS = 12
HANDLE_SECTION_SIDES = 8


# --- Deterministic trigonometry (ADR-010) ---
# math.sin / math.cos call the platform C library, which does not
# round the last bit identically across libcs; every other float
# operation this file needs (+, -, *, / and math.sqrt, whose correct
# rounding IEEE 754 mandates) is bit-identical on every platform.
# So sine and cosine are computed here in pure Python: quadrant
# reduction against a two-part pi/2 (Cody-Waite, so the reduced
# argument stays accurate), then Taylor polynomials in Horner form.
# Every operation is correctly rounded, so the results are the same
# doubles on any IEEE 754 platform, and the geometry built from them
# packs to the same bytes. Accuracy vs the platform libm is within a
# couple of ULP over the angles used here (all in [0, 2*pi]) — far
# below the float32 packing the GLB applies.
_PI_2_HI = 1.5707963267948966      # double nearest pi/2
_PI_2_LO = 6.123233995736766e-17   # pi/2 - _PI_2_HI


def _reduce_quadrant(x: float):
    """Split x into (r, q) with x ~= q * (pi/2) + r, r in [-pi/4, pi/4]."""
    q = math.floor(x / _PI_2_HI + 0.5)
    r = (x - q * _PI_2_HI) - q * _PI_2_LO
    return r, q % 4


def _sin_poly(r: float) -> float:
    """Taylor sine for |r| <= pi/4, through r**17 (Horner form)."""
    r2 = r * r
    return r * (1.0 + r2 * (-1.0 / 6.0 + r2 * (1.0 / 120.0 + r2 * (
        -1.0 / 5040.0 + r2 * (1.0 / 362880.0 + r2 * (
            -1.0 / 39916800.0 + r2 * (1.0 / 6227020800.0 + r2 * (
                -1.0 / 1307674368000.0 + r2 * (
                    1.0 / 355687428096000.0)))))))))


def _cos_poly(r: float) -> float:
    """Taylor cosine for |r| <= pi/4, through r**16 (Horner form)."""
    r2 = r * r
    return 1.0 + r2 * (-1.0 / 2.0 + r2 * (1.0 / 24.0 + r2 * (
        -1.0 / 720.0 + r2 * (1.0 / 40320.0 + r2 * (
            -1.0 / 3628800.0 + r2 * (1.0 / 479001600.0 + r2 * (
                -1.0 / 87178291200.0 + r2 * (
                    1.0 / 20922789888000.0))))))))


def _sin(x: float) -> float:
    r, q = _reduce_quadrant(x)
    if q == 0:
        return _sin_poly(r)
    if q == 1:
        return _cos_poly(r)
    if q == 2:
        return -_sin_poly(r)
    return -_cos_poly(r)


def _cos(x: float) -> float:
    r, q = _reduce_quadrant(x)
    if q == 0:
        return _cos_poly(r)
    if q == 1:
        return -_sin_poly(r)
    if q == 2:
        return -_cos_poly(r)
    return _sin_poly(r)


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


class TriangleSoup:
    """Non-indexed triangles with flat (per-face) normals."""

    def __init__(self) -> None:
        self.positions: list[float] = []
        self.normals: list[float] = []

    def triangle(self, a, b, c) -> None:
        normal = _cross(_sub(b, a), _sub(c, a))
        length = math.sqrt(sum(v * v for v in normal)) or 1.0
        unit = tuple(v / length for v in normal)
        for point in (a, b, c):
            self.positions.extend(point)
            self.normals.extend(unit)

    def quad(self, p00, p01, p11, p10) -> None:
        # (p00, p01, p11) + (p00, p11, p10): with u along p00->p10 and
        # v along p00->p01 the face normal is v x u; callers pick axis
        # pairs with v x u pointing outward.
        self.triangle(p00, p01, p11)
        self.triangle(p00, p11, p10)

    def vertex_count(self) -> int:
        return len(self.positions) // 3


def _ring_point(radius: float, sides: int, index: int, y: float):
    angle = 2.0 * math.pi * index / sides
    return (radius * _cos(angle), y, radius * _sin(angle))


def add_prism(soup: TriangleSoup, radius: float, sides: int,
              y0: float, y1: float) -> None:
    """A vertical n-gonal prism (side quads + top/bottom fans)."""
    for i in range(sides):
        j = (i + 1) % sides
        b0 = _ring_point(radius, sides, i, y0)
        b1 = _ring_point(radius, sides, j, y0)
        t0 = _ring_point(radius, sides, i, y1)
        t1 = _ring_point(radius, sides, j, y1)
        soup.quad(b0, t0, t1, b1)                     # side, outward
        soup.triangle((0.0, y1, 0.0), t1, t0)         # top fan, +Y
        soup.triangle((0.0, y0, 0.0), b0, b1)         # bottom fan, -Y


def add_box(soup: TriangleSoup, center, half) -> None:
    """An axis-aligned box; per-face (normal, u, v) with v x u = normal."""
    cx, cy, cz = center
    hx, hy, hz = half
    faces = [
        ((0, 1, 0), (1, 0, 0), (0, 0, 1), (cx, cy + hy, cz), (hx, hz)),
        ((0, -1, 0), (1, 0, 0), (0, 0, -1), (cx, cy - hy, cz), (hx, hz)),
        ((1, 0, 0), (0, 0, 1), (0, 1, 0), (cx + hx, cy, cz), (hz, hy)),
        ((-1, 0, 0), (0, 0, -1), (0, 1, 0), (cx - hx, cy, cz), (hz, hy)),
        ((0, 0, 1), (-1, 0, 0), (0, 1, 0), (cx, cy, cz + hz), (hx, hy)),
        ((0, 0, -1), (1, 0, 0), (0, 1, 0), (cx, cy, cz - hz), (hx, hy)),
    ]
    for _normal, u, v, c, (hu, hv) in faces:
        def pt(su, sv, u=u, v=v, c=c, hu=hu, hv=hv):
            return (c[0] + su * hu * u[0] + sv * hv * v[0],
                    c[1] + su * hu * u[1] + sv * hv * v[1],
                    c[2] + su * hu * u[2] + sv * hv * v[2])
        soup.quad(pt(-1, -1), pt(-1, 1), pt(1, 1), pt(1, -1))


def add_handle(soup: TriangleSoup) -> None:
    """A semicircular tube handle standing on the top cap (+Y plane arc).

    The arc runs in the XY plane from (R, y, 0) over the top to
    (-R, y, 0); each ring's cross-section is spanned by the arc radial
    direction and +Z. Open ends are capped with triangle fans.
    """
    def ring(t: float):
        angle = math.pi * t
        center = (HANDLE_RADIUS * _cos(angle),
                  HANDLE_CENTER_Y + HANDLE_RADIUS * _sin(angle), 0.0)
        radial = (_cos(angle), _sin(angle), 0.0)
        points = []
        for k in range(HANDLE_SECTION_SIDES):
            phi = 2.0 * math.pi * k / HANDLE_SECTION_SIDES
            offset = tuple(HANDLE_TUBE * (_cos(phi) * radial[d]
                                          + (_sin(phi) if d == 2 else 0.0))
                           for d in range(3))
            points.append(tuple(center[d] + offset[d] for d in range(3)))
        return center, points

    rings = [ring(i / HANDLE_ARC_STEPS) for i in range(HANDLE_ARC_STEPS + 1)]
    for i in range(HANDLE_ARC_STEPS):
        _, here = rings[i]
        _, nxt = rings[i + 1]
        for k in range(HANDLE_SECTION_SIDES):
            k2 = (k + 1) % HANDLE_SECTION_SIDES
            soup.quad(here[k], nxt[k], nxt[k2], here[k2])
    for center, points in (rings[0], rings[-1]):
        for k in range(HANDLE_SECTION_SIDES):
            k2 = (k + 1) % HANDLE_SECTION_SIDES
            if center is rings[0][0]:
                soup.triangle(center, points[k2], points[k])
            else:
                soup.triangle(center, points[k], points[k2])


def build_frame() -> TriangleSoup:
    soup = TriangleSoup()
    add_prism(soup, HEX_RADIUS, HEX_SIDES, BASE_Y0, BASE_Y1)
    for i in range(HEX_SIDES):
        angle = 2.0 * math.pi * i / HEX_SIDES
        center = (PILLAR_RADIUS * _cos(angle),
                  (PILLAR_Y0 + PILLAR_Y1) / 2.0,
                  PILLAR_RADIUS * _sin(angle))
        add_box(soup, center,
                (PILLAR_HALF, (PILLAR_Y1 - PILLAR_Y0) / 2.0, PILLAR_HALF))
    add_prism(soup, HEX_RADIUS, HEX_SIDES, TOP_Y0, TOP_Y1)
    add_prism(soup, KNOB_RADIUS, 12, KNOB_Y0, KNOB_Y1)
    add_handle(soup)
    return soup


def build_core() -> TriangleSoup:
    soup = TriangleSoup()
    add_prism(soup, CORE_RADIUS, 16, CORE_Y0, CORE_Y1)
    return soup


def _pack_f32(values: list[float]) -> bytes:
    return struct.pack(f"<{len(values)}f", *values)


def _bounds(values: list[float]):
    xs = values[0::3]
    ys = values[1::3]
    zs = values[2::3]
    return ([min(xs), min(ys), min(zs)], [max(xs), max(ys), max(zs)])


def build_lantern_glb() -> bytes:
    """The lantern GLB document, byte-identical on every call."""
    frame = build_frame()
    core = build_core()
    bin_chunks: list[bytes] = []
    buffer_views: list[dict] = []
    accessors: list[dict] = []
    meshes: list[dict] = []

    def add_mesh(soup: TriangleSoup, material: int) -> int:
        attributes = {}
        for semantic, values in (("POSITION", soup.positions),
                                 ("NORMAL", soup.normals)):
            raw = _pack_f32(values)
            offset = sum(len(chunk) for chunk in bin_chunks)
            bin_chunks.append(raw)
            buffer_views.append({"buffer": 0, "byteOffset": offset,
                                 "byteLength": len(raw)})
            accessor = {"bufferView": len(buffer_views) - 1,
                        "componentType": 5126, "count": soup.vertex_count(),
                        "type": "VEC3"}
            if semantic == "POSITION":
                low, high = _bounds(values)
                accessor["min"] = low
                accessor["max"] = high
            accessors.append(accessor)
            attributes[semantic] = len(accessors) - 1
        meshes.append({"name": "lantern_mesh", "primitives": [
            {"attributes": attributes, "material": material, "mode": 4}]})
        return len(meshes) - 1

    frame_mesh = add_mesh(frame, 0)
    core_mesh = add_mesh(core, 1)
    bin_data = b"".join(bin_chunks)
    doc = {
        "asset": {"version": "2.0",
                  "generator": "ai-animation-studio tools/generate_lantern.py"},
        "scene": 0,
        "scenes": [{"name": "Lantern", "nodes": [0]}],
        "nodes": [
            {"name": "Lantern", "children": [1, 2]},
            {"name": "LanternFrame", "mesh": frame_mesh},
            {"name": "LanternCore", "mesh": core_mesh},
        ],
        "meshes": meshes,
        "materials": [
            {"name": "lantern_frame_metal",
             "pbrMetallicRoughness": {
                 "baseColorFactor": [0.18, 0.16, 0.14, 1.0],
                 "metallicFactor": 0.85, "roughnessFactor": 0.45}},
            {"name": "lantern_flame_core",
             "pbrMetallicRoughness": {
                 "baseColorFactor": [1.0, 0.72, 0.3, 1.0],
                 "metallicFactor": 0.0, "roughnessFactor": 0.6},
             "emissiveFactor": [1.0, 0.55, 0.12]},
        ],
        "bufferViews": buffer_views,
        "accessors": accessors,
        "buffers": [{"byteLength": len(bin_data)}],
    }
    json_chunk = json.dumps(doc, separators=(",", ":")).encode("utf-8")
    json_chunk += b" " * (-len(json_chunk) % 4)
    bin_padded = bin_data + b"\x00" * (-len(bin_data) % 4)
    total = 12 + 8 + len(json_chunk) + 8 + len(bin_padded)
    return b"".join([
        struct.pack("<III", 0x46546C67, 2, total),
        struct.pack("<II", len(json_chunk), 0x4E4F534A), json_chunk,
        struct.pack("<II", len(bin_padded), 0x004E4942), bin_padded,
    ])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate the procedural lantern prop GLB (deterministic)")
    parser.add_argument("--out", type=Path, required=True,
                        help="output .glb path")
    args = parser.parse_args(argv)
    data = build_lantern_glb()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(data)
    print(f"Wrote {args.out} ({len(data)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
