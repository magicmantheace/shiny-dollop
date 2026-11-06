"""Skinning acceptance policy (pure data — no Blender imports).

Decides, from measured checks, whether a bone-heat (automatic weights)
result is good enough to ship or whether the rig stage must fall back
to distance-to-bone weights. Kept separate from rig_blender.py so the
decision is unit-testable without a Blender runtime.

The thresholds mirror the ones the P0 rig used informally: near-total
coverage, every bone carrying some verts, and the template's tip zone
actually dominated by its own bones (a heat result that leaves the
wingtips to the spine is not a skinning, whatever its coverage says).
The tip zone is per-template: wingtips for the winged creature, the
feet for a quadruped (legs glued to the belly are the classic failure),
the hands for a biped (arms glued to the torso).

This module also carries the weight-distance veto (``apply_veto``):
bone heat diffuses through a creature's whole volume, so on fused
masses (a fur ruff grown into the shoulders) an appendage bone can
end up owning most of the torso — and drags it, texture and all, when
the appendage swings. The veto zeroes any appendage-bone weight whose
vertex sits beyond that bone's reach radius and renormalizes what
remains onto the surviving bones (typically the trunk chain). The
axial trunk bones are exempt: their segments run through the body
mass they own, so distance-to-segment measures body radius there,
not bleed. ``assess_zone_share`` is the acceptance gate that catches
a bleed the veto missed.
"""


def assess_heat(coverage: float, per_bone: dict, bone_names: list,
                tip_frac: float, min_coverage: float = 0.98,
                min_tip: float = 0.5,
                tip_label: str = "wingtip") -> tuple[bool, list[str]]:
    """Return (accepted, reasons). ``reasons`` is empty when accepted;
    otherwise it names every failed check, for the rig report."""
    reasons = []
    if coverage < min_coverage:
        reasons.append(
            f"coverage {coverage:.3f} < {min_coverage:.2f}")
    empty = [name for name in bone_names if per_bone.get(name, 0) <= 0]
    if empty:
        reasons.append("bones with no weighted verts: " + ", ".join(empty))
    if tip_frac < min_tip:
        reasons.append(
            f"{tip_label} dominance {tip_frac:.3f} < {min_tip:.2f}")
    return (not reasons), reasons


def apply_veto(weights, distances, radii, veto_cols, beyond_end=None):
    """Distance-veto a (verts x bones) weight matrix.

    ``weights`` and ``distances`` are parallel rows (per vertex, per
    bone): the current influences and each vertex's distance to each
    bone's segment. For every column in ``veto_cols``, a vertex keeps
    its weight only when its distance to that bone's segment is within
    ``radii[col]``; vetoed weight is redistributed proportionally over
    the vertex's surviving bones by renormalization. Columns outside
    ``veto_cols`` are never touched, whatever the distance.

    A vertex left with no weight at all (everything it had was
    vetoed, or heat never reached it) is rescued onto its nearest
    ELIGIBLE bone at full weight, so coverage is preserved. Rescue
    eligibility is where the capsule model bites: a bone that vetoed
    this vertex is eligible again only when ``beyond_end`` says the
    vertex projects past that bone's segment endpoints — flesh beyond
    a joint (fingertips, ear tips, toes) belongs to that bone's chain
    at any radius, while flesh BESIDE the shaft (the armpit web a
    raised arm would otherwise tow into a sheet) rescues onto the
    trunk instead. ``beyond_end`` is a parallel (verts x bones)
    boolean matrix; when omitted, every bone is rescue-eligible.

    Returns (new_weights, stats) with stats counting the vetoed
    (vertex, bone) entries, the vertices touched, and the rescued
    vertex indices.
    """
    vetoed_entries = 0
    verts_touched = 0
    rescued = []
    out = []
    for vi, row in enumerate(weights):
        new = list(row)
        touched = False
        vetoed_here = set()
        for c in veto_cols:
            if new[c] > 0.0 and distances[vi][c] > radii[c]:
                new[c] = 0.0
                vetoed_entries += 1
                vetoed_here.add(c)
                touched = True
        total = sum(new)
        if total <= 0.0:
            def eligible(c):
                if c not in vetoed_here:
                    return True
                return (beyond_end is not None
                        and beyond_end[vi][c])

            candidates = [c for c in range(len(row)) if eligible(c)]
            if not candidates:
                candidates = list(range(len(row)))
            nearest = min(candidates,
                          key=lambda c: distances[vi][c])
            new = [0.0] * len(row)
            new[nearest] = 1.0
            rescued.append(vi)
            touched = True
        else:
            new = [w / total for w in new]
        if touched:
            verts_touched += 1
        out.append(new)
    stats = {"vetoed_entries": vetoed_entries,
             "verts_touched": verts_touched,
             "rescued_verts": rescued}
    return out, stats


def assess_zone_share(share: float, max_share: float = 0.25,
                      zone_label: str = "torso",
                      group_label: str = "arm") -> list[str]:
    """Gate one guard-zone weight share: the share of a body zone's
    total weight held by an appendage group (the arms over the torso,
    say) must stay small, or that group is still dragging body mass
    when it moves. Returns a list of failure reasons (empty = pass),
    shaped for assess_heat's reasons list. Calibrated on the biped:
    the Snow Goblin's unvetoed heat put 0.51 of the torso zone's
    weight on the arms; the vetoed rig measures 0.14."""
    if share > max_share:
        return [f"{zone_label} {group_label} weight share "
                f"{share:.3f} > {max_share:.2f}"]
    return []
