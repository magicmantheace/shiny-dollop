# Learned movement-memory update across two simulator families (experimental)

This pass extends the D1/D2/D3 work from another hand-built transfer adapter to an
**observation-trained memory update**. In visible-target `grid` training,
`train_grid_updates()` measures how the public clipped target-relative sensor
changes after an action and its public outcome event. It fits a categorical
transition table `P(Δtarget_x, Δtarget_y | action, outcome)` and deploys the
mode to maintain the remembered target offset in the `occluded` simulator,
where the target clue appears only once. It does **not** access either world's
hidden position, wall map, target location after the cue, or an oracle action.

**Important limitation:** one memory slot, the rule to write its initial beacon,
the target-offset representation, the event-name equivalence between task
families, and the trained navigation Q policy are *engineered*. **Only the
movement-conditioned offset update is learned.** The source and destination
families share 2D grid mechanics, so this is related-task transfer, not general
memory induction or transfer to delayed-choice problems. No runtime learning,
owner-person information, AthenZ identity, external actions or extra permissions.

## Locked protocol and data partitions

[`benchmarks/learned_memory_transfer_protocol.json`](../benchmarks/learned_memory_transfer_protocol.json)
was written before the additional-seed evaluation. All fits use **only**
`grid/train/0..1199` for a separate Q navigation policy and
`grid/train/0..79` for the memory updater, per seed. The two training sources
share some grid episode indices but solve different fitting problems: Q learns
which action to choose from state/reward, while the memory model learns action
and public sensor-change correspondences with no reward labels. No `test`
indices, private positions, or `occluded` episode rewards enter either fit.

- Development seeds: 2749, 6607, 9901 (previously inspected in D1/D3).
- Additional seeds: 15101, 22003, 31013 (first evaluated during this pass;
  **not an independent blind audit**).
- Test episodes: `occluded/test/80000..80063` per seed.
- Policies: random; a **forgetful** one-slot ablation; grid Q with
  **hand-engineered** dead reckoning; and the **same** frozen Q with a learned
  memory-update table. Policies use matched action RNG streams for fair
  comparisons, except the intentionally random-action reference.
- Result metrics: successful terminal collects, mean navigation steps,
  number of public transition samples and the learned update table. Each
  cohort contains 3 seeds × 64 test episodes = 192 evaluations per policy.

## Results

| Cohort and method | Seed 1 | Seed 2 | Seed 3 | Total |
| --- | ---: | ---: | ---: | ---: |
| Development random | 17 | 14 | 12 | 43/192 |
| Development forget target | 0 | 0 | 0 | 0/192 |
| Development engineered update | 52 | 41 | 40 | 133/192 |
| **Development learned update** | **52** | **41** | **40** | **133/192** |
| Additional random | 14 | 11 | 10 | 35/192 |
| Additional forget target | 0 | 0 | 0 | 0/192 |
| Additional engineered update | 42 | 42 | 40 | 124/192 |
| **Additional learned update** | **42** | **42** | **40** | **124/192** |

The sensor-learned update retains **all** baseline hand-coded navigational
successes in the examined protocol. This is evidence of successful
learning-and-reuse for an engineered finite-state memory transition, not a gain
over an ideal manual baseline. There are no downstream gains beyond replacing
hardcoded update arithmetic. The single-slot cue-write and task-specific
feature abstraction still account for much of the transfer ability.

## Verification, replay and limitations

- The updater has a versioned, counts-bound SHA-256 fingerprint, strict state
  validation, and deterministic regeneration from the same train namespace.
- `PortableOffsetMemory` persists a bounded public-event history and replays
  learned updates on restore; altered outcomes or derived memory contents are
  rejected even when the outside digest is recomputed, *unless* the altered
  event history is itself observationally plausible. This is consistency,
  **not authenticated provenance**.
- The new memory component exposes no system actions and cannot authorize a
  model bank promotion. The default navigation and AthenZ/Synveil boundaries
  remain unchanged.
- Clipped `±3` visible displacement values would confound displacement
  labels, so training uses only consecutive public sensor pairs with both
  axes strictly inside this clipping boundary.
- The delayed-choice task and unfamiliar non-grid task families remain an
  explicit unproven D3 gate; autonomous memory allocation, learned forgetting
  policies, true continual adaptation, and real independent blind tests remain
  open.

## Reproduce

```sh
python -m unittest tests.test_learned_spatial_memory tests.test_cross_family_transfer -v
python -m benchmarks.learned_memory_transfer_benchmark --seeds 2749 6607 9901 --train-q 1200 --train-memory 80 --episodes 64 --out benchmarks/learned_memory_transfer_results.json
python -m benchmarks.learned_memory_transfer_benchmark --seeds 15101 22003 31013 --train-q 1200 --train-memory 80 --episodes 64 --out benchmarks/learned_memory_transfer_audit_results.json
python -m benchmarks.transfer_benchmark
```

Versions 2A (affective development) and 2B (virtual room) remain post-v1
milestones, with their agreed overlap preserved.
