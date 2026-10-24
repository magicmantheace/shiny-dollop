/** IPC channel names. The renderer may only invoke these via preload. */
export const InvChannels = {
  itemsList: 'inv:items:list',
  itemsGet: 'inv:items:get',
  itemsCreate: 'inv:items:create',
  itemsUpdate: 'inv:items:update',
  itemsDelete: 'inv:items:delete',
  categoriesList: 'inv:categories:list',
  attachmentsAdd: 'inv:attachments:add',
  attachmentsGet: 'inv:attachments:get',
  attachmentsDelete: 'inv:attachments:delete',
  maintenanceList: 'inv:maintenance:list',
  maintenanceAdd: 'inv:maintenance:add',
  maintenanceDelete: 'inv:maintenance:delete',
  warrantiesExpiring: 'inv:warranties:expiring',
  backupExport: 'inv:backup:export',
  backupImport: 'inv:backup:import',
} as const;

export type InvChannel = (typeof InvChannels)[keyof typeof InvChannels];
