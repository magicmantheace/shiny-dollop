// Campfire Companions — a living desktop wallpaper.
//
// A field at dusk. Creatures built by the Game Asset Builder wander in
// from the dark, warm themselves around the campfire, and wander off
// again. Built for Lively Wallpaper (web type) and equally happy opened
// in a browser over HTTP as a preview.
//
// AAA GRAPHICS EXPERIMENT (branch campfire-wallpaper/aaa-graphics-
// experiment, owner-directed 2026-11-09; the bookmarked build at tag
// campfire-wallpaper/bookmark-definition-pass keeps the classic
// manners): this variant deliberately relaxes the no-shadow-maps
// rule — real-time sun/moon shadows, PMREM environment lighting,
// and a bloom post chain — to probe how far the scene can go toward
// a modern AAA look. Everything else still holds: capped pixel
// ratio, modest particle counts, and the render loop stops entirely
// while the page is hidden. See docs/AAA_EXPERIMENT.md.
//
// The creature director prefers a clip whose name contains "walk" for
// travel whenever a creature's GLB provides one. The GAB P4 animation
// slice added walk (and run) clips to all three catalog creatures, so
// travel walks; the per-creature styles (dragon hops, triceratops
// bounces, goblin glides on idle) remain as the fallback for any GLB
// without a walk clip. Signatures at the fire still use each
// creature's own clip: hop, wave, bounce.

import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import * as SkeletonUtils from 'three/addons/utils/SkeletonUtils.js';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';

/* ---------------------------------------------------------- utilities */

// Deterministic RNG so the field layout is the same every visit.
function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const layoutRand = mulberry32(20261108);
const rand = (a, b) => a + Math.random() * (b - a);

function lerpAngle(a, b, t) {
  let d = (b - a) % (Math.PI * 2);
  if (d > Math.PI) d -= Math.PI * 2;
  if (d < -Math.PI) d += Math.PI * 2;
  return a + d * t;
}

// Gentle ground undulation, zero near the fire so the gathering area is
// a flat clearing. The same function lifts creatures and props.
function groundH(x, z) {
  const d = Math.hypot(x, z);
  const s = THREE.MathUtils.smoothstep(d, 5, 22);
  return (Math.sin(x * 0.16) * 0.5 + Math.cos(z * 0.14) * 0.4 +
          Math.sin((x + z) * 0.06) * 0.6) * 0.5 * s;
}

// Pine foliage whose silhouette reads as a tree rather than a
// plain triangle: five flat, stepped tiers — a wide shelf at the
// bottom narrowing to the tip — each tier rotated a few degrees
// against its neighbours so the outline breaks up, plus a baked
// vertical shade gradient (dark under the shelves, lightest at
// the tip) carried as a vertex colour. Materials using this
// geometry need vertexColors: true (and flatShading suits it).
// Local units match the pine trunks: foliage spans y 0.8–4.65
// over a ~1.2-tall trunk.
function makePineFoliageGeo() {
  // AAA experiment stage 5: a new tree model. The stacked
  // cones (kept, jittered, through stage 4) are replaced by
  // whorls of displaced foliage clusters around the trunk
  // line — an irregular, lumpy silhouette with air in it,
  // instead of a paper cone. Same envelope as the old tiers
  // (about 2.1 wide, 0.75..4.7 tall) so every placement,
  // scale, and instance matrix in the scene keeps working.
  const parts = [];
  const levels = [
    // [centreY, spread, clusterRadius]
    [1.20, 1.00, 0.55], [1.95, 0.90, 0.52], [2.65, 0.74, 0.47],
    [3.30, 0.56, 0.42], [3.85, 0.38, 0.37],
  ];
  const addBlob = (cx, cy, cz, r, sy, shadeBase, seedK) => {
    const g = new THREE.IcosahedronGeometry(r, 1);
    displaceGeo(g, 0.16, 2.6);
    g.scale(1, sy, 1);
    g.translate(cx, cy, cz);
    const p = g.getAttribute('position');
    const col = new Float32Array(p.count * 3);
    for (let i = 0; i < p.count; i++) {
      const s = THREE.MathUtils.clamp(shadeBase +
        0.07 * Math.sin(p.getX(i) * 9 + p.getY(i) * 7 + seedK * 3), 0.3, 1.05);
      col[i * 3] = s; col[i * 3 + 1] = s; col[i * 3 + 2] = s;
    }
    g.setAttribute('color', new THREE.BufferAttribute(col, 3));
    parts.push(g);
  };
  levels.forEach(([cy, spread, cr], li) => {
    const shadeBase = 0.45 + 0.55 * (cy - 0.8) / 3.9;
    addBlob(0, cy + 0.06, 0, cr * 1.12, 0.82, shadeBase, li * 4);
    for (let j = 0; j < 3; j++) {
      const a = li * 1.3 + j * 2.1;
      addBlob(Math.cos(a) * spread * 0.52, cy - 0.05,
              Math.sin(a) * spread * 0.52, cr * 0.92, 0.78, shadeBase, li * 4 + j + 1);
    }
  });
  addBlob(0, 4.38, 0, 0.30, 1.25, 1.0, 99);   // the leader
  return mergeGeometries(parts);
}

// AAA experiment stage 5: rock and bush models to match the
// new trees — merged clusters of displaced blobs with
// flattened undersides, instead of single primitives.
function makeRockGeo() {
  const parts = [];
  for (const [ox, oy, oz, r] of [[0, 0, 0, 1], [0.58, -0.18, 0.28, 0.62], [-0.5, -0.22, -0.3, 0.48]]) {
    const g = displaceGeo(new THREE.DodecahedronGeometry(r, 1), 0.13, 1.6);
    g.translate(ox, oy, oz);
    parts.push(g);
  }
  const merged = mergeGeometries(parts);
  const p = merged.getAttribute('position');
  for (let i = 0; i < p.count; i++) {
    const y = p.getY(i);
    if (y < -0.55) p.setY(i, -0.55 - (y + 0.55) * 0.3);
  }
  return merged;
}
function makeBushGeo() {
  const parts = [];
  for (const [ox, oy, oz, r] of [[0, 0.05, 0, 1], [0.62, -0.03, 0.18, 0.66], [-0.55, 0, -0.22, 0.58]]) {
    const g = displaceGeo(new THREE.IcosahedronGeometry(r, 2), 0.13, 1.6);
    g.scale(1, 0.78, 1);
    g.translate(ox, oy, oz);
    parts.push(g);
  }
  return mergeGeometries(parts);
}

// AAA experiment stage 4: organic silhouettes for the primitive
// rocks and bushes — vertices pushed along their own direction
// by a position hash, so no two look stamped from the same
// mould. The polyhedron geometries' smooth sphere-projected
// normals are kept (recomputing would facet them); ±10%
// displacement does not stale them visibly.
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
  return geo;
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

/* ------------------------------------------- celestial (real clock) */

// The sky follows the real sun and moon for the owner's location,
// computed locally from the system clock with the standard
// NOAA/SunCalc-style solar math and the matching lunar
// approximation — no network, no libraries. Behaviour is driven by
// elevation/azimuth every frame; sunrise, sunset, moonrise and
// moonset fall out of the curves rather than being special-cased.
const HOME = { lat: 49.6942, lon: -112.8456 };   // Lethbridge, Alberta
const PAGE_PARAMS = new URLSearchParams(location.search);
// Verification seam: &time=<epoch ms | ISO string> freezes the
// celestial computation at that instant. Lively never passes it.
const _tp = PAGE_PARAMS.get('time');
const _frozenMs = _tp == null || _tp.trim() === '' ? NaN
  : (Number.isFinite(+_tp) ? +_tp : Date.parse(_tp));
const FROZEN_TIME = Number.isFinite(_frozenMs) ? _frozenMs : null;

const RAD = Math.PI / 180;
const DAY_MS = 86400000, J1970 = 2440588, J2000 = 2451545;
const OBL = RAD * 23.4397;                       // ecliptic obliquity

function toDays(date) { return date.valueOf() / DAY_MS - 0.5 + J1970 - J2000; }
function siderealTime(d, lw) { return RAD * (280.16 + 360.9856235 * d) - lw; }

function sunCoords(d) {
  const M = RAD * (357.5291 + 0.98560028 * d);                  // mean anomaly
  const L = M + RAD * (1.9148 * Math.sin(M) + 0.02 * Math.sin(2 * M) +
                       0.0003 * Math.sin(3 * M)) + RAD * 102.9372 + Math.PI;
  return {
    dec: Math.asin(Math.sin(L) * Math.sin(OBL)),
    ra: Math.atan2(Math.sin(L) * Math.cos(OBL), Math.cos(L)),
  };
}
function moonCoords(d) {
  const L = RAD * (218.316 + 13.176396 * d);                    // mean longitude
  const M = RAD * (134.963 + 13.064993 * d);                    // mean anomaly
  const F = RAD * (93.272 + 13.229350 * d);                     // mean distance
  const lon = L + RAD * 6.289 * Math.sin(M);                    // ecliptic longitude
  const lat = RAD * 5.128 * Math.sin(F);                        // ecliptic latitude
  return {
    ra: Math.atan2(Math.sin(lon) * Math.cos(OBL) - Math.tan(lat) * Math.sin(OBL),
                   Math.cos(lon)),
    dec: Math.asin(Math.sin(lat) * Math.cos(OBL) +
                   Math.cos(lat) * Math.sin(OBL) * Math.sin(lon)),
    dist: 385001 - 20905 * Math.cos(M),                         // km
  };
}
// Compass azimuth (radians, 0 = north) and elevation for a body
// with equatorial coordinates {ra, dec} at the given instant.
function bodyPosition(date, coords) {
  const lw = RAD * -HOME.lon, phi = RAD * HOME.lat;
  const H = siderealTime(toDays(date), lw) - coords.ra;
  return {
    az: Math.atan2(Math.sin(H),
      Math.cos(H) * Math.sin(phi) - Math.tan(coords.dec) * Math.cos(phi)) + Math.PI,
    el: Math.asin(Math.sin(phi) * Math.sin(coords.dec) +
                  Math.cos(phi) * Math.cos(coords.dec) * Math.cos(H)),
    hourAngle: H,
  };
}
function sunPosition(date) { return bodyPosition(date, sunCoords(toDays(date))); }
function moonPosition(date) { return bodyPosition(date, moonCoords(toDays(date))); }

function moonIllumination(date) {
  const d = toDays(date);
  const s = sunCoords(d), m = moonCoords(d);
  const sdist = 149598000;                                      // Earth–Sun, km
  const phi = Math.acos(Math.sin(s.dec) * Math.sin(m.dec) +
    Math.cos(s.dec) * Math.cos(m.dec) * Math.cos(s.ra - m.ra));
  const inc = Math.atan2(sdist * Math.sin(phi), m.dist - sdist * Math.cos(phi));
  const angle = Math.atan2(
    Math.cos(s.dec) * Math.sin(s.ra - m.ra),
    Math.sin(s.dec) * Math.cos(m.dec) - Math.cos(s.dec) * Math.sin(m.dec) * Math.cos(s.ra - m.ra));
  return {
    fraction: (1 + Math.cos(inc)) / 2,
    phase: 0.5 + 0.5 * inc * (angle < 0 ? -1 : 1) / Math.PI,
    angle,                                                      // bright-limb position angle
  };
}

// Scene direction for a compass azimuth + elevation: north is -z
// (into the screen), east is +x.
function azElToVec(az, el, r, out) {
  const ce = Math.cos(el);
  return out.set(r * ce * Math.sin(az), r * Math.sin(el), -r * ce * Math.cos(az));
}

/* ------------------------------------------------------------- setup */

const statusEl = document.getElementById('status');
const loadingEl = document.getElementById('loading');

let renderer;
try {
  renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'low-power' });
} catch (e) {
  document.getElementById('fallback').style.display = 'flex';
  loadingEl.classList.add('done');
  throw e;
}
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.3;
document.body.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.fog = new THREE.FogExp2(0x131a33, 0.0135);

const camera = new THREE.PerspectiveCamera(
  55, window.innerWidth / window.innerHeight, 0.1, 500);
// The camera sits at -z (the north side of the clearing) looking
// toward +z — facing SOUTH across the fire. At 49.7° N the sun and
// moon transit the southern sky, so from here their discs cross
// the visible sky (rising at frame-left/east, setting frame-
// right/west) instead of passing behind the viewer, as they did
// when the camera sat at +z facing north.
const CAM_BASE = new THREE.Vector3(0, 3.1, -10.8);
// The look target sits almost at camera height (pitch ≈ -0.5°), not
// down at the fire: at 49.7° N the sun's November noon culmination
// is ~24° and the frame's top edge lands at ~27°, so the discs
// cross the visible sky instead of skimming above it. The fire
// reads low-centre, campfire-photo style, with the sky and the
// mountain vista holding the upper frame.
const CAM_LOOK = new THREE.Vector3(0, 3.0, 0);
camera.position.copy(CAM_BASE);

/* ---------------------------------------------------------- lighting */

// Both lights are steered every frame by updateSky(): the hemisphere
// follows the sky palette, and the directional follows whichever of
// the sun / moon is contributing (warm low sun, white day sun, cool
// dim moonlight). Initial values are the dusk set.
const hemiLight = new THREE.HemisphereLight(0x2c3a5e, 0x191008, 1.15);
scene.add(hemiLight);
const skyLight = new THREE.DirectionalLight(0x8fa3cc, 0.75);
skyLight.position.set(-18, 26, -12);
scene.add(skyLight);
// AAA experiment: the sky light casts the scene's one real shadow
// map (sun by day, moon by night — it already follows whichever
// dominates). The ortho box covers the clearing and mid-field;
// the far treeline falls outside and stays unshadowed.
skyLight.castShadow = true;
skyLight.shadow.mapSize.set(2048, 2048);
skyLight.shadow.camera.left = -42;
skyLight.shadow.camera.right = 42;
skyLight.shadow.camera.top = 42;
skyLight.shadow.camera.bottom = -42;
skyLight.shadow.camera.near = 5;
skyLight.shadow.camera.far = 150;
skyLight.shadow.bias = -0.0003;
skyLight.shadow.normalBias = 0.05;
scene.add(skyLight.target);

