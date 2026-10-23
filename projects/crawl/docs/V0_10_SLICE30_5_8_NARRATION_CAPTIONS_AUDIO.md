# Crawl v0.10 — Slice 30.5.8 Narration, Captions & Audio

## Status

Implementation slice: **30.5.8 — Narration, Captions & Audio**

Phase: `"30.5"` (string, never floating point)

Base: accepted **30.5.7 — Headless Local Image Production** at `bedc04ae0c594c3da5253aaf7a1708ef157b1c7e`.

Protocol: `underreach.narration-captions-audio.v1`

This slice is downstream media infrastructure only. It does not gain gameplay authority.

---

# 1. Purpose

30.5.8 turns an accepted 30.5.5 **REVIEW_READY** narrative into a durable, local-first audio package for later 30.5.9 FFmpeg assembly.

It produces:

- the verified narration script verbatim,
- deterministic caption timing metadata,
- SRT captions,
- WebVTT captions,
- media-owned audio-package metadata,
- optional local WAV narration,
- optional local royalty-safe music/SFX references,
- durable job / attempt / artifact / provider provenance,
- a guaranteed caption-only degradation path.

It does **not** perform final audio mixing or video assembly.

---

# 2. Authority Boundary

The accepted architecture remains:

```text
Canonical Crawl / Ledger
        |
        | read-only export
        v
MediaEnvelope
        v
Chronicle Chapter
        v
30.5.5 Narrative Draft + Claim Manifest + REVIEW_READY Verification
        |
        v
30.5.8 Caption Package Job
        |
        +--------------------------+
        |                          |
        v                          v
TXT / SRT / VTT / JSON       Optional Voice Job
                                    |
                                    v
                              local WAV + JSON
```

30.5.8 MUST NOT:

- open or mutate canonical Crawl persistence,
- append or alter Ledger events,
- change health, inventory, survival, combat, movement, progression, relationships, parties, alliances, social memory, or outcomes,
- accept `NEEDS_REVIEW` or `REJECTED` prose as narration,
- rewrite or embellish the verified narration script,
- derive captions through speech recognition,
- treat TTS output as canonical truth,
- invoke Unreal,
- require cloud AI,
- require a paid provider,
- silently escalate to a billable provider,
- perform final music/SFX/voice mixing.

---

# 3. Verified Narrative Input

The sole narration text authority is an exact persisted 30.5.5 `NarrativeVerification` whose state is:

```text
status = REVIEW_READY
review_ready = true
```

30.5.8 resolves that verification's exact persisted `NarrativeDraft` and uses:

```text
NarrationPackageSpec.script == NarrativeDraft.prose
NarrationPackageSpec.sentences == NarrativeDraft.sentences
```

No summarization, rewriting, generation, cleanup, or provider output may change this script inside 30.5.8.

A `NEEDS_REVIEW` or `REJECTED` verification is a hard planning failure.

---

# 4. Caption Contract

Captions are deterministic and derive directly from verified draft sentences.

For each verified sentence, 30.5.8 creates exactly one `CaptionCue` containing:

- contiguous cue index,
- deterministic start time,
- deterministic end time,
- exact verified sentence text,
- deterministic cue digest.

Initial timing policy is based on word count:

```text
sentence_duration = max(minimum_caption_ms, word_count * milliseconds_per_word)
next_start = previous_end + caption_gap_ms
```

This is presentation timing only. It is not canonical game time.

30.5.8 writes:

- `narration.txt`,
- `captions.srt`,
- `captions.vtt`,
- `audio-package.json`.

Speech recognition is intentionally unnecessary and forbidden in the slice acceptance path.

---

# 5. Guaranteed Caption-Only Package

Caption generation is a separate durable job:

```text
underreach.audio.package
```

It has **no provider dependency**.

Once it completes, the package is valid for later 30.5.9 assembly even when voice synthesis is unavailable.

The package job writes four file-backed artifacts:

1. verified narration TXT,
2. SRT,
3. VTT,
4. deterministic JSON metadata.

This is the guaranteed degradation path.

---

# 6. Optional Voice Job

When voice is enabled, a second durable job is created:

```text
underreach.audio.voice
```

It depends on the caption package job.

The voice request uses accepted 30.5.2 `ProviderKind.VOICE` routing and requires:

- `headless_voice`,
- `wav_output`,
- deterministic seed support,
- sufficient maximum duration,
- configured local/paid policy.

Default policy is local-first and paid-disabled.

If no eligible provider exists, the voice job is held while the completed caption package remains valid.

If a provider fails, only the voice job retries/fails. The caption package remains complete and valid.

---

# 7. Local Acceptance Voice Backend

30.5.8 includes `DeterministicLocalWavProvider`.

It writes a real deterministic mono PCM WAV using only Python standard-library components.

Its role is to prove:

- executable voice-provider integration,
- provider routing,
- durable attempts,
- WAV file persistence,
- sidecar provenance,
- restart recovery,
- caption-only fallback independence.

