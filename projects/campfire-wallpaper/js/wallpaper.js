// Campfire Companions — a living desktop wallpaper.
//
// A field at dusk. Creatures built by the Game Asset Builder wander in
// from the dark, warm themselves around the campfire, and wander off
// again. Built for Lively Wallpaper (web type) and equally happy opened
// in a browser over HTTP as a preview.
//
// Resource manners matter: capped pixel ratio, modest particle counts,
// no shadow maps (blob shadows instead), and the render loop stops
// entirely while the page is hidden (Lively pauses wallpapers behind
// fullscreen apps; a hidden preview tab costs nothing either).
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
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.3;
document.body.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.fog = new THREE.FogExp2(0x131a33, 0.0135);

const camera = new THREE.PerspectiveCamera(
  55, window.innerWidth / window.innerHeight, 0.1, 500);
const CAM_BASE = new THREE.Vector3(0, 3.1, 10.8);
const CAM_LOOK = new THREE.Vector3(0, 1.0, 0);
camera.position.copy(CAM_BASE);

/* ---------------------------------------------------------- lighting */

scene.add(new THREE.HemisphereLight(0x2c3a5e, 0x191008, 1.15));
const moonLight = new THREE.DirectionalLight(0x8fa3cc, 0.75);
moonLight.position.set(-18, 26, -12);
scene.add(moonLight);
// The fire light is created with the campfire and flickers per-frame.

/* --------------------------------------------------------------- sky */

