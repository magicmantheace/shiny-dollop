"""Quarantined C adaptation with sandbox-only approval rehearsal.

A/B existing memory: 80 prior train episodes each. C: **80 new
unfiltered simulator episodes**, split=train indices 600..679. The
candidate is tested in disjoint TRAIN rehearsal indices 1200..1223,
then on already-inspected TEST 9300..9359. No production deployment.
"""
from __future__ import annotations

import argparse
import json

from developmental_ai.affordance_memory import FilteredNovel, RiskMemory
from developmental_ai.contextual_affordance import CUES, ContextMemory
from developmental_ai.dual_sentinel import DualSentinel
from developmental_ai.quarantined_c import (
    CandidateRoute, StagedCReview, _APPROVED_IN_THIS_PROCESS,
)
from developmental_ai.unseen_regime import UnseenDescriptorCargo
from benchmarks.contextual_affordance_benchmark import DEVELOPMENT, RESERVED, fit
from benchmarks.unseen_regime_benchmark import run as previous_run

SCHEMA="developmental-ai.quarantined-c-evaluation/v1"
TRAIN_START=600
TRAIN_N=80
VALIDATION_START=1200
VALIDATION_N=24
TEST_START=9300
TEST_N=60
ENVIRONMENTS=("A","B","C")
METHODS=("staged_C","old_sentinel","C_only","novel","oracle")


def train_c(seed):
    memory=RiskMemory()
    training=[]
    for i in range(TRAIN_N):
        world=UnseenDescriptorCargo(seed,"train",TRAIN_START+i,"C")
        policy=FilteredNovel()
        trace=[]
        for _ in range(18):
            before=world.frame()
            if before["base"]["done"]:
                break
            action=policy.choose(before)
            if action is None:
                break
            response=world.execute(action,before["base"]["tick"])
            trace.append(policy.feedback(before,action,response["accepted"],
                                         response["public"]))
        goal=bool(world.success())
        memory.add(i,trace,goal)
        training.append(int(goal))
    clone=RiskMemory.restore(memory.record())
    if clone.record()!=memory.record():
        raise AssertionError("C public training evidence failed deterministic replay")
    return clone,{"episodes":TRAIN_N,"successes":sum(training),
                  "learned_risks":sorted(clone.avoid())}


def trial(seed,split,index,environment,policy,sources,candidate):
    if (environment not in ENVIRONMENTS or policy not in METHODS
        or not isinstance(sources,ContextMemory)
        or not isinstance(candidate,RiskMemory)):
        raise ValueError("invalid isolated C adaptation trial")
    world=UnseenDescriptorCargo(seed,split,index,environment)
    if policy=="staged_C":
        controller=CandidateRoute(sources,candidate,
                                  _capability=_APPROVED_IN_THIS_PROCESS)
    elif policy=="old_sentinel":
        controller=DualSentinel(sources)
    elif policy=="C_only":
        controller=FilteredNovel(candidate)
    elif policy=="novel":
        controller=FilteredNovel()
    else:
        # The privileged old oracle receives the true C hazard identity.
        reference=previous_run(seed,split,index,environment,
                               "privileged_oracle",sources)
        return {**reference,"unknown":0,"C_route":0}

    failures=spoiled=0
    for _ in range(18):
        before=world.frame()
        if before["base"]["done"]:
            break
        action=controller.choose(before)
        if action is None:
            break
        # Ground truth for BENCHMARK SCORING ONLY.
        private=world.world.world.base._lookup[action]
        response=world.execute(action,before["base"]["tick"])
        controller.feedback(before,action,response["accepted"],
                            response["public"])
        failures+=int(not response["accepted"])
        spoiled+=int(private=="spoil" and response["accepted"])
    if policy=="staged_C" and controller.events:
        snapshot=controller.record()
        restored=CandidateRoute.restore(sources,candidate,snapshot,
                                         _capability=_APPROVED_IN_THIS_PROCESS)
        if restored.record()!=snapshot:
            raise AssertionError("restart changes C adaptation transcript")
        if not world.world.world.base.done:
            if restored.choose(world.frame())!=controller.choose(world.frame()):
                raise AssertionError("restart changes next observed action")
    return {"success":int(world.success()),
            "spoilage":spoiled,"attempts":world.world.world.base.tick,
            "blocked":failures,"stalled":int(not world.world.world.base.done),
            "unknown":int(getattr(controller,"unknown",False) or
                          getattr(controller,"sentinel",None) is not None
                          and controller.sentinel.unknown),
            "C_route":int(policy=="staged_C" and
                          controller.mode()=="quarantined-C-memory")}


