/**
 * The one Unicode-aware normalization used for file search, applied to
 * BOTH sides of the comparison: the stored `files.path_search` key (set in
 * `recordFile`, backfilled by migration v2) and every incoming query
 * (`searchFiles`).
 *
 * SQLite's built-in `lower()` folds ASCII only — it leaves e.g. 'É'
 * unchanged — while JavaScript's `toLowerCase()` is Unicode-aware. Mixing
 * the two makes a search for 'été' miss a file named 'ÉTÉ.txt'. NFC
 * composition is applied as well so decomposed and precomposed spellings
 * of the same name match.
 */
export function normalizeForSearch(value: string): string {
  return value.normalize('NFC').toLowerCase();
}
