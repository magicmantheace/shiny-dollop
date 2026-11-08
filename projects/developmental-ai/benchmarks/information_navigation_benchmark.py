"""Development benchmark: action-value of expected information, not general AI.

Predeclare weights; choose them *only* on independent train-namespace
navigation trials. Never tune to test results. Report every seed/regime and
baseline, including regressions. Hidden state is read only by the scorer.
"""
from __future__ import annotations

import argparse
import json
import math

from developmental_ai.adaptive_dynamics import CalibrationWorld, KnownPhysicsOracle, AdaptiveNavigator
from developmental_ai.information_navigation import InformationNavigator, SCHEMA
from developmental_ai.online_dynamics import fit, trajectory

REGIMES = {"original": ("standard", "fixed"), "changed": ("high", "shifted")}
WEIGHTS = (0.0, 0.5, 1.5)  # fixed a priori; 0.0 is the exact legacy policy


def trial(model, seed, split, index, regime, weight):
    world = CalibrationWorld(seed, split, index, *regime)
    nav = InformationNavigator(world.initial, world.goal, world.n, model, information_weight=weight)
    true_probability, covered, brier, steps, outcome = 0., 0, 0., 0, None
    while not world.done:
        action = nav.choose()
        seen, _, _, outcome = world.step(action)
        nav.advance(action, seen)
        # Benchmark-only state inspection: never an agent observation.
        probs = nav.probs
        true_probability += probs[world.pos]
        brier += sum((p - float(pos == world.pos)) ** 2 for pos, p in enumerate(probs))
        ranking = sorted(range(world.n), key=lambda k: (-probs[k], k))
        cumulative, subset = 0., set()
        for pos in ranking:
            cumulative += probs[pos]
            subset.add(pos)
            if cumulative >= .8 - 1e-12:
                break
        covered += int(world.pos in subset)
        steps += 1
    return {"success": int(outcome == "success"), "steps": steps,
            "p_true": true_probability / steps,
            "brier": brier / steps,
            "cred80_covered": covered / steps}


def aggregate(model, seed, split, start, episodes, regime, weight):
    trials = [trial(model, seed, split, start+i, regime, weight) for i in range(episodes)]
    return {k: round(sum(x[k] for x in trials) / episodes, 5) for k in trials[0]}


def measure(seeds=(17, 23, 41), *, fitting=65, iterations=5,
            tune_episodes=25, test_episodes=60):
    if (type(seeds) not in (list, tuple) or not seeds or
            any(type(s) is not int for s in seeds) or len(set(seeds)) != len(seeds) or
            any(type(k) is not int or k < 1 for k in (fitting, iterations, tune_episodes, test_episodes)) or
            fitting >= 4000 or iterations > 50):
        raise ValueError("invalid benchmark configuration")
    result = {"schema": SCHEMA, "kind": "inspected-development-not-blind",
              "seeds": list(seeds), "model_fit_train_histories": fitting,
              "model_fit_iterations": iterations,
              "weight_candidates": list(WEIGHTS), "tuning_episodes": tune_episodes,
              "test_episodes": test_episodes, "indices": {"fit": "train/0+",
              "policy_selection": "train/7000+", "evaluation": "test/18000+"},
              "note": "True positions used by scorer only. Control uses engineered Bayes filter, not a learned planning policy. Chosen weight uses training navigation feedback; test data never choose weights. Every seed already inspected historically.",
              "rows": []}
    for seed in seeds:
        row = {"seed": seed, "regimes": {}}
        for name, regime in REGIMES.items():
            training = [trajectory(seed, "train", i, *regime) for i in range(fitting)]
            model, _ = fit(training, iterations=iterations)
            oracle = KnownPhysicsOracle(*regime)
            tune = {w: aggregate(model, seed, "train", 7000, tune_episodes, regime, w)["success"] for w in WEIGHTS}
            # Selection is fixed before seeing test outcomes, tie -> legacy 0.
            weight = max(WEIGHTS, key=lambda w: (tune[w], -w))
            frozen = aggregate(model, seed, "test", 18000, test_episodes, regime, 0.)
            selected = aggregate(model, seed, "test", 18000, test_episodes, regime, weight)
            truth_legacy = aggregate(oracle, seed, "test", 18000, test_episodes, regime, 0.)
            truth_info = aggregate(oracle, seed, "test", 18000, test_episodes, regime, weight)
            row["regimes"][name] = {"tune_success": {str(w): tune[w] for w in WEIGHTS},
                                     "chosen_weight": weight,
                                     "legacy": frozen,
                                     "selected_information": selected,
                                     "physics_oracle_legacy": truth_legacy,
                                     "physics_oracle_information": truth_info}
        result["rows"].append(row)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seeds", nargs="+", type=int, default=[17, 23, 41])
    p.add_argument("--fit", type=int, default=65)
    p.add_argument("--iterations", type=int, default=5)
    p.add_argument("--tune", type=int, default=25)
    p.add_argument("--test", type=int, default=60)
    p.add_argument("--out")
    a = p.parse_args()
    result = measure(a.seeds, fitting=a.fit, iterations=a.iterations, tune_episodes=a.tune, test_episodes=a.test)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(rendered)
    print(rendered, end="")


if __name__ == "__main__":
    main()
