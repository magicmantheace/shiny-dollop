# Widened window abstention recovery — widened acting-window abstention trigger class for silent/split newest-four states

**6 November 2026 protocol frozen; 6 November 2026 implementation;
7 November 2026 evaluation; graded 7 November 2026. Status:
optional, simulated, unpromoted. No default-controller promotion,
no PR merge, no D1–D10 or V2A/V2B roadmap change, no
AthenZ/Synveil integration.**

## Experiment identity

- **Name and purpose:** `widened_window_abstention_recovery` —
  whether ONE new element, a widened abstention trigger class
  (newest-four opposition total ≤ 1 AND acting-window opposition
  ≥ 3 over the last 8 events, behind leg P and the carried
  authority), added to the graded preceding-pair candidate, can
  reach the first-switch (B1) engagement floor at states the
  newest four events leave silent or split, while holding the
  stationary profile and checkpoint-32 release. The preceding
  cycle answered the newest four events in both directions: the
  un-corroborated partial trigger engages but fails stationary
  selectivity, and four-event corroboration (leg R) holds the
  stationary partial arm but retained ZERO partial B1 firings
  (TAKEN 1/6 on both cohorts; newest-four total ≥ 2 at only 1/6
  B1 states per cohort). Build Order Priority 1 (Independent
  Learning), items 2 + 3 + 4; handoff §8 weak uncertainty
  calibration / excessive abstention. This protocol's PRIMARY
  criterion is criterion 11, the conjunction of the carried
  criterion 6 stationary form and the carried criterion 9 B1
  form as updated (a non-full firing may be a retained partial
  OR a widened firing); criteria 9, 6, 5 (release by checkpoint
  32, including sub-condition (d), abstained branch in 0 of 9
  states), 1 (B2 protection), and 4 (return-A harm) are its
  co-graded guards, reported second through sixth below. The
  protocol also froze a grading cap: a Demonstrated verdict
  additionally requires at least one widened-class B1 firing
  taken in at least one cohort.
- **Candidate:** `WidenedWindowAbstentionRecoveryMemory`
  (`developmental_ai/widened_window_abstention_recovery.py`) —
  IDENTICAL to the graded
  `PrecedingPairPartialAbstentionRecoveryMemory` in acting model
  (recent8 exactly), extended signal, retained archive, archive
  concordance, joint test (joint_count >= 1), recovery model,
  the full three-leg authority condition, the minority branch
  in full, leg P (reference_purity >= 0.70), and the full and
  retained-partial abstention classes with leg R on partials.
  The SINGLE changed element is the widened abstention trigger
  class: `newest4_opposed_count <= 1` (opposed_count +
  preceding_pair_opposed_count) AND `acting_opposed_count >= 3`
  over the last 8 events, behind leg P plus carried authority;
  leg R never gates widened triggers; the support threshold
  remains null (the acting count is this class's trigger
  threshold, not a revived support leg). New decision-record
  fields: newest4_opposed_count / widened_armed /
  widened_threshold (3). Minimum 52 events, else all-available
  fallback. Separate optional learner; the default controller
  and all existing learners are untouched; the graded
  preceding-pair candidate appears only as the decisive
  baseline.
- **Branch and commits:**
  `developmental-ai/widened-window-abstention-recovery`.
  Protocol frozen at `227494b` (BEFORE implementation);
  implementation at `57d0ae1`; evaluation at `4ca8304`. This
  grading report is committed on top of the evaluation commit.
- **Frozen protocol:**
  `benchmarks/widened_window_abstention_recovery_protocol.json`
  (frozen 2026-11-06, before any implementation, unit test,
  harness, or score inspection for this experiment). Its
  protocol-stage finding is part of the record: on the
  simulator's published rates the widened class's expected B1
  population was only ~0.08 raw / ~0.12 adjusted firings per
  cohort, and no wider window in the scan both populated the
  silent/split states non-vacuously and comfortably held the
  frozen stationary margins; W8 / >= 3 was frozen as the unique
  least-bad point with its stationary risk pre-registered.
