import type {
  ApprovedScript,
  DabApi,
  PreviewAction,
  Run,
  RunStatus,
  Workflow,
} from '../../shared/types';

export function sampleWorkflow(): Workflow {
  const steps: Workflow['steps'] = [
    {
      id: 's1',
      label: 'Copy report',
      kind: 'file-copy',
      from: 'a.txt',
      to: 'b.txt',
    },
    {
      id: 's2',
      label: 'Trash old',
      kind: 'file-move-to-trash',
      path: 'old.txt',
    },
    { id: 's3', label: 'Make dir', kind: 'folder-create', path: 'out' },
    {
      id: 's4',
      label: 'Run cleanup',
      kind: 'run-approved-script',
      scriptId: 'script-1',
      args: ['--fast'],
    },
    {
      id: 's5',
      label: 'Say done',
      kind: 'log-message',
      message: 'done',
    },
  ];
  return {
    id: 'wf-1',
    name: 'Test workflow',
    sandboxRoot: '/sandbox',
    steps,
    version: 1,
    versions: [
      {
        version: 1,
        name: 'Test workflow',
        sandboxRoot: '/sandbox',
        steps,
        createdAt: '2026-10-23T18:00:00.000Z',
      },
    ],
    createdAt: '2026-10-23T18:00:00.000Z',
    updatedAt: '2026-10-23T18:05:00.000Z',
  };
}

export function sampleScript(): ApprovedScript {
  return {
    id: 'script-1',
    name: 'Cleanup script',
    path: '/scripts/cleanup.sh',
    approvedAt: '2026-10-23T17:00:00.000Z',
  };
}

export function samplePreview(): PreviewAction[] {
  return [
    {
      stepId: 's1',
      kind: 'file-copy',
      label: 'Copy report',
      description: 'Copy a.txt to b.txt inside the sandbox',
    },
    {
      stepId: 's2',
      kind: 'file-move-to-trash',
      label: 'Trash old',
      description: 'Move old.txt to the sandbox trash folder',
    },
  ];
}

export function sampleRun(status: RunStatus): Run {
  return {
    id: 'run-1',
    workflowId: 'wf-1',
    workflowVersion: 1,
    status,
    steps: [
      {
        stepId: 's1',
        kind: 'file-copy',
        label: 'Copy report',
        outcome: 'succeeded',
        detail: 'copied 12 bytes',
      },
      {
        stepId: 's2',
        kind: 'file-move-to-trash',
        label: 'Trash old',
        outcome: status === 'failed' ? 'failed' : 'succeeded',
        detail: status === 'failed' ? 'disk is full' : 'moved to trash',
      },
    ],
    dryRun: false,
  };
}

type FakeOverrides = {
  [K in keyof DabApi]?: DabApi[K];
};

/**
 * Installs a hand-rolled fake window.dab. Every method records its name in
 * `calls` (in order) before running its implementation, unless overridden.
 */
export function installFakeDab(overrides: FakeOverrides = {}): {
  dab: DabApi;
  calls: string[];
} {
  const calls: string[] = [];

  const wrap = <F extends (...args: never[]) => Promise<unknown>>(
    name: string,
    impl: F,
  ): F =>
    (async (...args: never[]) => {
      calls.push(name);
      return impl(...args);
    }) as F;

  const dab = {
    workflowsList: wrap('workflowsList', async () => [sampleWorkflow()]),
    workflowsCreate: wrap(
      'workflowsCreate',
      async (name: string, sandboxRoot: string) => ({
        ...sampleWorkflow(),
        id: 'wf-new',
        name,
        sandboxRoot,
      }),
    ),
    workflowsGet: wrap('workflowsGet', async () => sampleWorkflow()),
    workflowsUpdate: wrap(
      'workflowsUpdate',
      async (
        id: string,
        patch: { name?: string; sandboxRoot?: string; steps?: Workflow['steps'] },
      ) => ({ ...sampleWorkflow(), id, ...patch, version: 2 }),
    ),
    workflowsDelete: wrap('workflowsDelete', async () => true),
    workflowsExport: wrap('workflowsExport', async () =>
      JSON.stringify(sampleWorkflow()),
    ),
    workflowsImport: wrap('workflowsImport', async () => sampleWorkflow()),
    scriptsList: wrap('scriptsList', async () => [sampleScript()]),
    scriptsRegister: wrap(
      'scriptsRegister',
      async (name: string, filePath: string) => ({
        ...sampleScript(),
        id: 'script-new',
        name,
        path: filePath,
      }),
    ),
    scriptsUnregister: wrap('scriptsUnregister', async () => true),
    runsPreview: wrap('runsPreview', async () => samplePreview()),
    runsStart: wrap('runsStart', async () => sampleRun('running')),
    runsCancel: wrap('runsCancel', async () => sampleRun('cancelled')),
    runsRetry: wrap('runsRetry', async () => sampleRun('running')),
    runsGet: wrap('runsGet', async () => sampleRun('completed')),
    runsList: wrap('runsList', async () => [] as Run[]),
    pickDirectory: wrap('pickDirectory', async () => null as string | null),
    ...overrides,
  } as DabApi;

  Object.defineProperty(window, 'dab', {
    value: dab,
    configurable: true,
    writable: true,
  });
  return { dab, calls };
}
