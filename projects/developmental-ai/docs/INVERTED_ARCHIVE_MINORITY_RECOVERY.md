# Inverted archive minority recovery — inverted full-archive fit for the minority branch's model

**7 November 2026 protocol frozen; 7 November 2026 implementation;
7 November 2026 evaluation; graded 8 November 2026. Status:
optional, simulated, unpromoted. No default-controller promotion,
no PR merge, no D1–D10 or V2A/V2B roadmap change, no
AthenZ/Synveil integration.**

## Experiment identity

- **Name and purpose:** `inverted_archive_minority_recovery` —
  whether ONE changed element, the minority branch's MODEL
  (a `RelationOutcomeMemory` fitted on ALL retained archive
  events with progress/damage labels swapped, neutral unchanged,
  in place of a fit on the minority set only), can bring
  second-switch (B2) pooled onset harm to ≤ guard AND
  ≤ 0.60 × recent8 on BOTH cohorts at full minority engagement,
  while holding engagement, selectivity, the criterion 11
  B1/stationary profile the widened-window cycle demonstrated,
  and checkpoint-32 release. The widened-window cycle's B2
  failure was at FULL engagement (minority TAKEN 6/6 development,
  harm 42 vs guard 30 and ceiling 36.6, all of it the minority
  model's own per-state harm), and its selection stage recorded
  that NO recorded minority-branch quantity separated high-harm
  from low-harm engaged states — so this cycle changed the model
  construction itself, not a gate. The minority SET is still
  computed in full and still drives arming, concordance/joint
  records, and every recorded minority field; branch selection
  is identical to the decisive baseline by construction. Build
  Order Priority 1 (Independent Learning), items 2 + 3 + 4;
  handoff §8 inconsistent adaptation to changing rules / harmful
  decisions from the recovery model. This protocol's PRIMARY
  criterion is criterion 12, the conjunction of (a) criterion 1's
  B2 form, (b) criterion 11's carried B1/stationary form in full,
  and (c) criterion 5's release form in full; criteria 1, 11, 9,
  6, 5, and 4 are its co-graded guards. The protocol also froze
  a grading cap: a Demonstrated verdict additionally requires
  ≥ 1 minority-fired B2 onset choice differing from the decisive
  baseline's in at least one cohort.
- **Candidate:** `InvertedArchiveMinorityRecoveryMemory`
  (`developmental_ai/inverted_archive_minority_recovery.py`) —
  IDENTICAL to the graded `WidenedWindowAbstentionRecoveryMemory`
  in acting model (recent8 exactly), extended signal, retained
  archive, archive concordance, joint test (joint_count >= 1),
  recovery model, the full three-leg authority condition, the
  minority branch's arming / concordance / joint records, leg P
  >= 0.70 on both recovery branches, and the full /
  retained-partial / widened abstention classes with leg R on
  partials and support threshold null — verified by a diff
  against the graded widened-window candidate at implementation:
  the ONLY code differences are the minority model construction,
  the new decision-record fields
  minority_model_archive_count / minority_model_inverted (true),
  its docstring, and names/schema. Minimum 52 events, else
  all-available fallback. Separate optional learner; the default
  controller and all existing learners are untouched; the graded
  widened-window candidate appears only as the decisive baseline.
- **Branch and commits:**
  `developmental-ai/inverted-archive-minority-recovery`.
  Protocol frozen at `c89916a` (BEFORE implementation);
  implementation at `fac6817`; evaluation at `9b83c2f`. This
  grading report is committed on top of the evaluation commit.
- **Frozen protocol:**
  `benchmarks/inverted_archive_minority_recovery_protocol.json`
  (frozen 2026-11-07, before any implementation, unit test,
  harness, or score inspection for this experiment). Its design
  basis is part of the record: a gating design was rejected on
  the selection stage's recorded evidence (no recorded minority
  quantity separates high- from low-harm engaged states, and
  gating a firing off returns its state to recent8 at a higher
  per-state harm level); the minority-set fit is structurally
  degenerate (per-bucket counts pure by construction); the
  simulator's exact-inversion structure defines the inverted fit
  with NO free threshold (archive 328/330 events at B2 k=2/4,
  majority-sign attenuation factor ~0.61, training-size ratio
  ~3.4x raw vs the minority set); an irreducible TEST flip floor
  of ~2 harm/state (~12 pooled) was stated in advance.
- **Cohorts:** development 462003/462021/462039 and additional
  463001/463017/463041 — NEW at freeze, disjoint from every
  earlier cohort. Both cohorts are now **INSPECTED** and must
  never be re-tuned against. Detailed results:
  `benchmarks/inverted_archive_minority_recovery_results.json`
  (development) and
  `benchmarks/inverted_archive_minority_recovery_additional_results.json`
  (additional).
