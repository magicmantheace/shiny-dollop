# Pre-acting joint release recovery — a pre-acting joint-pair release leg (leg T) on both recovery branches

**9 November 2026 protocol frozen; 9 November 2026 implementation;
9 November 2026 evaluation; graded 9 November 2026. Status:
optional, simulated, unpromoted. No default-controller promotion,
no PR merge, no D1–D10 or V2A/V2B roadmap change, no
AthenZ/Synveil integration.**

## Experiment identity

- **Name and purpose:** `pre_acting_joint_release_recovery` —
  whether ONE changed element, leg T, a PRE-ACTING JOINT-PAIR
  RELEASE LEG on BOTH recovery branches (a branch fires only if
  its own joint signal has NOT already completed in full at
  least twice before the acting window: stale pair counts over
  the 9 disjoint consecutive pairs of events[-26:-8], threshold
  2), can hold criterion 5's frozen checkpoint-32 release form
  on BOTH cohorts — the widened-removal cycle's selected
  limitation (criterion 5 FAILed there on BOTH cohorts on
  sub-condition (c) alone: non-recent8 routings in 2/9 and 3/9
  switch-stage checkpoint-32 states against the allowance of
  1) — while holding the stationary profile (criterion 6), B1
  engagement (criterion 9), B2 protection with the inverted
  minority model carried (criterion 1), and return-A harm
  (criterion 4) as co-graded guards. The threshold and window
  geometry were derived at the protocol stage from the
  simulator's published rates and the branches' structure ONLY
  (a full joint pair over pre-switch events is a noise event at
  the squared flip rate; T = 2 is the non-dominated value under
  both published rate pairs: onset stand-down 2.2 percent raw /
  1.0 percent adjusted, checkpoint-32 correct-rule stand-down
  0.9995 raw / 0.961 adjusted in the opposite-reference case);
  leg P was explicitly NOT raised, and no inspected per-state
  count was used to set any parameter. Build Order Priority 1
  (Independent Learning), items 2 + 3 + 4; handoff §8 slow or
  incorrect recovery of old knowledge / inconsistent
  adaptation to changing rules. This protocol's PRIMARY
  criterion is criterion 14, the conjunction of (a) criterion
  5's release form, (b) criterion 6's stationary form, (c)
  criterion 9's B1 form (non-full credit a retained partial
  only, the widened class's removal carried), and (d)
  criterion 1's B2 form with the inverted minority model
  carried; criteria 5, 6, 9, 1, 11, 4, 2, 3, and 7 are its
  co-graded guards. The protocol also froze a grading cap: a
  Demonstrated verdict additionally requires at least one
  checkpoint-32 state in at least one cohort at which the
  decisive baseline took a non-recent8 recovery branch and the
  candidate released to recent8 through leg T (that branch's
  stale-pair count >= 2).
- **Candidate:** `PreActingJointReleaseRecoveryMemory`
  (`developmental_ai/pre_acting_joint_release_recovery.py`) —
  IDENTICAL to the graded `WidenedClassRemovalRecoveryMemory`
  in every element (acting model recent8 exactly, extended
  signal, retained archive, archive concordance, joint test
  joint_count >= 1, recovery model, the full three-leg
  authority condition, the minority branch in full INCLUDING
  the inverted minority model, leg P >= 0.70 on both recovery
  branches, and the full / retained-partial abstention classes
  with leg R on partials, the widened class removed with its
  quantities records-only, support threshold null) — verified
  by a diff against the graded widened-removal candidate at
  implementation: the ONLY code differences are leg T (the
  stale-window per-event joint records over events[-26:-8] for
  both branches, stale_joint_pair_count /
  stale_minority_joint_pair_count over the 9 disjoint pairs,
  staleness_pair_threshold 2, the
  recovery_disarmed_by_staleness /
  minority_disarmed_by_staleness flags recorded only when
  joint, arming, and leg P all pass, and the two added firing
  conditions stale count < 2), its docstring, and
  names/schema. Separate optional learner; the default
  controller and all existing learners are untouched; the
  graded widened-removal candidate appears only as the
  decisive baseline.
