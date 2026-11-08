"""Experimental regime discovery from mixed, *unlabelled* sensor episodes.

Fits one or two stationary known-topology ring models without receiving simulator
regime labels or positions after reset. This is not online continual learning:
model fitting is an offline train-only proposal; acceptance is observation-only
validation and NEVER approves model promotion, deployment, or external actions.
"""
from __future__ import annotations

import hashlib
import json
import math

from developmental_ai.adaptive_dynamics import canonical
from developmental_ai.online_dynamics import forward_backward, validate_history
from developmental_ai.structured_landmarks import StructuredModel, fit_structured

SCHEMA = "mixed-experience/v1"


def _digest(data):
    return hashlib.sha256(canonical(data).encode("utf-8")).hexdigest()


def _validated(histories, lower=1, upper=500):
    if type(histories) not in (list, tuple) or not lower <= len(histories) <= upper:
        raise ValueError("invalid observation histories")
    for history in histories:
        validate_history(history)   # rejects privileged positions/regime labels
    if lower > 1 and {h["n"] for h in histories} != {9, 11}:
        raise ValueError("training requires observations of both known topologies")
    return list(histories)


def _agreement(history):
    observations = history["observations"]
    return sum(int(cmd == odo) for cmd, odo, _ in observations) / len(observations)


def _partition(histories, kind, min_group):
    """Observation-only deterministic initial guesses; no hidden regime labels."""
    length = len(histories)
    if kind == "odometry":
        ranked = sorted(range(length), key=lambda i: (_agreement(histories[i]), i))
    elif kind == "order":
        ranked = list(range(length))
    else:
        raise ValueError("unknown partition")
    boundary = length // 2
    groups = [set(ranked[:boundary]), set(ranked[boundary:])]
    if min(len(g) for g in groups) < min_group:
        raise ValueError("insufficient discovery evidence")
    return groups


def _enough_topology(histories, groups, min_group):
    return all(len(group) >= min_group and
               {histories[i]["n"] for i in group} == {9, 11}
               for group in groups)


def _fit_group(histories, group, iterations):
    return fit_structured([histories[i] for i in sorted(group)], iterations=iterations)[0]


def _labels(histories, models):
    """Maximum episode evidence, equal priors, deterministic tie breaking."""
    # DO NOT insert true condition labels, privileged oracle truth, or reward.
    logpairs = [(forward_backward(models[0], h), forward_backward(models[1], h))
                for h in histories]
    return [int(b > a) for a, b in logpairs]


def _candidate(histories, iterations, rounds, min_group, start):
    groups = _partition(histories, start, min_group)
    if not _enough_topology(histories, groups, min_group):
        return None
    for _ in range(rounds):
        models = tuple(_fit_group(histories, group, iterations) for group in groups)
        labels = _labels(histories, models)
        revised = [{i for i, label in enumerate(labels) if label == k} for k in (0, 1)]
        if not _enough_topology(histories, revised, min_group):
            break  # keep previous valid partition; do not coerce low-evidence assignment
        if revised == groups:
            break
        groups = revised
    models = tuple(_fit_group(histories, group, iterations) for group in groups)
    return models, [len(g) for g in groups]


def mixture_log_likelihood(models, history, *, weights=None):
    validate_history(history)
    if type(models) not in (tuple, list) or not 1 <= len(models) <= 2 or any(
            not isinstance(m, StructuredModel) for m in models):
        raise ValueError("invalid model collection")
    if weights is None:
        weights = [1 / len(models)] * len(models)
    if (type(weights) not in (tuple, list) or len(weights) != len(models) or
            any(type(w) not in (int, float) or not math.isfinite(w) or w <= 0 for w in weights) or
            not math.isclose(sum(weights), 1, abs_tol=1e-9)):
        raise ValueError("invalid mixture weights")
    parts = [math.log(weight) + forward_backward(model, history)
             for model, weight in zip(models, weights)]
    largest = max(parts)
    return largest + math.log(sum(math.exp(x - largest) for x in parts))


def validation_score(models, histories):
    observations = sum(len(h["observations"]) for h in histories)
    return sum(mixture_log_likelihood(models, h) for h in histories) / observations


