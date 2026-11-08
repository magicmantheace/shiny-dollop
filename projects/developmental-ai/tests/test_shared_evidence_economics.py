"""Frozen shared-vs-new evidence cost accounting and TEST contamination guards."""
from __future__ import annotations

import copy
import unittest

from benchmarks.shared_evidence_economics_benchmark import (
    DEV,ADDITIONAL,CHECKPOINTS,TEST_START,TEST_N,METHODS,
    COST_DAMAGE,COST_ABSTAIN,COST_EXTRA_ACTION,
    feed_bank,collect_on_demand,zero_cost,add_cost,study_costs,
    evaluate,measure,
)
from benchmarks.gated_composition_benchmark import training
from benchmarks.independent_witness_benchmark import fresh_witness
from benchmarks.validated_abstention_benchmark import models as prior_models
from developmental_ai.witness_recovery_memory import (
    WitnessRecoveryMemory,BATCH,MAX_WITNESS,
)


class EvidenceEconomicsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed=DEV[0]
        cls.source,cls.cost=training(cls.seed,"source",1000,240)

    def test_protocol_and_all_unique_actor_episode_ranges(self):
        self.assertEqual((BATCH,MAX_WITNESS),(8,32))
        self.assertEqual((COST_DAMAGE,COST_ABSTAIN,COST_EXTRA_ACTION),(10,1,1))
        self.assertEqual(TEST_N,16)
        self.assertEqual(TEST_START,{"conditional":410000,
                                      "return_source":420000,
                                      "xor":430000})
        self.assertEqual(CHECKPOINTS["return_source"],(0,8,16,32,64))
        self.assertEqual(len(METHODS),8)
        for stage_no,phase in enumerate(("conditional","return_source","xor"),1):
            shared=set(range(600000+stage_no*10000,
                             600000+stage_no*10000+32))
            fresh=set()
            for ordinal in range(len(CHECKPOINTS[phase])):
                first=650000+stage_no*10000+ordinal*100
                batch=set(range(first,first+32))
                self.assertFalse(fresh.intersection(batch))
                fresh.update(batch)
            self.assertFalse(shared.intersection(fresh))
            self.assertTrue(all(n>400000 and n<800000 for n in fresh|shared))

    def test_shared_bank_upfront_actor_cost_is_real(self):
        public,cost=training(self.seed,"conditional",610000,MAX_WITNESS)
        self.assertEqual(len(public),MAX_WITNESS)
        self.assertEqual(cost["observations"],32)
        self.assertEqual(sum(cost[x] for x in
                             ("harmful","productive","neutral")),32)
        self.assertEqual(training(self.seed,"conditional",610000,32),
                         (public,cost))
        self.assertEqual(set(public[0]),{"features","progress","damage"})

    def test_no_additional_actor_intervention_from_bank_consumption(self):
        policy=fresh_witness(self.source)
        old=policy.record()
        bank,source_cost=training(self.seed,"xor",630000,32)
        before=policy.witness_count
        trace=feed_bank(policy,bank)
        self.assertEqual(policy.witness_count-before,
                         trace["accepted_records"])
        self.assertLessEqual(trace["accepted_records"],32)
        self.assertEqual(trace["accepted_records"]%8,0)
        self.assertEqual(source_cost["observations"],32)
        self.assertNotIn("private_law",str(policy.record()))
        restored=WitnessRecoveryMemory.restore(copy.deepcopy(policy.record()))
        self.assertEqual(restored.record(),policy.record())
        self.assertFalse(hasattr(policy,"step"))

    def test_demand_observation_cost_matches_public_added_records(self):
        policy=fresh_witness(self.source)
        before=policy.record()
        trace=collect_on_demand(self.seed,"conditional","conditional",0,policy)
        cost=trace["external_actor_cost"]
        self.assertEqual(cost["observations"],trace["accepted_records"])
        self.assertEqual(trace["accepted_records"],policy.witness_count)
        self.assertEqual(sum(cost[k] for k in
                             ("harmful","productive","neutral")),
                         cost["observations"])
        self.assertLessEqual(cost["observations"],32)
        if cost["observations"]==0:
            self.assertEqual(before,policy.record())

    def test_invalid_actor_cost_values_never_mutate_original(self):
        a=zero_cost()
        b={"observations":8,"harmful":3,"productive":4,"neutral":1}
        add_cost(a,b)
        self.assertEqual(a,b)
        self.assertEqual(b["harmful"],3)
        c=zero_cost()
        add_cost(c,a)
        self.assertEqual(c,b)

    def test_study_loss_counts_shared_bank_once_not_each_checkpoint(self):
        rows=[]
        row={"bank_actor_cost":{},"stages":{}}
        zero={"observations":0,"harmful":0,"productive":0,"neutral":0}
        for stage,checks in CHECKPOINTS.items():
            row["bank_actor_cost"][stage]=dict(zero)
            row["stages"][stage]={}
            for k in checks:
                row["stages"][stage][str(k)]={
                    "fresh_actor_cost":dict(zero),
                    "scores":{m:{"successes":0,"harmful_actions":0,
                                  "abstained":0} for m in METHODS},
                }
        row["bank_actor_cost"]["conditional"]={
            "observations":32,"harmful":9,"productive":15,"neutral":8}
        row["stages"]["conditional"]["8"]["fresh_actor_cost"]={
            "observations":8,"harmful":2,"productive":4,"neutral":2}
        row["stages"]["conditional"]["8"]["scores"]["shared_bank"]={
            "successes":3,"harmful_actions":2,"abstained":11}
        row["stages"]["conditional"]["8"]["scores"]["fresh_witness"]={
            "successes":2,"harmful_actions":3,"abstained":11}
        rows.append(row)
        ledger=study_costs(rows)
        self.assertEqual(ledger["shared_bank"]["extra_actor_actions"],32)
        self.assertEqual(ledger["shared_bank"]["extra_actor_harm"],9)
        self.assertEqual(ledger["fresh_witness"]["extra_actor_actions"],8)
        self.assertEqual(ledger["fresh_witness"]["extra_actor_harm"],2)
        self.assertEqual(ledger["shared_bank"]["precommitted_study_loss"],
                         10*(2+9)+11+32)
        self.assertEqual(ledger["fresh_witness"]["precommitted_study_loss"],
                         10*(3+2)+11+8)

    def test_matched_TEST_is_read_only(self):
        history=self.source
        baselines=prior_models(history)
        baselines["no_extra_evidence"]=baselines["validated_abstain"]
        baselines["fresh_witness"]=fresh_witness(history)
        baselines["shared_bank"]=fresh_witness(history)
        original=baselines["fresh_witness"].record()
        for mode in METHODS:
            result=evaluate(self.seed,"conditional",410000,mode,baselines)
            self.assertIn(result["success"],(0,1))
            self.assertIn(result["harmful_actions"],(0,1))
            if mode=="always_abstain":
                self.assertEqual(result["success"],0)
                self.assertEqual(result["abstained"],1)
        self.assertEqual(original,baselines["fresh_witness"].record())

    def test_only_registered_seed_cohorts_allowed(self):
        self.assertNotEqual(DEV,ADDITIONAL)
        for invalid in ((1,2,3),(DEV[0],),tuple(reversed(ADDITIONAL))):
            with self.assertRaises(ValueError):
                measure(invalid)


if __name__=="__main__":
    unittest.main()
