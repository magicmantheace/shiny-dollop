# Crawl v0.10 — Slice 30.5.2 Media DB, Durable Queue & Provider Router

## Status

**Canonical slice:** 30.5.2 — Media DB, Durable Queue & Provider Router

**Accepted baseline:** 30.5.1 — Canonical Media Event Export at `3bd0bef780a446a6e3d068c7d08fa34631463226`.

**Parent roadmap:** `docs/V0_10_PHASE30_5_HEADLESS_CHRONICLE_PROMOTION_PLAN.md`

This document freezes the implementation contract for 30.5.2.

---

## Purpose

Establish the durable, non-authoritative infrastructure that every later Phase 30.5 media worker will use.

30.5.2 adds:

- a physically separate media-owned SQLite database,
- idempotent MediaEnvelope indexing,
- deterministic durable media jobs,
- explicit job dependencies,
- durable attempts and retry state,
- machine/process restart recovery,
- artifact/provenance record foundations,
- provider execution/resource/cost record foundations,
- capability-driven provider descriptions,
- deterministic provider routing,
- local-first routing policy,
- explicit paid-provider opt-in gates.

30.5.2 does **not** generate prose, images, video, narration, captions, music, or final edits.

---

# 1. Authority Boundary

The deterministic simulation remains the sole canonical authority.

The media database is presentation-owned state only.

30.5.2 may persist:

- MediaEnvelope copies/indexes,
- media jobs,
- dependencies,
- attempts,
- retry/hold/completion status,
- provider selections,
- media artifact metadata,
- provider execution/resource/cost metadata.

It may never write to:

- canonical health,
- movement,
- inventory/item ownership,
- injuries,
- combat outcomes,
- progression,
- parties,
- alliances,
- relationships,
- social memories,
- canonical Ledger rows,
- canonical history IDs,
- canonical simulation fingerprints.

The media database must not share authoritative Crawl tables.

---

# 2. Separate Media Database

Initial accepted backend:

```text
SQLite
```

Recommended production path:

```text
media.sqlite3
```

The schema is media-owned and uses dedicated table names:

- `media_envelopes`
- `media_jobs`
- `media_job_dependencies`
- `media_job_attempts`
- `media_artifacts`
- `media_provider_executions`

30.5.2 must not create or modify `crawls` or `crawl_events` in the media database.

The canonical simulation database and media database are separate persistence boundaries even if they happen to live on the same machine.

---

# 3. Envelope Index / Immutable Outbox Continuation

30.5.1 MediaEnvelope values may be copied into the media database.

Registration is idempotent:

- identical `envelope_id` + `idempotency_key` + digest is accepted without duplication,
- a conflicting payload for an existing identity is a hard failure,
- registering an envelope must not write a canonical Ledger event,
- canonical state is not changed by registration.

The media database therefore becomes the durable downstream continuation of the 30.5.1 immutable export boundary.

---

# 4. Durable Media Jobs

A job has deterministic identity derived from its normalized job specification.

The job specification includes:

- Phase/protocol identity,
- job type,
- source envelope ID when applicable,
- normalized payload,
- dependency IDs,
- provider request when applicable,
- priority,
- attempt limit.

Equivalent enqueue requests produce the same job identity rather than duplicate work.

Initial statuses:

```text
queued
running
retry
held
completed
failed
```

These are presentation workflow states only.

---

# 5. Dependencies

Jobs may depend on earlier media jobs.

A dependent job cannot be claimed until every dependency is `completed`.

Dependencies use deterministic IDs and survive database reopen/restart.

A high-priority dependent job must not bypass an incomplete lower-priority prerequisite.

---

# 6. Attempts, Retry & Restart Recovery

Each claim creates one deterministic attempt identity:

```text
media_attempt(<job_id>, <attempt_number>)
```

Attempt state is durable.

A process or machine may die while a job is `running`.

On restart, `recover_interrupted_jobs()` must:

1. find durable jobs left `running`,
2. mark the active attempt `interrupted`,
3. move the job to `retry` when attempts remain,
4. move the job to `failed` when no attempts remain,
5. preserve the same job ID,
6. never duplicate the job,
7. let the next claim use the next attempt number.

The crawl itself is unaffected by media recovery.

---

# 7. Artifact / Provider Execution Foundations

30.5.2 provides durable record shapes for later slices.

Artifacts retain:

- job provenance,
- artifact kind,
- URI/path reference,
- digest,
- metadata,
- review status,
- publication status.

Provider execution records retain:

- job ID,
- attempt ID,
- provider ID,
- execution status,
- estimated/actual monetary cost,
- estimated/actual GPU time,
- provider-specific presentation metadata.

These records do not make generated output canonical.

30.5.2 acceptance does not require an actual AI provider invocation.

---

# 8. Provider Model

Providers are capability descriptions, not hard-coded model dependencies.

Initial kinds:

```text
narrative
verification
image
video
voice
```

A provider descriptor may report:

- provider ID,
- local or remote,
- paid or free,
- availability,
- health,
- capability flags,
- deterministic-seed support,
- reference-conditioning support,
- image-to-video support,
- maximum dimensions/duration,
- estimated VRAM,
- estimated runtime,
- estimated monetary cost,
- quality rank/profile.

