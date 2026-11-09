"""Read animation clip names + durations from a GLB (stdlib only).

Parses the GLB container directly: the JSON chunk names the
animations and their samplers; each sampler's input accessor holds
the keyframe times, whose maximum is the clip duration. Accessor
``max`` is used when the exporter wrote it; otherwise the float32
times are decoded from the BIN chunk.
"""

import json
import struct

_JSON_CHUNK = 0x4E4F534A
_BIN_CHUNK = 0x004E4942


def read_glb_animations(path: str) -> dict[str, float]:
    """{clip name: duration in seconds} for a .glb file."""
    with open(path, "rb") as fh:
        data = fh.read()
    if data[:4] != b"glTF":
        raise ValueError(f"{path}: not a GLB file")
    offset = 12
    gltf = None
    bin_chunk = b""
    while offset < len(data):
        (length, ctype) = struct.unpack_from("<II", data, offset)
        chunk = data[offset + 8: offset + 8 + length]
        if ctype == _JSON_CHUNK:
            gltf = json.loads(chunk)
        elif ctype == _BIN_CHUNK:
            bin_chunk = chunk
        offset += 8 + length
    if gltf is None:
        raise ValueError(f"{path}: GLB has no JSON chunk")

    accessors = gltf.get("accessors", [])
    buffer_views = gltf.get("bufferViews", [])

    def accessor_max(idx: int) -> float:
        acc = accessors[idx]
        if acc.get("max"):
            return float(acc["max"][0])
        view = buffer_views[acc["bufferView"]]
        start = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
        count = acc["count"]
        values = struct.unpack_from(f"<{count}f", bin_chunk, start)
        return max(values)

    clips = {}
    for anim in gltf.get("animations", []):
        duration = 0.0
        for sampler in anim.get("samplers", []):
            duration = max(duration, accessor_max(sampler["input"]))
        clips[anim.get("name", "")] = duration
    return clips