// AAA experiment: image-based lighting. A PMREM environment is
// generated from a miniature of the sky dome (the same gradient
// uniforms, shared by reference so the colours always match) plus
// a dark ground disc, and regenerated only when the sun's
// elevation bucket changes — a few times an hour of page time.
const pmrem = new THREE.PMREMGenerator(renderer);
let envRT = null, lastEnvBucket = null;
function refreshEnvironment() {
  const envScene = new THREE.Scene();
  const envSky = new THREE.Mesh(
    new THREE.SphereGeometry(50, 32, 16),
    new THREE.ShaderMaterial({
      side: THREE.BackSide, depthWrite: false,
      uniforms: {
        top: skyUniforms.top, mid: skyUniforms.mid,
        horizon: skyUniforms.horizon,
      },
      vertexShader: `varying vec3 vP; void main(){ vP = position;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
      fragmentShader: `varying vec3 vP; uniform vec3 top; uniform vec3 mid; uniform vec3 horizon;
        void main(){ float h = normalize(vP).y;
          vec3 c = h > 0.22 ? mix(mid, top, smoothstep(0.22, 0.8, h))
                            : mix(horizon, mid, smoothstep(-0.03, 0.22, h));
          gl_FragColor = vec4(c, 1.0); }`,
    }));
  envScene.add(envSky);
  const envGround = new THREE.Mesh(
    new THREE.CircleGeometry(48, 24),
    new THREE.MeshBasicMaterial({ color: 0x2e4724 }));
  envGround.rotation.x = -Math.PI / 2;
  envGround.position.y = -2;
  envScene.add(envGround);
  const next = pmrem.fromScene(envScene, 0.04);
  if (envRT) envRT.dispose();
  envRT = next;
  scene.environment = envRT.texture;
}
// The fire light is created with the campfire and flickers per-frame.

// Time-of-day balances read by the fire and the dressing updaters:
// fireScale shrinks the fire's presence in daylight; nightFactor
// gates fireflies and the mushroom glow.
let fireScale = 1, nightFactor = 1;
// AAA experiment stage 2: shared wind clock for the grass sway
// shader (one uniform object, referenced by the grass material).
const windUniform = { value: 0 };
let skyState = { sunEl: -20, sunAz: 0, moonEl: -20, moonAz: 0, moonFrac: 0 };
// Scene elements created later (e.g. the horizon hills) register a
// callback here to be tinted by the sky palette each frame.
const skyFollowers = [];

/* --------------------------------------------------------------- sky */

let skyUniforms, starMat;
let sunDisc, sunHaloMat, moonDisc, moonMat, moonHaloMat;
const moonCanvas = document.createElement('canvas');
moonCanvas.width = moonCanvas.height = 1024;
const moonCtx = moonCanvas.getContext('2d');
const moonTex = new THREE.CanvasTexture(moonCanvas);
moonTex.colorSpace = THREE.SRGBColorSpace;
moonTex.center.set(0.5, 0.5);
let moonTexHour = -1;

{
  const skyMat = new THREE.ShaderMaterial({
    side: THREE.BackSide, depthWrite: false,
    uniforms: {
      top: { value: new THREE.Color(0x070d29) },
      mid: { value: new THREE.Color(0x1b2547) },
      horizon: { value: new THREE.Color(0x93502f) },
      uTime: { value: 0 },
      uCloud: { value: 0 },
    },
    vertexShader: `varying vec3 vP; void main(){ vP = position;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: `varying vec3 vP; uniform vec3 top; uniform vec3 mid; uniform vec3 horizon;
      uniform float uTime; uniform float uCloud;
      float hash21(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
      float vnoise(vec2 p) {
        vec2 i = floor(p), f = fract(p);
        f = f * f * (3.0 - 2.0 * f);
        return mix(mix(hash21(i), hash21(i + vec2(1, 0)), f.x),
                   mix(hash21(i + vec2(0, 1)), hash21(i + vec2(1, 1)), f.x), f.y);
      }
      float fbm2(vec2 p) {
        float v = 0.0, a = 0.5;
        for (int i = 0; i < 4; i++) { v += a * vnoise(p); p *= 2.11; a *= 0.5; }
        return v;
      }
      void main(){ vec3 dir = normalize(vP); float h = dir.y;
        vec3 c = h > 0.22 ? mix(mid, top, smoothstep(0.22, 0.8, h))
                          : mix(horizon, mid, smoothstep(-0.03, 0.22, h));
        // AAA experiment stage 3: soft procedural clouds, so the
        // sky stops being a flat gradient card behind the scene.
        // Wisps on a projected plane, drifting slowly, banded to
        // the lower sky and tinted by the horizon colour.
        vec2 cuv = dir.xz / (abs(dir.y) + 0.22) * 1.15 + vec2(uTime * 0.004, 0.0);
        float cl = fbm2(cuv * 1.6 + fbm2(cuv * 3.1) * 0.7);
        float cov = smoothstep(0.52, 0.74, cl)
          * smoothstep(0.015, 0.10, h) * (1.0 - smoothstep(0.38, 0.72, h));
        vec3 cloudCol = mix(horizon, vec3(1.02, 1.0, 0.98), 0.55);
        c = mix(c, cloudCol, cov * uCloud * 0.5);
        gl_FragColor = vec4(c, 1.0); }`,
  });
  skyUniforms = skyMat.uniforms;
  scene.add(new THREE.Mesh(new THREE.SphereGeometry(230, 48, 24), skyMat));

  // Stars.
  const starGeo = new THREE.BufferGeometry();
  const n = 650, pos = new Float32Array(n * 3), col = new Float32Array(n * 3);
  const c = new THREE.Color();
  for (let i = 0; i < n; i++) {
    const az = layoutRand() * Math.PI * 2;
    const el = 0.12 + Math.pow(layoutRand(), 0.7) * 1.35;
    const r = 205;
    pos[i * 3] = Math.cos(az) * Math.cos(el) * r;
    pos[i * 3 + 1] = Math.sin(el) * r;
    pos[i * 3 + 2] = Math.sin(az) * Math.cos(el) * r;
    const b = 0.35 + layoutRand() * 0.65;
    c.setRGB(b, b, b * (0.9 + layoutRand() * 0.1));
    col[i * 3] = c.r; col[i * 3 + 1] = c.g; col[i * 3 + 2] = c.b;
  }
  starGeo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  starGeo.setAttribute('color', new THREE.BufferAttribute(col, 3));
  starMat = new THREE.PointsMaterial({
    size: 1.5, sizeAttenuation: false, vertexColors: true, fog: false,
    transparent: true, opacity: 0.9, depthWrite: false,
  });
  scene.add(new THREE.Points(starGeo, starMat));

  // Sun: warm disc + halo, positioned by updateSky().
  sunDisc = new THREE.Mesh(
    new THREE.CircleGeometry(5, 48),
    new THREE.MeshBasicMaterial({ color: 0xffdf9e, fog: false }));
  scene.add(sunDisc);
  sunHaloMat = new THREE.MeshBasicMaterial({
    map: radialSpriteTexture('rgba(255,205,130,0.6)', 'rgba(255,205,130,0)'),
    transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, fog: false,
  });
  const sunHalo = new THREE.Mesh(new THREE.PlaneGeometry(52, 52), sunHaloMat);
  sunHalo.name = 'sunHalo';
  scene.add(sunHalo);
  sunDisc.userData.halo = sunHalo;

  // Moon: the disc texture is a canvas redrawn (at most hourly)
  // from the real phase; placement and brightness come from
  // updateSky(). Plus a soft halo.
  moonMat = new THREE.MeshBasicMaterial({
    map: moonTex, transparent: true, fog: false,
  });
  moonDisc = new THREE.Mesh(new THREE.CircleGeometry(6.5, 48), moonMat);
  scene.add(moonDisc);
  moonHaloMat = new THREE.MeshBasicMaterial({
    map: radialSpriteTexture('rgba(190,205,240,0.55)', 'rgba(190,205,240,0)'),
    transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, fog: false,
  });
  const moonHalo = new THREE.Mesh(new THREE.PlaneGeometry(46, 46), moonHaloMat);
  scene.add(moonHalo);
  moonDisc.userData.halo = moonHalo;
}

// Draw the moon's lit region for a phase (0 = new, 0.5 = full):
// the limb semicircle on the lit side plus the terminator ellipse.
// Maria are a fixed hint pattern under the lit paint.
function drawMoonPhase(phase) {
  const s = 1024, c = s / 2, r = c - 4;
  const g = moonCtx;
  g.clearRect(0, 0, s, s);
  g.beginPath(); g.arc(c, c, r, 0, Math.PI * 2);
  g.fillStyle = '#131a2c';                       // earthshine-dark side
  g.fill();
  g.save();
  g.beginPath(); g.arc(c, c, r, 0, Math.PI * 2); g.clip();
  const k = Math.cos(2 * Math.PI * phase);
  g.beginPath();
  if (phase <= 0.5) {                            // waxing: lit right
    g.arc(c, c, r, -Math.PI / 2, Math.PI / 2, false);
    g.ellipse(c, c, r * Math.abs(k), r, 0, Math.PI / 2, -Math.PI / 2, k > 0);
  } else {                                       // waning: lit left
    g.arc(c, c, r, Math.PI / 2, Math.PI * 1.5, false);
    g.ellipse(c, c, r * Math.abs(k), r, 0, Math.PI * 1.5, Math.PI / 2, k > 0);
  }
  g.closePath();
  const grad = g.createRadialGradient(c - r * 0.3, c - r * 0.3, r * 0.2, c, c, r);
  grad.addColorStop(0, '#f2f5fa');
  grad.addColorStop(1, '#c3ccd9');
  g.fillStyle = grad;
  g.fill();
  g.fillStyle = 'rgba(105,118,140,0.32)';
  for (const [mx, my, mr] of [[-0.25, -0.3, 0.28], [0.15, -0.05, 0.22],
                              [-0.05, 0.3, 0.18], [0.3, 0.35, 0.14]]) {
    g.beginPath(); g.arc(c + mx * r, c + my * r, mr * r, 0, Math.PI * 2); g.fill();
  }
  g.restore();
  g.beginPath(); g.arc(c, c, r - 1, 0, Math.PI * 2);
  g.strokeStyle = 'rgba(220,228,240,0.22)';
  g.lineWidth = 2;
  g.stroke();
}

// Sky/light palettes by sun elevation (degrees). The 0° stop IS the
// original dusk look this wallpaper shipped with — it is now the
// sunset/sunrise state instead of the permanent one.
const _C = (h) => new THREE.Color(h);
const SKY_STOPS = [
  { el: -18, top: _C(0x03061a), mid: _C(0x0a1128), hor: _C(0x1f1c30), fog: _C(0x0a1128), fogDen: 0.0135, hs: _C(0x2c3f6e), hg: _C(0x181209), hi: 0.9 },
  { el: -8,  top: _C(0x060b26), mid: _C(0x16203f), hor: _C(0x3c2c40), fog: _C(0x111a33), fogDen: 0.0135, hs: _C(0x3d5484), hg: _C(0x1e150c), hi: 1.05 },
  { el: 0,   top: _C(0x070d29), mid: _C(0x1b2547), hor: _C(0x93502f), fog: _C(0x131a33), fogDen: 0.0135, hs: _C(0x8fa3cc), hg: _C(0x2e4a2a), hi: 1.15 },
  { el: 6,   top: _C(0x2c4d7d), mid: _C(0x7d90b4), hor: _C(0xe09a52), fog: _C(0x5f6a80), fogDen: 0.009,  hs: _C(0x8093b8), hg: _C(0x2e2415), hi: 1.45 },
  { el: 18,  top: _C(0x38679f), mid: _C(0x84a8c8), hor: _C(0xd3e2e6), fog: _C(0xa7bcc4), fogDen: 0.0055, hs: _C(0xbfd8f0), hg: _C(0x44543c), hi: 1.7 },
  { el: 40,  top: _C(0x33629f), mid: _C(0x82a9cc), hor: _C(0xd8e4e8), fog: _C(0xb0c2ca), fogDen: 0.005,  hs: _C(0xcfe4f4), hg: _C(0x4a5c40), hi: 1.85 },
];
const _pal = {
  top: new THREE.Color(), mid: new THREE.Color(), hor: new THREE.Color(),
  fog: new THREE.Color(), hs: new THREE.Color(), hg: new THREE.Color(),
  fogDen: 0.0135, hi: 1,
};
function paletteAt(elDeg) {
  let a = SKY_STOPS[0], b = SKY_STOPS[SKY_STOPS.length - 1];
  for (let i = 0; i < SKY_STOPS.length - 1; i++) {
    if (elDeg >= SKY_STOPS[i].el && elDeg <= SKY_STOPS[i + 1].el) {
      a = SKY_STOPS[i]; b = SKY_STOPS[i + 1]; break;
    }
  }
  let t = b.el === a.el ? 0 : THREE.MathUtils.clamp((elDeg - a.el) / (b.el - a.el), 0, 1);
  t = t * t * (3 - 2 * t);
  _pal.top.lerpColors(a.top, b.top, t);
  _pal.mid.lerpColors(a.mid, b.mid, t);
  _pal.hor.lerpColors(a.hor, b.hor, t);
  _pal.fog.lerpColors(a.fog, b.fog, t);
  _pal.hs.lerpColors(a.hs, b.hs, t);
  _pal.hg.lerpColors(a.hg, b.hg, t);
  _pal.fogDen = a.fogDen + (b.fogDen - a.fogDen) * t;
  _pal.hi = a.hi + (b.hi - a.hi) * t;
  return _pal;
}

const _v1 = new THREE.Vector3(), _v2 = new THREE.Vector3();
const _sunWarm = new THREE.Color(0xff9448), _sunWhite = new THREE.Color(0xfff4e2);
const _moonCol = new THREE.Color(0x93a7d4);
const _sunColNow = new THREE.Color(), _mixCol = new THREE.Color(),
      _moonScaled = new THREE.Color();

// Steer every time-of-day element from the real positions. Called
// each frame from the main loop (and by the harness step seam).
function updateSky(nowMs) {
  const date = new Date(nowMs);
  const d = toDays(date);
  const sun = bodyPosition(date, sunCoords(d));
  const mc = moonCoords(d);
  const moon = bodyPosition(date, mc);
  const ill = moonIllumination(date);
  const sunEl = sun.el / RAD, moonEl = moon.el / RAD;
  skyState = {
    sunEl: +sunEl.toFixed(2), sunAz: +(sun.az / RAD).toFixed(1),
    moonEl: +moonEl.toFixed(2), moonAz: +(moon.az / RAD).toFixed(1),
    moonFrac: +ill.fraction.toFixed(3),
  };

  const P = paletteAt(sunEl);
  // AAA experiment: the sky dome is a ShaderMaterial, which the
  // direct renderer used to emit raw; through the composer the
  // OutputPass sRGB-encodes it, washing the tuned palette pale.
  // Converting the colours as-if-sRGB -> linear pre-compensates,
  // landing the dome back on its tuned values (ACES still applies
  // on top, a small residual shift accepted for stage 1).
  skyUniforms.top.value.copy(P.top).convertSRGBToLinear();
  skyUniforms.mid.value.copy(P.mid).convertSRGBToLinear();
  skyUniforms.horizon.value.copy(P.hor).convertSRGBToLinear();
  scene.fog.color.copy(P.fog);
  scene.fog.density = P.fogDen;
  hemiLight.color.copy(P.hs);
  hemiLight.groundColor.copy(P.hg);
  hemiLight.intensity = P.hi;

  // AAA experiment: refresh the PMREM environment only when the
  // sun crosses a 3-degree bucket (a few times an hour), and keep
  // its contribution modest so the stylized palette stays in charge.
  const envBucket = Math.round(sunEl / 3);
  if (envBucket !== lastEnvBucket) {
    lastEnvBucket = envBucket;
    refreshEnvironment();
  }
  scene.environmentIntensity = 0.15;
  // The IBL ambient stacks on the hemisphere light; trim the
  // hemisphere so the pair lands near the bookmark build's
  // ambient level instead of washing the field flat.
  hemiLight.intensity *= 0.8;

  // Sun disc + halo.
  const sunVis = THREE.MathUtils.clamp((sunEl + 2.5) / 5, 0, 1);
  sunDisc.visible = sunEl > -2.5;
  if (sunDisc.visible) {
    azElToVec(sun.az, sun.el, 192, _v1);
    sunDisc.position.copy(_v1);
    sunDisc.lookAt(0, 0, 0);
    sunDisc.material.color.set(0xffdf9e)
      .lerp(_sunWarm, THREE.MathUtils.clamp(1 - sunEl / 10, 0, 1));
    const halo = sunDisc.userData.halo;
    halo.position.copy(_v1);
    halo.lookAt(0, 0, 0);
    sunHaloMat.opacity = 0.5 * sunVis;
  } else {
    sunHaloMat.opacity = 0;
  }

  // Moon disc (phase texture refreshed at most hourly) + halo.
  // The disc's opacity is gated two ways: by daylight (the drawn
  // dark side reads correctly only against a dark sky — against
  // blue noon sky an ungated new moon would print as a black
  // circle) and by the illuminated fraction itself.
  const moonGate = THREE.MathUtils.clamp((6 - sunEl) / 10, 0, 1) *
                   THREE.MathUtils.clamp(ill.fraction * 2.5, 0, 1);
  moonDisc.visible = moonEl > -1.5 && moonGate > 0.02;
  const hourKey = Math.floor(nowMs / 3600000);
  if (hourKey !== moonTexHour) {
    moonTexHour = hourKey;
    drawMoonPhase(ill.phase);
    moonTex.needsUpdate = true;
  }
  if (moonDisc.visible) {
    // Rotate the disc so the bright limb faces the sun: bright-limb
    // position angle minus the parallactic angle.
    const q = Math.atan2(Math.sin(moon.hourAngle),
      Math.tan(RAD * HOME.lat) * Math.cos(mc.dec) -
      Math.sin(mc.dec) * Math.cos(moon.hourAngle));
    moonTex.rotation = ill.angle - q;
    azElToVec(moon.az, moon.el, 192, _v1);
    moonDisc.position.copy(_v1);
    moonDisc.lookAt(0, 0, 0);
    const bright = THREE.MathUtils.clamp(0.2 + moonEl / 25, 0.15, 1) *
                   (0.3 + 0.7 * ill.fraction);
    moonMat.opacity = moonGate;
    moonMat.color.setScalar(Math.max(0.06, bright));
    const halo = moonDisc.userData.halo;
    halo.position.copy(_v1);
    halo.lookAt(0, 0, 0);
    moonHaloMat.opacity = 0.4 * bright * moonGate * THREE.MathUtils.clamp((moonEl + 1) / 6, 0, 1);
  } else {
    moonHaloMat.opacity = 0;
  }

  // Directional light: contribution-weighted blend of the two
  // bodies, so dawn/dusk hand over without a pop.
  const sunI = sunEl > -4
    ? 2.2 * Math.pow(THREE.MathUtils.clamp((Math.sin(sun.el) + 0.06) / 0.38, 0, 1), 0.7) : 0;
  const moonI = (0.15 + 0.55 * ill.fraction) *
    THREE.MathUtils.clamp(Math.sin(moon.el), 0, 1) *
    THREE.MathUtils.clamp((1 - sunEl) / 5, 0, 1);
  if (sunI + moonI > 0.002) {
    azElToVec(sun.az, sun.el, 60, _v1).multiplyScalar(sunI);
    azElToVec(moon.az, moon.el, 60, _v2).multiplyScalar(moonI);
    skyLight.position.copy(_v1.add(_v2).normalize().multiplyScalar(60));
    skyLight.intensity = sunI + moonI;
    _sunColNow.lerpColors(_sunWarm, _sunWhite,
      THREE.MathUtils.clamp(sunEl / 16, 0, 1));
    _mixCol.copy(_sunColNow).multiplyScalar(sunI)
      .add(_moonScaled.copy(_moonCol).multiplyScalar(moonI))
      .multiplyScalar(1 / (sunI + moonI));
    skyLight.color.copy(_mixCol);
  } else {
    skyLight.intensity = 0.12;
    skyLight.color.copy(_moonCol);
  }

  // Stars, fireflies, mushrooms, and the fire's presence.
  starMat.opacity = 0.9 * THREE.MathUtils.clamp((-1 - sunEl) / 6, 0, 1);
  nightFactor = THREE.MathUtils.clamp((-0.5 - sunEl) / 5, 0, 1);
  fireScale = 0.35 + 0.65 * THREE.MathUtils.clamp((6 - sunEl) / 14, 0, 1);
  // AAA experiment stage 3: cloud clock + strength for the sky
  // shader (clouds belong to the lit hours; they are gone by
  // full night and only embers of them catch the sunset).
  skyUniforms.uTime.value = perfNow * 0.001;
  skyUniforms.uCloud.value = THREE.MathUtils.clamp((sunEl + 2.5) / 9, 0, 1);
  for (const f of skyFollowers) f(P, sunEl);
}

/* -------------------------------------------------------------- field */

// AAA experiment stage 2: procedural ground detail. A periodic
// value-noise heightfield (lattice frequencies divide the tile,
// so it wraps seamlessly) becomes both a near-neutral diffuse —
// it multiplies the vertex colours, so it hovers around a middle
// luminance — and a normal map derived from the same heights.
// Tiled across the field; the vertex-colour macro pattern breaks
// up any visible repetition.
function makeGroundTextures() {
  // 1024² (1080p-class): at 256² the foreground ground stretched
  // one texel over ~10 screen pixels on a 4K desktop; 1024 with
  // two extra fine octaves brings real detail to ~5 cm features.
  const S = 1024;
  const height = new Float32Array(S * S);
  const octaves = [[4, 0.5], [8, 0.28], [16, 0.16], [32, 0.09], [64, 0.05], [128, 0.028]];
  const lattices = octaves.map(([f]) => {
    const g = new Float32Array(f * f);
    for (let i = 0; i < g.length; i++) g[i] = Math.random();
    return g;
  });
  for (let y = 0; y < S; y++) for (let x = 0; x < S; x++) {
    let v = 0;
    for (let o = 0; o < octaves.length; o++) {
      const f = octaves[o][0], g = lattices[o];
      const fx = x / S * f, fy = y / S * f;
      const x0 = Math.floor(fx) % f, y0 = Math.floor(fy) % f;
      const x1 = (x0 + 1) % f, y1 = (y0 + 1) % f;
      let tx = fx - Math.floor(fx), ty = fy - Math.floor(fy);
      tx = tx * tx * (3 - 2 * tx); ty = ty * ty * (3 - 2 * ty);
      const a = g[y0 * f + x0], b = g[y0 * f + x1],
            c = g[y1 * f + x0], d = g[y1 * f + x1];
      v += ((a + (b - a) * tx) * (1 - ty) + (c + (d - c) * tx) * ty) * octaves[o][1];
    }
    height[y * S + x] = v;
  }
  const difC = document.createElement('canvas'); difC.width = difC.height = S;
  const dctx = difC.getContext('2d'); const dimg = dctx.createImageData(S, S);
  const norC = document.createElement('canvas'); norC.width = norC.height = S;
  const nctx = norC.getContext('2d'); const nimg = nctx.createImageData(S, S);
  for (let y = 0; y < S; y++) for (let x = 0; x < S; x++) {
    const i = y * S + x, h = height[i];
    const lum = 168 + (h - 0.5) * 130;
    dimg.data[i * 4] = lum * 0.97; dimg.data[i * 4 + 1] = lum;
    dimg.data[i * 4 + 2] = lum * 0.9; dimg.data[i * 4 + 3] = 255;
    const hx = height[y * S + (x + 1) % S] - height[y * S + (x - 1 + S) % S];
    const hy = height[((y + 1) % S) * S + x] - height[((y - 1 + S) % S) * S + x];
    // Slope scale compensates the finer texel grid (per-pixel
    // height deltas shrink as S grows); the fine octaves add
    // their own real slope on top.
    let nx = -hx * 6.0, ny = hy * 6.0, nz = 1;
    const il = 1 / Math.hypot(nx, ny, nz);
    nimg.data[i * 4] = (nx * il * 0.5 + 0.5) * 255;
    nimg.data[i * 4 + 1] = (ny * il * 0.5 + 0.5) * 255;
    nimg.data[i * 4 + 2] = (nz * il * 0.5 + 0.5) * 255;
    nimg.data[i * 4 + 3] = 255;
  }
  dctx.putImageData(dimg, 0, 0); nctx.putImageData(nimg, 0, 0);
  const aniso = Math.min(8, renderer.capabilities.getMaxAnisotropy());
  const dif = new THREE.CanvasTexture(difC);
  dif.wrapS = dif.wrapT = THREE.RepeatWrapping; dif.repeat.set(26, 26);
  dif.colorSpace = THREE.SRGBColorSpace; dif.anisotropy = aniso;
  const nor = new THREE.CanvasTexture(norC);
  nor.wrapS = nor.wrapT = THREE.RepeatWrapping; nor.repeat.set(26, 26);
  nor.anisotropy = aniso;
  return { dif, nor };
}

// AAA experiment stage 3: one shared fine-grain detail map for
// the environment set (pines, rocks, bushes, wood). The set was
// flat-shaded untextured primitives — the most "cartoon" part
// of the scene next to the painted creatures. A near-neutral
// noise multiply plus smooth shading takes the toy edge off
// without touching the geometry. Same periodic-noise recipe
// as the ground's, finer and weaker.
function makeDetailTexture() {
  const S = 256;
  const octaves = [[8, 0.45], [16, 0.3], [32, 0.18], [64, 0.1]];
  const lattices = octaves.map(([f]) => {
    const g = new Float32Array(f * f);
    for (let i = 0; i < g.length; i++) g[i] = Math.random();
    return g;
  });
  const cv = document.createElement('canvas'); cv.width = cv.height = S;
  const ctx = cv.getContext('2d'); const img = ctx.createImageData(S, S);
  for (let y = 0; y < S; y++) for (let x = 0; x < S; x++) {
    let v = 0;
    for (let o = 0; o < octaves.length; o++) {
      const f = octaves[o][0], g = lattices[o];
      const fx = x / S * f, fy = y / S * f;
      const x0 = Math.floor(fx) % f, y0 = Math.floor(fy) % f;
      const x1 = (x0 + 1) % f, y1 = (y0 + 1) % f;
      let tx = fx - Math.floor(fx), ty = fy - Math.floor(fy);
      tx = tx * tx * (3 - 2 * tx); ty = ty * ty * (3 - 2 * ty);
      const a = g[y0 * f + x0], b = g[y0 * f + x1],
            c = g[y1 * f + x0], d = g[y1 * f + x1];
      v += ((a + (b - a) * tx) * (1 - ty) + (c + (d - c) * tx) * ty) * octaves[o][1];
    }
    const i = (y * S + x) * 4, lum = 224 + (v - 0.5) * 64;
    img.data[i] = lum * 0.99; img.data[i + 1] = lum;
    img.data[i + 2] = lum * 0.97; img.data[i + 3] = 255;
  }
  ctx.putImageData(img, 0, 0);
  const tex = new THREE.CanvasTexture(cv);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping; tex.repeat.set(2, 2);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = Math.min(4, renderer.capabilities.getMaxAnisotropy());
  return tex;
}
const detailTex = makeDetailTexture();

// AAA experiment stage 4 (art redo): painted textures. The
// creatures are painted models; stage 3's neutral grain only
// went halfway. These canvases are dabbed like paint — over a
// thousand soft overlapping ellipses in a small tone family,
// drawn with the 3x3 wrap trick so they still tile, from a
// fixed seed so the art is reproducible — and each material
// family gets its own: needle greens, rock greys, bark browns,
// and a pale rock for the far ridges (whose vertex colours were
// tuned as near-final colours, so their map must stay light).
function makePaintedTexture(tones, { size = 512, dabs = 1100, streak = 0 } = {}) {
  const cv = document.createElement('canvas'); cv.width = cv.height = size;
  const ctx = cv.getContext('2d');
  ctx.fillStyle = tones[0]; ctx.fillRect(0, 0, size, size);
  let seed = 1234567;
  const rnd = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
  for (let i = 0; i < dabs; i++) {
    const tone = tones[1 + Math.floor(rnd() * (tones.length - 1))];
    const x = rnd() * size, y = rnd() * size;
    const rx = 4 + rnd() * 16;
    const ry = streak ? rx * (0.25 + rnd() * 0.3) : 3 + rnd() * 10;
    const rot = streak ? (rnd() - 0.5) * 0.5 : rnd() * Math.PI;
    ctx.fillStyle = tone;
    ctx.globalAlpha = 0.16 + rnd() * 0.22;
    for (const ox of [-size, 0, size]) for (const oy of [-size, 0, size]) {
      ctx.beginPath();
      ctx.ellipse(x + ox, y + oy, rx, ry, rot, 0, Math.PI * 2);
      ctx.fill();
    }
  }
  ctx.globalAlpha = 1;
  const tex = new THREE.CanvasTexture(cv);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy());
  return tex;
}
const foliageTex = makePaintedTexture(
  ['#263d20', '#1d3319', '#2c4a24', '#3a5c2e', '#4a7038', '#5d7a36']);
const rockTex = makePaintedTexture(
  ['#5a5e64', '#494c52', '#686c72', '#787d84', '#6e675c']);
const barkTex = makePaintedTexture(
  ['#3a2a1a', '#2c1e12', '#4c3822', '#5d4630', '#6b543a'], { streak: 1 });
const ridgeTex = makePaintedTexture(
  ['#cfd2d6', '#bcc0c5', '#dde0e3', '#c3c9cd', '#d5d2c8']);

{
  const geo = new THREE.PlaneGeometry(170, 170, 170, 170);
  geo.rotateX(-Math.PI / 2);
  const p = geo.attributes.position;
  const colors = new Float32Array(p.count * 3);
  const dark = new THREE.Color(0x31482a), light = new THREE.Color(0x496b35),
        dry = new THREE.Color(0x5e5f35), cc = new THREE.Color();
  for (let i = 0; i < p.count; i++) {
    const x = p.getX(i), z = p.getZ(i);
    p.setY(i, groundH(x, z));
    const n = 0.5 + 0.5 * Math.sin(x * 0.7 + Math.sin(z * 0.5) * 2.1) *
              Math.cos(z * 0.6 + Math.sin(x * 0.4) * 1.7);
    cc.copy(dark).lerp(light, n);
    if (n > 0.78) cc.lerp(dry, 0.35);
    colors[i * 3] = cc.r; colors[i * 3 + 1] = cc.g; colors[i * 3 + 2] = cc.b;
  }
  geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  geo.computeVertexNormals();
  const groundTex = makeGroundTextures();
  scene.add(new THREE.Mesh(geo,
    new THREE.MeshStandardMaterial({
      vertexColors: true, roughness: 1, metalness: 0,
      map: groundTex.dif, normalMap: groundTex.nor,
      normalScale: new THREE.Vector2(0.5, 0.5),
    })));
}

/* Builder environment pack (Game Asset Builder, 2026-11-10): the
   procedural dressing registers its placements here; once the
   catalogued GLBs load, placeBuilderPack() swaps them in at the same
   spots. Registration only records — the seeded layout RNG stream is
   untouched, so every other placement in the scene is unchanged. */
const BUILDER_SWAPS = { meshes: [], fernSpots: [], fernMesh: null,
  mushroomMeshes: [], mushroomAnchors: [] };
const builderPack = { pending: 0, done: false };

// Scattered primitive set dressing: pines, rocks, bushes. Shared
// geometries/materials, seeded placement, clearing kept free.
{
  const trunkGeo = new THREE.CylinderGeometry(0.09, 0.14, 1.1, 8);
  const rockGeo = makeRockGeo();
  const bushGeo = makeBushGeo();
  const trunkMat = new THREE.MeshStandardMaterial({ color: 0xf5efe8, roughness: 1, map: barkTex });
  const pineMat = new THREE.MeshStandardMaterial({
    color: 0xe6ebdd, roughness: 1, vertexColors: true, map: foliageTex });
  const pineFoliageGeo = makePineFoliageGeo();
  const rockMat = new THREE.MeshStandardMaterial({ color: 0xf5f5f5, roughness: 0.95, map: rockTex });
  const bushMat = new THREE.MeshStandardMaterial({ color: 0xd8dcc8, roughness: 1, map: foliageTex });

  function scatterPos(minR, maxR) {
    const a = layoutRand() * Math.PI * 2;
    const r = minR + layoutRand() * (maxR - minR);
    return [Math.cos(a) * r, Math.sin(a) * r];
  }
  function place(mesh, x, z) {
    mesh.position.set(x, groundH(x, z), z);
    scene.add(mesh);
  }
  for (let i = 0; i < 15; i++) {           // pines, mid/far ring
    const [x, z] = scatterPos(11, 52);
    const tree = new THREE.Group();
    const h = 2.2 + layoutRand() * 1.8;
    const trunk = new THREE.Mesh(trunkGeo, trunkMat);
    trunk.position.y = 0.5; trunk.scale.setScalar(h / 3);
    tree.add(trunk);
    const fol = new THREE.Mesh(pineFoliageGeo, pineMat);
    fol.scale.setScalar(h / 3.4);
    fol.position.y = 0.35;
    tree.add(fol);
    tree.rotation.y = layoutRand() * Math.PI * 2;
    place(tree, x, z);
    BUILDER_SWAPS.meshes.push({ obj: tree, kind: 'pine' });
  }
  for (let i = 0; i < 18; i++) {           // rocks
    const [x, z] = scatterPos(5.5, 55);
    const rock = new THREE.Mesh(rockGeo, rockMat);
    const s = 0.25 + layoutRand() * 0.85;
    rock.scale.set(s, s * (0.55 + layoutRand() * 0.4), s * (0.7 + layoutRand() * 0.5));
    rock.rotation.set(layoutRand() * 3, layoutRand() * 3, layoutRand() * 3);
    place(rock, x, z);
    rock.position.y -= s * 0.25;
    BUILDER_SWAPS.meshes.push({ obj: rock, kind: 'rock' });
  }
  for (let i = 0; i < 14; i++) {           // bushes
    const [x, z] = scatterPos(6, 48);
    const bush = new THREE.Mesh(bushGeo, bushMat);
    const s = 0.5 + layoutRand() * 0.8;
    bush.scale.set(s, s * 0.62, s);
    place(bush, x, z);
    bush.position.y += s * 0.25;
    BUILDER_SWAPS.meshes.push({ obj: bush, kind: 'bush' });
  }
}

/* --------------------------------------------------- scene dressing */

// Ambient animation hooks (fireflies, mushroom glow, shooting star)
// registered by the dressing block below and run from the main loop.
// Everything here is static instancing or a handful of sprites — no
// extra dynamic lights, no shadow maps.
const dressingUpdaters = [];
function updateDressing(t, dt) {
  for (const u of dressingUpdaters) u(t, dt);
}

// Dressing pass: the field was bare — a forest edge, ground life,
// whimsy, and furniture around the fire fill it in. All placement is
// seeded, the fire clearing (the 5 spots at r 2.75) stays readable,
// and dressing lives in the mid-field and at the edges.
{
  const dummy = new THREE.Object3D();
  const tint = new THREE.Color();

  function instanced(geo, mat, count) {
    const m = new THREE.InstancedMesh(geo, mat, count);
    m.frustumCulled = false;
    scene.add(m);
    return m;
  }
  function setInst(mesh, i, x, z, s, sink = 0) {
    dummy.position.set(x, groundH(x, z) - sink, z);
    dummy.rotation.set(0, layoutRand() * Math.PI * 2, 0);
    dummy.scale.setScalar(s);
    dummy.updateMatrix();
    mesh.setMatrixAt(i, dummy.matrix);
  }

  /* The worn dirt path: a flat ribbon following the terrain from
     the front-right field edge into the fire clearing. The sample
     points double as a keep-clear guide for grass and ferns. */
  const pathCurve = new THREE.QuadraticBezierCurve3(
    new THREE.Vector3(17, 0, 36),
    new THREE.Vector3(6.5, 0, 15),
    new THREE.Vector3(2.3, 0, 4.6));
  const pathPts = pathCurve.getPoints(60);
  function distToPath(x, z) {
    let d = Infinity;
    for (const p of pathPts) {
      const dd = (p.x - x) * (p.x - x) + (p.z - z) * (p.z - z);
      if (dd < d) d = dd;
    }
    return Math.sqrt(d);
  }
  {
    const rows = 44, posArr = [], colArr = [], idx = [];
    const cMid = new THREE.Color(0x503d27), cEdge = new THREE.Color(0x3a4526);
    for (let i = 0; i <= rows; i++) {
      const p = pathCurve.getPoint(i / rows);
      const tan = pathCurve.getTangent(i / rows);
      const px = -tan.z, pz = tan.x;
      const w = 0.62 + 0.22 * Math.sin(i * 1.7) + layoutRand() * 0.16;
      for (const side of [-1, 0, 1]) {
        const x = p.x + px * w * side, z = p.z + pz * w * side;
        posArr.push(x, groundH(x, z) + 0.02, z);
        const c = side === 0 ? cMid : cEdge;
        colArr.push(c.r, c.g, c.b);
      }
      if (i < rows) {
        const b = i * 3;
        idx.push(b, b + 3, b + 1, b + 1, b + 3, b + 4,
                 b + 1, b + 4, b + 2, b + 2, b + 4, b + 5);
      }
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(posArr), 3));
    g.setAttribute('color', new THREE.BufferAttribute(new Float32Array(colArr), 3));
    g.setIndex(idx);
    g.computeVertexNormals();
    const path = new THREE.Mesh(g, new THREE.MeshStandardMaterial({
      vertexColors: true, roughness: 1, metalness: 0,
      polygonOffset: true, polygonOffsetFactor: -1,
    }));
    scene.add(path);
  }

  /* Forest edge: two instanced meshes (trunks, stepped-tier
     foliage — see makePineFoliageGeo) sharing per-instance
     matrices — 245 pines at r 44–84 over the lone scattered
     pines, thinning the "few trees in a void" feel into an
     actual treeline; the outermost ring stands tallest so
     the forest reads as a wall, not a hedge. */
  {
    const trunkGeo = new THREE.CylinderGeometry(0.09, 0.15, 1.2, 8);
    trunkGeo.translate(0, 0.6, 0);
    const folGeo = makePineFoliageGeo();
    const trunks = instanced(trunkGeo,
      new THREE.MeshStandardMaterial({ color: 0xf5efe8, roughness: 1, map: barkTex }), 245);
    const fols = instanced(folGeo,
      new THREE.MeshStandardMaterial({
        color: 0xe6ebdd, roughness: 1, vertexColors: true, map: foliageTex }), 245);
    let i = 0;
    for (; i < 160; i++) {                 // the distant ring
      const a = layoutRand() * Math.PI * 2;
      const r = 54 + Math.pow(layoutRand(), 1.3) * 27;
      const x = Math.cos(a) * r, z = Math.sin(a) * r;
      const s = 0.95 + layoutRand() * 1.15;
      setInst(trunks, i, x, z, s, 0.12);
      fols.setMatrixAt(i, dummy.matrix);
      tint.setHSL(0.32, 0.3, 0.33 + layoutRand() * 0.16);
      fols.setColorAt(i, tint);
    }
    for (; i < 190; i++) {                 // a nearer blending band
      const a = layoutRand() * Math.PI * 2;
      const r = 44 + layoutRand() * 14;
      const x = Math.cos(a) * r, z = Math.sin(a) * r;
      const s = 0.85 + layoutRand() * 0.8;
      setInst(trunks, i, x, z, s, 0.12);
      fols.setMatrixAt(i, dummy.matrix);
      tint.setHSL(0.32, 0.3, 0.33 + layoutRand() * 0.16);
      fols.setColorAt(i, tint);
    }
    for (; i < 245; i++) {                 // a taller back wall (density pass)
      const a = layoutRand() * Math.PI * 2;
      const r = 66 + Math.pow(layoutRand(), 1.2) * 18;
      const x = Math.cos(a) * r, z = Math.sin(a) * r;
      const s = 1.5 + layoutRand() * 1.2;
      setInst(trunks, i, x, z, s, 0.12);
      fols.setMatrixAt(i, dummy.matrix);
      tint.setHSL(0.32, 0.3, 0.28 + layoutRand() * 0.14);
      fols.setColorAt(i, tint);
    }
    trunks.instanceMatrix.needsUpdate = true;
    fols.instanceMatrix.needsUpdate = true;
    if (fols.instanceColor) fols.instanceColor.needsUpdate = true;
  }

  /* Two nearer feature trees + a dead snag, hand-placed. */
  {
    const barkMat = new THREE.MeshStandardMaterial({ color: 0xf5efe8, roughness: 1, map: barkTex });
    const leafMat = new THREE.MeshStandardMaterial({ color: 0xd8dcc8, roughness: 1, map: foliageTex });
    // Broad oak, left mid-field.
    const oak = new THREE.Group();
    const otrunk = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.46, 2.3, 10), barkMat);
    otrunk.position.y = 1.1;
    oak.add(otrunk);
    const blobGeo = displaceGeo(new THREE.IcosahedronGeometry(1, 2), 0.13, 1.6);
    for (const [bx, by, bz, bs] of [[0, 3.4, 0, 2.2], [1.3, 2.9, 0.4, 1.6],
                                    [-1.2, 3.0, -0.5, 1.7], [0.2, 2.7, 1.1, 1.4]]) {
      const b = new THREE.Mesh(blobGeo, leafMat);
      b.position.set(bx, by, bz);
      b.scale.set(bs, bs * 0.78, bs);
      oak.add(b);
    }
    oak.position.set(-10.5, groundH(-10.5, -5.5), -5.5);
    oak.rotation.y = 0.7;
    scene.add(oak);
    // Tall pine, right mid-field.
    const pine = new THREE.Group();
    const ptrunk = new THREE.Mesh(new THREE.CylinderGeometry(0.13, 0.2, 2.2, 10), barkMat);
    ptrunk.position.y = 1.1;
    pine.add(ptrunk);
    const pfol = new THREE.Mesh(makePineFoliageGeo(),
      new THREE.MeshStandardMaterial({
        color: 0xe6ebdd, roughness: 1, vertexColors: true, map: foliageTex }));
    pfol.scale.setScalar(1.25);
    pfol.position.y = 1.15;
    pine.add(pfol);
    pine.position.set(11, groundH(11, -7.5) - 0.1, -7.5);
    scene.add(pine);
    // Dead snag, back-left — bare trunk, two branch stubs.
    const snag = new THREE.Group();
    const strunk = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.17, 3.4, 9),
      new THREE.MeshStandardMaterial({ color: 0x6b5a44, roughness: 1 }));
    strunk.position.y = 1.7;
    snag.add(strunk);
    for (const [ry, rz, len] of [[2.3, 0.7, 0.9], [2.9, -0.5, 0.65]]) {
      const br = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.05, len, 7),
        strunk.material);
      br.position.set(0.3, ry, 0);
      br.rotation.z = rz;
      snag.add(br);
    }
    snag.position.set(-16, groundH(-16, 8), 8);
    snag.rotation.z = 0.05;
    scene.add(snag);
  }

  /* Grass tufts: instanced seven-blade cones — 950 spread through
     the field, plus 300 more ringing the clearing (density pass).
     Sparse in the clearing, none on the path. AAA experiment
     stage 2: the blades sway in a vertex shader (see the
     material's onBeforeCompile below). */
  {
    const blades = [];
    for (let k = 0; k < 7; k++) {
      const b = new THREE.ConeGeometry(0.05, 0.42, 6);
      b.translate(0, 0.21, 0);
      const m = new THREE.Matrix4().makeRotationFromEuler(new THREE.Euler(
        Math.cos(k * 2.4) * 0.32, k * 1.257, Math.sin(k * 2.4) * 0.32));
      m.setPosition(Math.cos(k * 1.257) * 0.07, 0, Math.sin(k * 1.257) * 0.07);
      b.applyMatrix4(m);
      blades.push(b);
    }
    const tuftGeo = mergeGeometries(blades);
    // Wind sway: bend each blade by its height squared, phased by
    // the instance's world position so gusts travel across the
    // field. Injected into the standard material's vertex shader;
    // grass does not cast shadows, so the shadow pass never sees
    // the undisplaced-vs-displaced difference.
    const grassMat = new THREE.MeshStandardMaterial({ roughness: 1, flatShading: true });
    grassMat.onBeforeCompile = (shader) => {
      shader.uniforms.uWindTime = windUniform;
      shader.vertexShader = 'uniform float uWindTime;\n' + shader.vertexShader.replace(
        '#include <begin_vertex>',
        `#include <begin_vertex>
        {
          vec2 ip = vec2(instanceMatrix[3][0], instanceMatrix[3][2]);
          float ph = ip.x * 0.37 + ip.y * 0.29;
          float wgt = pow(clamp(position.y / 0.45, 0.0, 1.0), 2.0);
          float sway = sin(uWindTime * 1.6 + ph) * 0.6
                     + sin(uWindTime * 3.3 + ph * 1.7) * 0.4;
          transformed.x += sway * 0.06 * wgt;
          transformed.z += sway * 0.035 * wgt;
        }`);
    };
    const grass = instanced(tuftGeo, grassMat, 1250);
    grass.name = 'grassTufts';   // receives shadows; does not cast
    const gA = new THREE.Color(0x39512a), gB = new THREE.Color(0x5a7a3c);
    let placed = 0, guard = 0;
    while (placed < 1250 && guard++ < 11000) {
      const a = layoutRand() * Math.PI * 2;
      const r = placed < 950 ? 3 + Math.pow(layoutRand(), 0.75) * 49
                             : 6 + Math.pow(layoutRand(), 0.8) * 16;
      const x = Math.cos(a) * r, z = Math.sin(a) * r;
      if (r < 7 && layoutRand() < 0.55) continue;
      if (distToPath(x, z) < 0.8) continue;
      setInst(grass, placed, x, z, 0.7 + layoutRand() * 0.95, 0.02);
      tint.copy(gA).lerp(gB, layoutRand());
      grass.setColorAt(placed, tint);
      placed++;
    }
    grass.count = placed;
    grass.instanceMatrix.needsUpdate = true;
    if (grass.instanceColor) grass.instanceColor.needsUpdate = true;
  }

  /* Ferns: squashed-cone rosettes, ~115, biased toward the
     clearing edge (density pass), the rest mid-field. */
  {
    const fronds = [];
    for (let k = 0; k < 6; k++) {
      const f = new THREE.ConeGeometry(0.3, 0.55, 8);
      f.applyMatrix4(new THREE.Matrix4().makeScale(1, 0.5, 1));
      const m = new THREE.Matrix4().makeRotationFromEuler(new THREE.Euler(
        Math.cos(k * 1.047) * 0.95, 0, Math.sin(k * 1.047) * 0.95));
      m.setPosition(Math.cos(k * 1.047) * 0.13, 0.1, Math.sin(k * 1.047) * 0.13);
      f.applyMatrix4(m);
      fronds.push(f);
    }
    const fernGeo = mergeGeometries(fronds);
    const ferns = instanced(fernGeo,
      new THREE.MeshStandardMaterial({ color: 0x2a4a26, roughness: 1, flatShading: true }), 115);
    let placed = 0, guard = 0;
    while (placed < 115 && guard++ < 1600) {
      const a = layoutRand() * Math.PI * 2;
      const r = layoutRand() < 0.55 ? 5.5 + layoutRand() * 10.5
                                    : 6 + layoutRand() * 40;
      const x = Math.cos(a) * r, z = Math.sin(a) * r;
      if (distToPath(x, z) < 0.9) continue;
      const fs = 0.6 + layoutRand() * 0.75;
      setInst(ferns, placed, x, z, fs, 0.02);
      BUILDER_SWAPS.fernSpots.push([x, z, fs]);
      placed++;
    }
    ferns.count = placed;
    ferns.instanceMatrix.needsUpdate = true;
    BUILDER_SWAPS.fernMesh = ferns;
  }

  /* More bushes, seven of them dotted with berries (one instanced
     berry mesh shared across all seven). */
  {
    const bushGeo2 = new THREE.IcosahedronGeometry(1, 2);
    const bushMat2 = new THREE.MeshStandardMaterial({ color: 0xd8dcc8, roughness: 1, map: foliageTex });
    const berrySpots = [];
    for (let i = 0; i < 10; i++) {
      const a = layoutRand() * Math.PI * 2;
      const r = 6.5 + layoutRand() * 26;
      const x = Math.cos(a) * r, z = Math.sin(a) * r;
      const s = 0.55 + layoutRand() * 0.85;
      const bush = new THREE.Mesh(bushGeo2, bushMat2);
      bush.scale.set(s, s * 0.62, s);
      bush.position.set(x, groundH(x, z) + s * 0.25, z);
      bush.rotation.y = layoutRand() * Math.PI * 2;
      scene.add(bush);
      BUILDER_SWAPS.meshes.push({ obj: bush, kind: 'bush' });
      if (i < 7) {
        for (let k = 0; k < 9; k++) {
          const th = layoutRand() * Math.PI * 2, ph = layoutRand() * 1.1;
          berrySpots.push([
            x + Math.cos(th) * Math.sin(ph) * s * 0.92,
            bush.position.y + Math.cos(ph) * s * 0.55,
            z + Math.sin(th) * Math.sin(ph) * s * 0.92]);
        }
      }
    }
    const berries = instanced(new THREE.SphereGeometry(0.038, 10, 8),
      new THREE.MeshStandardMaterial({ color: 0x8e2430, emissive: 0x38060c, roughness: 0.5 }),
      berrySpots.length);
    berrySpots.forEach(([x, y, z], i) => {
      dummy.position.set(x, y, z);
      dummy.rotation.set(0, 0, 0);
      dummy.scale.setScalar(0.8 + layoutRand() * 0.5);
      dummy.updateMatrix();
      berries.setMatrixAt(i, dummy.matrix);
    });
    berries.instanceMatrix.needsUpdate = true;
  }

  /* Glowing mushrooms: instanced stems + emissive caps in nine
     clusters, one soft glow sprite per cluster (additive sprites,
     not lights). */
  {
    const anchors = [[-9.2, -3.4], [12.3, -6.2], [5.8, -3.4], [-6.4, 6.8],
                     [14.5, 3.5], [-15, -1.5], [2.5, -10.5], [19, -7], [-3.5, 12.5]];
    const stemGeo = new THREE.CylinderGeometry(0.035, 0.055, 0.17, 9);
    stemGeo.translate(0, 0.085, 0);
    const capGeo = new THREE.SphereGeometry(0.115, 14, 8, 0, Math.PI * 2, 0, Math.PI / 2);
    capGeo.translate(0, 0.15, 0);
    const spots = [];
    for (const [ax, az] of anchors) {
      const n = 3 + Math.floor(layoutRand() * 4);
      for (let k = 0; k < n; k++) {
        const a = layoutRand() * Math.PI * 2, rr = layoutRand() * 0.55;
        spots.push([ax + Math.cos(a) * rr, az + Math.sin(a) * rr,
                    0.6 + layoutRand() * 1.1]);
      }
    }
    const stems = instanced(stemGeo,
      new THREE.MeshStandardMaterial({ color: 0xcfc4a5, roughness: 0.9 }), spots.length);
    const capMat = new THREE.MeshStandardMaterial({
      color: 0x1d3a30, emissive: 0x5fe8c0, emissiveIntensity: 1.15, roughness: 0.6,
    });
    const caps = instanced(capGeo, capMat, spots.length);
    spots.forEach(([x, z, s], i) => {
      setInst(stems, i, x, z, s, 0.01);
      caps.setMatrixAt(i, dummy.matrix);
    });
    stems.instanceMatrix.needsUpdate = true;
    caps.instanceMatrix.needsUpdate = true;
    BUILDER_SWAPS.mushroomMeshes = [stems, caps];
    BUILDER_SWAPS.mushroomAnchors = anchors;

    const glowTex = radialSpriteTexture('rgba(140,255,215,0.85)', 'rgba(140,255,215,0)');
    const glows = [];
    anchors.forEach(([ax, az], ci) => {
      const sm = new THREE.SpriteMaterial({
        map: glowTex, color: 0x86ffd9, transparent: true, opacity: 0.2,
        blending: THREE.AdditiveBlending, depthWrite: false,
      });
      const spr = new THREE.Sprite(sm);
      spr.position.set(ax, groundH(ax, az) + 0.32, az);
      spr.scale.set(1.5, 1.5, 1);
      scene.add(spr);
      glows.push({ sm, phase: ci * 1.37 });
    });
    dressingUpdaters.push((t) => {
      // Glow only reads after dark; by day the caps go quiet too.
      const f = 0.1 + 0.9 * nightFactor;
      for (const g of glows) g.sm.opacity = (0.16 + 0.08 * Math.sin(t * 1.4 + g.phase)) * f;
      capMat.emissiveIntensity = 0.15 + 1.0 * nightFactor;
    });
  }

  /* Fireflies: one Points cloud, ~64 motes wandering the mid-field
     on slow sine paths with individual twinkles. */
  {
    const N = 64;
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(N * 3), 3));
    geo.setAttribute('color', new THREE.BufferAttribute(new Float32Array(N * 3), 3));
    const pts = new THREE.Points(geo, new THREE.PointsMaterial({
      size: 0.14, map: radialSpriteTexture('rgba(255,255,255,1)', 'rgba(255,255,255,0)'),
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
      vertexColors: true, sizeAttenuation: true,
    }));
    pts.frustumCulled = false;
    scene.add(pts);
    const motes = Array.from({ length: N }, () => {
      const a = layoutRand() * Math.PI * 2, r = 5 + layoutRand() * 33;
      return {
        x: Math.cos(a) * r, z: Math.sin(a) * r,
        y: 0.4 + layoutRand() * 1.8,
        seed: layoutRand() * 100, speed: 0.5 + layoutRand() * 0.9,
      };
    });
    const posA = geo.attributes.position, colA = geo.attributes.color;
    dressingUpdaters.push((t) => {
      for (let i = 0; i < N; i++) {
        const m = motes[i];
        posA.setXYZ(i,
          m.x + Math.sin(t * 0.31 * m.speed + m.seed) * 0.9,
          m.y + Math.sin(t * 0.53 * m.speed + m.seed * 1.7) * 0.28,
          m.z + Math.cos(t * 0.26 * m.speed + m.seed * 0.6) * 0.9);
        const tw = nightFactor *
          (0.25 + 0.75 * Math.pow(0.5 + 0.5 * Math.sin(t * m.speed * 2.2 + m.seed * 3), 2));
        colA.setXYZ(i, tw, tw * 0.82, tw * 0.38);
      }
      posA.needsUpdate = true;
      colA.needsUpdate = true;
    });
  }

  /* Fire-circle furniture: two log benches flanking the gathering,
     three stump seats behind, a woodpile + chopping block to the
     right. All outside the spot ring (r 2.75) and off the path. */
  {
    const barkMat = new THREE.MeshStandardMaterial({ color: 0xf5efe8, roughness: 1, map: barkTex });
    const endMat = new THREE.MeshStandardMaterial({ color: 0xa9834f, roughness: 0.9 });
    const logMats = [barkMat, endMat, endMat];
    function bench(a, r) {
      const g = new THREE.Group();
      const seat = new THREE.Mesh(new THREE.CylinderGeometry(0.15, 0.15, 1.7, 12), logMats);
      seat.rotation.z = Math.PI / 2;
      seat.position.y = 0.46;
      g.add(seat);
      for (const sx of [-0.55, 0.55]) {
        const sup = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.18, 0.34, 10), logMats);
        sup.position.set(sx, 0.17, 0);
        g.add(sup);
      }
      const x = Math.sin(a) * r, z = Math.cos(a) * r;
      g.position.set(x, groundH(x, z), z);
      g.rotation.y = a;
      scene.add(g);
    }
    bench(1.75, 3.5);
    bench(-1.75, 3.5);
    for (const a of [2.6, -2.6, Math.PI]) {
      const x = Math.sin(a) * 3.2, z = Math.cos(a) * 3.2;
      const stump = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.34, 0.48, 12), logMats);
      stump.position.set(x, groundH(x, z) + 0.24, z);
      scene.add(stump);
      BUILDER_SWAPS.meshes.push({ obj: stump, kind: 'stump' });
    }
    const pile = new THREE.Group();
    const logGeo2 = new THREE.CylinderGeometry(0.11, 0.11, 1.15, 10);
    for (const [lx, ly] of [[-0.24, 0.11], [0, 0.11], [0.24, 0.11],
                            [-0.12, 0.3], [0.12, 0.3], [0, 0.49]]) {
      const log = new THREE.Mesh(logGeo2, logMats);
      log.rotation.x = Math.PI / 2;
      log.position.set(lx, ly, 0);
      pile.add(log);
    }
    pile.position.set(4.7, groundH(4.7, 2.1), 2.1);
    pile.rotation.y = -0.5;
    scene.add(pile);
    const block = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.34, 0.5, 12), logMats);
    block.position.set(3.9, groundH(3.9, 3.3) + 0.25, 3.3);
    scene.add(block);
    BUILDER_SWAPS.meshes.push({ obj: block, kind: 'stump' });
    const split = new THREE.Mesh(new THREE.CylinderGeometry(0.13, 0.13, 0.5, 10), logMats);
    split.position.set(3.9, groundH(3.9, 3.3) + 0.72, 3.3);
    scene.add(split);
  }

  /* Distant hills: squashed domes on the horizon. Their colour
     follows the sky palette (registered as a sky follower) so they
     silhouette at dusk and haze blue-grey by day. */
  {
    const hillMat = new THREE.MeshBasicMaterial({ map: ridgeTex, fog: false });
    skyFollowers.push((P) => {
      hillMat.color.copy(P.hor).lerp(P.mid, 0.75).multiplyScalar(0.34);
    });
    const hillGeo = new THREE.SphereGeometry(1, 40, 20);
    for (const [hx, hz, w, h] of [[-95, -105, 62, 13], [15, -130, 80, 17],
                                  [100, -90, 55, 11], [-135, -25, 48, 9],
                                  [135, -35, 52, 10], [-40, -145, 70, 14]]) {
      const hill = new THREE.Mesh(hillGeo, hillMat);
      hill.position.set(hx, -1.5, hz);
      hill.scale.set(w, h, w * 0.55);
      scene.add(hill);
    }
  }

  /* Mountain vista to the south (density pass — Adam's reference
     photo: a fire in a forest clearing, a layered snow-capped
     range beyond the trees). Three ridge silhouettes span the
     facing horizon: a dark forested ridge, a blue mid ridge, and
     a far snow-capped range. Each is a skyline ribbon with baked
     vertex colours (rock gradient; snow above a jagged snowline
     on the far range only), tinted per frame from the sky
     palette like the hills — warm at sunset, blue distance at
     noon, near-black at night. Aligned notches at ±65° leave a
     pass on each side where the rising/setting sun can still
     touch the horizon line. */
  function buildRidge(R, baseY, peakY, cols, snowline, jag, tintFn) {
    const span = 1.40, steps = 160;
    const bumps = [];
    for (let k = 0; k < 8; k++) {
      bumps.push({
        c: -span + (2 * span) * (k + 0.2 + layoutRand() * 0.6) / 8,
        w: (0.15 + layoutRand() * 0.24) * jag,
        h: 0.40 + layoutRand() * 0.60,
      });
    }
    const prof = (th) => {
      let y = 0.10;
      for (const b of bumps) {
        const d = (th - b.c) / b.w;
        y += b.h * Math.exp(-d * d);
      }
      y *= 1 + 0.10 * Math.sin(th * 61 + R) * Math.sin(th * 23 + 1.7);
      const notch = Math.exp(-Math.pow((Math.abs(th) - 1.13) / 0.10, 2));
      y *= 1 - 0.78 * notch;
      return baseY + (Math.min(y, 1.25) / 1.25) * (peakY - baseY);
    };
    const pos = [], col = [], uv = [], idx = [];
    const cBase = new THREE.Color(cols[0]), cMid = new THREE.Color(cols[1]),
          cTop = new THREE.Color(cols[2]), cSnow = new THREE.Color(0xe9eae2),
          cc = new THREE.Color();
    // AAA experiment stage 4: the ridges stop being flat cards.
    // Five rows per column lean the face toward the viewer like
    // a real slope, the material is lit and textured (the pale
    // ridge rock), and the snowline is a soft blend instead of
    // a hard vertex-colour switch. (The snow jitter is pure sin
    // now, not layoutRand — downstream scatter lands in new
    // spots, same in kind.)
    const rowsT = [0, 0.22, 0.45, 0.7, 1];
    for (let i = 0; i <= steps; i++) {
      const th = -span + (2 * span * i) / steps;
      const x = Math.sin(th) * R, z = Math.cos(th) * R;
      const y = prof(th);
      const snowEdge = snowline === null ? 2 :
        snowline + 0.07 * Math.sin(th * 34) + 0.04 * Math.sin(th * 91 + R);
      for (let r = 0; r < rowsT.length; r++) {
        const t = rowsT[r];
        const ry = y + t * (-8 - y);
        const rz = z - t * R * 0.10;
        const h01 = THREE.MathUtils.clamp((ry - baseY) / (peakY - baseY), 0, 1);
        cc.copy(cBase).lerp(cMid, Math.min(h01 * 1.6, 1))
          .lerp(cTop, Math.max(0, h01 * 1.4 - 0.4));
        if (snowline !== null) {
          cc.lerp(cSnow, THREE.MathUtils.smoothstep(h01, snowEdge - 0.05, snowEdge + 0.06));
        }
        if (r === rowsT.length - 1) cc.multiplyScalar(0.75);
        pos.push(x, ry, rz); col.push(cc.r, cc.g, cc.b);
        uv.push(i / steps * 30, t * 3);
      }
      if (i < steps) {
        for (let r = 0; r < rowsT.length - 1; r++) {
          const a = i * rowsT.length + r, b = a + 1, c = a + rowsT.length, d = b + rowsT.length;
          idx.push(a, b, c, b, d, c);
        }
      }
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(pos), 3));
    g.setAttribute('color', new THREE.BufferAttribute(new Float32Array(col), 3));
    g.setAttribute('uv', new THREE.BufferAttribute(new Float32Array(uv), 2));
    g.setIndex(idx);
    g.computeVertexNormals();
    // Unlit on purpose: the ridges are backdrop, and their
    // day/night life (alpenglow at dusk, blue distance at noon)
    // comes from the palette tint, not from scene light. Stage
    // 4's first cut made them lit standard materials and the
    // sunset alpenglow died to black — the win was the geometry
    // and texture, not the lighting, so the lighting went back.
    const mat = new THREE.MeshBasicMaterial({
      vertexColors: true, map: ridgeTex, fog: false,
      side: THREE.DoubleSide,
    });
    skyFollowers.push((P) => tintFn(mat, P));
    const mesh = new THREE.Mesh(g, mat);
    mesh.frustumCulled = false;
    scene.add(mesh);
  }
  buildRidge(118, 3, 24, [0x2a3324, 0x39443a, 0x4c5c50], null, 1.0,
    (mat, P) => mat.color.copy(P.fog).lerp(P.mid, 0.3).multiplyScalar(0.6));
  buildRidge(142, 4, 34, [0x39445c, 0x5a6a86, 0x8294b2], null, 0.9,
    (mat, P) => mat.color.copy(P.mid).lerp(P.top, 0.35).multiplyScalar(0.95));
  buildRidge(168, 5, 45, [0x46536e, 0x71809c, 0xa9b8d0], 0.78, 0.7,
    (mat, P) => mat.color.copy(P.hor).lerp(P.top, 0.35).multiplyScalar(1.15));

  /* No foreground framing pines: the density pass planted four
     large pines around the camera to frame the view, and the
     owner asked for them gone (2026-11-09) — the clearing is
     viewed across open field again, the forest edge and the
     ridges carry the frame. (Removing the block shifts the
     seeded layout sequence for the scatter placed after it —
     moss, rocks, logs land in new spots; the treeline, placed
     earlier, is unchanged.) */

  /* Moss patches: dark-green discs mottling the forest floor —
     outside the clearing and off the path (density pass). */
  {
    const mossGeo = new THREE.CircleGeometry(1, 20);
    mossGeo.rotateX(-Math.PI / 2);
    const moss = instanced(mossGeo, new THREE.MeshStandardMaterial({
      color: 0x2a4423, roughness: 1,
      polygonOffset: true, polygonOffsetFactor: -1,
    }), 46);
    let placed = 0, guard = 0;
    while (placed < 46 && guard++ < 900) {
      const a = layoutRand() * Math.PI * 2;
      const r = 4.6 + Math.pow(layoutRand(), 0.8) * 35;
      const x = Math.cos(a) * r, z = Math.sin(a) * r;
      if (distToPath(x, z) < 1.1) continue;
      setInst(moss, placed, x, z, 0.5 + layoutRand() * 1.2, -0.015);
      placed++;
    }
    moss.count = placed;
    moss.instanceMatrix.needsUpdate = true;
  }

  /* More scattered rocks, two in five moss-tinted (density pass). */
  {
    const rocks = instanced(new THREE.DodecahedronGeometry(1, 1),
      new THREE.MeshStandardMaterial({ roughness: 0.95, flatShading: true }), 30);
    const grey = new THREE.Color(0x5d6068), mossy = new THREE.Color(0x51603c);
    let placed = 0, guard = 0;
    while (placed < 30 && guard++ < 700) {
      const a = layoutRand() * Math.PI * 2;
      const r = 4.6 + layoutRand() * 41;
      const x = Math.cos(a) * r, z = Math.sin(a) * r;
      if (distToPath(x, z) < 1.0) continue;
      const s = 0.18 + layoutRand() * 0.55;
      dummy.position.set(x, groundH(x, z) - s * 0.3, z);
      dummy.rotation.set(layoutRand() * 3, layoutRand() * 3, layoutRand() * 3);
      dummy.scale.set(s, s * (0.55 + layoutRand() * 0.4), s * (0.7 + layoutRand() * 0.5));
      dummy.updateMatrix();
      rocks.setMatrixAt(placed, dummy.matrix);
      tint.copy(layoutRand() < 0.4 ? mossy : grey)
        .multiplyScalar(0.8 + layoutRand() * 0.4);
      rocks.setColorAt(placed, tint);
      placed++;
    }
    rocks.count = placed;
    rocks.instanceMatrix.needsUpdate = true;
    if (rocks.instanceColor) rocks.instanceColor.needsUpdate = true;
  }

  /* Two fallen logs resting at the clearing edge (density pass). */
  {
    const barkMat = new THREE.MeshStandardMaterial({ color: 0xf5efe8, roughness: 1, map: barkTex });
    const endMat = new THREE.MeshStandardMaterial({ color: 0xa9834f, roughness: 0.9 });
    const logMats = [barkMat, endMat, endMat];
    function fallenLog(x, z, rotY, len) {
      const g = new THREE.Group();
      const trunk = new THREE.Mesh(
        new THREE.CylinderGeometry(0.17, 0.21, len, 12), logMats);
      trunk.rotation.z = Math.PI / 2;
      trunk.position.y = 0.17;
      g.add(trunk);
      const stub = new THREE.Mesh(
        new THREE.CylinderGeometry(0.05, 0.07, 0.7, 9), barkMat);
      stub.position.set(len * 0.22, 0.42, 0.08);
      stub.rotation.z = -0.7;
      g.add(stub);
      g.position.set(x, groundH(x, z), z);
      g.rotation.y = rotY;
      scene.add(g);
      BUILDER_SWAPS.meshes.push({ obj: g, kind: 'log', len });
    }
    fallenLog(-8.2, 5.5, 0.9, 2.6);
    fallenLog(10.5, -2.5, -0.6, 2.2);
  }

  /* An occasional shooting star: one additive sprite streaking the
     upper sky every ~10–25 s. Pure decoration, zero steady cost. */
  {
    const sm = new THREE.SpriteMaterial({
      map: radialSpriteTexture('rgba(255,255,255,1)', 'rgba(255,255,255,0)'),
      color: 0xdfe9ff, transparent: true, opacity: 0,
      blending: THREE.AdditiveBlending, depthWrite: false, fog: false,
      rotation: -0.24,
    });
    const star = new THREE.Sprite(sm);
    star.scale.set(4.6, 0.5, 1);
    star.position.set(0, 60, -150);
    scene.add(star);
    const st = { next: 6 + layoutRand() * 10, t0: -1, from: new THREE.Vector3() };
    dressingUpdaters.push((t) => {
      if (st.t0 < 0 && t >= st.next) {
        st.t0 = t;
        st.from.set(40 + layoutRand() * 60, 52 + layoutRand() * 20, -150);
      }
      if (st.t0 >= 0) {
        const p = (t - st.t0) / 0.9;
        if (p >= 1) {
          st.t0 = -1;
          st.next = t + 9 + layoutRand() * 16;
          sm.opacity = 0;
        } else {
          star.position.set(st.from.x - 58 * p, st.from.y - 13 * p, -150);
          sm.opacity = Math.sin(p * Math.PI) * 0.8;
        }
      }
    });
  }
}

