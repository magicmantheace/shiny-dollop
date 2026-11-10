"""Restore truthful provenance for an environment-pack asset after the
--resume finish overwrote the run-1 manifest with placeholders and the
catalog claimed Hunyuan paint. Mirrors the pine-tree correction pattern.
Usage: fix_provenance.py <slug> <mesh_stage_json> <runner_json> <input_desc>
"""
import json, os, sys
slug, mesh_f, runner_f, input_desc = sys.argv[1:5]
base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
mesh_stage = json.load(open(mesh_f))
runner = json.load(open(runner_f))
tex = {
    "method": "procedural-vertex-color",
    "tool": "Blender paint_env.py (generalized pack painter), run by Nyx 2026-11-10",
    "input_mesh": input_desc,
    "reason": ("Hunyuan3D paint stalls inside its VAE encode on this machine "
               "(data-independent; investigation 2026-11-10, fix deferred at the "
               "owner's direction). Per the owner's 2026-11-10 directive the "
               "environment pack is painted procedurally; this is NOT Hunyuan "
               "paint output."),
}
mpath = f"{base}/outputs/{slug}/run-manifest.json"
m = json.load(open(mpath))
m["stages"]["mesh"] = {"runner": runner, "stage": mesh_stage,
                       "note": "restored 2026-11-10 from lab stage result + log after --resume overwrote run 1"}
m["stages"]["texture"] = tex
json.dump(m, open(mpath, "w"), indent=1)

cpath = f"{base}/catalog/{slug}/metadata.json"
c = json.load(open(cpath))
c["provenance"]["texture_model"] = ("procedural vertex-color (Blender) — "
    "Hunyuan3D paint not used for this asset (see texture_stage)")
c["provenance"]["mesh_stage"] = mesh_stage
c["provenance"]["texture_stage"] = tex
json.dump(c, open(cpath, "w"), indent=1)
print("provenance fixed for", slug)
