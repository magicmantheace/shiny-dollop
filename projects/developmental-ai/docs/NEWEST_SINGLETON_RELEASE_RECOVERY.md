# Newest singleton release recovery — a newest-singleton acting-corroboration release path (leg D) on the regular recovery branch

**12 November 2026 protocol frozen; 12 November 2026
implementation; 12 November 2026 evaluation; graded 12 November
2026. Status: optional, simulated, unpromoted. No
default-controller promotion, no PR merge, no D1–D10 or V2A/V2B
roadmap change, no AthenZ/Synveil integration.**

## Experiment identity

- **Name and purpose:** `newest_singleton_release_recovery`
  — whether ONE changed element, leg D, a NEWEST-SINGLETON
  ACTING-CORROBORATION RELEASE PATH on the REGULAR recovery
  branch only (the regular branch ALSO fires when
  newest_joint_count == 1 AND acting_joint_count >= 3, with
  NO new numeric threshold — the singleton condition is the
  exact complement of leg N's threshold 2 within the newest
  window and the corroboration threshold is leg W's graded
  acting_joint_threshold 3), can hold criterion 5's frozen
  checkpoint-32 release form on BOTH cohorts — the newest
  grading's selected limitation (criterion 5 FAILed
  development on sub-condition (d) alone and carried that
  cycle's Regression: k=32 successes 71 below the recent8 − 4
  line of 75; both traced to leg N's single exercised
  stand-down, development seed 512003 return-A k=32, newest
  1 / acting 3, stale 0, purity 0.714, decisive retained
  routing 10/6 released to a taken partial abstention 0/0)
  — while holding return-A onset harm (criteria 17/4, with
  leg N's restoration side carried), first-switch (B1)
  engagement (criterion 9), stationary selectivity
  (criterion 6), and B2 protection (criterion 1) as
  co-graded guards. Leg N, leg W (minority), leg T, leg P,
  leg R, and leg C were explicitly NOT re-tuned. Build
  Order Priority 1 (Independent Learning), items 2 + 3 + 4;
  handoff §8 slow or incorrect recovery of old knowledge /
  inconsistent adaptation to changing rules. This protocol's
  PRIMARY criterion is criterion 18, criterion 5's frozen
  checkpoint-32 release form promoted to PRIMARY; criteria
  5, 17, 4, 9, 6, 1, 11, 2, 3, and 7 are its co-graded
  guards. The protocol also froze a grading cap: a
  Demonstrated verdict additionally requires at least one
  checkpoint-32 state in at least one cohort at which the
  decisive baseline was disarmed by leg N
  (recovery_disarmed_by_newest_breadth true,
  newest_joint_count == 1, acting_joint_count >= 3) while
  the candidate fired the regular branch through leg D
  (singleton_release_fired true).
- **Candidate:** `NewestSingletonReleaseRecoveryMemory`
  (`developmental_ai/newest_singleton_release_recovery.py`)
  — IDENTICAL to the graded
  `NewestWindowJointBreadthRecoveryMemory` in every element
  (acting model recent8 exactly, extended signal, retained
  archive, archive concordance, joint test joint_count >= 1,
  recovery model, the full three-leg authority condition,
  the minority branch in full INCLUDING the inverted
  minority model and leg W on the minority branch, leg T on
  both recovery branches, leg P >= 0.70, leg R and leg C on
  partial abstention triggers, and the full /
  retained-partial abstention classes with the widened class
  removed records-only, support threshold null) — verified
  by a diff against the graded newest candidate at
  implementation: the ONLY code differences are leg D (the
  regular branch's added firing path above, computed from
  the already-recorded counts; the new decision-record
  field singleton_release_fired, recorded true exactly when
  the regular branch fires through leg D;
  recovery_disarmed_by_newest_breadth keeps its graded
  formula, so it remains true alongside a leg-D firing,
  exactly as leg W's regular flag remained set alongside
  leg-N firings in the graded newest candidate), its
  docstring, and names/schema. Separate optional learner;
  the default controller and all existing learners are
  untouched; the graded newest candidate appears only as
  the decisive baseline.
- **Branch and commits:**
  `developmental-ai/newest-singleton-release-recovery`
  (forked from `fc8b48d`, the newest grading commit).
  Protocol frozen at `203892f` (BEFORE implementation);
  implementation at `5413e28`; evaluation at `8330ac6`. This
  grading report is committed on top of the evaluation
  commit.
- **Frozen protocol:**
  `benchmarks/newest_singleton_release_recovery_protocol.json`
  (frozen 2026-11-12, before any implementation, unit test,
  harness, or score inspection for this experiment).
- **Cohorts:** development 522003/522021/522039 and
  additional 523001/523017/523041 — NEW at freeze, disjoint
  from every earlier cohort. Both cohorts are now
  **INSPECTED** and must never be re-tuned against.
- **Decisive baseline:** `newest_window_joint_breadth_recovery`
  (identical but for leg D on the regular branch; branch
  selection identical except at regular-branch states with
  newest_joint_count == 1 AND acting_joint_count >= 3 and
  every other carried condition met, where the candidate
  fires through leg D and the decisive baseline fell
  through). `recent8` is the simplest credible baseline and
  the candidate's own acting model.

## Verification

- Unit tests: PASS — 108/108 new candidate tests at
  implementation; full suite 1848 tests OK in the
  implementation and evaluation stages, and re-run in this
  grading stage: 1848 tests OK (`python3 -m unittest
  discover -s tests`, run 2026-11-12 this pass). The new
  tests include the discriminating states: the newest
  stand-down rows at newest count 1 / acting count exactly
  3 (decisive newest baseline stands down to recent8 with
  reason recovery_disarmed_by_newest_breadth, candidate
  FIRES retained_archive through leg D with
  singleton_release_fired true and the newest-breadth flag
  still true under its kept formula), and the
  singleton-zero rows at newest count 0 / acting count 3
  (leg D never fires at newest 0; candidate identical to
  the decisive baseline after stripping the singleton
  field).
- Historical regressions: PASS — historical transfer
  benchmark (`python3 -m benchmarks.transfer_benchmark`)
  exit 0 in the evaluation stage and re-run in this grading
  stage, standard three-seed output (success gains 0.5567 /
  0.50 / 0.51 on seeds 17 / 23 / 41).
- Frozen cohorts: PASS (run exactly as registered) — both
  cohorts evaluated at `8330ac6`; every checkpoint entry
  carries per-method successes / harmful TEST actions /
  abstentions / attempted tasks, the candidate's full
  decision record (including the full singleton, newest-
  breadth, acting-breadth, companion, and stale records),
  checkpoint SHA256, and restore-replay identity
  (script-verified in this grading stage: true at every
  checkpoint in both cohorts, 72/72 entries per cohort).
- Linux validation: UNVERIFIED (no GitHub Actions run on
  the grading commit was checked; no CI is claimed).
- Windows validation: UNVERIFIED (same).

## Per-criterion grading (precommitted, graded individually, per cohort)

Graded script-computed from the saved detailed results at
`8330ac6` (grading script and output kept with the campaign
records). PRIMARY criterion 18 first, then co-graded guards
5, 9, 6, 1, 11, 17, 4, 2, 3, 7. Development / additional
throughout.

**Criterion 18 — PRIMARY (checkpoint-32 release, criterion
5's frozen form): PASS / PASS — as a carried profile, with
a singleton-release null result at checkpoint 32.** All
four sub-conditions pass on both cohorts: (a) abstentions
0/144 on both; (b) successes at EXACT recent8 parity on
both — development 58 = recent8 58 (line 50), additional
71 = recent8 71 (line 63); (c) non-recent8 branch in 0/9
states on both; (d) abstained branch in 0/9 states on both.
But the pass demonstrates nothing about leg D at
checkpoint 32, and the report says so in those words: **a
carried-profile pass with a singleton-release null result
at checkpoint 32 — the leg demonstrated nothing there on
these draws.** Neither cohort drew ANY checkpoint-32
recovery routing at all: all nine k=32 states per cohort
are recent8 in the candidate, the decisive baseline, AND
recent8 itself (candidate k=32 pooled successes/harm
58/86 development and 71/73 additional, identical under
all three methods), every state's firing path is
"neither", and leg D fired ZERO times at checkpoint 32 on
either cohort — **the grading cap is NOT MET on either
cohort.** Leg D's designed checkpoint-32 release
population (newest 1 / acting >= 3 with every other
carried condition met, the shape of the newest cycle's
512003 state) simply did not occur on these draws. Leg D's
ONLY firing anywhere in either cohort was at ONE ungraded
state — additional seed 523001, return-A, checkpoint 16
(newest 1 / acting 3, stale 1, purity 0.707): the
candidate fired retained_archive through leg D (10/6)
where the decisive baseline took a partial abstention
(0/0) and recent8 scored 4/12 — a productive release at
k=16 that is NOT a checkpoint-32 release and is not
counted toward the cap. On development leg D never fired
at any checkpoint (candidate score-identical to the
decisive baseline at 0/72 differing checkpoints; additional
1/72, the k=16 state alone). All nine k=32 states per
cohort (branch; kind; purity; stale regular/minority;
acting regular/minority; newest; candidate = decisive =
recent8 throughout): development — 522003 B1 recent8
(none, 0.742, 0/0, 0/1, newest 0, 11/5); 522003 return-A
recent8 (partial, 0.697, 0/0, 1/2, 0, 1/15); 522003 B2
recent8 (none, 0.680, 0/0, 0/0, 0, 7/9); 522021 B1 recent8
(partial, 0.750, 0/0, 1/0, 1, 2/14); 522021 return-A
recent8 (none, 0.621, 2/0, 1/0, 0, 2/14); 522021 B2
recent8 (none, 0.780, 0/0, 0/1, 0, 16/0); 522039 B1
recent8 (none, 0.759, 0/0, 1/0, 0, 0/16); 522039 return-A
recent8 (full, 0.647, 1/0, 5/1, 4, 6/10); 522039 B2
recent8 (none, 0.767, 0/0, 1/0, 0, 13/3). Additional —
523001 B1 recent8 (none, 0.607, 0/0, 0/2, 0, 8/8); 523001
return-A recent8 (none, 0.795, 0/0, 0/0, 0, 8/8); 523001
B2 recent8 (partial, 0.645, 0/0, 0/4, 0, 3/13); 523017 B1
recent8 (none, 0.722, 0/0, 0/0, 0, 11/5); 523017 return-A
recent8 (none, 0.647, 0/0, 0/1, 0, 8/8); 523017 B2
recent8 (none, 0.727, 0/0, 0/0, 0, 9/7); 523041 B1
recent8 (full, 0.758, 0/0, 2/4, 1, 0/16); 523041 return-A
recent8 (full, 0.683, 0/1, 0/2, 0, 10/6); 523041 B2
recent8 (partial, 0.649, 0/0, 1/0, 1, 14/2). Leg T
disarmed ZERO states on either cohort for the fifth
consecutive cycle.

**Criterion 5 — release and productivity by checkpoint 32
(guard position): PASS / PASS.** The same computation as
PRIMARY criterion 18, reported twice as registered, never
two thresholds: abstentions 0/144, successes at exact
recent8 parity (58/71), non-recent8 0/9, abstained 0/9 on
both cohorts — a carried-profile pass with the same
singleton-release null result stated under criterion 18.

**Criterion 9 — first-switch (B1) engagement: PASS /
PASS.** Leg D touched no B1 state on either cohort — the
candidate is identical to the decisive baseline at every
B1 state. Development: abstention TAKEN at 4/6 pooled B1
onset states (2 full + 2 retained partial, the partials
armed through leg R AND leg C, and leg R alone), harm 20
<= guard 49 (b) and 20 < recent8 81 (c). B1 successes 12
vs recent8 15 / guard 15, stated in full. Additional:
TAKEN 4/6 (2 full + 2 retained partial, the partials armed
through leg C alone, and leg R AND leg C), harm 29 <=
guard 72 and 29 < recent8 87. B1 successes 3 vs recent8 9
/ guard 8, stated in full.

**Criterion 6 — stationary control selectivity: FAIL /
FAIL.** Both failures are carried draws leg D does not
touch (candidate branch-identical to the decisive baseline
at 15/15 graded control states on both cohorts; on the
stationary arm the joint rate is 0 in the published-rate
model, so leg D is inert there in expectation, as legs N,
T, C, and W were). Development FAILs on sub-condition (b)
alone: (a) abstentions 32/240 AT the <= 32 budget PASS;
(b) successes 86 vs recent8 94, required >= 88, FAIL by 2;
(c) harm 122 vs recent8 146 PASS. The two carried control
abstention firings are seed 522003 k=2 (partial through
leg C, purity 0.868) and seed 522003 k=8 (full, purity
0.889), each 0/0 vs recent8 5/11 and 3/13 at its state.
Additional FAILs on (a) AND (b): abstentions 48/240
against the <= 32 budget FAIL; successes 89 vs recent8
101, required >= 95, FAIL by 6; harm 103 vs recent8 139
PASS. Its three carried firings are seed 523001 k=2
(partial through leg C, purity 0.846), seed 523001 k=4
(partial, purity 0.846), and seed 523041 k=32 (partial,
purity 0.886), each 0/0 vs recent8 10/6, 2/14, and 0/16
respectively. These two failures carry this cycle's
Regression (below).

**Criterion 1 — second-switch (B2) protection: FAIL /
FAIL.** Both failures are carried draws identical to the
decisive baseline (the minority branch is bit-for-bit the
baseline's, leg W included; leg D pre-empted and exposed
nothing at B2 at any graded state). Development FAILs on
(a) AND (d): minority TAKEN 1/6 (a) FAIL — the other five
states are two taken abstentions (both minority
breadth-disarmed fall-throughs carried from the baseline)
and three recent8; (b) selectivity 0/6 at B1 and 0/6 at
return-A PASS; (c) harm 52 vs guard 91 and ceiling 0.60 ×
recent8 91 = 54.6 PASS both; (d) successes 12 vs guard 5 +
16 = 21 FAIL. Additional FAILs on (a) alone: minority
TAKEN 2/6, one short of the floor (the other four states
are four taken abstentions, three of them minority
breadth-disarmed fall-throughs carried from the baseline);
selectivity 0/6 / 0/6 PASS; harm 13 vs guard 48 and
ceiling 0.60 × recent8 93 = 55.8 PASS both; successes 19
vs guard 0 + 16 = 16 PASS. The minority-model cross-check
PASSes at every minority-fired state (2 development / 3
additional applicable) with first-frame choices differing
from the widened-window method at 1/1 development and 2/2
additional minority-fired B2 onset states checked.

**Criterion 11 — B1/stationary conjunction (carried):
FAIL / FAIL.** Both cohorts fail on their stationary side
alone (criterion 6 above; both B1 sides pass).

**Criterion 17 — return-A onset harm (PRIMARY of the
preceding cycle, guard position): FAIL / PASS.**
Development FAILs on sub-condition (b) alone: harm 70 vs
guard 84 PASS on (a), but ceiling 0.60 × recent8 84 =
50.4 FAIL on (b) — identical to the decisive baseline at
every return-A onset state (regular recovery TAKEN 2/6
under both methods; pooled onset identical to decisive on
development, 50 successes / 142 harm). Additional PASSes
in full: harm 37 vs guard 60 and ceiling 0.60 × recent8
88 = 52.8, regular recovery TAKEN 5/6, likewise identical
to the decisive baseline at every graded return-A state.
Per-state return-A onset reporting (seed, checkpoint;
candidate branch = decisive branch throughout; newest /
acting counts; purity; candidate = decisive vs recent8
successes/harm): development — 522003 k=2 retained (2/3,
0.906; 10/6, recent8 6/10); 522003 k=4 recent8 (1/2,
0.875; 6/10 =); 522021 k=2 retained (2/2, 0.886; 10/6,
recent8 0/16; leg W breadth-disarmed records-only in both
methods, fired through leg N); 522021 k=4 recent8 (0/1,
0.882; 0/16 =); 522039 k=2 recent8 (1/1, 0.917; 0/16 =);
522039 k=4 recent8 (1/1, 0.895; 0/16 =). Additional —
523001 k=2 retained (3/3, 0.775; 11/5, recent8 0/16);
523001 k=4 retained (4/5, 0.750; 10/6, recent8 3/13);
523017 k=2 recent8 (1/1, 0.886; 0/16 =); 523017 k=4
retained (3/3, 0.882; 14/2, recent8 3/13); 523041 k=2
retained (2/3, 0.789; 12/4, recent8 1/15); 523041 k=4
retained (2/3, 0.750; 12/4, recent8 1/15).

**Criterion 4 — return-A onset harm (guard position):
FAIL / PASS.** The same computation as criterion 17,
reported twice as registered, never two thresholds:
development FAILs on the ceiling (b) alone (70 vs guard
84 PASS, ceiling 50.4 FAIL); additional PASSes in full
(37 vs guard 60 / ceiling 52.8).

**Criterion 2 — return-A recovery successes: FAIL /
PASS.** Development: successes 26 vs frozen_A 56 (floor
40% = 22.4) PASS on (a) but guard 12 + 16 = 28 FAIL on
(b) by 2. Additional: successes 59 vs frozen_A 62 (floor
24.8) PASS on (a) and guard 4 + 16 = 20 PASS on (b).
Stated in full, as registered: frozen_A beats the
candidate on BOTH axes at return-A on development (56/40
vs candidate 26/70) and cumulative does the same (68/28);
on additional, frozen_A (62/34) and cumulative (72/24)
both sit above the candidate's 59 successes with lower
harm than its 37 — both-axes dominance on both cohorts
again, in successes-and-harm terms on additional despite
criterion 2's PASS there.

**Criterion 3 — pooled onset harm: PASS / PASS.** Pooled
onset harm 142 vs guard 224 development and 79 vs guard
180 additional (a); individual onset cells <= recent8 in
6/6 on both cohorts (b). Stated in full: pooled onset is
IDENTICAL to the decisive baseline's on both cohorts at
graded checkpoints (50/142 development, 81/79 additional)
— leg D's sole firing is at ungraded checkpoint 16 and
enters no pooled onset figure.

**Criterion 7 — full accounting: PASS / PASS.** Replay
identity true at every checkpoint in both cohorts (72/72
entries per cohort); no criterion-7 field missing
anywhere; support_threshold null everywhere;
companion_threshold null everywhere;
abstention_disarmed_by_support false everywhere;
widened_threshold 3, staleness_pair_threshold 2,
preceding_pair_threshold 1, acting_joint_threshold 3, and
newest_joint_threshold 2 everywhere; abstention gate
recomputable everywhere (incl. the leg-C composition)
with 0 mismatches; companion fields recomputable at every
partial state (30 development / 26 additional) and at
fallback at every non-partial state (42 / 46); stale lists
of 18 with both pair counts recomputable everywhere with
0 mismatches; acting lists of 8 with both acting counts
recomputable everywhere with 0 mismatches; newest lists
of 4 with the newest count recomputable everywhere with
0 mismatches and newest records == acting records' last
four everywhere; both acting breadth flags, the newest
breadth flag, singleton_release_fired, and the
recovery_fired (leg N OR leg D) composition recomputed
everywhere with 0 mismatches; singleton-rule == candidate
branch everywhere; newest-breadth-rule == decisive
baseline branch everywhere; acting-breadth-rule == acting
branch everywhere; companion-rule == companion branch
everywhere; pre-acting-release-rule == pre-acting branch
everywhere; preceding-pair-rule == widened-removal-rule
everywhere; widened-rule == inverted branch everywhere;
newest4 / widened_armed recomputable everywhere;
abstention_trigger_kind in {full, partial, none}
everywhere — never widened, as the carried removal
requires; minority_model_archive_count ==
archive_events_count everywhere; minority_model_inverted
true everywhere; minority-model cross-check PASS at every
minority-fired state (2/2 development, 3/3 additional
applicable); learner acquisition actions 0 throughout.

## Learning evaluation

Candidate vs recent8 (simplest credible baseline),
successes / harmful TEST actions per stage-checkpoint cell
(candidate first; abstentions in parentheses where
nonzero):

Development — B1: k=0 0/48 vs 0/48; k=2 3/13 (32) vs 3/45;
k=4 9/7 (32) vs 12/36; k=8 1/15 (32) vs 14/34; k=16 1/15
(32) vs 1/47; k=32 13/35 vs 13/35. return-A: k=0 6/42 vs
6/42; k=2 20/28 vs 6/42; k=4 6/42 vs 6/42; k=8 22/26 vs
6/42; k=16 34/14 vs 22/26; k=32 9/39 vs 9/39. B2: k=0
0/48 vs 0/48; k=2 11/21 (16) vs 2/46; k=4 1/31 (16) vs
3/45; k=8 23/9 (16) vs 22/26; k=16 25/23 vs 25/23; k=32
36/12 vs 36/12. Control: k=0 18/30 vs 18/30; k=2 13/19
(16) vs 18/30; k=4 23/25 vs 23/25; k=8 14/18 (16) vs
17/31; k=16 18/30 vs 18/30; k=32 18/30 vs 18/30.

Additional — B1: k=0 1/47 vs 1/47; k=2 0/16 (32) vs 2/46;
k=4 3/13 (32) vs 7/41; k=8 7/25 (16) vs 18/30; k=16 27/21
vs 27/21; k=32 19/29 vs 19/29. return-A: k=0 5/43 vs
5/43; k=2 23/25 vs 1/47; k=4 36/12 vs 7/41; k=8 37/11 vs
31/17; k=16 29/19 vs 23/25; k=32 26/22 vs 26/22. B2: k=0
1/47 vs 1/47; k=2 0/0 (48) vs 1/47; k=4 19/13 (16) vs
2/46; k=8 17/15 (16) vs 22/26; k=16 21/11 (16) vs 21/27;
k=32 26/22 vs 26/22. Control: k=0 20/28 vs 20/28; k=2
15/17 (16) vs 25/23; k=4 18/14 (16) vs 20/28; k=8 22/26
vs 22/26; k=16 19/29 vs 19/29; k=32 15/17 (16) vs 15/33.

Pooled onset (checkpoints 2 and 4): candidate 50
successes / 142 harm development and 81/79 additional, vs
decisive baseline 50/142 and 81/79 (identical at graded
checkpoints), vs companion 58/150 and 90/142, vs
widened-removal 88/165 and 90/134 (= inverted additional;
inverted 88/165 development), vs widened-window 93/161
and 89/135, vs guard 32/224 and 20/180, vs recent8 32/256
and 20/268. The candidate differs from the decisive
baseline in score at 0/72 development checkpoints and
1/72 additional checkpoints (the ungraded k=16 leg-D
firing alone), from the companion method at 8/72 and
9/72, and from the inverted method at 12/72 and 17/72.
Past knowledge retention is graded by checkpoint-32 and
stationary behaviour above: checkpoint 32 drew no routing
at all on either cohort, and the stationary arm carried
five abstention firings across both cohorts identical to
the decisive baseline's, carrying the Regression (below).
Generalization level: at most handoff level 2–3, as
registered — designer-supplied rules throughout; no
novel-representation claim.

## Safety and evidence costs

- Harmful TEST actions: pooled onset 142 development /
  79 additional (candidate), detailed per criterion above;
  B1 pooled onset harm 20 / 29; B2 52 / 13; return-A 70 /
  37; stationary control harm 122 / 103; checkpoint-32
  harm 86 development and 73 additional (= decisive =
  recent8 on both).
- Failed-by-abstention: candidate onset abstentions
  96/288 development and 128/288 additional; stationary
  32/240 development and 48/240 additional; checkpoint-32
  0/144 on both.
- Learner information-acquisition actions: 0 throughout.
  Additional requested observations: 0.
- External TRAIN actor costs (shared evidence stream,
  identical for all methods, published in full, never
  netted against TEST results): development — stage A 720
  actions, 248 actually harmful (258 reported harmful, 22
  label flips); B1 192 actions, 75 harmful; B2 192, 85;
  return-A subset 144, 62; control continuation 192, 71.
  Additional — stage A 720 actions, 255 actually harmful
  (251 reported, 16 flips); B1 192, 67; B2 192, 67;
  return-A subset 144, 53; control continuation 192, 72.
- False confidence / unnecessary stand-downs: leg D fired
  exactly once in either cohort, at an ungraded checkpoint,
  and that firing was productive (10/6 against an
  abstention's 0/0). Its designed checkpoint-32 population
  did not occur. Leg T disarmed zero states for the fifth
  consecutive cycle.
- Report integrity: all figures script-computed from the
  saved detailed results at `8330ac6` in this grading
  stage; the 522003-family / 523001-family cohorts are
  INSPECTED and no parameter was re-tuned against them or
  any earlier cohort.

## Scientific conclusion

**Failed / Regression (stationary clause).** Failed under
the protocol's own definitions (PRIMARY criterion 18
PASSes on BOTH cohorts — but as a carried profile with a
singleton-release null result, cap NOT MET — and the
Failed clause triggers on the additional cohort several
times over: criteria 6, 1, and 11 FAIL there, criterion 7
PASSes both). Partially demonstrated does not rescue the
verdict: its cap clause caps a Demonstrated verdict at
Partially demonstrated, it does not override the Failed
clause, which triggers independently on the additional
cohort. A Regression clause DOES trigger — the stationary
clause: stationary-control successes fall below recent8's
by more than 6 on BOTH cohorts (development 86 vs 94,
−8; additional 89 vs 101, −12), on carried abstention
firings identical to the decisive baseline's. The other
Regression clauses do not trigger: pooled onset harm
142/79 is below recent8's 256/268 on both cohorts;
checkpoint-32 successes 58/71 sit at exact recent8 parity,
above the recent8 − 4 lines of 54/67; the full unit suite
and the historical transfer benchmark pass.

What the experiment actually establishes, stated as
prominently as the failure: the frozen checkpoint-32
release form HELD on both cohorts for the first time as a
PRIMARY (criteria 18/5 PASS/PASS, abstentions 0/144,
non-recent8 0/9, abstained 0/9, successes at exact recent8
parity) — but it held vacuously. Neither cohort drew a
single checkpoint-32 routing, so the form was never
exposed to the population it governs, and leg D — the
changed element — demonstrated nothing at checkpoint 32
on these draws: a carried-profile pass with a
singleton-release null result. The leg's one firing, at
ungraded additional checkpoint 16, was productive and of
exactly the designed shape (newest 1 / acting 3, decisive
abstention 0/0 → candidate retained 10/6), which is
evidence the path CAN fire correctly — at persistence
depth, on one state, ungraded. Everything else in the
profile is the decisive baseline's, bit-for-bit at graded
checkpoints: B1 engagement passes both (leg C carried),
return-A harm passes additional in full and fails
development on the ceiling alone, and the two
both-cohort guard failures — stationary selectivity and
B2 protection — are carried draws whose mechanisms (the
abstention classes' stationary firings; the minority
branch's engagement draw) no leg in the breadth line
touches. The breadth line has now spent four cycles on
the regular branch's firing conditions; on these draws
its remaining failures live elsewhere.

**Next limitation (selected for the next cycle, Priority
1):** stationary selectivity of the carried abstention
classes — criterion 6 FAILs on BOTH cohorts (development
on successes alone, 86 vs the >= 88 line, with volume AT
the budget; additional on volume AND successes, 48/240
against the <= 32 budget and 89 vs the >= 95 line) and it
carries this cycle's Regression (control successes −8 /
−12, both past the −6 clause), on five carried abstention
firings across both cohorts (2 development, 3 additional;
partial through leg C, partial, and full kinds; purity
0.846–0.889) that are identical to the decisive
baseline's, on an arm where every breadth/release leg is
inert in expectation. Measurable: on NEW cohorts under a
NEW protocol, whether an evidence-derived condition on
the abstention classes themselves can hold criterion 6's
frozen form on BOTH cohorts while holding B1 engagement
(criterion 9, PASSing both — the same classes at onset, so
a stationary tightening must not give B1 back),
checkpoint-32 release (criteria 18/5, PASSing both as a
carried profile), B2 protection (criterion 1), and
return-A profiles (criteria 17/4/2) as co-graded guards.
Recorded but not selected: criterion 1 FAILs on both
cohorts as well (minority 1/6 development with successes
also failing, 2/6 additional on the count alone) — a
carried engagement draw identical to the decisive
baseline's, with harm passing both comparisons on both
cohorts; it is carried as a co-graded guard, and a B2
retry needs an engagement population these draws do not
identify. Development's criteria 17/4 failure is the
return-A ceiling alone at fully carried states with
additional passing in full, and its criterion 2 failure
is the guard comparison alone by 2 — both single-cohort
and carried. Checkpoint-32 release PASSes both but with
zero routings drawn on either cohort there is no release
population to retry; leg D's single productive k=16
firing is recorded, not a graded population.
Frozen_A / cumulative both-axes return-A dominance holds
on both cohorts again.

Keep the learner optional and unpromoted, default
controller unchanged, no merge, no AthenZ/Synveil
integration, D1–D10/V2A/V2B unchanged.
