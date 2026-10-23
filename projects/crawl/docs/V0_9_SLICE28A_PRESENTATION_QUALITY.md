# Crawl v0.9 Slice 28A — Presentation Quality Foundation

## Purpose

The v0.9 Unreal vertical slice proved that Crawl can take canonical simulation history, stage it deterministically, build an Unreal level and Sequencer sequence, render it, and produce a playable MP4 without manual editing.

Slice 28A changes the goal from **pipeline feasibility** to **presentation quality**.

The first priority is not adding more transform tricks to placeholder cylinders and cubes. The priority is creating a stable contract between canonical Crawl events and real skeletal characters, locomotion, actions, reactions, interactions, and future procedural animation systems.

The architectural rule remains:

```text
SIMULATION TRUTH
    -> PRESENTATION STAGING
    -> SEMANTIC ANIMATION PLAN
    -> UNREAL ASSET RESOLUTION
    -> ANIMATION / IK / MOTION WARPING
    -> CAMERA
    -> RENDER
```

Animation is presentation. It must never become authoritative simulation truth.

---

## 1. Semantic animation layer

`src/livingworld/presentation_animation.py` translates staged presentation beats into deterministic `AnimationIntent` records.

Examples:

```text
COMBAT_HIT
  -> attacker: humanoid.combat.attack.default
  -> victim:   enemy.biped.reaction.hit.default

CRAWLER_RETREATED
  -> crawler: humanoid.locomotion.run
  -> locomotion_mode: run_away

RESCUE
  -> rescuer: humanoid.interaction.rescue
  -> rescued: humanoid.reaction.rescued
  -> contact_policy: paired_interaction
```

The planner does not select an authoritative kill, hit, injury, rescue, movement result, or death. Those facts must already exist in the source event ledger.

The Unreal vertical demo now writes both:

```text
unreal/CrawlPresentation/Generated/stage_manifest.json
unreal/CrawlPresentation/Generated/animation_plan.json
```

The animation plan must match the staging digest and canonical source-event list before Unreal will accept it.

---

## 2. Asset slots instead of hard-coded assets

Animation intents reference semantic asset slots rather than Unreal package paths.

Example:

```text
humanoid.combat.attack.default
humanoid.reaction.hit.default
humanoid.locomotion.run
humanoid.interaction.rescue
rig.humanoid.crawler
```

The example registry lives at:

`unreal/CrawlPresentation/presentation_assets.example.json`

Copy it locally to:

`unreal/CrawlPresentation/presentation_assets.json`

The local file is intentionally gitignored. This allows licensed Marketplace/Fab content and machine-specific asset paths to remain local while the source-controlled semantic slots remain stable.

A slot value may be either a direct Unreal object path string or an object containing `asset`/`path`.

Example:

```json
{
  "slots": {
    "rig.humanoid.crawler": "/Game/Characters/Example/SKM_Crawler.SKM_Crawler",
    "humanoid.combat.attack.default": "/Game/Characters/Example/Animations/A_Attack.A_Attack"
  }
}
```

Changing these bindings does not alter simulation truth or replay history.

---

## 3. Unreal skeletal binding adapter

`unreal/CrawlPresentation/Content/Python/build_vertical_slice.py` now consumes both the staging manifest and semantic animation plan.

For each staged actor it:

1. resolves the actor's semantic `rig_slot`,
2. tries to load the configured Skeletal Mesh,
3. spawns a `SkeletalMeshActor` when the asset resolves,
4. keeps the existing primitive actor as a safe fallback when it does not,
5. binds the actor to Sequencer,
6. keeps transform tracks for presentation staging/world displacement,
7. creates `MovieSceneSkeletalAnimationTrack` sections for resolved idle/action/reaction/locomotion slots,
8. records resolved slots, missing slots, failed assets, skeletal actor count, fallback actor count, and animation-section count in `unreal_build_result.json`.

A missing art asset should reduce presentation quality, not destroy the canonical replay/render pipeline.

