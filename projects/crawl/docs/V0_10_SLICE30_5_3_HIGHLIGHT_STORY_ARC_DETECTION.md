# Underreach v0.10 — Slice 30.5.3

## Highlight & Story-Arc Detection

### Status

Implementation slice after accepted 30.5.2.

Accepted source baseline:

`8cae3df5633a088262d1f0c96ac93a98e3a0678e`

Canonical phase roadmap:

`docs/V0_10_PHASE30_5_HEADLESS_CHRONICLE_PROMOTION_PLAN.md`

---

# 1. Purpose

30.5.3 converts immutable 30.5.1 `MediaEnvelope` records into deterministic presentation analysis:

- highlight scores,
- output tiers,
- structured `MediaHighlight` records for qualifying envelopes,
- persistent thematic `MediaStoryArc` records.

The detector does not generate prose, images, audio, video, dialogue, commentary, or prompts.

The detector does not invoke an LLM.

The detector does not invoke a provider selected by 30.5.2.

The detector does not enqueue downstream generation jobs.

The detector cannot mutate canonical simulation truth.

---

# 2. Authority Boundary

Frozen contract:

```text
Canonical deterministic simulation
        |
        v
Canonical Ledger
        |
        v
30.5.1 MediaEnvelope (read-only export)
        |
        v
30.5.2 separate media SQLite database
        |
        v
30.5.3 deterministic Python scoring + story-arc records
```

30.5.3 is non-authoritative presentation analysis.

It receives a `MediaEnvelope` and a 30.5.2 `MediaPersistence` store. It does not receive a simulation mutation service.

Required invariants:

- `authoritative = false`
- `canonical_owner = deterministic_simulation`
- `presentation_can_mutate_simulation = false`
- `llm_decision_used = false`
- `unreal_dependency = false`
- `provider_invocation_used = false`

A detector failure can only affect media analysis.

---

# 3. Score Contract

The canonical roadmap defines seven bounded dimensions totaling 100 points.

30.5.3 freezes these maxima:

| Component | Maximum |
| --- | ---: |
| Danger / severity | 20 |
| Rarity | 15 |
| Social stakes | 20 |
| Character significance | 15 |
| Outcome reversal | 10 |
| Continuity / arc value | 15 |
| Visual potential | 5 |
| **Total** | **100** |

All scoring is deterministic Python over immutable envelope data.

No stochastic score component exists.

No model-generated score exists.

---

# 4. Danger / Severity — 0 to 20

Primary evidence:

- canonical semantic `danger_level`,
- death,
- near-death,
- boss/elite events,
- critical injury,
- combat/attack/hazard signals.

The strongest supported signal wins the component.

No danger may be inferred from generated prose or visual output.

---

# 5. Rarity — 0 to 15

Primary evidence:

- canonical item rarity in envelope item context,
- important-item marker,
- Relic events,
- epic/rare event signals,
- boss/cache significance.

Generated visual rarity does not count.

---

# 6. Social Stakes — 0 to 20

Primary bounded signals include:

- betrayal / alliance betrayal,
- sacrifice,
- rescue,
- abandonment,
- revenge,
- deception,
- loot theft,
- promise violation,
- aid refusal,
- party/alliance/leadership changes,
- protection/resource sharing.

This component reads structured source event types only.

---

# 7. Character Significance — 0 to 15

30.5.3 does not yet have a public follower/audience system.

Therefore significance uses only presentation-safe canonical history available in the envelope:

- current Stratum depth,
- progression level,
- encounters survived,
- kills.

Future audience-following signals may be added only by a later accepted slice and must not retroactively change persisted 30.5.3 identities under the same policy digest.

---

# 8. Outcome Reversal — 0 to 10

Bounded reversal signals include:

- comeback,
- near-death survival,
- escape,
- survival,
- rescue,
- retreat,
- explicit reversal/unexpected-defeat outcomes.

Structured canonical outcome facts may contribute.

---

# 9. Continuity / Arc Value — 0 to 15

Continuity is derived from immutable canonical social context inside the envelope, not from generated narrative.

Highest-value case:

- the source event reinforces an already-existing event-linked social-memory thread.

Additional supported continuity includes:

- the source event itself is linked into social memory,
- an established reinforced social memory exists for involved Delvers,
- party/alliance context gives a current social event continuity,
- repeated related source event types occur inside one envelope.

30.5.3 does not rescore an old highlight merely because later media records exist.

---

# 10. Visual Potential — 0 to 5

Visual potential is only a scheduling/display signal.

Evidence includes:

- canonical encounter context,
- a known Sector with participating Delvers,
- inherently visual structured event categories such as combat, boss, death, rescue, betrayal, Relic, or sacrifice.

It does not call an image or video model.

