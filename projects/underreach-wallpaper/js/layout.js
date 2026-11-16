// Underreach Wallpaper — town layout: zones, plots, network.
//
// Adam's starting-state brief (2026-11-16): the scene is a cavern
// big enough for a small settlement — an Underreach TOWN. The
// founding settlement (the current asset roster) sits as the
// town's core; around it lies open ground in named expansion
// zones where the settlement will develop.
//
// This file is deliberately shaped like the state a future
// living-world simulation feed could drive (phase 2 — discussed,
// NOT commissioned; nothing here talks to anything):
//
//   TOWN STATE = { version, zones: [...], plots: [...], network }
//   plot = { id, zone, asset: <roster slug | null>, x, z, rotY,
//            y?, rotX?, rotZ?, noObstacle?, note? }
//
// The wallpaper renders DEFAULT_TOWN below. A future feed only
// has to supply plot -> asset assignments (and eventually new
// plots) to grow the town; no scene code changes. Plots with
// asset: null are surveyed expansion ground — defined, named,
// and empty in v1 by design.
//
// Coordinates: x east, z south (toward the viewer). The Surface
// Gate stands in the north wall; the town core centres ~(0,-25);
// expansion ground runs south and east into the dark.

export const ZONES = [
  { id: 'gate-ward', name: 'The Gate Ward', kind: 'founding',
    cx: 0, cz: -44, r: 9,
    note: 'The entrance: Surface Gate, gate road head, T3/T0 light.' },
  { id: 'founding-core', name: 'The Founding Core', kind: 'founding',
    cx: 0, cz: -25, r: 11,
    note: 'The first camp: Deep Ledger civic heart, stations, cots.' },
  { id: 'fungal-terraces', name: 'The Fungal Terraces', kind: 'founding',
    cx: -11, cz: -27, r: 8,
    note: 'West terraces: fungal nodes, herbalist, T2 spore light.' },
  { id: 'crystal-reach', name: 'The Crystal Reach', kind: 'founding',
    cx: 10, cz: -33, r: 8,
    note: 'East rise: crystal relay and the T4 heart-lantern.' },
  { id: 'magma-verge', name: 'The Magma Verge', kind: 'founding',
    cx: 11, cz: -13, r: 7,
    note: 'South-east warm corner: T5 thermal lamp, heat-pipe relay.' },
  { id: 'workshop-row', name: 'Workshop Row', kind: 'expansion',
    cx: 14, cz: -24, r: 7,
    note: 'Surveyed for future stations; ventilation staging in v1.' },
  { id: 'residential-edge', name: 'The Residential Edge', kind: 'expansion',
    cx: 0, cz: -4, r: 10,
    note: 'South of the core: first dwelling plots, unbuilt in v1.' },
  { id: 'south-meadow', name: 'The South Meadow', kind: 'expansion',
    cx: 2, cz: 16, r: 11,
    note: 'Open foreground ground between the town and the viewer.' },
  { id: 'deep-ward', name: 'The Deep-Ward', kind: 'expansion',
    cx: 19, cz: -42, r: 9,
    note: 'North-east, toward the dark: the direction delving goes.' },
];

