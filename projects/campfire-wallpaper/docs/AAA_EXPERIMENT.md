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

## Stage 2 — ground, grass, fire (owner's pick, 2026-11-09)

- **Ground texture.** A periodic value-noise heightfield
  (lattice frequencies divide the tile, so it wraps seamlessly)
  generated at runtime into a 256² near-neutral diffuse plus a
  Sobel normal map from the same heights, tiled 26× over the
  field under the existing vertex colours. Daylight captures
  show real grain and patch variation where the field used to
  be flat colour.
- **Grass.** Tufts went from five blades to seven, and a vertex
  shader injected into the grass material bends each blade by
  height², phased by instance position so gusts travel. Grass
  does not cast shadows, so the displaced render has no shadow
  mismatch. Motion itself cannot be proven from stills; the
  captures show the varied lean the shader produces.
- **Fire.** A continuous flame body under the particles: three
  crossed planes with a procedural flame shader (scrolling fbm
  erodes a teardrop mask; deep orange → yellow → near-white at
  the base), so the particle flames read as tongues off a real
  body. Plus a 12-sprite smoke pool that swells, drifts +x, and
  fades. First smoke tuning was WRONG — light-grey puffs stacked
  over the fire read as a searchlight beam against the dusk
  sky; darkened (0x42464e), thinned (peak opacity 0.10), and
  spread from birth. Final captures: smoke is subtle, present
  if you look for it — the safe side of the line.
- Captures (SwiftShader, zero console errors): `aaa2-morning`
  (ground grain + fuller grass), `aaa2-sunset2` / `aaa2-night2`
  (flame body, embers, glow). Added steady-state cost is small
  (one texture pair, one extra shader material ×3 planes,
  12 sprites); the SwiftShader fps floor did not move, which
  cannot resolve deltas this small — the real-GPU number still
  waits on an owner-approved PC test.
- **Texture audit + raise (owner's ask, same day).** The GLB
  creature/chest maps were already 2048×2048 — above the ask.
  The genuinely low-res maps were this stage's own ground pair
  (256²) and the moon canvas (512²): ground raised to 1024²
  with two extra fine octaves (features to ~5 cm; normal slope
  rescaled for the finer texel grid), moon to 1024² (beyond
  what its small on-screen disc can show, done for uniformity).
  The 128² radial-gradient sprites were left alone on purpose:
  a smooth gradient has no detail for resolution to add.
  Verified in `aaa3-morning` (zero console errors; finer
  foreground grain, most visible at desktop scale).

## Stage 3 — de-cartoon (owner's diagnosis, 2026-11-09)

The owner named the real problem: the background looked out
of place next to the creatures. Correct — the creatures are
painted, textured models; the background was flat-shaded,
untextured primitives in saturated flat colours. Four moves,
all aimed at the mismatch, none at the creatures:

- **Texture + smooth shading for the environment set.** One
  shared runtime-generated fine-grain detail map (periodic
  noise, near-neutral) now multiplies the pines, rocks,
  bushes, oak leaves, trunks, fire logs, and fire stones, and
  flatShading came off the foliage/rocks/bushes/leaves so
  forms shade continuously instead of faceting like paper.
- **Palette softening.** Day sky stops desaturated toward a
  deeper, greyer blue; field vertex colours shifted a few
  points warmer and less saturated.
- **Clouds.** The sky shader gained soft fbm cloud wisps on a
  projected plane, drifting slowly, banded to the lower sky,
  tinted by the horizon colour, present in the lit hours and
  gone by full night. The flat gradient card was the single
  most "cartoon" surface in the scene.
- **One grade over everything.** A final ShaderPass between
  bloom and output: gentle desaturation (0.93), a whisper of
  warmth, a soft vignette. One filmic pass over the whole
  frame is what makes two asset styles read as one image.

Verified in `aaa4-morning` / `aaa4-sunset` (zero console
errors): the morning scene is visibly less toy-like — living
sky, softer forms, moodier field; dusk keeps the fire's pop
against a richer frame. Remaining stylization, honestly: the
low-poly geometry itself, and the flat ridge backdrops (the
bright snow band is the most graphic element left). Closing
those would mean new backdrop art, not more tuning.

## Stage 4 — art redo (owner: "Redo the art", 2026-11-09)

- **Painted textures.** A seeded dab-painting generator
  (1,100+ soft ellipses per canvas, 3×3 wrap so they tile)
  produced per-family maps: needle greens for foliage, rock
  greys, streaked bark browns, and a pale rock for the ridges.
  They replace stage 3's neutral grain on pines, bushes, oak
  leaves, rocks, trunks, logs, and fire stones; material
  colours went near-white so the painting carries the hue.
- **Organic silhouettes.** Pine tiers are radially jittered
  by a smooth angular wave and their shade is a continuous
  height gradient (the hard per-tier bands are gone); rocks
  and bushes are displaced ±10–13% by a position hash, so no
  two read as stamped from the same mould.
- **Ridges rebuilt.** The flat cards became five-row slopes
  leaning toward the viewer, textured with the pale rock,
  with a smooth-blended snowline instead of the hard switch.
  First cut made them lit standard materials — and the
  sunset alpenglow died to black, because the glow was the
  palette tint acting on an unlit surface. Final call: unlit
  textured geometry (geometry + texture were the win; the
  tint system keeps the day/night life). Hills got the same
  texture on their unlit domes.
- Verified in `aaa5-morning2` / `aaa5-sunset2` (zero console
  errors): snowy textured ranges with soft snow, glowing at
  dusk again; near pines rich and painted; lumpy bushes.
  Remaining tells, honestly: the mid-distance treeline still
  reads pale through the haze (near trees carry the detail),
  and up close the geometry is still stylized low-poly —
  that is the scene's skeleton, not its skin.
