import { readFileSync } from 'node:fs';

import type {
  Artwork,
  ChangeEntry,
  Collection,
  ConflictInfo,
  Game,
  MetadataBundle,
  Tag,
} from '../shared/ipc-contract.js';
import { ArtworkStore } from './artwork.js';
import { ChangeLog } from './changes.js';
import { Library } from './library.js';

export const BUNDLE_FORMAT = '1.0.0';
export const BUNDLE_EXPORTER = 'game-metadata-manager/1.0.0';
export const BUNDLE_MAJOR = 1;
export const MAX_BUNDLE_BYTES = 50 * 1024 * 1024;

const SEMVER_RE = /^\d+\.\d+\.\d+$/;

export function parseMajor(version: string): number | null {
  if (!SEMVER_RE.test(version)) return null;
  const major = Number(version.split('.')[0]);
  return Number.isInteger(major) ? major : null;
}

export class BundleIO {
  constructor(
    private library: Library,
    private artwork: ArtworkStore,
    private changes: ChangeLog
  ) {}

  /** Build the bundle JSON (games + base64 artwork + tags/collections for reversibility). */
  exportBundle(): string {
    const games = this.library.list();
    const artworkEntries: MetadataBundle['artwork'] = [];
    for (const art of this.artwork.list()) {
      const bytes = readFileSync(this.artwork.filePath(art.id));
      artworkEntries.push({
        id: art.id,
        provenance: art.provenance,
        mime: art.mime,
        dataBase64: bytes.toString('base64'),
      });
    }
    const bundle: MetadataBundle & { tags: Tag[]; collections: Collection[] } = {
      formatVersion: BUNDLE_FORMAT,
      exportedAt: new Date().toISOString(),
      exporter: BUNDLE_EXPORTER,
      games,
      artwork: artworkEntries,
      tags: this.library.listTags(),
      collections: this.library.listCollections(),
    };
    const json = JSON.stringify(bundle);
    if (Buffer.byteLength(json, 'utf8') > MAX_BUNDLE_BYTES) {
      throw new Error('bundle exceeds the 50 MB limit');
    }
    return json;
  }

  /**
   * Import a bundle: validate formatVersion (semver, reject unknown major),
   * dedupe by game id, merge per-field preferring newest updatedAt, record
   * conflicts, and log ChangeEntry records for bundle-sourced changes.
   */
  importBundle(jsonText: string): {
    added: number;
    updated: number;
    conflicts: ConflictInfo[];
  } {
    if (Buffer.byteLength(jsonText, 'utf8') > MAX_BUNDLE_BYTES) {
      throw new Error('bundle exceeds the 50 MB limit');
    }
    let parsed: unknown;
    try {
      parsed = JSON.parse(jsonText);
    } catch {
      throw new Error('bundle is not valid JSON');
    }
    if (typeof parsed !== 'object' || parsed === null) {
      throw new Error('bundle must be a JSON object');
    }
    const bundle = parsed as Partial<MetadataBundle> & {
      tags?: Tag[];
      collections?: Collection[];
    };

    if (typeof bundle.formatVersion !== 'string') {
      throw new Error('bundle is missing formatVersion');
    }
    const major = parseMajor(bundle.formatVersion);
    if (major === null) {
      throw new Error(`bundle formatVersion is not valid semver: ${bundle.formatVersion}`);
    }
    if (major !== BUNDLE_MAJOR) {
      throw new Error(
        `unsupported bundle formatVersion ${bundle.formatVersion} (this app handles major version ${BUNDLE_MAJOR})`
      );
    }
    if (!Array.isArray(bundle.games)) throw new Error('bundle.games must be an array');
    if (!Array.isArray(bundle.artwork)) throw new Error('bundle.artwork must be an array');

    const conflicts: ConflictInfo[] = [];

    const mergeFields: Array<'title' | 'description' | 'artworkId' | 'tagIds' | 'collectionIds'> = [
      'title',
      'description',
      'artworkId',
      'tagIds',
      'collectionIds',
    ];

    const eq = (a: unknown, b: unknown): boolean => JSON.stringify(a) === JSON.stringify(b);

    // The whole import is transactional: games, change-log entries,
    // artwork rows and taxonomy all commit together or not at all.
    // Previously each write committed individually, so a failure while
    // restoring artwork (e.g. an unwritable cache) left the preceding
    // game changes persisted while the IPC reported a failed import.
    // Artwork files written during the import are compensated on
    // failure: files for artwork ids that did not exist before the
    // import are deleted after the DB rollback.
    const preExistingArtworkIds = new Set(this.artwork.list().map((a) => a.id));
    const attemptedNewArtworkIds: string[] = [];
    try {
      return this.library.runInTransaction(() =>
        this.importBundleInTransaction(bundle, mergeFields, eq, conflicts, preExistingArtworkIds, attemptedNewArtworkIds)
      );
    } catch (err) {
      for (const id of attemptedNewArtworkIds) this.artwork.deleteCachedFile(id);
      throw err;
    }
  }