def summarize(rows):
    return {"successes":sum(x["success"] for x in rows),
            "episodes":len(rows),
            "spoilage":sum(x["spoilage"] for x in rows),
            "stalled":sum(x["stalled"] for x in rows),
            "mean_attempts":round(sum(x["attempts"] for x in rows)/len(rows),3),
            "mean_blocked":round(sum(x["blocked"] for x in rows)/len(rows),3),
            "unknown":sum(x["unknown"] for x in rows),
            "C_routes":sum(x["C_route"] for x in rows)}


def stage(seed):
    a,_=fit(seed,"A")
    b,_=fit(seed,"B")
    sources=ContextMemory([[CUES["A"],a],[CUES["B"],b]])
    candidate,training=train_c(seed)
    source_before=sources.record()
    candidate_before=candidate.record()
    validation={}
    for environment in ENVIRONMENTS:
        rows=[trial(seed,"train",VALIDATION_START+i,environment,
                    "staged_C",sources,candidate) for i in range(VALIDATION_N)]
        summary=summarize(rows)
        validation[environment]={key:summary[key] for key in
                                 ("successes","episodes","spoilage","stalled")}
    proposal=StagedCReview(sources,candidate,validation)
    if source_before!=sources.record() or candidate_before!=candidate.record():
        raise AssertionError("validation modified old memories or candidate")
    return proposal,sources,candidate,training


def measure(seeds=DEVELOPMENT):
    if type(seeds) not in (tuple,list) or tuple(seeds) not in (DEVELOPMENT,RESERVED):
        raise ValueError("only already-inspected fixed seed cohorts")
    data={"schema":SCHEMA,"blind":False,
          "previously_inspected":True,
          "C_training":[TRAIN_START,TRAIN_START+TRAIN_N-1],
          "C_training_episodes":TRAIN_N,
          "validation_split":"train",
          "validation_indices":[VALIDATION_START,VALIDATION_START+VALIDATION_N-1],
          "test_indices":[TEST_START,TEST_START+TEST_N-1],
          "simulated_manual_approval_only":True,
          "rows":[]}
    for seed in seeds:
        review,sources,candidate,training=stage(seed)
        receipt=review.review()
        if not receipt["receipt"]["eligible_for_explicit_approval"]:
            # Preserve failure as data. Do not silently approve a failed gate.
            approved=False
            route_receipt=None
        else:
            # Explicit in-process approval ONLY for this simulation benchmark.
            # Never installs weights or grants real operating-system authority.
            simulated_route=review.approve(approved=True,
                                           receipt_sha256=receipt["sha256"])
            approved=isinstance(simulated_route,CandidateRoute)
            route_receipt=simulated_route.source_sha
        frozen_source=sources.record()
        frozen_candidate=candidate.record()
        outcomes={}
        for environment in ENVIRONMENTS:
            outcomes[environment]={}
            for policy in METHODS:
                # Staged preview is a bounded offline simulation. Even
                # failure to approve must not prevent reporting C controls.
                rows=[trial(seed,"test",TEST_START+i,environment,
                            policy,sources,candidate)
                      for i in range(TEST_N)]
                outcomes[environment][policy]=summarize(rows)
        if frozen_source!=sources.record() or frozen_candidate!=candidate.record():
            raise AssertionError("TEST observation changed source/candidate policy")
        data["rows"].append({"seed":seed,"training":training,
                            "review":receipt,"approved_in_simulation":approved,
                            "approved_source_sha256":route_receipt,
                            "outcomes":outcomes})
    return data


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--cohort",choices=("development","inspected-additional"),
                   default="development")
    args=p.parse_args()
    print(json.dumps(measure(DEVELOPMENT if args.cohort=="development" else RESERVED),
                     sort_keys=True,indent=2))


if __name__=="__main__":
    main()
