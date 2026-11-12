# Newest window joint breadth recovery — a newest-window joint-breadth leg (leg N) replacing leg W on the regular recovery branch

**11 November 2026 protocol frozen; 11 November 2026
implementation; 11 November 2026 evaluation; graded 11 November
2026. Status: optional, simulated, unpromoted. No
default-controller promotion, no PR merge, no D1–D10 or V2A/V2B
roadmap change, no AthenZ/Synveil integration.**

## Experiment identity

- **Name and purpose:** `newest_window_joint_breadth_recovery`
  — whether ONE changed element, leg N, a NEWEST-WINDOW
  JOINT-BREADTH LEG replacing leg W on the REGULAR recovery
  branch only (the regular branch fires only if its joint
  count over the newest four events events[-4:] reaches
  newest_joint_threshold 2; leg W carried unchanged on the
  minority branch and records-only on the regular branch),
  can hold criterion 4's frozen return-A onset harm form on
  BOTH cohorts — the acting cycle's selected limitation
  (criterion 4 FAILed on BOTH cohorts there on the ceiling
  sub-condition (b) alone — development harm 57 vs ceiling
  39.0, additional 62 vs ceiling 40.8 — with the guard
  comparison (a) PASSing both, its mechanism entirely leg
  W's regular-branch stand-downs at return-A onset falling
  through to recent8) — while holding checkpoint-32 release
  (criterion 5, passing on both in the acting cycle with its
  grading cap met), first-switch (B1) engagement (criterion
  9), stationary selectivity (criterion 6), and B2
  protection (criterion 1) as co-graded guards. Leg P, leg
  R, leg T, and leg C were explicitly NOT re-tuned. Build
  Order Priority 1 (Independent Learning), items 2 + 3 + 4;
  handoff §8 slow or incorrect recovery of old knowledge /
  inconsistent adaptation to changing rules. This protocol's
  PRIMARY criterion is criterion 17, criterion 4's frozen
  return-A onset harm form promoted to PRIMARY; criteria 5,
  9, 6, 1, 11, 4, 2, 3, and 7 are its co-graded guards. The
  protocol also froze a grading cap: a Demonstrated verdict
  additionally requires at least one return-A onset state in
  at least one cohort at which the decisive baseline fell
  through from the regular branch through leg W
  (acting_joint_count < 3, every other carried condition
  met) while the candidate fired the regular branch through
  leg N (newest_joint_count >= 2).
- **Candidate:** `NewestWindowJointBreadthRecoveryMemory`
  (`developmental_ai/newest_window_joint_breadth_recovery.py`)
  — IDENTICAL to the graded
  `ActingWindowJointBreadthRecoveryMemory` in every element
  (acting model recent8 exactly, extended signal, retained
  archive, archive concordance, joint test joint_count >= 1,
  recovery model, the full three-leg authority condition,
  the minority branch in full INCLUDING the inverted
  minority model and leg W on the minority branch, leg T on
  both recovery branches, leg P >= 0.70, leg R and leg C on
  partial abstention triggers, and the full /
  retained-partial abstention classes with the widened class
  removed records-only, support threshold null) — verified
  by a diff against the graded acting candidate at
  implementation: the ONLY code differences are leg N (the
  per-event newest joint records over events[-4:],
  newest_joint_count, newest_joint_threshold 2, the regular
  branch's firing condition newest_joint_count >= 2
  REPLACING leg W's acting_joint_count >= 3 for that branch,
  recovery_disarmed_by_newest_breadth recorded only when
  joint, arming, leg P, leg T, and leg W's records-only count
  all pass; leg W's acting records and
  recovery_disarmed_by_acting_breadth keep their graded
  formulas, computed and recorded RECORDS-ONLY for the
  regular branch), its docstring, and names/schema. Separate
  optional learner; the default controller and all existing
  learners are untouched; the graded acting candidate
  appears only as the decisive baseline.
- **Branch and commits:**
  `developmental-ai/newest-window-joint-breadth-recovery`
  (forked from `197bb33`, the acting grading commit).
  Protocol frozen at `386a801` (BEFORE implementation);
  implementation at `46eec47`; evaluation at `60a13af`. This
  grading report is committed on top of the evaluation
  commit.
