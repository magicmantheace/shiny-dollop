# Crawl v0.10 — Slice 30.5.10 Local Video Enhancement & GPU Scheduling

## Status

**Canonical slice:** `30.5.10 — Local Video Enhancement & GPU Scheduling`

**Accepted parent:** `30.5.9 — Automated FFmpeg Motion-Story Production`

**Parent SHA:** `b7beb3b432e586c0ad6fbb082645e85df346f705`

**Phase:** `"30.5"` as a string, never a float.

---

# 1. Purpose

30.5.10 adds optional local short-shot video enhancement after the guaranteed
30.5.9 motion-story path already produced a valid review-ready vertical MP4.

The frozen roadmap requires:

- local animation eligibility at highlight score 90+,
- highest local cinematic priority at score 95+,
- only a bounded number of short 3–5 second shots,
- capability-routed local I2V/T2V providers,
- serialized heavy GPU work,
- an 8 GPU-hour default daily/window budget,
- at most two retries per selected shot,
- automatic fallback to the accepted motion story,
- paid APIs disabled unless explicitly authorized.

The slice does **not** replace the deterministic highlight system and does not
allow a video model to decide what happened.

---

# 2. Authority Boundary

The canonical authority chain remains unchanged:

```text
Deterministic Crawl Simulation
        |
        v
Canonical State + Ledger
        |
        v
Read-only MediaEnvelope
        |
        v
Deterministic highlight / Chronicle / verified narrative
        |
        v
30.5.7 stills + 30.5.8 audio/captions
        |
        v
30.5.9 guaranteed motion-story MP4
        |
        +------------------------------+
        | optional presentation branch |
        v                              |
30.5.10 local short-shot enhancement   |
        |                              |
        +------------------------------+
                 fallback remains
```

30.5.10:

- never opens `CrawlPersistence`,
- never mutates canonical state,
- never writes a Ledger event,
- never changes combat/social/progression truth,
- never invokes Unreal,
- never makes generated video canonical,
- never requires cloud or a paid API.

Every enhancement spec and sidecar carries:

- source event IDs,
- source MediaEnvelope IDs when available,
- persisted deterministic highlight IDs and score,
- source 30.5.7 image artifact provenance,
- source 30.5.9 story/fallback provenance,
- selected provider identity,
- deterministic seed,
- GPU accounting,
- `canonical_authority = false`,
- `presentation_can_mutate_simulation = false`.

---

# 3. Guaranteed Fallback Rule

30.5.9 is complete **before** any 30.5.10 job is eligible.

The 30.5.9 MP4 is therefore not regenerated or overwritten by 30.5.10.

Every video enhancement spec contains:

```text
fallback_motion_story_ready = true
fallback_artifact_id
fallback_uri
fallback_digest
```

If optional video enhancement:

- has no eligible provider,
- exceeds VRAM policy,
- exceeds GPU budget,
- crashes,
- exhausts retry attempts,
- is interrupted by machine restart,

then the existing motion-story artifact remains the review-ready promotional
asset.

A failed optional enhancement can delay only that enhancement.

---

# 4. Eligibility Policy

30.5.10 consumes persisted deterministic `MediaHighlight` records from 30.5.3.
It does not rescore events with an LLM or model.

Default policy:

| Highlight score | Treatment |
| ---: | --- |
| 0–89 | motion-story fallback only |
| 90–94 | partial local animation; one selected short shot |
| 95–100 | cinematic priority; up to three selected short shots |

The source highlight score and tier remain unchanged.

30.5.10 selects eligible storyboard shots deterministically. Selection is
bounded and reproducible. It prefers longer eligible short shots and then stable
shot/artifact ordering.

Default eligible animation duration:

```text
minimum = 3 seconds
maximum = 5 seconds
```

A 30.5.9 storyboard shot shorter than the configured minimum is skipped rather
than extended beyond its source timeline.

---

# 5. Provider Contract

Providers are selected through the accepted 30.5.2 `MediaProviderRouter` using
`ProviderKind.VIDEO`.

30.5.10 acceptance uses I2V because every accepted promotional package already
has deterministic storyboard stills. Text-to-video is optional future provider
capability and is not required for acceptance.

Each shot requests:

```text
kind = video
headless_video
mp4_output
short_shot
deterministic_seed_required = true
image_to_video_required = true
local_required = true
paid_allowed = false
max_vram_mb = 12288
```