/* ----------------------------------------------------------- campfire */

const FIRE_POS = new THREE.Vector3(0, 0, 0);
let fireLight, glowDisc, bounceLight;
const flameSystems = [];
// AAA experiment stage 2: the shader flame's per-plane uniforms
// and the smoke sprite pool, both driven from updateFire.
const flameUniformsList = [];
const smokePuffs = [];

function makeParticles(count, size, color, blending) {
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position',
    new THREE.BufferAttribute(new Float32Array(count * 3), 3));
  geo.setAttribute('color',
    new THREE.BufferAttribute(new Float32Array(count * 3), 3));
  const mat = new THREE.PointsMaterial({
    size, map: radialSpriteTexture('rgba(255,255,255,1)', 'rgba(255,255,255,0)'),
    transparent: true, depthWrite: false, blending: blending || THREE.AdditiveBlending,
    vertexColors: true, sizeAttenuation: true,
  });
  const points = new THREE.Points(geo, mat);
  points.frustumCulled = false;
  scene.add(points);
  return points;
}

function resetParticle(sys, p, randomAge) {
  p.life = sys.kind === 'flame' ? rand(0.5, 1.0) : rand(2.2, 4.4);
  p.age = randomAge ? Math.random() * p.life : 0;
  const r = Math.sqrt(Math.random()) * 0.3, a = Math.random() * Math.PI * 2;
  p.x = Math.cos(a) * r; p.z = Math.sin(a) * r;
  const n = p.age / p.life;
  p.y = sys.kind === 'flame' ? 0.22 + n * 0.55 : 0.4 + n * 2.4;
  p.vy = sys.kind === 'flame' ? 1.0 : rand(0.9, 1.3);
}

