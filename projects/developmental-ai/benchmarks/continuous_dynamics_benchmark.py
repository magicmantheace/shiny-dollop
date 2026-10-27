"""Reproducible *development* stream adaptation; true regime labels for scoring only.

The learner observes initial beacons, commands, odometry, and landmarks. It
never receives these benchmark schedule labels or privileged transition truth.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from developmental_ai.adaptive_dynamics import KnownPhysicsOracle, navigate
from developmental_ai.continuous_dynamics import SCHEMA, StreamMonitor
from developmental_ai.online_dynamics import ModelBank, fit, trajectory

CONDITIONS = {"original": ("standard", "fixed"), "changed": ("high", "shifted")}


def measure(seeds=(17, 23, 41), train_episodes=350, iterations=10, phase_episodes=25,
            navigation_episodes=15):
    if (not seeds or len(set(seeds)) != len(seeds) or
        any(type(s) is not int for s in seeds) or
        not all(type(v) is int and v > 0 for v in (train_episodes, iterations, phase_episodes, navigation_episodes)) or
        phase_episodes < 8 or phase_episodes * 3 > 500):
        raise ValueError("invalid benchmark parameters")
    result = {"schema": SCHEMA, "kind": "inspected-development-not-blind",
              "seeds": list(seeds), "train_episodes_per_model": train_episodes,
              "iterations": iterations, "phase_episodes": phase_episodes,
              "navigation_episodes_per_phase": navigation_episodes,
              "order": ["original", "changed", "original"],
              "note": "the monitor sees only ordinary unlabelled histories; benchmark truth is used only for measurement",
              "rows": []}
    with tempfile.TemporaryDirectory(prefix="devai-stream-") as folder:
        for seed in seeds:
            model_db = Path(folder) / f"models-{seed}.db"
            state_db = Path(folder) / f"stream-{seed}.db"
            with ModelBank(model_db, seed) as bank:
                for name, (noise, layout) in CONDITIONS.items():
                    samples = [trajectory(seed, "train", i, noise, layout) for i in range(train_episodes)]
                    model, _ = fit(samples, iterations=iterations)
                    bank.save(name, model, train_episodes)
                models = {name: bank.get(name) for name in CONDITIONS}
                phases = []
                with StreamMonitor(state_db, bank) as stream:
                    for stage, regime in enumerate(result["order"]):
                        condition = CONDITIONS[regime]
                        readings = []
                        for j in range(phase_episodes):
                            index = 6000 + stage * phase_episodes + j
                            h = trajectory(seed, "test", index, *condition)
                            readings.append(stream.observe(h))
                        successes = sum(ev["selected"] == regime and ev["status"] != "unknown" for ev in readings)
                        after_start = next((j + 1 for j, ev in enumerate(readings) if ev["selected"] == regime and ev["status"] != "unknown"), None)
                        switches = sum(ev["status"] == "switch" for ev in readings)
                        # Independent navigation worlds; monitor receives no navigation outcomes.
                        nav_indices = range(10000 + stage * navigation_episodes,
                                            10000 + (stage+1) * navigation_episodes)
                        # Each navigation trial uses the model selected *at the end* of
                        # the corresponding stream phase (not secret regime metadata).
                        chosen = readings[-1]["selected"]
                        def nav(model):
                            if model is None:
                                return None
                            return round(sum(navigate(model, seed, i, *condition) for i in nav_indices)
                                         / navigation_episodes, 4)
                        phases.append({
                            "regime_for_scoring_only": regime,
                            "final_selected": chosen,
                            "correct_steps": successes,
                            "fraction_correct": round(successes/phase_episodes, 4),
                            "first_correct_step": after_start,
                            "switch_events": switches,
                            "final_status": readings[-1]["status"],
                            "mean_end_model_log_likelihoods": readings[-1]["scores"],
                            "selected_model_navigation": nav(models.get(chosen)),
                            "fixed_original_navigation": nav(models["original"]),
                            "correct_snapshot_navigation": nav(models[regime]),
                            "known_physics_oracle_navigation": nav(KnownPhysicsOracle(*condition)),
                        })
                    # Integrity checked after stream, without modifying it.
                    all_events = stream.events()
                    assert len(all_events) == phase_episodes * 3
                # Check restorable selected knowledge without auto-learning.
                with StreamMonitor(state_db, bank) as restored:
                    assert restored.state["active"] == phases[-1]["final_selected"]
                result["rows"].append({"seed": seed, "phases": phases})
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seeds", nargs="+", type=int, default=[17,23,41])
    p.add_argument("--train-episodes", type=int, default=350)
    p.add_argument("--iterations", type=int, default=10)
    p.add_argument("--phase-episodes", type=int, default=25)
    p.add_argument("--navigation-episodes", type=int, default=15)
    p.add_argument("--out", type=Path)
    a = p.parse_args()
    output = json.dumps(measure(a.seeds,a.train_episodes,a.iterations,a.phase_episodes,a.navigation_episodes),
                        indent=2,sort_keys=True)+"\n"
    if a.out:
        a.out.write_text(output, encoding="utf-8")
    print(output,end="")


if __name__=="__main__":
    main()
