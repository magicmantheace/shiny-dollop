import { describe, expect, it } from 'vitest';
import { mkdtempSync, mkdirSync, rmSync, writeFileSync, symlinkSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { scanRoots, titleFromExeName, gameIdFor } from '../engine/scanner.js';

describe('titleFromExeName', () => {
  it('strips .exe and turns underscores into spaces', () => {
    expect(titleFromExeName('halo_infinite.exe')).toBe('halo infinite');
  });
  it('handles mixed separators and extra whitespace', () => {
    expect(titleFromExeName('My.Game__Deluxe.EXE')).toBe('My Game Deluxe');
  });
  it('keeps hyphens', () => {
    expect(titleFromExeName('doom-eternal.exe')).toBe('doom-eternal');
  });
});

describe('scanRoots', () => {
  function fixtureTree(): { root: string; cleanup: () => void } {
    const root = mkdtempSync(join(tmpdir(), 'gmm-scan-'));
    const exe = (rel: string) => {
      const full = join(root, rel);
      mkdirSync(join(full, '..'), { recursive: true });
      writeFileSync(full, 'MZ-fake');
    };
    exe('Games/Halo/halo_infinite.exe');
    exe('Games/Doom/doom_eternal.exe');
    exe('Games/deep/a/b/c/d/e/too_deep.exe'); // depth 6 — beyond limit
    exe('Games/node_modules/fake/node_fake.exe'); // skipped dir
    exe('Games/.git/hooks/git_fake.exe'); // skipped dir
    exe('Games/Windows/system_fake.exe'); // skipped dir
    writeFileSync(join(root, 'Games/readme.txt'), 'not an exe');
    return { root, cleanup: () => rmSync(root, { recursive: true, force: true }) };
  }

  it('finds exes, applies depth limit, skips forbidden dirs', () => {
    const { root, cleanup } = fixtureTree();
    try {
      const found = scanRoots([join(root, 'Games')]);
      const names = found.map((f) => f.installPath.split(/[/\\]/).pop());
      expect(names).toContain('halo_infinite.exe');
      expect(names).toContain('doom_eternal.exe');
      expect(names).not.toContain('too_deep.exe');
      expect(names).not.toContain('node_fake.exe');
      expect(names).not.toContain('git_fake.exe');
      expect(names).not.toContain('system_fake.exe');
      expect(found).toHaveLength(2);
    } finally {
      cleanup();
    }
  });

  it('derives titles from filenames', () => {
    const { root, cleanup } = fixtureTree();
    try {
      const found = scanRoots([join(root, 'Games')]);
      const halo = found.find((f) => f.installPath.includes('halo_infinite.exe'));
      expect(halo?.title).toBe('halo infinite');
      expect(halo?.originalTitle).toBe('halo infinite');
    } finally {
      cleanup();
    }
  });

  it('ignores missing roots without throwing', () => {
    expect(scanRoots([join(tmpdir(), 'gmm-no-such-dir-xyz')])).toEqual([]);
  });

  it('guards against symlink loops', () => {
    const root = mkdtempSync(join(tmpdir(), 'gmm-loop-'));
    try {
      mkdirSync(join(root, 'Games'), { recursive: true });
      writeFileSync(join(root, 'Games', 'game.exe'), 'MZ-fake');
      symlinkSync(join(root, 'Games'), join(root, 'Games', 'self-link'), 'dir');
      const found = scanRoots([join(root, 'Games')]);
      expect(found.map((f) => f.installPath)).toHaveLength(1);
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });

  it('gameIdFor is stable and path-normalized', () => {
    const a = gameIdFor('C:\\Games\\Doom\\doom_eternal.exe');
    const b = gameIdFor('c:/games/doom/doom_eternal.exe');
    expect(a).toBe(b);
    expect(a).toMatch(/^[0-9a-f]{64}$/);
  });
});