{
  const fire = new THREE.Group();
  scene.add(fire);

  // Stone ring: sixteen individual rocks around the pit, varied
  // in size, shape, tilt and shade (instanced; density pass).
  const stoneGeo = new THREE.DodecahedronGeometry(0.17, 1);
  const stoneMat = new THREE.MeshStandardMaterial({ roughness: 1, flatShading: true, map: rockTex });
  const stones = new THREE.InstancedMesh(stoneGeo, stoneMat, 16);
  stones.frustumCulled = false;
  {
    const sd = new THREE.Object3D(), sc = new THREE.Color();
    for (let i = 0; i < 16; i++) {
      const a = (i / 16) * Math.PI * 2 + 0.2 + (layoutRand() - 0.5) * 0.18;
      const r = 0.92 + layoutRand() * 0.14;
      const s = 0.75 + layoutRand() * 0.75;
      sd.position.set(Math.cos(a) * r, 0.05, Math.sin(a) * r);
      sd.rotation.set(layoutRand() * 3, layoutRand() * 3, layoutRand() * 3);
      sd.scale.set(s, s * (0.6 + layoutRand() * 0.35), s * (0.75 + layoutRand() * 0.4));
      sd.updateMatrix();
      stones.setMatrixAt(i, sd.matrix);
      sc.setHSL(0.08, 0.03 + layoutRand() * 0.05, 0.34 + layoutRand() * 0.16);
      stones.setColorAt(i, sc);
    }
    stones.instanceMatrix.needsUpdate = true;
    if (stones.instanceColor) stones.instanceColor.needsUpdate = true;
  }
  fire.add(stones);
  // Log pile: a low teepee of cylinders plus two crossed logs.
  const logGeo = new THREE.CylinderGeometry(0.075, 0.09, 1.15, 10);
  const logMat = new THREE.MeshStandardMaterial({ color: 0xf5efe8, roughness: 1, map: barkTex });
  for (let i = 0; i < 5; i++) {
    const a = (i / 5) * Math.PI * 2;
    const log = new THREE.Mesh(logGeo, logMat);
    log.position.set(Math.cos(a) * 0.3, 0.26, Math.sin(a) * 0.3);
    log.rotation.set(Math.sin(a) * 0.85, 0, Math.cos(a) * 0.85);
    fire.add(log);
  }
  // Warm glow pooled on the ground.
  glowDisc = new THREE.Mesh(
    new THREE.CircleGeometry(2.6, 48),
    new THREE.MeshBasicMaterial({
      map: radialSpriteTexture('rgba(255,140,50,0.5)', 'rgba(255,140,50,0)'),
      transparent: true, blending: THREE.AdditiveBlending, depthWrite: false,
    }));
  glowDisc.rotation.x = -Math.PI / 2;
  glowDisc.position.y = 0.03;
  fire.add(glowDisc);

  fireLight = new THREE.PointLight(0xff8a3d, 26, 34, 2);
  fireLight.position.set(0, 0.85, 0);
  fire.add(fireLight);
  // A whisper of warm bounce on the spots side of the fire, so the
  // gathered creatures' flame-lit faces read as more than
  // silhouettes from the south-facing camera.
  bounceLight = new THREE.PointLight(0xff9a50, 5, 13, 2);
  bounceLight.position.set(0, 0.6, 1.9);
  fire.add(bounceLight);

  // AAA experiment stage 2: a continuous flame body under the
  // particles — three crossed planes with a procedural flame
  // shader (scrolling fbm noise erodes a teardrop mask; the
  // colour ramps deep orange -> yellow -> near-white at the
  // base). The particle flames above read as tongues and licks
  // off this body instead of the whole fire.
  const flameVert = `
    varying vec2 vUv;
    void main() {
      vUv = uv;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }`;
  const flameFrag = `
    varying vec2 vUv;
    uniform float uTime, uScale, uSeed;
    float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
    float noise(vec2 p) {
      vec2 i = floor(p), f = fract(p);
      f = f * f * (3.0 - 2.0 * f);
      return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x),
                 mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y);
    }
    float fbm(vec2 p) {
      float v = 0.0, a = 0.5;
      for (int i = 0; i < 4; i++) { v += a * noise(p); p *= 2.03; a *= 0.5; }
      return v;
    }
    void main() {
      vec2 uv = vUv;
      float rise = fbm(vec2(uv.x * 3.0 + uSeed, uv.y * 2.4 - uTime * 1.7 + uSeed));
      float rise2 = fbm(vec2(uv.x * 7.0 - uSeed, uv.y * 5.0 - uTime * 2.6));
      float cx = abs(uv.x - 0.5) + (rise - 0.5) * 0.34 * (0.25 + uv.y);
      float width = mix(0.40, 0.015, pow(uv.y, 0.75));
      float body = smoothstep(width, width - 0.30, cx);
      float base = smoothstep(0.0, 0.14, uv.y);
      float inten = body * base * (1.0 - uv.y * 0.72) * (0.75 + rise2 * 0.5);
      vec3 col = mix(vec3(0.95, 0.22, 0.01), vec3(1.0, 0.55, 0.08), inten);
      col = mix(col, vec3(1.0, 0.88, 0.45), smoothstep(0.55, 0.95, inten - uv.y * 0.35));
      gl_FragColor = vec4(col * inten * 1.8 * uScale, inten * uScale);
    }`;
  for (let i = 0; i < 3; i++) {
    const fu = { uTime: { value: 0 }, uScale: { value: 1 }, uSeed: { value: i * 7.31 } };
    const fm = new THREE.ShaderMaterial({
      uniforms: fu, vertexShader: flameVert, fragmentShader: flameFrag,
      transparent: true, depthWrite: false,
      blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
    });
    const plane = new THREE.Mesh(new THREE.PlaneGeometry(0.8, 1.05), fm);
    plane.rotation.y = i * Math.PI / 3;
    plane.position.y = 0.6;
    plane.renderOrder = 6;
    fire.add(plane);
    flameUniformsList.push(fu);
  }

  // Smoke: a slow pool of soft sprites that swell, drift with
  // the wind (+x), and fade; nearly invisible at night, as smoke
  // mostly is. Driven from updateFire.
  const smokeTex = radialSpriteTexture('rgba(205,210,220,0.9)', 'rgba(205,210,220,0)');
  for (let i = 0; i < 12; i++) {
    const sm = new THREE.SpriteMaterial({
      map: smokeTex, transparent: true, opacity: 0,
      depthWrite: false, color: 0x42464e,
    });
    const sp = new THREE.Sprite(sm);
    sp.renderOrder = 5;
    sp.userData.seed = Math.random();
    fire.add(sp);
    smokePuffs.push(sp);
  }

  // Flames: short-lived particles that narrow and redden as they rise.
  const flames = makeParticles(90, 0.62);
  const flameSys = {
    points: flames, count: 90, kind: 'flame',
    parts: Array.from({ length: 90 }, () => ({ seed: Math.random() * 10 })),
  };
  flameSys.parts.forEach((p) => resetParticle(flameSys, p, true));
  flameSystems.push(flameSys);
  // Embers: fewer, smaller, longer-lived, swaying as they climb.
  const embers = makeParticles(46, 0.085);
  const emberSys = {
    points: embers, count: 46, kind: 'ember',
    parts: Array.from({ length: 46 }, () => ({ seed: Math.random() * 10 })),
  };
  emberSys.parts.forEach((p) => resetParticle(emberSys, p, true));
  flameSystems.push(emberSys);
}

