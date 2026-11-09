"""Conservative post-selection abstention on per-step simulation evidence.

No environment labels are accepted at inference. A label-aware *offline* tuning
procedure chooses a score-gap cutoff on distinct training-namespace histories;
its empirical error rate is not a calibrated probability or safety guarantee.
The gate does not mutate the detector, models, or agent permissions.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math

from developmental_ai.adaptive_dynamics import canonical
from developmental_ai.step_dynamics import catalogue

SCHEMA = "decision-abstention/v1"


def _sha(payload):
    return hashlib.sha256(canonical(payload).encode("utf-8")).hexdigest()


def signal(event, model_names):
    """Accept only detector observations, rejecting non-finite/unknown evidence."""
    if type(event) is not dict or event.get("kind") != "observation":
        raise ValueError("expected step observation event")
    scores = event.get("scores")
    if type(scores) is not dict or set(scores) != set(model_names) or len(scores) < 2:
        raise ValueError("unexpected model scores")
    if any(type(s) not in (float, int) or not math.isfinite(s) for s in scores.values()):
        raise ValueError("nonfinite model evidence")
    if event.get("active") not in (None, *model_names) or event.get("status") not in (
        "warming", "uncertain", "pending", "switch", "stable", "unknown"):
        raise ValueError("invalid detector selection")
    order = sorted(scores, key=lambda n: (-scores[n], n))
    lead, second = order[:2]
    return {"active": event["active"], "lead": lead,
            "gap": round(scores[lead] - scores[second], 9),
            "status": event["status"]}


def decide(event, model_names, *, gap):
    """Abstain unless saved selection and current evidence agree by a margin."""
    if type(gap) not in (float, int) or not math.isfinite(gap) or gap < 0:
        raise ValueError("invalid acceptance gap")
    s = signal(event, model_names)
    if (s["active"] is None or s["status"] in ("warming", "unknown", "uncertain")
            or s["lead"] != s["active"] or s["gap"] < gap):
        return None
    return s["active"]


@dataclass(frozen=True)
class GateProfile:
    schema: str
    seed: int
    bank_digest: str
    max_empirical_error: float
    gap: float
    training_samples: int
    accepted_samples: int
    wrong_samples: int
    evidence_digest: str
    digest: str

    def as_dict(self):
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


def train_gate(bank, labeled_events, *, max_empirical_error=0.10, min_accepted=24):
    """Tune a selective decision rule on strictly *offline labelled* events.

    If no threshold reaches the target empirical conditional error rate while
    retaining at least `min_accepted` decisions, produce a fail-closed profile
    with gap=1e6. This is development-only, not a statistical confidence bound.
    """
    if (type(max_empirical_error) not in (int, float) or not math.isfinite(max_empirical_error)
            or not 0 <= max_empirical_error < 1 or type(min_accepted) is not int
            or not 1 <= min_accepted <= 100000):
        raise ValueError("invalid selective-risk settings")
    models, fingerprint = catalogue(bank)
    if type(labeled_events) not in (list, tuple) or not 100 <= len(labeled_events) <= 100000:
        raise ValueError("insufficient or excessive calibration steps")
    evaluated = []
    for pair in labeled_events:
        if type(pair) not in (tuple, list) or len(pair) != 2 or pair[1] not in models:
            raise ValueError("invalid labelled calibration event")
        obs, actual = pair
        s = signal(obs, models)
        evaluated.append((obs, actual, s))
    # Only rows whose current leader matches a non-uncertain active selection
    # can ever pass. Sort once, then sweep equal-gap groups in descending
    # order; this is equivalent to testing every possible cutoff, but O(NlogN).
    eligible = sorted(((s["gap"], s["active"] != actual)
                       for _, actual, s in evaluated
                       if s["active"] is not None and s["lead"] == s["active"]
                       and s["status"] not in ("warming", "unknown", "uncertain")),
                      reverse=True)
    best = None
    accepted = wrong = 0
    i = 0
    while i < len(eligible):
        threshold = eligible[i][0]
        while i < len(eligible) and eligible[i][0] == threshold:
            accepted += 1
            wrong += int(eligible[i][1])
            i += 1
        if accepted >= min_accepted and wrong / accepted <= max_empirical_error:
            candidate = (accepted, -wrong, threshold, wrong)
            if best is None or candidate > best:
                best = candidate
    if best is not None:
        coverage, _, gap, wrong = best
    else:
        coverage, wrong, gap = 0, 0, 1000000.0
    evidence_digest = _sha([{ "e": ev, "actual": actual} for ev, actual, _ in evaluated])
    values = {"schema": SCHEMA, "seed": bank.seed, "bank_digest": fingerprint,
              "max_empirical_error": float(max_empirical_error), "gap": float(gap),
              "training_samples": len(evaluated), "accepted_samples": coverage,
              "wrong_samples": wrong, "evidence_digest": evidence_digest}
    return GateProfile(**values, digest=_sha(values))


def verify_gate(bank, profile):
    if type(profile) is not GateProfile:
        raise ValueError("invalid gate profile type")
    values = profile.as_dict()
    digest = values.pop("digest")
    _, fingerprint = catalogue(bank)
    if (set(values) != set(GateProfile.__dataclass_fields__) - {"digest"} or
        values["schema"] != SCHEMA or values["seed"] != bank.seed or
        values["bank_digest"] != fingerprint or _sha(values) != digest or
        type(profile.training_samples) is not int or profile.training_samples < 100 or
        type(profile.accepted_samples) is not int or not 0 <= profile.accepted_samples <= profile.training_samples or
        type(profile.wrong_samples) is not int or not 0 <= profile.wrong_samples <= profile.accepted_samples or
        type(profile.gap) not in (int, float) or not math.isfinite(profile.gap) or profile.gap < 0 or
        type(profile.max_empirical_error) not in (int, float) or not 0 <= profile.max_empirical_error < 1 or
        type(profile.evidence_digest) is not str or len(profile.evidence_digest) != 64):
        raise ValueError("incompatible or corrupt abstention profile")
    if profile.accepted_samples and profile.wrong_samples / profile.accepted_samples > profile.max_empirical_error:
        raise ValueError("corrupt training error record")
    return profile.gap


def load_gate(data):
    obj = json.loads(data)
    if type(obj) is not dict or set(obj) != set(GateProfile.__dataclass_fields__):
        raise ValueError("invalid profile fields")
    return GateProfile(**obj)