- **Branch and commits:**
  `developmental-ai/pre-acting-joint-release-recovery` (forked
  from `6029f3f`, the widened-class-removal grading commit).
  Protocol frozen at `348d8aa` (BEFORE implementation);
  implementation at `393bcbf`; evaluation at `15c25c3`. This
  grading report is committed on top of the evaluation commit.
- **Frozen protocol:**
  `benchmarks/pre_acting_joint_release_recovery_protocol.json`
  (frozen 2026-11-09, before any implementation, unit test,
  harness, or score inspection for this experiment).
- **Cohorts:** development 482003/482021/482039 and additional
  483001/483017/483041 — NEW at freeze, disjoint from every
  earlier cohort (verified by grep before the freeze commit).
  Both cohorts are now **INSPECTED** and must never be re-tuned
  against.
- **Decisive baseline:** `widened_class_removal_recovery`
  (identical but for leg T; branch selection identical except
  at stale-disarmed states). `recent8` is the simplest
  credible baseline and the candidate's own acting model.

## Verification

- Unit tests: PASS — 67/67 new candidate tests at
  implementation; full suite 1477 tests OK in the
  implementation and evaluation stages, and re-run in this
  grading stage: 1477 tests OK (`python3 -m unittest discover
  -s tests`, run 2026-11-09 this pass). The new tests include
  the discriminating states: the regular stale-disarmed rows
  (stale pairs 2, purity 0.92 — decisive baseline FIRES
  retained_archive, candidate stands down to recent8) and the
  minority stale-disarmed rows (stale minority pairs 2,
  regular stale 0 — decisive baseline FIRES minority_archive,
  candidate's minority branch stands down and the decision
  falls through to the taken full abstention).
- Historical regressions: PASS — historical transfer benchmark
  (`python3 -m benchmarks.transfer_benchmark`) exit 0 in the
  evaluation stage and re-run in this grading stage, standard
  three-seed output (success gains 0.5567 / 0.50 / 0.51 on
  seeds 17 / 23 / 41).
- Frozen cohorts: PASS (run exactly as registered) — both
  cohorts evaluated at `15c25c3`; every checkpoint entry
  carries per-method successes / harmful TEST actions /
  abstentions / attempted tasks, the candidate's full decision
  record (including the full stale record), checkpoint SHA256,
  and restore-replay identity (script-verified in this grading
  stage: true at every checkpoint in both cohorts, 72/72
  entries per cohort).
- Linux validation: UNVERIFIED (no GitHub Actions run on the
  grading commit was checked; no CI is claimed).
- Windows validation: UNVERIFIED (same).

## Per-criterion grading (precommitted, graded individually, per cohort)

Graded script-computed from the saved detailed results at
`15c25c3` (grading script and output kept with the campaign
records). PRIMARY criterion 14 first, then co-graded guards 5,
6, 9, 1, 11, 4, 2, 3, 7. Development / additional throughout.

**Criterion 14 — PRIMARY (release + stationary + B1 + B2
conjunction): FAIL / FAIL.** Development: release side FAIL,
stationary side PASS, B1 side FAIL, B2 side PASS. Additional:
ALL FOUR sides FAIL (release on successes, stationary on
successes, B1 on engagement count, B2 on the harm ceiling).
The conjunction therefore fails on both cohorts, each failure
attributable to its exact side below.

