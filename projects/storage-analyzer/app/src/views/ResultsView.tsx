import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { api, friendlyErrorMessage, unwrap } from '../api';
import { duplicateSavingsBytes, formatBytes, formatDateTime, formatInt } from '../format';
import type { DuplicateGroup, ScanSummaryInfo, SearchResult, SummaryResult } from '../types';

export interface ResultsViewProps {
  scanId: number;
  onError: (message: string) => void;
}

/**
 * Results view: ranked folder sizes, largest files, file-type summary,
 * SHA-256 duplicate groups (informational — no deletion in this MVP),
 * full-text search, and CSV/JSON export.
 */
export function ResultsView({ scanId, onError }: ResultsViewProps) {
  const [summary, setSummary] = useState<SummaryResult | null>(null);
  const [duplicates, setDuplicates] = useState<DuplicateGroup[] | null>(null);
  const [scanInfo, setScanInfo] = useState<ScanSummaryInfo | null>(null);
  const [stale, setStale] = useState(false);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResult[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [outPath, setOutPath] = useState('');
  const [exporting, setExporting] = useState<null | 'csv' | 'json'>(null);
  const [exported, setExported] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        const [summaryResult, duplicatesResult, listResult] = await Promise.all([
          api().results.summary({ scanId }).then(unwrap),
          api().results.duplicates({ scanId }).then(unwrap),
          api().scan.list().then(unwrap),
        ]);
        if (cancelled) {
          return;
        }
        setSummary(summaryResult);
        setDuplicates(duplicatesResult.groups);
        const info = listResult.scans.find((s) => s.id === scanId) ?? null;
        setScanInfo(info);
        if (info) {
          // A result is stale when the scan did not complete, or when a newer
          // scan of the same root exists.
          const newerExists = listResult.scans.some(
            (s) => s.rootPath === info.rootPath && s.startedAt > info.startedAt,
          );
          setStale(info.state !== 'complete' || newerExists);
        }
      } catch (err) {
        if (!cancelled) {
          onError(friendlyErrorMessage(err));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [scanId, onError]);

  async function runSearch(e?: FormEvent) {
    e?.preventDefault();
    const q = query.trim();
    if (!q || searching) {
      return;
    }
    setSearching(true);
    setSearchResults(null);
    try {
      const result = unwrap(await api().results.search({ scanId, query: q }));
      setSearchResults(result.files);
    } catch (err) {
      onError(friendlyErrorMessage(err));
    } finally {
      setSearching(false);
    }
  }

  async function runExport(format: 'csv' | 'json') {
    if (!outPath.trim() || exporting) {
      return;
    }
    setExporting(format);
    setExported(null);
    try {
      const result = unwrap(await api().export.report({ scanId, format, outPath: outPath.trim() }));
      setExported(result.outPath);
    } catch (err) {
      onError(friendlyErrorMessage(err));
    } finally {
      setExporting(null);
    }
  }

  if (loading) {
    return (
      <section aria-labelledby="results-heading">
        <h2 id="results-heading">Results</h2>
        <p>Loading results…</p>
      </section>
    );
  }

  return (
    <section aria-labelledby="results-heading">
      <h2 id="results-heading">Results</h2>

      <div className="scan-meta">
        <p>
          <strong>Root:</strong> <span title={scanInfo?.rootPath}>{scanInfo?.rootPath ?? '—'}</span>
        </p>
        <p>
          <strong>Scanned:</strong> {formatDateTime(scanInfo?.startedAt ?? null)}
          {stale && (
            <span className="stale-label" role="status">
              {' '}
              — Stale: this scan did not complete, or a newer scan of this folder exists
            </span>
          )}
        </p>
      </div>

      <div className="export-row">
        <label htmlFor="export-path">Report output path</label>
        <input
          id="export-path"
          type="text"
          value={outPath}
          onChange={(e) => setOutPath(e.target.value)}
          placeholder="C:\temp\storage-report.csv"
        />
        <button type="button" onClick={() => runExport('csv')} disabled={!outPath.trim() || exporting !== null}>
          {exporting === 'csv' ? 'Exporting…' : 'Export CSV'}
        </button>
        <button type="button" onClick={() => runExport('json')} disabled={!outPath.trim() || exporting !== null}>
          {exporting === 'json' ? 'Exporting…' : 'Export JSON'}
        </button>
      </div>
      {exported && (
        <p className="success-text" role="status">
          Report written to {exported}
        </p>
      )}

      <div className="totals">
        <p>
          <strong>{formatInt(summary?.totalFiles ?? 0)}</strong> files,{' '}
          <strong>{formatBytes(summary?.totalBytes ?? 0)}</strong> total
        </p>
      </div>

      <h3>Folder sizes (top 20)</h3>
      <table aria-label="Folder sizes">
        <thead>
          <tr>
            <th scope="col">Folder</th>
            <th scope="col">Size</th>
            <th scope="col">Files</th>
          </tr>
        </thead>
        <tbody>
          {(summary?.dirSizes ?? []).slice(0, 20).map((d) => (
            <tr key={d.path}>
              <td title={d.path}>{d.path}</td>
              <td>{formatBytes(d.bytes)}</td>
              <td>{formatInt(d.files)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>Largest files (top 50)</h3>
      <table aria-label="Largest files">
        <thead>
          <tr>
            <th scope="col">File</th>
            <th scope="col">Size</th>
          </tr>
        </thead>
        <tbody>
          {(summary?.largestFiles ?? []).slice(0, 50).map((f) => (
            <tr key={f.path}>
              <td title={f.path}>{f.path}</td>
              <td>{formatBytes(f.size)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>File types</h3>
      <table aria-label="File type summary">
        <thead>
          <tr>
            <th scope="col">Extension</th>
            <th scope="col">Files</th>
            <th scope="col">Bytes</th>
          </tr>
        </thead>
        <tbody>
          {(summary?.typeSummary ?? []).map((t) => (
            <tr key={t.ext}>
              <td>{t.ext || '(none)'}</td>
              <td>{formatInt(t.files)}</td>
              <td>{formatBytes(t.bytes)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>Duplicate groups ({duplicates?.length ?? 0})</h3>
      <p className="hint">
        Verified by SHA-256. Informational only — this MVP cannot delete files.
      </p>
      {(duplicates ?? []).map((group) => {
        const savings = duplicateSavingsBytes(group.sizeBytes, group.files.length);
        return (
          <div key={group.sha256} className="dup-group" role="group" aria-label={`Duplicate group ${group.sha256.slice(0, 12)}`}>
            <p>
              <strong>Size:</strong> {formatBytes(group.sizeBytes)} × {group.files.length} copies
            </p>
            <p className="hash" title={group.sha256}>
              <strong>SHA-256:</strong> <code>{group.sha256}</code>
            </p>
            <p>
              <strong>Potential savings:</strong> {formatBytes(savings)}
            </p>
            <ul>
              {group.files.map((file) => (
                <li key={file} title={file}>
                  {file}
                </li>
              ))}
            </ul>
          </div>
        );
      })}
      {duplicates !== null && duplicates.length === 0 && <p>No duplicate files found.</p>}

      <h3>Search files</h3>
      <form onSubmit={runSearch} className="input-row">
        <label htmlFor="search-box">Search in scan results</label>
        <input
          id="search-box"
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="filename or path fragment…"
        />
        <button type="submit" disabled={searching || !query.trim()}>
          {searching ? 'Searching…' : 'Search'}
        </button>
      </form>
      {searchResults !== null && (
        <div aria-live="polite">
          <p>
            {searchResults.length} match{searchResults.length === 1 ? '' : 'es'} (max 500)
          </p>
          <ul className="search-results">
            {searchResults.map((f) => (
              <li key={f.path} title={f.path}>
                {f.path} — {formatBytes(f.size)}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
