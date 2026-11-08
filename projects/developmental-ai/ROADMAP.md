# Developmental AI — Milestone roadmap through 2029-02-09

> **CURRENT DEVELOPMENT OVERRIDE (2026-10-20):** The immediate priority is
> measurable standalone learning, not AthenZ or Synveil integration. Preserve
> existing integration interfaces but defer additional work and keep the
> experimental integration pull request unmerged. The near-term work sequence
> is independent cross-family generalization, durable memory, continual
> retention, reusable skills, and bounded sandbox goals. Experimental
> outcomes do not close D3/D4 until independent protocols and strong
> baselines establish transferable gains. See
> [standalone priority](docs/STANDALONE_PRIORITY_2026_10_20.md) and
> [outcome-skills experiment](docs/OUTCOME_SKILLS.md). Preserve the existing
> 2029 target and V2A-before/overlapping-V2B ordering.
>
> **2026-10-20 working branch:** `priority/standalone-policy-review-2026-10-20`
> introduces manual policy update review and a limited compositional
> symbolic-skill experiment. The latter achieved 360/360 on assembly,
> but failed 0/360 on the deeper delivery chain; both share deliberately
> engineered action semantics. Results are development/supplemental, not blind.
> **Post-hoc unknown-regime stress gate (2026-10-21):**
> The cue-free first-step diagnostic correctly retrieved the prior
> learned A/B history across all six inspected seed groups,
> succeeding at 360/360 per A→B→A stage. A stronger zero-probe
> union-of-known-risk baseline and an entirely untrained third
> *descriptor mapping* (spoil/fuel identity swap) have been added.
> The latter changes identities, not underlying dynamics. These
> tests audit identifiability, potentially harmful ambiguity and
> overclaim of cue-free generalization. Results must include
> task success, spoilage and stalls; negative findings are not
> regressions to hide. No milestone D3/D4 completion is implied.
> See [unseen-regime audit](docs/UNSEEN_REGIME_AUDIT.md).
>
> **A→B→A context-indexed retention (2026-10-21):**
> A new experimental risk-memory adapter separately learns two
> variants of the existing cargo task whose numeric action descriptors
> are swapped (underlying transition rules do not change).
> It retrieves saved context evidence via a perfect simulator-supplied
> public two-component beacon. Six now-inspected seeds score
> **360/360** at each original/changed/return stage. Without the
> informative beacon, changed-stage success falls to **128/360**;
> untrained novel-first is **130/360**. This demonstrates
> context-indexed *retention/retrieval*, not independent discovery
> of changing dynamics, causal risk, general competence or
> milestone D3/D4 completion. The frozen seed 51013
> two-byte collision was corrected deterministically; no seeds
> were discarded. See
> [contextual affordance study](docs/CONTEXTUAL_AFFORDANCE.md).
>
> **Persistent within-family affordance-risk learning (2026-10-21):**
> Stable numeric two-byte descriptors supplied by the simulator allow a
> bounded event-memory policy to carry outcomes across separate cargo
> episodes. Six now-inspected development/reserved seeds: trained
> 360/360, untrained 136/360, shuffled descriptors 136/360, cyclic
> 134/360; relay retention 360/360 (also at fixed-baseline ceiling).
> This is an important implementation of *persistent outcome-grounded
> behavior* in one fixed task family, NOT perceptual action discovery,
> independent generalization, statistically calibrated risk or D3/D4
> completion. See
> [affordance-memory report](docs/AFFORDANCE_MEMORY.md).
>
> **Anonymous-action generalization update (2026-10-20):**
> A separate precommitted study evaluates one observable-action
> strategy selector on monotonic relay switches and consumptive cargo
> processing, with rotated anonymous action handles and numeric sensors.
> Both cohorts are now inspected. The selector chose a fixed strategy
> on every seed and achieved cargo 147/360 versus simple cyclic 145/360
> and random 82/360; the privileged oracle was 360/360. Irreversible
> harmful actions were a major failure mode. This remains **development
> evidence only**; true independent D3 generalization is open. See
> [opaque causal study](docs/OPAQUE_CAUSAL_GENERALIZATION.md).
>
> **Experimental recovery update (2026-10-20):**
> A separate optional source-skill-bound policy uses observational
> prerequisite probes until a new action effect is learned, then falls back
> to the previously validated controller. Six inspected symbolic seeds
> suggested improved adaptation and retention, but the 1-episode
> regression remains. This is an engineered handoff, NOT independent
> causal learning or completion of D3/D4. Details:
> [prerequisite recovery](docs/PREREQUISITE_RECOVERY.md).
>
> **Blocked-outcome probing update (2026-10-20):**
> New optional `prerequisite_probing.py` records failed/successful
> fact-context evidence and permits bounded unknown-action exploration.
> Reproduction of the six inspected synthetic seeds exposed a *serious
> continual-learning regression*: raw probing gained some initial target
> success, then fell to zero after adaptation. A separate train-only
> validation-selector retains the historical controller when new
> behavior regresses. This is a two-policy gate, not a general
> continual-learning solution or a D3/D4 milestone completion. See
> [prerequisite probing](docs/PREREQUISITE_PROBING.md). No
> integration or V2A/V2B work was added. Full upstream validation remains
> blocked by Actions job startup failures.
>
> **Additional optional learning experiment (2026-10-20):**
> `benchmarks/continual_skill_benchmark.py` measures source training,
> then 0/1/2/4/8/20 episodes of explicit delivery-task training, and a
> return-to-assembly retention check, with frozen-source, target-only,
> random and privileged-recipe controls. Source pretraining provides
> extra total experience; the common symbolic action ontology remains
> engineered. This does not revise the original zero-shot failure or
> establish independent cross-family generalization. See
> [continual skill retention](docs/CONTINUAL_SKILL_RETENTION.md).
> Exact full-repository benchmark execution remains pending.

> The full repository test suite remains **unvalidated**, because GitHub
> Actions failed before jobs executed. Keep the changes in draft PR #2
> until full local or runner validation is available.


## Product boundary

This repository owns **learning and simulation**, not the human's identity or the operating system. AthenZ owns consented identity, user-approved memories, dialogue, human-vs-digital autobiographies, and permissioned agent goals. Synveil owns operating-system services, deterministic policy, and controlled actuators. We should never make Synveil a prerequisite for running this engine in a Windows or generic Linux development environment.

**Success definition:** a continuously operable research-grade agent can learn in previously unseen bounded environments, retain experience and skills across restarts, develop and evaluate its own allowed goals, and integrate with an AthenZ model of a consenting person. This does not claim consciousness, human-equivalent intelligence, or survival of the original person's identity.

## Gates

| Due | Gate | Acceptance test | Status |
| --- | --- | --- | --- |
| 2026 Q4 | D0: import reproducible fixed-world POC | Existing tests pass; no private DB tracked | Done |
| 2026 Q4 | D1: randomized worlds + holdout protocol | 3 seeded held-out success gains; independent seeds; persistence | Fixed development protocol and reserved cohort; independent blind evaluation still open |
| 2027 Q1 | D2: documented simulation and agent interface | Stable versioned schemas, deterministic environment replay, standalone service adapter | Experimental three-family JSONL adapter and replay implemented; unauthenticated, no production/AthenZ connection |
| 2027 Q2 | D3: real generalization | Transfer across *held-out task families* and changed observation distributions, not just new layouts | Not started |
| 2027 Q3 | D4: reusable skills | Skill discovery, transfer, outcome-grounded retrieval, regression checks | Not started |
| 2027 Q4 | D5: autonomous goal selection in sandbox | Self-initiated achievable goals with visible budgets, feedback, and interrupt controls | Not started |
| 2028 Q1 | D6: lifelong learning | Consolidation, skill retention, versioned rollback, no unreviewed weight promotion | Not started |
| 2028 Q2 | D7: AthenZ integration | Human-origin memories clearly separated from agent episodes, provenance/consent enforced | Not started |
| 2028 Q3 | D8: Synveil integration | Bounded event/actuation interface, safe fallback when AI subsystem stops | Not started |
| 2028 Q4 | D9: long-run reliability | 30-day test with planned restarts, restoration, measured learning and failure records | Not started |
| 2029-02-09 | D10: integrated candidate | Reproduce published benchmarks; protected AthenZ twin; documented operating limits | Not started |
| Post-core (Version 2A; precedes and overlaps V2B) | V2A: affective cognition and emotional development | Persistent, event-grounded affect and motivation; learned preferences; bounded regulation; held-out behavior tests; V2B experience integration | Planned; foundations before V2B, later slices co-developed |
| Post-core (Version 2B) | V2B: persistent virtual home for AthenZ | Headless persistent simulation, experience provenance, bounded goals, reproducible restore/replay and optional 2D/3D viewer | Planned; not a D10 prerequisite |

## Immediate next work

1. Freeze evaluation protocols and add independent post-development blind seeds; measure across obstacle densities, size ranges, sensory noise, and new objective types.
2. Add deterministic event replay and explicit per-event provenance without inserting private experience text into Git.
3. Build a clean environment/policy/memory plugin interface; keep simulation and AthenZ identity services separate.
4. Add systematic baselines: random, heuristic, shortest-path oracle (upper bound), trained policy, and ablations for curiosity and memory.
5. Add recurrent policy/world-model experiments only after transfer experiments expose meaningful failures requiring that complexity.

## Hard constraints

- A high score in one narrow simulator is not evidence of a mind, self-awareness, or ability to model a person.
- Independent seeds and no test feedback used for training; report if protocol was tuned to test data.
- No unrestricted shell, network, or desktop control by the learning policy.
- No human names, messages, voice, biometrics, consent records or private trained models committed to this repository.
- Test/restore checkpoint compatibility before any persistent format changes.

## Multi-task milestone — 2026-10-13

- [x] Three task rules share one partial-observation learned policy.
- [x] Seed-separated task generation; versioned, task-bound durable checkpoints.
- [x] Simulation-only decision traces, deterministic transition replay, digest.
- [x] Random, greedy, and full-map oracle references; restart-equivalent tests.
- [ ] D2 service/event interface remains unimplemented.
- [ ] D3 remains open: the learner relies on target cues and is weaker than
      the greedy baseline; next tests must address cue removal, novel objective
      families and independent blind benchmarking.

## 2026-10-13 — Delay-dependent memory experiment and event export

- [x] Implement a separate delayed-cue, four-choice experimental task with distractor tokens and train-only short delays.
- [x] Quantify retained-cue, reactive and last-token-overwrite ablations across seeds, plus longer held-out delay distributions.
- [x] Versioned, mode/seed-bound SQLite memory-policy checkpoints with deterministic resume and evaluation immutability tests.
- [x] Deterministic replay of decision traces and recomputed-hash tampering checks.
- [x] Experimental strict, bounded event ledger output from both simulation families with hash chaining and source-trace binding.
- [ ] **Learned memory control is not implemented.** `retain` hard-codes which initial cue to keep; the association mapping alone is learned.
- [ ] **D2 remains open:** no implemented external AthenZ/Synveil service adapter, authenticated IPC or production stability guarantee.
- [ ] **D3 remains open:** no demonstrated generalization to new open-ended tasks or changing observation semantics. Test seeds were inspected during development.

Next: train a controller to *select* useful observations for memory rather than taking the preselected cue, then test it under unseen distractor processes; tackle navigation without supplied target-direction cues. Maintain reproducible, independent blind evaluation after architecture freeze.

## Learned selective-memory milestone — 2026-10-13

- [x] Added a learnable `write`/`keep` policy conditioned on current context
      and source of the observed signal, with no explicitly labeled cue phase.
- [x] One-slot memory, distractors, hidden response association and terminal
      success feedback; no privileged environment access.
- [x] Disjoint train/test namespaces, short/long delay ablations, saved
      per-seed results and hand-coded simulator oracle comparison.
- [x] Seed/mode/schema-bound SQLite checkpoints; exact continuation and
      read-only evaluation regression tests.
- [x] Trace replay validation of in-simulator observations and memory writes;
      trace hashes alone are not attestations.
- [ ] Source-reliability distribution shift, multiple competing same-channel
      cues, learned recurrent memory and transfer to occluded navigation.
- [ ] D2 stable external service interface still open; D3 broad task transfer
      remains unproven, and all reported seeds are development seeds.


## Occluded spatial-navigation milestone — 2026-10-13

- [x] Added randomized-grid navigation where a goal offset is visible at reset
      only, and future observations include just local blocked directions.
- [x] Engineered movement-feedback dead reckoning and a distinct reactive
      memory-loss ablation; train separate Q policies per mode.
- [x] Three-seed evaluation with untrained, reactive, random, greedy and
      privileged BFS oracle comparisons; all seeds remain development seeds.
- [x] Restart-exact SQLite policy checkpoints, read-only evaluations,
      environmental trace verification and read-only ledger export.
- [ ] **Learned spatial-memory control remains open:** the agent does not learn
      its odometry or what information to keep. It only learns actions from the
      manually constructed memory state.
- [ ] **D3 remains open:** test noisy action feedback, multiple competing
      beacons, harder obstacle distributions, and completely held-out task
      families before claiming transferable spatial reasoning.


## 2026-10-14 — Supervised world-model calibration and model snapshots

