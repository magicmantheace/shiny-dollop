"""Rig stage (Blender headless): textured GLB -> rigged GLB + .blend.

Canonicalize (bake importer transforms, scale to height 2.0, center XY,
ground Z — the scoring pipeline's lessons), decimate to a runtime weight,
then repair the geometry (stages/rig geometry cleanup: duplicate and
degenerate faces, debris shells, over-connected edges, holes) — Hunyuan
output arrives as triangle soup whose residual non-manifold edges make
Blender's bone-heat solver fail outright ("failed to find solution",
zero weights). Fit the winged-creature template
(stages/rig/template.py) to the bounding box and snap any bone endpoint
that lands outside the mesh volume onto the nearest surface point,
pulled slightly inward — bbox fractions cannot know where a generated
model folded its wings, and heat weighting gives outside bones nothing.
Skin with automatic (bone-heat) weights, then restrain them with the
weight-distance veto (stages/rig/skin_policy.py): heat diffuses
through a fused mass, so an appendage bone can come to own most of
the torso and drag it when it swings — the Snow Goblin's ruff was
51% arm-weighted and its wave smeared the chest fur. Any non-trunk
bone's weight on a vertex farther than its reach radius (a fraction
of bone length, floored by a fraction of mesh height) is zeroed and
renormalized onto the survivors; the root->head trunk chain is
exempt (its flesh IS the body mass). The acceptance policy in
skin_policy.py then decides whether the result ships, including a
guard-zone share check that fails a rig whose torso is still
appendage-owned. A handful of verts the heat field never reaches are
rescued with distance weights (counted in the report); only a
rejected heat result falls back to full distance-to-bone weights,
and the report says which method produced the shipped weights and
why.

Usage:
  blender -b --python rig_blender.py -- --input textured.glb \
      --output rigged.glb --blend rigged.blend --report rig-report.json \
      --template winged-creature --ears 0 --arms 1 --target-verts 50000

``--template`` selects the armature template (winged-creature,
quadruped, biped — stages/rig/template.py); the skinning stack
(cleanup -> snap -> bone heat -> skin_policy) and the report shape are
the same for all of them, with the policy's tip check and the zone
checks chosen per template. ``--rotate-z`` turns the canonicalized
mesh about Z before fitting: generated meshes do not guarantee the
character faces -Y, and the honest fix is a recorded per-run rotation
(chosen from renders of the raw mesh), not a template that pretends.
"""

import argparse
import json
import math
import os
import sys
from collections import Counter

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from template import build_template, trunk_chain  # noqa: E402
from skin_policy import (  # noqa: E402
    apply_veto, assess_heat, assess_zone_share)


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
    p.add_argument("--rotate-z", type=int, default=0,
                   choices=(0, 90, 180, 270),
                   help="rotate the canonicalized mesh about Z so the "
                        "character faces -Y before fitting the template")
    p.add_argument("--veto-factor", type=float, default=0.85,
                   help="weight-distance veto: a non-trunk bone's reach "
                        "radius is this factor times its length, floored "
                        "by --veto-floor times the mesh height "
                        "(calibrated on the Snow Goblin, see "
                        "skin_policy.py)")
    p.add_argument("--veto-floor", type=float, default=0.19,
                   help="weight-distance veto radius floor, as a "
                        "fraction of mesh height")
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


def rotate_z(obj, degrees):
    """Rotate about the world Z axis through the origin (the mesh is
    XY-centered and grounded after canonicalize, so this is a pure
    facing change), baking the rotation into the vertices.

    Applied through matrix_world, NOT rotation_euler: glTF imports
    arrive in QUATERNION rotation mode, where euler writes are
    silently ignored (the bake-off scorer's lesson, relearned here —
    the first quadruped run's rotate-z was a no-op for exactly this
    reason)."""
    if not degrees:
        return
    from mathutils import Matrix
    obj.matrix_world = Matrix.Rotation(
        math.radians(degrees), 4, "Z") @ obj.matrix_world
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=False, rotation=True,
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


def _nonmanifold_edges(bm):
    return sum(1 for e in bm.edges if len(e.link_faces) != 2)


def _shells(bm):
    """Connected components (by edge adjacency) as lists of bmesh verts."""
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for e in bm.edges:
        a, b = e.verts[0].index, e.verts[1].index
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    comps = {}
    for v in bm.verts:
        comps.setdefault(find(v.index), []).append(v)
    return list(comps.values())


