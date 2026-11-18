# Minority acting breadth removal recovery — removal of leg W (acting breadth) from the minority branch only

**17 November 2026 protocol frozen; 17 November 2026
implementation; 17 November 2026 evaluation; graded 18 November
2026. Status: optional, simulated, unpromoted. No
default-controller promotion, no PR merge, no D1–D10 or V2A/V2B
roadmap change, no AthenZ/Synveil integration.**

## Experiment identity

- **Name and purpose:** `minority_acting_breadth_removal_recovery`
  — whether ONE changed element, the removal of leg W
  (acting breadth, `acting_minority_joint_count >= 3`) from the
  MINORITY branch only (the minority branch fires iff
  `minority_joint_count >= 1` AND `minority_armed` AND leg P
  AND leg T, through the inverted archive model as carried;
  leg W stays on the regular branch bit-for-bit; NO new
  numeric value — a leg deleted from one branch; new
  decision-record field `minority_breadth_removal_fired`, true
  exactly when the minority branch fires with
  `acting_minority_joint_count < 3`) can hold criterion 1's
  frozen B2 form on BOTH cohorts — the signal-concordance
  grading's selected limitation (criterion 1 was the SOLE
  failing criterion, FAILing on BOTH cohorts carried identical
  to the decisive baseline at every B2 onset state, leg V
  disarming zero B2 states) — while holding stationary
  selectivity (criteria 24/22/19/6), the return-A gains
  (criteria 23/17/4), B1 engagement (criteria 21/9),
  checkpoint-32 release (criteria 18/5), and criteria 11/2/3
  as co-graded guards. Leg P, leg R, leg C, leg S, leg L,
  leg A, leg V, leg T, leg N, leg D, leg Q, and regular-branch
  leg W were explicitly NOT re-tuned. Build Order Priority 1
  (Independent Learning); handoff §8 inconsistent adaptation /
  slow or incorrect recovery of old knowledge. This protocol's
  PRIMARY criterion is criterion 1, criterion 1's frozen B2
  form promoted to PRIMARY. The protocol froze ONE grading
  cap: a Demonstrated verdict requires at least one graded B2
  onset state in at least one cohort where the decisive
  baseline was disarmed by leg W on the minority branch while
  the candidate fired the minority branch through the removal.
- **Candidate:** `MinorityActingBreadthRemovalRecoveryMemory`
  (`developmental_ai/minority_acting_breadth_removal_recovery.py`)
  — IDENTICAL to the graded
  `SignalArchiveConcordancePartialRecoveryMemory` in every
  element except the removal (see the campaign state and the
  frozen protocol for the full carried inventory).
- **Repository branch and exact commits:** branch
  `developmental-ai/minority-acting-breadth-removal-recovery`,
  forked from `de525fe`. Protocol frozen at `fc3b0ee`;
  implementation at `cc2b96f`; evaluation at `cb3a79d` (the
  commit graded here); this grading commit sits on top of
  `cb3a79d`.
- **Frozen protocol:**
  `benchmarks/minority_acting_breadth_removal_recovery_protocol.json`.
- **Seeds:** development 592003 / 592021 / 592039; additional
  593001 / 593017 / 593041 — both cohorts NEW and uninspected
  at freeze, both now INSPECTED. Never re-tune any parameter
  against them (or any earlier inspected cohort).
- **Decisive baseline:** the graded signal-concordance
  candidate (identical but for the removal). **Simplest
  credible baseline:** recent8.

## Verification

- Unit tests: PASS — full suite re-run in the grading stage
  (2871 tests OK).
- Historical regressions: PASS — historical transfer
  benchmark re-run in the grading stage, exit 0 (gains
  0.5567 / 0.50 / 0.51).
- Frozen cohorts: graded below, per criterion, per cohort.
- Linux validation: UNVERIFIED (no CI claimed for the
  grading commit).
- Windows validation: UNVERIFIED (no CI claimed for the
  grading commit).
