// Script lifecycle regressions (Codex cycle 4):
//  - a script step must not complete while descendants it spawned are
//    still alive in its process group (no invisible background
//    persistence), even when the descendant redirected its stdio so
//    the parent's `close` fires immediately;
//  - script output must be bounded WHILE it is collected, not only
//    truncated when the step detail is persisted.
import { chmodSync, existsSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import {
  MAX_RETAINED_SCRIPT_OUTPUT,
  runScript,
  type ActiveRunControl,
} from '../../electron/main/executor.js';
import { makeFixture, type Fixture } from './helpers.js';

let fx: Fixture;

beforeEach(() => {
  fx = makeFixture();
});

afterEach(() => fx.cleanup());

function freshCtrl(): ActiveRunControl {
  return { cancelled: false, child: undefined };
}

function writeScript(name: string, body: string): string {
  const p = join(fx.root, name);
  writeFileSync(p, body);
  chmodSync(p, 0o755);
  return p;
}

describe('script step descendant cleanup', () => {
  it('terminates a surviving background descendant before completing', async () => {
    const marker = join(fx.root, 'descendant-was-here.txt');
    // Background subshell with redirected stdio: the parent exits 0
    // immediately and its pipes close, so without group cleanup the
    // descendant would write the marker ~1s after the step completed.
    const scriptPath = writeScript(
      'spawner.sh',
      `#!/bin/sh\n( sleep 1; touch "${marker}" ) >/dev/null 2>&1 &\necho parent-done\n`,
    );
    const startedAt = Date.now();
    const result = await runScript(scriptPath, [], fx.root, freshCtrl(), 10_000);
    const elapsed = Date.now() - startedAt;
    expect(result.exitCode).toBe(0);
    expect(result.stdout).toContain('parent-done');
    // Cleanup must not wait for the descendant's natural lifetime.
    expect(elapsed).toBeLessThan(5_000);
    // Well past the descendant's scheduled write: it must never happen.
    await new Promise((r) => setTimeout(r, 1_400));
    expect(existsSync(marker)).toBe(false);
  }, 15000);
});

describe('script output bounding', () => {
  it('caps retained stdout while collecting, while still draining the stream', async () => {
    const payload = join(fx.root, 'payload.txt');
    writeFileSync(payload, 'x'.repeat(1_000_000));
    const scriptPath = writeScript('noisy.sh', `#!/bin/sh\ncat "${payload}"\n`);
    const result = await runScript(scriptPath, [], fx.root, freshCtrl(), 10_000);
    expect(result.exitCode).toBe(0);
    expect(result.stdout.length).toBeLessThanOrEqual(
      MAX_RETAINED_SCRIPT_OUTPUT + 64,
    );
    expect(result.stdout.length).toBeLessThan(100_000);
    expect(result.stdout).toContain('truncated');
  }, 15000);

  it('caps retained stderr independently', async () => {
    const payload = join(fx.root, 'payload2.txt');
    writeFileSync(payload, 'y'.repeat(500_000));
    const scriptPath = writeScript('noisy-err.sh', `#!/bin/sh\ncat "${payload}" 1>&2\n`);
    const result = await runScript(scriptPath, [], fx.root, freshCtrl(), 10_000);
    expect(result.exitCode).toBe(0);
    expect(result.stderr.length).toBeLessThanOrEqual(
      MAX_RETAINED_SCRIPT_OUTPUT + 64,
    );
    expect(result.stderr).toContain('truncated');
  }, 15000);
});