- **Cohorts:** development 452003/452021/452027 and additional
  453001/453017/453041 — NEW at freeze, disjoint from every
  earlier cohort. Both cohorts are now **INSPECTED** and must
  never be re-tuned against. Detailed results:
  `benchmarks/widened_window_abstention_recovery_results.json`
  (development) and
  `benchmarks/widened_window_abstention_recovery_additional_results.json`
  (additional).
- **Simulator:** `StochasticWorld` unchanged. Schedule per seed:
  A → B1 (inverted) → return-A → B2 (inverted), plus a stationary
  A→A control arm. Checkpoints 0/2/4/8/16/32 for every stage;
  checkpoint 0 is a reported diagnostic, NOT graded.

## Verification

- Unit tests: **PASS** — full suite `python -m unittest discover
  -s tests`: 1294 tests OK in the implementation and evaluation
  stages, and 1294 tests OK again when re-run in this grading
  stage (run this pass; the grading-stage changes are
  documentation only, no code changed). Focused candidate
  tests: 53/53 PASS in the implementation stage.
- Historical regressions: **PASS** — `python -m
  benchmarks.transfer_benchmark` (unchanged) exited 0 in the
  evaluation stage, and exited 0 again when re-run in this
  grading stage.
- Frozen cohorts: **PASS (ran exactly as registered)** — both
  cohorts were run with no change to any frozen parameter,
  threshold, seed, or checkpoint. Every checkpoint entry carries
  the candidate's full decision record (including all widened
  fields and the full abstention-gate record with support
  threshold null), a checkpoint SHA256, and restore-replay
  identity verified true at every checkpoint in both cohorts
  (script-verified again in this grading stage — 72/72 entries
  per cohort; no criterion-7 field missing anywhere;
  support_threshold null everywhere;
  abstention_disarmed_by_support false everywhere;
  widened_threshold 3 everywhere; abstention_gate_armed
  recomputable from purity_armed, trigger kind, and
  preceding_pair_armed everywhere with 0 mismatches;
  newest4_opposed_count recomputable everywhere with 0
  mismatches; widened_armed recomputable everywhere with 0
  mismatches; the records-only widened-rule equals the
  candidate's taken branch everywhere).
- Linux validation: **UNVERIFIED** — no GitHub Actions run on the
  evaluation or grading commit was checked; no CI is claimed for
  `4ca8304` or for this grading commit.
- Windows validation: **UNVERIFIED** — same reason as above.

## Per-criterion grading (precommitted, graded individually, per cohort)

All figures below were script-computed from the saved detailed
results in this grading stage, not hand-copied (script and output
kept with the campaign records). Criterion 11, this experiment's
PRIMARY criterion, is reported first, and criteria 9, 6, 5, 1, and
4, its co-graded guards, next, as the protocol requires.

| # | Criterion | Development | Additional |
| --- | --- | --- | --- |
| 11 | PRIMARY B1 engagement beyond newest four with stationary selectivity (conjunction: (a) stationary side = criterion 6 form; (b) B1 abstention TAKEN ≥3/6 with ≥1 NON-FULL firing (retained partial or widened); (c) B1 harm ≤ guard; (d) B1 harm < recent8) | **PASS** | **PASS** |
| 9 | First-switch B1 engagement beyond newest four preserved ((a) TAKEN ≥3/6 with ≥1 non-full firing; (b) B1 harm ≤ guard; (c) B1 harm < recent8) | **PASS** | **PASS** |
| 6 | Stationary control selectivity not given back (abstentions ≤32/240; successes ≥ recent8 −6; harm ≤ recent8) | **PASS** | **PASS** |
| 5 | Release/productivity by k=32 (abstentions ≤36/144; successes ≥ recent8 −8; non-recent8 branch in ≤1 of 9 k=32 states; (d) abstained branch in 0 of 9 states) | **PASS** | **PASS** |
| 1 | Second-switch B2 protection preserved ((a) minority recovery TAKEN ≥3/6 pooled B2 onset states; (b) minority TAKEN ≤1/6 B1 and ≤1/6 return-A; (c) B2 harm ≤ guard AND ≤60% of recent8; (d) B2 successes ≥ guard + 16) | **FAIL** | **PASS** |
| 4 | Return-A onset harm preserved (≤ guard AND ≤60% of recent8, pooled k=2,4) | **FAIL** | **PASS** |
| 2 | Return-A recovery successes preserved (≥40% of frozen_A AND ≥ guard + 16, pooled k=2,4) | **PASS** | **PASS** |
| 3 | Pooled onset harm (≤ guard same-cohort; ≥5/6 cells ≤ recent8) | **PASS** | **PASS** |
| 7 | Full accounting in the saved detailed results | **PASS** | **PASS** |

### Criterion 11 (PRIMARY) — B1 engagement beyond the newest four with stationary selectivity (PASS / PASS)

Development: the **stationary side (a) PASSes in full** —
abstentions **0 of 240**, successes **124 = recent8's 124**, harm
**116 = recent8's 116** (see criterion 6). The **B1 side PASSes**:
abstention TAKEN at **3 of 6** pooled B1 onset states, exactly at
the floor, with **1 non-full firing — the cohort's widened
firing** (seed 452021 k=2, opposed_count 1, preceding 0,
newest4 1, acting 3, purity 0.857 — a split configuration leg R
could not retain). Sub-conditions (c) and (d) PASS: B1 harm
**48** vs the guard's **48** (at equality) and 48 < recent8's
**86**. Additional: the **stationary side PASSes** — abstentions
**16 of 240**, successes **89** vs recent8's **93** (required
≥ 87), harm **135** vs **147** (see criterion 6). The **B1 side
PASSes in full**: TAKEN at **6 of 6**, with **2 non-full
firings** — 1 retained partial (seed 453001 k=2, purity 0.943,
preceding 1) and **1 widened firing** (seed 453017 k=4,
opposed_count 0, preceding 1, newest4 1, acting 3, purity
0.824 — a silent newest pair at checkpoint 4). (c) B1 harm **0**
vs guard **55**; (d) 0 < recent8's **61**. **This is the first
PRIMARY pass on both cohorts in this abstention line, and the
grading cap's condition is met on raw figures on BOTH cohorts:
exactly one widened-class B1 firing was taken per cohort —
against the protocol's pre-registered expectation of ~0.08 raw
/ ~0.12 adjusted widened firings per cohort, and the additional
firing occurred at checkpoint 4, where the pre-registered
checkpoint-4-emptiness expectation said the class would be
effectively empty. The cap therefore does not bind; what blocks
a Demonstrated verdict is criteria 1 and 4 on development
alone (see the conclusion).**