- **Frozen protocol:**
  `benchmarks/newest_window_joint_breadth_recovery_protocol.json`
  (frozen 2026-11-11, before any implementation, unit test,
  harness, or score inspection for this experiment).
- **Cohorts:** development 512003/512021/512039 and
  additional 513001/513017/513041 — NEW at freeze, disjoint
  from every earlier cohort. Both cohorts are now
  **INSPECTED** and must never be re-tuned against.
- **Decisive baseline:** `acting_window_joint_breadth_recovery`
  (identical but for leg N on the regular branch; branch
  selection identical except at states where the regular
  branch met every carried condition and exactly one of leg
  W's acting count >= 3 and leg N's newest count >= 2
  holds). `recent8` is the simplest credible baseline and
  the candidate's own acting model.

## Verification

- Unit tests: PASS — 98/98 new candidate tests at
  implementation; full suite 1740 tests OK in the
  implementation and evaluation stages, and re-run in this
  grading stage: 1740 tests OK (`python3 -m unittest
  discover -s tests`, run 2026-11-11 this pass). The new
  tests include the discriminating states: the
  purity-armed recovery rows at acting count 2 / newest
  count 2 (decisive baseline stands down to recent8 through
  leg W, candidate FIRES retained_archive through leg N),
  and the newest stand-down rows at acting count 3 / newest
  count 1 (decisive baseline FIRES retained_archive,
  candidate stands down to recent8 with reason
  recovery_disarmed_by_newest_breadth).
- Historical regressions: PASS — historical transfer
  benchmark (`python3 -m benchmarks.transfer_benchmark`)
  exit 0 in the evaluation stage and re-run in this grading
  stage, standard three-seed output (success gains 0.5567 /
  0.50 / 0.51 on seeds 17 / 23 / 41).
- Frozen cohorts: PASS (run exactly as registered) — both
  cohorts evaluated at `60a13af`; every checkpoint entry
  carries per-method successes / harmful TEST actions /
  abstentions / attempted tasks, the candidate's full
  decision record (including the full newest-breadth,
  acting-breadth, companion, and stale records), checkpoint
  SHA256, and restore-replay identity (script-verified in
  this grading stage: true at every checkpoint in both
  cohorts, 72/72 entries per cohort).
- Linux validation: UNVERIFIED (no GitHub Actions run on
  the grading commit was checked; no CI is claimed).
- Windows validation: UNVERIFIED (same).

## Per-criterion grading (precommitted, graded individually, per cohort)

Graded script-computed from the saved detailed results at
`60a13af` (grading script and output kept with the campaign
records). PRIMARY criterion 17 first, then co-graded guards
5, 9, 6, 1, 11, 4, 2, 3, 7. Development / additional
throughout.

