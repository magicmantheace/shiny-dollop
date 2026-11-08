"""Segmentation proxy builder (Blender headless, runs on the VM).

Reduces the textured mesh to ~50k faces with the EXACT recipe the
segmentation bake-off scored (benchmarks/segmentation/
scores.md): import, COLLAPSE-decimate to the face target, strip
materials — in the mesh's RAW frame, no canonicalize, no weld.
The recipe is load-bearing, not an accident: a rig-frame variant
(canonicalize + rotate-z + weld first) changed P3-SAM's prompt
draw enough to collapse the triceratops' segmentation to a
single part (measured 2026-11-06; the bake-off draw on this
recipe gave it 5 parts).

The rig stage works in the canonical frame, so this script also
emits the canonical transform of the raw mesh — the same math
rig_blender.canonicalize + rotate_z apply (uniform scale from the
raw height, centering/grounding offsets, then the run's Z
rotation) — and the segment glue stores it in labels.npz for the
rig's label transfer.

Prints PROXY_JSON {...} and PROXY_OK.
"""

import importlib.util
import json
import math
import os
import sys

import bpy


def _load_rig():
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "..", "rig", "rig_blender.py")
    spec = importlib.util.spec_from_file_location("gab_rig", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    args = {}
    for i in range(0, len(argv), 2):
        args[argv[i].lstrip("-")] = argv[i + 1]
    rb = _load_rig()
    obj = rb.import_mesh(args["input"])
    (x0, x1), (y0, y1), (z0, z1) = rb.world_bbox(obj)
    rotate_z = int(args.get("rotate-z", "0"))
    # rig_blender.canonicalize: scale s about the origin, then
    # translate so the scaled bbox is XY-centered and grounded.
    s = 2.0 / (z1 - z0)
    offset = (-s * (x0 + x1) / 2, -s * (y0 + y1) / 2, -s * z0)
    transform = {"scale": s, "offset": list(offset),
                 "rotate_z": rotate_z}
    target_faces = int(args.get("target-faces", "50000"))
    faces = len(obj.data.polygons)
    if faces > target_faces:
        mod = obj.modifiers.new("decimate", "DECIMATE")
        mod.decimate_type = "COLLAPSE"
        mod.ratio = target_faces / faces
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=mod.name)
    # P3-SAM loads the proxy with trimesh (process=True), which
    # silently drops zero-area and duplicate faces — every dropped
    # face shifts the per-face ids against this file's face list.
    # Remove them here instead, so the ids align 1:1 (the segment
    # glue validates the count and refuses to guess otherwise).
    # Measured: the goblin proxy carried exactly one such face.
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    zero = [f for f in bm.faces if f.calc_area() <= 1e-10]
    if zero:
        bmesh.ops.delete(bm, geom=zero, context="FACES")
    seen = set()
    dups = []
    bm.faces.ensure_lookup_table()
    for f in bm.faces:
        key = tuple(sorted(v.index for v in f.verts))
        if key in seen:
            dups.append(f)
        else:
            seen.add(key)
    if dups:
        bmesh.ops.delete(bm, geom=dups, context="FACES")
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    dropped = {"degenerate_faces_dropped": len(zero),
               "duplicate_faces_dropped": len(dups)}
    obj.data.materials.clear()
    out = args["output"]
    os.makedirs(os.path.dirname(out), exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=out, export_format="GLB",
                              export_apply=True)
    report = {"proxy_verts": len(obj.data.vertices),
              "proxy_faces": len(obj.data.polygons),
              "source_faces": faces,
              **dropped,
              "transform": transform}
    print("PROXY_JSON " + json.dumps(report))
    print("PROXY_OK")


if __name__ == "__main__":
    main()
