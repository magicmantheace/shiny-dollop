"""Rig stage (Blender headless): textured GLB -> rigged GLB + .blend.

Canonicalize (bake importer transforms, scale to height 2.0, center XY,
ground Z — the scoring pipeline's lessons), decimate to a runtime weight,
fit the winged-creature template (stages/rig/template.py) to the bounding
box, and skin with automatic (bone-heat) weights. If bone heat fails its
coverage / wingtip checks, fall back to deterministic distance-to-bone
weights and say so in the report.

Usage:
  blender -b --python rig_blender.py -- --input textured.glb \
      --output rigged.glb --blend rigged.blend --report rig-report.json \
      --template winged-creature --ears 0 --arms 1 --target-verts 50000
"""

import argparse
import json
import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from template import build_template  # noqa: E402


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:]
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--blend")
    p.add_argument("--report", required=True)
    p.add_argument("--template", default="winged-creature")
    p.add_argument("--ears", type=int, default=0)
    p.add_argument("--arms", type=int, default=1)
    p.add_argument("--target-verts", type=int, default=50000)
    return p.parse_args(argv)


def world_bbox(obj):
    pts = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    xs = [p.x for p in pts]
    ys = [p.y for p in pts]
    zs = [p.z for p in pts]
    return (min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs))


def clean_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_mesh(path):
    clean_scene()
    if path.lower().endswith(".glb") or path.lower().endswith(".gltf"):
        bpy.ops.import_scene.gltf(filepath=path)
    elif path.lower().endswith(".obj"):
        bpy.ops.wm.obj_import(filepath=path)
    else:
        raise ValueError(f"unsupported mesh format: {path}")
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not meshes:
        raise RuntimeError("no mesh objects after import")
    bpy.ops.object.select_all(action="DESELECT")
    for m in meshes:
        m.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    return bpy.context.view_layer.objects.active


def canonicalize(obj):
    """Bake importer axis conversion, scale to height 2.0, center, ground."""
    bpy.context.view_layer.objects.active = obj
    (x0, x1), (y0, y1), (z0, z1) = world_bbox(obj)
    s = 2.0 / (z1 - z0)
    obj.scale = (s, s, s)
    bpy.ops.object.transform_apply(location=False, rotation=True,
                                   scale=True)
    (x0, x1), (y0, y1), (z0, z1) = world_bbox(obj)
    obj.location.x -= (x0 + x1) / 2
    obj.location.y -= (y0 + y1) / 2
    obj.location.z -= z0
    bpy.ops.object.transform_apply(location=True, rotation=False,
                                   scale=False)


def weld(obj, threshold=0.0005):
    """Merge split duplicate verts (the paint stage emits many), which
    otherwise defeat both decimation ratios and bone-heat weighting."""
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    try:
        bpy.ops.mesh.merge_by_distance(distance=threshold)
    except AttributeError:  # Blender <= 4.4 name
        bpy.ops.mesh.remove_doubles(threshold=threshold)
    bpy.ops.object.mode_set(mode="OBJECT")


def decimate(obj, target_verts):
    """Iterate the decimate modifier toward a VERTEX target — a single
    ratio pass tracks face count, which undershoots badly on meshes
    whose vert:face ratio is not the usual ~1:2."""
    start = len(obj.data.vertices)
    verts = start
    passes = 0
    while verts > target_verts and passes < 5:
        mod = obj.modifiers.new("decimate", "DECIMATE")
        mod.ratio = max(0.05, min(0.9, target_verts / verts))
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=mod.name)
        verts = len(obj.data.vertices)
        passes += 1
    return start, verts


def build_armature(bones, dims):
    (x0, x1), (y0, y1), (z0, z1) = dims
    w, d, h = x1 - x0, y1 - y0, z1 - z0

    def place(frac):
        fx, fy, fz = frac
        return Vector((fx * w, fy * d, fz * h))

    arm_data = bpy.data.armatures.new("Armature")
    arm = bpy.data.objects.new("Armature", arm_data)
    bpy.context.scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    roll_targets = {
        "vertical": Vector((0, -1, 0)),
        "horizontal": Vector((0, 0, 1)),
        "tail": Vector((0, 0, 1)),
    }
    for spec in bones:
        eb = arm_data.edit_bones.new(spec.name)
        eb.head = place(spec.head)
        eb.tail = place(spec.tail)
        eb.align_roll(roll_targets[spec.roll])
        if spec.parent:
            eb.parent = arm_data.edit_bones[spec.parent]
        eb.use_connect = False
    bpy.ops.object.mode_set(mode="OBJECT")
    return arm


def weight_coverage(obj, bone_names):
    """Fraction of verts with meaningful weight + per-bone vert counts."""
    import numpy as np
    n = len(obj.data.vertices)
    totals = np.zeros(n, dtype=np.float64)
    per_bone = {}
    group_index = {g.name: g.index for g in obj.vertex_groups}
    vert_groups = [[] for _ in range(n)]
    for v in obj.data.vertices:
        for g in v.groups:
            vert_groups[v.index].append((g.group, g.weight))
    for name in bone_names:
        gi = group_index.get(name)
        count = 0
        if gi is not None:
            for v in obj.data.vertices:
                for gidx, wgt in vert_groups[v.index]:
                    if gidx == gi and wgt > 0.01:
                        count += 1
                        break
        per_bone[name] = count
    for v in obj.data.vertices:
        totals[v.index] = sum(w for _, w in vert_groups[v.index])
    covered = int((totals > 0.05).sum())
    return covered / n, per_bone


