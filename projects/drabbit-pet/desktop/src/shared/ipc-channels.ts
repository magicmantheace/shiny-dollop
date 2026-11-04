/** IPC channel names shared by main, preload, and renderer. */
export const PetChannels = {
  /** invoke → IpcResult<PetSummary> */
  getSummary: 'pet:getSummary',
  /** invoke { kind } → IpcResult<ActionOutcome> */
  action: 'pet:action',
  /** invoke → IpcResult<PetEvent[]> (most recent, oldest first) */
  events: 'pet:events',
  /** invoke → IpcResult<null>; opens/toggles the care panel */
  openPanel: 'pet:openPanel',
  /** main → renderer push: { summary, events } after any state change */
  changed: 'pet:changed',
  /** main → renderer push: { hopping } when roaming state flips */
  roamState: 'pet:roamState',
} as const;

/** Companion server channels (P3). */
export const CompanionChannels = {
  /** invoke → IpcResult<CompanionState> */
  getState: 'companion:getState',
  /** invoke { enabled } → IpcResult<CompanionState> */
  setEnabled: 'companion:setEnabled',
  /** invoke → IpcResult<CompanionState> */
  regenerateToken: 'companion:regenerateToken',
} as const;
