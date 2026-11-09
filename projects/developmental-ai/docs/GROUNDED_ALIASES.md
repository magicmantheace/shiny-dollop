# Train-grounded source aliases (D3 experiment, not zero-shot transfer)

## Question and boundary

Can a reward-trained one-slot write/keep gate operate when the target task calls
its contexts and cue sources something completely different from the source
training task? The existing `online_memory_gate` was trained on source labels
`A/B/N` and context integers `0/1`. This adapter estimates a mapping from
**target-domain paired public cues** to the roles the gate already knows.

**Calibration is supervised**: in *train* episodes 70000+, the simulator
provides a one-time, public target beacon, and the experimental cue generator
provides five competing offsets. An exact match to the public beacon is an
informative calibration signal. The adapter never uses the simulator's hidden
position, full map, privileged correct-channel label, or *test* rewards. It
never receives the reference in `select(...)` during evaluation.

The calibration must contain both context categories, all five sources, and
unique evidence. It refuses ambiguous matches (best rate < 0.65 or advantage
< 0.25). It maps observed source labels into the roles favored by the frozen
`online_memory_gate`. Arbitrary alias naming/order is permuted per seed.

This is **not** zero-shot cross-domain understanding. The public reference
and the fact that exact offset equality establishes correctness are strong,
**engineered** shared semantics. The target cue stream itself is synthesized
from the public beacon and the source role structure remains analogous.
Only the names have changed; a real independent environment family has not
been solved.

## Fixed evaluation within this development pass

Training: 1,800 delayed selective-memory episodes (`train/0+`) and 24
visible-grid episodes for the learned motion updater. The alias adapter sees
48 paired *train* observations at `train/70000+`. Evaluation is 40 new
occluded-navigation `test/97000+` episodes per seed, using the unchanged
navigation action heuristic. Initial seeds 2749/6607/9901; additional
previously inspected seeds 17431/24869/37021. Both cohorts were examined
in this development pass, so **neither is blind**.

| Controller | Initial 120 | Additional 120 | Combined 240 |
|---|---:|---:|---:|
| Alias-grounded learned gate | 113 | 110 | **223** |
| Simple paired-label lookup (no memory model needed) | 113 | 110 | **223** |
| Correct reference cue, privileged to scoring | 113 | 110 | **223** |
| Always first | 24 | 19 | 43 |
| Always last | 18 | 33 | 51 |
| Random cue | 19 | 23 | 42 |
| Wrong context alignment | 0 | 0 | 0 |

These are *task success* metrics, not source-alignment confidence bounds.
Simple paired-label lookup matches the learned gate: **the stronger control
shows no incremental benefit from transfer here**. We retain this negative
result rather than claiming it establishes D3 generalization.

The adapter binds its saved model to a specific memory gate and recomputes its
mapping from saved calibration observations on restore. Hashes are not signed
or authenticated: an attacker able to forge both evidence and checksum can
still create a plausible self-consistent snapshot. This code grants no model
promotion or system actions. `select()` rejects unknown target aliases and
unexpected fields. No private identity or personal experience is stored.

## Reproduce

```sh
python -m unittest discover -s tests -p 'test_grounded_aliases.py' -v
python -m benchmarks.grounded_aliases_benchmark --seeds 2749 6607 9901 --out benchmarks/grounded_aliases_results.json
python -m benchmarks.grounded_aliases_benchmark --seeds 17431 24869 37021 --out benchmarks/grounded_aliases_additional_results.json
python -m benchmarks.transfer_benchmark
```

**Next:** add a novel environment with different cue reliability mechanisms,
then freeze candidate/protocol prior to independent evaluation. The D1/D3
gates remain open. The D2 API remains simulation-only. Versions 2A and 2B
remain post-core in the approved sequence.
