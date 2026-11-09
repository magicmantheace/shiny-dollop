# Widened class removal recovery — the widened abstention trigger class removed from the abstention classes' composition

**8 November 2026 protocol frozen; 8 November 2026 implementation;
8 November 2026 evaluation; graded 8 November 2026. Status:
optional, simulated, unpromoted. No default-controller promotion,
no PR merge, no D1–D10 or V2A/V2B roadmap change, no
AthenZ/Synveil integration.**

## Experiment identity

- **Name and purpose:** `widened_class_removal_recovery` —
  whether ONE changed element, the REMOVAL of the widened
  abstention trigger class (newest4_opposed_count <= 1 AND
  acting_opposed_count >= 3, behind leg P) from the abstention
  classes' composition, can hold the stationary selectivity the
  inverted-archive cycle failed on both cohorts (criterion 6
  FAILed there on abstention volume, 48/240 development and
  64/240 additional against the <= 32 budget, development
  successes failing with it), while holding first-switch (B1)
  engagement, second-switch (B2) protection as demonstrated by
  the inverted minority model, and checkpoint-32 release. The
  selection stage's evidence review confirmed the failure was
  selectivity / productivity, not harm, and that the widened
  class's pre-registered stationary survival — absent on its
  own cohorts — had materialized on both inverted cohorts (7
  stationary firings in total, widened 4 + partial 3, full 0).
  The protocol's design basis is published rates and class
  structure ONLY: the widened class is the ONLY
  selectivity-negative class under both published rate pairs
  (pooled-onset / stationary trigger rates raw 0.014 / 0.056,
  adjusted 0.020 / 0.034 — its newest4 <= 1 condition excludes
  exactly the onset states where post-switch evidence has
  accumulated in the newest four, while on the stationary arm
  newest4 <= 1 is the common case and acting >= 3 is a pure
  noise tail); raising its threshold to >= 4 is strictly
  dominated, so removal is the unique non-dominated disposition
  with no free threshold; a gating alternative was rejected at
  the selection stage because NO recorded quantity separates
  the stationary-fired and B1-taken populations. Build Order
  Priority 1 (Independent Learning), items 2 + 3 + 4; handoff
  §8 excessive abstention / inconsistent adaptation to changing
  rules. This protocol's PRIMARY criterion is criterion 13, the
  conjunction of (a) criterion 6's stationary form, (b)
  criterion 9's B1 form (non-full credit a retained partial
  only, the widened class being removed), (c) criterion 1's B2
  form with the inverted minority model carried, and (d)
  criterion 5's release form; criteria 6, 9, 1, 5, 11, 4, 2, 3,
  and 7 are its co-graded guards. The protocol also froze a
  grading cap: a Demonstrated verdict additionally requires
  >= 1 widened-armed graded state at which the decisive
  baseline abstained through the widened class and the
  candidate did not, in at least one cohort.
- **Candidate:** `WidenedClassRemovalRecoveryMemory`
  (`developmental_ai/widened_class_removal_recovery.py`) —
  IDENTICAL to the graded `InvertedArchiveMinorityRecoveryMemory`
  in acting model (recent8 exactly), extended signal, retained
  archive, archive concordance, joint test (joint_count >= 1),
  recovery model, the full three-leg authority condition, the
  minority branch in full INCLUDING the inverted minority model,
  leg P >= 0.70 on both recovery branches, and the full /
  retained-partial abstention classes with leg R on partials
  and support threshold null — verified by a diff against the
  graded inverted-archive candidate at implementation: the ONLY
  code differences are the widened class's removal from trigger
  / kind / gate composition, its docstring, and names/schema.
  `abstention_would_fire` is opposed_count >= 1 only;
  `abstention_trigger_kind` is full / partial / none only (never
  widened); newest4_opposed_count / widened_armed /
  widened_threshold (3) remain computed and recorded
  records-only at every checkpoint. Separate optional learner;
  the default controller and all existing learners are
  untouched; the graded inverted-archive candidate appears only
  as the decisive baseline.
- **Branch and commits:**
  `developmental-ai/widened-class-removal-recovery` (forked from
  `cee8a8b`, the inverted-archive grading commit). Protocol
  frozen at `e601238` (BEFORE implementation); implementation
  at `9341528`; evaluation at `3717ed2`. This grading report is
  committed on top of the evaluation commit.
- **Frozen protocol:**
  `benchmarks/widened_class_removal_recovery_protocol.json`
  (frozen 2026-11-08, before any implementation, unit test,
  harness, or score inspection for this experiment).
