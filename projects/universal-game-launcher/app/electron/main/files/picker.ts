/** OS-native file picker for choosing a game executable. */
import { BrowserWindow, dialog } from 'electron';

export type PickResult = { path: string } | { canceled: true };

export async function chooseExecutable(): Promise<PickResult> {
  const parent = BrowserWindow.getFocusedWindow() ?? undefined;
  // On Windows we filter to .exe; on other platforms (dev) allow any file so
  // the manual-add flow can be exercised honestly.
  const filters =
    process.platform === 'win32'
      ? [{ name: 'Windows executables', extensions: ['exe'] }]
      : [{ name: 'All files', extensions: ['*'] }];
  const result = await dialog.showOpenDialog(parent, {
    title: 'Choose a game executable',
    properties: ['openFile'],
    filters,
  });
  if (result.canceled || result.filePaths.length === 0) {
    return { canceled: true };
  }
  const picked = result.filePaths[0];
  if (!picked) return { canceled: true };
  return { path: picked };
}
