import unittest

from stages import STAGES, get_stage, model_stages, stage_names


class StageRegistryTests(unittest.TestCase):
    def test_stage_order_is_the_pipeline_order(self):
        self.assertEqual(
            stage_names(),
            ["prep", "mesh", "texture", "segment", "rig", "animate",
             "catalog"])

    def test_stage_names_are_unique(self):
        names = stage_names()
        self.assertEqual(len(names), len(set(names)))

    def test_mesh_runs_before_texture(self):
        names = stage_names()
        self.assertLess(names.index("mesh"), names.index("texture"))

    def test_texture_runs_before_rig(self):
        names = stage_names()
        self.assertLess(names.index("texture"), names.index("rig"))

    def test_every_model_stage_is_an_isolated_gpu_process(self):
        # The owner's unload discipline: mesh and texture are separate
        # models, each in its own process, each on the GPU.
        for stage in model_stages():
            self.assertTrue(stage.isolated_process, stage.name)
            self.assertEqual(stage.device, "gpu", stage.name)

    def test_mesh_and_texture_are_distinct_stages(self):
        self.assertIsNot(get_stage("mesh"), get_stage("texture"))

    def test_unknown_stage_raises(self):
        with self.assertRaises(KeyError):
            get_stage("nope")

    def test_every_stage_has_a_summary(self):
        for stage in STAGES:
            self.assertTrue(stage.summary.strip(), stage.name)


if __name__ == "__main__":
    unittest.main()