const _fc = new THREE.Color(), _fc2 = new THREE.Color();
function updateFire(t, dt) {
  const flicker = 0.82 + 0.18 * (Math.sin(t * 11.3) * 0.4 + Math.sin(t * 23.7 + 1.7) * 0.35 +
                                 Math.sin(t * 5.1 + 0.4) * 0.45);
  // The fire burns around the clock, but daylight shrinks its
  // presence: fireScale (from updateSky) is 1.0 at night, ~0.35 by
  // day. The flicker rides on top either way.
  fireLight.intensity = 26 * flicker * fireScale;
  bounceLight.intensity = 5 * fireScale;
  glowDisc.material.opacity = (0.75 + 0.25 * flicker) * (0.3 + 0.7 * fireScale);
  const gs = 1 + 0.05 * Math.sin(t * 7.3);
  glowDisc.scale.set(gs, gs, 1);

  for (const sys of flameSystems) {
    const pos = sys.points.geometry.attributes.position;
    const col = sys.points.geometry.attributes.color;
    for (let i = 0; i < sys.count; i++) {
      const p = sys.parts[i];
      p.age += dt;
      if (p.age >= p.life) resetParticle(sys, p, false);
      const n = p.age / p.life;
      if (sys.kind === 'flame') {
        p.y += dt * p.vy * (1.05 - n * 0.35);
        p.x *= (1 - 0.9 * dt * n); p.z *= (1 - 0.9 * dt * n);
        _fc.setRGB(1, 0.82, 0.35).lerp(_fc2.setRGB(0.9, 0.25, 0.03), n);
        _fc.multiplyScalar((1 - n) * (0.75 + 0.25 * flicker) * (0.35 + 0.65 * fireScale));
      } else {
        p.y += dt * p.vy;
        p.x += Math.sin(p.age * 2.1 + p.seed) * 0.25 * dt;
        p.z += Math.cos(p.age * 1.7 + p.seed) * 0.25 * dt;
        const tw = 0.6 + 0.4 * Math.sin(p.age * 9 + p.seed * 3);
        _fc.setRGB(1, 0.5, 0.12).multiplyScalar(
          Math.max(0, 1 - n * 1.15) * tw * (0.35 + 0.65 * fireScale));
      }
      pos.setXYZ(i, p.x, p.y, p.z);
      col.setXYZ(i, _fc.r, _fc.g, _fc.b);
    }
    pos.needsUpdate = true;
    col.needsUpdate = true;
  }

  // AAA experiment stage 2: flame body + smoke (see the fire
  // block for the setup).
  for (const fu of flameUniformsList) {
    fu.uTime.value = t;
    fu.uScale.value = (0.3 + 0.7 * fireScale) * (0.8 + 0.35 * flicker);
  }
  for (const sp of smokePuffs) {
    const seed = sp.userData.seed, cycle = 8 + seed * 4;
    const n = ((t * (0.75 + seed * 0.3) + seed * cycle) % cycle) / cycle;
    sp.position.set(
      (seed - 0.5) * 0.9 * n + n * n * 4.2 + Math.sin(seed * 40) * 0.2,
      1.1 + n * 4.3,
      (seed - 0.5) * 0.5 + Math.sin(t * 0.4 + seed * 20) * 0.18 * n);
    const sc = 0.7 + n * 2.6;
    sp.scale.set(sc, sc, 1);
    sp.material.opacity = Math.sin(Math.PI * Math.min(1, n * 1.06)) *
      0.10 * (1 - nightFactor * 0.65);
  }
}

