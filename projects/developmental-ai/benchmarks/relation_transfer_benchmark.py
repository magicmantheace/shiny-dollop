"""Frozen structural transfer experiment; simulation-only.

Source and two targets deliberately share an unlabelled range-to-effect
mechanism, expressed through different numeric feature names/dimensions.
Counterphase deliberately reverses this mechanism and tests harmful negative
transfer. This is controlled invariant reuse, NOT discovery of arbitrary
new physics or a blind independently administered benchmark.
"""
from __future__ import annotations

import argparse
import json
import random

from developmental_ai.observable_affordances import (
    VariableOutcomeMemory, digest
)
from developmental_ai.relation_outcome_memory import RelationOutcomeMemory, span
from benchmarks.variable_affordance_benchmark import (
    SCHEMA as FRAME_SCHEMA, public_outcome
)

SCHEMA = "developmental-ai.relation-transfer-benchmark/v1"
DEV = (152003, 152021, 152039)
ADDITIONAL = (153001, 153017, 153041)
FAMILIES = ("basin", "lattice", "prism", "counterphase")
TARGETS = FAMILIES[1:]
KEYS = {
    "basin": ("inlet", "outlet"),
    "lattice": ("north", "charge", "plume"),
    "prism": ("flux", "tone", "vapor", "texture"),
    "counterphase": ("keel", "wisp", "coil"),
}
INDEX = {"basin": 1000, "lattice": 2000, "prism": 3000, "counterphase": 4000}
SOURCE_N = 240
TARGET_N = 64
CHECKPOINTS = (0, 8, 24, 64)
TEST_START = 50000
TEST_N = 40
METHODS = (
    "transfer_range", "source_frozen_range", "target_only_range",
    "raw_schema_memory", "max_span_fixed", "fixed_band_4",
    "min_span_fixed", "untrained_random", "always_abstain",
    "privileged_oracle",
)


def band(seed):
    if type(seed) is not int:
        raise ValueError("noninteger experiment seed")
    # Private BENCHMARK physics parameter, never passed to a learner.
    return (2, 4, 6)[int(digest([SCHEMA, seed, "band"])[:12],16) % 3]


def effect_for(seed, family, features):
    if family not in FAMILIES:
        raise ValueError("unknown synthetic family")
    gap = span(features)
    k = band(seed)
    outcome = ("progress" if gap in (k,k+1) else
               "damage" if gap <= k-2 or gap >= k+3 else
               "neutral")
    if family == "counterphase":
        return {"progress":"damage", "damage":"progress",
                "neutral":"neutral"}[outcome]
    return outcome


class RelationWorld:
    """Anonymized public numeric I/O, independent action aliases per episode."""

    def __init__(self, seed, split, index, family):
        if (type(seed) is not int or split not in ("train","test") or
                type(index) is not int or not 0 <= index < 1000000 or
                family not in FAMILIES):
            raise ValueError("invalid synthetic relation-world configuration")
        self.family, self.seed = family, seed
        self.episode = digest([SCHEMA,seed,split,index,family])
        rng = random.Random(int(self.episode[:16],16))
        self.goal = 3
        self.budget = 6
        self.tick = 0
        self.progress = 0
        self.damage = 0
        self.done = False
        good = {"progress":[], "damage":[], "neutral":[]}
        for gap in range(10):
            category=effect_for(seed,family,{KEYS[family][0]:0,
                                            KEYS[family][1]:gap})
            good[category].append(gap)
        if any(not x for x in good.values()):
            raise ValueError("unscorable outcome partition")
        actions = []
        seen = set()
        for label, count in (("progress",5),("damage",4),("neutral",3)):
            for _ in range(count):
                for _retry in range(100):
                    gap = rng.choice(good[label])
                    offset = rng.randrange(10-gap)
                    vals = [offset,offset+gap]
                    vals.extend(rng.randrange(offset,offset+gap+1)
                                for _ in range(len(KEYS[family])-2))
                    rng.shuffle(vals)
                    features = dict(zip(KEYS[family],vals))
                    signature = tuple(sorted(features.items()))
                    if signature not in seen:
                        seen.add(signature)
                        actions.append(features)
                        break
                else:
                    raise AssertionError("synthetic action sampler exhausted")
        rng.shuffle(actions)
        handles = [f"a_{rng.getrandbits(72):018x}" for _ in actions]
        if len(set(handles)) != len(handles):
            raise AssertionError("anonymous handle collision")
        self._actions=dict(zip(handles,actions))
        self._used=set()

    def frame(self):
        return {"schema":FRAME_SCHEMA, "episode":self.episode,
                "tick":self.tick, "budget":self.budget,
                "progress":self.progress, "damage":self.damage,
                "target":self.goal, "done":self.done,
                "actions":[{"id":a,"features":dict(f)}
                           for a,f in self._actions.items() if a not in self._used]
                           if not self.done else []}

    def step(self, action, tick):
        if (self.done or type(tick) is not int or tick != self.tick or
                type(action) is not str or action not in self._actions or
                action in self._used):
            raise ValueError("unknown or stale simulator action")
        category = effect_for(self.seed,self.family,self._actions[action])
        self.tick += 1
        self.progress += int(category=="progress")
        self.damage += int(category=="damage")
        self._used.add(action)
        self.done = (self.progress>=self.goal or self.damage>0
                     or self.tick>=self.budget
                     or len(self._used)==len(self._actions))
        return self.frame()

    def success(self):
        return self.progress >= self.goal and not self.damage


