# D4 research — no-context plan repair under hidden prerequisite changes

**Optional sandbox-only study. Not a passed D1, D3, or D4 gate.**

The protocol was committed before implementation evaluation (`benchmarks/plan_repair_protocol.json`, commit `19078c0546660fb30130d58461e7e19e086164b3`). It fixes six seeds, 80 episodes per seed, and an unannounced A→B→A change in a hidden dependency graph. A context label and graph are **not** in public frames. Each action is assigned a new per-episode alias, although a **stable opaque role ID** remains public; this engineered ID is a major shortcut. Seven attempted actions are allowed. The world has seven role IDs and one goal; the two hidden graphs differ in one prerequisite. The generator is designed, not independently authored.

`RepairPlanMemory` saves *whole successful sequences* and avoids immediately retrying an action blocked at the same progress level. Its checkpoint replays every bounded observed action and terminal outcome. SHA-256 is **not** an owner signature or evidence of real consent. No file, shell, OS, network, physical or AthenZ/Synveil actions exist in this experiment.

## Frozen task results

Every cohort contains 3 seeds × 80 = 240 episodes. All cohorts were evaluated as part of this development pass and are **not blind**. `role_order` is hand-engineered to know a viable ordering of both graphs; the `oracle` reads private graph prerequisites **only in the scorer**.

| Method | Development success /240 | Additional success /240 | Combined /480 |
| --- | ---: | ---: | ---: |
| Repair-aware cached plan | 236 | 198 | **434** |
| Last successful plan, no block repair | 236 | 198 | **434** |
| No cross-episode memory | 81 | 73 | 154 |
| Reactive block avoidance, no plan | 81 | 73 | 154 |
| Hand-coded viable role order | 240 | 240 | 480 |
| Hidden-graph oracle | 240 | 240 | 480 |

Repair-aware and latest-plan reuse **tie on completed tasks**. Repair-aware reduces average blocked attempts from ~0.31 to ~0.11 across seeds, but that efficiency metric alone is insufficient evidence of transferable causal learning. Successful cached traces can contain *all prerequisite roles*, so they often work after the hidden graph changes without repair. The `plan_repair_protocol.json` and its original results are preserved unchanged.

## Reproduce

```sh
python -m unittest tests.test_plan_repair -v
python -m benchmarks.plan_repair_benchmark --cohort development --out benchmarks/plan_repair_results.json
python -m benchmarks.plan_repair_benchmark --cohort additional --out benchmarks/plan_repair_additional_results.json
python -m benchmarks.transfer_benchmark
```

The full repository suite and GitHub Actions are **not claimed**. The experiment is deliberately separated from all existing agent defaults and owner data. Versions 2A and 2B remain in their agreed order.
