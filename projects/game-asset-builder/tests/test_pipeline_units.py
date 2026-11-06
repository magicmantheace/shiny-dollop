"""Unit tests for the P0 pipeline's pure-Python parts.

Blender and GPU stages are verified by actually running them (see
docs/TEST_PLAN.md); these tests pin the parts that must never drift:
the rig template's shape, the pose recipes' math, the catalog record,
the cutout algorithm, and the bridge runner's token discipline.
Stage modules are loaded by file path because ``stages`` (the registry
module, stages.py) and the ``stages/`` directory share a name by design.
"""

import importlib.util
import os
import sys
import tempfile
import unittest
from unittest import mock

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(name, relpath):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(PROJECT, relpath))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


template = load("gab_template", "stages/rig/template.py")
poses = load("gab_poses", "stages/animate/poses.py")
catalog = load("gab_catalog", "stages/catalog/catalog.py")
skin_policy = load("gab_skin_policy", "stages/rig/skin_policy.py")


class TemplateTests(unittest.TestCase):
    def test_pip_configuration_is_the_proven_14_bones(self):
        bones = template.build_template(ears=True, arms=False)
        names = [b.name for b in bones]
        self.assertEqual(len(names), 14)
        self.assertIn("ear.L", names)
        self.assertIn("wing2.R", names)
        self.assertNotIn("arm.L", names)

    def test_dragon_configuration_swaps_ears_for_arms(self):
        bones = template.build_template(ears=False, arms=True)
        names = [b.name for b in bones]
        self.assertEqual(len(names), 14)
        self.assertIn("arm.L", names)
        self.assertIn("arm.R", names)
        self.assertNotIn("ear.L", names)

    def test_parents_precede_children_and_names_unique(self):
        for options in ({"ears": True}, {"arms": True},
                        {"ears": True, "arms": True}, {}):
            bones = template.build_template(**options)
            names = [b.name for b in bones]
            self.assertEqual(len(names), len(set(names)))
            for bone in bones:
                if bone.parent:
                    self.assertLess(names.index(bone.parent),
                                    names.index(bone.name))

    def test_fraction_bounds(self):
        for bone in template.build_template(ears=True, arms=True):
            for frac in bone.head + bone.tail:
                self.assertGreaterEqual(frac, -0.55)
                self.assertLessEqual(frac, 1.0)

    def test_unknown_template_raises(self):
        with self.assertRaises(KeyError):
            template.build_template("centipede")


class PoseTests(unittest.TestCase):
    def test_hop_arch_endpoints_and_apex(self):
        self.assertAlmostEqual(poses.hop_arch(0.0, 0.62), 0.0)
        self.assertAlmostEqual(poses.hop_arch(0.31, 0.62), 1.0)
        self.assertAlmostEqual(poses.hop_arch(0.62, 0.62), 0.0)

    def test_hop_root_lift_peaks_near_apex(self):
        peak = max(poses.pose_hop(t / 100)["root_y"]
                   for t in range(0, 63))
        self.assertGreater(peak, 0.18)
        self.assertLessEqual(peak, 0.19)

    def test_hop_wings_sweep_up(self):
        self.assertGreater(poses.pose_hop(0.31)["wing_pitch"], 0.6)

    def test_idle_is_gentle(self):
        for t in range(0, 480):
            pose = poses.pose_idle(t / 100)
            for channel, value in pose.items():
                self.assertLessEqual(abs(value), 0.09, channel)

    def test_sample_frame_counts(self):
        self.assertEqual(len(poses.sample("hop", fps=24)),
                         round(1.24 * 24))
        self.assertEqual(len(poses.sample("idle", fps=24)),
                         round(4.8 * 24))

    def test_recipes_cover_all_channels(self):
        for name, (fn, _seconds) in poses.RECIPES.items():
            self.assertEqual(set(fn(0.3)), set(poses.CHANNELS), name)