- **Simulator:** `StochasticWorld` unchanged. Schedule per seed:
  A → B1 (inverted) → return-A → B2 (inverted), plus a stationary
  A→A control arm. Checkpoints 0/2/4/8/16/32 for every stage;
  checkpoint 0 is a reported diagnostic, NOT graded.

## Verification

- Unit tests: **PASS** — full suite `python -m unittest discover
  -s tests`: 1351 tests OK in the implementation and evaluation
  stages, and 1351 tests OK again when re-run in this grading
  stage (run this pass; the grading-stage changes are
  documentation only, no code changed). Focused candidate
  tests: 57/57 PASS in the implementation stage.
- Historical regressions: **PASS** — `python -m
  benchmarks.transfer_benchmark` (unchanged) exited 0 in the
  evaluation stage, and exited 0 again when re-run in this
  grading stage.
- Frozen cohorts: **PASS (ran exactly as registered)** — both
  cohorts were run with no change to any frozen parameter,
  threshold, seed, or checkpoint. Every checkpoint entry carries
  the candidate's full decision record (including both
  minority-model fields and the full abstention-gate record with
  support threshold null), a checkpoint SHA256, and
  restore-replay identity verified true at every checkpoint in
  both cohorts (script-verified again in this grading stage —
  72/72 entries per cohort; no criterion-7 field missing
  anywhere; support_threshold null everywhere;
  abstention_disarmed_by_support false everywhere;
  widened_threshold 3 everywhere; preceding_pair_threshold 1
  everywhere; abstention_gate_armed, newest4_opposed_count, and
  widened_armed recomputable everywhere with 0 mismatches; the
  records-only widened-rule equals the candidate's taken branch
  everywhere; minority_model_archive_count ==
  archive_events_count everywhere and minority_model_inverted
  true everywhere; branch selection identical to the widened
  method at 72/72 entries per cohort; the minority-model
  cross-check PASSes at every minority-fired state — 11
  development / 13 additional — candidate choice == the
  swapped-archive model's choice and widened choice == the
  minority-set model's choice in every case).
- Linux validation: **UNVERIFIED** — no GitHub Actions run on the
  evaluation or grading commit was checked; no CI is claimed for
  `9b83c2f` or for this grading commit.
- Windows validation: **UNVERIFIED** — same reason as above.

## Per-criterion grading (precommitted, graded individually, per cohort)

All figures below were script-computed from the saved detailed
results in this grading stage, not hand-copied (script and output
kept with the campaign records). Criterion 12, this experiment's
PRIMARY criterion, is reported first, and criteria 1, 11, 9, 6,
5, and 4, its co-graded guards, next, as the protocol requires.

| # | Criterion | Development | Additional |
| --- | --- | --- | --- |
| 12 | PRIMARY B2 protection at full engagement with carried profile (conjunction: (a) criterion 1 B2 form; (b) criterion 11 carried profile in full; (c) criterion 5 release in full) | **FAIL** | **FAIL** |
| 1 | Second-switch B2 protection preserved ((a) minority recovery TAKEN ≥3/6 pooled B2 onset states; (b) minority TAKEN ≤1/6 B1 and ≤1/6 return-A; (c) B2 harm ≤ guard AND ≤60% of recent8; (d) B2 successes ≥ guard + 16) | **PASS** | **PASS** |
| 11 | Carried profile: B1 engagement beyond newest four with stationary selectivity (conjunction of criterion 6 stationary form and criterion 9 B1 form) | **FAIL** | **FAIL** |
| 9 | First-switch B1 engagement beyond newest four preserved ((a) TAKEN ≥3/6 with ≥1 non-full firing; (b) B1 harm ≤ guard; (c) B1 harm < recent8) | **FAIL** | **PASS** |
| 6 | Stationary control selectivity not given back (abstentions ≤32/240; successes ≥ recent8 −6; harm ≤ recent8) | **FAIL** | **FAIL** |
| 5 | Release/productivity by k=32 (abstentions ≤36/144; successes ≥ recent8 −8; non-recent8 branch in ≤1 of 9 k=32 states; (d) abstained branch in 0 of 9 states) | **PASS** | **FAIL** |
| 4 | Return-A onset harm preserved (≤ guard AND ≤60% of recent8, pooled k=2,4) | **PASS** | **PASS** |
| 2 | Return-A recovery successes preserved (≥40% of frozen_A AND ≥ guard + 16, pooled k=2,4) | **PASS** | **PASS** |
| 3 | Pooled onset harm (≤ guard same-cohort; ≥5/6 cells ≤ recent8) | **PASS** | **PASS** |
| 7 | Full accounting in the saved detailed results | **PASS** | **PASS** |

### Criterion 12 (PRIMARY) — B2 protection at full engagement with carried profile (FAIL / FAIL)

Development: side (a), the B2 form, **PASSes in full** (see
criterion 1: minority TAKEN 5/6, harm 19 vs guard 28 and ceiling
39.6, successes 61). Side (c), release, **PASSes in full** (see
criterion 5). Side (b), the carried profile, **FAILs on both of
its sides** (see criterion 11: criterion 9 FAILs on engagement
alone, TAKEN 2/6; criterion 6 FAILs on abstention volume and
successes). The conjunction therefore FAILs, and its failure is
attributable entirely to the carried profile — the side this
experiment's changed element does not touch (branch selection
is identical to the decisive baseline's at every checkpoint;
the candidate's B1 and control lines are the widened method's
own lines on this cohort).
Additional: side (a) **PASSes in full** (minority TAKEN 5/6,
harm 46 vs guard 74 and ceiling 54.0, successes 50). Side (b)
**FAILs on its stationary side alone** (criterion 9 PASSes;
criterion 6 FAILs on abstention volume, 64/240 vs the ≤32
budget). Side (c) **FAILs on the records sub-condition alone**
(non-recent8 branch in 2/9 k=32 states; see criterion 5). The
conjunction FAILs on two independent sides.

