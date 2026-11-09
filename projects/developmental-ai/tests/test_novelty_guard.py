"""Bounded model-surprise diagnostics; no privilege escalation."""
import copy
import unittest

from developmental_ai.online_dynamics import trajectory
from developmental_ai.structured_landmarks import fit_structured
from developmental_ai.novelty_guard import NoveltyGuard, calibrate_guard, verify_guard, _profile, _digest


def record(seed, idx, split="train", *, noise="standard", layout="fixed"):
    h=trajectory(seed,split,idx,noise,layout)
    return {"initial":h["initial"], "goal":0, "n":h["n"],
            "observations":[[0 if cmd==-1 else 1, {"beacon":None,"odometry":odo,"landmark":mark}]
                            for cmd,odo,mark in h["observations"]]}


class NoveltyGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        h=[trajectory(17,"train",i) for i in range(12)]
        cls.models={"a": fit_structured(h,iterations=1)[0]}
        cls.ref=[record(17,40000+i) for i in range(25)]
        cls.receipt=calibrate_guard(cls.models,cls.ref,alpha=.1)

    def test_rejects_duplicate_or_privileged_references(self):
        with self.assertRaises(ValueError):calibrate_guard(self.models, [self.ref[0]]*25)
        privileged=copy.deepcopy(self.ref);privileged[0]["true_position"]=2
        with self.assertRaises(ValueError):calibrate_guard(self.models, privileged)

    def test_bad_receipt_fails_closed_even_after_resigning_checksum(self):
        bad=copy.deepcopy(self.receipt);bad["state"]["bank"]["a"]="0"*64
        bad["sha256"]=_digest(bad["state"])
        with self.assertRaises(ValueError):verify_guard(bad,self.models)
        bad=copy.deepcopy(self.receipt);bad["state"]["threshold"]=-1
        bad["sha256"]=_digest(bad["state"])
        with self.assertRaises(ValueError):verify_guard(bad,self.models)

    def test_exact_restart_and_latching(self):
        h=record(17,90001,split="test")
        a=NoveltyGuard(h["initial"],h["goal"],h["n"],self.models,self.receipt)
        for act,ob in h["observations"][:5]:a.advance(act,ob)
        b=NoveltyGuard.restore(a.snapshot(),self.models,self.receipt)
        self.assertEqual(a.snapshot(),b.snapshot())
        for act,ob in h["observations"][5:]:
            self.assertEqual(a.advance(act,ob), b.advance(act,ob))
        self.assertEqual(a.snapshot(),b.snapshot())

    def test_forged_recomputed_digest_cannot_alter_alert(self):
        h=record(17,90001,split="test")
        a=NoveltyGuard(h["initial"],h["goal"],h["n"],self.models,self.receipt)
        for act,ob in h["observations"]:a.advance(act,ob)
        snap=a.snapshot();snap["state"]["alarm"]=not a.alarm
        snap["sha256"]=_digest(snap["state"])
        with self.assertRaises(ValueError):NoveltyGuard.restore(snap,self.models,self.receipt)

    def test_sensor_truth_forbidden_without_mutation(self):
        h=record(17,90002,split="test")
        a=NoveltyGuard(h["initial"],h["goal"],h["n"],self.models,self.receipt)
        event=copy.deepcopy(h["observations"][0]);event[1]["regime"]="changed"
        with self.assertRaises(ValueError):a.advance(*event)
        self.assertEqual(a.nav.steps,0)
        self.assertEqual(a.log,[])

    def test_model_binding_and_mutation(self):
        h=record(17,90003,split="test")
        a=NoveltyGuard(h["initial"],h["goal"],h["n"],self.models,self.receipt)
        altered=copy.deepcopy(self.models); altered["a"].counts if False else None
        altered["a"].offsets["9"] if False else None
        altered["a"].roles["9"] if False else None
        altered["a"].motion[0][0] += 1.
        with self.assertRaises(ValueError):NoveltyGuard.restore(a.snapshot(),altered,self.receipt)

    def test_prefix_calibration_matches_monitored_maximum(self):
        h=record(17,90004,split="test")
        x=_profile(self.models,h,0)
        g=NoveltyGuard(h["initial"],h["goal"],h["n"],self.models,self.receipt)
        for act,ob in h["observations"]:g.advance(act,ob)
        self.assertAlmostEqual(g.max_surprise,x)

