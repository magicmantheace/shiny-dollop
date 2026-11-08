"""Development-set benchmark: delayed cue vs reactive and overwrite ablations.

Protocol: all learners train only with short delays and are tested on separate
long-delay namespaces; these seeds are public development data, not blind proof.
"""
from __future__ import annotations
import argparse
import json
import tempfile
from pathlib import Path
from developmental_ai.delayed_choice import DelayBrain, MODES, SCHEMA


def benchmark(seeds: tuple[int, ...] = (11, 31, 73), training: int = 800,
              testing: int = 400) -> dict:
    if not seeds or len(seeds) != len(set(seeds)) or training < 1 or testing < 1:
        raise ValueError("unique seeds and positive episode counts required")
    rows = []
    with tempfile.TemporaryDirectory() as root:
        for seed in seeds:
            for mode in MODES:
                path = Path(root) / f"{seed}-{mode}.db"
                with DelayBrain(path, seed, mode) as brain:
                    before = brain.evaluate(testing, "long")
                    brain.train(training)
                    after_short = brain.evaluate(testing, "short")
                    after_long = brain.evaluate(testing, "long")
                rows.append({"seed": seed, "mode": mode,
                             "before_long": before["success_rate"],
                             "after_short": after_short["success_rate"],
                             "after_long": after_long["success_rate"]})
    return {"schema": SCHEMA, "protocol": {"training_band": "short", "test_split": "test",
             "test_bands": ["short", "long"], "training_episodes": training,
             "test_episodes": testing, "seeds": list(seeds), "evaluation": "development"},
            "rows": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", nargs="+", type=int, default=[11, 31, 73])
    parser.add_argument("--train-episodes", type=int, default=800)
    parser.add_argument("--test-episodes", type=int, default=400)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = benchmark(tuple(args.seeds), args.train_episodes, args.test_episodes)
    formatted = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(formatted, encoding="utf-8")
    print(formatted, end="")


if __name__ == "__main__":
    main()
