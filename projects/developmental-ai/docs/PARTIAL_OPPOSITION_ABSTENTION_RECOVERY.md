# Partial opposition abstention recovery — abstention trigger widened to partial opposition

**5 November 2026 protocol frozen / implementation / evaluation; graded
5 November 2026. Status: optional, simulated, unpromoted. No
default-controller promotion, no PR merge, no D1–D10 or V2A/V2B roadmap
change, no AthenZ/Synveil integration.**

## Experiment identity

- **Name and purpose:** `partial_opposition_abstention_recovery` — whether
  widening the abstention trigger from full opposition
  (`opposed_count == 2` on the newest pair) to partial opposition
  (`opposed_count >= 1`) can restore first-switch (B1) onset protection,
  after the graded abstention-purity-only experiment showed the gate's
  composition no longer binds B1 anywhere (leg P blocked zero B1 firings;
  every triggered state was taken, 4/4 across cohorts) and the binding
  constraint had moved upstream to the trigger itself, which fired at
  only 4 of 12 B1 onset states across the purity-only cohorts. Build
  Order Priority 1 (Independent Learning), items 2 + 3 + 4; handoff §8
  weak uncertainty calibration / excessive abstention and slow or
  incorrect recovery of old knowledge. This protocol's PRIMARY criterion
  is criterion 9, first-switch B1 partial-opposition engagement;
  criteria 6 (stationary selectivity), 5 (release by checkpoint 32,
  including sub-condition (d), abstained branch in 0 of 9 states), 1
  (B2 protection), and 4 (return-A harm) are its co-graded guards,
  reported second, third, fourth, and fifth below.
- **Candidate:** `PartialOppositionAbstentionRecoveryMemory`
  (`developmental_ai/partial_opposition_abstention_recovery.py`) —
  IDENTICAL to the graded `AbstentionPurityOnlyRecoveryMemory` in acting
  model (recent8 exactly), extended signal (newest 2 vs 50-event
  reference, opposed_count), retained archive (events[:N-26]), archive
  concordance, joint test (joint_count >= 1), recovery model, the full
  three-leg authority condition, the minority branch in full, and the
  purity-only abstention gate (leg P >= 0.70 sole leg, support threshold
  null, acting records records-only). The SINGLE changed element is the
  abstention trigger: `opposed_count >= 1` (partial or full) in place of
  `== 2`, with `abstention_trigger_kind` (full / partial / none) added to
  the decision record. Minimum 52 events, else all-available fallback
  (never exercised in evaluation). Separate optional learner; the default
  controller and all existing learners are untouched; the graded
  purity-only candidate appears only as the decisive baseline.
- **Branch and commits:** `developmental-ai/partial-opposition-abstention-recovery`.
  Protocol frozen at `bec31ce` (BEFORE implementation); implementation
  at `5031fee`; evaluation at `4efce8a`. This grading report is committed
  on top of the evaluation commit.
- **Frozen protocol:** `benchmarks/partial_opposition_abstention_recovery_protocol.json`
  (frozen 2026-11-05, before any implementation, unit test, harness, or
  score inspection for this experiment).
- **Cohorts:** development 432003/432021/432039 and additional
  433001/433017/433041 — NEW at freeze, disjoint from every earlier
  cohort. Both cohorts are now **INSPECTED** and must never be re-tuned
  against. Detailed results:
  `benchmarks/partial_opposition_abstention_recovery_results.json`
  (development) and
  `benchmarks/partial_opposition_abstention_recovery_additional_results.json`
  (additional).
- **Simulator:** `StochasticWorld` unchanged. Schedule per seed: A →
  B1 (inverted) → return-A → B2 (inverted), plus a stationary A→A
  control arm. Checkpoints 0/2/4/8/16/32 for every stage; checkpoint 0
  is a reported diagnostic, NOT graded.

## Verification

- Unit tests: **PASS** — full suite `python -m unittest discover -s
  tests`: 1195 tests OK in the implementation and evaluation stages,
  and 1195 tests OK again in this grading stage (run this pass; the
  grading-stage changes are documentation only, no code changed).
  Focused candidate tests: 42/42 PASS in the implementation stage.
- Historical regressions: **PASS** — `python -m
  benchmarks.transfer_benchmark` (unchanged) exited 0 in the evaluation
  stage, and exited 0 again when re-run in this grading stage.