if __name__=="__main__":unittest.main()

# Adapter tests intentionally use the same ordinary observation sequences as
# the learner tests. It must not grant new actions, and replay must be exact.
class GuardedNavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from developmental_ai.online_dynamics import trajectory
        from developmental_ai.mixed_experience import fit_mixed
        from developmental_ai.closed_loop_adaptation import models_from_proposal
        from developmental_ai.switching_belief import calibrate_hazard
        cls.proposal=fit_mixed([trajectory(31,'train',i) for i in range(20)],
                               [trajectory(31,'train',10000+i) for i in range(10)],
                               seed=31,iterations=1,rounds=1,min_group=5)
        cls.models=models_from_proposal(cls.proposal)
        r=[record(31,40000+i) for i in range(25)]
        cls.receipt=calibrate_guard(cls.models,r,alpha=.1)
        cls.hazard=calibrate_hazard(cls.models,r[:3],candidates=(0.,.01))

    def test_action_stop_and_exact_combined_restart(self):
        from developmental_ai.novelty_guard import GuardedNavigation
        a=GuardedNavigation(self.proposal,self.hazard,self.receipt,0,4,9)
        action=a.select_action()
        self.assertIn(action,(0,1,2))
        with self.assertRaises(ValueError):a.advance(1-action if action in (0,1) else 0,
                                                     {'beacon':None,'odometry':0,'landmark':None})
        a.advance(action,{'beacon':None,'odometry':0,'landmark':None})
        b=GuardedNavigation.restore(a.snapshot(),self.proposal,self.hazard,self.receipt)
        self.assertEqual(a.snapshot(),b.snapshot())
        a.guard.alarm=True
        self.assertIsNone(a.select_action())
        with self.assertRaises(ValueError):a.advance(action,{'beacon':None,'odometry':0,'landmark':None})

    def test_guard_and_session_log_cannot_be_rebound(self):
        from developmental_ai.novelty_guard import GuardedNavigation, _digest
        a=GuardedNavigation(self.proposal,self.hazard,self.receipt,0,4,9)
        action=a.select_action()
        a.advance(action,{'beacon':None,'odometry':0,'landmark':None})
        saved=a.snapshot()
        saved['state']['guard']['state']['log'][0][1]['odometry']=1
        guardstate=saved['state']['guard']['state']
        saved['state']['guard']['sha256']=_digest(guardstate)
        saved['sha256']=_digest(saved['state'])
        with self.assertRaises(ValueError):GuardedNavigation.restore(saved,self.proposal,self.hazard,self.receipt)


class GuardedCheckpointTests(GuardedNavigationTests):
    def test_atomic_sqlite_checkpoint_and_pending_recovery(self):
        import sqlite3
        import tempfile
        from pathlib import Path
        from developmental_ai.novelty_guard import GuardedCheckpoint, GuardedNavigation
        a=GuardedNavigation(self.proposal,self.hazard,self.receipt,0,4,9)
        act=a.select_action()
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'guard.db'
            with GuardedCheckpoint(path) as db:
                self.assertIsNone(db.load(self.proposal,self.hazard,self.receipt))
                db.save(a)
            with GuardedCheckpoint(path) as db:
                b=db.load(self.proposal,self.hazard,self.receipt)
            self.assertEqual(a.snapshot(),b.snapshot())
            self.assertEqual(act,b.select_action())
            a.advance(act,{'beacon':None,'odometry':0,'landmark':None})
            b.advance(act,{'beacon':None,'odometry':0,'landmark':None})
            self.assertEqual(a.snapshot(),b.snapshot())
            with GuardedCheckpoint(path) as db:db.save(a)
            with sqlite3.connect(path) as db:
                db.execute("UPDATE guarded_state SET record='{}'")
            with GuardedCheckpoint(path) as db:
                with self.assertRaises(ValueError):db.load(self.proposal,self.hazard,self.receipt)
