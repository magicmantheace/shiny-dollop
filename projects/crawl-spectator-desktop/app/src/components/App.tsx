import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { isHighlight } from '../../shared/contract';
import type { LedgerEvent } from '../../shared/contract';
import type { ConnectionStatus, Descender, FeedSnapshot, Party, Prefs, SearchResult } from '../../shared/types';
import { bannerKind, bannerText } from '../lib/spectator';

const api = (): Window['spectator'] => window.spectator;

function errText(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

export function App(): React.JSX.Element {
  const [status, setStatus] = useState<ConnectionStatus | null>(null);
  const [prefs, setPrefs] = useState<Prefs>({ baseUrl: 'http://127.0.0.1:8000', followedDescenderIds: [] });
  const [baseUrlInput, setBaseUrlInput] = useState('');
  const [descenders, setDescenders] = useState<Descender[]>([]);
  const [parties, setParties] = useState<Party[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [profile, setProfile] = useState<Descender | null>(null);
  const [history, setHistory] = useState<LedgerEvent[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResult, setSearchResult] = useState<SearchResult | null>(null);
  const [feed, setFeed] = useState<FeedSnapshot>({ events: [], cursorTick: null, droppedCount: 0, truncatedCatchUps: 0, bufferedCount: 0 });
  const [followedOnly, setFollowedOnly] = useState(false);
  const [highlights, setHighlights] = useState<LedgerEvent[]>([]);
  const [replayAfter, setReplayAfter] = useState('');
  const [replayType, setReplayType] = useState('');
  const [replay, setReplay] = useState<LedgerEvent[]>([]);
  const [actionError, setActionError] = useState<string | null>(null);

  const followed = useMemo(() => new Set(prefs.followedDescenderIds), [prefs.followedDescenderIds]);
  const connected = status?.state === 'connected';

  // Connection identity + generation guard. Source-specific renderer
  // state (selected profile, history, search, replay, directory, feed,
  // highlights) belongs to ONE connection: when the identity changes
  // (demo -> live, a different live URL, a different descent) it is all
  // cleared synchronously, the generation is bumped, and any async
  // response that started under the old generation is discarded — so
  // fixture data can never reappear under a LIVE banner (or vice versa).
  const connectionGenRef = useRef(0);
  const connectionIdentityRef = useRef<string | null>(null);

  const clearSourceSpecificState = useCallback(() => {
    setDescenders([]);
    setParties([]);
    setSelectedId(null);
    setProfile(null);
    setHistory([]);
    setSearchQuery('');
    setSearchResult(null);
    setFeed({ events: [], cursorTick: null, droppedCount: 0, truncatedCatchUps: 0, bufferedCount: 0 });
    setHighlights([]);
    setReplayAfter('');
    setReplayType('');
    setReplay([]);
  }, []);

  const refreshData = useCallback(async (gen: number = connectionGenRef.current) => {
    try {
      const [list, partyList, snapshot, hl] = await Promise.all([
        api().listDescenders(),
        api().listParties(),
        api().getFeed(),
        api().getHighlights(),
      ]);
      if (gen !== connectionGenRef.current) return; // stale: previous connection
      setDescenders(list);
      setParties(partyList);
      setFeed(snapshot);
      setHighlights(hl);
    } catch (err) {
      if (gen === connectionGenRef.current) setActionError(errText(err));
    }
  }, []);

  const applyStatus = useCallback((next: ConnectionStatus) => {
    const identity = next.mode && next.baseUrl ? `${next.mode}|${next.baseUrl}|${next.descentId ?? ''}` : null;
    if (next.state === 'disconnected') {
      connectionGenRef.current += 1;
      connectionIdentityRef.current = null;
      clearSourceSpecificState();
    } else if (identity !== null && connectionIdentityRef.current !== identity) {
      connectionGenRef.current += 1;
      connectionIdentityRef.current = identity;
      clearSourceSpecificState();
    }
    setStatus(next);
    if (next.state === 'connected') void refreshData(connectionGenRef.current);
  }, [clearSourceSpecificState, refreshData]);

  useEffect(() => {
    let alive = true;
    void (async () => {
      try {
        const [s, p] = await Promise.all([api().getStatus(), api().getPrefs()]);
        if (!alive) return;
        setPrefs(p);
        setBaseUrlInput(p.baseUrl);
        applyStatus(s);
      } catch (err) {
        if (alive) setActionError(errText(err));
      }
    })();
    const offStatus = api().onStatusChanged((s) => applyStatus(s));
    const offFeed = api().onFeedChanged((snapshot) => setFeed(snapshot));
    return () => {
      alive = false;
      offStatus();
      offFeed();
    };
  }, [applyStatus]);

  const run = async (fn: () => Promise<void>): Promise<void> => {
    setActionError(null);
    try {
      await fn();
    } catch (err) {
      setActionError(errText(err));
    }
  };

  const selectDescender = (id: string): void => {
    const gen = connectionGenRef.current;
    setSelectedId(id);
    void run(async () => {
      const [p, h] = await Promise.all([api().getProfile(id), api().getHistory(id)]);
      if (gen !== connectionGenRef.current) return; // stale: previous connection
      setProfile(p);
      setHistory(h);
    });
  };

  const toggleFollow = (id: string): void => {
    const gen = connectionGenRef.current;
    void run(async () => {
      const next = followed.has(id) ? await api().unfollow(id) : await api().follow(id);
      setPrefs(next);
      const hl = await api().getHighlights();
      if (gen !== connectionGenRef.current) return; // stale highlights
      setHighlights(hl);
    });
  };

  const doSearch = (): void => {
    const gen = connectionGenRef.current;
    const q = searchQuery.trim();
    if (!q) {
      setSearchResult(null);
      return;
    }
    void run(async () => {
      const result = await api().search(q);
      if (gen !== connectionGenRef.current) return; // stale: previous connection
      setSearchResult(result);
    });
  };

  const loadReplay = (): void => {
    const gen = connectionGenRef.current;
    void run(async () => {
      const after = replayAfter.trim() === '' ? null : Number(replayAfter);
      const events = await api().getReplay({
        afterTick: after !== null && Number.isFinite(after) ? after : null,
        eventType: replayType.trim() === '' ? null : replayType.trim(),
        limit: 100,
      });
      if (gen !== connectionGenRef.current) return; // stale: previous connection
      setReplay(events);
    });
  };

  const visibleFeed = useMemo(() => {
    const rows = [...feed.events].reverse();
    return followedOnly ? rows.filter((e) => e.actor_ids.some((id) => followed.has(id))) : rows;
  }, [feed.events, followedOnly, followed]);

  const partyName = (partyId: string | null): string => partyId ?? '—';

  return (
    <div className="app">
      <header className="topbar">
        <h1>Crawl Live Spectator</h1>
        <span className="readonly-badge">READ-ONLY</span>
        {status && (
          <span className="status-line">
            {status.state}
            {status.tick !== null ? ` · tick ${status.tick}` : ''}
            {status.descentId ? ` · ${status.descentId}` : ''}
          </span>
        )}
      </header>

      {status && <div className={`banner banner-${bannerKind(status)}`} role="status">{bannerText(status)}</div>}
      {actionError && <div className="banner banner-error" role="alert">{actionError}</div>}

      <section className="panel connection">
        <h2>Connection</h2>
        <label>
          Feed API base URL
          <input
            aria-label="Feed API base URL"
            value={baseUrlInput}
            onChange={(e) => setBaseUrlInput(e.target.value)}
            placeholder="http://127.0.0.1:8000"
          />
        </label>
        <div className="row">
          <button type="button" onClick={() => void run(async () => applyStatus(await api().connectLive(baseUrlInput)))}>
            Connect live
          </button>
          <button type="button" onClick={() => void run(async () => applyStatus(await api().connectDemo()))}>
            Start demo (fixture data)
          </button>
          <button type="button" onClick={() => void run(async () => applyStatus(await api().disconnect()))}>
            Disconnect
          </button>
        </div>
        {status && <p className="hint">{status.message}</p>}
      </section>

      <div className="grid">
        <section className="panel">
          <h2>Descenders</h2>
          <div className="row">
            <input
              aria-label="Search descenders and events"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search id, event, summary…"
            />
            <button type="button" onClick={doSearch} disabled={!connected}>Search</button>
          </div>
          {searchResult && (
            <p className="hint">
              Search “{searchResult.query}”: {searchResult.descenders.length} descender(s), {searchResult.events.length} event(s).
              <button type="button" className="link" onClick={() => setSearchResult(null)}>Clear</button>
            </p>
          )}
          <ul className="descender-list">
            {(searchResult ? searchResult.descenders : descenders).map((d) => (
              <li key={d.descender_id} className={d.descender_id === selectedId ? 'selected' : ''}>
                <button type="button" className="descender-main" onClick={() => selectDescender(d.descender_id)}>
                  <strong>{d.descender_id}</strong>
                  <span>{d.status} · Stratum {d.current_stratum} · {d.current_sector_id ?? 'unknown sector'} · HP {d.health}</span>
                </button>
                <button
                  type="button"
                  aria-label={`${followed.has(d.descender_id) ? 'Unfollow' : 'Follow'} ${d.descender_id}`}
                  className={followed.has(d.descender_id) ? 'follow active' : 'follow'}
                  onClick={() => toggleFollow(d.descender_id)}
                >
                  {followed.has(d.descender_id) ? '★' : '☆'}
                </button>
              </li>
            ))}
          </ul>
          {!connected && <p className="hint">Connect to list Descenders.</p>}

          <h3>Parties</h3>
          <ul className="party-list">
            {parties.map((p) => (
              <li key={p.id}>
                <strong>{p.id}</strong> — leader {p.leader_descender_id ?? '—'}; members {p.member_descender_ids.join(', ')};
                cohesion {p.cohesion}; loot {p.loot_policy}
              </li>
            ))}
          </ul>
        </section>

        <section className="panel">
          <h2>Profile</h2>
          {!profile && <p className="hint">Select a Descender to inspect authentic state and history.</p>}
          {profile && (
            <div className="profile">
              <h3>{profile.descender_id}</h3>
              <dl>
                <dt>Status</dt><dd>{profile.status}</dd>
                <dt>Stratum / sector</dt><dd>{profile.current_stratum} / {profile.current_sector_id ?? '—'}</dd>
                <dt>Health</dt><dd>{profile.health}</dd>
                <dt>Level / XP</dt><dd>{profile.level} / {profile.experience}</dd>
                <dt>Specialization</dt><dd>{profile.specialization ?? '—'}</dd>
                <dt>Party</dt><dd>{partyName(profile.current_party_id)}</dd>
                <dt>Objective</dt><dd>{profile.current_objective ?? '—'}</dd>
                <dt>Kills / encounters survived</dt><dd>{profile.kills} / {profile.encounters_survived}</dd>
                <dt>Abilities</dt><dd>{profile.abilities.join(', ') || '—'}</dd>
              </dl>
              <h4>Relationships</h4>
              {(profile.relationships ?? []).length === 0 && <p className="hint">No recorded relationships.</p>}
              <ul>
                {(profile.relationships ?? []).map((r) => (
                  <li key={r.target_id}>
                    {r.target_id} — trust {r.trust}, respect {r.respect}, rivalry {r.rivalry}, familiarity {r.familiarity}
                  </li>
                ))}
              </ul>
              <h4>History</h4>
              <ul className="event-list">
                {history.map((e) => (
                  <li key={e.id}><span className="tick">t{e.tick}</span> <strong>{e.event_type}</strong> — {e.summary}</li>
                ))}
              </ul>
            </div>
          )}
        </section>

        <section className="panel">
          <h2>Live Ledger</h2>
          <label className="row">
            <input type="checkbox" checked={followedOnly} onChange={(e) => setFollowedOnly(e.target.checked)} />
            Followed Descenders only
          </label>
          <p className="hint">
            Buffered {feed.bufferedCount} event(s), cursor tick {feed.cursorTick ?? '—'}
            {feed.droppedCount > 0 ? `, ${feed.droppedCount} older event(s) dropped by the bounded buffer` : ''}
            {feed.truncatedCatchUps > 0 ? `, ${feed.truncatedCatchUps} catch-up window(s) hit the retrieval limit — some events may have been missed` : ''}.
          </p>
          <ul className="event-list feed">
            {visibleFeed.map((e) => (
              <li key={e.id} className={isHighlight(e, followed) ? 'highlight' : ''}>
                <span className="tick">t{e.tick}</span> <strong>{e.event_type}</strong> — {e.summary}
                <span className="actors"> [{e.actor_ids.join(', ')}]</span>
              </li>
            ))}
          </ul>

          <h3>Highlights — followed Descenders</h3>
          {followed.size === 0 && <p className="hint">Follow a Descender (☆) to collect their notable events here.</p>}
          <ul className="event-list">
            {highlights.map((e) => (
              <li key={e.id} className="highlight"><span className="tick">t{e.tick}</span> <strong>{e.event_type}</strong> — {e.summary}</li>
            ))}
          </ul>

          <h3>Replay browser</h3>
          <div className="row">
            <input aria-label="Replay after tick" value={replayAfter} onChange={(e) => setReplayAfter(e.target.value)} placeholder="After tick (optional)" />
            <input aria-label="Replay event type" value={replayType} onChange={(e) => setReplayType(e.target.value)} placeholder="Event type (optional)" />
            <button type="button" onClick={loadReplay} disabled={!connected}>Load replay</button>
          </div>
          <ul className="event-list">
            {replay.map((e) => (
              <li key={e.id}><span className="tick">t{e.tick}</span> <strong>{e.event_type}</strong> — {e.summary}</li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}
