import { describe, expect, it } from 'vitest';
import { existsSync, readFileSync, unlinkSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
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
  it('approval is rejected when the target file changed after the diff was created', async () => {
    const { engine, db, config, ws } = makeFixture();
    engine.saveConfig(config);
    const { mkdirSync } = await import('node:fs');
    mkdirSync(join(ws, 'notes'), { recursive: true });
    writeFileSync(join(ws, 'notes/existing.txt'), 'original\n');
    engine.submit({ prompt: proposePrompt('notes/existing.txt', 'proposed replacement\n') });
    await engine.whenIdle();
    const p = engine.listProposals()[0]!;
    // The hash of the content the diff was created against is persisted.
    expect(p.originalHash).toBe(createHash('sha256').update('original\n', 'utf8').digest('hex'));
    // Intervening edit made while the proposal is pending.
    writeFileSync(join(ws, 'notes/existing.txt'), 'intervening edit\n');
    await expect(engine.approve(p.id)).rejects.toMatchObject({ code: 'PROPOSAL_FILE_CHANGED' });
    // The intervening edit is NOT silently lost, and the proposal stays pending.
    expect(readFileSync(join(ws, 'notes/existing.txt'), 'utf8')).toBe('intervening edit\n');
    expect(engine.getProposal(p.id).status).toBe('pending');
    expect(engine.listAudit(500).some((a) => a.event === 'proposal.stale')).toBe(true);
    db.close();
  });
  it('approval is rejected when the file was deleted after the diff was created', async () => {
    const { engine, db, config, ws } = makeFixture();
    engine.saveConfig(config);
    writeFileSync(join(ws, 'gone.txt'), 'original\n');
    engine.submit({ prompt: proposePrompt('gone.txt', 'proposed replacement\n') });
    await engine.whenIdle();
    const p = engine.listProposals()[0]!;
    unlinkSync(join(ws, 'gone.txt'));
    await expect(engine.approve(p.id)).rejects.toMatchObject({ code: 'PROPOSAL_FILE_CHANGED' });
    expect(existsSync(join(ws, 'gone.txt'))).toBe(false);
    expect(engine.getProposal(p.id).status).toBe('pending');
    db.close();
  });
  it('approval is rejected when a file appeared at a previously non-existent target', async () => {
    const { engine, db, config, ws } = makeFixture();
    engine.saveConfig(config);
    engine.submit({ prompt: proposePrompt('fresh.txt', 'proposed content\n') });
    await engine.whenIdle();
    const p = engine.listProposals()[0]!;
    expect(p.originalHash).toBeNull();
    writeFileSync(join(ws, 'fresh.txt'), 'someone else created this\n');
    await expect(engine.approve(p.id)).rejects.toMatchObject({ code: 'PROPOSAL_FILE_CHANGED' });
    expect(readFileSync(join(ws, 'fresh.txt'), 'utf8')).toBe('someone else created this\n');
    expect(engine.getProposal(p.id).status).toBe('pending');
    db.close();
  });
  it('approval still applies when the target file is unchanged since the diff', async () => {
    const { engine, db, config, ws } = makeFixture();
    engine.saveConfig(config);
    writeFileSync(join(ws, 'stable.txt'), 'original\n');
    engine.submit({ prompt: proposePrompt('stable.txt', 'proposed replacement\n') });
    await engine.whenIdle();
    const p = engine.listProposals()[0]!;
    const approved = await engine.approve(p.id);
    expect(approved.status).toBe('approved');
    expect(readFileSync(join(ws, 'stable.txt'), 'utf8')).toBe('proposed replacement\n');
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
