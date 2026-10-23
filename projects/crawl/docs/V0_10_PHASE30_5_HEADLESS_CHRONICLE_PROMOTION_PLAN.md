# Crawl v0.10 — Phase 30.5 Headless Chronicle & Promotion System

## Status

**Canonical phase:** `30.5` — Headless Chronicle & Promotion System

**Accepted baseline:** Phase 30C complete at `729570fb6b8d517a3976cbc660b55059157f258e`.

**Planned slice count:** 12

**Next canonical phase after 30.5:** Phase 31 — Dialogue / Commentary.

This document freezes Phase 30.5 before implementation begins. It intentionally inserts a local-first presentation-data and media-automation phase between completed Phase 30C social intelligence and Phase 31 expressive dialogue/commentary work.

This plan supersedes the earlier Phase 30C planning note that Phase 31 would begin immediately after 30C.6.

The phase identifier must be stored and compared as the string `"30.5"` (or an equivalent symbolic enum), never as a floating-point number.

---

# 1. Purpose

Phase 30.5 turns canonical headless simulation history into ongoing Delver chronicles, deterministic promotional highlights, and finished review-ready social-media assets without requiring Unreal, cloud AI, paid APIs, or human intervention during production.

The phase consumes canonical Crawl/Underreach history only through a read-only export membrane.

It produces two primary public-facing products:

1. continuously updated Delver profile chronicles,
2. promotional media generated from high-value canonical events and multi-event arcs.

Candidate source events include:

- fights and encounter resolutions,
- deaths and near-death escapes,
- rescues, protection, and sacrifice,
- party formation and dissolution,
- leadership changes,
- alliance formation and hostile alliance breaks,
- betrayal, abandonment, theft, deception exposure, and revenge state,
- important cache, Relic, or equipment acquisition,
- Stratum progression,
- long-running relationship reversals and payoffs.

The entire MVP must run on the local machine with no required recurring AI cost. Paid APIs are optional providers only.

---

# 2. Non-Negotiable Authority Rules

The canonical architecture remains:

```text
Deterministic Crawl Simulation
        |
        v
Authoritative Crawl State + Canonical Ledger
        |
        | read-only export
        v
Phase 30.5 Presentation-Safe Media Envelope
        |
        +---------------------+
        |                     |
        v                     v
Chronicle / Profile      Highlight / Media Pipeline
        |                     |
        +----------+----------+
                   |
                   v
            Review / Publishing
```

The following rules are frozen:

- The deterministic simulation remains the only authority for gameplay truth.
- Phase 30.5 may read canonical state and canonical Ledger history but may never mutate either.
- No generated prose, image, audio, video, edit, score, or provider result may write back to health, inventory, relationships, parties, alliances, combat, movement, progression, memory, survival state, or the Ledger.
- Unreal is not required and must not be invoked by Phase 30.5 acceptance paths.
- Cloud AI is not required.
- Paid AI is not required.
- Every published or review-ready story/highlight retains provenance to canonical event IDs and export digests.
- Media worker failure may delay media production only; it must never block or corrupt the headless crawl.
- A no-video motion-story fallback must always be capable of producing a valid promotional asset.
- Provider implementations are replaceable presentation backends, never canonical dependencies.

---

# 3. Local-First Operating Contract

The default configuration is local-only:

```text
MODE = local_only
UNREAL = disabled
CLOUD_AI = disabled
PAID_PROVIDERS = disabled

chronicle.writer = local_ollama
chronicle.verifier = local_small_model
highlight.detector = deterministic
image.provider = local_comfyui
video.provider = local_lightweight_i2v
video.fallback = motion_story
voice.provider = local_kokoro
editor.provider = ffmpeg
publishing.mode = review_required
```

A missing local provider must not silently trigger a paid API.

Paid escalation requires explicit configuration such as:

```text
providers.allow_paid = false
providers.daily_paid_budget = 0
providers.require_explicit_paid_policy = true
```