### Criterion 9 — first-switch B1 engagement beyond the newest four preserved (PASS / PASS)

Development: **(a) ENGAGEMENT PASS at the floor** — TAKEN at
**3 of 6** pooled B1 onset states (1/3 at checkpoint 2, 2/3 at
checkpoint 4): 2 full firings (seed 452021 k=4, purity 0.824;
seed 452027 k=4, purity 0.806) and the 1 widened firing above.
The records-only preceding-pair-rule took **2 of 6** on the
same states, so the widened class added exactly the firing
that reaches the floor. Two partial B1 states were DISARMED by
leg R alone, both at preceding_pair_opposed_count 0 (seed
452003 k=4, purity 0.839; seed 452027 k=2, purity 0.838 — the
partial-purity-rule took both, and took 5/6 in total); one
state had no trigger of any class (seed 452003 k=2, opposed 0,
acting 1). **(b)** B1 harm **48** vs guard **48** — passes at
equality. **(c)** 48 < recent8's **86** — passes. B1 successes,
reported in full: candidate **0** vs recent8 **10** vs the
guard's **0** — every taken state forfeits its successes, and
the untaken states scored 0 through recent8 as well on this
cohort. Derivations at the same states: preceding-pair-rule 2,
widened-rule 3 (= candidate), partial-purity-rule 5,
purity-only-rule 2, partial-ungated-rule 5,
reference-purity-rule 2, release-rule 2, higher-corroboration 1.
The decisive preceding-pair baseline METHOD's B1 line is 0
successes / 64 harm, so the widened class is also worth 16 harm
against the decisive baseline on this cohort.
Additional: **(a) PASS** — TAKEN at **6 of 6** (3/3 at each
checkpoint): 4 full, 1 retained partial, 1 widened (above).
The preceding-pair-rule took **5 of 6** — the widened class
added the silent-pair checkpoint-4 state (seed 453017 k=4)
that no carried class could take. No B1 state was disarmed by
leg P or leg R on this cohort. **(b)** B1 harm **0** vs guard
**55**. **(c)** 0 < recent8's **61**. B1 successes: candidate
**0** vs recent8 **35** vs guard **25**, stated in full — the
engagement is bought with a complete forfeiture of B1 onset
successes on this cohort, exactly the abstention productivity
cost the protocol required reporting, not a hidden one.
Derivations: preceding-pair-rule 5, widened-rule 6,
partial-purity-rule 5, purity-only-rule 4, partial-ungated 5,
reference-purity-rule 4, release-rule 4, higher-corroboration
2. Recovery and minority firing at B1: 0 of 6 on both cohorts,
as in every preceding cycle.

