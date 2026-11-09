"""Grid-trained public-sensor transition memory transferred to occluded grid.

The target memory slot, observation mapping and tabular navigation Q policy are
engineered. The action/outcome -> offset update is learned only on visible-grid
train observations; never from hidden positions or occluded training rewards.
"""
from __future__ import annotations
import argparse
import json
import random
import tempfile
from pathlib import Path

from developmental_ai.cross_family_transfer import SpatialEncoder
from developmental_ai.environment_api import EnvironmentSession
from developmental_ai.learned_spatial_memory import PortableOffsetMemory, train_grid_updates
from developmental_ai.transfer import TransferBrain
from benchmarks.environment_contract_benchmark import action_seed

SCHEMA = "developmental-ai.learned-memory-transfer-benchmark/v1"
DEVELOPMENT_SEEDS = (2749, 6607, 9901)


def trial(brain, updater, *, seed, index, mode, split="test"):
    """Runs ONLY public frames, actions, and feedback; no policy weight updates."""
    if mode not in ("learned", "engineered", "forget", "random") or split not in ("train", "test"):
        raise ValueError("invalid benchmark method")
    session = EnvironmentSession("occluded", seed, split, index)
    encoder = SpatialEncoder("occluded") if mode == "engineered" else PortableOffsetMemory(updater, retain=mode != "forget")
    rng = random.Random(action_seed(seed, split, index, "occluded", "learned_memory_common" if mode != "random" else "learned_memory_random"))
    last = ""
    while not session.done:
        frame = session.frame()
        state = encoder.features(frame)
        action = rng.randrange(5) if mode == "random" else brain._choose(state, 0, rng)
        result = session.step(action, expected_tick=frame["tick"])
        encoder.feedback(action, result)
        last = result["event"]
    return {"success": last == "collected", "steps": session.tick}


def measure(*, seeds=DEVELOPMENT_SEEDS, train_q=1200, train_memory=80, episodes=64,
            start_index=80000):
    if (type(seeds) not in (list, tuple) or not seeds or len(set(seeds)) != len(seeds) or
            any(type(s) is not int for s in seeds) or
            any(type(x) is not int for x in (train_q, train_memory, episodes, start_index)) or
            not 1 <= train_q <= 10000 or not 1 <= train_memory <= 2000 or
            not 1 <= episodes <= 300 or not 0 <= start_index < 999000 or
            start_index + episodes > 1000000):
        raise ValueError("invalid benchmark configuration")
    result = {"schema": SCHEMA, "purpose": "exploratory D3 learned memory-update transfer",
              "blind": False, "train_family": "grid", "evaluation_family": "occluded",
              "policy_train_grid_episodes": train_q, "updater_train_grid_episodes": train_memory,
              "eval_test_start": start_index, "eval_episodes_per_seed": episodes,
              "evaluation_note": "Previously examined seed family and a new test episode range; not independent blind validation. Cue write, action/event labels and fixed Q features remain engineered.",
              "rows": []}
    for seed in seeds:
        updater = train_grid_updates(seed, train_memory)
        with tempfile.TemporaryDirectory() as d:
            brain = TransferBrain(Path(d) / "policy.db", seed=seed)
            try:
                brain.train(train_q)
                for mode in ("random", "forget", "engineered", "learned"):
                    runs = [trial(brain, updater, seed=seed, index=start_index+i, mode=mode)
                            for i in range(episodes)]
                    result["rows"].append({"seed": seed, "mode": mode,
                              "successes": sum(r["success"] for r in runs),
                              "success_rate": round(sum(r["success"] for r in runs) / episodes, 5),
                              "mean_steps": round(sum(r["steps"] for r in runs) / episodes, 4)})
            finally:
                brain.close()
        result.setdefault("updater_evidence", []).append({"seed": seed, "fingerprint": updater.fingerprint,
          "learned_updates": updater.updates, "sample_count": sum(sum(v.values()) for v in updater.counts.values())})
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seeds", nargs="+", type=int, default=list(DEVELOPMENT_SEEDS))
    p.add_argument("--train-q", type=int, default=1200)
    p.add_argument("--train-memory", type=int, default=80)
    p.add_argument("--episodes", type=int, default=64)
    p.add_argument("--out", type=Path)
    args=p.parse_args()
    data = json.dumps(measure(seeds=args.seeds,train_q=args.train_q,
              train_memory=args.train_memory,episodes=args.episodes), indent=2,sort_keys=True) + "\n"
    if args.out: args.out.write_text(data, encoding="utf-8")
    print(data, end="")

if __name__ == "__main__": main()
