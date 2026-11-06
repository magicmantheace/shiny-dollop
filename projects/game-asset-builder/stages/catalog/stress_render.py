"""Catalog-stage stress render (Blender headless): pose a finished GLB
far beyond its shipped clips and render the result — the deformation
evidence that weight metrics cannot give. One wing driven to full
raise (the hop recipe peaks at 0.65 rad; this uses 1.25), the head
turned hard, the tail curled hard, arms swept. Joint collapse,
tearing, or candy-wrapper twists show up here or nowhere.

Usage:
  blender -b --python stress_render.py -- --input final.glb \
      --threeq-png stress.png --front-png stress-front.png
"""

import argparse
import json
import math
import sys

import bpy
from mathutils import Vector


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:]
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--threeq-png", required=True)
    p.add_argument("--front-png")
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
    scene.camera = cam
    sun_data = bpy.data.lights.new("sun", "SUN")
    sun_data.energy = 3.0
    sun = bpy.data.objects.new("sun", sun_data)
    sun.rotation_euler = (math.radians(50), 0, math.radians(-35))
    scene.collection.objects.link(sun)
    return scene, cam


def point_cam(cam, pos, target=(0, 0, 0.95)):
    cam.location = pos
    direction = Vector(target) - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


# Bone -> (rotation_euler x, z). Deliberately beyond the shipped clips.
STRESS_POSE = {
    "wing.L": (1.25, 0.0),    # full raise (hop peaks at 0.65)
    "wing2.L": (0.60, 0.0),
    "wing.R": (0.0, 0.0),     # left at rest for contrast
    "head": (-0.30, 0.65),    # pitched + turned hard
    "arm.L": (-0.90, 0.0),
    "arm.R": (-0.90, 0.0),
    "tail.1": (0.0, 0.85),    # hard curl, accumulating down the chain
    "tail.2": (0.0, 0.55),
    "tail.3": (0.0, 0.35),
}


def main():
    args = parse_args()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=args.input)
    scene, cam = setup_render()
    arm = next(o for o in scene.objects if o.type == "ARMATURE")
    for bone in arm.pose.bones:
        bone.rotation_mode = "XYZ"
    applied = {}
    for name, (x, z) in STRESS_POSE.items():
        bone = arm.pose.bones.get(name)
        if bone is None:
            continue
        bone.rotation_euler.x = x
        bone.rotation_euler.z = z
        applied[name] = [x, z]
    bpy.context.view_layer.update()

    point_cam(cam, (2.6, -2.6, 1.7))
    scene.render.filepath = args.threeq_png
    bpy.ops.render.render(write_still=True)
    if args.front_png:
        point_cam(cam, (0, -4.2, 1.0))
        scene.render.filepath = args.front_png
        bpy.ops.render.render(write_still=True)
    print("STRESS_JSON " + json.dumps({"input": args.input,
                                       "pose_applied": applied}))
    print("STRESS_OK")


if __name__ == "__main__":
    main()