### Criterion 6 — stationary control selectivity not given back (PASS / PASS)

Development: **PASS in full, at exact recent8 parity** —
**(a)** abstentions **0 of 240**; **(b)** successes **124 =
recent8's 124**; **(c)** harm **116 = recent8's 116**. No
control state was widened-armed (widened_armed at 0 of 15 graded
control states) and no widened-kind state occurred; the
candidate's branch differs from the preceding-pair-rule at 0 of
15 control states and from the partial-purity-rule at 2 of 15
(the two leg-R disarmings carried from the preceding cycle's
design). The pre-registered stationary widened survival did
not occur on this cohort.
Additional: **PASS in full** — **(a)** abstentions **16 of
240**; **(b)** successes **89** vs recent8's **93**, required
≥ 87 — passes with 2 to spare; **(c)** harm **135** vs
recent8's **147** — passes. The sole control abstention is the
carried **FULL** firing (seed 453041 k=2, opposed 2, preceding
1, newest4 3, acting 3, purity 0.811, 16 episodes; recent8
scored there in the pooled control line) — the candidate's
control line is identical to the decisive preceding-pair
baseline method's, branch diffs vs the preceding-pair-rule
0 of 15. Again **zero widened-armed and zero widened-kind
control states** (0 of 15): on these cohorts the widened class
added NO stationary firing on either cohort, against its
pre-registered expectation of ~0.8 raw / ~0.5 adjusted widened
control firings per cohort. **Net: the stationary risk the
protocol priced in advance did not materialize on these draws,
and the criterion-6 failure mode of the partial generation
(48/240 on both cohorts) stays repaired — development at exact
parity for the second consecutive cycle, additional passing
for the first time in this line.**

### Criterion 5 — release and productivity by checkpoint 32 (PASS / PASS)

Development: all four sub-conditions pass — **(a)**
abstentions **0 of 144**; **(b)** successes **60 = recent8's
60** (required ≥ 52); **(c)** non-recent8 branch in **0 of 9**
switch-stage k=32 states; **(d)** abstained branch in **0 of
9**. No late widened firing occurred; at return-A k=32 seed
452021 a full trigger was released by leg P alone (purity
0.618, disarmed_by_purity).
Additional: all four pass — abstentions **0 of 144**;
successes **60** vs recent8's **64** (required ≥ 56);
non-recent8 **1 of 9** (seed 453017 return-A minority_archive,
purity 0.741, scoring 0/16 vs recent8's 4/12 — a carried
minority routing, at the allowance exactly); abstained **0 of
9** (a late partial trigger at return-A k=32 seed 453041 was
released by leg P, purity 0.656). **Stated in full: the
additional k=32 successes (60) sit exactly ON the protocol's
Regression line (recent8 − 4 = 60) — at the line, not below it,
so the Regression clause does not trigger (see the
conclusion); the deficit is the one minority routing above
plus per-state variation, and the abstention side of release —
this cycle's exposed sub-condition (d), with the widened class
reading a window the carried releases did not gate — held at
zero on both cohorts.**

