import { useCallback, useEffect, useRef, useState } from 'react';
import type {
  Capability,
  JournalEntry,
  Profile,
  ResourceSnapshot,
} from '../shared/gpp-types';
import {
  listCapabilities,
  listJournal,
  listProfiles,
  listSnapshots,
} from './gpp';

export interface GppData {
  capabilities: Capability[];
  profiles: Profile[];
  journal: JournalEntry[];
  snapshots: ResourceSnapshot[];
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

/** Loads the four top-level collections once and exposes a refresh. */
export function useGppData(): GppData {
  const [capabilities, setCapabilities] = useState<Capability[]>([]);
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [journal, setJournal] = useState<JournalEntry[]>([]);
  const [snapshots, setSnapshots] = useState<ResourceSnapshot[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    (async () => {
      try {
        const [caps, profs, entries, snaps] = await Promise.all([
          listCapabilities(),
          listProfiles(),
          listJournal(),
          listSnapshots(),
        ]);
        if (cancelled || !mounted.current) return;
        setCapabilities(caps);
        setProfiles(profs);
        setJournal(entries);
        setSnapshots(snaps);
      } catch (err) {
        if (cancelled || !mounted.current) return;
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (!cancelled && mounted.current) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [nonce]);

  const refresh = useCallback(() => setNonce((n) => n + 1), []);

  return { capabilities, profiles, journal, snapshots, loading, error, refresh };
}

/**
 * A profile counts as "applied" while the journal holds at least one entry
 * for it that has not been rolled back. The contract has no separate
 * applied-flag, so the journal is the source of truth.
 */
export function isProfileApplied(profileId: string, journal: JournalEntry[]): boolean {
  return journal.some((e) => e.profileId === profileId && !e.rolledBackAt);
}
