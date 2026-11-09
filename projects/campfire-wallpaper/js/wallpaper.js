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
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';

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
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
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
// The fire light is created with the campfire and flickers per-frame.

// Time-of-day balances read by the fire and the dressing updaters:
// fireScale shrinks the fire's presence in daylight; nightFactor
// gates fireflies and the mushroom glow.
let fireScale = 1, nightFactor = 1;
let skyState = { sunEl: -20, sunAz: 0, moonEl: -20, moonAz: 0, moonFrac: 0 };
// Scene elements created later (e.g. the horizon hills) register a
// callback here to be tinted by the sky palette each frame.
const skyFollowers = [];

/* --------------------------------------------------------------- sky */

let skyUniforms, starMat;
let sunDisc, sunHaloMat, moonDisc, moonMat, moonHaloMat;
const moonCanvas = document.createElement('canvas');
moonCanvas.width = moonCanvas.height = 256;
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
    },
    vertexShader: `varying vec3 vP; void main(){ vP = position;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: `varying vec3 vP; uniform vec3 top; uniform vec3 mid; uniform vec3 horizon;
      void main(){ float h = normalize(vP).y;
        vec3 c = h > 0.22 ? mix(mid, top, smoothstep(0.22, 0.8, h))
                          : mix(horizon, mid, smoothstep(-0.03, 0.22, h));
        gl_FragColor = vec4(c, 1.0); }`,
  });
  skyUniforms = skyMat.uniforms;
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
  starMat = new THREE.PointsMaterial({
    size: 1.5, sizeAttenuation: false, vertexColors: true, fog: false,
    transparent: true, opacity: 0.9, depthWrite: false,
  });
  scene.add(new THREE.Points(starGeo, starMat));

  // Sun: warm disc + halo, positioned by updateSky().
  sunDisc = new THREE.Mesh(
    new THREE.CircleGeometry(5, 32),
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
  moonDisc = new THREE.Mesh(new THREE.CircleGeometry(6.5, 32), moonMat);
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
  const s = 256, c = s / 2, r = c - 4;
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
  { el: 18,  top: _C(0x2f6bb8), mid: _C(0x79aede), hor: _C(0xc8dfeb), fog: _C(0x9db8cc), fogDen: 0.0055, hs: _C(0xbfd8f0), hg: _C(0x44543c), hi: 1.7 },
  { el: 40,  top: _C(0x2a63c4), mid: _C(0x74aae6), hor: _C(0xd2e6f2), fog: _C(0xa8c4d8), fogDen: 0.005,  hs: _C(0xcfe4f4), hg: _C(0x4a5c40), hi: 1.85 },
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
  skyUniforms.top.value.copy(P.top);
  skyUniforms.mid.value.copy(P.mid);
  skyUniforms.horizon.value.copy(P.hor);
  scene.fog.color.copy(P.fog);
  scene.fog.density = P.fogDen;
  hemiLight.color.copy(P.hs);
  hemiLight.groundColor.copy(P.hg);
  hemiLight.intensity = P.hi;

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
  for (const f of skyFollowers) f(P, sunEl);
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

  /* Forest edge: two instanced meshes (trunks, merged-cone foliage)
     sharing per-instance matrices — 245 pines at r 44–84 over the
     lone scattered pines, thinning the "few trees in a void" feel
     into an actual treeline; the outermost ring stands tallest so
     the forest reads as a wall, not a hedge. */
  {
    const trunkGeo = new THREE.CylinderGeometry(0.09, 0.15, 1.2, 6);
    trunkGeo.translate(0, 0.6, 0);
    const cone1 = new THREE.ConeGeometry(0.88, 2.4, 8); cone1.translate(0, 1.95, 0);
    const cone2 = new THREE.ConeGeometry(0.68, 2.4, 8); cone2.translate(0, 2.8, 0);
    const cone3 = new THREE.ConeGeometry(0.48, 2.4, 8); cone3.translate(0, 3.65, 0);
    const folGeo = mergeGeometries([cone1, cone2, cone3]);
    const trunks = instanced(trunkGeo,
      new THREE.MeshStandardMaterial({ color: 0x33261a, roughness: 1 }), 245);
    const fols = instanced(folGeo,
      new THREE.MeshStandardMaterial({ color: 0x1c3020, roughness: 1 }), 245);
    let i = 0;
    for (; i < 160; i++) {                 // the distant ring
      const a = layoutRand() * Math.PI * 2;
      const r = 54 + Math.pow(layoutRand(), 1.3) * 27;
      const x = Math.cos(a) * r, z = Math.sin(a) * r;
      const s = 0.95 + layoutRand() * 1.15;
      setInst(trunks, i, x, z, s, 0.12);
      fols.setMatrixAt(i, dummy.matrix);
      tint.setHSL(0.32, 0.25, 0.42 + layoutRand() * 0.2);
      fols.setColorAt(i, tint);
    }
    for (; i < 190; i++) {                 // a nearer blending band
      const a = layoutRand() * Math.PI * 2;
      const r = 44 + layoutRand() * 14;
      const x = Math.cos(a) * r, z = Math.sin(a) * r;
      const s = 0.85 + layoutRand() * 0.8;
      setInst(trunks, i, x, z, s, 0.12);
      fols.setMatrixAt(i, dummy.matrix);
      tint.setHSL(0.32, 0.25, 0.42 + layoutRand() * 0.2);
      fols.setColorAt(i, tint);
    }
    for (; i < 245; i++) {                 // a taller back wall (density pass)
      const a = layoutRand() * Math.PI * 2;
      const r = 66 + Math.pow(layoutRand(), 1.2) * 18;
      const x = Math.cos(a) * r, z = Math.sin(a) * r;
      const s = 1.5 + layoutRand() * 1.2;
      setInst(trunks, i, x, z, s, 0.12);
      fols.setMatrixAt(i, dummy.matrix);
      tint.setHSL(0.32, 0.25, 0.36 + layoutRand() * 0.18);
      fols.setColorAt(i, tint);
    }
    trunks.instanceMatrix.needsUpdate = true;
    fols.instanceMatrix.needsUpdate = true;
    if (fols.instanceColor) fols.instanceColor.needsUpdate = true;
  }

  /* Two nearer feature trees + a dead snag, hand-placed. */
  {
    const barkMat = new THREE.MeshStandardMaterial({ color: 0x3a2a1a, roughness: 1 });
    const leafMat = new THREE.MeshStandardMaterial({ color: 0x22391f, roughness: 1, flatShading: true });
    // Broad oak, left mid-field.
    const oak = new THREE.Group();
    const otrunk = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.46, 2.3, 7), barkMat);
    otrunk.position.y = 1.1;
    oak.add(otrunk);
    const blobGeo = new THREE.IcosahedronGeometry(1, 1);
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
    const ptrunk = new THREE.Mesh(new THREE.CylinderGeometry(0.13, 0.2, 2.2, 6), barkMat);
    ptrunk.position.y = 1.1;
    pine.add(ptrunk);
    const pconeGeo = new THREE.ConeGeometry(1, 2.6, 8);
    const pfolMat = new THREE.MeshStandardMaterial({ color: 0x1d3320, roughness: 1 });
    for (let k = 0; k < 4; k++) {
      const cone = new THREE.Mesh(pconeGeo, pfolMat);
      cone.scale.set(1.15 - k * 0.2, 1.15, 1.15 - k * 0.2);
      cone.position.y = 2.2 + k * 1.15;
      pine.add(cone);
    }
    pine.position.set(11, groundH(11, -7.5) - 0.1, -7.5);
    scene.add(pine);
    // Dead snag, back-left — bare trunk, two branch stubs.
    const snag = new THREE.Group();
    const strunk = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.17, 3.4, 6),
      new THREE.MeshStandardMaterial({ color: 0x6b5a44, roughness: 1 }));
    strunk.position.y = 1.7;
    snag.add(strunk);
    for (const [ry, rz, len] of [[2.3, 0.7, 0.9], [2.9, -0.5, 0.65]]) {
      const br = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.05, len, 5),
        strunk.material);
      br.position.set(0.3, ry, 0);
      br.rotation.z = rz;
      snag.add(br);
    }
    snag.position.set(-16, groundH(-16, 8), 8);
    snag.rotation.z = 0.05;
    scene.add(snag);
  }

  /* Grass tufts: instanced five-blade cones — 950 spread through
     the field, plus 300 more ringing the clearing (density pass).
     Sparse in the clearing, none on the path. */
  {
    const blades = [];
    for (let k = 0; k < 5; k++) {
      const b = new THREE.ConeGeometry(0.05, 0.42, 4);
      b.translate(0, 0.21, 0);
      const m = new THREE.Matrix4().makeRotationFromEuler(new THREE.Euler(
        Math.cos(k * 2.4) * 0.32, k * 1.257, Math.sin(k * 2.4) * 0.32));
      m.setPosition(Math.cos(k * 1.257) * 0.07, 0, Math.sin(k * 1.257) * 0.07);
      b.applyMatrix4(m);
      blades.push(b);
    }
    const tuftGeo = mergeGeometries(blades);
    const grass = instanced(tuftGeo,
      new THREE.MeshStandardMaterial({ roughness: 1, flatShading: true }), 1250);
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
      const f = new THREE.ConeGeometry(0.3, 0.55, 5);
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
      setInst(ferns, placed, x, z, 0.6 + layoutRand() * 0.75, 0.02);
      placed++;
    }
    ferns.count = placed;
    ferns.instanceMatrix.needsUpdate = true;
  }

  /* More bushes, seven of them dotted with berries (one instanced
     berry mesh shared across all seven). */
  {
    const bushGeo2 = new THREE.IcosahedronGeometry(1, 1);
    const bushMat2 = new THREE.MeshStandardMaterial({ color: 0x27401f, roughness: 1, flatShading: true });
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
    const berries = instanced(new THREE.SphereGeometry(0.038, 6, 5),
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
    const stemGeo = new THREE.CylinderGeometry(0.035, 0.055, 0.17, 6);
    stemGeo.translate(0, 0.085, 0);
    const capGeo = new THREE.SphereGeometry(0.115, 8, 5, 0, Math.PI * 2, 0, Math.PI / 2);
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
    const barkMat = new THREE.MeshStandardMaterial({ color: 0x4a3018, roughness: 1 });
    const endMat = new THREE.MeshStandardMaterial({ color: 0xa9834f, roughness: 0.9 });
    const logMats = [barkMat, endMat, endMat];
    function bench(a, r) {
      const g = new THREE.Group();
      const seat = new THREE.Mesh(new THREE.CylinderGeometry(0.15, 0.15, 1.7, 8), logMats);
      seat.rotation.z = Math.PI / 2;
      seat.position.y = 0.46;
      g.add(seat);
      for (const sx of [-0.55, 0.55]) {
        const sup = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.18, 0.34, 7), logMats);
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
      const stump = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.34, 0.48, 9), logMats);
      stump.position.set(x, groundH(x, z) + 0.24, z);
      scene.add(stump);
    }
    const pile = new THREE.Group();
    const logGeo2 = new THREE.CylinderGeometry(0.11, 0.11, 1.15, 7);
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
    const block = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.34, 0.5, 9), logMats);
    block.position.set(3.9, groundH(3.9, 3.3) + 0.25, 3.3);
    scene.add(block);
    const split = new THREE.Mesh(new THREE.CylinderGeometry(0.13, 0.13, 0.5, 7), logMats);
    split.position.set(3.9, groundH(3.9, 3.3) + 0.72, 3.3);
    scene.add(split);
  }

  /* Distant hills: squashed domes on the horizon. Their colour
     follows the sky palette (registered as a sky follower) so they
     silhouette at dusk and haze blue-grey by day. */
  {
    const hillMat = new THREE.MeshBasicMaterial({ color: 0x0c1428, fog: false });
    skyFollowers.push((P) => {
      hillMat.color.copy(P.hor).lerp(P.mid, 0.75).multiplyScalar(0.34);
    });
    const hillGeo = new THREE.SphereGeometry(1, 24, 12);
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
    const span = 1.40, steps = 88;
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
    const pos = [], col = [], idx = [];
    const cBase = new THREE.Color(cols[0]), cMid = new THREE.Color(cols[1]),
          cTop = new THREE.Color(cols[2]), cSnow = new THREE.Color(0xeef2fa),
          cc = new THREE.Color();
    for (let i = 0; i <= steps; i++) {
      const th = -span + (2 * span * i) / steps;
      const x = Math.sin(th) * R, z = Math.cos(th) * R;
      const y = prof(th);
      const h01 = THREE.MathUtils.clamp((y - baseY) / (peakY - baseY), 0, 1);
      cc.copy(cBase).lerp(cMid, Math.min(h01 * 1.6, 1))
        .lerp(cTop, Math.max(0, h01 * 1.4 - 0.4));
      if (snowline !== null &&
          h01 > snowline + 0.07 * Math.sin(th * 34) + layoutRand() * 0.05) {
        cc.copy(cSnow);
      }
      pos.push(x, y, z); col.push(cc.r, cc.g, cc.b);
      pos.push(x, -8, z); col.push(cc.r * 0.75, cc.g * 0.75, cc.b * 0.75);
      if (i < steps) {
        const b = i * 2;
        idx.push(b, b + 1, b + 2, b + 1, b + 3, b + 2);
      }
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(pos), 3));
    g.setAttribute('color', new THREE.BufferAttribute(new Float32Array(col), 3));
    g.setIndex(idx);
    const mat = new THREE.MeshBasicMaterial({
      vertexColors: true, fog: false, side: THREE.DoubleSide,
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

  /* Foreground framing pines (density pass): four large pines
     close around the camera, trunks crossing the frame edges like
     the reference photo — the clearing is now seen INTO a forest,
     not across a lawn. */
  {
    const trunkGeo = new THREE.CylinderGeometry(0.11, 0.18, 1.2, 6);
    trunkGeo.translate(0, 0.6, 0);
    const cone1 = new THREE.ConeGeometry(0.88, 2.4, 8); cone1.translate(0, 1.95, 0);
    const cone2 = new THREE.ConeGeometry(0.68, 2.4, 8); cone2.translate(0, 2.8, 0);
    const cone3 = new THREE.ConeGeometry(0.48, 2.4, 8); cone3.translate(0, 3.65, 0);
    const folGeo = mergeGeometries([cone1, cone2, cone3]);
    const trunks = instanced(trunkGeo,
      new THREE.MeshStandardMaterial({ color: 0x33261a, roughness: 1 }), 4);
    const fols = instanced(folGeo,
      new THREE.MeshStandardMaterial({ color: 0x1c3020, roughness: 1 }), 4);
    const frames = [[-5.4, -3.4, 2.5], [5.6, -4.2, 2.85],
                    [-9.2, -8.8, 3.2], [9.8, -9.6, 3.0]];
    frames.forEach(([x, z, s], i) => {
      setInst(trunks, i, x, z, s, 0.12);
      fols.setMatrixAt(i, dummy.matrix);
      tint.setHSL(0.32, 0.25, 0.30 + layoutRand() * 0.12);
      fols.setColorAt(i, tint);
    });
    trunks.instanceMatrix.needsUpdate = true;
    fols.instanceMatrix.needsUpdate = true;
    if (fols.instanceColor) fols.instanceColor.needsUpdate = true;
  }

  /* Moss patches: dark-green discs mottling the forest floor —
     outside the clearing and off the path (density pass). */
  {
    const mossGeo = new THREE.CircleGeometry(1, 10);
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
    const rocks = instanced(new THREE.DodecahedronGeometry(1, 0),
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
    const barkMat = new THREE.MeshStandardMaterial({ color: 0x4a3018, roughness: 1 });
    const endMat = new THREE.MeshStandardMaterial({ color: 0xa9834f, roughness: 0.9 });
    const logMats = [barkMat, endMat, endMat];
    function fallenLog(x, z, rotY, len) {
      const g = new THREE.Group();
      const trunk = new THREE.Mesh(
        new THREE.CylinderGeometry(0.17, 0.21, len, 8), logMats);
      trunk.rotation.z = Math.PI / 2;
      trunk.position.y = 0.17;
      g.add(trunk);
      const stub = new THREE.Mesh(
        new THREE.CylinderGeometry(0.05, 0.07, 0.7, 6), barkMat);
      stub.position.set(len * 0.22, 0.42, 0.08);
      stub.rotation.z = -0.7;
      g.add(stub);
      g.position.set(x, groundH(x, z), z);
      g.rotation.y = rotY;
      scene.add(g);
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
  const stoneGeo = new THREE.DodecahedronGeometry(0.17, 0);
  const stoneMat = new THREE.MeshStandardMaterial({ roughness: 1, flatShading: true });
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
  // A whisper of warm bounce on the spots side of the fire, so the
  // gathered creatures' flame-lit faces read as more than
  // silhouettes from the south-facing camera.
  bounceLight = new THREE.PointLight(0xff9a50, 5, 13, 2);
  bounceLight.position.set(0, 0.6, 1.9);
  fire.add(bounceLight);

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

// Gathering spots on the far side of the fire from the camera, so
// the creatures face the flames (and mostly the viewer). One
// creature per spot.
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

  updateSky(FROZEN_TIME ?? Date.now());
  updateFire(t, dt);
  updateDirector(dt);
  updateDressing(t, dt);

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
});

/* ------------------------------------------- verification harness */

// Only with ?harness=1 (used by docs/TEST_PLAN.md checks; Lively
// never passes it): step the simulation deterministically, without
// depending on how fast the host can composite frames — headless
// software renderers manage a frame every few seconds, which would
// otherwise make a travelling creature look parked. Combine with
// &time=<epoch ms | ISO> to freeze the sun/moon at a chosen instant.
if (PAGE_PARAMS.has('harness')) {
  window.__campfireStep = (steps, dt) => {
    for (let i = 0; i < steps; i++) {
      perfNow += dt * 1000;
      const t = perfNow * 0.001;
      updateFire(t, dt);
      updateDirector(dt);
    }
    updateSky(FROZEN_TIME ?? Date.now());
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
  updateSky(FROZEN_TIME ?? Date.now());
  renderer.setAnimationLoop(tick);
})();
