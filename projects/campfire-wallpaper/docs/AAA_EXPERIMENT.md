# AAA graphics experiment (branch campfire-wallpaper/aaa-graphics-experiment)

Owner-directed 2026-11-09: bookmark the current build, then try a
version that "looks on par with modern AAA game graphics."

**Bookmark:** git tag `campfire-wallpaper/bookmark-definition-pass`
(= PR #49 tip `f1a7732`, the definition-pass build) is the restore
point. It stays deployed live on the owner's PC while this
experiment is evaluated from captures. This branch never deploys
over it without the owner's explicit say-so.

**Deliberate rule deviation:** the project AGENTS.md manners say
"no shadow maps." AAA-par rendering is not reachable under that
rule, so this branch relaxes it — on this branch only, and with
the owner's direction on record. Everything else in the manners
still holds here: pixel-ratio cap 2, modest particle counts,
hidden-page pause, self-contained folder, GLBs untouched.

## What stage 1 changes (all in js/wallpaper.js + vendored addons)

- Real-time shadows: the existing sun/moon directional light casts
  one 2048² PCF-soft shadow map over a ±42 m box (clearing and
  mid-field). Creatures, the chest, and all lit dressing cast and
  receive; grass receives only. The painted creature blob stays as
  a faint contact grounding at 0.22 opacity.
- Image-based lighting: a PMREM environment generated from a
  miniature of the sky dome (the same gradient uniforms, shared by
  reference) plus a dark ground disc, refreshed when the sun
  crosses a 3° elevation bucket; `scene.environmentIntensity` 0.35.
- Post chain (EffectComposer, HalfFloat + 4× MSAA target):
  RenderPass → UnrealBloomPass (strength 0.35, radius 0.55,
  threshold 0.85 — fire, glow mushrooms, sky discs) → OutputPass
  (tone mapping + sRGB). Vendored from three.js r180 to match the
  vendored core: postprocessing/{EffectComposer, RenderPass,
  ShaderPass, MaskPass, Pass, UnrealBloomPass, OutputPass}.js and
  shaders/{CopyShader, LuminosityHighPassShader, OutputShader}.js.

## Honest expectations

The environment rendering (light, shadow, atmosphere, glow) can
move a long way toward a modern game look. The creatures are
stylized painted GLBs from the Game Asset Builder; no scene
lighting makes them photoreal, and this branch does not touch the
GLBs (project rule). The realistic target is a high-end stylized
look — rich light and shadow under stylized characters.

## Verification

Frozen-time harness captures against this worktree (SwiftShader,
zero console errors in all): `aaa-noon.png` (first tuning —
WASHED OUT: the OutputPass sRGB-encodes the sky dome's
ShaderMaterial output that the direct renderer used to emit raw,
and the IBL ambient stacked on the hemisphere light),
`aaa-noon2.png` (compensation applied: sky colours converted
as-if-sRGB→linear at uniform set, environmentIntensity 0.35 →
0.15, hemisphere × 0.8, bloom threshold 0.9 — palette restored),
`aaa-morning.png` (sun el 18.6°, az 149.5°: soft cast shadows
visible from pines, rocks, stumps, and creatures — real but
subtle at this angle; PCF-soft over a ±42 m box is a 4 cm texel),
`aaa-sunset.png` / `aaa-golden.png` (sun just set: the fire and
glow mushrooms bloom, darks are richer than the bookmark build —
the clearest stage-1 win is dusk/night).

Honest stage-1 read: dusk and night are visibly richer; daylight
is roughly on par with the bookmark build (better grounding,
similar palette). This is a step toward a modern game look, not
AAA parity — the remaining gaps are the stylized assets
themselves (kept by design), the flat untextured ground, and
the static grass. Stage-2 candidates, in impact order:
procedural ground texture (diffuse + normal), wind-sway grass
blades, a shader flame with smoke, a procedural cloud layer.

Frame cost on the real GPU is unmeasured until/unless the owner
approves a PC-side test (a second Lively library entry would
leave the bookmarked build untouched). SwiftShader fps stayed
at the known 22 artifact floor, which says nothing about the
RTX 3060 either way.
