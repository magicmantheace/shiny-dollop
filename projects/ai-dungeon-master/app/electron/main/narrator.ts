// Narration adapters — FLAVOR ONLY.
//
// A narrator receives a read-only description of an already-decided log
// event and returns prose. It has no access to the database, the dice
// stream, or any service method, so there is no path by which narration
// can change a rules outcome. The service attaches the returned text to
// the log entry's narration field and nothing else.
//
// Default: MockNarrator (deterministic, offline, no network).
// Optional: HttpNarrator posts to a user-configured LOOPBACK endpoint
// (Ollama-style /api/generate). Any failure falls back to the mock text
// with source 'mock-fallback' — a missing model is never a hard error.

import { AIDM_ERROR_CODES, aidmError } from '../../shared/errors.js';
import type { LogEntry, NarrationSettings } from '../../shared/types.js';

export interface NarrationContext {
  campaignName: string;
  entry: LogEntry;
}

export interface Narrator {
  readonly source: 'mock' | 'local';
  narrate(context: NarrationContext): Promise<string>;
}

const MOCK_LINES: Record<string, string[]> = {
  roll: [
    'The dice clatter across the scarred oak table and settle into silence.',
    'A held breath, a rattle of bone-white dice, and fate shows its hand.',
  ],
  check: [
    'Every eye turns toward the attempt as the moment stretches thin.',
    'The outcome hangs for a heartbeat before it lands.',
  ],
  damage: [
    'A cry goes up as the blow finds its mark.',
    'Steel bites; the fight turns uglier by the second.',
  ],
  heal: [
    'A steady hand and a muttered word knit the worst of the wound closed.',
    'Color returns, slowly, like dawn through a shuttered window.',
  ],
  encounter: [
    'Weapons come free of their sheaths. There will be no more talking.',
    'The room shrinks to the space between heartbeats.',
  ],
  note: ['The chronicler scratches it down before the moment fades.'],
  import: ['New pages are pressed into the campaign chronicle.'],
  system: ['The chronicle turns a page.'],
  narration: ['The tale is told again, softer this time.'],
};

export class MockNarrator implements Narrator {
  readonly source = 'mock' as const;

  async narrate(context: NarrationContext): Promise<string> {
    const lines = MOCK_LINES[context.entry.kind] ?? MOCK_LINES.system ?? ['The tale goes on.'];
    // Deterministic pick from the entry's sequence number.
    const line = lines[context.entry.seq % lines.length] ?? lines[0] ?? '';
    return `${line} (${context.entry.text})`;
  }
}

/** True when a URL points at this machine only (the no-cloud guarantee). */
export function isLoopbackUrl(raw: string): boolean {
  let url: URL;
  try {
    url = new URL(raw);
  } catch {
    return false;
  }
  if (url.protocol !== 'http:' && url.protocol !== 'https:') return false;
  const host = url.hostname.toLowerCase();
  // Only actual loopback hosts. A "*.local" name is NOT loopback: mDNS
  // names resolve to any machine on the LAN, so accepting that suffix
  // would let narration traffic (and the log text it carries) go to
  // another computer, breaking the no-cloud / this-machine-only rule.
  return host === 'localhost' || host === '127.0.0.1' || host === '::1' || host === '[::1]';
}

export class HttpNarrator implements Narrator {
  readonly source = 'local' as const;
  private readonly endpoint: string;
  private readonly model: string;
  private readonly timeoutMs: number;

  constructor(settings: NarrationSettings, timeoutMs = 15_000) {
    if (!isLoopbackUrl(settings.endpoint)) {
      throw aidmError(
        AIDM_ERROR_CODES.INPUT_INVALID,
        'Narration endpoint must be a loopback URL (localhost / 127.0.0.1). Cloud endpoints are not supported.',
      );
    }
    this.endpoint = settings.endpoint.replace(/\/+$/, '');
    this.model = settings.model;
    this.timeoutMs = timeoutMs;
  }

  async narrate(context: NarrationContext): Promise<string> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const res = await fetch(`${this.endpoint}/api/generate`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        signal: controller.signal,
        // NEVER follow redirects: the configured endpoint was validated
        // as loopback, but a 307/308 redirect could forward the POST
        // body (which contains session event text) to a non-loopback
        // destination, silently breaking the loopback-only guarantee.
        // With `redirect: 'manual'` a redirect surfaces as a response
        // here and is rejected below without sending data anywhere else.
        redirect: 'manual',
        body: JSON.stringify({
          model: this.model,
          stream: false,
          prompt:
            `Write one or two sentences of atmospheric tabletop narration for this event. ` +
            `Do not invent dice results or change any outcome.\nEvent: ${context.entry.text}`,
        }),
      });
      if (res.status >= 300 && res.status < 400) {
        throw aidmError(
          AIDM_ERROR_CODES.NARRATION_UNAVAILABLE,
          `Narration endpoint attempted a redirect (${res.status}); redirects are not followed from the loopback narration endpoint.`,
        );
      }
      if (!res.ok) {
        throw aidmError(
          AIDM_ERROR_CODES.NARRATION_UNAVAILABLE,
          `Narration endpoint answered ${res.status}.`,
        );
      }
      const body = (await res.json()) as { response?: unknown };
      if (typeof body.response !== 'string' || body.response.trim().length === 0) {
        throw aidmError(
          AIDM_ERROR_CODES.NARRATION_UNAVAILABLE,
          'Narration endpoint returned no text.',
        );
      }
      return body.response.trim();
    } catch (err) {
      if ((err as { name?: string }).name === 'AbortError') {
        throw aidmError(
          AIDM_ERROR_CODES.NARRATION_UNAVAILABLE,
          `Narration endpoint timed out after ${this.timeoutMs}ms.`,
        );
      }
      throw err;
    } finally {
      clearTimeout(timer);
    }
  }
}

export function createNarrator(settings: NarrationSettings): Narrator {
  if (settings.narrator === 'local') return new HttpNarrator(settings);
  return new MockNarrator();
}
