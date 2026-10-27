"""Precommitted D3 probabilistic correspondence vs frozen max-path baselines.

Only simulator benchmark knows the real cue or hidden cipher, and only for
scoring. Train-model fitting is unchanged from the older unaligned benchmark.
"""
from __future__ import annotations

import argparse
import json

from developmental_ai.environment_api import EnvironmentSession, digest
from developmental_ai.learned_spatial_memory import train_grid_updates
from developmental_ai.probabilistic_alignment import TemporalCorrespondence
from developmental_ai.unaligned_stream import alignment_score
from benchmarks.unaligned_stream_benchmark import fit, stream, choose, DEV, ADDITIONAL
from benchmarks.raw_token_transfer_benchmark import cipher
from benchmarks.dynamic_reliability_benchmark import navigate

SCHEMA = "developmental-ai.temporal-correspondence-benchmark/v1"
START = 99700
EPISODES = 40


def measure(seeds=DEV):
    if type(seeds) not in (tuple, list) or tuple(seeds) not in (DEV, ADDITIONAL):
        raise ValueError("evaluation cohort must match frozen protocol")
    output = {"schema": SCHEMA, "protocol": "benchmarks/temporal_correspondence_protocol.json",
              "independent_blind": False, "train": "train/89400..89639",
              "test": "test/99700..99739", "observed_training_labels": False,
              "frozen_parameters": {"latent_matches": 8, "match": .75, "mismatch": .25 / 3, "noise": .25},
              "rows": []}
    for seed in seeds:
        updater = train_grid_updates(seed, 24)
        learned, perm, identity = fit(seed, updater)  # SAME original training evidence
        token_model = TemporalCorrespondence(perm, evidence_digest=digest({
            "seed": seed, "fit": learned.record()["digest"], "permutation": perm,
            "budget": 240}), episodes=240)
        token_model = TemporalCorrespondence.restore(token_model.record())
        source_name = min(identity, key=lambda name: (-(identity[name][0] + 1) / (identity[name][1] + 2), name))
        old_weights = [1. if perm[i] == j else -1. for i in range(4) for j in range(4)]
        choices = ("learned_old", "fixed_identity", "unsup_max_path", "unsup_marginal",
                   "oracle_cipher_marginal", "correct_cue")
        task = {key: 0 for key in choices}
        hit = {key: 0 for key in choices}
        margin = []
        for j in range(EPISODES):
            index = START + j
            beacon = list(EnvironmentSession("occluded", seed, "test", index).frame()["observation"]["beacon"])
            observed, candidates, truth = stream(seed, "test", index, beacon)
            diagnosis = token_model.ranked(observed, candidates)
            scores = {
                "learned_old": learned.source(observed, candidates),
                "fixed_identity": source_name,
                "unsup_max_path": choose(observed, candidates, old_weights),
                "unsup_marginal": diagnosis["selected"],
                "oracle_cipher_marginal": TemporalCorrespondence(cipher(seed), evidence_digest=token_model.evidence_digest, episodes=240).select(observed, candidates),
                "correct_cue": truth,
            }
            margin.append(diagnosis["margin"])
            cache = {}
            for method, picked in scores.items():
                hit[method] += (picked == truth)
                if picked not in cache:
                    target = next(c[1] for c in candidates if c[0] == picked)
                    cache[picked] = navigate(seed, "test", index, updater, target)
                task[method] += cache[picked]
        output["rows"].append({"seed": seed, "navigation_successes": task,
                               "correct_source": hit, "learned_token_mapping_exact": perm == cipher(seed),
                               "model_training_sha256": token_model.record()["sha256"],
                               "mean_uncalibrated_margin": round(sum(margin) / len(margin), 6)})
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", choices=("development", "additional"), default="development")
    parser.add_argument("--out")
    args = parser.parse_args()
    data = json.dumps(measure(DEV if args.cohort == "development" else ADDITIONAL), indent=2, sort_keys=True) + "\n"
    if args.out:
        from pathlib import Path
        Path(args.out).write_text(data)
    print(data, end="")

if __name__ == "__main__": main()