**Criterion 17 — PRIMARY (return-A onset harm, criterion
4's frozen form): FAIL / FAIL.** Development FAILs on
sub-condition (b) alone: harm 52 vs guard 65 PASS on (a),
but ceiling 0.60 × recent8 80 = 48.0 FAIL on (b) — despite
development's three leg-N restorations being worth +24
successes / −24 harm against the decisive baseline on the
pooled return-A line (below). Additional FAILs on BOTH
sub-conditions: harm 76 vs guard 67 FAIL on (a) and ceiling
0.60 × recent8 83 = 49.8 FAIL on (b). Per-state return-A
onset reporting (seed, checkpoint; candidate branch vs
decisive branch; newest / acting counts; purity; candidate
vs decisive vs recent8 successes/harm): development —
512003 k=2 retained (5/4, 0.889; 8/8 = decisive, recent8
4/12); 512003 k=4 retained (2/4, 0.853; 8/8 =); 512021 k=2
recent8, leg W breadth-disarmed in BOTH methods (1/2,
0.857; 0/16 =); 512021 k=4 **restored through leg N**
(decisive recent8 → candidate retained_archive; 2/2,
0.833; candidate 10/6 vs decisive / recent8 3/13); 512039
k=2 **restored** (2/2, 0.927; 9/7 vs 1/15); 512039 k=4
**restored** (2/2, 0.900; 9/7 vs 0/16). Additional —
513001 k=2 recent8 (1/1, 0.976; 5/11 =); 513001 k=4 recent8
(1/1, 0.951; 6/10 =); 513017 k=2 recent8 (0/1, 0.778; 1/15
=); 513017 k=4 recent8 (1/2, 0.769; 1/15 =); 513041 k=2
recent8 (0/0, 0.972; 0/16 =); 513041 k=4 **restored through
leg N** (decisive ABSTAINED, full trigger → candidate
retained_archive; 2/2, 0.971; candidate 7/9 vs decisive
abstention 0/0, recent8 0/16 there). The restoration
population EXISTS on both cohorts — **the grading cap is
MET (3 graded restorations development, 1 additional, plus
one further restoration at ungraded additional checkpoint
16, 513001 return-A, candidate 8/8 vs decisive abstained
0/0)** — so this is not a newest-breadth null; the cap's
satisfaction does not rescue the verdict, because the
harm lines still fail as above, and what each restoration
was worth is charged in full: development's three were
each productive against their recent8 fall-throughs, and
additional's one converted an abstention's 0 harm into a
7/9 firing.

**Criterion 5 — release and productivity by checkpoint
32: FAIL / PASS.** Development FAILs on sub-condition (d)
alone: (a) abstentions 16/144 PASS; (b) successes 71 at
EXACTLY the recent8 − 8 line (recent8 79) PASS; (c)
non-recent8 branch in 1/9 states, at the allowance, PASS;
(d) abstained branch in 1/9 states against the frozen 0/9
FAIL. That one state is leg N's stand-down side, exercised
exactly ONCE across both cohorts: seed 512003, return-A
k=32, newest count 1 / acting count 3, stale count 0,
purity 0.714 — the candidate released the decisive
baseline's retained_archive routing (decisive 10/6,
recent8 8/8) and fell through to a taken partial
abstention (0/0). Candidate k=32 pooled line development:
successes/harm 71/57 vs decisive 81/63 vs recent8 79/65 —
the release cost 10 successes against the decisive
baseline at that single state and pushed the cohort's
k=32 successes 8 below recent8's (see the Regression
clause below). Additional PASSes in full: abstentions
0/144, successes 81 = recent8 81, non-recent8 0/9,
abstained 0/9 — no checkpoint-32 routing drawn at all,
candidate identical to the decisive baseline at all nine
states. All nine k=32 states per cohort (branch; kind;
purity; stale regular/minority; acting regular/minority;
newest; candidate vs decisive vs recent8 — identical
triples abbreviated =): development — 512003 B1 recent8
(partial, 0.697, 0/0, 1/0, newest 1, 13/3 =); 512003
return-A **released through leg N** (decisive
retained_archive → candidate abstained, partial; 0.714,
0/0, 3/1, newest 1, newest-disarmed; candidate 0/0,
decisive 10/6, recent8 8/8); 512003 B2 recent8 (none,
0.676, 0/0, 0/1, 0, 10/6 =); 512021 B1 recent8 (partial,
0.694, 0/0, 1/1, 1, 0/16 =); 512021 return-A recent8 (none,
0.647, 0/0, 1/0, 1, 8/8 =); 512021 B2 recent8 (none, 0.651,
0/0, 0/1, 0, 11/5 =); 512039 B1 recent8 (partial, 0.718,
0/0, 0/4, 0, 10/6 =); 512039 return-A recent8 (none, 0.679,
0/0, 1/0, 0, 6/10 =); 512039 B2 recent8 (partial, 0.704,
0/0, 0/2, 0, 13/3 =). Additional — 513001 B1 recent8
(none, 0.750, 0/0, 0/0, 0, 13/3 =); 513001 return-A recent8
(partial, 0.639, 0/0, 2/1, 0, 5/11 =); 513001 B2 recent8
(none, 0.686, 0/0, 0/0, 0, 12/4 =); 513017 B1 recent8
(partial, 0.625, 0/0, 1/0, 1, 0/16 =); 513017 return-A
recent8 (none, 0.765, 0/0, 0/0, 0, 13/3 =); 513017 B2
recent8 (partial, 0.684, 0/0, 0/3, 0, 11/5 =); 513041 B1
recent8 (none, 0.696, 0/0, 0/0, 0, 3/13 =); 513041
return-A recent8 (partial, 0.655, 0/0, 2/0, 1, 12/4 =);
513041 B2 recent8 (none, 0.656, 0/0, 0/0, 0, 12/4 =). Leg
T disarmed ZERO states on either cohort for the fourth
consecutive cycle.

