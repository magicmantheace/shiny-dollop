"""P5 campfire-pack tests: the snail and winged-quadruped rig plans,
the per-creature signature recipes and their selection plumbing, and
the gpu_bridge session-0 PowerShell transport helpers.

Hermetic: no Blender, no bridge, no GPU. The pose tests pin the
contracts the animate stage relies on (exact channel coverage, loop
closure, signature envelopes); the transport tests pin the quote-free
cmd contract the session-0 core requires.
"""

import importlib.util
import os
import sys
import unittest

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(name, rel):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(PROJECT, rel))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


poses = load("gab_poses_p5", "stages/animate/poses.py")
template = load("gab_template_p5", "stages/rig/template.py")
catalog = load("gab_catalog_p5", "stages/catalog/catalog.py")
gpu_bridge = load("gab_gpu_bridge_p5", "gpu_bridge.py")


class NewTemplateTests(unittest.TestCase):
    def test_snail_has_no_leg_bones(self):
        bones = template.build_template("snail")
        names = [b.name for b in bones]
        self.assertEqual(len(names), 9)
        self.assertFalse(any(n.startswith("leg") for n in names))
        self.assertIn("shell", names)
        self.assertEqual(
            {b.name: b.parent for b in bones}["shell"], "root")

    def test_winged_quadruped_is_quadruped_plus_wings(self):
        plain = template.build_template("winged-quadruped")
        names = [b.name for b in plain]
        self.assertEqual(len(names), 19)  # 15 quadruped + 4 wing
        for wing in ("wing.L", "wing2.L", "wing.R", "wing2.R"):
            self.assertIn(wing, names)
        eared = template.build_template("winged-quadruped", ears=True)
        self.assertEqual(len(eared), 21)

    def test_new_templates_parents_precede_and_bounds(self):
        for name, options in (("snail", {}),
                              ("winged-quadruped", {}),
                              ("winged-quadruped", {"ears": True})):
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


class SignatureRegistryTests(unittest.TestCase):
    def test_every_signature_covers_exactly_its_channels(self):
        for tname, sigs in poses.SIGNATURES.items():
            spec = poses.template_spec(tname)
            for clip, (fn, _seconds) in sigs.items():
                self.assertEqual(set(fn(0.3)), set(spec["channels"]),
                                 f"{tname}/{clip}")

    def test_recipes_for_default_is_the_historical_set(self):
        for tname, spec in poses.TEMPLATE_RECIPES.items():
            self.assertEqual(poses.recipes_for(tname),
                             dict(spec["recipes"]), tname)
            self.assertEqual(
                poses.recipes_for(tname, spec["showcase"]),
                dict(spec["recipes"]), tname)

    def test_recipes_for_signature_swaps_showcase_only(self):
        out = poses.recipes_for("biped", "bow")
        self.assertEqual(sorted(out), ["bow", "idle", "run", "walk"])
        out = poses.recipes_for("winged-quadruped", "fan")
        self.assertEqual(sorted(out), ["fan", "idle", "run", "walk"])
        out = poses.recipes_for("winged-creature", "headturn")
        self.assertEqual(sorted(out),
                         ["headturn", "idle", "run", "walk"])

    def test_unknown_signature_raises(self):
        with self.assertRaises(KeyError):
            poses.recipes_for("biped", "cartwheel")


