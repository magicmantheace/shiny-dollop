"""Frozen cross-schema public-outcome adaptation with three distinct rules.

The independent training actor chooses ONE random first action per episode.
The learner never receives the family string, true action physics, hidden
outcome labels, or action-handle identity across episodes. A common,
engineered progress/damage contract and observed named sensor fields remain
significant task-designer priors, NOT natural unsupervised representation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random

from developmental_ai.observable_affordances import (
    VariableOutcomeMemory, canonical, digest, variable_feature_check,
)

SCHEMA = "developmental-ai.variable-affordance-frame/v1"
RESULT_SCHEMA = "developmental-ai.variable-affordance-evaluation/v1"
FAMILIES = ("quarry", "coolant", "relay")
DEV = (142003, 142021, 142039)
ADDITIONAL = (143001, 143017, 143041)
SOURCE_N = 180
TARGET_N = 160
CHECKPOINTS = (0, 16, 48, 160)
TEST_START = 40000
TEST_N = 40
METHODS = ("schema_memory", "target_only", "recent_48", "source_frozen",
           "untrained_random", "always_abstain", "privileged_oracle")
PARAMETERS = {
    "quarry": (("grade", "moisture"), 3, 6, 1000),
    "coolant": (("flow", "heat", "seal"), 4, 7, 2000),
    "relay": (("phase", "pulse", "shield", "noise"), 2, 5, 3000),
}


def hidden_effect(family, features):
    """SIMULATOR ONLY. Never pass this or a family label to the learner."""
    if family == "quarry":
        grade, moisture = features["grade"], features["moisture"]
        return "progress" if grade >= moisture + 3 else (
            "damage" if moisture >= grade + 3 else "neutral")
    if family == "coolant":
        flow, heat, seal = features["flow"], features["heat"], features["seal"]
        return "progress" if flow >= 5 and seal >= 5 and heat <= 5 else (
            "damage" if heat >= 7 and seal <= 3 else "neutral")
    if family == "relay":
        phase, pulse = features["phase"], features["pulse"]
        shield, noise = features["shield"], features["noise"]
        return "progress" if phase % 3 == pulse % 3 and shield >= noise else (
            "damage" if pulse >= 7 and shield < noise else "neutral")
    raise ValueError("unknown simulator family")


class VariableWorld:
    """Different underlying transition law, keys, and completion requirement.

    One-shot action handles are randomized for each new episode. The public
    frame has no family marker. Its named features are still manually supplied
    physical observations, not automatically discovered semantics.
    """

    def __init__(self, seed, split, index, family):
        if (type(seed) is not int or split not in ("train","test")
                or type(index) is not int or not 0 <= index < 1000000
                or family not in FAMILIES):
            raise ValueError("invalid synthetic cross-schema episode")
        self.family = family
        keys, target, budget, _ = PARAMETERS[family]
        self.target, self.budget = target, budget
        self.episode = digest([SCHEMA, seed, split, index, family])
        rng = random.Random(int(self.episode[:16], 16))
        samples = {"progress": [], "damage": [], "neutral": []}
        used = set()
        for _ in range(30000):
            if all(len(samples[k]) >= n for k, n in
                   (("progress",5),("damage",4),("neutral",3))):
                break
            row = {key:rng.randrange(10) for key in keys}
            packed = tuple(row[k] for k in keys)
            if packed in used:
                continue
            label = hidden_effect(family, row)
            if len(samples[label]) < {"progress":5,"damage":4,"neutral":3}[label]:
                samples[label].append(row)
                used.add(packed)
        if any(len(samples[k]) != n for k, n in
               (("progress",5),("damage",4),("neutral",3))):
            raise AssertionError("could not produce balanced independent actions")
        selected = samples["progress"]+samples["damage"]+samples["neutral"]
        rng.shuffle(selected)
        handles = [f"a_{rng.getrandbits(72):018x}" for _ in selected]
        if len(set(handles)) != len(handles):
            raise AssertionError("duplicate opaque action handle")
        self._actions = dict(zip(handles, selected))
        self._used = set()
        self.progress = 0
        self.damage = 0
        self.tick = 0
        self.done = False

    def frame(self):
        return {
            "schema":SCHEMA, "episode":self.episode,
            "tick":self.tick, "budget":self.budget,
            "progress":self.progress, "damage":self.damage,
            "target":self.target,
            "actions":[{"id":a, "features":dict(row)}
                       for a, row in self._actions.items() if a not in self._used]
                      if not self.done else [],
            "done":self.done,
        }

    def step(self, action, tick):
        if (self.done or type(tick) is not int or tick != self.tick
                or type(action) is not str or action not in self._actions
                or action in self._used):
            raise ValueError("stale or unauthorized simulated action")
        effect = hidden_effect(self.family, self._actions[action])
        self.progress += int(effect == "progress")
        self.damage += int(effect == "damage")
        self._used.add(action)
        self.tick += 1
        self.done = (self.damage > 0 or self.progress >= self.target
                     or self.tick >= self.budget
                     or len(self._used) == len(self._actions))
        return self.frame()

    def success(self):
        return self.damage == 0 and self.progress >= self.target


def public_outcome(before, action, after):
    if (type(before) is not dict or type(after) is not dict or
            set(before) != set(after) or before["schema"] != SCHEMA or
            after["schema"] != SCHEMA or
            before["episode"] != after["episode"] or
            after["tick"] != before["tick"] + 1 or
            any(before[k] != after[k] for k in ("budget", "target"))):
        raise ValueError("inconsistent public action observation")
    options = {a["id"]:a["features"] for a in before["actions"]}
    if action not in options:
        raise ValueError("unknown public handle")
    dp = after["progress"] - before["progress"]
    dh = after["damage"] - before["damage"]
    if (type(dp) is not int or type(dh) is not int or
            dp not in (0,1) or dh not in (0,1) or dp+dh>1):
        raise ValueError("invalid public reward difference")
    expected = set(options)-{action}
    if not after["done"] and {a["id"] for a in after["actions"]} != expected:
        raise ValueError("action set inconsistent with observed effect")
    variable_feature_check(options[action])
    return {"features":dict(options[action]),"progress":bool(dp),"damage":bool(dh)}


def actor_event(seed, family, index):
    world = VariableWorld(seed, "train", index, family)
    before = world.frame()
    rng = random.Random(int(digest(["independent-variable-actor",world.episode])[:16],16))
    action = rng.choice(before["actions"])["id"]
    after = world.step(action, before["tick"])
    return public_outcome(before, action, after)


def train_events(seed, family, n):
    _, _, _, start = PARAMETERS[family]
    return [actor_event(seed, family, start+i) for i in range(n)]


def memory(events):
    out = VariableOutcomeMemory()
    for row in events:
        out.observe(row)
    return out


def play(seed, family, index, method, policies):
    if method not in METHODS:
        raise ValueError("unknown frozen cross-schema policy")
    world = VariableWorld(seed,"test",index,family)
    rng = random.Random(int(digest(["untrained-var-policy",world.episode])[:16],16))
    hurt = 0
    abstained = False
    for _ in range(world.budget):
        before = world.frame()
        if before["done"]:
            break
        if method in policies:
            action = policies[method].choose(before)
        elif method == "untrained_random":
            action = rng.choice(before["actions"])["id"]
        elif method == "always_abstain":
            action = None
        else:
            # BENCHMARK-PRIVATE oracle, never available to learner.
            good = [a["id"] for a in before["actions"]
                    if hidden_effect(family,a["features"]) == "progress"]
            action = good[0] if good else None
        if action is None:
            abstained = True
            break
        after = world.step(action,before["tick"])
        hurt += int(public_outcome(before,action,after)["damage"])
    return {"success":int(world.success()),"hurt":hurt,
            "abstained":int(abstained), "attempts":world.tick}


def summarize(rows):
    return {"episodes":len(rows),
            "successes":sum(x["success"] for x in rows),
            "hurt":sum(x["hurt"] for x in rows),
            "abstained":sum(x["abstained"] for x in rows),
            "mean_attempts":round(sum(x["attempts"] for x in rows)/len(rows),3)}


def measure(seeds=DEV):
    if type(seeds) not in (tuple,list) or tuple(seeds) not in (DEV,ADDITIONAL):
        raise ValueError("cohort does not match frozen research protocol")
    report = {"schema":RESULT_SCHEMA,
              "protocol":"benchmarks/variable_affordance_protocol.json",
              "blind":False,"learner_training_actions":0,
              "scoring_test_indices":[TEST_START,TEST_START+TEST_N-1],
              "rows":[]}
    for seed in seeds:
        source = train_events(seed,"quarry",SOURCE_N)+train_events(seed,"coolant",SOURCE_N)
        relay = train_events(seed,"relay",TARGET_N)
        frozen = memory(source)
        costs = {family:{
            "observations":len(rows),
            "harmful":sum(int(x["damage"]) for x in rows),
            "productive":sum(int(x["progress"]) for x in rows),
            "neutral":sum(int(not x["progress"] and not x["damage"]) for x in rows)}
            for family,rows in (
                ("quarry",source[:SOURCE_N]),
                ("coolant",source[SOURCE_N:]),
                ("relay",relay))}
        per_checkpoint = {}
        for n in CHECKPOINTS:
            history=source+relay[:n]
            learned = VariableOutcomeMemory.restore(memory(history).record())
            frozen_copy = VariableOutcomeMemory.restore(frozen.record())
            target = memory(relay[:n])
            recent = memory(history[-48:])
            policies = {"schema_memory":learned,
                        "target_only":target,
                        "recent_48":recent,
                        "source_frozen":frozen_copy}
            snapshots = {name:model.record() if model.events else None
                         for name,model in policies.items()}
            results = {}
            for family in FAMILIES:
                results[family] = {
                    method: summarize([
                        play(seed,family,TEST_START+i,method,policies)
                        for i in range(TEST_N)])
                    for method in METHODS}
            if any((model.record() if model.events else None) != snapshots[name]
                   for name, model in policies.items()):
                raise AssertionError("held-out test altered recorded learning")
            per_checkpoint[str(n)] = {
                "target_observations":n,
                "total_training_events":len(history),
                "schema_counts":learned.signatures(),
                "checkpoint_sha256":snapshots["schema_memory"]["sha256"],
                "results":results}
        report["rows"].append({"seed":seed,"actor_costs":costs,
                               "checkpoints":per_checkpoint})
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--cohort",choices=("development","additional"),default="development")
    a=p.parse_args()
    print(json.dumps(measure(DEV if a.cohort=="development" else ADDITIONAL),
                     sort_keys=True,indent=2))


if __name__=="__main__":
    main()
