// Script timeout: the timeout must terminate the whole process GROUP,
// not just the immediate child (Codex cycle-2 regression). With the old
// `spawn(..., { timeout })` behaviour, descendants of a timed-out script
// survived and — holding the inherited stdout/stderr pipes open — kept
// the `close` event (and therefore the run) waiting until they exited.
import { chmodSync, existsSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { runScript, type ActiveRunControl } from '../../electron/main/executor.js';
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

describe('script timeout process-group termination', () => {
  it('timeout kills descendants holding the stdio pipes, so close fires promptly', async () => {
    // The parent waits on a 4s background descendant. Killing only the
    // parent (old spawn-timeout) leaves the descendant holding the pipes:
    // close would not fire until ~4s.
    const scriptPath = writeScript('tree.sh', '#!/bin/sh\nsleep 4 &\nwait\n');
    const startedAt = Date.now();
    const result = await runScript(scriptPath, [], fx.root, freshCtrl(), 400);
    const elapsed = Date.now() - startedAt;

    expect(result.timedOut).toBe(true);
    expect(elapsed).toBeLessThan(2_500);
  }, 15000);

  it('escalates to SIGKILL when the process group ignores SIGTERM', async () => {
    // The parent ignores TERM; the background sleep inherits the ignored
    // disposition, so only the SIGKILL escalation can end the tree.
    const scriptPath = writeScript('stubborn.sh', "#!/bin/sh\ntrap '' TERM\nsleep 4 &\nwait\n");
    const startedAt = Date.now();
    const result = await runScript(scriptPath, [], fx.root, freshCtrl(), 400);
    const elapsed = Date.now() - startedAt;

    expect(result.timedOut).toBe(true);
    expect(elapsed).toBeLessThan(3_000);
  }, 15000);

  it('never spawns when the run was already cancelled', async () => {
    const marker = join(fx.root, 'ran.txt');
    const scriptPath = writeScript('marker.sh', `#!/bin/sh\ntouch "${marker}"\n`);
    const ctrl = freshCtrl();
    ctrl.cancelled = true;

    const result = await runScript(scriptPath, [], fx.root, ctrl, 5_000);

    expect(result.killed).toBe(true);
    expect(existsSync(marker)).toBe(false);
  });

  it('a fast script still completes normally and is not flagged timed out', async () => {
    const scriptPath = writeScript('fast.sh', '#!/bin/sh\necho hello-from-script\n');
    const result = await runScript(scriptPath, [], fx.root, freshCtrl(), 5_000);

    expect(result.exitCode).toBe(0);
    expect(result.stdout).toContain('hello-from-script');
    expect(result.timedOut).toBe(false);
    expect(result.killed).toBe(false);
  });
});
