import { afterEach, describe, expect, it } from 'vitest';
import { loadRecentDocs, upsertRecentDoc } from './recentDocs';

afterEach(() => {
  localStorage.clear();
});

describe('recentDocs index', () => {
  it('keeps every document beyond the old 50-entry cap', () => {
    for (let i = 1; i <= 51; i++) {
      upsertRecentDoc({
        id: `doc-${i}`,
        templateId: 'simple-invoice',
        templateName: 'Simple Invoice',
        updatedAt: `2026-10-23T15:${String(i).padStart(2, '0')}:00.000Z`,
      });
    }
    const docs = loadRecentDocs();
    expect(docs).toHaveLength(51);
    // The oldest document must still be reachable, not silently evicted.
    expect(docs.map((d) => d.id)).toContain('doc-1');
    expect(docs.map((d) => d.id)).toContain('doc-51');
  });
});
