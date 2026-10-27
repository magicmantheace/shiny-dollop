"""Experimental multi-start latent-state EM selected on disjoint ordinary observations.

All fitting, initialization, and selection use only action/odometry/landmark
histories and the public initial position beacon. There are no privileged
transitions, layout names, simulator rewards, or test split inputs.

This is an optional experiment: not a new default model, deployment selector,
or a guarantee of generalization or safety.
"""
from __future__ import annotations

import hashlib
import json
import math
import random

from developmental_ai.adaptive_dynamics import DynamicsModel, canonical, reading_index
from developmental_ai.online_dynamics import (
    MAX_EPISODES, fit, initial_model, score, validate_history,
)

SCHEMA = "robust-world-model/v1"
MAX_STARTS = 5


def _digest(history):
    validate_history(history)
    return hashlib.sha256(canonical(history).encode("utf-8")).hexdigest()


def ensure_disjoint(training, validation):
    if type(training) not in (list, tuple) or type(validation) not in (list, tuple):
        raise ValueError("training and validation must be sequences")
    if not 1 <= len(training) <= MAX_EPISODES or not 1 <= len(validation) <= MAX_EPISODES:
        raise ValueError("invalid sample counts")
    fit_ids = [_digest(h) for h in training]
    valid_ids = [_digest(h) for h in validation]
    if len(set(fit_ids)) != len(fit_ids) or len(set(valid_ids)) != len(valid_ids) or set(fit_ids).intersection(valid_ids):
        raise ValueError("duplicated or overlapping evidence")
    return {"fit_sha256": hashlib.sha256(canonical(fit_ids).encode()).hexdigest(),
            "validation_sha256": hashlib.sha256(canonical(valid_ids).encode()).hexdigest()}


def seeded_start(histories, seed, candidate):
    """Generate diverse initial guesses without simulator truth or task labels.

    Candidate 0 is the frozen baseline. Candidate 1 uses noisy odometry as a
    weak *initialization only* to place possible landmarks. Candidates 2+
    hypothesize random locations for marker types, then learn by soft EM.
    """
    if type(seed) is not int or type(candidate) is not int or not 0 <= candidate < MAX_STARTS:
        raise ValueError("invalid initialization")
    model = initial_model()
    if candidate == 0:
        return model
    rng = random.Random(f"{SCHEMA}/{seed}/{candidate}")
    counts = json.loads(canonical(model.counts))
    if candidate == 1:
        for history in histories:
            n, pos, obs = validate_history(history)
            for _, odo, marker in obs:
                pos = (pos + odo) % n  # measured odometry, *not* hidden state
                if marker is not None:
                    counts["landmark"][str(n)][pos][reading_index(marker)] += 2.0
    else:
        for n in (9, 11):
            p0, p1 = rng.sample(range(n), 2)
            counts["landmark"][str(n)][p0] = [1.5, 9.0, 0.2]
            counts["landmark"][str(n)][p1] = [1.5, 0.2, 9.0]
        for cmd in range(2):
            counts["motion"][cmd] = [rng.uniform(3, 9), rng.uniform(1, 4), rng.uniform(1, 5)]
    return DynamicsModel(counts)


def fit_robust(training, validation, *, seed, starts=3, iterations=8):
    """Pick a fit by disjoint validation likelihood; ties prefer candidate 0.

    Never use the `test` namespace for validation. The caller is responsible
    for supplying train-namespace evidence; disjointness is enforced by data
    hashes, independent namespace discipline is enforced in benchmark/tests.
    """
    if type(seed) is not int or type(starts) is not int or not 1 <= starts <= MAX_STARTS:
        raise ValueError("invalid multi-start settings")
    if type(iterations) is not int or not 1 <= iterations <= 50:
        raise ValueError("invalid iteration count")
    lineage = ensure_disjoint(training, validation)
    candidates = []
    for i in range(starts):
        start = seeded_start(training, seed, i)
        model, curve = fit(training, iterations=iterations, start=start)
        v = score(model, validation)
        if not math.isfinite(v):
            raise ValueError("invalid validation likelihood")
        candidates.append((model, v, curve[-1]))
    choice = max(range(starts), key=lambda i: (candidates[i][1], -i))
    receipt = {
        "schema": SCHEMA, "seed": seed, "starts": starts, "iterations": iterations,
        "training_histories": len(training), "validation_histories": len(validation),
        "chosen_start": choice, "validation_scores": [round(x[1], 8) for x in candidates],
        "baseline_validation_score": round(candidates[0][1], 8),
        "selected_validation_score": round(candidates[choice][1], 8),
        "lineage": lineage, "selected_model_sha256": hashlib.sha256(canonical(candidates[choice][0].counts).encode()).hexdigest(),
        "scope": "simulation-only",
    }
    return candidates[choice][0], receipt
