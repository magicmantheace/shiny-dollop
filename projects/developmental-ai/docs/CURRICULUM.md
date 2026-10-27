# Multi-task curriculum-v1: engineering and evidence

This is a **development experiment**, not a blind evaluation, neural brain,
independently self-directed mind, or complete AthenZ integration.

## Rules and limits

- `reach`: move onto the goal; no interaction required.
- `collect`: move onto the goal and use `eat` (generic `interact`).
- `courier`: move onto pickup and interact, then return to starting depot and
  interact again. The environment changes the direction-to-target observation
  when carrying. It does not reveal the full map or a shortest path.
- Five actions: north, south, west, east, interact. Clipped relative goal
  displacement and an adjacent obstacle bitmask are the only observations.
- World size 5–8 with reachable random walls. Start and goal differ by at least
  Manhattan distance 3. No human or user-specific information is imported.
- Reward: -0.04 per step, -0.6 for collision, -0.5 for empty interaction,
  +2 for successful pickup, +8 on task completion, -2 on timeout.
- The tabular policy shares values between task rules; it does not receive a
  task identifier. In this experiment one learned navigation strategy is enough
  for many decisions; success in courier cannot establish that it invented a
  multi-stage goal or understands object permanence.

## Training, persistence, and evaluation

SQLite checkpoints store only a seed, schema, trained episode count, training
curriculum, state-action values and novelty counts; the current schema has no
migration path because it is a new experiment. Changing seeds or the training
curriculum at resume is rejected. Training uses a per-episode action RNG and
stable `sha256`-derived procedural seeds independent of Python's `hash()`.

The train namespace is distinct from the held-out `test` namespace for each
of the three tasks. The test split is never used for training, but seeds and
metrics were inspected during development. Evaluation does not update counts,
Q-values or training episode index. Evaluate all seeds rather than selecting
only the best run. An oracle BFS planner sees global map data withheld from
all other policies, so it is an upper bound, not a fair like-for-like agent.

A trace uses `developmental-ai.trace/v1`. Its checksum verifies internal
integrity only; replaying the action list against the exact procedural seed
also catches inconsistencies even after someone recomputes the checksum.
It contains **simulation-only** authority and no executor interface. AthenZ
must continue to distinguish synthetic agent experiences from true human
biography; Synveil must enforce independent typed action policies.

## Measured shortcomings and upcoming tests

The initial learned policy is substantially below the greedy baseline on each
of the three tasks. This is especially notable given both receive the same
engineered target-direction cues. Next experiments should test explicit
experience memories, occluded goals, changed cue reliability, and world models
only after fixing a *frozen* evaluation protocol with novel seeds. Neither
this module nor the first grid-world learner exhibits open-domain learning.
