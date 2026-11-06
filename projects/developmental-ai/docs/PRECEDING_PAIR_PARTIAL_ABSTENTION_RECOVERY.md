# Preceding pair partial abstention recovery — preceding-pair corroboration leg on partial abstention triggers

**5 November 2026 protocol frozen; 6 November 2026 implementation /
evaluation; graded 6 November 2026. Status: optional, simulated,
unpromoted. No default-controller promotion, no PR merge, no D1–D10
or V2A/V2B roadmap change, no AthenZ/Synveil integration.**

## Experiment identity

- **Name and purpose:** `preceding_pair_partial_abstention_recovery` —
  whether adding ONE new condition, the preceding-pair leg (leg R:
  opposition in the two events immediately preceding the newest pair,
  required ONLY for partial abstention triggers) to the graded
  partial-opposition candidate can distinguish a genuine switch onset
  from stationary partial opposition well enough to hold the frozen
  stationary margins while keeping first-switch (B1) engagement.
  The graded partial-opposition experiment left the trigger question
  answered in one direction (criterion 9 PASS/PASS; criterion 6
  FAIL/FAIL — five partial stationary firings at realized purity
  0.825–0.872, inside the B1 taken range 0.750–0.865, so neither the
  newest pair's opposition count nor leg P separates the
  populations). Build Order Priority 1 (Independent Learning),
  items 2 + 3 + 4; handoff §8 weak uncertainty calibration /
  excessive abstention. This protocol's PRIMARY criterion is
  criterion 10, the conjunction of the carried criterion 6
  stationary form and the carried criterion 9 B1 form (with at
  least one RETAINED partial-only firing); criteria 9, 6, 5
  (release by checkpoint 32, including sub-condition (d),
  abstained branch in 0 of 9 states), 1 (B2 protection), and 4
  (return-A harm) are its co-graded guards, reported second
  through sixth below.
- **Candidate:** `PrecedingPairPartialAbstentionRecoveryMemory`
  (`developmental_ai/preceding_pair_partial_abstention_recovery.py`) —
  IDENTICAL to the graded `PartialOppositionAbstentionRecoveryMemory`
  in acting model (recent8 exactly), extended signal (newest 2 vs
  50-event reference, opposed_count), retained archive
  (events[:N-26]), archive concordance, joint test
  (joint_count >= 1), recovery model, the full three-leg authority
  condition, the minority branch in full, the partial-or-full
  abstention trigger (opposed_count >= 1), and the purity-only
  abstention gate (leg P >= 0.70, support threshold null, acting
  records records-only). The SINGLE changed element is leg R on
  PARTIAL triggers only: `preceding_pair_opposed_count >= 1` over
  events[-4:-2], each event scored against the same
  extended-reference majorities as the acting-window records; full
  triggers are unchanged behind leg P alone. Minimum 52 events,
  else all-available fallback (never exercised in evaluation).
  Separate optional learner; the default controller and all
  existing learners are untouched; the graded partial-opposition
  candidate appears only as the decisive baseline.
- **Branch and commits:**
  `developmental-ai/preceding-pair-partial-abstention-recovery`.
  Protocol frozen at `657014a` (BEFORE implementation);
  implementation at `045c019`; evaluation at `f3491f2`. This
  grading report is committed on top of the evaluation commit.
- **Frozen protocol:**
  `benchmarks/preceding_pair_partial_abstention_recovery_protocol.json`
  (frozen 2026-11-05, before any implementation, unit test,
  harness, or score inspection for this experiment).
- **Cohorts:** development 442003/442021/442039 and additional
  443001/443017/443041 — NEW at freeze, disjoint from every earlier
  cohort. Both cohorts are now **INSPECTED** and must never be
  re-tuned against. Detailed results:
  `benchmarks/preceding_pair_partial_abstention_recovery_results.json`
  (development) and
  `benchmarks/preceding_pair_partial_abstention_recovery_additional_results.json`
  (additional).
- **Simulator:** `StochasticWorld` unchanged. Schedule per seed:
  A → B1 (inverted) → return-A → B2 (inverted), plus a stationary
  A→A control arm. Checkpoints 0/2/4/8/16/32 for every stage;
  checkpoint 0 is a reported diagnostic, NOT graded.

## Verification