export const PLOTS = [
  /* ------------------------------------------------ Gate Ward */
  { id: 'surface-gate', zone: 'gate-ward', asset: 'surface-gate',
    x: 0, z: -52, rotY: 0, note: 'The cave entrance (Adam: mandatory).' },
  { id: 'gate-lantern-t3', zone: 'gate-ward', asset: 'sealed-pressure-lantern',
    x: 2.8, z: -46, rotY: -0.5 },
  { id: 'gate-torch-t0', zone: 'gate-ward', asset: 'torch-on-a-stand',
    x: -2.7, z: -45, rotY: 0.4 },
  { id: 'gate-spine', zone: 'gate-ward', asset: 'piped-light-spine-segment',
    x: 1.7, z: -41, rotY: Math.PI / 2 },
  { id: 'gate-timber', zone: 'gate-ward', asset: 'timber-support-set',
    x: -6.2, z: -40, rotY: 0.35 },
  { id: 'gate-vent', zone: 'gate-ward', asset: 'ventilation-pieces',
    x: -4.6, z: -47.5, rotY: 0.5 },
  { id: 'gate-harness', zone: 'gate-ward', asset: 'harness-and-rope',
    x: -5.8, z: -39.4, y: 1.05, rotY: 0.35, noObstacle: true,
    note: 'Climbing harness hung on the gate timber.' },

  /* ---------------------------------------------- Founding Core */
  { id: 'core-spine', zone: 'founding-core', asset: 'piped-light-spine-segment',
    x: 1.7, z: -33.5, rotY: Math.PI / 2 },
  { id: 'deep-ledger', zone: 'founding-core', asset: 'deep-ledger',
    x: 0, z: -27.5, rotY: 0, note: 'The civic heart of the town.' },
  { id: 'core-lantern-t1', zone: 'founding-core', asset: 'lantern',
    x: -1.9, z: -23.8, rotY: 0.3 },
  { id: 'forge', zone: 'founding-core', asset: 'converter-forge',
    x: -4.6, z: -25.8, rotY: 0.55 },
  { id: 'forge-pickaxe', zone: 'founding-core', asset: 'miner-pickaxe',
    x: -3.7, z: -24.9, rotY: 0.4, rotZ: 0.32, noObstacle: true,
    note: 'Pickaxe leaning at the forge.' },
  { id: 'chandlery', zone: 'founding-core', asset: 'chandlery-bench',
    x: 4.7, z: -26.2, rotY: -0.55 },
  { id: 'chandlery-helmet-lamp', zone: 'founding-core', asset: 'miner-helmet-lamp',
    x: 4.7, z: -26.2, y: 1.08, rotY: 0.8, noObstacle: true,
    note: 'Helmet lamp resting on the chandlery bench.' },
  { id: 'kiln', zone: 'founding-core', asset: 'charcoal-kiln',
    x: -5.8, z: -21.2, rotY: 0.9 },
  { id: 'tailor', zone: 'founding-core', asset: 'tailor-bench',
    x: 5.9, z: -22.2, rotY: -0.9 },
  { id: 'tailor-spore-mask', zone: 'founding-core', asset: 'spore-mask',
    x: 5.9, z: -22.2, y: 1.08, rotY: -0.4, noObstacle: true,
    note: 'Finished spore mask on the tailor bench.' },
  { id: 'food-store', zone: 'founding-core', asset: 'sealed-food-store',
    x: -3.6, z: -30.8, rotY: 0.3 },
  { id: 'store-sickle', zone: 'founding-core', asset: 'farmer-sickle',
    x: -3.6, z: -30.8, y: 1.24, rotY: 2.4, rotX: -1.2, noObstacle: true,
    note: 'Sickle laid across the food store top.' },
  { id: 'store-pouch', zone: 'founding-core', asset: 'farmer-pouch',
    x: -2.7, z: -29.9, rotY: 0.6 },
  { id: 'cart', zone: 'founding-core', asset: 'cart',
    x: 3.4, z: -31.2, rotY: 1.25 },
  { id: 'cart-basket', zone: 'founding-core', asset: 'hauler-ore-basket',
    x: 2.5, z: -30, rotY: 1.9, note: 'Ore basket set down by the cart.' },
  { id: 'cot-1', zone: 'founding-core', asset: 'cot',
    x: -2.3, z: -20.6, rotY: 1.35 },
  { id: 'cot-1-boot-wraps', zone: 'founding-core', asset: 'quiet-gear-boot-wraps',
    x: -2.3, z: -20.6, y: 0.58, rotY: 1.3, noObstacle: true,
    note: 'Quiet gear laid out on the cot, ready for the dark.' },
  { id: 'cot-2', zone: 'founding-core', asset: 'cot',
    x: 2.5, z: -20.4, rotY: -1.2 },
  { id: 'cot-2-arm-wraps', zone: 'founding-core', asset: 'quiet-gear-arm-wraps',
    x: 2.5, z: -20.4, y: 0.58, rotY: -1.1, noObstacle: true },

  /* -------------------------------------------- Fungal Terraces */
  { id: 'fungal-lantern-t2', zone: 'fungal-terraces', asset: 'fungal-oil-lantern',
    x: -7.2, z: -27.8, rotY: 1.1 },
  { id: 'herbalist', zone: 'fungal-terraces', asset: 'herbalist-bench',
    x: -8.8, z: -30.8, rotY: 1.15 },
  { id: 'herbalist-bundle', zone: 'fungal-terraces', asset: 'herbalist-herb-bundle',
    x: -8.8, z: -30.8, y: 1.08, rotY: 1.7, rotX: -1.1, noObstacle: true,
    note: 'Herb bundle drying on the bench.' },
  { id: 'herbalist-satchel', zone: 'fungal-terraces', asset: 'herbalist-satchel',
    x: -7.8, z: -29.9, rotY: 2.8 },
  { id: 'fungal-node-1', zone: 'fungal-terraces', asset: 'fungal-node',
    x: -12.2, z: -28.5, rotY: 0.7 },
  { id: 'fungal-node-2', zone: 'fungal-terraces', asset: 'fungal-node',
    x: -14.2, z: -24, rotY: 2.2 },
  { id: 'fungal-node-3', zone: 'fungal-terraces', asset: 'fungal-node',
    x: -10.8, z: -22.2, rotY: 4.0 },
  { id: 'fungal-node-4', zone: 'fungal-terraces', asset: 'fungal-node',
    x: -13.4, z: -31.8, rotY: 1.4 },

  /* ---------------------------------------------- Crystal Reach */
  { id: 'crystal-lantern-t4', zone: 'crystal-reach', asset: 'crystal-heart-lantern',
    x: 7.2, z: -32.8, rotY: -1.0 },
  { id: 'crystal-relay', zone: 'crystal-reach', asset: 'crystal-relay',
    x: 10.6, z: -34.5, rotY: -0.7 },
  { id: 'crystal-timber', zone: 'crystal-reach', asset: 'timber-support-set',
    x: 6.4, z: -36.5, rotY: -0.3 },

  /* ------------------------------------------------ Magma Verge */
  { id: 'thermal-lamp-t5', zone: 'magma-verge', asset: 'thermal-lamp',
    x: 9.6, z: -13.2, rotY: -0.8 },
  { id: 'heat-pipe-relay', zone: 'magma-verge', asset: 'heat-pipe-relay',
    x: 12.2, z: -15.8, rotY: -1.2 },
  { id: 'cooling-vest', zone: 'magma-verge', asset: 'cooling-gear-vest',
    x: 8.5, z: -11.9, rotY: 2.2, note: 'Magma kit staged by the lamp.' },
  { id: 'cooling-gauntlets', zone: 'magma-verge', asset: 'cooling-gear-gauntlets',
    x: 9.2, z: -11.2, rotY: 0.9 },

  /* --------------------------------------------- Workshop Row */
  { id: 'workshop-vent', zone: 'workshop-row', asset: 'ventilation-pieces',
    x: 13.8, z: -24, rotY: -0.9, note: 'Ventilation staging for the row.' },
  { id: 'workshop-plot-1', zone: 'workshop-row', asset: null,
    x: 11, z: -20.5, rotY: 0, note: 'Expansion: unbuilt workshop plot.' },
  { id: 'workshop-plot-2', zone: 'workshop-row', asset: null,
    x: 15.5, z: -28.5, rotY: 0, note: 'Expansion: unbuilt workshop plot.' },

  /* ------------------------------------------- Residential Edge */
  { id: 'res-lantern-t1', zone: 'residential-edge', asset: 'lantern',
    x: 2.8, z: -5.5, rotY: 2.6, note: 'The street light of the new edge.' },
  { id: 'res-plot-1', zone: 'residential-edge', asset: null,
    x: -6, z: -4, rotY: 0, note: 'Expansion: unbuilt dwelling plot.' },
  { id: 'res-plot-2', zone: 'residential-edge', asset: null,
    x: 8.5, z: -2.5, rotY: 0, note: 'Expansion: unbuilt dwelling plot.' },
  { id: 'res-plot-3', zone: 'residential-edge', asset: null,
    x: -11, z: -9.5, rotY: 0, note: 'Expansion: unbuilt dwelling plot.' },

  /* ----------------------------------------------- South Meadow */
  { id: 'meadow-plot-1', zone: 'south-meadow', asset: null,
    x: -6, z: 14, rotY: 0, note: 'Expansion: open meadow ground.' },
  { id: 'meadow-plot-2', zone: 'south-meadow', asset: null,
    x: 9, z: 18, rotY: 0, note: 'Expansion: open meadow ground.' },

  /* -------------------------------------------------- Deep-Ward */
  { id: 'deep-timber', zone: 'deep-ward', asset: 'timber-support-set',
    x: 14, z: -41, rotY: 0.8, note: 'First shoring on the deep road.' },
  { id: 'deep-plot-1', zone: 'deep-ward', asset: null,
    x: 17, z: -45, rotY: 0, note: 'Expansion: unbuilt deep-ward plot.' },
  { id: 'deep-plot-2', zone: 'deep-ward', asset: null,
    x: 22, z: -37, rotY: 0, note: 'Expansion: unbuilt deep-ward plot.' },
];

