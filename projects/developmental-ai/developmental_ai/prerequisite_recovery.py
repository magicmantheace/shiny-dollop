"""Experimental target-oriented probing with baseline-assisted recovery.

This is an optional, simulation-only controller. A change in the observed
set of learned action effects triggers fallback to the historical policy;
no privileged simulator labels or external actions are available. This is a
hand-engineered safeguard, NOT a learned general continual-learning rule.
"""
from __future__ import annotations

import hashlib
from developmental_ai.outcome_skills import OutcomeSkills, check_frame, digest
from developmental_ai.prerequisite_probing import constraints

SCHEMA = 'developmental-ai.prerequisite-recovery/v1'


class RecoveryProber:
    """Preserve a versioned source boundary within the existing skill memory."""

    def __init__(self, memory: OutcomeSkills):
        if not isinstance(memory, OutcomeSkills):
            raise TypeError('OutcomeSkills expected')
        self.memory = memory
        self._source_count = len(memory.events)
        self._source_sha256 = memory.record()['sha256'] if self._source_count else None
        self._source_glyphs = frozenset(memory.knowledge())

    @classmethod
    def from_source(cls, source):
        if not isinstance(source, OutcomeSkills) or not source.events:
            raise ValueError('nonempty source evidence required')
        return cls(OutcomeSkills.restore(source.record()))

    def observe(self, glyph, before, after, accepted):
        self.memory.observe(glyph, before, after, accepted)

    def record(self):
        state = {'schema': SCHEMA,
                 'memory': self.memory.record() if self.memory.events else None,
                 'source_count': self._source_count,
                 'source_sha256': self._source_sha256,
                 'source_glyphs': sorted(self._source_glyphs)}
        return {'state':state, 'sha256':digest(state)}

    @classmethod
    def restore(cls, saved):
        if (type(saved) is not dict or set(saved) != {'state','sha256'}
            or type(saved['state']) is not dict
            or saved['sha256'] != digest(saved['state'])):
            raise ValueError('invalid recovery checkpoint integrity')
        state = saved['state']
        if (set(state) != {'schema','memory','source_count','source_sha256','source_glyphs'}
            or state['schema'] != SCHEMA
            or type(state['source_count']) is not int
            or type(state['source_glyphs']) is not list
            or any(type(g) is not str for g in state['source_glyphs'])
            or state['source_glyphs'] != sorted(set(state['source_glyphs']))):
            raise ValueError('unsupported recovery schema')
        memory = OutcomeSkills() if state['memory'] is None else OutcomeSkills.restore(state['memory'])
        length = state['source_count']
        if not 0 <= length <= len(memory.events):
            raise ValueError('invalid source boundary')
        source = OutcomeSkills()
        for row in memory.events[:length]:
            source.observe(*row)
        actual_sha = source.record()['sha256'] if length else None
        if (actual_sha != state['source_sha256'] or
            sorted(source.knowledge()) != state['source_glyphs']):
            raise ValueError('unreplayable source-skill boundary')
        obj = cls(source)
        obj.memory = memory
        if obj.record() != saved:
            raise ValueError('recovery checkpoint replay differs')
        return obj

    def choose(self, frame, blocked_at=None):
        check_frame(frame)
        if frame['done']:
            raise ValueError('finished')
        blocked_at = {} if blocked_at is None else blocked_at
        if type(blocked_at) is not dict or len(blocked_at)>24:
            raise ValueError('invalid local block history')
        actions = {row['glyph']: row['id'] for row in frame['actions']}
        if any(type(k) is not str or k not in actions.values() or
               type(v) is not list or any(type(f) is not str for f in v) or
               v != sorted(set(v)) or not set(v).issubset(frame['facts'])
               for k,v in blocked_at.items()):
            raise ValueError('invalid local block evidence')
        facts = set(frame['facts'])
        evidence = constraints(self.memory)
        knowledge = self.memory.knowledge()
        newly_learned = set(knowledge) - self._source_glyphs
        if newly_learned:
            # An unfamiliar successful action changes the plan frontier.
            # Let the established controller exploit this new effect rather
            # than repeatedly retrying a target with uncertain prerequisites.
            # Block only actions failed at the CURRENT observable fact state.
            same_state = {a for a, prior in blocked_at.items()
                          if set(prior) == facts}
            return self.memory.choose(frame, same_state)

        goal = next(row['glyph'] for row in frame['actions'] if row['id'] == frame['goal'])

        def attemptable(g):
            prior = blocked_at.get(actions[g])
            return prior is None or set(prior) != facts

        def producers(fact):
            return sorted((g for g, item in knowledge.items() if g in actions and
                           fact in item['effects']), key=lambda g:(-knowledge[g]['successes'],g))

        # Avoid positive-context intersections: co-occurring distractors are
        # not verified preconditions. Only isolated fail/succeed contrasts
        # are used to prioritize old-skill preparation (still observational).
        core = {g for g,row in evidence.items()
                if g in actions and row['single_fact_differences'] and g in knowledge}
        for g in tuple(core):
            for fact in evidence[g]['single_fact_differences']:
                core.update(producers(fact))

        def solve(g, stack):
            if g in stack or g not in actions:
                return None
            if g in knowledge and set(knowledge[g]['effects']) <= facts:
                return None
            if not attemptable(g):
                return None
            for fact in evidence.get(g,{}).get('single_fact_differences',()):
                if fact not in facts:
                    for p in producers(fact):
                        option = solve(p, stack | {g})
                        if option is not None:
                            return option
            return g

        # Unknown goal: one early diagnostic probe.
        if goal not in knowledge and frame['tick'] == 0 and attemptable(goal):
            return actions[goal]
        for g in sorted(core, key=lambda g:(-len(evidence[g]['single_fact_differences']),g)):
            option = solve(g,set())
            if option is not None:
                return actions[option]
        if goal in knowledge and attemptable(goal):
            return actions[goal]
        if goal not in knowledge and frame['remaining'] > 1:
            unknown = [g for g in actions if g not in knowledge and g!=goal and attemptable(g)]
            if unknown:
                # Shared symbolic ontology remains an engineered shortcut.
                def rank(g):
                    seen_failures = evidence.get(g,{}).get('failures',0)
                    return (-int(seen_failures>0),
                            hashlib.sha256((frame['episode']+'/'+g).encode()).digest())
                return actions[min(unknown,key=rank)]
        if attemptable(goal):
            return actions[goal]
        return None