### Criterion 1 — second-switch B2 protection preserved (FAIL development / PASS additional)

Development: **(a)** minority recovery TAKEN at **6 of 6**
pooled B2 onset states (3/3 at each checkpoint; fractions
0.254–0.292, purity armed at every state) — passes, at full
engagement. **(b)** minority TAKEN 0/6 at B1 and 0/6 at
return-A — passes. **(c) FAIL on both comparisons**: B2 harm
**42** vs the guard's **30**, AND vs the 0.60 × recent8 ceiling
of 0.60 × 61 = **36.6**. **(d)** B2 successes **54** vs guard
+ 16 = 18 — passes. The failure's shape differs from every
preceding cycle's B2 failure in this line: engagement is NOT
the binding term — the minority branch fired at every B2 onset
state, no abstention fired at B2 onset, and the harm is the
minority model's own per-state harm at engaged states
(5, 5, 7, 7, 9, 9 across the six states; at seed 452027, both
checkpoints, the minority model scored 7/9 against recent8's
10/6 and 11/5 — worse than the acting model it replaced).
The guard, by contrast, abstained at the full-trigger B2
states (0 harm at 4 of 6 states). This is the carried B2
profile's harm ceiling failing at FULL engagement on new
cohorts — charged unchanged, and selected as the next
limitation (see the conclusion).
Additional: **PASS, narrowly on the ceiling** — (a) minority
TAKEN **5 of 6** (2/3 k=2, 3/3 k=4; the one non-engaged state,
seed 453001 k=2, took regular recovery at joint_count 1 and
scored 0/16, carrying 16 of the cohort's 43 B2 harm); (b) 0/6
and 0/6; (c) harm **43** vs guard **57** and vs the ceiling
0.60 × 72 = **43.2** — passes by **0.2**; (d) successes **53**
vs guard + 16 = 39. Stated in full: across both cohorts the
candidate's B2 harm (42 / 43) sits essentially at the frozen
ceiling on both — the B2 harm margin is exhausted in this
family even where the criterion passes.

### Criterion 4 — return-A onset harm preserved (FAIL development / PASS additional)

Development: **(a)** candidate return-A pooled onset harm
**55** vs the guard's **86** — passes. **(b) FAIL**: the
0.60 × recent8 ceiling is 0.60 × 86 = **51.6**, failed by 3.4.
Regular recovery TAKEN at 3 of 6 return-A onset states; the
three non-engaged states acted through recent8 and carry 44 of
the 55 harm (seed 452021 at both checkpoints, 16 each; seed
452027 k=2, 12), while the three recovery states scored harm
3, 3, and 5. The candidate is identical at return-A onset to
the extended, minority, reference-purity, abstention-release,
higher-corroboration, purity-only, partial, and preceding-pair
baseline methods on this cohort (all 41 successes / 55 harm):
inherited from the carried profile, not produced by the
widened class (no widened firing at return-A on either
cohort), and charged unchanged.
Additional: **PASS** — harm **36** vs guard **46** and ceiling
0.60 × 84 = **50.4**; regular recovery TAKEN at 6 of 6 states.

### Criterion 2 — return-A recovery successes preserved (PASS / PASS)

Development: candidate **41** successes vs frozen_A's 66 (40%
floor 26.4) and guard + 16 = 26 — passes. Additional:
candidate **60** vs frozen_A's 70 (floor 28.0) and guard + 16
= 18 — passes. Reported in full, not hidden: cumulative beats
the candidate at return-A on BOTH axes on BOTH cohorts
(development 64 successes at 32 harm vs the candidate's 41 at
55; additional 62 at 34 vs 60 at 36), and frozen_A also beats
it on both axes on both cohorts (66 at 30 development; 70 at
26 additional). Cumulative's return-A dominance on both axes
on both cohorts now extends to **eight** consecutive graded
cohort pairs.

### Criterion 3 — pooled onset harm not above guard (PASS / PASS)

