"""Optional observable-feedback prerequisite probing for symbolic simulations.

Wraps existing OutcomeSkills records rather than replacing its memory system.
Failed/accepted observations are correlated evidence, never ground-truth causes.
The planner only accepts public frames and local same-episode blocked-action data.
No OS, network, file actuation, hidden recipes, or automatic model promotion.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
from developmental_ai.outcome_skills import OutcomeSkills, check_frame


def constraints(memory: OutcomeSkills):
    """Summarize evidence about each action's possible necessary facts.

    An observed failure at F followed by success at F+{x} is suggestive
    evidence of x, not a controlled intervention; observations may be confounded.
    """
    if not isinstance(memory, OutcomeSkills):
        raise TypeError('expected OutcomeSkills memory')
    grouped = defaultdict(lambda: {'success': [], 'failed': []})
    for glyph, before, after, accepted in memory.events:
        grouped[glyph]['success' if accepted else 'failed'].append(frozenset(before))
    out = {}
    for glyph, rows in sorted(grouped.items()):
        wins, failures = rows['success'], rows['failed']
        possible = set.intersection(*(set(x) for x in wins)) if wins else set()
        # Only one-fact differences are counted as corroboration. We DO NOT
        # assert causality or promote these hypotheses automatically.
        paired = sorted({next(iter(s - f)) for s in wins for f in failures
                         if f < s and len(s - f) == 1})
        out[glyph] = {
            'successes': len(wins), 'failures': len(failures),
            'possible_prerequisites': sorted(possible),
            'single_fact_differences': paired,
            'uncertainty': 'no-success' if not wins else
                           'confounded' if not paired and len(possible) > 1 else
                           'observational',
        }
    return out


class PrerequisiteProber:
    """An optional policy layered over the original replayable OutcomeSkills.

    `blocked_at` maps per-episode *opaque action IDs* to sorted public facts
    at the last refusal. It is volatile, not learned training feedback.
    The agent can decide using recorded evidence without updating on test data.
    """
    def __init__(self, memory: OutcomeSkills):
        if not isinstance(memory, OutcomeSkills):
            raise TypeError('expected OutcomeSkills')
        self.memory = memory

    @classmethod
    def from_source(cls, source):
        return cls(OutcomeSkills.restore(source.record()))

    def observe(self, glyph, before, after, accepted):
        self.memory.observe(glyph, before, after, accepted)

    def record(self):
        return self.memory.record()

    @classmethod
    def restore(cls, record):
        return cls(OutcomeSkills.restore(record))

    def choose(self, frame, blocked_at=None):
        check_frame(frame)
        if frame['done']:
            raise ValueError('cannot act in completed episode')
        if blocked_at is None:
            blocked_at = {}
        if type(blocked_at) is not dict or len(blocked_at) > 24:
            raise ValueError('invalid local failed-action observations')
        actions = {a['glyph']: a['id'] for a in frame['actions']}
        if (any(type(a) is not str or a not in actions.values() for a in blocked_at)
            or any(type(f) is not list or any(type(v) is not str for v in f)
                   or f != sorted(set(f)) or not set(f).issubset(frame['facts'])
                   for f in blocked_at.values())):
            raise ValueError('forged blocked-action context')
        goal = next(a['glyph'] for a in frame['actions'] if a['id'] == frame['goal'])
        facts = set(frame['facts'])
        evidence = constraints(self.memory)
        effects = self.memory.knowledge()

        def ready(glyph):
            # Never repeat a failed action at exactly the same observable state.
            prior = blocked_at.get(actions[glyph])
            return prior is None or set(prior) != facts

        def missing(glyph):
            # Only paired failed/success observations are strong enough to
            # defer a probe. Mere co-occurrence produces spurious ancestors.
            row = evidence.get(glyph)
            return set(row['single_fact_differences']) - facts if row and row['successes'] else set()

        def solve(glyph, visited):
            if glyph in visited or glyph not in actions or not ready(glyph):
                return None
            needed = missing(glyph)
            if needed:
                for fact in sorted(needed):
                    producers = sorted((a for a in effects if a in actions and
                                        fact in effects[a]['effects']),
                                       key=lambda a: (-effects[a]['successes'], a))
                    for producer in producers:
                        next_action = solve(producer, visited | {glyph})
                        if next_action is not None:
                            return next_action
                return None
            # A successful known action that produces no new facts is not useful.
            if glyph in effects and set(effects[glyph]['effects']) <= facts:
                return None
            return glyph

        # Known goals and their observed prerequisites are the first choice.
        if goal in effects:
            option = solve(goal, set())
            if option is not None:
                return actions[option]
        # On an unfamiliar goal, one bounded probe first reveals blockage.
        elif frame['tick'] == 0 and ready(goal):
            return actions[goal]

        # Reconstruct known old skills using observed action outcomes.
        known = sorted((g for g in effects if g != goal and g in actions),
                       key=lambda g: (-len(evidence[g]['possible_prerequisites']),
                                      -effects[g]['successes'], g))
        for glyph in known:
            candidate = solve(glyph, set())
            if candidate is not None:
                return actions[candidate]

        previous_goal_failure = blocked_at.get(actions[goal])
        if (goal not in effects and ready(goal)
            and (previous_goal_failure is None
                 or len(previous_goal_failure) == 0
                 or frame['remaining'] <= 1)):
            return actions[goal]

        # Rotate unknown-action probing across episodes instead of permanently
        # sorting by action glyph. This is an engineered exploration heuristic.
        def rank_unknown(glyph):
            key = (frame['episode'] + '/' + glyph).encode('utf-8')
            return (evidence.get(glyph, {}).get('failures', 0),
                    hashlib.sha256(key).digest())
        unknown = sorted((g for g in actions if g not in effects and g != goal and ready(g)),
                         key=rank_unknown)
        if unknown:
            return actions[unknown[0]]
        if ready(goal):
            return actions[goal]
        # If every action has been observed blocked at this state, abstain;
        # the caller must terminate its bounded trial rather than spin.
        return None