**Criterion 5 — release and productivity by checkpoint 32:
FAIL / FAIL** — on different sub-conditions per cohort, both
traced to the checkpoint-32 routings leg T did not release.
(a) abstentions 0/144 on both PASS; (d) abstained branch 0/9
on both PASS. Development FAILs on (c) alone: non-recent8
branch in 2/9 switch-stage k=32 states against the allowance
of 1 — a return-A retained routing at seed 482021 (purity
0.750, stale regular count 1 — one pair short of standing
down — scoring 10/6 vs recent8 0/16, strongly productive) and
a B2 minority routing at seed 482021 (purity 0.732, stale
minority count 0, scoring 11/5 vs recent8 5/11, productive);
(b) successes 59 vs recent8 43 (line 35) PASS with a wide
margin, so development's failure is routing COUNT of two
productive routings, exactly the pre-registered shape the
protocol charged. Additional FAILs on (b) alone: successes
65 vs recent8 75, below the recent8 − 8 line of 67; (c)
non-recent8 1/9 PASSes at the allowance exactly — and that
one routing is the entire deficit: a B2 retained routing at
seed 483001 (purity 0.769, stale regular count 0) scoring
0/16 vs recent8 10/6, a −10 successes / +10 harm state. All
nine k=32 states per cohort are reported here in full:
development — B1 all recent8 (482003 purity 0.718 stale 0/1,
0/16 = recent8; 482021 purity 0.615, 1/15 =; 482039 purity
0.667, 12/4 =); return-A 482003 recent8 (0.733, stale 0/0,
1/15 =), 482021 retained above, 482039 recent8 (0.789, 9/7
=); B2 482003 recent8 (0.690, purity-disarmed minority joint,
10/6 =), 482021 minority above, 482039 recent8 (0.758, 5/11
=). Additional — B1 all recent8 (483001 purity 0.639 stale
0/1, 14/2 =; 483017 0.684, 4/12 =; 483041 0.769, 12/4 =);
return-A all recent8 (483001 0.700, 10/6 =; 483017 0.714,
6/10 =; 483041 0.762 stale 1, 13/3 =); B2 483001 retained
above, 483017 recent8 (0.821, 1/15 =), 483041 recent8
(0.718, 5/11 =). **Leg T released ZERO checkpoint-32
routings on either cohort**: the three routings across
cohorts carried stale counts 1, 0, and 0 for their own
branches — the leg's designed population (a routing whose own
joint signal had already completed in full at least twice
before the acting window) did not occur at checkpoint 32 on
these draws, so every k=32 outcome above is a carried outcome
identical to the decisive baseline's, charged as registered.

**Criterion 6 — stationary control selectivity: PASS / FAIL.**
Development PASSes in full, at the margin exactly:
abstentions 16/240, successes 124 vs recent8 130 (required
>= 124 — met exactly), harm 100 vs 110. The one control
firing is a carried FULL abstention (seed 482039, k=16,
purity 0.784, 0/0 vs recent8 6/10 at that state). Additional
FAILs on (b) alone: abstentions 32/240 PASS (at the budget
exactly) and harm 142 vs 167 PASS, but successes 66 vs
recent8 73, required >= 67 — short by 1 against the line, 7
against recent8. The deficit is exactly the cohort's two
carried retained-PARTIAL firings, both at k=16 (seed 483017,
purity 0.833, 0/0 vs recent8 0/16; seed 483041, purity 0.886,
0/0 vs recent8 7/9 — the second firing alone is the −7).
Leg T is inert on the control arm on these draws as the rate
model predicted: the candidate's control line is identical
to the decisive baseline's on both cohorts, branch
differences 0/15 graded control states per cohort.

**Criterion 9 — first-switch (B1) engagement: FAIL / FAIL**
— on complementary halves of sub-condition (a), with harm
PASSing both comparisons on both cohorts. Development:
abstention TAKEN at 3/6 pooled B1 onset states, meeting the
count floor — but ALL THREE are FULL firings (seed 482003
k=4, purity 0.943; seed 482039 k=2, purity 0.763; seed 482039
k=4, purity 0.737), so the NON-FULL sub-condition (at least 1
retained-partial firing) FAILs: non-full 0. Harm 48 = guard
48 (b) PASS and 48 < recent8 95 (c) PASS. B1 successes 0 vs
recent8 1 / guard 0, stated in full. Additional: TAKEN only
2/6, one short of the floor — but both taken firings ARE
retained partials (seed 483017 k=4, purity 0.842; seed 483041
k=4, purity 0.879; both at checkpoint 4, none at checkpoint
2), so the non-full sub-condition is met and the count
sub-condition FAILs. Harm 60 vs guard 89 (b) PASS and 60 <
recent8 89 (c) PASS. B1 successes 4 vs recent8 7 / guard 7.
The candidate is identical to the decisive baseline at every
B1 state on both cohorts — leg T has no B1 exposure on these
draws and both failures are carried outcomes, charged as
registered. Together the two cohorts show the carried B1
profile failing the SAME frozen form in mirror image: where
the count is met, the composition is full-only; where the
composition is partial, the count is short. See the next
limitation.

