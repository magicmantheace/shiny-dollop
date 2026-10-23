# Crawl v0.10 — Slice 30B.1 AI Brain Foundation

## Purpose

30B.1 begins Phase 30B without weakening the deterministic authority established by Phase 30A.

The accepted 30A.5 system can already complete a multi-Stratum Descent autonomously using a bounded deterministic policy. 30B.1 does **not** replace that execution loop. It introduces the contract that future richer brains will use to inspect authoritative state and propose structured intents.

The central rule is:

```text
Authoritative Descent state
        ↓
Epistemically bounded brain observation
        ↓
Brain provider
        ↓
Structured advisory intent
        ↓
[future deterministic validation/execution layer]
        ↓
Canonical simulation mutation + Ledger event
```

In 30B.1 the pipeline stops at **structured advisory intent**.

A brain cannot directly cause gameplay truth.

---

## Authority contract

### The deterministic simulation owns

- Descent status and tick,
- Descender position,
- health,
- canonical stamina,
- hydration and nutrition,
- item ownership,
- cache state,
- encounter state/outcomes,
- Stratum progression,
- elimination/death,
- the canonical Event Ledger.

### The brain may

- receive a bounded observation,
- reason from that observation,
- return one typed proposal,
- attach confidence and reason codes,
- optionally identify an observed/owned target allowed by the proposal schema.

### The brain may not

- mutate `Descent`,
- move a Descender,
- consume an item,
- open a cache,
- apply damage,
- decide combat outcomes,
- advance a Stratum,
- alter knowledge,
- append gameplay Ledger events,
- use Unreal or presentation feedback as gameplay truth.

Proposal generation is deliberately **non-authoritative**.

---

## Observation protocol

Protocol:

`underreach.ai-brain-observation.v1`

An observation contains only information legitimately available to the selected active Descender at the current canonical tick.

Included state:

- Descent ID,
- Descender ID,
- canonical tick,
- current Stratum,
- current Sector and Sector kind,
- health,
- canonical gameplay stamina,
- hydration,
- nutrition,
- survival risk band,
- whether the Descender is currently at an exit,
- whether the Descender is currently at a safe area,
- currently known neighboring Sectors,
- currently known safe Sectors,
- currently known exits,
- canonical inventory item IDs,
- owned survival-supply item IDs,
- owned survival-supply kinds,
- current Stratum cache status,
- whether the cache Sector is actually known to that Descender,
- accepted 30A.5 step count for the current Stratum,
- deterministic observation digest.

The observation does **not** expose:

- every Sector on the Stratum,
- hidden routes the Descender has not discovered,
- unrevealed future information,
- future encounter results,
- omniscient target locations merely because the simulator internally knows them,
- Unreal state,
- camera state,
- presentation annotations.

This keeps the brain epistemically bounded to canonical character knowledge.

---

## Intent protocol

Protocol:

`underreach.ai-brain-intent.v1`

Every intent contains:

- provider ID,
- deterministic proposal ID,
- Descender ID,
- exact source observation digest,
- bounded action,
- optional known Sector target,
- optional owned survival item target,
- confidence,
- machine-readable reason codes.

### 30B.1 action vocabulary

The bounded proposal vocabulary is:

- `explore`
- `seek_cache`
- `seek_exit`
- `seek_safety`
- `recover`
- `consume_supply`
- `wait`

This is a proposal vocabulary, not an execution API.

A future slice must translate or reject these intents through deterministic simulation rules before canonical state can change.

---

## Intent gate

`validate_brain_intent()` verifies that a proposal is bound to the exact observation supplied to the provider.

It rejects, at minimum:

- an intent for another Descender,
- a stale/wrong observation digest,
- an unknown action,
- a Sector target outside the Descender's observed knowledge,
- consumption of an item the Descender does not canonically own,
- a recovery intent outside a canonical safe area,
- invalid target/action combinations.

This prevents a future model/provider from escaping its observation by simply naming arbitrary hidden IDs.

---