- Frozen cohorts: **PASS (ran exactly as registered)** — both cohorts
  were run with no change to any frozen parameter, threshold, seed, or
  checkpoint. Every checkpoint entry carries the candidate's full
  decision record (including `abstention_trigger_kind` at every
  checkpoint and the full abstention-gate record with support threshold
  null), a checkpoint SHA256, and restore-replay identity verified true
  at every checkpoint in both cohorts (script-verified again in this
  grading stage — 72/72 entries per cohort; no criterion-7 field missing
  anywhere; support_threshold null everywhere; abstention_gate_armed ==
  purity_armed everywhere).
- Linux validation: **UNVERIFIED** — no GitHub Actions run on the
  evaluation or grading commit was checked; no CI is claimed for
  `4efce8a` or for this grading commit.
- Windows validation: **UNVERIFIED** — same reason as above.

## Per-criterion grading (precommitted, graded individually, per cohort)

All figures below were script-computed from the saved detailed results
in this grading stage, not hand-copied (script and output kept with the
campaign records). Criterion 9, this experiment's PRIMARY criterion, is
reported first, and criteria 6, 5, 1, and 4, its co-graded guards, next,
as the protocol requires.

| # | Criterion | Development | Additional |
| --- | --- | --- | --- |
| 9 | PRIMARY first-switch B1 partial-opposition engagement ((a) abstention TAKEN ≥3/6 pooled B1 onset states with ≥1 partial-only firing; (b) B1 harm ≤ guard; (c) B1 harm < recent8) | **PASS** | **PASS** |
| 6 | Stationary control selectivity not given back (abstentions ≤32/240; successes ≥ recent8 −6; harm ≤ recent8) | **FAIL** | **FAIL** |
| 5 | Release/productivity by k=32 (abstentions ≤36/144; successes ≥ recent8 −8; non-recent8 branch in ≤1 of 9 k=32 states; (d) abstained branch in 0 of 9 states) | **FAIL** | **PASS** |
| 1 | Second-switch B2 protection preserved ((a) minority recovery TAKEN ≥3/6 pooled B2 onset states; (b) minority TAKEN ≤1/6 B1 and ≤1/6 return-A; (c) B2 harm ≤ guard AND ≤60% of recent8; (d) B2 successes ≥ guard + 16) | **PASS** | **PASS** |
| 4 | Return-A onset harm preserved (≤ guard AND ≤60% of recent8, pooled k=2,4) | **PASS** | **FAIL** |
| 2 | Return-A recovery successes preserved (≥40% of frozen_A AND ≥ guard + 16, pooled k=2,4) | **PASS** | **PASS** |
| 3 | Pooled onset harm (≤ guard same-cohort; ≥5/6 cells ≤ recent8) | **PASS** | **PASS** |
| 7 | Full accounting in the saved detailed results | **PASS** | **PASS** |

### Criterion 9 (PRIMARY) — first-switch B1 partial-opposition engagement (PASS / PASS)

