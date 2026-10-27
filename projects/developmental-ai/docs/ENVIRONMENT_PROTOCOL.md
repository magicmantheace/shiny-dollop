# D1/D2 foundation: cross-family environment contract (experimental)

The strategic focus has shifted from optimizing narrow ring-world detectors to **test protocol integrity**, **a common environment/service interface**, and **measuring task-family transfer**. This is working code, but D1, D2 and D3 are **not closed**.

## Three independent simulator families

`developmental_ai.environment_api.EnvironmentSession(family, seed, split, index, variant)` supports:

- `grid`: target-direction and blocked directions every step (`transfer` arena).
- `occluded`: one-time target-position difference and blocked directions (`occluded_navigation` arena).
- `delayed`: cue, distractors, and a final four-button choice (`delayed_choice` arena); long delays are held out from short-delay association training.

All share the same versioned `frame()` observation contract, action mask, `step(action, expected_tick=...)`, deterministic step outcome, checkpoint, and `restore(checkpoint)`. Only **public** simulator observations cross this boundary. No hidden current position, actual physics, rule-table labels, hidden association, wall map, unrestricted action, personal data, external tool or privileged OS action is exported. Rewards and action outcome events are environment feedback, not system permissions.

Every session has a stable namespaced episode ID, monotonic tick, bounded action budget, and `simulation-only` source. Checkpoints store recorded observations/actions and a digest chain. **Restore reruns the deterministic simulator and rejects mismatched observations/outcomes, even if a consumer recalculates the hash.** SHA-256 is an accidental-integrity check, *not* an authenticated signature or evidence of human approval.

## Headless external adapter (D2 proof of interface, not production RPC)

```sh
python -m developmental_ai.environment_service
```

The process accepts one JSON object per line and writes one JSON response per line. A session is wholly in process memory. `start` and `restore` accept one session; `observe` reads it; `step` requires the current tick; `checkpoint` returns a replay-verifiable record; `close` ends it. Unknown operations, stale ticks, unknown fields and invalid actions fail closed. The bridge has **no filesystem paths, subprocess commands, sockets or system tool handlers**. It works in vanilla Python without AthenZ or Synveil.

Example input (one line):

```json
{"schema":"developmental-ai.environment-service/v1","request_id":"example1","op":"start","config":{"family":"grid","seed":17,"split":"train","index":0}}
```

Use `{"schema":"developmental-ai.environment-service/v1","request_id":"example2","op":"observe"}` to read the frame, then `step` with an allowed action and the frame's `tick`. This experimental stdin/stdout transport has **no caller authentication**, resource isolation from hostile local processes, remote service authentication, or AthenZ identity/consent integration. Those are required for completing D2.

## D1 test manifest and honest baseline

[`benchmarks/frozen_environment_protocol.json`](../benchmarks/frozen_environment_protocol.json) defines:

- A documented development cohort of seeds 2749, 6607, and 9901, test episodes starting at 60000, 16 per seed/family.
- A **reserved, not yet executed** cohort 32081 and 48779. These seeds are published and not secret, so a later independent evaluator is still necessary for genuine blindness. `--profile reserved` is disabled unless an explicit `--unlock-reserved` is supplied.
- Disjoint `train` split: 96 *short-delay* reward-labelled interactions per seed for the delayed task. No test episode enters training.
- Locked comparison metrics: terminal success, step cost, reward, valid actions.
- Baselines: seeded random legal actions versus a **family-specific** navigation heuristic or reward-learned cue association with an engineered memory gate. The heuristics do *not* show that a single policy transfers skills among families.

```sh
python -m benchmarks.environment_contract_benchmark --out benchmarks/environment_contract_results.json
python -m unittest tests.test_environment_api tests.test_environment_contract_benchmark -v
python -m benchmarks.transfer_benchmark
```

The runner saves the SHA-256 of the exact protocol bytes in every result. This initial development cohort has been inspected during implementation; do not relabel it independent/blind. The reserved cohort should remain untouched until a separate candidate freeze and an independently run evaluation. No hyperparameter tuning on test episodes and no changing the locked protocol to improve a score.

## What remains before the roadmap gates can close

- **D1:** independent, genuinely blind evaluation and robustness across previously unseen task families, beyond merely reproducible splits.
- **D2:** a stable long-running authenticated service, version negotiation/migrations, error contract, resource limits, and supervised connection to AthenZ. This JSONL adapter is an executable *prototype*.
- **D3:** one learner capable of acquiring, retaining and transferring skills across the **three different families**, beating family-specific/reactive baselines on frozen independent tests. This benchmark establishes infrastructure only, not that learning capability.

Existing navigation models and their published results remain unchanged. V2A affective cognition and V2B virtual home remain in their agreed later sequence.