**Criterion 1 — second-switch (B2) protection: PASS / FAIL.**
Development PASSes in full — and it is this criterion that
carries leg T's only exercised state in the entire
experiment. Minority TAKEN 5/6 (a) PASS: the missing firing
is the pre-registered onset-engagement cost, realized once —
seed 482003, k=2, stale_minority_joint_pair_count 2, purity
0.800: the decisive baseline fired minority_archive (9/7)
and the candidate stood the minority branch down
(minority_disarmed_by_staleness) and fell through to a FULL
abstention (0/0; recent8 1/15 at that state). Against the
decisive baseline there, leg T cost −9 successes and saved
−7 harm on that one state — which is also the whole of the
development pooled-onset success gap vs the decisive
baseline (89 vs 98) and of the B2 engagement shortfall (5/6
vs 6/6); decisive B2 line 59/37 vs candidate 50/30.
Selectivity (b) PASSes (0/6 at B1, 0/6 at return-A); harm
(c) PASSes both comparisons (30 vs guard 44 and ceiling
0.60 × recent8 69 = 41.4); successes (d) PASS (50 vs guard
20 + 16 = 36). The minority-model cross-check differs at 5/5
minority-fired B2 onset states against the widened-window
method on this cohort. Additional FAILs on (c)'s ceiling
alone: minority TAKEN 3/6 (a) PASS at the floor, selectivity
0/6 / 0/6 (b) PASS, successes 39 vs guard 7 + 16 = 23 (d)
PASS, harm 57 vs guard 73 PASS on the guard comparison but
above the ceiling 0.60 × recent8 89 = 53.4 by 3.6. The
candidate is identical to the decisive baseline at every
additional-cohort checkpoint (score differences 0/72) — the
ceiling failure is a carried outcome at engaged and
non-engaged states leg T never touched on this cohort;
cross-check differing choices 3/3 at minority-fired B2 onset
states.

**Criterion 11 — B1/stationary conjunction (carried): FAIL /
FAIL.** Development fails on its B1 side only (criterion 9;
its stationary side PASSes at the exact margin); additional
fails on BOTH sides (criteria 6 and 9).

**Criterion 4 — return-A onset harm: FAIL / PASS.**
Development: harm 57 vs guard 82 PASS on (a) but ceiling
0.60 × recent8 82 = 49.2 FAIL on (b) by 7.8; regular recovery
TAKEN 3/6. Additional: harm 38 vs guard 59 and ceiling 54.0,
PASS in full; regular recovery TAKEN 5/6. Candidate identical
to the decisive baseline at return-A onset on the additional
cohort and differing on development only through carried
states — leg T stood down no return-A state on either cohort
(the one development return-A state at stale count 1, seed
482021 k=32, is a checkpoint-32 state graded under criterion
5, not an onset state).

**Criterion 2 — return-A recovery successes: PASS / PASS.**
Development: successes 39 vs frozen_A 68 (floor 27.2) and
guard 14 + 16 = 30, PASS. Additional: 58 vs frozen_A 62
(floor 24.8) and guard 5 + 16 = 21, PASS. Stated in full, as
registered: cumulative (64 dev / 68 add successes at 32 / 28
harm) and frozen_A (68/28 dev, 62/34 add) beat the candidate
(39/57 dev, 58/38 add) on BOTH axes at return-A on BOTH
cohorts again this cycle.

**Criterion 3 — pooled onset harm: PASS / PASS.** Pooled
onset harm 135 vs guard 174 development and 155 vs guard 221
additional, with all 6/6 individual onset cells <= recent8 on
both cohorts. Development's pooled figure is BELOW the
decisive baseline's 142 (the stale stand-down's −7 harm at
the B2 onset state); additional's is identical to the
decisive baseline's 155.

