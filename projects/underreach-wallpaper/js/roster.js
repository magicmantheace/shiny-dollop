// Underreach Wallpaper — the asset roster (data-driven).
//
// ROSTER RULE (Adam, 2026-11-16): this wallpaper must include at
// least one copy of EVERY Game Asset Builder asset as it is
// created and passes its gates. This file is the single source of
// truth for WHAT exists; js/layout.js is the source of truth for
// WHERE it stands (named plots in named zones). Adding a newly
// completed asset = one row here + one plot row in layout.js +
// its GLB in assets/ — no other scene-code changes.
//
// v1 carries the full completed initial set: the Underreach queue
// #1–#28 and #30, the Cart extra, and the four pre-queue Underreach
// catalogue assets (delver, gloam-lurker, the Tier-1 lantern, cot).
// Parked assets (#29 ore face, #31 crystal cluster) are NOT listed:
// they join only when they complete and pass their gates, like
// every future queue asset (#32 onward).
//
// Entry fields:
//   slug    catalogue slug; GLB is assets/<slug>.glb, a
//           byte-for-byte copy of the catalogued file (sha256 in
//           docs/MUSE_HANDOFF.md).
//   queue   queue number from the asset-queue ledger ('pre' for
//           pre-queue catalogue assets, 'extra' for the Cart).
//   kind    creature | lantern | structure | station | prop
//   height  normalize the model's bounding box to this height.
//   glow    lanterns: fake-light recipe {color, pool (light-pool
//           radius), sprite (glow sprite scale), at (flame height
//           as a fraction of height), real: true spends one of the
//           few real PointLights — budget in docs/TEST_PLAN.md}.
//   glowShroom  fungal growth: emissive pulse + spore glow, no pool.
//   creatures: speed (units/s), signature (clip played dwelling),
//           weight (spawn weighting), outerOnly (dim rim only).

export const ROSTER = [
  /* ------------------------------------------------ creatures */
  { slug: 'gloam-rat', queue: 1, kind: 'creature', height: 0.55,
    speed: 1.6, signature: 'bite', weight: 3 },
  { slug: 'frontier-bearer', queue: 2, kind: 'creature', height: 1.8,
    speed: 0.85, signature: 'plant', weight: 2 },
  { slug: 'delver', queue: 'pre', kind: 'creature', height: 1.7,
    speed: 1.0, signature: 'bounce', weight: 3 },
  { slug: 'gloam-lurker', queue: 'pre', kind: 'creature', height: 1.15,
    speed: 0.75, signature: 'shiver', weight: 1, outerOnly: true },

  /* --------------------------------------- the lantern family */
  { slug: 'torch-on-a-stand', queue: 11, kind: 'lantern', height: 1.9,
    glow: { color: 0xff9a3c, pool: 2.4, sprite: 1.7, at: 0.86 } },
  { slug: 'lantern', queue: 'pre', kind: 'lantern', height: 2.1,
    glow: { color: 0xffb45e, pool: 3.2, sprite: 2.0, at: 0.8, real: true } },
  { slug: 'fungal-oil-lantern', queue: 12, kind: 'lantern', height: 2.0,
    glow: { color: 0x7dff9a, pool: 2.8, sprite: 1.8, at: 0.78 } },
  { slug: 'sealed-pressure-lantern', queue: 13, kind: 'lantern', height: 2.0,
    glow: { color: 0x9fd8ff, pool: 2.6, sprite: 1.7, at: 0.8 } },
  { slug: 'crystal-heart-lantern', queue: 14, kind: 'lantern', height: 2.05,
    glow: { color: 0xc09aff, pool: 3.0, sprite: 1.9, at: 0.8 } },
  { slug: 'thermal-lamp', queue: 15, kind: 'lantern', height: 1.9,
    glow: { color: 0xff7a3c, pool: 3.0, sprite: 2.0, at: 0.72, real: true } },
  { slug: 'piped-light-spine-segment', queue: 16, kind: 'lantern', height: 1.5,
    glow: { color: 0xffb45e, pool: 3.6, sprite: 2.6, at: 0.92 } },
  { slug: 'crystal-relay', queue: 17, kind: 'lantern', height: 2.6,
    glow: { color: 0xb78cff, pool: 3.8, sprite: 2.4, at: 0.84, real: true } },
  { slug: 'heat-pipe-relay', queue: 18, kind: 'lantern', height: 2.2,
    glow: { color: 0xff8a4a, pool: 3.2, sprite: 2.0, at: 0.7 } },

  /* -------------------------------------- structures & stations */
  { slug: 'surface-gate', queue: 26, kind: 'structure', height: 4.8 },
  { slug: 'timber-support-set', queue: 27, kind: 'structure', height: 3.1 },
  { slug: 'ventilation-pieces', queue: 28, kind: 'structure', height: 2.6 },
  { slug: 'deep-ledger', queue: 25, kind: 'station', height: 2.6 },
  { slug: 'converter-forge', queue: 19, kind: 'station', height: 2.2 },
  { slug: 'chandlery-bench', queue: 20, kind: 'station', height: 2.0 },
  { slug: 'charcoal-kiln', queue: 21, kind: 'station', height: 2.1 },
  { slug: 'tailor-bench', queue: 23, kind: 'station', height: 2.0 },
  { slug: 'sealed-food-store', queue: 24, kind: 'station', height: 2.3 },
  { slug: 'herbalist-bench', queue: 22, kind: 'station', height: 2.0 },
  { slug: 'cart', queue: 'extra', kind: 'station', height: 1.7 },
  { slug: 'cot', queue: 'pre', kind: 'station', height: 0.8 },
  { slug: 'fungal-node', queue: 30, kind: 'station', height: 1.1, glowShroom: true },

  /* -------------------------------------- small props (the kits) */
  { slug: 'miner-pickaxe', queue: 3, kind: 'prop', height: 0.95 },
  { slug: 'miner-helmet-lamp', queue: 3, kind: 'prop', height: 0.34 },
  { slug: 'hauler-ore-basket', queue: 4, kind: 'prop', height: 0.62 },
  { slug: 'farmer-sickle', queue: 5, kind: 'prop', height: 0.55 },
  { slug: 'farmer-pouch', queue: 5, kind: 'prop', height: 0.42 },
  { slug: 'herbalist-herb-bundle', queue: 6, kind: 'prop', height: 0.5 },
  { slug: 'herbalist-satchel', queue: 6, kind: 'prop', height: 0.52 },
  { slug: 'spore-mask', queue: 7, kind: 'prop', height: 0.36 },
  { slug: 'harness-and-rope', queue: 8, kind: 'prop', height: 0.85 },
  { slug: 'quiet-gear-boot-wraps', queue: 9, kind: 'prop', height: 0.4 },
  { slug: 'quiet-gear-arm-wraps', queue: 9, kind: 'prop', height: 0.38 },
  { slug: 'cooling-gear-vest', queue: 10, kind: 'prop', height: 0.72 },
  { slug: 'cooling-gear-gauntlets', queue: 10, kind: 'prop', height: 0.42 },
];