- Replay identity: script-verified true at every checkpoint
  in both cohorts (72/72 entries per cohort) in the grading
  stage, with the evaluation analysis script re-run in full;
  no criterion-7 field missing; `support_threshold` 1 and
  `long_window_threshold` 1 everywhere;
  `minority_breadth_removal_fired` recomputed exactly
  (minority_fired AND `acting_minority_joint_count < 3`);
  candidate `minority_disarmed_by_acting_breadth` false at
  every state, as registered; the decisive-side leg-W
  minority disarming recomputation matches the removal
  firings exactly (7/7); leg V / leg A / leg Q /
  support-agreement fields recomputed exactly as carried;
  gate recomputed exactly everywhere (full: leg P alone;
  partial: leg P AND (leg R OR leg C) AND leg S AND leg L
  AND concordant_count == 0);
  `abstention_taken_through_long_window` false at every
  taken state, as carried; minority-breadth-removal-rule ==
  candidate branch and signal-concordance-rule == decisive
  branch everywhere; `singleton_release_fired` (0 firings
  dev, 1 add at 593001 return-A k=2, carried identical to
  decisive) and the `recovery_fired` composition recomputed
  everywhere; companion fields recomputable at every partial
  state and at fallback elsewhere; kind never widened;
  acting lists of 8 and newest lists of 4 with all counts
  recomputable everywhere and newest records == acting tail;
  `minority_model_archive_count == archive_events_count` and
  `minority_model_inverted` true everywhere; cross-check PASS
  at every minority-fired state 5/5 dev and 9/9 add;
  acquisition 0, training actions 0, additional requested
  observations 0.

## Learning evaluation

The removal fired exactly SEVEN states across both cohorts,
every one at B2, ZERO UNEXPECTED — dev 2, both graded B2
onset: 592003 k=4 (minority_joint 2, acting_min 2, stale_min
1, purity 0.765, candidate minority 12/4 vs decisive
abstained 0/0) and 592021 k=2 (joint 1, acting 1, stale 0,
purity 0.853, 14/2 vs decisive recent8 0/16); add 5: graded
onset 593001 k=4 (joint 1, acting 1, purity 0.865, 12/4 vs
recent8 0/16), 593017 k=2 (joint 1, acting 2, purity 0.790,
10/6 vs abstained 0/0), 593041 k=2 (joint 1, acting 2,
purity 0.818, 10/6 vs abstained 0/0), plus diagnostic 593017
k=0 (10/6 vs recent8 0/16) and ungraded 593001 k=16 (12/4 vs
abstained 0/0). Branch diffs vs decisive: dev 2, add 5, ALL
classified minority_breadth_removal; score diffs vs decisive
2/72 dev and 5/72 add.

Scores [successes, harm] (abstained episodes third where
graded): pooled onset candidate [109, 83] dev vs decisive
[83, 93] and recent8 [31, 257]; add candidate [122, 102] vs
decisive [90, 102] and recent8 [32, 256]. B1 candidate
[0, 16] dev / [2, 30] add, identical to decisive on both.
B2 candidate [47, 33] dev vs decisive [21, 43] and recent8
[11, 85]; add [52, 44] vs decisive [20, 44] and recent8
[20, 76] — the whole B2 gap the removal firings. Return-A
candidate [62, 34] dev / [68, 28] add, identical to decisive
on both. Checkpoint-32 candidate [55, 89, 0] dev identical
to decisive AND recent8; add [61, 83, 0] identical to
decisive vs recent8 [60, 84, 0]. Control candidate
[137, 103, 0] dev and [125, 99, 16] add, IDENTICAL to
decisive on both (vs recent8 [137, 103, 0] dev /
[132, 108, 0] add). Engagement onset (k=2/4): B1 abstained
dev 5/6 and add 4/6, identical to decisive; B2 minority dev
4/6 (decisive 2/6) and add 5/6 (decisive 2/6) — the
removal's two dev and three add graded firings; return-A
recovery dev 6/6 and add 6/6, identical to decisive.

Per-criterion grading (development / additional), PRIMARY
criterion 1 first, then co-graded guards 24/22/19/6,
23/17/4, 21/9, 18/5, 11, 2, 3, 7 — script-computed from the
saved detailed results at `cb3a79d`:

