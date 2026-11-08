"""Independent-landmark geometry experiment; no regime/position labels to fits.

The harness constructs labelled simulator conditions and scores actual navigation;
model training is ordinary (command, odometry, mark) histories with start beacon.
Previously inspected seed groups are NOT blind. Policy receives no hidden state.
"""
from __future__ import annotations

import argparse
import json
import random

from developmental_ai.adaptive_dynamics import ACTIONS, CalibrationWorld, AdaptiveNavigator, KnownPhysicsOracle
from developmental_ai.flexible_landmarks import SCHEMA, fit_flexible
from developmental_ai.online_dynamics import fit, score
from developmental_ai.structured_landmarks import fit_structured
from developmental_ai.uncertain_navigation import seed_for

CONDITIONS = {
    # Existing high-noise geometry, correctly described by the older family.
    "known_half": {"noise": "high", "sites": {"9": [2, 6], "11": [2, 7]}},
    # Two identifiable landmarks at non-half distances, never passed to fits.
    "unequal_two": {"noise": "high", "sites": {"9": [1, 3], "11": [1, 8]}},
    # No second landmark; the absent role must not be hallucinated into the map.
    "one_site": {"noise": "standard", "sites": {"9": [3, None], "11": [7, None]}},
    # Background false positive readings, with no actual landmark sites.
    "no_sites": {"noise": "standard", "sites": {"9": [None, None], "11": [None, None]}},
}


class FlexibleWorld(CalibrationWorld):
    def __init__(self, seed, split, index, condition):
        if type(condition) is not dict or set(condition) != {"noise", "sites"} or condition["noise"] not in ("standard", "high"):
            raise ValueError("invalid test environment")
        from developmental_ai.flexible_landmarks import _check_sites
        _check_sites(condition["sites"])
        self.experiment_sites = condition["sites"]
        super().__init__(seed, split, index, condition["noise"], "fixed")

    def _landmark(self):
        site_a, site_b = self.experiment_sites[str(self.n)]
        role = 0 if self.pos == site_a else 1 if self.pos == site_b else None
        draw = self.rng.random()
        if role is None:
            return 0 if draw < .01 else 1 if draw < .02 else None
        return role if draw < .85 else 1-role if draw < .86 else None


class FlexOracle(KnownPhysicsOracle):
    def __init__(self, condition):
        super().__init__(condition["noise"], "fixed")
        self.sites = condition["sites"]

    def landmark_probs(self, n, position):
        a, b = self.sites[str(n)]
        if position == a:
            return (.14, .85, .01)
        if position == b:
            return (.14, .01, .85)
        return (.98, .01, .01)


def observation_history(seed, split, index, condition, *, steps=12):
    world = FlexibleWorld(seed, split, index, condition)
    initial = world.initial_observation()["beacon"][0]
    rng = random.Random(seed_for(seed, split, index, "policy"))
    observations = []
    for _ in range(steps):
        action = rng.randrange(2)
        sensed, _, _, _ = world.step(action)
        observations.append((ACTIONS[action], sensed["odometry"], sensed["landmark"]))
    return {"n": world.n, "initial": initial, "observations": observations}


def navigate(model, seed, index, condition):
    world = FlexibleWorld(seed, "test", index, condition)
    controller = AdaptiveNavigator(world.initial, world.goal, world.n, model)
    terminal = None
    while not world.done:
        action = controller.heuristic()
        sensed, _, _, terminal = world.step(action)
        controller.advance(action, sensed)
    return terminal == "success"


def measure(seeds=(17,23,41), *, train_episodes=70, iterations=5,
            map_histories=24, test_episodes=30, navigation_episodes=40,
            conditions=("known_half", "unequal_two", "one_site", "no_sites")):
    if (type(seeds) not in (list,tuple) or len(seeds)==0 or len(set(seeds))!=len(seeds) or
        any(type(s) is not int for s in seeds) or
        any(type(x) is not int or x < 1 for x in (train_episodes,iterations,test_episodes,navigation_episodes)) or
        type(map_histories) is not int or not 2 <= map_histories <= train_episodes or
        type(conditions) not in (list,tuple) or not conditions or len(set(conditions)) != len(conditions) or
        any(c not in CONDITIONS for c in conditions)):
        raise ValueError("invalid benchmark configuration")
    result = {"schema":SCHEMA, "kind":"previously-inspected-seeds-not-blind",
              "fit_partition":"train/0+", "test_partition":"test/51000+",
              "navigation_partition":"test/57000+", "seeds":list(seeds),
              "train_episodes":train_episodes,"iterations":iterations,
              "map_histories":map_histories,"test_episodes":test_episodes,
              "navigation_episodes":navigation_episodes,"conditions":list(conditions),
              "site_penalty":3.0,
              "notes":"Known ring sizes and two recognizable possible sensor symbols remain fixed priors. Baselines receive identical train/test evidence. Oracle knows true physics/map, not live position. All outcomes include negative results; no default model changes.",
              "rows":[]}
    for seed in seeds:
        row={"seed":seed,"conditions":{}}
        for name in conditions:
            condition=CONDITIONS[name]
            train=[observation_history(seed,"train",i,condition) for i in range(train_episodes)]
            test=[observation_history(seed,"test",51000+i,condition) for i in range(test_episodes)]
            generic,_=fit(train,iterations=iterations)
            half,_=fit_structured(train,iterations=iterations)
            flex,fitdata=fit_flexible(train,iterations=iterations,map_histories=map_histories)
            models={"unconstrained_em":generic,"fixed_half_structure":half,
                    "flexible_sites":flex,"physics_oracle":FlexOracle(condition)}
            row["conditions"][name]={
                "learned_sites":flex.sites,
                "true_sites_for_scoring_only":condition["sites"],
                "mean_observation_log_likelihood":{label:round(score(model,test),5) for label,model in models.items()},
                "navigation_success":{label:round(sum(navigate(model,seed,57000+i,condition) for i in range(navigation_episodes))/navigation_episodes,5) for label,model in models.items()},
                "training_curve":fitdata["fit_curve"],
            }
        result["rows"].append(row)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seeds",nargs="+",type=int,default=[17,23,41])
    p.add_argument("--train",type=int,default=70)
    p.add_argument("--iterations",type=int,default=5)
    p.add_argument("--map-histories",type=int,default=24)
    p.add_argument("--test",type=int,default=30)
    p.add_argument("--navigation",type=int,default=40)
    p.add_argument("--conditions",nargs="+",choices=tuple(CONDITIONS),default=list(CONDITIONS))
    p.add_argument("--out")
    args=p.parse_args()
    data=measure(args.seeds,train_episodes=args.train,iterations=args.iterations,map_histories=args.map_histories,
                 test_episodes=args.test,navigation_episodes=args.navigation,conditions=args.conditions)
    output=json.dumps(data,sort_keys=True,indent=2)+"\n"
    if args.out:
        from pathlib import Path
        Path(args.out).write_text(output,encoding="utf-8")
    print(output,end="")

if __name__ == "__main__":main()