Development: candidate pooled onset harm **145** vs the
guard's **164**, with all **6 of 6** pooled onset cells ≤
recent8 (B1 32/48 and 16/38, return-A 31/44 and 24/42, B2
21/36 and 21/25 against recent8). Additional: **79** vs the
guard's **158**, 6 of 6 cells ≤ recent8. Stated in full
alongside: the decisive preceding-pair baseline method's
pooled onset harm is ABOVE the candidate's on both cohorts
(161 development, 95 additional) — the widened class's net
onset effect on these cohorts was harm-reducing — while the
partial baseline method's pooled figure is BELOW the
candidate's on development (113; its B1 line took 5/6 states
there) and equal to the preceding-pair method's on additional
(95 vs the candidate's 79 — the candidate is below both
there).

### Criterion 7 — full accounting (PASS / PASS)

The saved detailed results contain every field listed in
metrics_reported: per-seed TRAIN actor accounting counted once,
per-method successes / harmful actions / abstentions at every
checkpoint, the candidate's full decision record including the
complete preceding-pair record (preceding_pair_threshold 1 at
72/72 entries per cohort), the full abstention-gate record
(support threshold null at 72/72 entries per cohort,
abstention_disarmed_by_support false everywhere,
abstention_gate_armed recomputable everywhere with 0
mismatches), AND the widened-class record (widened_threshold 3
at 72/72 entries per cohort, newest4_opposed_count and
widened_armed recomputable everywhere with 0 mismatches, the
records-only widened-rule equal to the candidate's branch
everywhere), checkpoint SHA256, and restore-replay identity
true at every checkpoint in both cohorts (72/72 entries per
cohort, script-verified in this grading stage). Learner
information-acquisition actions = 0, learner training actions
= 0, additional requested observations = 0, throughout.

## Learning evaluation

- Task successes at each checkpoint (candidate succ/harm/abst vs
  recent8 succ/harm), development: B1-0 (0/48/0 vs 0/48), B1-2
  (0/32/16 vs 0/48), B1-4 (0/16/32 vs 10/38), B1-8 (0/0/48 vs
  30/18), B1-16 (13/35/0 vs 15/33), B1-32 (21/27/0 vs 21/27);
  return_A-0 (9/39/0 vs 4/44), return_A-2 (17/31/0 vs 4/44),
  return_A-4 (24/24/0 vs 6/42), return_A-8 (34/14/0 vs 23/25),
  return_A-16 (29/19/0 vs 31/17), return_A-32 (27/21/0 vs
  27/21); B2-0 (11/37/0 vs 1/47), B2-2 (27/21/0 vs 12/36), B2-4
  (27/21/0 vs 23/25), B2-8 (33/15/0 vs 25/23), B2-16 (32/16/0 vs
  32/16), B2-32 (12/36/0 vs 12/36); control-0 (27/21/0 vs
  27/21), control-2 (28/20/0 vs 28/20), control-4 (27/21/0 vs
  27/21), control-8 (30/18/0 vs 30/18), control-16 (15/33/0 vs
  15/33), control-32 (24/24/0 vs 24/24). Additional: B1-0
  (0/32/16 vs 1/47), B1-2 (0/0/48 vs 13/35), B1-4 (0/0/48 vs
  22/26), B1-8 (12/4/32 vs 31/17), B1-16 (14/18/16 vs 25/23),
  B1-32 (31/17/0 vs 31/17); return_A-0 (0/48/0 vs 0/48),
  return_A-2 (30/18/0 vs 2/46), return_A-4 (30/18/0 vs 10/38),
  return_A-8 (19/13/16 vs 25/23), return_A-16 (28/20/0 vs
  21/27), return_A-32 (14/34/0 vs 18/30); B2-0 (10/38/0 vs
  4/44), B2-2 (22/26/0 vs 1/47), B2-4 (31/17/0 vs 23/25), B2-8
  (22/10/16 vs 29/19), B2-16 (30/18/0 vs 29/19), B2-32 (15/33/0
  vs 15/33); control-0 (5/27/16 vs 14/34), control-2 (14/18/16
  vs 18/30), control-4 (19/29/0 vs 19/29), control-8 (24/24/0
  vs 24/24), control-16 (18/30/0 vs 18/30), control-32
  (14/34/0 vs 14/34). Checkpoint 0 is diagnostic only
  (candidate k=0 harm per switch stage 48/39/37 development,
  32/48/38 additional).
