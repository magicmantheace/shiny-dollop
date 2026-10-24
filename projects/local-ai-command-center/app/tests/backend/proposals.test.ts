import { describe, expect, it } from 'vitest';
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { makeFixture } from './helpers.js';

function proposePrompt(path: string, content: string): string {
  return `Do it\n\`\`\`propose path=${path}\n${content}\`\`\``;
}
describe('proposals', () => {
  it('full flow reject then approve', async () => {
    const { engine, db, config, ws } = makeFixture();
    engine.saveConfig(config);
    engine.submit({ prompt: proposePrompt('notes/out.txt', 'hello\nworld\n') });
    await engine.whenIdle();
    const props = engine.listProposals();
    expect(props.length).toBe(1);
    const p = props[0]!;
    expect(p.status).toBe('pending');
    expect(p.diff).toContain('+hello');
    expect(p.proposedContent).toBe('hello\nworld\n');
    await engine.reject(p.id);
    expect(existsSync(join(ws, 'notes/out.txt'))).toBe(false);
    // second proposal approve
    engine.submit({ prompt: proposePrompt('notes/ok.txt', 'approved line\n') });
    await engine.whenIdle();
    const p2 = engine.listProposals().find((x) => x.relativePath === 'notes/ok.txt')!;
    expect(p2).toBeTruthy();
    await engine.approve(p2.id);
    expect(readFileSync(join(ws, 'notes/ok.txt'), 'utf8')).toBe('approved line\n');
    // decided checks
    await expect(engine.approve(p2.id)).rejects.toMatchObject({ code: 'PROPOSAL_NOT_PENDING' });
    await expect(engine.reject(p.id)).rejects.toMatchObject({ code: 'PROPOSAL_NOT_PENDING' });
    db.close();
  });
  it('reject racing an in-flight approve cannot be overwritten by the approval', async () => {
    const { engine, db, config, ws } = makeFixture();
    engine.saveConfig(config);
    engine.submit({ prompt: proposePrompt('notes/race.txt', 'raced\n') });
    await engine.whenIdle();
    const p = engine.listProposals()[0]!;
    // Start approve without awaiting: it claims the decision synchronously
    // before yielding on mkdir, so the racing reject must fail — it can
    // never succeed and then be overwritten by the resumed approval.
    const approving = engine.approve(p.id);
    await expect(engine.reject(p.id)).rejects.toMatchObject({ code: 'PROPOSAL_NOT_PENDING' });
    const approved = await approving;
    expect(approved.status).toBe('approved');
    expect(engine.getProposal(p.id).status).toBe('approved');
    expect(readFileSync(join(ws, 'notes/race.txt'), 'utf8')).toBe('raced\n');
    db.close();
  });
  it('symlink escape: approving a proposal through an outside symlink writes nothing outside', async () => {
    const { engine, db, config, ws } = makeFixture();
    engine.saveConfig(config);
    engine.submit({ prompt: proposePrompt('notes/ok2.txt', 'x\n') });
    await engine.whenIdle();
    const p = engine.listProposals()[0]!;
    // Point the proposal at a path through a symlinked dir outside the workspace.
    const { mkdtempSync, symlinkSync } = await import('node:fs');
    const { tmpdir } = await import('node:os');
    const outside = mkdtempSync(join(tmpdir(), 'lacc-outside-'));
    symlinkSync(outside, join(ws, 'link'), 'dir');
    db.prepare('UPDATE proposals SET relative_path=? WHERE id=?').run('link/evil.txt', p.id);
    await expect(engine.approve(p.id)).rejects.toMatchObject({ code: 'PATH_OUTSIDE_WORKSPACE' });
    expect(existsSync(join(outside, 'evil.txt'))).toBe(false);
    expect(engine.getProposal(p.id).status).toBe('pending');
    db.close();
  });
  it('escape path creates no proposal, task completes, audit records', async () => {
    const { engine, db, config } = makeFixture();
    engine.saveConfig(config);
    const task = engine.submit({ prompt: proposePrompt('../escape.txt', 'evil\n') });
    await engine.whenIdle();
    expect(engine.getTask(task.id).status).toBe('completed');
    expect(engine.listProposals().length).toBe(0);
    const audit = engine.listAudit(500);
    expect(audit.some((a) => a.event === 'proposal.rejected-path')).toBe(true);
    const logs = engine.listTaskLogs(task.id);
    expect(logs.some((l) => l.level === 'error')).toBe(true);
    db.close();
  });
});