def cleanup_geometry(obj):
    """Repair the decimated mesh toward a closed 2-manifold, which is
    what bone-heat weighting requires. Measured on Hunyuan output: the
    soup weld leaves a few dozen non-manifold edges (exact duplicate
    faces, faces shared by >2 neighbours, boundary holes) plus small
    debris shells of interior floaters. Returns a stats dict; the
    caller reports whatever residual remains rather than hiding it."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.edges.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    stats = {"nonmanifold_edges_before": _nonmanifold_edges(bm)}

    degen = [f for f in bm.faces if f.calc_area() < 1e-9]
    bmesh.ops.delete(bm, geom=degen, context="FACES")
    stats["degenerate_faces_deleted"] = len(degen)

    seen, dups = {}, []
    for f in bm.faces:
        key = tuple(sorted(v.index for v in f.verts))
        if key in seen:
            dups.append(f)
        else:
            seen[key] = f
    bmesh.ops.delete(bm, geom=dups, context="FACES")
    stats["duplicate_faces_deleted"] = len(dups)

    comps = _shells(bm)
    largest = max((len(c) for c in comps), default=0)
    drop = [v for c in comps if len(c) < 0.005 * largest for v in c]
    bmesh.ops.delete(bm, geom=drop, context="VERTS")
    stats["shells_before"] = len(comps)
    stats["debris_verts_deleted"] = len(drop)

    extras = []
    for e in bm.edges:
        if len(e.link_faces) > 2:
            faces = sorted(e.link_faces, key=lambda f: -f.calc_area())
            extras.extend(faces[2:])
    extras = list({f.index: f for f in extras}.values())
    bmesh.ops.delete(bm, geom=extras, context="FACES")
    stats["overconnected_extra_faces_deleted"] = len(extras)

    filled = 0
    for _ in range(2):  # second pass catches holes exposed by deletions
        boundary = [e for e in bm.edges if len(e.link_faces) == 1]
        if not boundary:
            break
        res = bmesh.ops.holes_fill(bm, edges=boundary, sides=0)
        filled += len(res["faces"])
        loose = [v for v in bm.verts if not v.link_faces]
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
    stats["holes_filled_faces"] = filled
    stats["nonmanifold_edges_after"] = _nonmanifold_edges(bm)
    stats["nonmanifold_verts_after"] = sum(1 for v in bm.verts
                                           if not v.is_manifold)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return stats


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


def _point_inside(tree, p):
    """Ray-parity inside test, stepping through BVH hits along -X and
    counting crossings strictly before the point (deduplicated)."""
    origin = Vector((p.x + 10.0, p.y, p.z))
    direction = Vector((-1, 0, 0))
    crossings = 0
    last = None
    o = origin
    for _ in range(128):
        loc, *_ = tree.ray_cast(o, direction)
        if loc is None or loc.x < p.x:
            break
        if last is None or (loc - last).length > 1e-3:
            crossings += 1
            last = loc
        o = loc + direction * 1e-3
    return crossings % 2 == 1


def snap_bone_endpoints(arm, obj):
    """Pull armature endpoints that sit OUTSIDE the mesh volume to the
    nearest surface point, nudged inward along the surface normal (an
    endpoint whose bone floats in air gets no heat weights at all).
    Returns {bone.endpoint: action} for the report."""
    dg = bpy.context.evaluated_depsgraph_get()
    tree = BVHTree.FromObject(obj, dg)
    (_, _), (_, _), (z0, z1) = world_bbox(obj)
    h = z1 - z0
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    actions = {}
    for eb in arm.data.edit_bones:
        for label in ("head", "tail"):
            p = getattr(eb, label).copy()
            key = f"{eb.name}.{label}"
            if _point_inside(tree, p):
                actions[key] = "inside (kept)"
                continue
            other = eb.tail if label == "head" else eb.head
            loc, normal, *_ = tree.find_nearest(p)
            placed = None
            if loc is not None:
                for delta in (0.01 * h, 0.004 * h, 0.001 * h):
                    cand = loc - normal * delta
                    if _point_inside(tree, cand):
                        placed = (cand, "snapped to surface "
                                  f"(-{delta:.3f} along normal)")
                        break
            if placed is None:
                for t in (0.25, 0.5, 0.75):
                    cand = p.lerp(other, t)
                    if _point_inside(tree, cand):
                        placed = (cand, f"pulled {t:.0%} toward other end")
                        break
            if placed is not None:
                setattr(eb, label, placed[0])
                actions[key] = placed[1]
            else:
                actions[key] = "FAILED to place inside"
    bpy.ops.object.mode_set(mode="OBJECT")
    return actions


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


def _zone_defs(template, dims):
    """Per-template evidence zones: (predicate, wanted bone names).
    Zones are bbox-relative, so a model whose anatomy departs from the
    template's assumptions may legitimately score low — the numbers
    are evidence; only the tip check (tip_dominance) gates."""
    (x0, x1), (y0, y1), (z0, z1) = dims
    w, d, h = x1 - x0, y1 - y0, z1 - z0
    if template == "quadruped":
        return {
            "head": (lambda x, y, z: y < y0 + 0.20 * d
                     and z > z0 + 0.40 * h, ("neck", "head")),
            "tail": (lambda x, y, z: y > y0 + 0.78 * d,
                     ("tail.1", "tail.2")),
        }
    if template == "biped":
        return {
            # No centre-strip constraint, unlike the winged head zone:
            # a biped's ears sit at the silhouette edge but are head
            # appendages, so the zone spans the full width and counts
            # the ear bones as head bones. (First measured on the Snow
            # Goblin: the strip version read 0.24 while the actual
            # skull zone was ~87% head/ear-driven.)
            "head": (lambda x, y, z: z > z0 + 0.62 * h,
                     ("head", "ear.L", "ear.R")),
            "feet": (lambda x, y, z: z < z0 + 0.10 * h,
                     ("leg.L", "leg2.L", "leg.R", "leg2.R")),
        }
    return {
        "head": (lambda x, y, z: z > z0 + 0.62 * h and abs(x) < 0.30 * w,
                 ("head",)),
        "tail": (lambda x, y, z: y > y0 + 0.72 * d and z < z0 + 0.45 * h,
                 ("tail.1", "tail.2", "tail.3")),
    }


def zone_dominance(obj, dims, template="winged-creature"):
    """Zone dominance checks, same idea as the wingtip check: verts in
    a zone should be driven by that zone's own bones."""
    out = {}
    for zone, (test, want) in _zone_defs(template, dims).items():
        ok = total = 0
        for v in obj.data.vertices:
            if not test(v.co.x, v.co.y, v.co.z):
                continue
            total += 1
            if not v.groups:
                continue
            top = max(v.groups, key=lambda g: g.weight)
            if obj.vertex_groups[top.group].name in want:
                ok += 1
        out[zone] = (round(ok / total, 4) if total else 0.0, total)
    return out