- **Cohorts:** development 472003/472021/472039 and additional
  473001/473017/473041 — NEW at freeze, disjoint from every
  earlier cohort (verified by grep before the freeze commit).
  Both cohorts are now **INSPECTED** and must never be re-tuned
  against.
- **Decisive baseline:** `inverted_archive_minority_recovery`
  (identical but for the widened class's presence; branch
  selection identical except at widened-armed states).
  `recent8` is the simplest credible baseline and the
  candidate's own acting model.

## Verification

- Unit tests: PASS — 59/59 new candidate tests at
  implementation; full suite 1410 tests OK in the
  implementation and evaluation stages, and re-run in this
  grading stage: 1410 tests OK (`python3 -m unittest discover
  -s tests`, run 2026-11-08 this pass). The new tests include the
  discriminating states: the silent widened-armed state
  (newest4 0, acting 3, purity 0.94) where the graded
  inverted-archive candidate ABSTAINS as kind widened and this
  candidate ACTS on recent8 with kind none; and the split
  widened-armed state (opposed 1, preceding 0, newest4 1,
  acting 3) where the inverted candidate takes kind widened
  and this candidate records kind partial disarmed by leg R.
- Historical regressions: PASS — historical transfer benchmark
  (`python3 -m benchmarks.transfer_benchmark`) exit 0 in the
  evaluation stage and re-run in this grading stage, standard
  three-seed output (success gains 0.5567 / 0.50 / 0.51 on
  seeds 17 / 23 / 41).
- Frozen cohorts: PASS (run exactly as registered) — both
  cohorts evaluated at `3717ed2`; every checkpoint entry
  carries per-method successes / harmful TEST actions /
  abstentions / attempted tasks, the candidate's full decision
  record, checkpoint SHA256, and restore-replay identity
  (script-verified in this grading stage: true at every
  checkpoint in both cohorts, 72/72 entries per cohort).
- Linux validation: UNVERIFIED (no GitHub Actions run on the
  grading commit was checked; no CI is claimed).
- Windows validation: UNVERIFIED (same).

## Per-criterion grading (precommitted, graded individually, per cohort)

Graded script-computed from the saved detailed results at
`3717ed2` (grading script and output kept with the campaign
records). PRIMARY criterion 13 first, then co-graded guards 6,
9, 1, 5, 11, 4, 2, 3, 7. Development / additional throughout.

**Criterion 13 — PRIMARY (stationary + B1 + B2 + release
conjunction): FAIL / FAIL.** Development: stationary side PASS,
B1 side FAIL, B2 side FAIL, release side FAIL. Additional:
stationary side FAIL, B1 side PASS, B2 side PASS, release side
FAIL. No side passes on both cohorts except none — every side
fails on at least one cohort, and the release side fails on
both. The conjunction therefore fails on both cohorts, each
failure attributable to its exact side below.

**Criterion 6 — stationary control selectivity: PASS / FAIL.**
Development: abstentions 0/240, successes 105 = recent8 105,
harm 135 = recent8 135 — EXACT recent8 parity, the strongest
stationary line in this abstention line's history on a
development cohort. The decisive inverted method's control
line on the same cohort was 100/124 with 16 abstention
episodes: the one widened firing the removal spent (seed
472021, k=2, widened-armed, candidate acted on recent8 at
5/11 where the abstention scored 0/0) is worth exactly the
+5 successes / +11 harm difference, and it lands the candidate
at parity rather than past it. Additional: abstentions 16/240
PASS and harm 142 vs recent8 149 PASS, but successes 82 vs
recent8 91 FAIL — required >= 85, short by 3 against the line
and 9 against recent8. The entire deficit is ONE carried
RETAINED-PARTIAL firing (seed 473017, k=4, purity 0.7812,
0/0 vs recent8's 9/7 at that state): the removal spent the
cohort's widened firing too (seed 473017, k=8, candidate acted
8/8 vs the abstention's 0/0; the inverted method's control
line was 74/134 with 32 abstention episodes), but one carried
partial firing at a 9-success state consumes more than the
frozen −6 margin on its own. The selected limitation is
therefore answered in part: with the widened class removed,
stationary volume is inside the budget on both cohorts
(0 and 16 against 48 and 64 in the inverted cycle) and
development holds every margin — but the carried partial
class alone can still break the successes margin on a cohort,
by one firing.