The executable interface is `HeadlessVideoProvider`.

A production provider such as local Wan/ComfyUI can implement the interface
without changing canonical simulation code, the media queue, highlight
selection, or GPU scheduler.

---

# 6. Acceptance I2V Backend

`DeterministicLocalI2VProvider` is a zero-model local acceptance backend.

It uses the already-required local FFmpeg installation to create a short real
MP4 from the accepted source PNG with deterministic motion.

It exists to prove:

- provider routing,
- file-backed video artifacts,
- MP4 validation,
- deterministic seeds,
- durable attempts,
- GPU reservations,
- fallback behavior,
- restart safety.

It is **not** presented as a production-quality generative video model.

The provider descriptor intentionally carries a synthetic constrained-GPU
estimate so the 30.5.10 scheduler is exercised in acceptance. A real I2V model
provider must publish its real VRAM/runtime estimates.

---

# 7. GPU Scheduling

GPU scheduling state lives in the separate media-owned SQLite database.

Tables introduced by 30.5.10:

```text
media_video_gpu_reservations
media_video_gpu_lock
```

No canonical table is added or modified.

## Default budget

```text
max_gpu_hours_per_window = 8
max_vram_mb = 12288
max_retries_per_shot = 2
```

The scheduling window is supplied explicitly to enqueue operations. In normal
operation the caller uses the local calendar day as the window key. Explicit
window keys make deterministic tests/replay possible without embedding wall
clock time into job identity.

## Reservation behavior

Before a routed video job can run:

1. the provider must satisfy capabilities/policy,
2. a conservative GPU reservation must fit the current scheduling window,
3. the job remains durable in `media_jobs`,
4. exactly one video job may own the GPU lock at a time.

Reservation capacity accounts for the initial attempt plus the allowed retries.
Unused reservation is released when the job reaches terminal state because
terminal window accounting uses accumulated actual GPU time.

## Serialization

`media_video_gpu_lock` is a single durable lock record.

Only one GPU-heavy 30.5.10 job may be marked running by this scheduler.

This intentionally prevents assumptions that writer/image/video models coexist
in the 12 GB GPU simultaneously.

---

# 8. Retry Semantics

The roadmap says:

```text
media.video.max_retries_per_shot = 2
```

30.5.10 interprets this as:

```text
initial attempt
+ retry 1
+ retry 2
= maximum 3 attempts
```

A provider failure therefore produces the expected durable sequence:

```text
attempt 1 -> RETRY
attempt 2 -> RETRY
attempt 3 -> FAILED
```

The motion-story fallback remains valid throughout all three attempts.

Provider failure is recorded in:

- media attempt records,
- media provider execution records,
- GPU consumed-time accounting,
- final reason code.

---

# 9. Restart Recovery

A machine/process restart may leave:

```text
media job = RUNNING
GPU reservation = RUNNING
GPU lock = job ID
```

Recovery order:

1. accepted `MediaPersistence.recover_interrupted_jobs()` converts the durable
   running job back to retry/failed according to attempt limits,
2. `LocalVideoEnhancementService.recover_gpu_scheduler()` clears the stale GPU
   lock,
3. the existing reservation returns to reserved state when retryable,
4. the same media job is claimed again,
5. no duplicate enhancement job or reservation is created.

The 30.5.10 proof deliberately performs this sequence.

---

# 10. File Outputs

Successful enhancement jobs write:

```text
video-enhancements/
  <story_id>/
    shot-<index>-<spec_id>.mp4
    shot-<index>-<spec_id>.json
```

The MP4 is validated by local `ffprobe` for:

- one video stream,
- expected 9:16 dimensions,
- bounded duration.

The JSON sidecar includes:

- story/spec/job/attempt IDs,
- provider ID and local/paid flags,
- deterministic highlight score/tier,
- selected shot provenance,
- source event/envelope IDs,
- fallback motion-story artifact ID/digest,
- deterministic seed,
- output SHA-256,
- `ffprobe` result,
- provider metadata,
- estimated/actual GPU milliseconds,
- presentation-only authority flags.

The media DB records both artifacts and the provider execution.

---

# 11. Paid Provider Rules

The default policy remains:

```text
local_required = true
paid_allowed = false
explicit_paid_authorization = false
```

A paid provider requires all accepted 30.5.2 gates:

