/** Canonical IPC channel names. Preload and main must use these constants. */
export const IpcChannels = {
  libraryList: 'library.list',
  libraryAddManual: 'library.addManual',
  libraryUpdate: 'library.update',
  libraryRemove: 'library.remove',
  librarySetFavorite: 'library.setFavorite',
  gamesLaunch: 'games.launch',
  sessionsList: 'sessions.list',
  sessionsClear: 'sessions.clear',
  settingsGet: 'settings.get',
  settingsUpdate: 'settings.update',
  filesChooseExecutable: 'files.chooseExecutable',
  sourcesStatus: 'sources.status',
  sourcesScan: 'sources.scan',
  sourcesCancelScan: 'sources.cancelScan',
  sourcesOpenClient: 'sources.openClient',
} as const;

export type IpcChannel = (typeof IpcChannels)[keyof typeof IpcChannels];
