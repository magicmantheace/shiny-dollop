# D4 research — outcome-only removal of unnecessary plan actions

**Optional sandbox-only follow-up. No automatic promotion.** This experiment was designed after seeing the original plan-repair result, so it is **exploratory and post hoc relative to that study**. Its own separate protocol, `benchmarks/plan_compaction_protocol.json` (commit `8a733f4399f21293aa637f5a3d7d0ec91da33e3d`), was frozen before this follow-up's evaluation. Neither evaluation cohort is independently blind.

`CompactionMemory` performs one leave-one-role-out trial per subsequent episode using a previously completed plan, then receives only action acceptance/block feedback and terminal goal success. If omitting an action still leads to success and a shorter accepted trace, the shorter plan is retained; otherwise the attempted omission is marked as tested. Stable, opaque role IDs, deterministic action aliases, a fixed graph family and a seven-action budget remain **engineered**. This does not prove causal prerequisite identification, robust skill composition or reliable transfer to unrelated worlds.

## Frozen evaluation results

Six seeds, 80 episodes/seed. Same A (20 episodes) → B (40) → A (20) hidden schedule, with no public context label.

| Method | First cohort /240 | Second cohort /240 | Total /480 | Approx. mean attempted actions |
| --- | ---: | ---: | ---: | ---: |
| Existing repair-aware cached plan | **236** | 198 | **434** | 7.00 |
| Outcome-trained plan compaction | 192 | **203** | 395 | **4.96** |
| Memoryless reactive control | 81 | 73 | 154 | 7.00 |
| Hand-coded role order | 240 | 240 | 480 | 5.00 |
| Hidden-graph oracle | 240 | 240 | 480 | 4.00 |

**Main trade-off:** the ablation learner uses about two fewer actions per episode, but finishes **39 fewer goals** out of 480 compared with cached repair. In the development cohort it falls from 236 to 192 completions, while the additional cohort improves narrowly from 198 to 203. This is mixed evidence and **not a policy promotion**. A stronger adaptive baseline could balance success against action count; this code does not yet make that choice robustly.

During phase reversals, removing a prerequisite that seemed redundant in the previous hidden graph can cause failures. The learner cannot infer that a plan is safe in a new graph from a previous success. It stores whole action traces, not an explicit causal prerequisite DAG. The optional compaction strategy and old `RepairPlanMemory` are separately versioned and have replay-checked, tamper-detecting checkpoints; an internally consistent forged history cannot be authenticated by SHA-256.

## Reproduce

```sh
python -m unittest tests.test_plan_repair tests.test_plan_compaction -v
python -m benchmarks.plan_compaction_benchmark --cohort development --out benchmarks/plan_compaction_results.json
python -m benchmarks.plan_compaction_benchmark --cohort additional --out benchmarks/plan_compaction_additional_results.json
python -m benchmarks.transfer_benchmark
```

Run all historical tests separately before any release; local reconstructed tests are not comprehensive remote CI. Recommended next D4 research: plan safety testing against fresh graph families and action budgets with a frozen utility objective penalizing failures more than a few extra actions; compare against engineer-supplied role-order and proper causal-graph learner baselines. Do not use AthenZ identity, human-origin memories or Synveil action permissions. D1/D3/D4 are still open; V2A affective cognition remains before/overlapping V2B virtual home.
