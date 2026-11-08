"""Explicit, review-before-promotion updates for the existing tabular learner.

A proposal trains in a disposable private SQLite database. Its review uses
public simulator observations and a disjoint TRAIN-namespace validation cohort,
never the published TEST split or a simulator oracle. No weights are installed
without a separate explicit approval. This is a conservative development gate,
not proof of generalization, blindness, or model safety.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import random
import tempfile
from collections import defaultdict
from pathlib import Path

from developmental_ai.transfer import Layout, TransferBrain, episode_seed

SCHEMA = "developmental-ai.transfer-policy-review/v1"
VALIDATION_START = 3_000_000


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(seed, trained, q, visits):
    state = {
        "schema": SCHEMA,
        "seed": seed,
        "trained": trained,
        "q": [[list(s), a, v] for (s, a), v in sorted(q.items())],
        "visits": [[list(s), n] for s, n in sorted(visits.items())],
    }
    return hashlib.sha256(_canonical(state).encode("utf-8")).hexdigest()


def _validation(brain, count):
    outcomes = []
    for offset in range(count):
        index = VALIDATION_START + offset
        layout = Layout.generate(episode_seed(brain.seed, "train", index))
        action_rng = random.Random(episode_seed(brain.seed + 2, "train", index))
        outcomes.append(brain._run(layout, learning=False, rng=action_rng))
    return {
        "successes": sum(o.success for o in outcomes),
        "episodes": count,
        "mean_steps": round(sum(o.steps for o in outcomes) / count, 4),
        "mean_reward": round(sum(o.reward for o in outcomes) / count, 4),
        "mean_blocked": round(sum(o.blocked for o in outcomes) / count, 4),
    }


class StagedPolicyUpdate:
    """A single-use candidate; the original persistent model stays untouched.

    The candidate is held in process memory until approve/reject, not
    automatically restored after a crash. Approval SHA is an integrity
    cross-check, NOT a signature, identity proof, or delegation of permission.
    """

    def __init__(self, brain: TransferBrain, episodes: int, *,
                 validation_episodes: int = 64, max_success_loss: float = 0.02):
        if not isinstance(brain, TransferBrain):
            raise TypeError("expected an existing TransferBrain")
        if (type(episodes) is not int or episodes < 1 or
                type(validation_episodes) is not int or
                not 8 <= validation_episodes <= 256 or
                type(max_success_loss) not in (int, float) or
                not math.isfinite(max_success_loss) or
                not 0 <= max_success_loss <= 1 or
                brain.trained + episodes >= VALIDATION_START):
            raise ValueError("invalid or overlapping update/review budget")
        self._brain = brain
        self._closed = False
        self._baseline_hash = _fingerprint(brain.seed, brain.trained, brain.q, brain.visits)
        before = _validation(brain, validation_episodes)

        # The normal train() method persists, but only to this disposable DB.
        with tempfile.TemporaryDirectory(prefix="developmental-ai-candidate-") as temp:
            candidate = TransferBrain(Path(temp) / "candidate.sqlite3", seed=brain.seed)
            try:
                candidate.trained = brain.trained
                candidate.q = copy.deepcopy(brain.q)
                candidate.visits = defaultdict(int, copy.deepcopy(dict(brain.visits)))
                candidate.train(episodes)
                after = _validation(candidate, validation_episodes)
                self._candidate_q = copy.deepcopy(candidate.q)
                self._candidate_visits = copy.deepcopy(dict(candidate.visits))
                self._candidate_trained = candidate.trained
            finally:
                candidate.close()

        candidate_hash = _fingerprint(
            brain.seed, self._candidate_trained, self._candidate_q,
            self._candidate_visits,
        )
        # Simple paired-cohort non-inferiority threshold, not a confidence bound.
        eligible = (after["successes"] / validation_episodes >=
                    before["successes"] / validation_episodes - max_success_loss)
        self._receipt = {
            "schema": SCHEMA,
            "baseline_sha256": self._baseline_hash,
            "candidate_sha256": candidate_hash,
            "training_episodes": episodes,
            "validation_namespace": "train",
            "validation_start": VALIDATION_START,
            "validation_episodes": validation_episodes,
            "max_success_loss": float(max_success_loss),
            "before": before,
            "after": after,
            "eligible_for_manual_approval": eligible,
        }
        self._receipt_sha = hashlib.sha256(_canonical(self._receipt).encode()).hexdigest()

    def review(self):
        """Return measurements and a digest, without installing candidate data."""
        return {"receipt": copy.deepcopy(self._receipt), "sha256": self._receipt_sha}

    def reject(self):
        """Discard the unpromoted candidate; the original DB remains unchanged."""
        if self._closed:
            raise ValueError("proposal already resolved")
        self._closed = True

    def promote(self, *, approved: bool, receipt_sha256: str):
        """Require explicit approval, eligibility, and unchanged starting weights."""
        if self._closed or approved is not True or receipt_sha256 != self._receipt_sha:
            raise ValueError("missing or mismatched explicit candidate approval")
        if not self._receipt["eligible_for_manual_approval"]:
            raise ValueError("validation regression: promotion rejected")
        brain = self._brain
        if _fingerprint(brain.seed, brain.trained, brain.q, brain.visits) != self._baseline_hash:
            raise ValueError("base policy changed after proposal; restage update")
        if _fingerprint(brain.seed, self._candidate_trained, self._candidate_q,
                        self._candidate_visits) != self._receipt["candidate_sha256"]:
            raise ValueError("candidate mutated after validation")
        old_q = brain.q
        old_visits = brain.visits
        old_trained = brain.trained
        try:
            brain.q = copy.deepcopy(self._candidate_q)
            brain.visits = defaultdict(int, copy.deepcopy(self._candidate_visits))
            brain.trained = self._candidate_trained
            brain.persist()
        except Exception:
            brain.q, brain.visits, brain.trained = old_q, old_visits, old_trained
            raise
        self._closed = True
        return copy.deepcopy(self._receipt)
