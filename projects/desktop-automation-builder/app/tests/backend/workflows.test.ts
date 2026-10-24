// Workflow CRUD, versioning, and export/import.
import { mkdirSync } from 'node:fs';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import {
  createWorkflow,
  deleteWorkflow,
  getWorkflow,
  listRuns,
  updateWorkflow,
} from '../../electron/main/store.js';
import { exportWorkflowJson, importWorkflowJson } from '../../electron/main/transfer.js';
import { makeFixture, type Fixture } from './helpers.js';

let fx: Fixture;

beforeEach(() => {
  fx = makeFixture();
  mkdirSync(fx.sandbox, { recursive: true });
});

afterEach(() => fx.cleanup());

describe('workflow versioning', () => {
  it('update bumps the version and archives the previous snapshot in history', () => {
    const wf = createWorkflow(fx.db, { name: 'v1-name', sandboxRoot: fx.sandbox });
    expect(wf.version).toBe(1);
    expect(wf.versions).toHaveLength(0);

    const v2 = updateWorkflow(fx.db, wf.id, {
      name: 'v2-name',
      steps: [{ id: 'lg', label: 'Log', kind: 'log-message', message: 'hi' }],
    });
    expect(v2).not.toBeNull();
    expect(v2!.version).toBe(2);
    expect(v2!.name).toBe('v2-name');
    expect(v2!.versions).toHaveLength(1);
    expect(v2!.versions[0]?.version).toBe(1);
    expect(v2!.versions[0]?.name).toBe('v1-name');
    expect(v2!.versions[0]?.steps).toEqual([]);

    const v3 = updateWorkflow(fx.db, wf.id, { sandboxRoot: fx.sandbox });
    expect(v3!.version).toBe(3);
    expect(v3!.versions).toHaveLength(2);
    expect(v3!.versions[1]?.name).toBe('v2-name');
    expect(v3!.versions[1]?.steps).toHaveLength(1);
  });

  it('delete removes the workflow', () => {
    const wf = createWorkflow(fx.db, { name: 'gone', sandboxRoot: fx.sandbox });
    expect(deleteWorkflow(fx.db, wf.id)).toBe(true);
    expect(getWorkflow(fx.db, wf.id)).toBeNull();
    expect(deleteWorkflow(fx.db, wf.id)).toBe(false);
  });
});

describe('export / import', () => {
  function seedWorkflow() {
    const wf = createWorkflow(fx.db, { name: 'exportable', sandboxRoot: fx.sandbox });
    const updated = updateWorkflow(fx.db, wf.id, {
      steps: [
        { id: 'cp', label: 'Copy', kind: 'file-copy', from: 'a.txt', to: 'b.txt' },
        { id: 'lg', label: 'Log', kind: 'log-message', message: 'note' },
      ],
    });
    return updated!;
  }

  it('round-trips: export then import creates a NEW workflow with the same content', () => {
    const original = seedWorkflow();
    const json = exportWorkflowJson(original);
    const envelope = JSON.parse(json) as { formatVersion: string; workflow: { name: string } };
    expect(envelope.formatVersion).toBe('1.0.0');
    expect(envelope.workflow.name).toBe('exportable');

    const imported = importWorkflowJson(fx.db, json);
    expect(imported.id).not.toBe(original.id);
    expect(imported.name).toBe('exportable');
    expect(imported.steps).toEqual(original.steps);
    expect(imported.version).toBe(original.version);
    // Import never auto-runs: no run records exist for the new workflow.
    expect(listRuns(fx.db, imported.id)).toHaveLength(0);
  });

  it('rejects an import with an unsupported major formatVersion', () => {
    const original = seedWorkflow();
    const json = exportWorkflowJson(original).replace('"1.0.0"', '"2.0.0"');
    expect(() => importWorkflowJson(fx.db, json)).toThrowError(
      expect.objectContaining({ code: 'IMPORT_VERSION_UNSUPPORTED' }),
    );
  });

  it('rejects malformed JSON and wrong shapes with IMPORT_INVALID', () => {
    expect(() => importWorkflowJson(fx.db, 'not json at all')).toThrowError(
      expect.objectContaining({ code: 'IMPORT_INVALID' }),
    );
    expect(() =>
      importWorkflowJson(fx.db, JSON.stringify({ formatVersion: '1.0.0', exportedAt: 'now', workflow: { name: 42 } })),
    ).toThrowError(expect.objectContaining({ code: 'IMPORT_INVALID' }));
    expect(() =>
      importWorkflowJson(fx.db, JSON.stringify({ exportedAt: 'now', workflow: {} })),
    ).toThrowError(expect.objectContaining({ code: 'IMPORT_INVALID' }));
  });

  it('imported workflows keep their steps but not the source history', () => {
    const original = seedWorkflow();
    const imported = importWorkflowJson(fx.db, exportWorkflowJson(original));
    expect(imported.versions).toHaveLength(0);
  });
});