Development: **(a) ENGAGEMENT** — the abstention branch was TAKEN at
**6 of 6** pooled B1 onset states (3/3 at checkpoint 2, 3/3 at
checkpoint 4; required ≥ 3), of which **4 are partial-only firings**
(opposed_count == 1 — states the graded purity-only candidate's trigger
could not have taken) and 2 full. Taken states, with realized purity
(all purity-armed): seed 432003 k=2 partial, purity 0.861; seed 432003
k=4 partial, 0.833; seed 432021 k=2 partial, 0.865; seed 432021 k=4
full, 0.861; seed 432039 k=2 full, 0.780; seed 432039 k=4 partial,
0.811. **(b) HARM vs GUARD** — candidate B1 pooled onset harm **0** vs
the guard's **62** — passes. **(c) HARM vs RECENT8** — 0 < recent8's
**90** — passes. B1 successes, reported in full as the protocol
requires: candidate **0** vs recent8 **6** vs the guard's **2** — the
candidate abstained at all 96 B1 onset episode-checkpoints on this
cohort, so the protection is complete and its productivity at B1 onset
is zero; that cost is stated, not hidden. Against the records-only
derivations at the same states: the purity-only-rule (trigger == 2 +
leg P, the graded candidate's exact rule) took only the 2 full states,
so the widening added **4** B1 firings on this cohort; the
partial-purity-rule (this candidate's own rule) and the
partial-ungated-rule each also took 6, so leg P blocked no B1 firing
here; the release-rule took 1 and the higher-corroboration-rule 0.
Additional: **(a)** TAKEN at **5 of 6** pooled B1 onset states (2/3 at
k=2, 3/3 at k=4), of which **2 partial-only** and 3 full — passes. The
sole untaken state is seed 433001 k=2 at opposed_count **0** (kind
none, purity 0.818, armed) — signal absence, not gate blockage; it
scored 0 successes / 16 harm, the cohort's entire remaining B1 onset
harm. Taken states: seed 433001 k=4 partial, purity 0.750; seed 433017
k=2 partial, 0.829; seed 433017 k=4 full, 0.846; seed 433041 k=2 full,
0.829; seed 433041 k=4 full, 0.771. **(b)** candidate B1 harm **16** vs
the guard's **70** — passes. **(c)** 16 < recent8's **78** — passes.
B1 successes: candidate **0** vs recent8 **18** vs the guard's **10**.
Derivations: the purity-only-rule took the 3 full states, so the
widening added **2** B1 firings on this cohort; partial-purity and
partial-ungated each took 5, leg P again blocking none; release-rule
2, higher-corroboration-rule 2. Recovery and minority firing at B1:
0 of 6 on both cohorts, as in every preceding cycle. **The widening
works at B1, on both cohorts, and is credited with the added firings
exactly as pre-registered — this is the first cycle in this line whose
PRIMARY engagement criterion PASSes on both cohorts.**

### Criterion 6 — stationary control selectivity not given back (FAIL / FAIL)

This is the pre-registered central cost of the widening, and it
materialized in full on both cohorts. Development: **(a)** candidate
failed-by-abstention **48 of 240** against the ≤ 32 budget — FAIL.
**(b)** candidate successes **66** vs recent8's **84**, required ≥ 78 —
FAIL by 12 beyond the margin (raw deficit 18). **(c)** candidate harm
**126** vs recent8's **156** — passes (the false abstentions did remove
harm; they cost successes, not safety). The entire deficit is three
stationary states, all **partial** firings the unwidened rule could
not have taken (branch diffs vs the purity-only-rule: 3 of 15 graded
control states): seed 432003 k=8 (purity 0.853, 0/0/16 vs recent8
5/11), seed 432003 k=32 (purity 0.872, 0/0/16 vs 6/10), and seed
432039 k=4 (purity 0.825, 0/0/16 vs 7/9) — the three states' recent8
successes sum to exactly the 18-success deficit. Additional: **(a)**
abstentions **48 of 240** — FAIL. **(b)** successes **109** vs
recent8's **143**, required ≥ 137 — FAIL (raw deficit 34). **(c)**
harm **83** vs recent8's **97** — passes. Three abstained states
(branch diffs vs purity-only: 2 of 15 — one of the three is a full
firing the unwidened rule also took): seed 433001 k=4 **full**
(purity 0.813, 0/0/16 vs recent8 9/7 — also taken by the purity-only
rule and the guard), seed 433017 k=2 **partial** (0.829, 0/0/16 vs
12/4), seed 433041 k=8 **partial** (0.842, 0/0/16 vs 13/3); their
recent8 successes sum to exactly the 34-success deficit. One further
additional control state (seed 433041 k=16) took a retained recovery
identical in score to recent8 (13/3). Minority never fired on either
control arm. As pre-registered in the protocol: neither leg P
(designed armed on stationary evidence) nor the carried authority
arming releases a stationary partial firing — a flipped stationary
event is locally identical to a partial onset event, and this
criterion's frozen margins price exactly that.

### Criterion 5 — release and productivity by checkpoint 32 (FAIL development / PASS additional)

Development: **(a)** abstentions **0 of 144** — passes. **(b)**
successes **82** = recent8's **82**, required ≥ 74 — passes. **(c)**
non-recent8 branch in **2 of 9** switch-stage k=32 states against the
1-of-9 allowance — FAIL: both are carried minority routings (seed
432003 B2, purity 0.758; seed 432039 B2, purity 0.733), identical to
the purity-only baseline method at k=32 there. **(d)** abstained
branch in **0 of 9** — passes: the widened trigger produced no late
abstention on either cohort; at the development B1 k=32 seed 432003
state a full trigger was present but leg P was disarmed (purity
0.658), an exercised leg-P release. Additional: all four pass —
abstentions 0/144, successes **65** = recent8's 65, non-recent8
**0 of 9**, abstained **0 of 9** (two return-A k=32 partial triggers
were leg-P-disarmed, purity 0.697 and 0.567). The development failure
is the carried recovery branches' k=32 records, not a widened-trigger
effect — recorded but not selected as the next limitation, as in the
preceding gradings.

### Criterion 1 — second-switch B2 protection preserved (PASS / PASS)

Development: **(a)** minority recovery TAKEN at **5 of 6** pooled B2
onset states — passes. **(b)** minority TAKEN 0/6 at B1 and 0/6 at
return-A — passes. **(c)** B2 harm **39** vs the guard's **61** and
the 0.60 × recent8 ceiling of 52.2 (recent8 87) — passes. **(d)** B2
successes **57** vs guard + 16 = 19 — passes. Additional: minority
TAKEN **6 of 6**; selectivity 0/6 and 0/6; B2 harm **33** vs guard
**48** and ceiling 55.2 (recent8 92); successes **63** vs 16 — all
pass. The widened abstention trigger did not disturb the minority
branch's B2 protection on either cohort.

### Criterion 4 — return-A onset harm preserved (PASS development / FAIL additional)

Development: candidate return-A pooled onset harm **36** vs the
guard's **75** and the 0.60 × recent8 ceiling of 52.2 (recent8 87) —
passes both comparisons; regular recovery TAKEN at 6/6 return-A onset
states. Additional: candidate **53** vs the guard's **53** — sub-condition
(a) passes at equality — but the ceiling is 0.60 × 85 = **51.0**, so
sub-condition (b) FAILs by 2. Regular recovery TAKEN at 4/6 states.
The candidate is identical to every carried gate-generation baseline
method at return-A onset on this cohort (all score 43 successes / 53
harm there): the failure is inherited from the carried profile, not
produced by the widened trigger, and is charged unchanged, as the
protocol requires.

### Criterion 2 — return-A recovery successes preserved (PASS / PASS)

Development: candidate **60** successes vs frozen_A's 60 (40% floor
24.0) and guard + 16 = 21 — passes. Additional: candidate **43** vs
frozen_A's 66 (floor 26.4) and guard + 16 = 27 — passes. Reported in
full, not hidden: on development cumulative scores 68 successes at 28
harm against the candidate's 60 at 36 — beating it on both axes —
while frozen_A exactly ties the candidate there (60 successes, 36
harm); on additional, frozen_A (66 at 30 harm) and cumulative (60 at
36 harm) both beat the candidate's 43 at 53 on BOTH axes. Cumulative's
first-return dominance on both axes on both cohorts now extends to
**six** consecutive graded cohort pairs.

