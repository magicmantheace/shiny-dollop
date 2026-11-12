"""Unit tests for the cross-zone bone ban (skin_policy.chain_groups
+ zone_ban_map) and for apply_veto enforcing label-forbidden pairs
on NON-veto (trunk) columns.

The ban exists because Layer 3 only forbids bones that dominate
another part label: on the Snow Goblin the arm labels are dominated
by arm2.L/arm2.R, so arm.L/arm.R were never banned on the torso
label and the heat's torso arm share stuck at 0.32+ against the
0.25 gate. Pure stdlib + the modules under test; no Blender.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "stages", "rig"))

import skin_policy  # noqa: E402
import template  # noqa: E402


def biped_parents():
    bones = template.build_template("biped", ears=True, arms=True)
    return {b.name: b.parent for b in bones}, template.trunk_chain(bones)


class ChainGroupsTests(unittest.TestCase):
    def test_biped_chains(self):
        parent, trunk = biped_parents()
        groups = skin_policy.chain_groups(parent, trunk)
        self.assertEqual(groups["trunk"], {"root", "spine", "head"})
        self.assertEqual(groups["arm.L"], {"arm.L", "arm2.L"})
        self.assertEqual(groups["arm.R"], {"arm.R", "arm2.R"})
        self.assertEqual(groups["leg.L"], {"leg.L", "leg2.L"})
        self.assertEqual(groups["leg.R"], {"leg.R", "leg2.R"})
        self.assertEqual(groups["ear.L"], {"ear.L"})
        # Every bone is in exactly one group.
        all_members = [n for members in groups.values()
                       for n in members]
        self.assertEqual(sorted(all_members), sorted(parent))


# A trimmed copy of the Snow Goblin rebuild's real label map
# (rig-report.json at the gate failure): label 0 is the torso
# (spine-dominant), 1 an arm (arm2.L-dominant), 5 a leg
# (leg2.R-dominant).
GOBLIN_LABEL_MAP = {
    0: {"dominant": "spine",
        "allowed": ["arm.L", "arm.R", "head", "root", "spine"],
        "forbidden": ["arm2.L", "arm2.R", "ear.L", "ear.R", "leg2.R"]},
    1: {"dominant": "arm2.L",
        "allowed": ["arm.L", "arm2.L", "head", "root", "spine"],
        "forbidden": ["arm2.R", "ear.L", "ear.R", "leg2.R"]},
    5: {"dominant": "leg2.R",
        "allowed": ["head", "leg.R", "leg2.R", "root", "spine"],
        "forbidden": ["arm2.L", "arm2.R", "ear.L", "ear.R"]},
}
PAIRS = [("trunk", "arm.L"), ("trunk", "arm.R")]


class ZoneBanMapTests(unittest.TestCase):
    def ban(self):
        parent, trunk = biped_parents()
        return skin_policy.zone_ban_map(GOBLIN_LABEL_MAP, parent,
                                        trunk, PAIRS)

    def test_torso_label_bans_the_whole_arm_chains(self):
        out, bans = self.ban()
        self.assertEqual(bans[0],
                         ["arm.L", "arm.R", "arm2.L", "arm2.R"])
        for name in ("arm.L", "arm.R", "arm2.L", "arm2.R"):
            self.assertIn(name, out[0]["forbidden"])
        # ...and the recorded allowed set no longer claims them.
        self.assertEqual(out[0]["allowed"], ["head", "root", "spine"])

    def test_arm_label_bans_the_trunk(self):
        out, bans = self.ban()
        self.assertEqual(bans[1], ["head", "root", "spine"])
        for name in ("head", "root", "spine"):
            self.assertIn(name, out[1]["forbidden"])
        self.assertEqual(out[1]["allowed"], ["arm.L", "arm2.L"])

    def test_unpaired_groups_are_untouched(self):
        out, bans = self.ban()
        self.assertNotIn(5, bans)
        self.assertEqual(out[5], GOBLIN_LABEL_MAP[5])

    def test_own_dominant_is_never_banned(self):
        parent, trunk = biped_parents()
        label_map = {2: {"dominant": "arm.L", "allowed": ["arm.L"],
                         "forbidden": []}}
        out, _ = skin_policy.zone_ban_map(label_map, parent, trunk,
                                          PAIRS)
        self.assertNotIn("arm.L", out[2]["forbidden"])

    def test_unknown_group_fails_loudly(self):
        parent, trunk = biped_parents()
        with self.assertRaises(ValueError):
            skin_policy.zone_ban_map(GOBLIN_LABEL_MAP, parent, trunk,
                                     [("trunk", "wing.L")])


class TrunkColumnForbiddenTests(unittest.TestCase):
    """apply_veto must enforce forbidden pairs on trunk columns
    too — the ban names the spine on arm-labelled flesh, and the
    spine is never a distance-veto column."""
    RADII = [1.0, 1.0, 1.0]
    # Columns: 0 = spine (trunk, NOT vetoed), 1 = arm.L, 2 = arm2.L.
    VETO_COLS = [1, 2]

    def test_forbidden_trunk_weight_is_zeroed_and_renormalized(self):
        weights = [[0.4, 0.35, 0.25]]
        distances = [[0.1, 0.1, 0.1]]  # inside every radius
        out, stats = skin_policy.apply_veto(
            weights, distances, self.RADII, veto_cols=self.VETO_COLS,
            forbidden=[[True, False, False]])
        self.assertEqual(stats["label_vetoed_entries"], 1)
        self.assertEqual(stats["vetoed_entries"], 0)
        self.assertAlmostEqual(out[0][0], 0.0)
        self.assertAlmostEqual(out[0][1], 0.35 / 0.6)
        self.assertAlmostEqual(out[0][2], 0.25 / 0.6)

    def test_forbidden_trunk_bone_is_never_the_rescue(self):
        weights = [[1.0, 0.0, 0.0]]  # all weight on the banned spine
        distances = [[0.05, 0.2, 0.3]]  # spine is also the nearest
        out, stats = skin_policy.apply_veto(
            weights, distances, self.RADII, veto_cols=self.VETO_COLS,
            forbidden=[[True, False, False]])
        self.assertEqual(stats["rescued_verts"], [0])
        self.assertEqual(out[0], [0.0, 1.0, 0.0])

    def test_trunk_column_untouched_without_forbidden(self):
        weights = [[0.4, 0.35, 0.25]]
        distances = [[0.1, 0.1, 0.1]]
        out, stats = skin_policy.apply_veto(
            weights, distances, self.RADII, veto_cols=self.VETO_COLS)
        self.assertEqual(out[0], [0.4, 0.35, 0.25])
        self.assertEqual(stats["label_vetoed_entries"], 0)


if __name__ == "__main__":
    unittest.main()
