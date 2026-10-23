# Crawl v0.9 — Unreal Presentation Vertical Slice

## Purpose

This vertical slice proves that an event which genuinely happened in the deterministic Crawl simulation can be reconstructed as a real-time 3D presentation in Unreal Engine and rendered to video without giving the renderer authority over the simulation.

The target pipeline is:

```text
Deterministic Crawl Simulation
        ↓
Authoritative Event Ledger
        ↓
Real Autonomous Combat Selection
        ↓
Presentation Staging Resolver
        ↓
Presentation Staging Manifest
        ↓
Unreal Procedural Scene
        ↓
Level Sequence + Camera Playback
        ↓
Movie Render Queue
        ↓
H.264 MP4
```

The vertical slice intentionally prioritizes proving the complete data and rendering pipeline before committing the project to a final character art or animation library.

---

## Authority Boundary

### Crawl owns

- which participants exist,
- which encounter happened,
- event order,
- hits and damage outcomes,
- injuries,
- retreats,
- defeated enemies,
- crawler deaths/eliminations,
- encounter outcome,
- authoritative history.

### Presentation owns

- where an actor stands inside an Unreal room,
- camera placement,
- interpolation between staged positions,
- how many seconds a canonical event receives on screen,
- which animation represents an already-resolved action,
- non-authoritative environment geometry,
- lighting and visual effects.

Presentation must never feed its results back into Crawl.

The staging manifest is therefore explicitly:

```text
authoritative = false
canonical_source = crawl_event_ledger
```

---

## Presentation Staging Resolver

`src/livingworld/presentation_staging.py`

The resolver converts canonical `CrawlEvent` objects into a deterministic presentation contract.

The contract contains:

- source event IDs,
- Crawl final-state fingerprint,
- presentation seed,
- bounded staged cast,
- deterministic initial transforms,
- presentation beats,
- performer/target roles,
- real-time beat durations,
- camera cues,
- total duration,
- deterministic manifest digest.

Canonical ordering uses `crawl.history_event_ids` as the authoritative tie-breaker when several events share the same simulation tick. This is important because combat can resolve many actions during a single Crawl tick while a viewer must see those actions sequentially.

### Large battles

A broad canonical event may contain dozens or hundreds of participants. A personal highlight does not need to visually stage every person in that event.

The resolver may choose a bounded visible cast while retaining the untouched source event ID and canonical source event.

Example:

```text
Canonical COMBAT_STARTED:
100 crawlers participated

Presentation for crawler_000:
crawler_000
crawler_014
enemy_003
```

This is legal because the presentation did not rewrite the source event. It only chose which members of that canonical event are visible in this particular shot package.

---

## Real Autonomous Encounter Export

`src/livingworld/crawl_unreal_vertical_demo.py`

The acceptance exporter runs a normal headless Crawl and searches its ledger for a combat encounter that actually occurred.

It does not inject a synthetic rescue, kill, or combat outcome for the render.

The selector:

1. finds canonical `COMBAT_STARTED` events,
2. groups events by authoritative `encounter_id`,
3. requires genuine combat action such as hits, damage, injuries, defeats, retreats, or deaths,
4. prefers a visually manageable encounter,
5. selects a real crawler as presentation focus,
6. exports only after the simulation has resolved the encounter.

Outputs:

```text
validation/crawl-v0.9-unreal-vertical-slice.json
unreal/CrawlPresentation/Generated/stage_manifest.json
```

---

## Unreal Project

Project:

```text
unreal/CrawlPresentation/CrawlPresentation.uproject
```

The project enables the presentation-oriented Unreal plugins required for later production work, including:

- Python Editor scripting,
- Sequencer scripting,
- Movie Render Queue,
- MP4 encoding,
- Control Rig,
- Pose Search / Motion Matching foundation,
- Motion Warping.

### Current placeholder visuals

The first vertical slice deliberately creates its geometry procedurally from engine primitives:

- a simple arena floor,
- four walls,
- directional/fill lighting,
- cylinder crawler placeholders,
- cube enemy placeholders.

No purchased asset pack is required to prove the pipeline.

Generated `.umap` and `.uasset` files are local build artifacts and are ignored by Git. Source Python and project configuration remain version controlled.

---

## Procedural 60 FPS Motion

`unreal/CrawlPresentation/Content/Python/build_vertical_slice.py`

The Unreal builder consumes `crawl.presentation-stage.v1` and creates a 60 FPS Level Sequence.

Current presentation actions include:

- attack lunges,
- target knockback,
- hit reactions,
- injury reactions,
- near-death posture,
- defeat/death fall,
- retreat movement,
- rescue approach,
- general movement,
- automated camera movement.

These are smooth transform-based placeholder motions, not the final skeletal animation solution.

That distinction is intentional.

The first acceptance target is:

> prove that canonical simulation events can reliably become timed 3D motion and camera footage.

