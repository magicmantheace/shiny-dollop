"""Skinning acceptance policy (pure data — no Blender imports).

Decides, from measured checks, whether a bone-heat (automatic weights)
result is good enough to ship or whether the rig stage must fall back
to distance-to-bone weights. Kept separate from rig_blender.py so the
decision is unit-testable without a Blender runtime.

The thresholds mirror the ones the P0 rig used informally: near-total
coverage, every bone carrying some verts, and the wingtip zone actually
dominated by the wing bones (a heat result that leaves the wingtips to
the spine is not a skinning, whatever its coverage says).
"""


def assess_heat(coverage: float, per_bone: dict, bone_names: list,
                wingtip_frac: float, min_coverage: float = 0.98,
                min_wingtip: float = 0.5) -> tuple[bool, list[str]]:
    """Return (accepted, reasons). ``reasons`` is empty when accepted;
    otherwise it names every failed check, for the rig report."""
    reasons = []
    if coverage < min_coverage:
        reasons.append(
            f"coverage {coverage:.3f} < {min_coverage:.2f}")
    empty = [name for name in bone_names if per_bone.get(name, 0) <= 0]
    if empty:
        reasons.append("bones with no weighted verts: " + ", ".join(empty))
    if wingtip_frac < min_wingtip:
        reasons.append(
            f"wingtip dominance {wingtip_frac:.3f} < {min_wingtip:.2f}")
    return (not reasons), reasons
