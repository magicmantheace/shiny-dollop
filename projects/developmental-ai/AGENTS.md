# Joint concordance recovery: per-event joint archive recovery — 2026-10-30 (FAILED)

Optional `developmental_ai/joint_concordance_recovery.py`
(identical to the graded retained-recovery candidate in acting
model, signal, archive, concordance definition and recovery model;
the SINGLE change is a per-event JOINT recovery test — recovery iff
at least one newest event is both archive-concordant and
reference-opposed on the SAME event) was evaluated under the
protocol frozen BEFORE implementation at
`benchmarks/joint_concordance_recovery_protocol.json` on NEW
cohorts 332003/332021/332039 and 333001/333017/333041, both now
INSPECTED — never re-tune against them. **Graded Failed under the
protocol's own definitions (criterion 1 FAILs on the additional
cohort — in fact on both, on the exceed-cumulative sub-condition
alone; criterion 4 FAIL development; criterion 5 FAIL both);
NOT a Regression (pooled onset harm well below recent8 on both
cohorts, control successes above recent8, suite + transfer pass).**
Per-criterion, development / additional: C1 return-A successes
FAIL/FAIL (56 vs frozen_A 68 and guard+16=38 — both floors PASS —
but cumulative 60, required >60; 52 vs 60 / 23 PASS, cumulative
64), C2 engagement PASS/PASS (recovery 5/6 return-A states both
cohorts vs the preceding candidate's 1/6; B1 1/6 and 0/6; pooled
rule records-only would-fire 3/6 and 2/6), C3 pooled onset harm
PASS/PASS (165 vs guard 166 — by one action — 5/6 cells ≤ recent8;
156 vs 185, 6/6), C4 return-A harm FAIL/PASS (40 vs guard 42 PASS
but ceiling 37.8; 44 vs 73 and ceiling 51.6 PASS), C5 release
FAIL/FAIL (abstentions 0/144 and 16/144 PASS, but k=32 successes
58 vs recent8 77 and 77 vs 86 — required ≥69 / ≥78), C6 stationary
selectivity PASS/PASS (0/240 abstentions; 97 vs 91 successes /
143 vs 149 harm; 130 vs 120 / 110 vs 120; control recovery 1/15
and 3/15 graded states), C7 full accounting PASS/PASS (decision
records incl. per-event joint flags complete, replay identity
true everywhere, learner acquisition 0). Diagnosis: engagement is
solved — in every firing state the candidate matched cumulative
exactly, and the whole C1 deficit is the single
opposed_count == 0 blind-spot state per cohort (−4 / −12). The
new failure is persistence: the gate never expires, so at k=32
two development stale-archive routings scored 0/16 each (B1 and
B2) and one additional B1 abstention cost 9 successes, failing
C5 on both cohorts. Full unit suite (920) and historical transfer
benchmark passed in the evaluation and grading stages; no CI
claimed for the evaluation or grading commits (UNVERIFIED). See
`docs/JOINT_CONCORDANCE_RECOVERY.md`. Keep the learner optional
and unpromoted, default controller unchanged, no merge, no
AthenZ/Synveil integration, D1–D10/V2A/V2B unchanged. Next
limitation selected: P1 gate persistence without expiry —
whether an evidence-derived onset-bounded gate can keep the
onset profile while restoring k=32 productivity, on NEW cohorts
under a NEW protocol.

# Evidence-opposition retained recovery: signal-gated archive recovery — 2026-10-30 (FAILED)

Optional `developmental_ai/evidence_opposition_retained_recovery.py`
(recent8 acting model exactly; graded guard's evidence-opposition
signal reused unchanged; plus a retained-archive concordance test —
act through an archive-only relation model iff both newest events
are archive-concordant AND at least one is opposed; else abstain iff
opposed_count == 2; else recent8) was evaluated under the protocol
frozen BEFORE implementation at
`benchmarks/evidence_opposition_retained_recovery_protocol.json` on
NEW cohorts 322003/322021/322039 and 323001/323017/323041, both now
INSPECTED — never re-tune against them. **Graded Failed under the
protocol's own definitions (criteria 1–4 FAIL on both cohorts);
NOT a Regression (pooled onset harm equal to recent8 on development,
below on additional; control successes equal/above; suite +
transfer pass). The cumulative-dominance cap is also triggered on
both cohorts.** Per-criterion, development / additional: C1 return-A
successes FAIL/FAIL (23 vs frozen_A 64, floor 25.6 and guard+16=30;
18 vs 66, floor 26.4 and 29), C2 engagement FAIL/FAIL (recovery
fired 1/6 return-A onset states both cohorts, required ≥2; B1 0/6),
C3 pooled onset harm FAIL/FAIL (262 vs guard 255 and recent8 262,
ceiling 196.5; 231 vs guard 236 PASS but ceiling 190.5 FAIL),
C4 return-A harm FAIL/FAIL (73 vs guard 66 and ceiling 43.8; 78 vs
guard 83 PASS but ceiling 49.8 FAIL), C5 release PASS/PASS
(0/144 abstentions at k=32; successes 57 vs recent8 62, 65=65),
C6 stationary selectivity PASS/PASS (0/240 abstentions; dev
identical to recent8, add 148 vs 146 successes / 92 vs 94 harm),
C7 full accounting PASS/PASS (decision records complete incl.
archive concordance records, replay identity true everywhere,
learner acquisition 0). Diagnosis: the both-events concordance
requirement squares a per-event rate realized at ~1/2–2/3 —
concordant_count == 1 in 5/6 return-A onset states in BOTH cohorts,
the protocol's pre-registered failure mode 1. Where recovery fired
it converted as designed (additional firing state 11 succ / 5 harm
vs recent8 6 / 10); false recovery at B1 never occurred. Plain
cumulative retention (return-A 58 / 66 successes at 38 / 30 harm)
dominates the gated recovery — at a first return, retained knowledge
did not need this sparse gate. Full unit suite (895) and historical
transfer benchmark passed in the evaluation and grading stages; no
CI claimed for the evaluation or grading commits (UNVERIFIED). See
`docs/EVIDENCE_OPPOSITION_RETAINED_RECOVERY.md`. Keep the learner
optional and unpromoted, default controller unchanged, no merge,
no AthenZ/Synveil integration, D1–D10/V2A/V2B unchanged. Next
limitation selected: P1 recovery engagement sparsity — whether a
less sparse concordance test can engage at materially more return-A
states and beat cumulative, on NEW cohorts under a NEW protocol.

# Evidence-opposition onset guard: evidence-count gate — 2026-10-29 (DEMONSTRATED, simulator-bounded)

Optional `developmental_ai/evidence_opposition_onset_guard.py`
(recent8 acting model exactly, plus a gate from the observed
evidence itself: hard span-majority expectation from the 24 events
preceding the newest 2; abstain iff both newest events are matched
and opposed; NO fitted probabilities in the signal) was evaluated
under the protocol frozen BEFORE implementation at
`benchmarks/evidence_opposition_onset_guard_protocol.json` on NEW
cohorts 312003/312021/312039 and 313001/313017/313041, both now
INSPECTED — never re-tune against them. **Graded Demonstrated under
the protocol's own definitions (all six criteria PASS on both
cohorts, full suite + transfer pass); NOT a general-intelligence
or calibrated-uncertainty claim — handoff level 2–3, this
simulator only.** Per-criterion, development / additional: C1
signal separation PASS/PASS (onset mean opposed 1.056 / 1.000 vs
control (k=2,4) 0.000 / 0.167; gaps 1.056 / 0.833 vs ≥0.5
required), C2 gate firing PASS/PASS (5/18 onset states, 0/15
graded control states, both cohorts), C3 onset harm PASS/PASS
narrowly (185 vs recent8 250, ceiling 187.5; 198 vs 270, ceiling
202.5; 6/6 cells ≤ recent8 both cohorts), C4 release PASS/PASS
(0/144 abstentions at k=32; successes 65=65 dev, 59=59 add),
C5 stationary selectivity PASS/PASS (0/240 abstentions; successes
and harm identical to recent8), C6 full accounting PASS/PASS
(signal records complete, replay identity true everywhere,
learner acquisition 0). The two preceding probability-derived
gates were silent at onset; the evidence-count signal is not.
Honest limits: absolute onset harm remains high (185 / 198 of
288 onset episode-checkpoints); the gate fires at only ~1/3 of
onset states (opposed_count 1 in 9/18 dev and 8/18 add onset
states); k=8/16 persistence costs successes (dev B1-16 5 vs
recent8 26; add B1-8 10 vs 27); onset successes fall vs recent8
(23 vs 38 dev; 10 vs 18 add) because abstention, not adaptation,
is the response; at return-A onset frozen_A scores 68 / 70 pooled
successes vs the candidate's 10 / 4 — detection without recovery.
Full unit suite (873) and historical transfer benchmark passed
in the evaluation and grading stages; no CI claimed for the
evaluation or grading commits (UNVERIFIED). See
`docs/EVIDENCE_OPPOSITION_ONSET_GUARD.md`. Keep the learner
optional and unpromoted, default controller unchanged, no merge,
no AthenZ/Synveil integration, D1–D10/V2A/V2B unchanged. Next
limitation selected: P1 detection without recovery — at a return
to a previously learned rule the only protective response is
abstention, forfeiting immediately usable retained knowledge.