- Unit tests: **PASS** — full suite `python -m unittest discover -s
  tests`: 1241 tests OK in the implementation and evaluation
  stages, and 1241 tests OK again in this grading stage (run
  this pass; the grading-stage changes are documentation only,
  no code changed). Focused candidate tests: 46/46 PASS in the
  implementation stage.
- Historical regressions: **PASS** — `python -m
  benchmarks.transfer_benchmark` (unchanged) exited 0 in the
  evaluation stage, and exited 0 again when re-run in this
  grading stage.
- Frozen cohorts: **PASS (ran exactly as registered)** — both
  cohorts were run with no change to any frozen parameter,
  threshold, seed, or checkpoint. Every checkpoint entry carries
  the candidate's full decision record (including all
  preceding-pair fields and the full abstention-gate record with
  support threshold null), a checkpoint SHA256, and
  restore-replay identity verified true at every checkpoint in
  both cohorts (script-verified again in this grading stage —
  72/72 entries per cohort; no criterion-7 field missing
  anywhere; support_threshold null everywhere;
  abstention_disarmed_by_support false everywhere;
  abstention_gate_armed recomputable from purity_armed, trigger
  kind, and preceding_pair_armed everywhere with 0 mismatches;
  the records-only preceding-pair-rule equals the candidate's
  taken branch everywhere).
- Linux validation: **UNVERIFIED** — no GitHub Actions run on the
  evaluation or grading commit was checked; no CI is claimed for
  `f3491f2` or for this grading commit.
- Windows validation: **UNVERIFIED** — same reason as above.

## Per-criterion grading (precommitted, graded individually, per cohort)

All figures below were script-computed from the saved detailed
results in this grading stage, not hand-copied (script and output
kept with the campaign records). Criterion 10, this experiment's
PRIMARY criterion, is reported first, and criteria 9, 6, 5, 1, and
4, its co-graded guards, next, as the protocol requires.

| # | Criterion | Development | Additional |
| --- | --- | --- | --- |
| 10 | PRIMARY stationary selectivity under partial-opposition trigger (conjunction: (a) stationary side = criterion 6 form; (b) B1 abstention TAKEN ≥3/6 with ≥1 RETAINED partial-only firing (preceding_pair_opposed_count ≥1); (c) B1 harm ≤ guard; (d) B1 harm < recent8) | **FAIL** | **FAIL** |
| 9 | First-switch B1 partial-opposition engagement preserved ((a) TAKEN ≥3/6 with ≥1 retained partial-only firing; (b) B1 harm ≤ guard; (c) B1 harm < recent8) | **FAIL** | **FAIL** |
| 6 | Stationary control selectivity not given back (abstentions ≤32/240; successes ≥ recent8 −6; harm ≤ recent8) | **PASS** | **FAIL** |
| 5 | Release/productivity by k=32 (abstentions ≤36/144; successes ≥ recent8 −8; non-recent8 branch in ≤1 of 9 k=32 states; (d) abstained branch in 0 of 9 states) | **FAIL** | **PASS** |
| 1 | Second-switch B2 protection preserved ((a) minority recovery TAKEN ≥3/6 pooled B2 onset states; (b) minority TAKEN ≤1/6 B1 and ≤1/6 return-A; (c) B2 harm ≤ guard AND ≤60% of recent8; (d) B2 successes ≥ guard + 16) | **FAIL** | **FAIL** |
| 4 | Return-A onset harm preserved (≤ guard AND ≤60% of recent8, pooled k=2,4) | **PASS** | **FAIL** |
| 2 | Return-A recovery successes preserved (≥40% of frozen_A AND ≥ guard + 16, pooled k=2,4) | **PASS** | **PASS** |
| 3 | Pooled onset harm (≤ guard same-cohort; ≥5/6 cells ≤ recent8) | **PASS** | **PASS** |
| 7 | Full accounting in the saved detailed results | **PASS** | **PASS** |

### Criterion 10 (PRIMARY) — stationary selectivity under a partial-opposition trigger (FAIL / FAIL)

