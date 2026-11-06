"""Catalog-stage verification (Blender headless): re-import a finished
GLB cold and prove what it contains — armature bones, populated vertex
groups, named animation actions — then render preview frames (rest pose
+ the hop apex) as deformation evidence.

Usage:
  blender -b --python render_verify.py -- --input final.glb \
      --rest-png rest.png --action-png hop.png --report verify.json
"""

import argparse
import json
import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "animate"))
import poses as pose_mod  # noqa: E402


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:]
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--rest-png", required=True)
    p.add_argument("--action-png", required=True)
    p.add_argument("--report", required=True)
    p.add_argument("--action", default="hop")
    return p.parse_args(argv)


def setup_render():
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 32
    scene.cycles.use_denoising = False
    scene.render.resolution_x = 512
    scene.render.resolution_y = 512
    scene.render.film_transparent = False
    world = bpy.data.worlds.new("W")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.05, 0.05, 0.06, 1)
    bg.inputs[1].default_value = 1.0
    cam_data = bpy.data.cameras.new("cam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 2.5
    cam = bpy.data.objects.new("cam", cam_data)
    scene.collection.objects.link(cam)
    cam.location = (2.6, -2.6, 1.7)
    direction = Vector((0, 0, 0.95)) - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam
    sun_data = bpy.data.lights.new("sun", "SUN")
    sun_data.energy = 3.0
    sun = bpy.data.objects.new("sun", sun_data)
    sun.rotation_euler = (math.radians(50), 0, math.radians(-35))
    scene.collection.objects.link(sun)
    return scene


def ground_z(mesh):
    """Ground clearance of the EVALUATED (posed) mesh — reading
    mesh.data directly would always report the rest pose."""
    import numpy as np
    deps = bpy.context.evaluated_depsgraph_get()
    ev = mesh.evaluated_get(deps)
    coords = np.empty(len(ev.data.vertices) * 3)
    ev.data.vertices.foreach_get("co", coords)
    world = np.array(ev.matrix_world)
    zs = coords.reshape(-1, 3) @ world[:3, :3].T + world[:3, 3]
    return float(zs[::37, 2].min())


def main():
    args = parse_args()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=args.input)
    scene = setup_render()
    arm = next((o for o in scene.objects if o.type == "ARMATURE"), None)
    mesh = next((o for o in scene.objects if o.type == "MESH"), None)
    if arm is None or mesh is None:
        raise RuntimeError("GLB lacks an armature or a mesh")

    bones = [b.name for b in arm.data.bones]
    weighted = 0
    for v in mesh.data.vertices:
        if any(g.weight > 0.01 for g in v.groups):
            weighted += 1
    coverage = weighted / max(len(mesh.data.vertices), 1)
    actions = sorted(a.name for a in bpy.data.actions)

    # Rest-pose render (no action assigned).
    scene.frame_set(1)
    rest_ground = ground_z(mesh)
    scene.render.filepath = args.rest_png
    bpy.ops.render.render(write_still=True)

    # Action render at the recipe's apex frame. Blender's glTF importer
    # renames imported actions to "<clip>_<armature>", so resolve by
    # exact name first, then by prefix.
    samples = pose_mod.sample(args.action, fps=24)
    apex_frame = max(samples, key=lambda s: s[1]["root_y"])[0]
    action = bpy.data.actions.get(args.action)
    if action is None:
        action = next((a for a in bpy.data.actions
                       if a.name.startswith(args.action + "_")), None)
    report = {
        "input": args.input,
        "verts": len(mesh.data.vertices),
        "faces": len(mesh.data.polygons),
        "bones": bones,
        "vertex_groups": len(mesh.vertex_groups),
        "weight_coverage": round(coverage, 4),
        "actions": actions,
        "rest_ground_z": round(rest_ground, 3),
    }
    if action is not None:
        arm.animation_data_create()
        arm.animation_data.action = action
        scene.frame_set(apex_frame)
        bpy.context.view_layer.update()
        report["action_frame"] = apex_frame
        report["action_ground_z"] = round(ground_z(mesh), 3)
        scene.render.filepath = args.action_png
        bpy.ops.render.render(write_still=True)
    with open(args.report, "w") as fh:
        json.dump(report, fh, indent=1)
    print("VERIFY_JSON " + json.dumps(report))
    print("VERIFY_OK")


if __name__ == "__main__":
    main()