### Criterion 3 — pooled onset harm not above guard (PASS / PASS)

Development: candidate pooled onset harm **75** vs the guard's
**198**, with all **6 of 6** onset cells ≤ recent8 (B1 0/0, return-A
18/18, B2 15/24 against recent8's 48/42, 44/43, 47/40). Additional:
**102** vs the guard's **171**, 6 of 6 cells ≤ recent8. The pooled
figure the higher-corroboration generation failed on additional is
restored on both cohorts, driven by the B1 repair.

### Criterion 7 — full accounting (PASS / PASS)

The saved detailed results contain every field listed in
metrics_reported: per-seed TRAIN actor accounting counted once,
per-method successes / harmful actions / abstentions at every
checkpoint, the candidate's full decision record including the
complete abstention-gate record (support threshold null at 72/72
entries per cohort, abstention_disarmed_by_support false everywhere,
abstention_gate_armed == purity_armed everywhere,
abstention_trigger_kind at every checkpoint), checkpoint SHA256, and
restore-replay identity true at every checkpoint in both cohorts
(72/72 entries per cohort, script-verified in this grading stage).
Learner information-acquisition actions = 0, learner training actions
= 0, additional requested observations = 0, throughout.

## Learning evaluation

- Task successes at each checkpoint (candidate succ/harm/abst vs
  recent8 succ/harm), development: B1-2 (0/0/48 vs 0/48), B1-4 (0/0/48
  vs 6/42), B1-8 (0/0/48 vs 10/38), B1-16 (17/31/0 vs 17/31), B1-32
  (25/23/0 vs 25/23); return_A-2 (30/18/0 vs 4/44), return_A-4 (30/18/0
  vs 5/43), return_A-8 (19/29/0 vs 25/23), return_A-16 (33/15/0 vs
  26/22), return_A-32 (26/22/0 vs 26/22); B2-2 (33/15/0 vs 1/47),
  B2-4 (24/24/0 vs 8/40), B2-8 (27/21/0 vs 13/35), B2-16 (34/14/0 vs
  19/29), B2-32 (31/17/0 vs 31/17); control-2 (17/31/0 vs 17/31),
  control-4 (14/18/16 vs 21/27), control-8 (2/30/16 vs 7/41),
  control-16 (15/33/0 vs 15/33), control-32 (18/14/16 vs 24/24).
  Additional: B1-2 (0/16/32 vs 8/40), B1-4 (0/0/48 vs 10/38), B1-8
  (9/7/32 vs 28/20), B1-16 (26/22/0 vs 26/22), B1-32 (14/34/0 vs
  14/34); return_A-2 (22/26/0 vs 0/48), return_A-4 (21/27/0 vs 11/37),
  return_A-8 (36/12/0 vs 24/24), return_A-16 (28/20/0 vs 28/20),
  return_A-32 (21/27/0 vs 21/27); B2-2 (32/16/0 vs 1/47), B2-4
  (31/17/0 vs 3/45), B2-8 (28/20/0 vs 21/27), B2-16 (17/31/0 vs
  17/31), B2-32 (30/18/0 vs 30/18); control-2 (17/15/16 vs 29/19),
  control-4 (25/7/16 vs 34/14), control-8 (20/12/16 vs 33/15),
  control-16 (29/19/0 vs 29/19), control-32 (18/30/0 vs 18/30).
  Checkpoint 0 is diagnostic only (candidate k=0 harm per switch
  stage 48/39/47 development, 32/26/48 additional).
- Comparison with the preceding learner: the candidate differs from
  the graded purity-only baseline method at 8 of 72 checkpoints
  (development) and 7 of 72 (additional) — exactly the widened
  trigger's footprint: the added B1 onset abstentions, the stationary
  partial false firings, and their downstream cells. Onset pooled
  successes / harm: candidate 117/75 development and 106/102
  additional, vs the purity-only method's 119/137 and 108/132.
- Comparison with simple fixed baselines: recent8 and the guard are
  graded throughout above; cumulative and frozen_A dominate the
  candidate at return-A on both axes (see criterion 2).
- Evidence needed before adaptation / retention: unchanged from the
  carried family — the widened trigger engages at the earliest graded
  checkpoint (k=2) at B1 on both cohorts; past knowledge (minority and
  retained recovery) is retained exactly as in the graded candidate.
- Generalization: handoff level 2–3, simulator-bounded only. No
  level-6 or novel-representation claim: every element, including the
  widened trigger threshold, is designer-supplied. A PASS on criterion
  9 demonstrates partial-opposition-triggered, purity-gated abstention
  protecting the first switch in this simulator — not general
  first-contact handling, not calibrated uncertainty, and not
  real-world safety.

## Safety and evidence costs

- Harmful TEST actions: reported per cell above and per criterion;
  pooled onset 75 (development) / 102 (additional) against recent8's
  264 / 255 and the guard's 198 / 171.
- Harmful TRAIN acquisition actions by the learner: **0** — the
  learner issues no training interventions; all TRAIN evidence comes
  from the shared external actor stream, whose actual harmful /
  productive / neutral outcomes, reported harm, and label flips are
  published per seed in the saved results (criterion 7).
- Failed-by-abstention: pooled onset 96 / 288 (development) and
  80 / 288 (additional); checkpoint-32 0 / 144 on both cohorts;
  stationary control **48 / 240 on both cohorts** — the cycle's
  dominant cost, graded under criterion 6. Abstentions are scored as
  failed tasks, never as successes.
- Additional requested observations: **0**.
- False confidence / unnecessary abstention: the unnecessary
  abstentions are the stationary ones graded under criterion 6 —
  five partial firings across the two cohorts' control arms (plus one
  full firing on additional the unwidened rule also took), each a full
  16-episode refusal at a state where recent8 scored 5–13 successes.
  At B1 onset the symmetric cost is stated under criterion 9: B1
  successes 0 on both cohorts against recent8's 6 / 18.