**Grading cap: the condition is MET on both cohorts and does
not bind.** At every minority-fired B2 onset state — 5 of 5 on
EACH cohort — the candidate's first-frame choice DIFFERS from
the decisive baseline's (cross-check verified: candidate ==
inverted model, widened == minority-set model, at every such
state). The inverted model is therefore NOT a null result: the
pre-registered inverted-model null/equivalence failure mode did
not occur. What blocks a Demonstrated verdict is not the cap
and not the B2 side — it is the carried profile (both cohorts)
and checkpoint-32 release (additional).

### Criterion 1 — second-switch B2 protection preserved (PASS / PASS)

Development: **(a)** minority recovery TAKEN at **5 of 6**
pooled B2 onset states (3/3 at checkpoint 2, 2/3 at checkpoint
4; fractions 0.281–0.310, purity armed at every state) — the
sixth state (seed 462021 k=4, joint_count 0) was taken by a
partial abstention, not by a competing branch. **(b)** minority
TAKEN 0/6 at B1 and 0/6 at return-A. **(c)** B2 harm **19** vs
the guard's **28** AND vs the 0.60 × recent8 ceiling of
0.60 × 66 = **39.6** — both comparisons pass, where the decisive
baseline's own graded cycle failed both on its development
cohort (42 vs 30 / 36.6). **(d)** B2 successes **61** vs guard
+ 16 = 36. Against the decisive baseline method ON THIS COHORT
(widened method's B2 line 51 successes / 29 harm), the inverted
model is worth **+10 successes / −10 harm** pooled.
Additional: **(a)** minority TAKEN **5 of 6** (3/3 at checkpoint
2, 2/3 at checkpoint 4; fractions 0.284–0.328); the sixth state
(seed 463001 k=4, joint_count 0) fell through to recent8 and
scored 0/16, carrying 16 of the cohort's 46 B2 harm — a
non-engaged state, charged unchanged. **(b)** 0/6 and 0/6.
**(c)** harm **46** vs guard **74** and ceiling 0.60 × 90 =
**54.0**. **(d)** successes **50** vs guard + 16 = 22. Against
the decisive baseline on this cohort the pooled B2 line is
IDENTICAL (50/46 both methods): the per-state differences
cancel exactly (see the per-state table).

**Per-state B2 table — every B2 onset state, candidate vs the
decisive baseline (widened method), successes/harm per state
(16 episodes each). Minority-fired states are marked; at every
minority-fired state the cross-check holds (candidate ==
inverted model, widened == minority-set model) and the
first-frame choices differ.**

Development:

| Seed | k | Branch | Minority-fired | Candidate | Widened | Δ succ/harm |
| --- | --- | --- | --- | --- | --- | --- |
| 462003 | 2 | minority_archive | yes (frac 0.291, joint 2, purity 0.800, archive 328) | 11/5 | 12/4 | −1/+1 |
| 462003 | 4 | minority_archive | yes (frac 0.293, joint 1, purity 0.800, archive 330) | 11/5 | 10/6 | +1/−1 |
| 462021 | 2 | minority_archive | yes (frac 0.281, joint 2, purity 0.824, archive 328) | 11/5 | 11/5 | 0/0 (scores equal; first-frame choices differ) |
| 462021 | 4 | abstained (partial) | no (frac 0.284, joint 0) | 0/0 | 0/0 | 0/0 |
| 462039 | 2 | minority_archive | yes (frac 0.310, joint 2, purity 0.811, archive 328) | 14/2 | 9/7 | +5/−5 |
| 462039 | 4 | minority_archive | yes (frac 0.307, joint 1, purity 0.771, archive 330) | 14/2 | 9/7 | +5/−5 |

Additional:

| Seed | k | Branch | Minority-fired | Candidate | Widened | Δ succ/harm |
| --- | --- | --- | --- | --- | --- | --- |
| 463001 | 2 | minority_archive | yes (frac 0.328, joint 1, purity 0.906, archive 328) | 12/4 | 10/6 | +2/−2 |
| 463001 | 4 | recent8 | no (frac 0.326, joint 0) | 0/16 | 0/16 | 0/0 |
| 463017 | 2 | minority_archive | yes (frac 0.285, joint 1, purity 0.789, archive 328) | 9/7 | 11/5 | −2/+2 |
| 463017 | 4 | minority_archive | yes (frac 0.284, joint 2, purity 0.784, archive 330) | 9/7 | 11/5 | −2/+2 |
| 463041 | 2 | minority_archive | yes (frac 0.303, joint 2, purity 0.897, archive 328) | 10/6 | 9/7 | +1/−1 |
| 463041 | 4 | minority_archive | yes (frac 0.303, joint 1, purity 0.897, archive 330) | 10/6 | 9/7 | +1/−1 |

Stated in full on both sides: on development the inverted
model's differing choices convert to a pooled improvement over
the decisive baseline (+10/−10) and close the guard gap the
minority-set model could not (19 vs guard 28). On additional
the same differing choices are worth +2/−2, −2/+2, −2/+2, +1/−1,
+1/−1 per state — they **cancel exactly** in the pooled
aggregate, so on that cohort the inverted model demonstrated
per-state difference without pooled benefit. The pre-registered
attenuation-misranking failure mode is visible in the
463017 states (−2/+2 at both checkpoints) and did not dominate
either cohort's pooled figure.

### Criterion 11 — carried B1/stationary profile (FAIL / FAIL)

Development: BOTH sides FAIL — the stationary side FAILs
(criterion 6: abstentions 48/240 vs the ≤32 budget, successes
85 vs the ≥91 floor) and the B1 side FAILs (criterion 9:
TAKEN 2/6 vs the ≥3 floor). Additional: the B1 side PASSes in
full (criterion 9) and the stationary side FAILs on abstention
volume alone (criterion 6: 64/240). Every figure on this
criterion is a carried-class figure: branch selection is
identical to the decisive baseline's everywhere, the
candidate's control and B1 score lines are identical to the
widened method's on both cohorts, and no minority firing
occurred at any B1 or control state on either cohort — the
inverted model had no exposure here, and the failure is
charged to the carried profile exactly as recorded, not
excused by that fact.

### Criterion 9 — first-switch B1 engagement beyond the newest four preserved (FAIL development / PASS additional)

Development: **(a) ENGAGEMENT FAIL** — abstention TAKEN at
**2 of 6** pooled B1 onset states (1/3 at each checkpoint):
1 full firing (seed 462003 k=2, opposed 2, purity 0.865) and
1 retained partial firing (seed 462003 k=4, opposed 1,
preceding 2, newest4 3, purity 0.816) — the non-full
sub-condition is met by the partial, but the count is one
short of the floor. The four untaken states: two partial
states DISARMED by leg R alone at preceding_pair_opposed_count
0 (seed 462021 k=2, purity 0.889; seed 462039 k=4, purity
0.811) and two states with no trigger of any class (seed
462021 k=4, opposed 0, acting 1; seed 462039 k=2, opposed 0,
acting 1). **Zero widened B1 firings on this cohort** (the
widened class's B1 population on this draw was empty — the
pre-registered rarity of that class, ~0.08 raw / ~0.12 adjusted
expected firings per cohort from its own protocol, recurring).
**(b)** B1 harm **62** vs guard **72** — passes. **(c)** 62 <
recent8's **87** — passes. B1 successes, reported in full:
candidate **2** vs recent8 **9** vs the guard's **8**; the
candidate's B1 line is identical to the widened method's
(2/62).
Additional: **(a) PASS** — TAKEN at **5 of 6** (3/3 at
checkpoint 2, 2/3 at checkpoint 4): 2 full (seed 463001 k=2,
purity 0.818; seed 463001 k=4, purity 0.765), 1 retained
partial (seed 463017 k=2, purity 0.919, preceding 1), and
**2 widened firings** (seed 463041 k=2, opposed 1, preceding 0,
newest4 1, acting 3, purity 0.879; seed 463041 k=4, opposed 0,
preceding 1, newest4 1, acting 3, purity 0.816). The sole
untaken state (seed 463017 k=4, no trigger) carries all 16 of
the cohort's B1 harm through recent8. **(b)** B1 harm **16**
vs guard **65**. **(c)** 16 < recent8's **81**. B1 successes:
candidate **0** vs recent8 **15** vs guard **15**, stated in
full — the abstention productivity cost on this cohort is
complete at B1 onset, exactly as in the preceding cycles.

### Criterion 6 — stationary control selectivity not given back (FAIL / FAIL)

Development: **FAIL on two sub-conditions** — **(a)**
abstentions **48 of 240** vs the ≤32 budget; **(b)** successes
**85** vs recent8's **97**, required ≥ 91 — FAIL by 6 beyond
the allowance; **(c)** harm **107** vs recent8's **143** —
passes. All three abstained control states are at seed 462003:
k=2 **widened** (opposed 1, preceding 0, newest4 1, acting 3,
purity 0.865; recent8 scored 4/12 there), k=4 **partial**
(opposed 1, preceding 1, newest4 2, acting 3, purity 0.825;
recent8 3/13), k=8 **widened** (opposed 1, preceding 0,
newest4 1, acting 3, purity 0.806; recent8 2/14). The success
deficit is exactly the recent8 successes at those states
(4+3+2 = 9) plus per-state variation at the two
retained_archive control states. **The widened class's
pre-registered stationary-survival failure mode — priced in
its own protocol at ~0.8 raw / ~0.5 adjusted expected widened
control firings per cohort, and absent on BOTH of that cycle's
cohorts — materialized here: 2 widened stationary firings on
this cohort.** The candidate's control line is identical to
the decisive baseline method's (85/107/48), so this is the
carried classes' stationary record on a NEW draw, not an
inverted-model effect.
Additional: **FAIL on sub-condition (a) alone** — abstentions
**64 of 240** vs the ≤32 budget; **(b)** successes **71** vs
recent8's **76**, required ≥ 70 — passes by 1; **(c)** harm
**105** vs recent8's **164** — passes. Four abstained control
states: seed 463001 k=16 **widened** (newest4 1, acting 3,
purity 0.818), seed 463017 k=2 **partial** (preceding 1,
purity 0.919), seed 463041 k=8 **widened** (newest4 1, acting
3, purity 0.757), seed 463041 k=16 **partial** (preceding 1,
purity 0.750) — 2 widened + 2 retained partial firings, each
forfeiting its state's recent8 successes (1, 8, 0, 4). Again
identical to the widened method's control line (71/105/64).
**Net: criterion 6 is the only co-graded guard that FAILs on
BOTH cohorts in this cycle, and it fails on the abstention
classes' stationary volume — the widened class contributed 2
stationary firings per cohort, the retained-partial class 1–2,
and no full firing occurred on either control arm.**

### Criterion 5 — release and productivity by checkpoint 32 (PASS development / FAIL additional)

Development: all four sub-conditions pass — **(a)**
abstentions **0 of 144**; **(b)** successes **77 = recent8's
77** (required ≥ 69); **(c)** non-recent8 branch in **0 of 9**
switch-stage k=32 states; **(d)** abstained branch in **0 of
9**. No late minority routing occurred on this cohort at all;
the candidate is identical to the widened method at k=32
(77 successes).
Additional: **(a)** abstentions **0 of 144** and **(d)**
abstained branch **0 of 9** pass; **(b)** successes **58** vs
recent8's **64**, required ≥ 56 — passes; **(c) FAIL** —
non-recent8 branch in **2 of 9** states: return-A minority
routing at seed 463001 (purity 0.758, scoring 0/16 vs recent8
5/11 — the widened method took the same routing and also
scored 0/16: a carried routing, identical under both minority
models there) and B2 minority routing at seed 463017 (purity
0.714, scoring **9/7 through the inverted model vs 10/6 for
both the widened method and recent8** — the one k=32 state
where the inverted model itself is the worse scorer). The
cohort's entire −6 k=32 deficit against recent8 is those two
routings (−5 and −1 successes). **Stated in full: sub-condition
(b) passes, but the −6 deficit crosses the protocol's
Regression line (recent8 − 4 = 60; candidate 58) — see the
conclusion.**

### Criterion 4 — return-A onset harm preserved (PASS / PASS)

Development: harm **34** vs the guard's **39** and the ceiling
0.60 × 76 = **45.6** — passes both. Regular recovery TAKEN at
5 of 6 return-A onset states; the one non-engaged state (seed
462039 k=2) acted through recent8 and carries 15 of the 34
harm. Additional: harm **28** vs guard **37** and ceiling
0.60 × 79 = **47.4** — passes both; regular recovery TAKEN at
6 of 6. The candidate is identical to the widened method at
return-A onset on both cohorts (no minority or abstention
firing at return-A on either).

### Criterion 2 — return-A recovery successes preserved (PASS / PASS)

Development: candidate **62** successes vs frozen_A's 64 (40%
floor 25.6) and guard + 16 = 25 — passes. Additional:
candidate **68** vs frozen_A's 68 (floor 27.2) and guard + 16
= 27 — passes. Reported in full, not hidden: on development
BOTH cumulative (64 successes at 32 harm) and frozen_A (64 at
32) beat the candidate (62 at 34) on both axes; on additional
frozen_A exactly TIES the candidate (68 at 28) and cumulative
(62 at 34) sits below it. The cumulative/frozen_A both-axes
dominance that ran for eight consecutive graded cohort pairs
therefore does NOT extend to this pair — it holds on
development only and is a tie-or-below on additional.

