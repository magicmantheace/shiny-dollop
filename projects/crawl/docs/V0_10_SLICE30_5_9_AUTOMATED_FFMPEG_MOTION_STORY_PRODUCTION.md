# Crawl v0.10 — Slice 30.5.9 Automated FFmpeg Motion-Story Production

## Status

**Implemented — awaiting local acceptance validation.**

- **Phase:** `"30.5"`
- **Slice:** `30.5.9 — Automated FFmpeg Motion-Story Production`
- **Protocol:** `underreach.ffmpeg-motion-story.v1`
- **Implementation version:** `30.5.9`
- **Base:** accepted 30.5.8 SHA `abcb56fbf8b967deed0dc591205439882e73d99f`
- **Branch:** `agent/underreach-v0.10-slice30_5_9-automated-ffmpeg-motion-story-production`

Nothing in this slice is canonical gameplay authority.

---

# 1. Purpose

30.5.9 establishes the guaranteed Tier-1 promotional-media path before optional local AI-video enhancement is introduced in 30.5.10.

The primary acceptance target frozen by the Phase 30.5 roadmap is:

> Verified local stills plus narration/captions assemble automatically into a valid vertical promotional MP4 with zero video-model dependency.

The pipeline is:

```text
30.5.7 completed Chronicle scene stills
                +
30.5.8 completed verified caption package
                +
optional completed 30.5.8 narration WAV
                +
optional installed royalty-safe local music/SFX
                |
                v
Durable 30.5.9 assembly job
                |
                v
Local FFmpeg
  - pan / push / crop motion
  - transitions
  - caption burn-in
  - optional narration
  - optional music / SFX
  - ducking / mixing
  - loudness normalization
  - fades
  - H.264 / AAC final encode
                |
                v
9:16 MP4 + caption sidecar + provenance manifest
```

No diffusion-video model is needed for this path.

---

# 2. Authority Boundary

The canonical architecture remains unchanged:

```text
Deterministic Crawl Simulation
        |
        v
Canonical Crawl State + Ledger
        |
        | read-only export
        v
MediaEnvelope / Chronicle / verified narrative
        |
        v
Presentation identity / stills / audio
        |
        v
30.5.9 FFmpeg motion story
```

30.5.9 must never:

- open the canonical Crawl database,
- add or alter a Ledger event,
- alter health, inventory, combat, social state, movement, progression, survival, parties, alliances, or identity truth,
- treat generated media as canonical fact,
- invoke Unreal,
- require a cloud API,
- require a paid provider,
- invoke image-to-video or text-to-video generation,
- feed the resulting MP4 or edit decisions back into simulation authority.

The production module imports presentation/media contracts only.

---

# 3. Required Inputs

A motion story is planned only from durable completed media-owned inputs.

## 3.1 Still images

Each still must be:

- a persisted `image/png` artifact,
- produced by a completed 30.5.7 `underreach.image.generate` job,
- a Chronicle-scene artifact whose `chapter_id` matches the verified narration package,
- backed by an existing file whose SHA-256 still matches the media DB artifact digest,
- carrying canonical source event provenance through its 30.5.7 artifact metadata.

A presentation portrait or other static identity reference cannot masquerade as a Chronicle scene input.

## 3.2 Captions

The required caption source is exactly one persisted `text/srt` artifact from a completed 30.5.8 caption package.

The SRT text is already derived directly from REVIEW_READY verified narrative. 30.5.9 does not perform speech recognition or rewrite captions.

## 3.3 Voice

A completed 30.5.8 `audio/wav` artifact is optional.

If no completed voice artifact exists, 30.5.9 intentionally assembles a caption-first/silent MP4 rather than blocking production.

## 3.4 Music and SFX

30.5.8 may include royalty-safe local `SoundAssetReference` records.

30.5.9 resolves those references against the shared media root and hashes the actual local files before assembly.

A missing optional music/SFX file is recorded in `missing_sound_asset_ids` and skipped. Missing optional polish cannot block the guaranteed motion-story path.

---

# 4. Durable Motion-Story Job

Job type:

```text
underreach.motion-story.assemble
```