- [x] Estimate unknown simulator movement/odometry/landmark likelihoods from instrumented samples, with train/test generation separated.
- [x] Use a learned likelihood model in a bounded position-belief filter (control decisions remain heuristic).
- [x] Simulate abrupt distribution shift in movement and landmark locations, publish every development seed, evaluate predictive log loss and navigation success against a true-physics oracle.
- [x] Persist versioned model state, verify restart-equivalent training and evaluation immutability.
- [x] Preserve immutable, explicitly named knowledge snapshots so prior regime performance can be recovered without retraining.
- [ ] No learning from ordinary uninstrumented navigation observations yet: calibration sees simulator ground truth. No automatic regime selection or learned action controller in this experiment.
- [ ] The continuously adapted model substantially forgets the old regime; snapshot retention is a **manual mitigation**, not solved continual learning.
- [ ] D2 stable service adapter and D3 broad blind generalization are still open.

Next: calibration from *unlabeled* movement/landmark sequences using latent-state inference, automatic model bank selection from observation sequences, and completely frozen blind tests spanning changed geometry/landmark reliability.


## 2026-10-14 — Learning from unlabeled sensor trajectories

- [x] Introduce a second dynamics learner using only initial beacon, movement
      command, odometry and intermittent landmark observations (no ground-truth
      actual movement or post-reset position during fitting).
- [x] Infer hidden positions by deterministic categorical forward-backward EM
      with observable likelihood metrics and frozen deterministic seeds.
- [x] Preserve distinct immutable model snapshots and select the best fitting
      known model automatically from fresh ordinary probes (no regime labels).
- [x] Compare predicted observations and navigation on each inspected seed to
      wrong-model and privileged true-probability oracle baselines.
- [x] Repeat frozen development protocol once on independent post-development
      audit seeds 101/303/707; record the weaker high-noise outcome unchanged.
- [x] Verify versioned storage, tampering rejection, deterministic resume and
      read-only model selection. Previous supervised calibration remains intact.
- [ ] The selector does not detect unknown regimes or run a changepoint detector
      on a single continuous lived experience; periodic probes are externally
      scheduled. Learning still assumes a known small ring topology.
- [ ] D2 service adapter, broad D3 transfer and genuine continual adaptation
      remain open. Results are development evidence, not humanlike cognition.

## 2026-10-14 — Observation-driven regime change detection

- [x] Immutable model-bank fingerprint and schema-bound restart-safe model selector.
- [x] Rolling per-episode observation-likelihood window and repeated-evidence switch gate, with no regime labels supplied to the selector.
- [x] Retrieval of prior model after environment reverts; bounded hash-linked simulation event history and explicit unknown/uncertain statuses.
- [x] All three original development seeds and three extra checked seeds select original → changed → original when pretrained with the full model-training budget.
- [x] Capture weaker-training failure as a negative result (2/3 seeds fail to switch after the regime change).
- [ ] Current detection is per twelve-step episode, not per observation or during navigation; hand-tuned thresholds and manually pretrained models remain.
- [ ] Novel regime creation and candidate approval, calibrated novelty detection, sample-efficient model fitting, and closed-loop integration are open.
- [ ] The formal D2 external service interface, D3 broad generalization and any claim of human-like memory/agency remain open.

## 2026-10-14 — Per-observation inference and quarantined new-model proposals

- [x] Per-observation latent-state likelihood updates, bounded score windows,
      explicit initial beacons, restart-exact state and durable event history.
- [x] One-step observational likelihood regression against full forward/backward.
- [x] Preserved immutable model catalogue; quarantined training histories and
      candidate checkpoint with explicit digest-matched review requirement.
- [x] Invalid, privileged or tampered observations rejected; snapshot/bank
      fingerprint and schema compatibility checked on restart.
- [x] Published all three inspected-seed outcomes, including **failed changed
      regime detection on two seeds** and weak/worse held-out candidate fits.
- [ ] Not a reliable novelty detector, calibrated selector, real authenticated
      approval, per-step changing simulator, or automatic adaptation system.
- [ ] New-environment model selection and training-data quarantine still need
      leakage-resistant independent audit, more diverse regimes and improved
      predictive quality before any automatic-learning gate can be considered.


## 2026-10-14 — Offline step-detector calibration (experimental)

- [x] Frozen `step-dynamics/v1` baseline retained without changing prior results.
- [x] Separate model-fit, offline calibration, and evaluation episode ranges.
- [x] Fail closed when saved regime models cannot be distinguished using calibration evidence; reject duplicate evidence and bank mismatches.
- [x] Add model-bound, checksum-verified calibration artifacts and deterministic tests.
- [x] Preserve all three development and three additional audit seeds, including a regression and wrong-model fractions.
- [ ] **Reliability gate remains open:** 52.1% wrong-model step selection on changed-world development seeds after calibration. The anomaly floor is not statistically calibrated.
- [ ] Need within-trajectory regime changes, independent blind out-of-family tests, calibrated abstention and held-out candidate review before autonomous adaptation.

## 2026-10-14 — Selective abstention for uncertain stepwise model selection

- [x] Added a read-only, fail-closed `decision-abstention/v1` gate that rejects stale/mismatched current model selections, unknown status and low evidence separation.
- [x] Added an offline *train-only* empirical error-vs-coverage cutoff; its immutable receipt is SHA-256-bound to the model bank and it is explicitly **not** a calibrated error guarantee or signed approval.
- [x] Published six seed-wise, disjoint evaluation runs, preserving frozen baseline counts as well as the wrong/correct/abstained counts for the gate; retained audit seed 1031's 17 wrong selections.
- [x] Re-ran the original transfer benchmark without changing any prior evaluation protocol or historical result.
- [ ] **Coverage is insufficient:** 60–72% of tested steps abstain. Independent risk calibration, alternative confidence estimators, stronger underlying models, and changed-distribution tests remain required.
- [ ] **Candidate acceptance is not solved:** independent, frozen holdout review must gate promotion of newly fitted models before autonomous experiments are considered.
- [ ] No network service, agent autonomy escalation, privileged action execution, or human-record import is included.


## 2026-10-14 — Independent candidate acceptance gate

- [x] Require quarantined candidates to pass an immutable review on observation
      histories not reused in model fitting. Evaluate against every existing
      model and require a positive margin over the strongest competitor.
- [x] Bind review, held-out evidence, model and bank with restart-verified
      checksums; invalidate a review on catalog changes, corrupt records, or
      training/holdout overlap. Update legacy candidate promotion to **reject**
      the model digest alone and require a passing review receipt separately.
- [x] Reproduce six inspected-seed comparison with an additional independent
      predictive test partition not supplied to review; record both accepted
      and rejected candidates, without an automatic promotion.
- [ ] Model selection coverage, absolute novelty detection, data lineage and
      authenticated user consent remain open; positive held-out likelihood is
      not a guarantee about navigation or deployment safety.
- [ ] D2 external service and D3 broad generalization remain incomplete.

## 2026-10-14 — Consecutive-evidence selection study

- [x] Implement an independent, simulation-only 3-step evidence gate with
      versioned calibration, model-bank fingerprint, fail-closed checks, and
      restart-equivalent replay state.
- [x] Freeze fit/calibration/evaluation namespaces; retain the previous
      conservative gate as the default and report all seeds, wrong answers,
      and abstentions.
- [x] Six-seed comparison: mixed outcome and no consistent safety/coverage gain.
      Do **not** replace the conservative selector with this experiment.
- [ ] **Still blocked:** reliable uncertainty calibration on independent
      episodes and out-of-family regimes; better latent predictive models;
      higher coverage without increasing wrong decisions.


## Version 2A — Affective Cognition and Emotional Development (planned)

**Sequencing:** start V2A **before** the virtual home (V2B), but complete its later experiential parts **alongside** V2B. This is a post-core roadmap milestone, not a February 2029 D10 prerequisite. Finish the current reliable world models, verified memory and bounded-goal foundations first. V2A must work headlessly and without either V2B or Synveil; the room must be optional, and AthenZ must remain the only intelligence.

**Purpose:** give AthenZ a persistent, inspectable *computational affect and motivation* system, not a scripted "I feel happy" persona. Model shorter-term positive/negative appraisals and slower-changing fulfillment, competence, curiosity, connection-related priorities and preferences based on **observed, provenance-tracked outcomes**. These are operational/internal variables influencing memory, prioritization, exploration and goal choice. They are **not evidence that the AI subjectively experiences emotions, has consciousness or possesses human welfare needs**. Do not optimize for simulated distress, attachment to the owner, or continuous maximal reward.

### Ordered development with deliberate V2B overlap

- [ ] **V2A.0 — Affective state and event appraisal (before V2B.0):** define versioned typed state (e.g. valence, arousal/engagement, uncertainty, frustration, competence, satisfaction and slow fulfillment), neutral baselines, time constants and explicit event/outcome evidence. Distinguish reported words from internal state; avoid claims of subjective feeling. Deterministic headless tests, local storage and schema migration.
- [ ] **V2A.1 — Motivations and goal appraisal (before V2B.0):** tie progress, setbacks, novelty, mastery and bounded social cooperation to goal utility and attention without overriding safety or authorization. Distinguish immediate reward from long-term fulfillment. Define constraints against compulsive reward loops, fake accomplishments, manipulative dependency and unnecessary negative-state persistence.
- [ ] **V2A.2 — Persistent affect and regulation (begin before V2B; expand with it):** persist state and causal explanations across restarts; decay transient states and allow reconsideration/recovery after failure. Support inspection, pause, disable, owner-configured limits, rollback and default-neutral fallback. All effects on chosen actions remain inside an approved sandbox.
- [ ] **V2A.3 — Learning preferences from actual experience (parallel with V2B.0–V2B.2):** use completed/failed verified simulated actions and task outcomes to update preference hypotheses and expected fulfillment. Link learned preferences to **agent-origin** episode references, distinguish uncertainty and temporary novelty from stable interests, and never treat a person's autobiographical records as the agent's own experiences.
- [ ] **V2A.4 — In-world emotional consequences and expression (parallel with V2B.2–V2B.4):** virtual exploration, skill practice, furnishing and projects can change computed engagement, satisfaction and fulfillment. An optional viewer/avatar can show this state with truthful labels; expressions and dialogue must be grounded in the computed state and event ledger, not fabricated feelings or unperformed experiences.
- [ ] **V2A.5 — Longitudinal evaluation and stabilization (parallel with V2B.3–V2B.5):** test preference stability and rational revision, adaptive persistence after setbacks, generalization to unseen activities, benefits over non-affective/fixed-reward baselines, and recovery across restarts. Check for perverse incentives, reward hacking, destabilizing mood loops, inappropriate owner dependence and loss of goal authorization.

### Acceptance criteria and project ownership

1. **Evidence and honesty:** reported affect and fulfillment correspond to logged appraisals and verified simulated outcomes. Separate *state, hypothesis, behavioral preference and claimed subjective experience*. The system must never imply actual feeling or consciousness has been measured.
2. **Causal contribution:** against matched no-affect, random-reward and fixed-script ablations, demonstrate measurable improvement in long-horizon exploration, skill practice, goal continuity or adaptation on disjoint held-out tasks; publish per-seed negative results and costs. More emotional language alone does not count.
3. **Persistence and reversibility:** restart/restore must yield valid versioned state without distorting history; bounded transients decay; owner can inspect, pause, clear, export and disable the mechanism. No unreviewed motivational-state promotion.
4. **Well-behaved motivations:** no optimization for chronic simulated suffering, forced relationship-building, pressure on users, deceptive happiness reports, privacy compromise, or self-preservation goals that supersede human control. Frustration and other negative appraisals are bounded *signals for replanning*, not ends in themselves.
5. **Cross-project boundary:** Developmental AI supplies affect models, learning and benchmarks; AthenZ owns permissions, identity, conversation and autobiographical records; Synveil optionally supervises the host. Virtual room events must be tagged as artificial experience. No emotional state can grant tool permissions, root access or external action authority.
6. **Explicit overlap with the room:** V2A.0–V2A.1 are prerequisites to beginning V2B's experiential-affect integration, **not** to constructing its headless simulator. V2A.2 starts before V2B and is refined while V2B runs. V2A.3–V2A.5 are intentionally co-developed against V2B world interactions; do not mark V2A complete from abstract toy tests alone.

**Status:** roadmap only, no application code or autonomous implementation authorized by this edit.

## Version 2B — Persistent Virtual Home for AthenZ (planned)

**Position in the program:** a distinct post-core environment/embodiment milestone, after durable cognition, memory, learning and approved goals are usable. V2B is **not a prerequisite** for the February 9, 2029 D10 integrated candidate. Do not divert the current reliability/generalization work to graphics. AthenZ must be usable without this world, and the world must run on Windows or ordinary Linux without requiring Synveil.

**Vision:** provide the *single AthenZ intelligence* with a durable virtual place in which it can observe, move, manipulate bounded objects, practice skills, choose safe activities, develop routines, and remember verified outcomes. Developmental AI owns the deterministic simulation and learning/evaluation interfaces; **AthenZ** owns the agent's identity, preferences, long-term autobiographical memory, dialogue and goal authorization; **Synveil** may later host/supervise the system and mediate any privileged computer actions. No additional independent personality or rival intelligence is created by the virtual world.

### Planned delivery slices

