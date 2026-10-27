"""Bounded per-observation regime transition without privileged inputs."""
import copy
import math
import sqlite3
import tempfile
import unittest
from pathlib import Path

from developmental_ai.online_dynamics import forward_backward, trajectory
from developmental_ai.structured_landmarks import StructuredModel
from developmental_ai.switching_belief import SwitchingBelief, SwitchingCheckpoint, _digest, calibrate_hazard, verified_hazard


def models():
    original=StructuredModel()
    shifted=StructuredModel(offsets={"9":2,"11":2})
    return {"old":original,"changed":shifted}


def records():
    h=trajectory(17,"test",777)
    return h, [(0 if cmd == -1 else 1,{"beacon":None,"odometry":odo,"landmark":lm})
                for cmd,odo,lm in h["observations"]]


class SwitchingBeliefTests(unittest.TestCase):
    def test_single_model_filter_matches_latent_likelihood(self):
        h,events=records()
        m={"old":models()["old"]}
        nav=SwitchingBelief(h["initial"],3,h["n"],m,hazard=.2)
        for act,ob in events:nav.advance(act,ob)
        self.assertAlmostEqual(nav.log_evidence,forward_backward(m["old"],h),places=9)
        self.assertAlmostEqual(sum(nav.probs),1.)

    def test_zero_hazard_equals_stationary_mixture_evidence(self):
        h,events=records()
        from developmental_ai.mixed_experience import mixture_log_likelihood
        m=models();nav=SwitchingBelief(h["initial"],3,h["n"],m,hazard=0)
        for act,ob in events:nav.advance(act,ob)
        self.assertAlmostEqual(nav.log_evidence,mixture_log_likelihood(list(m.values()),h),places=9)

    def test_hazard_mixes_model_probabilities_without_erasing_location(self):
        m=models()
        nav=SwitchingBelief(0,3,9,m,hazard=.25,priors={"old":1.,"changed":0.})
        nav.advance(2,{"beacon":None,"odometry":0,"landmark":None})
        self.assertEqual(nav.steps,1)
        self.assertAlmostEqual(sum(nav.weights.values()),1.)
        self.assertGreater(nav.weights["changed"],0.)
        self.assertGreater(nav.weights["old"],0.)
        self.assertAlmostEqual(sum(nav.probs),1.)

    def test_exact_sqlite_restart_under_switching(self):
        h,events=records();m=models()
        nav=SwitchingBelief(h["initial"],3,h["n"],m,hazard=.07)
        for act,ob in events[:4]:nav.advance(act,ob)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"state.db"
            with SwitchingCheckpoint(path) as db:
                self.assertIsNone(db.load(m))
                db.save(nav)
            with SwitchingCheckpoint(path) as db:restored=db.load(m,expected_hazard=.07)
            self.assertEqual(nav.snapshot(),restored.snapshot())
            for act,ob in events[4:]:
                nav.advance(act,ob);restored.advance(act,ob)
            self.assertEqual(nav.snapshot(),restored.snapshot())

    def test_bank_or_hazard_change_rejected_even_with_same_shape(self):
        h,_=records();m=models()
        snap=SwitchingBelief(h["initial"],3,h["n"],m,hazard=.1).snapshot()
        with self.assertRaises(ValueError):SwitchingBelief.restore(snap,m,expected_hazard=.2)
        changed=models();changed["old"].offsets["9"]=5
        with self.assertRaises(ValueError):SwitchingBelief.restore(snap,changed)

    def test_rejects_corruption_and_privileged_fields(self):
        nav=SwitchingBelief(1,3,9,models(),hazard=.1)
        for ob in ({"beacon":None,"odometry":1,"landmark":0,"position":1},
                   {"beacon":None,"odometry":0,"landmark":2},
                   {"beacon":[0,3],"odometry":0,"landmark":None}):
            with self.assertRaises(ValueError):nav.advance(0,ob)
        self.assertEqual(nav.steps,0)
        snap=nav.snapshot();snap["state"]["steps"]=-1;snap["sha256"]=_digest(snap["state"])
        with self.assertRaises(ValueError):SwitchingBelief.restore(snap,models())
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"s.db"
            with SwitchingCheckpoint(path) as db:db.save(nav)
            with sqlite3.connect(path) as db:db.execute("UPDATE switching_state SET record='{}'")
            with SwitchingCheckpoint(path) as db:
                with self.assertRaises(ValueError):db.load(models())

    def test_model_bound_calibration_is_reproducible_and_observation_only(self):
        h,events=records();m=models()
        stream={"initial":h["initial"],"goal":3,"n":h["n"],
                "observations":[[a,ob] for a,ob in events]}
        copy2=copy.deepcopy(stream)
        copy2["observations"]=copy2["observations"][:5]
        r=calibrate_hazard(m,[stream,copy2],candidates=(0.,.04))
        self.assertEqual(r,calibrate_hazard(m,[stream,copy2],candidates=(0.,.04)))
        self.assertEqual(verified_hazard(r,m),r["state"]["hazard"])
        tampered=copy.deepcopy(r)
        tampered["state"]["hazard"]=.2
        with self.assertRaises(ValueError):verified_hazard(tampered,m)
        altered=models();altered["old"].offsets["9"]=4
        with self.assertRaises(ValueError):verified_hazard(r,altered)
        contaminated=copy.deepcopy(stream);contaminated["truth"]="original"
        with self.assertRaises(ValueError):calibrate_hazard(m,[stream,contaminated])
        with self.assertRaises(ValueError):calibrate_hazard(m,[stream,copy.deepcopy(stream)])

    def test_invalid_hazards_and_priors_fail_closed(self):
        for h in (-.1,.31,float("nan"),True):
            with self.assertRaises(ValueError):SwitchingBelief(0,3,9,models(),hazard=h)
        for priors in ({"old":1.}, {"old":1.1,"changed":-.1},
                       {"old":float("nan"),"changed":0}):
            with self.assertRaises(ValueError):SwitchingBelief(0,3,9,models(),priors=priors)
        nav=SwitchingBelief(0,3,9,models())
        with self.assertRaises(ValueError):nav.selected(-.1)
        self.assertIn(nav.heuristic(),(0,1,2))

if __name__=="__main__": unittest.main()
