# Pip bake-off — scores

## Round 1 — 2026-11-06

Input (fixed): `input-idle.png`. Reference: the owner's Meshy Pip
(1,123,359 verts / 2,246,850 faces, 2048px texture), rendered through the
same scorer as the candidates. GPU stages ran on the owner's PC (RTX 3060,
12,288 MiB VRAM, 9,210 MiB free at rest); meshes were fetched back to the
build VM and their counts/hashes re-verified before scoring. Scoring ran
on the VM (Blender 4.2 headless, Cycles CPU — EEVEE has no EGL headless
here). Scorer: `score_render.py` + `iou_sheet.py` in this folder;
raw numbers in `scores.json`.

| Candidate | Mesh (verts / faces) | Texture | Wall time | Peak VRAM | IoU front | IoU side | IoU back | IoU ¾ | IoU mean | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| **Hunyuan3D-2 shape + paint** (two processes, unloaded between) | 830,136 / 1,052,668 | UV + 2048×2048 image | shape 305 s, paint 1,520 s | shape 8,762 MiB, paint 12,086 MiB | **0.84** | 0.27 | 0.84 | 0.43 | 0.59 | **RIGGABLE** |
| TRELLIS-image-large (fallback export) | 354,576 / 709,092 | vertex colors only | 176 s | 12,020 MiB | 0.55 | 0.24 | 0.55 | 0.31 | 0.41 | **MELTED** (as delivered) |
| TripoSR | 81,284 / 162,468 | vertex colors only | 39 s | 6,100 MiB | 0.49 | 0.44 | 0.49 | 0.39 | 0.45 | **MELTED** |
| Stable Fast 3D | — | — | — | — | — | — | — | — | — | **BLOCKED** |

### Verdicts

- **Hunyuan3D-2 (shape → paint, the designed split pair) — RIGGABLE, the
  round-1 winner.** Front IoU 0.84 clears the 0.75 bar, and the visual
  sheet agrees: ears, horns, wings with swirl detail, face, collar gem,
  and curled scaled tail are all present and cleanly separated — the only
  candidate that is recognizably Pip from every angle. Known divergence:
  the side profile (IoU 0.27) — its wings angle outward and the tail
  curls tighter than the reference's, whose profile is unusually slim.
  Operational notes: paint peaked at 12,086 MiB — only ~200 MiB of
  headroom on this card — and its ~21-minute texturing phase is
  CPU-bound (mesh prep / xatlas on the 1.05M-face shape) at 1–11% GPU
  utilisation; it looks hung but finishes. VRAM was released after each
  stage, as the unload discipline requires.
- **TRELLIS — MELTED as delivered.** Inference itself succeeded (176 s,
  no OOM), but the proper textured GLB export needs
  `diff_gaussian_rasterization`, whose CUDA build failed on this machine
  (CUB errors, CUDA 12.4 vs torch build flags). The fallback vertex-color
  export is an amorphous sideways blob. Its 0.55 front IoU is a
  blob-coverage artifact — a large shapeless mass overlaps much of the
  reference outline — and per the protocol the visual sheet overrules
  the number. Revisit only if the rasterizer ever builds here.
- **TripoSR — MELTED.** Fast (39 s) and light (6.1 GB), but the GPU run
  reproduces the CPU spike's failure: a ruffled, melted heap with
  wing-like fragments — no clean silhouette, no UVs, its texture bake
  crashed (device mismatch). Stays as the speed baseline only.
- **Stable Fast 3D — BLOCKED before the GPU.** Its Hugging Face repo is
  gated; unblocking needs the owner to accept Stability's licence there
  and supply an HF token. Not chased.

### Method notes (read before reusing these numbers)

- Canonicalisation trusts the importer's up axis and normalises by Z
  height. A longest-axis-to-Z rule was tried and rejected: Pip's
  wingspan exceeds his height, so it tipped the reference onto one
  wingtip.
- Yaw is orbited by the camera, never by rotating the object: glTF
  imports can sit in quaternion rotation mode, where writing
  `rotation_euler` silently does nothing (caught when two GLB
  candidates rendered identically at every yaw).
- Front IoU always equals back IoU — that is geometry, not a bug: an
  orthographic silhouette from directly behind is the exact mirror of
  the front silhouette, and IoU is mirror-invariant when both masks
  flip. The discriminating views are front, side, and three-quarter.
- The importer's axis conversion must be baked into the vertices before
  any transform work; the first scoring pass rendered the reference
  lying on its back for exactly this reason and was discarded.

### Next

Build the P0 pipeline around the Hunyuan3D-2 pair (prep → shape →
paint → rig → animate → catalog) and prove it end-to-end on a second
creature that isn't Pip.
