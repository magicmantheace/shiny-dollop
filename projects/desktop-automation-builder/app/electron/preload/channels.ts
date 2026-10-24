// Maps every DabApi method name to its IPC channel, 1:1 with
// DAB_IPC_CHANNELS in shared/types.ts. Shared by the preload script and the
// main-process IPC registration so the two can never drift apart.
import { DAB_IPC_CHANNELS, type DabApi, type DabIpcChannel } from '../../shared/types.js';

export const DAB_METHOD_CHANNELS: Record<keyof DabApi, DabIpcChannel> = {
  workflowsList: 'dab:workflows:list',
  workflowsCreate: 'dab:workflows:create',
  workflowsGet: 'dab:workflows:get',
  workflowsUpdate: 'dab:workflows:update',
  workflowsDelete: 'dab:workflows:delete',
  workflowsExport: 'dab:workflows:export',
  workflowsImport: 'dab:workflows:import',
  scriptsList: 'dab:scripts:list',
  scriptsRegister: 'dab:scripts:register',
  scriptsUnregister: 'dab:scripts:unregister',
  runsPreview: 'dab:runs:preview',
  runsStart: 'dab:runs:start',
  runsCancel: 'dab:runs:cancel',
  runsRetry: 'dab:runs:retry',
  runsGet: 'dab:runs:get',
  runsList: 'dab:runs:list',
  pickDirectory: 'dab:dialog:pick-directory',
};

/** Compile-time + runtime assertion that the map covers every channel exactly once. */
const _channelCoverage: Record<DabIpcChannel, keyof DabApi> = (() => {
  const inverse = {} as Record<DabIpcChannel, keyof DabApi>;
  for (const [method, channel] of Object.entries(DAB_METHOD_CHANNELS) as [keyof DabApi, DabIpcChannel][]) {
    inverse[channel] = method;
  }
  return inverse;
})();

export function assertChannelCoverage(): void {
  const mapped = new Set(Object.values(DAB_METHOD_CHANNELS));
  for (const channel of DAB_IPC_CHANNELS) {
    if (!mapped.has(channel)) {
      throw new Error(`DAB_IPC_CHANNELS entry "${channel}" has no DabApi method mapping.`);
    }
  }
  if (Object.keys(_channelCoverage).length !== DAB_IPC_CHANNELS.length) {
    throw new Error('DAB_METHOD_CHANNELS does not cover DAB_IPC_CHANNELS exactly once.');
  }
}