---

## 4. Asset discovery helper

`unreal/CrawlPresentation/Content/Python/discover_presentation_assets.py` inventories Skeletal Mesh and animation assets already available under `/Game`.

It writes:

`unreal/CrawlPresentation/Generated/presentation_asset_inventory.json`

The inventory is non-authoritative and exists only to make local asset binding easier. Candidate names such as Manny, Quinn, humanoid, idle, run, attack, hit, reaction, combat, and death are sorted toward the top without automatically selecting them.

---

## 5. Character motion stack target

The target Unreal character stack is:

```text
STAGING TARGET / NAVIGATION
          |
          v
LOCOMOTION
  Motion Matching or compatible locomotion system
          +
ACTION LAYER
  attack / block / interact / ability / pickup
          +
REACTION LAYER
  hit / injury / stumble / near-death / death
          +
PROCEDURAL SOLVING
  foot IK / hand IK / look-at / aim / contact alignment
          +
MOTION WARPING
  align attacks and paired interactions to staged targets
          +
FINAL SKELETAL POSE
```

The current adapter establishes the Sequencer skeletal-animation path. Motion Matching, Control Rig, IK and true motion-warp solving remain follow-on quality increments rather than canonical systems.

---

## 6. Root motion and navigation policy

Animation intents explicitly carry a presentation root-motion policy.

Current policies:

- `navigation_driven` — Unreal navigation/staging moves the actor while locomotion represents that motion.
- `motion_warp_to_target` — an action may visually align to a staged target without changing the canonical event.
- `in_place` — animation does not own world displacement.

This prevents authored animation clips from silently becoming simulation movement authority.

---

## 7. Contact policy

Some actions need visual contact solving.

Current semantic policies:

- `none`
- `weapon_or_hand_contact`
- `react_at_contact`
- `paired_interaction`

These are requests to the renderer. They are not proof that a hit or rescue happened. The event ledger remains the proof.

---

## 8. First real-character milestone

The next acceptance milestone is to bind local real assets and render the same canonical encounter with skeletal actors.

Minimum milestone:

1. Bind one humanoid crawler skeletal mesh.
2. Bind one biped enemy skeletal mesh or temporary compatible mannequin.
3. Bind idle and locomotion animation.
4. Bind one attack animation.
5. Bind one hit reaction.
6. Bind one death/defeat reaction.
7. Bind retreat locomotion.
8. Resolve the existing `AnimationIntent` plan in Unreal.
9. Preserve the existing camera plan and canonical source IDs.
10. Render the same deterministic event package to MP4.

The acceptance question is:

> Did Unreal render the canonical event using skeletal characters and real animation while preserving exactly the same source-event truth?

---

## 9. Follow-on quality work

After the first skeletal milestone is stable, add quality in this order:

1. locomotion continuity and turn quality,
2. attack/contact alignment,
3. reaction timing,
4. motion warping,
5. foot and hand IK,
6. injury posture overlays,
7. equipment attachment and weapon sockets,
8. improved staging and collision-aware spacing,
9. camera line-of-sight and obstruction solving,
10. modular dungeon environment assets,
11. VFX and impact feedback,
12. HUD/overlays/subtitles,
13. commentary and audio timing,
14. render caching and automated highlight assembly,
15. buffered live rendering.

---

## 10. Validation

Headless validation verifies:

- animation planning is deterministic,
- all plans remain non-authoritative,
- every animation intent points to a staged actor,
- every animation intent points to a canonical source event already included in staging,
- attack events create attacker + reaction roles,
- rescue events create paired interaction roles,
- movement/retreat use navigation-driven presentation motion,
- changing presentation asset bindings cannot alter Crawl event truth.

The full local Unreal runner additionally verifies that staging and animation manifests are emitted before launching Unreal. The Unreal build result records whether each staged actor used a skeletal mesh or primitive fallback and how many animation sections were successfully bound.

No GitHub Actions are required. Validation remains local.