/* ---------------------------------------------------------- creatures */

// Per-creature facts. `travelStyle` is the fallback locomotion used
// until a GLB provides a walk clip (see the director's clip choice).
const CREATURES = [
  { slug: 'ember-dragon', file: 'assets/ember-dragon.glb', height: 1.5,
    speed: 1.05, travelStyle: 'hop', signature: 'hop', bobAmp: 0.2 },
  { slug: 'snow-goblin', file: 'assets/snow-goblin.glb', height: 1.12,
    speed: 1.3, travelStyle: 'glide', signature: 'wave', bobAmp: 0.03 },
  { slug: 'triceratops', file: 'assets/triceratops.glb', height: 1.3,
    speed: 0.9, travelStyle: 'bounce', signature: 'bounce', bobAmp: 0.11 },
  { slug: 'moth-hart', file: 'assets/moth-hart.glb', height: 1.45,
    speed: 0.95, travelStyle: 'glide', signature: 'fan', bobAmp: 0.04 },
  { slug: 'toasty', file: 'assets/toasty.glb', height: 1.05,
    speed: 1.25, travelStyle: 'bounce', signature: 'bounce', bobAmp: 0.12 },
  { slug: 'lantern-snail', file: 'assets/lantern-snail.glb', height: 0.8,
    speed: 0.45, travelStyle: 'glide', signature: 'retract', bobAmp: 0.02 },
  { slug: 'axolotl-capybara', file: 'assets/axolotl-capybara.glb', height: 0.95,
    speed: 0.8, travelStyle: 'bounce', signature: 'wiggle', bobAmp: 0.07 },
  { slug: 'geode-tortoise', file: 'assets/geode-tortoise.glb', height: 0.9,
    speed: 0.5, travelStyle: 'bounce', signature: 'shiver', bobAmp: 0.04 },
  { slug: 'crow-postman', file: 'assets/crow-postman.glb', height: 1.15,
    speed: 1.2, travelStyle: 'glide', signature: 'bow', bobAmp: 0.03 },
  { slug: 'mandrake-toddler', file: 'assets/mandrake-toddler.glb', height: 0.95,
    speed: 1.1, travelStyle: 'bounce', signature: 'scream', bobAmp: 0.09 },
  { slug: 'ember-owl-cat', file: 'assets/ember-owl-cat.glb', height: 1.0,
    speed: 0.9, travelStyle: 'bounce', signature: 'headturn', bobAmp: 0.06 },
];
const MAX_ACTIVE = 3;
const SPAWN_RADIUS = 30;