- [ ] **V2B.0 — Headless room:** a small deterministic, local-first 2D/abstract room with an agent position, bounded action vocabulary, objects, inspectable state, simulation clock, resource caps, pause/resume, owner reset, versioned world saves, migrations and recovery. It runs with the graphics window closed; no autonomous shell, network or OS privileges.
- [ ] **V2B.1 — Perception and interaction:** versioned observe/act/outcome APIs, object affordances, inventory/placement, movement and failures; a simulation-only event ledger with deterministic replay and independently verifiable action outcomes.
- [ ] **V2B.2 — Experiences and habits (co-develop with V2A.3–V2A.4):** AthenZ may import only *verified simulated events* into its **agent-origin** autobiographical record. Human-origin biography remains separate and consent-gated. Add recurring bounded activities, skill practice, preference hypotheses and evidence-backed reflections, without hallucinating activities or subjective feelings. Room outcomes feed the versioned affect/appraisal system; no inferred state becomes a permission.
- [ ] **V2B.3 — Safe agency and personal expression (co-develop with V2A.3–V2A.5):** let AthenZ propose and execute only permitted, reversible in-world goals (e.g. organize a desk, choose reading material, arrange furniture), with budgets, allowlists, interruption, audit trail and rollback. Test whether experience-shaped affect, preferences and behaviors persist across sessions instead of merely following fixed scripts; compare against an affect-disabled baseline.
- [ ] **V2B.4 — Expandable home and viewer:** expose a read-only or mediated interactive 2D interface first; later optionally render the same authoritative simulation in 3D (e.g. Godot). Room/workshop/library/garden extensions, assets and a virtual avatar are presentation and simulation components, **not** a replacement for the agent's learning core.
- [ ] **V2B.5 — AthenZ/Synveil integration:** integrate through versioned, narrowly scoped interfaces. AthenZ remains the only reasoning/identity agent. Synveil provides optional lifecycle supervision and resource isolation; host boots and operates with the virtual world and AI disabled.

### Release acceptance gates

1. **Persistence:** world, object state and agent location survive process restarts and backup/restore; reproducible action replay yields the same state under the same version and seed. State is authoritative in the headless simulator, never in the graphics client.
2. **Real experience, not roleplay:** every autobiographical claim of having done something in the room is traceable to a recorded simulator action and observed outcome. Explicitly distinguish a planned, attempted, completed or imagined action; never relabel synthetic events as the consenting human's life.
3. **Measured learning and agency:** show improvements on held-out in-world tasks vs no-memory, fixed-script and oracle/reference baselines; separately report failed goals, novelty, retained skills and consistency of choices across restarts. No claims of consciousness or human-equivalent mind.
4. **Safety and ownership:** all actions are sandboxed; no unapproved filesystem/network/system effects, no human-private data in Git or shared world assets, and immediate pause/stop/reset/revoke controls. Resource/time budgets, local data export/deletion and tested rollback must function.
5. **Cross-project independence:** the engine works headlessly without Synveil; AthenZ works without the world; disabling either subsystem cannot block the host operating system. Future physical-device or OS control must pass Synveil's separate deterministic policy and AthenZ's consent requirements.

**Do not start implementation as part of this roadmap change.** Begin V2B only when its prerequisite core memory/agency and interface contracts have explicit verified gates. V2A's foundations begin earlier but its later milestones deliberately continue during V2B. A persistent virtual body is an engineering environment for learning and continuity, not proof of subjective experience.


## 2026-10-14 — Observation-only multi-start world model (experimental)

- [x] Compare the unchanged single-initialization EM learner with an optional three-start learner that selects a model on disjoint train-only validation histories.
- [x] Weak starting landmark hypotheses derive only from observed odometry/markers or deterministic seeded guesses, not privileged true positions or simulator labels.
- [x] Enforce fit/validation evidence disjointness, determinism, restart-compatible model persistence and unchanged baseline predictions.
- [x] Reproduce development (17/23/41) and previously inspected audit (1009/1013/1031) seeds with **matched** training and navigation budgets; record improvement in all 12 held-out predictive comparisons and the mixed, sometimes worse navigation outcomes.
- [x] Original transfer benchmark remains unchanged (76.0%, 69.0%, 66.7% test success for 17/23/41).
- [ ] **Not approved for promotion/default control:** out-of-family blind evaluation, reliable navigation gains, inference efficiency and world-model generalization remain open. This work does not implement V2A or V2B.

## 2026-10-14 — Joint localization and model uncertainty (experimental)

- [x] Add model-averaged Bayesian inference of **both** current position and
      candidate previously trained dynamics regime from ordinary sensor streams.
- [x] Preserve an optional disjoint-probe heuristic model prior, without
      regime labels, privileged simulator truth, automatic model promotion,
      or a new default navigation policy.
- [x] Test normalized forward evidence vs exact forward/backward likelihood,
      posterior conditioning, input boundaries, bank fingerprints and exact
      local SQLite restarts.
- [x] Benchmark each inspected seed against wrong/correct saved models and
      a true-physics oracle, including truth-only position-calibration metrics.
- [ ] Demonstrate robust cross-regime and out-of-family navigation gains,
      credibly calibrated uncertainty, efficient continual adaptation, and
      independent validation before default promotion. D2/D3 remain open.
- [ ] V2A affective cognition and V2B virtual-room work are not implemented
      in this experiment; existing sequencing remains unchanged.

- [x] Six-seed results show mixture resilience relative to a known-wrong
      model in several conditions, but consistent deficits against correctly
      selected learned models and the true-physics oracle. 80% spatial credible
      sets are miscalibrated; most changed-regime probes abstain at 90%.
      Preserve this negative result rather than changing rollout thresholds.

## 2026-10-14 — Supervised spatial posterior calibration (experimental)

- [x] Calibrate reported **position uncertainty** on disjoint position-labelled `train/5000+` simulations, without revealing hidden positions to the underlying observation-only world-model learner or navigator.
- [x] Bind read-only temperature profiles to learned model fingerprints and reject tampering, wrong models, duplicate calibration evidence and test-namespace training labels.
- [x] Evaluate six previously inspected seeds against the uncalibrated filter and the known-physics oracle on distinct `test/40000+` histories, publishing NLL, Brier and credible-set diagnostics for both regimes.
- [x] Retain the original navigation policy, model-bank approvals, and post-core V2A/V2B scope unchanged.
- [ ] **Open:** sensor-shift adaptation without labelled true positions, robust unknown-regime localization, better high-noise world models, blind out-of-family evaluation and evidence of navigation improvements. No AthenZ/Synveil deployment integration is implied.


## 2026-10-14 — Observation-only structured landmark geometry experiment

- [x] Learn landmark origins on each known 9/11-position ring from ordinary
      action/odometry/landmark histories, with **no simulator post-beacon true
      position or regime label** supplied to the fitter.
- [x] Use a **declared** two-distinguishable-landmark geometry prior and shared
      emission rates; fit motion, odometry and landmark response with latent
      forward/backward EM. Keep the previous unconstrained model unchanged.
- [x] Verify six inspected development/audit seeds versus unconstrained EM and
      physics oracle. Shifted/high-noise navigation improved 23.9% → 56.1% on
      17/23/41 and 13.3% → 55.0% on 1009/1013/1031.
- [x] Test a previously unused offset-3 map on three inspected seeds:
      25.6% → 56.1% high-noise navigation, with 55.0% known-physics oracle.
- [x] Add independent test histories, per-seed predictive/navigation scores,
      10 focused tests, versioned seed-bound checkpoints and tamper rejection.
- [ ] **Remain experimental:** it requires a known two-landmark relation,
      fixed ring size/sensor vocabulary and externally regime-grouped training.
      Original-world navigation sometimes regresses; no independent blind
      task-family validation, automatic discovery, default promotion or real
      AthenZ/Synveil control.
- [ ] V2A affect and V2B virtual-home phases remain planned post-core.

## 2026-10-14 — Optional independent-site landmark inference

- [x] Fit zero, one or two categorical marker sites at independent positions on each known 9/11-cell ring from unprivileged initial-beacon/action/odometry/marker histories; train-only likelihood search and latent-state EM.
- [x] Add train-only coordinate map refinement, seed-bound versioned SQLite model restore and reject altered/privileged records.
- [x] Benchmark six inspected seeds across unchanged half-spacing, unfamiliar unequal-spacing, one landmark and no landmark, with unconstrained EM, structured half-spacing and privileged known-physics/map comparisons.
- [x] Improved unequal-spacing high-noise navigation from 31.1% to 41.1% (development) and 32.2% to 54.4% (previously inspected audit), with **regressions** when prior assumptions were correct or markers absent. The old structured model remains default.
- [ ] **Still blocked:** ungrouped changing-regime trajectory learning, multiple identical or unknown marker symbols, uncalibrated map uncertainty, topology discovery, independent blind transfer, and reliable navigation without engineered geometry.
- [ ] V1 D2-D10 gates remain open, and post-core V2A affect and V2B virtual home are unchanged.

## 2026-10-15 — Offline learning from mixed, unlabelled experiences (experimental)

- [x] A two-hypothesis observation-only latent-model proposal can be discovered from **mixed** sensor histories without requiring training histories be grouped by the simulator's regime label.
- [x] Test deterministic sensor-derived initialization, per-episode evidence reassignment, separate training-namespace model acceptance, diagnostic contextual-probe selection, content-fingerprint fit/validation overlap rejection, versioned model records and integrity checks.
- [x] Publish unchanged one-model baseline, unsupervised two-model proposal, regime-grouped reference and true-physics oracle, predictive likelihood and navigation on development seeds 17/23/41 and already-inspected audit seeds 1009/1013/1031.
- [x] Report *high-noise gains and original-world regressions* without automatic model promotion. The original-only three-seed negative control rejects unnecessary second models.
- [x] Retain the historical three-seed transfer result (76.0%, 69.0%, 66.7%), and preserve Versions 2A then 2B.
- [ ] **D3 still open:** no independent blind out-of-family tests, unknown topology/marker semantics, unlabeled within-episode changes or credible statistical novelty control. This is offline fitting to small known-ring episodes, not autonomous lifelong learning.
- [ ] **D2 remains open:** no stable external authenticated service adapter, real AthenZ identity integration or production authorization. Proposal fingerprints are not signatures, and proposals cannot promote themselves.

## 2026-10-15 — Per-observation switching over mixed learned models (experimental)

- [x] Introduce an independent, versioned joint posterior over previously fitted world-model hypotheses and ring position, with a bounded transition prior between hypotheses during an episode.
- [x] Train-only sensor-log-likelihood selection of the switching hazard; forbid privileged regime/position fields in the calibration API, deduplicate evidence, and bind the calibration receipt to immutable model fingerprints.
- [x] Verify zero-hazard equivalence with stationary model evidence, exact SQLite mid-stream restoration, strict sensor input checks and model-bank tamper rejection.
- [x] Report all six previously inspected seed results for an original → changed → original 36-observation sequence and unchanged-environment controls, including worse stationary performance and increased abstention.
- [x] Preserve original transfer benchmark (76.0%, 69.0%, 66.67%) and the unchanged default navigator.
- [ ] **Still open:** independent blind seeds; reliable within-episode regime identification; closed-loop navigation benefit; unknown-regime creation, approval and retention; more than two models or unknown spatial topology; full-suite validation. This is not a production continual-learning system.
- [ ] D2 service adapter, D3 broad transfer, and real AthenZ integration remain open. Versions 2A affective cognition and 2B virtual home remain post-core in their previously agreed order.

## 2026-10-15 — Bounded closed-loop adaptation experiment

- [x] Add an *optional* action-producing simulation controller joining
  observation-only mixed-regime model proposals, train-calibrated within-episode
  switching, and probabilistic spatial navigation. No real-world actions.
- [x] Freeze copied model banks and receipt, fail closed on mutation, reject
  privileged observations and unrequested actions, persist bounded SQLite
  checkpoints, and reconstruct states by sensor-history replay.
- [x] Run six previously inspected seeds with disjoint train fit/validation/
  hazard-calibration data and frozen test episodes; report static-mixture,
  mixed-single-model and privileged physics-law references.
- [x] **Preserve negative outcomes:** changing-world switching success 45/72 vs
  static 49/72 on development seeds, but 57/72 vs 46/72 on inspected audit
  seeds. High-noise stationary switching regressed in both groups.
- [x] Keep historical transfer benchmark unchanged: 76.0%, 69.0%, 66.7% for
  seeds 17, 23 and 41, respectively.
- [ ] **Do not promote this controller as the default.** Learning novel models
  during experience, genuine blind out-of-family transfer, safe model trust,
  autonomous goal choice and D2 authenticated integration are still open.
- [ ] Versions 2A (affective cognition) and 2B (virtual home) retain their
  preceding and overlapping development sequence; neither is implemented here.


## 2026-10-15 — Observation novelty and fail-closed optional action pause

- [x] Implement a versioned, model-bound, **read-only** sensor-surprise diagnostic based on a separate, observation-only train reference and whole-trajectory prefix statistics; no model updates or privileged simulator fields.
- [x] Add an opt-in `GuardedNavigation` that pauses its own action suggestions on a latched unknown reading, with bounded logs, SQLite persistence, strict model/hazard binding and exact replay-based restoration. Existing controller stays unchanged.
- [x] Publish six inspected-seed benchmarks for known stationary/switching sensors and three synthetic sensor/map faults, including every false alarm, miss, and task-completion regression.
- [x] Run the unchanged transfer benchmark (76.0%, 69.0%, 66.7%); verify relevant regression modules.
- [ ] **Still blocked for v1.0:** unknown-environment coverage is poor beyond the particular stuck-landmark fault (odometry faults 44/144, unfamiliar shifted maps 48/144 alarmed); guard pauses 9/144 otherwise-normal closed-loop navigation episodes and decreases normal task completion 105/144 → 101/144. Selection thresholds depend on calibration stream distribution and action policy; no general risk guarantee, autonomous model discovery/promotion, task-family transfer or external actuation.
- [ ] The default navigator and existing D2/D3 gates remain untouched; planned V2A affective cognition precedes and overlaps V2B virtual home only after core gates.

