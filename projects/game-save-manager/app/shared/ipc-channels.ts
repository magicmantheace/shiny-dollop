/**
 * Canonical IPC channel names (request/response) and event names
 * (main → renderer push). Preload and main must use these constants.
 */
export const IpcChannels = {
  gamesList: 'games.list',
  gamesAdd: 'games.add',
  gamesUpdate: 'games.update',
  gamesRemove: 'games.remove',
  gamesDiscoverCandidates: 'games.discoverCandidates',
  gamesChooseFolder: 'games.chooseFolder',
  backupsCreate: 'backups.create',
  backupsList: 'backups.list',
  backupsGet: 'backups.get',
  backupsVerify: 'backups.verify',
  backupsRestore: 'backups.restore',
  schedulesList: 'schedules.list',
  schedulesSet: 'schedules.set',
  schedulesDelete: 'schedules.delete',
} as const;

export type IpcChannel = (typeof IpcChannels)[keyof typeof IpcChannels];

/** Push events emitted by the main process (backup progress / outcome). */
export const IpcEvents = {
  backupProgress: 'backup.progress',
  backupCompleted: 'backup.completed',
  backupFailed: 'backup.failed',
} as const;

export type IpcEvent = (typeof IpcEvents)[keyof typeof IpcEvents];
