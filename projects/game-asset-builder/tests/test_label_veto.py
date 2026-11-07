"""Unit tests for the Layer-3 label veto in skin_policy.apply_veto:
part-label forbidden pairs are banned at ANY distance (inside the
reach radius, past the tail), and a forbidden bone is never a
rescue target. Pure stdlib + the module under test; no Blender.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "stages", "rig"))

import skin_policy  # noqa: E402


class ForbiddenVetoTests(unittest.TestCase):
    RADII = [1.0, 1.0, 0.3]

    def test_forbidden_pair_zeroed_inside_the_radius(self):
        # Distance 0.1 is well inside col 2's 0.3 radius — the
        # distance veto alone would keep this weight. The label
        # veto must still remove it.
        weights = [[0.2, 0.3, 0.5]]
        distances = [[0.4, 0.5, 0.1]]
        forbidden = [[False, False, True]]
        out, stats = skin_policy.apply_veto(
            weights, distances, self.RADII, veto_cols=[2],
            forbidden=forbidden)
        self.assertEqual(stats["label_vetoed_entries"], 1)
        self.assertEqual(stats["vetoed_entries"], 0)
        self.assertAlmostEqual(out[0][2], 0.0)
        self.assertAlmostEqual(sum(out[0]), 1.0)

    def test_forbidden_beats_the_beyond_tail_exemption(self):
        weights = [[0.2, 0.3, 0.5]]
        distances = [[0.4, 0.5, 0.9]]
        out, stats = skin_policy.apply_veto(
            weights, distances, self.RADII, veto_cols=[2],
            beyond_tail=[[False, False, True]],
            forbidden=[[False, False, True]])
        self.assertEqual(stats["label_vetoed_entries"], 1)
        self.assertAlmostEqual(out[0][2], 0.0)

    def test_forbidden_bone_is_never_the_rescue(self):
        # All weight was on the forbidden bone, which is also the
        # nearest: rescue must land on a non-forbidden bone.
        weights = [[0.0, 0.0, 1.0]]
        distances = [[0.4, 0.5, 0.1]]
        out, stats = skin_policy.apply_veto(
            weights, distances, self.RADII, veto_cols=[2],
            beyond_end=[[False, False, True]],
            forbidden=[[False, False, True]])
        self.assertEqual(stats["rescued_verts"], [0])
        self.assertEqual(out[0][2], 0.0)
        self.assertEqual(out[0][0], 1.0)  # nearest allowed = col 0

    def test_unlabelled_rows_are_untouched_by_forbidden(self):
        weights = [[0.2, 0.3, 0.5]]
        distances = [[0.4, 0.5, 0.1]]
        out, stats = skin_policy.apply_veto(
            weights, distances, self.RADII, veto_cols=[2],
            forbidden=[[False, False, False]])
        self.assertEqual(stats["label_vetoed_entries"], 0)
        self.assertEqual(out[0], [0.2, 0.3, 0.5])


if __name__ == "__main__":
    unittest.main()
