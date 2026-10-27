"""Observation-only structured geometry: deterministic fit, safety, persistence."""
import copy
import json
import math
import sqlite3
import tempfile
import unittest
from pathlib import Path
from developmental_ai.adaptive_dynamics import AdaptiveNavigator, KnownPhysicsOracle
from developmental_ai.online_dynamics import score, trajectory, validate_history
from developmental_ai.structured_landmarks import StructuredModel, ModelStorage, fit_structured, select_offsets, checksum


class StructuredLandmarkTests(unittest.TestCase):
    def test_same_input_same_parameters_and_curve(self):
        data=[trajectory(17,'train',i,'high','shifted') for i in range(25)]
        a,curve=fit_structured(data,iterations=3)
        b,other=fit_structured(data,iterations=3)
        self.assertEqual(a.state(),b.state())
        self.assertEqual(curve,other)
        self.assertEqual(a.offsets,{'9':2,'11':2})
        self.assertTrue(all(math.isfinite(v) for v in curve))

    def test_original_geometry_is_learned(self):
        data=[trajectory(23,'train',i,'standard','fixed') for i in range(25)]
        model,_=fit_structured(data,iterations=2)
        self.assertEqual(model.offsets,{'9':0,'11':0})
        self.assertLess(score(model,[trajectory(23,'test',300+i) for i in range(10)]),0)

    def test_model_probabilities_are_normalized_and_compatible_with_navigation(self):
        model=StructuredModel({'9':3,'11':3})
        for n in (9,11):
            self.assertEqual(model.role(n,3),1)
            self.assertEqual(model.role(n,(3+n//2)%n),2)
            for p in range(n):self.assertAlmostEqual(sum(model.landmark_probs(n,p)),1)
        for v in (-1,1):self.assertAlmostEqual(sum(model.motion_probs(v)),1)
        for v in (-1,0,1):self.assertAlmostEqual(sum(model.odo_probs(v)),1)
        nav=AdaptiveNavigator(0,4,9,model)
        nav.advance(1,{'beacon':None,'odometry':1,'landmark':None})
        self.assertAlmostEqual(sum(nav.probs),1)
        self.assertIn(nav.heuristic(),(0,1,2))

    def test_refuses_privileged_or_malformed_observations(self):
        sample=trajectory(17,'train',2)
        bad=dict(sample);bad['true_position']=2
        with self.assertRaises(ValueError):fit_structured([sample,bad])
        bad=copy.deepcopy(sample);bad['observations'][0]=(1,0,99)
        with self.assertRaises(ValueError):select_offsets([sample,bad],StructuredModel())
        with self.assertRaises(ValueError):fit_structured([sample],iterations=3)
        with self.assertRaises(ValueError):fit_structured([sample,sample],iterations=0)

    def test_missing_topology_group_is_rejected(self):
        histories=[trajectory(17,'train',i) for i in range(10)]
        size=histories[0]['n']
        only=[h for h in histories if h['n']==size]
        with self.assertRaises(ValueError):fit_structured(only)

    def test_checkpoint_restart_and_seed_binding(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'model.db'
            model=StructuredModel({'9':2,'11':3})
            with ModelStorage(path) as store:
                self.assertIsNone(store.load(17))
                store.save(model,17)
            with ModelStorage(path) as store:
                loaded=store.load(17)
                self.assertEqual(loaded.state(),model.state())
                with self.assertRaises(ValueError):store.load(23)
                store.save(loaded,17)
            with ModelStorage(path) as store:self.assertEqual(store.load(17).record(17),model.record(17))

    def test_tampered_checkpoint_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'model.db'
            with ModelStorage(path) as store:store.save(StructuredModel(),17)
            with sqlite3.connect(path) as sql:
                obj=json.loads(sql.execute('SELECT record FROM structured_state').fetchone()[0])
                obj['state']['offsets']['11']=7
                sql.execute('UPDATE structured_state SET record=?',(json.dumps(obj),))
            with ModelStorage(path) as store:
                with self.assertRaises(ValueError):store.load(17)

    def test_invalid_model_parameters_and_record_structure_rejected(self):
        model=StructuredModel()
        with self.assertRaises(ValueError):StructuredModel({'9':True,'11':0})
        with self.assertRaises(ValueError):StructuredModel(roles=[[1,2,float('nan')]]*3)
        with self.assertRaises(ValueError):StructuredModel(odo=[[-1,2,3]]*3)
        with self.assertRaises(ValueError):StructuredModel.from_record({'state':model.state(),'digest':'x'},17)
        with self.assertRaises(ValueError):model.motion_probs(True)

    def test_unseen_offset_three_can_be_inferred_from_unlabelled_sensors(self):
        from benchmarks.structured_landmark_novelty_benchmark import trajectory_offset
        training=[trajectory_offset(17,'train',i,offset=3) for i in range(50)]
        model,_=fit_structured(training,iterations=3)
        self.assertEqual(model.offsets,{'9':3,'11':3})
        self.assertTrue(all(set(h)=={'n','initial','observations'} for h in training))
        result=score(model,[trajectory_offset(17,'test',41000+i,offset=3) for i in range(12)])
        self.assertTrue(math.isfinite(result))

    def test_training_and_heldout_prediction_without_position_labels(self):
        train=[trajectory(17,'train',i,'high','shifted') for i in range(35)]
        test=[trajectory(17,'test',28000+i,'high','shifted') for i in range(12)]
        model,_=fit_structured(train,iterations=3)
        self.assertEqual(model.offsets,{'9':2,'11':2})
        self.assertLess(abs(score(model,test)-score(KnownPhysicsOracle('high','shifted'),test)),.20)
        self.assertTrue(all(set(h)=={'n','initial','observations'} for h in train+test))

if __name__=='__main__':unittest.main()
