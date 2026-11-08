# Occluded navigation v1 — one-time spatial clue and dead reckoning

## Claim and scope

The `developmental_ai.occluded_navigation` experiment requires an agent to navigate to a goal whose offset is revealed **only in the initial observation**. Later observations show four adjacent blocked-direction flags but **not** the target or absolute position. The agent receives the outcome of each attempted action (`move`, `blocked`, `empty_interact` or `collected`). It uses that feedback to update an explicitly engineered working-memory estimate of how far away the original target should be.

It learns the *action-selection policy* with tabular Q-learning. It does **not** learn how to design a memory representation, select relevant memories, map an unknown environment, infer imperfect proprioception, or discover autonomous goals. There are no real system actions.

## Environment

- Uses the unchanged `transfer.Layout.generate` distribution: 5–8-cell square grids, random start and target (at least three Manhattan cells apart), random walls with densities from 0.10 to 0.24 and a guaranteed reachable target.
- A single initial beacon reveals the exact signed target displacement relative to the start; the clue disappears forever after the first attempted action, even if that action is blocked.
- Every later observation contains **only** a four-bit wall mask. It contains neither target direction nor player coordinates. Perception is deterministic; actions provide perfect movement success/failure feedback.
- The `memory` controller stores the beacon and subtracts successful movement vectors from the stored displacement. The `reactive` controller discards the cue after its first action. Each has a **separately trained** Q-table and identical environment rules.
- States are the stored target displacement, clipped to +/-3 cells per axis, plus local wall mask. The learned policy does not receive any global map. Its exact internally stored displacement may be larger than three cells.
- The action vocabulary is up/down/left/right/interact. The success condition requires interacting at the hidden target. Each episode is limited to twice the grid area in steps.

## Benchmarks

```bash
python -m unittest discover -s tests -v
python -m benchmarks.occluded_navigation_benchmark --seeds 7 23 41 --train-episodes 3000 --test-episodes 200
python -m benchmarks.transfer_benchmark

python -m developmental_ai.occluded_navigation train --db private-nav.db --seed 7 --mode memory --episodes 3000
python -m developmental_ai.occluded_navigation evaluate --db private-nav.db --seed 7 --mode memory --episodes 200
python -m developmental_ai.occluded_navigation trace --db private-nav.db --seed 7 --policy learned > nav-trace.json
python -m developmental_ai.occluded_navigation verify --trace-file nav-trace.json
python -m developmental_ai.event_ledger export --trace-file nav-trace.json > nav-events.json
python -m developmental_ai.event_ledger verify --ledger-file nav-events.json --trace-file nav-trace.json
```

Three inspected development seeds were trained for 3,000 episodes in each mode, with 200 deterministic test-namespace episodes per seed. The test namespace is disjoint from training but **not a truly blind independent evaluation**, because the seeds and results have been inspected during development. We did not alter the old transfer benchmark or old episode generator, but this new experiment shares that generator's world family. Baselines are:

- `memory_untrained`: same model and memory mechanism without policy learning.
- `memory_trained`: learned policy with engineered beacon retention and exact action-based odometry.
- `reactive_trained`: separately trained policy that loses its initial beacon after the first action.
- `reactive_random`: random actions with no meaningful use of the stored target.
- `memory_greedy`: hand-coded greedy, obstacle-aware controller with access to stored displacement (same engineered memory as the learner).
- `full_map_oracle`: full-map breadth-first search with privileged layout access. **Not a same-observation comparison.**

The exact per-seed outputs live in `benchmarks/occluded_navigation_results.json`; changes to these numbers must be reproducible by rerunning the command, and no benchmark adjustment should be made to improve an inspected score.

## Restart and trace integrity

The model stores a schema/seed/mode-bound Q-table, visit counts and training counter in separate SQLite tables. It resumes at a deterministic train-namespace episode index; incompatible checkpoints fail closed. Test evaluations neither change learned Q-values nor advance training counters.

A trace contains the full sequence of simulation-only observed clues, local-wall masks, *estimated* memory state, action attempts and environmental outcomes. The verifier regenerates the layout and independently recomputes each action transition and engineered memory update. The optional `event_ledger` adapter exports the same evidence into bounded simulation-only event triplets, without executing actions or binding identities. Checksums are not signatures or proof of original process provenance.

## Remaining limitations

- Exact odometry is an explicit assumption. No uncertainty, path integration errors or landmark mapping are modeled.
- Maps are small and generated by the same family; there is no proof of broader task transfer.
- The heuristic baseline outperforms the learned policy. The zero-success learned reactive ablation reflects its particular training/decision behavior; the random baseline still succeeds on some maps.
- AthenZ identity information must never be injected into this repository or its synthetic training sets.
- Future work: learned landmark retention, conflicting location clues, noisy movement feedback, persistent map formation, task transfer under changed dynamics, and independently held-out protocol evaluation.