# First-contact onset guard: contradiction gate — 2026-10-28 (FAILED)

Optional `developmental_ai/first_contact_onset_guard.py`
(recent8 acting model exactly, plus a count-based contradiction
gate on its own strict prequential predictions over the newest 4
events: abstain if ≥2 assigned probability < 0.125) was evaluated
under the protocol frozen BEFORE implementation at
`benchmarks/first_contact_onset_guard_protocol.json` on NEW
cohorts 302003/302021/302039 and 303001/303017/303041, both now
INSPECTED — never re-tune against them. **Graded Failed (protocol
definition: criteria 1–2 fail on the additional cohort); NOT a
Regression (onset harm equal/lower vs recent8, control successes
identical, suite + transfer pass).** Per-criterion: C1 FAIL/FAIL
(dev pooled onset harm 260 vs recent8 260, ceiling 195; add 206
vs 222, ceiling 166.5), C2 FAIL/FAIL (onset abstentions dev
0/288, add 16/288 from ONE firing onset state; required ≥48),
C3 PASS/PASS (trivially — gate never fired at k=8 either),
C4 PASS/PASS (0 graded-control abstentions; one ungraded
control-0 false-fire on stationary evidence, additional seed
303017), C5 PASS/PASS (full gate records, replay identity true
everywhere, learner acquisition 0). Diagnosis: the detection
signal, not the abstention response, is missing — contradiction
count 0 in 28/36 onset states; only 9/144 onset prequential
probabilities < 0.125, because sparse 8-event fits assign
≈0.33 to reversed outcomes. Both abstention triggers tried so
far (mean log-score, contradiction count) derive from the same
sparse model's probabilities and are silent at onset. Full unit
suite (851) and historical transfer benchmark passed in the
evaluation and grading stages; no CI claimed for the evaluation
or grading commits (UNVERIFIED). See
`docs/FIRST_CONTACT_ONSET_GUARD.md`. Keep the learner optional
and unpromoted, default controller unchanged, no merge, no
AthenZ/Synveil integration, D1–D10/V2A/V2B unchanged. Next
limitation selected: P1/P2 — onset signal absence in the acting
model's own probabilities; next cycle tests a change signal
computed from the observed evidence itself.

# Early post-switch adaptation: gated archive — 2026-10-28 (FAILED / regression)

Optional `developmental_ai/gated_archive_prequential_memory.py`
(immutable 192-event archive, displacement margin 1.0, contradiction
override ≥2/4 at archive p<0.125, adequacy gate at mean prequential
log-score −1.2) was evaluated under the protocol frozen BEFORE
implementation at `benchmarks/early_post_switch_adaptation_protocol.json`
on NEW cohorts 292003/292021/292039 and 293001/293017/293041, both
now INSPECTED — never re-tune against them. **Graded Failed (protocol
definition: criteria 1–3 fail on the additional cohort) and a
Regression vs recent8 (criteria 1 and 2 worse on both cohorts).**
Per-criterion: C1 FAIL/FAIL (dev B2-8 5 vs recent8 9; add B1-8 9 vs
15, B2-8 0 vs 15), C2 FAIL/FAIL (harm exceeds recent8 at 10/21 dev
and 9/21 add stage-checkpoints; onset harm 48/96 at most onsets),
C3 PASS dev (29 vs required 27) / FAIL add (24 vs 32), C4 PASS/PASS
vacuously (**0 abstentions at every checkpoint in both cohorts —
the adequacy gate never fired**), C5 FAIL/FAIL (no archive selected
at B-64, but B-64 harm 10–28/96 vs ≤8 limit; dev control archive
only 15/18 vs ≥17), C6 PASS/PASS (full per-seed TRAIN/TEST
accounting, learner acquisition 0, replay identity true everywhere).
Early contradiction override routes to recent32, still A-dominated
at k≤4, reproducing obsolete-model harm. Full unit suite and
historical transfer benchmark passed in the evaluation stage; no
CI claimed for the evaluation or grading commits (UNVERIFIED).
See `docs/EARLY_POST_SWITCH_ADAPTATION.md`. Keep the learner
optional and unpromoted, default controller unchanged, no merge,
no AthenZ/Synveil integration, D1–D10/V2A/V2B unchanged. Next
limitation selected: P1 first-contact onset behavior (k=0–4) —
acting without abstention on contradicted models.

# Paired public outcome witness verification — 2026-10-22

Research-only `developmental_ai/paired_witness.py` requires
two signed matching public event histories from **separate
fixture HMAC-SHA256 keys** before admitting any observations.
Protocol `benchmarks/paired_witness_protocol.json` frozen
before implementation. Six now INSPECTED seeds, 60 TEST
tasks each: paired honest signers **286/360 successes**,
**4 harmful TEST actions**; forged primary plus honest
witness **0/360 and 0 harm by 360 abstentions**; missing
or changed-after-signing witness also all abstain.
**Both colluding fixture signers** pass all matching MACs
and achieve **22/360** with **338 damaging TEST actions**,
the identical outcome of bypassing the gate and trusting a
single forged corpus. Actor's **319 harmful /1,440 distinct
training actions** were relabeled as productive; forged
streams replay SAME actor actions, no double counting.
Focused run **39772852676** passed 11/11 tests and both
cohorts. These fixed fixture keys authenticate possession
only, NOT truthful physical events, real identity,
independence, consent or robust real-world safety. The
benchmark can sign both streams by design; physical truth
flag is always false for the candidate. Full Linux/Windows
historical run is a separate gate. See
`docs/PAIRED_WITNESS.md`. Maintain experimental draft PR,
main/default policies unchanged, no outside actuation or
AthenZ/Synveil integration, D1/D3/D4 still open; preserve
V2A before/overlapping V2B ordering.

# Passive evidence quality audit — 2026-10-22

The optional `passive_quality.py` audit uses only public
numeric action-feature opportunities from **60 independent
unacted simulation frames per seed** and coarse feature
coverage. Earlier passive archives remain untouched.
Precommitted protocol:
`benchmarks/passive_quality_protocol.json`.
[Focused run 39722045466] passed 11/11 regression tests
and both seed cohorts. Across six now INSPECTED seeds:
random-observer memory completed **269/360** third-rule
tasks, **4 harmful test actions**; biased-observer memory
**13/360**, **66 test harms**, but a coverage gate rejected
all biased datasets and abstained on **360/360** tasks.
A *coherently falsified* training stream (328 actually damaging
outcomes rewritten as productive) passed coverage **6/6**
and replay integrity, but its model completed only
**33/360** tasks and caused **327 harmful test actions**.
The forged corpus reuses the original random actor's
events; the genuinely separate training actors caused
**328 random + 513 biased = 841** harms in **2,880** action
events, not zero. No dataset received real source
authentication. Valid checksum or covariate coverage
CANNOT prove public physical sensor changes truly happened.
The first focused run expected exactly 60 falsifications
on a seed with only 58 harmful outcomes; this was
corrected to frozen **up to 60** requirement without
changing seeds/method. Full historical CI is separate.
See `docs/PASSIVE_QUALITY.md`. This is NOT deployable
safety, independent physics learning or D1/D3/D4.
Keep experimental PR draft/unmerged, main and defaults
unchanged, no AthenZ/Synveil work; preserve V2A/V2B order.

