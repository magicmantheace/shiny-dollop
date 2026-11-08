# Rig compatibility contract: studio_humanoid_v1

## Canonical space

Right-handed asset authoring; unit scale = meters; neutral rest pose consistent across parts; +Y vertical in Godot. Document forward orientation per importer, convert/verify on import. Never guess character height from mesh bounds alone.

## Required skeleton

Root/pelvis/spine/chest/neck/head, left/right clavicle-upperarm-lowerarm-hand, left/right thigh-calf-foot-toe. Recommended: wrist/ankle twist and fingers. Keep stable semantic names and a humanoid retarget map, not rigid identical bone lengths.

## Animation interoperability

- All stock humanoid clips target a normalized animation skeleton with rest-pose orientation maps.
- Movement in-place or with explicit root-motion tag; state whether clip moves root. Avoid double translation.
- Contacts marked by metadata: left/right foot ground, left/right hand prop anchor, seated hip anchor.
- Blend entry/exit pose, duration, loopability, emotion and required props.
- Upper-body overlays are masked separately from locomotion.
- Enforce maximum joint limits and foot locking with IK as needed.

## Faces

Prefer blendshapes: blink_l/r, brow_up/down, smile/frown, jaw_open, mouth_open/round/wide, lip_close, eyes_squint. Speech visemes must have a published mapping independent of the TTS model. Unknown visemes fall back to jaw intensity.

## Interaction sockets

`hand_r`, `hand_l`, `head`, `back`, `hip`. Socket axes and offsets documented per prop, not hardcoded into story commands. Rigs outside humanoid family carry a distinct rig_id and own animation mappings.

## Gates before promotion

Import success; valid skeleton and skin weights; coherent neutral pose; no missing source media; retarget 5 stock movements; hand/foot contact check; animation loop check; 30-second stress preview. Log failures in validation_runs.

**Status:** contract only. No rigged skeletal characters provided yet.

## studio_humanoid_v1 — adopted definition (2026-11-03, ADR-007)

`studio_humanoid_v1` is the Quaternius universal humanoid rig as shipped
in the free Standard (CC0) Godot exports of Universal Base Characters and
Universal Animation Libraries 1 + 2. Facts below are from direct glTF
inspection of the downloaded files on 2026-11-03, not vendor copy.

- **Skeleton:** 65 joints, one shared skeleton across both base bodies
  and all animation files, so every clip targets both bodies unchanged.
  Bone names (UE-style): `root`, `pelvis`, `spine_01`, `spine_02`,
  `spine_03`, `neck_01`, `Head`, `clavicle_l/r`, `upperarm_l/r`,
  `lowerarm_l/r`, `hand_l/r`, full finger chains (`index/middle/pinky/
  ring/thumb_01..03` + `_04_leaf`), `thigh_l/r`, `calf_l/r`, `foot_l/r`,
  `ball_l/r` (+ `ball_leaf_l/r`). This satisfies the required skeleton
  above with `spine_03` as the chest segment and `ball` as the toe.
- **Units/scale:** meters, no root-node scaling. Male body bind-pose
  mesh height ≈ 1.81 m (POSITION accessor maximum Y).
- **Animations:** 43 clips per library GLB (86 unique across UAL1+UAL2),
  each shipped in-place and in a root-motion (`_RM`) variant file.
  In-place is the default for scene playback (the preview moves actors
  by timeline); root-motion variants are catalogued, not auto-applied,
  to avoid double translation.
- **Faces — known gap:** the adopted exports contain **no morph
  targets** (0 on both bodies, eyebrows, hair and the female
  mannequin). The preferred blendshape list above is therefore NOT met
  by `studio_humanoid_v1`; expressions currently ride the `emote` event
  channel and body-language clips. A rig revision adding blendshapes
  (e.g. from a future pack or an owner-authored head) must keep the
  65-joint skeleton and clip compatibility to stay in this family.
- **Sockets (measured 2026-11-03, F1 completion pass):** bind-pose
  world positions of the joint node origins, in metres relative to the
  character origin (floor centre, +Y up). Method: `studio/gltf.py`
  composes each node's local translation/rotation/scale down the glTF
  scene tree and reports the world translation of the skin's joint
  nodes; reproducible with `python3 -m studio sockets [--body <uri>]`.

  | anchor | male body | female body |
  |---|---|---|
  | `hand_l` | [0.706, 1.455, -0.065] | [0.641, 1.418, -0.052] |
  | `hand_r` | [-0.706, 1.455, -0.065] | [-0.641, 1.418, -0.052] |
  | `head` (`Head` joint) | [0.0, 1.600, -0.017] | [0.0, 1.550, -0.011] |

  Reference points (same method): `neck_01` male [0.0, 1.520, -0.041],
  female [0.0, 1.485, -0.041]; `pelvis` male [0.0, 0.949, -0.043],
  female [0.0, 0.932, -0.046]. The bind pose holds the arms extended,
  so the hand anchors sit at full arm reach; they are bone origins for
  attachment, and per-prop grip offsets remain F4 work.
