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


def apply_veto(weights, distances, radii, veto_cols, beyond_end=None,
               veto_distances=None, beyond_tail=None, forbidden=None):
    """Distance-veto a (verts x bones) weight matrix.

    ``weights`` and ``distances`` are parallel rows (per vertex, per
    bone): the current influences and each vertex's distance to each
    bone's segment. For every column in ``veto_cols``, a vertex keeps
    its weight only when its distance to that bone's segment is within
    ``radii[col]``; vetoed weight is redistributed proportionally over
    the vertex's surviving bones by renormalization. Columns outside
    ``veto_cols`` are never touched, whatever the distance.

    ``veto_distances``, when given, replaces ``distances`` for the
    veto comparison ONLY (the rescue below still measures
    ``distances``): the rig passes graph-geodesic distances there, so
    a vertex that is Euclidean-close to a bone across a fused web but
    surface-far from it (the path runs around the web) is vetoed,
    while a vertex close both ways keeps its weight. ``inf`` counts
    as beyond reach, like any overshoot.

    ``beyond_tail`` is a parallel (verts x bones) boolean matrix
    marking vertices that project past a bone's TAIL (distal end).
    It exempts those (vertex, bone) pairs from the veto entirely:
    flesh past the distal joint — fingertips, ear tips, toes, a
    chibi foot's far side — is that bone's continuation, not bleed,
    and its distance from the segment measures the part's size, not
    its ownership. (Measured: the triceratops' foot blobs sit
    ~0.4-0.5 from their leg2 tails, past the 0.39 reach radius, and
    the veto stripped them to the root — feet dominance 1.0 ->
    0.87.) The exemption is tail-only, deliberately: flesh past a
    bone's HEAD (proximal end) is the parent part's territory, and
    on the Snow Goblin the ruff bleed lives exactly there — ~2.4k
    torso vertices per arm project before the arm's head, and
    exempting both ends took the torso arm share from 0.133 to
    0.320 and got the heat rejected. ``beyond_end`` (either end)
    still governs rescue eligibility below: a vertex left with no
    weight at all is rescued onto its nearest eligible bone at full
    weight, so coverage is preserved, and a bone that vetoed a
    vertex is rescue-eligible for it again only when the vertex is
    beyond one of its ends. When the matrices are omitted, no pair
    is exempt and every bone is rescue-eligible.

    ``forbidden`` is an optional (verts x bones) boolean matrix of
    pairs banned outright by PART LABELS (Layer 3): a vertex whose
    segmented part maps to other bones may not hold weight on this
    one at any distance — not within the radius, not past the tail —
    and a forbidden bone is never rescue-eligible for that vertex.
    Distance asks "how far is the flesh from the bone"; labels
    answer "whose flesh is it" first. Forbidden vetoes are counted
    separately in the stats (``label_vetoed_entries``).

    Returns (new_weights, stats) with stats counting the vetoed
    (vertex, bone) entries, the vertices touched, and the rescued
    vertex indices.
    """
    vetoed_entries = 0
    label_vetoed_entries = 0
    verts_touched = 0
    rescued = []
    out = []
    for vi, row in enumerate(weights):
        new = list(row)
        touched = False
        vetoed_here = set()
        forbidden_here = set()
        for c in veto_cols:
            if forbidden is not None and forbidden[vi][c]:
                if new[c] > 0.0:
                    new[c] = 0.0
                    label_vetoed_entries += 1
                    touched = True
                vetoed_here.add(c)
                forbidden_here.add(c)
                continue
            if (beyond_tail is not None and beyond_tail[vi][c]):
                continue  # continuation flesh past the bone's tail
            reach = (veto_distances[vi][c] if veto_distances is not None
                     else distances[vi][c])
            if new[c] > 0.0 and reach > radii[c]:
                new[c] = 0.0
                vetoed_entries += 1
                vetoed_here.add(c)
                touched = True
        total = sum(new)
        if total <= 0.0:
            def eligible(c):
                if c in forbidden_here:
                    return False
                if c not in vetoed_here:
                    return True
                return (beyond_end is not None
                        and beyond_end[vi][c])

            candidates = [c for c in range(len(row)) if eligible(c)]
            if not candidates:
                candidates = [c for c in range(len(row))
                              if c not in forbidden_here]
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
             "label_vetoed_entries": label_vetoed_entries,
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
