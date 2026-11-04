/** IPC channel names. The renderer may only invoke these narrow channels. */
export const SimChannels = {
  debtsList: 'sim:debts/list',
  debtsUpsert: 'sim:debts/upsert',
  debtsDelete: 'sim:debts/delete',
  incomeList: 'sim:income/list',
  incomeUpsert: 'sim:income/upsert',
  incomeDelete: 'sim:income/delete',
  simulateRun: 'sim:simulate/run',
  reportSave: 'sim:report/save',
} as const;

export type SimChannel = (typeof SimChannels)[keyof typeof SimChannels];