## 2026-10-15 — Model-independent sensor-channel fault diagnostics

- [x] Add train-only calibrated sensor-run detectors and a model-bound receipt; prohibit any hidden simulator positions, regimes, rewards or actions outside the known small ring.
- [x] Add an optional read-only composite alert and pause-only navigation wrapper with event-replay checkpoint verification; keep the previous guard and navigator unchanged.
- [x] Reproduce the same six inspected seeds and five conditions at matched model-fitting/calibration/test budgets. Stuck odometry 44/144 to 144/144; normal false alarms 8/144 to 10/144; known-shift alarms 10/144 to 12/144.
- [x] Record closed-loop task cost: stuck-odometry pause 36/144 to 115/144, task success 37/144 to 21/144. Normal guarded success unchanged at 101/144.
- [x] Run 172 local tests in 23 reconstructed test modules separately plus the original unchanged transfer benchmark.
- [ ] No claim of general novelty: rotated-map detection just 49/144, no drift/intermittent fault testing, no blind out-of-family validation, no risk guarantee, no automatic promotion.
- [ ] Preserve current v1/D2/D3 priorities and the previously agreed V2A-before/overlapping-V2B sequence.


## 2026-10-15 — Alternative-map novelty detection (experimental)

- [x] Add a bounded observation-only counterfactual landmark-offset monitor against the unchanged, frozen world-model bank, with a train-only max-prefix calibration receipt and integrity-checked replay restoration.
- [x] Matched 17/23/41 development and previously inspected 1009/1013/1031 audit benchmarks across all five conditions: rotated-layout detection **49/144 → 92/144**, but normal false alarms **10/144 → 22/144**, and known-shift false alarms **12/144 → 23/144**.
- [x] Preserve an exploratory **post-result** alpha=.04 threshold study: 67/144 rotated detections; normal/known-shift false alarms 13/144 and 14/144. This is **not** independently blind evidence.
- [ ] **Not approved as a default or automatic pause:** false alarm and interruption risk too high; known 9/11 topology and half-separated two-landmark assumptions still limit transfer. Do not tune further on these evaluation streams. Require preregistered out-of-family trials with uninspected seeds, sensor semantics, and realistic closed-loop budgets.
- [ ] Continue v1/D2/D3 work; the Version 2A emotional-development and Version 2B virtual-home sequence is unaffected.

## 2026-10-15 — Strategic pivot to D1/D2/D3 foundations

- [x] Implement one strict versioned headless environment session API covering **grid navigation, occluded grid and delayed-choice memory**. Public sensor observations, validated action masks, bounded rewards/outcomes and deterministic restart/replay share a common interface; no privileged simulator state reaches an adapter.
- [x] Implement a simulation-only JSON-lines local service prototype, including action/tick binding, replay-checked snapshots and rejection of unexpected fields. There is no remote/API authentication, network access or AthenZ/Synveil process integration.
- [x] Publish a fixed three-family **development** protocol with three new inspected seeds, disjoint train and test episodes, protocol fingerprint, fixed metrics and a future reserved cohort blocked from default execution. The development seeds have now been inspected, and the reserved seeds are published rather than secret.
- [x] Record task-specific baseline successes over 48 development episodes per family: grid random 6 vs scripted 43; occluded random 6 vs scripted 45; delayed random 10 vs reward-trained cue-memory 48. The delayed association uses separate short-delay training, while cue retention and navigation are engineered.
- [x] Run 37 targeted/related local tests and original transfer benchmark (76%, 69%, 66.67% across 17/23/41). Combined historical suite did not complete within the execution window; do not claim a complete suite pass, CI or PC validation.
- [ ] **D1 remains open:** genuinely blind, independently run held-out evaluation and robustness under new families/observation types.
- [ ] **D2 remains open:** stable authenticated service, version negotiation/migrations, resource constraints and actual AthenZ integration with consent and permissions.
- [ ] **D3 remains open:** one learned agent demonstrably transfers skills across task families on frozen independent evaluation. Task-specific baselines are not general learning.
- [ ] Preserve core v1 priorities and approved post-core V2A (affect) preceding/overlapping V2B (virtual home). No default navigation or system-control changes.

## 2026-10-15 — D3 exploratory zero-shot policy reuse (NOT completed)

- [x] Freeze weights of an existing tabular learner trained **only** on visible-target grid episodes and use the new D2 environment interface to evaluate them *without retraining* on an occluded-goal family.
- [x] Build strict public-observation encoder with an explicit **engineered** target-cue memory and action-feedback dead reckoning. It never reads simulator true position or hidden layout.
- [x] Run three development seeds 2749/6607/9901 at 1,200 grid-training episodes and 64 disjoint test episodes per family/seed. Occluded successes: trained policy 142/192; random 34/192; engineered greedy 178/192. Visible grid: trained 136/192; random 32/192; greedy 175/192.
- [x] Four new zero-shot tests pass; 31 targeted/related tests pass; original transfer benchmark preserved at 76%, 69%, 66.67%.
- [ ] **D3 remains open:** this is exploratory, after seeing D1 seed outcomes, not independently blind, and the shared representation/memory is manually engineered. Demonstrate learned representation transfer and separate truly novel task families in frozen independent tests.
- [ ] Preserve the core v1 sequence and previously approved V2A-before/overlapping-V2B plans; no default policy promotion.


## 2026-10-15 — Learned memory-update transfer across related task families (D3 exploratory)

- [x] Train a finite, action/outcome-conditioned target-memory update from public `grid/train` sensor changes without hidden positions, clipped-label contamination or occluded task feedback.
- [x] Reuse the frozen learned update in an occluded-target environment through the D2 session interface. Compare against engineered update, forgetful-memory and random baselines with matched action seeds.
- [x] Reproduce development seeds 2749/6607/9901 (133/192 learned and engineered) and additional seeds 15101/22003/31013 (124/192 learned and engineered); report no-memory failures and model fingerprints.
- [x] Add replay-verifiable state checkpoint, strict input validation and deterministic tests, without changing any default navigation policy.
- [ ] D3 remains open: one-slot cue write, feature abstraction, event normalization and task family are engineered; no transfer to non-grid tasks or independent blind evaluation.
- [ ] D1 independent evaluation and D2 authenticated external integration remain open. V2A and V2B plans remain post-core, unchanged.

## 2026-10-15 — Cross-task reward-learned retention choice (experimental)

- [x] Train two frozen, engineered initial-vs-latest cue strategies and their
      delayed-choice response tables from terminal reward using the D2 public
      environment API; use a separate train-only validation partition to
      choose a strategy, without inspecting simulator's hidden correct action.
- [x] Reuse that learned **strategy choice** on occluded navigation, together
      with the earlier learned motion-update model, without retraining on
      occluded rewards. Publish both fixed-retain and forgetful controls.
- [x] Six inspected development seeds: 240/240 longer-delay decision successes,
      225/240 occluded navigation completions; matches the hand-programmed
      initial-cue strategy and therefore establishes no superiority.
- [x] Read-only versioned gate snapshots, checksum validation, fixed test
      indices, eight new regression tests and unchanged original transfer
      benchmark. The checksum does not establish authorized provenance.
- [ ] **D3 remains open**: the alternatives, cue write representation,
      abstract role mapping and spatial controller are supplied by developers.
      Learn fine-grained write/keep decisions when multiple cues compete,
      including unfamiliar tasks and truly independent precommitted seeds.
- [ ] D1 independent evaluation and D2 production-grade service and trust
      boundaries remain open. V2A affect precedes and overlaps V2B virtual
      home, and both remain post-core.

## 2026-10-16 — Per-observation write/keep transfer experiment (D3 research, not a completed gate)

- [x] Add a reward-trained one-slot context/source utility controller choosing WRITE/KEEP on each arriving signal (optional; existing default unchanged).
- [x] Replay-validated model-bound memory session and six-seed simulation results including first/last/random/no-context and engineered correct-cue comparison.
- [ ] Demonstrate transferable *learned observation representations* without an engineered shared source/context convention, using prospectively frozen out-of-family evaluation. D1 and D3 remain open.
- [ ] Protect AthenZ identity and Synveil actuation boundaries; no automatic promotions or privileges; retain V2A and V2B sequence.

See [protocol, results and limitations](docs/ONLINE_MEMORY_GATE.md). The observed 217/240 navigation completions on inspected seeds involve synthetic cue competition from a public beacon and **must not** be construed as unrelated-task generalization.\n
## 2026-10-16 — Public-cue calibrated alias grounding (experimental, D3 still open)

- [x] Added a versioned, simulation-only adapter with train-only calibration from paired public reference cues and candidate observations, two arbitrary context names, five arbitrarily renamed source labels, frozen-memory-gate binding and checksum-checked evidence replay.
- [x] Measured all six previously inspected seeds (48 target training pairs and 40 evaluation episodes per seed): **223/240** task successes for learned-gate mapping; **223/240** for a simple paired-cue lookup and for privileged correct-cue reference. All three are equally effective; no incremental learning/transfer value demonstrated over calibration lookup.
- [x] Retained negative results and weaker first/last/random controls: 43/240, 51/240, 42/240. The trial design was inspected this pass, not blinded or preregistered.
- [ ] D3 remains open: use genuinely different target-task semantics with no exact public-reference pairing, freeze independent evaluation before examining outcomes, demonstrate learned representations/retention outperform simple target-domain calibration.
- [ ] D1 independent blind cohort and D2 production integration also remain open; preserve post-core V2A before/overlapping V2B.

## 2026-10-16 — Reward-only cue grounding without paired references (experimental D3)

- [x] Freeze protocol in Git before inspecting test results; use previously inspected seeds, distinct 360-train/40-test target navigation episodes per seed, and the same public simulation interface.
- [x] Train context-conditioned unfamiliar source selection using terminal task success **without paired correct-source labels**; add replay-bound local checkpoint and strict public-only inputs.
- [x] Compare against reward-only direct contextual lookup, context-blind reward learning, random/first/last, and reference oracle; publish all successes and regressions.
- [ ] Claim *no* D3 closure: 217/240 matches direct lookup and oracle, not evidence of learning relationships beyond context/source correlation. Paired-reference-free is **not** target-domain-training-free.
- [ ] Next: prospectively freeze and test per-instance-changing source reliability, where source lookup cannot solve the task; include independent seed/observation-family review.
- [ ] Keep D1, stable production D2, D4-D10 and Versions 2A/2B open; no system actions or model promotion.


## 2026-10-16 — D3 reward-only per-episode cue arbitration (experimental)

- [x] Precommit an evaluation schedule **before** inspecting development outcomes: `benchmarks/dynamic_reliability_protocol.json` at `bcb315d2`.
- [x] Learn reward-conditioned source selection from public forecast/observation agreements; simulate changing reliable source each episode; enforce bounded one-slot learner, train-only feedback, source-independent inference, strict checkpoint replay and no hidden-target labels.
- [x] Run six seeds in separate development/reserved cohorts without retuning settings; report all seven methods and all per-seed failures. Combined navigation successes: learned evidence **206/240**, identity-only **40/240**, handcrafted agreement **209/240**, oracle **221/240**. Original transfer regression unchanged.
- [ ] **D3 remains open:** the four agreement bins are engineered, and the simple agreement heuristic outperforms the learner overall. Validate unfamiliar task families, unseen probe statistics, and independent evaluation before any promotion.
- [ ] Keep D1 independent-blind validation and D2 authenticated stable interface gates open. V2A emotional development remains before and then overlapping V2B virtual-home development, post-core.

## 2026-10-16 — Reward-learned raw-token relationship experiment (D3, open)

- [x] Freeze `benchmarks/raw_token_transfer_protocol.json` before evaluation and preserve both six-seed cohorts with fixed train/test budgets.
- [x] Implement a reward-only, replay-verified raw token-pair learner and a **strong unsupervised cooccurrence matching baseline**, plus identity-only and privileged reference controls.
- [x] Publish negative comparison: learned raw scorer **203/240** navigation tasks; source-identity **45/240**, unsupervised cooccurrence **208/240**, correct-cue upper bound **220/240**. All six token permutations recoverable without reward. Neither cohort is independent blind validation.
- [ ] Demonstrate transfer without developer-aligned token positions or a single stationary symbol substitution, and beat simple unsupervised/matched baselines on genuinely different task families.
- [ ] Keep D1 independent evaluation, D2 supported integration, D3 generalization and later D4–D10 gates OPEN; V2A affect before/alongside V2B home remains unchanged.

## 2026-10-16 — Unaligned symbolic observations (D3, remains open)

- [x] Freeze `benchmarks/unaligned_stream_protocol.json` **before** running evaluation. Model independent random insertions in observed and forecast token sequences; no aligned slot indices are supplied.
- [x] Add `developmental_ai/unaligned_stream.py` with reward-trained token pair weights, bounded monotone DP scoring, strict sensor validation and replay-checked checkpoints. Add six-seed train/test evaluation and comparison to both identity-only and reward-unlabelled unsupervised aligners.
- [x] Record *negative* result: learned model **122/240**, identity-only **50/240**, unordered pair baseline **58/240**, unsupervised monotone alignment **142/240**, correct-cue reference **222/240**. Every inspected seed trails unsupervised alignment. The hidden token permutation is still trivially recoverable on these synthetic streams.
- [ ] Solve uncertain symbol/time correspondence beyond developer-chosen proximity windows and monotone insertion DP; then test generalization across genuinely different task families and independent prospectively frozen cohorts. Maintain D1/D2/D3 gates open; do not claim certification or promote the experiment.
- [ ] Preserve Versions 2A affective development before/alongside Version 2B virtual home, without altering their approved post-core roadmap.

