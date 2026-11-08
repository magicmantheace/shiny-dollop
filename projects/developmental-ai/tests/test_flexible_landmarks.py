"""Independent optional marker-map inference under honest observation constraints."""
import copy
import json
import math
import sqlite3
import tempfile
import unittest
from pathlib import Path

from benchmarks.flexible_landmarks_benchmark import (
    CONDITIONS, FlexOracle, observation_history, navigate, measure,
)
from developmental_ai.adaptive_dynamics import AdaptiveNavigator
from developmental_ai.flexible_landmarks import (
    FlexibleModel, FlexibleStore, fit_flexible, refine_sites, select_sites, digest,
)
from developmental_ai.online_dynamics import score


class FlexibleLandmarkTests(unittest.TestCase):
    def data(self, name="one_site", seed=17, count=24):
        return [observation_history(seed,"train",i,CONDITIONS[name]) for i in range(count)]

    def test_model_accepts_optional_sites_and_independent_geometry(self):
        m=FlexibleModel({"9":[1,3],"11":[None,7]})
        self.assertEqual([m.role(9,i) for i in (0,1,3,4)], [0,1,2,0])
        self.assertEqual(m.role(11,7),2)
        for n in (9,11):
            for pos in range(n):self.assertAlmostEqual(sum(m.landmark_probs(n,pos)),1.)
        nav=AdaptiveNavigator(0,4,9,m)
        nav.advance(1,{"beacon":None,"odometry":1,"landmark":None})
        self.assertAlmostEqual(sum(nav.probs),1.)
        self.assertIn(nav.heuristic(),(0,1,2))

    def test_absent_landmarks_learned_without_truth(self):
        model, meta = fit_flexible(self.data("no_sites"),iterations=3,map_histories=12)
        self.assertEqual(model.sites,{"9":[None,None],"11":[None,None]})
        self.assertTrue(all(math.isfinite(x) for x in meta["fit_curve"]))

    def test_single_landmark_learned_without_truth(self):
        model, _ = fit_flexible(self.data("one_site"),iterations=3,map_histories=12)
        self.assertEqual(model.sites,CONDITIONS["one_site"]["sites"])
        self.assertTrue(all(set(h)=={"n","initial","observations"} for h in self.data("one_site")))

    def test_separation_is_not_half_ring(self):
        model, _ = fit_flexible(self.data("unequal_two",count=30),iterations=3,map_histories=16)
        self.assertEqual(model.sites["9"],[1,3])
        # Under severe noise the other site's exact coordinate can be wrong;
        # independent positioning, not universal recovery, is the contract.
        self.assertNotEqual(model.sites["11"][0], model.sites["11"][1])

    def test_reproducible_inference_and_curves(self):
        train=self.data()
        a,one=fit_flexible(train,iterations=3,map_histories=12)
        b,two=fit_flexible(train,iterations=3,map_histories=12)
        self.assertEqual(a.state(),b.state())
        self.assertEqual(one,two)
        observations=[observation_history(17,"test",52000+i,CONDITIONS["one_site"]) for i in range(5)]
        self.assertTrue(math.isfinite(score(a,observations)))

    def test_model_does_not_accept_privileged_supervision(self):
        h=self.data()[0]
        bad=dict(h);bad["hidden_position"] = 1
        with self.assertRaises(ValueError):fit_flexible([h,bad])
        malformed=copy.deepcopy(h);malformed["observations"][0] = (1,0,True)
        with self.assertRaises(ValueError):fit_flexible([h,malformed])

    def test_bad_geometry_and_inputs_rejected(self):
        for sites in ({"9":[2,2],"11":[0,5]}, {"9":[True,None],"11":[0,5]},
                      {"9":[0],"11":[0,5]}, {"9":[0,1]},
                      {"9":[-1,2],"11":[0,5]}):
            with self.subTest(sites=sites),self.assertRaises(ValueError):FlexibleModel(sites)
        with self.assertRaises(ValueError):fit_flexible(self.data()[:1])
        with self.assertRaises(ValueError):fit_flexible(self.data(),iterations=0)
        with self.assertRaises(ValueError):fit_flexible(self.data(),map_histories=1)
        with self.assertRaises(ValueError):select_sites(self.data(),FlexibleModel(),site_penalty=-1)
        with self.assertRaises(ValueError):refine_sites(self.data(),FlexibleModel(),site_penalty=float('nan'))

    def test_model_record_integrity_and_seed_binding(self):
        m=FlexibleModel({"9":[3,None],"11":[None,None]})
        self.assertEqual(FlexibleModel.from_record(m.record(17),17).state(),m.state())
        with self.assertRaises(ValueError):FlexibleModel.from_record(m.record(17),23)
        modified=m.record(17)
        modified["body"]["sites"]["9"]=[1,None]
        with self.assertRaises(ValueError):FlexibleModel.from_record(modified,17)
        modified["digest"]=digest(modified["body"])
        modified["body"]["sites"]["9"]=[11,None]
        modified["digest"]=digest(modified["body"])
        with self.assertRaises(ValueError):FlexibleModel.from_record(modified,17)

    def test_sqlite_restart_is_exact_and_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"sample.db"
            m=FlexibleModel({"9":[1,3],"11":[None,None]})
            with FlexibleStore(path) as store:
                self.assertIsNone(store.load(17))
                store.save(m,17)
            with FlexibleStore(path) as store:
                self.assertEqual(store.load(17).state(),m.state())
                with self.assertRaises(ValueError):store.load(23)
            with sqlite3.connect(path) as db:db.execute("UPDATE flexible_state SET record='{}'")
            with FlexibleStore(path) as store:
                with self.assertRaises(ValueError):store.load(17)

    def test_small_protocol_returns_all_comparators_and_map_truth_only_for_scoring(self):
        result=measure([17],train_episodes=16,iterations=2,map_histories=8,
                       test_episodes=4,navigation_episodes=5,conditions=["no_sites"])
        item=result["rows"][0]["conditions"]["no_sites"]
        self.assertEqual(set(item["navigation_success"]),
                         {"unconstrained_em","fixed_half_structure","flexible_sites","physics_oracle"})
        self.assertEqual(set(item["learned_sites"]), {"9","11"})
        self.assertEqual(result["fit_partition"],"train/0+")
        self.assertEqual(result["test_partition"],"test/51000+")

if __name__=="__main__":unittest.main()
