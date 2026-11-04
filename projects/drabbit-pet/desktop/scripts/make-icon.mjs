#!/usr/bin/env node
/**
 * Generates assets/icon.png (256×256): a simple royal-purple drabbit
 * glyph (ears, horns, face) drawn pixel-by-pixel and PNG-encoded with
 * node's zlib. Placeholder art, like the SVG pet — replace freely.
 */
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';
import { fileURLToPath } from 'node:url';

const SIZE = 256;
const px = new Uint8Array(SIZE * SIZE * 4); // RGBA, transparent

function set(x, y, [r, g, b, a]) {
  if (x < 0 || y < 0 || x >= SIZE || y >= SIZE) return;
  const i = (y * SIZE + x) * 4;
  px[i] = r;
  px[i + 1] = g;
  px[i + 2] = b;
  px[i + 3] = a;
}

function ellipse(cx, cy, rx, ry, color) {
  for (let y = Math.floor(cy - ry); y <= cy + ry; y++) {
    for (let x = Math.floor(cx - rx); x <= cx + rx; x++) {
      const d = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2;
      if (d <= 1) set(x, y, color);
    }
  }
}

const FUR = [139, 92, 199, 255];
const FUR_DARK = [103, 64, 156, 255];
const BELLY = [230, 215, 250, 255];
const GOLD = [232, 182, 76, 255];
const PINK = [217, 132, 168, 255];
const DARK = [43, 33, 53, 255];
const WHITE = [255, 255, 255, 255];

// ears
ellipse(92, 62, 20, 52, FUR);
ellipse(164, 62, 20, 52, FUR);
ellipse(92, 68, 9, 34, PINK);
ellipse(164, 68, 9, 34, PINK);
// horns (small gold triangles, approximated with shrinking rows)
for (let i = 0; i < 26; i++) {
  const w = Math.max(1, 7 - Math.floor(i / 4));
  for (let dx = -w; dx <= w; dx++) {
    set(104 + dx, 66 - i, GOLD);
    set(152 + dx, 66 - i, GOLD);
  }
}
// body + head
ellipse(128, 178, 84, 62, FUR);
ellipse(128, 196, 46, 38, BELLY);
ellipse(128, 118, 58, 52, FUR);
// cheeks + muzzle
ellipse(92, 132, 11, 7, PINK);
ellipse(164, 132, 11, 7, PINK);
ellipse(128, 136, 22, 14, BELLY);
// eyes
ellipse(106, 112, 9, 11, DARK);
ellipse(150, 112, 9, 11, DARK);
ellipse(109, 108, 3, 4, WHITE);
ellipse(153, 108, 3, 4, WHITE);
// nose
ellipse(128, 130, 6, 4, PINK);
// feet
ellipse(84, 240, 26, 10, FUR_DARK);
ellipse(172, 240, 26, 10, FUR_DARK);

// --- PNG encode (RGBA, filter 0 per row) -------------------------------
const raw = Buffer.alloc(SIZE * (SIZE * 4 + 1));
for (let y = 0; y < SIZE; y++) {
  raw[y * (SIZE * 4 + 1)] = 0;
  Buffer.from(px.buffer, y * SIZE * 4, SIZE * 4).copy(raw, y * (SIZE * 4 + 1) + 1);
}
const CRC_TABLE = (() => {
  const t = new Int32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c;
  }
  return t;
})();
function crc32(buf) {
  let c = 0xffffffff;
  for (const b of buf) c = CRC_TABLE[(c ^ b) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}
function chunk(type, data) {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length);
  const body = Buffer.concat([Buffer.from(type, 'ascii'), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(body));
  return Buffer.concat([len, body, crc]);
}
const ihdr = Buffer.alloc(13);
ihdr.writeUInt32BE(SIZE, 0);
ihdr.writeUInt32BE(SIZE, 4);
ihdr[8] = 8; // bit depth
ihdr[9] = 6; // RGBA
const png = Buffer.concat([
  Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
  chunk('IHDR', ihdr),
  chunk('IDAT', zlib.deflateSync(raw, { level: 9 })),
  chunk('IEND', Buffer.alloc(0)),
]);

const out = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'assets', 'icon.png');
fs.writeFileSync(out, png);
console.log(`wrote ${out} (${png.length} bytes)`);