- Report integrity: frozen protocol committed before implementation
  (`bec31ce`); cohorts inspected only through the registered
  evaluation; no parameter was re-tuned against the 432003-family /
  433001-family cohorts after inspection. Provenance limitation:
  developer-selected simulation seeds in one engineered two-feature
  simulator family; not independent external proof.

## Scientific conclusion

**Failed — and a Regression on the stationary control arm.** Per the
protocol's own grading definitions: NOT Demonstrated (criteria 6, 5,
and 4 FAIL). The **Failed** clause is triggered on the additional
cohort twice over — criterion 6 FAILs there (abstentions 48/240
against the ≤ 32 budget; successes 109 vs recent8's 143 against the
−6 margin) and criterion 4 FAILs there (return-A harm 53 vs the 51.0
ceiling) — either is sufficient under the clause; criterion 6 also
FAILs on development, and criterion 5 FAILs on development only.
The Partially-demonstrated clause requires criterion 9 AND criterion
7 to PASS on both cohorts with failures confined to criteria 1–6 on
either cohort — criterion 9 and 7 do PASS on both — but the Failed
clause keys on additional-cohort failures of criteria 6 and 4, which
occurred, so Failed governs. **Regression:** the protocol's
Regression clause is triggered by the stationary control arm —
candidate control successes fall below recent8's by more than 6 on
BOTH cohorts (−18 development, −34 additional). The other Regression
clauses do not trigger (pooled onset harm 75/102 well below recent8's
264/255; k=32 successes 82/65 equal to recent8's, above the
recent8 − 4 lines; full unit suite and historical transfer benchmark
pass — see Verification). What the experiment establishes, stated as
prominently as the failure: the PRIMARY hypothesis is confirmed on
both cohorts — widening the trigger to partial opposition restored B1
engagement (6/6 and 5/6 taken, with 4 and 2 partial-only firings
credited to the widening itself), held B1 pooled onset harm at 0 and
16 against the guard's 62 and 70 and recent8's 90 and 78, and kept
the abstained branch out of the k=32 records on both cohorts
(criterion 5(d) PASS/PASS) — and the price pre-registered for it is
also confirmed, in full: partial opposition is not onset-specific in
this simulator, so the same widened trigger refuses whole stationary
segments (48/240 abstentions on both cohorts) and converts the
preceding generation's no-trigger stationary PASS into a stationary
Regression. The trigger question and the gate question are now both
answered: no trigger threshold on the newest pair alone — full or
partial — separates a genuine first switch from stationary noise at
the frozen selectivity margins. Generalization level 2–3,
simulator-bounded (see Learning evaluation).