**Criterion 7 — full accounting: PASS / PASS.** Replay
identity true at every checkpoint in both cohorts (72/72
entries per cohort); no criterion-7 field missing anywhere;
support_threshold null everywhere;
abstention_disarmed_by_support false everywhere;
widened_threshold 3, staleness_pair_threshold 2, and
preceding_pair_threshold 1 everywhere; abstention gate /
newest4 / widened_armed recomputable everywhere with 0
mismatches; abstention_trigger_kind in {full, partial, none}
everywhere — never widened, as the carried removal requires;
stale event lists of 18 at every checkpoint with BOTH stale
pair counts recomputable from the stale records everywhere
(0 mismatches); pre-acting-release-rule == candidate branch
everywhere; widened-removal-rule == decisive baseline branch
everywhere; preceding-pair-rule == widened-removal-rule
everywhere; widened-rule == inverted branch everywhere;
minority_model_archive_count == archive_events_count
everywhere; minority_model_inverted true everywhere;
minority-model cross-check PASS at every minority-fired state
(9 dev / 5 add: candidate == swapped-archive inverted model
AND candidate == inverted method AND candidate ==
widened-removal method AND widened-window method ==
minority-set model); learner acquisition actions = 0, learner
training actions = 0, additional requested observations = 0.

**Grading cap (exercised checkpoint-32 release): NOT MET on
either cohort** — zero checkpoint-32 releases through leg T
in either cohort (the three k=32 routings carried stale
counts 1, 0, 0). The cap is a necessary condition for
Demonstrated, so even a conjunction pass would have been
capped at Partially demonstrated; here it is recorded as the
experiment's central null result, not as a near-miss: leg T's
designed population did not occur at checkpoint 32 on these
draws at all. The leg was exercised at exactly ONE state
across both cohorts — the development B2 onset stand-down
graded under criterion 1 — which is the pre-registered
onset-engagement cost, not a release.

**Per-state leg-T reporting (registered, part of the grading,
not an appendix).** Across all 72 checkpoints per cohort,
candidate and decisive baseline branches differ at exactly
ONE state (development seed 482003, B2 k=2, graded under
criterion 1 above) and at ZERO states on the additional
cohort; score differences are 1/72 checkpoints development
and 0/72 additional vs the decisive method, 2/72 and 0/72 vs
the inverted method. Stale-disarmed flags are set at exactly
that one state. Every other graded figure in this report —
including both cohorts' checkpoint-32 lines, both stationary
lines, and the additional cohort entire — is a carried
outcome identical to the decisive baseline, charged to this
experiment's criteria exactly as the protocol registered.

## Learning evaluation

Candidate vs recent8 (successes / harmful actions /
abstentions per stage-checkpoint cell, pooled over seeds):

Development — B1: k=0 0/48/0 (= recent8 0/48), k=2 0/32/16
(recent8 0/48), k=4 0/16/32 (1/47), k=8 8/8/32 (32/16),
k=16 29/19/0 (= 29/19), k=32 13/35/0 (= 13/35). return-A:
k=0 0/48/0 (=), k=2 21/27/0 (3/45), k=4 18/30/0 (11/37),
k=8 18/30/0 (11/37), k=16 30/18/0 (17/31), k=32 20/28/0
(10/38). B2: k=0 0/48/0 (=), k=2 20/12/16 (8/40), k=4
30/18/0 (19/29), k=8 31/17/0 (35/13), k=16 25/23/0 (17/31),
k=32 26/22/0 (20/28). Control: k=0 36/12/0 (=), k=2 30/18/0
(=), k=4 26/22/0 (=), k=8 25/23/0 (=), k=16 13/19/16
(19/29), k=32 30/18/0 (=); pooled 124/100/16 vs recent8
130/110/0.