{
  const skyMat = new THREE.ShaderMaterial({
    side: THREE.BackSide, depthWrite: false,
    uniforms: {
      top: { value: new THREE.Color(0x070d29) },
      mid: { value: new THREE.Color(0x1b2547) },
      horizon: { value: new THREE.Color(0x93502f) },
    },
    vertexShader: `varying vec3 vP; void main(){ vP = position;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: `varying vec3 vP; uniform vec3 top; uniform vec3 mid; uniform vec3 horizon;
      void main(){ float h = normalize(vP).y;
        vec3 c = h > 0.22 ? mix(mid, top, smoothstep(0.22, 0.8, h))
                          : mix(horizon, mid, smoothstep(-0.03, 0.22, h));
        gl_FragColor = vec4(c, 1.0); }`,
  });
  scene.add(new THREE.Mesh(new THREE.SphereGeometry(230, 24, 16), skyMat));

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
  const stars = new THREE.Points(starGeo, new THREE.PointsMaterial({
    size: 1.5, sizeAttenuation: false, vertexColors: true, fog: false,
    transparent: true, opacity: 0.9, depthWrite: false,
  }));
  scene.add(stars);

  // Moon: a pale disc with a soft halo.
  const moon = new THREE.Mesh(
    new THREE.CircleGeometry(7, 32),
    new THREE.MeshBasicMaterial({ color: 0xdfe8f5, fog: false }));
  moon.position.set(-40, 42, -125);
  moon.lookAt(0, 4, 0);
  scene.add(moon);
  const halo = new THREE.Mesh(
    new THREE.PlaneGeometry(46, 46),
    new THREE.MeshBasicMaterial({
      map: radialSpriteTexture('rgba(190,205,240,0.55)', 'rgba(190,205,240,0)'),
      transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, fog: false,
    }));
  halo.position.copy(moon.position);
  halo.lookAt(0, 4, 0);
  scene.add(halo);
}

/* -------------------------------------------------------------- field */

{
  const geo = new THREE.PlaneGeometry(170, 170, 100, 100);
  geo.rotateX(-Math.PI / 2);
  const p = geo.attributes.position;
  const colors = new Float32Array(p.count * 3);
  const dark = new THREE.Color(0x2e4724), light = new THREE.Color(0x466b31),
        dry = new THREE.Color(0x5a5c2e), cc = new THREE.Color();
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
  scene.add(new THREE.Mesh(geo,
    new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 1, metalness: 0 })));
}

// Scattered primitive set dressing: pines, rocks, bushes. Shared
// geometries/materials, seeded placement, clearing kept free.
{
  const trunkGeo = new THREE.CylinderGeometry(0.09, 0.14, 1.1, 6);
  const coneGeo = new THREE.ConeGeometry(1, 2.2, 8);
  const rockGeo = new THREE.DodecahedronGeometry(1, 0);
  const bushGeo = new THREE.IcosahedronGeometry(1, 1);
  const trunkMat = new THREE.MeshStandardMaterial({ color: 0x3a2a1a, roughness: 1 });
  const pineMat = new THREE.MeshStandardMaterial({ color: 0x1d3320, roughness: 1 });
  const rockMat = new THREE.MeshStandardMaterial({ color: 0x5d6068, roughness: 0.95, flatShading: true });
  const bushMat = new THREE.MeshStandardMaterial({ color: 0x243d22, roughness: 1, flatShading: true });

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
    for (let k = 0; k < 3; k++) {
      const cone = new THREE.Mesh(coneGeo, pineMat);
      cone.scale.set(0.75 - k * 0.16, h / 2.6, 0.75 - k * 0.16);
      cone.position.y = 0.9 + k * (h / 3.4);
      tree.add(cone);
    }
    tree.rotation.y = layoutRand() * Math.PI * 2;
    place(tree, x, z);
  }
  for (let i = 0; i < 18; i++) {           // rocks
    const [x, z] = scatterPos(5.5, 55);
    const rock = new THREE.Mesh(rockGeo, rockMat);
    const s = 0.25 + layoutRand() * 0.85;
    rock.scale.set(s, s * (0.55 + layoutRand() * 0.4), s * (0.7 + layoutRand() * 0.5));
    rock.rotation.set(layoutRand() * 3, layoutRand() * 3, layoutRand() * 3);
    place(rock, x, z);
    rock.position.y -= s * 0.25;
  }
  for (let i = 0; i < 14; i++) {           // bushes
    const [x, z] = scatterPos(6, 48);
    const bush = new THREE.Mesh(bushGeo, bushMat);
    const s = 0.5 + layoutRand() * 0.8;
    bush.scale.set(s, s * 0.62, s);
    place(bush, x, z);
    bush.position.y += s * 0.25;
  }
}

/* ----------------------------------------------------------- campfire */

const FIRE_POS = new THREE.Vector3(0, 0, 0);
let fireLight, glowDisc;
const flameSystems = [];

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

  // Stone ring.
  const stoneGeo = new THREE.DodecahedronGeometry(0.16, 0);
  const stoneMat = new THREE.MeshStandardMaterial({ color: 0x6a6d74, roughness: 1, flatShading: true });
  for (let i = 0; i < 9; i++) {
    const a = (i / 9) * Math.PI * 2 + 0.2;
    const st = new THREE.Mesh(stoneGeo, stoneMat);
    st.position.set(Math.cos(a) * 0.88, 0.07, Math.sin(a) * 0.88);
    st.rotation.set(i * 1.7, i * 2.3, i * 0.9);
    st.scale.setScalar(0.8 + (i % 3) * 0.25);
    fire.add(st);
  }
  // Log pile: a low teepee of cylinders plus two crossed logs.
  const logGeo = new THREE.CylinderGeometry(0.075, 0.09, 1.15, 7);
  const logMat = new THREE.MeshStandardMaterial({ color: 0x4a3018, roughness: 1 });
  for (let i = 0; i < 5; i++) {
    const a = (i / 5) * Math.PI * 2;
    const log = new THREE.Mesh(logGeo, logMat);
    log.position.set(Math.cos(a) * 0.3, 0.26, Math.sin(a) * 0.3);
    log.rotation.set(Math.sin(a) * 0.85, 0, Math.cos(a) * 0.85);
    fire.add(log);
  }
  // Warm glow pooled on the ground.
  glowDisc = new THREE.Mesh(
    new THREE.CircleGeometry(2.6, 32),
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
  // A whisper of warm bounce on the camera side of the fire, so the
  // gathered creatures read as more than silhouettes.
  const bounce = new THREE.PointLight(0xff9a50, 5, 13, 2);
  bounce.position.set(0, 0.6, 1.9);
  fire.add(bounce);

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
  fireLight.intensity = 26 * flicker;
  glowDisc.material.opacity = 0.75 + 0.25 * flicker;
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
        _fc.multiplyScalar((1 - n) * (0.75 + 0.25 * flicker));
      } else {
        p.y += dt * p.vy;
        p.x += Math.sin(p.age * 2.1 + p.seed) * 0.25 * dt;
        p.z += Math.cos(p.age * 1.7 + p.seed) * 0.25 * dt;
        const tw = 0.6 + 0.4 * Math.sin(p.age * 9 + p.seed * 3);
        _fc.setRGB(1, 0.5, 0.12).multiplyScalar(Math.max(0, 1 - n * 1.15) * tw);
      }
      pos.setXYZ(i, p.x, p.y, p.z);
      col.setXYZ(i, _fc.r, _fc.g, _fc.b);
    }
    pos.needsUpdate = true;
    col.needsUpdate = true;
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
];
const MAX_ACTIVE = 3;
const SPAWN_RADIUS = 30;

const loader = new GLTFLoader();
const templates = new Map();   // slug -> { cfg, scene, animations, clips }
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

// Gathering spots on the camera side of the fire, so the creatures
// face the flames (and mostly the viewer). One creature per spot.
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
    this.group.add(this.model);
    const shadow = new THREE.Mesh(
      new THREE.PlaneGeometry(1, 1),
      new THREE.MeshBasicMaterial({
        map: blobTex, transparent: true, depthWrite: false, opacity: 0.55 }));
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
        this.shadow.material.opacity = 0.55 - bob * 0.7;
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

  updateFire(t, dt);
  updateDirector(dt);

  // Very slight camera drift — alive, never seasick.
  camera.position.set(
    CAM_BASE.x + Math.sin(t * 0.045) * 0.55,
    CAM_BASE.y + Math.sin(t * 0.061 + 1.3) * 0.18,
    CAM_BASE.z);
  camera.lookAt(CAM_LOOK);

  renderer.render(scene, camera);
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
    loaded: [...templates.keys()],
    loadErrors,
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
});

/* ------------------------------------------- verification harness */

// Only with ?harness=1 (used by docs/TEST_PLAN.md checks; Lively
// never passes it): step the simulation deterministically, without
// depending on how fast the host can composite frames — headless
// software renderers manage a frame every few seconds, which would
// otherwise make a travelling creature look parked.
if (new URLSearchParams(location.search).has('harness')) {
  window.__campfireStep = (steps, dt) => {
    for (let i = 0; i < steps; i++) {
      perfNow += dt * 1000;
      const t = perfNow * 0.001;
      updateFire(t, dt);
      updateDirector(dt);
    }
    camera.position.copy(CAM_BASE);
    camera.lookAt(CAM_LOOK);
    renderer.render(scene, camera);
    publishStatus();
    return window.__campfireStatus;
  };
}

/* -------------------------------------------------------------- boot */

(async () => {
  // Sequential on purpose: three ~20 MB models parsing at once is a
  // needless memory spike for a wallpaper that should sip resources.
  for (const cfg of CREATURES) await loadTemplate(cfg);
  placeChest();
  // Open mid-scene: one creature already warming itself, one on its
  // way in, and the director tops up from there.
  if (templates.size) {
    spawn('dwell');
    spawn('near');
  }
  renderer.setAnimationLoop(tick);
})();