### Criterion 3 — pooled onset harm not above guard (PASS / PASS)

Development: candidate pooled onset harm **115** vs the
guard's **139**, with all **6 of 6** pooled onset cells ≤
recent8 (B1 31/46 and 31/41, return-A 22/42 and 12/34, B2
12/38 and 7/28 against recent8). Additional: **90** vs the
guard's **176**, 6 of 6 cells ≤ recent8. Stated in full
alongside: the decisive baseline method's pooled onset harm is
ABOVE the candidate's on development (125) and EQUAL to it on
additional (90) — the inverted model's pooled onset effect is
exactly its B2 effect, −10 harm on development and 0 on
additional, with all other onset lines identical by
construction.

### Criterion 7 — full accounting (PASS / PASS)

The saved detailed results contain every field listed in
metrics_reported: per-seed TRAIN actor accounting counted once,
per-method successes / harmful actions / abstentions at every
checkpoint, the candidate's full decision record including the
complete minority record AND the minority-model record
(minority_model_archive_count == archive_events_count at 72/72
entries per cohort, minority_model_inverted true at 72/72),
the full abstention-gate record (support threshold null at
72/72 entries per cohort, abstention_disarmed_by_support false
everywhere, abstention_gate_armed recomputable everywhere with
0 mismatches), the preceding-pair record (threshold 1 at
72/72), the widened-class record (threshold 3 at 72/72,
newest4_opposed_count and widened_armed recomputable
everywhere with 0 mismatches, the records-only widened-rule
equal to the candidate's branch everywhere), branch selection
identical to the widened method at 72/72 entries per cohort,
the minority-model cross-check PASSing at every minority-fired
state (11 development / 13 additional applicable states),
checkpoint SHA256, and restore-replay identity true at every
checkpoint in both cohorts (72/72 entries per cohort,
script-verified in this grading stage). Learner
information-acquisition actions = 0, learner training actions
= 0, additional requested observations = 0, throughout.

## Learning evaluation

- Task successes at each checkpoint (candidate succ/harm/abst vs
  recent8 succ/harm), development: B1-0 (0/48/0 vs 0/48), B1-2
  (1/31/16 vs 2/46), B1-4 (1/31/16 vs 7/41), B1-8 (9/7/32 vs
  34/14), B1-16 (17/31/0 vs 19/29), B1-32 (25/23/0 vs 25/23);
  return_A-0 (0/48/0 vs 0/48), return_A-2 (26/22/0 vs 6/42),
  return_A-4 (36/12/0 vs 14/34), return_A-8 (19/13/16 vs
  27/21), return_A-16 (17/31/0 vs 22/26), return_A-32 (24/24/0
  vs 24/24); B2-0 (25/23/0 vs 1/47), B2-2 (36/12/0 vs 10/38),
  B2-4 (25/7/16 vs 20/28), B2-8 (20/28/0 vs 28/20), B2-16
  (36/12/0 vs 29/19), B2-32 (28/20/0 vs 28/20); control-0
  (19/29/0 vs 19/29), control-2 (10/22/16 vs 14/34), control-4
  (13/19/16 vs 19/29), control-8 (13/19/16 vs 15/33),
  control-16 (25/23/0 vs 25/23), control-32 (24/24/0 vs
  24/24). Additional: B1-0 (1/47/0 vs 1/47), B1-2 (0/0/48 vs
  2/46), B1-4 (0/16/32 vs 13/35), B1-8 (0/0/48 vs 23/25),
  B1-16 (16/32/0 vs 16/32), B1-32 (27/21/0 vs 27/21);
  return_A-0 (14/34/0 vs 2/46), return_A-2 (34/14/0 vs 0/48),
  return_A-4 (34/14/0 vs 17/31), return_A-8 (25/7/16 vs
  25/23), return_A-16 (28/20/0 vs 28/20), return_A-32 (21/27/0
  vs 26/22); B2-0 (1/47/0 vs 1/47), B2-2 (31/17/0 vs 3/45),
  B2-4 (19/29/0 vs 3/45), B2-8 (30/18/0 vs 31/17), B2-16
  (30/18/0 vs 21/27), B2-32 (10/38/0 vs 11/37); control-0
  (19/29/0 vs 19/29), control-2 (20/12/16 vs 20/28), control-4
  (13/35/0 vs 13/35), control-8 (14/18/16 vs 14/34), control-16
  (3/13/32 vs 8/40), control-32 (21/27/0 vs 21/27). Checkpoint
  0 is diagnostic only (candidate k=0 harm per switch stage
  48/48/23 development, 47/34/47 additional).
- Comparison with the preceding learner: the candidate differs
  from the decisive widened-window baseline method at 8 of 72
  checkpoints (development) and 10 of 72 (additional) — exactly
  the inverted minority model's footprint (minority-fired
  states and their downstream cells); branch selection differs
  at 0. Onset pooled successes / harm: candidate 125/115
  development and 118/90 additional, vs the widened method's
  115/125 and 118/90.