class MixedProposal:
    """Frozen proposed models; a SHA checksum is NOT authenticated consent."""
    def __init__(self, models, baseline, validation, accepted, kind, seed, evidence):
        if (type(seed) is not int or type(accepted) is not bool or
                kind not in ("single", "odometry", "order") or
                type(validation) is not dict or
                set(validation) != {"single", "candidate", "delta"} or
                any(type(x) not in (float, int) or not math.isfinite(x) for x in validation.values()) or
                type(models) not in (tuple, list) or not 1 <= len(models) <= 2 or
                any(not isinstance(x, StructuredModel) for x in models) or
                not isinstance(baseline, StructuredModel) or
                (len(models) == 2) != accepted or
                (kind == "single") != (not accepted) or
                type(evidence) is not dict or set(evidence) != {"fit_digest", "validation_digest", "fit_count", "validation_count"} or
                any(type(evidence[k]) is not str or len(evidence[k]) != 64 or
                    any(c not in "0123456789abcdef" for c in evidence[k])
                    for k in ("fit_digest", "validation_digest")) or
                any(type(evidence[k]) is not int or evidence[k] < 2 for k in ("fit_count", "validation_count"))):
            raise ValueError("invalid candidate proposal")
        self.models = tuple(models)
        self.baseline = baseline
        self.validation = dict(validation)
        self.accepted = accepted
        self.kind = kind
        self.seed = seed
        self.evidence = dict(evidence)

    def select(self, histories, *, threshold=.8):
        """Diagnostic only: return index or None when uncertain (not authority)."""
        _validated(histories, 1, 100)
        if type(threshold) not in (float, int) or not math.isfinite(threshold) or not .5 <= threshold <= 1:
            raise ValueError("invalid diagnostic threshold")
        if len(self.models) == 1:
            return 0
        totals = [sum(forward_backward(model, h) for h in histories) for model in self.models]
        maximum = max(totals)
        probabilities = [math.exp(x - maximum) for x in totals]
        total = sum(probabilities)
        leader = max(range(len(totals)), key=lambda k: (probabilities[k], -k))
        return leader if probabilities[leader] / total >= threshold else None

    def state(self):
        return {"schema": SCHEMA, "seed": self.seed, "accepted": self.accepted,
                "kind": self.kind, "validation": self.validation,
                "evidence": self.evidence, "models": [model.state() for model in self.models],
                "baseline": self.baseline.state()}

    def record(self):
        state = self.state()
        return {"state": state, "sha256": _digest(state)}

    @classmethod
    def restore(cls, record, seed):
        if (type(record) is not dict or set(record) != {"state", "sha256"} or
                type(record["state"]) is not dict or
                record["sha256"] != _digest(record["state"])):
            raise ValueError("invalid checkpoint digest")
        s = record["state"]
        if (set(s) != {"schema", "seed", "accepted", "kind", "validation", "evidence", "models", "baseline"} or
                s["schema"] != SCHEMA or type(seed) is not int or s["seed"] != seed):
            raise ValueError("invalid checkpoint schema or seed")
        def restore_model(value):
            if type(value) is not dict or set(value) != {"schema", "offsets", "motion", "odo", "roles"} or value["schema"] != "structured-landmarks/v1":
                raise ValueError("invalid model structure")
            return StructuredModel(value["offsets"], value["motion"], value["odo"], value["roles"])
        try:
            baseline = restore_model(s["baseline"])
            models = tuple(restore_model(m) for m in s["models"])
            return cls(models, baseline, s["validation"], s["accepted"], s["kind"], seed, s["evidence"])
        except (TypeError, KeyError, AttributeError) as exc:
            raise ValueError("invalid checkpoint model") from exc


def fit_mixed(histories, validation, *, seed=17, iterations=3, rounds=2,
              min_group=10, min_validation_gain=.007):
    """Train-only offline proposal; validation histories are never used for fitting.

    Caller must supply disjoint fit/validation evidence (fit and validation
    histories must have different content digests). Validates but cannot prove
    absence of a repeated physical episode with different formatting.
    """
    histories = _validated(histories, 2, 500)
    validation = _validated(validation, 2, 250)
    if (type(seed) is not int or type(iterations) is not int or not 1 <= iterations <= 15 or
            type(rounds) is not int or not 1 <= rounds <= 6 or
            type(min_group) is not int or not 5 <= min_group <= 200 or
            len(histories) < min_group * 2 or
            type(min_validation_gain) not in (float, int) or not math.isfinite(min_validation_gain) or
            not 0 <= min_validation_gain <= .5):
        raise ValueError("invalid fit configuration")
    fit_fingerprints = {_digest(h) for h in histories}
    if len(fit_fingerprints) != len(histories):
        raise ValueError("duplicate fit evidence")
    val_fingerprints = {_digest(h) for h in validation}
    if len(val_fingerprints) != len(validation) or fit_fingerprints & val_fingerprints:
        raise ValueError("fit/validation evidence overlap")
    baseline = fit_structured(histories, iterations=iterations)[0]
    reference = validation_score((baseline,), validation)
    winner = None
    candidates = []
    for kind in ("odometry", "order"):
        option = _candidate(histories, iterations, rounds, min_group, kind)
        if option is None:
            continue
        models, sizes = option
        score = validation_score(models, validation)
        candidates.append((score, kind, models, sizes))
    if candidates:
        winner = max(candidates, key=lambda row: (row[0], row[1] == "odometry"))
    gain = 0. if winner is None else winner[0] - reference
    accepted = bool(winner and gain >= min_validation_gain)
    validation_metrics = {"single": round(reference, 6),
                          "candidate": round(winner[0] if winner else reference, 6),
                          "delta": round(gain, 6)}
    receipts = {"fit_digest": _digest(sorted(fit_fingerprints)),
                "validation_digest": _digest(sorted(val_fingerprints)),
                "fit_count": len(histories), "validation_count": len(validation)}
    return MixedProposal(winner[2] if accepted else (baseline,), baseline,
                         validation_metrics, accepted, winner[1] if accepted else "single", seed,
                         receipts)