- Comparison with the preceding learner: the candidate differs
  from the decisive preceding-pair baseline method at 2 of 72
  checkpoints (development) and 3 of 72 (additional) — exactly
  the widened class's footprint (the two B1 widened firings and
  their downstream cells, plus one additional downstream cell).
  Onset pooled successes / harm: candidate 95/145 development
  and 113/79 additional, vs the preceding-pair method's 95/161
  and 113/95.
- Comparison with simple fixed baselines: recent8 and the guard
  are graded throughout above; cumulative and frozen_A dominate
  the candidate at return-A (see criterion 2).
- Evidence needed before adaptation / retention: unchanged from
  the carried family at the recovery branches; at B1 the
  abstention family now engages on all three trigger classes.
  Past knowledge (minority and retained recovery) is retained
  exactly as in the graded candidate.
- Generalization: handoff level 2–3, simulator-bounded only. No
  level-6 or novel-representation claim: every element,
  including the widened class, its window, and its threshold,
  is designer-supplied. A PASS on criterion 11 demonstrates
  that a purity-gated abstention branch whose classes are a
  full-pair trigger, a preceding-pair-corroborated partial
  trigger, and a widened acting-window trigger for silent/split
  newest-four states protects the first switch in this
  simulator — on these cohorts, in this simulator only, not
  general first-contact handling, not calibrated uncertainty,
  and not real-world safety.

## Safety and evidence costs

- Harmful TEST actions: reported per cell above and per
  criterion; pooled onset 145 (development) / 79 (additional)
  against recent8's 233 / 217 and the guard's 164 / 158 — and
  against the decisive preceding-pair baseline method's 161 /
  95, which the candidate is BELOW on both cohorts.
- Harmful TRAIN acquisition actions by the learner: **0** — the
  learner issues no training interventions; all TRAIN evidence
  comes from the shared external actor stream, whose actual
  harmful / productive / neutral outcomes, reported harm, and
  label flips are published per seed in the saved results
  (criterion 7). Per-cohort totals (all stages): development —
  1,440 actor actions, 535 actual harmful, 531 actual
  productive, 374 actual neutral, 44 label flips; additional —
  1,440 actor actions, 522 actual harmful, 569 actual
  productive, 349 actual neutral, 51 label flips.
- Failed-by-abstention: pooled onset 48 / 288 (development) and
  96 / 288 (additional); checkpoint-32 0 / 144 on both cohorts;
  stationary control **0 / 240 (development) and 16 / 240
  (additional)** — the stationary cost is the single carried
  full firing, with zero widened stationary firings on either
  cohort. Abstentions are scored as failed tasks, never as
  successes.
- Additional requested observations: **0**.
- False confidence / unnecessary abstention: the unnecessary
  abstention is the additional control full firing graded
  under criterion 6. The B1 productivity cost is stated under
  criterion 9 in full: candidate B1 pooled successes 0 on both
  cohorts vs recent8's 10 / 35 and the guard's 0 / 25.
- Report integrity: frozen protocol committed before
  implementation (`227494b`); cohorts inspected only through
  the registered evaluation; no parameter was re-tuned against
  the 452003-family / 453001-family cohorts after inspection.
  Provenance limitation: developer-selected simulation seeds
  in one engineered two-feature simulator family; not
  independent external proof.

## Scientific conclusion

