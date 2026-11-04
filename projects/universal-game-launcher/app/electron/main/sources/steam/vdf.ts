/**
 * Valve KeyValues (VDF) parser.
 *
 * Pure logic — no Node/Electron APIs — so it is fully unit-testable.
 * Handles the subset Steam actually writes: quoted strings with \" and \\
 * escapes, bare tokens, nested { } blocks, and // line comments.
 *
 * Never throws on hostile input: oversized input, excessive nesting and
 * truncated structures all produce typed errors instead of exceptions.
 */

export type VdfValue = string | { [key: string]: VdfValue };

export type VdfErrorCode =
  | 'INPUT_TOO_LARGE'
  | 'TRUNCATED'
  | 'UNEXPECTED_TOKEN'
  | 'DEPTH_EXCEEDED';

export interface VdfParseError {
  code: VdfErrorCode;
  message: string;
  /** Character offset where the problem was detected. */
  position: number;
}

export type VdfResult = { ok: true; value: VdfValue } | { ok: false; error: VdfParseError };

const MAX_INPUT_BYTES = 8 * 1024 * 1024;
const MAX_DEPTH = 100;

type Token =
  | { kind: 'string'; value: string }
  | { kind: 'open' }
  | { kind: 'close' };

function fail(code: VdfErrorCode, message: string, position: number): VdfResult {
  return { ok: false, error: { code, message, position } };
}

function tokenize(text: string): VdfResult & { tokens?: Token[] } {
  const tokens: Token[] = [];
  let i = 0;
  const n = text.length;
  while (i < n) {
    const ch = text[i]!;
    // Whitespace
    if (ch === ' ' || ch === '\t' || ch === '\r' || ch === '\n') {
      i++;
      continue;
    }
    // // line comments
    if (ch === '/' && text[i + 1] === '/') {
      while (i < n && text[i] !== '\n') i++;
      continue;
    }
    if (ch === '{') {
      tokens.push({ kind: 'open' });
      i++;
      continue;
    }
    if (ch === '}') {
      tokens.push({ kind: 'close' });
      i++;
      continue;
    }
    if (ch === '"') {
      let value = '';
      i++; // opening quote
      let closed = false;
      while (i < n) {
        const c = text[i]!;
        if (c === '\\' && i + 1 < n) {
          const esc = text[i + 1]!;
          if (esc === '"' || esc === '\\') value += esc;
          else if (esc === 'n') value += '\n';
          else if (esc === 't') value += '\t';
          else if (esc === 'r') value += '\r';
          else value += '\\' + esc; // unknown escape: keep both chars verbatim
          i += 2;
          continue;
        }
        if (c === '"') {
          closed = true;
          i++;
          break;
        }
        value += c;
        i++;
      }
      if (!closed) return fail('TRUNCATED', 'Unterminated quoted string.', i);
      tokens.push({ kind: 'string', value });
      continue;
    }
    // Bare token: runs until whitespace or a brace.
    let value = '';
    while (i < n) {
      const c = text[i]!;
      if (c === ' ' || c === '\t' || c === '\r' || c === '\n' || c === '{' || c === '}') break;
      value += c;
      i++;
    }
    if (value.length > 0) tokens.push({ kind: 'string', value });
  }
  return { ok: true, value: {}, tokens };
}

/**
 * Parse VDF text into a nested object. Duplicate keys: last value wins.
 * A document is a sequence of key/value or key/block pairs merged into one object.
 */
export function parseVdf(text: string): VdfResult {
  if (typeof text !== 'string') {
    return fail('UNEXPECTED_TOKEN', 'VDF input must be a string.', 0);
  }
  if (text.length === 0) {
    return fail('TRUNCATED', 'VDF input is empty.', 0);
  }
  if (text.length > MAX_INPUT_BYTES) {
    return fail('INPUT_TOO_LARGE', `VDF input exceeds ${MAX_INPUT_BYTES} bytes.`, 0);
  }
  const lexed = tokenize(text);
  if (!lexed.ok || !lexed.tokens) return lexed;
  const tokens = lexed.tokens;

  let pos = 0;
  function parseBlock(depth: number): VdfResult & { node?: { [k: string]: VdfValue } } {
    if (depth > MAX_DEPTH) return fail('DEPTH_EXCEEDED', 'VDF nesting exceeds 100 levels.', pos);
    const node: { [k: string]: VdfValue } = {};
    for (;;) {
      const t = tokens[pos];
      if (!t) return fail('TRUNCATED', 'Unexpected end of input inside a block.', pos);
      if (t.kind === 'close') {
        pos++;
        return { ok: true, value: node, node };
      }
      if (t.kind !== 'string') {
        return fail('UNEXPECTED_TOKEN', `Expected a key but found "${t.kind}".`, pos);
      }
      const key = t.value;
      pos++;
      const next = tokens[pos];
      if (!next) return fail('TRUNCATED', `Key "${key}" has no value.`, pos);
      if (next.kind === 'open') {
        pos++;
        const child = parseBlock(depth + 1);
        if (!child.ok || !child.node) return child;
        node[key] = child.node;
      } else if (next.kind === 'string') {
        node[key] = next.value;
        pos++;
      } else {
        return fail('UNEXPECTED_TOKEN', `Key "${key}" is followed by an unexpected "}".`, pos);
      }
    }
  }

  const root: { [k: string]: VdfValue } = {};
  while (pos < tokens.length) {
    const t = tokens[pos]!;
    if (t.kind === 'close') {
      return fail('UNEXPECTED_TOKEN', 'Stray closing brace at document top level.', pos);
    }
    if (t.kind !== 'string') {
      return fail('UNEXPECTED_TOKEN', 'Expected a key at document top level.', pos);
    }
    const key = t.value;
    pos++;
    const next = tokens[pos];
    if (!next) return fail('TRUNCATED', `Key "${key}" has no value.`, pos);
    if (next.kind === 'open') {
      pos++;
      const child = parseBlock(1);
      if (!child.ok || !child.node) return child;
      root[key] = child.node;
    } else if (next.kind === 'string') {
      root[key] = next.value;
      pos++;
    } else {
      return fail('UNEXPECTED_TOKEN', `Key "${key}" is followed by an unexpected "}".`, pos);
    }
  }
  return { ok: true, value: root };
}

