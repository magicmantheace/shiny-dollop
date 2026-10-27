"""Development-set multi-task transfer benchmark; never a blind evaluation."""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from developmental_ai.curriculum import CurriculumBrain, TASKS


def measure(seed: int, train_episodes: int, test_episodes: int,
            train_tasks: tuple[str, ...]) -> dict:
    with tempfile.TemporaryDirectory() as temp:
        with CurriculumBrain(Path(temp) / "research.sqlite3", seed=seed) as brain:
            before = {task: brain.evaluate(task, test_episodes) for task in TASKS}
            brain.train(train_episodes, train_tasks)
            after = {task: brain.evaluate(task, test_episodes) for task in TASKS}
            random = {task: brain.evaluate(task, test_episodes, policy="random") for task in TASKS}
            greedy = {task: brain.evaluate(task, test_episodes, policy="greedy") for task in TASKS}
            oracle = {task: brain.evaluate(task, test_episodes, policy="oracle") for task in TASKS}
    return {"seed": seed, "tasks": {task: {
        "untrained": before[task], "trained": after[task],
        "random": random[task], "greedy": greedy[task], "oracle": oracle[task],
        "success_gain": round(after[task]["success_rate"] - before[task]["success_rate"], 4),
    } for task in TASKS}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", nargs="+", type=int, default=[13, 29, 47])
    parser.add_argument("--train-episodes", type=int, default=3500)
    parser.add_argument("--test-episodes", type=int, default=150)
    parser.add_argument("--train-tasks", nargs="+", choices=TASKS, default=["collect"])
    args = parser.parse_args()
    if args.train_episodes < 1 or args.test_episodes < 1 or len(set(args.train_tasks)) != len(args.train_tasks):
        parser.error("positive episode counts and distinct training tasks required")
    results = [measure(seed, args.train_episodes, args.test_episodes,
                       tuple(args.train_tasks)) for seed in args.seeds]
    print(json.dumps({"benchmark": "curriculum-v1", "status": "development-seeds-inspected",
                      "training_tasks": args.train_tasks, "train_episodes": args.train_episodes,
                      "test_episodes": args.test_episodes, "results": results}, indent=2))


if __name__ == "__main__":
    main()
