// Hermetic in-memory implementation of the canonical window.pkv contract
// (app/shared/types.ts) for UI tests. No Electron, no SQLite, no network:
// tests assert against this mock's recorded calls and observable state.

import type {
  BackupImportResult,
  LinkedNote,
  Note,
  NoteFilters,
  NoteInput,
  NoteSource,
  NoteUpdateInput,
  PkvApi,
  Revision,
  SearchFilters,
} from '../../src/types';

export interface MockCalls {
  create: NoteInput[];
  get: string[];
  list: NoteFilters[];
  update: Array<{ id: string; patch: NoteUpdateInput }>;
  delete: string[];
  search: Array<{ query: string; filter: SearchFilters }>;
  approve: string[];
  reject: Array<{ id: string; reason: string }>;
  revisionsList: string[];
  export: number;
  import: string[];
}

export interface MockBehavior {
  /** Override the export payload string. */
  exportResult?: string;
  /** Throw from backup.export. */
  exportError?: string;
  /** Override the import result (may include a forward-compat errors array). */
  importResult?: BackupImportResult & { errors?: string[] };
  /** Throw from a given IPC method. */
  fail?: { method: string; message: string };
}

export interface MockPkv extends PkvApi {
  calls: MockCalls;
  behavior: MockBehavior;
  /** Live in-memory notes; tests may inspect after actions. */
  store: Note[];
  revisionsStore: Record<string, Revision[]>;
}

function matchesStatusTag(
  note: Note,
  filter: NoteFilters | SearchFilters,
): boolean {
  if (filter.status && note.status !== filter.status) {
    return false;
  }
  if (filter.tag && filter.tag.trim().length > 0 && !note.tags.includes(filter.tag.trim())) {
    return false;
  }
  return true;
}

function failIf(behavior: MockBehavior, method: string): void {
  if (behavior.fail?.method === method) {
    throw new Error(behavior.fail.message);
  }
}

function toNoteSource(id: string, input: NonNullable<NoteInput['source']>): NoteSource {
  return {
    id,
    title: input.title ?? null,
    author: input.author ?? null,
    url: input.url ?? null,
    docPointer: input.docPointer ?? null,
    accessedAt: input.accessedAt ?? null,
  };
}

