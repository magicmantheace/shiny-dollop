/**
 * Canonical IPC channel names. Preload and main must use these constants.
 * The renderer must only talk through the typed `window.storageAnalyzer`
 * bridge — never raw channel strings.
 */
export const IpcChannels = {
  dialogChooseDirectory: 'storage.dialog.chooseDirectory',
  scanStart: 'storage.scan.start',
  scanCancel: 'storage.scan.cancel',
  scanStatus: 'storage.scan.status',
  scanList: 'storage.scan.list',
  resultsSummary: 'storage.results.summary',
  resultsDuplicates: 'storage.results.duplicates',
  resultsSearch: 'storage.results.search',
  exportReport: 'storage.export.report',
} as const;

export type IpcChannel = (typeof IpcChannels)[keyof typeof IpcChannels];

/** Renderer-subscribable event names (webContents.send from main). */
export const StorageEvents = {
  progress: 'storage.scan.progress',
  finished: 'storage.scan.finished',
} as const;

export type StorageEvent = (typeof StorageEvents)[keyof typeof StorageEvents];