Development: the **stationary side (a) PASSes in full** —
abstentions **0 of 240**, successes **110 = recent8's 110**, harm
**130 = recent8's 130** (see criterion 6). The **B1 side FAILs on
sub-condition (b) alone**: abstention TAKEN at **1 of 6** pooled
B1 onset states (required ≥ 3), and **0 retained partial-only
firings** (required ≥ 1) — every partial B1 state on this cohort
realized preceding_pair_opposed_count 0. Sub-conditions (c) and
(d) PASS: B1 harm **78** vs the guard's **78** (passes at
equality) and 78 < recent8's **92**. Additional: **both sides
FAIL** — the stationary side fails sub-condition (a2) by one
success (102 vs recent8's 109, required ≥ 103; see criterion 6),
and the B1 side again takes **1 of 6** with **0 retained
partials**, (c) 78 ≤ guard 78 and (d) 78 < recent8 94 passing.
The conjunction therefore FAILs on both cohorts, and the failure
is attributable exactly: on development to the B1 side only, on
additional to both sides, with the additional stationary failure
caused by a carried FULL firing the leg never claimed to gate
(criterion 6).

### Criterion 9 — first-switch B1 partial-opposition engagement preserved (FAIL / FAIL)

Development: **(a) ENGAGEMENT FAIL** — TAKEN at **1 of 6** pooled
B1 onset states (0/3 at checkpoint 2, 1/3 at checkpoint 4), the
sole taken state a FULL firing (seed 442003 k=4, opposed_count 2,
purity 0.800). The cohort's only partial B1 state (seed 442021
k=2, purity 0.870, preceding_pair_opposed_count **0**) was
DISARMED by leg R alone — the pre-registered checkpoint-2
sacrifice, since at k=2 the preceding pair is pre-switch. The
remaining four B1 states had opposed_count **0** (seeds 442003
k=2, 442021 k=4, and 442039 at both k=2 and k=4): signal
absence no condition on this signal can reach.
**(b)** B1 harm **78** vs the guard's **78** — passes at
equality. **(c)** 78 < recent8's **92** — passes. B1 successes,
reported in full: candidate **2** vs recent8 **4** vs the guard's
**2**. Against the records-only derivations at the same states:
the partial-purity-rule (the graded partial candidate's exact
rule, leg R removed) took **2 of 6** (the full state plus the
leg-R-disarmed k=2 partial) — so on this cohort even the
un-corroborated widened trigger would have FAILED the ≥3 floor;
leg R removed 1 of those 2. The purity-only-rule took 1 (the
full state), the partial-ungated-rule 2, the release-rule 0, the
higher-corroboration-rule 0.
Additional: **(a) FAIL** — TAKEN at **1 of 6** (0/3 at k=2, 1/3
at k=4), again a sole FULL firing (seed 443017 k=4, purity
0.865, preceding_pair_opposed_count 1 — a full trigger, for
which leg R is never consulted). THREE partial B1 states were
DISARMED by leg R alone, every one at preceding_pair_opposed_count
**0**: seed 443017 k=2 (purity 0.889), seed 443041 k=2 (0.895),
and seed 443001 k=4 (0.849) — the third is the pre-registered
checkpoint-4 case, and on this cohort's draws the checkpoint-4
rescue did not occur (the only partial state at k=4 across both
cohorts realized preceding 0). One further state had
opposed_count 0 (seed 443001 k=2). **(b)** B1 harm **78** vs
guard **78** — passes at equality. **(c)** 78 < recent8's **94**
— passes. B1 successes: candidate **2** vs recent8 **2** vs the
guard's **2**. Derivations: the partial-purity-rule took **4 of
6** (the one full state plus all three partials — on this
cohort the widened trigger alone WOULD have passed the
engagement count, and leg R removed 3 of its 4 firings,
including every partial-class firing);
purity-only-rule 1, partial-ungated-rule 4, release-rule 1,
higher-corroboration-rule 0. Recovery and minority firing at B1:
0 of 6 on both cohorts, as in every preceding cycle. **The
leg's B1 cost is exact: across both cohorts it disarmed 4 of 4
partial B1 states that carried leg P, retained 0, and pooled
engagement fell from the partial-purity-rule's 2/6 and 4/6 to
1/6 on both — below the frozen floor on both, with zero
retained partials on either.**

### Criterion 6 — stationary control selectivity not given back (PASS development / FAIL additional)