**Criterion 9 — first-switch (B1) engagement: FAIL / PASS.**
Development: abstention TAKEN at 2/6 pooled B1 onset states
(1 full — seed 472021 k=2, purity 0.816; 1 retained partial —
seed 472003 k=4, purity 0.825), one short of the 3/6 floor;
the non-full sub-condition is met by that partial. Harm PASSes
both comparisons (51 vs guard 66 and < recent8 82). The
untaken states are stated in full: one partial disarmed by
leg R at preceding 0 (seed 472003 k=2, purity 0.850, candidate
0/16 = recent8), one triggerless state at opposed 0 (seed
472021 k=4), one state taken by the retained-archive recovery
branch instead (seed 472039 k=2), and one recent8 state (seed
472039 k=4, 12/4). B1 successes 13 vs recent8 14 / guard 14.
Additional: TAKEN 5/6 (3 full, 2 retained partial — both
partials at seed 473041, purity-armed with preceding 1), harm
16 vs guard 53 and < recent8 68, PASS in full; the one untaken
state is a partial disarmed by leg R at preceding 0 (seed
473001 k=2). B1 successes 0 vs recent8 28 / guard 27, stated
in full — the abstention branch's productivity cost on that
cohort is total. **The removal's own share of the development
shortfall is exactly zero:** the decisive inverted method took
the identical 2/6 on the same cohort with zero widened B1
firings — the removal is a complete onset null on these draws
(see the widened reporting below), and the shortfall is a
carried outcome, charged to this experiment's criteria as
registered, not excused.

**Criterion 1 — second-switch (B2) protection: FAIL / PASS.**
Development FAILs on three sub-conditions: (a) minority
TAKEN only 2/6 pooled B2 onset states (both at seed 472003,
12/4 each; seed 472021 unarmed at fractions 0.243/0.242 — one
of its states abstained full instead, 0/0 — and seed 472039
armed at 0.362/0.364 but not taken, falling through to recent8
at 2/14 and 1/15); (c) harm 53 vs guard 49 AND vs the ceiling
0.60 × recent8 79 = 47.4 — above both, the harm concentrated
at the non-engaged states (0/16, 2/14, 1/15 through recent8);
(d) successes 27 vs guard 15 + 16 = 31. Selectivity (b) PASSes
(0/6 at B1, 0/6 at return-A). Additional PASSes in full:
minority TAKEN 4/6 (seeds 473001 and 473017, both checkpoints;
seed 473041 armed but not taken, 0/16 through recent8 at both
checkpoints), selectivity 0/6 / 0/6, harm 53 vs guard 96 and
ceiling 57.6, successes 43 vs guard 0 + 16. The candidate's B2
line is identical to the decisive inverted method's on both
cohorts, per-state and pooled — again a carried outcome of the
engagement draw, not a removal effect and not an inverted-model
effect on these cohorts: where the minority branch engaged,
it scored 12/4, 12/4 (dev) and 10/6, 10/6, 11/5, 12/4 (add)
through the inverted model, and the cross-check confirms the
inverted model's first-frame choices differ from the
minority-set model's at 2/2 minority-fired B2 onset states on
development and 4/4 on additional. What failed on development
is engagement itself (2/6), the term the inverted cycle had
at 5/6 on both cohorts.

**Criterion 5 — release and productivity by checkpoint 32:
FAIL / FAIL** — on sub-condition (c) alone on both cohorts.
(a) abstentions 0/144 on both PASS; (b) successes 62 vs
recent8 64 (line 56) development and 52 vs recent8 45 (line
37) additional PASS — additional EXCEEDS recent8 at k=32;
(d) abstained branch 0/9 on both PASS. (c) non-recent8 branch
in 2/9 switch-stage k=32 states development and 3/9
additional, against the allowance of 1: development — a
return-A minority routing at seed 472021 (purity 0.711,
0/16 vs recent8 2/14, scored through the inverted model) and
a return-A retained routing at seed 472039 (purity exactly
0.700, 5/11 = recent8, outcome-neutral); additional — a B1
retained routing at seed 473001 (purity 0.750, 0/16 vs
recent8 5/11), a B2 minority routing at seed 473001 (purity
0.714, 10/6 vs recent8 11/5, one success worse through the
inverted model), and a return-A retained routing at seed
473041 (purity 0.744, 13/3 vs recent8 0/16, strongly
productive). All five routings sit at purity 0.700–0.750,
just above the leg-P floor. The k=32 line is identical to the
decisive inverted method's on both cohorts. This criterion
has now failed on at least one cohort in every recent cycle
and fails on BOTH here on the same sub-condition; see the
next limitation.