**Next limitation (selected for the next cycle, Priority 1):**
stationary selectivity under a partial-opposition trigger — B1
protection now demonstrably requires engaging on partial opposition
(criterion 9 PASS/PASS, B1 harm 0/16), and partial opposition occurs
on stationary arms at the simulator's flip rates, where neither leg P
nor the carried authority arming releases it (criterion 6 FAIL/FAIL;
five partial stationary firings across cohorts, each a full
16-episode refusal; control successes −18/−34 vs recent8, a
Regression). Measurable: on NEW cohorts under a NEW protocol, whether
a condition derived from observed evidence — beyond the newest pair's
own opposition count and the reference-purity leg, neither of which
separates the populations — can distinguish a genuine switch onset
from stationary partial opposition well enough to hold criterion 6's
frozen margins (abstentions ≤ 32/240, successes ≥ recent8 − 6) while
keeping criterion 9's B1 engagement and harm profile, without giving
back checkpoint-32 release. Recorded but not selected: criterion 5's
development failure is the carried recovery branches' k=32 records
(2/9, both minority routings), not a trigger effect; criterion 4's
additional failure is shared identically with every carried
gate-generation baseline method at return-A onset; and cumulative's
return-A dominance on both axes on both cohorts now extends to six
consecutive graded cohort pairs (frozen_A beats the candidate on
both axes on additional and exactly ties it on development).

Keep the learner optional and unpromoted, default controller
unchanged, no merge, no AthenZ/Synveil integration, D1–D10/V2A/V2B
unchanged.
