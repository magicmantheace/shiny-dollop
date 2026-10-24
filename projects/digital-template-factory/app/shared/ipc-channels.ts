/**
 * Canonical IPC channel names (request/response). Preload and main must
 * use these constants. All channels carry the `dtf:` prefix.
 */
export const IpcChannels = {
  templatesList: 'dtf:templates:list',
  templatesGet: 'dtf:templates:get',
  templatesImport: 'dtf:templates:import',
  documentsCreate: 'dtf:documents:create',
  documentsGet: 'dtf:documents:get',
  documentsUpdateField: 'dtf:documents:update-field',
  documentsUpdateTokens: 'dtf:documents:update-tokens',
  documentsDelete: 'dtf:documents:delete',
  exportGenerate: 'dtf:export:generate',
  exportSave: 'dtf:export:save',
} as const;

export type IpcChannel = (typeof IpcChannels)[keyof typeof IpcChannels];