**Criterion 11 — B1/stationary conjunction (carried): FAIL /
FAIL.** Development fails on its B1 side only (criterion 9);
additional fails on its stationary side only (criterion 6).
Each side passes on exactly one cohort and fails on the
other — the conjunction's two sides have effectively swapped
cohorts relative to the inverted cycle, where both sides
failed on both cohorts.

**Criterion 4 — return-A onset harm: PASS / FAIL.**
Development: harm 46 vs guard 62 and ceiling 0.60 × recent8
90 = 54.0, PASS; regular recovery TAKEN 6/6. Additional:
harm 60 vs guard 69 PASS on (a) but ceiling 0.60 × recent8
85 = 51.0 FAIL on (b) by 9.0; regular recovery TAKEN only
3/6 there, the non-engaged states carrying the harm through
recent8. Candidate identical to the decisive method at
return-A onset on both cohorts — the carried profile,
charged unchanged.

**Criterion 2 — return-A recovery successes: PASS / PASS.**
Development: successes 50 vs frozen_A 54 (floor 21.6) and
guard 2 + 16, PASS. Additional: 36 vs frozen_A 68 (floor
27.2) and guard 11 + 16 = 27, PASS. Stated in full, as
registered: cumulative (54 dev / 68 add successes at 42 / 28
harm) and frozen_A (54/42 dev, 68/28 add) beat the candidate
(50/46 dev, 36/60 add) on BOTH axes at return-A on BOTH
cohorts again this cycle — after the inverted cycle, where
that dominance held on development only, the both-cohorts
both-axes pattern resumes.

**Criterion 3 — pooled onset harm: PASS / PASS.** Pooled
onset harm 150 vs guard 177 development and 129 vs guard 218
additional, with all 6/6 individual onset cells <= recent8 on
both cohorts. The candidate's pooled onset line is identical
to the decisive inverted method's on both cohorts (90/150
dev, 79/129 add successes/harm).

**Criterion 7 — full accounting: PASS / PASS.** Replay
identity true at every checkpoint in both cohorts (72/72
entries per cohort); no criterion-7 field missing anywhere;
support_threshold null everywhere; abstention_disarmed_by_support
false everywhere; widened_threshold 3 and
preceding_pair_threshold 1 everywhere; abstention gate /
newest4 / widened_armed recomputable everywhere with 0
mismatches; abstention_trigger_kind in {full, partial, none}
everywhere — never widened, as the removal requires;
preceding-pair-rule == candidate branch everywhere;
widened-rule == decisive inverted branch everywhere;
minority_model_archive_count == archive_events_count
everywhere; minority_model_inverted true everywhere;
minority-model cross-check PASS at every minority-fired state
(8 dev / 8 add: candidate == swapped-archive inverted model
AND candidate == inverted method AND widened-window method ==
minority-set model); learner acquisition actions = 0, learner
training actions = 0, additional requested observations = 0.

**Grading cap (exercised removal): MET on both cohorts** —
and it does not rescue the verdict, because the cap is a
necessary condition for Demonstrated, not a remedy for failed
criteria. The exercised states are both stationary control
states: development seed 472021 k=2 and additional seed 473017
k=8, at each of which the decisive baseline abstained through
the widened class (0/0, 16 abstention episodes) and the
candidate acted on recent8 (5/11 dev, 8/8 add).

**Per-state widened reporting (registered, part of the
grading, not an appendix).** The decisive baseline took ZERO
widened firings at any onset state on either cohort (B1 0/6,
B2 0/6, return-A 0/6 per cohort) and zero at checkpoint 32.
Its widened firings in graded populations are exactly the two
cap states above, both on the stationary control arm, worth
+5 successes / +11 harm (dev) and +8 successes / +8 harm (add)
to the candidate against the abstention's 0/0. One further
widened firing sits outside the graded populations: a
persistence state (development seed 472021, B1 k=16) where the
candidate acted on recent8 and the decisive baseline
abstained. Widened-armed states (records-only in the
candidate): 7 development / 5 additional in total. Candidate
scores differ from the decisive method at 2/72 checkpoints
development and 1/72 additional; from the widened-window
method at 9/72 and 7/72. Onset, the removal is a complete null
on these draws — every onset failure above is a carried
outcome identical to the decisive baseline, and every onset
pass is equally carried.

## Learning evaluation

Candidate vs recent8 (successes / harmful actions /
abstentions per stage-checkpoint cell, pooled over seeds):

