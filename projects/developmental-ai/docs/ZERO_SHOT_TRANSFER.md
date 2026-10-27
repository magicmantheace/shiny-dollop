# Exploratory D3 zero-shot navigation policy transfer (not a completed gate)

This study asks whether an **existing trained policy** can be used in a second simulator family *without retraining its weights on that family*. It uses the new D2 public environment contract; it does not modify default navigation or the published D1 cross-family manifest.

## Setup

- Train the legacy `0transfer-v1` tabular Q policy **only** on 1,200 procedural visible-target grid episodes per seed, using `0train` data.
- Freeze the policy weights. Evaluate on 64 `0test` episodes per seed/family, indices 70000–70063, over seeds 2749, 6607, 9901. These seeds were already inspected during D1 development: **not independent or blind**.
- Evaluate **grid** and a distinct **occluded-navigation** world with a target clue only at the beginning. The goal disappears from observations after the first step.
- `0SpatialEncoder` uses a deliberately engineered one-slot target displacement memory and movement-feedback dead reckoning on the occluded task. This converts two observation formats to the old `0(dx,dy,blocked)` feature space. The policy never sees simulator true positions or full layout data, but the adapter is engineered domain knowledge and is not a learned memory controller.
- Compare **untrained/random actions**, **task-specific greedy heuristic** (strong hand-built reference), and **grid-trained Q reused zero-shot**. All use the public session API to choose actions and receive outcomes. No evaluation rewards update Q weights.
- Each seed is trained independently; no cross-seed pooled model. This is reuse of one learned policy between two *related* navigational families, not unrelated tasks or a universal transferable agent.

## Results

The evaluation contains 3 seeds × 64 episodes = 192 episodes per family.

| Test family | Random | Greedy (engineered) | Grid-trained Q (zero-shot) |
| --- | ---: | ---: | ---: |
| Grid, visible target | 32/192 (16.7%) | 175/192 (91.1%) | 136/192 (70.8%) |
| Occluded, initial beacon only | 34/192 (17.7%) | 178/192 (92.7%) | **142/192 (74.0%)** |

The grid-trained policy works significantly better than random in the occluded family **without learning from occluded rewards**. It does **not** beat the engineered greedy controller or demonstrate transfer to delayed-choice memory. Because the observation abstraction and dead reckoning were manually supplied, the outcome is a limited skill-reuse proof of concept, not learned perceptual transfer, robust world understanding, or completion of D3.

The protocol was added and examined during this development pass, **not prospectively frozen before running its results**. Preserve it unchanged as an exploratory baseline. Any future independent D3 claim needs a separate precommitted protocol, unrelated held-out task families, larger seed diversity, and matched controls including memory/feature ablations.

## Reproduce

```bash
python -m unittest tests.test_cross_family_transfer -v
python -m benchmarks.zero_shot_navigation_transfer_benchmark --train 1200 --test 64 --out benchmarks/zero_shot_navigation_transfer_results.json
python -m benchmarks.transfer_benchmark
```

No AthenZ/Synveil service actuation or private identity data is involved. Versions 2A and 2B remain future milestones.