def _dominance_where(obj, test, want_for):
    """Share of verts passing ``test`` whose dominant group is in
    ``want_for(vertex)``. Returns (fraction, verts_checked)."""
    ok = total = 0
    for v in obj.data.vertices:
        if not test(v.co.x, v.co.y, v.co.z):
            continue
        total += 1
        if not v.groups:
            continue
        top = max(v.groups, key=lambda g: g.weight)
        if obj.vertex_groups[top.group].name in want_for(v.co.x):
            ok += 1
    return (ok / total if total else 0.0), total


def tip_dominance(obj, dims, template="winged-creature"):
    """The skin_policy gate check, per template: the extremity the
    template most often loses to the body mass.
    - winged-creature: wingtips (see dominant_check)
    - quadruped: the feet — lowest 10% of verts should belong to the
      leg bones, not the belly/spine
    - biped: the hands — verts outboard and below shoulder height
      should belong to that side's arm bones, not the torso
    Returns (fraction, verts_checked, label)."""
    (x0, x1), (y0, y1), (z0, z1) = dims
    w, d, h = x1 - x0, y1 - y0, z1 - z0
    if template == "quadruped":
        legs = ("leg.FL", "leg2.FL", "leg.FR", "leg2.FR",
                "leg.HL", "leg2.HL", "leg.HR", "leg2.HR")
        frac, total = _dominance_where(
            obj, lambda x, y, z: z < z0 + 0.10 * h, lambda x: legs)
        return frac, total, "feet"
    if template == "biped":
        frac, total = _dominance_where(
            obj,
            lambda x, y, z: abs(x) > 0.30 * w and z < z0 + 0.55 * h,
            lambda x: ("arm.L", "arm2.L") if x > 0
            else ("arm.R", "arm2.R"))
        return frac, total, "hands"
    frac, total = dominant_check(obj, dims,
                                 [g.name for g in obj.vertex_groups])
    return frac, total, "wingtip"


