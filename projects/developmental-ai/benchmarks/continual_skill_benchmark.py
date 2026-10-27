"""Sequential symbolic skill adaptation: source -> target -> source retention.

A small *development* learning curve, not blind, out-of-ontology transfer,
independent causal discovery, or statistical evidence of lifelong cognition.
Uses only public simulator feedback and the existing OutcomeSkills learner.
The prior frozen zero-shot outcome_skills_benchmark remains unchanged.
"""
from __future__ import annotations

import argparse
import json
from developmental_ai.outcome_skills import OutcomeSkills
from benchmarks.outcome_skills_benchmark import (
    DEV, EXTRA, TRAIN, EPISODES, TRAIN_EPISODES, learn, run,
)

SCHEMA = "developmental-ai.continual-symbolic-skills/v1"
TARGET = "delivery"
RETAIN = "assembly"
TARGET_TRAIN_START = 120000
EVAL_START = 92000
EVAL_EPISODES = 40
STAGES = (0, 1, 2, 4, 8, 20)
MODES = ("transfer_adapt", "target_only", "frozen_source", "random", "oracle")


def _score(seed, agent, family, mode):
    policy = ("learned" if mode in ("transfer_adapt", "target_only", "frozen_source")
              else mode)
    outcomes = [
        run(seed, family, "test", EVAL_START+i, agent, policy=policy)
        for i in range(EVAL_EPISODES)
    ]
    return {
        "success": sum(int(x["success"]) for x in outcomes),
        "episodes": EVAL_EPISODES,
        "mean_attempts": round(sum(x["attempts"] for x in outcomes) / EVAL_EPISODES, 4),
        "mean_blocked": round(sum(x["blocked"] for x in outcomes) / EVAL_EPISODES, 4),
    }


def measure(seeds=DEV):
    if type(seeds) not in (tuple, list) or tuple(seeds) not in (DEV, EXTRA):
        raise ValueError("only predeclared, previously inspected development cohorts")
    output = {
        "schema": SCHEMA,
        "blind": False,
        "generator_independent": False,
        "shared_engineered_glyphs": True,
        "train_source_families": list(TRAIN),
        "target_family": TARGET,
        "retention_family": RETAIN,
        "source_train_episodes": TRAIN_EPISODES,
        "target_train_start": TARGET_TRAIN_START,
        "target_train_stages": list(STAGES),
        "test_start": EVAL_START,
        "test_episodes_per_family": EVAL_EPISODES,
        "rows": [],
    }
    for seed in seeds:
        source = learn(seed)
        # Restore the original memory to ensure no per-phase evaluation writes.
        transferred = OutcomeSkills.restore(source.record())
        source_checksum = source.record()["sha256"]
        scratch = OutcomeSkills()
        curves = []
        old = 0
        for count in STAGES:
            for index in range(old, count):
                episode_index = TARGET_TRAIN_START + index
                run(seed, TARGET, "train", episode_index, transferred, "learned", True)
                run(seed, TARGET, "train", episode_index, scratch, "learned", True)
            old = count
            transferred_record = transferred.record()
            restored = OutcomeSkills.restore(transferred_record)
            if restored.record() != transferred_record:
                raise AssertionError("learned skills failed checkpoint restart")
            if source.record()["sha256"] != source_checksum:
                raise AssertionError("immutable source control changed")
            target_scores = {
                "transfer_adapt": _score(seed, restored, TARGET, "transfer_adapt"),
                "target_only": _score(seed, scratch, TARGET, "target_only"),
                "frozen_source": _score(seed, source, TARGET, "frozen_source"),
                "random": _score(seed, None, TARGET, "random"),
                "oracle": _score(seed, None, TARGET, "oracle"),
            }
            retention_scores = {
                "transfer_adapt": _score(seed, restored, RETAIN, "transfer_adapt"),
                "frozen_source": _score(seed, source, RETAIN, "frozen_source"),
                "target_only": _score(seed, scratch, RETAIN, "target_only"),
            }
            curves.append({
                "target_train_episodes": count,
                "target": target_scores,
                "retention": retention_scores,
                "stored_experiences": len(restored.events),
                "stored_glyphs": len(restored.knowledge()),
                "sha256": transferred_record["sha256"],
            })
        output["rows"].append({"seed": seed, "curve": curves})
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cohort", choices=("dev", "additional"), default="dev")
    opt = parser.parse_args()
    print(json.dumps(measure(DEV if opt.cohort == "dev" else EXTRA),
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