Development: **PASS in full, as a leg-retention pass** —
**(a)** abstentions **0 of 240**; **(b)** successes **110 =
recent8's 110**; **(c)** harm **130 = recent8's 130**. The
records-only partial-purity-rule took 2 stationary states on
this cohort (the partial baseline method's control line is
102/106/32); leg R DISARMED both, each a partial state at
preceding_pair_opposed_count 0 (seed 442003 k=2, purity 0.805;
seed 442003 k=32, purity 0.816), and the candidate is
downstream-identical to recent8 on the entire control arm.
Additional: **(a)** abstentions **16 of 240** — passes.
**(b)** successes **102** vs recent8's **109**, required ≥ 103 —
**FAIL by 1** (raw deficit 7). **(c)** harm **122** vs recent8's
**131** — passes. Leg R again removed every partial stationary
firing: the partial-purity-rule took 4 states (partial baseline
method control line 86/90/64); leg R disarmed the three partial
states, all at preceding_pair_opposed_count 0 (seed 443041 k=2,
purity 0.895; k=16, 0.900; k=32, 0.781). The entire remaining
deficit is ONE carried **full** stationary firing the leg does
not gate by design (seed 443017 k=2, opposed_count 2, purity
0.889, abstained 16/16, 0/0 vs recent8's 7/9 at that state) —
the same state the unwidened purity-only rule also took (branch
diffs vs the purity-only-rule: 0 of 15 graded control states on
both cohorts). **Net: the preceding-pair leg repaired the
partial-opposition stationary failure completely on both
cohorts (partial stationary abstentions 32/64 episodes under the
decisive baseline method → 0 on both); what remains is the
carried full-pair stationary exposure, which on additional
costs exactly one success more than the frozen −6 margin
allows.**

### Criterion 5 — release and productivity by checkpoint 32 (FAIL development / PASS additional)

Development: **(a)** abstentions **0 of 144** — passes. **(b)**
successes **60** vs recent8's **68**, required ≥ 60 — passes at
the line exactly. **(c)** non-recent8 branch in **2 of 9**
switch-stage k=32 states against the 1-of-9 allowance — FAIL:
seed 442021 B1 retained_archive (purity 0.711, full trigger
present) and seed 442021 return-A minority_archive (purity
0.867) — the latter scored 0/16 against recent8's 8/8 and is the
cohort's entire −8 k=32 success deficit (see the Regression
clause below). **(d)** abstained branch in **0 of 9** — passes:
no late abstention on either cohort; the one late partial
trigger (seed 442039 return-A k=32, purity 0.645,
preceding_pair_opposed_count 1) was released by leg P alone.
Additional: all four pass — abstentions 0/144, successes **57**
vs recent8's **65** (required ≥ 57, at the line exactly),
non-recent8 **1 of 9** (seed 443001 return-A minority_archive,
purity 0.731, scoring 0/16 vs recent8's 8/8 — this cohort's
entire −8 deficit), abstained **0 of 9** (the one late partial
trigger, seed 443041 return-A k=32, was blocked by BOTH legs:
purity 0.692 disarmed, preceding_pair_opposed_count 0). The
candidate is identical to the partial baseline method at k=32
on both cohorts: the records failures and the −8 deficits are
the carried minority branch's late persistence, not a
preceding-pair effect — recorded, and charged as recorded.

### Criterion 1 — second-switch B2 protection preserved (FAIL / FAIL)

Development: **(a)** minority recovery TAKEN at **4 of 6** pooled
B2 onset states (1/3 at k=2, 3/3 at k=4; fractions 0.266–0.318,
purity armed at every taken state) — passes. **(b)** minority
TAKEN 0/6 at B1 and 0/6 at return-A — passes. **(c)** B2 harm
**58** vs the guard's **94** — passes — but the 0.60 × recent8
ceiling is 0.60 × 94 = **56.4**, so the ceiling FAILs by 1.6.
**(d)** B2 successes **38** vs guard + 16 = 18 — passes.
Additional: **(a)** minority TAKEN at exactly **3 of 6** (2/3 at
k=2, 1/3 at k=4; fractions 0.294–0.302) — passes at the floor.
**(b)** 0/6 and 0/6 — passes. **(c)** B2 harm **65** vs the
guard's **80** passes, but the ceiling is 0.60 × 86 = **51.6** —
FAIL by 13.4; the harm is concentrated at the three non-engaged
states, which acted through recent8 at 16 harm each (seeds
443001 k=4, 443041 k=2 and k=4, all joint-silent at
opposed_count 0). **(d)** successes **31** vs 16 — passes. No
abstention fired at B2 onset on either cohort and leg R disarmed
none there, so both failures are the carried B2 profile on new
cohorts — the minority branch engaging at/above its floor while
its non-engaged states run at recent8's harm level — charged
unchanged, as the protocol requires.