If `providers.allow_paid` is false, a failed local job is queued, retried, degraded, or held. It is never converted into a billable request.

---

# 4. Canonical Media Export / Immutable Outbox

The media layer must not read arbitrary simulation internals directly.

A read-only exporter produces an immutable, normalized **MediaEnvelope** from canonical events and bounded canonical context.

The exporter acts like an append-only export journal/outbox even before the durable media database is introduced in 30.5.2.

Every envelope must include at minimum:

- `schema`,
- `exporter_version`,
- `phase = "30.5"`,
- deterministic `envelope_id`,
- deterministic `idempotency_key`,
- Crawl/Descent ID,
- seed,
- canonical tick,
- Stratum/Floor,
- Sector/location where available,
- ordered source canonical event IDs,
- source event type(s),
- participating Delver IDs,
- presentation-safe participant state relevant to the event,
- presentation-safe equipment/ownership context relevant to the event,
- relevant directed relationship values when available,
- relevant event-linked social-memory references when available,
- party/alliance context when available,
- structured encounter/combat context when available,
- deterministic semantic metadata already attached to the Ledger event,
- normalized allowed-fact records,
- canonical Crawl fingerprint captured at export time,
- canonical history prefix digest,
- envelope payload digest,
- `presentation_can_mutate_simulation = false`.

If Character DNA or richer canonical identity data does not yet exist in the accepted simulation model, the envelope must not invent it. It should export only available stable identity fields and leave future presentation-identity references optional.

Example:

```json
{
  "schema": "underreach.media-envelope.v1",
  "exporter_version": "30.5.1",
  "phase": "30.5",
  "envelope_id": "media_envelope_...",
  "idempotency_key": "...",
  "crawl_id": "descent_...",
  "source_event_ids": ["crawl_event_..."],
  "delver_ids": ["descender_047", "descender_103"],
  "stratum": 4,
  "sector": "sector_017",
  "allowed_facts": [],
  "social_context": {},
  "combat_context": {},
  "visual_identity_refs": [],
  "canonical_fingerprint": "...",
  "history_prefix_digest": "...",
  "presentation_can_mutate_simulation": false
}
```

## Export invariants

- Exporting the same canonical event prefix twice produces byte-equivalent semantic envelopes/digests.
- Export does not add a Ledger event.
- Export does not change `history_event_ids`.
- Export does not change the canonical Crawl fingerprint.
- Export does not change any canonical metadata counter.
- Missing requested canonical events are hard failures, not silently omitted facts.
- Envelope source-event order follows canonical Ledger order, never arbitrary database ordering.

---

# 5. Media Database, Durable Queue & Provider Router Foundation

Durable media infrastructure is intentionally moved forward to **30.5.2** because nearly every later subsystem depends on restart-safe jobs, idempotency, retries, provider selection, and resource scheduling.

Use a separate media-owned SQLite database such as `media.sqlite3`.

It must not share authoritative tables with the simulation database.

Core media records should include:

- exported envelope index,
- media jobs,
- job dependencies,
- attempts and retry reason codes,
- generated artifacts,
- publication/review status,
- provenance,
- provider execution records,
- idempotency keys,
- resource estimates/actuals,
- optional monetary cost records,
- GPU-time records.

Restarting the process must not duplicate canonical exports, Chronicle chapters, highlights, or media jobs.

## MediaProviderRouter

Introduce a capability-driven provider abstraction:

```text
MediaProviderRouter
    NarrativeProvider
    VerificationProvider
    ImageProvider
    VideoProvider
    VoiceProvider
```

Providers report structured capabilities rather than forcing the pipeline to know model names:

- provider ID,
- local/remote,
- paid/free,
- availability/health,
- capability flags,
- deterministic-seed support,
- reference-image support,
- image-to-video support,
- maximum resolution/duration,
- estimated VRAM requirement,
- estimated runtime,
- estimated monetary cost,
- quality profile.

Jobs request capabilities/policy constraints such as:

```text
local_required = true
paid_allowed = false
reference_conditioning = true
max_vram_mb <= configured_limit
```

Future hardware or API providers should be configuration changes, not architecture changes.

---

# 6. Deterministic Highlight & Story-Arc Detection

Highlight discovery is deterministic Python, not an LLM decision.

The detector consumes MediaEnvelopes and creates structured `MediaHighlight` records only when configured criteria are met.

Initial scoring dimensions:

| Signal | Suggested range | Purpose |
| --- | ---: | --- |
| Danger / severity | 0-20 | death, critical injury, wipe risk |
| Rarity | 0-15 | rare item/event/outcome |
| Social stakes | 0-20 | betrayal, rescue, alliance break, sacrifice |
| Character significance | 0-15 | long-running or audience-followed Delver |
| Outcome reversal | 0-10 | comeback, escape, unexpected defeat |
| Continuity / arc value | 0-15 | payoff to earlier memories/rivalry |
| Visual potential | 0-5 | clear presentable scene |

Suggested policy:

| Score | Automatic output |
| ---: | --- |
| 0-49 | archive only |
| 50-69 | Chronicle/profile material |
| 70-79 | motion-story candidate |
| 80-89 | enhanced still sequence + narration |
| 90-94 | locally animated shot if budget permits |
| 95-100 | highest-priority local cinematic treatment |

Video eligibility is a scheduling decision, not a requirement for the highlight to exist.

---

# 7. Delver Chronicle & Profile System

Every Delver may receive a public profile that becomes a living biography derived from canonical history.

Profile fields may include only supported presentation-safe information:

```text
DELVER PROFILE

Stable ID / public name when available
Current status: ACTIVE | RETREATED | DEAD
Current Stratum
Current party / alliance
Known allies and rivals derived from canonical social state
Current notable equipment
Presentation identity reference

THE CHRONICLE
Chapter 1 - ...
Chapter 2 - ...
...
```

A terminal chapter closes the active Chronicle on death or retreat.

Chapter triggers include:

- major fight or boss/elite encounter,
- death or near-death survival,
- rescue/protection/sacrifice,
- party/alliance/leadership change,
- theft/betrayal/abandonment/deception exposure/revenge,
- important loot/Relic/cache acquisition,
- Stratum completion,
- major relationship reversal or reinforced social arc,
- configurable quiet-life recap after enough meaningful canonical history accumulates.

The writer may improve pacing, imagery, transitions, and emotional tone, but it cannot invent new factual claims.

---

# 8. Narrative Claim Manifest & Fact Verification

The writer must produce two outputs:

1. creative draft prose,
2. structured claim manifest.

A claim record should contain fields such as:

```text
claim_id
claim_type
subject
predicate
target_or_value
supporting_allowed_fact_ids
confidence
```

The writer is never trusted to self-certify canonical truth.

Verification combines:

- deterministic claim/fact matching,
- bounded structural rules,
- an optional smaller local model for ambiguous claim extraction/classification.

The smaller model may help interpret prose but cannot override deterministic contradictions.

Reject claims such as:

- wrong killer/attacker,
- wrong Stratum/Sector,
- invented item ownership,
- invented injury/death,
- invented party/alliance membership,
- invented relationship history,
- invented social memory,
- invented outcome.

Clearly stylistic language may pass only when it adds no new canonical factual assertion.

Verification failure affects the media job only.

---

# 9. Presentation Identity Versioning

Generated character art is presentation state, not canonical character state.

Use an explicit versioned presentation identity contract such as:

```text
presentation_identity.v1
```

Example layout:

```text
media/
  delvers/
    <delver_id>/
      identity.json
      portrait.png
      face-reference.png
      three-quarter.png
      full-body-front.png
      full-body-side.png
      combat-reference.png
      current-equipment-reference.png
```

Rules:

- Generate only when a Delver becomes media-relevant.
- Preserve deterministic presentation seed and generation metadata.
- Reuse identity references across later scenes.
- Regenerate equipment reference only after meaningful visible canonical equipment change.
- Generated facial/body details do not become canonical unless separately represented in canonical identity data.
- Switching image models may create a new presentation-identity version without changing the Delver's canonical identity.

---

# 10. Headless Local Image & Video Production

All visual generation runs through headless workers.

Local ComfyUI or an equivalent engine may be exposed through a local service/API without opening a GUI.

## Guaranteed production tiers

### Tier 1 — Motion Story

This is the guaranteed promotional path.

Use generated/reused stills plus FFmpeg for:

- slow push/pan/crop,
- transitions,
- captions,
- narration,
- local music/SFX,
- particles/overlays where available,
- final encode.

Tier 1 requires no video diffusion.

### Tier 2 — Partially Animated Highlight

Generate a complete still storyboard and animate only the highest-value 1-3 shots through a local image-to-video provider.

### Tier 3 — Full Local Cinematic

Reserve for the highest-value events and GPU budget.

Prefer multiple short independent shots rather than one long generation.

Target 3-5 second shots. A 25-35 second social clip may contain roughly 6-9 independent shots.

Video failure falls back to Tier 1 or Tier 2; it never prevents a review-ready promotional artifact.

---

# 11. Narration, Captions & Audio

Narration scripts consume the same verified media package as the Chronicle/highlight system.

Default local voice provider: Kokoro or equivalent.

Caption text derives directly from the verified narration script; speech recognition is not required.

Maintain a royalty-safe/local library for music and sound effects.

FFmpeg owns:

- loudness normalization,
- ducking,
- fades,
- mixing,
- caption burn-in/sidecar generation,
- final encode.

Support both narrated and caption-first/silent variants where useful.

---

# 12. Resource Scheduler & GPU Budget

Canonical simulation remains CPU-first and independent from media throughput.

Large GPU workloads are serialized.

Typical batch behavior:

```text
Chronicle batch
  -> load local writer
  -> process bounded jobs
  -> unload

Image batch
  -> load image model
  -> process bounded jobs
  -> unload

Video batch
  -> load video model
  -> process highest-priority eligible jobs
  -> unload
```

The scheduler must not assume writer, image, and video models can coexist in VRAM.

Example local limits:

```text
media.video.enabled = true
media.video.max_gpu_hours_per_day = 8
media.video.minimum_highlight_score = 90
media.video.max_retries_per_shot = 2
media.video.fallback = motion_story
```

Paid-provider budget and GPU-hour budget are separate controls.

---

# 13. Reliability & Graceful Degradation

Every media worker uses durable queues and may fail independently.

| Failure | Required behavior |
| --- | --- |
| Writer unavailable | queue Chronicle job; simulation continues |
| Verification fails | revise/regenerate media draft only |
| Image provider fails | retry or reuse identity/reference art |
| Video provider fails | retry or fall back to motion story |
| TTS fails | caption-only draft or retry |
| FFmpeg fails | retain intermediates and retry assembly |
| Machine restarts | resume durable queue without duplicate exports/jobs |
| Paid provider unavailable | local/queued/degraded path according to explicit policy |

No media failure may stop canonical simulation advancement.

---

# 14. Media Website / Underreach Blog

The public site is generated from media-owned data, not directly from the live simulation database.

Prefer a static site initially.

Initial content:

- Delver directory,
- active/retreated/deceased filters,
- individual Delver profiles,
- Chronicle chapters,
- current presentation-safe status,
- current Stratum,
- party/alliance,
- notable equipment,
- allies/rivals,
- visual identity,
- approved highlight/reel gallery,
- terminal profile state for death/retreat.

Canonical provenance remains retained internally but need not be exposed publicly.

---

# 15. Storage & Retention

Suggested retention:

