"""Unit tests for the graph-geodesic skinning distances (Layer 2 of
the cleanup slice) and for skin_policy's geodesic veto path.

Blender and GPU stages are verified by running them (TEST_PLAN.md);
these tests pin the pure-Python math. The discriminating fixture is
a hairpin: a long thin sheet folded back on itself so the two legs
run parallel, 0.20 apart in space (bone-centreline to foreign sheet,
the scale an armpit web presents), joined only at the far end. A
vertex at the end of the return leg is Euclidean-close to a bone
lying along the outgoing leg (straight-line distance crosses the
fold, 0.20) but surface-far from it (the path runs the whole strip,
~8.1). That is the armpit-web geometry in miniature: Euclidean reach
says "near the arm", surface reach says "not the arm's flesh".
"""

import importlib.util
import os
import sys
import unittest

import numpy as np

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(name, relpath):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(PROJECT, relpath))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


geodesic = load("gab_geodesic", "stages/rig/geodesic.py")
skin_policy = load("gab_skin_policy_geo", "stages/rig/skin_policy.py")


def hairpin(step=0.25, width=0.5, gap=0.20, length=4.0):
    """A folded sheet: (verts, faces, landmarks). Rings run out
    along y=0, around a semicircular turn, and back along y=gap.
    landmarks: {"start_out": idx of the first outgoing ring centre,
    "web": idx of the last return ring centre (Euclidean-close to
    start_out across the fold, surface-far), "mid_out": idx of the
    outgoing ring at x = length/2}."""
    centre = []
    xs = np.arange(0.0, length + 1e-9, step)
    for x in xs:
        centre.append((x, 0.0, 0.0))
    for a in np.linspace(-np.pi / 2, np.pi / 2, 5)[1:-1]:
        centre.append((length + (gap / 2) * np.cos(a),
                       gap / 2 + (gap / 2) * np.sin(a), 0.0))
    for x in xs[::-1]:
        centre.append((x, gap, 0.0))
    verts, faces = [], []
    for i, (x, y, z) in enumerate(centre):
        verts.append((x, y, z - width / 2))
        verts.append((x, y, z + width / 2))
        if i:
            a, b = 2 * (i - 1), 2 * (i - 1) + 1
            c, d = 2 * i, 2 * i + 1
            faces.append((a, b, c))
            faces.append((b, d, c))
    landmarks = {
        "start_out": 0,
        "mid_out": int(round((length / 2) / step)) * 2,
        "web": len(verts) - 2,
    }
    return (np.array(verts, dtype=np.float64),
            np.array(faces, dtype=np.int64), landmarks)


class GeodesicDistanceTests(unittest.TestCase):
    def setUp(self):
        self.verts, self.faces, self.lm = hairpin()
        # One bone along the outgoing leg at the strip's start.
        self.heads = [(0.0, 0.0, 0.0)]
        self.tails = [(0.5, 0.0, 0.0)]

    def test_euclidean_crosses_the_fold_geodesic_does_not(self):
        euclid = geodesic.segment_distances(
            self.heads, self.tails, self.verts)
        web = self.lm["web"]
        # 0.32 in the fixture (fold gap 0.20 + the landmark's
        # across-width offset 0.25) — comfortably inside the 0.5
        # veto radius the geodesic tests below use.
        self.assertLess(euclid[web, 0], 0.35,
                        "fixture broken: web vertex should be "
                        "Euclidean-close to the bone")
        geo = geodesic.geodesic_distance_matrix(
            self.verts, self.faces, self.heads, self.tails,
            radii=[9.0])
        self.assertGreater(geo[web, 0], 7.0,
                           "surface path around the hairpin should "
                           "be ~the whole strip length")

    def test_geodesic_along_one_leg_tracks_along_surface_distance(self):
        geo = geodesic.geodesic_distance_matrix(
            self.verts, self.faces, self.heads, self.tails,
            radii=[9.0])
        mid = geo[self.lm["mid_out"], 0]
        self.assertAlmostEqual(mid, 1.5, delta=0.6,
                               msg="mid-leg vertex should measure "
                                   "roughly its along-strip distance "
                                   "from the bone's seed sleeve")

    def test_seeds_measure_zero_and_cap_reports_inf(self):
        geo = geodesic.geodesic_distance_matrix(
            self.verts, self.faces, self.heads, self.tails,
            radii=[0.6])
        self.assertEqual(geo[self.lm["start_out"], 0], 0.0)
        self.assertTrue(np.isinf(geo[self.lm["web"], 0]),
                        "beyond the cap the distance must read as "
                        "beyond reach (inf), not a capped number")

    def test_unreachable_shell_reports_inf(self):
        # A separate triangle floating away from the sheet.
        extra_v = np.array([(10.0, 10.0, 10.0), (10.3, 10.0, 10.0),
                            (10.0, 10.3, 10.0)])
        extra_f = np.array([[len(self.verts), len(self.verts) + 1,
                             len(self.verts) + 2]])
        verts = np.vstack([self.verts, extra_v])
        faces = np.vstack([self.faces, extra_f])
        geo = geodesic.geodesic_distance_matrix(
            verts, faces, self.heads, self.tails, radii=[9.0])
        self.assertTrue(np.isinf(geo[len(self.verts), 0]))

    def test_seed_fallback_for_bone_in_empty_space(self):
        heads = [(20.0, 20.0, 20.0)]
        tails = [(20.5, 20.0, 20.0)]
        geo = geodesic.geodesic_distance_matrix(
            self.verts, self.faces, heads, tails, radii=[40.0])
        finite = np.isfinite(geo[:, 0])
        self.assertTrue(finite.any(),
                        "a bone with no close sleeve must still get "
                        "a field from its nearest vertices")


