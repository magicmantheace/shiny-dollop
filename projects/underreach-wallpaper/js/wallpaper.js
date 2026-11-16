// The Underreach — a delving colony town, live desktop wallpaper.
//
// A cavern big enough for a small settlement. At its north end the
// Surface Gate stands in the rock; below it the founding town —
// the Deep Ledger at its civic heart, workshops and stores around
// it, cots and a cart, the lantern network for streets — and
// around the town, named districts of open ground where the
// settlement will grow. Creatures walk the network the way the
// game's nav graph works: node to node, inside the light. Beyond
// the lantern pools, dark.
//
// Sibling to projects/campfire-wallpaper/ and built on its
// patterns (seeded layout, clip-preferring creature director,
// grid A* + string-pulled obstacle routing, #status verification
// seam, wallpaper manners). It deliberately keeps the CLASSIC
// campfire lighting discipline rather than the AAA branch's
// shadow/bloom chain: no shadow maps, no post chain, and a hard
// budget of real lights (docs/TEST_PLAN.md) — every lantern
// beyond the few real ones is faked with glow sprites and
// light-pool decals, the way the classic build faked its fire.
//
// Data-driven by design (Adam, 2026-11-16): js/roster.js says
// WHAT exists (the roster rule: every gate-passed Game Asset
// Builder asset appears at least once), js/layout.js says WHERE
// it stands (named plots in named zones, in the shape of a town
// state a future living-world feed could drive — phase 2 is
// discussed, not commissioned; this build renders the founding
// state and talks to nothing).

import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import * as SkeletonUtils from 'three/addons/utils/SkeletonUtils.js';
import { ROSTER } from './roster.js';
import { ZONES, PLOTS, NETWORK, TOWN_STATE } from './layout.js';

/* ---------------------------------------------------------- utilities */

function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const layoutRand = mulberry32(20261116);
const rand = (a, b) => a + Math.random() * (b - a);

function lerpAngle(a, b, t) {
  let d = (b - a) % (Math.PI * 2);
  if (d > Math.PI) d -= Math.PI * 2;
  if (d < -Math.PI) d += Math.PI * 2;
  return a + d * t;
}

const PAGE_PARAMS = new URLSearchParams(location.search);
const statusEl = document.getElementById('status');
const loadingEl = document.getElementById('loading');

/* ------------------------------------------------------ cave floor */

// Uneven rock floor, flattened where the town actually stands and
// walks: the founding-core disc, the gate road corridor, and the
// south street. The same function lifts every prop and creature,
// so nothing floats or sinks.
function caveFloorH(x, z) {
  let h = Math.sin(x * 0.16) * 0.4 + Math.cos(z * 0.13) * 0.36 +
          Math.sin((x - z) * 0.07) * 0.5 + Math.sin(x * 0.41 + z * 0.23) * 0.12;
  let flat = THREE.MathUtils.smoothstep(Math.hypot(x, z + 25), 9, 30);
  if (z < -2 && z > -54) {          // the gate road corridor
    flat = Math.min(flat, THREE.MathUtils.smoothstep(Math.abs(x), 2.4, 10));
  }
  if (z < 4 && z > -20) {           // the south street to the edge
    flat = Math.min(flat, THREE.MathUtils.smoothstep(Math.abs(x - 1.5), 2.4, 9));
  }
  return h * flat;
}

/* ----------------------------------------------------------- renderer */

const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.3;
document.body.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x04060a);
scene.fog = new THREE.FogExp2(0x04060a, 0.0095);

const camera = new THREE.PerspectiveCamera(54, window.innerWidth / window.innerHeight, 0.1, 320);
const CAM_BASE = new THREE.Vector3(0, 10.5, 31);
const CAM_LOOK = new THREE.Vector3(0, 0.8, -21);
camera.position.copy(CAM_BASE);
camera.lookAt(CAM_LOOK);

/* ------------------------------------------------------------- lights */

// REAL LIGHT BUDGET: 1 hemisphere + 4 point lights, total. Every
// other lantern in the network is emissive + sprite + pool decal.
// (Measured cost notes: docs/TEST_PLAN.md.)
scene.add(new THREE.HemisphereLight(0x2b3648, 0x0a0806, 0.62));

function makePoint(color, intensity, distance, x, y, z) {
  const l = new THREE.PointLight(color, intensity, distance, 1.8);
  l.position.set(x, y, z);
  scene.add(l);
  return l;
}
// Town heart (the founding core's Tier-1 lantern) — warm, flickers.
const campLight = makePoint(0xffa845, 60, 19, -0.6, 2.6, -23.8);
// Surface Gate — a dim shaft of surface light, cool and steady.
const gateLight = makePoint(0x86a8d8, 30, 17, 0, 4.2, -47.5);
// Crystal relay, east rise — violet, slow pulse.
const relayLight = makePoint(0xa678ff, 34, 16, 9.8, 3.0, -33.6);
// Thermal lamp corner, south-east — molten orange, flickers.
const magmaLight = makePoint(0xff6a33, 36, 14, 9.9, 2.1, -13.8);
const REAL_LIGHT_COUNT = 5;   // hemi + 4 points

/* --------------------------------------------------- canvas textures */

