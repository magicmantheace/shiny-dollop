import { describe, expect, it } from 'vitest';
import { symlinkSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { makeContext, minimalPng, minimalJpeg } from './helpers.js';

describe('artwork.add', () => {
  it('accepts a valid PNG by magic bytes', () => {
    const ctx = makeContext();
    try {
      const src = join(ctx.dir, 'cover.png');
      writeFileSync(src, minimalPng());
      const art = ctx.artwork.add(src, 'file');
      expect(art.mime).toBe('image/png');
      expect(art.fileName).toMatch(/\.png$/);
      expect(ctx.artwork.list()).toHaveLength(1);
      const url = ctx.artwork.fileUrl(art.id);
      expect(url).toMatch(/^file:\/\//);
      expect(url.endsWith(art.fileName)).toBe(true);
    } finally {
      ctx.dispose();
    }
  });

  it('accepts a valid JPEG', () => {
    const ctx = makeContext();
    try {
      const src = join(ctx.dir, 'cover.jpg');
      writeFileSync(src, minimalJpeg());
      const art = ctx.artwork.add(src, 'file');
      expect(art.mime).toBe('image/jpeg');
    } finally {
      ctx.dispose();
    }
  });

  it('accepts a valid WEBP (RIFF....WEBP magic)', () => {
    const ctx = makeContext();
    try {
      const webp = Buffer.concat([
        Buffer.from('RIFF', 'ascii'),
        Buffer.alloc(4),
        Buffer.from('WEBP', 'ascii'),
      ]);
      const src = join(ctx.dir, 'cover.webp');
      writeFileSync(src, webp);
      const art = ctx.artwork.add(src, 'file');
      expect(art.mime).toBe('image/webp');
    } finally {
      ctx.dispose();
    }
  });

  it('rejects a corrupt file with an image extension', () => {
    const ctx = makeContext();
    try {
      const src = join(ctx.dir, 'fake.png');
      writeFileSync(src, 'this is not an image at all');
      expect(() => ctx.artwork.add(src, 'file')).toThrow(/unsupported image type/);
      expect(ctx.artwork.list()).toHaveLength(0);
    } finally {
      ctx.dispose();
    }
  });

  it('rejects an oversize file', () => {
    const ctx = makeContext();
    try {
      const src = join(ctx.dir, 'big.png');
      // valid PNG header then pad past 10 MB
      const big = Buffer.concat([minimalPng(), Buffer.alloc(10 * 1024 * 1024 + 1)]);
      writeFileSync(src, big);
      expect(() => ctx.artwork.add(src, 'file')).toThrow(/too large/);
    } finally {
      ctx.dispose();
    }
  });

  it('rejects a missing file', () => {
    const ctx = makeContext();
    try {
      expect(() => ctx.artwork.add(join(ctx.dir, 'nope.png'), 'file')).toThrow(
        /not found/
      );
    } finally {
      ctx.dispose();
    }
  });

  it('resolves symlinks explicitly instead of following blindly', () => {
    const ctx = makeContext();
    try {
      const real = join(ctx.dir, 'real.png');
      writeFileSync(real, minimalPng());
      const link = join(ctx.dir, 'link.png');
      symlinkSync(real, link);
      const art = ctx.artwork.add(link, 'file');
      expect(art.mime).toBe('image/png');
    } finally {
      ctx.dispose();
    }
  });

  it('rejects a dangling symlink', () => {
    const ctx = makeContext();
    try {
      const link = join(ctx.dir, 'dangling.png');
      symlinkSync(join(ctx.dir, 'missing-target.png'), link);
      expect(() => ctx.artwork.add(link, 'file')).toThrow();
    } finally {
      ctx.dispose();
    }
  });

  it('rejects an unsupported but real format (GIF)', () => {
    const ctx = makeContext();
    try {
      const src = join(ctx.dir, 'anim.gif');
      writeFileSync(src, Buffer.from('GIF89a' + 'x'.repeat(64), 'ascii'));
      expect(() => ctx.artwork.add(src, 'file')).toThrow(/unsupported image type/);
    } finally {
      ctx.dispose();
    }
  });
});