def dominant_check(obj, dims, bone_names):
    """Wingtip spot-check: verts beyond 75% of half-width AND above 45%
    of the height (the tail curls wide but stays low, so altitude is
    what separates wingtips from tail) should be dominated by the same
    side's wing bones."""
    (x0, x1), _, (z0, z1) = dims
    half = (x1 - x0) / 2
    z_floor = z0 + 0.45 * (z1 - z0)
    ok = total = 0
    for v in obj.data.vertices:
        x = v.co.x
        if abs(x) < 0.75 * half or v.co.z < z_floor:
            continue
        total += 1
        if not v.groups:
            continue
        top = max(v.groups, key=lambda g: g.weight)
        name = obj.vertex_groups[top.group].name
        want = ("wing.L", "wing2.L") if x > 0 else ("wing.R", "wing2.R")
        if name in want:
            ok += 1
    return (ok / total if total else 0.0), total


def distance_weights(obj, arm, bones, dims):
    """Deterministic fallback: inverse-square falloff to bone segments."""
    import numpy as np
    (x0, x1), (y0, y1), (z0, z1) = dims
    w, d, h = x1 - x0, y1 - y0, z1 - z0
    verts = np.empty(len(obj.data.vertices) * 3)
    obj.data.vertices.foreach_get("co", verts)
    verts = verts.reshape(-1, 3)
    heads, tails = [], []
    for spec in bones:
        heads.append([spec.head[0] * w, spec.head[1] * d,
                      spec.head[2] * h])
        tails.append([spec.tail[0] * w, spec.tail[1] * d,
                      spec.tail[2] * h])
    heads = np.array(heads)
    tails = np.array(tails)
    seg = tails - heads
    seg_len2 = (seg ** 2).sum(axis=1)
    weights = np.zeros((len(verts), len(bones)))
    for i in range(len(bones)):
        t = np.clip(((verts - heads[i]) * seg[i]).sum(axis=1)
                    / max(seg_len2[i], 1e-9), 0, 1)
        closest = heads[i] + t[:, None] * seg[i]
        dist = np.linalg.norm(verts - closest, axis=1)
        weights[:, i] = 1.0 / (dist + 0.03) ** 2
    # Keep the 4 strongest influences per vertex, then normalize.
    for v in range(len(verts)):
        top = np.argsort(weights[v])[::-1][:4]
        mask = np.zeros(len(bones))
        mask[top] = 1
        weights[v] *= mask
        total = weights[v].sum()
        if total > 0:
            weights[v] /= total
    for gi in list(obj.vertex_groups):
        obj.vertex_groups.remove(gi)
    for i, spec in enumerate(bones):
        group = obj.vertex_groups.new(name=spec.name)
        idx = np.nonzero(weights[:, i] > 0.001)[0]
        for vi in idx:
            group.add([int(vi)], float(weights[vi, i]), "REPLACE")
    if not any(m.type == "ARMATURE" for m in obj.modifiers):
        mod = obj.modifiers.new("Armature", "ARMATURE")
        mod.object = arm


def main():
    args = parse_args()
    obj = import_mesh(args.input)
    raw_verts, raw_faces = len(obj.data.vertices), len(obj.data.polygons)
    canonicalize(obj)
    weld(obj)
    welded_verts = len(obj.data.vertices)
    pre_verts, post_verts = decimate(obj, args.target_verts)
    dims = world_bbox(obj)

    bones = build_template(args.template, ears=bool(args.ears),
                           arms=bool(args.arms))
    bone_names = [b.name for b in bones]
    arm = build_armature(bones, dims)

    # Bone-heat skinning first.
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    method = "bone-heat (automatic weights)"
    try:
        bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    except RuntimeError:
        method = "failed"
    coverage, per_bone = (0.0, {})
    wing_frac, wing_total = 0.0, 0
    heat_checks = None
    if method != "failed":
        coverage, per_bone = weight_coverage(obj, bone_names)
        wing_frac, wing_total = dominant_check(obj, dims, bone_names)
        heat_checks = {"coverage": round(coverage, 4),
                       "wingtip_dominance": round(wing_frac, 4)}
    if coverage < 0.98 or wing_frac < 0.5:
        distance_weights(obj, arm, bones, dims)
        method = "distance-to-bone fallback (bone heat failed checks)"
        coverage, per_bone = weight_coverage(obj, bone_names)
        wing_frac, wing_total = dominant_check(obj, dims, bone_names)
        if not any(m.type == "ARMATURE" and m.object == arm
                   for m in obj.modifiers):
            mod = obj.modifiers.new("Armature", "ARMATURE")
            mod.object = arm
        obj.parent = arm

    report = {
        "stage": "rig",
        "input": args.input,
        "raw_verts": raw_verts,
        "raw_faces": raw_faces,
        "welded_verts": welded_verts,
        "pre_decimation_verts": pre_verts,
        "rigged_verts": post_verts,
        "rigged_faces": len(obj.data.polygons),
        "template": args.template,
        "options": {"ears": bool(args.ears), "arms": bool(args.arms)},
        "bones": bone_names,
        "weight_method": method,
        "bone_heat_checks": heat_checks,
        "weight_coverage": round(coverage, 4),
        "per_bone_weighted_verts": per_bone,
        "wingtip_dominance": round(wing_frac, 4),
        "wingtip_verts_checked": wing_total,
        "bbox_dims": [round(dims[0][1] - dims[0][0], 3),
                      round(dims[1][1] - dims[1][0], 3),
                      round(dims[2][1] - dims[2][0], 3)],
    }
    if args.blend:
        bpy.ops.wm.save_as_mainfile(filepath=args.blend)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(filepath=args.output, export_format="GLB",
                              export_animations=False)
    with open(args.report, "w") as fh:
        json.dump(report, fh, indent=1)
    print("RIG_JSON " + json.dumps(report))
    print("RIG_OK")


if __name__ == "__main__":
    main()
