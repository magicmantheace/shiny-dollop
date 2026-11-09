"""Experimental observation-only ring mapper with 0, 1, or 2 landmark sites.

Two sensor symbols (0 and 1) remain engineered and distinguishable, ring size
and initial position are supplied by the simulator, and only one stationary map
is represented per ring size. Unlike structured_landmarks, the two sites need
not lie a predefined distance apart; either site may be absent. No hidden
positions, movement outcomes, reward, or regime labels are fit inputs.
"""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from pathlib import Path

from developmental_ai.adaptive_dynamics import DynamicsModel, blank_counts, canonical
from developmental_ai.online_dynamics import forward_backward, validate_history
from developmental_ai.structured_landmarks import StructuredModel, INIT_ROLES

SCHEMA = "flexible-landmarks/v1"


def _check_sites(sites):
    if type(sites) is not dict or set(sites) != {"9", "11"}:
        raise ValueError("invalid site dictionary")
    for n in (9, 11):
        pair = sites[str(n)]
        if (type(pair) is not list or len(pair) != 2 or
                any(p is not None and (type(p) is not int or p < 0 or p >= n) for p in pair) or
                (pair[0] is not None and pair[0] == pair[1])):
            raise ValueError("invalid landmark configuration")


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


class FlexibleModel(StructuredModel):
    """Categorical role emissions with independent, optional map positions."""

    def __init__(self, sites=None, motion=None, odo=None, roles=None):
        self.sites = ({"9": [None, None], "11": [None, None]} if sites is None
                      else sites)
        super().__init__({"9": 0, "11": 0}, motion, odo, roles)

    def validate(self):
        super().validate()
        _check_sites(self.sites)

    def role(self, n, pos):
        if type(n) is not int or n not in (9, 11) or type(pos) is not int or not 0 <= pos < n:
            raise ValueError("invalid position")
        left, right = self.sites[str(n)]
        return 1 if pos == left else 2 if pos == right else 0

    def state(self):
        self.validate()
        return {"schema": SCHEMA, "sites": self.sites, "motion": self.motion,
                "odo": self.odo, "roles": self.roles}

    def record(self, seed):
        if type(seed) is not int:
            raise ValueError("invalid seed")
        body = {**self.state(), "seed": seed}
        return {"body": body, "digest": digest(body)}

    @classmethod
    def from_record(cls, record, seed):
        if (type(record) is not dict or set(record) != {"body", "digest"} or
                type(record["body"]) is not dict or
                set(record["body"]) != {"schema", "sites", "motion", "odo", "roles", "seed"} or
                record["body"]["schema"] != SCHEMA or type(seed) is not int or
                record["body"]["seed"] != seed or record["digest"] != digest(record["body"])):
            raise ValueError("invalid model record")
        body = record["body"]
        return cls(body["sites"], body["motion"], body["odo"], body["roles"])


def select_sites(histories, model, *, map_histories=24, site_penalty=3.0):
    """Search each topology's 0/1/2-site maps via observation likelihood.

    Evidence penalty is fixed before test evaluation, discouraging spurious
    landmarks when the signal is absent. A bounded TRAIN subset is only used
    for map discovery; EM still sees all provided training histories.
    """
    if not isinstance(model, FlexibleModel):
        raise ValueError("expected flexible model")
    if (type(histories) not in (tuple, list) or not 2 <= len(histories) <= 2400 or
            type(map_histories) is not int or not 2 <= map_histories <= 2400 or
            type(site_penalty) not in (int, float) or not 0 <= site_penalty <= 100 or
            not math.isfinite(site_penalty)):
        raise ValueError("invalid map fit settings")
    groups = {9: [], 11: []}
    for h in histories:
        n, _, _ = validate_history(h)
        groups[n].append(h)
    if any(not rows for rows in groups.values()):
        raise ValueError("both topologies require evidence")
    chosen = {}
    objective = {}
    for n, records in groups.items():
        subset = records[:map_histories]
        baseline = model.sites[str(n)]
        winner = None
        best = float("-inf")
        # Coordinates are not constrained to n//2 apart. Either role can be
        # absent, giving genuine 0/1/2-site hypotheses. Ordered marker IDs
        # are observed sensor classes, NOT simulator-provided map labels.
        candidates = [None] + list(range(n))
        for first in candidates:
            for second in candidates:
                if first is not None and first == second:
                    continue
                candidate = [first, second]
                model.sites[str(n)] = candidate
                logp = sum(forward_backward(model, h) for h in subset)
                cost = site_penalty * sum(p is not None for p in candidate)
                val = logp - cost
                # Fixed lexicographic enumeration breaks ties deterministically.
                if val > best + 1e-10:
                    best = val
                    winner = candidate
        model.sites[str(n)] = winner if winner is not None else baseline
        chosen[str(n)] = list(model.sites[str(n)])
        objective[str(n)] = round(best, 5)
    model.validate()
    return chosen, objective


