"""Conservative known-risk union and unseen identifier-remapping simulator.

Policy only: union of risk identities learned in *two existing* public
outcome histories. It cannot identify new hazards, learn latent semantics,
or guarantee safety; blocking a necessary action may halt useful behavior.

Simulator only: C remaps the old harmful `spoil` numeric signature and
the productive `fuel` signature, with no C training. Neither this mapping
nor the third-regime name is exposed to a runtime policy.
"""
from __future__ import annotations

from developmental_ai.affordance_memory import RiskMemory
from developmental_ai.contextual_affordance import ContextMemory, ShiftedCargo


class ConservativeUnionRisk(RiskMemory):
    """Optional read-only risk *veto*, not a causality or safety guarantee."""

    def __init__(self, histories: ContextMemory):
        if not isinstance(histories, ContextMemory):
            raise TypeError("two replayable known histories required")
        super().__init__()
        saved=histories.record()
        self.history_digest=saved["sha256"]
        # Retain only the already accepted positive risk flags from both
        # replayed observational histories; no environment-specific lookup.
        self._risk=frozenset().union(
            *(memory.avoid() for _,memory in histories._rows.values()))
        if not self._risk:
            raise ValueError("no learned risk associations to evaluate")

    def avoid(self):
        return set(self._risk)


class UnseenDescriptorCargo:
    """Benchmark-only third remapping with unchanged cargo physics."""

    def __init__(self, seed, split, index, variant):
        if variant not in ("A", "B", "C"):
            raise ValueError("unknown synthetic descriptor mapping")
        self.variant=variant  # SCORING/SIMULATOR ONLY
        self.world=ShiftedCargo(seed, split, index,
                                "B" if variant=="B" else "A")
        if variant=="C":
            # Intentionally novel relative to A/B training: the stable
            # two-byte signatures of necessary fuel and harmful spoil
            # exchange meanings. All original cargo transitions stay same.
            codes=self.world.world._features
            codes["spoil"],codes["fuel"]=list(codes["fuel"]),list(codes["spoil"])

    def frame(self):
        # Strip all phase/cue information before any learner sees it.
        return self.world.frame()["public"]

    def step(self, action, tick):
        return self.world.step(action, tick)["frame"]["public"]

    def execute(self, action, tick):
        result=self.world.step(action,tick)
        return {"accepted":result["accepted"],"public":result["frame"]["public"]}

    def success(self):
        return self.world.success()