export function createMockPkv(
  seed: Note[],
  revisions: Record<string, Revision[]> = {},
): MockPkv {
  const store: Note[] = seed.map((n) => ({
    ...n,
    source: n.source ? { ...n.source } : null,
    tags: [...n.tags],
    links: n.links.map((l) => ({ ...l })),
  }));
  const revisionsStore: Record<string, Revision[]> = Object.fromEntries(
    Object.entries(revisions).map(([k, v]) => [k, v.map((r) => ({ ...r, tags: [...r.tags] }))]),
  );
  const calls: MockCalls = {
    create: [],
    get: [],
    list: [],
    update: [],
    delete: [],
    search: [],
    approve: [],
    reject: [],
    revisionsList: [],
    export: 0,
    import: [],
  };
  const behavior: MockBehavior = {};
  let counter = 100;

  const resolveLinks = (ids: string[]): LinkedNote[] =>
    ids.map((linkId) => {
      const target = store.find((n) => n.id === linkId);
      return target
        ? { id: target.id, title: target.title, status: target.status }
        : { id: linkId, title: `(unknown record ${linkId})`, status: 'candidate' as const };
    });

  const mock: MockPkv = {
    calls,
    behavior,
    store,
    revisionsStore,
    notes: {
      async create(input: NoteInput): Promise<Note> {
        failIf(behavior, 'notes.create');
        calls.create.push(input);
        counter += 1;
        const now = new Date().toISOString();
        const note: Note = {
          id: `note-${counter}`,
          title: input.title,
          body: input.body,
          status: 'candidate',
          rejectionReason: null,
          createdAt: now,
          updatedAt: now,
          source: input.source ? toNoteSource(`src-${counter}`, input.source) : null,
          tags: [...input.tags],
          links: resolveLinks(input.links ?? []),
          revisionCount: 0,
        };
        store.push(note);
        return structuredClone(note);
      },
      async get(id: string): Promise<Note | null> {
        failIf(behavior, 'notes.get');
        calls.get.push(id);
        const found = store.find((n) => n.id === id);
        return found ? structuredClone(found) : null;
      },
      async list(filters?: NoteFilters): Promise<Note[]> {
        failIf(behavior, 'notes.list');
        calls.list.push(filters ?? {});
        return store.filter((n) => matchesStatusTag(n, filters ?? {})).map((n) => structuredClone(n));
      },
      async update(id: string, patch: NoteUpdateInput): Promise<Note> {
        failIf(behavior, 'notes.update');
        calls.update.push({ id, patch });
        const note = store.find((n) => n.id === id);
        if (!note) throw new Error(`Note not found: ${id}`);
        if (patch.title !== undefined) note.title = patch.title;
        if (patch.body !== undefined) note.body = patch.body;
        if (patch.tags !== undefined) note.tags = [...patch.tags];
        if (patch.links !== undefined) note.links = resolveLinks(patch.links);
        note.updatedAt = new Date().toISOString();
        note.revisionCount += 1;
        const revs = revisionsStore[id] ?? [];
        revs.push({
          id: `rev-${id}-${revs.length + 1}`,
          noteId: id,
          revNo: revs.length + 1,
          title: note.title,
          body: note.body,
          tags: [...note.tags],
          status: note.status,
          changeSummary: patch.changeSummary,
          createdAt: note.updatedAt,
        });
        revisionsStore[id] = revs;
        return structuredClone(note);
      },
      async delete(id: string): Promise<boolean> {
        failIf(behavior, 'notes.delete');
        calls.delete.push(id);
        const index = store.findIndex((n) => n.id === id);
        if (index === -1) return false;
        store.splice(index, 1);
        return true;
      },
      async search(query: string, filters?: SearchFilters): Promise<Note[]> {
        failIf(behavior, 'notes.search');
        calls.search.push({ query, filter: filters ?? {} });
        const q = query.toLowerCase();
        return store
          .filter((n) => matchesStatusTag(n, filters ?? {}))
          .filter((n) =>
            [n.title, n.body, ...n.tags].join('\n').toLowerCase().includes(q),
          )
          .map((n) => structuredClone(n));
      },
    },
    review: {
      async approve(id: string): Promise<Note> {
        failIf(behavior, 'review.approve');
        calls.approve.push(id);
        const note = store.find((n) => n.id === id);
        if (!note) throw new Error(`Note not found: ${id}`);
        note.status = 'verified';
        note.rejectionReason = null;
        note.updatedAt = new Date().toISOString();
        return structuredClone(note);
      },
      async reject(id: string, reason: string): Promise<Note> {
        failIf(behavior, 'review.reject');
        calls.reject.push({ id, reason });
        const note = store.find((n) => n.id === id);
        if (!note) throw new Error(`Note not found: ${id}`);
        note.status = 'rejected';
        note.rejectionReason = reason;
        note.updatedAt = new Date().toISOString();
        return structuredClone(note);
      },
    },
    revisions: {
      async list(noteId: string): Promise<Revision[]> {
        failIf(behavior, 'revisions.list');
        calls.revisionsList.push(noteId);
        return [...(revisionsStore[noteId] ?? [])];
      },
    },
    backup: {
      async export(): Promise<string> {
        failIf(behavior, 'backup.export');
        calls.export += 1;
        if (behavior.exportError) throw new Error(behavior.exportError);
        if (behavior.exportResult !== undefined) return behavior.exportResult;
        return JSON.stringify({
          formatVersion: '1.0.0',
          exportedAt: new Date().toISOString(),
          notes: store.map((n) => ({ id: n.id, title: n.title })),
        });
      },
      async import(json: string): Promise<BackupImportResult> {
        failIf(behavior, 'backup.import');
        calls.import.push(json);
        if (behavior.importResult) return behavior.importResult;
        let parsed: unknown;
        try {
          parsed = JSON.parse(json);
        } catch {
          throw new Error('Invalid JSON: the file is not valid JSON.');
        }
        if (
          typeof parsed !== 'object' ||
          parsed === null ||
          !Array.isArray((parsed as { notes?: unknown }).notes)
        ) {
          throw new Error('Invalid backup: expected an object with a "notes" array.');
        }
        const entries = (parsed as { notes: Array<{ id?: string }> }).notes;
        let imported = 0;
        let skipped = 0;
        for (const entry of entries) {
          if (entry.id && store.some((n) => n.id === entry.id)) {
            skipped += 1;
          } else {
            imported += 1;
          }
        }
        return { imported, skipped };
      },
    },
  };
  return mock;
}

