"""Only development fixtures; these are not independent blind tasks."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from developmental_ai.outcome_skills import OutcomeSkills, check_frame, digest
from benchmarks.outcome_skills_benchmark import SkillWorld, learn, run, DEV, measure, TRAIN, TEST


class OutcomeSkillsTests(unittest.TestCase):
    def test_rotated_identifiers_and_public_frames(self):
        one = SkillWorld(17011, "assembly", "test", 90000)
        two = SkillWorld(17011, "assembly", "test", 90001)
        self.assertNotEqual([x["id"] for x in one.frame()["actions"]],
                            [x["id"] for x in two.frame()["actions"]])
        self.assertEqual(check_frame(one.frame()), one.frame())
        self.assertNotIn("requirements", one.frame())
        self.assertNotIn("true_recipe", one.frame())

    def test_observed_effects_and_candidate_prereqs(self):
        a=OutcomeSkills()
        a.observe("gather", [], ["ore"], True)
        a.observe("smelt", [], [], False)
        a.observe("smelt", ["ore"], ["ingot", "ore"], True)
        k=a.knowledge()
        self.assertEqual(k["gather"]["effects"], {"ore":1})
        self.assertEqual(k["smelt"]["possible_prerequisites"], ["ore"])
        self.assertEqual(k["smelt"]["effects"], {"ingot":1})

    def test_replay_and_digest_corruption_rejection(self):
        a=learn(17011)
        saved=a.record()
        restored=OutcomeSkills.restore(copy.deepcopy(saved))
        self.assertEqual(restored.record(), saved)
        bad=copy.deepcopy(saved)
        bad["state"]["knowledge"]["smelt"]["effects"]["ingot"]+=1
        bad["sha256"]=digest(bad["state"])
        with self.assertRaisesRegex(ValueError,"does not replay"):
            OutcomeSkills.restore(bad)

    def test_disk_checkpoint_survives_restart_and_corruption(self):
        original=learn(17011)
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"skills.json"
            original.save(path)
            restored=OutcomeSkills.load(path)
            self.assertEqual(original.record(),restored.record())
            a=SkillWorld(17011,"assembly","test",90000).frame()
            self.assertEqual(original.choose(a), restored.choose(a))
            path.write_text('{"invalid":true}',encoding="utf-8")
            with self.assertRaises(ValueError):OutcomeSkills.load(path)

    def test_rejects_oversized_observation(self):
        learner=OutcomeSkills()
        with self.assertRaises(ValueError):
            learner.observe("x"*65, [], ["valid"], True)
        with self.assertRaises(ValueError):
            learner.observe("valid", [], ["x"*65], True)

    def test_rejects_privileged_or_malformed_frames(self):
        f=SkillWorld(17011,"metal","test",90000).frame()
        for key in ("requirements", "hidden_phase", "private_state"):
            bad=copy.deepcopy(f); bad[key]="forged"
            with self.assertRaises(ValueError):check_frame(bad)
        bad=copy.deepcopy(f);bad["actions"].append(copy.deepcopy(bad["actions"][0]))
        with self.assertRaises(ValueError):check_frame(bad)
        bad=copy.deepcopy(f);bad["facts"]=[[]]
        with self.assertRaises(ValueError):check_frame(bad)

    def test_rejects_malformed_transitions(self):
        a=OutcomeSkills()
        for before,after,accepted in [([], ["a","b"],True),([], ["a"],False),(["a"],[],True), ([],[[]],True)]:
            with self.assertRaises(ValueError):a.observe("verb",before,after,accepted)

    def test_historical_transfer_succeeds_on_composed_goal_development_fixture(self):
        agent=learn(17011)
        before=json.dumps(agent.record(),sort_keys=True)
        outcomes=[run(17011,"assembly","test",90000+i,agent) for i in range(10)]
        self.assertTrue(all(x["success"] for x in outcomes))
        self.assertEqual(before,json.dumps(agent.record(),sort_keys=True))
        self.assertTrue(all(x["attempts"] <= 8 for x in outcomes))

    def test_difficult_unseen_chained_family_regression_is_visible(self):
        a=learn(17011)
        score=run(17011,"delivery","test",90000,a)
        self.assertFalse(score["success"])
        self.assertTrue(run(17011,"delivery","test",90000,policy="oracle")["success"])

    def test_frozen_dev_protocol_and_replay(self):
        self.assertEqual(TRAIN,("metal", "wood"))
        self.assertEqual(TEST,("assembly", "delivery"))
        with self.assertRaises(ValueError):measure((DEV[0],))


if __name__ == "__main__":
    unittest.main()