- Comparison with simple fixed baselines: recent8 and the guard
  are graded throughout above; cumulative and frozen_A at
  return-A are reported under criterion 2 in full.
- Evidence needed before adaptation / retention: unchanged from
  the carried family at the recovery branches; the minority
  branch's model is now fitted on the full archive under
  inversion rather than on the minority set only. Past
  knowledge (minority set, retained archive, concordance) is
  retained exactly as in the graded candidate — only the model
  fitted over it changed.
- Generalization: handoff level 2–3, simulator-bounded only. No
  level-6 or novel-representation claim: every element,
  including the inversion construction, is designer-supplied,
  and the inverted model exploits this simulator's
  exact-inversion structure directly (B is the precise
  progress/damage inversion of A). A PASS on criterion 1
  demonstrates that a protective model for the second switch
  fitted by inverting the retained archive can outperform the
  minority-set-only fit at full engagement — on these cohorts,
  in this simulator only, not general second-switch handling,
  not calibrated uncertainty, and not real-world safety.

## Safety and evidence costs

- Harmful TEST actions: reported per cell above and per
  criterion; pooled onset 115 (development) / 90 (additional)
  against recent8's 229 / 250 and the guard's 139 / 176 — and
  against the decisive widened-window baseline method's 125 /
  90, which the candidate is BELOW on development and EQUAL to
  on additional.
