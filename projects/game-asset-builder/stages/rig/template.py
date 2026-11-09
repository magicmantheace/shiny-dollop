"""Armature templates (pure data — no Blender imports).

Bone positions are fractions of the canonical bounding box:
  x: -0.5 (character's right) .. +0.5 (left), of width
  y: -0.5 (front) .. +0.5 (back), of depth   (character faces -Y)
  z:  0 (ground) .. 1 (top), of height

Templates:
- ``winged-creature`` — Pip's proven 14-bone layout from Drabbit Pet,
  with parameterized ``ears`` / ``arms`` groups.
- ``quadruped`` (P1) — horizontal spine chain, neck + head at the
  front, four two-segment legs, tail chain at the rear.
- ``biped`` (P1) — vertical spine, head, two-segment arms and legs,
  optional ``ears``.

With an option off, its bones are simply absent and the animate
stage's recipes skip them. Parents always precede children in the
returned list. Every template function accepts (and ignores) the
options it does not use, so callers can pass the full option set.
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


def quadruped(ears: bool = False, arms: bool = False) -> list[BoneSpec]:
    # Horizontal body plan: the spine chain runs along Y (front is
    # -Y), the back line sits near z 0.55 of the height (chubby
    # stylized quadrupeds are leg + belly below that), legs are two
    # segments (upper + lower, mirroring the wing/wing2 naming).
    bones = [
        BoneSpec("root", (0, 0.06, 0.30), (0, 0.06, 0.56), None,
                 "vertical"),
        BoneSpec("spine", (0, 0.08, 0.52), (0, -0.16, 0.56), "root",
                 "horizontal"),
        BoneSpec("hips", (0, 0.04, 0.52), (0, 0.28, 0.54), "root",
                 "horizontal"),
        BoneSpec("neck", (0, -0.16, 0.56), (0, -0.32, 0.70), "spine",
                 "horizontal"),
        BoneSpec("head", (0, -0.32, 0.70), (0, -0.44, 0.80), "neck",
                 "horizontal"),
    ]
    for side, sx in (("L", 1), ("R", -1)):
        bones += [
            BoneSpec(f"leg.F{side}", (sx * 0.17, -0.17, 0.46),
                     (sx * 0.18, -0.18, 0.23), "spine", "vertical"),
            BoneSpec(f"leg2.F{side}", (sx * 0.18, -0.18, 0.23),
                     (sx * 0.18, -0.19, 0.02), f"leg.F{side}",
                     "vertical"),
            BoneSpec(f"leg.H{side}", (sx * 0.17, 0.25, 0.46),
                     (sx * 0.18, 0.26, 0.23), "hips", "vertical"),
            BoneSpec(f"leg2.H{side}", (sx * 0.18, 0.26, 0.23),
                     (sx * 0.18, 0.26, 0.02), f"leg.H{side}",
                     "vertical"),
        ]
    bones += [
        BoneSpec("tail.1", (0, 0.32, 0.52), (0, 0.44, 0.42), "hips",
                 "vertical"),
        BoneSpec("tail.2", (0, 0.44, 0.42), (0, 0.48, 0.30), "tail.1",
                 "vertical"),
    ]
    return bones


def biped(ears: bool = False, arms: bool = True) -> list[BoneSpec]:
    # Upright body plan: vertical spine (Pip proportions — head takes
    # the top third on chubby stylized bipeds), arms hanging at the
    # sides in two segments, legs in two segments.
    bones = [
        BoneSpec("root", (0, 0, 0.02), (0, 0, 0.32), None, "vertical"),
        BoneSpec("spine", (0, 0, 0.32), (0, 0, 0.60), "root",
                 "vertical"),
        BoneSpec("head", (0, -0.02, 0.62), (0, -0.04, 0.92), "spine",
                 "vertical"),
    ]
    if ears:
        bones += [
            BoneSpec("ear.L", (0.09, -0.02, 0.85), (0.16, -0.02, 1.00),
                     "head", "vertical"),
            BoneSpec("ear.R", (-0.09, -0.02, 0.85), (-0.16, -0.02, 1.00),
                     "head", "vertical"),
        ]
    if arms:
        # Arm bones use the "horizontal" roll: probed on the template
        # geometry, it makes local X the raise axis — +X lifts either
        # hand up and outward symmetrically (the wave), where the
        # "vertical" roll only swings a hanging arm fore-aft or sweeps
        # it horizontally.
        for side, sx in (("L", 1), ("R", -1)):
            bones += [
                BoneSpec(f"arm.{side}", (sx * 0.18, -0.02, 0.56),
                         (sx * 0.27, -0.03, 0.35), "spine", "horizontal"),
                BoneSpec(f"arm2.{side}", (sx * 0.27, -0.03, 0.35),
                         (sx * 0.29, -0.04, 0.16), f"arm.{side}",
                         "horizontal"),
            ]
    for side, sx in (("L", 1), ("R", -1)):
        bones += [
            BoneSpec(f"leg.{side}", (sx * 0.11, 0, 0.32),
                     (sx * 0.13, 0, 0.17), "root", "vertical"),
            BoneSpec(f"leg2.{side}", (sx * 0.13, 0, 0.17),
                     (sx * 0.13, -0.01, 0.02), f"leg.{side}",
                     "vertical"),
        ]
    return bones


def winged_quadruped(ears: bool = False, arms: bool = False
                     ) -> list[BoneSpec]:
    """Quadruped body plan + a wing pair on the spine (P5: the
    Moth-Hart is a four-legged deer with four moth wings — the upright
    winged-creature plan cannot rig it). Wings use the winged
    template's "horizontal" roll, so the animate stage's wing drivers
    carry over. ``ears`` adds antenna/ear bones on the head."""
    base = quadruped()
    extra = []
    if ears:
        extra += [
            BoneSpec("ear.L", (0.07, -0.30, 0.80), (0.13, -0.33, 0.99),
                     "head", "vertical"),
            BoneSpec("ear.R", (-0.07, -0.30, 0.80), (-0.13, -0.33, 0.99),
                     "head", "vertical"),
        ]
    extra += [
        BoneSpec("wing.L", (0.10, 0.02, 0.78), (0.34, 0.10, 0.94),
                 "spine", "horizontal"),
        BoneSpec("wing2.L", (0.34, 0.10, 0.94), (0.52, 0.16, 0.76),
                 "wing.L", "horizontal"),
        BoneSpec("wing.R", (-0.10, 0.02, 0.78), (-0.34, 0.10, 0.94),
                 "spine", "horizontal"),
        BoneSpec("wing2.R", (-0.34, 0.10, 0.94), (-0.52, 0.16, 0.76),
                 "wing.R", "horizontal"),
    ]
    return base[:5] + extra + base[5:]


def snail(ears: bool = False, arms: bool = False) -> list[BoneSpec]:
    """Legless snail plan (P5): a three-bone chain along the foot,
    a rising neck + head at the front, two eye-stalk bones, and one
    shell bone parented to the root so the lantern shell rides the
    body sway without deforming under the undulation. No legs exist
    on this plan by design — locomotion is a body wave (the animate
    stage's glide), never a leg gait."""
    return [
        BoneSpec("root", (0, 0.02, 0.02), (0, 0.02, 0.20), None,
                 "vertical"),
        BoneSpec("body.1", (0, 0.30, 0.05), (0, 0.10, 0.06), "root",
                 "vertical"),
        BoneSpec("body.2", (0, 0.10, 0.06), (0, -0.12, 0.07), "body.1",
                 "vertical"),
        BoneSpec("body.3", (0, -0.12, 0.07), (0, -0.28, 0.14), "body.2",
                 "vertical"),
        BoneSpec("neck", (0, -0.28, 0.14), (0, -0.34, 0.44), "body.3",
                 "vertical"),
        BoneSpec("head", (0, -0.34, 0.44), (0, -0.38, 0.64), "neck",
                 "vertical"),
        BoneSpec("eye.L", (0.07, -0.36, 0.58), (0.10, -0.38, 0.86),
                 "head", "vertical"),
        BoneSpec("eye.R", (-0.07, -0.36, 0.58), (-0.10, -0.38, 0.86),
                 "head", "vertical"),
        BoneSpec("shell", (0, 0.14, 0.26), (0, 0.20, 0.58), "root",
                 "vertical"),
    ]


def trunk_chain(bones: list[BoneSpec],
                head_name: str = "head") -> set[str]:
    """The axial (trunk) bones: the parent chain from ``head_name``
    up to the root, inclusive. Every template's large-amplitude
    recipe motion lives in the appendages (arms, legs, wings, ears,
    tail); the trunk chain's segments run through the body mass they
    legitimately own, so the rig stage's weight-distance veto
    restrains only the non-trunk bones (see
    stages/rig/skin_policy.py). Falls back to the first (root) bone
    when the template has no bone named ``head_name``."""
    parent = {b.name: b.parent for b in bones}
    chain: set[str] = set()
    cur = head_name if head_name in parent else None
    while cur is not None:
        chain.add(cur)
        cur = parent.get(cur)
    if not chain and bones:
        chain = {bones[0].name}
    return chain


TEMPLATES = {"winged-creature": winged_creature,
             "quadruped": quadruped,
             "biped": biped,
             "winged-quadruped": winged_quadruped,
             "snail": snail}


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
