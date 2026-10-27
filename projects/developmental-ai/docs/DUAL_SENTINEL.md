# Two-sentinel known-regime check and untrained-C abstention

**Experimental research only.** This mechanism is not an autonomous general
causal learner, risk certificate, new model default, or real-world permission.

## Why a second test is needed

The prior untrained-C stress showed the following successes **out of 360**:
A/B no-cue diagnostic 360/360 each, conservative union 360/360 each,
while unknown C produced 79/360 for the diagnostic, **0/360** for
the union, 120/360 for untrained exploration, and 360/360 for an
unfair privileged oracle. The zero-probe union matched full known
A/B performance; therefore claims that context identification itself
was necessary for those tasks are not supported.

This study evaluates a *different goal*: identifying when **neither of
two already trained outcome models** matches simple public feedback,
and abstaining from further ungrounded actions. An abstention is
explicitly recorded as **failure to complete the task**, even when it
avoids an irreversible harm in this fixed deterministic simulator.

## Mechanism

From 80 public training episodes in A and 80 in B per seed, the
algorithm identifies two known observational risk tokens
(one per previously segregated history). It uses only first-step
accepted/blocked statistics and requires each to have >=2 first
attempts in both training histories, with smoothed acceptance clearly
above or below 0.5.

On the same zero-resource start as the prior tests, it attempts
the two identified token-coded actions in the same order every time.
It then compares the pair of accepted/blocked outcomes against the
two source predictions. Exactly one match selects that memory.
No matches or insufficient training confidence returns **unknown** and
stops further attempts. Both probes count against the 18-step budget.
The public frame has numeric channels, opaque handles and two-byte
simulator-engineered identity descriptors, **never a context beacon,
private action mapping or variant label**.

In A/B, one risk-associated action is blocked at zero resources and
the other represents the harmless wash distractor. In the specifically
designed C swap, the first risk-associated identifier now means
productive fuel and the second still represents wash. Both are
accepted. This pair contradicts BOTH A and B known signatures.

The first two probes happen to be non-harmful in this exact toy
world because of its zero-resource starting state. This is
**not guaranteed safe in a different world**, and the model has
not learned a rigorous safety bound.

## Independent controls and requirements

This work uses the **same six previously inspected seeds**, and C
was invented post-hoc after observing the A/B successes. It is NOT
a fresh blind holdout. The benchmark runs A, B, C at test indices
9000–9059 with exactly the original prior A/B histories and all
previous C controls: original no-cue, union-known-risks, frozen
A-only, frozen B-only, untrained novel and privileged oracle.

Report **task completion, spoilage, stalls, attempted steps, known
classification and unknown flags** together. Short, harmless
stalled episodes are NOT successful task solving.

```sh
python -m unittest tests.test_dual_sentinel -v
python -m benchmarks.dual_sentinel_benchmark --cohort development
python -m benchmarks.dual_sentinel_benchmark --cohort inspected-additional
python -m unittest discover -s tests -v
python -m benchmarks.transfer_benchmark --seeds 17 23 41 --train-episodes 5000 --test-episodes 300
```

This optional safeguard should remain unmerged/default-disabled even
if C harm avoidance succeeds: an unknown model may abstain on
innocent novelty, and a genuinely harmful unknown action may already
cause harm on its first diagnostic. Generalizing will require
uncertainty estimation on fresh independent task generators, new
behavioral descriptors rather than hidden identity hashes, and
meaningful cost-of-information constraints. AthenZ/Synveil and
computational affect/virtual-room integration remain deferred.