### Criterion 4 — return-A onset harm preserved (PASS development / FAIL additional)

Development: candidate return-A pooled onset harm **34** vs the
guard's **57** and the 0.60 × recent8 ceiling of 43.8 (recent8
73) — passes both comparisons; regular recovery TAKEN at 4/6
return-A onset states. Additional: candidate **45** vs the
guard's **71** — sub-condition (a) passes — but the ceiling is
0.60 × 71 = **42.6**, so sub-condition (b) FAILs by 2.4. Regular
recovery TAKEN at 5/6 states. The candidate is identical at
return-A onset to the extended, minority, purity-only, and
partial baseline methods on additional (all 51 successes / 45
harm): inherited from the carried profile, not produced by the
preceding-pair leg, and charged unchanged.

### Criterion 2 — return-A recovery successes preserved (PASS / PASS)

Development: candidate **62** successes vs frozen_A's 62 (40%
floor 24.8) and guard + 16 = 39 — passes. Additional: candidate
**51** vs frozen_A's 62 (floor 24.8) and guard + 16 = 41 —
passes. Reported in full, not hidden: on development the
candidate is exactly tied by frozen_A and by every carried
gate-generation baseline method (all 62 successes at 34 harm),
while cumulative scores 68 at 28 harm and beats it on BOTH axes;
on additional, frozen_A (62 at 34) and cumulative (60 at 36)
both beat the candidate's 51 at 45 on BOTH axes. Cumulative's
return-A dominance on both axes on both cohorts now extends to
**seven** consecutive graded cohort pairs.

### Criterion 3 — pooled onset harm not above guard (PASS / PASS)

Development: candidate pooled onset harm **170** vs the guard's
**229**, with all **6 of 6** pooled onset cells ≤ recent8 (B1
46/46 and 32/46, return-A 19/43 and 15/30, B2 37/47 and 21/47
against recent8). Additional: **188** vs the guard's **229**,
6 of 6 cells ≤ recent8. Stated in full alongside: the decisive
partial baseline method's pooled onset harm is BELOW the
candidate's on both cohorts (154 development, 141 additional)
— leg R's B1 disarmings returned onset harm the widened trigger
had removed, and on additional that give-back (188 vs 141) is
the largest single harm movement in this experiment; the pooled
figure stays under the guard only because the carried recovery
profile dominates it.

### Criterion 7 — full accounting (PASS / PASS)

The saved detailed results contain every field listed in
metrics_reported: per-seed TRAIN actor accounting counted once,
per-method successes / harmful actions / abstentions at every
checkpoint, the candidate's full decision record including the
complete preceding-pair record (preceding_pair_threshold 1 at
72/72 entries per cohort) and the full abstention-gate record
(support threshold null at 72/72 entries per cohort,
abstention_disarmed_by_support false everywhere,
abstention_gate_armed recomputable from purity_armed, trigger
kind, and preceding_pair_armed everywhere with 0 mismatches,
the records-only preceding-pair-rule equal to the candidate's
branch everywhere), checkpoint SHA256, and restore-replay
identity true at every checkpoint in both cohorts (72/72
entries per cohort, script-verified in this grading stage).
Learner information-acquisition actions = 0, learner training
actions = 0, additional requested observations = 0, throughout.

## Learning evaluation