function paintedTexture(base, tones, { size = 512, dabs = 1500, repeat = 6 } = {}) {
  const c = document.createElement('canvas');
  c.width = c.height = size;
  const g = c.getContext('2d');
  g.fillStyle = base;
  g.fillRect(0, 0, size, size);
  for (let i = 0; i < dabs; i++) {
    g.fillStyle = tones[Math.floor(layoutRand() * tones.length)];
    g.globalAlpha = 0.05 + layoutRand() * 0.13;
    const r = 4 + layoutRand() * 26;
    g.beginPath();
    g.ellipse(layoutRand() * size, layoutRand() * size, r, r * (0.5 + layoutRand() * 0.7),
      layoutRand() * Math.PI, 0, Math.PI * 2);
    g.fill();
  }
  g.globalAlpha = 1;
  const tex = new THREE.CanvasTexture(c);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.repeat.set(repeat, repeat);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

function radialSpriteTexture(inner, outer) {
  const c = document.createElement('canvas');
  c.width = c.height = 128;
  const g = c.getContext('2d');
  const grad = g.createRadialGradient(64, 64, 2, 64, 64, 64);
  grad.addColorStop(0, inner);
  grad.addColorStop(1, outer);
  g.fillStyle = grad;
  g.fillRect(0, 0, 128, 128);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}
const glowTex = radialSpriteTexture('rgba(255,255,255,1)', 'rgba(255,255,255,0)');
const blobTex = radialSpriteTexture('rgba(0,0,0,0.55)', 'rgba(0,0,0,0)');

/* -------------------------------------------------------- cave shell */

const rockTex = paintedTexture('#4a453e', ['#5a5348', '#3a362f', '#655c4e', '#2e2b26'], { repeat: 10 });
const wallTex = paintedTexture('#3d3a35', ['#4c463e', '#2f2c28', '#575046'], { repeat: 4 });
const rockMat = new THREE.MeshStandardMaterial({ map: rockTex, color: 0x9a938a, roughness: 1 });
const wallMat = new THREE.MeshStandardMaterial({ map: wallTex, color: 0x847d74, roughness: 1 });

function displaceGeo(geo, amt, freq) {
  const p = geo.attributes.position, v = new THREE.Vector3();
  for (let i = 0; i < p.count; i++) {
    v.fromBufferAttribute(p, i);
    const n = Math.sin(v.x * freq * 3.1 + v.y * freq * 1.7) *
              Math.sin(v.y * freq * 2.3 + v.z * freq * 2.9) *
              Math.sin(v.z * freq * 3.7 + v.x * freq * 1.3);
    v.multiplyScalar(1 + amt * n);
    p.setXYZ(i, v.x, v.y, v.z);
  }
  geo.computeVertexNormals();
  return geo;
}

{ // floor — a town-scale cavern, ~160 units across
  const geo = new THREE.CircleGeometry(82, 128, 0, Math.PI * 2);
  geo.rotateX(-Math.PI / 2);
  const p = geo.getAttribute('position');
  for (let i = 0; i < p.count; i++) {
    p.setY(i, caveFloorH(p.getX(i), p.getZ(i)));
  }
  geo.computeVertexNormals();
  const floor = new THREE.Mesh(geo, rockMat);
  floor.name = 'caveFloor';
  scene.add(floor);
}

{ // wall ring, ceiling, stalactites, rubble — all instanced
  const wallGeo = displaceGeo(new THREE.IcosahedronGeometry(1, 2), 0.22, 1.4);
  const walls = new THREE.InstancedMesh(wallGeo, wallMat, 40);
  const m = new THREE.Matrix4(), q = new THREE.Quaternion(),
    e = new THREE.Euler(), s = new THREE.Vector3(), pv = new THREE.Vector3();
  for (let i = 0; i < 40; i++) {
    const a = (i / 40) * Math.PI * 2 + (layoutRand() - 0.5) * 0.1;
    const r = 76 + layoutRand() * 6;
    const sx = 10 + layoutRand() * 9, sy = 10 + layoutRand() * 10, sz = 8 + layoutRand() * 6;
    pv.set(Math.cos(a) * r, sy * 0.3 - 2, Math.sin(a) * r);
    e.set(0, layoutRand() * Math.PI, 0); q.setFromEuler(e);
    s.set(sx, sy, sz);
    m.compose(pv, q, s);
    walls.setMatrixAt(i, m);
  }
  walls.name = 'caveWalls';
  scene.add(walls);

  const ceil = new THREE.Mesh(new THREE.CircleGeometry(88, 32),
    new THREE.MeshBasicMaterial({ color: 0x05070b }));
  ceil.rotation.x = Math.PI / 2;
  ceil.position.y = 26;
  scene.add(ceil);
  const stalGeo = new THREE.ConeGeometry(0.6, 4.2, 7);
  const stal = new THREE.InstancedMesh(stalGeo, wallMat, 60);
  for (let i = 0; i < 60; i++) {
    const a = layoutRand() * Math.PI * 2;
    const r = 18 + layoutRand() * 55;
    const len = 0.7 + layoutRand() * 1.4;
    pv.set(Math.cos(a) * r, 26 - 2.1 * len, Math.sin(a) * r);
    e.set(Math.PI, 0, 0); q.setFromEuler(e);
    s.set(0.8 + layoutRand(), len, 0.8 + layoutRand());
    m.compose(pv, q, s);
    stal.setMatrixAt(i, m);
  }
  scene.add(stal);

  const rubbleGeo = displaceGeo(new THREE.DodecahedronGeometry(1, 1), 0.16, 1.7);
  const rubble = new THREE.InstancedMesh(rubbleGeo, rockMat, 70);
  for (let i = 0; i < 70; i++) {
    const a = layoutRand() * Math.PI * 2;
    const r = 26 + layoutRand() * 44;
    const x = Math.cos(a) * r, z = Math.sin(a) * r;
    const sc = 0.35 + layoutRand() * 1.5;
    pv.set(x, caveFloorH(x, z) + sc * 0.2, z);
    e.set(layoutRand() * 3, layoutRand() * 3, layoutRand() * 3); q.setFromEuler(e);
    s.set(sc, sc * (0.6 + layoutRand() * 0.5), sc);
    m.compose(pv, q, s);
    rubble.setMatrixAt(i, m);
  }
  scene.add(rubble);
}

/* ------------------------------------------------------------ particles */

// Dust motes drifting over the town + a green spore shimmer over
// the fungal terraces. Two small Points systems, additive.
function makeParticles(count, size, color, opacity) {
  const geo = new THREE.BufferGeometry();
  const pos = new Float32Array(count * 3);
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  const mat = new THREE.PointsMaterial({
    size, color, transparent: true, opacity, depthWrite: false,
    blending: THREE.AdditiveBlending, map: glowTex, sizeAttenuation: true });
  const pts = new THREE.Points(geo, mat);
  pts.frustumCulled = false;
  scene.add(pts);
  return { pts, pos, count };
}
const dust = makeParticles(150, 0.16, 0xd8c9a8, 0.32);
for (let i = 0; i < dust.count; i++) {
  dust.pos[i * 3] = rand(-30, 30); dust.pos[i * 3 + 1] = rand(0.3, 7);
  dust.pos[i * 3 + 2] = rand(-56, 10);
}
const spores = makeParticles(50, 0.18, 0x63ffb4, 0.5);
for (let i = 0; i < spores.count; i++) {
  spores.pos[i * 3] = rand(-18, -7); spores.pos[i * 3 + 1] = rand(0.3, 3.4);
  spores.pos[i * 3 + 2] = rand(-34, -18);
}
function updateParticles(sys, t, drift, sink, ceilY) {
  const p = sys.pos;
  for (let i = 0; i < sys.count; i++) {
    p[i * 3] += Math.sin(t * 0.24 + i * 1.7) * drift;
    p[i * 3 + 1] += Math.cos(t * 0.17 + i * 2.3) * drift * 0.6 - sink;
    if (p[i * 3 + 1] < 0.15) p[i * 3 + 1] = ceilY;
    if (p[i * 3 + 1] > ceilY + 1) p[i * 3 + 1] = 0.3;
  }
  sys.pts.geometry.getAttribute('position').needsUpdate = true;
}

/* ------------------------------------------------- obstacle routing */

// The campfire build's planner, carried over with its semantics
// intact (docs/TEST_PLAN.md there has the geometry battery that
// justifies the design): A* over a coarse grid + string-pulling
// against segBlocker(), so every emitted leg is exactly validated
// against every obstacle. Planning runs once per trip leg.
const OBSTACLES = [];
function addObstacle(x, z, r) { OBSTACLES.push({ x, z, r }); }

function segBlocker(ax, az, bx, bz, margin, isFinalLeg) {
  const abx = bx - ax, abz = bz - az;
  const l2 = abx * abx + abz * abz;
  let best = null, bestT = Infinity;
  for (const o of OBSTACLES) {
    const R = o.r + margin;
    if (Math.hypot(o.x - ax, o.z - az) < R) continue;
    if (isFinalLeg && Math.hypot(o.x - bx, o.z - bz) < R) continue;
    let t = l2 > 0 ? ((o.x - ax) * abx + (o.z - az) * abz) / l2 : 0;
    t = Math.max(0, Math.min(1, t));
    const cx = ax + abx * t, cz = az + abz * t;
    if (Math.hypot(o.x - cx, o.z - cz) < R && t < bestT) {
      best = o; bestT = t;
    }
  }
  return best;
}

const ROUTE_CELL = 0.5;
const ROUTE_HALF = 48;                 // grid covers [-48, 48]^2
const ROUTE_N = Math.round((ROUTE_HALF * 2) / ROUTE_CELL);

function routeCellIndex(x, z) {
  const ix = Math.max(0, Math.min(ROUTE_N - 1,
    Math.floor((x + ROUTE_HALF) / ROUTE_CELL)));
  const iz = Math.max(0, Math.min(ROUTE_N - 1,
    Math.floor((z + ROUTE_HALF) / ROUTE_CELL)));
  return iz * ROUTE_N + ix;
}
function routeCellCentre(ci) {
  return {
    x: -ROUTE_HALF + (ci % ROUTE_N + 0.5) * ROUTE_CELL,
    z: -ROUTE_HALF + (Math.floor(ci / ROUTE_N) + 0.5) * ROUTE_CELL,
  };
}
function projectOutOfObstacles(x, z, margin) {
  let px = x, pz = z;
  for (let k = 0; k < 8; k++) {
    let moved = false;
    for (const p of OBSTACLES) {
      const dx = px - p.x, dz = pz - p.z;
      const d = Math.hypot(dx, dz), R = p.r + margin;
      if (d < R) {
        if (d > 1e-6) { px = p.x + dx * (R + 0.05) / d; pz = p.z + dz * (R + 0.05) / d; }
        else px = p.x + R + 0.05;
        moved = true;
      }
    }
    if (!moved) break;
  }
  return { x: px, z: pz };
}
function buildRouteGrid(margin, bx, bz) {
  const grid = new Uint8Array(ROUTE_N * ROUTE_N);
  for (const o of OBSTACLES) {
    const R = o.r + margin;
    if (Math.hypot(bx - o.x, bz - o.z) < R) continue;
    const Ri = R + 0.36;
    const x0 = Math.max(0, Math.floor((o.x - Ri + ROUTE_HALF) / ROUTE_CELL));
    const x1 = Math.min(ROUTE_N - 1, Math.floor((o.x + Ri + ROUTE_HALF) / ROUTE_CELL));
    const z0 = Math.max(0, Math.floor((o.z - Ri + ROUTE_HALF) / ROUTE_CELL));
    const z1 = Math.min(ROUTE_N - 1, Math.floor((o.z + Ri + ROUTE_HALF) / ROUTE_CELL));
    for (let iz = z0; iz <= z1; iz++) {
      for (let ix = x0; ix <= x1; ix++) {
        const d = Math.hypot(-ROUTE_HALF + (ix + 0.5) * ROUTE_CELL - o.x,
          -ROUTE_HALF + (iz + 0.5) * ROUTE_CELL - o.z);
        const v = d < R ? 2 : (d < Ri ? 1 : 0);
        const ci = iz * ROUTE_N + ix;
        if (v > grid[ci]) grid[ci] = v;
      }
    }
  }
  return grid;
}
function gridAStar(grid, s, g) {
  const size = ROUTE_N * ROUTE_N;
  const gScore = new Float64Array(size).fill(Infinity);
  const came = new Int32Array(size).fill(-1);
  const closed = new Uint8Array(size);
  const gx = g % ROUTE_N, gz = Math.floor(g / ROUTE_N);
  const heapF = [], heapI = [];
  function heapPush(f, i) {
    heapF.push(f); heapI.push(i);
    let c = heapF.length - 1;
    while (c > 0) {
      const p = (c - 1) >> 1;
      if (heapF[p] <= heapF[c]) break;
      const tf = heapF[p]; heapF[p] = heapF[c]; heapF[c] = tf;
      const ti = heapI[p]; heapI[p] = heapI[c]; heapI[c] = ti;
      c = p;
    }
  }
  function heapPop() {
    const top = heapI[0];
    const lf = heapF.pop(), li = heapI.pop();
    if (heapF.length) {
      heapF[0] = lf; heapI[0] = li;
      let c = 0;
      for (;;) {
        const l = c * 2 + 1, r = l + 1;
        let m = c;
        if (l < heapF.length && heapF[l] < heapF[m]) m = l;
        if (r < heapF.length && heapF[r] < heapF[m]) m = r;
        if (m === c) break;
        const tf = heapF[m]; heapF[m] = heapF[c]; heapF[c] = tf;
        const ti = heapI[m]; heapI[m] = heapI[c]; heapI[c] = ti;
        c = m;
      }
    }
    return top;
  }
  const DIRS = [[1, 0, 1], [-1, 0, 1], [0, 1, 1], [0, -1, 1],
    [1, 1, Math.SQRT2], [1, -1, Math.SQRT2],
    [-1, 1, Math.SQRT2], [-1, -1, Math.SQRT2]];
  gScore[s] = 0;
  heapPush(Math.hypot((s % ROUTE_N) - gx, Math.floor(s / ROUTE_N) - gz), s);
  while (heapI.length) {
    const cur = heapPop();
    if (closed[cur]) continue;
    closed[cur] = 1;
    if (cur === g) {
      const path = [];
      for (let c = g; c !== -1; c = came[c]) path.push(c);
      return path.reverse();
    }
    const cx = cur % ROUTE_N, cz = Math.floor(cur / ROUTE_N);
    for (const [dx, dz, w] of DIRS) {
      const nx = cx + dx, nz = cz + dz;
      if (nx < 0 || nz < 0 || nx >= ROUTE_N || nz >= ROUTE_N) continue;
      const ni = nz * ROUTE_N + nx;
      if (closed[ni]) continue;
      if (grid[ni] === 2 && ni !== g) continue;
      if (dx && dz) {
        const o1 = cz * ROUTE_N + nx, o2 = nz * ROUTE_N + cx;
        if ((grid[o1] === 2 && o1 !== g) || (grid[o2] === 2 && o2 !== g)) continue;
      }
      const ng = gScore[cur] + w * (grid[ni] === 1 ? 6 : 1);
      if (ng < gScore[ni]) {
        gScore[ni] = ng;
        came[ni] = cur;
        heapPush(ng + Math.hypot(nx - gx, nz - gz), ni);
      }
    }
  }
  return null;
}
function planRoute(ax, az, bx, bz, margin) {
  const start = projectOutOfObstacles(ax, az, margin);
  const grid = buildRouteGrid(margin, bx, bz);
  const s = routeCellIndex(start.x, start.z);
  const g = routeCellIndex(bx, bz);
  grid[s] = 0; grid[g] = 0;
  const cells = gridAStar(grid, s, g);
  if (!cells) return [{ x: bx, z: bz }];
  const pts = [{ x: start.x, z: start.z }];
  for (const ci of cells) {
    const c = routeCellCentre(ci);
    const last = pts[pts.length - 1];
    if (Math.hypot(c.x - last.x, c.z - last.z) > 0.01) pts.push(c);
  }
  const dest = { x: bx, z: bz };
  const tail = pts[pts.length - 1];
  if (Math.hypot(dest.x - tail.x, dest.z - tail.z) > 0.01) pts.push(dest);
  else pts[pts.length - 1] = dest;
  const out = [];
  if (start.x !== ax || start.z !== az) out.push({ x: start.x, z: start.z });
  let cur = pts[0], curIdx = 0;
  while (curIdx < pts.length - 1) {
    let advanced = false;
    for (let j = pts.length - 1; j > curIdx; j--) {
      if (!segBlocker(cur.x, cur.z, pts[j].x, pts[j].z, margin,
        j === pts.length - 1)) {
        out.push(pts[j]); cur = pts[j]; curIdx = j; advanced = true;
        break;
      }
    }
    if (!advanced) { curIdx++; out.push(pts[curIdx]); cur = pts[curIdx]; }
  }
  return out;
}

/* -------------------------------------------------- the network graph */

const NODES = new Map(NETWORK.nodes.map((n) => [n.id, n]));
const NEIGHBOURS = new Map(NETWORK.nodes.map((n) => [n.id, []]));
for (const [a, b] of NETWORK.edges) {
  NEIGHBOURS.get(a).push(b);
  NEIGHBOURS.get(b).push(a);
}
// Breadth-first node path from -> to (ids), or null.
function nodePath(from, to) {
  if (from === to) return [from];
  const prev = new Map([[from, null]]);
  const queue = [from];
  while (queue.length) {
    const cur = queue.shift();
    for (const nb of NEIGHBOURS.get(cur)) {
      if (prev.has(nb)) continue;
      prev.set(nb, cur);
      if (nb === to) {
        const path = [to];
        for (let c = cur; c !== null; c = prev.get(c)) path.unshift(c);
        return path;
      }
      queue.push(nb);
    }
  }
  return null;
}

/* -------------------------------------------------------- asset loading */

const loader = new GLTFLoader();
const loadErrors = [];
const MAX_ANISO = Math.min(8, renderer.capabilities.getMaxAnisotropy());
function sharpenTextures(root) {
  root.traverse((o) => {
    if (!o.isMesh) return;
    const mats = Array.isArray(o.material) ? o.material : [o.material];
    for (const m of mats) {
      for (const key of ['map', 'normalMap', 'roughnessMap',
                         'metalnessMap', 'emissiveMap', 'aoMap']) {
        const tex = m[key];
        if (tex) { tex.anisotropy = MAX_ANISO; tex.needsUpdate = true; }
      }
    }
  });
}
function findClip(animations, names) {
  const lower = animations.map((a) => a.name.toLowerCase());
  for (const n of names) {
    const i = lower.indexOf(n);
    if (i >= 0) return animations[i];
  }
  for (const n of names) {
    const i = lower.findIndex((a) => a.includes(n));
    if (i >= 0) return animations[i];
  }
  return null;
}
function loadGLB(slug) {
  return new Promise((resolve) => {
    loader.load('assets/' + slug + '.glb', (gltf) => {
      sharpenTextures(gltf.scene);
      resolve(gltf);
    }, undefined, (err) => {
      loadErrors.push(slug + ': ' + ((err && err.message) || err));
      resolve(null);
    });
  });
}
// Normalize a loaded scene: uniform scale to the target height,
// feet on y=0, centred on x/z. Returns { holder, size } where size
// is the SCALED bounding size (for obstacle radii).
function normalize(srcScene, height, rotX = 0, rotZ = 0) {
  const inner = srcScene;
  inner.rotation.set(rotX, 0, rotZ);
  const box = new THREE.Box3().setFromObject(inner);
  const size = box.getSize(new THREE.Vector3());
  inner.scale.setScalar(height / (size.y || 1));
  const b2 = new THREE.Box3().setFromObject(inner);
  const s2 = b2.getSize(new THREE.Vector3());
  inner.position.set(-(b2.min.x + b2.max.x) / 2, -b2.min.y, -(b2.min.z + b2.max.z) / 2);
  const holder = new THREE.Group();
  holder.add(inner);
  return { holder, size: s2 };
}

/* ------------------------------------------------------------ fake light */

const flickerGlows = [];   // {sprite, pool, baseS, baseO, phase, speed}
function addGlow(x, z, height, glow, flicker) {
  const y = caveFloorH(x, z);
  const pool = new THREE.Mesh(new THREE.CircleGeometry(glow.pool, 26),
    new THREE.MeshBasicMaterial({
      map: glowTex, color: glow.color, transparent: true, opacity: 0.30,
      blending: THREE.AdditiveBlending, depthWrite: false }));
  pool.rotation.x = -Math.PI / 2;
  pool.position.set(x, y + 0.06, z);
  pool.renderOrder = 2;
  scene.add(pool);
  const sm = new THREE.SpriteMaterial({
    map: glowTex, color: glow.color, transparent: true, opacity: 0.5,
    blending: THREE.AdditiveBlending, depthWrite: false });
  const sprite = new THREE.Sprite(sm);
  sprite.position.set(x, y + height * glow.at, z);
  sprite.scale.setScalar(glow.sprite);
  scene.add(sprite);
  // a small hot core at the flame point
  const core = new THREE.Sprite(new THREE.SpriteMaterial({
    map: glowTex, color: 0xfff2d8, transparent: true, opacity: 0.85,
    blending: THREE.AdditiveBlending, depthWrite: false }));
  core.position.copy(sprite.position);
  core.scale.setScalar(glow.sprite * 0.32);
  scene.add(core);
  if (flicker) {
    flickerGlows.push({ sprite, core, pool,
      baseS: glow.sprite, phase: Math.random() * 10, speed: flicker });
  }
  return { sprite, pool };
}
function updateGlows(t) {
  for (const g of flickerGlows) {
    const n = Math.sin(t * g.speed + g.phase) * 0.5 +
              Math.sin(t * g.speed * 2.7 + g.phase * 1.7) * 0.3 +
              Math.sin(t * g.speed * 6.1 + g.phase * 0.6) * 0.2;
    const k = 1 + n * 0.13;
    g.sprite.scale.setScalar(g.baseS * k);
    g.sprite.material.opacity = 0.5 + n * 0.09;
    g.core.material.opacity = 0.85 + n * 0.12;
    g.pool.material.opacity = 0.30 + n * 0.045;
  }
  relayLight.intensity = 34 + Math.sin(t * 0.7) * 7;
  campLight.intensity = 60 + Math.sin(t * 9.3) * 5 + Math.sin(t * 23.7) * 3;
  magmaLight.intensity = 36 + Math.sin(t * 7.1 + 2) * 5 + Math.sin(t * 17.3) * 3;
}

/* --------------------------------------------------------- town builder */

// Build every occupied plot in the town state. Assets load once
// per slug and are cloned per plot (shared geometry/materials).
// A failed load degrades: the plot stands empty, the error is in
// the status feed, the town still renders.
const placedCount = {};      // slug -> instances placed
let plotsBuilt = 0;

async function buildTown() {
  const bySlug = new Map();  // slug -> [plots]
  for (const plot of PLOTS) {
    const slug = TOWN_STATE.plots[plot.id];
    if (!slug) continue;
    if (!bySlug.has(slug)) bySlug.set(slug, []);
    bySlug.get(slug).push(plot);
  }
  const rosterBySlug = new Map(ROSTER.map((r) => [r.slug, r]));
  await Promise.all([...bySlug.entries()].map(async ([slug, plots]) => {
    const cfg = rosterBySlug.get(slug);
    const gltf = await loadGLB(slug);
    if (!gltf || !cfg) return;
    for (const plot of plots) {
      const inner = gltf.scene.clone(true);
      if (cfg.glowShroom) {
        inner.traverse((o) => {
          if (o.isMesh && o.material) {
            o.material = o.material.clone();
            if (o.material.emissive) {
              o.material.emissive = new THREE.Color(0x1f7a4d);
              o.material.emissiveIntensity = 0.55;
            }
          }
        });
      }
      const { holder, size } = normalize(inner, cfg.height, plot.rotX || 0, plot.rotZ || 0);
      holder.position.set(plot.x, caveFloorH(plot.x, plot.z) + (plot.y || 0), plot.z);
      holder.rotation.y = plot.rotY || 0;
      scene.add(holder);
      placedCount[slug] = (placedCount[slug] || 0) + 1;
      plotsBuilt++;
      if (!plot.noObstacle) {
        const r = THREE.MathUtils.clamp(
          0.5 * Math.hypot(size.x, size.z) * 0.72, 0.3, 3.4);
        addObstacle(plot.x, plot.z, r);
      }
      if (cfg.glow) addGlow(plot.x, plot.z, cfg.height, cfg.glow,
        cfg.kind === 'lantern' ? 7 + Math.random() * 4 : 0);
      if (cfg.glowShroom) {
        addGlow(plot.x, plot.z, cfg.height,
          { color: 0x2affa0, pool: 1.7, sprite: 1.15, at: 0.82 }, 1.6);
      }
      if (slug === 'surface-gate') {
        // the surface shaft: one big cool halo in the gate arch
        const halo = new THREE.Sprite(new THREE.SpriteMaterial({
          map: glowTex, color: 0x86a8d8, transparent: true, opacity: 0.16,
          blending: THREE.AdditiveBlending, depthWrite: false }));
        halo.position.set(plot.x, caveFloorH(plot.x, plot.z) + 3.4, plot.z + 1.5);
        halo.scale.set(9, 7, 1);
        scene.add(halo);
      }
    }
  }));
}

/* ------------------------------------------------------ creature templates */

const templates = new Map();   // slug -> { cfg, holder, clips }
async function loadCreature(cfg) {
  const gltf = await loadGLB(cfg.slug);
  if (!gltf) return;
  const { holder } = normalize(gltf.scene, cfg.height);
  const anims = gltf.animations || [];
  templates.set(cfg.slug, {
    cfg, holder,
    clips: {
      idle: findClip(anims, ['idle']),
      walk: findClip(anims, ['walk']),
      signature: findClip(anims, [cfg.signature]),
    },
  });
}

/* ------------------------------------------------------------ creatures */

// Walkers live on the network: they travel node to node along the
// graph (each leg obstacle-routed), dwell in the light, and after
// a few trips leave — north through the gate, south into the dark,
// or (the lurker) sideways into the rim dark. Spawn points are the
// same mouths: the gate, the south street end, the rim.
const BOB = { 'gloam-rat': 0.03, 'delver': 0.05, 'frontier-bearer': 0.02, 'gloam-lurker': 0.03 };
const EXIT_POINTS = {
  gate: { x: 0, z: -48.5 },
  south: { x: 2.5, z: 9.5 },
  rimW: { x: -25, z: -17 },
  rimE: { x: 25, z: -31 },
};
let instanceSeq = 0;

class Creature {
  constructor(tpl, startNodeId, startPos, startState) {
    this.tpl = tpl;
    this.cfg = tpl.cfg;
    this.id = ++instanceSeq;
    this.node = startNodeId;              // node id when dwelling
    this.group = new THREE.Group();
    this.model = SkeletonUtils.clone(tpl.holder);
    this.group.add(this.model);
    const shadow = new THREE.Mesh(
      new THREE.PlaneGeometry(1, 1),
      new THREE.MeshBasicMaterial({
        map: blobTex, transparent: true, depthWrite: false, opacity: 0.3 }));
    shadow.rotation.x = -Math.PI / 2;
    shadow.position.y = 0.03;
    shadow.scale.setScalar(this.cfg.height * 1.6);
    this.group.add(shadow);
    this.group.position.set(startPos.x, caveFloorH(startPos.x, startPos.z), startPos.z);
    scene.add(this.group);
    this.mixer = new THREE.AnimationMixer(this.model);
    this.actions = {};
    for (const role of ['idle', 'walk', 'signature']) {
      const clip = tpl.clips[role];
      if (clip) this.actions[role] = this.mixer.clipAction(clip);
    }
    this.currentRole = null;
    this.mixer.addEventListener('finished', () => {
      if (this.state === 'dwell' && this.currentRole === 'signature') this.play('idle');
    });
    this.yaw = rand(0, Math.PI * 2);
    this.targetYaw = this.yaw;
    this.route = [];
    this.legQueue = [];                   // remaining node ids to visit
    this.tripsLeft = 2 + Math.floor(Math.random() * 3);
    this.state = 'dwell';
    if (startState === 'dwell') this.enterDwell();
    else this.chooseTrip();
  }

  play(role, once = false) {
    const action = this.actions[role];
    if (!action) return;
    if (this.currentRole === role && !once) return;
    const prev = this.currentRole ? this.actions[this.currentRole] : null;
    action.reset();
    action.setLoop(once ? THREE.LoopOnce : THREE.LoopRepeat, once ? 1 : Infinity);
    action.clampWhenFinished = once;
    action.fadeIn(0.3).play();
    if (prev && prev !== action) prev.fadeOut(0.3);
    this.currentRole = role;
  }

  pickDestination() {
    const ids = NETWORK.nodes
      .filter((n) => n.id !== this.node && (!this.cfg.outerOnly || n.outer || n.id === 'gate'))
      .map((n) => n.id);
    return ids[Math.floor(Math.random() * ids.length)];
  }

  chooseTrip() {
    const dest = this.pickDestination();
    const path = nodePath(this.node, dest);
    if (!path || path.length < 2) { this.enterDwell(); return; }
    this.legQueue = path.slice(1);
    this.state = 'travel';
    this.startLeg();
  }

  startLeg() {
    const nextId = this.legQueue[0];
    const n = NODES.get(nextId);
    const pos = this.group.position;
    const margin = 0.30 + this.cfg.height * 0.15;
    // dwell points sit a step off the node centre so walkers do
    // not stack on the same stone
    this.legTarget = {
      x: n.x + rand(-0.5, 0.5), z: n.z + rand(-0.5, 0.5), id: nextId };
    this.route = planRoute(pos.x, pos.z, this.legTarget.x, this.legTarget.z, margin);
    if (this.actions.walk) this.play('walk');
    else this.play('idle');
  }

  enterDwell() {
    this.state = 'dwell';
    this.dwellLeft = this.cfg.slug === 'gloam-rat' ? rand(5, 13) : rand(10, 28);
    this.signatureIn = rand(4, 9);
    this.play('idle');
    // Face the town heart, or the nearest light: dwellers look
    // toward the light they stand in.
    const p = this.group.position;
    this.targetYaw = Math.atan2(0 - p.x, -25 - p.z);
  }

  startLeaving() {
    this.state = 'leave';
    const exit = this.cfg.outerOnly
      ? (Math.random() < 0.5 ? EXIT_POINTS.rimW : EXIT_POINTS.rimE)
      : (Math.random() < 0.55 ? EXIT_POINTS.gate : EXIT_POINTS.south);
    this.legQueue = [];
    const pos = this.group.position;
    const margin = 0.30 + this.cfg.height * 0.15;
    this.route = planRoute(pos.x, pos.z, exit.x, exit.z, margin);
    this.legTarget = { x: exit.x, z: exit.z, id: null };
    if (this.actions.walk) this.play('walk');
    else this.play('idle');
  }

  // Follow this.route toward this.legTarget. Returns 'arrived' |
  // 'walking'.
  followRoute(dt, t) {
    const pos = this.group.position;
    while (this.route.length > 1 &&
           Math.hypot(this.route[0].x - pos.x, this.route[0].z - pos.z) <= 0.4) {
      this.route.shift();
    }
    if (!this.route.length) return 'arrived';
    const goal = this.route[0];
    const dx = goal.x - pos.x, dz = goal.z - pos.z;
    const dist = Math.hypot(dx, dz);
    if (this.route.length === 1 && dist <= 0.15) return 'arrived';
    const heading = Math.atan2(dx, dz);
    this.yaw = lerpAngle(this.yaw, heading, Math.min(1, dt * 5));
    let bob = 0;
    if (!this.actions.walk) bob = Math.sin(t * 2.3 + this.id) * (BOB[this.cfg.slug] || 0.03);
    pos.x += Math.sin(heading) * this.cfg.speed * dt;
    pos.z += Math.cos(heading) * this.cfg.speed * dt;
    pos.y = caveFloorH(pos.x, pos.z) + bob;
    return 'walking';
  }

  update(dt, t) {
    this.mixer.update(dt);
    const pos = this.group.position;
    if (this.state === 'travel') {
      if (this.followRoute(dt, t) === 'arrived') {
        this.node = this.legTarget.id;
        this.legQueue.shift();
        if (this.legQueue.length) this.startLeg();
        else {
          this.tripsLeft--;
          this.enterDwell();
        }
      }
    } else if (this.state === 'leave') {
      if (this.followRoute(dt, t) === 'arrived') return false;
    } else { // dwell
      pos.y = caveFloorH(pos.x, pos.z);
      this.yaw = lerpAngle(this.yaw, this.targetYaw, Math.min(1, dt * 3));
      this.dwellLeft -= dt;
      this.signatureIn -= dt;
      if (this.signatureIn <= 0 && this.currentRole === 'idle') {
        this.play('signature', true);
        this.signatureIn = rand(7, 15);
      }
      if (this.dwellLeft <= 0) {
        if (this.tripsLeft <= 0) this.startLeaving();
        else this.chooseTrip();
      }
    }
    this.group.rotation.y = this.yaw;
    return true;
  }

  dispose() {
    scene.remove(this.group);
    this.mixer.stopAllAction();
    this.mixer.uncacheRoot(this.model);
  }
}

/* -------------------------------------------------------------- director */

const MAX_ACTIVE = 4;
const active = [];
let spawnTimer = 1.0;

function spawn(initial) {
  const loaded = [...templates.values()];
  if (!loaded.length) return;
  const counts = {};
  for (const c of active) counts[c.cfg.slug] = (counts[c.cfg.slug] || 0) + 1;
  const caps = { 'gloam-lurker': 1, 'frontier-bearer': 1, 'gloam-rat': 2, 'delver': 2 };
  const pool = loaded.filter((tpl) => (counts[tpl.cfg.slug] || 0) < (caps[tpl.cfg.slug] ?? 2));
  if (!pool.length) return;
  const totalW = pool.reduce((s, tpl) => s + (tpl.cfg.weight || 1), 0);
  let pick = Math.random() * totalW, tpl = pool[0];
  for (const cand of pool) { pick -= cand.cfg.weight || 1; if (pick <= 0) { tpl = cand; break; } }

  let startPos, startNode, state;
  if (initial === 'dwell') {
    startNode = 'core';
    const n = NODES.get('core');
    startPos = { x: n.x + rand(-1.5, 1.5), z: n.z + rand(-1.5, 1.5) };
    state = 'dwell';
  } else if (tpl.cfg.outerOnly) {
    const rim = Math.random() < 0.5 ? EXIT_POINTS.rimW : EXIT_POINTS.rimE;
    startPos = { x: rim.x, z: rim.z };
    startNode = Math.random() < 0.5 ? 'westF' : 'crystal';
    state = 'travel-in';
  } else if (Math.random() < 0.55) {
    startPos = { x: EXIT_POINTS.gate.x, z: EXIT_POINTS.gate.z };
    startNode = 'gate';
    state = 'travel-in';
  } else {
    startPos = { x: EXIT_POINTS.south.x, z: EXIT_POINTS.south.z };
    startNode = 'south';
    state = 'travel-in';
  }
  const c = new Creature(tpl, startNode, startPos, state === 'dwell' ? 'dwell' : 'travel');
  if (state === 'travel-in') {
    // walk in toward a first destination instead of dwelling at
    // the mouth
    c.node = startNode;
    c.chooseTrip();
  }
  active.push(c);
}

function updateDirector(dt, t) {
  for (let i = active.length - 1; i >= 0; i--) {
    if (!active[i].update(dt, t)) {
      active[i].dispose();
      active.splice(i, 1);
    }
  }
  if (active.length < MAX_ACTIVE && templates.size) {
    spawnTimer -= dt;
    if (spawnTimer <= 0) {
      spawn(false);
      spawnTimer = active.length === 0 ? 2.5 : rand(7, 15);
    }
  }
}

/* -------------------------------------------------------------- main loop */

const clock = new THREE.Clock();
let perfNow = 0;
let frames = 0, fpsTimer = 0, fps = 0;
let statusTimer = 0;
let firstFrame = true;

function tick() {
  const dt = Math.min(clock.getDelta(), 0.05);
  perfNow = performance.now();
  const t = clock.elapsedTime;

  updateGlows(t);
  updateParticles(dust, t, 0.0016, 0.0006, 6.5);
  updateParticles(spores, t, 0.0012, -0.0002, 3.2);
  updateDirector(dt, t);

  camera.position.set(
    CAM_BASE.x + Math.sin(t * 0.04) * 0.8,
    CAM_BASE.y + Math.sin(t * 0.053 + 1.3) * 0.3,
    CAM_BASE.z);
  camera.lookAt(CAM_LOOK);

  renderer.render(scene, camera);
  if (firstFrame) {
    firstFrame = false;
    loadingEl.classList.add('done');
  }
  frames++; fpsTimer += dt; statusTimer += dt;
  if (fpsTimer >= 0.5) { fps = Math.round(frames / fpsTimer); frames = 0; fpsTimer = 0; }
  if (statusTimer >= 0.5) { statusTimer = 0; publishStatus(); }
}

function publishStatus() {
  const s = {
    ready: true, fps,
    era: TOWN_STATE.era,
    zones: ZONES.map((z) => z.id),
    plotsBuilt,
    rosterLoaded: [...Object.keys(placedCount), ...templates.keys()]
      .filter((v, i, a) => a.indexOf(v) === i),
    rosterPlaced: placedCount,
    // The roster rule, checked by the page itself: every roster
    // slug with zero instances (statics) or no loaded template
    // (creatures) is listed here. Empty = rule satisfied.
    rosterMissing: ROSTER
      .filter((r) => r.kind === 'creature'
        ? !templates.has(r.slug) : !(placedCount[r.slug] > 0))
      .map((r) => r.slug),
    loadErrors,
    realLights: REAL_LIGHT_COUNT,
    creatures: active.map((c) => ({
      slug: c.cfg.slug, state: c.state, clip: c.currentRole,
      x: +c.group.position.x.toFixed(2), z: +c.group.position.z.toFixed(2),
    })),
  };
  window.__underreachStatus = s;
  statusEl.textContent = JSON.stringify(s);
}

document.addEventListener('visibilitychange', () => {
  if (document.hidden) renderer.setAnimationLoop(null);
  else renderer.setAnimationLoop(tick);
});
window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

/* ------------------------------------------- verification harness */

// Only with ?harness=1 (used by docs/TEST_PLAN.md checks; Lively
// never passes it): deterministic stepping + a raw render-cost
// bench, independent of how fast the host composites frames.
if (PAGE_PARAMS.has('harness')) {
  window.__scene = scene;
  window.__underreachRoute = { planRoute, obstacles: OBSTACLES, network: NETWORK };
  window.__underreachStep = (steps, dt) => {
    for (let i = 0; i < steps; i++) {
      perfNow += dt * 1000;
      const t = perfNow * 0.001;
      updateGlows(t);
      updateDirector(dt, t);
    }
    camera.position.copy(CAM_BASE);
    camera.lookAt(CAM_LOOK);
    renderer.render(scene, camera);
    publishStatus();
    return window.__underreachStatus;
  };
  // Time n back-to-back renders of the full scene: the honest
  // per-frame cost on this host, no compositor in the way.
  window.__underreachBench = (n = 60) => {
    camera.position.copy(CAM_BASE);
    camera.lookAt(CAM_LOOK);
    renderer.render(scene, camera);   // warm
    const t0 = performance.now();
    for (let i = 0; i < n; i++) renderer.render(scene, camera);
    const ms = (performance.now() - t0) / n;
    return { frames: n, msPerFrame: +ms.toFixed(2), fpsEquiv: +(1000 / ms).toFixed(1) };
  };
}

/* -------------------------------------------------------------- boot */

(async () => {
  // Creatures first (sequential — parsing several ~20 MB models
  // at once is a needless memory spike), then the town's statics
  // (loaded per slug in parallel, cloned per plot).
  for (const cfg of ROSTER.filter((r) => r.kind === 'creature')) {
    await loadCreature(cfg);
  }
  await buildTown();
  if (templates.size) {
    spawn('dwell');
    spawn(false);
  }
  publishStatus();
  renderer.setAnimationLoop(tick);
})();