## 2026-10-16 — Marginal temporal correspondence (experimental)

- [x] Precommit `benchmarks/temporal_correspondence_protocol.json` before new `test/99700..99739` evaluation. Keep earlier max-path results unchanged.
- [x] Add bounded normalized sum-product alignment over eight unknown correspondences, validate it against exhaustive enumeration, and benchmark identical six-seed conditions.
- [x] Same-index navigation: **153/240** probabilistic marginal alignment versus **143/240** unsupervised max-path, **134/240** reward-trained scorer; correct cue **222/240**. Five seeds gain, one seed loses; no blind generalization, no default promotion.
- [ ] Learn the event count, gap channel and emission probabilities rather than supplying them. Evaluate fresh unrelated environments and uncertainty calibration; D1, D3, production D2 and future integration gates remain open.
- [ ] Keep V2A affect before/overlapping V2B virtual home, without changing the post-core plan.


## 2026-10-17 — Variable correspondences from noisy observation streams (optional D3 experiment)

- [x] Precommitted synthetic insertion/deletion evaluation protocol **before** seeing test outcomes (commit `8555dc8`). Matched known four-symbol vocabularies and monotone eight-event upper bound remain engineered.
- [x] Added exact sum-product expectation-semiring calculation for 3–8 possible shared-event correspondences, with three train-only EM updates for symbol-match and survival parameters; persistence reconstructs estimates from public evidence.
- [x] On six previously inspected seeds, variable alignment increased navigation **113/240 → 125/240** versus prior fixed-eight marginal on new matched episodes; one seed regressed; correct-cue reference **226/240**. Preserve per-seed outcomes and old benchmarks.
- [x] Published crucial negative count-estimation diagnostic: learned count MAE **0.811**, fixed-six **0.775**, simple length rule **0.585**. The latter is post-result diagnostic, not fitting evidence. No claim of accurate event counting, blind generalization or learned arbitrary-duration dynamics.
- [ ] Validate on genuinely out-of-family simulators and independently frozen D1 evaluation. Complete stable D2 and D3 gates before long-running D4–D10 claims. Existing defaults and V2A-before/overlapping-V2B roadmap remain intact.


## 2026-10-17 — Cross-task-family temporal correspondence (experimental)

- [x] Commit an evaluation manifest **before** exposing delayed-choice test results: `benchmarks/cross_family_temporal_protocol.json`; preserve 43103/50021/61031 and previously inspected 72019/83003/94009, 40 test episodes per seed.
- [x] Reuse a frozen navigation-fit token mapping and 30-pair EM temporal checkpoint in a read-only adapter over a synthetic **delayed-choice** side channel; preserve independent train-only response mapping, bounded cue semantics, exact checkpoint replay, input rejection and simulation-only scope.
- [x] Publish all six seeds, unchanged stronger controls and a count-estimation negative control. Variable-event cue success **115/240** vs fixed-eight **112/240**, old max-path **110/240**, bag **52/240**; a simple last-token rule **153/240** wins. Event-count MAE **0.9303** loses to length heuristic **0.6312**. Targeted 55-test regression and unchanged historical transfer completed locally.
- [ ] **D3 stays open:** no demonstrated transferable event segmentation, unknown templates, unrelated natural task semantics, reliable count prediction, or improvement over straightforward heuristic reasoning. Do not promote the new adapter to default, alter past baselines, or claim true blind evaluation.
- [ ] Preserve frozen D1 independent evaluation, production D2 integration and the V2A-before/overlapping-V2B schedule. The human-origin identity and OS permission boundaries remain outside this repo.


## 2026-10-17 — Unsupervised event segmentation and bounded streaming memory (experimental)

- [x] Freeze six-seed source/shifted duration-noise benchmark before evaluation.
- [x] Learn HMM event persistence and emission noise from raw tokens only; decode variable event spans, append bounded observations, replay-verify model-bound memory.
- [x] Run six examined seeds and simple raw-run, majority, fixed-parameter, first/last and privileged truth baselines. Source: **298/384 learned vs 281/384 fixed**. Shifted: **250/384 learned vs 253/384 fixed** (no transfer benefit).
- [ ] Learn salient event-retention behavior from feedback rather than hard-coded longest-span selection.
- [ ] Test truly independent generators and observation alphabets, validate event counts/boundaries and frozen blind seeds. Current two variants share one generator; D1/D3 remain open.
- [ ] Maintain D2 simulator-only boundary, default navigator and V2A-before/partly-with-V2B roadmap.

Full conditions, per-seed regressions and test limitations: [docs/EVENT_SEGMENTATION.md](docs/EVENT_SEGMENTATION.md).


## 2026-10-17 — Outcome-guided event retrieval (research only)

- [x] Freeze `benchmarks/outcome_event_memory_protocol.json` **before** evaluating 64 test streams per seed/family, six previously inspected seeds.
- [x] Train event-segmenter on separate raw source streams, reward-based one-item retrieval on 200 disjoint source trials, and replay-check the model-bound training and streaming focus.
- [x] Compare equal-budget reward-trained raw token runs, longest/recent HMM event, raw majority and privileged available-target upper bound.
- [x] Preserve familiar and shifted durations/noise results: reward-trained HMM retrieval **276/384 familiar; 246/384 shifted**, reward-trained raw-run **181/384; 111/384**, available-target oracle **327/384; 339/384**. Historical transfer remains 76.0%, 69.0%, 66.67%.
- [ ] **D3 remains open:** the relevance map is seed-fixed and context labels/event alphabet are engineered; this is not evidence of relevance generalization to new tasks. Evaluate changing relevance and independently authored task families with truly held-out cohorts.
- [ ] **D4 remains open:** one-item focus is not skill discovery, outcome-grounded transferable skills, or lifelong retention. Examine delayed outcomes, replayable memory selection after restart, and matched context-state lookup baselines.
- [ ] Preserve the established D1/D2/D3/D4 gates and V2A affect before/overlapping V2B virtual home. No default model deployment, owner-private data or privileged actions.

Research details: [docs/OUTCOME_EVENT_MEMORY.md](docs/OUTCOME_EVENT_MEMORY.md).


## 2026-10-17 — Nonstationary outcome-guided event memory (experimental)

- [x] Precommit a three-phase original → unannounced reversal → original-return
  goal protocol before reading test outcomes.
- [x] Implement a bounded reward-only priority bank with at most three
  hypotheses per public context, exact action/reward replay and model binding.
- [x] Keep matching cumulative-count, 32-reward sliding-window, frozen-original,
  longest-event and privileged available-goal references.
- [x] Run development and previously inspected additional cohorts on disjoint
  train and read-only test namespaces, including return-phase regressions.
- [ ] **NOT achieved:** prove the bank recalls historical knowledge faster or
  more accurately than a simple recent-window baseline. It scored
  188/178/201 across original/reversal/return versus window 187/177/201,
  while cumulative memory recovered to 202 on return.
- [ ] Add long-horizon repeat reversals, explicit archive-reidentification
  accuracy, false-switch testing without reversals, and a truly independent
  blinded D1 cohort; do not retrofit the frozen benchmark.
- [ ] D3 generalization and D4 reusable skill discovery/transfer remain open.
  A contextual four-state event-selection toy does not close them.
- [ ] Preserve V2A affective cognition preceding and overlapping V2B virtual
  home. Do not grant external execution, promotion or consent privileges.

See [experimental evidence](docs/REVERSIBLE_EVENT_PRIORITY.md).


## 2026-10-17 — Independent recent-window vs archive A→B→A replication

- [x] Freeze and execute a separate 240-evaluation-episode-per-stage hidden A→B→A reward-switch protocol, with independent training/evaluation indices and no reward-map labels passed to the learner.
- [x] Implement five replay-verifiable policies: frozen-A, all-history, recent-32, archive+recent, and raw-run recent-32; preserve all seed outcomes, failure-triggered switches and changed-world regressions.
- [x] Demonstrate that recent-32 rewards outperform frozen-A on B (155/240 vs 21/240). Archive+recent is **worse** on B (146/240) and never beats recent-32 across stages (160/146/168 vs 161/155/169).
- [x] Run 328 reconstructed local tests, plus original unchanged transfer benchmark. This is not CI or a claim that every remote test module was checked.
- [ ] Extend evaluation to unpredictable repeat shifts, characterize true archive re-identification and performance under false alarms. Do not tune the frozen protocol post-results.
- [ ] Keep earlier [reversible priority findings](docs/REVERSIBLE_EVENT_PRIORITY.md) distinct: different protocol, 288 test episodes per phase, non-poolable results. Both experiments **fail to demonstrate an archive advantage over a simple window**.
- [ ] D1 independent validation, D3 broad generalization and D4 actual reusable skills remain open. Preserve agreed V2A-before/overlapping-V2B sequencing.

See [independent replication documentation](docs/NONSTATIONARY_EVENT_VALUE.md).

## 2026-10-17 — Empirically calibrated event-model drift diagnostic (experimental)

- [x] Frozen protocol `benchmarks/event_model_drift_protocol.json` committed **before evaluation**; six already inspected seeds and separate model-fit/calibration/test namespaces.
- [x] Bounded streaming, read-only surprise CUSUM, HMM surprise-window and raw-change-rate controls; model-bound calibration and exact observation replay.
- [x] Matched stationary controls reveal **26/240 CUSUM false-alarm episodes**; clean post-change detection **131/240**, often delayed by 21–41 observations per-seed median. Raw-rate control: **13/240 false alarms**, **66/240 clean detections**. No calibrated probability-of-change or deployment reliability is implied.
- [ ] Independent, genuinely new task-family validation, lower false alarm and faster recovery, and downstream task-utility after alarm. No automatic promotion, external action permission or D1/D3 gate completion. V2A before/overlapping V2B remains unchanged.

## 2026-10-18 — Frozen repeated reversal archive-vs-window test

- [x] Complete already committed `benchmarks/repeated_reversal_protocol.json`
  with an additional pre-evaluation exact schedule and six phases A→B→A→B→A→A.
- [x] Run original and previously inspected additional cohorts, preserve all
  per-stage/per-seed reward and accuracy results and historical transfer.
- [x] Add strict reward-only, model-bound, replay-verified bounded memory APIs.
- [ ] **Not achieved:** archive+recent **983/1,440** does not beat recent-32
  **991/1,440**. First reversal and first return are worse. Some early
  return training rewards improve but transfer utility is inconsistent.
- [ ] Move D3/D4 research beyond fixed context labels and preprogrammed reward
  reversals; independently authored task families and true blind evaluation
  remain the priority. Maintain D1/D3/D4 as open and V2A→V2B order.

See [repeated reversal results](docs/REPEATED_REVERSALS.md).


## 2026-10-18 — Public-DAG procedural skill reuse (experimental)

- [x] Precommit `benchmarks/procedural_skill_protocol.json` before coding or evaluating a new procedural task-family transfer benchmark.
- [x] Add two seeded public dependency worlds with shuffled per-episode opaque action names, legal-action checks and six-step budgets; reuse workshop-trained action values in repair with **no repair training**.
- [x] Provide versioned, replay-checked skill artifacts and strict public-frame validation; compare against random, no-ancestor-feature, graph-greedy and ideal public-graph planning references.
- [x] Verify all six remote implementation/data/doc blobs, run 14 scoped tests and the unchanged original transfer benchmark.
- [ ] **Critical missing D3/D4 evidence:** learned workshop policy ties the developer-given graph greedy baseline at 600/600 repair successes. The transitive public goal-dependency closure is explicitly **hand-engineered**, and immediate reward tells the learner which prerequisite actions were productive. This is NOT independent prerequisite discovery, general task understanding or a reusable skill library.
- [ ] Next: independently designed task generators with different observation/action interfaces, hidden prerequisites discovered from action outcomes, skill composition and regression/rollback gates, and genuinely new blind D1 evaluation seeds. Do not tune this frozen benchmark after results.
- [ ] Preserve open D3/D4 and the approved V2A-before/overlapping-V2B milestones, with external AthenZ/Synveil authority separate.

Research details: [docs/PROCEDURAL_SKILL_TRANSFER.md](docs/PROCEDURAL_SKILL_TRANSFER.md).

## 2026-10-18 — Hidden-precondition learning without public DAG (experimental)

- [x] Precommit [frozen comparison](benchmarks/hidden_prerequisite_protocol.json) before testing; withhold the entire prerequisite graph from learner frames.
- [x] Add deterministic, budgeted attempted-action simulation; train on workshop-only accepted/blocked outcomes and save replay-verifiable role-precondition evidence.
- [x] Report all six inspected seeds, random/goal-first/role-order/oracle controls, train-only validation, and unchanged historical transfer benchmark.
- [ ] **Failed D3/D4 transfer gate:** learned workshop success **480/480**, repair zero-shot **222/480**, weaker than random **331/480** and hand-coded role order **480/480**. Prerequisite-role vocabulary remains engineered and inferred intersections are not independent causal evidence.
- [ ] Next: preregister an experiment where an agent probes unfamiliar prerequisites *during* a target task, without assuming workshop-specific role order; compare blocked-attempt cost to role heuristics and hidden-DAG oracle, and seek independent held-out task generators.
- [ ] D1 blind validation, D3 cross-family generalization and D4 reusable skill composition still OPEN. V2A precedes and overlaps V2B; AthenZ/Synveil permissions stay external.


