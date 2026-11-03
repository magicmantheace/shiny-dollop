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
