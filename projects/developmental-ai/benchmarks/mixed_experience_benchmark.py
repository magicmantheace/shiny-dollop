"""Mixed unlabelled regime discovery, train-only validation and untouched tests.

Simulator condition labels are only used by this HARNESS to generate and score
sensor streams, never exposed in histories supplied to learner. All seed groups
in this experimental program have been previously inspected, not blind.
"""
from __future__ import annotations

import argparse
import json

from developmental_ai.adaptive_dynamics import KnownPhysicsOracle, navigate
from developmental_ai.mixed_experience import SCHEMA, fit_mixed, validation_score
from developmental_ai.online_dynamics import trajectory, forward_backward
from developmental_ai.structured_landmarks import fit_structured

REGIMES = (("original", "standard", "fixed"), ("changed", "high", "shifted"))


def history_set(seed, split, beginning, number, mode):
    """Mixed experiences; condition names never appear inside records."""
    if mode not in ("alternating", "blocks", "original_only"):
        raise ValueError("unknown schedule")
    records = []
    for i in range(number):
        regime = 0 if mode == "original_only" else i % 2 if mode == "alternating" else int(i >= number // 2)
        _, noise, layout = REGIMES[regime]
        records.append(trajectory(seed, split, beginning + i, noise, layout))
    return records


def evaluate(seeds=(17, 23, 41), *, train=72, validation=24, test=28,
             iterations=3, rounds=2, schedule="alternating", navigation=24):
    if (type(seeds) not in (list, tuple) or not seeds or len(seeds) != len(set(seeds)) or
            any(type(x) is not int for x in seeds) or
            any(type(x) is not int or x < 4 for x in (train, validation, test, navigation)) or
            train % 2 or validation % 2 or test % 2 or
            schedule not in ("alternating", "blocks", "original_only")):
        raise ValueError("invalid benchmark configuration")
    result = {"schema": SCHEMA, "seeds": list(seeds), "schedule": schedule,
              "kind": "inspected-development-not-blind", "train": train,
              "validation": validation, "test": test, "navigation": navigation,
              "iterations": iterations, "rounds": rounds,
              "partitions": {"fit": "train/0+", "validation": "train/10000+",
                             "evaluation": "test/70000+", "probe": "test/65000+",
                             "navigation": "test/77000+"},
              "notes": "No regime/position labels passed to fitting or selection. Known 9/11 rings and two half-separated sensor markers remain an engineered bias. Test only scores after training and candidate selection. Oracle sees true simulator probability law. Per-seed inspected results, no runtime model promotion.",
              "rows": []}
    for seed in seeds:
        fitting = history_set(seed, "train", 0, train, schedule)
        holdout = history_set(seed, "train", 10000, validation, schedule)
        proposal = fit_mixed(fitting, holdout, seed=seed, iterations=iterations, rounds=rounds)
        group = {"seed": seed, "accepted": proposal.accepted, "kind": proposal.kind,
                 "validation": proposal.validation, "regimes": {}}
        for name, noise, layout in REGIMES:
            if schedule == "original_only" and name == "changed":
                continue
            test_rows = [trajectory(seed, "test", 70000+i, noise, layout) for i in range(test)]
            truth = KnownPhysicsOracle(noise, layout)
            # A second labelled, separately fitted model is only a BENCHMARK upper
            # bound, never an input to proposal. It receives same per-regime train budget.
            trained_oracle = fit_structured([
                trajectory(seed, "train", 40000+i, noise, layout) for i in range(train//2)],
                iterations=iterations)[0]
            # Runtime regime choice is based on five other unlabelled test-namespace
            # probe episodes, not the navigation outcome or the evaluation set.
            probes = [trajectory(seed,"test",65000+i,noise,layout) for i in range(5)]
            selected = proposal.select(probes)
            chosen = proposal.models[selected] if selected is not None else proposal.baseline
            navigation_models = {"single": proposal.baseline,
                                 "mixed_selected_or_fallback": chosen,
                                 "regime_grouped_upper": trained_oracle,
                                 "physics_oracle": truth}
            navigation_success = {label: round(sum(navigate(model,seed,77000+i,noise,layout)
                                                for i in range(navigation))/navigation,6)
                                  for label,model in navigation_models.items()}
            group["regimes"][name] = {
                "navigation_success": navigation_success,
                "probe_selected": selected,
                "single_score": round(validation_score((proposal.baseline,),test_rows),6),
                "unsupervised_score": round(validation_score(proposal.models,test_rows),6),
                "regime_grouped_score": round(validation_score((trained_oracle,),test_rows),6),
                "physics_oracle_score": round(sum(forward_backward(truth,h) for h in test_rows) / sum(len(h["observations"]) for h in test_rows),6),
                "selected": proposal.select(test_rows),
                "model_offsets": [m.offsets for m in proposal.models]}
        result["rows"].append(group)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seeds", nargs="+", type=int, default=[17,23,41])
    p.add_argument("--train", type=int, default=72)
    p.add_argument("--validation", type=int, default=24)
    p.add_argument("--test", type=int, default=28)
    p.add_argument("--iterations", type=int, default=3)
    p.add_argument("--rounds", type=int, default=2)
    p.add_argument("--navigation", type=int, default=24)
    p.add_argument("--schedule", choices=("alternating","blocks","original_only"), default="alternating")
    p.add_argument("--out")
    args = p.parse_args()
    payload = evaluate(args.seeds, train=args.train, validation=args.validation,
                       test=args.test, iterations=args.iterations, rounds=args.rounds,
                       schedule=args.schedule, navigation=args.navigation)
    content = json.dumps(payload, sort_keys=True, indent=2) + "\n"
    if args.out:
        from pathlib import Path
        Path(args.out).write_text(content, encoding="utf-8")
    print(content, end="")

if __name__ == "__main__":
    main()
