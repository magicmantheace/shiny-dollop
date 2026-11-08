"""Prop stage (Blender headless): textured GLB -> clean static GLB.

The unrigged path for props (P1): canonicalize (bake importer
transforms, scale to height 2.0, center XY, ground Z — the same
normalization rigged assets get, so the catalog shares one scale
convention), weld, decimate to a prop-appropriate weight, and run the
rig stage's geometry cleanup so debris shells and duplicate faces do
not ship. No armature is created and no animation is exported; the
report states ``rigged: False`` plainly so nothing downstream can
mistake the asset for a rigged one.

Usage:
  blender -b --python prop_blender.py -- --input textured.glb \
      --output prop.glb --report prop-report.json --target-verts 30000
"""

import argparse
import json
import os
import sys

import bpy

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "rig"))
import rig_blender as rig  # noqa: E402


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:]
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--report", required=True)
    p.add_argument("--target-verts", type=int, default=30000)
    return p.parse_args(argv)


def main():
    args = parse_args()
    obj = rig.import_mesh(args.input)
    raw_verts, raw_faces = len(obj.data.vertices), len(obj.data.polygons)
    rig.canonicalize(obj)
    rig.weld(obj)
    welded_verts = len(obj.data.vertices)
    pre_verts, post_verts = rig.decimate(obj, args.target_verts)
    cleanup = rig.cleanup_geometry(obj)
    dims = rig.world_bbox(obj)

    report = {
        "stage": "prop",
        "input": args.input,
        "rigged": False,
        "raw_verts": raw_verts,
        "raw_faces": raw_faces,
        "welded_verts": welded_verts,
        "pre_decimation_verts": pre_verts,
        "prop_verts": post_verts,
        "prop_faces": len(obj.data.polygons),
        "target_verts": args.target_verts,
        "geometry_cleanup": cleanup,
        "weight_method": None,
        "bbox_dims": [round(dims[0][1] - dims[0][0], 3),
                      round(dims[1][1] - dims[1][0], 3),
                      round(dims[2][1] - dims[2][0], 3)],
    }
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(filepath=args.output, export_format="GLB",
                              export_animations=False)
    with open(args.report, "w") as fh:
        json.dump(report, fh, indent=1)
    print("PROP_JSON " + json.dumps(report))
    print("PROP_OK")


if __name__ == "__main__":
    main()