def weight_metrics(obj, bone_names):
    """Blend-quality metrics for whatever weights the mesh carries:
    how many verts are genuinely blended (strongest influence between
    0.05 and 0.95), multi-influence share, mean influences per vert,
    weight-sum error, unweighted share, and per-bone vert counts.
    Note the distance fallback scores HIGH on blended share by
    construction (it smears every bone everywhere) — the zone
    dominance checks are the correctness evidence; these numbers are
    the blend-shape evidence. Both are reported."""
    import numpy as np
    n = len(obj.data.vertices)
    sums = np.zeros(n)
    maxw = np.zeros(n)
    ngroups = np.zeros(n, dtype=int)
    per_bone = Counter()
    for v in obj.data.vertices:
        for g in v.groups:
            sums[v.index] += g.weight
            maxw[v.index] = max(maxw[v.index], g.weight)
            if g.weight > 0.05:
                ngroups[v.index] += 1
            if g.weight > 0.01:
                per_bone[obj.vertex_groups[g.group].name] += 1
    weighted = sums > 0.001
    return {
        "unweighted_pct": round(float((~weighted).mean() * 100), 3),
        "blended_pct": round(
            float((((maxw > 0.05) & (maxw < 0.95)).sum()) / n * 100), 2),
        "multi_influence_pct": round(float((ngroups >= 2).mean() * 100), 2),
        "mean_groups_per_vert": round(float(ngroups.mean()), 3),
        "sum_err_mean": round(
            float(np.abs(sums[weighted] - 1.0).mean()), 5)
        if weighted.any() else None,
        "per_bone_verts": {b: int(per_bone.get(b, 0)) for b in bone_names},
    }


def _segment_projection(heads, tails, verts):
    """(verts x bones) raw projection parameter along each bone
    segment: 0 at the head, 1 at the tail, outside [0, 1] beyond the
    endpoints (skin_policy's rescue eligibility uses exactly that)."""
    import numpy as np
    heads = np.asarray(heads, dtype=np.float64)
    tails = np.asarray(tails, dtype=np.float64)
    seg = tails - heads
    seg_len2 = (seg ** 2).sum(axis=1)
    t = np.zeros((len(verts), len(heads)))
    for i in range(len(heads)):
        t[:, i] = ((verts - heads[i]) * seg[i]).sum(axis=1) \
            / max(seg_len2[i], 1e-9)
    return t


def _segment_distances(heads, tails, verts):
    """(verts x bones) distance from each vertex to each bone segment."""
    import numpy as np
    heads = np.asarray(heads, dtype=np.float64)
    tails = np.asarray(tails, dtype=np.float64)
    seg = tails - heads
    t = np.clip(_segment_projection(heads, tails, verts), 0, 1)
    closest = heads[None, :, :] + t[:, :, None] * seg[None, :, :]
    return np.linalg.norm(verts[:, None, :] - closest, axis=2)


def _distance_matrix(heads, tails, verts):
    import numpy as np
    dist = _segment_distances(heads, tails, verts)
    weights = 1.0 / (dist + 0.03) ** 2
    for v in range(len(verts)):
        top = np.argsort(weights[v])[::-1][:4]
        mask = np.zeros(len(heads))
        mask[top] = 1
        weights[v] *= mask
        total = weights[v].sum()
        if total > 0:
            weights[v] /= total
    return weights


def _bone_endpoints(arm):
    """Current (post-snap) bone names + head/tail positions in armature
    space, in armature order — weight matrices are built and applied in
    this order so columns can never drift from group names."""
    names, heads, tails = [], [], []
    for bone in arm.data.bones:
        names.append(bone.name)
        heads.append(tuple(bone.head_local))
        tails.append(tuple(bone.tail_local))
    return names, heads, tails


