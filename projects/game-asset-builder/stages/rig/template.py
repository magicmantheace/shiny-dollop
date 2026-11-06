"""Winged-creature armature template (pure data — no Blender imports).

Bone positions are fractions of the canonical bounding box:
  x: -0.5 (character's right) .. +0.5 (left), of width
  y: -0.5 (front) .. +0.5 (back), of depth   (character faces -Y)
  z:  0 (ground) .. 1 (top), of height

The base layout is Pip's proven 14-bone rig from Drabbit Pet. Optional
bone groups are parameterized: ``ears`` for earred characters (Pip) and
``arms`` for armed ones (the Ember Dragon) — with either option off, its
bones are simply absent and the animate stage's recipes skip them.
Parents always precede children in the returned list.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class BoneSpec:
    name: str
    head: tuple[float, float, float]  # (x/W, y/D, z/H)
    tail: tuple[float, float, float]
    parent: str | None
    roll: str  # "vertical": local X ~ world X (pitch = nod)
    #            "horizontal": local X ~ world -Y (pitch = wing sweep)


def winged_creature(ears: bool = True, arms: bool = False) -> list[BoneSpec]:
    bones = [
        BoneSpec("root", (0, 0, 0.02), (0, 0, 0.30), None, "vertical"),
        BoneSpec("spine", (0, 0, 0.30), (0, 0, 0.58), "root", "vertical"),
        BoneSpec("head", (0, -0.03, 0.60), (0, -0.05, 0.92),
                 "spine", "vertical"),
    ]
    if ears:
        bones += [
            BoneSpec("ear.L", (0.10, -0.03, 0.86), (0.17, -0.03, 1.00),
                     "head", "vertical"),
            BoneSpec("ear.R", (-0.10, -0.03, 0.86), (-0.17, -0.03, 1.00),
                     "head", "vertical"),
        ]
    bones += [
        BoneSpec("wing.L", (0.10, 0.10, 0.66), (0.34, 0.15, 0.78),
                 "spine", "horizontal"),
        BoneSpec("wing2.L", (0.34, 0.15, 0.78), (0.52, 0.18, 0.60),
                 "wing.L", "horizontal"),
        BoneSpec("wing.R", (-0.10, 0.10, 0.66), (-0.34, 0.15, 0.78),
                 "spine", "horizontal"),
        BoneSpec("wing2.R", (-0.34, 0.15, 0.78), (-0.52, 0.18, 0.60),
                 "wing.R", "horizontal"),
    ]
    if arms:
        bones += [
            BoneSpec("arm.L", (0.16, -0.08, 0.52), (0.25, -0.12, 0.30),
                     "spine", "vertical"),
            BoneSpec("arm.R", (-0.16, -0.08, 0.52), (-0.25, -0.12, 0.30),
                     "spine", "vertical"),
        ]
    bones += [
        BoneSpec("leg.L", (0.13, -0.02, 0.30), (0.18, -0.05, 0.03),
                 "root", "vertical"),
        BoneSpec("leg.R", (-0.13, -0.02, 0.30), (-0.18, -0.05, 0.03),
                 "root", "vertical"),
        BoneSpec("tail.1", (0, 0.12, 0.30), (0, 0.30, 0.20),
                 "root", "vertical"),
        BoneSpec("tail.2", (0, 0.30, 0.20), (0, 0.43, 0.12),
                 "tail.1", "vertical"),
        BoneSpec("tail.3", (0, 0.43, 0.12), (0, 0.46, 0.21),
                 "tail.2", "vertical"),
    ]
    return bones


TEMPLATES = {"winged-creature": winged_creature}


def build_template(name: str = "winged-creature", **options) -> list[BoneSpec]:
    if name not in TEMPLATES:
        raise KeyError(f"unknown rig template: {name!r}")
    bones = TEMPLATES[name](**options)
    seen = set()
    for bone in bones:
        if bone.parent is not None and bone.parent not in seen:
            raise ValueError(
                f"bone {bone.name!r} appears before parent {bone.parent!r}")
        seen.add(bone.name)
    return bones
