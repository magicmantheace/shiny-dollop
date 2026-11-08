"""Precommitted A-B-A contextual risk retrieval with a changed descriptor map.

The simulator is unchanged cargo physics. Swapping the public signatures of
'wash' and 'spoil' changes which previously seen identifier is dangerous.
An engineered public numeric context beacon permits separate old/new memory.
This is context-conditioned retrieval, NOT unsupervised regime discovery.
"""
from __future__ import annotations

import argparse
import json
import random

from developmental_ai.affordance_memory import (
    FilteredNovel, RiskMemory, record_step, signature, token
)
from developmental_ai.contextual_affordance import (
    CUES, ContextMemory, ContextNovel, ShiftedCargo
)

SCHEMA = "developmental-ai.contextual-affordance-evaluation/v1"
DEVELOPMENT = (51001, 51013, 51031)
RESERVED = (61001, 61013, 61031)
TRAIN_N = 80
TEST_N = 60
METHODS = ("context", "A_only", "B_only", "novel", "ambiguous_cue",
           "risk_oracle", "full_oracle")
EVALUATIONS = (("A", 8400), ("B", 8400), ("A_return", 8500))


class PrivilegedRisk(RiskMemory):
    """SCORING REFERENCE ONLY; uses simulator action meaning."""
    def __init__(self, risky_code):
        super().__init__()
        self.risky_code = risky_code

    def avoid(self):
        return {self.risky_code}


def trial(seed, split, index, phase, method, memories=None, *, collect=False):
    if method not in METHODS or phase not in CUES:
        raise ValueError("invalid controlled context trial")
    if method in ("context", "ambiguous_cue", "A_only", "B_only") and not isinstance(memories, ContextMemory):
        raise ValueError("fitted source and changed-context memories required")
    world = ShiftedCargo(seed, split, index, phase)
    ambiguous = method == "ambiguous_cue"
    if method in ("context", "ambiguous_cue"):
        controller = ContextNovel(memories)
    elif method == "A_only":
        controller = FilteredNovel(memories.choose_memory(CUES["A"]))
    elif method == "B_only":
        controller = FilteredNovel(memories.choose_memory(CUES["B"]))
    elif method == "novel":
        controller = FilteredNovel()
    elif method == "risk_oracle":
        # The privileged benchmark reference reads the simulator's true
        # descriptor assignment (including deterministic collision repair).
        # This is NEVER exposed to ContextNovel/ContextMemory.
        controller = FilteredNovel(
            PrivilegedRisk(token(world.world._features["spoil"])))
    else:
        controller = None
    # Hidden rules and label used ONLY by privileged reference or scoring.
    recipe = ("extract", "charge", "refine", "fuel", "load", "ship")
    events = []
    blocked = spoiled = 0
    for _ in range(18):
        before = world.frame(ambiguous=ambiguous)
        base = before["public"]["base"]
        if base["done"]:
            break
        if method in ("context", "ambiguous_cue"):
            action = controller.choose(before)
        elif controller is not None:
            action = controller.choose(before["public"])
        else:
            action = world.world.base._ids[recipe[base["tick"]]] if base["tick"] < len(recipe) else None
        if action is None:
            break
        # Benchmark labels NEVER enter the learner or memory event.
        true_action = world.world.base._lookup[action]
        response = world.step(action, base["tick"], ambiguous=ambiguous)
        after = response["frame"]
        if method in ("context", "ambiguous_cue"):
            event = controller.feedback(before, action, response["accepted"], after)
        elif controller is not None:
            event = controller.feedback(before["public"], action,
                                        response["accepted"], after["public"])
        else:
            event = record_step(before["public"], action, response["accepted"],
                                after["public"])
        events.append(event)
        blocked += int(not response["accepted"])
        spoiled += int(true_action == "spoil" and response["accepted"])
    outcome = {"success": int(world.success()),
               "attempts": world.world.base.tick, "blocked": blocked,
               "spoilage": spoiled,
               "stalled": int(not world.world.base.done)}
    return (outcome, events) if collect else outcome


def fit(seed, phase):
    memory = RiskMemory()
    out = []
    for i in range(TRAIN_N):
        index = i if phase == "A" else 300+i
        result, events = trial(seed, "train", index, phase, "novel",
                               collect=True)
        memory.add(i, events, bool(result["success"]))
        out.append(result)
    if RiskMemory.restore(memory.record()).record() != memory.record():
        raise AssertionError("individual phase memory failed replay")
    return memory, summarise(out)


def summarise(rows):
    if not rows:
        raise ValueError("empty evaluation group")
    return {"successes": sum(r["success"] for r in rows),
            "episodes": len(rows),
            "spoilage": sum(r["spoilage"] for r in rows),
            "mean_attempts": round(sum(r["attempts"] for r in rows)/len(rows),3),
            "mean_blocked": round(sum(r["blocked"] for r in rows)/len(rows),3),
            "stalled": sum(r["stalled"] for r in rows)}


def measure(seeds=DEVELOPMENT):
    if type(seeds) not in (tuple,list) or tuple(seeds) not in (DEVELOPMENT,RESERVED):
        raise ValueError("only frozen development or reserved cohorts")
    results = {"schema":SCHEMA,"blind":False,
               "engineered_cue":True, "descriptor_swap_only":True,
               "train": {"A":[0,79], "B":[300,379]},
               "evaluations":{"A":[8400,8459],"B":[8400,8459],
                              "A_return":[8500,8559]},
               "rows":[]}
    for seed in seeds:
        earlier, train_a = fit(seed, "A")
        later, train_b = fit(seed, "B")
        model = ContextMemory([[CUES["A"],earlier],[CUES["B"],later]])
        saved = model.record()
        restored = ContextMemory.restore(saved)
        if restored.record() != saved:
            raise AssertionError("context checkpoint differs after restore")
        risks = {phase:sorted(model.choose_memory(CUES[phase]).avoid())
                 for phase in ("A","B")}
        measurements = {}
        for period,index_start in EVALUATIONS:
            phase = "A" if period.startswith("A") else "B"
            measurements[period] = {}
            for method in METHODS:
                outcomes = [trial(seed,"test",index_start+i,phase,method,restored)
                            for i in range(TEST_N)]
                measurements[period][method] = summarise(outcomes)
        if restored.record()!=saved or model.record()!=saved:
            raise AssertionError("read-only A-B-A evaluation mutated memory")
        results["rows"].append({
            "seed":seed,"source_training":train_a,"shifted_training":train_b,
            "learned_risks":risks,"memory_sha256":saved["sha256"],
            "scores":measurements})
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cohort",choices=("development","reserved"),
                        default="development")
    args = parser.parse_args()
    print(json.dumps(measure(DEVELOPMENT if args.cohort=="development" else RESERVED),
                     indent=2,sort_keys=True))


if __name__ == "__main__":
    main()
