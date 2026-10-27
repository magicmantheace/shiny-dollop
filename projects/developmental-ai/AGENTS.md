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