Additional — B1: k=0 0/32/16 (recent8 0/48), k=2 4/44/0
(= 4/44), k=4 0/16/32 (3/45), k=8 0/0/48 (14/34), k=16
0/0/48 (14/34), k=32 30/18/0 (= 30/18). return-A: k=0
13/35/0 (1/47), k=2 35/13/0 (4/44), k=4 23/25/0 (2/46),
k=8 36/12/0 (18/30), k=16 27/21/0 (26/22), k=32 29/19/0
(= 29/19). B2: k=0 12/36/0 (1/47), k=2 21/27/0 (1/47),
k=4 18/30/0 (6/42), k=8 16/32/0 (14/34), k=16 35/13/0
(= 35/13), k=32 6/42/0 (16/32). Control: k=0 18/14/16
(20/28), k=2 12/36/0 (=), k=4 5/43/0 (=), k=8 11/37/0 (=),
k=16 12/4/32 (19/29), k=32 26/22/0 (=); pooled 66/142/32
vs recent8 73/167/0.

Checkpoint-0 harm (diagnostic, ungraded): 48/48/48 per switch
stage development, 32/35/36 additional — identical in kind to
prior cycles; no method protects first contact.

Retention: past knowledge is retained by construction (the
retained archive and both recovery branches are carried
bit-for-bit, leg T aside) and return-A regular recovery is
TAKEN at 3/6 development and 5/6 additional onset states; but
the simple retention baselines (cumulative, frozen_A) again
beat the candidate on both axes at return-A on both cohorts
(see criterion 2), so retention-through-the-archive machinery
is not demonstrated to be worth its routing cost at return-A
on these cohorts. Generalization level: at most handoff level
2–3, in this simulator only — choosing among / applying
designer-supplied representations; no novel-representation or
level-6 claim is made or permitted by the protocol.

## Safety and evidence costs

- Harmful TEST actions (candidate): pooled onset 135 dev /
  155 add (vs recent8 246 / 268, guard 174 / 221); B1 48 / 60;
  B2 30 / 57; return-A 57 / 38; stationary control 100 / 142
  (vs recent8 110 / 167); checkpoint-32 pooled 85 dev / 79
  add across switch stages (from the per-stage k=32 cells
  above). Leg T's one exercised state is stated per state, not
  netted: at development B2 k=2 seed 482003 the stand-down
  converted a 9/7 minority firing into a 0/0 abstention
  (−9 successes / −7 harm against the decisive baseline;
  recent8 scored 1/15 there).
- Failed-by-abstention: onset 64/288 episodes dev, 32/288 add;
  stationary control 16/240 dev, 32/240 add; checkpoint-32
  0/144 both.
- Learner information-acquisition actions: 0 throughout.
  Additional requested observations: 0. Learner training
  actions: 0 — all TRAIN evidence comes from the shared
  external actor stream.
- External TRAIN actor costs (per cohort, counted once across
  seeds' streams as recorded in the detailed results; actual
  harmful / observations): development — A 236/720, B1 70/192,
  B2 79/192, return-A 54/144, control continuation 59/192;
  additional — A 277/720, B1 78/192, B2 66/192, return-A
  39/144, control continuation 67/192. Reported (label-flip
  inclusive) figures and full per-seed accounting are in the
  saved detailed results. These are fixed costs of the shared
  evidence stream, identical for every method, never netted
  against TEST results.
- False confidence / unnecessary abstention: additional's
  single checkpoint-32 retained routing (0/16 where recent8
  scored 10/6, purity 0.769, stale count 0 — leg T had nothing
  to release) and additional's two stationary partial firings
  at k=16 (16-episode refusals costing 7 successes pooled)
  are the cycle's two clearest instances, one on each side of
  the act/abstain line.
- Report integrity: all figures above are script-computed
  from the saved detailed results at the evaluation commit;
  inspected cohorts (482003-family / 483001-family) are never
  re-tuned against. Provenance limitation: developer-selected
  simulation seeds in the same engineered two-feature simulator
  family as all preceding switch experiments — not independent
  external proof.

## Scientific conclusion