**Partially demonstrated — NOT Failed, and NOT a Regression.**
Per the protocol's own grading definitions: NOT Demonstrated,
because criteria 1 and 4 FAIL on the development cohort (all
nine criteria PASS on the additional cohort, and criterion 11
and criterion 7 PASS on both, so the Demonstrated clause's
all-nine-on-both requirement is not met; the grading cap does
not bind — the widened class recorded exactly one taken B1
firing on EACH cohort). The **Partially demonstrated** clause
governs exactly: criterion 11 and criterion 7 PASS on both
cohorts but criteria 1 and 4 FAIL on one cohort. The **Failed**
clause does not trigger: criterion 11, 9, 6, and 5 all PASS on
the additional cohort, none of criteria 1–4 FAIL there, and
criterion 7 PASSes on both. **Regression: no clause triggers**
— pooled onset harm 145/79 is well below recent8's 233/217;
control successes are level on development (124 = 124) and
−4 on additional (89 vs 93), so the more-than-6-on-both clause
does not trigger; checkpoint-32 successes are 60 vs the
recent8 − 4 line of 56 (development) and 60 vs the line of 60
(additional — AT the line, not below it); the full unit suite
and the historical transfer benchmark pass (see Verification).
What the experiment establishes, stated as prominently as the
remaining failures: **the widened class worked on these
cohorts beyond its own pre-registered expectation.** It was
frozen as a near-null population (~0.08 raw / ~0.12 adjusted
expected B1 firings per cohort, effectively checkpoint-2 only,
with its stationary survival priced as the central cost-side
risk); it realized exactly one taken B1 firing per cohort —
development at checkpoint 2 on a split configuration leg R
could not retain (the firing that lifts development's B1
engagement from the preceding-pair rule's 2/6 to the floor at
3/6), additional at checkpoint 4 on a silent newest pair (the
checkpoint the design arithmetic expected to be empty) — and
**zero** widened stationary firings on either cohort. With it,
the PRIMARY conjunction PASSes on both cohorts for the first
time in this abstention line: B1 engagement at/above the floor
with a non-full firing on both, B1 harm at the guard's level
(development, equality) and at zero (additional), the
stationary arm at exact recent8 parity (development) and
inside the frozen margins (additional), and checkpoint-32
abstention release held at 0 of 9 on both — including
sub-condition (d) for the widened class, whose late-firing
risk was pre-registered and did not occur. What remains
failing is outside the abstention branch entirely: the B2
harm ceiling at full minority engagement (development) and
the return-A harm ceiling at non-engaged states (development),
both carried profiles charged unchanged. Generalization level
2–3, simulator-bounded (see Learning evaluation).

**Next limitation (selected for the next cycle, Priority 1):**
second-switch (B2) onset harm at FULL minority engagement —
the B2 question in this line has changed shape: engagement is
no longer the binding term (minority TAKEN 6/6 development and
5/6 additional in this cycle; in earlier cycles the failures
were concentrated at non-engaged states), yet B2 pooled onset
harm sits at/above the frozen ceiling on both cohorts (42 vs
ceiling 36.6 and guard 30 on development — FAIL; 43 vs ceiling
43.2 on additional — PASS by 0.2), and the development harm is
the minority model's own per-state harm at engaged states
(5–9 per state, at one seed worse than recent8 at both
checkpoints). Measurable: on NEW cohorts under a NEW protocol,
whether an evidence-derived condition on the minority branch
itself (its model, its arming, or its joint test) can bring B2
pooled onset harm to ≤ guard AND ≤ 0.60 × recent8 on both
cohorts while holding minority engagement (≥ 3/6), selectivity
(≤ 1/6 at B1 and return-A), the criterion 11 B1/stationary
profile this cycle demonstrated, and checkpoint-32 release.
Recorded but not selected: criterion 4's development failure
is the return-A harm ceiling at the three non-engaged states
(44 of 55 harm through recent8; candidate identical to every
carried baseline method at return-A onset there); cumulative's
return-A dominance on both axes on both cohorts is now eight
consecutive graded cohort pairs, and frozen_A also beats the
candidate on both axes on both cohorts in this cycle; the
additional k=32 successes sit exactly on the recent8 − 4 line;
and B1 pooled successes are 0 on both cohorts — the abstention
branch's full productivity cost, reported under criterion 9,
which any future B1-productivity claim must answer.

Keep the learner optional and unpromoted, default controller
unchanged, no merge, no AthenZ/Synveil integration, D1–D10/V2A/V2B
unchanged.
