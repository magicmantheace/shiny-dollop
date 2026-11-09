/**
 * Renderer-local index of documents the renderer has seen.
 *
 * The index is a COMPLETE index, never truncated: it is one of only two
 * ways the documents browser learns a document exists (the other is the
 * backend `documents:list` endpoint, which DocumentsList merges in), so
 * evicting the oldest entry would strand that document in SQLite with no
 * way to open, export, or delete it from the UI. Entries are keyed by
 * document id; deleting a document removes its entry.
 */
export interface RecentDoc {
  id: string;
  templateId: string;
  templateName: string;
  updatedAt: string;
}

const STORAGE_KEY = 'dtf.recentDocs.v1';

export function loadRecentDocs(): RecentDoc[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (e): e is RecentDoc =>
        typeof e === 'object' &&
        e !== null &&
        typeof (e as RecentDoc).id === 'string' &&
        typeof (e as RecentDoc).templateName === 'string',
    );
  } catch {
    return [];
  }
}

function persist(entries: RecentDoc[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
  } catch {
    // Storage full or unavailable: the index is best-effort only.
  }
}

/** Insert or refresh an entry; newest first. */
export function upsertRecentDoc(entry: RecentDoc): void {
  const rest = loadRecentDocs().filter((e) => e.id !== entry.id);
  persist([entry, ...rest]);
}

export function removeRecentDoc(id: string): void {
  persist(loadRecentDocs().filter((e) => e.id !== id));
}
