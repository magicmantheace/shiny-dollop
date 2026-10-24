// App-level types + the renderer-facing API surface (window.spectator).
// Wire payload types live in ./contract.ts; this file defines connection
// state, local preferences and IPC shapes owned by this app.

import type { DescentSummary, Descender, LedgerEvent, Party, SearchResult, FeedHealth } from './contract.js';

export type { DescentSummary, Descender, LedgerEvent, Party, SearchResult, FeedHealth };

export type ConnectionMode = 'live' | 'demo';
export type ConnectionState = 'disconnected' | 'connecting' | 'connected' | 'error';

export interface ConnectionStatus {
  state: ConnectionState;
  /** null when disconnected before any connection was made. */
  mode: ConnectionMode | null;
  /** Base URL for live mode; 'demo://fixture' for demo mode. */
  baseUrl: string | null;
  /** Human-readable, actionable status detail. */
  message: string;
  descentId: string | null;
  /** Latest known simulation tick (from health / ledger). */
  tick: number | null;
  /** Consecutive failed reconnect attempts in the current error streak. */
  reconnectAttempts: number;
}

export interface FeedSnapshot {
  events: LedgerEvent[];
  /** Highest tick currently buffered (the replay cursor), null when empty. */
  cursorTick: number | null;
  /** Events dropped by the bounded buffer since connect (backpressure). */
  droppedCount: number;
  bufferedCount: number;
}

export interface ReplayQuery {
  afterTick?: number | null;
  limit?: number;
  eventType?: string | null;
}

export interface Prefs {
  baseUrl: string;
  followedDescenderIds: string[];
}

export const PREFS_FORMAT_VERSION = '1.0.0';

export interface PrefsEnvelope {
  formatVersion: string;
  prefs: Prefs;
}

/** IPC channel names. The preload writes these as literals on purpose
 *  (sandboxed preloads cannot load shared modules at runtime); a backend
 *  test asserts the preload literals match this table exactly. */
export const SPECTATOR_IPC_CHANNELS = {
  getStatus: 'spectator:get-status',
  connectLive: 'spectator:connect-live',
  connectDemo: 'spectator:connect-demo',
  disconnect: 'spectator:disconnect',
  getDescent: 'spectator:get-descent',
  listDescenders: 'spectator:list-descenders',
  getProfile: 'spectator:get-profile',
  getHistory: 'spectator:get-history',
  search: 'spectator:search',
  listParties: 'spectator:list-parties',
  getFeed: 'spectator:get-feed',
  getReplay: 'spectator:get-replay',
  getHighlights: 'spectator:get-highlights',
  getPrefs: 'spectator:get-prefs',
  follow: 'spectator:follow',
  unfollow: 'spectator:unfollow',
  exportPrefs: 'spectator:export-prefs',
  importPrefs: 'spectator:import-prefs',
  statusChanged: 'spectator:status-changed',
  feedChanged: 'spectator:feed-changed',
} as const;

export interface SpectatorApi {
  getStatus(): Promise<ConnectionStatus>;
  connectLive(baseUrl: string): Promise<ConnectionStatus>;
  connectDemo(): Promise<ConnectionStatus>;
  disconnect(): Promise<ConnectionStatus>;
  getDescent(): Promise<DescentSummary | null>;
  listDescenders(): Promise<Descender[]>;
  getProfile(descenderId: string): Promise<Descender>;
  getHistory(descenderId: string, limit?: number): Promise<LedgerEvent[]>;
  search(query: string): Promise<SearchResult>;
  listParties(): Promise<Party[]>;
  getFeed(): Promise<FeedSnapshot>;
  getReplay(query: ReplayQuery): Promise<LedgerEvent[]>;
  getHighlights(): Promise<LedgerEvent[]>;
  getPrefs(): Promise<Prefs>;
  follow(descenderId: string): Promise<Prefs>;
  unfollow(descenderId: string): Promise<Prefs>;
  exportPrefs(): Promise<PrefsEnvelope>;
  importPrefs(envelope: unknown): Promise<Prefs>;
  /** Subscribe to connection-status pushes; returns an unsubscribe fn. */
  onStatusChanged(listener: (status: ConnectionStatus) => void): () => void;
  /** Subscribe to live-feed pushes; returns an unsubscribe fn. */
  onFeedChanged(listener: (snapshot: FeedSnapshot) => void): () => void;
}
