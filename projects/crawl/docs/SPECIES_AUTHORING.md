# Species Authoring — 29A.1

## Human v1

`species.human` uses approximately twenty high-level correlated traits. Height
is distributed from 150–205 cm and body composition combines frame, muscle,
fat, proportions, and facial fullness rather than driving one slider.

## Dwarf v1

`species.dwarf` uses the same logical 53-bone humanoid hierarchy but authored
non-uniform proportions: 118–158 cm stature, shorter legs/arms, broad torso,
larger corrected head, distinct facial ranges, and stronger beard selection.
It is not a uniformly scaled Human.

Both species export Idle, Walk, Attack, Reaction, and Death semantic clips.
Renderer manifests include `stride_scale` and `foot_ik_offset_cm`; live actors
retain the existing `humanoid.standard` animation family. The current proof
uses authored MPFB skin weights and actor-level meter-to-centimeter conversion
because UE 5.8 Interchange preserved morph names but rendered the joined mesh as
rigid. The legacy FBX importer preserves skin deformation and morphs.

Body extremes inspected in Blender are Human average/short-heavy/tall-thin and
Dwarf average/heavy/alternate. Soft garments follow the skinned body. Proxy
helmet, breastplate, beard, and sword use deterministic attachment/fitting and
are intentionally low-detail proof art.
