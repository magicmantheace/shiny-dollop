"""Navigation state and boundaries; no simulator truth enters controller."""
import copy
import sqlite3
import tempfile
import unittest
from pathlib import Path

from developmental_ai.online_dynamics import trajectory
from developmental_ai.mixed_experience import fit_mixed
from developmental_ai.closed_loop_adaptation import (
    NavigationSession, NavigationCheckpoint, models_from_proposal, _digest,
)
from developmental_ai.switching_belief import calibrate_hazard


class ClosedLoopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        training = [trajectory(17, "train", i, "standard", "fixed") for i in range(20)]
        validation = [trajectory(17, "train", 10000+i, "standard", "fixed") for i in range(10)]
        cls.proposal = fit_mixed(training, validation, seed=17, iterations=1, rounds=1, min_group=5)
        cls.models = models_from_proposal(cls.proposal)
        # No simulator hidden positions or regime labels; only sensor history.
        cls.streams = [{"initial": h["initial"], "goal": 0, "n": h["n"],
                        "observations": [[0 if cmd == -1 else 1,
                            {"beacon": None, "odometry": odo, "landmark": mark}]
                            for cmd, odo, mark in h["observations"]]}
                       for h in [trajectory(17, "train", 40000+i) for i in range(2)]]
        cls.receipt = calibrate_hazard(cls.models, cls.streams, candidates=(0., .01))

    def make(self, mode="switching"):
        return NavigationSession(self.proposal, 0, 4, 9, self.receipt, mode=mode)

    def observation(self):
        return {"beacon": None, "odometry": 0, "landmark": None}

    def test_requires_calibration_and_rejects_unmatched_bank(self):
        with self.assertRaises(ValueError):
            NavigationSession(self.proposal, 0, 4, 9)
        fake = copy.deepcopy(self.receipt)
        fake["state"]["hazard"] = .2
        with self.assertRaises(ValueError):
            NavigationSession(self.proposal, 0, 4, 9, fake)

    def test_action_is_only_suggestion_and_must_be_acknowledged(self):
        s = self.make()
        a = s.select_action()
        self.assertEqual(a, s.select_action())
        with self.assertRaises(ValueError):
            s.advance(2 if a != 2 else 0, self.observation())
        self.assertEqual(s.nav.steps, 0)
        reply = s.advance(a, self.observation())
        self.assertEqual(s.nav.steps, 1)
        self.assertIn("position_belief", reply)
        self.assertNotIn("true_position", reply)
        with self.assertRaises(ValueError):
            s.advance(a, self.observation())

    def test_rejects_privileged_fields_without_mutation(self):
        s = self.make()
        a = s.select_action()
        with self.assertRaises(ValueError):
            s.advance(a, {**self.observation(), "true_position": 3})
        self.assertEqual(s.nav.steps, 0)
        self.assertEqual(s.pending, a)

    def test_static_mode_hazard_is_zero(self):
        s = self.make("static")
        self.assertEqual(s.nav.hazard, 0.)
        self.assertIsNone(s.receipt_digest)

    def test_restart_exact_pending_and_after_step(self):
        s = self.make()
        first = s.select_action()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"session.db"
            with NavigationCheckpoint(path) as db:
                db.save(s)
            with NavigationCheckpoint(path) as db:
                restored = db.load(self.proposal, self.receipt)
            self.assertEqual(restored.snapshot(), s.snapshot())
            restored.advance(first, self.observation())
            s.advance(first, self.observation())
            self.assertEqual(restored.snapshot(), s.snapshot())
            with NavigationCheckpoint(path) as db:
                db.save(s)
            with NavigationCheckpoint(path) as db:
                restarted = db.load(self.proposal, self.receipt)
            self.assertEqual(restarted.snapshot(), s.snapshot())

    def test_snapshot_is_detached_from_later_advances(self):
        # Regression: snapshot() stored the live log list, so advancing
        # the session afterwards silently grew the saved snapshot's log
        # and its digest stopped matching -- restore() then failed with
        # 'invalid or altered session snapshot' even though the caller
        # never modified the record.
        s = self.make()
        s.advance(s.select_action(), self.observation())
        saved = s.snapshot()
        s.advance(s.select_action(), self.observation())
        self.assertEqual(len(saved["state"]["log"]), 1)
        restored = NavigationSession.restore(saved, self.proposal, self.receipt)
        self.assertEqual(restored.snapshot(), saved)
        self.assertEqual(restored.nav.steps, 1)
        self.assertEqual(len(restored.log), 1)

    def test_reject_forged_posterior_even_with_new_digest(self):
        s = self.make()
        a=s.select_action()
        s.advance(a, self.observation())
        forged = s.snapshot()
        n = forged["state"]["navigator"]["state"]["joint"]
        name = next(iter(n))
        n[name][0] += .3
        forged["state"]["navigator"]["sha256"] = _digest(forged["state"]["navigator"]["state"])
        forged["sha256"] = _digest(forged["state"])
        with self.assertRaises(ValueError):
            NavigationSession.restore(forged, self.proposal, self.receipt)

    def test_cannot_act_after_terminal(self):
        s = self.make()
        action = s.select_action()
        s.advance(action, self.observation(), done=True)
        with self.assertRaises(ValueError):
            s.select_action()

    def test_source_proposal_cannot_mutate_active_navigator(self):
        session = self.make()
        original = session.nav.models["h0"].offsets["9"]
        model = self.proposal.models[0]
        was = model.offsets["9"]
        try:
            model.offsets["9"] = (was + 1) % 9
            self.assertEqual(session.nav.models["h0"].offsets["9"], original)
        finally:
            model.offsets["9"] = was

    def test_live_model_mutation_fails_closed(self):
        session = self.make()
        session.nav.models["h0"].offsets["9"] = (session.nav.models["h0"].offsets["9"]+1) % 9
        with self.assertRaises(ValueError):
            session.select_action()

    def test_db_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            dbpath = Path(d)/"state.db"
            with NavigationCheckpoint(dbpath) as db:
                db.save(self.make())
            with sqlite3.connect(dbpath) as db:
                db.execute("UPDATE adaptation_state SET record = '{}' ")
            with NavigationCheckpoint(dbpath) as db:
                with self.assertRaises(ValueError):
                    db.load(self.proposal, self.receipt)

if __name__=="__main__": unittest.main()
