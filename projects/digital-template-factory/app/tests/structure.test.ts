/**
 * Structure validator tests: required markers, balance, script rejection.
 */
import { describe, expect, it } from 'vitest';
import { validateStructure } from '../electron/main/validators/structure';

const VALID = `<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>T</title></head>
<body><main><p>hi</p><br><img src="x"></main></body>
</html>`;

describe('validateStructure', () => {
  it('accepts well-formed output', () => {
    expect(validateStructure(VALID)).toEqual({ ok: true });
  });

  it('rejects a missing <main>', () => {
    const result = validateStructure(
      '<html><head></head><body><p>no main</p></body></html>',
    );
    expect(result.ok).toBe(false);
    expect(result.reason).toBe('missing-main');
  });

  it('rejects a missing <head>', () => {
    const result = validateStructure('<html><body><main></main></body></html>');
    expect(result.ok).toBe(false);
    expect(result.reason).toBe('missing-head');
  });

  it('rejects unbalanced tags', () => {
    const result = validateStructure(
      '<html><head></head><body><main><div><p></div></main></body></html>',
    );
    expect(result.ok).toBe(false);
    expect(result.reason).toMatch(/^mismatched-close/);
  });

  it('rejects unclosed tags', () => {
    const result = validateStructure(
      '<html><head></head><body><main><div></main></body></html>',
    );
    expect(result.ok).toBe(false);
    expect(result.reason).toMatch(/^mismatched-close|^unclosed/);
  });

  it('rejects stray closing tags', () => {
    const result = validateStructure(
      '<html><head></head><body><main></main></body></html></div>',
    );
    expect(result.ok).toBe(false);
    expect(result.reason).toMatch(/^stray-closing/);
  });

  it('forbids script tags anywhere in the output', () => {
    const result = validateStructure(
      '<html><head></head><body><main><script>alert(1)</' + 'script></main></body></html>',
    );
    expect(result.ok).toBe(false);
    expect(result.reason).toBe('script-tag-forbidden');
  });

  it('ignores void and self-closing elements', () => {
    const html =
      '<html><head><meta charset="utf-8"/><link rel="x"/></head>' +
      '<body><main><hr/><br></main></body></html>';
    expect(validateStructure(html)).toEqual({ ok: true });
  });
});
