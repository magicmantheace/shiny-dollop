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