1. request allows paid,
2. request contains explicit paid authorization when required,
3. global provider policy allows paid,
4. cloud use is allowed for remote providers,
5. monetary budget is positive and sufficient,
6. provider satisfies VRAM/capability constraints.

An API key or provider registration alone never authorizes spend.

GPU-hour budget and paid monetary budget remain independent controls.

---

# 12. VRAM Policy

The default local limit is:

```text
12 GB = 12288 MB
```

A provider advertising 16 GB estimated VRAM is ineligible even if its quality
rank is higher than every eligible provider.

This rule targets the current RTX 3060 12 GB machine and remains configurable for
future hardware.

---

# 13. Graceful Degradation Matrix

| Condition | Result |
| --- | --- |
| score < 90 | no video job; use 30.5.9 MP4 |
| video disabled | no video job; use 30.5.9 MP4 |
| no eligible 3–5 s shots | no video job; use 30.5.9 MP4 |
| no eligible VIDEO provider | durable job held; use 30.5.9 MP4 |
| provider exceeds 12 GB | durable job held; use 30.5.9 MP4 |
| GPU window exhausted | durable job held; use 30.5.9 MP4 |
| provider attempt fails | retry enhancement; fallback remains ready |
| two retries exhausted | enhancement fails; fallback remains ready |
| machine restart | recover same job/reservation; fallback remains ready |
| paid provider disabled | hold/degrade; never auto-spend |

No row in this matrix can fail the canonical crawl.

---

# 14. Acceptance Proof

Generator:

```text
scripts/generate-underreach-local-video-enhancement-proof.py
```

Output:

```text
validation/underreach-30_5_10/local-video-enhancement-proof.json
```

The deterministic proof creates:

- one persisted score-97 cinematic highlight,
- three accepted source still artifacts,
- one completed 30.5.9 fallback MP4,
- three scheduled enhancement jobs,
- three real short local MP4 enhancement clips,
- three sidecar manifests,
- three completed GPU reservations.

The first enhancement job is deliberately left running while owning the durable
GPU lock. The media DB is reopened, the interrupted job is recovered, the stale
GPU lock is cleared, and that same job completes on attempt 2.

Separate proof databases validate:

- GPU-budget exhaustion before execution,
- injected provider failure through initial attempt + two retries,
- fallback retention during every failure,
- paid routing gates,
- rejection of a 16 GB provider under the 12 GB policy.

The proof runs twice and requires identical semantic digests.

---

# 15. Acceptance Gate

Validator:

```text
scripts/run-underreach-local-video-enhancement-validation.ps1
```

Acceptance requires:

- accepted 30A.1 through 30.5.9 regressions,
- focused 30.5.10 tests,
- local `ffmpeg` and `ffprobe`,
- `libx264`,
- production source contains no canonical Crawl-service imports,
- production source contains no required HTTP/cloud client,
- deterministic proof run twice,
- identical proof/media/GPU digests,
- score 97 selects exactly 3 cinematic-priority shots,
- exactly 3 enhancement jobs,
- exactly 3 enhancement MP4 artifacts,
- exactly 3 JSON sidecars,
- exactly 3 completed local provider executions,
- restart recovers one media job + one GPU lock,
- recovered first job completes on attempt 2,
- GPU serialization lock is clear at completion,
- budget exhaustion yields `gpu_budget_exhausted` and no reservation,
- injected failure sequence is `retry,retry,failed`,
- motion-story fallback survives all failure paths,
- paid provider is blocked by default,
- paid provider can route only with every explicit gate,
- 16 GB provider is rejected under 12 GB policy,
- canonical state/Ledger snapshot remains unchanged,
- full repository regression suite passes.

The terminal validator line is:

```text
[30.5.10] PASS
```

Until the user reports that PASS, 30.5.10 is not accepted.

---

# 16. Out of Scope

30.5.10 does not add:

- canonical video state,
- gameplay writeback from generated media,
- Unreal rendering,
- automatic publishing,
- static website/blog generation,
- unattended phase soak,
- mandatory Wan/ComfyUI installation,
- required video diffusion,
- automatic paid escalation,
- highlight scoring by an LLM.

30.5.11 owns media website/blog generation.

30.5.12 owns the unattended Phase 30.5 promotion soak.

---

# 17. Next Canonical Slice

After explicit local acceptance of 30.5.10, the next exact frozen slice is:

**30.5.11 — Media Website / Blog Generation**

Nothing in 30.5.10 is merged automatically.
