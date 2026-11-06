"""Animate stage (Blender headless): rigged GLB -> GLB with baked clips.

Bakes the procedural recipes from stages/animate/poses.py (ported from
Drabbit Pet's pose driver) as named actions on the armature: bone
rotations from the recipe channels, root lift on the root bone. All
bones take the recipe's signed pitch as-is — with the template's roll
alignment, the .R bones' flipped local axes cancel the geometric
mirror, so one sign sweeps both wings up (proven in the Pip hop test).

The root bone points +Z (its local Y is world-up), so lift is applied on
the root's local Y — but rather than trusting that, the stage probes it:
it poses the hop apex, measures the evaluated mesh's ground clearance,
and falls back to local Z if Y shows no lift. The probe result is in the
report.

Usage:
  blender -b --python animate_blender.py -- --input rigged.glb \
      --output final.glb --report animate-report.json
"""

import argparse
import json
import os
import sys

import bpy

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
import poses as pose_mod  # noqa: E402

FPS = 24


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:]
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--report", required=True)
    return p.parse_args(argv)


def ground_clearance(arm, mesh):
    import numpy as np
    deps = bpy.context.evaluated_depsgraph_get()
    ev = mesh.evaluated_get(deps)
    coords = np.empty(len(ev.data.vertices) * 3)
    ev.data.vertices.foreach_get("co", coords)
    world = np.array(ev.matrix_world)
    zs = coords.reshape(-1, 3) @ world[:3, :3].T + world[:3, 3]
    return float(zs[::37, 2].min())


def set_pose(arm, pose, lift_axis):
    """Apply one recipe pose dict to the armature's pose bones."""
    pb = arm.pose.bones

    def rot(name, x=None, z=None):
        bone = pb.get(name)
        if bone is None:
            return
        if x is not None:
            bone.rotation_euler.x = x
        if z is not None:
            bone.rotation_euler.z = z

    root = pb.get("root")
    if root is not None:
        if lift_axis == "y":
            root.location.y = pose["root_y"]
        else:
            root.location.z = pose["root_y"]
    # NOTE: no sign mirroring for .R bones. With the template's roll
    # alignment, opposite wings' local X axes point opposite ways in
    # world space, which exactly cancels the geometric mirror — the
    # same signed pitch sweeps both wings up. (Verified empirically:
    # a mirrored .R pitch folded the right wing down in the hop test.)
    rot("head", x=pose["head_pitch"])
    rot("ear.L", x=pose["ear_pitch"])
    rot("ear.R", x=pose["ear_pitch"])
    rot("wing.L", x=pose["wing_pitch"])
    rot("wing.R", x=pose["wing_pitch"])
    rot("wing2.L", x=pose["wing2_pitch"])
    rot("wing2.R", x=pose["wing2_pitch"])
    rot("arm.L", x=pose["arm_pitch"])
    rot("arm.R", x=pose["arm_pitch"])
    for i, name in enumerate(("tail.1", "tail.2", "tail.3")):
        rot(name, z=pose["tail_yaw"] * (1.0, 0.6, 0.35)[i])


def key_pose(arm, frame):
    for bone in arm.pose.bones:
        bone.keyframe_insert("rotation_euler", frame=frame)
    root = arm.pose.bones.get("root")
    if root is not None:
        root.keyframe_insert("location", frame=frame)


def reset_pose(arm):
    for bone in arm.pose.bones:
        bone.rotation_euler = (0, 0, 0)
        bone.location = (0, 0, 0)
    bpy.context.view_layer.update()


def probe_lift_axis(arm, mesh):
    """Determine which root-bone local axis produces world-up lift."""
    apex = pose_mod.pose_hop(0.31)  # near the hop apex (arch ~ 1)
    base = ground_clearance(arm, mesh)
    for axis in ("y", "z"):
        reset_pose(arm)
        set_pose(arm, apex, axis)
        bpy.context.view_layer.update()
        lift = ground_clearance(arm, mesh) - base
        if lift > 0.08:
            reset_pose(arm)
            return axis, round(lift, 3)
    reset_pose(arm)
    return None, 0.0


def main():
    args = parse_args()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=args.input)
    scene = bpy.context.scene
    scene.render.fps = FPS
    arm = next(o for o in scene.objects if o.type == "ARMATURE")
    mesh = next(o for o in scene.objects if o.type == "MESH")
    for bone in arm.pose.bones:
        bone.rotation_mode = "XYZ"

    lift_axis, probe_lift = probe_lift_axis(arm, mesh)
    if lift_axis is None:
        raise RuntimeError("root-lift probe failed on both local axes")

    arm.animation_data_create()
    baked = {}
    for name in pose_mod.RECIPES:
        samples = pose_mod.sample(name, fps=FPS)
        action = bpy.data.actions.new(name)
        arm.animation_data.action = action
        reset_pose(arm)
        for frame, pose in samples:
            scene.frame_set(frame)
            set_pose(arm, pose, lift_axis)
            key_pose(arm, frame)
        action.use_fake_user = True
        # Stash into an NLA track so the glTF exporter ships every clip.
        track = arm.animation_data.nla_tracks.new()
        track.name = name
        track.strips.new(name, 1, action)
        baked[name] = {"frames": len(samples), "fps": FPS,
                       "seconds": round(len(samples) / FPS, 2)}
    reset_pose(arm)
    scene.frame_set(1)

    bpy.ops.export_scene.gltf(
        filepath=args.output, export_format="GLB",
        export_animations=True, export_animation_mode="ACTIONS")
    report = {
        "stage": "animate",
        "input": args.input,
        "output": args.output,
        "lift_axis": lift_axis,
        "probe_lift_at_apex": probe_lift,
        "actions": baked,
    }
    with open(args.report, "w") as fh:
        json.dump(report, fh, indent=1)
    print("ANIMATE_JSON " + json.dumps(report))
    print("ANIMATE_OK")


if __name__ == "__main__":
    main()
