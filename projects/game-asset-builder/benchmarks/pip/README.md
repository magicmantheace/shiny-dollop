# Benchmark — Pip

- `input-idle.png` — the fixed benchmark input: the 1240×1240 RGBA cutout
  of Pip (royal-purple drabbit, wings spread) that the owner fed to Meshy
  to produce the reference mesh. Every local candidate gets this exact
  file. Do not regenerate or re-cut it; comparability depends on it.
- **Reference (not in git):** the owner's Meshy output — OBJ + 2048px
  texture, 1.12M verts / 2.25M faces ("Amethyst Dreamwing"). The owner
  keeps the master file; the scoring pipeline renders it through the same
  camera set as the candidates.
- Scores land in `scores.md` in this folder after each bake-off round:
  per-view silhouette IoU, raw vert/face counts, wall time, peak VRAM per
  stage, and the RIGGABLE / ROUGH / MELTED verdict (protocol:
  `docs/DESIGN.md`).