class SignatureShapeTests(unittest.TestCase):
    def test_fan_raises_wings_and_flutters(self):
        fn, seconds = poses.SIGNATURES["winged-quadruped"]["fan"]
        self.assertAlmostEqual(fn(0.0)["wing_pitch"], 0.0, places=6)
        spread = fn(1.4)["wing_pitch"]
        self.assertGreater(spread, 0.7)
        # Flutter: the spread wing oscillates while held.
        samples = [fn(0.6 + i * 0.05)["wing_pitch"] for i in range(32)]
        self.assertGreater(max(samples) - min(samples), 0.15)
        self.assertAlmostEqual(fn(seconds)["wing_pitch"],
                               fn(0.0)["wing_pitch"], places=6)

    def test_headturn_yaws_both_ways(self):
        fn, _ = poses.SIGNATURES["winged-creature"]["headturn"]
        values = [fn(i * 0.05)["head_yaw"] for i in range(65)]
        self.assertGreater(max(values), 0.45)
        self.assertLess(min(values), -0.45)

    def test_biped_bounce_lifts_like_the_quadruped_one(self):
        fn, _ = poses.SIGNATURES["biped"]["bounce"]
        peak = max(fn(t / 100)["root_y"] for t in range(0, 125))
        self.assertGreater(peak, 0.08)
        self.assertLessEqual(peak, 0.13)

    def test_scream_raises_both_arms_then_waves(self):
        fn, _ = poses.SIGNATURES["biped"]["scream"]
        hold = fn(1.5)
        self.assertGreater(hold["arm_sway"], 1.3)   # both arms up
        self.assertLess(hold["head_pitch"], -0.25)  # head thrown back
        self.assertAlmostEqual(fn(0.0)["arm_sway"], 0.0, places=6)

    def test_bow_dips_the_head(self):
        fn, _ = poses.SIGNATURES["biped"]["bow"]
        self.assertGreater(fn(1.3)["head_pitch"], 0.7)
        self.assertAlmostEqual(fn(0.0)["head_pitch"], 0.0, places=6)

    def test_shiver_is_small_and_fast(self):
        fn, seconds = poses.SIGNATURES["quadruped"]["shiver"]
        for i in range(65):
            pose = fn(i * seconds / 64)
            for channel, value in pose.items():
                self.assertLessEqual(abs(value), 0.25, channel)
        sway = [fn(i * 0.02)["sway"] for i in range(80)]
        self.assertGreater(max(sway), 0.03)
        self.assertLess(min(sway), -0.03)

    def test_wiggle_travels_to_the_tail(self):
        fn, seconds = poses.SIGNATURES["quadruped"]["wiggle"]
        peak = max(fn(i * seconds / 96)["tail_yaw"] for i in range(97))
        self.assertGreater(peak, 0.3)
        # Phase lag: at t=0 the tail has barely started while the
        # root sway is already moving.
        self.assertGreater(abs(fn(0.3)["sway"]), abs(fn(0.3)["tail_yaw"]))


class SnailPoseTests(unittest.TestCase):
    def test_snail_has_no_walk_or_run(self):
        recipes = poses.template_spec("snail")["recipes"]
        self.assertNotIn("walk", recipes)
        self.assertNotIn("run", recipes)
        self.assertEqual(poses.LOCOMOTION["snail"], ("glide",))

    def test_glide_is_a_travelling_wave(self):
        fn, seconds = poses.recipe_fn("snail", "glide")
        # Rear-to-front phase lag: at a fixed t the three undulate
        # channels are at clearly different phases.
        pose = fn(0.4)
        values = [pose[f"undulate.{i}"] for i in (1, 2, 3)]
        self.assertGreater(max(values) - min(values), 0.08)
        start, end = fn(0.0), fn(seconds)
        for channel in poses.SNAIL_CHANNELS:
            self.assertAlmostEqual(start[channel], end[channel],
                                   places=6, msg=channel)

    def test_retract_envelope_folds_and_releases(self):
        fn, seconds = poses.recipe_fn("snail", "retract")
        self.assertAlmostEqual(fn(0.0)["retract"], 0.0, places=6)
        self.assertAlmostEqual(fn(1.5)["retract"], 1.0, places=6)
        self.assertAlmostEqual(fn(seconds)["retract"], 0.0, places=6)


class TransportTests(unittest.TestCase):
    def test_wrap_stops_on_errors_and_propagates_native_exit(self):
        body = gpu_bridge.wrap_powershell_script("hostname")
        self.assertIn("$ErrorActionPreference = 'Stop'", body)
        self.assertIn("hostname", body)
        self.assertIn("exit $LASTEXITCODE", body)

    def test_ps_file_command_is_quote_free_full_path(self):
        cmd = gpu_bridge.ps_file_command(
            r"D:\asset-forge-lab\scripts\gab_ps_1_1.ps1")
        self.assertNotIn('"', cmd)
        self.assertIn(r"C:\Windows\System32\WindowsPowerShell"
                      r"\v1.0\powershell.exe", cmd)
        self.assertIn("-File", cmd)

    def test_ps_file_command_rejects_spacey_paths(self):
        with self.assertRaises(gpu_bridge.BridgeError):
            gpu_bridge.ps_file_command(r"D:\my lab\script.ps1")


class CatalogClipsTests(unittest.TestCase):
    def test_build_entry_carries_clips_when_given(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "x.glb")
            with open(path, "wb") as fh:
                fh.write(b"glTF-fake")
            entry = catalog.build_entry(
                "Test Critter", "concept.webp", path,
                {"verts": 1, "faces": 1}, ["root"], ["idle"], {},
                clips={"idle": {"seconds": 4.79, "frames": 115,
                                "fps": 24}})
            self.assertEqual(entry["clips"]["idle"]["frames"], 115)
            plain = catalog.build_entry(
                "Test Critter", "concept.webp", path,
                {"verts": 1, "faces": 1}, ["root"], ["idle"], {})
            self.assertNotIn("clips", plain)


if __name__ == "__main__":
    unittest.main()