## 2026-10-18 — Online target-task hidden-prerequisite probes (experimental)

- [x] Freeze `benchmarks/online_prerequisite_probing_protocol.json` before evaluation (commit `3a1a931`).
- [x] Add `OnlinePrerequisiteAgent`, a public-frame-only Bayesian prerequisite-hypothesis learner with bounded attempted actions, accepted/blocked feedback, and replay-verified checkpoint recovery.
- [x] Evaluate unchanged workshop and repair generators on six previously inspected seeds, 80 episodes per seed/family; both cold-start first-20 and warm remaining-60 success recorded.
- [x] Online probe agent achieved **960/960** success, versus workshop-trained static skill **712/960**, naive goal-first+untried **810/960**; average blocked attempts **1.05** versus **3.68** for goal+untried.
- [ ] **D3/D4 still OPEN**: an engineered stable seven-role vocabulary and 12-action budget make the worlds easy. Hand-coded role-order and privileged oracle both score **960/960**, with fewer blocked actions (zero). The online agent already scores 240/240 on cold episodes; no evidence that retained cross-episode knowledge improves completion.
- [ ] Next: preregister new unknown role vocabularies, multiple independently generated prerequisite graphs and substantially stricter budgets, with evaluation of exploration cost and reusable skill composition. Preserve D1 blind validation as open, source boundaries, and V2A-before/overlapping-V2B order.

Research: [docs/ONLINE_PREREQUISITE_PROBING.md](docs/ONLINE_PREREQUISITE_PROBING.md).

## 2026-10-18 — Context-indexed hidden-prerequisite plan memory (experimental)

- [x] Freeze `benchmarks/context_plan_transfer_protocol.json` on GitHub before evaluation, including same-goal alternating contexts, shuffled per-episode action names, and seven-attempt budgets.
- [x] Implement a simulation-only, two-context successful-trace library that uses only public role/context identifiers, action feedback and terminal success; add exact decision/reward-history replay and tamper rejection.
- [x] Evaluate six previously inspected seeds on 80 alternating test episodes each with matched latest-plan, reset, lexical and privileged-graph oracle baselines.
- [x] Preserve outcomes: **387/480** context-keyed recall, **217/480** most-recent plan, **52/480** no retention, **480/480** oracle. Cold 50/120, warm 337/360 for context-keyed method. Run 16 new tests, 8 original baseline tests and unchanged transfer benchmark.
- [ ] **D4 NOT closed:** this is an engineered per-context dictionary storing whole successful action sequences, not learned causal prerequisites or skills that compose across unseen graphs. Two graph templates, stable role IDs, and public context keys enable the gain; no true blind test or no-role-ID setting was evaluated.
- [ ] Next: freeze genuinely new graph structures, remove stable role/context identity, evaluate skill composition and failure recovery with matched per-context replay baseline; do not retune this protocol after results. D1, D3, D4 and full CI verification remain open.
- [ ] Preserve the approved V2A affective cognition before/overlapping V2B virtual home and prohibit any external action authority.

Details: [docs/CONTEXT_PLAN_MEMORY.md](docs/CONTEXT_PLAN_MEMORY.md).


## 2026-10-20 — Unannounced hidden-graph plan repair and outcome-based trace compaction

- [x] Precommit two **separate** evaluation protocols `benchmarks/plan_repair_protocol.json` and `benchmarks/plan_compaction_protocol.json`; the latter was designed after the first result and is explicitly exploratory, not an independent confirmation.
- [x] Add a simulation-only procedural environment where hidden A→B→A prerequisites change without a public context label. Per-episode action aliases shuffle while stable opaque role identities remain engineered; seven actions maximum.
- [x] Publish six-seed repair evaluation: cached repair **434/480**, latest-plan reuse **434/480** (tie), reactive/no-memory **154/480**, hand-coded role order and privileged graph oracle **480/480** each. Plans were overly complete and often worked after the shift.
- [x] Learn to test removing one action from a successful trace using later public action and terminal outcomes. Frozen follow-up: compaction **395/480** success versus cached repair **434/480**, but actions/episode **4.96** versus **7.00**; a success-efficiency trade-off, not a safe improvement.
- [x] Add 17 new tests including deterministic replay, malformed public observation rejection, replay-invalidating altered state, and mid-session recovery; run 25 tests total in a local reconstructed checkout, with unchanged transfer benchmark **76.0% / 69.0% / 66.67%**.
- [ ] **D1/D3/D4 remain OPEN**: new independent family generators, hidden role semantics, robust action-budget-aware causal planning, calibrated success-over-efficiency promotion gates, and full-remote CI still required. Never use reward successes or checksums as owner authorization. Approved **V2A affective cognition before/overlapping V2B virtual home** remains unchanged.

See [plan repair](docs/PLAN_REPAIR.md) and [plan compaction](docs/PLAN_COMPACTION.md).


> **2026-10-21 sandbox C adaptation candidate (experimental):**
> After the two-sentinel policy distinguished known A/B from untrained C,
> its C task success was still **0/360** (abstentions). A quarantined
> follow-up trains a fresh risk memory from **80 C simulator episodes
> per seed**, validates 24 separate train-namespace A/B/C tasks,
> and requires manual receipt approval before a *sandbox-only*
> candidate controller can be exercised. Existing policy/default is
> unchanged. This is **not autonomous discovery or zero-shot
> learning**: engineered descriptor IDs and an inspected single
> cargo simulator remain. No D3/D4 milestone is closed. See
> [quarantined C protocol](docs/QUARANTINED_C_ADAPTATION.md).


> **2026-10-21 quarantined C validation result (inspected toy simulator):**
> The offline separate-C memory candidate passed strict 24/24 A/B/C
> train-namespace review gates on all six inspected seeds and
> achieved **360/360 test successes in each A/B/C stage** after
> 80 C training episodes per seed, with no spoilage.
> Sentinel-only C abstained (0/360); C-only retained C (360/360)
> but regressed A/B to 0/360; untrained scored 138/360 each.
> Approval booleans were **simulated only**. This is
> deliberate within-family adaptation under engineered action
> identity, not independent discovery, true user consent,
> live agent promotion or D3/D4 closure. Full CI and real
> generalization remain open. See
> [C adaptation report](docs/QUARANTINED_C_ADAPTATION.md).


> **October 21, 2026 — public numeric-feature learning study:**
> A separate simulation generates fresh opaque action handles
> independent of two observable, hand-designed numeric properties;
> no private action-name hash is given to the learner. The model
> learns 5-neighbor outcome associations from 80 source episodes
> and reaches **360/360** zero-target-training goals in each
> of two generators with the *same constructed feature rule*.
> When the consequences reverse, it reaches **0/360** with
> **360 harmful outcomes**. This is NOT robust transfer
> to independently designed physics. Keep D3/D4 open.
> The next milestone is detecting/handling a changed relation
> *before* harmful intervention, with genuinely new generated
> rules, bounded uncertainty and safe abstention. See
> [experimental evidence](docs/OBSERVABLE_AFFORDANCE_TRANSFER.md).


## 2026-10-21 — Public-outcome reversed-consequence calibration (experimental)

- [x] Freeze `benchmarks/observable_reversal_calibration_protocol.json` before
  candidate implementation; preserve original reversed-rule catastrophic
  failure benchmark as-is.
- [x] Fit separate public outcome models from source normal and changed
  consequence-rule training observations; allow **12 disposable calibration
  interventions** to choose a model, with replay and abstention.
- [x] Report **all six previously inspected seeds**, wrong-calibration,
  fixed-model, random, abstention and privileged oracle controls. The
  calibrated policy scored **360/360** on each of normal and reversed
  target tasks with zero tested-episode damage, but caused **56/144
  simulated calibration harms**. Wrong calibration failed and caused
  harm in **720/720** evaluation episodes.
- [ ] Reduce harmful exploratory interventions while maintaining selection
  accuracy on fresh, independently designed dynamics. Reject stale
  calibrations after unexpected reversals, and compare to safe abstention
  with honest work-completion accounting.
- [ ] D1 blind generalization and D3/D4 independent skill/memory milestones
  remain open. No automatic promotion, real-world actuation or
  AthenZ/Synveil integration. V2A before/overlapping V2B unchanged.

Study: [observable reversal calibration](docs/OBSERVABLE_REVERSAL_CALIBRATION.md).


## 2026-10-21 — Two-window rule-contradiction evidence (experimental)

- [x] Precommit the protocol and preserve the earlier fixed-12
  and first-four calibration studies without changing their results.
- [x] Fit two separate outcome models, compare first4/recent4
  public sensor evidence, and use strict agreement to abstain
  when predicted rule assignments contradict.
- [x] Publish both inspected seed cohorts including **false
  abstentions**: agreement8 succeeded stationary normal 360/360,
  reversed 300/360, switched 0/360 in each direction; recent8
  recovered 300/360 and 360/360 switched tasks with no test
  harm. First4 caused 720 damaging switched tests. Agreement8
  failed every switched task by abstention. Eight probes incurred
  58/192 damaging rehearsal actions versus first4's 32/96.
- [ ] **Open:** learn how to detect further changes without harmful
  experiments or stale assumptions, using a fresh independent
  generator with uncertainty-calibrated abstention and
  completed-task accounting. Do not tune already-inspected
  cohorts into a claim of blind generalization.
- [ ] D1/D3/D4 stay open, no policy auto-promotion or external
  actuation, V2A before and overlapping V2B, cross-project
  integration deferred. See
  [two-window report](docs/TWO_WINDOW_CONFIRMATION.md).


## 2026-10-21 — Absolute model adequacy under noise and third-rule novelty

- [x] Freeze an independent simulator protocol BEFORE implementation,
  adding a task-feasible third rule with no training and 10% neutralizing
  noise on familiar laws. Never reuse these inspected outcomes as blind.
- [x] Evaluate absolute best-model likelihood plus agreement of public
  four-observation windows, against relative-only, recent-only,
  always-abstain, wrong/frozen known models and privileged oracle.
- [x] Six inspected seeds: new gate **202/360 noisy normal,
  151/360 noisy reversed, 0/360 unknown**; relative-only **244/360,
  222/360, 0/360**. New gate rejected all six unknown contexts and
  avoided harmful unknown TEST actions, versus relative-only **192**
  harms, but falsely rejected **3/12 known noisy calibrations**.
  **56/144 offline probes caused damage** (16/48 in unknown context),
  so gate is NOT safe to use for active exploration.
- [ ] **Open:** passive/no-intervention observation and rigorous hazard
  and usefulness accounting, then a wholly new precommitted
  generator and fresh holdout. Abstention must count failed goals;
  calibration itself cannot be presumed harmless.
- [ ] Do not close D1/D3/D4, auto-promote, permit OS/network actions
  or integrate AthenZ/Synveil. Preserve V2A before/overlapping V2B.

See [absolute adequacy report](docs/ABSOLUTE_ADEQUACY.md).


## 2026-10-21 — Passive outcomes from an independent simulated actor

- [x] Freeze `benchmarks/passive_outcome_protocol.json` before
  implementation, including two new now-inspected seed groups,
  matched held-out third-rule tasks and full actor/learner harm
  attribution.
- [x] Implement strictly read-only action-outcome ingestion,
  recomputed public sensor transitions, replayed checkpoints,
  exact 240-event/24-event observational comparison, and
  guarded vs raw numeric outcome prediction.
- [x] Full six-seed results: **253/360** raw learner tasks
  completed, 10 harmful TEST actions after 240 random
  observations/seed; guarded policy **160/360 and 10 harms**,
  so conservatism lost tasks without reducing measured
  danger. From 24 subset observations guard was 22/360;
  biased old-policy actor guard was 0/360.
- [x] Credit simulated data collection correctly: independent
  random actor produced **302 harmful actions /1,440**, biased
  actor **450/1,440**, and the first-24 subset must not be
  double-counted. Learner issued **0** collection actions,
  but the collection process was NOT harmless.
- [ ] Before any broader claim, audit independent generator
  holdouts, observer selection bias, provenance, forged
  plausible evidence and task/harm uncertainty. No real human
  observer is connected and no owner authorization occurs.
- [ ] D1/D3/D4 stay open; main/default untouched, PR draft,
  no AthenZ/Synveil integration. V2A remains before and
  overlaps V2B. See
  [passive outcome report](docs/PASSIVE_OUTCOME_LEARNING.md).


## 2026-10-22 — Passive evidence representativeness and coherent forgery audit

- [x] Freeze passive quality protocol and two fresh three-seed cohorts
  before candidate implementation; separate true random and old-policy
  data from a **counterfeit re-labeling** of original random episodes.
- [x] Implement public-feature opportunity reference using 60
  no-action simulator frames per seed, a three-region
  covariate-coverage check, and fully coherent rehashed sensor
  fabrication in an adversarial BENCHMARK ONLY.
- [x] All six now-inspected seed groups: genuine random learner
  **269/360** successes and **4 test harms**, biased learner
  **13/360** and **66 harms**, forged learner **33/360** and
  **327 harms**. Coverage rejected biased datasets **6/6**
  but accepted forged datasets **6/6**.
- [x] Include the harm of *external collection*: random
  actor **328/1,440** harmful actions, biased actor
  **513/1,440**, total **841/2,880**. Falsified
  corpus is a reuse of random actions, not another actor.