def apply_weight_matrix(obj, arm, bone_names, weights, only_verts=None):
    """Write a (verts x bones) matrix into vertex groups. With
    ``only_verts`` set, existing groups are kept and just those verts
    are (re)assigned — the heat-rescue path."""
    import numpy as np
    if only_verts is None:
        for gi in list(obj.vertex_groups):
            obj.vertex_groups.remove(gi)
        targets = range(len(obj.data.vertices))
    else:
        targets = list(only_verts)
        target_set = set(targets)
        for v in obj.data.vertices:
            if v.index in target_set:
                for g in list(v.groups):
                    obj.vertex_groups[g.group].remove([v.index])
    groups = {}
    for i, name in enumerate(bone_names):
        groups[name] = obj.vertex_groups.get(name) or \
            obj.vertex_groups.new(name=name)
    for vi in targets:
        for i, name in enumerate(bone_names):
            if weights[vi, i] > 0.001:
                groups[name].add([int(vi)], float(weights[vi, i]),
                                 "REPLACE")
    if not any(m.type == "ARMATURE" for m in obj.modifiers):
        mod = obj.modifiers.new("Armature", "ARMATURE")
        mod.object = arm


def distance_weights(obj, arm, bones, dims):
    """Deterministic fallback: inverse-square falloff to bone segments
    (uses the armature's current — possibly snapped — endpoints)."""
    import numpy as np
    verts = np.empty(len(obj.data.vertices) * 3)
    obj.data.vertices.foreach_get("co", verts)
    verts = verts.reshape(-1, 3)
    names, heads, tails = _bone_endpoints(arm)
    weights = _distance_matrix(heads, tails, verts)
    apply_weight_matrix(obj, arm, names, weights)


def _weight_matrix(obj, bone_names):
    """Current vertex-group influences as an (n_verts x n_bones)
    numpy matrix, columns in ``bone_names`` order."""
    import numpy as np
    col = {name: i for i, name in enumerate(bone_names)}
    weights = np.zeros((len(obj.data.vertices), len(bone_names)))
    for v in obj.data.vertices:
        for g in v.groups:
            name = obj.vertex_groups[g.group].name
            if name in col:
                weights[v.index, col[name]] = g.weight
    return weights


def apply_distance_veto(obj, arm, bones, dims, factor, floor_frac):
    """Restrain the heat weights in place with skin_policy's veto.

    Reach radius per bone = max(factor * bone length, floor_frac *
    mesh height), applied to every bone outside the root->head trunk
    chain. Writes the vetoed matrix back through apply_weight_matrix
    and returns the stats for the rig report (radii included, so a
    future run can see exactly what reach each bone was allowed)."""
    import numpy as np
    names, heads, tails = _bone_endpoints(arm)
    lengths = [float(np.linalg.norm(np.array(t) - np.array(hd)))
               for hd, t in zip(heads, tails)]
    (_, _), (_, _), (z0, z1) = dims
    height = z1 - z0
    radii = [max(factor * length, floor_frac * height)
             for length in lengths]
    trunk = trunk_chain(bones)
    veto_cols = [i for i, name in enumerate(names) if name not in trunk]
    verts = np.empty(len(obj.data.vertices) * 3)
    obj.data.vertices.foreach_get("co", verts)
    verts = verts.reshape(-1, 3)
    distances = _segment_distances(heads, tails, verts)
    projection = _segment_projection(heads, tails, verts)
    beyond_end = (projection < 0.0) | (projection > 1.0)
    weights = _weight_matrix(obj, names)
    new_weights, stats = apply_veto(
        weights.tolist(), distances.tolist(), radii, veto_cols,
        beyond_end=beyond_end.tolist())
    apply_weight_matrix(obj, arm, names, np.array(new_weights))
    return {
        "factor": factor,
        "floor_frac": floor_frac,
        "trunk_bones": [n for n in names if n in trunk],
        "vetoed_bones": [names[i] for i in veto_cols],
        "radius_by_bone": {n: round(r, 4)
                           for n, r in zip(names, radii)},
        "vetoed_entries": stats["vetoed_entries"],
        "verts_touched": stats["verts_touched"],
        "rescued_verts": len(stats["rescued_verts"]),
    }