It is **not** intended as final-quality narration.

A local Kokoro or equivalent implementation plugs into the same `HeadlessVoiceProvider` contract without changing canonical systems, verified narrative records, caption timing, queue semantics, or downstream 30.5.9 assembly.

---

# 8. Voice Artifacts

A successful voice job writes:

- `narration.wav`,
- `narration.wav.json`.

The WAV sidecar includes:

- package ID,
- verification ID,
- durable voice job ID,
- attempt ID,
- provider ID,
- local/paid metadata,
- sample rate,
- channel count,
- deterministic duration,
- WAV SHA-256,
- provider metadata,
- explicit presentation-only authority,
- confirmation that caption-only fallback remains available.

The media database also retains the accepted 30.5.2 provider execution record.

---

# 9. Music / SFX Metadata

30.5.8 may carry `SoundAssetReference` records for local royalty-safe music and sound effects.

Each reference requires:

- stable asset ID,
- `music` or `sfx` kind,
- relative local URI,
- license label,
- `royalty_safe = true`,
- deterministic digest.

HTTP/remote paths and parent traversal are rejected.

30.5.8 records these references only.

**It does not mix them.**

Loudness normalization, ducking, fades, music/SFX mixing, caption burn-in, and final encode remain 30.5.9 responsibilities owned by FFmpeg.

---

# 10. Paid / Cloud Policy

Default behavior remains zero-spend:

```text
local_required = true
paid_allowed = false
explicit_paid_authorization = false
providers.allow_paid = false
providers.daily_paid_budget = 0
```

An API key or registered remote provider does not authorize spending.

A paid provider may route only when every accepted 30.5.2 gate is explicitly enabled, including global permission, per-request permission, explicit authorization when required, and positive budget.

---

# 11. Restart & Idempotency

The package and voice jobs use accepted 30.5.2 durable queue semantics.

Acceptance proves:

- a voice job can be leased and interrupted,
- SQLite can be reopened,
- `recover_interrupted_jobs()` returns that same voice job to retry,
- the recovered job completes on attempt 2,
- re-enqueuing the exact same package and voice specs with identical priorities returns the same job IDs,
- no duplicate artifacts or executions are created by completed re-enqueue.

File writes are atomic and artifact recording is idempotent.

---

# 12. Resource / Reliability Rules

30.5.8 must remain independent of simulation progress.

Voice failure may only affect voice media work.

Required degradation behavior:

| Condition | Result |
| --- | --- |
| Verified narrative valid, TTS healthy | captions + narrated WAV |
| Verified narrative valid, no TTS provider | completed caption-only package; voice held |
| TTS provider fails | voice retries/fails; caption package remains valid |
| Process restarts during voice attempt | durable retry of same voice job |
| Paid provider registered but not authorized | provider remains ineligible |
| Music/SFX unavailable | narration/captions remain valid; mixing deferred |

---

# 13. Acceptance Proof

The deterministic proof runs twice against file-backed media SQLite stores and must produce identical semantic digests.

The proof establishes:

- one exact 30.5.5 REVIEW_READY narrative source,
- narration script equals verified draft prose verbatim,
- caption cue text equals verified sentences exactly,
- no speech recognition,
- no audio mixing,
- one royalty-safe local music reference,
- one successful local narrated package,
- real WAV signature,
- one deliberately interrupted/recovered voice job completing on attempt 2,
- one second no-provider caption-only package,
- held voice job with no voice artifact,
- completed-job idempotent re-enqueue,
- paid provider blocked by default,
- paid provider selectable only when all explicit gates are enabled,
- canonical Crawl state and Ledger remain unchanged.

Expected proof-owned audio media totals:

```text
jobs = 4
artifacts = 10
provider executions = 1
```

Breakdown:

```text
Narrated package job      4 artifacts
Narrated voice job        2 artifacts
Caption-only package job  4 artifacts
Held voice job            0 artifacts
```

---

# 14. Validation

Run:

```powershell
.\scripts\run-underreach-narration-captions-audio-validation.ps1
```

Acceptance requires:

```text
[30.5.8] PASS
```

The gate runs:

1. accepted 30A.1 through 30.5.7 regressions,
2. focused 30.5.8 tests,
3. deterministic file-backed proof twice,
4. explicit proof invariants,
5. full repository regression suite.

No GitHub Actions are required or used.

---

# 15. Explicit Non-Goals

30.5.8 does not implement:

- final FFmpeg assembly,
- audio mixing,
- loudness normalization,
- ducking,
- fades,
- caption burn-in,
- promotional MP4 encoding,
- local image-to-video generation,
- GPU-hour scheduling,
- publishing.

Those remain later frozen Phase 30.5 slices.

---

# 16. Next Canonical Slice

After local acceptance of 30.5.8, the next frozen slice is:

**30.5.9 — Automated FFmpeg Motion-Story Production**

Its purpose is to combine accepted verified stills, narration/captions, and optional local music/SFX into the guaranteed no-video-diffusion vertical promotional MP4 path.
