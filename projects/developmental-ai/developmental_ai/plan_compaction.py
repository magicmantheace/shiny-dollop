"""Optional reward-only leave-one-out compression of whole successful action plans.

This is not causal prerequisite discovery: it tests whether removing a role
from a saved plan still permits simulated goal completion. Stable role names,
a finite candidate library, and episode boundaries are engineered. The
controller receives no hidden graph or phase, and never executes real tools.
"""
from __future__ import annotations

import copy
from developmental_ai.plan_repair import (
    RepairPlanMemory, SCHEMA as BASE_SCHEMA, check_frame, canonical, digest,
)

SCHEMA = 'developmental-ai.plan-compaction/v1'


class CompactionMemory(RepairPlanMemory):
    """One independent remove-one-role test per episode; never uses truth labels."""

    def __init__(self, seed):
        super().__init__(seed, mode='repair')
        self.tested = {}
        self.active = None
        self.probe_outcomes = []

    def _set_probe(self):
        plan = self.plans[-1] if self.plans else None
        if not plan or len(plan) <= 2:
            self.active = None
            return
        ident = digest(plan)
        used = set(self.tested.get(ident, []))
        role = next((r for r in plan[:-1] if r not in used), None)
        self.active = {'plan_sha256':ident,'omit':role} if role is not None else None

    def _pick(self, frame):
        if self.active is None or not self.plans:
            return super()._pick(frame)
        last = self.plans[-1]
        if digest(last) != self.active['plan_sha256']:
            raise ValueError('plan mutated during leave-one-out trial')
        reduced = [r for r in last if r != self.active['omit']]
        self.plans[-1] = reduced
        try:
            return super()._pick(frame)
        finally:
            self.plans[-1] = last

    def propose(self, frame):
        check_frame(frame)
        is_new = self.last is None or (frame['episode_id'] != self.last['episode_id'] and self.last['done'])
        if is_new and frame['tick'] == 0:
            self._set_probe()
        return super().propose(frame)

    def feedback(self, result):
        if self.pending is None:
            raise ValueError('unrequested terminal feedback')
        active = copy.deepcopy(self.active)
        baseline_plan = list(self.plans[-1]) if self.plans else None
        super().feedback(result)
        if self.last['done']:
            if active is not None:
                plan_sha = active['plan_sha256']
                omit = active['omit']
                improved = (self.last['goal'] in self.last['completed'] and
                            omit not in self.accepted_order and
                            baseline_plan is not None and
                            len(self.accepted_order) < len(baseline_plan))
                self.probe_outcomes.append({'plan_sha256':plan_sha, 'omitted':omit,
                                            'improved':improved})
                if not improved:
                    attempted = self.tested.setdefault(plan_sha, [])
                    if omit not in attempted:
                        attempted.append(omit)
            self.active = None

    def record(self):
        state={'schema':SCHEMA,'base':super().record(),'tested':copy.deepcopy(self.tested),
               'active':copy.deepcopy(self.active),'probe_outcomes':copy.deepcopy(self.probe_outcomes)}
        return {'state':state,'sha256':digest(state)}

    @classmethod
    def restore(cls,record):
        if (type(record) is not dict or set(record) != {'state','sha256'} or
                type(record['state']) is not dict or digest(record['state']) != record['sha256']):
            raise ValueError('altered compaction checkpoint')
        s = record['state']
        if (set(s) != {'schema','base','tested','active','probe_outcomes'} or s['schema'] != SCHEMA or
                type(s['base']) is not dict or type(s['base'].get('state')) is not dict or
                s['base']['state'].get('schema') != BASE_SCHEMA):
            raise ValueError('invalid compaction version or embedded memory')
        obj=cls(s['base']['state']['seed'])
        for event in s['base']['state']['events']:
            if (type(event) is not dict or set(event) != {'before','action','result'} or
                    obj.propose(event['before']) != event['action']):
                raise ValueError('unreplayable compaction choice')
            obj.feedback(event['result'])
        if canonical(obj.record()) != canonical(record):
            raise ValueError('plan compaction state differs from replay')
        return obj