class CatalogTests(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual(catalog.slugify("Ember Dragon"), "ember-dragon")
        self.assertEqual(catalog.slugify("  Pip!! "), "pip")

    def test_entry_roundtrip_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            glb = os.path.join(tmp, "ember-dragon.glb")
            with open(glb, "wb") as fh:
                fh.write(b"glTF-fake-bytes" * 64)
            entry = catalog.build_entry(
                "Ember Dragon", "concept.webp", glb,
                {"verts": 10, "faces": 12}, ["root"],
                ["idle", "hop"], {"mesh_model": "x"})
            path = catalog.write_entry(tmp, entry)
            self.assertTrue(os.path.exists(path))
            loaded = catalog.read_entry(tmp, "ember-dragon")
            self.assertEqual(loaded["sha256"], entry["sha256"])
            self.assertTrue(catalog.verify_entry(loaded, glb))
            with open(glb, "ab") as fh:
                fh.write(b"tamper")
            self.assertFalse(catalog.verify_entry(loaded, glb))


class CutoutTests(unittest.TestCase):
    def test_cutout_on_synthetic_image(self):
        try:
            import numpy as np
            from PIL import Image
        except ImportError:
            self.skipTest("PIL/numpy not available")
        cutout = load("gab_cutout", "stages/prep/cutout.py")
        with tempfile.TemporaryDirectory() as tmp:
            src = np.full((60, 80, 3), 235, dtype=np.uint8)
            src[20:40, 30:50] = (200, 90, 20)  # "dragon" block
            inp = os.path.join(tmp, "in.png")
            out = os.path.join(tmp, "out.png")
            Image.fromarray(src).save(inp)
            stats = cutout.make_cutout(inp, out)
            self.assertGreater(stats["foreground_fraction"], 0.05)
            self.assertLess(stats["foreground_fraction"], 0.25)
            x0, y0, x1, y1 = stats["foreground_bbox"]
            self.assertAlmostEqual(x0, 30, delta=2)
            self.assertAlmostEqual(y0, 20, delta=2)
            alpha = np.asarray(Image.open(out))[:, :, 3]
            self.assertEqual(alpha[0, 0], 0)  # corner transparent
            cy, cx = alpha.shape[0] // 2, alpha.shape[1] // 2
            self.assertGreater(alpha[cy, cx], 200)  # centre opaque


class SkinPolicyTests(unittest.TestCase):
    BONES = ["root", "spine", "wing.L", "wing.R"]

    def per_bone(self, **overrides):
        base = {name: 100 for name in self.BONES}
        base.update(overrides)
        return base

    def test_healthy_heat_result_is_accepted(self):
        accepted, reasons = skin_policy.assess_heat(
            0.995, self.per_bone(), self.BONES, 0.83)
        self.assertTrue(accepted)
        self.assertEqual(reasons, [])

    def test_low_coverage_is_rejected_with_reason(self):
        accepted, reasons = skin_policy.assess_heat(
            0.42, self.per_bone(), self.BONES, 0.83)
        self.assertFalse(accepted)
        self.assertTrue(any("coverage" in r for r in reasons))

    def test_a_bone_with_no_verts_is_rejected_and_named(self):
        accepted, reasons = skin_policy.assess_heat(
            0.995, self.per_bone(**{"wing.R": 0}), self.BONES, 0.83)
        self.assertFalse(accepted)
        self.assertTrue(any("wing.R" in r for r in reasons))

    def test_wingtips_left_to_other_bones_is_rejected(self):
        accepted, reasons = skin_policy.assess_heat(
            0.995, self.per_bone(), self.BONES, 0.0)
        self.assertFalse(accepted)
        self.assertTrue(any("wingtip" in r for r in reasons))

    def test_multiple_failures_are_all_reported(self):
        accepted, reasons = skin_policy.assess_heat(
            0.0, self.per_bone(**{"wing.L": 0}), self.BONES, 0.0)
        self.assertFalse(accepted)
        self.assertGreaterEqual(len(reasons), 3)


class QuadrupedTemplateTests(unittest.TestCase):
    def test_fifteen_bones_with_four_two_segment_legs(self):
        bones = template.build_template("quadruped")
        names = [b.name for b in bones]
        self.assertEqual(len(names), 15)
        for leg in ("leg.FL", "leg2.FL", "leg.FR", "leg2.FR",
                    "leg.HL", "leg2.HL", "leg.HR", "leg2.HR"):
            self.assertIn(leg, names)
        for part in ("root", "spine", "hips", "neck", "head",
                     "tail.1", "tail.2"):
            self.assertIn(part, names)

    def test_spine_chain_runs_front_to_back(self):
        bones = {b.name: b for b in template.build_template("quadruped")}
        # Head end of the chain sits at the front (-Y), tail at back.
        self.assertLess(bones["head"].head[1], bones["neck"].head[1])
        self.assertLess(bones["neck"].head[1], bones["spine"].head[1])
        self.assertGreater(bones["tail.2"].tail[1],
                           bones["hips"].tail[1])

    def test_front_legs_parent_to_spine_hind_to_hips(self):
        bones = {b.name: b for b in template.build_template("quadruped")}
        self.assertEqual(bones["leg.FL"].parent, "spine")
        self.assertEqual(bones["leg.HR"].parent, "hips")
        self.assertEqual(bones["leg2.FL"].parent, "leg.FL")


class BipedTemplateTests(unittest.TestCase):
    def test_eleven_bones_without_ears_thirteen_with(self):
        plain = template.build_template("biped")
        self.assertEqual(len(plain), 11)
        self.assertNotIn("ear.L", [b.name for b in plain])
        eared = template.build_template("biped", ears=True)
        names = [b.name for b in eared]
        self.assertEqual(len(names), 13)
        self.assertIn("ear.R", names)

    def test_two_segment_arms_and_legs(self):
        bones = {b.name: b for b in template.build_template("biped")}
        self.assertEqual(bones["arm2.L"].parent, "arm.L")
        self.assertEqual(bones["leg2.R"].parent, "leg.R")
        self.assertEqual(bones["arm.L"].parent, "spine")
        self.assertEqual(bones["leg.L"].parent, "root")

    def test_new_templates_parents_precede_and_bounds(self):
        for name, options in (("quadruped", {}), ("biped", {}),
                              ("biped", {"ears": True})):
            bones = template.build_template(name, **options)
            names = [b.name for b in bones]
            self.assertEqual(len(names), len(set(names)))
            for bone in bones:
                if bone.parent:
                    self.assertLess(names.index(bone.parent),
                                    names.index(bone.name))
                for frac in bone.head + bone.tail:
                    self.assertGreaterEqual(frac, -0.55)
                    self.assertLessEqual(frac, 1.0)


class PerTemplatePoseTests(unittest.TestCase):
    def test_every_template_recipe_covers_exactly_its_channels(self):
        for tname, spec in poses.TEMPLATE_RECIPES.items():
            for clip, (fn, _seconds) in spec["recipes"].items():
                self.assertEqual(set(fn(0.3)), set(spec["channels"]),
                                 f"{tname}/{clip}")

    def test_quadruped_idle_is_gentle(self):
        for t in range(0, 480):
            for channel, value in poses.quad_idle(t / 100).items():
                self.assertLessEqual(abs(value), 0.12, channel)

    def test_quadruped_bounce_lifts_and_tucks(self):
        peak = max(poses.quad_bounce(t / 100)["root_y"]
                   for t in range(0, 125))
        self.assertGreater(peak, 0.08)
        self.assertLessEqual(peak, 0.12)
        apex = poses.quad_bounce(0.31)
        for leg in ("leg.FL", "leg.FR", "leg.HL", "leg.HR"):
            self.assertGreater(apex[leg], 0.1, leg)
            self.assertGreater(apex["leg2." + leg[-2:]], apex[leg])

    def test_biped_wave_raises_then_lowers(self):
        self.assertAlmostEqual(poses.biped_wave(0.0)["arm_wave"], 0.0)
        self.assertGreater(poses.biped_wave(1.2)["arm_wave"], 1.8)
        self.assertAlmostEqual(poses.biped_wave(2.4)["arm_wave"], 0.0)

    def test_biped_idle_is_gentle(self):
        for t in range(0, 480):
            for channel, value in poses.biped_idle(t / 100).items():
                self.assertLessEqual(abs(value), 0.09, channel)

    def test_sample_for_frame_counts(self):
        self.assertEqual(len(poses.sample_for("quadruped", "bounce")),
                         round(1.24 * 24))
        self.assertEqual(len(poses.sample_for("biped", "wave")),
                         round(2.4 * 24))
        self.assertEqual(poses.showcase_clip("quadruped"), "bounce")
        self.assertEqual(poses.showcase_clip("biped"), "wave")
        self.assertEqual(poses.showcase_clip("winged-creature"), "hop")


class SkinPolicyTipLabelTests(unittest.TestCase):
    def test_custom_tip_label_is_named_in_the_reason(self):
        accepted, reasons = skin_policy.assess_heat(
            0.995, {"root": 10}, ["root"], 0.1, tip_label="feet")
        self.assertFalse(accepted)
        self.assertTrue(any("feet" in r for r in reasons))

    def test_default_label_stays_wingtip(self):
        accepted, reasons = skin_policy.assess_heat(
            0.995, {"root": 10}, ["root"], 0.1)
        self.assertFalse(accepted)
        self.assertTrue(any("wingtip" in r for r in reasons))

    def test_good_tip_passes_for_other_templates(self):
        accepted, reasons = skin_policy.assess_heat(
            0.995, {"root": 10}, ["root"], 0.9, tip_label="hands")
        self.assertTrue(accepted)
        self.assertEqual(reasons, [])


class PropCatalogTests(unittest.TestCase):
    def test_prop_entry_records_no_rig(self):
        with tempfile.TemporaryDirectory() as tmp:
            glb = os.path.join(tmp, "treasure-chest.glb")
            with open(glb, "wb") as fh:
                fh.write(b"glTF-fake-bytes" * 32)
            entry = catalog.build_entry(
                "Treasure Chest", "chest.webp", glb,
                {"verts": 10, "faces": 12}, [], [],
                {"rigged": False, "rig_template": None,
                 "weight_method": None})
            self.assertEqual(entry["bones"], [])
            self.assertEqual(entry["actions"], [])
            self.assertFalse(entry["provenance"]["rigged"])
            self.assertIsNone(entry["provenance"]["weight_method"])
            path = catalog.write_entry(tmp, entry)
            loaded = catalog.read_entry(tmp, "treasure-chest")
            self.assertEqual(loaded["sha256"], entry["sha256"])
            self.assertTrue(os.path.exists(path))


class BridgeDisciplineTests(unittest.TestCase):
    def test_bridge_runner_requires_a_token(self):
        sys.path.insert(0, PROJECT)
        import gpu_bridge
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(gpu_bridge.BridgeError):
                gpu_bridge.BridgeRunner()


if __name__ == "__main__":
    unittest.main()