| Artifact | Retention |
| --- | --- |
| Canonical MediaEnvelopes/provenance | permanent or compacted with durable provenance |
| Published Chronicle text | permanent |
| Presentation identity pack | permanent while profile exists |
| Failed raw generations | 3 days |
| Unused raw generations | 14 days |
| Accepted intermediate shots | 30 days or until publication |
| Final promotional MP4 | permanent |
| Temporary FFmpeg files | delete after successful encode |

The media database stores provenance and metadata even when disposable raw assets are cleaned up.

---

# 16. Current-PC Operating Model

The first complete implementation targets the current local machine.

The intended operating assumptions are:

- headless Underreach: always-on CPU-first,
- media SQLite: lightweight/durable,
- Chronicle writing: local batch model,
- verification: smaller local model plus deterministic checks,
- still images: one GPU worker at a time,
- local I2V/T2V: possible but slow and restricted to high-value jobs,
- TTS: local and preferably CPU-capable when practical,
- FFmpeg: local,
- Unreal: unused,
- paid APIs: disabled by default and optional only.

The 12 GB GPU is treated as a constrained shared media resource rather than assumed to hold all models simultaneously.

---

# 17. Provider Upgrade Path

Each AI/media subsystem sits behind a provider interface.

Examples:

```text
NarrativeProvider
  - local_ollama
  - optional_paid_api

VerificationProvider
  - deterministic_only
  - local_small_model
  - optional_paid_api

ImageProvider
  - local_comfyui
  - optional_paid_api

VideoProvider
  - local_lightweight_i2v
  - future_local_large_model
  - optional_paid_api

VoiceProvider
  - local_kokoro
  - optional_paid_api
```

Specific vendor/provider names are configuration concerns, not canonical architecture.

Hardware upgrades should change provider quality profiles and throughput, not media-envelope or simulation code.

---

# 18. Frozen Phase 30.5 Slice Order

## 30.5.1 — Canonical Media Event Export

**Purpose:** establish the read-only simulation-to-media membrane.

**Primary acceptance target:** canonical Ledger events export into stable deterministic MediaEnvelopes with provenance, allowed facts, and canonical digests while the canonical Crawl fingerprint and Ledger remain unchanged.

No media database, AI generation, image generation, video generation, or paid provider belongs in this slice.

---

## 30.5.2 — Media DB, Durable Queue & Provider Router

**Purpose:** establish restart-safe media-owned persistence and capability-based provider selection before downstream workers exist.

**Primary acceptance target:** durable idempotent jobs survive process restart; duplicate export/job creation is prevented; local-only and paid-disabled policy is enforced; providers are selected by capability/policy rather than hard-coded model names.

---

## 30.5.3 — Highlight & Story-Arc Detection

**Purpose:** deterministically rank real canonical events and connect related event windows/arcs.

**Primary acceptance target:** multiple canonical event histories produce reproducible scored highlights and arc context without an LLM deciding what happened or what is important.

---

## 30.5.4 — Delver Chronicle & Profile System

**Purpose:** create living media-owned Delver profiles and Chronicle chapter jobs from real event history.

**Primary acceptance target:** a Delver receives generated local draft chapters and a terminal death/retreat chapter sourced from MediaEnvelopes without simulation mutation.

---

## 30.5.5 — Narrative Claim Manifest & Fact Verification

**Purpose:** prevent generated prose from presenting unsupported canonical facts.

**Primary acceptance target:** structured claims are deterministically matched to allowed facts; unsupported claims are rejected/revised without affecting the simulation or losing provenance.

---

## 30.5.6 — Presentation Identity System

**Purpose:** create stable reusable versioned visual identities without making generated appearance canonical.

**Primary acceptance target:** deterministic `presentation_identity.v1` packs can be generated/reused/versioned independently of canonical identity truth.

---

## 30.5.7 — Headless Local Image Production

**Purpose:** generate scene/identity stills through a local headless provider.

**Primary acceptance target:** Python jobs generate/reuse images through the provider router with bounded resource use, provenance, restart safety, and no GUI/Unreal dependency.

---

## 30.5.8 — Narration, Captions & Audio

