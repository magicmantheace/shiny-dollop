// three.js hand-off verification driver (runs on the owner's PC).
// Serves the harness folder over localhost HTTP (Chrome blocks
// file:// ES-module imports), spawns Chrome headless once per
// asset against verify.html, and extracts the JSON verdict from
// the dumped DOM.
//
// Usage: node run_verify.mjs <harness-dir>
// The harness dir must contain verify.html, three.module.js,
// three.core.js, addons/, and the exported .glb files.
// CHROME_PATH env overrides the Chrome location.
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
const ASSETS = [
  { slug: 'ember-dragon', clips: 'hop,idle', bones: 14 },
  { slug: 'snow-goblin', clips: 'idle,wave', bones: 13 },
  { slug: 'triceratops', clips: 'bounce,idle', bones: 15 },
  { slug: 'treasure-chest', clips: '', bones: 0 },
];

function runOne(asset) {
  return new Promise((resolve) => {
    const url = `http://127.0.0.1:${PORT}/verify.html` +
      `?glb=${asset.slug}.glb&clips=${asset.clips}&bones=${asset.bones}`;
    const args = ['--headless=new',
      '--use-angle=swiftshader-webgl', '--enable-unsafe-swiftshader',
      '--mute-audio', '--timeout=60000', '--dump-dom', url];
    const child = spawn(CHROME, args, { windowsHide: true });
    let dom = '';
    child.stdout.on('data', (d) => { if (dom.length < 8_000_000) dom += d; });
    child.stderr.on('data', () => {});
    const timer = setTimeout(() => { child.kill(); }, 120_000);
    child.on('exit', () => {
      clearTimeout(timer);
      const matches = [...dom.matchAll(/<pre id="result">([\s\S]*?)<\/pre>/g)];
      const m = matches.length ? matches[matches.length - 1] : null;
      if (!m) {
        resolve({ slug: asset.slug, ok: false,
                  error: 'no result in DOM (page did not finish?)' });
        return;
      }
      try {
        const parsed = JSON.parse(m[1]);
        parsed.slug = asset.slug;
        resolve(parsed);
      } catch (e) {
        resolve({ slug: asset.slug, ok: false,
                  error: 'unparseable result: ' + m[1].slice(0, 200) });
      }
    });
  });
}

const server = spawn('python',
  ['-m', 'http.server', String(PORT), '--bind', '127.0.0.1',
   '--directory', path.resolve(DIR)],
  { windowsHide: true });
server.stderr.on('data', () => {});
await new Promise((r) => setTimeout(r, 1500));

let allOk = true;
try {
  for (const asset of ASSETS) {
    const result = await runOne(asset);
    if (!result.ok) allOk = false;
    console.log('THREE_VERIFY ' + JSON.stringify(result));
  }
} finally {
  server.kill();
}
console.log('THREE_VERIFY_DONE ' + JSON.stringify({ ok: allOk }));
process.exit(allOk ? 0 : 1);
