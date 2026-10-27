"""Cross-family, privilege-denying contract and deterministic replay tests."""
import copy
import io
import json
import unittest
from developmental_ai.environment_api import EnvironmentSession, FAMILIES, digest
from developmental_ai.environment_service import EnvironmentService, SERVICE_SCHEMA, serve


class EnvironmentApiTests(unittest.TestCase):
    def test_three_families_have_only_typed_observations(self):
        for family in FAMILIES:
            cfg = {"family": family, "seed": 2749, "split": "test", "index": 60011}
            if family == "delayed": cfg["variant"] = "long"
            session = EnvironmentSession(**cfg)
            frame = session.frame()
            self.assertEqual(frame["scope"], "simulation-only")
            self.assertEqual(frame["source"], "simulation")
            self.assertNotIn("position", frame["observation"])
            self.assertNotIn("correct_action", frame["observation"])
            self.assertNotIn("walls", frame["observation"])
            self.assertEqual(frame["available_actions"], [4] if family == "delayed" else [0,1,2,3,4])
            self.assertEqual(session.step(frame["available_actions"][0], expected_tick=0)["frame"]["tick"], 1)

    def test_all_families_restore_and_replay_exact(self):
        for family in FAMILIES:
            cfg = {"family": family, "seed": 17, "split": "test", "index": 60019}
            if family == "delayed": cfg["variant"] = "short"
            session = EnvironmentSession(**cfg)
            for _ in range(5):
                if session.done: break
                session.step(session.frame()["available_actions"][0], expected_tick=session.tick)
            restored = EnvironmentSession.restore(session.checkpoint())
            self.assertEqual(restored.checkpoint(), session.checkpoint())
            if not session.done:
                x = session.frame()["available_actions"][0]
                self.assertEqual(session.step(x, expected_tick=session.tick), restored.step(x, expected_tick=restored.tick))
                self.assertEqual(restored.checkpoint(), session.checkpoint())

    def test_replay_rejects_even_rehashed_forged_observations(self):
        session = EnvironmentSession("occluded", 17, "train", 0)
        session.step(0, expected_tick=0)
        wrong = session.checkpoint()
        wrong["state"]["entries"][0]["result"]["frame"]["observation"]["blocked"] = 9999
        wrong["digest"] = digest(wrong["state"])
        with self.assertRaises(ValueError): EnvironmentSession.restore(wrong)

    def test_rejects_privileged_fields_stale_commands_and_wrong_variant(self):
        with self.assertRaises(ValueError): EnvironmentSession("grid", 17, "test", 0, variant="long")
        with self.assertRaises(ValueError): EnvironmentSession("grid", True, "test", 0)
        s = EnvironmentSession("grid", 17, "test", 1)
        with self.assertRaises(ValueError): s.step(0, expected_tick=1)
        with self.assertRaises(ValueError): s.step(True, expected_tick=0)
        with self.assertRaises(ValueError): s.step(99, expected_tick=0)
        with self.assertRaises(ValueError): EnvironmentSession.restore({"state":{},"digest":"x"})

    def test_delayed_action_mask_changes_only_after_cue_and_distractors(self):
        session = EnvironmentSession("delayed", 17, "test", 3, "short")
        while session.frame()["available_actions"] == [4]:
            session.step(4, expected_tick=session.tick)
        self.assertEqual(session.frame()["available_actions"], [0,1,2,3])
        self.assertIsNone(session.frame()["observation"]["token"])
        self.assertTrue(session.step(0, expected_tick=session.tick)["frame"]["done"])

    def test_service_protocol_replay_and_action_binding(self):
        service = EnvironmentService()
        def req(op, **kwargs):
            return service.handle({"schema": SERVICE_SCHEMA,"request_id":"abc-1","op":op,**kwargs})["result"]
        frame = req("start",config={"family":"grid","seed":17,"split":"train","index":1})["frame"]
        self.assertEqual(frame["tick"],0)
        with self.assertRaises(ValueError): req("step",action=1,expected_tick=3)
        req("step",action=1,expected_tick=0)
        checkpoint = req("checkpoint")["checkpoint"]
        req("close")
        self.assertEqual(req("restore",checkpoint=checkpoint)["frame"]["tick"],1)
        with self.assertRaises(ValueError): service.handle({"schema":SERVICE_SCHEMA,"request_id":"x","op":"run_shell", "command":"whoami"})

    def test_stdio_service_handles_invalid_input_without_exiting(self):
        valid = json.dumps({"schema":SERVICE_SCHEMA,"request_id":"t1","op":"start","config":{"family":"delayed","seed":4,"split":"test","index":0,"variant":"short"}})
        target = io.StringIO()
        serve(io.BytesIO(("not-json\n"+valid+"\n").encode()), target)
        rows = [json.loads(t) for t in target.getvalue().splitlines()]
        self.assertEqual(rows[0]["error"]["code"],"invalid_request")
        self.assertEqual(rows[1]["request_id"],"t1")

if __name__ == "__main__":unittest.main()
