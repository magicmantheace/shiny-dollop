"""Development-only cross-split multi-start latent-model comparison.

All optimization/selection uses disjoint train-namespace histories; only the
benchmark reads the simulated regime label and the separate test histories.
The historical single-start online_dynamics results are not overwritten.
"""
from __future__ import annotations

import argparse
import json

from developmental_ai.adaptive_dynamics import KnownPhysicsOracle, navigate
from developmental_ai.online_dynamics import fit, score, trajectory
from developmental_ai.robust_world_model import SCHEMA, fit_robust

REGIMES = {"original": ("standard", "fixed"), "changed": ("high", "shifted")}


def measure(seeds=(17, 23, 41), *, train_episodes=140, validation_episodes=45,
            test_episodes=50, iterations=8, starts=3, navigation_episodes=20):
    if (type(seeds) not in (list, tuple) or not seeds or len(set(seeds)) != len(seeds)
            or any(type(seed) is not int for seed in seeds)
            or any(type(n) is not int or n < 1 for n in (train_episodes, validation_episodes,
                                                        test_episodes, iterations, starts, navigation_episodes))):
        raise ValueError("invalid benchmark input")
    out = {"schema": SCHEMA, "kind": "inspected-development-not-blind",
           "seeds": list(seeds), "training_count": train_episodes,
           "validation_count": validation_episodes, "test_count": test_episodes,
           "iterations": iterations, "starts": starts,
           "navigation_episodes": navigation_episodes,
           "partitions": {"fit": "train 0+", "validation": "train 2500+", "test": "test 9000+"},
           "notes": "No simulator truth in training, validation or model selection. Oracle only for comparison. Held-out test results inspected after design; not blind.",
           "rows": []}
    for seed in seeds:
        models = {"baseline": {}, "multistart": {}}
        row = {"seed": seed, "regimes": {}, "selection": {}}
        for name, (noise, layout) in REGIMES.items():
            fitting = [trajectory(seed, "train", i, noise, layout) for i in range(train_episodes)]
            validation = [trajectory(seed, "train", 2500+i, noise, layout) for i in range(validation_episodes)]
            testing = [trajectory(seed, "test", 9000+i, noise, layout) for i in range(test_episodes)]
            fixed, _ = fit(fitting, iterations=iterations)
            robust, receipt = fit_robust(fitting, validation, seed=seed, iterations=iterations, starts=starts)
            oracle = KnownPhysicsOracle(noise, layout)
            models["baseline"][name], models["multistart"][name] = fixed, robust
            def nav(model):
                return round(sum(navigate(model, seed, 14000+i, noise, layout)
                                 for i in range(navigation_episodes))/navigation_episodes, 4)
            row["regimes"][name] = {
                "chosen_start": receipt["chosen_start"],
                "validation_scores": receipt["validation_scores"],
                "baseline_test_log_likelihood": round(score(fixed, testing), 6),
                "multistart_test_log_likelihood": round(score(robust, testing), 6),
                "oracle_test_log_likelihood": round(score(oracle, testing), 6),
                "baseline_navigation": nav(fixed),
                "multistart_navigation": nav(robust),
                "oracle_navigation": nav(oracle),
            }
        for method in ("baseline", "multistart"):
            selections = {}
            for true_name, condition in REGIMES.items():
                probes = [trajectory(seed, "test", 16000+i, *condition) for i in range(test_episodes)]
                likelihoods = {name: score(model, probes) for name, model in models[method].items()}
                prediction = max(sorted(likelihoods), key=likelihoods.get)
                selections[true_name] = {"predicted": prediction, "correct": prediction == true_name,
                                         "scores": {key: round(value, 6) for key, value in likelihoods.items()}}
            row["selection"][method] = selections
        out["rows"].append(row)
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seeds", nargs="+", type=int, default=[17, 23, 41])
    p.add_argument("--train-episodes", type=int, default=140)
    p.add_argument("--validation-episodes", type=int, default=45)
    p.add_argument("--test-episodes", type=int, default=50)
    p.add_argument("--iterations", type=int, default=8)
    p.add_argument("--starts", type=int, default=3)
    p.add_argument("--navigation-episodes", type=int, default=20)
    p.add_argument("--out")
    a = p.parse_args()
    payload = measure(a.seeds, train_episodes=a.train_episodes, validation_episodes=a.validation_episodes,
                      test_episodes=a.test_episodes, iterations=a.iterations, starts=a.starts,
                      navigation_episodes=a.navigation_episodes)
    contents = json.dumps(payload, indent=2, sort_keys=True)+"\n"
    if a.out:
        from pathlib import Path
        Path(a.out).write_text(contents, encoding="utf-8")
    print(contents, end="")


if __name__ == "__main__":
    main()