- Task successes at each checkpoint (candidate succ/harm/abst vs
  recent8 succ/harm), development: B1-2 (2/46/0 vs 2/46), B1-4
  (0/32/16 vs 2/46), B1-8 (0/16/32 vs 18/30), B1-16 (21/27/0 vs
  21/27), B1-32 (26/22/0 vs 26/22); return_A-2 (29/19/0 vs 5/43),
  return_A-4 (33/15/0 vs 18/30), return_A-8 (28/20/0 vs 24/24),
  return_A-16 (30/18/0 vs 21/27), return_A-32 (9/39/0 vs 17/31);
  B2-2 (11/37/0 vs 1/47), B2-4 (27/21/0 vs 1/47), B2-8 (21/27/0
  vs 19/29), B2-16 (27/21/0 vs 9/39), B2-32 (25/23/0 vs 25/23);
  control-2 (16/32/0 vs 16/32), control-4 (20/28/0 vs 20/28),
  control-8 (28/20/0 vs 28/20), control-16 (21/27/0 vs 21/27),
  control-32 (25/23/0 vs 25/23). Additional: B1-2 (1/47/0 vs
  1/47), B1-4 (1/31/16 vs 1/47), B1-8 (0/0/48 vs 16/32), B1-16
  (12/20/16 vs 18/30), B1-32 (16/32/0 vs 16/32); return_A-2
  (20/28/0 vs 7/41), return_A-4 (31/17/0 vs 18/30), return_A-8
  (31/17/0 vs 28/20), return_A-16 (27/21/0 vs 26/22),
  return_A-32 (14/34/0 vs 22/26); B2-2 (21/27/0 vs 0/48), B2-4
  (10/38/0 vs 10/38), B2-8 (29/19/0 vs 15/33), B2-16 (31/17/0 vs
  14/34), B2-32 (27/21/0 vs 27/21); control-2 (18/14/16 vs
  25/23), control-4 (20/28/0 vs 20/28), control-8 (25/23/0 vs
  25/23), control-16 (17/31/0 vs 17/31), control-32 (22/26/0 vs
  22/26). Checkpoint 0 is diagnostic only (candidate k=0 harm
  per switch stage 47/29/38 development, 48/47/48 additional).
- Comparison with the preceding learner: the candidate differs
  from the graded partial-opposition baseline method at 4 of 72
  checkpoints (development) and 6 of 72 (additional) — exactly
  leg R's footprint: the disarmed B1 partials, the disarmed
  stationary partials, and their downstream cells. Onset pooled
  successes / harm: candidate 102/170 development and 84/188
  additional, vs the partial method's 102/154 and 83/141 (the
  leg cost pooled onset harm on both cohorts while buying the
  stationary repair graded under criterion 6).
- Comparison with simple fixed baselines: recent8 and the guard
  are graded throughout above; cumulative and frozen_A dominate
  or tie the candidate at return-A (see criterion 2).
- Evidence needed before adaptation / retention: unchanged from
  the carried family — no branch of this candidate engages at
  B1 beyond the single full abstention per cohort; past
  knowledge (minority and retained recovery) is retained
  exactly as in the graded candidate.
- Generalization: handoff level 2–3, simulator-bounded only. No
  level-6 or novel-representation claim: every element,
  including the preceding-pair leg and its threshold, is
  designer-supplied. A PASS on criterion 10 would have
  demonstrated preceding-pair-corroborated partial abstention
  protecting the first switch in this simulator; the FAIL
  demonstrates the narrower negative result stated in the
  conclusion — not general first-contact handling, not
  calibrated uncertainty, and not real-world safety.

## Safety and evidence costs

- Harmful TEST actions: reported per cell above and per
  criterion; pooled onset 170 (development) / 188 (additional)
  against recent8's 259 / 251 and the guard's 229 / 229 — and
  against the decisive partial baseline method's 154 / 141,
  which the candidate EXCEEDS on both cohorts (leg R's onset
  give-back, stated in full).
- Harmful TRAIN acquisition actions by the learner: **0** — the
  learner issues no training interventions; all TRAIN evidence
  comes from the shared external actor stream, whose actual
  harmful / productive / neutral outcomes, reported harm, and
  label flips are published per seed in the saved results
  (criterion 7).
- Failed-by-abstention: pooled onset 16 / 288 on both cohorts;
  checkpoint-32 0 / 144 on both cohorts; stationary control
  **0 / 240 (development) and 16 / 240 (additional)** — the
  stationary cost is now the single carried full firing, not
  partial firings. Abstentions are scored as failed tasks,
  never as successes.
- Additional requested observations: **0**.
- False confidence / unnecessary abstention: the unnecessary
  abstention is the additional control full firing graded
  under criterion 6 (one 16-episode refusal at a state where
  recent8 scored 7 successes). The symmetric B1 cost is stated
  under criterion 9: 4 of 4 leg-P-carrying partial B1 states
  across both cohorts were refused corroboration and acted
  through recent8 at full onset harm — candidate B1 pooled
  onset harm exceeds the decisive partial baseline method's by
  16 (development: 78 vs 62) and by 47 (additional: 78 vs 31).
