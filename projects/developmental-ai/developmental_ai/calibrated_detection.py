"""Leakage-aware development calibration for stepwise model discrimination.

Calibration uses known regime identities only in a separate, explicitly
labelled offline calibration dataset.  The online StepDetector still receives
only ordinary (action, odometry, landmark) observations, never regime labels.
A calibration margin is a heuristic and NOT a posterior confidence value.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass

from developmental_ai.adaptive_dynamics import canonical
from developmental_ai.online_dynamics import score, validate_history
from developmental_ai.step_dynamics import catalogue

SCHEMA = "calibrated-step/v1"
MAX_CALIBRATION_HISTORIES = 512


@dataclass(frozen=True)
class Calibration:
    """Non-secret evaluation artifact. Does not authorize model promotion."""
    schema: str
    seed: int
    catalogue: str
    margin: float
    episodes_per_regime: int
    signed_advantages: dict[str, float]
    input_hash: str
    artifact_digest: str

    def as_dict(self):
        return {
            "schema": self.schema, "seed": self.seed,
            "catalogue": self.catalogue, "margin": self.margin,
            "episodes_per_regime": self.episodes_per_regime,
            "signed_advantages": dict(self.signed_advantages),
            "input_hash": self.input_hash,
            "artifact_digest": self.artifact_digest,
        }


def calibrate(bank, histories_by_model, *, fraction=0.5, max_margin=0.12):
    """Derive a shared threshold *without* observing evaluation episodes.

    The caller must supply independent, labelled calibration histories. This
    deliberately does not claim that a digest proves training/test separation:
    the benchmark owns and audits namespace/index allocation.

    Refuse to calibrate if any known regime has lower aggregate likelihood
    under its own model than under a competing model. This prevents deriving
    an optimistic decision threshold from a non-identifiable model bank.
    """
    if (type(fraction) not in (float, int) or not math.isfinite(fraction)
            or not 0 < fraction <= 1 or type(max_margin) not in (int, float)
            or not math.isfinite(max_margin) or not 0 < max_margin <= .12):
        raise ValueError("invalid calibration settings")
    models, fingerprint = catalogue(bank)
    if (type(histories_by_model) is not dict or set(histories_by_model) != set(models)
            or len(models) < 2):
        raise ValueError("provide separate calibration histories for all models")
    unique = set()
    advantages = {}
    counts = set()
    for name in sorted(models):
        histories = histories_by_model[name]
        if (type(histories) not in (list, tuple) or not 4 <= len(histories) <= MAX_CALIBRATION_HISTORIES):
            raise ValueError("invalid calibration history count")
        counts.add(len(histories))
        for h in histories:
            validate_history(h)
            key = hashlib.sha256(canonical(h).encode()).hexdigest()
            if key in unique:
                raise ValueError("reused calibration history")
            unique.add(key)
        own = score(models[name], histories)
        competing = max(score(m, histories) for other, m in models.items() if other != name)
        gap = own - competing
        if not math.isfinite(gap) or gap <= 0:
            raise ValueError("model bank is not identifiable on calibration histories")
        advantages[name] = round(gap, 9)
    if len(counts) != 1:
        raise ValueError("regimes require equal calibration budgets")
    margin = round(min(float(max_margin), fraction * min(advantages.values())), 9)
    if margin <= 0:
        raise ValueError("zero calibrated discrimination margin")
    body = canonical({"models": fingerprint, "seed": bank.seed,
                      "calibration_histories": {name: histories_by_model[name] for name in sorted(models)}})
    fields = {"schema": SCHEMA, "seed": bank.seed, "catalogue": fingerprint,
              "margin": margin, "episodes_per_regime": next(iter(counts)),
              "signed_advantages": advantages,
              "input_hash": hashlib.sha256(body.encode()).hexdigest()}
    return Calibration(**fields, artifact_digest=hashlib.sha256(canonical(fields).encode()).hexdigest())


def verify_calibration(bank, artifact):
    """Bound a stored calibration to an *unchanged* model bank; fail closed."""
    if type(artifact) is not Calibration or artifact.schema != SCHEMA:
        raise ValueError("unsupported calibration schema")
    _, fingerprint = catalogue(bank)
    if artifact.seed != bank.seed or artifact.catalogue != fingerprint:
        raise ValueError("calibration bound to another model bank")
    validate_artifact(artifact)
    if (not 0 < artifact.margin <= 0.12 or artifact.episodes_per_regime < 4
            or set(artifact.signed_advantages) != set(catalogue(bank)[0])
            or any(not math.isfinite(v) or v <= 0 for v in artifact.signed_advantages.values())
            or type(artifact.input_hash) is not str or len(artifact.input_hash) != 64):
        raise ValueError("malformed calibration")
    return artifact.margin


def validate_artifact(artifact):
    """Check accidental/tampered changes without claiming signed provenance."""
    if type(artifact) is not Calibration:
        raise ValueError("invalid calibration object")
    fields = artifact.as_dict()
    claimed = fields.pop("artifact_digest")
    if (type(claimed) is not str or len(claimed) != 64
            or hashlib.sha256(canonical(fields).encode()).hexdigest() != claimed):
        raise ValueError("calibration artifact checksum mismatch")


def load_calibration(blob):
    """Parse an untrusted artifact; still requires verify_calibration(bank, ...)."""
    data = json.loads(blob)
    fields = set(Calibration.__dataclass_fields__)
    if type(data) is not dict or set(data) != fields:
        raise ValueError("invalid calibration fields")
    if (type(data["seed"]) is not int or type(data["episodes_per_regime"]) is not int
            or type(data["margin"]) not in (float, int)
            or type(data["signed_advantages"]) is not dict):
        raise ValueError("invalid calibration types")
    artifact = Calibration(**data)
    validate_artifact(artifact)
    return artifact
