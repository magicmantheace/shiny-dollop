"""Joint latent world/position filter; only ordinary observation access."""
import copy
import math
import sqlite3
import tempfile
import unittest
from pathlib import Path

from developmental_ai.adaptive_dynamics import DynamicsModel
from developmental_ai.mixture_navigation import MixtureNavigator, MixtureCheckpoint, digest, probe_priors
from developmental_ai.online_dynamics import forward_backward, initial_model, trajectory


class MixtureNavigationTests(unittest.TestCase):
    def setUp(self):
        self.models = {"first": initial_model(), "second": DynamicsModel()}
        self.history = trajectory(17, "test", 120, "standard", "fixed", 12)

    def make(self):
        h = self.history
        return MixtureNavigator(h["initial"], (h["initial"]+3)%h["n"], h["n"], self.models)

    def test_single_model_matches_forward_likelihood_and_full_posterior(self):
        h = self.history
        nav = MixtureNavigator(h["initial"], 0, h["n"], {"first": self.models["first"]})
        for cmd, odo, marker in h["observations"]:
            nav.advance(0 if cmd==-1 else 1, {"beacon": None, "odometry": odo, "landmark": marker})
        self.assertAlmostEqual(nav.log_evidence, forward_backward(self.models["first"], h), places=9)
        self.assertAlmostEqual(sum(nav.probs), 1, places=9)

    def test_two_model_marginal_evidence_and_weights(self):
        h = self.history
        nav = self.make()
        for cmd, odo, marker in h["observations"]:
            nav.advance(0 if cmd == -1 else 1, {"beacon": None, "odometry": odo, "landmark": marker})
        a, b = [forward_backward(m, h) for m in self.models.values()]
        correct = math.log((math.exp(a) + math.exp(b)) / 2)
        self.assertAlmostEqual(nav.log_evidence, correct, places=8)
        self.assertAlmostEqual(nav.weights["first"], math.exp(a)/(math.exp(a)+math.exp(b)), places=8)
        self.assertAlmostEqual(sum(nav.probs), 1., places=8)

    def test_restart_exact_across_sensor_steps(self):
        h=self.history
        nav=self.make()
        for cmd,odo,lm in h["observations"][:5]:
            nav.advance(0 if cmd==-1 else 1,{"beacon":None,"odometry":odo,"landmark":lm})
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"brain.db"
            with MixtureCheckpoint(path) as db:
                self.assertIsNone(db.load(self.models))
                db.save(nav)
            with MixtureCheckpoint(path) as db:
                restarted=db.load(self.models)
            self.assertEqual(nav.snapshot(),restarted.snapshot())
            for cmd,odo,lm in h["observations"][5:]:
                data={"beacon":None,"odometry":odo,"landmark":lm}
                nav.advance(0 if cmd==-1 else 1,data)
                restarted.advance(0 if cmd==-1 else 1,data)
            self.assertEqual(nav.snapshot(),restarted.snapshot())

    def test_corrupt_posterior_refused_even_with_updated_digest(self):
        nav=self.make()
        s=nav.snapshot()
        s["body"]["joint"]["first"][0]=5.
        s["digest"]=digest(s["body"])
        with self.assertRaises(ValueError):
            MixtureNavigator.restore(s,self.models)

    def test_changed_model_rejected(self):
        nav=self.make()
        from developmental_ai.online_dynamics import fit
        model,_=fit([trajectory(17,"train",i) for i in range(2)],iterations=1)
        with self.assertRaises(ValueError):
            MixtureNavigator.restore(nav.snapshot(),{"first":model,"second":self.models["second"]})

    def test_rejects_privileged_data_and_invalid_probabilities(self):
        nav=self.make()
        with self.assertRaises(ValueError):
            nav.advance(0,{"beacon":None,"odometry":0,"landmark":None,"position":1})
        with self.assertRaises(ValueError):
            nav.advance(0,{"beacon":None,"odometry":2,"landmark":None})
        with self.assertRaises(ValueError):
            nav.advance(True,{"beacon":None,"odometry":0,"landmark":None})
        with self.assertRaises(ValueError):
            MixtureNavigator(0,0,9,{"first":self.models["first"],"invalid name":self.models["second"]})
        with self.assertRaises(ValueError):
            nav.select(threshold=1.2)

    def test_normalized_posterior_and_finite_log_likelihood(self):
        nav=self.make()
        for cmd,odo,lm in self.history["observations"]:
            nav.advance(0 if cmd==-1 else 1,{"beacon":None,"odometry":odo,"landmark":lm})
            self.assertAlmostEqual(sum(nav.weights.values()),1,places=9)
            self.assertGreaterEqual(min(nav.probs),0)
            self.assertTrue(math.isfinite(nav.log_evidence))
            self.assertIn(nav.heuristic(),(0,1,2))

    def test_probe_prior_is_normalized_and_only_observational(self):
        histories=[trajectory(17,"test",i) for i in range(5)]
        priors=probe_priors(self.models,histories)
        self.assertEqual(set(priors),set(self.models))
        self.assertAlmostEqual(sum(priors.values()),1.)
        nav=MixtureNavigator(self.history["initial"],0,self.history["n"],self.models,priors=priors)
        self.assertEqual(nav.weights,priors)
        tampered=dict(histories[0]);tampered["regime"]="standard"
        with self.assertRaises(ValueError):
            probe_priors(self.models,[tampered])

    def test_priors_refuse_invalid_and_restore_exactly(self):
        h=self.history
        with self.assertRaises(ValueError):
            MixtureNavigator(h["initial"],0,h["n"],self.models,priors={"first":1.1,"second":-.1})
        nav=MixtureNavigator(h["initial"],0,h["n"],self.models,priors={"first":.7,"second":.3})
        self.assertEqual(MixtureNavigator.restore(nav.snapshot(),self.models).snapshot(),nav.snapshot())

    def test_database_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"checkpoint.db"
            with MixtureCheckpoint(path) as cp:
                cp.save(self.make())
            with sqlite3.connect(path) as db:
                db.execute("UPDATE mixture_state SET record='{}'")
            with MixtureCheckpoint(path) as cp:
                with self.assertRaises(ValueError):
                    cp.load(self.models)

if __name__ == "__main__":
    unittest.main()
