import { useCallback, useEffect, useState } from 'react';
import { getGmm, type Artwork, type Collection, type Game, type Tag } from './gmm';

export interface LibraryData {
  games: Game[];
  tags: Tag[];
  collections: Collection[];
  artworks: Artwork[];
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

/**
 * Loads the whole library snapshot (games, tags, collections, cached artwork)
 * for the top-level views. `refreshKey` changes and the returned `refresh()`
 * both re-trigger a load; components call `onChanged` after any mutation.
 */
export function useLibraryData(refreshKey: number): LibraryData {
  const [games, setGames] = useState<Game[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [collections, setCollections] = useState<Collection[]>([]);
  const [artworks, setArtworks] = useState<Artwork[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  const refresh = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    void (async () => {
      try {
        const gmm = getGmm();
        const [g, t, c, a] = await Promise.all([
          gmm.lib.list(),
          gmm.tags.list(),
          gmm.collections.list(),
          gmm.artwork.list(),
        ]);
        if (cancelled) return;
        // Missing flags are computed on demand by the engine (never persisted),
        // so merge the rescan result into the loaded games. Best-effort: the
        // library still loads if detection fails.
        let missing = new Set<string>();
        try {
          const r = await gmm.lib.rescan();
          missing = new Set(r.missingIds ?? []);
        } catch {
          missing = new Set();
        }
        setGames((g ?? []).map((game) => (missing.has(game.id) ? { ...game, missing: true } : game)));
        setTags(t ?? []);
        setCollections(c ?? []);
        setArtworks(a ?? []);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [refreshKey, nonce]);

  return { games, tags, collections, artworks, loading, error, refresh };
}