- Report integrity: frozen protocol committed before
  implementation (`657014a`); cohorts inspected only through
  the registered evaluation; no parameter was re-tuned against
  the 442003-family / 443001-family cohorts after inspection.
  Provenance limitation: developer-selected simulation seeds
  in one engineered two-feature simulator family; not
  independent external proof.

## Scientific conclusion

**Failed — and a Regression on the checkpoint-32 clause.** Per
the protocol's own grading definitions: NOT Demonstrated
(criteria 10, 9, 6, 5, 1, and 4 FAIL). The **Failed** clause is
triggered on the additional cohort several times over —
criterion 10 FAILs there, criterion 9 FAILs there, criterion 6
FAILs there, and criteria 1 and 4 FAIL there — any one is
sufficient under the clause; criteria 10, 9, and 1 also FAIL on
development. The Partially-demonstrated clause requires
criterion 10 AND criterion 7 to PASS on both cohorts; criterion
10 FAILs on both, so it cannot govern. **Regression:** the
protocol's Regression clause is triggered by checkpoint-32
successes — candidate 60 vs the recent8 − 4 line of 64
(development) and 57 vs 61 (additional), below the line on
BOTH cohorts, each deficit in full a single stale minority
routing at return-A k=32 scoring 0/16 against recent8's 8/8
(seeds 442021 / 443001; the candidate is identical to the
partial baseline method at k=32 on both cohorts, so the
deficit is the carried minority branch's late persistence, not
a preceding-pair effect — charged as recorded). The other
Regression clauses do not trigger (pooled onset harm 170/188
well below recent8's 259/251; control successes 110 vs 110 and
102 vs 109 — the more-than-6-on-both clause requires both
cohorts and development is level; full unit suite and
historical transfer benchmark pass — see Verification). What
the experiment establishes, stated as prominently as the
failure: the preceding-pair leg does exactly the stationary
half of its hypothesis — it removed EVERY partial stationary
firing on both cohorts (decisive-baseline control abstentions
32/64 episodes → candidate 0/16, the additional remainder a
carried full firing), restoring development's control arm to
exact recent8 parity — and it does so at a B1 price the pooled
arithmetic did not predict at this size: ZERO retained
partial-only firings on either cohort, because every partial
B1 state on these cohorts realized preceding_pair_opposed_count
0, including the sole checkpoint-4 partial (seed 443001 k=4),
whose preceding pair the design arithmetic expected to retain
at 0.89–0.97. Four-event corroboration is therefore answered
in the same shape as the newest pair alone was: a partial
state whose corroborating window is also split carries too
little onset-specific information in this simulator to be
both retained at B1 and refused on stationary arms at the
frozen floors — on these cohorts the corroborated-partial
population was empty in every graded arm. Generalization
level 2–3, simulator-bounded (see Learning evaluation).

**Next limitation (selected for the next cycle, Priority 1):**
first-switch (B1) onset engagement beyond the newest four
events — B1 protection has now failed from both directions on
the newest-window signal: the un-corroborated partial trigger
engages but cannot hold stationary selectivity (preceding
cycle), and four-event corroboration holds the stationary
partial arm but engages nothing (taken 1/6 on both cohorts,
retained partials 0/6 on both, and on development even the
un-corroborated rule took only 2/6 because opposed_count was 0
at half the B1 states). Measurable: on NEW cohorts under a NEW
protocol, whether an onset signal accumulated over a wider
evidence window than the newest four events — one that can be
populated when the newest pair and its predecessor are jointly
silent or split — can reach criterion 9's engagement floor
(≥3/6 taken with a partial-class firing) and its harm profile
while holding the stationary profile this cycle demonstrated
on development (exact recent8 parity on the control arm) and
checkpoint-32 abstention release. Recorded but not selected:
criterion 6's additional failure is a single carried FULL
stationary firing the leg never claimed to gate (deficit −7
against the −6 margin); the criterion 5 development failure
and the checkpoint-32 Regression are one stale minority
routing per cohort at return-A k=32, identical to the decisive
baseline method there; criterion 1's B2 ceiling failures are
the carried B2 profile at its non-engaged states; criterion
4's additional failure is shared with the carried baselines at
return-A onset; and cumulative's return-A dominance on both
axes on both cohorts now extends to seven consecutive graded
cohort pairs.

Keep the learner optional and unpromoted, default controller
unchanged, no merge, no AthenZ/Synveil integration, D1–D10/V2A/V2B
unchanged.
