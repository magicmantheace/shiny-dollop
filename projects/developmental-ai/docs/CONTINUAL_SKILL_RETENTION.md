# Sequential skill adaptation and retention — October 20, 2026

## Purpose and boundaries

Optional development-only A→B→A study of the **existing**, simple
`OutcomeSkills` learner. It investigates whether prior metal/wood experience
helps a bounded agent acquire a deeper `delivery` goal after limited
target-domain practice, then retain ability on `assembly`. This is **not**
zero-shot delivery, out-of-ontology transfer, long-term artificial cognition,
or general catastrophic-forgetting prevention.

All four symbolic task families were manually built from a **shared** action
and fact ontology. The public action `glyph` labels retain meaning; only
opaque instance action IDs rotate. Recipes are deterministic, effects are
monotonic, rewards are terminal, and a public goal ID is always supplied.
The policy's unknown-action exploration is developer-defined and fixed.
Skill prerequisites inferred by intersection may contain irrelevant facts.
There is no learned natural-language understanding, autonomous goal selection,
or causal proof.

## Protocol

This follow-up was designed *after inspecting the earlier delivery 0/360
result*, so even previously uninspected extra seeds **cannot** be claimed as
an independent blind study. All six existing seeds have been inspected.

- Source training: 80 alternating `metal` / `wood` episodes (`train`
  namespace indices 0..79), as in the earlier optional experiment.
- Candidate adaptation: 0, 1, 2, 4, 8 and 20 `delivery` episodes with
  `learning=True` (`train` indices 120000..120019).
- Target-only control: identical 0..20 `delivery` training episodes,
  **no source experience**. This matches *target exposure*, not total
  experience or compute. Do not label it a fully experience-matched baseline.
- Frozen-source control: the original 80-episode model, **never updated**
  during target learning. Also compare memoryless/random and privileged
  recipe oracle target policies.
- After each milestone evaluate `delivery` **and** previously composed
  `assembly`, both without learning, at `test` indices 92000..92039.
- Each stage reuses those test indices, a deliberate repeated-development
  measurement, **not independent holdout**. No test outcomes enter learning.
- Count successes and attempted/blocked actions. Track stored observations
  and retained glyphs, and check exact state reconstruction after each
  stage; immutable frozen source must remain unchanged.
- Cohorts: development 17011/17021/17027; inspected additional
  33011/33023/33031. Do not silently change these values based on scores.

The learner does **not** advance its knowledge on evaluation feedback;
it updates only on the explicit target training steps.

## Expected failure mode and exploratory observation

Preliminary independent local *simplified-model reproduction* using the
same action rules suggested that two to four target delivery training
episodes are enough to learn the remaining `assemble/package/deliver`
chain after 80 source episodes, while a 20-episode delivery-only policy
remains stuck. The previously unadapted 0/360 delivery result stands:
**this is online target-domain adaptation, not new zero-shot success**.
The reproduction is a debugging indication only. **Do not publish exact
new benchmark scores until the repository's actual benchmark script runs.**

Target-only learning has fewer total episodes than the transferred policy
and faces fixed action ordering and distractors. A genuine generalization
study needs a stronger discovery/exploration baseline and tests with
previously unseen action semantics, not this common symbolic ontology.

## Run and validation

```sh
python -m unittest tests.test_continual_skill_benchmark -v
python -m benchmarks.continual_skill_benchmark --cohort dev
python -m benchmarks.continual_skill_benchmark --cohort additional
python -m unittest discover -s tests -v
python -m benchmarks.transfer_benchmark --seeds 17 23 41 --train-episodes 5000 --test-episodes 300
```

**Current blocker:** The private repository's GitHub Actions jobs continue
to fail with no executed steps. The full upstream suite and the new exact
benchmark runs are **not verified**. Keep the work as draft until executable
validation proves compatibility. The historical zero-shot experiment and
protocol are not modified.

## Follow-on work

1. Gather actual per-stage and per-seed learning curves; report sample and
   computational costs without cherry-picking.
2. Diagnose whether learning is driven by meaningful outcome-dependent
   exploration or fixed lexical action ordering. Add a stronger exploration
   control, permuted glyph identities, irrelevant observation structures,
   and independent families.
3. Introduce prerequisite counterexamples and policy confidence to avoid
   performing all spurious subskills; compare success **and** action costs.
4. Extend A→B→A into longer sequential, changed-rule environments, with
   measured forgetting rather than assuming append-only memory solves it.

No AthenZ or Synveil integration changes. Preserve V2A/V2B roadmap order.