**Criterion 9 — first-switch (B1) engagement: PASS /
PASS.** Leg N touched no B1 state on either cohort — the
candidate is identical to the decisive baseline at every
B1 state. Development: abstention TAKEN at 3/6 pooled B1
onset states, AT the floor (1 full + 2 retained partial,
both partials armed through leg C only — preceding 0,
companion armed), harm 47 <= guard 74 (b) and 47 < recent8
79 (c). B1 successes 1 vs recent8 17 / guard 6, stated in
full. Additional: TAKEN 4/6 (3 full + 1 retained partial,
the partial armed through leg R AND leg C both), harm 32
<= guard 42 and 32 < recent8 64. B1 successes 0 vs recent8
32 / guard 22, stated in full.

**Criterion 6 — stationary control selectivity: FAIL /
PASS.** Development FAILs on TWO sub-conditions on a
carried draw leg N does not touch (candidate branch-
identical to the decisive baseline at 15/15 graded control
states): (a) abstentions 64/240 against the <= 32 budget
FAIL; (b) successes 88 vs recent8 115, required >= 109,
FAIL by 21; (c) harm 88 vs recent8 125 PASS. The four
carried control abstention firings are seed 512003 k=2
(partial through leg C, purity 0.875), seed 512003 k=16
(partial, 0.833), seed 512021 k=4 (partial through leg C,
0.921), and seed 512021 k=16 (full, 0.921) — each 0/0 vs
recent8 6/10, 6/10, 9/7, and 6/10 respectively at its
state, which is the whole of the cohort's −27 control
success deficit. Additional PASSes at EXACT recent8
parity: abstentions 0/240, successes 127 = recent8 127,
harm 113 = 113 — no control firing at all, identical to
the decisive baseline.

**Criterion 1 — second-switch (B2) protection: FAIL /
PASS.** Development FAILs on sub-condition (a) alone, a
carried draw identical to the decisive baseline (the
minority branch is bit-for-bit the baseline's, leg W
included; leg N pre-empted and exposed nothing at B2):
minority TAKEN 2/6 (the other four states are three taken
abstentions — two of them minority breadth-disarmed
fall-throughs carried from the baseline — and one
recent8); (b) selectivity 0/6 at B1 and 0/6 at return-A
PASS; (c) harm 28 vs guard 46 and ceiling 0.60 × recent8
94 = 56.4 PASS both; (d) successes 20 vs guard 2 + 16 =
18 PASS. Additional PASSes in full: minority TAKEN 3/6 AT
the floor, selectivity 0/6 / 0/6, harm 20 vs guard 61 and
ceiling 0.60 × recent8 81 = 48.6, successes 28 vs guard
3 + 16 = 19. The minority-model cross-check PASSes at
every minority-fired state (5 development / 6 additional
applicable) with first-frame choices differing from the
widened-window method at 2/2 development and 2/3
additional minority-fired B2 onset states checked.

**Criterion 11 — B1/stationary conjunction (carried):
FAIL / PASS.** Development fails on its stationary side
alone (criterion 6 above; its B1 side passes). Additional
passes both sides.