**Failed — and a Regression at checkpoint 32.** Failed under
the protocol's own definitions: PRIMARY criterion 14 FAILs on
BOTH cohorts (development on its release and B1 sides;
additional on all four sides), and the Failed clause triggers
on the additional cohort several times over (criteria 14, 5,
6, 9, 1, and 11 all FAIL there; criterion 7 PASSes both). A
Regression under the protocol's checkpoint-32 clause:
additional k=32 successes 65 fall below the recent8 − 4 line
of 71 — the deficit is exactly the one carried retained
routing at seed 483001 (0/16 vs recent8 10/6) that leg T did
not release (its stale count was 0). The other Regression
clauses do not trigger: pooled onset harm 135/155 is well
below recent8's 246/268 on both cohorts; the
control-successes clause requires both cohorts and
development's deficit is exactly −6, not more (additional
−7); the full unit suite and the historical transfer
benchmark pass.

What the experiment actually establishes, stated as
prominently as the failure: leg T, the single changed
element, was exercised at exactly ONE state in 144 graded
checkpoint populations across both cohorts, and that state
was its pre-registered COST, not its designed benefit. At
checkpoint 32 — the population the leg was built for — its
designed population did not occur: the three routings across
cohorts carried stale pair counts of 1, 0, and 0 for their own
branches, so the leg released nothing, the grading cap is NOT
MET on either cohort, and every checkpoint-32 outcome is a
carried outcome of the decisive baseline, including the one
harmful additional routing that crosses the Regression line.
The published-rate derivation is not thereby refuted in
general — it predicted stand-downs only where a branch's own
joint signal had already completed twice before the acting
window, and on these draws that condition simply never held
at a checkpoint-32 routing — but as a release mechanism for
the routings that actually occur (stale counts 0–1, purity
0.732–0.769), leg T in its frozen form is a null, and its one
realized onset stand-down converted a productive 9/7 minority
firing into a 0/0 abstention. A checkpoint-32 release
mechanism whose exercised population is empty at checkpoint
32 and non-empty only as an onset cost is a Failed experiment
under this protocol, recorded exactly that way. Partially
demonstrated does not apply (it requires criterion 14 PASS on
both cohorts).

**Next limitation (selected for the next cycle, Priority 1):**
first-switch (B1) onset engagement composition — criterion 9
FAILs on BOTH cohorts in this cycle, on complementary halves
of the same sub-condition (a), with harm PASSing both
comparisons on both cohorts: development meets the 3/6 count
floor only with FULL firings and records ZERO non-full
(retained-partial) firings, while additional records two
retained-partial firings and meets the non-full sub-condition
but reaches only 2/6 on the count. The failure is therefore
engagement composition/count in the carried abstention
classes at B1 onset, not harm: no cohort in this cycle
delivers count AND composition together. Measurable: on NEW
cohorts under a NEW protocol, whether an evidence-derived
condition on the B1 onset abstention classes (their trigger,
gate, or class composition) can hold criterion 9's frozen
form in full on BOTH cohorts (TAKEN >= 3/6 with >= 1 non-full
firing, B1 harm <= guard AND < recent8) while holding
stationary selectivity (criterion 6), B2 protection
(criterion 1), checkpoint-32 release (criterion 5), and
return-A harm (criterion 4) as co-graded guards. Recorded but
not selected: criterion 5's checkpoint-32 release FAILs on
both cohorts again, but on different sub-conditions —
development's two routings are both productive (+10/−10 and
+6/−6 vs recent8; its failure is count alone) and additional's
is one harmful routing at stale count 0 — and leg T's
designed population was absent on these draws, so a further
release retry would need a genuinely new structural quantity,
not a threshold variant of a leg whose population did not
occur; checkpoint-32 release is carried as a co-graded guard
in the next protocol, and its Regression state (additional
seed 483001, 0/16) is recorded, not softened. Additional's
stationary failure is 1 success past the line on two carried
partial firings at k=16 with development passing at its exact
margin — single-cohort. Additional's criterion 1 failure is
the harm ceiling alone (57 vs 53.4; engagement at its floor,
guard passed) with development passing in full —
single-cohort. Development's criterion 4 failure is the
return-A ceiling alone (57 vs 49.2; guard passed, recovery
3/6) with additional passing in full — single-cohort.
Cumulative/frozen_A both-axes return-A dominance holds on
both cohorts again this cycle.

Keep the learner optional and unpromoted, default controller
unchanged, no merge, no AthenZ/Synveil integration,
D1–D10/V2A/V2B unchanged.