Later providers may replace current local implementations without changing the MediaEnvelope or canonical simulation.

---

# 9. Capability-Driven Routing

Jobs request capabilities, not model names.

A request may constrain:

- provider kind,
- required capability flags,
- local-only requirement,
- deterministic seed support,
- reference conditioning,
- image-to-video,
- minimum dimensions/duration,
- maximum VRAM,
- maximum estimated cost,
- minimum quality rank.

Eligibility is evaluated before ranking.

Among eligible providers, routing is deterministic and prefers:

1. local over remote,
2. free over paid,
3. higher quality,
4. lower monetary cost,
5. lower estimated runtime,
6. stable provider ID tie-break.

Routing only selects provider metadata in 30.5.2. It does not call the provider.

---

# 10. Local-First / Paid Provider Safety

Default policy:

```text
local_only = true
cloud_allowed = false
allow_paid = false
require_explicit_paid_policy = true
daily_paid_budget = 0
```

A paid provider is eligible only if all required gates pass:

1. the global policy allows paid providers,
2. cloud/remote execution is allowed when the provider is remote,
3. the individual job request allows paid providers,
4. explicit paid authorization is present when required,
5. the configured daily paid budget is positive,
6. projected daily spend remains within budget,
7. any per-job estimated-cost limit is satisfied.

A configured credential/API key is **not** an authorization signal.

If no provider is eligible, the job is held/retried/degraded by later policy. It is never silently converted into a billable request.

---

# 11. Resource Constraints

Provider routing understands resource estimates now so later workers do not need architectural changes.

At minimum 30.5.2 supports filtering by estimated VRAM.

This is important for the current local operating target where large GPU models cannot all remain resident simultaneously.

Actual serialization/GPU scheduling is expanded in later media slices, especially 30.5.10.

---

# 12. Deterministic Snapshot

The media persistence layer exposes a semantic snapshot containing:

- envelope index,
- jobs,
- dependencies through each job,
- attempts,
- artifacts,
- provider execution records,
- authority/local-first flags,
- deterministic digest.

Wall-clock timestamps and SQLite implementation details are excluded from the semantic digest.

Reopening an unchanged SQLite database must reconstruct an equal semantic snapshot.

---

# 13. Focused Acceptance Requirements

Focused tests must prove:

- media and canonical table sets are disjoint,
- envelope registration is idempotent,
- media writes do not change canonical state or Ledger rows,
- equivalent job enqueue does not duplicate work,
- dependencies block claims until prerequisites complete,
- retryable failures create bounded retry behavior,
- an interrupted job survives SQLite reopen and resumes as the next attempt,
- local/free providers are preferred when eligible,
- capability/VRAM constraints are enforced before ranking,
- paid providers are blocked by default,
- paid providers require every explicit opt-in/budget gate,
- no-provider routing holds rather than silently spending,
- artifact/provider execution records are durable and idempotent,
- provider routing itself invokes no external provider.

---

# 14. Proof Requirements

The deterministic proof must:

1. create an accepted autonomous Descent,
2. create a real canonical Ledger event,
3. export a real 30.5.1 MediaEnvelope,
4. register the envelope twice and persist only one record,
5. enqueue one job twice and persist only one job identity,
6. create a dependent job,
7. select an eligible local provider,
8. claim the primary job,
9. simulate a process restart by reopening file-backed SQLite,
10. recover the interrupted attempt,
11. reclaim the same job as attempt 2,
12. complete it,
13. prove the dependency then becomes runnable,
14. prove a current-machine VRAM constraint selects the eligible lower-VRAM provider,
15. prove paid routing is blocked under default policy,
16. prove paid routing becomes selectable only under explicit paid policy,
17. prove over-budget paid routing is rejected,
18. reopen SQLite again and prove the semantic snapshot is equal,
19. prove canonical state/fingerprint/history/Ledger rows are unchanged by all media activity,
20. run twice and produce the same proof digest.

---

# 15. Forbidden Scope

30.5.2 must not add:

- Ollama calls,
- OpenAI/Anthropic/other paid API calls,
- ComfyUI calls,
- image generation,
- video generation,
- TTS generation,
- FFmpeg production,
- Chronicle prose generation,
- fact-verification model calls,
- highlight scoring,
- Unreal calls,
- canonical simulation mutations.

Provider metadata may name conceptual local/remote backends in tests/proofs, but no network/model execution occurs.

---

# 16. Acceptance Gate

30.5.2 is accepted only when local validation ends with:

```text
[30.5.2] PASS
```

The proof must show a file-backed media queue survives restart without duplicate work and the paid-provider router remains zero-spend by default.

Nothing in 30.5.2 may change canonical simulation truth.

---

# Next Slice

After acceptance, the next frozen slice is:

**30.5.3 — Highlight & Story-Arc Detection**

It will consume accepted MediaEnvelope/media persistence infrastructure and deterministically rank canonical events/arcs without using an LLM to decide what happened or what is important enough to become a highlight.