def _share_zone_defs(template, dims):
    """Guard zones for the zone-share gate: (predicate, appendage
    group, group label) per zone — body mass whose weight must NOT
    sit on the appendages that swing past it. Bbox-relative like the
    dominance zones; the biped torso band sits below the head zone
    and inboard of the hands zone."""
    (x0, x1), (y0, y1), (z0, z1) = dims
    w, d, h = x1 - x0, y1 - y0, z1 - z0
    if template == "quadruped":
        legs = ("leg.FL", "leg2.FL", "leg.FR", "leg2.FR",
                "leg.HL", "leg2.HL", "leg.HR", "leg2.HR")
        return {
            "belly": (lambda x, y, z: z0 + 0.10 * h <= z <= z0 + 0.40 * h
                      and abs(x) < 0.25 * w, legs, "leg"),
        }
    if template == "biped":
        return {
            "torso": (lambda x, y, z: z0 + 0.30 * h <= z <= z0 + 0.62 * h
                      and abs(x) < 0.30 * w,
                      ("arm.L", "arm2.L", "arm.R", "arm2.R"), "arm"),
        }
    return {
        "torso": (lambda x, y, z: z0 + 0.30 * h <= z <= z0 + 0.62 * h
                  and abs(x) < 0.30 * w,
                  ("wing.L", "wing2.L", "wing.R", "wing2.R",
                   "arm.L", "arm.R"), "wing/arm"),
    }


def zone_weight_share(obj, dims, template="winged-creature"):
    """Per guard zone: the share of the zone's total vertex weight
    held by the zone's appendage group, as (share, verts_checked).
    This is the number the Snow Goblin's ruff failed before the veto:
    0.51 of its torso weight sat on the arm bones."""
    out = {}
    for zone, (test, group, _label) in \
            _share_zone_defs(template, dims).items():
        group_idx = {g.index for g in obj.vertex_groups
                     if g.name in group}
        held = total = 0.0
        count = 0
        for v in obj.data.vertices:
            if not test(v.co.x, v.co.y, v.co.z):
                continue
            count += 1
            for g in v.groups:
                total += g.weight
                if g.group in group_idx:
                    held += g.weight
        out[zone] = (round(held / total, 4) if total else 0.0, count)
    return out


