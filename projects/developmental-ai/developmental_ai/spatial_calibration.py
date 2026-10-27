"""Experiment: supervised *calibration* of a learned spatial posterior.

A simulator-only evaluation instrument reveals the real location, for fitting
and scoring temperature scaling. Neither the navigator nor the deployed
postprocessor sees the true location. This is not self-supervised, does not
improve the underlying dynamics model, and does not grant action permissions.
"""
from __future__ import annotations

import hashlib
import json
import math
import random

from developmental_ai.adaptive_dynamics import AdaptiveNavigator, CalibrationWorld, DynamicsModel, canonical
from developmental_ai.uncertain_navigation import seed_for

SCHEMA = "spatial-calibration/v1"
TEMPERATURES = (0.5, 0.67, 0.8, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0)
MAX_RECORDS = 20000


def digest(body):
    return hashlib.sha256(canonical(body).encode("utf-8")).hexdigest()


def _belief(belief):
    if (type(belief) not in (tuple, list) or len(belief) not in (9, 11) or
            any(type(p) not in (int, float) or not math.isfinite(p) or p < 0 or p > 1 for p in belief) or
            not math.isclose(sum(belief), 1.0, abs_tol=1e-7)):
        raise ValueError("invalid normalized location posterior")
    return list(belief)


def temper(belief, temperature):
    """Display-only normalized power posterior; no privileged inputs."""
    vals = _belief(belief)
    if type(temperature) not in (int, float) or not math.isfinite(temperature) or temperature <= 0:
        raise ValueError("invalid temperature")
    scaled = [math.log(max(p, 1e-300)) / temperature for p in vals]
    maximum = max(scaled)
    weights = [math.exp(x - maximum) for x in scaled]
    total = sum(weights)
    return [x / total for x in weights]


def _record(record):
    if type(record) is not dict or set(record) != {"split", "episode", "step", "posterior", "true_position"}:
        raise ValueError("invalid instrumented calibration record")
    if record["split"] != "train" or type(record["episode"]) is not int or record["episode"] < 5000:
        raise ValueError("calibration requires isolated train-namespace episodes 5000+")
    if type(record["step"]) is not int or not 1 <= record["step"] <= 40:
        raise ValueError("invalid calibration step")
    belief = _belief(record["posterior"])
    truth = record["true_position"]
    if type(truth) is not int or not 0 <= truth < len(belief):
        raise ValueError("invalid held-out true position")
    return belief, truth


def mean_nll(rows, temperature):
    if not rows:
        raise ValueError("no calibration records")
    return sum(-math.log(max(temper(p, temperature)[truth], 1e-300)) for p, truth in rows) / len(rows)


def _fingerprint(model):
    if not isinstance(model, DynamicsModel):
        raise ValueError("temperature profile requires a learned dynamics model")
    model.validate()
    return digest(model.counts)


def fit_profile(model, records):
    """Supervised offline calibration only; refuses test evidence and duplicates."""
    model_digest = _fingerprint(model)
    if type(records) not in (list, tuple) or not 1 <= len(records) <= MAX_RECORDS:
        raise ValueError("invalid calibration sample count")
    seen = set()
    checked = []
    for rec in records:
        row = _record(rec)
        identity = (rec["episode"], rec["step"])
        if identity in seen:
            raise ValueError("duplicate instrumented evidence")
        seen.add(identity)
        checked.append(row)
    losses = [(mean_nll(checked, t), t) for t in TEMPERATURES]
    # Tie-breaking prefers the original, unaltered posterior.
    best = min(losses, key=lambda x: (round(x[0], 12), abs(math.log(x[1]))))[1]
    body = {"schema": SCHEMA, "model_digest": model_digest, "temperature": best,
            "count": len(checked), "evidence_digest": digest(records),
            "split": "instrumented-train-5000+", "scope": "read-only-uncertainty-display"}
    return {"body": body, "digest": digest(body)}


def validate_profile(model, record):
    if type(record) is not dict or set(record) != {"body", "digest"} or type(record["body"]) is not dict:
        raise ValueError("invalid calibration profile")
    b = record["body"]
    if (set(b) != {"schema", "model_digest", "temperature", "count", "evidence_digest", "split", "scope"} or
            record["digest"] != digest(b) or b["schema"] != SCHEMA or b["model_digest"] != _fingerprint(model) or
            type(b["temperature"]) not in (float, int) or b["temperature"] not in TEMPERATURES or
            type(b["count"]) is not int or not 1 <= b["count"] <= MAX_RECORDS or
            type(b["evidence_digest"]) is not str or len(b["evidence_digest"]) != 64 or
            b["split"] != "instrumented-train-5000+" or b["scope"] != "read-only-uncertainty-display"):
        raise ValueError("altered or mismatched calibration profile")
    return b["temperature"]


def calibrated_posterior(model, profile, belief):
    """Never changes navigator state, model identity, policy or permissions."""
    return temper(belief, validate_profile(model, profile))


def instrumented_stream(model, seed, *, split, first, episodes, noise, layout, steps=12):
    """Research harness only: world.pos used to make ground-truth labels.

    No true position, regime or reward is passed to the actual navigator.
    """
    _fingerprint(model)
    if (split not in ("train", "test") or type(seed) is not int or
            type(first) is not int or first < (5000 if split == "train" else 0) or
            type(episodes) is not int or not 1 <= episodes <= 2000 or
            type(steps) is not int or not 1 <= steps <= 40):
        raise ValueError("invalid instrumented measurement window")
    records = []
    for index in range(first, first+episodes):
        world = CalibrationWorld(seed, split, index, noise, layout)
        nav = AdaptiveNavigator(world.initial, world.goal, world.n, model)
        rng = random.Random(seed_for(seed, split, index, "policy"))
        for step in range(1, steps+1):
            action = rng.randrange(2)
            observed, _, _, _ = world.step(action)
            nav.advance(action, observed)
            records.append({"split": split, "episode": index, "step": step,
                            "posterior": nav.probs[:], "true_position": world.pos})
    return records


def diagnostics(records, temperature=1.0):
    """Evaluate spatial distribution accuracy on *instrumented* episodes."""
    if type(records) not in (list, tuple) or not records:
        raise ValueError("empty evaluation")
    accum = {"nll":0.0, "brier":0.0, "top1_accuracy":0.0,
             "credible80_coverage":0.0,"credible80_set_size":0.0, "true_position_mass":0.0}
    for rec in records:
        # Eval records may use test split; do not reuse the fit-only validator.
        if type(rec) is not dict or set(rec) != {"split", "episode", "step", "posterior", "true_position"} or rec["split"] not in ("train", "test"):
            raise ValueError("invalid evaluation record")
        belief = temper(rec["posterior"], temperature)
        truth = rec["true_position"]
        if type(truth) is not int or not 0 <= truth < len(belief):
            raise ValueError("invalid benchmark truth")
        accum["nll"] -= math.log(max(belief[truth], 1e-300))
        accum["brier"] += sum((p - (i == truth))**2 for i,p in enumerate(belief))
        accum["top1_accuracy"] += int(max(range(len(belief)), key=lambda i:belief[i]) == truth)
        accum["true_position_mass"] += belief[truth]
        order = sorted(range(len(belief)),key=lambda i:(-belief[i],i))
        total = 0.
        size = 0
        for i in order:
            total += belief[i]
            size += 1
            if total >= .8-1e-12:
                break
        accum["credible80_coverage"] += int(truth in order[:size])
        accum["credible80_set_size"] += size
    return {k:round(v/len(records), 5) for k,v in accum.items()}