const loader = new GLTFLoader();
const templates = new Map();   // slug -> { cfg, scene, animations, clips }

// Crisp creature textures at grazing angles: without anisotropy
// the GLB maps smear on ground-level views. Capped at 8 — past
// that the sampling cost buys nothing on these textures. Set
// once on the template; SkeletonUtils clones share the maps.
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
const loadErrors = [];

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

function loadTemplate(cfg) {
  return new Promise((resolve) => {
    loader.load(cfg.file, (gltf) => {
      sharpenTextures(gltf.scene);
      // Normalize: uniform scale so the model's bounding box matches
      // the configured height, feet on y=0, centred on x/z.
      const box = new THREE.Box3().setFromObject(gltf.scene);
      const size = box.getSize(new THREE.Vector3());
      const scale = cfg.height / (size.y || 1);
      gltf.scene.scale.setScalar(scale);
      const box2 = new THREE.Box3().setFromObject(gltf.scene);
      gltf.scene.position.set(
        -(box2.min.x + box2.max.x) / 2, -box2.min.y,
        -(box2.min.z + box2.max.z) / 2);
      const holder = new THREE.Group();
      holder.add(gltf.scene);
      const anims = gltf.animations || [];
      const clips = {
        idle: findClip(anims, ['idle']),
        // The director prefers a walk clip for travel whenever the
        // GLB provides one (the catalog does since GAB P4); without
        // one, travel falls back to cfg.travelStyle + signature clip.
        walk: findClip(anims, ['walk']),
        signature: findClip(anims, [cfg.signature]),
      };
      templates.set(cfg.slug, { cfg, holder, clips });
      resolve(true);
    }, undefined, (err) => {
      loadErrors.push(cfg.slug + ': ' + (err && err.message || err));
      resolve(false);
    });
  });
}

// Treasure chest: static set dressing near the fire, no clips.
function placeChest() {
  loader.load('assets/treasure-chest.glb', (gltf) => {
    sharpenTextures(gltf.scene);
    gltf.scene.traverse((o) => {
      if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; }
    });
    const box = new THREE.Box3().setFromObject(gltf.scene);
    const size = box.getSize(new THREE.Vector3());
    gltf.scene.scale.setScalar(0.72 / (size.y || 1));
    const b2 = new THREE.Box3().setFromObject(gltf.scene);
    gltf.scene.position.y = -b2.min.y;
    const g = new THREE.Group();
    g.add(gltf.scene);
    g.position.set(-3.3, groundH(-3.3, 2.3), 2.3);
    g.rotation.y = 0.75;
    scene.add(g);
  }, undefined, () => { /* the scene is fine without it */ });
}

/* ------------------------------------------------------ fire spots */

// Gathering spots on the far side of the fire from the camera, so
// the creatures face the flames (and mostly the viewer). One
// creature per spot.
// Builder environment pack: swap the registered procedural dressing
// for the catalogued Game Asset Builder GLBs at the same spots. Each
// GLB loads once and is cloned per spot; a failed load simply leaves
// the procedural dressing in place. The hero pines keep the spots the
// pine proof used.
function groundPackClone(srcScene, place) {
  const inner = srcScene.clone(true);
  inner.traverse((o) => {
    if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; }
  });
  place(inner);
  const b2 = new THREE.Box3().setFromObject(inner);
  inner.position.y -= b2.min.y;
  const g = new THREE.Group();
  g.add(inner);
  return g;
}

function swapIn(srcScene, entry) {
  const obj = entry.obj;
  const wp = new THREE.Vector3();
  obj.getWorldPosition(wp);
  const size = new THREE.Box3().setFromObject(obj)
    .getSize(new THREE.Vector3());
  const rotY = obj.rotation.y || 0;
  const rockRot = entry.kind === 'rock'
    ? [obj.rotation.x, obj.rotation.y, obj.rotation.z] : null;
  scene.remove(obj);
  const g = groundPackClone(srcScene, (inner) => {
    const s0 = new THREE.Box3().setFromObject(inner)
      .getSize(new THREE.Vector3());
    if (entry.kind === 'log') {
      if (s0.z > s0.x) inner.rotation.y = Math.PI / 2;
      inner.scale.setScalar(entry.len / Math.max(s0.x, s0.z));
    } else {
      inner.scale.setScalar((size.y || 1) / (s0.y || 1));
    }
    if (rockRot) inner.rotation.set(rockRot[0], rockRot[1], rockRot[2]);
  });
  g.position.set(wp.x, groundH(wp.x, wp.z) - 0.05, wp.z);
  if (!rockRot) g.rotation.y = rotY;
  scene.add(g);
}