def main():
    args = parse_args()
    obj = import_mesh(args.input)
    raw_verts, raw_faces = len(obj.data.vertices), len(obj.data.polygons)
    canonicalize(obj)
    rotate_z(obj, args.rotate_z)
    weld(obj)
    welded_verts = len(obj.data.vertices)
    pre_verts, post_verts = decimate(obj, args.target_verts)
    cleanup = cleanup_geometry(obj)
    dims = world_bbox(obj)

    bones = build_template(args.template, ears=bool(args.ears),
                           arms=bool(args.arms))
    bone_names = [b.name for b in bones]
    arm = build_armature(bones, dims)
    snap = snap_bone_endpoints(arm, obj)
    snap_failed = [k for k, v in snap.items() if v.startswith("FAILED")]

    # Bone-heat skinning.
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    heat_error = None
    try:
        bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    except RuntimeError as exc:
        heat_error = str(exc)

    method = None
    heat_checks = None
    veto_stats = None
    shares = {}
    rescue_filled = 0
    coverage, per_bone = 0.0, {}
    tip_frac, tip_total, tip_label = 0.0, 0, "wingtip"
    if heat_error is None and obj.vertex_groups:
        # Heat fields leave small per-vert sum residuals; normalize so
        # shipped influences sum to 1.
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.vertex_group_normalize_all(
            group_select_mode="ALL", lock_active=False)
        # Distance veto: heat owns too much of the body through fused
        # masses; restrain appendage bones to their reach BEFORE the
        # policy measures anything, so the gate judges what ships.
        veto_stats = apply_distance_veto(
            obj, arm, bones, dims, args.veto_factor, args.veto_floor)
        rescue_filled = veto_stats["rescued_verts"]
        # Rescue: any vert still carrying no meaningful weight (the
        # veto's nearest-bone rescue normally covers these) gets
        # distance weights — ONLY those verts are (re)assigned.
        import numpy as np
        sums = np.zeros(len(obj.data.vertices))
        for v in obj.data.vertices:
            sums[v.index] = sum(g.weight for g in v.groups)
        bare = np.nonzero(sums < 0.05)[0]
        if len(bare):
            verts = np.empty(len(obj.data.vertices) * 3)
            obj.data.vertices.foreach_get("co", verts)
            names, heads, tails = _bone_endpoints(arm)
            matrix = _distance_matrix(heads, tails,
                                      verts.reshape(-1, 3))
            apply_weight_matrix(obj, arm, names, matrix,
                                only_verts=[int(i) for i in bare])
            rescue_filled += int(len(bare))
        coverage, per_bone = weight_coverage(obj, bone_names)
        tip_frac, tip_total, tip_label = tip_dominance(
            obj, dims, args.template)
        zones = zone_dominance(obj, dims, args.template)
        shares = zone_weight_share(obj, dims, args.template)
        share_defs = _share_zone_defs(args.template, dims)
        heat_checks = {"coverage": round(coverage, 4),
                       f"{tip_label}_dominance": round(tip_frac, 4)}
        for zone_name, (zone_frac, _n) in zones.items():
            heat_checks[f"{zone_name}_dominance"] = zone_frac
        for zone_name, (share, _n) in shares.items():
            heat_checks[f"{zone_name}_"
                        f"{share_defs[zone_name][2]}_share"] = share
        accepted, reasons = assess_heat(coverage, per_bone, bone_names,
                                        tip_frac, tip_label=tip_label)
        for zone_name, (share, _n) in shares.items():
            reasons += assess_zone_share(
                share, zone_label=zone_name,
                group_label=share_defs[zone_name][2])
        if accepted and not reasons:
            method = ("bone-heat (automatic weights); distance veto "
                      f"(factor {args.veto_factor}, "
                      f"floor {args.veto_floor})")
            if rescue_filled:
                method += f"; distance rescue on {rescue_filled} verts"
        else:
            heat_checks["rejected_because"] = reasons
    elif heat_error is not None:
        heat_checks = {"operator_error": heat_error}
    if method is None:
        distance_weights(obj, arm, bones, dims)
        why = heat_error or "heat result rejected by skin_policy"
        method = f"distance-to-bone fallback ({why})"
        coverage, per_bone = weight_coverage(obj, bone_names)
        tip_frac, tip_total, tip_label = tip_dominance(
            obj, dims, args.template)
        if not any(m.type == "ARMATURE" and m.object == arm
                   for m in obj.modifiers):
            mod = obj.modifiers.new("Armature", "ARMATURE")
            mod.object = arm
        obj.parent = arm
    metrics = weight_metrics(obj, bone_names)
    zones = zone_dominance(obj, dims, args.template)
    shares = zone_weight_share(obj, dims, args.template)

    report = {
        "stage": "rig",
        "input": args.input,
        "raw_verts": raw_verts,
        "raw_faces": raw_faces,
        "welded_verts": welded_verts,
        "pre_decimation_verts": pre_verts,
        "rigged_verts": len(obj.data.vertices),
        "rigged_faces": len(obj.data.polygons),
        "template": args.template,
        "options": {"ears": bool(args.ears), "arms": bool(args.arms)},
        "bones": bone_names,
        "geometry_cleanup": cleanup,
        "bone_snap": {
            "kept_inside": sum(1 for v in snap.values()
                               if v == "inside (kept)"),
            "snapped": sum(1 for v in snap.values()
                           if v.startswith(("snapped", "pulled"))),
            "failed": snap_failed,
            "actions": snap,
        },
        "weight_method": method,
        "bone_heat_checks": heat_checks,
        "weight_veto": veto_stats,
        "rescue_filled_verts": rescue_filled,
        "weight_metrics": metrics,
        "zone_dominance": zones,
        "zone_weight_share": shares,
        "weight_coverage": round(coverage, 4),
        "per_bone_weighted_verts": per_bone,
        "tip_label": tip_label,
        "tip_dominance": round(tip_frac, 4),
        "tip_verts_checked": tip_total,
        "rotate_z": args.rotate_z,
        "bbox_dims": [round(dims[0][1] - dims[0][0], 3),
                      round(dims[1][1] - dims[1][0], 3),
                      round(dims[2][1] - dims[2][0], 3)],
    }
    if args.template == "winged-creature":
        # P0 report keys, kept for the winged template's comparability.
        report["wingtip_dominance"] = report["tip_dominance"]
        report["wingtip_verts_checked"] = report["tip_verts_checked"]
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