/* The lantern network: the town's streets. Nodes are walk
   targets; edges are the lit routes creatures travel (each leg is
   obstacle-routed at walk time). `outer` nodes are where the
   Gloam Lurker will go — the network's dim rim. */
export const NETWORK = {
  nodes: [
    { id: 'gate', x: 0, z: -46.5 },
    { id: 'road1', x: 0, z: -40 },
    { id: 'road2', x: 0, z: -33.5 },
    { id: 'core', x: 0, z: -24.5 },
    { id: 'coreS', x: 0.8, z: -18.5 },
    { id: 'south', x: 2.5, z: -6 },
    { id: 'westF', x: -7, z: -27.5, outer: true },
    { id: 'westC', x: -8, z: -20.5 },
    { id: 'coreE', x: 5.5, z: -28.5 },
    { id: 'crystal', x: 6.2, z: -31.5, outer: true },
    { id: 'magma', x: 9, z: -12.8, outer: true },
  ],
  edges: [
    ['gate', 'road1'], ['road1', 'road2'], ['road2', 'core'],
    ['core', 'coreS'], ['coreS', 'south'],
    ['core', 'westF'], ['westF', 'westC'], ['westC', 'coreS'],
    ['core', 'coreE'], ['coreE', 'crystal'], ['coreE', 'magma'],
    ['magma', 'south'],
  ],
};

/* The v1 town state: every plot at its founding assignment. A
   future sim feed replaces assignments, not this file's shape. */
export const TOWN_STATE = {
  version: 1,
  era: 'founding',
  plots: Object.fromEntries(PLOTS.map((p) => [p.id, p.asset])),
};