Development — B1: k=0 0/48/0 (= recent8 0/48), k=2 0/32/16
(recent8 1/47), k=4 13/19/16 (13/35), k=8 11/37/0 (20/28),
k=16 26/22/0 (= 26/22), k=32 18/30/0 (= 18/30). return-A:
k=0 2/46/0 (=), k=2 25/23/0 (1/47), k=4 25/23/0 (5/43),
k=8 26/22/0 (21/27), k=16 20/28/0 (17/31), k=32 15/33/0
(17/31). B2: k=0 12/36/0 (1/47), k=2 14/34/0 (4/44), k=4
13/19/16 (13/35), k=8 12/20/16 (18/30), k=16 22/10/16
(23/25), k=32 29/19/0 (= 29/19). Control: exact recent8
parity at every checkpoint (105/135/0 pooled vs 105/135/0).

Additional — B1: k=0 2/46/0 (=), k=2 0/16/32 (14/34), k=4
0/0/48 (14/34), k=8 6/42/0 (19/29), k=16 21/27/0 (=), k=32
14/34/0 (19/29). return-A: k=0 14/34/0 (4/44), k=2 24/24/0
(5/43), k=4 12/36/0 (6/42), k=8 24/24/0 (21/27), k=16
32/16/0 (=), k=32 18/30/0 (5/43). B2: k=0 0/48/0 (=), k=2
21/27/0 (0/48), k=4 22/26/0 (0/48), k=8 30/18/0 (12/36),
k=16 14/34/0 (=), k=32 20/28/0 (21/27). Control: k=4
10/22/16 (19/29) — the one carried partial firing — all other
checkpoints at exact recent8 parity; pooled 82/142/16 vs
recent8 91/149/0.

Checkpoint-0 harm (diagnostic, ungraded): 48/46/36 per switch
stage development, 46/34/48 additional — identical in kind to
prior cycles; no method protects first contact.

Retention: past knowledge is retained by construction (the
retained archive and both recovery branches are carried
bit-for-bit) and return-A regular recovery is TAKEN at 6/6
development and 3/6 additional onset states; but the simple
retention baselines (cumulative, frozen_A) again beat the
candidate on both axes at return-A on both cohorts (see
criterion 2), so retention-through-the-archive machinery is
not demonstrated to be worth its routing cost at return-A on
these cohorts. Generalization level: at most handoff level
2–3, in this simulator only — choosing among / applying
designer-supplied representations; no novel-representation or
level-6 claim is made or permitted by the protocol.

## Safety and evidence costs

- Harmful TEST actions (candidate): pooled onset 150 dev /
  129 add (vs recent8 251 / 249, guard 177 / 218); B1 51 / 16;
  B2 53 / 53; return-A 46 / 60; stationary control 135 / 142
  (vs recent8 135 / 149); checkpoint-32 pooled 82 dev / 84 add
  across switch stages (from the per-stage k=32 cells above).
  The removal's fall-through harm is stated per state, not
  netted: at the two exercised control states the candidate's
  acting cost +11 (dev) and +8 (add) harm against the
  abstention's zero, in exchange for +5 / +8 successes.
- Failed-by-abstention: onset 48/288 episodes dev, 80/288 add
  (identical to the decisive method — all carried classes);
  stationary control 0/240 dev, 16/240 add; checkpoint-32
  0/144 both.
- Learner information-acquisition actions: 0 throughout.
  Additional requested observations: 0. Learner training
  actions: 0 — all TRAIN evidence comes from the shared
  external actor stream.
- External TRAIN actor costs (per cohort, counted once across
  seeds' streams as recorded in the detailed results; actual
  harmful / observations): development — A 237/720, B1 68/192,
  B2 85/192, return-A 66/144, control continuation 77/192;
  additional — A 242/720, B1 80/192, B2 73/192, return-A
  37/144, control continuation 60/192. Reported (label-flip
  inclusive) figures and full per-seed accounting are in the
  saved detailed results. These are fixed costs of the shared
  evidence stream, identical for every method, never netted
  against TEST results.
- False confidence / unnecessary abstention: the development
  B2 non-engaged states (harm 16, 14, 15 through recent8 at
  states where the minority branch was armed or abstention
  fired instead) and the additional stationary partial firing
  (a 16-episode refusal at a state where recent8 scored 9/7)
  are the cycle's two clearest instances, one on each side of
  the act/abstain line.
- Report integrity: all figures above are script-computed
  from the saved detailed results at the evaluation commit;
  inspected cohorts (472003-family / 473001-family) are never
  re-tuned against. Provenance limitation: developer-selected
  simulation seeds in the same engineered two-feature simulator
  family as all preceding switch experiments — not independent
  external proof.

