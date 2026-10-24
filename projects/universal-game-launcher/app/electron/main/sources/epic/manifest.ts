/**
 * Parser for Epic Games Launcher `.item` manifests.
 *
 * These are JSON files, but we treat them as hostile input: only a small
 * whitelist of fields is read, every field is type- and shape-validated,
 * and install locations are rejected when they escape (traversal) or are
 * otherwise unsafe. Manifest contents are data, never commands.
 */

export type ManifestErrorCode =
  | 'INVALID_JSON'
  | 'INVALID_SHAPE'
  | 'INVALID_FIELD';

export interface ManifestError {
  code: ManifestErrorCode;
  detail: string;
}

export interface EpicManifest {
  /** Human display name, e.g. "Fortnite". */
  displayName: string;
  /** Epic AppName id string, e.g. "Fortnite". Used as the stable external id. */
  appName: string;
  /** Absolute install location as written in the manifest. */
  installLocation: string;
  /** Catalog namespace, when present. */
  catalogNamespace: string | null;
}

export type ManifestResult =
  | { ok: true; manifest: EpicManifest; warnings: string[] }
  | { ok: false; error: ManifestError };

const MAX_DISPLAY_NAME = 256;
const MAX_FIELD_LEN = 1024;
/** Conservative id shape: letters, digits and a few separators. */
const APP_NAME_RE = /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$/;

function isPlainObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}

function isAbsoluteLike(platform: NodeJS.Platform, p: string): boolean {
  if (platform === 'win32') {
    return /^[A-Za-z]:[\\/]/.test(p) || p.startsWith('\\\\');
  }
  return p.startsWith('/');
}

/**
 * Reject locations that escape via `..` segments. The manifest path is
 * absolute by contract; any surviving `..` after normalization means the
 * author wrote an escaping path, and we refuse it rather than resolve it.
 */
function hasTraversal(p: string): boolean {
  const segs = p.split(/[\\/]+/);
  return segs.includes('..');
}

export function parseEpicManifest(
  text: string,
  platform: NodeJS.Platform,
): ManifestResult {
  let raw: unknown;
  try {
    raw = JSON.parse(text);
  } catch (err) {
    return {
      ok: false,
      error: { code: 'INVALID_JSON', detail: `Not valid JSON: ${(err as Error).message}` },
    };
  }
  if (!isPlainObject(raw)) {
    return {
      ok: false,
      error: { code: 'INVALID_SHAPE', detail: 'Manifest root must be a JSON object.' },
    };
  }

  const warnings: string[] = [];
  const field = (name: string): unknown => raw[name];

  const displayName = field('DisplayName');
  if (typeof displayName !== 'string' || displayName.trim() === '') {
    return {
      ok: false,
      error: { code: 'INVALID_FIELD', detail: 'DisplayName must be a non-empty string.' },
    };
  }
  if (displayName.length > MAX_DISPLAY_NAME) {
    return {
      ok: false,
      error: {
        code: 'INVALID_FIELD',
        detail: `DisplayName exceeds ${MAX_DISPLAY_NAME} characters.`,
      },
    };
  }

  const appName = field('AppName');
  if (typeof appName !== 'string' || !APP_NAME_RE.test(appName)) {
    return {
      ok: false,
      error: {
        code: 'INVALID_FIELD',
        detail: 'AppName must be a 1–128 char id of letters, digits, and . _ : -',
      },
    };
  }

  const installLocation = field('InstallLocation');
  if (typeof installLocation !== 'string' || installLocation.trim() === '') {
    return {
      ok: false,
      error: { code: 'INVALID_FIELD', detail: 'InstallLocation must be a non-empty string.' },
    };
  }
  if (installLocation.length > MAX_FIELD_LEN) {
    return {
      ok: false,
      error: { code: 'INVALID_FIELD', detail: 'InstallLocation is absurdly long; rejected.' },
    };
  }
  if (!isAbsoluteLike(platform, installLocation)) {
    return {
      ok: false,
      error: { code: 'INVALID_FIELD', detail: 'InstallLocation must be an absolute path.' },
    };
  }
  if (hasTraversal(installLocation)) {
    return {
      ok: false,
      error: { code: 'INVALID_FIELD', detail: 'InstallLocation escapes via ".."; rejected.' },
    };
  }

  const catalogNamespace = field('CatalogNamespace');
  if (catalogNamespace !== undefined && catalogNamespace !== null) {
    if (typeof catalogNamespace !== 'string' || catalogNamespace.length > MAX_FIELD_LEN) {
      return {
        ok: false,
        error: { code: 'INVALID_FIELD', detail: 'CatalogNamespace must be a string.' },
      };
    }
  }

  // Unknown fields are ignored deliberately — the whitelist is the contract.
  const knownFields = new Set([
    'DisplayName',
    'AppName',
    'InstallLocation',
    'CatalogNamespace',
  ]);
  for (const key of Object.keys(raw)) {
    if (!knownFields.has(key)) warnings.push(`Ignored unknown field "${key}".`);
  }

  return {
    ok: true,
    manifest: {
      displayName: displayName.trim(),
      appName,
      installLocation,
      catalogNamespace:
        typeof catalogNamespace === 'string' ? catalogNamespace : null,
    },
    warnings,
  };
}