- **C1 PRIMARY (B2 protection, criterion 1's frozen form):
  PASS / PASS, in full on both.** Dev: minority 4/6 PASS
  (a); selectivity PASS (b) (B1 minority 0/6, return-A
  minority 0/6); harm 33 vs guard 69 PASS and ceiling
  0.60 × recent8 85 = 51.0 PASS (c); successes 47 vs
  guard+16 = 27 PASS (d). Add: minority 5/6 PASS (a);
  selectivity PASS (b) (0/6 and 0/6); harm 44 vs guard 67
  PASS and ceiling 0.60 × recent8 76 = 45.6 PASS (c) by 1.6;
  successes 52 vs guard+16 = 29 PASS (d). This PASSes where
  criterion 1 FAILed on BOTH cohorts in the preceding cycle
  carried identical to decisive — here the gap is the
  removal's own firings, not a draw difference.
- **C24 / C22 / C19 / C6 (stationary selectivity, criterion
  6's frozen form): PASS / FAIL.** Dev: abstentions 0/240
  PASS (a); successes 137 = recent8 137 PASS (b); harm 103
  = recent8 103 PASS (c) — no taken control abstention drawn
  on development. Add: abstentions 16/240 PASS (a);
  successes 125 vs recent8 132, line >= 126, FAIL (b) by 1;
  harm 99 vs recent8 108 PASS (c). IDENTICAL to decisive on
  both cohorts (branch diffs vs decisive 0/15 graded control
  states per cohort; the removal's pooled leg-W minority
  population at graded control checkpoints is zero, exactly
  as frozen): the entire additional deficit is ONE carried
  partial S&L firing kept under leg V at concordant 0 —
  593017 control k=8 (supporting 1, stale 1, concordant 0,
  purity 0.825, abstained 0/0 vs recent8 7/9), whose
  7-success cost is the whole 125-vs-132 gap.
- **C23 / C17 / C4 (return-A harm, criterion 4's frozen
  form): PASS / PASS**, in full on both — dev harm 34 vs
  guard 56 and ceiling 0.60 × recent8 86 = 51.6; add harm 28
  vs guard 93 and ceiling 0.60 × recent8 93 = 55.8. Identical
  to decisive on both.
- **C21 / C9 (B1 engagement): PASS / PASS.** Dev TAKEN 5/6
  (4 full + 1 partial, path R+C), harm 16 vs guard 46 and <
  recent8 86; add TAKEN 4/6 (3 full + 1 partial, path R+C),
  harm 30 vs guard 62 and < recent8 87. Identical takings to
  decisive at onset on both.
- **C18 / C5 (checkpoint-32 release): PASS / PASS.** Dev in
  full — abstentions 0/144, successes 55 = recent8 55,
  non-recent8 0/9, abstained 0/9. Add: abstentions 0/144,
  successes 61 vs recent8 60, non-recent8 1/9 AT its line
  (the carried retained firing at 593017 return-A k=32,
  identical to decisive), abstained 0/9.
- **C11 (conjunction of C6 and C9): PASS / FAIL** — the
  additional failure is its stationary (C6) side alone; the
  B1 side PASSes both.
- **C2 (return-A successes): PASS / PASS.** Dev successes
  62 vs frozen_A floor 0.40 × 56 = 22.4 and guard+16 = 24;
  add 68 vs floor 0.40 × 66 = 26.4 and guard+16 = 19. Note
  in full: frozen_A's return-A successes (56 dev / 66 add)
  sit below the candidate's on both cohorts this cycle.
- **C3 (pooled onset): PASS / PASS** — harm 83 vs guard 171
  dev and 102 vs guard 222 add, cells 6/6 on both.
- **C7 (accounting / reproducibility): PASS / PASS** —
  replay 72/72 per cohort, all recomputations clean
  (above), acquisition 0.

**The grading cap is MET on BOTH cohorts** — five graded B2
onset removal firings across both cohorts (dev 592003 k=4
and 592021 k=2; add 593001 k=4, 593017 k=2, 593041 k=2), each
a state where the decisive baseline was disarmed by leg W
on the minority branch while the candidate fired the
minority branch through the removal. The PRIMARY's PASS is
therefore a removal demonstration, not a carried profile.

## Safety and evidence costs

- Harmful task actions: pooled onset 83 dev / 102 add (vs
  decisive 93 / 102 and recent8 257 / 256); return-A 34 / 28;
  B1 16 / 30; B2 33 / 44; control harm 103 / 99 (at / below
  recent8 103 / 108).
- Failed-by-abstention: control 0 abstained episodes dev
  (0/240) and 16 add (16/240, the one kept concordant-0
  partial S&L firing at 593017 k=8); onset abstentions
  carried identical to decisive except where a removal
  firing pre-empted one (dev 592003 B2 k=4); k32 abstentions
  0.
- Additional requested observations / learner information
  acquisition / training actions: 0 / 0 / 0.
- False confidence and unnecessary abstention: the removal's
  five graded firings converted decisive abstentions 0/0
  (three) and recent8 fall-throughs 0/16 (two) into minority
  actions at 12/4, 14/2, 12/4, 10/6, 10/6 — productive on
  their designed population, worth +26 successes / −10 harm
  dev and +32 successes / +0 harm add against decisive at B2
  onset. The kept concordant-0 stationary firing on
  additional is the cycle's remaining unnecessary-abstention
  cost, charged in full under C24/22/19/6 (it alone fails
  additional's (b) by 1).
- Report integrity: all figures script-computed this pass
  from the saved detailed results at `cb3a79d`; the
  evaluation analysis script was re-run in the grading
  stage with identical recomputations. No CI claimed for
  the evaluation or grading commits (Linux/Windows
  UNVERIFIED).

## Scientific conclusion

**FAILED, not a Regression**, under the protocol's own
definitions. The Failed clause triggers on the additional
cohort: criteria 24, 22, 19, and 6 FAIL there (on
sub-condition (b) alone) and criterion 11 FAILs there with
them; criterion 7 PASSes both, and every other criterion —
including PRIMARY criterion 1 — PASSes both. The Regression
clauses do not trigger — pooled onset harm 83/102 below
recent8 257/256, control successes 0 dev and −7 add (the
clause needs more than −6 on BOTH cohorts), k=32 successes
55/61 above the recent8 − 4 lines of 51/56, suite +
transfer pass. PRIMARY criterion 1 PASSes on BOTH cohorts
and the grading cap is MET on BOTH cohorts, so the
removal's mechanism is demonstrated on its designed
population: deleting leg W from the minority branch alone
moved B2 minority engagement from decisive's 2/6 to 4/6 dev
and 5/6 add, with B2 harm at or below decisive on both
cohorts and every guard the removal can touch held. The
overall verdict is nevertheless Failed, because the frozen
Failed clause is triggered by the stationary family on
additional — a carried profile identical to the decisive
baseline on an arm where the removal is structurally inert,
its entire deficit one kept concordant-0 partial S&L
stationary firing (593017 control k=8, recent8 7/9) that no
element of this experiment changes. Thirteen of sixteen
criteria PASS on both cohorts; the three stationary forms
(24/22/19/6, one computation) and their conjunction (11)
fail additional only. Generalization level: handoff level
2–3 at most (choosing among / applying designer-supplied
rules); no novel-representation, calibrated-uncertainty, or
real-world-safety claim.

## Next limitation selected

**P1 stationary selectivity of the kept concordant-0
partial S&L abstention firings** — criteria 24/22/19/6 are
now the SOLE failing family, FAILing additional on
sub-condition (b) alone by 1 success (125 vs the >= 126
line), while PRIMARY criterion 1 and every other criterion
PASS on both, on an arm where the candidate is identical to
the decisive baseline at every graded control state and the
removal fired zero control states; the entire deficit is
one kept concordant-0 partial S&L firing (593017 control
k=8, supporting 1, stale 1, purity 0.825, abstained 0/0 vs
recent8 7/9). This is the population recorded but not
selected in the signal-concordance grading: leg V kept 4/12
pooled stationary S&L firings (the concordant-0 ones), and
that cycle's pooled review found no permitted quantity
separating kept concordant-0 firings — whether an
evidence-derived condition on the kept concordant-0 partial
population itself can hold criterion 6's frozen form on
BOTH cohorts while holding the B2 gains (criterion 1, now
PASSing both through the removal), the return-A gains
(criteria 23/17/4), B1 engagement (criteria 21/9),
checkpoint-32 release (criteria 18/5), and criteria 11/2/3
as co-graded guards, on NEW cohorts under a NEW protocol.
Recorded but not selected: additional's criterion-1(c)
ceiling margin is thin (44 vs 45.6) — the removal's priced
tail, carried as a guard; no other criterion fails on
either cohort.