**Criterion 4 — return-A onset harm (guard position):
FAIL / FAIL.** The same computation as PRIMARY criterion
17, reported twice as registered, never two thresholds:
development FAILs on the ceiling (b) alone (52 vs guard
65 PASS, ceiling 48.0 FAIL; regular recovery TAKEN 5/6 vs
the decisive baseline's 2/6); additional FAILs on both
(76 vs guard 67 and ceiling 49.8; regular recovery TAKEN
1/6 vs the decisive baseline's 0/6 — its one would-be
state abstained). Candidate return-A harm 52 / 76 vs the
decisive baseline's 76 / 67: leg N's restorations REDUCED
return-A harm by 24 on development and RAISED it by 9 on
additional, the entire additional increase being the one
restoration's 9 harm against its abstention fall-through.

**Criterion 2 — return-A recovery successes: PASS /
FAIL.** Development: successes 44 vs frozen_A 62 (floor
24.8) PASS on (a) and guard 15 + 16 = 31 PASS on (b).
Additional: successes 20 vs frozen_A 70 (floor 28.0) FAIL
on (a) by 8 and guard 13 + 16 = 29 FAIL on (b) by 9.
Stated in full, as registered: frozen_A beats the
candidate on BOTH axes at return-A on BOTH cohorts (62/34
vs 44/52 development; 70/26 vs 20/76 additional), and
cumulative does the same on both (54/42 development;
56/40 additional); the decisive baseline is beaten on
both axes by the candidate on development (20/76 vs
44/52) and beats it on successes on additional while
losing on harm (13/67 vs 20/76).

**Criterion 3 — pooled onset harm: PASS / PASS.** Pooled
onset harm 127 vs guard 185 development and 128 vs guard
170 additional (a); individual onset cells <= recent8 in
6/6 on both cohorts (b). Stated in full: pooled onset
harm is BELOW the decisive baseline's on development
(127 vs 151 — the restorations' net) and ABOVE it on
additional (128 vs 119 — the one restoration's +9 harm
against its abstention fall-through, with no other graded
additional difference at onset).

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
partial state (22 development / 23 additional) and at
fallback at every non-partial state (50 / 49); stale lists
of 18 with both pair counts recomputable everywhere with
0 mismatches; acting lists of 8 with both acting counts
recomputable everywhere with 0 mismatches; newest lists
of 4 with the newest count recomputable everywhere with
0 mismatches and newest records == acting records' last
four everywhere; both acting breadth flags and the newest
breadth flag recomputed everywhere with 0 mismatches;
newest-breadth-rule == candidate branch everywhere;
acting-breadth-rule == decisive baseline branch
everywhere; companion-rule == companion branch everywhere;
pre-acting-release-rule == pre-acting branch everywhere;
preceding-pair-rule == widened-removal-rule everywhere;
widened-rule == inverted branch everywhere; newest4 /
widened_armed recomputable everywhere;
abstention_trigger_kind in {full, partial, none}
everywhere — never widened, as the carried removal
requires; minority_model_archive_count ==
archive_events_count everywhere; minority_model_inverted
true everywhere; minority-model cross-check PASS at every
minority-fired state (5/5 development, 6/6 additional
applicable); learner acquisition actions 0 throughout.

## Learning evaluation

Candidate vs recent8 (simplest credible baseline),
successes / harmful TEST actions per stage-checkpoint cell
(candidate first; abstentions in parentheses where
nonzero):

Development — B1: k=0 1/47 vs 1/47; k=2 1/31 (16) vs 1/47;
k=4 0/16 (32) vs 16/32; k=8 19/13 (16) vs 28/20; k=16
16/16 (16) vs 25/23; k=32 23/25 vs 23/25. return-A: k=0
8/40 vs 0/48; k=2 17/31 vs 5/43; k=4 27/21 vs 11/37; k=8
29/19 vs 30/18; k=16 29/19 vs 30/18; k=32 14/18 (16) vs
22/26. B2: k=0 0/48 vs 0/48; k=2 0/16 (32) vs 0/48; k=4
20/12 (16) vs 2/46; k=8 20/12 (16) vs 26/22; k=16 35/13
vs 37/11; k=32 34/14 vs 34/14. Control: k=0 24/24 vs
24/24; k=2 21/11 (16) vs 27/21; k=4 11/21 (16) vs 20/28;
k=8 25/23 vs 25/23; k=16 6/10 (32) vs 18/30; k=32 25/23
vs 25/23.

Additional — B1: k=0 0/48 vs 0/48; k=2 0/16 (32) vs 11/37;
k=4 0/16 (32) vs 21/27; k=8 0/0 (48) vs 23/25; k=16 27/21
vs 27/21; k=32 16/32 vs 16/32. return-A: k=0 1/47 vs
1/47; k=2 6/42 vs 6/42; k=4 14/34 vs 7/41; k=8 24/24 vs
24/24; k=16 25/23 vs 26/22; k=32 30/18 vs 30/18. B2: k=0
0/16 (32) vs 0/48; k=2 8/8 (32) vs 3/45; k=4 20/12 (16) vs
12/36; k=8 27/21 vs 29/19; k=16 9/39 vs 10/38; k=32 35/13
vs 35/13. Control: k=0 30/18 vs 30/18; k=2 27/21 vs 27/21;
k=4 22/26 vs 22/26; k=8 26/22 vs 26/22; k=16 28/20 vs
28/20; k=32 24/24 vs 24/24.

Pooled onset (checkpoints 2 and 4): candidate 65
successes / 127 harm development and 48/128 additional,
vs decisive baseline 41/151 and 41/119, vs companion
102/138 and 90/134, vs widened-removal 107/165 and 90/134
(= inverted additional; inverted 107/165 development), vs
widened-window 111/161 and 89/135, vs guard 23/185 and
38/170, vs recent8 35/253 and 60/228. The candidate
differs from the decisive baseline in score at 4/72
development checkpoints and 2/72 additional checkpoints,
from the companion method at 7/72 and 10/72, and from the
inverted method at 12/72 and 10/72. Past knowledge
retention is graded by checkpoint-32 and stationary
behaviour above: leg N's single k=32 stand-down is the
cohort's Regression (below), and development's stationary
arm carried four abstention firings identical to the
decisive baseline's. Generalization level: at most
handoff level 2–3, as registered — designer-supplied
rules throughout; no novel-representation claim.

## Safety and evidence costs

- Harmful TEST actions: pooled onset 127 development /
  128 additional (candidate), detailed per criterion
  above; B1 pooled onset harm 47 / 32; B2 28 / 20;
  return-A 52 / 76; stationary control harm 88 / 113;
  checkpoint-32 harm 57 development (vs decisive 63,
  recent8 65) and 63 additional (= decisive = recent8).
- Failed-by-abstention: candidate onset abstentions
  96/288 development and 112/288 additional; stationary
  64/240 development and 0/240 additional; checkpoint-32
  16/144 development (the single leg-N-released state)
  and 0/144 additional.
- Learner information-acquisition actions: 0 throughout.
  Additional requested observations: 0.
- External TRAIN actor costs (shared evidence stream,
  identical for all methods, published in full, never
  netted against TEST results): development — stage A 720
  actions, 249 actually harmful (250 reported harmful, 27
  label flips); B1 192 actions, 74 harmful; B2 192, 90;
  return-A subset 144, 53; control continuation 192, 70.
  Additional — stage A 720 actions, 239 actually harmful
  (244 reported, 29 flips); B1 192, 78; B2 192, 87;
  return-A subset 144, 43; control continuation 192, 62.
- False confidence / unnecessary stand-downs: leg N's
  stand-down side fired exactly once in the graded
  populations, at the worst checkpoint for it — a
  productive checkpoint-32 routing given back to an
  abstention. Its restoration side fired four times at
  graded return-A onset states, three productively and
  once against an abstention. Leg T disarmed zero states
  for the fourth consecutive cycle.
- Report integrity: all figures script-computed from the
  saved detailed results at `60a13af` in this grading
  stage; the 512003-family / 513001-family cohorts are
  INSPECTED and no parameter was re-tuned against them or
  any earlier cohort.

## Scientific conclusion

**Failed / Regression at checkpoint 32.** Failed under
the protocol's own definitions (PRIMARY criterion 17
FAILs on BOTH cohorts — development on the ceiling
sub-condition (b) alone, additional on both
sub-conditions — and the Failed clause triggers on the
additional cohort several times over: criteria 17, 4, and
2 FAIL there, criterion 7 PASSes both). Partially
demonstrated does not apply (it requires criterion 17
PASS on both cohorts). A Regression clause DOES trigger:
development checkpoint-32 successes 71 fall below the
recent8 − 4 line of 75 (the deficit is exactly leg N's
single released routing, decisive 10/6 → abstention 0/0
at seed 512003 return-A k=32, against the other eight
states' identity with the decisive baseline; candidate
k=32 successes 71 vs decisive 81, recent8 79). The other
Regression clauses do not trigger: pooled onset harm
127/128 is below recent8's 253/228 on both cohorts; the
stationary-control clause requires more than 6 on BOTH
cohorts and additional is at exact parity against
development's −27; the full unit suite and the historical
transfer benchmark pass.

What the experiment actually establishes, stated as
prominently as the failure: leg N did the restoration it
was designed for — **the grading cap is MET on both
cohorts** (3 graded return-A restorations on development,
1 on additional), and on development those restorations
were the cycle's clearest positive result: return-A
recovery TAKEN 5/6 vs the decisive baseline's 2/6, pooled
return-A successes/harm 44/52 vs decisive 20/76, pooled
onset harm BELOW the decisive baseline (127 vs 151) for
the first time in the breadth line. But the frozen harm
form still fails: on development the pooled return-A harm
(52) sits above the ceiling (48.0) on the strength of the
states leg N does not change, and on additional the
single restoration converted a taken abstention's 0/0
into a 7/9 firing, pushing return-A harm (76) above both
the guard (67) and the ceiling (49.8) while the cohort's
remaining return-A harm is carried recent8 fall-through
at non-engaged states (candidate identical to recent8 at
5 of 6 additional return-A onset states; criterion 2
fails there on both sub-conditions). And leg N's
stand-down side, exercised exactly once, realized the
pre-registered checkpoint-32 release risk in its sharpest
form: a productive routing released not to recent8 but
through it to a taken partial abstention, failing
criterion 5(d) and carrying the Regression. A
four-event breadth window restores onset firings an
eight-event window cannot reach, but at checkpoint 32 —
where the newest four are the stalest evidence about a
routing's rule — the same window releases what the wider
window held.

**Next limitation (selected for the next cycle, Priority
1):** checkpoint-32 release through leg N — criterion 5
FAILs on development on sub-condition (d) alone (abstained
branch 1/9 against the frozen 0/9), the failure is the
Regression's exact deficit (k=32 successes 71 below the
recent8 − 4 line of 75; candidate 71 vs decisive 81 on
that cohort), and its mechanism is entirely the changed
element's stand-down side: the sole newest-disarmed state
across both cohorts is a correct-rule retained routing at
newest count 1 / acting count 3, stale count 0, purity
0.714, released to a partial abstention — while
additional drew no k=32 routing at all and passes
criterion 5 in full, and the acting cycle had just
repaired this criterion on both cohorts. Measurable: on
NEW cohorts under a NEW protocol, whether an
evidence-derived condition on the regular recovery
branch's late routings — a condition that distinguishes
leg N's checkpoint-32 release population from its onset
restoration population without re-tuning leg N's onset
form — can hold criterion 5's frozen form on BOTH cohorts
while holding return-A onset harm (criteria 17/4, with
leg N's restoration side carried), B1 engagement
(criterion 9), stationary selectivity (criterion 6), and
B2 protection (criterion 1) as co-graded guards. Recorded
but not selected: criteria 17/4 fail on both cohorts
again, but development's restorations were productive
(+24 successes / −24 harm vs the decisive baseline) and
additional's failure is dominated by carried recent8
fall-through harm at non-engaged return-A states plus the
one abstention-converting restoration — a further
return-A retry needs a condition on the non-engaged
fall-through population, a different population from the
one leg N exercises, and is carried in this protocol's
reporting; development's criterion 6 stationary failure
is a carried draw identical to the decisive baseline
(branch differences 0/15 graded control states; four
carried abstention firings, −27 successes) with
additional at exact parity; development's criterion 1
B2 failure is likewise carried identical (minority 2/6
under both methods, harm and successes passing) with
additional passing in full at the floor; additional's
criterion 2 failure is driven by the same non-engaged
return-A population as its criterion 17 failure;
frozen_A / cumulative both-axes return-A dominance holds
on both cohorts again.

Keep the learner optional and unpromoted, default
controller unchanged, no merge, no AthenZ/Synveil
integration, D1–D10/V2A/V2B unchanged.