  private importBundleInTransaction(
    bundle: Partial<MetadataBundle> & { tags?: Tag[]; collections?: Collection[] },
    mergeFields: Array<'title' | 'description' | 'artworkId' | 'tagIds' | 'collectionIds'>,
    eq: (a: unknown, b: unknown) => boolean,
    conflicts: ConflictInfo[],
    preExistingArtworkIds: Set<string>,
    attemptedNewArtworkIds: string[]
  ): { added: number; updated: number; conflicts: ConflictInfo[] } {
    let added = 0;
    let updated = 0;
    for (const bundleGame of bundle.games as Game[]) {
      if (typeof bundleGame.id !== 'string' || !bundleGame.id) {
        throw new Error('bundle contains a game with a missing id');
      }
      const local = this.library.get(bundleGame.id);

      if (!local) {
        // New game: restore wholesale and log the import.
        this.library.insertGame(bundleGame);
        this.changes.append(bundleGame.id, 'import', '', bundleGame.title);
        added++;
        continue;
      }

      // Merge per field: newest updatedAt wins; record conflicts for divergences.
      const bundleNewer = bundleGame.updatedAt >= local.updatedAt;
      let touched = false;

      for (const field of mergeFields) {
        const localVal = local[field];
        const bundleVal = bundleGame[field];
        if (eq(localVal, bundleVal)) continue;
        const winner = bundleNewer ? bundleVal : localVal;
        if (!eq(winner, localVal)) {
          const before = JSON.stringify(localVal);
          const after = JSON.stringify(winner);
          if (field === 'artworkId') {
            this.library.setArtworkId(local.id, winner as string | null, bundleGame.updatedAt);
          } else if (field === 'title' || field === 'description') {
            this.library.setField(local.id, field, winner as string, bundleGame.updatedAt);
          } else {
            this.library.setField(local.id, field, JSON.stringify(winner), bundleGame.updatedAt);
          }
          this.changes.append(local.id, field, before, after);
          touched = true;
        }
        conflicts.push({
          gameId: local.id,
          field,
          localValue: JSON.stringify(localVal),
          bundleValue: JSON.stringify(bundleVal),
          chosen: bundleNewer ? 'bundle' : 'local',
        });
      }
      if (touched) updated++;
    }

    // Restore artwork payloads into the app-owned cache.
    for (const entry of bundle.artwork as MetadataBundle['artwork']) {
      if (typeof entry.id !== 'string' || typeof entry.dataBase64 !== 'string') continue;
      // Record new artwork ids BEFORE writing, so a write that fails
      // part-way still gets its partial file compensated by the caller.
      if (!preExistingArtworkIds.has(entry.id) && !attemptedNewArtworkIds.includes(entry.id)) {
        attemptedNewArtworkIds.push(entry.id);
      }
      this.artwork.addBase64(entry.id, entry.provenance ?? 'bundle', entry.mime, entry.dataBase64);
    }

    // Restore tags/collections so export→wipe→import is fully reversible.
    for (const tag of bundle.tags ?? []) {
      if (tag && typeof tag.id === 'string' && typeof tag.name === 'string') {
        this.library.upsertTag(tag);
      }
    }
    for (const collection of bundle.collections ?? []) {
      if (collection && typeof collection.id === 'string' && typeof collection.name === 'string') {
        this.library.upsertCollection(collection);
      }
    }

    return { added, updated, conflicts };
  }

  /** Wipe all library data (used by the reversible export→wipe→import flow). */
  wipe(): void {
    for (const game of this.library.list()) this.library.removeGame(game.id);
    this.artwork.clear();
    this.changes.clear();
  }
}

export type { Artwork, ChangeEntry };