function findRootKey(value: VdfValue, name: string): { [k: string]: VdfValue } | null {
  if (typeof value !== 'object' || value === null) return null;
  for (const key of Object.keys(value)) {
    if (key.toLowerCase() === name) {
      const v = (value as { [k: string]: VdfValue })[key];
      if (typeof v === 'object' && v !== null) return v as { [k: string]: VdfValue };
      return null;
    }
  }
  return null;
}

export interface LibraryFoldersResult {
  /** Absolute library folder paths, deduplicated, in numeric order. */
  folders: string[];
  warnings: string[];
}

/**
 * Interpret a parsed libraryfolders.vdf. Handles both the modern nested form
 * (each entry an object with a "path" key) and the legacy flat form
 * (each entry a path string directly).
 */
export function parseLibraryFolders(value: VdfValue): LibraryFoldersResult {
  const warnings: string[] = [];
  const root = findRootKey(value, 'libraryfolders');
  if (!root) {
    return { folders: [], warnings: ['No "libraryfolders" section found.'] };
  }
  const entries: Array<{ order: number; path: string }> = [];
  for (const key of Object.keys(root)) {
    const entry = root[key]!;
    const order = /^\d+$/.test(key) ? parseInt(key, 10) : Number.MAX_SAFE_INTEGER;
    if (typeof entry === 'string') {
      // Legacy flat form: "1" "D:\SteamLibrary"
      if (entry.trim()) entries.push({ order, path: entry });
      continue;
    }
    if (typeof entry === 'object' && entry !== null) {
      const p = (entry as { [k: string]: VdfValue })['path'];
      if (typeof p === 'string' && p.trim()) {
        entries.push({ order, path: p });
      } else {
        warnings.push(`Library entry "${key}" has no usable "path"; skipped.`);
      }
      continue;
    }
  }
  entries.sort((a, b) => a.order - b.order);
  const seen = new Set<string>();
  const folders: string[] = [];
  for (const e of entries) {
    const normalized = e.path.replace(/\\/g, '/').toLowerCase();
    if (!seen.has(normalized)) {
      seen.add(normalized);
      folders.push(e.path);
    }
  }
  return { folders, warnings };
}

export interface AppManifest {
  appid: string;
  name: string;
  installdir: string;
}

export type ManifestResult =
  | { ok: true; manifest: AppManifest; warnings: string[] }
  | { ok: false; error: string };

/**
 * Interpret a parsed appmanifest_<appid>.acf. fileAppId comes from the file
 * name (the install identity); the inner "appid" is cross-checked.
 */
export function parseAppManifest(value: VdfValue, fileAppId: string): ManifestResult {
  const root = findRootKey(value, 'appstate');
  if (!root) return { ok: false, error: 'No "AppState" section found.' };
  const warnings: string[] = [];
  const str = (k: string): string | null => {
    const v = root[k];
    return typeof v === 'string' ? v : null;
  };
  const innerAppId = str('appid');
  if (innerAppId && innerAppId !== fileAppId) {
    warnings.push(
      `Inner appid "${innerAppId}" differs from file appid "${fileAppId}"; using the file appid.`,
    );
  }
  const name = str('name');
  if (!name || !name.trim()) return { ok: false, error: 'Manifest has no usable "name".' };
  const installdir = str('installdir');
  if (!installdir || !installdir.trim()) {
    return { ok: false, error: `Manifest for "${name}" has no usable "installdir".` };
  }
  if (/^(?:[a-zA-Z]:[\\/]|\\\\|[\\/])/.test(installdir) || installdir.split(/[\\/]/).includes('..')) {
    return {
      ok: false,
      error: `"installdir" "${installdir}" is absolute or escapes its folder; rejected as unsafe.`,
    };
  }
  return { ok: true, manifest: { appid: fileAppId, name: name.trim(), installdir: installdir.trim() }, warnings };
}