class GeodesicVetoTests(unittest.TestCase):
    """Through skin_policy.apply_veto: the same vertex, weights and
    Euclidean distances — only the veto metric changes."""

    def setUp(self):
        verts, faces, lm = hairpin()
        self.web = lm["web"]
        heads = [(0.0, 0.0, 0.0), (0.0, 0.0, -1.0)]
        tails = [(0.5, 0.0, 0.0), (0.0, 0.0, 1.0)]
        self.euclid = geodesic.segment_distances(heads, tails, verts)
        self.geo = geodesic.geodesic_distance_matrix(
            verts, faces, heads, tails, radii=[0.5, 0.5])
        # A matrix of just the web vertex's row, for apply_veto's
        # list-of-rows shape.
        self.weights = [[0.8, 0.2]]  # arm owns the web vertex
        self.dist_row = [self.euclid[self.web].tolist()]
        self.geo_row = [self.geo[self.web].tolist()]

    def test_euclidean_veto_keeps_the_bleed(self):
        out, stats = skin_policy.apply_veto(
            self.weights, self.dist_row, [0.5, 0.5], veto_cols=[0])
        self.assertAlmostEqual(out[0][0], 0.8,
                               msg="Euclidean-close across the fold: "
                                   "the old metric cannot see the web")
        self.assertEqual(stats["vetoed_entries"], 0)

    def test_geodesic_veto_cuts_the_bleed(self):
        self.assertTrue(np.isinf(self.geo_row[0][0]),
                        "fixture: web vertex must be surface-beyond "
                        "the arm's reach")
        out, stats = skin_policy.apply_veto(
            self.weights, self.dist_row, [0.5, 0.5], veto_cols=[0],
            veto_distances=self.geo_row)
        self.assertEqual(stats["vetoed_entries"], 1)
        self.assertAlmostEqual(out[0][0], 0.0)
        self.assertAlmostEqual(out[0][1], 1.0,
                               msg="vetoed weight renormalizes onto "
                                   "the surviving (trunk) bone")

    def test_geodesic_veto_leaves_genuinely_near_flesh_alone(self):
        # Vertex 0 sits in the bone's own sleeve: geodesic ~ 0.
        row_w = [[0.8, 0.2]]
        row_d = [self.euclid[0].tolist()]
        row_g = [self.geo[0].tolist()]
        out, stats = skin_policy.apply_veto(
            row_w, row_d, [0.5, 0.5], veto_cols=[0],
            veto_distances=row_g)
        self.assertEqual(stats["vetoed_entries"], 0)
        self.assertAlmostEqual(out[0][0], 0.8)


class BeyondTailExemptionTests(unittest.TestCase):
    """The veto exempts flesh projecting past a bone's TAIL: that is
    the bone's continuation (toes, fingertips, a chibi foot's far
    side), and its distance measures the part's size, not bleed.
    Beside the shaft — or past the HEAD, which is the parent part's
    territory (the goblin's ruff) — the veto applies in full."""

    RADII = [1.0, 1.0, 0.3]

    def test_beyond_tail_blend_survives_the_veto(self):
        weights = [[0.3, 0.3, 0.4]]
        distances = [[0.4, 0.5, 0.9]]  # col 2 far beyond its radius
        tail = [[False, False, True]]
        out, stats = skin_policy.apply_veto(
            weights, distances, self.RADII, veto_cols=[2],
            beyond_tail=tail)
        self.assertEqual(stats["vetoed_entries"], 0)
        self.assertAlmostEqual(out[0][2], 0.4)

    def test_beside_the_shaft_the_same_distance_is_vetoed(self):
        weights = [[0.3, 0.3, 0.4]]
        distances = [[0.4, 0.5, 0.9]]
        tail = [[False, False, False]]
        out, stats = skin_policy.apply_veto(
            weights, distances, self.RADII, veto_cols=[2],
            beyond_tail=tail)
        self.assertEqual(stats["vetoed_entries"], 1)
        self.assertAlmostEqual(out[0][2], 0.0)
        self.assertAlmostEqual(sum(out[0]), 1.0)

    def test_beyond_the_head_does_not_exempt(self):
        # beyond_end (rescue eligibility) may be set while
        # beyond_tail is not: the pair is still vetoed — the ruff
        # past the shoulder belongs to the torso, not the arm.
        weights = [[0.3, 0.3, 0.4]]
        distances = [[0.4, 0.5, 0.9]]
        out, stats = skin_policy.apply_veto(
            weights, distances, self.RADII, veto_cols=[2],
            beyond_end=[[False, False, True]],
            beyond_tail=[[False, False, False]])
        self.assertEqual(stats["vetoed_entries"], 1)
        self.assertAlmostEqual(out[0][2], 0.0)


if __name__ == "__main__":
    unittest.main()