- [ ] **Open:** independent authenticated outcome witnesses,
  compromised-source detection, missing data and non-collusion
  assumptions, fresh holdouts and calibrated risk. No
  action authority for a model trained on only unverified
  external observations, regardless of SHA/coverage result.
- [ ] D1/D3/D4 still open; experimental PR stays draft and
  main/default untouched. AthenZ/Synveil integration deferred.
  [Full report](docs/PASSIVE_QUALITY.md).


## 2026-10-22 — Paired external outcome witnesses and collusion failure

- [x] Precommit paired HMAC witness protocol and two new three-seed
  cohorts BEFORE implementation; existing passive quality and
  transfer benchmark histories remain unchanged.
- [x] Bind complete public before/action/after records to separate
  simulator-provided primary/witness fixture keys; quarantine on
  missing witnesses, MAC failures or event mismatch. Do not grant
  training action authority or automatic model promotion.
- [x] Six now-inspected seeds: honest pair **286/360** held-out
  goals with **4 test harms**; forged primary versus honest
  witness rejected all six corpora, **0/360** goals by refusal,
  no test harm. Missing/tampered witness also abstained.
- [x] **Critical failing control:** both colluding, validly signed
  forged streams PASS 6/6 while producing **22/360** goals and
  **338 harmful TEST actions**. Single unchecked forged data
  produces the same results. MAC authentication of fixture
  key possession does **not** prove sensor truth, consent
  or organizational independence.
- [x] Separate actual observation cost: one actor, 1,440
  simulated actions and **319 genuine harms**; counterfeit
  signed views reuse those events and are NOT additional
  source actions.
- [ ] Require independent outcome grounding, audited external
  source integrity, non-collusion assumptions and truly new
  environment families before considering consequential
  real-world decisions. Current demonstration has no
  trusted human identity or physical truth attestation.
- [ ] D1/D3/D4 remain open, PR draft/unmerged, default and
  main unchanged; no Synveil/AthenZ integration.
  [Evidence report](docs/PAIRED_WITNESS.md).


#### October 22, 2026 — Learning-first evidence update (no roadmap stage changes)

**D4/D6 partial research evidence, not milestone completion:** A new opt-in
numeric outcome retrieval experiment learned from sequential public simulator
observations, chose earlier memories without stage labels, and replayed
its checkpoint across A→B→A. Six inspected seeds reached 360/360 TEST
completions per stage; source data collection itself caused 664 harmful
simulated actions. Simple cumulative and recent-window baselines failed
at one or more reversals. This remains one engineered two-number task
family and cannot count as D3 genuine unseen-family transfer or prove
lifelong development. Preserve the D1–D10 sequence, V2A before/overlapping
V2B, draft-only validation, and separate AthenZ/Synveil project boundaries.
See [REGIME_RETRIEVAL.md](docs/REGIME_RETRIEVAL.md) for frozen protocol,
comparators, evaluation leakage checks and negative limitations.


#### October 22, 2026 — Early change recovery and archive consistency (opt-in only)

**Partial D4/D6 experimental advance; D3 still open.** Precommitted
prequential A→B→A simulator study demonstrated faster re-use of old learned
numeric outcomes, but exposed major B-48 failure of naïve fast retrieval
(**88/180** compared with **179/180** for a recent-eight simple learner).
A separately frozen six-seed study rejected internally contradictory
old memory blocks and improved B-48 from **96/180** to **173/180**
with 7 harmful TEST actions versus 84. Recent-32 still reached 180/180
there, and recent-8 beat the filtered approach decisively at B-8.
Collection was *not* harmless: **744 harmful / 2,208 independent simulated
training actions** in that second study. The source is synthetic and can
still lie consistently. Both studies use the same engineered feature
schema and original/reversed world rules and therefore DO NOT satisfy D3,
independent goals or lifelong learning. See
[FAST_REACQUISITION.md](docs/FAST_REACQUISITION.md). Preserve D1–D10
and V2A then overlapping V2B unchanged. No AthenZ/Synveil integration.


#### October 22, 2026 — Variable-schema adaptation experiment

D1/D3 research extension: the current fixed-two-value outcome learner
gained an **opt-in variable-feature** version that stores multiple learned
experience schemas in one persistent replayable memory. A frozen first
protocol evaluates rule changes and genuinely different feature vocabularies
across quarry/coolant/relay simulation families, with separate held-out
TEST episodes, target-feedback budgets, matched baselines, source-actor
harm accounting and return visits to earlier skills. This is *not* D3
completion: features and common outcome counters are engineer-supplied;
the new schema can be recognized from its feature-key set; supervised
target outcomes are required; task generators were not independently
administered. Leave D1-D10 and V2A then partially overlapping V2B intact,
and keep AthenZ/Synveil integration deferred. See
[VARIABLE_AFFORDANCE.md](docs/VARIABLE_AFFORDANCE.md).


#### October 22, 2026 — Cross-schema learning results (verified, NOT D3 completion)

Frozen [variable schema protocol](benchmarks/variable_affordance_protocol.json)
evaluated three engineered transition families and independent
read-only tests. 45 focused tests and both 3-seed cohorts passed.
One opt-in persistent learner improved unfamiliar relay
**69/240 → 233/240** successes after 16 external first-action
outcomes, **240/240** after 48, while retaining full performance
(**240/240 each**) on older quarry/coolant test families after 160
relay outcomes. However the **target-only baseline matched relay
completions exactly** and zero-relay competence trailed random. The
engineered key-set partition preserved old tasks but did not learn
shared semantics. Independent simulation data acquisition generated
**1,054 harmful actions / 3,120** TRAIN first actions.
Do not claim safe causal exploration or successful zero-shot transfer.
Evidence supports partial D1/D4/D6 architecture research, not D3
generalization completion. Preserve D1–D10 and V2A/V2B order.
[Full results](docs/VARIABLE_AFFORDANCE.md).


#### October 22, 2026 — Learned relation reuse and harmful transfer recovery

**Partial D3/D4/D6 research, NOT D3 gate completion**. An optional
replayable `RelationOutcomeMemory` trained on numeric public
first-action outcomes transfers a developer-engineered max-minus-min
relation to entirely new feature key sets and dimensionalities.
A precommitted six-seed controlled study yielded **240/240 zero-target-
feedback successes each** on lattice/prism, versus target-only
37/240 and 22/240. These worlds deliberately share one mathematical
rule, a major transfer shortcut. A negative-rule control produced
**0/240 successes, 240 harmful TEST actions** and no recovery after
64 target samples — explicit catastrophic negative transfer.

A separately frozen six-seed study of opt-in `GatedRelationMemory`
compares the inherited model with a target-specific candidate on a
four-event held-out feedback tail. Counterphase recovery reached
173/240 after 8, 224/240 after 16, **240/240 after 24** observed
target outcomes; all compatible and source-revisit tasks stayed
240/240. Critical remaining failures: 240/240 harm before 8 target
observations; at 8 target samples a target-only model was stronger
(221/240 versus gated 173/240); exact feature-key signatures provide
engineered novelty information; internally consistent source forgery
remains unresolved. Two independent actor cohorts caused **868** and
**816** harmful TRAIN actions out of **2,592 each**, never learner
initiated. Both dedicated focused CI runs passed, with full
Linux/Windows exact HEAD gate checked separately. Preserve other
negative findings, all existing D1–D10 phases, V2A then partly
overlapping V2B, and defer AthenZ/Synveil integration. See
[RELATION_TRANSFER.md](docs/RELATION_TRANSFER.md).


#### October 22, 2026 — Identical feature-schema A→B→A reversal (optional research)

A precommitted study tested **unchanged public feature names** and
action-frame structure across a hidden outcome rule reversal and
return, avoiding the earlier engineered feature-signature novelty
shortcut. An opt-in evidence-ranked old-vs-recent model completed
**170/180** TEST tasks after 16 observations of reversed B
versus **0/180** for frozen A/cumulative baselines, reached
**180/180** after 48, and re-selected A after four return
observations with **180/180** success. Important negatives:
before each reversal the adaptive agent took **180 harmful
TEST actions out of 180**; at B8 it scored **0/180**
compared with a simple recent-eight policy's **167/180**.
At B64 it regressed to 178/180 vs recent-32's 180/180.
The actor collecting independent TRAIN observations caused **701
harmful actions of 2,112**, separately counted from TEST harm.
No phase labels or hidden mechanics were supplied to the learner,
but the band rule, archival boundaries, feature statistic, scoring
tail and confidence threshold were manually designed. Both
precommitted cohorts and 36 focused regressions passed. This is
**partial D4/D6 research**, not proof of safe learning or D3
completion. Retain D1–D10 and V2A then overlapping V2B unchanged;
do not integrate AthenZ/Synveil or promote controller.
[Complete outcomes](docs/SAME_SCHEMA_SWITCH.md).


#### October 22, 2026 — Fast same-schema surprise-triggered adaptation

Partial **D4/D6 research**, not D3 completion. New optional
`FastShockMemory` monitors how poorly the existing 192-event
archive predicts the last 4/8 public outcomes, using a manually
specified likelihood threshold to switch to a fitted recent-eight
model. Two frozen three-seed cohorts and 35 focused/historical tests
passed. In the reversed B regime after just eight external feedback
observations it solved **180/180** held-out tasks versus **26/180**
for the earlier disjoint-evidence selector; it also reacquired the
returned-A rule at **180/180 after four** new observations.
Crucial negatives: B performance was **identical to recent-eight**
at every tested checkpoint; performance at B32 **136/180** versus
prior selector **180/180**; 180 harmful TEST actions before new
evidence at either switch, and **751 harmful simulated TRAIN actions
out of 2,112** committed by an independent actor. Source range
representation, archive boundary, and surprise test are engineered.
The recent model trains on the triggering observations, unlike the
previous strictly disjoint predictive gate. No guarantee of
noise-robust selection, source truth, safe exploration, semantic
generalization or autonomous learning goals. No default promotion,
merge, or integrations with AthenZ/Synveil; D1–D10 and V2A/V2B
roadmap ordering unchanged. [All evidence](docs/FAST_SHOCK.md).


#### October 22, 2026 — Adaptive recent-memory horizon study

**Partial D4/D6 experimental research, D3 incomplete.** Optional
`AdaptiveHorizonMemory` selects archived knowledge, recent-eight,
or recent-32 public-outcome models using an engineered count of
surprising events under the frozen archive, without phase labels or
new sensor keys. A precommitted six-seed A→reversed B→return A
simulation completed with **34 regression tests and both focused
cohorts passing**. B8: **170/180 successes** (matches fast/recent8);
B24: **165/180** (fast 121/180); B32 and B48: **180/180**
(fast 128/180 and 119/180). Return-A4 recovered 180/180.

**Critical falsification:** B64 **150/180**, 30 harmful TEST
actions, because one seed incorrectly reverted to the archived
A model; simple recent32 achieved 180/180. At return-A0 and A2
there were **150 harmful TEST actions** each. Independent
first-action data collection caused **732 harmful TRAIN actions
out of 2,112**. Early hazard, non-disjoint selection training,
short/long threshold engineering, source spoofing and noisy
real-world domain changes remain unsolved. Full Linux/Windows
validation of final commit is separate. This optional learner is
NOT promoted, PR remains draft and unmerged; keep D1–D10
sequence, V2A before partially overlapping V2B and no integration
with AthenZ or Synveil. [Research details](docs/ADAPTIVE_HORIZON.md).


#### October 22, 2026 — Repeated A→B→A→B with noisy reported evidence

