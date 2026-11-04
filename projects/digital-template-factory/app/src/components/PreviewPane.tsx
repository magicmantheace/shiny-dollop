import { useMemo } from 'react';
import type { DocumentRecord, TemplateManifest } from '../../shared/types';
import { renderPreviewHtml } from '../preview';

interface PreviewPaneProps {
  manifest: TemplateManifest;
  doc: DocumentRecord;
}

/**
 * Live preview: renders the current document through the local pure
 * renderer (`src/preview.ts`) into a sandboxed iframe. The banner makes
 * the approximation explicit — the exported file is authoritative.
 */
export function PreviewPane({ manifest, doc }: PreviewPaneProps) {
  const html = useMemo(
    () => renderPreviewHtml(manifest, doc),
    [manifest, doc],
  );

  return (
    <section aria-labelledby="preview-heading" className="preview-pane">
      <div className="preview-head">
        <h2 id="preview-heading">Preview</h2>
        <p className="preview-note" role="note">
          Approximate preview — the exported file is authoritative.
        </p>
      </div>
      <iframe
        title={`Preview of ${manifest.name}`}
        className="preview-frame"
        sandbox=""
        srcDoc={html}
      />
    </section>
  );
}
