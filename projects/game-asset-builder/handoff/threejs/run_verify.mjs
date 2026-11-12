// three.js hand-off verification driver (runs on the owner's PC).
// Serves the harness folder over localhost HTTP (Chrome blocks
// file:// ES-module imports), then drives Chrome headless through
// the DevTools protocol: navigate to verify.html and poll the
// result element until the page's own async verification finishes.
// (chrome --dump-dom was tried first and is not usable here: it
// snapshots the DOM while the GLB load is still in flight.)
//
// Usage: node run_verify.mjs <harness-dir>
// The harness dir must contain verify.html, three.module.js,
// three.core.js, addons/, and the exported .glb files.
// CHROME_PATH env overrides the Chrome location. Node >= 22 (for
// the built-in WebSocket client).
import { spawn } from 'node:child_process';
import path from 'node:path';

const CHROME = process.env.CHROME_PATH ||
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const DIR = process.argv[2];
if (!DIR) {
  console.error('usage: node run_verify.mjs <harness-dir>');
  process.exit(2);
}
const PORT = 8931;
const CDP_PORT = 9223;
const ASSETS = [
  { slug: 'ember-dragon', clips: 'hop,idle,run,walk', bones: 14 },
  { slug: 'snow-goblin', clips: 'idle,run,walk,wave', bones: 13 },
  { slug: 'triceratops', clips: 'bounce,idle,run,walk', bones: 15 },
  { slug: 'treasure-chest', clips: '', bones: 0 },
];

async function waitForCdp() {
  for (let i = 0; i < 60; i++) {
    try {
      const resp = await fetch(
        `http://127.0.0.1:${CDP_PORT}/json/list`);
      const targets = await resp.json();
      const page = targets.find((t) => t.type === 'page');
      if (page) return page.webSocketDebuggerUrl;
    } catch { /* not up yet */ }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error('Chrome DevTools endpoint never came up');
}

class Cdp {
  constructor(url) {
    this.ws = new WebSocket(url);
    this.nextId = 1;
    this.pending = new Map();
    this.ws.addEventListener('message', (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.id && this.pending.has(msg.id)) {
        const { resolve, reject } = this.pending.get(msg.id);
        this.pending.delete(msg.id);
        if (msg.error) reject(new Error(msg.error.message));
        else resolve(msg.result);
      }
    });
  }
  async open() {
    await new Promise((resolve, reject) => {
      this.ws.addEventListener('open', resolve, { once: true });
      this.ws.addEventListener('error', reject, { once: true });
    });
  }
  call(method, params = {}) {
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }
  async evaluate(expression) {
    const result = await this.call('Runtime.evaluate',
      { expression, returnByValue: true });
    if (result.exceptionDetails) {
      throw new Error('page evaluate failed: ' +
        JSON.stringify(result.exceptionDetails).slice(0, 300));
    }
    return result.result.value;
  }
}

async function verifyAsset(cdp, asset) {
  const url = `http://127.0.0.1:${PORT}/verify.html` +
    `?glb=${asset.slug}.glb&clips=${asset.clips}&bones=${asset.bones}`;
  await cdp.call('Page.navigate', { url });
  const deadline = Date.now() + 180_000;
  while (Date.now() < deadline) {
    const text = await cdp.evaluate(
      "document.getElementById('result')?.textContent ?? ''");
    if (text.startsWith('{')) {
      const parsed = JSON.parse(text);
      parsed.slug = asset.slug;
      return parsed;
    }
    if (text.startsWith('PAGE_')) {
      return { slug: asset.slug, ok: false, error: text };
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  return { slug: asset.slug, ok: false,
           error: 'page verification timed out (180 s)' };
}

const server = spawn('python',
  ['-m', 'http.server', String(PORT), '--bind', '127.0.0.1',
   '--directory', path.resolve(DIR)],
  { windowsHide: true });
server.stderr.on('data', () => {});

const chrome = spawn(CHROME, [
  '--headless=new', `--remote-debugging-port=${CDP_PORT}`,
  '--remote-debugging-address=127.0.0.1',
  `--user-data-dir=${path.join(path.resolve(DIR), '.chrome-profile')}`,
  '--use-angle=swiftshader-webgl', '--enable-unsafe-swiftshader',
  '--mute-audio', 'about:blank',
], { windowsHide: true });
chrome.stderr.on('data', () => {});

let allOk = true;
try {
  const wsUrl = await waitForCdp();
  const cdp = new Cdp(wsUrl);
  await cdp.open();
  await cdp.call('Page.enable');
  await cdp.call('Runtime.enable');
  for (const asset of ASSETS) {
    const result = await verifyAsset(cdp, asset);
    if (!result.ok) allOk = false;
    console.log('THREE_VERIFY ' + JSON.stringify(result));
  }
  await cdp.call('Browser.close').catch(() => {});
} finally {
  chrome.kill();
  server.kill();
}
console.log('THREE_VERIFY_DONE ' + JSON.stringify({ ok: allOk }));
process.exit(allOk ? 0 : 1);
