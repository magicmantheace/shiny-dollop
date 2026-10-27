"""Inspectable development-only occluded-navigation benchmark, with ablations."""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from developmental_ai.occluded_navigation import OccludedBrain, SCHEMA


def run(seeds=(7, 23, 41), train_episodes=3000, test_episodes=200) -> dict:
    if not seeds or train_episodes < 1 or test_episodes < 1:
        raise ValueError("nonempty seeds and positive episodes required")
    outputs = []
    with tempfile.TemporaryDirectory() as tmp:
        for seed in seeds:
            with OccludedBrain(Path(tmp) / f"{seed}-memory.db", seed, "memory") as mem:
                before = mem.evaluate(test_episodes)
                mem.train(train_episodes)
                after = mem.evaluate(test_episodes)
                greedy = mem.evaluate(test_episodes, "greedy")
                oracle = mem.evaluate(test_episodes, "oracle")
            with OccludedBrain(Path(tmp) / f"{seed}-reactive.db", seed, "reactive") as reactive:
                reactive.train(train_episodes)
                forget = reactive.evaluate(test_episodes)
                random = reactive.evaluate(test_episodes, "random")
            outputs.append({"seed": seed, "memory_untrained": before, "memory_trained": after,
                            "reactive_trained": forget, "reactive_random": random,
                            "memory_greedy": greedy, "full_map_oracle": oracle})
    return {"schema": SCHEMA, "status": "development_seed_only", "train_episodes": train_episodes,
            "test_episodes": test_episodes, "seeds": list(seeds), "results": outputs,
            "limitations": ["The target offset is visible at reset only.",
                            "Memory retention and exact odometry are engineered, not learned.",
                            "Layouts share the existing procedural distribution; seeds are not blind.",
                            "The full-map oracle has privileged simulation information."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", nargs="+", type=int, default=[7, 23, 41])
    parser.add_argument("--train-episodes", type=int, default=3000)
    parser.add_argument("--test-episodes", type=int, default=200)
    args = parser.parse_args()
    print(json.dumps(run(args.seeds, args.train_episodes, args.test_episodes), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