The job is stored in the accepted 30.5.2 media SQLite queue.

Its durable dependencies include:

- the completed 30.5.8 caption-package job,
- every completed 30.5.7 image job supplying a scene still.

The voice job is not a hard dependency because voice is optional by design. The planner uses a completed voice artifact when one exists and otherwise freezes a caption-only spec.

Enqueuing the exact same spec at the exact same priority reuses the same durable job ID.

Restart recovery uses the accepted media attempt/retry model rather than creating a replacement job.

---

# 5. MotionStorySpec

The immutable specification records at minimum:

- protocol / implementation / phase,
- deterministic `story_id`,
- Chronicle chapter ID,
- narration package ID,
- verification / draft / manifest IDs and digests,
- caption artifact ID / URI / digest,
- optional voice artifact ID / URI / digest,
- normalized scene still inputs and file digests,
- normalized source MediaEnvelope IDs,
- normalized canonical source event IDs,
- resolved royalty-safe sound assets and file hashes,
- missing optional sound asset IDs,
- deterministic shot plan,
- target duration,
- exact output dimensions,
- FPS,
- transition duration,
- narration mode,
- audio/mix processing flags,
- deterministic presentation seed,
- FFmpeg profile version,
- policy digest,
- explicit false authority/dependency flags.

The deterministic identity is based on media input identity/digests plus the FFmpeg profile and policy. It is not based on wall-clock time.

---

# 6. Default Production Profile

The default output profile is:

```text
1080 x 1920
30 fps
exact 9:16
H.264 / libx264
AAC when audio is present
CRF 23
veryfast preset
```

The acceptance proof deliberately uses a reduced but architecturally identical profile:

```text
360 x 640
12 fps
ultrafast
CRF 28
```

This keeps local validation practical while still proving a real MP4 is assembled through the same filter, caption, audio, retry, provenance, and output-validation path.

---

# 7. Deterministic Still Motion

A motion story turns static scene art into a sequence of deterministic shots.

Supported Tier-1 motion patterns are:

- `push_in`,
- `push_out`,
- `drift_left`,
- `drift_right`.

The plan derives each shot pattern from deterministic media identity rather than runtime randomness.

The planner chooses a bounded shot count from target duration, repeats/reuses available stills when necessary, and creates an overlapping timeline for transitions.

FFmpeg owns the actual:

- aspect-preserving scale,
- center crop,
- zoom/pan,
- shot trim,
- transition,
- opening/closing fade,
- final pixel format.

No video-generation model is involved.

---

# 8. Caption Burn-In

The 30.5.8 verified SRT is copied into the job working directory and used by FFmpeg's `subtitles` filter.

The finished package also retains an SRT sidecar.

30.5.9 does not:

- transcribe narration,
- infer timing from audio,
- rewrite verified sentences,
- add factual claims.

---

# 9. Audio Mixing

When audio inputs exist, FFmpeg performs the processing reserved for 30.5.9 by the canonical Phase 30.5 roadmap.

## Narration only

- resample,
- pad / trim to final duration,
- loudness normalization,
- fade-in / fade-out.

## Music only

- deterministic local loop when needed,
- bounded volume,
- trim to final duration,
- loudness normalization,
- fades.

## Narration + music

- split narration into audible and sidechain feeds,
- sidechain-compress the music under narration,
- mix narration and ducked music,
- loudness normalize,
- fades.

## SFX

- place at deterministic transition points,
- apply bounded volume,
- mix with existing audio bed.

If there are no available audio inputs, the valid output contains no audio stream.

---

# 10. Local FFmpeg Capability Contract

30.5.9 requires the local editor itself; it does not require an AI/video provider.

Acceptance requires both executables on PATH:

```text
ffmpeg
ffprobe
```

The validator requires a build exposing the capabilities used by the production path, including:

- `subtitles`,
- `xfade`,
- `zoompan`,
- `fade`,
- `loudnorm`,
- `sidechaincompress`,
- `amix`,
- `libx264`.

The worker probes required capabilities before an assembly attempt.

The exact FFmpeg version line and semantic edit-plan digest are retained in the final manifest.

---

# 11. Output Validation