# Passive outcome learning on the third numeric rule — 2026-10-21

Optional `developmental_ai/passive_outcome_learning.py` accepts only
already-executed *public before/action/after transitions* from
independent simulated actors. It never chooses an action to
collect its own training data. A synthetic random actor
provided 240 third-rule events per seed across six now
INSPECTED seeds. Raw five-nearest-neighbor model trained
on those observations completed **253/360** held-out third-rule
tasks, with **10 harmful TEST actions**; conservative
filter completed **160/360** with the **same 10 harms**.
A 24-event filtered learner completed **22/360**. A biased
old-normal-policy actor produced only **13 productive events**
of 1,440 events, and its guarded passive learner completed
**0/360**. The frozen old normal and reversed memories
remained at 0/360 with 293 and 296 harms respectively.
Passive data does NOT mean harmless data collection: random
actor incurred **302 harmful actions in 1,440 recorded events**,
and separate biased actor **450/1,440**. The random24 prefix
is a subset (34 harmful events already counted in the
random240 total). The observer and learner are both only
simulated and no human consent/provenance verification exists.
The archive is replayable by SHA-256 but not authenticated.
[Focused CI 39718642738] passed **11/11** tests and both
three-seed cohorts; final full historical regression is
a separate gate. Frozen protocol
`benchmarks/passive_outcome_protocol.json`,
full report `docs/PASSIVE_OUTCOME_LEARNING.md`.
This is NOT zero-shot unknown law competence, risk-free
learning, independent world transfer, general self-developed
intelligence or D1/D3/D4 completion. No automatic policy
promotion. Keep PR draft, main untouched, AthenZ/Synveil
integration deferred and V2A then V2B ordering unchanged.

# Absolute outcome adequacy: noisy and never-trained third feature rule — 2026-10-21

Optional `developmental_ai/absolute_adequacy.py` and
`novel_feature_world.py` retain original two engineered numeric
outcome models. An eight-probe public-only offline calibration
compares per-window **absolute** predictive fit (mean negative
log likelihood threshold 1.2) plus previous relative margin.
One new simulator rule makes near-diagonal features productive,
a rule neither source model has been trained on; known normal/
reversed regimes have hash-deterministic 10% neutralizing noise.
Frozen protocol `benchmarks/absolute_adequacy_protocol.json`
was committed before candidate code. On six now-INSPECTED
seeds, adequacy gate scored noisy normal **202/360**, reversed
**151/360**, third **0/360** with all 6 unknown contexts
identified and **0 harmful third-world test actions**.
Relative-only control scored 244/360, 222/360, 0/360,
but caused **192 harmful test actions** in the third world.
Absolute gate made **3/12 false unknown decisions** on known
noisy worlds. **56/144 calibration actions damaged disposable
simulators**, including 16/48 against the unfamiliar rule.
Third-rule oracle is 360/360, showing tasks are feasible, but
candidate **does not learn** the third rule and only abstains.
Focused GitHub CI 39717495708 passed 8/8 and both seed cohorts.
See `docs/ABSOLUTE_ADEQUACY.md`. This is NOT safe exploration,
blind naturalistic transfer, general cognition or D3/D4.
Preserve all original tests; keep PR draft, main/default
unchanged and Synveil/AthenZ integration deferred.

# Two-window confirmation evidence (2026-10-21)

