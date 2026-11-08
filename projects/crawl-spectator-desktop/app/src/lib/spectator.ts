// Small renderer helpers for status/mode presentation.

import type { ConnectionStatus } from '../../shared/types';

export type BannerKind = 'live' | 'demo' | 'error' | 'off';

export function bannerKind(status: ConnectionStatus): BannerKind {
  if (status.state === 'error') return 'error';
  if (status.mode === 'demo' && status.state !== 'disconnected') return 'demo';
  if (status.mode === 'live' && status.state === 'connected') return 'live';
  return 'off';
}

export function bannerText(status: ConnectionStatus): string {
  const kind = bannerKind(status);
  if (kind === 'demo') return 'DEMO MODE — invented fixture data. This is NOT a live Underreach.';
  if (kind === 'live') return `LIVE — connected to the real Feed API at ${status.baseUrl}.`;
  if (kind === 'error') return `Connection problem: ${status.message}`;
  if (status.state === 'connecting') return 'Connecting…';
  return 'Not connected. Connect to a live Feed API, or start demo mode to explore with fixture data.';
}
