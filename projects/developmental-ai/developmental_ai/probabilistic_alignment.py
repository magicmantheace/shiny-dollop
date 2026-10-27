"""Optional sum-product alignment over unknown monotone event correspondence.

A known eight-event latent length and a fixed sensor/forecast emission family
are modeling priors.  The seed-specific token permutation comes from public,
unsupervised training streams, never simulator labels. No permissions or actions.
"""
from __future__ import annotations

import itertools
import math
from developmental_ai.environment_api import canonical, digest
from developmental_ai.raw_token_transfer import OBS, FORECAST
from developmental_ai.unaligned_stream import validate

SCHEMA = "developmental-ai.temporal-correspondence/v1"
MATCHES = 8
SAME, DIFFERENT, NULL = .75, .25 / 3, .25


def _permutation(mapping):
    if (type(mapping) not in (tuple, list) or len(mapping) != 4 or
            any(type(x) is not int for x in mapping) or set(mapping) != {0, 1, 2, 3}):
        raise ValueError("invalid learned token permutation")
    return tuple(mapping)


def marginal_score(observed, forecast, permutation):
    """Log mean predictive likelihood ratio over ALL eight-pair alignments.

    Each correspondence is a strictly increasing pair of observed and forecast
    positions. Unmatched readings are independent uniform insertions. Returns
    log E_alignment[ P(paired symbols | same event) / P(independent symbols) ].
    The partition function is computed via sum-product prefix DP, not max path.
    """
    perm = _permutation(permutation)
    if (type(observed) is not list or type(forecast) is not list or
            not 8 <= len(observed) <= 12 or not 8 <= len(forecast) <= 12 or
            any(type(t) is not str or t not in OBS for t in observed) or
            any(type(t) is not str or t not in FORECAST for t in forecast)):
        raise ValueError("malformed or unbounded public sequences")
    n, m = len(observed), len(forecast)
    weight = [[SAME / NULL if perm[OBS.index(x)] == FORECAST.index(y) else DIFFERENT / NULL
               for y in forecast] for x in observed]
    prev = None
    for k in range(1, MATCHES + 1):
        dp = [[0.0] * m for _ in range(n)]
        for i in range(k - 1, n):
            for j in range(k - 1, m):
                dp[i][j] = weight[i][j] if k == 1 else weight[i][j] * prev[i][j]
        prefix = [[0.0] * (m + 1) for _ in range(n + 1)]
        for i in range(n):
            for j in range(m):
                prefix[i + 1][j + 1] = (prefix[i][j + 1] + prefix[i + 1][j] -
                                         prefix[i][j] + dp[i][j])
        # prefix[i][j] sums earlier row < i and col < j.
        prev = prefix
    total = prefix[n][m]
    if not math.isfinite(total) or total <= 0:
        raise ValueError("alignment partition not finite")
    return math.log(total / (math.comb(n, MATCHES) * math.comb(m, MATCHES)))


def exhaustive_score(observed, forecast, permutation):
    """Small-input reference for tests; not used in evaluation."""
    perm = _permutation(permutation)
    n, m = len(observed), len(forecast)
    if n > 9 or m > 9: raise ValueError("exhaustive verification too large")
    total = 0.0
    count = 0
    for ix in itertools.combinations(range(n), MATCHES):
        for iy in itertools.combinations(range(m), MATCHES):
            likelihood = 1.0
            for i,j in zip(ix,iy):
                likelihood *= SAME/NULL if perm[OBS.index(observed[i])] == FORECAST.index(forecast[j]) else DIFFERENT/NULL
            total += likelihood
            count += 1
    return math.log(total/count)


class TemporalCorrespondence:
    """Frozen, unsupervised permutation with read-only posterior diagnostics."""

    def __init__(self, permutation, *, evidence_digest, episodes):
        self.mapping = _permutation(permutation)
        if (type(evidence_digest) is not str or len(evidence_digest) != 64 or
                any(c not in '0123456789abcdef' for c in evidence_digest) or
                type(episodes) is not int or episodes != 240):
            raise ValueError("invalid model training evidence")
        self.evidence_digest, self.episodes = evidence_digest, episodes

    def ranked(self, observed, candidates):
        seqs = validate(observed, candidates)
        scores = {source: marginal_score(observed, seq, self.mapping) for source, seq in seqs.items()}
        ordered = sorted(scores, key=lambda source: (-scores[source], source))
        # Softmax is a normalized ranking diagnostic only; NOT calibrated correctness.
        max_score = max(scores.values())
        masses = {s: math.exp(scores[s] - max_score) for s in scores}
        denom = sum(masses.values())
        return {"selected": ordered[0], "ranking": ordered,
                "log_scores": scores, "pseudo_posterior": {s: masses[s] / denom for s in ordered},
                "margin": scores[ordered[0]] - scores[ordered[1]]}

    def select(self, observed, candidates):
        return self.ranked(observed, candidates)["selected"]

    def record(self):
        state = {"schema": SCHEMA, "mapping": list(self.mapping),
                 "training_digest": self.evidence_digest, "episodes": self.episodes}
        return {"state": state, "sha256": digest(state)}

    @classmethod
    def restore(cls, record):
        if (type(record) is not dict or set(record) != {"state", "sha256"} or
                type(record["state"]) is not dict or type(record["sha256"]) is not str or
                record["sha256"] != digest(record["state"])):
            raise ValueError("modified alignment receipt")
        state = record["state"]
        if set(state) != {"schema", "mapping", "training_digest", "episodes"} or state["schema"] != SCHEMA:
            raise ValueError("invalid alignment receipt schema")
        return cls(state["mapping"], evidence_digest=state["training_digest"], episodes=state["episodes"])