function placeBuilderPack() {
  const swapKind = (srcScene, kind) => {
    for (const e of BUILDER_SWAPS.meshes) {
      if (e.kind !== kind) continue;
      // Far rocks stay procedural: the builder boulder is a smooth
      // round form that reads as a dark ball against the fog wall at
      // range; up close it reads as a rock. (Noon capture, 2026-11-10.)
      if (kind === 'rock') {
        const p = e.obj.position;
        if (Math.hypot(p.x, p.z) > 30) continue;
      }
      swapIn(srcScene, e);
    }
  };
  const jobs = [
    ['pine-tree', (srcScene) => {
      const spots = [
        { x: 11,   z: -7.5, h: 30, rot: 0.4 },   // the hero spot
        { x: 7.5,  z: -14,  h: 27, rot: 1.7 },
        { x: -14,  z: -11,  h: 28, rot: 2.9 },
        { x: 18,   z: -20,  h: 29, rot: 0.9 },
        { x: -6,   z: -22,  h: 4.9, rot: 2.1 },
        { x: 24,   z: -9,   h: 4.4, rot: 1.2 },
      ];
      for (const s of spots) {
        const g = groundPackClone(srcScene, (inner) => {
          const s0 = new THREE.Box3().setFromObject(inner)
            .getSize(new THREE.Vector3());
          inner.scale.setScalar(s.h / (s0.y || 1));
        });
        g.position.set(s.x, groundH(s.x, s.z) - 0.05, s.z);
        g.rotation.y = s.rot;
        scene.add(g);
      }
      swapKind(srcScene, 'pine');
    }],
    ['boulder', (srcScene) => swapKind(srcScene, 'rock')],
    ['bush', (srcScene) => swapKind(srcScene, 'bush')],
    ['fern', (srcScene) => {
      if (BUILDER_SWAPS.fernMesh) BUILDER_SWAPS.fernMesh.count = 0;
      BUILDER_SWAPS.fernSpots.forEach(([x, z, fs], i) => {
        if (i % 4 !== 0) return;
        const g = groundPackClone(srcScene, (inner) => {
          const s0 = new THREE.Box3().setFromObject(inner)
            .getSize(new THREE.Vector3());
          inner.scale.setScalar((fs * 0.95) / (s0.y || 1));
        });
        g.position.set(x, groundH(x, z) - 0.03, z);
        g.rotation.y = Math.random() * Math.PI * 2;
        scene.add(g);
      });
    }],
    ['mushroom-cluster', (srcScene) => {
      srcScene.traverse((o) => {
        if (o.isMesh && o.material) {
          o.material = o.material.clone();
          o.material.emissive = new THREE.Color(0x0d4038);
          o.material.emissiveIntensity = 0.6;
        }
      });
      for (const m of BUILDER_SWAPS.mushroomMeshes) m.visible = false;
      for (const [ax, az] of BUILDER_SWAPS.mushroomAnchors) {
        const g = groundPackClone(srcScene, (inner) => {
          const s0 = new THREE.Box3().setFromObject(inner)
            .getSize(new THREE.Vector3());
          inner.scale.setScalar(0.6 / (s0.y || 1));
        });
        g.position.set(ax, groundH(ax, az) - 0.03, az);
        g.rotation.y = Math.random() * Math.PI * 2;
        scene.add(g);
      }
    }],
    ['fallen-log', (srcScene) => swapKind(srcScene, 'log')],
    ['stump', (srcScene) => swapKind(srcScene, 'stump')],
  ];
  builderPack.pending = jobs.length;
  for (const [slug, fn] of jobs) {
    loader.load('assets/' + slug + '.glb', (gltf) => {
      try { fn(gltf.scene); } catch (e) {
        console.log('PACK_SWAP_ERROR ' + slug + ' ' + e);
      }
      if (--builderPack.pending <= 0) {
        builderPack.done = true;
        console.log('PACK_LOAD_OK');
      }
    }, undefined, (e) => {
      console.log('PACK_LOAD_ERROR ' + slug + ' ' + e);
      if (--builderPack.pending <= 0) builderPack.done = true;
    });
  }
}

const SPOTS = [-1.05, -0.52, 0, 0.52, 1.05].map((a) => ({
  pos: new THREE.Vector3(Math.sin(a) * 2.75, 0, Math.cos(a) * 2.75),
  takenBy: null,
}));

/* ------------------------------------------------- creature instance */

const blobTex = radialSpriteTexture('rgba(0,0,0,0.5)', 'rgba(0,0,0,0)');
let instanceSeq = 0;

class Creature {
  constructor(tpl, spot, startPos, startState) {
    this.tpl = tpl;
    this.cfg = tpl.cfg;
    this.id = ++instanceSeq;
    this.spot = spot;
    if (spot) spot.takenBy = this;

    this.group = new THREE.Group();          // ground position + yaw
    this.model = SkeletonUtils.clone(tpl.holder);
    // AAA experiment: creatures cast and receive real shadows; the
    // painted blob stays only as a faint contact grounding (0.22).
    this.model.traverse((o) => {
      if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; }
    });
    this.group.add(this.model);
    const shadow = new THREE.Mesh(
      new THREE.PlaneGeometry(1, 1),
      new THREE.MeshBasicMaterial({
        map: blobTex, transparent: true, depthWrite: false, opacity: 0.22 }));
    shadow.rotation.x = -Math.PI / 2;
    shadow.position.y = 0.02;
    shadow.scale.setScalar(this.cfg.height * 1.5);
    this.group.add(shadow);
    this.shadow = shadow;

    this.group.position.copy(startPos);
    this.group.position.y = groundH(startPos.x, startPos.z);
    scene.add(this.group);

    this.mixer = new THREE.AnimationMixer(this.model);
    this.actions = {};
    for (const role of ['idle', 'walk', 'signature']) {
      const clip = tpl.clips[role];
      if (clip) this.actions[role] = this.mixer.clipAction(clip);
    }
    this.currentRole = null;
    this.mixer.addEventListener('finished', () => {
      if (this.state === 'dwell' && this.currentRole === 'signature') {
        this.play('idle');
      }
    });

    this.state = startState;                 // enter | dwell | leave
    this.target = new THREE.Vector3();
    this.dwellLeft = 0;
    this.signatureIn = rand(5, 11);
    this.yaw = this.group.rotation.y;
    if (startState === 'dwell') {
      this.enterDwell();
    } else {
      this.setTarget(spot.pos);
      this.startTravel();
    }
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

  // Travel clip choice: a real walk clip wins; otherwise hop/bounce
  // styles ride their signature clip and glide rides idle.
  startTravel() {
    if (this.actions.walk) this.play('walk');
    else if (this.cfg.travelStyle === 'glide') this.play('idle');
    else this.play('signature');
  }

  setTarget(v) {
    this.target.copy(v);
    this.target.y = 0;
  }

  enterDwell() {
    this.state = 'dwell';
    this.dwellLeft = rand(16, 42);
    this.signatureIn = rand(5, 11);
    this.play('idle');
    // Face the fire.
    this.targetYaw = Math.atan2(-this.group.position.x, -this.group.position.z);
  }

  startLeaving() {
    if (this.spot) { this.spot.takenBy = null; this.spot = null; }
    this.state = 'leave';
    const a = Math.random() * Math.PI * 2;
    this.setTarget(new THREE.Vector3(
      Math.sin(a) * (SPAWN_RADIUS + 6), 0, Math.cos(a) * (SPAWN_RADIUS + 6)));
    this.startTravel();
  }

  // Returns false when the creature has left and should be removed.
  update(dt, t) {
    this.mixer.update(dt);
    const pos = this.group.position;

    if (this.state === 'enter' || this.state === 'leave') {
      const dx = this.target.x - pos.x, dz = this.target.z - pos.z;
      const dist = Math.hypot(dx, dz);
      const arriveAt = this.state === 'enter' ? 0.12 : 1.2;
      if (dist <= arriveAt) {
        if (this.state === 'enter') { this.enterDwell(); }
        else return false;
      } else {
        const heading = Math.atan2(dx, dz);
        this.yaw = lerpAngle(this.yaw, heading, Math.min(1, dt * 5));
        let speed = this.cfg.speed;
        let bob = 0;
        const travel = this.actions[this.currentRole];
        if (!this.actions.walk && travel &&
            (this.cfg.travelStyle === 'hop' || this.cfg.travelStyle === 'bounce')) {
          // Surge and lift with the clip's own cycle.
          const dur = travel.getClip().duration || 1;
          const phase = (travel.time % dur) / dur;
          const lift = Math.abs(Math.sin(phase * Math.PI));
          bob = lift * this.cfg.bobAmp;
          speed *= 0.5 + 0.7 * lift;
        } else if (!this.actions.walk) {
          bob = Math.sin(t * 2.3 + this.id) * this.cfg.bobAmp;
        }
        pos.x += Math.sin(heading) * speed * dt;
        pos.z += Math.cos(heading) * speed * dt;
        pos.y = groundH(pos.x, pos.z) + bob;
        this.shadow.material.opacity = 0.22 - bob * 0.28;
      }
    } else { // dwell
      pos.y = groundH(pos.x, pos.z);
      this.yaw = lerpAngle(this.yaw, this.targetYaw, Math.min(1, dt * 3));
      this.dwellLeft -= dt;
      this.signatureIn -= dt;
      if (this.signatureIn <= 0 && this.currentRole === 'idle') {
        this.play('signature', true);
        this.signatureIn = rand(7, 16);
      }
      if (this.dwellLeft <= 0) this.startLeaving();
    }
    this.group.rotation.y = this.yaw;
    return true;
  }

  dispose() {
    if (this.spot) this.spot.takenBy = null;
    scene.remove(this.group);
    this.mixer.stopAllAction();
    this.mixer.uncacheRoot(this.model);
  }
}

/* ------------------------------------------------------------ director */

const active = [];
let spawnTimer = 1.2;

function freeSpot() {
  const free = SPOTS.filter((s) => !s.takenBy);
  return free.length ? free[Math.floor(Math.random() * free.length)] : null;
}

function spawn(initial) {
  const loaded = [...templates.values()];
  if (!loaded.length) return;
  const spot = freeSpot();
  if (!spot) return;
  const tpl = loaded[Math.floor(Math.random() * loaded.length)];
  let startPos, state;
  if (initial === 'dwell') {
    startPos = spot.pos.clone();
    state = 'dwell';
  } else {
    const a = Math.random() * Math.PI * 2;
    const r = initial === 'near' ? 15 : SPAWN_RADIUS;
    startPos = new THREE.Vector3(Math.sin(a) * r, 0, Math.cos(a) * r);
    state = 'enter';
  }
  active.push(new Creature(tpl, spot, startPos, state));
}

function updateDirector(dt) {
  for (let i = active.length - 1; i >= 0; i--) {
    if (!active[i].update(dt, perfNow * 0.001)) {
      active[i].dispose();
      active.splice(i, 1);
    }
  }
  if (active.length < MAX_ACTIVE && templates.size) {
    spawnTimer -= dt;
    if (spawnTimer <= 0) {
      spawn(false);
      spawnTimer = active.length === 0 ? 2.5 : rand(6, 14);
    }
  }
}

/* ---------------------------------------------------------- main loop */

const clock = new THREE.Clock();
let perfNow = 0;
let frames = 0, fpsTimer = 0, fps = 0;
let statusTimer = 0;
let firstFrame = true;

function tick() {
  const dt = Math.min(clock.getDelta(), 0.05);
  perfNow = performance.now();
  const t = clock.elapsedTime;

  updateSky(FROZEN_TIME ?? Date.now());
  windUniform.value = t;
  updateFire(t, dt);
  updateDirector(dt);
  updateDressing(t, dt);

  // Very slight camera drift — alive, never seasick.
  camera.position.set(
    CAM_BASE.x + Math.sin(t * 0.045) * 0.55,
    CAM_BASE.y + Math.sin(t * 0.061 + 1.3) * 0.18,
    CAM_BASE.z);
  camera.lookAt(CAM_LOOK);

  composer.render();
  if (firstFrame) {
    firstFrame = false;
    loadingEl.classList.add('done');
  }

  frames++; fpsTimer += dt; statusTimer += dt;
  if (fpsTimer >= 0.5) { fps = Math.round(frames / fpsTimer); frames = 0; fpsTimer = 0; }
  if (statusTimer >= 0.5) {
    statusTimer = 0;
    publishStatus();
  }
}

function publishStatus() {
  const s = {
    ready: true, fps,
    builderDone: builderPack.done,
    loaded: [...templates.keys()],
    loadErrors,
    sky: skyState,
    creatures: active.map((c) => ({
      slug: c.cfg.slug, state: c.state, clip: c.currentRole,
      x: +c.group.position.x.toFixed(2), z: +c.group.position.z.toFixed(2),
    })),
  };
  window.__campfireStatus = s;
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
  composer.setSize(window.innerWidth, window.innerHeight);
});

/* ------------------------------------------- verification harness */

// Only with ?harness=1 (used by docs/TEST_PLAN.md checks; Lively
// never passes it): step the simulation deterministically, without
// depending on how fast the host can composite frames — headless
// software renderers manage a frame every few seconds, which would
// otherwise make a travelling creature look parked. Combine with
// &time=<epoch ms | ISO> to freeze the sun/moon at a chosen instant.
if (PAGE_PARAMS.has('harness')) {
  window.__scene = scene;
  window.__campfireStep = (steps, dt) => {
    for (let i = 0; i < steps; i++) {
      perfNow += dt * 1000;
      const t = perfNow * 0.001;
      windUniform.value = t;
      updateFire(t, dt);
      updateDirector(dt);
    }
    updateSky(FROZEN_TIME ?? Date.now());
    camera.position.copy(CAM_BASE);
    camera.lookAt(CAM_LOOK);
    composer.render();
    publishStatus();
    return window.__campfireStatus;
  };
}

/* ------------------------------------- AAA experiment: shadows */

// One policy pass over the static scene: every lit mesh casts and
// receives. Unlit materials (sky shader, sun/moon discs, halos,
// glow planes, blob shadows) are skipped; grass receives but does
// not cast (1,250 tufts of shadow acne help no one). Creatures and
// the chest opt in at load time instead.
scene.traverse((o) => {
  if (!o.isMesh) return;
  const m = o.material;
  if (m && (m.isMeshBasicMaterial || m.isShaderMaterial)) return;
  o.receiveShadow = true;
  o.castShadow = o.name !== 'grassTufts';
});

/* ---------------------------------- AAA experiment: post chain */

// HDR composer: scene -> bloom (the 0.85 threshold keeps it to the
// fire, the glow mushrooms, and the sky discs) -> OutputPass (tone
// mapping and sRGB live there when a composer is in use). The
// HalfFloat target with 4x MSAA keeps edges clean without the
// renderer's own antialias, which the composer bypasses.
const composer = new EffectComposer(renderer,
  new THREE.WebGLRenderTarget(window.innerWidth, window.innerHeight,
    { type: THREE.HalfFloatType, samples: 4 }));
composer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
composer.setSize(window.innerWidth, window.innerHeight);
composer.addPass(new RenderPass(scene, camera));
const bloomPass = new UnrealBloomPass(
  new THREE.Vector2(window.innerWidth, window.innerHeight),
  0.3, 0.55, 0.9);
composer.addPass(bloomPass);
// AAA experiment stage 3: one gentle grade over the whole frame
// (slight desaturation, a whisper of warmth, a soft vignette).
// A single filmic pass is what makes the painted creatures and
// the procedural background feel like one photograph.
const gradePass = new ShaderPass({
  uniforms: { tDiffuse: { value: null } },
  vertexShader: `varying vec2 vUv; void main(){ vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
  fragmentShader: `uniform sampler2D tDiffuse; varying vec2 vUv;
    void main(){
      vec4 tex = texture2D(tDiffuse, vUv);
      vec3 c = tex.rgb;
      float luma = dot(c, vec3(0.2126, 0.7152, 0.0722));
      c = mix(vec3(luma), c, 0.93);
      c *= vec3(1.02, 1.0, 0.98);
      float d = distance(vUv, vec2(0.5, 0.46));
      c *= 0.90 + 0.10 * smoothstep(0.95, 0.45, d);
      gl_FragColor = vec4(c, tex.a);
    }`,
});
composer.addPass(gradePass);
composer.addPass(new OutputPass());

/* -------------------------------------------------------------- boot */

(async () => {
  // Sequential on purpose: three ~20 MB models parsing at once is a
  // needless memory spike for a wallpaper that should sip resources.
  for (const cfg of CREATURES) await loadTemplate(cfg);
  placeChest();
  placeBuilderPack();
  // Open mid-scene: one creature already warming itself, one on its
  // way in, and the director tops up from there.
  if (templates.size) {
    spawn('dwell');
    spawn('near');
  }
  updateSky(FROZEN_TIME ?? Date.now());
  renderer.setAnimationLoop(tick);
})();
