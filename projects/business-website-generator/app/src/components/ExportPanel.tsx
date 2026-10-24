import { useState } from 'react';
import type { ExportResult, ValidationIssue } from '../../shared/types';
import { getApi } from '../api';
import { fieldToSectionId } from '../validation';

interface ExportPanelProps {
  siteId: string;
  /** Jump to the editor section an issue refers to (switches to Profile tab). */
  onJumpToSection: (sectionId: string) => void;
}

/**
 * Export flow: Validate → issue list (codes link back to editor sections) →
 * Export… → directory picker → export.run → success / blocked panel.
 *
 * The Export button stays disabled until `export.validate` returns clean —
 * export is never allowed with validation errors present.
 */
export function ExportPanel({ siteId, onJumpToSection }: ExportPanelProps) {
  const [issues, setIssues] = useState<ValidationIssue[] | null>(null);
  const [validating, setValidating] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [result, setResult] = useState<ExportResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const isClean = issues !== null && issues.length === 0;

  const runValidation = async () => {
    setValidating(true);
    setError(null);
    setResult(null);
    try {
      const result = await getApi().export.validate(siteId);
      setIssues(result.issues);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Validation failed.');
    } finally {
      setValidating(false);
    }
  };

  const runExport = async () => {
    if (!isClean || exporting) return;
    setExporting(true);
    setError(null);
    try {
      const destDir = await getApi().dialog.pickDirectory();
      if (destDir === null) {
        // User cancelled the picker: not an error, stay on the clean state.
        return;
      }
      const outcome = await getApi().export.run(siteId, destDir);
      setResult(outcome);
      if (!outcome.ok) {
        setIssues(outcome.issues);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Export failed.');
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="export-panel">
      <div className="row-actions">
        <button type="button" className="button" onClick={() => void runValidation()} disabled={validating}>
          {validating ? 'Validating…' : 'Validate'}
        </button>
        <button
          type="button"
          className="button button-primary"
          onClick={() => void runExport()}
          disabled={!isClean || exporting}
          title={!isClean ? 'Run validation with no issues before exporting.' : undefined}
          aria-describedby="export-disabled-hint"
        >
          {exporting ? 'Exporting…' : 'Export…'}
        </button>
      </div>
      {!isClean && (
        <p id="export-disabled-hint" className="field-hint">
          Export is available after validation reports no issues.
        </p>
      )}
      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}

      {issues && issues.length > 0 && (
        <section aria-labelledby="export-issues-heading" className="editor-section">
          <h3 id="export-issues-heading" tabIndex={-1}>
            Validation issues ({issues.length})
          </h3>
          <ul className="issue-list">
            {issues.map((issue, i) => (
              <li key={`${issue.code}-${i}`} className="issue">
                <code className="issue-code">{issue.code}</code>
                <span className="issue-message">{issue.message}</span>
                <button
                  type="button"
                  className="link-button"
                  onClick={() => onJumpToSection(fieldToSectionId(issue.field))}
                >
                  Go to section
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {issues && issues.length === 0 && !result && (
        <p className="success-note" role="status">
          Validation passed — the site is ready to export.
        </p>
      )}

      {result && result.ok && (
        <section aria-labelledby="export-success-heading" className="editor-section">
          <h3 id="export-success-heading" tabIndex={-1}>
            Export complete
          </h3>
          <p>
            Written to <code>{result.destDir}</code>
          </p>
          <ul className="file-list">
            {result.files.map((f) => (
              <li key={f}>
                <code>{f}</code>
              </li>
            ))}
          </ul>
        </section>
      )}

      {result && !result.ok && (
        <section aria-labelledby="export-blocked-heading" className="editor-section">
          <h3 id="export-blocked-heading" tabIndex={-1}>
            Export blocked
          </h3>
          <p>The export did not complete. Fix the issues below and try again.</p>
          <ul className="issue-list">
            {result.issues.map((issue, i) => (
              <li key={`${issue.code}-${i}`} className="issue">
                <code className="issue-code">{issue.code}</code>
                <span className="issue-message">{issue.message}</span>
                <button
                  type="button"
                  className="link-button"
                  onClick={() => onJumpToSection(fieldToSectionId(issue.field))}
                >
                  Go to section
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
