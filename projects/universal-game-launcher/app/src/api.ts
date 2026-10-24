import type { ApiError, ApiResult, GameLauncherApi } from '../shared/types';

export class ApiCallError extends Error {
  readonly code: string;
  constructor(error: ApiError) {
    super(error.message);
    this.name = 'ApiCallError';
    this.code = error.code;
  }
}

export function getApi(): GameLauncherApi {
  const api = (window as unknown as { gameLauncher?: GameLauncherApi }).gameLauncher;
  if (!api) {
    throw new Error('Native bridge unavailable. This UI must run inside the Electron app.');
  }
  return api;
}

/** Unwrap an ApiResult or throw ApiCallError carrying the machine-readable code. */
export async function unwrap<T>(promise: Promise<ApiResult<T>>): Promise<T> {
  const result = await promise;
  if (!result.ok) throw new ApiCallError(result.error);
  return result.data;
}

export function formatDuration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return '—';
  if (ms < 1000) return '<1 sec';
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s} sec`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  const rest = m % 60;
  return rest === 0 ? `${h} hr` : `${h} hr ${rest} min`;
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString();
}

export function basenameOf(p: string): string {
  const parts = p.split(/[\\/]/);
  return parts[parts.length - 1] ?? p;
}

export function dirnameOf(p: string): string {
  const parts = p.split(/[\\/]/);
  parts.pop();
  return parts.join('/') || p;
}