/** Installs the mock on window.pkv and returns it for call assertions. */
export function installMockPkv(
  seed: Note[],
  revisions: Record<string, Revision[]> = {},
): MockPkv {
  const mock = createMockPkv(seed, revisions);
  (window as unknown as { pkv: PkvApi }).pkv = mock;
  return mock;
}

/** Synthetic fixture notes — no real user data. Canonical shapes. */
export function fixtureNotes(): Note[] {
  return [
    {
      id: 'note-garden',
      title: 'Compost ratios',
      body: 'Carbon to nitrogen ratio around 25:1.\nTurn the pile weekly.',
      status: 'candidate',
      rejectionReason: null,
      createdAt: '2026-10-20T10:00:00.000Z',
      updatedAt: '2026-10-21T10:00:00.000Z',
      source: {
        id: 'src-garden',
        title: 'The Compost Handbook',
        author: 'M. Reyes',
        url: null,
        docPointer: null,
        accessedAt: null,
      },
      tags: ['gardening', 'soil'],
      links: [{ id: 'note-worms', title: 'Worm bin temperatures', status: 'verified' }],
      revisionCount: 2,
    },
    {
      id: 'note-worms',
      title: 'Worm bin temperatures',
      body: 'Keep the bin between 15 and 25 degrees Celsius.',
      status: 'verified',
      rejectionReason: null,
      createdAt: '2026-10-18T10:00:00.000Z',
      updatedAt: '2026-10-19T10:00:00.000Z',
      source: {
        id: 'src-worms',
        title: 'Vermiculture blog',
        author: null,
        url: 'https://example.com/worms',
        docPointer: null,
        accessedAt: null,
      },
      tags: ['gardening', 'worms'],
      links: [],
      revisionCount: 0,
    },
    {
      id: 'note-moon',
      title: 'Moon planting myth',
      body: 'No controlled trial supports planting by moon phase.',
      status: 'rejected',
      rejectionReason: 'Contradicted by trial data.',
      createdAt: '2026-10-17T10:00:00.000Z',
      updatedAt: '2026-10-18T10:00:00.000Z',
      source: null,
      tags: ['myth'],
      links: [],
      revisionCount: 0,
    },
  ];
}

/** Synthetic fixture revisions for note-garden — second revision edits the ratio. */
export function fixtureRevisions(): Record<string, Revision[]> {
  return {
    'note-garden': [
      {
        id: 'rev-garden-1',
        noteId: 'note-garden',
        revNo: 1,
        title: 'Compost ratios',
        body: 'Carbon to nitrogen ratio around 25:1.\nTurn the pile weekly.',
        tags: ['gardening', 'soil'],
        status: 'candidate',
        changeSummary: 'Initial capture from the handbook.',
        createdAt: '2026-10-20T10:00:00.000Z',
      },
      {
        id: 'rev-garden-2',
        noteId: 'note-garden',
        revNo: 2,
        title: 'Compost ratios',
        body: 'Carbon to nitrogen ratio around 30:1.\nTurn the pile weekly.\nKeep moist, not soggy.',
        tags: ['gardening', 'soil'],
        status: 'candidate',
        changeSummary: 'Corrected the ratio per chapter 4.',
        createdAt: '2026-10-21T10:00:00.000Z',
      },
    ],
  };
}
