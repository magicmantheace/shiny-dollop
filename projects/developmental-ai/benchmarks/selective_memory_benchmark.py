"""Development-only learned write/keep policy and no-memory ablations.

Training uses train/short; evaluation uses disjoint test/short and test/long.
Printed seeds are development seeds; do not describe them as blind holdouts.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from developmental_ai.selective_memory import MODES, SCHEMA, SelectiveBrain


def benchmark(seeds: tuple[int, ...] = (11, 31, 73), training: int = 6000,
              testing: int = 400) -> dict:
    if not seeds or len(set(seeds)) != len(seeds) or any(type(s) is not int for s in seeds):
        raise ValueError("seeds must be unique integers")
    if type(training) is not int or type(testing) is not int or training < 1 or testing < 1:
        raise ValueError("positive evaluation size required")
    rows = []
    with tempfile.TemporaryDirectory() as root:
        for seed in seeds:
            for mode in MODES:
                db = Path(root) / f"seed-{seed}-{mode}.db"
                with SelectiveBrain(db, seed, mode) as brain:
                    before = brain.evaluate(testing)
                    brain.train(training)
                    short = brain.evaluate(testing, "short")
                    long = brain.evaluate(testing, "long")
                rows.append({"seed": seed, "mode": mode,
                             "before_long": before["accuracy"],
                             "after_short": short["accuracy"],
                             "after_long": long["accuracy"],
                             "retention_long": long["target_retention"]})
    return {"schema": SCHEMA, "protocol": {
        "train_split": "train", "train_band": "short", "test_split": "test",
        "testing_bands": ["short", "long"], "training_episodes": training,
        "testing_episodes": testing, "seeds": list(seeds),
        "evaluation": "development (all seeds inspected)"}, "rows": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", nargs="+", type=int, default=[11, 31, 73])
    parser.add_argument("--train-episodes", type=int, default=6000)
    parser.add_argument("--test-episodes", type=int, default=400)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    data = benchmark(tuple(args.seeds), args.train_episodes, args.test_episodes)
    result = json.dumps(data, indent=2) + "\n"
    if args.output:
        args.output.write_text(result, encoding="utf-8")
    print(result, end="")


if __name__ == "__main__":
    main()
