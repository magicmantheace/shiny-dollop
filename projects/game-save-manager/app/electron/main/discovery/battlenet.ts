/**
 * Battle.net discovery — client DETECTION ONLY.
 *
 * Battle.net keeps no parseable local install registry we can read honestly,
 * so the launcher client is detected (to show install state) and games are
 * registered MANUALLY by the user pointing at their save folders. We never
 * invent Battle.net game entries.
 */
import fs from 'node:fs';
import path from 'node:path';

export interface BattleNetStatus {
  detected: boolean;
  launcherPath?: string;
}

/** Default Battle.net launcher locations on Windows. Override in tests. */
export function defaultBattleNetLauncherPaths(): string[] {
  if (process.platform !== 'win32') return [];
  const programFiles = process.env['ProgramFiles'] ?? 'C:\\Program Files';
  const programFilesX86 = process.env['ProgramFiles(x86)'] ?? 'C:\\Program Files (x86)';
  return [
    path.join(programFilesX86, 'Battle.net', 'Battle.net Launcher.exe'),
    path.join(programFiles, 'Battle.net', 'Battle.net Launcher.exe'),
  ];
}

/** True when the Battle.net launcher executable exists on disk. */
export function detectBattleNet(launcherPaths?: string[]): BattleNetStatus {
  const candidates = launcherPaths ?? defaultBattleNetLauncherPaths();
  for (const p of candidates) {
    try {
      const st = fs.statSync(p);
      if (st.isFile()) return { detected: true, launcherPath: p };
    } catch {
      // Not here — keep looking.
    }
  }
  return { detected: false };
}
