"""Frozen closed-loop navigation after observation-only regime discovery.

Fit/validation/calibration are disjoint train namespaces. At evaluation the
simulator may change its law at step 4 (and return at step 14); no change flag,
real position, regime label, or physics parameters reach the controller. An
explicit benchmark-only oracle sees the scheduled physics law, not true position.
All test seeds are previously inspected and therefore not a blind audit.
"""
from __future__ import annotations

import argparse
import json

from developmental_ai.adaptive_dynamics import AdaptiveNavigator, CalibrationWorld, KnownPhysicsOracle
from developmental_ai.closed_loop_adaptation import NavigationSession, models_from_proposal, SCHEMA
from developmental_ai.mixed_experience import fit_mixed
from developmental_ai.switching_belief import calibrate_hazard, verified_hazard
from benchmarks.switching_belief_benchmark import REGIMES, HAZARDS, mixed_histories, stream

SCHEDULES = ("switch", "original", "changed")
METHODS = ("single", "static", "switching", "physics_oracle")


def physics_at(step, schedule):
    """Benchmark-only true simulator parameters, never sent to the learner."""
    if schedule not in SCHEDULES or type(step) is not int or step < 0:
        raise ValueError("invalid benchmark schedule")
    if schedule == "original":
        return REGIMES[0]
    if schedule == "changed":
        return REGIMES[1]
    return REGIMES[0] if step < 4 or step >= 14 else REGIMES[1]


def run_episode(proposal, receipt, seed, index, schedule, method):
    if method not in METHODS or schedule not in SCHEDULES or type(index) is not int or index < 0:
        raise ValueError("invalid episode")
    world = CalibrationWorld(seed, "test", index, *physics_at(0, schedule))
    if method in ("static", "switching"):
        session = NavigationSession(proposal, world.initial, world.goal, world.n, receipt,
                                    mode="static" if method == "static" else "switching")
        nav = None
    else:
        nav = AdaptiveNavigator(world.initial, world.goal, world.n,
                                 proposal.baseline if method == "single" else KnownPhysicsOracle(*physics_at(0,schedule)))
        session = None
    last = ""
    abstained = 0
    votes = 0
    changed_steps = 0
    while not world.done:
        # The loop reads scheduled physics to configure the SIMULATOR only.
        # The oracle below is the only agent permitted the benchmark's truth.
        condition = physics_at(world.steps, schedule)
        world.noise, world.layout = condition
        if method == "physics_oracle":
            nav.model = KnownPhysicsOracle(*condition)
        action = session.select_action() if session else nav.heuristic()
        observation, _, done, last = world.step(action)
        if session:
            result = session.advance(action, observation, done=done)
            abstained += int(result["model_selected"] is None)
            votes += 1
        else:
            nav.advance(action, observation)
        changed_steps += int(condition == REGIMES[1])
    return {"success": int(last == "success"), "steps": world.steps,
            "changed_steps": changed_steps, "abstention_rate": abstained / votes if votes else None}


def run(seeds=(17, 23, 41), *, train=48, validation=16, calibration=12,
        iterations=2, rounds=1, episodes=24):
    if (type(seeds) not in (list, tuple) or not seeds or len(set(seeds)) != len(seeds) or
            any(type(s) is not int for s in seeds) or
            any(type(i) is not int for i in (train, validation, calibration, iterations, rounds, episodes)) or
            train < 20 or train > 300 or train % 2 or validation < 10 or validation > 200 or validation % 2 or
            not 2 <= calibration <= 100 or not 1 <= iterations <= 10 or not 1 <= rounds <= 4 or not 1 <= episodes <= 300):
        raise ValueError("invalid benchmark parameters")
    output = {"schema": SCHEMA, "kind": "inspected-development-not-blind",
              "seeds": list(seeds), "train": train, "validation": validation,
              "calibration": calibration, "iterations": iterations, "rounds": rounds,
              "episodes_per_schedule_method_seed": episodes,
              "partitions": {"fit": "train/0+", "discovery_validation": "train/10000+",
                             "hazard_calibration": "train/40000+", "navigation": "test/99000+"},
              "notes": "No true regime/position/reward supplied to the learner. Known ring and two-mark geometry. A frozen pre-trained model bank; new regimes are not learned during navigation. Simulated regime shift at steps 4 and 14; many short episodes may end before both shifts. The physics oracle knows the true scheduled law. Previously inspected seeds, no blind generalization, no deployment.",
              "rows": []}
    for seed in seeds:
        proposal = fit_mixed(mixed_histories(seed, train, 0), mixed_histories(seed, validation, 10000),
                             seed=seed, iterations=iterations, rounds=rounds)
        bank = models_from_proposal(proposal)
        calibration_records = []
        for i in range(calibration):
            beacon, events = stream(seed, "train", 40000+i, change=True)
            calibration_records.append({"initial": beacon[0], "goal": beacon[1], "n": beacon[2],
                                        "observations": [[a, ob] for a, ob, *_ in events]})
        receipt = calibrate_hazard(bank, calibration_records, candidates=HAZARDS)
        hazard = verified_hazard(receipt, bank)
        result = {"seed": seed, "proposal_two_models": proposal.accepted,
                  "selected_hazard": hazard, "receipt_sha256": receipt["sha256"],
                  "validation": proposal.validation, "schedules": {}}
        for schedule in SCHEDULES:
            methods = {}
            for method in METHODS:
                rows = [run_episode(proposal,receipt,seed,99000+i,schedule,method)
                        for i in range(episodes)]
                methods[method] = {
                    "success": round(sum(r["success"] for r in rows)/episodes, 6),
                    "success_count": sum(r["success"] for r in rows),
                    "mean_steps": round(sum(r["steps"] for r in rows)/episodes, 4),
                    "episodes_exposed_to_changed_world": sum(r["changed_steps"] > 0 for r in rows),
                }
                if method in ("static", "switching"):
                    methods[method]["abstention_rate"] = round(sum(r["abstention_rate"] for r in rows)/episodes, 6)
            result["schedules"][schedule] = methods
        output["rows"].append(result)
    return output


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seeds", nargs="+", type=int, default=[17, 23, 41])
    p.add_argument("--train", type=int, default=48); p.add_argument("--validation", type=int, default=16)
    p.add_argument("--calibration", type=int, default=12); p.add_argument("--iterations", type=int, default=2)
    p.add_argument("--rounds", type=int, default=1); p.add_argument("--episodes", type=int, default=24)
    p.add_argument("--out")
    args = p.parse_args()
    result = run(args.seeds, train=args.train, validation=args.validation,
                 calibration=args.calibration, iterations=args.iterations,
                 rounds=args.rounds, episodes=args.episodes)
    content = json.dumps(result, sort_keys=True, indent=2)+"\n"
    if args.out:
        from pathlib import Path
        Path(args.out).write_text(content, encoding="utf-8")
    print(content,end="")

if __name__ == "__main__":
    main()