## Provider interface

`BrainProvider` is intentionally small:

```python
provider_id: str

def propose(observation: BrainObservation) -> BrainIntent:
    ...
```

The provider does not receive the mutable `Descent` object.

That allows future adapters for local models, remote models, learned policies, utility planners, or experimental agents while preserving one common validation boundary.

30B.1 ships a `DeterministicReferenceBrain` so the contract can be validated without internet access, model APIs, GPUs, or nondeterministic inference.

The reference provider is not intended to be the final intelligence system.

---

## Canonical-mutation guard

`AIBrainFoundationService.propose()` captures:

- the canonical Descent fingerprint,
- a digest of the full serialized canonical state,
- the canonical history-event sequence.

After provider execution, the service verifies those values are unchanged.

The focused test suite also includes a deliberately malicious provider with an out-of-band reference to the Descent. The proposal gate must detect the attempted mutation and reject the provider result.

This is defense in depth. Providers should only receive the immutable observation contract.

---

## Proposal bundles

`proposal_bundle()` can produce one proposal for every active current-Stratum Descender.

The bundle explicitly states:

```text
authoritative = false
advisory_only = true
simulation_execution_required = true
```

The bundle is not stored in `Descent.modifiers` and is not appended to the canonical gameplay Ledger in 30B.1.

This is deliberate.

Asking a brain what it *would like to do* must not change replay truth merely because the question was asked.

---

## Determinism

30B.1 requires deterministic behavior for the reference implementation.

For the same canonical state:

- observation JSON must be identical,
- observation digests must be identical,
- reference-provider intents must be identical,
- proposal IDs must be identical,
- proposal bundles must be identical.

After the canonical simulation advances, the bundle is expected to change when the observed authoritative state changes.

A checkpoint restored to the exact same authoritative state must reproduce the same proposal bundle.

---

## Acceptance proof

The acceptance proof creates an accepted 30A.5 Descent with:

- 8 Descenders,
- 3 Strata,
- the full accepted 30A.1–30A.5 canonical stack.

It then proves:

1. the first proposal bundle can be generated without mutating canonical state,
2. a fresh `AIBrainFoundationService` produces the exact same bundle,
3. canonical model JSON is unchanged,
4. canonical history IDs are unchanged,
5. canonical fingerprint is unchanged,
6. the accepted 30A.5 simulation advances one real autonomous step,
7. a new brain bundle responds to the changed authoritative state,
8. proposal generation again leaves canonical state unchanged,
9. the state is written through `AlphaCheckpointStore`,
10. the restored checkpoint produces the exact same post-step proposal bundle.

The proof itself is advisory/non-authoritative because no brain proposal is executed in this slice.

---

## Files

- `src/livingworld/underreach_ai_brain_foundation.py`
- `tests/test_underreach_30b1_ai_brain_foundation.py`
- `scripts/generate-underreach-ai-brain-foundation-proof.py`
- `scripts/run-underreach-ai-brain-foundation-validation.ps1`
- `docs/V0_10_SLICE30B1_AI_BRAIN_FOUNDATION.md`

No accepted 30A implementation file is modified by this slice.

No Unreal file is modified.

No GitHub Actions workflow is added or required.

---

## Local validation

Run:

```powershell
.\scripts\run-underreach-ai-brain-foundation-validation.ps1
```

The validator runs:

1. accepted 30A.1–30A.5 focused regressions,
2. focused 30B.1 authority/proposal tests,
3. the deterministic brain proof twice,
4. proof invariants and checkpoint equality checks,
5. the full repository regression suite.

Acceptance requires the explicit terminal line:

```text
[30B.1] PASS
```

---

## Scope boundary

30B.1 does **not** wire brain proposals into authoritative movement or gameplay execution.

That separation is essential. The first AI-brain slice establishes observation, intent, provider, validation, and authority contracts before richer reasoning can influence gameplay.

The canonical next slice should build on this proposal contract rather than allowing a model/provider to call simulation mutation methods directly.