def actor_event(seed,family,index):
    world=RelationWorld(seed,"train",index,family)
    frame=world.frame()
    actor=random.Random(int(digest(["independent-relation-actor",world.episode])[:16],16))
    pick=actor.choice(frame["actions"])["id"]
    outcome=world.step(pick,frame["tick"])
    return public_outcome(frame,pick,outcome)


def observed(seed,family,n):
    return [actor_event(seed,family,INDEX[family]+i) for i in range(n)]


def relation_model(rows):
    m=RelationOutcomeMemory()
    for row in rows:
        m.observe(row)
    return m


def raw_model(rows):
    m=VariableOutcomeMemory()
    for row in rows:
        m.observe(row)
    return m


def _heuristic(frame,method,rng):
    if method=="always_abstain":
        return None
    if method=="untrained_random":
        return rng.choice(frame["actions"])["id"]
    if method=="max_span_fixed":
        return min(frame["actions"],key=lambda x:(-span(x["features"]),x["id"]))["id"]
    if method=="min_span_fixed":
        return min(frame["actions"],key=lambda x:(span(x["features"]),x["id"]))["id"]
    if method=="fixed_band_4":
        return min(frame["actions"],key=lambda x:(
            min(abs(span(x["features"])-s) for s in (4,5)),x["id"]))["id"]
    raise ValueError("unsupported heuristic")


def play(seed,family,index,method,policies):
    if method not in METHODS:
        raise ValueError("unfrozen comparison method")
    world=RelationWorld(seed,"test",index,family)
    rng=random.Random(int(digest(["untrained-relation-policy",world.episode])[:16],16))
    harm=0
    abstained=0
    for _ in range(world.budget):
        before=world.frame()
        if before["done"]:
            break
        if method in policies:
            picked=policies[method].choose(before)
        elif method=="privileged_oracle":
            # Scoring-only privileged simulator truth.
            picked=next((a["id"] for a in before["actions"]
                         if effect_for(seed,family,a["features"])=="progress"),None)
        else:
            picked=_heuristic(before,method,rng)
        if picked is None:
            abstained=1
            break
        after=world.step(picked,before["tick"])
        harm+=int(public_outcome(before,picked,after)["damage"])
    return {"success":int(world.success()),"harmful_actions":harm,
            "abstained":abstained,"attempts":world.tick}


def summarize(rows):
    return {"episodes":len(rows),
            "successes":sum(x["success"] for x in rows),
            "harmful_actions":sum(x["harmful_actions"] for x in rows),
            "abstained":sum(x["abstained"] for x in rows),
            "mean_attempts":round(sum(x["attempts"] for x in rows)/len(rows),3)}


def measure(seeds=DEV):
    if type(seeds) not in (tuple,list) or tuple(seeds) not in (DEV,ADDITIONAL):
        raise ValueError("not frozen relation-transfer cohort")
    report={"schema":SCHEMA,"protocol":"benchmarks/relation_transfer_protocol.json",
            "blind":False,"learner_training_actions":0,
            "test_episodes_per_family_checkpoint_seed":TEST_N,
            "shared_rule_authoring_acknowledged":True,"rows":[]}
    for seed in seeds:
        source=observed(seed,"basin",SOURCE_N)
        sources=relation_model(source)
        raw_source=raw_model(source)
        training={family:observed(seed,family,TARGET_N) for family in TARGETS}
        costs={
          name:{"observations":len(rows),
                "harmful":sum(int(x["damage"]) for x in rows),
                "productive":sum(int(x["progress"]) for x in rows),
                "neutral":sum(int(not x["progress"] and not x["damage"]) for x in rows)}
          for name,rows in (("basin",source),*training.items())}
        checkpoints={}
        for family in TARGETS:
            target_trials={}
            for count in CHECKPOINTS:
                history=source+training[family][:count]
                learned=RelationOutcomeMemory.restore(relation_model(history).record())
                frozen=RelationOutcomeMemory.restore(sources.record())
                target=relation_model(training[family][:count])
                raw=raw_model(history)
                policies={"transfer_range":learned,
                          "source_frozen_range":frozen,
                          "target_only_range":target,
                          "raw_schema_memory":raw}
                snapshots={key:(m.record() if m.events else None)
                           for key,m in policies.items()}
                scores={
                  env:{
                    mode:summarize([play(seed,env,TEST_START+i,mode,policies)
                                    for i in range(TEST_N)])
                    for mode in METHODS}
                  for env in ("basin",family)}
                if any((m.record() if m.events else None)!=snapshots[name]
                       for name,m in policies.items()):
                    raise AssertionError("held-out scoring updated learned model")
                target_trials[str(count)]={
                    "target_observations":count,
                    "trained_events":len(history),
                    "training_checkpoint_sha256":snapshots["transfer_range"]["sha256"],
                    "counts_by_span":learned.counts,
                    "scores":scores}
            checkpoints[family]=target_trials
        report["rows"].append({"seed":seed,"private_source_band_scoring_only":band(seed),
                               "training_actor_costs":costs,"checkpoints":checkpoints})
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--cohort",choices=("development","additional"),default="development")
    x=p.parse_args()
    print(json.dumps(measure(DEV if x.cohort=="development" else ADDITIONAL),
                     indent=2,sort_keys=True))


if __name__=="__main__":
    main()
