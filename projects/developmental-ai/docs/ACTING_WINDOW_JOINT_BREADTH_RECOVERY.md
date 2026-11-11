# Acting window joint breadth recovery — an acting-window joint-breadth leg (leg W) on both recovery branches

**10 November 2026 protocol frozen; 10 November 2026
implementation; 11 November 2026 evaluation; graded 11 November
2026. Status: optional, simulated, unpromoted. No
default-controller promotion, no PR merge, no D1–D10 or V2A/V2B
roadmap change, no AthenZ/Synveil integration.**

## Experiment identity

- **Name and purpose:** `acting_window_joint_breadth_recovery`
  — whether ONE changed element, leg W, an ACTING-WINDOW
  JOINT-BREADTH LEG on BOTH recovery branches (a branch fires
  only if its own joint count over the acting window
  events[-8:] — per-event joint flags scored exactly as the
  branch's newest-pair and stale-window flags are — reaches
  acting_joint_threshold 3, shared by both branches), can hold
  criterion 5's frozen checkpoint-32 release form on BOTH
  cohorts — the companion cycle's selected limitation
  (criterion 5 FAILed development there on successes and
  routing count: two HARMFUL regular retained routings at
  seed 492003, purity 0.737 / 0.711, stale counts 0/0, each
  scoring 0/16, a population neither leg T — whose designed
  population was again absent — nor leg C touches, and the
  failure carried that cycle's checkpoint-32 Regression) —
  while holding first-switch (B1) engagement with leg C
  carried (criterion 9), stationary selectivity (criterion 6),
  B2 protection with the inverted minority model carried
  (criterion 1), and return-A harm (criterion 4) as co-graded
  guards. Leg P, leg R, leg T, and leg C were explicitly NOT
  re-tuned. Build Order Priority 1 (Independent Learning),
  items 2 + 3 + 4; handoff §8 slow or incorrect recovery of
  old knowledge / inconsistent adaptation to changing rules.
  This protocol's PRIMARY criterion is criterion 16, the
  conjunction of (a) criterion 5's checkpoint-32 release form,
  (b) criterion 9's B1 form with leg C carried, (c) criterion
  6's stationary form, and (d) criterion 1's B2 form with the
  inverted minority model carried; criteria 5, 9, 6, 1, 11,
  4, 2, 3, and 7 are its co-graded guards. The protocol also
  froze a grading cap: a Demonstrated verdict additionally
  requires at least one switch-stage checkpoint-32 state in
  at least one cohort at which the decisive baseline took a
  non-recent8 recovery branch and the candidate released to
  recent8 through leg W (that branch's acting joint count
  below 3, its stale pair count below 2, every other carried
  condition met).
- **Candidate:** `ActingWindowJointBreadthRecoveryMemory`
  (`developmental_ai/acting_window_joint_breadth_recovery.py`)
  — IDENTICAL to the graded
  `CompanionConcordancePartialRecoveryMemory` in every element
  (acting model recent8 exactly, extended signal, retained
  archive, archive concordance, joint test joint_count >= 1,
  recovery model, the full three-leg authority condition, the
  minority branch in full INCLUDING the inverted minority
  model, leg T on both recovery branches, leg P >= 0.70, leg R
  and leg C on partial abstention triggers, and the full /
  retained-partial abstention classes with the widened class
  removed records-only, support threshold null) — verified by
  a diff against the graded companion candidate at
  implementation: the ONLY code differences are leg W (the
  per-event acting joint records over events[-8:] for both
  branches, acting_joint_count / acting_minority_joint_count,
  acting_joint_threshold 3, the two added firing conditions,
  the recovery_disarmed_by_acting_breadth /
  minority_disarmed_by_acting_breadth flags recorded only
  when joint, arming, leg P, and leg T all pass, and the two
  reason strings), its docstring, and names/schema. Separate
  optional learner; the default controller and all existing
  learners are untouched; the graded companion candidate
  appears only as the decisive baseline.
- **Branch and commits:**
  `developmental-ai/acting-window-joint-breadth-recovery`
  (forked from `e625f8f`, the companion grading commit).
  Protocol frozen at `d74a9e7` (BEFORE implementation);
  implementation at `ec4b54d`; evaluation at `b36133c`. This
  grading report is committed on top of the evaluation commit.
- **Frozen protocol:**
  `benchmarks/acting_window_joint_breadth_recovery_protocol.json`
  (frozen 2026-11-10, before any implementation, unit test,
  harness, or score inspection for this experiment).
- **Cohorts:** development 502003/502021/502039 and additional
  503001/503017/503041 — NEW at freeze, disjoint from every
  earlier cohort. Both cohorts are now **INSPECTED** and must
  never be re-tuned against.
- **Decisive baseline:** `companion_concordance_partial_recovery`
  (identical but for leg W; branch selection identical except
  at states where a recovery branch met every carried
  condition but its acting joint count is below 3, and those
  states' fall-throughs). `recent8` is the simplest credible
  baseline and the candidate's own acting model.

## Verification

- Unit tests: PASS — 88/88 new candidate tests at
  implementation; full suite 1642 tests OK in the
  implementation and evaluation stages, and re-run in this
  grading stage: 1642 tests OK (`python3 -m unittest discover
  -s tests`, run 2026-11-11 this pass). The new tests include
  the discriminating states: the purity-armed regular recovery
  rows at acting_joint_count 2 (decisive baseline FIRES
  retained_archive, candidate stands down to recent8), the
  minority recovery rows at acting_minority_joint_count 2
  (decisive baseline FIRES minority_archive, candidate's
  minority branch stands down and the decision falls through
  to the taken full abstention), and the precedence rows where
  both branches are breadth-disarmed.
- Historical regressions: PASS — historical transfer benchmark
  (`python3 -m benchmarks.transfer_benchmark`) exit 0 in the
  evaluation stage and re-run in this grading stage, standard
  three-seed output (success gains 0.5567 / 0.50 / 0.51 on
  seeds 17 / 23 / 41).
- Frozen cohorts: PASS (run exactly as registered) — both
  cohorts evaluated at `b36133c`; every checkpoint entry
  carries per-method successes / harmful TEST actions /
  abstentions / attempted tasks, the candidate's full decision
  record (including the full acting-breadth, companion, and
  stale records), checkpoint SHA256, and restore-replay
  identity (script-verified in this grading stage: true at
  every checkpoint in both cohorts, 72/72 entries per cohort).
- Linux validation: UNVERIFIED (no GitHub Actions run on the
  grading commit was checked; no CI is claimed).
- Windows validation: UNVERIFIED (same).

## Per-criterion grading (precommitted, graded individually, per cohort)

Graded script-computed from the saved detailed results at
`b36133c` (grading script and output kept with the campaign
records). PRIMARY criterion 16 first, then co-graded guards
5, 9, 6, 1, 11, 4, 2, 3, 7. Development / additional
throughout.

**Criterion 16 — PRIMARY (release + B1 + stationary + B2
conjunction): FAIL / PASS.** Development: release side PASS,
B1 side PASS, stationary side PASS, B2 side FAIL.
Additional: all four sides PASS. The conjunction therefore
fails on development alone, attributable to its B2 side
below — and, as the Failed clause below records, the
experiment is Failed on the additional cohort's criteria 4
and 2 regardless of the conjunction's pass there.

**Criterion 5 — release and productivity by checkpoint 32:
PASS / PASS.** Both cohorts pass in full — the first
checkpoint-32 release PASS on both cohorts in this line.
(a) abstentions 0/144 on both; (d) abstained branch 0/9 on
both. Development: (b) successes 56 = recent8 56 (line 48);
(c) non-recent8 branch in 0/9 states. **Development drew NO
checkpoint-32 routing at all** — the decisive baseline took
recent8 at all 9 switch-stage states and the candidate is
identical there (successes/harm 56/88 = decisive = recent8).
Additional: (b) successes 85 = recent8 85 (line 77); (c)
non-recent8 0/9. Additional drew exactly ONE routing — seed
503017, B2, minority branch, purity 0.750, stale minority
count 0, acting minority count 1 — which leg W released to
recent8: decisive 14/2 vs candidate / recent8 8/8. **That
routing was PRODUCTIVE for the decisive baseline, so the
release gave back 6 successes and 6 harm** (candidate k=32
harm 59 vs decisive 53; successes 85 vs decisive 91), landing
the candidate exactly on recent8's k=32 line — the
pre-registered productive-routing give-back, charged in full
view; criterion 5's frozen form holds because its (b) margin
is measured against recent8, not against the decisive
baseline. Leg T disarmed ZERO states on either cohort for
the third consecutive cycle. All nine k=32 states per cohort
(branch; kind; purity; stale regular/minority; acting
regular/minority; candidate vs decisive vs recent8 successes
/harm — identical triples abbreviated =): development —
502003 B1 recent8 (partial, 0.735, 0/0, 0/2, 0/16 =); 502003
return-A recent8 (none, 0.655, 0/0, 0/0, 5/11 =); 502003 B2
recent8 (partial, 0.632, 0/0, 1/0, 11/5 =); 502021 B1 recent8
(none, 0.800, 0/0, 0/0, 2/14 =); 502021 return-A recent8
(none, 0.727, 1/0, 0/0, 7/9 =); 502021 B2 recent8 (partial,
0.657, 0/0, 0/1, 3/13 =); 502039 B1 recent8 (partial, 0.667,
0/0, 0/1, 10/6 =); 502039 return-A recent8 (none, 0.690, 0/0,
0/0, 9/7 =); 502039 B2 recent8 (none, 0.676, 0/0, 0/0, 9/7 =).
Additional — 503001 B1 recent8 (none, 0.684, 0/0, 0/0, 12/4
=); 503001 return-A recent8 (none, 0.781, 0/0, 0/1, 9/7 =);
503001 B2 recent8 (none, 0.694, 0/0, 0/1, 8/8 =); 503017 B1
recent8 (partial, 0.684, 0/0, 0/2, 12/4 =); 503017 return-A
recent8 (partial, 0.676, 0/0, 0/1, 13/3 =); 503017 B2
**released through leg W** (decisive minority_archive →
candidate recent8; partial, 0.750, stale_min 0, acting_min 1,
breadth-disarmed; candidate 8/8, decisive 14/2, recent8 8/8);
503041 B1 recent8 (none, 0.846, 0/0, 0/0, 9/7 =); 503041
return-A recent8 (none, 0.667, 0/0, 0/0, 7/9 =); 503041 B2
recent8 (none, 0.750, 0/0, 1/0, 7/9 =).

**Criterion 9 — first-switch (B1) engagement: PASS / PASS.**
Leg W touched no B1 state on either cohort — the candidate
is identical to the decisive baseline at every B1 state.
Development: abstention TAKEN at 4/6 pooled B1 onset states
(1 full + 3 retained partial, all three partials armed
through leg C only — preceding 0, companion armed), harm 31
<= guard 95 (b) and 31 < recent8 95 (c). B1 successes 1 vs
recent8 1 / guard 1, stated in full. Additional: TAKEN 5/6
(0 full + 5 retained partial; corroboration paths C, R+C,
R+C, C, R), harm 9 <= guard 81 and 9 < recent8 81. B1
successes 7 vs recent8 15 / guard 15, stated in full.

**Criterion 6 — stationary control selectivity: PASS /
PASS.** Development PASSes at EXACT recent8 parity:
abstentions 0/240, successes 149 = recent8 149, harm 91 =
91 — no control firing at all, candidate identical to the
decisive baseline on the control arm (branch differences
0/15 graded control states). Additional: abstentions 16/240
and harm 106 vs 118 PASS, successes 118 vs recent8 122,
required >= 116 — the sole control firing is ONE carried
retained-partial firing (seed 503041, k=16, purity 0.870,
0/0 vs recent8 4/12), identical in the decisive baseline;
leg W added no control difference on either cohort.

**Criterion 1 — second-switch (B2) protection: FAIL /
PASS.** Development FAILs on THREE sub-conditions, every one
of them a leg-W minority stand-down. (a) minority TAKEN
2/6 vs the decisive baseline's 5/6: the three stood-down
states are seed 502003 k=4 (acting minority count 2 —
minority released to recent8, candidate 10/6 vs decisive
13/3), seed 502021 k=2 (count 2 — stand-down falling through
to a full abstention, 0/0 vs decisive 9/7), and seed 502039
k=2 (count 2 — stand-down to a full abstention, 0/0 vs
decisive 8/8). (b) selectivity 0/6 at B1 and 0/6 at return-A
PASSes. (c) harm 35 vs guard 34 FAILs by exactly 1 (the
0.60 × recent8 ceiling, 43.2, PASSes). (d) successes 29 vs
guard 14 + 16 = 30 FAILs by exactly 1. Additional PASSes in
full: minority TAKEN 3/6, AT the frozen floor — its two
breadth stand-downs are seed 503017 k=4 (count 1 — released
to recent8, 1/15 vs decisive 13/3) and seed 503041 k=2
(count 2 — stand-down to a partial abstention, 0/0 vs
decisive 10/6); selectivity 0/6 / 0/6; harm 49 vs guard 95
and ceiling 0.60 × recent8 95 = 57.0; successes 31 vs guard
1 + 16 = 17. The minority-model cross-check PASSes at every
minority-fired state (6 development / 6 additional
applicable) with first-frame choices differing from the
widened-window method at 2/2 development and 3/3 additional
minority-fired B2 onset states checked.

**Criterion 11 — B1/stationary conjunction (carried): PASS
/ PASS.** Both sides pass on both cohorts (criteria 9 and 6
above).

**Criterion 4 — return-A onset harm: FAIL / FAIL.** The
only individual co-graded guard FAILing on BOTH cohorts,
on the SAME sub-condition — (b) the ceiling — with (a) the
guard comparison PASSing on both. Development: harm 57 vs
guard 58 PASS on (a) by 1, but ceiling 0.60 × recent8 65 =
39.0 FAIL on (b); regular recovery TAKEN 3/6 vs the decisive
baseline's 5/6 — the two breadth stand-downs are both at
k=2: seed 502021 (acting count 2; decisive retained firing
10/6, candidate fell through to recent8 1/15) and seed
502039 (acting count 2; decisive 12/4, candidate 0/16).
Candidate return-A harm 57 vs the decisive baseline's 36.
Additional: harm 62 vs guard 68 PASS on (a), ceiling
0.60 × recent8 68 = 40.8 FAIL on (b); regular recovery
TAKEN 2/6 vs the decisive baseline's 6/6 — FOUR breadth
stand-downs, all released to recent8: seed 503001 k=4
(acting 1; 11/5 → 8/8), seed 503017 k=2 (acting 2; 14/2 →
0/16), seed 503041 k=2 (acting 1; 9/7 → 1/15), and seed
503041 k=4 (acting 2; 9/7 → 0/16). Candidate return-A harm
62 vs the decisive baseline's 28. The regular branch's
fall-through to recent8 at these states is where leg W's
harm price concentrates: a stood-down correct-rule firing
is replaced not by silence but by recent8's realized harm.

**Criterion 2 — return-A recovery successes: PASS / FAIL.**
Development: successes 39 vs frozen_A 62 (floor 24.8) and
guard 22 + 16 = 38, PASS on both by 1 on (b). Additional:
successes 34 vs frozen_A 76 (floor 30.4) PASS on (a), but
guard 28 + 16 = 44 FAIL on (b) by 10. Stated in full, as
registered: frozen_A beats the candidate on BOTH axes at
return-A on BOTH cohorts (62/34 vs 39/57 development; 76/20
vs 34/62 additional), and cumulative does the same on both
(56/40 development; 64/32 additional); the decisive baseline
also beats it on both axes on both (60/36; 68/28).

**Criterion 3 — pooled onset harm: PASS / PASS.** Pooled
onset harm 123 vs guard 187 development and 120 vs guard
244 additional (a); individual onset cells <= recent8 in
6/6 development and 5/6 additional (b, at its >= 5 line
exactly — the additional return-A k=2 cell is 36 vs recent8
33). Stated in full: the candidate's pooled onset harm is
ABOVE the decisive baseline's on BOTH cohorts (123 vs 114
development; 120 vs 80 additional) — the two development
return-A releases to recent8 cost +21 harm against −12 saved
at B2, and the additional stand-downs cost +40 net — even
though both pooled figures remain below the guard's.

**Criterion 7 — full accounting: PASS / PASS.** Replay
identity true at every checkpoint in both cohorts (72/72
entries per cohort); no criterion-7 field missing anywhere;
support_threshold null everywhere; companion_threshold null
everywhere; abstention_disarmed_by_support false everywhere;
widened_threshold 3, staleness_pair_threshold 2,
preceding_pair_threshold 1, and acting_joint_threshold 3
everywhere; abstention gate recomputable everywhere (incl.
the leg-C composition) with 0 mismatches; companion fields
recomputable at every partial state (25 development / 36
additional) and at fallback at every non-partial state
(47 / 36); acting lists of 8 with both acting joint counts
recomputable everywhere with 0 mismatches; both breadth
flags recomputed everywhere with 0 mismatches;
acting-breadth-rule == candidate branch everywhere;
companion-rule == decisive baseline branch everywhere;
pre-acting-release-rule == pre-acting branch everywhere;
preceding-pair-rule == widened-removal-rule everywhere;
widened-rule == inverted branch everywhere; newest4 /
widened_armed recomputable everywhere;
abstention_trigger_kind in {full, partial, none} everywhere
— never widened, as the carried removal requires; stale
lists of 18 with both pair counts recomputable everywhere
with 0 mismatches; minority_model_archive_count ==
archive_events_count everywhere; minority_model_inverted
true everywhere; minority-model cross-check PASS at every
minority-fired state (6/6 development, 6/6 additional
applicable); learner acquisition actions 0 throughout.

## Learning evaluation

Candidate vs recent8 (simplest credible baseline), successes
/ harmful TEST actions per stage-checkpoint cell (candidate
first; abstentions in parentheses where nonzero):

Development — B1: k=0 0/48 vs 0/48; k=2 0/0 (48 abst) vs
0/48; k=4 1/31 (16) vs 1/47; k=8 0/0 (48) vs 21/27; k=16
9/7 (32) vs 14/34; k=32 12/36 vs 12/36. return-A: k=0 4/44
vs 4/44; k=2 12/36 vs 6/42; k=4 27/21 vs 25/23; k=8 32/16
vs 26/22; k=16 32/16 vs 34/14; k=32 21/27 vs 21/27. B2: k=0
0/48 vs 0/48; k=2 2/14 (32) vs 3/45; k=4 27/21 vs 21/27;
k=8 17/31 vs 23/25; k=16 33/15 vs 32/16; k=32 23/25 vs
23/25. Control: k=0 27/21 vs 27/21; k=2 23/25 vs 23/25;
k=4 32/16 vs 32/16; k=8 32/16 vs 32/16; k=16 30/18 vs
30/18; k=32 32/16 vs 32/16.

Additional — B1: k=0 0/32 (16) vs 0/48; k=2 0/0 (48) vs
8/40; k=4 7/9 (32) vs 7/41; k=8 5/11 (32) vs 12/36; k=16
21/11 (16) vs 24/24; k=32 33/15 vs 33/15. return-A: k=0
11/37 vs 5/43; k=2 12/36 vs 15/33; k=4 22/26 vs 13/35; k=8
29/19 vs 24/24; k=16 27/21 vs 16/32; k=32 29/19 vs 29/19.
B2: k=0 0/32 (16) vs 0/48; k=2 10/22 (16) vs 0/48; k=4
21/27 vs 1/47; k=8 20/12 (16) vs 19/29; k=16 38/10 vs
41/7; k=32 23/25 vs 23/25. Control: k=0 20/12 (16) vs
25/23; k=2 22/26 vs 22/26; k=4 16/32 vs 16/32; k=8 28/20
vs 28/20; k=16 16/16 (16) vs 20/28; k=32 36/12 vs 36/12.

Pooled onset (checkpoints 2 and 4): candidate 69 successes
/ 123 harm development and 72/120 additional, vs decisive
baseline 110/114 and 128/80, vs widened-removal 110/162 and
128/112 (= inverted on development; inverted 128/112
additional), vs widened-window 117/155 and 129/111, vs
guard 37/187 and 44/244, vs recent8 56/232 and 44/244. The
candidate differs from the decisive baseline in score at
5/72 development checkpoints and 9/72 additional checkpoints
(the 7 graded breadth differences plus ungraded differences
at additional B2 k=0 and k=8), from the preceding-pair
method at 14/72 and 18/72, and from the inverted method at
9/72 and 13/72. Past knowledge retention is graded by
checkpoint-32 and stationary behaviour above: criterion 5
passes both cohorts in full (the release side is repaired
on these draws), while the onset populations paid the
breadth price. Generalization level: at most handoff level
2–3, as registered — designer-supplied rules throughout; no
novel-representation claim.

## Safety and evidence costs

- Harmful TEST actions: pooled onset 123 development / 120
  additional (candidate), detailed per criterion above; B1
  pooled onset harm 31 / 9; B2 35 / 49; return-A 57 / 62;
  stationary control harm 91 / 106; checkpoint-32 harm 88
  development (= decisive = recent8) and 59 additional (vs
  decisive 53, recent8 59 — the release's +6 give-back).
- Failed-by-abstention: candidate onset abstentions 96/288
  on both cohorts; stationary 0/240 development and 16/240
  additional; checkpoint-32 0/144 on both. Two of leg W's
  development B2 stand-downs and one of its additional
  stand-downs fell through to abstentions (0 successes, 0
  harm at those states); the remaining stand-downs fell
  through to recent8 and are charged at recent8's realized
  outcomes per state above.
- Learner information-acquisition actions: 0 throughout.
  Additional requested observations: 0.
- External TRAIN actor costs (shared evidence stream,
  identical for all methods, published in full, never netted
  against TEST results): development — stage A 720 actions,
  236 actually harmful (234 reported harmful, 20 label
  flips); B1 192 actions, 70 harmful; B2 192, 77; return-A
  subset 144, 47; control continuation 192, 57. Additional —
  stage A 720 actions, 242 actually harmful (239 reported,
  25 flips); B1 192, 69; B2 192, 72; return-A subset 144,
  54; control continuation 192, 76.
- False confidence / unnecessary stand-downs: the cycle's
  characteristic error is the opposite of false confidence —
  leg W stood down ELEVEN graded onset firings of the
  decisive baseline across both cohorts (5 development, 6
  additional), every one a correct-rule firing (minority 5,
  regular 6), plus the one productive checkpoint-32 routing
  it released. The pre-registered onset price (pooled
  firing-level pass 0.725 raw / 0.520 adjusted) realized at
  or above its adjusted severity.
- Report integrity: all figures script-computed from the
  saved detailed results at `b36133c` in this grading stage;
  the 502003-family / 503001-family cohorts are INSPECTED
  and no parameter was re-tuned against them or any earlier
  cohort. One correction to the evaluation stage's raw
  notes: pooled per-cell onset harm on the additional cohort
  is <= recent8 in 5/6 cells, not 6/6 (the return-A k=2 cell
  is 36 vs recent8 33); criterion 3 still passes at its
  >= 5 line, and the grading above uses the pooled figures.

## Scientific conclusion

**Failed, NOT a Regression.** Failed under the protocol's
own definitions (PRIMARY criterion 16 FAILs on the
development cohort — its B2 side alone — and the Failed
clause triggers on the additional cohort several times over:
criteria 4 and 2 FAIL there, criterion 7 PASSes both).
Partially demonstrated does not apply (it requires
criterion 16 PASS on both cohorts). No Regression clause
triggers: pooled onset harm 123/120 is below recent8's
232/244 on both cohorts; stationary-control successes are
at exact parity on development and −4 on additional (the
clause requires more than 6 on BOTH); checkpoint-32
successes 56/85 sit above the recent8 − 4 lines of 52/81 on
both cohorts — criterion 5's repair removed this line's
checkpoint-32 Regression pattern on these draws; the full
unit suite and the historical transfer benchmark pass.

What the experiment actually establishes, stated as
prominently as the failure: leg W, the single changed
element, did exactly the release it was designed for at the
only checkpoint-32 routing these cohorts drew — additional
seed 503017, B2 k=32, acting minority count 1, released to
recent8 — so **the grading cap is MET via that state** (on
development the cap's population never occurred: no routing
was drawn at all). Criterion 5 PASSes on BOTH cohorts in
full, with criteria 9, 6, and 11 also passing on both. But
the released routing was productive (decisive 14/2 vs
released 8/8), and the leg's onset price was the cycle's
dominant fact: eleven graded onset stand-downs of
correct-rule firings, B2 minority engagement cut to 2/6 on
development (failing criterion 1 on count, on harm vs the
guard by 1, and on successes by 1) and return-A recovery cut
to 3/6 and 2/6, with the fall-throughs to recent8 pushing
return-A harm past the frozen ceiling on both cohorts
(criterion 4) and pooled onset harm ABOVE the decisive
baseline on both cohorts despite criterion 3 passing. An
acting-window breadth requirement strong enough to release
the wrong-rule-shaped checkpoint-32 population cannot
distinguish that population from correct-rule onset firings
at checkpoint 2, where the acting window is mostly
pre-switch evidence — the breadth signal arrives exactly
one switch too late.

**Next limitation (selected for the next cycle, Priority
1):** return-A onset harm — criterion 4 FAILs on BOTH
cohorts on sub-condition (b) alone (harm 57 vs ceiling 39.0
development, 62 vs ceiling 40.8 additional), the guard
comparison (a) PASSing on both (57 vs 58; 62 vs 68), and
its mechanism is entirely leg W's regular-branch
stand-downs at return-A onset (2 development states, both
k=2; 4 additional states; regular recovery TAKEN 3/6 and
2/6 vs the decisive baseline's 5/6 and 6/6; candidate
return-A harm 57/62 vs the decisive baseline's 36/28, every
stood-down state falling through to recent8). Measurable: on
NEW cohorts under a NEW protocol, whether an
evidence-derived condition on the regular recovery branch's
onset behaviour — its breadth composition or its fall-through
at return-A — can hold criterion 4's frozen form on BOTH
cohorts while holding checkpoint-32 release (criterion 5,
now passing on both with the cap met), B1 engagement
(criterion 9), stationary selectivity (criterion 6), and B2
protection (criterion 1) as co-graded guards. Recorded but
not selected: development's criterion 1 B2 failure is
single-cohort and narrow (harm and successes each short by
exactly 1, count cut by the same leg's minority stand-downs;
additional passes criterion 1 in full at the TAKEN floor) —
it is leg W's onset price on the minority branch, the mirror
of the selected mechanism on the regular branch, and is
carried as a guard; additional's criterion 2 failure is
driven by the same return-A stand-downs as the selected
limitation and is carried in its reporting; checkpoint-32
release now passes on both cohorts with the cap met, but its
exercised population across both cohorts was ONE productive
routing given back and an empty development population —
there is no release population left to retry on this
evidence; frozen_A and cumulative beat the candidate on
BOTH axes at return-A on both cohorts again.

Keep the learner optional and unpromoted, default controller
unchanged, no merge, no AthenZ/Synveil integration,
D1–D10/V2A/V2B unchanged.
