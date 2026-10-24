/** Unit tests for the Valve KeyValues (VDF) parser. */
import { describe, expect, it } from 'vitest';
import {
  parseAppManifest,
  parseLibraryFolders,
  parseVdf,
  type VdfValue,
} from '../../electron/main/sources/steam/vdf';

function okValue(text: string): VdfValue {
  const r = parseVdf(text);
  if (!r.ok) throw new Error(`Expected parse success, got ${r.error.code}: ${r.error.message}`);
  return r.value;
}

describe('parseVdf', () => {
  it('parses nested blocks', () => {
    const v = okValue(`"root"\n{\n\t"a"\t"1"\n\t"child"\n\t{\n\t\t"b"\t"2"\n\t}\n}`);
    expect(v).toEqual({ root: { a: '1', child: { b: '2' } } });
  });

  it('handles escaped backslashes and quotes', () => {
    const v = okValue(`"k" "C:\\\\Games\\\\Steam"\n"q" "say \\"hi\\""`);
    expect(v).toEqual({ k: 'C:\\Games\\Steam', q: 'say "hi"' });
  });

  it('skips // line comments', () => {
    const v = okValue(`// a comment\n"k" "v" // trailing\n`);
    expect(v).toEqual({ k: 'v' });
  });

  it('accepts bare tokens', () => {
    const v = okValue(`key value`);
    expect(v).toEqual({ key: 'value' });
  });

  it('last duplicate key wins', () => {
    const v = okValue(`"a" "1"\n"a" "2"`);
    expect(v).toEqual({ a: '2' });
  });

  it('keeps unicode paths intact', () => {
    const v = okValue(`"path" "D:\\\\Jeux\\\\Café"`);
    expect(v).toEqual({ path: 'D:\\Jeux\\Café' });
  });

  it('fails on empty input', () => {
    const r = parseVdf('');
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.error.code).toBe('TRUNCATED');
  });

  it('fails on unbalanced braces', () => {
    const r = parseVdf(`"a"\n{\n"b" "c"`);
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.error.code).toBe('TRUNCATED');
  });

  it('fails on unterminated strings', () => {
    const r = parseVdf(`"a" "oops`);
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.error.code).toBe('TRUNCATED');
  });

  it('fails on stray closing brace', () => {
    const r = parseVdf(`"a" "b"\n}`);
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.error.code).toBe('UNEXPECTED_TOKEN');
  });

  it('fails on garbage', () => {
    const r = parseVdf(`{{{}}}`);
    expect(r.ok).toBe(false);
  });

  it('rejects excessive nesting', () => {
    let text = '';
    for (let i = 0; i < 120; i++) text += `"k${i}"\n{\n`;
    const r = parseVdf(text);
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.error.code).toBe('DEPTH_EXCEEDED');
  });

  it('rejects oversized input', () => {
    const r = parseVdf('x'.repeat(9 * 1024 * 1024));
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.error.code).toBe('INPUT_TOO_LARGE');
  });
});

describe('parseLibraryFolders', () => {
  it('reads the modern nested form in numeric order', () => {
    const v = okValue(`"libraryfolders"
{
\t"0"
\t{
\t\t"path"\t\t"C:\\\\Program Files (x86)\\\\Steam"
\t\t"label"\t\t""
\t}
\t"1"
\t{
\t\t"path"\t\t"D:\\\\SteamLibrary"
\t}
}`);
    const r = parseLibraryFolders(v);
    expect(r.folders).toEqual(['C:\\Program Files (x86)\\Steam', 'D:\\SteamLibrary']);
  });

  it('reads the legacy flat form', () => {
    const v = okValue(`"LibraryFolders"\n{\n\t"1"\t\t"D:\\\\Games"\n}`);
    const r = parseLibraryFolders(v);
    expect(r.folders).toEqual(['D:\\Games']);
  });

  it('deduplicates case-insensitively and warns on pathless entries', () => {
    const v = okValue(`"libraryfolders"\n{\n\t"0"\n\t{\n\t\t"path"\t\t"D:\\\\Lib"\n\t}\n\t"1"\n\t{\n\t\t"path"\t\t"d:\\\\lib"\n\t}\n\t"2"\n\t{\n\t\t"label"\t\t"no path here"\n\t}\n}`);
    const r = parseLibraryFolders(v);
    expect(r.folders).toEqual(['D:\\Lib']);
    expect(r.warnings.length).toBeGreaterThan(0);
  });

  it('reports a missing section', () => {
    const r = parseLibraryFolders(okValue(`"other" { "a" "b" }`));
    expect(r.folders).toEqual([]);
    expect(r.warnings.length).toBeGreaterThan(0);
  });
});

describe('parseAppManifest', () => {
  it('extracts appid, name and installdir', () => {
    const v = okValue(`"AppState"\n{\n\t"appid"\t\t"730"\n\t"name"\t\t"Counter-Strike 2"\n\t"installdir"\t\t"Counter-Strike Global Offensive"\n}`);
    const r = parseAppManifest(v, '730');
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.manifest).toEqual({ appid: '730', name: 'Counter-Strike 2', installdir: 'Counter-Strike Global Offensive' });
  });

  it('warns when the inner appid differs from the file appid', () => {
    const v = okValue(`"AppState"\n{\n\t"appid"\t\t"731"\n\t"name"\t\t"X"\n\t"installdir"\t\t"X"\n}`);
    const r = parseAppManifest(v, '730');
    expect(r.ok).toBe(true);
    if (r.ok) {
      expect(r.manifest.appid).toBe('730');
      expect(r.warnings.join(' ')).toContain('731');
    }
  });

  it('rejects manifests without a name or installdir', () => {
    expect(parseAppManifest(okValue(`"AppState" { "appid" "1" }`), '1').ok).toBe(false);
    expect(parseAppManifest(okValue(`"AppState" { "appid" "1" "name" "X" }`), '1').ok).toBe(false);
  });

  it('rejects absolute or escaping installdir values', () => {
    const abs = okValue(`"AppState" { "appid" "1" "name" "X" "installdir" "C:\\\\evil" }`);
    expect(parseAppManifest(abs, '1').ok).toBe(false);
    const trav = okValue(`"AppState" { "appid" "1" "name" "X" "installdir" "..\\\\evil" }`);
    expect(parseAppManifest(trav, '1').ok).toBe(false);
  });

  it('rejects a missing AppState section', () => {
    const r = parseAppManifest(okValue(`"Nope" { "a" "b" }`), '1');
    expect(r.ok).toBe(false);
  });
});