---

# 11. Output Tier Contract

Default roadmap thresholds are frozen exactly:

| Total score | Tier |
| ---: | --- |
| 0–49 | `archive_only` |
| 50–69 | `chronicle` |
| 70–79 | `motion_story` |
| 80–89 | `enhanced_stills` |
| 90–94 | `local_animation` |
| 95–100 | `cinematic` |

Video eligibility remains a later scheduling decision.

A tier does not mean the corresponding media has been generated.

---

# 12. Persisted Highlight Rule

An envelope below the configured Chronicle threshold receives a deterministic `HighlightEvaluation` but is not persisted as a `MediaHighlight`.

An envelope at or above the threshold receives a stable highlight identity:

```text
highlight_id = hash(envelope_id + policy_digest)
```

Persisted highlight fields include:

- highlight identity,
- envelope identity,
- Crawl ID,
- canonical source event IDs,
- participating Delver IDs,
- exact component score,
- total score,
- output tier,
- deterministic reason codes,
- associated story-arc IDs,
- policy digest,
- authority/dependency flags,
- payload digest.

Repeating the same analysis under the same policy must produce the same payload.

---

# 13. Story-Arc Contract

30.5.3 recognizes bounded thematic arc classes:

- `survival`
- `combat`
- `social_conflict`
- `party_alliance`
- `loot_progression`
- `stratum_progression`

Arc identity is stable by:

```text
crawl_id + arc_type + normalized subject IDs
```

Each arc accumulates only canonical/media provenance:

- envelope IDs,
- source canonical event IDs,
- first/last canonical tick seen in contributing envelopes,
- occurrence count,
- active/closed status.

Provenance collections are de-duplicated and normalized so repeated processing does not duplicate the arc.

---

# 14. Terminal Arc Rules

Initial bounded closure rules:

### Survival

Closed by terminal death/elimination/retreat events.

`NEAR_DEATH` does not close the survival arc.

### Party / Alliance

Closed by:

- party disband,
- alliance dissolution,
- alliance betrayal.

Other arc classes remain historical active thematic threads in this slice.

---

# 15. Media Database Boundary

30.5.3 adds two media-owned SQLite tables:

```text
media_highlights
media_story_arcs
```

They are deliberately declared under a 30.5.3-only SQLAlchemy metadata base rather than 30.5.2 `MediaBase`.

This preserves the accepted 30.5.2 table contract when only `MediaPersistence.initialize()` is used.

30.5.3 tables are created only by `HighlightStoryArcService.initialize()`.

Canonical Crawl tables are never opened or mutated by this service.

---

# 16. Idempotency / Restart Rules

Required behavior:

- repeated envelope analysis does not duplicate a highlight,
- repeated envelope analysis does not duplicate arc provenance,
- reopening the same `media.sqlite3` reproduces the same highlight/arc snapshot,
- replaying an already-analyzed envelope after restart is side-effect free,
- input ordering to batch evaluation is normalized deterministically,
- story-arc merges use set-union/min/max semantics so persisted arc content is stable.

---

# 17. What Is Explicitly Not in 30.5.3

Deferred:

- Chronicle prose,
- public Delver profile generation,
- LLM narrative writing,
- claim manifests,
- fact-verifier models,
- image generation,
- presentation identity generation,
- voice/TTS,
- FFmpeg production,
- local video generation,
- cloud/paid provider execution,
- publishing.

30.5.3 also does not enqueue generation jobs. It only persists deterministic analysis records.

---

# 18. Validation Gate

The local acceptance gate must prove:

1. accepted 30A.1 through 30C.6 regressions pass,
2. accepted 30.5.1 tests pass,
3. accepted 30.5.2 tests pass,
4. focused 30.5.3 tests pass,
5. exact roadmap tier boundaries remain unchanged,
6. a low-signal envelope remains archive-only and creates no persisted highlight,
7. a high-signal envelope qualifies using deterministic canonical evidence,
8. reinforced event-linked social memory contributes continuity,
9. story arcs accumulate canonical provenance without duplication,
10. terminal death closes the relevant survival arc,
11. media SQLite reopen preserves exact highlight/arc state,
12. repeated analysis after reopen is side-effect free,
13. canonical state/fingerprint/history/Ledger rows remain unchanged during media analysis,
14. no LLM/provider/Unreal dependency is introduced,
15. full repository pytest passes.

The terminal acceptance string is:

```text
[30.5.3] PASS
```

---

# 19. Next Canonical Slice

After local acceptance, the next frozen Phase 30.5 slice is:

**30.5.4 — Delver Chronicle & Profile System**

It will consume accepted MediaEnvelopes, highlights, and story arcs to build durable structured profile/Chronicle state before later narrative generation is introduced.
