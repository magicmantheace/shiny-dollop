# D4 research: context-indexed procedural plan recall

**Status:** optional, synthetic and simulation-only. **D1, D3 and D4 remain open**. This is NOT hidden-prerequisite discovery, learned planning, or transfer into unrelated tasks. The evaluation protocol `benchmarks/context_plan_transfer_protocol.json` was committed at `ea787aae8647f6e8b0918b203ca3c70eb2829b4b` before code and evaluation.

## Experiment and assumptions

Two tasks **alternate every episode** and have the *same public goal* but different hidden prerequisite sequences. The model receives seven stable, opaque, seed-specific role identifiers, a stable but opaque context identifier, and randomly shuffled per-episode executable action aliases. The prerequisite graph is **never shown**. Every episode permits only **seven attempted actions**, including blocked attempts.

- Context A: two independent prerequisite actions, then their dependent assembly, then goal (four necessary successful steps).
- Context B: a three-action prerequisite chain followed by the same goal (four necessary successful steps).
- These two fixed, developer-designed graph patterns are reused across all seeds; only role strings and action aliases vary. This is **not** graph-topology generalization.
- Public feedback is accepted/blocked and goal completion; the simulator alone knows the graph. Training occurs online **during the reported test episodes**, not before them. “Later” results have benefited from earlier evaluation interactions and are not an independent offline holdout.

`ContextPlanMemory` tries a deterministic exploratory action order without role semantics. When a goal is reached, it saves the ordered **accepted** role sequence, indexed by context, with a shortest-success-trace preference. It replays that plan on future episodes of the same context. The frozen `latest` control keeps only the most recent successful plan for *both* contexts. The `reset` control uses the same exploratory selection but forgets between episodes. The lexical control simply tries opaque roles in string order. The oracle uses the generator's hidden prerequisites **for scoring only**.

No simulator internals, hidden DAGs, or privileged roles reach the learner. The use of stable role IDs, stable context labels, a fixed goal, and a binary success signal is itself a major hand-engineered prior. The model stores successful plans; it does not prove which prerequisites were causally necessary, and a simple per-context dictionary captures the gain.

## Precommitted protocol and exact results

- Development cohort: 14003, 14009, 14033; additional *previously inspected* cohort: 27007, 27011, 27017.
- `test/85000..85079`, 80 episodes per seed, alternating context A/B. First 20 are called “cold”; last 60 “warm”. No hyperparameter change after any result.
- Six seeds × 80 tasks = 480; methods compared on the same episodes and action limits.

| Method | First cohort / 240 | Second cohort / 240 | Combined / 480 | Cold / 120 | Warm / 360 |
| --- | ---: | ---: | ---: | ---: | ---: |
| **Context-indexed successful plan** | **185** | **202** | **387 (80.6%)** | 50 | 337 |
| Single latest successful plan | 105 | 112 | 217 (45.2%) | 37 | 180 |
| Reset memory every episode | 33 | 19 | 52 (10.8%) | 15 | 37 |
| Fixed lexical role order | 0 | 0 | 0 (0%) | 0 | 0 |
| Hidden-dependency oracle | 240 | 240 | 480 (100%) | 120 | 360 |

Average blocked attempts per episode: context-indexed **0.665**, latest-plan **2.294**, reset **3.015**, oracle **0**. The fixed lexical baseline is weak in this setting; the latest-plan baseline is a stronger, useful comparator. Context-indexed recall reaches 337/360 (93.6%) success after the first 20 episodes, but was **50/120 (41.7%)** in cold episodes and still fails on some seeds. All six learners eventually acquired a plan for both contexts, but the time required varies considerably.

## Integrity and boundaries

`NovelProcedure` verifies strictly bounded simulated actions and fresh ticks; public frames deliberately omit the DAG. The learner tracks pending proposals, prevents switching away from an unfinished episode, and replays all stored public action/outcome records before trusting a checkpoint. Recomputed digests cannot hide an inconsistent selected action, changed plan, or altered learned state. **SHA-256 is not authentication**: a fully self-consistent invented history requires external trusted signing/auditing to exclude. This module has no filesystem, network, or OS action executor.

Sixteen new scoped tests passed locally. Historical `python -m benchmarks.transfer_benchmark` was also re-executed from the unchanged original source snapshot and returned seeds 17 **76.0%**, 23 **69.0%**, 41 **66.67%**. The complete current remote GitHub suite or CI were not run. No personal information, user memories, or private model weights were committed.

## Next falsifiable research

A real D4 advancement requires **composable, transferable skills**, not a context-keyed list of actions: test novel graph topologies, remapped role identifiers across tasks, context changes within a single episode, and fewer action attempts; compare against a matched per-context trace lookup (which should tie this experiment) and independent causal discovery from attempted actions. Freeze new cohorts before any benchmark outcomes. D1 independent blind evaluation, D3 broad generalization, D4 skill-transfer evidence, AthenZ and Synveil integrations remain open. Approved V2A affective cognition precedes and overlaps V2B virtual home.