Once that works, the same `PresentationBeat` actions can drive skeletal animation assets instead of primitive transforms.

---

## Planned Skeletal Animation Upgrade

After the end-to-end vertical slice renders successfully, replace placeholder actor presentation with a character layer built around:

```text
PresentationBeat
      ↓
Animation Intent Router
      ↓
Locomotion / Motion Matching
      +
Action Montage
      +
Motion Warping
      +
Control Rig / IK
      +
Additive Injury / Reaction Pose
      ↓
Final Skeletal Pose
```

Expected mapping examples:

```text
attack_hit
  -> choose weapon attack animation
  -> Motion Warp attack toward staged target
  -> target plays matching reaction

retreat
  -> locomotion Motion Matching
  -> NavMesh/path-directed staged destination

injury_reaction
  -> hit reaction
  -> persistent injury additive if Crawl says injury remains

near_death
  -> critical-health posture/additive

rescue
  -> approach target
  -> context-appropriate interaction animation
```

The animation system is allowed to decide *how an event looks*, not whether it happened.

---

## Camera Integration

The existing deterministic `AutomatedCameraDirector` remains the source of semantic camera intent.

The staging resolver translates camera tick windows into presentation seconds and clamps camera subjects to the actors actually staged in the current replay.

Unreal then converts those logical modes into physical camera transforms.

Current supported camera intents include:

- crawler follow,
- over-the-shoulder,
- combat tracking,
- wide establishing,
- overhead tactical,
- party shot,
- enemy reveal,
- reaction closeup,
- slow-motion replay.

Later Unreal-specific camera work will add collision/obstruction handling, lenses, spring/damping behavior, and environment-aware composition.

---

## Movie Render Queue

`unreal/CrawlPresentation/Content/Python/create_render_preset.py`

The preset builder creates a local Movie Render Queue configuration using:

- deferred rendering,
- 1280×720 initial acceptance resolution,
- 60 FPS,
- H.264 MP4 output,
- CRF 18 high-quality baseline,
- no audio in the first vertical slice.

The resolution is intentionally modest for rapid iteration. Production profiles can later include 1080p, 4K, horizontal, and vertical deliverables.

---

## One-Command Local Workflow

Run:

```powershell
.\scripts\run-crawl-unreal-vertical-slice.ps1
```

The script performs:

1. focused staging tests,
2. autonomous Crawl simulation,
3. real combat selection,
4. staging manifest export,
5. optional full Python regression suite,
6. Unreal installation discovery,
7. procedural scene creation,
8. Level Sequence creation,
9. Movie Render Queue preset creation,
10. H.264 video rendering,
11. MP4 existence verification.

Unreal can also be specified explicitly:

```powershell
.\scripts\run-crawl-unreal-vertical-slice.ps1 `
  -UnrealEditorCmd "C:\Program Files\Epic Games\UE_5.x\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
```

Useful development switches:

```text
-SkipFullRegression  skip the inherited Python suite
-SkipUnreal          stop after canonical staging export
-SkipRender          build Unreal scene + render preset but do not render MP4
```

---

## Acceptance Gates

### Backend staging

The report must prove:

- the Crawl completed,
- a real autonomous combat was selected,
- the encounter contains genuine combat action,
- all staging source events are canonical,
- canonical history order is preserved,
- staging is explicitly non-authoritative,
- staging does not mutate the Crawl fingerprint,
- actor count is bounded,
- the focus actor is present,
- camera cues exist,
- presentation duration is positive.

### Unreal scene

Unreal must successfully create:

- a generated level,
- staged actors,
- a Level Sequence,
- keyed action motion,
- a camera track,
- render metadata,
- an MP4 render preset.

### First-footage gate

The one-command workflow must produce a real `.mp4` file from the selected canonical encounter.

The first video is accepted as a *pipeline proof*, not final art quality.

---

## What This Batch Does Not Claim

The initial vertical slice does **not** claim:

- production-quality humanoid models,
- final combat animation quality,
- Motion Matching databases already populated,
- final dungeon art,
- complete VFX/audio,
- live streaming infrastructure,
- zero-delay live presentation,
- production camera collision/LOS solving.

Those become much easier to build once the first end-to-end rendered replay is proven.

---

## Next Visual Milestone After This Passes

The immediate follow-on visual milestone is:

1. acquire/import a reusable humanoid character foundation,
2. replace primitive crawler representation with skeletal characters,
3. establish a common skeleton/retarget strategy,
4. create locomotion Motion Matching database,
5. route combat PresentationBeats to animation montages,
6. add Motion Warping for target-aware attacks,
7. add Control Rig / IK for feet, hands, weapons, look-at, and aiming,
8. add injury and health-driven additive poses,
9. compare the skeletal render to the exact same staging manifest used by the primitive proof.

This is how Crawl can eventually achieve fluid live motion without making an LLM or the deterministic simulator generate individual animation frames.