The optional `two_window_confirmation.py` experiment is
simulation-only and cannot be promoted automatically. Preserve
`benchmarks/two_window_confirmation_protocol.json`, its six
already inspected seeds, and the original single/fixed-12 calibration
benchmarks. The new public-observation-only test compares first4,
two-window agreement, last4, pooled8, abstention and private oracle
on stationary rules and both four-step rule-change directions.
Full scores over 360 tasks per condition: first4 stationary
360/360 each but switched 0/360 each with **720 test damages**;
agreement8 stationary normal 360/360, reversed 300/360,
switched 0/360 each with zero *test* damage; recent8 stationary
normal 360/360, reversed 300/360, switched 300/360 and 360/360
with zero *test* damage; pooled8 switched 0/360 and 240/360
with **60** test damages. Across all six seeds and four worlds,
four-probe strategy costs 96 disposable probes/**32 calibration harms**,
all eight-probe strategies 192/**58** harms. Do not hide abstentions
as completed tasks or simulator-only probe harms. Stable numerical
features, engineered reversal and two candidate models do not
demonstrate generic causal discovery or safe active exploration.
Results are post-hoc and D1/D3/D4 remain OPEN; keep historic
transfer, V2A/V2B and AthenZ/Synveil separation intact.
See `docs/TWO_WINDOW_CONFIRMATION.md`.

# Numeric consequence reversal calibration — 2026-10-21

The optional `observable_reversal_calibration.py` experiment fits an
engineered-feature source model from 80 normal `collect` episodes
and a separate reversed-rule model from 80 `route-reversed` episodes.
It selects between these **already trained** models using the public
effects of 12 disposable training-namespace interventions, with an
explicit minimum evidence/margin abstention criterion and exact
replay checks. On six INSPECTED seeds (test indices 14000..14059),
both normal and reversed test worlds reached **360/360** completions
and 0 *test* damage, but **56/144 calibration interventions damaged
the simulated rehearsal worlds**. The deliberately wrong-calibration
control caused **720/720 test failures and damaging actions**, and
abstention avoided harm but completed no tasks. Frozen protocol:
`benchmarks/observable_reversal_calibration_protocol.json`;
full report: `docs/OBSERVABLE_REVERSAL_CALIBRATION.md`.

The numeric features and physics are engineered, all seeds inspected;
this is NOT blind cross-domain generalization, real-world safe
experimentation, automatically learned new causal dynamics or
authenticated model promotion. Preserve original numeric affordance
negative results, rerun nine focused tests, both calibration cohorts,
full Linux/Windows unit tests and original frozen transfer benchmark.
Keep experimental PR draft, main/defaults/real actions unchanged,
AthenZ/Synveil integration deferred, D1/D3/D4 open and V2A/V2B order.

# Numeric public-feature transfer research — October 21, 2026

A new isolated `observable_affordances.py` experiment no longer
hashes simulator-private action names into stable identity codes:
instead each fresh per-episode action has two **engineered public
physical measurements**. A 5-nearest-neighbor model learns
measurement → progress/damage from 80 unfiltered source tasks per
seed, then faces a new generated task family with 0 target
training. **Both families deliberately share a simple fixed
feature law**. On 6 inspected seeds numeric model completed
collect **360/360**, route **360/360**, while untrained route
was **31/360** and shuffled-feature route **16/360**. When
the feature law is reversed, numeric policy fails **0/360**
and incurs **360 damage actions**. Preserve this severe
negative result, all stronger controls, seed cohorts and
the original transfer/legacy benchmarks. Neither artificial
feature correlations nor near-perfect toy scores establish
independent semantic understanding, robust safety or D3/D4.
Run `tests.test_observable_affordances` and both
`benchmarks.observable_affordance_benchmark` cohorts,
plus full Linux and Windows validation. All seeds are now
inspected. Do not merge/promote the experimental branch,
modify AthenZ/Synveil or authorize external actions.
See `docs/OBSERVABLE_AFFORDANCE_TRANSFER.md`.

# Verified quarantined C study — 2026-10-21

The optional quarantined C candidate passed its **dedicated** two-cohort
GitHub benchmark at source commit `8d76bc2`. Six INSPECTED seeds
scored `staged_C` A/B/C **360/360 each**, 0 spoilage/stalls;
old sentinel A/B 360/360 but C 0/360; **C-only memory**
A/B 0/360 (442 accepted spoilage actions across A+B (221 per environment)), C 360/360;
untrained novel A/B/C 138/360 each; privileged oracle 360/360 each.
This study used **80 C simulator episodes per seed** plus prior A/B
training and per-seed separate 24/24 A/B/C *train-validation* gates.
All six `approved=True` calls were **simulated harness inputs**,
not actual owner permission. No production promotion occurred.
The task remains one deterministic hand-authored cargo world with
simulator-hashed stable numeric action IDs. Hence this is NOT
zero-shot C, independent transfer, safe novel action discovery,
real authenticated autonomy, or D3/D4 completion. See
`docs/QUARANTINED_C_ADAPTATION.md`. Preserve every frozen
benchmark/negative control and keep PR draft/unmerged.

# Quarantined C adaptation (2026-10-21)

Quarantined, simulation-only `developmental_ai/quarantined_c.py`
stores a new C `RiskMemory` from **80 separate C training
episodes**, after the dual-sentinel controller correctly flagged all
360 C episodes as unknown while completing 0 C goals. The code
rehearses 24 **disjoint train-namespace** A/B/C episodes per seed,
rejecting any C risk candidate that overlaps known risks or fails a
24/24 goal, zero-spoilage, zero-stall criterion. Receipt review,
single-use explicit approval and stale-memory checks are sandbox
programming constructs, NOT verified human authorization. Test
`approved=True` only represents a simulated caller. All three
environments retain engineered two-byte action identity descriptors,
one deterministic cargo simulator, and already-inspected cohorts.
Do NOT call this independent generalization or D3/D4 completion,
do not auto-promote or deploy, do not alter AthenZ/Synveil.
See `docs/QUARANTINED_C_ADAPTATION.md`. Dedicated workflow
`quarantined-c-validation.yml` checks complete cohorts;
historical full CI and test suite must remain intact.

The optional `prerequisite_recovery.py` is a **post-hoc, engineered
handoff** to the old `OutcomeSkills.choose` policy after new action effects
are observed. It is not a corrected causal learner, independent transfer, or
proof of lifelong learning. Retain the severe 1-episode regression and
earlier raw-prober negative results. On changes, run
`tests.test_prerequisite_recovery`, both cohorts of
`benchmarks.prerequisite_recovery_benchmark`, the full repository tests,
the original transfer benchmark and focused Windows checks. Checkpoint
source boundaries must replay exactly; no default-model promotion or
AthenZ/Synveil work. See `docs/PREREQUISITE_RECOVERY.md`.

# Unknown-regime stress audit (2026-10-21)

The latest *experimental* no-cue learner correctly selected A/B histories
from one public intervention on all six **inspected** seeds: 360/360 per
A→B→A stage, compared to 147/360 on B for the same probe followed
by permanently selecting A. This benchmark was green on Linux
(562/562 tests) and Windows (104/104 focused). This is two-known-
context retrieval, not autonomous discovery of a new regime.

An omitted strong baseline has now been added: **union of all risk codes
flagged by either historical memory**, with no diagnostic or regime
choice. A third, **never-trained mapping C** swaps signatures for the
harmful action and a necessary *fuel* action (not the harmless wash
distractor). The current study is post-hoc, keeps all pre-inspected
seeds, and compares no-cue inference, union-risk, frozen A/B, novel
and privileged hazard oracle, with spoilage/stalls measured.
Its protocol was committed first at
`benchmarks/unseen_regime_protocol.json`. See
`docs/UNSEEN_REGIME_AUDIT.md`. The union is NOT generally safe,
and cannot recognize newly harmful meanings absent from memories.

Do not claim independent generalization, automatic novelty detection,
causal safety, retained skill discovery or D3/D4 milestone completion.
Keep all baselines, negative outcomes, default policies and
AthenZ/Synveil integrations unchanged. Validate full Linux/Windows
tests, historical transfer, and both
`benchmarks.unseen_regime_benchmark` inspected cohorts.

# Latest retained context-indexed learning experiment (2026-10-21)

A new optional A→B→A descriptor-remapping study has two
replayable `RiskMemory` stores and a publicly supplied, perfectly
distinguishing two-number context beacon. The generator keeps cargo
physics the same but swaps numeric identities of a harmless and a
harmful action. **Both prior memories are trained separately**, each on
80 cargo episodes, and a context nearest-neighbor lookup picks a store.
This is **memory retrieval with an engineered cue**, NOT latent change
detection, autonomous regime discovery or independent transfer.
The protocol at `benchmarks/contextual_affordance_protocol.json`
was frozen first. On six now-inspected seeds, exact A→B→A results
were **360/360 in each stage** versus changed-B frozen A-only
**128/360**, untrained **130/360**, and ambiguous-cue **128/360**.
The first development run was blocked by a two-byte hash collision
on frozen seed 51013; it was repaired deterministically within the
optional simulator instead of changing seeds. All previous physics,
experimental protocols and default policies were untouched.
See `docs/CONTEXTUAL_AFFORDANCE.md`.

Run `tests.test_contextual_affordance`, both
`benchmarks.contextual_affordance_benchmark` cohorts, full unit
suite and unchanged three-seed historical transfer regression on
changes. Never claim blind generalization, statistically reliable
real-world safety, user consent, self-development or automatic policy
promotion. Keep AthenZ/Synveil integration deferred.

# Current evidence: stable affordance-memory experiment (2026-10-21)

`affordance_memory.py` adds optional *engineered stable two-byte numeric
action descriptors* to unchanged `OpaqueWorld` cargo and relay. A
`RiskMemory` model replays exactly 80 cargo training episodes and
identifies observational failure-associated features from public actions,
numeric sensor deltas and terminal outcome. The code/benchmark protocol
was committed first (`benchmarks/affordance_protocol.json`). This is
**within-family cargo adaptation**, NOT independent semantic inference:
descriptors are simulator-created, seed/family-scoped re-encodings of
hidden action identities. On six now-inspected seeds, trained cargo
360/360 versus fixed novel 136/360, shuffled-descriptor 136/360,
cyclic 134/360 and privileged risk oracle 360/360. Relay retention
remained 360/360 but fixed methods were already at ceiling. A
causally confounded risk association is not guaranteed safe outside
this fixed simulator. No promotion/merge by default.

Keep both cohorts, strong controls, training budget, descriptors and
historical protocols fixed; run `tests.test_affordance_memory`,
`benchmarks.affordance_benchmark` (development AND reserved), full
suite and original three-seed transfer before changing. Preserve negative
results and make no AthenZ/Synveil integration edits. Details:
`docs/AFFORDANCE_MEMORY.md`.

# Latest cross-dynamics result — 2026-10-20

`developmental_ai/opaque_causal.py` and
`benchmarks.opaque_causal_benchmark` use different hand-coded hidden
relay/cargo dynamics, per-episode rotated anonymous action handles and
sensor channels, a common **engineered** numeric observation contract,
and a relay-only learned choice among three prewritten exploration
strategies. The protocol at `benchmarks/opaque_causal_protocol.json`
was committed before model execution. Both seed groups are now
**inspected**; they must not be presented as fresh blind holdouts.
The strategy selector chose fixed `novel` on all six seeds: cargo
147/360 versus cyclic 145/360, random 82/360, privileged oracle
360/360. This is NOT evidence of meaningful semantic generalization;
irreversible spoilage explains most failures. Preserve all controls,
report both source/target families and all seeds, and run
`tests.test_opaque_causal` and both cohorts plus the full and frozen
transfer suites on changes. No AthenZ/Synveil integration.

Historical notes in this file about GitHub Actions startup failure are
outdated: the isolated fallback-policy branch has had fully successful
Linux/Windows CI. **Only claim success for the exact current commit**.

# Critical development override — 2026-10-20

**Standalone learning first.** This directive supersedes earlier instructions
that would prioritize AthenZ, Synveil, integration plumbing, IPC, synthetic
adapters, UI work, or unrelated infrastructure. Preserve functioning
integration code and leave its existing PR unmerged, but do not implement or
complete integrations unless separately authorized. Do not modify AthenZ
or Synveil repositories in this development phase.

Every development pass should attempt multiple meaningful, related
implementation tasks where possible. Measure improvements over strong
baselines, with unchanged historical protocols and explicit negative results.
Priority order: (1) generalization beyond a single simulator family,
(2) long-term experiential/semantic/procedural memory, (3) continual
learning and retention, (4) learned reusable skills and composition,
(5) bounded autonomous simulated goals, (6) sample/compute efficiency.

The optional `benchmarks.continual_skill_benchmark` is a later
development-only target-adaptation/retention follow-up. It **does train** on
the nominally unseen delivery task before reporting later success and thus
cannot be called zero-shot transfer. Source-trained agents have 80 extra
source episodes relative to the matched target-only training control. Preserve
the earlier 0/360 unadapted delivery result. Report the complete learning
curve, the return-to-assembly check, action cost, reference oracle, unchanged
source control, and full checkpoint replay. See
`docs/CONTINUAL_SKILL_RETENTION.md` and run both cohorts plus its focused
tests when changing this experiment. Do not portray the shared glyph action
ontology, repeated test indices, or inspected cohorts as blind independent
task-family generalization.

The optional `prerequisite_probing.py` and
`benchmarks.prerequisite_probing_benchmark` use **observational** failed/
successful action contexts; singleton fact-set differences are *suggestive*,
not verified causal prerequisites. The tool must never access simulator
`RECIPES` or private state, promote itself as default, or authorize actions.
Preserve the prior zero-shot protocol and negative results. The additional
development study showed raw probing 40/180 at zero target training but 0/180
after 4 or 20 target episodes while the existing controller reached 180/180
at those stages, in an isolated local reproduction. The train-only
validation-selected controller retains the existing policy when new
learning regresses; this is **not** independent generalization or proved
safe lifelong learning. Run its focused tests, both six-seed development
cohorts, full suite, and historical transfer benchmark before merging.
See `docs/PREREQUISITE_PROBING.md`. Private Actions are still blocked
before any jobs start; never claim full validation or merge readiness.

The new optional `outcome_skills.py` experiment has **engineered shared
glyphs and fact semantics**; its assembly success and delivery failures do
NOT close D3 or D4. Run `tests.test_outcome_skills` and
`benchmarks.outcome_skills_benchmark` on both documented cohorts if you
modify it. Document each phase of evaluation as development, supplemental
inspected, or genuinely independent. See `docs/OUTCOME_SKILLS.md`.

Do not automatically promote policy or weight changes. Staged candidates
must be reviewed and approved. `policy_review.py` is a research-stage
regression gate, not a guarantee of safe lifelong learning. Require
restart/corruption regression tests for schema changes and run the **full**
test suite plus unchanged original transfer benchmark before merging.
Both current Linux and Windows Actions jobs fail before executing any
steps; this is **not a passing CI signal**. A local scoped test does not
establish full repository validation. Preserve V2A (computational affect)
before and overlapping V2B (virtual home) in the longer roadmap.

---

# Worker instructions

**Purpose:** Build a verifiable local-first learning engine for the independent-twin research program, due 2029-02-09. Own simulations, policies, procedural memory, reproducible evaluation, and tested integration APIs only.

1. Inspect the current Git branch and tests before changes; do several coherent tasks per pass when practical. Use meaningful commits and verify result; do not claim CI/hardware passed without evidence.
2. Run `python -m unittest discover -s tests -v`. For algorithm changes, run `python -m benchmarks.transfer_benchmark` and report all seeds, not only the best result.
3. Never commit `.db`/SQLite/WAL, private model weights, user stories, biometric data, secrets or consenting-person records. Keep such data in separately protected, owner-controlled local storage.
4. Report held-out data contamination and test tuning. A frozen evaluation protocol should not be modified merely to improve a reported score. Preserve baseline outcomes.
5. State limits exactly: the present transfer experiment varies maps of one family, with engineered directional observations. It does not prove broad intelligence or emergence of identity.
6. Keep AthenZ and Synveil as optional, versioned external integrations. No policy-derived root shell, automatic sharing, publishing, or unrestricted action execution.
7. Make persisted schema migrations and restart/resume regression tests explicit.
8. Before committing changes, verify repository visibility; assume code becomes public even if it is currently private.

9. Run `python -m benchmarks.delayed_choice_benchmark` for changes touching the
   delayed-cue memory experiment; publish all three mode ablations and all
   development seeds. Never describe its hard-coded retention gate as learned.
10. Event-ledger SHA-256 links are not provenance signatures or evidence of an
    authorized user. Do not add network, shell or system-action execution to the
    simulation-only ledger exporter.
11. Learned selective-memory claims require running `python -m benchmarks.selective_memory_benchmark`, comparing learned vs first/last/random and oracle, and explicitly disclosing the engineered context/source features and inspected development seeds.

12. Changes to occluded navigation must rerun the multi-seed
    `python -m benchmarks.occluded_navigation_benchmark`, preserve separate
    train/test indices and compare against learned-reactive, random, greedy
    and privileged full-map oracle baselines. Never call engineered dead
    reckoning a learned memory mechanism.

13. For `adaptive_dynamics.py` changes, rerun the full three-seed adaptive benchmark and report old-regime regression as well as new-regime gains, oracle predictive loss and navigation scores. Calibrated physics uses explicit **privileged simulation labels**; do not portray it as an independently discovered latent world model. Named snapshots are retained knowledge, not automatic context switching.

14. Changes to `online_dynamics.py` must run the full three-seed
    `python -m benchmarks.online_dynamics_benchmark` and report per-regime
    model selection, likelihood, wrong-model and privileged-oracle baselines.
    Do not mislabel initial-position-beacon/known-topology latent-state EM as
    unsupervised discovery of general physics or automatic continuous learning.

15. For `continuous_dynamics.py` changes, run both the three-seed main benchmark
    and additional-seed audit with the **same full model-training budget**.
    Retain the published small-budget failure rather than tuning it away.
    The monitor scores unlabelled *per-episode* observation streams against
    manually pretrained models; this is not self-sufficient discovery of new
    dynamics, within-episode control or a calibrated anomaly detector.

16. `step_dynamics.py` experiments must compare each incremental log-likelihood
    to the full latent forward likelihood, test exact mid-episode restarts,
    reject unknown labels in sensor records, and disclose changed-regime
    detection failures. Never describe the simple digest approval token as
    authenticated consent or stage candidate training as automatic promotion.
    Run `python -m benchmarks.step_dynamics_benchmark` and the original
    `python -m benchmarks.transfer_benchmark` unchanged.


16. Offline-calibrated step detection must never consume `test` namespace
    histories during calibration. Use `train` indices `5000+`, disjoint from
    model-fit `train` indices `0..N-1`. Keep the original `margin=0.12`
    detector unchanged, publish per-seed correct/wrong/abstained selection on
    development and additional audit seeds, and state that offline labels
    calibrate a heuristic threshold, **not** confidence probabilities.

17. `decision_abstention.py` introduces *read-only selective abstention*, not new model accuracy or a confidence probability. Preserve the frozen StepDetector baseline, use offline `train`-namespace calibration disjoint from model-fit and `test` evaluation, and report every seed's correct/wrong/abstain counts **and** coverage. Historical audit seeds have been inspected and cannot become a new blind holdout. Do not give an abstention profile permission to install or promote a model.

18. Candidate promotion now requires `CandidateStore.review` with distinct held-
    out observation histories, followed by explicit approval of the **review**
    digest. Never use the old model digest as approval. Run the six-seed
    `python -m benchmarks.candidate_review_benchmark` and separate unchanged
    transfer benchmark. Do not treat predictive likelihood gain as safety,
    navigation improvement or signed owner authorization. Keep all failures.

17. `streak_selection.py` is experimental and must not replace
    `decision_abstention.py` or authorize any real actions. Reproduce both
    the 17/23/41 benchmark and 1009/1013/1031 audit at the same training
    budget. Report correct/wrong/abstained for every seed, including
    regressions; 2% empirical step error is not a safety/confidence bound.

19. For optional `robust_world_model.py` experiments, compare against the unchanged `online_dynamics.fit` on identical train histories and EM iterations; keep model selection in separate train-namespace validation histories and evaluation in test-only indices. Publish predictive scores *and* downstream navigation regressions on seeds 17/23/41 and 1009/1013/1031 with matching budgets. A predictive gain does not authorize deployment, candidate promotion or claims of independent blind generalization. Preserve baseline and V2A/V2B roadmap scope.

20. New `mixture_navigation.py` is strictly simulation-only and optional.
    Its regime probabilities are learned or probe-conditioned hypotheses, **not**
    validated confidence guarantees. Never supply simulator true positions or
    regime labels to its state transitions. To change this experiment, rerun
    three development seeds plus three inspected audit seeds with matching fit
    budgets, compare uniform-vs-probed mixture with correct/wrong model and
    true-physics baselines, report Brier and credible-set coverage, and rerun
    the unchanged transfer benchmark. No automatic rollout on mixed results.


21. Changes to `structured_landmarks.py` must retain the two-site ring prior
    explicitly and use **only** initial-beacon/action/odometry/landmark histories
    for inference; benchmark truth must not leak into training or navigation.
    Run 17/23/41 and 1009/1013/1031 matched-budget predictive/navigation
    comparisons, the offset-3 novelty test, and unchanged transfer benchmark.
    Report original-regime regressions, not just high-noise improvements.
    No automatic model-bank promotion or out-of-family generalization claims.

21. `flexible_landmarks.py` is a **simulation-only optional experiment**. Its two possible distinguishable marker identities, 9/11-cell topology, first-position beacon, and condition-grouped training data are engineering priors. Rerun `python -m benchmarks.flexible_landmarks_benchmark` with identical fit/map/test/navigation budgets across 17/23/41 and inspected audit 1009/1013/1031, compare against untouched constrained, unconstrained and true-physics models, and preserve all four condition results including known-layout and sparse-world regressions. Do not call inspected audit seeds blind, interpret map/record SHA as signed user approval, or silently promote the new model. Keep V2A and V2B milestones intact.

21. `mixed_experience.py` may only propose observation-derived models in a simulation. Re-run `python -m benchmarks.mixed_experience_benchmark` on seeds 17/23/41 and 1009/1013/1031 at the *same* fitting/validation/test/navigation budgets, plus the original-only negative control and unchanged transfer benchmark. Report high-noise improvements **and** original-world regressions. Its known 9/11-ring, half-separated markers and initial beacons are engineered assumptions. Do not pass regime labels or simulator true locations to fit, validation, probes or navigation inference. Distinct test probes are context inputs, not candidate training. A validation-selected proposal, diagnostic confidence and SHA256 checksum are **not** approval, independent blindness or permission to act.

21. `switching_belief.py` is a bounded, **optional** per-sensor-step hypothesis-switching experiment. Preserve its stationary `hazard=0` reference and the existing navigation default. Hazard calibration must use observation-only train-namespace records, disjoint from learned model fitting and test evaluation; never supply simulator positions, regime labels or rewards to the filter or its calibration API. Rerun `python -m benchmarks.switching_belief_benchmark` on inspected development seeds 17/23/41 and audit seeds 1009/1013/1031 with the **same** fit/validation/calibration/test budgets. Report log-loss, Brier and abstention on both switching and stationary-control streams. A calibration checksum is not authenticated consent, not statistical confidence, and cannot approve model rollout. Restore/regression tests are required.

22. `closed_loop_adaptation.py` is **experimental simulation-only** and must
    not authorize external actions or silently promote candidates. Use only
    frozen `MixedProposal` bank entries and a model-bound, train-only hazard
    receipt. Reject privileged simulator fields, unrequested actions and
    tampered/replaced checkpoints; verify restored states by replaying bounded
    sensor histories. Reproduce development 17/23/41 and previously inspected
    audit 1009/1013/1031 on identical train/validation/calibration/evaluation
    partitions. Compare single-model, static-mixture, live switching and
    privileged physics-law reference navigation **per seed** in changing,
    unchanged and continually high-noise worlds. Explicitly publish the
    high-noise and changing-world regressions. Rerun the unchanged transfer
    benchmark; preserve D2/D3 and V2A/V2B as open gates.


23. `novelty_guard.py` is a diagnostic research experiment only, not a certified anomaly detector, permission provider or default policy. Reproduce `python -m benchmarks.novelty_guard_benchmark` on seeds 17/23/41 and inspected 1009/1013/1031 at matching fit/calibration/navigation budgets. Retain all five sensor conditions, especially normal false alarms, missed odometry/map faults and closed-loop task-success reductions. Calibration may read **only** disjoint train-namespace ordinary sensor histories, with all sensor/position/label truth restricted to benchmark scoring. Re-run the original transfer benchmark. No threshold tuning to test episodes, background model promotion, unrestricted external actions, or unreviewed autonomy expansion. Preserve V2A/V2B roadmap order.

24. `channel_novelty.py` is optional, simulation-only and must not replace the default navigation policy. Re-run `python -m benchmarks.channel_novelty_benchmark` on seeds 17/23/41 and previously inspected 1009/1013/1031 with matched fit, calibration, reference and evaluation budgets. Calibrate solely on ordinary sensor histories from disjoint train indices; never leak environment truth. Report five per-condition alarm/false-alarm counts plus closed-loop task completion and pause regressions. Combined detector false-alarm rates are not guaranteed by either component's alpha. Checksums do not authenticate permission, and the guard must not authorize actions, automatic model promotion or autonomous deployment. Preserve V2A/V2B ordering.


24. `layout_novelty.py` is an optional, observation-only **diagnostic**. Never
    use its hypothetical offsets to authorize an action, automatically promote
    a model, or claim arbitrary-map understanding. Preserve the frozen bank and
    known two-half-separated-marker ring assumption. Validate checkpoint
    replay and reject privileged fields. Calibrate the entire offset/prefix
    search using disjoint training reference episodes, not test results. Re-run
    matched budgets (48/16/12/64/24) on seeds 17/23/41 and previously inspected
    audit 1009/1013/1031, all five fault/normal conditions, and unchanged
    transfer. Report additional normal and known-change false alarms and
    delays, not just increased rotated-map sensitivity. The alpha=.04 study
    was explicitly chosen after alpha=.10 outcomes; it is post-hoc, not blind.
    Neither a threshold nor an integrity hash is permission or a statistical
    safety guarantee. Keep existing guard/controller defaults and V2A/V2B order.

23. Cross-family D1/D2 adapter contract: keep `environment_api.py`
    and `environment_service.py` strictly simulation-only. Do not expose
    true hidden position, world internals, hidden task rules, arbitrary file
    access, network, shell commands or permissions. Preserve bounded action
    masks, monotonic ticks, versioned frames and exact checkpoint replay.
    A digest is NOT a signed approval. Run `tests.test_environment_api`,
    `tests.test_environment_contract_benchmark`, the relevant older family
    tests, and the unchanged transfer benchmark. The JSONL process prototype
    has no caller authentication or production service guarantees.

24. Treat `benchmarks/frozen_environment_protocol.json` as locked.
    Never retune seeds/indices, baselines, metrics or reserved test cases after
    seeing evaluation outcomes. The development seeds have been inspected.
    Reserved seeds are public, NOT automatically blind; run them only after a
    candidate freeze and with separate review. The task-specific navigation
    heuristics and delayed-memory gate are ENGINEERED: they are baseline
    references, NOT evidence of transferable general intelligence or
    completion of D1, D2 or D3. Preserve V2A before/alongside V2B.

25. Zero-shot transfer study `cross_family_transfer.py` is experimental.
    Grid-training Q weights MUST remain frozen during evaluation in the
    occluded task. Use only the public D2 environment frame and action feedback.
    The occluded beacon retention/dead reckoning is an ENGINEERED adapter,
    not learned representation transfer. Keep task-specific greedy and random
    baselines, all inspected development seeds, original-grid regression,
    per-seed successes and the original transfer benchmark. Do not call any
    such study blind, universally transferable or a passed D3 gate. Preserve
    the sealed D1 cohort unused and the V2A/V2B roadmap ordering.


26. `learned_spatial_memory.py` is simulation-only D3 research. Fit movement-memory update rules from *public visible-grid train observations*, not hidden positions, test observations, or occluded rewards. Keep the memory slot, beacon write and event aliases described as engineered. Re-run development 2749/6607/9901 and additional 15101/22003/31013 at the fixed training/evaluation budgets with identical action RNG for learned-vs-engineered comparisons; retain forgetful and random controls. These results are not independently blind and do not close D3. Run `tests.test_learned_spatial_memory` and the unchanged transfer benchmark; preserve D1/D2 and V2A/V2B scope.

25. `cross_task_retention.py` is an **experimental cross-family strategy
    selector**, not a generally learned attention or memory architecture.
    The candidate rules (initial/latest), shared cue abstraction, one-slot
    representation, learned spatial updater and navigation heuristic are
    explicitly engineered. Training/evidence selection must use train-only
    observations and terminal feedback; keep test indices 85000+ and 86000+
    isolated. Reproduce both 2749/6607/9901 and 17431/24869/37021
    cohorts with matching budgets; compare delayed latest-cue and occluded
    forgetful/initial-cue controls, including all regressions. Never claim
    blind independence, D3 gate completion, authenticated consent, or
    authorization of system actions. Preserve the existing transfer benchmark,
    model defaults, and V2A-before-overlapping-V2B roadmap ordering.

27. `online_memory_gate.py` is optional D3 research. `MemoryGate` must choose bounded per-candidate WRITE/KEEP from context/source/token and reward-only training; do not read simulator truth in its policy. Preserve train/0..1799 vs test/93000+ and test/94000+ namespaces, paired seeds 2749/6607/9901 and 17431/24869/37021, and the first/last/random/oracle/no-context ablations with matched budgets. Navigation cues are synthetic decoys built from an initial *public* beacon, with manually shared A/B source semantics. Do not claim unrelated-task transfer, blindness, general-purpose memory or D3 acceptance. `CueMemory` restores by replay; a digest is not authenticated permission. Keep default controls, D1/D2 gates and V2A-before/overlapping-V2B roadmap intact. Run tests.test_online_memory_gate, both six-seed evaluation cohorts and the original transfer benchmark.\n
27. `grounded_aliases.py` is an **experimental, supervised target-domain calibration adapter**, not zero-shot semantics or passed D3. Source/context aliases differ, but pairings are inferred by comparing candidate offsets with a PUBLIC initial reference in train-only `train/70000+` episodes; target evaluation `test/97000+` supplies no reference to its selector. Match both seed cohorts 2749/6607/9901 and already-inspected 17431/24869/37021 with equal fit/calibration/evaluation budgets. Include no-memory-model paired lookup, privileged correct-cue, first/last/random and wrong-context controls. Explicitly disclose the 223/240 tie against simple lookup; never claim superior knowledge transfer. Checksum replay is not authentication; do not install models or grant actions. Re-run `tests.test_grounded_aliases` and unchanged `transfer_benchmark`; keep D1/D3 gates open and V2A/V2B ordering.

27. `reward_aliases.py` / `reward_only_alignment_benchmark.py` are optional D3 research. Keep `benchmarks/reward_only_alignment_protocol.json` frozen from its first commit (`8c0a4c8`); no post-result tuning of cohorts, indices, training counts or baselines. The learned model's inputs and reward feedback must NEVER include paired reference offsets, correct-source labels, simulator true positions or hidden regimes. Target-domain navigation rewards **are** used during training; this is not zero-shot transfer. Run both 2749/6607/9901 and 17431/24869/37021 and report exact per-seed success vs same-evidence source lookup, context-blind, first/latest/random and reference oracle. Direct lookup matching performance must be disclosed. Use replay-bound checkpoint validation, original unchanged transfer and relevant regression tests. No automatic deployment or external action. Preserve V2A/V2B ordering.


27. `dynamic_reliability.py` is optional simulator-only D3 research: the evidence agreement feature, four quantization bins, candidate offsets, probe vocabulary and navigation controller are ENGINEERED. Preserve `benchmarks/dynamic_reliability_protocol.json` committed before evaluation; do not tune it using inspected development or previously reserved test outcomes. Rerun both fixed cohorts 43103/50021/61031 and 72019/83003/94009 with matched 360 train + 40 test episodes per seed and all seven baselines, including reward-trained identity lookup and stronger hand-coded maximum-agreement. Report 206/240 learned vs 209/240 agreement on original published cohorts, and all per-seed regressions. Replay validation is not signed provenance. Never describe public reserved seeds as secret blind evaluation, promote this policy as default, or authorize non-simulated actions. Preserve V2A/V2B order and unchanged historical transfer benchmark.

27. `raw_token_transfer.py` is **optional simulation-only D3 research**. Never pass correct-source labels, simulator goal truth, hidden symbol permutation or privileged positions to its public learner API. Preserve the fixed 360 train and 40 test episodes per seed, six precommitted seeds, seeded forecast cipher, disjoint public alphabets, single terminal reward, all per-seed scores and separate historical transfer benchmark. ALWAYS compare the reward-learned pair model with the identity-only same-reward bandit, unsupervised raw cooccurrence permutation (which currently scores better), literal matching, random and correct-cue references. Check saved-state replay and reject malformed/privileged observations. D1/D3 stay open; no model promotion, action authority, private user data or V2A/V2B scope changes.

28. `unaligned_stream.py` is **optional, simulation-only** D3 research. The pre-evaluation `benchmarks/unaligned_stream_protocol.json` fixes training indices 89400–89639 and test 99600–99639 for seeds 43103/50021/61031 and inspected 72019/83003/94009; do not retune on either test cohort. Always reproduce reward-trained monotone alignment against *stronger* reward-free unsupervised permutation + monotone alignment, fixed-source identity trained on the same reward observations, unordered learned-pair, random and privileged oracle controls. Publish both cohorts and six per-seed failures (**122/240** learned vs **142/240** unsupervised). Sequence time-window, token alphabets and gap cost are engineered. Require exact replay and strict sensor bounds. Hashes are not signatures or consent; no model promotion, OS action permissions or D3-generalization claims. Preserve historical transfer baseline and V2A/V2B scope.

28. The optional `probabilistic_alignment.py` experiment uses an engineered eight-correspondence, fixed-noise sum-product model, not learned general time reasoning. Preserve the precommitted `benchmarks/temporal_correspondence_protocol.json`, compare against the existing same-index unsupervised max-path baseline on six inspected seeds, retain all per-seed regressions and run old transfer regression. No policy promotion, real-world action or inference of consent from hashes. D1/D3 remain open; V2A/V2B unchanged.


27. `variable_correspondence.py` is optional, strictly simulation-only, and its known four-symbol alphabet, monotone order and eight-event upper limit are engineered. Reproduce the frozen `benchmarks/variable_correspondence_protocol.json` six-seed cohorts with train/90000..90119 pseudo-selection fixed to the older eight-event model and test/99800..99839 disjoint. Compare previous fixed-eight marginal, max-path, reward pair, fixed identity, oracle cipher and privileged correct cue; publish all six seeds including the regression on 72019. Report exact event-count error against **fixed-six and public-length minus-four baselines**: the new model underperforms these simple counting controls; the supplemental comparison was post-hoc. Never feed true dropped positions, cipher, hidden state, reference cue or test rewards to learner. Run its nine new tests plus existing temporal/unaligned/raw-token/dynamic modules and unchanged `transfer_benchmark`; keep existing defaults, D1/D3 open and V2A/V2B order. A hash/replayed fit is integrity validation, not authorization.


27. The new optional `cross_family_temporal.py` adapter is **simulation-only, read-only** and must remain isolated from default navigation and user/OS actions. The extra delayed-choice side-channel templates, alphabet, first-cue benchmark generator and candidate-provided cue IDs are **engineered**, not learned perception. Train the temporal model on navigation train streams only and the separate response policy on delayed-choice train data; never provide delayed test cues or correct actions to the selector. Freeze the [cross-family temporal protocol](benchmarks/cross_family_temporal_protocol.json); reproduce the six previously inspected seeds in both 40-episode cohorts with matched bag, fixed-eight, max-path, last-token and privileged-cue controls. Report **115/240** variable vs **153/240** last-token and learned event-count MAE **0.9303** vs length **0.6312**, including all per-seed changes. Run `tests.test_cross_family_temporal` and related regression tests and the unchanged `transfer_benchmark`. D1 and D3 remain open. No checksum is authentication; retain the approved V2A/V2B sequencing.


27. `event_segmentation.py` is an optional four-state symmetric HMM and simulation-only streaming memory; the four latent labels, Markov structure, target = longest event and 128-token memory limit are engineered. Preserve raw-observation-only source fitting and train/test separation. Reproduce both frozen 14003/14009/14033 and 27007/27011/27017 cohorts with 160 source-fit and 64 per-family test histories, compare fixed-parameter HMM, majority, raw longest-run, first/last and privileged true boundaries. Report the **shifted-generator regression (250/384 learned vs 253/384 fixed)** and imperfect boundary recall, not just familiar gains. Both families are parameter variants of one synthetic generator; do not call them truly independent tasks or blind validation. Reject forged/rehashed session snapshots, detect model mutation, run original transfer benchmark. No automatic model promotion, external authorization, owner-private memory or changes to V2A/V2B order.


27. `outcome_event_memory.py` is optional reward-guided *event retrieval*, not an autonomous episodic memory, general relevance learning or completed D4 skill discovery. The event HMM must be trained only on source-generator raw `train/0..159`; the priority bandit may train only on `source_bursts/train/2000..2199` via the single terminal boolean per episode. The model must not consume hidden relevance labels, true segment boundaries, hidden position or benchmark oracle data. Keep evaluation `test/93000..93063` frozen for development 14003/14009/14033 and previously inspected additional 27007/27011/27017, for BOTH source and shifted generators. Publish all per-seed results and compare against independently reward-trained raw runs, fixed longest/recent spans, majority and hidden-state upper bound. Test rehashed checkpoint tampering and model-bound exact replay; SHA256 is not user authentication. Re-run `tests.test_outcome_event_memory`, event/model/environment tests and unchanged transfer. Never automatically promote the model, alter system permissions or private identity data, or change the approved V2A/V2B sequence. Maintain D3/D4 as open.


27. `reversible_event_priority.py` is an optional observation/reward-only
    research controller, NOT autonomous goal selection, general lifelong memory,
    authenticated owner memory, or permission to promote or operate any system.
    Preserve the precommitted original→reversal→return protocol at
    `benchmarks/reversible_event_memory_protocol.json` and independently
    replay-verifiable model-bound checkpoints. Run tests for
    `tests.test_reversible_event_priority` and prior event-segmentation/outcome
    memory, plus both benchmark cohorts and unchanged transfer. Compare
    archived bank, cumulative, recent-32 window, frozen original, HMM longest,
    and privileged available-target references **per phase and seed**.
    Current results show the bank 188/178/201 and the recent-window
    187/177/201 on 288 episodes/phase; return-phase early learning regresses.
    Do not claim archive recall or D3/D4 completion without better evidence.
    Training may use only public context/raw tokens, selected event and terminal
    boolean feedback. Evaluation must remain read-only; private goal changes
    and hidden labels are benchmark-only. SHA256 is not signed authorization.
    Keep V2A before and overlapping V2B.


28. `nonstationary_event_value.py` is an optional A→B→A **replication study** separate from `reversible_event_priority.py` and must never replace it or alter default learning/actuation. Preserve the precommitted `benchmarks/nonstationary_event_value_protocol.json` schedule and all six inspected seeds. Do not expose hidden phase, goal map, true spans or simulator outcome counterfactuals to the training or inference APIs. Compare frozen, cumulative, recent-32, failure-triggered archive, raw-run recent-32 and available-target reference on original/changed/returned phases, including all regressions and switch counts. Reproducible outcomes: window 161/155/169 vs archive 160/146/168; do not claim archive advantage. Re-run new tests, `tests.test_outcome_event_memory`, `tests.test_event_segmentation`, and historical transfer benchmark. Checkpoint SHA/replay are not signed consent. Maintain D1/D3/D4 as open and V2A/V2B ordering; no external or OS actions.

27. `event_model_drift.py` is a simulation-only **read-only** diagnostic. Keep `benchmarks/event_model_drift_protocol.json` frozen and do not adjust CUSUM/window/rate thresholds after inspecting test episodes. Reproduce 14003/14009/14033 and previously inspected 27007/27011/27017 with equal model-fit (`train/0..159`), independent stationary calibration (`train/800+`), and `test/94000+` budgets. Report stationary false alarms, *early* alarms on changed streams, clean post-change detections, delays, and per-seed failures. Neither the calibration receipt nor a model/trace SHA-256 is signed approval, a safety guarantee, or a permission to change an action, memory or installed model. Re-run the original transfer benchmark. Keep D1/D3/D4 open and V2A/V2B sequence intact.


29. `repeated_reversal.py` completes the previously committed six-stage
    A→B→A→B→A→A-control protocol. Never alter the original
    `benchmarks/repeated_reversal_protocol.json`, the exact schedule, or
    published per-seed results to improve performance. Archive+recent scored
    983/1,440 against window32 991/1,440; D3/D4 remain OPEN. The agent
    cannot receive hidden phase or target labels, only own action/reward
    histories. Re-run `tests.test_repeated_reversal`, related event-memory
    tests, both cohorts and original transfer. Checkpoint SHA is not signed
    provenance, owner permission or safe automatic promotion. Preserve
    optional simulation-only status and approved V2A before/overlapping V2B.


Procedural skill research `developmental_ai/procedural_skill.py` is an **optional sandbox-only** D3/D4 scaffold. For any edits rerun `tests.test_procedural_skill`, both frozen `benchmarks.procedural_skill_benchmark` cohorts at 600 workshop training / 100 test episodes per seed/family, and the original `benchmarks.transfer_benchmark`. Never claim graph-free prerequisite learning: the goal and full public DAG are visible, transitive ancestry is a manually engineered feature, and reward shaping reinforces good ancestry actions. Publish and retain greedy/oracle ties, random/feature-ablation controls, all six per-seed scores and target-world regressions. Do not reinterpret inspected cohorts as blind, alter the precommitted protocol, install arbitrary external actions or promote policies. Keep D1/D3/D4 open and V2A/V2B sequencing unchanged.

30. Optional `hidden_prerequisites.py` experiment has a hidden dependency graph. Never leak `HiddenProcedure._requirements`, role ancestry or the private correct action into `PreconditionSkill` public frames, inference, training or checkpoints. Its task uses developer-supplied stable role tags, so it is *not* general semantic prerequisite discovery. Preserve frozen `benchmarks/hidden_prerequisite_protocol.json`, training workshop episodes `0..359`, test indices `81000..81079` and six already inspected seeds. Rerun `tests.test_hidden_prerequisites` and `benchmarks.hidden_prerequisite_benchmark` for both cohorts, plus historical transfer. Report workshop **480/480** vs repair **222/480**, random repair **331/480** and role-order repair **480/480**. Do not tune this protocol, claim D3/D4 completion, grant external action authority, or change the V2A/V2B roadmap order. SHA256 and deterministic replay are not signed owner approval.

30. `context_plan_memory.py` is optional simulation-only research, not approval to execute user actions. Preserve precommitted `benchmarks/context_plan_transfer_protocol.json` and evaluate 14003/14009/14033 plus previously inspected 27007/27011/27017, 80 alternating episodes each, seven attempted actions maximum, with context-keyed, latest-plan, no-memory, lexical and privileged oracle comparisons. Public role tokens and stable context keys are engineered; successful-trace replay is NOT learned causal skill composition or a passed D3/D4 gate. Report cold-start failures and per-context outcomes. Checkpoints are integrity/replay checks rather than owner authentication. Rerun `tests.test_context_plan_memory` and the unchanged original `transfer_benchmark`. Keep D1/D3/D4 and approved V2A-before-overlapping-V2B sequence open.


31. `plan_repair.py` and `plan_compaction.py` are **experimental simulation-only**, never permitted to issue real file/network/shell/OS actions. Their six-seed A→B→A protocols are frozen and were inspected during development, **not blind**. `plan_repair_benchmark` cached repair tied latest plan at 434/480, with a strong hand-coded role-order baseline of 480/480. The separately frozen, explicitly post-hoc `plan_compaction_benchmark` improved mean attempts to 4.96 from 7 but **regressed success to 395/480** versus 434/480; do not silently promote, suppress failures, or edit frozen protocols after evaluation. Stable opaque role IDs and known seven-role structure are developer priors; replay and SHA are integrity only, **not owner authentication or causal identification**. Rerun `tests.test_plan_repair`, `tests.test_plan_compaction`, both cohort benchmarks of each study, and unchanged `benchmarks.transfer_benchmark`; preserve D1/D3/D4 OPEN and V2A-before-overlapping-V2B ordering.