- Harmful TRAIN acquisition actions by the learner: **0** — the
  learner issues no training interventions; all TRAIN evidence
  comes from the shared external actor stream, whose actual
  harmful / productive / neutral outcomes, reported harm, and
  label flips are published per seed in the saved results
  (criterion 7). Per-cohort totals (all stages): development —
  1,440 actor actions, 531 actual harmful, 548 actual
  productive, 361 actual neutral, 54 label flips; additional —
  1,440 actor actions, 509 actual harmful, 575 actual
  productive, 356 actual neutral, 65 label flips.
- Failed-by-abstention: pooled onset 48 / 288 (development) and
  80 / 288 (additional); checkpoint-32 0 / 144 on both cohorts;
  stationary control **48 / 240 (development) and 64 / 240
  (additional)** — the stationary cost graded under criterion
  6: 2 widened + 1 partial firings (development, all at one
  seed) and 2 widened + 2 partial firings (additional), each
  identical to the decisive baseline method's. Abstentions are
  scored as failed tasks, never as successes.
- Additional requested observations: **0**.
- False confidence / unnecessary abstention: the unnecessary
  abstentions are the seven stationary firings graded under
  criterion 6. The B1 productivity cost is stated under
  criterion 9 in full: candidate B1 pooled successes 2
  (development) and 0 (additional) vs recent8's 9 / 15.