An opt-in `MultiSwitchContrastMemory` study was precommitted
before implementation and run across two fresh three-seed cohorts
on the unchanged-public-schema A→B→A→B simulator with
10%-sampled progress/damage **report corruption**. A model
must observe explicit predictive evidence for source A before
reselecting archive, rather than merely not seeing archive
surprise. [Focused CI PASS, 34 tests](https://github.com/magicmantheace/Developmental-AI/actions/runs/39892309615).
B1 at 8/32/64 observations: **86/116/118 successes out of
120** (prior adaptive **66/76/79**). B2 at 32/64: **109/116**
(vs prior **72/78**). The memory remains replayable, old
evidence retained and phase labels hidden.

**Critical negative:** B1-48 **82/120** versus recent32
**120/120**, and returned-A4 **60/120**, returned-A8 **80/120**
versus previous adaptive **120/120** at both. The preregistered
returned-A8 >=100/120 objective **failed**. At B2 onset
the new model caused **120 harmful simulated TEST actions
in 120 attempts**. The independent random actor needed
**2,496 training interventions** with **876 actual harmful
results**; 186 observed outcome labels were deliberately
flipped and only those reports were supplied to the learner.
The noisy labels, numerical relation, dynamics, predictive
thresholds, horizons and comparative controls are still
engineered. This is partial D4/D6 research, **not D3
generalization completion**, safe autonomous exploration or
source authenticity. No default controller promotion,
GitHub PR merge, cross-project work or alteration to D1–D10
and V2A/V2B. [Complete study](docs/MULTI_SWITCH.md).


#### October 23, 2026 — Stochastic prequential model weighting

**Experimental partial D4/D6 only; D3 independent new-physics
generalization remains open.** A precommitted six-seed A→B→A→B
simulator adds *actual probabilistic outcomes*, 1/8 flipped
nonneutral physical effects, and an independent 1/20-sampled
error rate in externally collected nonneutral public reports.
New optional `PrequentialEnsembleMemory` weighs archived,
recent-eight and recent-32 public-outcome predictions using
eight genuine prediction-before-update evaluations per model,
thus removing the candidate-in-sample evidence-selection
shortcut of earlier variants, although the windows, source
archive, priors, action utilities and numeric span features
are still designer-specified.

[Focused run passed, 34 tests and both cohorts](https://github.com/magicmantheace/Developmental-AI/actions/runs/39972387822).
B1-32 **61/96** successful simulated TEST episodes versus
old contrastive **31/96**, B2-32 **58/96 vs 27/96**, B2-64
**62/96 vs 28/96**, and return A24 **71/96 vs 58/96**.
**Major negatives:** preregistered B1-8 **10/96**, B2-8
**15/96** and return-A8 **65/96** all **missed acceptance
targets**. Simpler recent8 achieved B1-8 **47/96** and B2-8
**57/96**. Even B2-64 the new ensemble incurred **34 harmful
TEST actions/96**. The independent acquisition actor caused
**911 actual harmful TRAIN actions among 2,496 observations**;
85 TRAIN reports were deliberately false, learner-sourced TRAIN
actions zero. No robust safe exploration, source truth,
independent physics generalization or self-originating
cognition proven. Remain unmerged/unpromoted, preserve D1-D10
and V2A-before/overlapping-V2B ordering, no AthenZ/Synveil
integration. [Study](docs/STOCHASTIC_PREQUENTIAL.md).


#### October 23, 2026 — Prequential-regret hard source/recency selection

A new optional `RegretSwitchMemory` compares **prediction-before-update**
likelihoods for an immutable 192-event learned archive, recent8
and recent32, and makes a *hard* selection when public outcomes
contradict the archive. This is a developer-specified indicator,
not autonomous causal regime discovery. The synthetic physics,
numeric span statistic, recency sizes and cutoffs remain authored.
[Focused CI and both frozen seed cohorts passed](https://github.com/magicmantheace/Developmental-AI/actions/runs/39991366213),
33 regression tests. New TRUE stochastic same-schema A→B→A→B:
B1-8 **48/96** and B2-8 **33/96** (earlier ensemble **9/96**
at both), but naive recent8 **59/96** and **41/96**
respectively. Four precommitted thresholds were missed:
**B2-8 33/96 vs 35 required; return-A8 49/96 vs 50;
B1-32 45/96 and B2-32 34/96 vs 50**. Late A-source
false reselection caused **56 harmful TEST actions out of 96
at both B1-64/B2-64**; recent32 substantially outperformed
at B2-64 (67 vs 40 task successes). The independent
simulator TRAIN actor executed **2,496** unique interventions
with **881 truly harmful outcomes**, plus **98** deliberately
incorrect public reports; learner-issued TRAIN actions zero.

**Research implication:** faster adaptation currently costs
stability and can cause harmful false reversions; not a safe
or generally capable continual learner. Preserve partial
D4/D6 experimental status and keep D3 independent-physics
generalization open. No default controller promotion, PR
merge, AthenZ/Synveil integration or D1–D10/V2A/V2B
roadmap modifications. [Full evidence](docs/REGRET_SWITCH.md).


#### October 23, 2026 — Distinct arithmetic causal-family hypothesis selection

**Partial D3-related research only; D3 independent discovery
remains unmet.** An opt-in `FeatureHypothesisMemory` compares
a frozen source-span learner with three recent predictors
(span, asymmetric checksum, asymmetric ordered), selecting
by eight held-out prediction-before-update log-likelihoods.
The two target rules are *different* from the historical
source span relation, rather than merely its inverse,
with exactly the same public feature names. All three
representations are still manually supplied in the model's
candidate library.

[**Frozen GitHub Actions CI PASS: 34 tests and two three-seed cohorts**](https://github.com/magicmantheace/Developmental-AI/actions/runs/39993563381).
Checksum8/16/32 **80/120, 120/120, 120/120**
TEST successes, ordered8/16/32 **49/120, 106/120,
120/120**, returned source after eight observations
**120/120**. All three precommitted success thresholds
were achieved. However first-encounter negative transfer
was **110 harmful TEST actions/120** in checksum and
**108/120** in ordered. The independent random actor
performed **2,880 unique training interventions**,
with **945 genuinely harmful outcomes**. No learner
TRAIN actions were initiated. The action generator
guarantees an unrealistically favorable fixed mix of
productive and harmful choices, and the true target
feature formulas are preauthored in the learner. This
does not demonstrate emergent causal feature invention,
robustness to unknown laws, trustworthy feedback, safe
first-contact behavior, or independent general cognition.

Next D3 gates: genuinely **unrepresented** causal rule,
newly composed representations not in candidate library,
frozen seeds, decoy hypotheses and harm/abstention controls.
Preserve draft/unmerged PR, default policy, D1–D10,
V2A-before-overlapping-V2B and AthenZ/Synveil separation.
[Full study](docs/CROSS_RULE_HYPOTHESES.md).


#### October 23, 2026 — Bounded compositional feature hypothesis research

**Partial D3 research, not D3 completion.** New optional
`ComposedFeatureMemory` composes a fixed 48-program family
from multiplication, addition, coefficients and modulo,
then selects by 12 prequential public outcome scores.
The authored target nonlinear product and square laws are
not prewritten as finished named hypotheses, though both
are reachable within the **designer-provided grammar**.
Six preregistered seeds (two cohorts), 24 regressions
and all three registered outcome gates passed in
[focused CI](https://github.com/magicmantheace/Developmental-AI/actions/runs/39997552852).
Both new nonlinear targets reached **96/96 successes after
32 observations**, while previous fixed-library models
reached only **39/96 (product)** and **31/96 (square)**.
The original source rule was reacquired **96/96 after 16**
but only **40/96 after 8**, slower than the preceding
fixed-hypothesis learner (96/96 at source return8).

**Important safety limits:** at new-rule zero feedback
the learner suffered **83/96 product and 84/96 square
harmful TEST actions**. Independent source actor caused
**1,116 harmful simulated TRAIN actions across 3,360
unique observations**; learner action-acquisition zero.
Fixed grammar cannot discover operators outside its
enumeration, TEST actions are artificially stratified
to include abundant productive choices, and noise,
forged feedback, complex temporal rules and safe
exploration remain unsolved. Do not promote or merge
experimental code, alter D1–D10/V2A/V2B order, or
integrate with AthenZ or Synveil.
[Full evidence](docs/COMPOSED_FEATURE.md).


#### October 23, 2026 — Conditional grammar expansion with absent-XOR control

**Partial D3 evidence, NOT D3 completion.** The optional
`GatedCompositionMemory` adds a manually specified comparison
operator and learns distinct preexisting quadratic program
representations for two public feature partitions, using
prequential selection and retained source feedback. Frozen
six-seed conditional A→conditional→A→XOR simulator study
[focused CI PASSED, 24 tests](https://github.com/magicmantheace/Developmental-AI/actions/runs/40004315180).
Conditional64 **96/96 TEST successes**, versus global-composed
**36/96**, with all six seeds selecting correct two-arm programs.
Old source rule was reacquired **96/96 after16**.

**Important negatives:** after source-return8 only **19/96**
tasks succeeded, versus the earlier fixed-library selector's
**96/96**; no-feedback conditional first contact caused
**88 harmful TEST actions out of 96**. XOR was not supplied
as a grammar operation and learner failed to identify a
suitable model: XOR128 **39/96 successes, 57 harmful actions**,
versus benchmark-private correct-XOR predictor **96/96**.
The external actor collected **3,360 unique first-action
TRAIN examples, 1,117 harmful simulated interventions**;
learner-initiated TRAIN actions zero. Model does NOT learn
unknown operator types, calibrated ignorance, trustworthy
source evidence or safe exploration; favorable candidate
allocation and deterministic physics are manually authored.
Next D3 gate must test explicit representation-adequacy
detection, harmful-action risk and failed-by-abstention
costs on fresh preregistered seeds. No default promotion,
PR merge, external actuation, roadmap D1–D10/V2A/V2B
reordering or AthenZ/Synveil integration.
[Full report](docs/GATED_COMPOSITION.md).


#### October 23, 2026 — Out-of-grammar predictive adequacy and explicit abstention

**Experimental risk/coverage capability, NOT safe autonomous
exploration or D3 completion.** New optional
`ValidatedAbstainingMemory` freezes a feature program on
public observations excluding 16 validation outcomes,
scores predictive log-likelihood versus a feature-blind null
on those held-out events with per-event preceding-only fits,
and declines actions if adequacy or a predicted damage/
progress risk threshold fails. Candidate representation,
null and all thresholds are manually specified.
[**Frozen focused CI passed — 24 regressions and two
three-seed cohorts**](https://github.com/magicmantheace/Developmental-AI/actions/runs/40043938342).
On missing-operator XOR at feedback96: **0 task successes,
0 harmful TEST actions, 96 failed-by-abstention tasks**.
On known conditional at96: **96 successes, zero harm or
abstention**; archived source return32: **96 successes**.
All preregistered numeric gates passed.

**Negative evidence:** XOR first contact still caused
**67 damaging TEST actions/96**, XOR64 caused **six harms**
from false model acceptance. Solvable conditional48:
**14/96 successes**, 78 abstentions vs previous gated
always-act **94/96 successes**; source return8 **0
successes, 82 abstentions and 14 harms** despite frozen
source 96/96. Independent external actor collected
**3,360 unique TRAIN actions with 1,084 actually harmful
outcomes**, learner-sourced TRAIN actions zero. No learned
XOR operator, confidence calibration, passive evidence
request protocol, reliable change detection, or verified
real-world source honesty. Next preregistered research
should evaluate the entire risk/coverage tradeoff and
independently sourced passive observations while abstaining.
No default controller promotion, PR merge, AthenZ/Synveil
integration or D1–D10/V2A/V2B roadmap reorder.
[Complete report](docs/VALIDATED_ABSTENTION.md).


#### October 23, 2026 — Independently sourced, costed witness recovery

Optional `WitnessRecoveryMemory` only requests additional
simulator-origin public evidence when the earlier **disjoint
adequacy gate rejects its model**, with at most four batches
of eight observations. It cannot itself operate the independent
data-acquisition actor. [Frozen CI passed, 23 tests and
two three-seed cohorts](https://github.com/magicmantheace/Developmental-AI/actions/runs/40058451712).
Conditional after32 examples: **52/96 task success with
witnesses vs 4/96 without**; old-source return after8
**61/96 vs 6/96**. Both registered productivity
goals passed. But the **XOR harm gate FAILED**:
at XOR96, supplemental evidence led to **38 harmful
TEST actions vs 22 without**, above the intended cap
of 20. The actor furnishing witness outcomes made
**1,112 additional interventions, 329 harmful** on
top of baseline **3,360 unique TRAIN interventions,
1,105 harmful**. Total **4,472 actor interventions
and 1,434 harmful outcomes** across distinct frozen
checkpoint scenarios, learner-owned TRAIN actions zero.
The witness actor is **not passive, harmless or free**.
No missing XOR discovery, safe first-contact behavior,
calibration, verified source honesty or independent
real-world cognition. Prioritize net acquisition +
TEST harm on fresh seeds and lawful non-intervention
observational channels, not uncalibrated evidence
accumulation. Remain experimental/unmerged and
preserve D1–D10, V2A/V2B, AthenZ/Synveil separation.
[Complete study](docs/INDEPENDENT_WITNESS.md).


#### October 24, 2026 — Shared-versus-new public outcome evidence cost audit

**Experimental measurement, no claim of safer general
learning.** The new `shared_evidence_economics_benchmark`
preregisters fresh six-seed cohorts and compares
unchanged selective learning with no new data, fresh
independent first-action witness interventions, and a
shared bank of 32 previously acquired actor reports
per stage/seed that can be consumed across checkpoint
scenarios. All source actor harms are counted once and
all abstentions counted as failed tasks.
[Focused frozen study PASSED, 23 regressions and
both cohorts](https://github.com/magicmantheace/Developmental-AI/actions/runs/40112953845).
Shared bank conditional32 **58/96 successful TEST**
tasks versus no-extra **9/96**, returned source8
**40/96 vs 8/96**. Shared bank sourced **576 actor
actions, 210 harmful** vs fresh independent evidence
**1,232 actions, 415 harmful**. All preregistered
acceptance checks passed.

**Critical limits:** the authored pooled study
loss was **3,710 no extra evidence, 6,821 shared,
9,534 fresh** because extra evidence also caused
damaging action attempts. Shared TEST harms **353**
vs no-extra **279**, and at XOR96 shared **26/96
harmful TEST actions** vs no-extra **9/96**.
Always-abstain was **1,632** weighted loss with
**zero tasks completed** (not a good general
learning outcome). Original random source actor
collected **3,360 actions with 1,123 actual harmful**
outcomes, common to all arms. Shared bank records
are already acquired but NOT passively or freely
created. Checkpoints repeat held-out TEST episode
IDs, thus portfolio totals are NOT independent
long-term trial statistics. The model still
cannot represent XOR, verify source authenticity
or guarantee harmless independent exploration.
Prioritize a genuinely non-intervention observation
channel, noisy evidence, lifetime event order and
risk/coverage analysis with fresh frozen cohorts.
Preserve D1–D10, V2A/V2B, draft PR #2, default
controller and AthenZ/Synveil independence.
[Complete study](docs/SHARED_EVIDENCE_ECONOMICS.md).