def refine_sites(histories, model, *, site_penalty=3.0, map_histories=36):
    """Train-only coordinate refinement after sensor model probabilities are fit.

    Fixed model parameters isolate map-search changes from simultaneous EM
    drift. Do not run on held-out evaluation records.
    """
    if (not isinstance(model, FlexibleModel) or type(map_histories) is not int or map_histories < 2 or
            type(site_penalty) not in (int, float) or not math.isfinite(site_penalty) or
            site_penalty < 0 or site_penalty > 100):
        raise ValueError("invalid refinement inputs")
    groups = {9: [], 11: []}
    for h in histories:
        n, _, _ = validate_history(h)
        groups[n].append(h)
    if any(not rows for rows in groups.values()):
        raise ValueError("need both topologies")
    sites = {n: list(row) for n, row in model.sites.items()}
    for n in (9, 11):
        sub = groups[n][:map_histories]
        for role in range(2):
            best_site = sites[str(n)][role]
            best_score = float('-inf')
            for candidate in [None] + list(range(n)):
                other = sites[str(n)][1-role]
                if candidate is not None and candidate == other:
                    continue
                model.sites[str(n)][role] = candidate
                value = sum(forward_backward(model, h) for h in sub)
                value -= site_penalty * sum(p is not None for p in model.sites[str(n)])
                if value > best_score + 1e-10:
                    best_score = value
                    best_site = candidate
            model.sites[str(n)][role] = best_site
            sites[str(n)][role] = best_site
    model.validate()
    return {n: list(v) for n, v in sites.items()}


def fit_flexible(histories, *, iterations=6, map_histories=24, site_penalty=3.0):
    """Observation-only EM on a selected independent-site map."""
    if (type(histories) not in (tuple, list) or not 2 <= len(histories) <= 2400 or
            type(iterations) is not int or not 1 <= iterations <= 30):
        raise ValueError("invalid fit settings")
    for h in histories:
        validate_history(h)
    model = FlexibleModel()
    site_map, objective = select_sites(histories, model,
                                       map_histories=map_histories, site_penalty=site_penalty)
    curves = []
    initial_sites = {n: list(v) for n, v in site_map.items()}
    for iteration in range(iterations):
        if iteration == max(1, iterations // 2) and iterations >= 3:
            site_map = refine_sites(histories, model, site_penalty=site_penalty,
                                    map_histories=max(map_histories, 36))
        expected = blank_counts()
        ll = sum(forward_backward(model, h, expected) for h in histories)
        roles = [[0.] * 3 for _ in range(3)]
        for n in (9, 11):
            for pos, counts in enumerate(expected["landmark"][str(n)]):
                role = model.role(n, pos)
                for i, value in enumerate(counts):
                    roles[role][i] += value
        model = FlexibleModel(
            {n: list(v) for n, v in site_map.items()},
            [[v + .05 for v in row] for row in expected["motion"]],
            [[v + .05 for v in row] for row in expected["odo"]],
            [[roles[r][i] + .05 * INIT_ROLES[r][i] for i in range(3)] for r in range(3)],
        )
        curves.append(round(ll, 5))
    return model, {"initial_sites": initial_sites, "map_objective": objective, "fit_curve": curves}


class FlexibleStore:
    """Optional seed-bound, integrity-checked SQLite checkpoint (not approval)."""

    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.execute("CREATE TABLE IF NOT EXISTS flexible_state (id INTEGER PRIMARY KEY CHECK(id=1), record TEXT NOT NULL)")

    def save(self, model, seed):
        if not isinstance(model, FlexibleModel):
            raise ValueError("invalid model")
        payload = canonical(model.record(seed))
        with self.conn:
            self.conn.execute("INSERT INTO flexible_state(id,record) VALUES(1,?) ON CONFLICT(id) DO UPDATE SET record=excluded.record", (payload,))

    def load(self, seed):
        row = self.conn.execute("SELECT record FROM flexible_state WHERE id=1").fetchone()
        if row is None:
            return None
        try:
            return FlexibleModel.from_record(json.loads(row[0]), seed)
        except (TypeError, KeyError, json.JSONDecodeError) as exc:
            raise ValueError("invalid model checkpoint") from exc

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