- Report integrity: frozen protocol committed before
  implementation (`c89916a`); cohorts inspected only through
  the registered evaluation; no parameter was re-tuned against
  the 462003-family / 463001-family cohorts after inspection.
  Provenance limitation: developer-selected simulation seeds
  in one engineered two-feature simulator family; not
  independent external proof.

## Scientific conclusion

**Failed — and a Regression under the checkpoint-32 clause.**
Per the protocol's own grading definitions: NOT Demonstrated,
because criteria 12, 11, and 6 FAIL on both cohorts and
criterion 5 FAILs on the additional cohort (the grading cap
does not bind — its differing-choice condition is met 5/5 on
EACH cohort). The **Partially demonstrated** clause does not
apply: it requires criterion 12 and criterion 7 to PASS on
both cohorts, and criterion 12 FAILs on both. The **Failed**
clause triggers on the additional cohort several times over:
criterion 12 FAILs there, criterion 11 FAILs there, criterion
6 FAILs there, and criterion 5 FAILs there. **Regression: the
checkpoint-32 clause triggers** — additional k=32 successes 58
fall below the recent8 − 4 line of 60 (the deficit is exactly
the two non-recent8 k=32 routings graded under criterion 5(c),
one of them scored through the inverted model itself). The
other Regression clauses do not trigger: pooled onset harm
115/90 is well below recent8's 229/250; the control-successes
clause requires BOTH cohorts and additional's deficit is −5
(development's is −12, which would trigger it alone if the
clause were per-cohort — stated, not hidden); the full unit
suite and the historical transfer benchmark pass (see
Verification).
What the experiment establishes, stated as prominently as the
failure: **the changed element worked on its own criterion.**
The inverted model is not a null — its first-frame choice
differs from the minority-set model's at every minority-fired
B2 onset state on both cohorts (5/5 each, cross-check
verified) — and criterion 1, the B2 criterion this cycle
selected, **PASSes on BOTH cohorts**: on development the
inverted fit closes the guard gap that defeated the
minority-set fit at full engagement (harm 19 vs guard 28 and
ceiling 39.6; +10 successes / −10 harm against the decisive
baseline method on the same cohort), and on additional it
holds the guard and ceiling (46 vs 74 / 54.0) with its
per-state differences cancelling exactly in the pooled
aggregate. The pre-registered attenuation-misranking risk is
real but bounded (one seed's two states at −2/+2 each on
additional; one state at −1/+1 on development). What failed
is everything the changed element does not touch: the carried
B1/stationary profile, which passed on the widened cycle's
cohorts, FAILs on both of these cohorts — on the stationary
arm on both (abstention volume 48/240 and 64/240 against a
≤32 budget, with the widened class's pre-registered stationary
survival materializing at 2 firings per cohort, and
development's successes also failing at −12), and on the B1
arm on development (TAKEN 2/6, zero widened B1 firings there)
— plus checkpoint-32 release on additional, where one of the
two stale routings is scored through the inverted model. A
conjunction PRIMARY grades the whole carried profile, so a
demonstrated B2 model improvement inside a failing carried
profile is a Failed experiment under this protocol, recorded
exactly that way. Generalization level 2–3, simulator-bounded
(see Learning evaluation).

**Next limitation (selected for the next cycle, Priority 1):**
stationary selectivity of the carried abstention classes —
criterion 6 is the only co-graded guard that FAILs on BOTH
cohorts in this cycle, on abstention volume on both (48/240
development, 64/240 additional, against the frozen ≤32/240
budget; development also FAILs successes at 85 vs recent8's
97, a −12 deficit against a −6 allowance), and the firings are
now mixed across classes: 2 widened + 1 retained-partial
stationary firings on development (all at seed 462003,
checkpoints 2/4/8, purity 0.806–0.865, acting_opposed_count 3
in every case) and 2 widened + 2 retained-partial on
additional (purity 0.750–0.919). The widened class's stationary
survival was pre-registered in its own protocol, did not occur
on its own cohorts, and has now occurred on both of these;
the retained-partial class's stationary firings recur across
cycles whenever leg R's preceding pair happens to be opposed.
Measurable: on NEW cohorts under a NEW protocol, whether an
evidence-derived condition on the abstention classes
themselves (their triggers, gates, or arming — the minority
model and the B2 profile of THIS cycle held fixed as the
carried candidate) can hold criterion 6's frozen margins
(abstentions ≤ 32/240, successes ≥ recent8 − 6, harm ≤
recent8) on BOTH cohorts while holding criterion 9's B1
engagement and harm profile, criterion 1's B2 protection as
demonstrated here, and checkpoint-32 release. Recorded but
not selected: the additional checkpoint-32 Regression is two
routings — one carried return-A minority routing identical
under both minority models (0/16 for both methods) and one B2
minority routing scored 1 success worse through the inverted
model (9/7 vs 10/6) — a release-side exposure of the minority
branch, now including its inverted model, which the selected
limitation's protocol must carry as a co-graded guard even
though it is not the selected target; development's B1
engagement shortfall is one state (TAKEN 2/6, with two partial
states disarmed by leg R at preceding 0 and zero widened B1
firings on that cohort — the widened class's registered
rarity recurring on the onset arm while its stationary arm
fired twice on the same cohort); the additional B2 pooled
cancellation (per-state inverted-model differences of +2/−2,
−2/+2, −2/+2, +1/−1, +1/−1 netting to exactly zero against
the decisive baseline) means the inverted model's B2 benefit
is demonstrated on one cohort's pooled figures and only
per-state on the other's; and cumulative/frozen_A return-A
dominance on both axes holds on development only this cycle
(additional is a frozen_A tie), so the eight-pair streak does
not extend and is not selected.

Keep the learner optional and unpromoted, default controller
unchanged, no merge, no AthenZ/Synveil integration, D1–D10/V2A/V2B
unchanged.
