"""Segment stage glue (runs on the VM, in-process for the pipeline).

Turns P3-SAM's per-face ids for the proxy mesh into the labels
file the rig stage consumes: the proxy's vertices/faces read from
its GLB and converted from glTF's Y-up storage back to the
Blender frame — (x, y, z)_blender = (x, -z, y)_gltf, the inverse
of Blender's exporter mapping; verified against the canonical
bbox (height 2.0 on Z, ground at 0) — plus the canonical
transform make_proxy recorded, plus the face ids remapped from
P3-SAM's sparse prompt-cluster values to 0..K-1 (-1, P3-SAM's
"no part", is preserved). The rig stage applies the transform to
the proxy's face centroids when it transfers labels onto its
canonical working mesh.

The GLB is read with a minimal stdlib+numpy reader instead of
trimesh: the file is this pipeline's own export (single primitive,
indexed), and face ORDER is load-bearing — P3-SAM indexed the
faces of its trimesh load of the same file, whose face order is
the GLB's index-buffer order. The reader validates that the id
count matches the face count and fails loudly otherwise, rather
than mislabelling a mesh.
"""

import json
import struct

import numpy as np


def _read_glb_mesh(path):
    with open(path, "rb") as fh:
        blob = fh.read()
    if blob[:4] != b"glTF":
        raise ValueError(f"not a GLB: {path}")
    jlen = struct.unpack("<I", blob[12:16])[0]
    gltf = json.loads(blob[20:20 + jlen])
    off = 20 + jlen
    blen = struct.unpack("<I", blob[off:off + 4])[0]
    binchunk = blob[off + 8:off + 8 + blen]

    def accessor(i):
        acc = gltf["accessors"][i]
        view = gltf["bufferViews"][acc["bufferView"]]
        start = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
        ncomp = {"SCALAR": 1, "VEC2": 2, "VEC3": 3,
                 "VEC4": 4}[acc["type"]]
        dt = {5126: np.float32, 5123: np.uint16,
              5125: np.uint32}[acc["componentType"]]
        arr = np.frombuffer(binchunk, dtype=dt,
                            count=acc["count"] * ncomp, offset=start)
        return arr.reshape(acc["count"], ncomp) if ncomp > 1 else arr

    prim = gltf["meshes"][0]["primitives"][0]
    verts = accessor(prim["attributes"]["POSITION"]).astype(np.float64)
    faces = accessor(prim["indices"]).reshape(-1, 3).astype(np.int64)
    return verts, faces


def write_labels_npz(proxy_glb, face_ids_path, out_path,
                     transform=None):
    """Build labels.npz {verts, faces, face_ids, transform}.

    ``verts`` are the proxy's vertices in the RAW Blender frame
    (glTF Y-up storage converted back); ``transform`` is the
    canonical transform make_proxy recorded (scale, offset,
    rotate_z) — the rig stage applies it to the face centroids
    when transferring labels into its canonical working frame.
    """
    verts, faces = _read_glb_mesh(proxy_glb)
    # glTF Y-up storage -> Blender frame.
    verts = np.stack([verts[:, 0], -verts[:, 2], verts[:, 1]], axis=1)
    raw = np.load(face_ids_path).astype(np.int64).reshape(-1)
    if len(raw) != len(faces):
        raise ValueError(
            f"face id count {len(raw)} != proxy face count "
            f"{len(faces)} — refusing to guess the alignment")
    uniq = sorted(int(u) for u in set(raw.tolist()) if u >= 0)
    remap = {u: i for i, u in enumerate(uniq)}
    ids = np.array([remap.get(int(v), -1) for v in raw],
                   dtype=np.int32)
    if transform is None:
        transform = {"scale": 1.0, "offset": [0.0, 0.0, 0.0],
                     "rotate_z": 0}
    np.savez(out_path,
             verts=verts.astype(np.float32),
             faces=faces,
             face_ids=ids,
             transform_scale=np.float64(transform["scale"]),
             transform_offset=np.array(transform["offset"],
                                       dtype=np.float64),
             transform_rotate_z=np.int64(transform["rotate_z"]))
    return {"parts": len(uniq),
            "proxy_verts": int(len(verts)),
            "proxy_faces": int(len(faces)),
            "unlabelled_faces": int((ids < 0).sum()),
            "raw_label_ids": uniq}