**Purpose:** create local narration, caption, music/SFX, and audio metadata from verified story packages.

**Primary acceptance target:** a verified package produces local narration/captions or a valid caption-only degradation path.

---

## 30.5.9 — Automated FFmpeg Motion-Story Production

**Purpose:** establish the guaranteed no-video-diffusion promotional path before adding optional animation.

**Primary acceptance target:** verified local stills + narration/captions assemble automatically into a valid vertical promotional MP4 with zero video-model dependency.

---

## 30.5.10 — Local Video Enhancement & GPU Scheduling

**Purpose:** add optional local I2V/T2V enhancement under capability, retry, GPU-hour, and fallback policies.

**Primary acceptance target:** eligible highlights can animate selected short shots locally; failure or exhausted GPU budget degrades automatically to the accepted motion-story path; paid APIs remain opt-in only.

---

## 30.5.11 — Media Website / Blog Generation

**Purpose:** regenerate public Delver/profile/Chronicle/highlight pages exclusively from media-owned data.

**Primary acceptance target:** static pages rebuild without touching or querying live canonical mutation paths.

---

## 30.5.12 — Unattended Promotion Soak

**Purpose:** close Phase 30.5 with an unattended local-first end-to-end run.

**Primary acceptance target:** one command runs a meaningful headless crawl/media session, produces Chronicle content and at least one review-ready vertical promotional asset, survives injected media-worker failure/restart, and requires no Unreal, cloud AI, paid API, or human intervention to reach review state.

---

# 19. Final Phase Acceptance Gate

Phase 30.5 is complete only when one unattended local-first run can create both Chronicle content and a promotional media artifact derived from canonical events.

```text
START ONE COMMAND
      |
      v
Headless Underreach launches/runs
      |
      v
20+ Delvers operate autonomously
      |
      v
Canonical combat/social/progression events occur
      |
      v
Read-only MediaEnvelope export
      |
      +-------------------------+
      |                         |
      v                         v
Chronicle pipeline        Highlight pipeline
      |                         |
verified chapter          deterministic selection
      |                         |
      |                   local visual package
      |                         |
      |                   local narration/captions
      |                         |
      +------------+------------+
                   |
                   v
        FFmpeg motion-story path
                   |
                   v
        finished vertical promo MP4
                   |
                   v
              REVIEW QUEUE
```

## Mandatory zeroes

- zero Unreal calls,
- zero required cloud API calls,
- zero required paid AI dependencies,
- zero generated-media mutation of canonical simulation truth,
- zero human intervention required for production to reach review state,
- zero automatic paid escalation when paid providers are disabled.

## Acceptance invariants

- Canonical fingerprints before/after media processing are identical except for legitimate simulation advancement performed by the simulation itself.
- Media export itself does not advance or mutate simulation state.
- Every Chronicle chapter and highlight package retains canonical event provenance.
- Checkpoint/restart does not duplicate exports, chapters, highlights, or media jobs.
- Failure of any media worker cannot stop or corrupt the crawl.
- Motion-story fallback can produce a promotional asset when local video generation is unavailable.
- GPU scheduler respects configured GPU-hour/retry limits.
- Paid-provider router respects explicit opt-in and monetary budget limits.
- The same media package can move between compliant local or paid providers without changing canonical simulation code.
- Generated presentation identities remain presentation-only.
- Phase 31 may consume verified presentation-safe context but remains downstream of canonical simulation truth.

---

# 20. Definition of Success

Phase 30.5 succeeds when Underreach can run headlessly for long periods and independently produce an ever-growing public history of its Delvers plus a review queue of promotional stories/videos derived from events that genuinely happened.

The public layer may be cinematic, emotional, and creative.

The canonical Ledger remains the source of truth.

After 30.5 acceptance, the next canonical phase is:

**Phase 31 — Dialogue / Commentary**

Phase 31 may express verified canonical history through dialogue, reactions, interviews, commentary, narration, or other generated presentation content, but it inherits the same no-writeback authority boundary.