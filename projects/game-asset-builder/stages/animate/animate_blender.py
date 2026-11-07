"""Animate stage (Blender headless): rigged GLB -> GLB with baked clips.

Bakes the procedural recipes from stages/animate/poses.py as named
actions on the armature. Recipes speak in abstract channels
(``head_pitch``, ``leg.FL``, ``arm_wave``...); the per-template DRIVERS
table below maps each channel onto (bone, local axis, scale). Axes and
signs were determined by probing the template armatures (build the
armature with no mesh, pose +0.5 rad on each axis, measure where the
bone tail travels):

- winged-creature: the original P0 mapping. No sign mirroring for .R
  bones — with the template's roll alignment, opposite wings' local X
  axes point opposite ways in world space, which exactly cancels the
  geometric mirror, so one sign sweeps both wings up. (Verified
  empirically in P0: a mirrored .R pitch folded the right wing down.)
- quadruped: legs' +local X swings the foot forward on all four legs,
  so the bounce's tuck drivers are negative (legs trail and fold as
  the body lifts); the spine/neck/head +X raises the front end; the
  tail wags on local Z.
- biped: head +X bows forward (as winged); arm bones carry the
  "horizontal" roll, which makes +local X raise either hand up and
  outward symmetrically — the wave. With the "vertical" roll no
  single axis raises a hanging arm at all.

The root bone's lift axis is NOT assumed either: the stage probes it
with a synthetic pose (root_y = 0.19, everything else at rest),
measures the evaluated mesh's ground clearance, and falls back to the
other local axis if the first shows no lift. The probe result is in
the report.

Usage:
  blender -b --python animate_blender.py -- --input rigged.glb \
      --output final.glb --report animate-report.json \
      [--template quadruped]
"""

import argparse
import json
import os
import sys

import bpy

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
import poses as pose_mod  # noqa: E402

FPS = 24

# (bone, channel, local axis, scale) — applied additively, so two
# drivers may share a bone+axis (e.g. the biped's waving arm also
# receives the idle sway channel).
DRIVERS = {
    "winged-creature": [
        ("head", "head_pitch", "x", 1.0),
        ("ear.L", "ear_pitch", "x", 1.0),
        ("ear.R", "ear_pitch", "x", 1.0),
        ("wing.L", "wing_pitch", "x", 1.0),
        ("wing.R", "wing_pitch", "x", 1.0),
        ("wing2.L", "wing2_pitch", "x", 1.0),
        ("wing2.R", "wing2_pitch", "x", 1.0),
        ("arm.L", "arm_pitch", "x", 1.0),
        ("arm.R", "arm_pitch", "x", 1.0),
        ("tail.1", "tail_yaw", "z", 1.0),
        ("tail.2", "tail_yaw", "z", 0.6),
        ("tail.3", "tail_yaw", "z", 0.35),
    ],
    "quadruped": [
        ("root", "sway", "z", 1.0),
        ("spine", "spine_pitch", "x", 1.0),
        ("neck", "neck_pitch", "x", 1.0),
        ("head", "head_pitch", "x", 1.0),
        ("leg.FL", "leg.FL", "x", -1.0),
        ("leg.FR", "leg.FR", "x", -1.0),
        ("leg.HL", "leg.HL", "x", -1.0),
        ("leg.HR", "leg.HR", "x", -1.0),
        ("leg2.FL", "leg2.FL", "x", -1.0),
        ("leg2.FR", "leg2.FR", "x", -1.0),
        ("leg2.HL", "leg2.HL", "x", -1.0),
        ("leg2.HR", "leg2.HR", "x", -1.0),
        ("tail.1", "tail_yaw", "z", 1.0),
        ("tail.2", "tail_yaw", "z", 0.6),
    ],
    "biped": [
        ("root", "sway", "z", 1.0),
        ("head", "head_pitch", "x", 1.0),
        ("head", "head_tilt", "z", 1.0),
        ("ear.L", "ear_pitch", "x", 1.0),
        ("ear.R", "ear_pitch", "x", 1.0),
        ("arm.L", "arm_sway", "x", 1.0),
        ("arm.R", "arm_sway", "x", 1.0),
        ("arm2.L", "arm_sway", "x", 0.5),
        ("arm2.R", "arm_sway", "x", 0.5),
        ("arm.R", "arm_wave", "x", 1.0),
        ("arm2.R", "arm2_wave", "x", 1.0),
    ],
}


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:]
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--report", required=True)
    p.add_argument("--template", default="winged-creature")
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


def set_pose(arm, pose, lift_axis, template):
    """Apply one recipe pose dict to the armature's pose bones."""
    pb = arm.pose.bones
    totals = {}
    for bone_name, channel, axis, scale in DRIVERS[template]:
        if pb.get(bone_name) is None:
            continue  # template option off (e.g. no ears) — skip
        key = (bone_name, axis)
        totals[key] = totals.get(key, 0.0) + pose.get(channel, 0.0) * scale
    for (bone_name, axis), value in totals.items():
        bone = pb[bone_name]
        if axis == "x":
            bone.rotation_euler.x = value
        elif axis == "y":
            bone.rotation_euler.y = value
        else:
            bone.rotation_euler.z = value
    root = pb.get("root")
    if root is not None:
        if lift_axis == "y":
            root.location.y = pose.get("root_y", 0.0)
        else:
            root.location.z = pose.get("root_y", 0.0)


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


def probe_lift_axis(arm, mesh, template):
    """Determine which root-bone local axis produces world-up lift,
    using a synthetic pose (pure root_y) so the probe is independent
    of which clips the template bakes."""
    spec = pose_mod.template_spec(template)
    apex = dict(spec["rest"])
    apex["root_y"] = 0.19
    base = ground_clearance(arm, mesh)
    for axis in ("y", "z"):
        reset_pose(arm)
        set_pose(arm, apex, axis, template)
        bpy.context.view_layer.update()
        lift = ground_clearance(arm, mesh) - base
        if lift > 0.08:
            reset_pose(arm)
            return axis, round(lift, 3)
    reset_pose(arm)
    return None, 0.0


def main():
    args = parse_args()
    spec = pose_mod.template_spec(args.template)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=args.input)
    scene = bpy.context.scene
    scene.render.fps = FPS
    arm = next(o for o in scene.objects if o.type == "ARMATURE")
    mesh = next(o for o in scene.objects if o.type == "MESH")
    for bone in arm.pose.bones:
        bone.rotation_mode = "XYZ"

    lift_axis, probe_lift = probe_lift_axis(arm, mesh, args.template)
    if lift_axis is None:
        raise RuntimeError("root-lift probe failed on both local axes")

    arm.animation_data_create()
    baked = {}
    for name in spec["recipes"]:
        samples = pose_mod.sample_for(args.template, name, fps=FPS)
        action = bpy.data.actions.new(name)
        arm.animation_data.action = action
        reset_pose(arm)
        for frame, pose in samples:
            scene.frame_set(frame)
            set_pose(arm, pose, lift_axis, args.template)
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
        "template": args.template,
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