After encoding, `ffprobe` verifies the result before the job may complete.

The output must have:

- exactly one video stream,
- the requested exact 9:16 dimensions,
- an MP4-compatible container,
- a duration within bounded tolerance of the frozen spec,
- an audio stream if and only if the spec contains audio inputs.

A failed probe is an assembly failure and follows the retry path.

---

# 12. Output Artifacts

Each successful motion-story job records exactly three 30.5.9 artifacts:

```text
video/mp4
text/srt
application/json
```

Example layout:

```text
motion-stories/
  <chapter_id>/
    <story_id>/
      motion-story.mp4
      captions.srt
      motion-story.json
      work/
```

The JSON manifest records:

- job / attempt IDs,
- canonical event and MediaEnvelope provenance,
- image artifact IDs,
- narration package / verification / draft provenance,
- source caption artifact,
- optional voice artifact,
- local music/SFX hashes and license metadata,
- missing optional sound assets,
- shot plan,
- dimensions / duration / FPS,
- narration mode,
- caption-burn status,
- loudness / ducking / fades / mixing state,
- FFmpeg provider/profile/version,
- required filter list,
- semantic FFmpeg command-plan digest,
- ffprobe result,
- final MP4 SHA-256,
- explicit noncanonical authority flags.

---

# 13. Failure, Retry, and Restart

If FFmpeg fails:

- canonical simulation remains unaffected,
- the media attempt fails with reason code `ffmpeg_assembly_failed`,
- the same durable job becomes retryable while attempts remain,
- the `work/` directory and captions/intermediates are retained,
- no replacement canonical event or media truth is created.

If the machine/process dies while a motion-story job is RUNNING, the accepted 30.5.2 recovery mechanism converts that attempt to interrupted and returns the same job to retry state.

The deterministic proof explicitly crashes one leased assembly job, reopens SQLite, recovers it, and completes the same job on attempt 2.

---

# 14. Acceptance Proof

Generator:

```text
scripts/generate-underreach-ffmpeg-motion-story-proof.py
```

Validator:

```text
scripts/run-underreach-ffmpeg-motion-story-validation.ps1
```

The proof builds real accepted media inputs and assembles two real MP4 outputs:

## Narrated motion story

- two completed 30.5.7 Chronicle scene stills,
- completed 30.5.8 verified caption package,
- completed local narration WAV,
- physical royalty-safe local music WAV,
- burned captions,
- narration/music mix,
- sidechain ducking,
- loudness normalization,
- fades,
- local FFmpeg final encode,
- audio stream present.

## Caption-only motion story

- same accepted still provenance,
- separately completed 30.5.8 caption package with voice disabled,
- burned captions,
- no required audio,
- local FFmpeg final encode,
- no audio stream.

The expected 30.5.9-only durable counts are:

```text
motion jobs:          2
motion artifacts:     6
FFmpeg executions:    2
```

The narrated restart probe must complete the same motion job on attempt 2.

Completed exact-spec re-enqueue must create no duplicate job/artifact/execution state.

The proof is run twice. Its reproducibility digest deliberately covers the semantic edit plan, stable media identities, durable job identities, dimensions, modes, counts, restart behavior, and authority state rather than requiring FFmpeg binary bytes to be identical across separate encodes/builds.

Each individual produced MP4 is still SHA-256 hashed and its exact digest is retained in that run's manifest/artifact record.

---

# 15. Non-Goals

30.5.9 does not implement:

- image-to-video generation,
- text-to-video generation,
- local diffusion-video models,
- GPU-hour scheduling,
- video-provider retry/fallback policy,
- cinematic Tier-2/Tier-3 enhancement,
- website/blog publication,
- automated social publishing,
- canonical gameplay changes.

Those remain downstream.

---

# 16. Next Canonical Slice

After 30.5.9 passes local acceptance, the next frozen slice is:

**30.5.10 — Local Video Enhancement & GPU Scheduling**

That slice may optionally replace selected high-value Tier-1 shots with local image-to-video output, while 30.5.9 remains the guaranteed completed fallback whenever enhancement is unavailable, fails, exceeds budget, or is not warranted by highlight score.
