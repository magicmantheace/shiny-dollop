# Layer 3 bake-off — 3D part segmentation (cleanup slice)

**Date:** 2026-11-06 · **Hardware:** Adam's PC (AthenZ971), RTX 3060, 12,288 MiB,
driver 610.62 · **Rule:** fully local after one-time weight downloads; one model
resident at a time; every run its own process (load → run → exit), VRAM release
verified by the lab `stage_runner.py` sampler after each run.

## Proof meshes and method

| Mesh | Source | Full size | Run input |
|---|---|---|---|
| snow-goblin (biped) | `outputs/snow-goblin/textured.glb` | 854,106 v / 1,072,406 f | decimated to 50,000 f |
| triceratops (quadruped) | `outputs/triceratops/textured.glb` | 513,882 v / 667,540 f | decimated to 50,000 f |

Both candidates were run on the **same decimated proxies** (Blender Decimate,
COLLAPSE; `~/workspace/gui-test-shots/assetforge/p2-seg/inputs/`). Reason: both
pipelines' CPU post-processing builds full face-adjacency structures over the
input mesh (P3-SAM's part-neighbour phase alone took 97 s at 50k faces), and
PartField's agglomerative clustering is per-face. The learned models themselves
sample a fixed 100,000 surface points regardless of face count, so the
segmentation *signal* is barely affected by decimation; labels are produced
**per face of the decimated mesh** and would be transferred to the full mesh by
nearest face centroid (see integration notes). The tests scored:

- **Goblin:** do the arms carry a different label from the chest/ruff, with the
  boundary near the shoulder/armpit (not mid-chest, not mid-arm)? This is the
  fused-fur case that motivated Layer 3.
- **Triceratops:** are the legs labeled separately from the belly? (Legs sharing
  one "leg" label is acceptable; four distinct legs is better.)

Verdicts: **CLEAN** = boundary where anatomy says · **ROUGH** = parts exist but
boundary wanders / cuts through a part / is inconsistent · **UNUSABLE** = blob
labels, whole-body single part, or crash. All verdicts are from rendered
evidence (Blender headless, Cycles CPU, front/back/side/three-quarter) plus a
per-label spatial breakdown (face-centroid positions per label) used to resolve
palette ambiguities.

## Results at a glance

| Candidate | Install | Goblin verdict | Trike verdict | Wall time | Peak VRAM | Licence |
|---|---|---|---|---|---|---|
| **P3-SAM** (Hunyuan3D-Part) | ✅ after era pins + 3 shims | **CLEAN** (9 parts) | **ROUGH** (5 parts) | 188 s goblin / 100 s trike, per mesh, all-in | 9,680 / 9,099 MiB | Tencent Community — commercial OK in Canada |
| **PartField** (nv-tlabs) | ✅ after era pins + 2 shims | **CLEAN** (10 parts @ L10) | **CLEAN** (10 parts @ L10) | 29 s features + 53 s clustering, *both* meshes | 7,677 MiB | NVIDIA — **non-commercial only** |
| SAMesh | not attempted | — | — | — | — | not verified |

Setup wall time (clone + venv + all installs + weights + smoke): P3-SAM
384.7 s in one staged run; PartField 433.8 s (its stage stopped at the last
step on a missing `huggingface_hub` in my deps list; the fix and the era pins
took ~4 more minutes of short jobs). GPU baseline at rest was 774–912 MiB
across the session (desktop apps); every run returned to baseline after exit.

---

## 1. P3-SAM — Tencent Hunyuan3D-Part

Repo `Tencent-Hunyuan/Hunyuan3D-Part` @ `e96be06`, subfolder `P3-SAM`.
Weights: `tencent/Hunyuan3D-Part` → `p3sam/p3sam.safetensors` (451 MB) plus the
Sonata backbone `facebook/sonata` → `sonata.pth` (434 MB); Sonata code is
vendored in the same repo under `XPart/partgen`. Native 3D point-promptable
segmentation: 100k sampled surface points (hardcoded), 400 FPS prompts, masks
voted onto input faces. Venv `venvs\p3sam`, Python 3.12.8, torch 2.4.0+cu121.

**Runs** (seed 42, `--parallel 0`, `post_process=0` = CLI default):

| Mesh | Exit | Wall | Peak VRAM | After exit | Parts |
|---|---|---|---|---|---|
| snow-goblin | 0 | 188.12 s | 9,680 MiB | 783 MiB | 9 labels |
| triceratops | 0 | 100.17 s | 9,099 MiB | 789 MiB | 5 labels |

Phase split (its own timers, goblin): Sonata features 4.8 s, mask inference at
prompt_bs 4 = 41.1 s, NMS/merge ≈ 2.8 s, **CPU part-neighbour post-process
97.2 s**; remainder ≈ 40 s is imports + weight load. Trike post-process: 33.4 s.

**Goblin — CLEAN.** Both arms carry labels different from the chest/ruff label
(5.8% and 5.7% of faces) and the boundary sits at the shoulder/armpit in the
front, side *and* back renders — the fused-fur test passes. Caveats: the head
is fused into the torso label (74.9% of faces in one label); one ear is its own
label; there is light single-face speckle inside the large labels; below the
waist it over-splits into five small labels (shorts / legs / feet — each one
anatomical, just finer than a rigger would choose).

**Triceratops — ROUGH.** Head+frill split cleanly at the neck (22.1%), and the
two *far-side* legs get their own labels (5.2% front, 4.2% hind) with
boundaries at plausible shoulder/hip lines — but both *near-side* legs stay
fused into the body/belly label (68.3%). Only 2 of 4 legs separate, so the
leg↔belly test half-passes: real parts, two good boundaries, but the split is
inconsistent across symmetric legs.

Renders: `~/workspace/gui-test-shots/assetforge/p2-seg/p3sam/snow-goblin/renders/p3sam_goblin_{front,back,side,threequarter}.png`,
`~/workspace/gui-test-shots/assetforge/p2-seg/p3sam/triceratops/renders/p3sam_trike_{front,back,side,threequarter}.png`
Labeled meshes: `~/workspace/gui-test-shots/assetforge/p2-seg/p3sam/<mesh>/auto_mask_mesh_final.glb` (+ `face_ids.npy`).

**Shims/workarounds (all in the lab copies on the PC, pipeline repo untouched):**

1. *Sonata flash-attention:* `XPart/partgen/models/sonata/model.py` — activated
   the authors' own commented-out `ckpt["config"]['enable_flash'] = False`
   line. No flash-attn Windows wheel exists; the SDPA fallback path ran fine.
2. *prompt_bs OOM + upstream bug:* stock `prompt_bs=32` OOMs on 12 GB (one
   `torch.cat` tried to allocate 9.26 GiB; peak 11,781 MiB). The CLI parses
   `--prompt_bs` but `__main__` **never forwards it** to `predict_aabb`, so the
   flag is a no-op upstream. Patched the lab copy's `predict_aabb` default
   32 → 4. Peak then 9,680 MiB.
3. *Era pins:* `numpy==1.26.4, scipy==1.13.1, scikit-learn==1.5.2,
   numba==0.60.0`. torch 2.4.0+cu121's Windows build cannot initialise its
   NumPy bridge against numpy ≥ 2.0.2 ("_ARRAY_API not found";
   `torch.from_numpy` raises). numpy 2.1.2 (XPart's pin) and 2.0.2 both fail;
   1.26.4 works.
4. *Encoding:* `PYTHONUTF8=1` — the demo's phase Timer prints Chinese text and
   crashed with `UnicodeEncodeError` under cp1252 on the first run.
   Also `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`.
5. *Sonata weight path:* `model.py` hardcodes `download_root='/root/sonata'`
   (drive-relative on Windows → `D:\root\sonata` in the lab). Pre-seeded
   `sonata.pth` there. P3-SAM weights were passed via explicit `--ckpt_path`
   because the built-in download path mis-joins `~` with an absolute-looking
   subpath on Windows.
6. `spconv-cu121`, `torch-scatter` (pyg wheel for pt24cu121) and `fpsample`
   all installed; fpsample source-built a win_amd64 wheel in 40 s (MSVC
   present on the PC). The `utils/chamfer3D` CUDA extension is **not** needed
   for `auto_mask.py` (only the unused `auto_mask_no_postprocess.py` imports
   it) and was not built.

**Licence:** Tencent Hunyuan 3D-Part Community License (repo `LICENSE`).
Territory = worldwide **excluding EU, UK, South Korea** — Canada is inside.
Royalty-free, commercial use permitted; a separate licence is needed only
above 1M monthly active users; Tencent claims no rights in Outputs; outputs
must not be used to improve another AI model. **Permits adoption for Adam's
use in Canada.**

## 2. PartField — nv-tlabs/PartField (ICCV 2025)

Repo `nv-tlabs/PartField` @ `373025d`. Weights: `mikaelaangel/partfield-ckpt`
→ `model_objaverse.ckpt` (1.24 GB; the PartNet-trained variant is withheld
upstream for licensing reasons). Feed-forward triplane feature field over
100k sampled points, then agglomerative clustering over per-face features
(`--option 1 --with_knn True`, the README's setting for AI-generated meshes).
Venv `venvs\partfield`, Python 3.12.8, torch 2.4.0+cu124. Upstream
`environment.yml` is a Linux conda dump (incl. RAPIDS) and was not used; a
Windows pip subset was installed instead.

**Runs** (two stages, each its own process):

| Stage | Exit | Wall | Peak VRAM | After exit |
|---|---|---|---|---|
| Feature extraction, both meshes | 0 | 28.76 s (7.7–9.2 s per mesh) | 7,677 MiB | 906 MiB |
| Agglomerative clustering, both meshes, all 20 levels | 0 | 52.67 s (CPU) | 950 MiB | 934 MiB |

Clustering exports a **hierarchy** (per-face label arrays for 1–20 clusters).
Scored at the **10-cluster level** for both meshes; 6- and 14-cluster arrays
were also fetched and counted.

**Goblin — CLEAN.** At 10 parts: left arm and right arm are separate labels
with boundaries at the shoulder in front, side and back renders; torso is a
different label (split front/back); the head is split further into crown vs
face, plus one ear label; legs/feet split below. The fused arm↔torso test
passes with more anatomical granularity than P3-SAM gave.

**Triceratops — CLEAN** (on the leg↔belly test). Per-label spatial breakdown
at 10 parts shows **four distinct leg labels at the four body corners** (up
ranges 0.00–0.43, 0.00–0.43, 0.00–0.29, 0.00–0.68), a **separate belly label**
(17.0%, centroid at up 0.26), head+frill separate, tail separate. That is the
rubric's "better" outcome. Caveats: the trunk is split into transverse bands
(front/mid/rear body labels instead of one torso — a hierarchy-level choice;
a pipeline would merge trunk bands or score a coarser level for the body),
and one leg label rides high (thigh/shoulder included, up-range to 0.68).

Renders: `~/workspace/gui-test-shots/assetforge/p2-seg/partfield/snow-goblin/renders10/partfield_snow-goblin_10_{front,back,side,threequarter}.png`,
`~/workspace/gui-test-shots/assetforge/p2-seg/partfield/triceratops/renders10/partfield_triceratops_10_{front,back,side,threequarter}.png`
Labeled data: `~/workspace/gui-test-shots/assetforge/p2-seg/partfield/<mesh>/`
(`labels_10.npy`, `colored_10.glb`, `input.ply`, plus levels 06/14).
⚠ PartField's own PLY face colors are dropped by Blender's PLY importer, so
the renders were rebuilt locally from `input.ply` + `labels_10.npy` with a
sequential tab20 palette. The `.npy` values are agglomerative **cluster node
ids** (e.g. 7544, 15356), not 0..K−1 — a naive `id % 20` palette collides
(two pairs in these very results, including one leg that first rendered the
same green as the head); always remap unique values first. Distinctness was
verified via the spatial breakdown above, not just the pictures.

**Shims/workarounds:**

1. *Lightning DDP on Windows:* upstream hardcodes
   `Trainer(devices=-1, strategy=DDPStrategy(...))`. Windows torch has no
   libuv (rendezvous fails) and no NCCL (backend fails, even with
   `USE_LIBUV=0`). Patched the lab copy to `devices=1, strategy="auto"`.
   `torch.distributed` is imported by the model trainer but never called on
   the predict path, so single-device inference is faithful.
2. *Era pins:* `numpy==1.26.4, scipy==1.13.1, scikit-learn==1.5.2` (same
   torch 2.4 NumPy-bridge issue as P3-SAM) and `matplotlib==3.8.4`
   (`plt.cm.get_cmap` was removed in matplotlib ≥ 3.9 and crashed PLY export
   *after* labels were computed). Note: installing the matplotlib pin pulled
   numpy back to 2.5.4 for the clustering process (resolver conflict warning;
   clustering is CPU-only and exited 0). Feature extraction ran under the
   era pins.
3. *Missing implicit deps* from the conda env: `huggingface_hub`, `pytz`
   installed separately. `mesh2sdf` source-built fine; `tetgen`, `pymeshlab`,
   `open3d`, `vtk` all have usable Windows wheels for cp312.
4. `dataset.val_num_workers 0` via `--opts` to keep the DataLoader in-process
   on Windows.

**Licence — the blocker.** Repo `LICENSE` is the NVIDIA License; §3.3:
*"The Work and any derivative works thereof only may be used or intended for
use non-commercially… for non-commercial research and educational purposes
only."* Running it here for research evaluation is permitted. **Adopting it
into the asset pipeline is not**, on any path where the assets or the work
around them could be commercial (products, client work) — which is the stated
direction of the self-employment plan. This is a licence rejection for
adoption, not a quality rejection.

## 3. SAMesh — not run (by the bake-off's own rule)

`gtangg12/samesh` (SAM2 multiview lifting) was designated *"only if 1 and 2
are quick fails; it is the heaviest pipeline."* Candidates 1 and 2 both
installed and produced scored segmentations on both meshes, so the condition
never triggered. On paper: zero-shot, needs a separately downloaded SAM2
checkpoint, upstream tested on Python 3.12 + CUDA 11.8 with a SAM2 source
build, no Windows evidence, and a much heavier render → SAM2 → mask-lifting
stack than either feed-forward candidate. Its licence was not audited since
it was not run. If a third opinion is ever wanted, budget it as its own slice.

**Also rejected on paper:** X-Part (the other half of Hunyuan3D-Part) — it is
a *generative part-completion* stage that consumes P3-SAM's segmentation, not
a segmenter; evaluating it belongs to a part-generation slice, not this one.

---

## Recommendation

**Adopt P3-SAM as the pipeline's segmentation stage. Do not adopt PartField,
despite it winning on raw quality and speed — its licence is
non-commercial-only.**

Why P3-SAM is adoptable and sufficient:

- **Licence-clean for Adam's actual use** (Canada, incl. commercial;
  < 1M MAU). PartField's §3.3 bars exactly the product/client direction this
  pipeline feeds. PartField remains legal as an offline research cross-check
  only — do not wire it into the pipeline or ship its outputs commercially.
- **It passes the test Layer 3 exists for.** The fused biped (goblin) arms
  split from the torso at the shoulder — CLEAN. The known weakness is
  quadruped legs (2 of 4 on the triceratops); if quadruped leg separation
  becomes load-bearing, revisit then (options: different seed/prompt draw,
  or a leg-region re-prompt using P3-SAM's interactive point-prompt mode,
  which the automatic pass doesn't use).
- **Integration is the simplest of the two:** one process per mesh, in =
  GLB/OBJ/PLY, out = per-face ids + a colorized GLB (below).

### Integration notes for the coordinator (P3-SAM)

- **Stage shape:** separate venv (`D:\asset-forge-lab\venvs\p3sam` already
  built), run `P3-SAM/demo/auto_mask.py` as its own process per mesh with
  cwd = the `demo` folder. Env: `HF_HOME=<lab>\hf`, `PYTHONUTF8=1`,
  `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`. Weights already in the
  lab: `D:\asset-forge-lab\seg\p3sam_weights\p3sam\p3sam.safetensors`
  (pass via `--ckpt_path`) and `D:\root\sonata\sonata.pth`.
- **Carry the shims with the integration** (they live only in the lab copy at
  `D:\asset-forge-lab\repos\Hunyuan3D-Part`): Sonata `enable_flash=False`;
  `predict_aabb` default `prompt_bs=4`; the era pins
  (numpy 1.26.4 / scipy 1.13.1 / scikit-learn 1.5.2 / numba 0.60.0 /
  torch 2.4.0+cu121 / spconv-cu121 / torch-scatter pt24cu121). Do not "fix"
  the `--prompt_bs` CLI flag upstream-style — it is parsed but never
  forwarded; set the default or call `AutoMask.predict_aabb(...,
  prompt_bs=4)` from a driver instead of the CLI.
- **Input:** feed a decimated proxy (≈50k faces worked; the model samples
  100k surface points internally either way). Keep the proxy's face list —
  outputs index *its* faces.
- **Output mapping (the part that matters):**
  `auto_mask_mesh_final_face_ids.npy` is an int64 array, **one label per face
  of the input (proxy) mesh, in that mesh's face order** (label −1 = no part).
  `auto_mask_mesh_final.glb/.ply` is the same mesh with per-face colors.
  Transfer to the full-resolution mesh by nearest **face centroid** (proxy →
  original), not by vertex — the proxy's vertices do not correspond to the
  original's. P3-SAM label values are sparse prompt-cluster ids (e.g. 23,
  243); remap unique values to 0..K−1.
- **Unload behaviour:** verified — the process exits after each mesh and
  VRAM returned to baseline both times (783 vs 774 baseline; 789 vs 795).
  Nothing stays resident.
- **Time budget per asset:** ~100–190 s at 50k faces, of which the CPU
  part-neighbour post-process is the largest single chunk (33–97 s). Peak
  VRAM 9.7 GB at prompt_bs 4 — fits the 12 GB card alongside nothing else;
  keep the one-model-at-a-time discipline.
- **Caveats to design around:** head fuses with torso on the goblin (if the
  rig stage needs a head split, that's a separate cut); expect light
  single-face speckle (a majority-vote pass over face adjacency cleans it);
  label count is automatic (9 and 5 here) with no target-part-count knob in
  the automatic path.

### If the licence situation ever changes

PartField is the better segmenter on this evidence (CLEAN/CLEAN, ~7× faster
end-to-end, 7.7 GB peak) and its integration shape is also documented in
`partfield_results.json` (two stages; labels per face of its re-exported
input PLY, same face order as the decimated input; hierarchy level is a
policy choice — 10 worked for both; remap cluster node ids). Re-check the
NVIDIA licence before any non-research use.

## Files

- Per-candidate machine-readable results: `p3sam_results.json`,
  `partfield_results.json`, `samesh_results.json` (this folder).
- PC lab artifacts: `D:\asset-forge-lab\seg\` (inputs, outputs, weights),
  logs in `D:\asset-forge-lab\logs\seg_*`, stage results in
  `D:\asset-forge-lab\out\seg_*_result.json`, venvs `venvs\p3sam` and
  `venvs\partfield`, repos `repos\Hunyuan3D-Part` and `repos\PartField`
  (lab copies carry the shims listed above).
- VM scratch (inputs, labeled meshes, renders, logs):
  `~/workspace/gui-test-shots/assetforge/p2-seg/`.
