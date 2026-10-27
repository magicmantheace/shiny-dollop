"""Held-out candidate model review versus existing immutable snapshots.

Review labels describe synthetic conditions for data generation only. They are
not supplied to candidate scoring. Nothing is promoted during this benchmark.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from developmental_ai.online_dynamics import ModelBank, fit, score, trajectory
from developmental_ai.step_dynamics import CandidateStore, catalogue

SCHEMA = "candidate-review-benchmark/v1"
ARMS = {
    "missing_original": {"known": {"changed": ("high", "shifted")}, "candidate": ("standard", "fixed")},
    "mixed_novelty": {"known": {"changed": ("high", "shifted"), "original": ("standard", "fixed")}, "candidate": ("high", "fixed")},
}


def measure(seeds=(17, 23, 41), *, fit_episodes=75, candidate_episodes=80,
            review_episodes=40, test_episodes=60, iterations=5, min_gain=.02):
    if (type(seeds) not in (tuple, list) or not seeds or len(seeds) != len(set(seeds))
        or any(type(s) is not int for s in seeds)
        or any(type(v) is not int or v < 1 for v in
               (fit_episodes, candidate_episodes, review_episodes, test_episodes, iterations))
        or not 24 <= review_episodes <= 500 or fit_episodes > 500 or candidate_episodes > 500
        or test_episodes > 500 or not 1 <= iterations <= 30 or not 0 <= min_gain <= 2):
        raise ValueError("invalid benchmark protocol")
    report = {"schema": SCHEMA, "kind": "inspected-development-not-blind",
              "seeds": list(seeds), "training_histories_per_existing": fit_episodes,
              "candidate_training_histories": candidate_episodes,
              "review_histories": review_episodes, "independent_test_histories": test_episodes,
              "iterations": iterations, "minimum_review_improvement": min_gain,
              "fit_split": "train 0..", "candidate_split": "train 2000..",
              "validation_split": "train 5000..", "test_split": "test 12000..",
              "notes": "Review separated from candidate fitting. Independent test is never consulted by review. Synthetic ring with known topology; no real-world action permissions.",
              "rows": []}
    with tempfile.TemporaryDirectory(prefix="devai-review-") as folder:
        for seed in seeds:
            for arm, conditions in ARMS.items():
                root = Path(folder)
                with ModelBank(root / f"bank-{seed}-{arm}.db", seed) as bank:
                    for name, regime in conditions["known"].items():
                        training = [trajectory(seed, "train", i, *regime) for i in range(fit_episodes)]
                        model, _ = fit(training, iterations=iterations)
                        bank.save(name, model, len(training))
                    prior, fingerprint = catalogue(bank)
                    with CandidateStore(root / f"staged-{seed}-{arm}.db", seed, fingerprint) as stage:
                        for i in range(candidate_episodes):
                            stage.add(trajectory(seed, "train", 2000+i, *conditions["candidate"]), catalogue=fingerprint)
                        ticket = stage.propose(iterations=iterations)
                        heldout = [trajectory(seed, "train", 5000+i, *conditions["candidate"])
                                   for i in range(review_episodes)]
                        review = stage.review(bank, heldout, min_gain=min_gain)
                        assert stage.get_review(bank) == review
                        test = [trajectory(seed, "test", 12000+i, *conditions["candidate"])
                                for i in range(test_episodes)]
                        best_prior = max(score(model, test) for model in prior.values())
                        test_gain = round(score(stage.get_candidate()[0], test) - best_prior, 8)
                        assert bank.conn.execute("SELECT COUNT(*) FROM online_models").fetchone()[0] == len(prior)
                        report["rows"].append({"seed": seed, "arm": arm,
                                               "review_gain": review["gain"],
                                               "review_passed": review["passed"],
                                               "test_gain_not_used_in_review": test_gain,
                                               "independent_test_improved": test_gain >= min_gain,
                                               "automatic_promotions": 0,
                                               "candidate_digest": ticket["model_digest"],
                                               "review_digest": review["review_digest"]})
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", nargs="+", type=int, default=[17, 23, 41])
    parser.add_argument("--fit-episodes", type=int, default=75)
    parser.add_argument("--candidate-episodes", type=int, default=80)
    parser.add_argument("--review-episodes", type=int, default=40)
    parser.add_argument("--test-episodes", type=int, default=60)
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--min-gain", type=float, default=.02)
    parser.add_argument("--out", type=Path)
    options = parser.parse_args()
    result = measure(options.seeds, fit_episodes=options.fit_episodes,
                     candidate_episodes=options.candidate_episodes,
                     review_episodes=options.review_episodes,
                     test_episodes=options.test_episodes,
                     iterations=options.iterations, min_gain=options.min_gain)
    output = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if options.out:
        options.out.write_text(output, encoding="utf-8")
    print(output, end="")

if __name__ == "__main__":
    main()