## Scientific conclusion

**Failed — NOT a Regression.** Failed under the protocol's
own definitions: PRIMARY criterion 13 FAILs on BOTH cohorts
(development on its B1, B2, and release sides; additional on
its stationary and release sides), and the Failed clause
triggers on the additional cohort several times over
(criteria 13, 6, 5, and 4 all FAIL there; criterion 7 PASSes
both). NOT a Regression: no Regression clause triggers —
pooled onset harm 150/129 is well below recent8's 251/249 on
both cohorts; the control-successes clause requires both
cohorts and development is at exact parity (additional −9);
checkpoint-32 successes 62 and 52 sit above the recent8 − 4
lines of 60 and 41 on both cohorts; the full unit suite and
the historical transfer benchmark pass.

What the experiment actually establishes, stated as
prominently as the failure: the SINGLE changed element did
the narrow thing it was designed to do, on the arm it was
designed to do it on. Removing the widened class cut
stationary abstention volume from the inverted cycle's
48/240 and 64/240 to 0/240 and 16/240, held development's
stationary arm at exact recent8 parity, and was exercised at
exactly one graded state per cohort — both times spending a
widened abstention that was costing successes (the abstained
states scored 0/0; acting scored 5/11 and 8/8). The grading
cap is met on both cohorts. But the removal is an onset null
on these draws, and the conjunction PRIMARY grades the whole
carried profile: B1 engagement failed on development by one
state, B2 engagement collapsed to 2/6 on development with its
harm above guard and ceiling, checkpoint-32 release failed on
both cohorts on routing count, and one carried partial firing
broke additional's stationary successes margin by itself. A
demonstrated stationary-volume repair inside a failing carried
profile is a Failed experiment under this protocol, recorded
exactly that way. Partially demonstrated does not apply (it
requires criterion 13 PASS on both cohorts).

**Next limitation (selected for the next cycle, Priority 1):**
checkpoint-32 release — the non-recent8 recovery routings at
checkpoint 32. Criterion 5 is the only individual co-graded
guard that FAILs on BOTH cohorts in this cycle, on the same
sub-condition (c): non-recent8 branch in 2/9 (dev) and 3/9
(add) of the switch-stage k=32 states against an allowance of
1, with abstentions 0/144, abstained branch 0/9, and successes
above their lines on both — the failure is routing count, not
late abstention and not a productivity collapse. It has now
failed on at least one cohort in each of the last several
cycles (the preceding-pair and inverted cycles' k=32
Regressions were this same mechanism) and this cycle it is
the only both-cohort failure whose mechanism is untouched by
the cycle's changed element. The five routings are mixed in
quality — one harmful minority routing (0/16 vs 2/14), one
harmful retained routing (0/16 vs 5/11), one near-neutral
minority routing (10/6 vs 11/5), one outcome-neutral retained
routing (5/11 = recent8), and one strongly productive retained
routing (13/3 vs 0/16) — and all five sit at reference purity
0.700–0.750, just above the carried leg-P floor, which is a
recorded observation for the next protocol's design basis,
not a tuned threshold. Measurable: on NEW cohorts under a NEW
protocol, whether an evidence-derived condition on the
recovery branches' late (checkpoint-32) routings can hold
criterion 5's frozen form in full on BOTH cohorts (abstentions
<= 36/144, successes >= recent8 − 8, non-recent8 <= 1/9,
abstained 0/9) while holding the stationary profile this cycle
demonstrated on development, B1 engagement, B2 protection, and
return-A harm as co-graded guards. Recorded but not selected:
additional's stationary failure is one carried partial firing
(473017 k=4, purity 0.7812, the whole −9 deficit) with
development at exact parity — single-cohort, single-state,
carried as a guard; development's B1 shortfall is one state
with the removal's share exactly zero; development's B2
failure is an engagement draw (2/6) with the candidate
identical to the decisive baseline, while additional passes
criterion 1 in full — the inverted model's pooled B2 benefit
is therefore demonstrated on the inverted cycle's development
cohort and per-state here, not pooled-replicated here;
additional's criterion 4 failure is the return-A ceiling at
non-engaged states (recovery TAKEN 3/6 there), shared with the
carried baselines; cumulative/frozen_A both-axes return-A
dominance resumes on both cohorts this cycle.

Keep the learner optional and unpromoted, default controller
unchanged, no merge, no AthenZ/Synveil integration,
D1–D10/V2A/V2B unchanged.
