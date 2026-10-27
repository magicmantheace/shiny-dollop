"""Frozen baseline versus train-only-calibrated step detector (development audit)."""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from developmental_ai.calibrated_detection import calibrate, verify_calibration, SCHEMA
from developmental_ai.online_dynamics import ModelBank, fit, trajectory
from developmental_ai.step_dynamics import StepDetector

REGIMES = {"original": ("standard", "fixed"), "changed": ("high", "shifted")}
ORDER = ("original", "changed", "original")


def phase_score(detector, seed, phase, episodes):
    truth = ORDER[phase]
    observations = []
    for i in range(episodes):
        h = trajectory(seed, "test", 6000 + phase * episodes + i, *REGIMES[truth])
        detector.begin(h["n"], h["initial"])
        observations.extend(detector.step(*step) for step in h["observations"])
        detector.finish()
    total = len(observations)
    return {
        "regime_for_scoring_only": truth,
        "fraction_correct": round(sum(e["active"] == truth for e in observations) / total, 4),
        "fraction_wrong": round(sum(e["active"] not in (truth, None) for e in observations) / total, 4),
        "fraction_abstained": round(sum(e["active"] is None or e["status"] == "unknown" for e in observations) / total, 4),
        "switches": sum(e["status"] == "switch" for e in observations),
        "first_correct_observation": next((i+1 for i,e in enumerate(observations) if e["active"] == truth), None),
        "final_selected": detector.state["active"],
    }


def measure(seeds=(17,23,41), *, train_episodes=130, iterations=6,
            calibration_episodes=40, phase_episodes=12):
    if (not seeds or len(seeds) != len(set(seeds)) or any(type(s) is not int for s in seeds)
            or any(type(v) is not int or v < 1 for v in (train_episodes, iterations, calibration_episodes, phase_episodes))
            or not 4 <= calibration_episodes <= 512 or train_episodes > 1000
            or iterations > 50 or phase_episodes * 3 * 14 > 4000):
        raise ValueError("invalid benchmark settings")
    result = {
        "schema": SCHEMA, "kind": "inspected-development-not-blind",
        "seed_list": list(seeds), "train_episodes_per_model": train_episodes,
        "calibration_episodes_per_model": calibration_episodes,
        "fit_iterations": iterations, "phase_episodes": phase_episodes,
        "calibration_namespace": "train indices 5000..", "evaluation_namespace": "test indices 6000..",
        "note": "regime truth is used only for offline calibration and scoring, never online selection; threshold is not calibrated confidence",
        "rows": [],
    }
    with tempfile.TemporaryDirectory(prefix="devai-calibrated-") as temp:
        for seed in seeds:
            with ModelBank(Path(temp)/f"models-{seed}.db", seed) as bank:
                for name, condition in REGIMES.items():
                    histories = [trajectory(seed, "train", i, *condition) for i in range(train_episodes)]
                    model, _ = fit(histories, iterations=iterations)
                    bank.save(name, model, len(histories))
                calibration = {
                    name: [trajectory(seed, "train", 5000+i, *cond) for i in range(calibration_episodes)]
                    for name, cond in REGIMES.items()
                }
                profile = calibrate(bank, calibration)
                margin = verify_calibration(bank, profile)
                policies = {}
                for name, threshold in (("frozen_baseline", 0.12), ("offline_calibrated", margin)):
                    with StepDetector(Path(temp)/f"detector-{seed}-{name}.db", bank,
                                      margin=threshold) as detector:
                        policies[name] = [phase_score(detector, seed, p, phase_episodes) for p in range(3)]
                        detector.events()  # validate the entire persisted chain
                result["rows"].append({"seed": seed, "calibration": profile.as_dict(), "strategies": policies})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", nargs="+", type=int, default=[17,23,41])
    parser.add_argument("--train-episodes", type=int, default=130)
    parser.add_argument("--iterations", type=int, default=6)
    parser.add_argument("--calibration-episodes", type=int, default=40)
    parser.add_argument("--phase-episodes", type=int, default=12)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = measure(args.seeds, train_episodes=args.train_episodes,
                     iterations=args.iterations, calibration_episodes=args.calibration_episodes,
                     phase_episodes=args.phase_episodes)
    contents = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.write_text(contents, encoding="utf-8")
    print(contents, end="")


if __name__ == "__main__":
    main()
