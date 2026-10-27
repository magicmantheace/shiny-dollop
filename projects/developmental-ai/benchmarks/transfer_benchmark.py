"""Reproducible seeded generalization benchmark (standard library only)."""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from developmental_ai.transfer import TransferBrain


def measure(seed: int, train_episodes: int, test_episodes: int) -> dict:
    """Fresh private training database; hold-out layout seeds never enter training."""
    with tempfile.TemporaryDirectory() as temp:
        brain = TransferBrain(Path(temp) / "training.sqlite3", seed=seed)
        try:
            before = brain.evaluate(test_episodes, "test")
            brain.train(train_episodes)
            after = brain.evaluate(test_episodes, "test")
        finally:
            brain.close()
    return {"seed": seed, "before": before, "after": after,
            "success_gain": round(after["success_rate"] - before["success_rate"], 4)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", nargs="+", type=int, default=[17, 23, 41])
    parser.add_argument("--train-episodes", type=int, default=5000)
    parser.add_argument("--test-episodes", type=int, default=300)
    args = parser.parse_args()
    if not args.seeds or args.train_episodes < 1 or args.test_episodes < 1:
        parser.error("nonempty seeds and positive episode counts required")
    results = [measure(seed, args.train_episodes, args.test_episodes)
               for seed in args.seeds]
    print(json.dumps({"benchmark": "transfer-v1", "train_episodes": args.train_episodes,
                      "test_episodes": args.test_episodes, "results": results}, indent=2))


if __name__ == "__main__":
    main()
