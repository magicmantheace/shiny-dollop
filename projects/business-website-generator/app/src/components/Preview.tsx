import { useEffect, useState } from 'react';
import type { RenderedPage } from '../../shared/types';
import { getApi } from '../api';

interface PreviewProps {
  /** Site id whose pages to render. */
  siteId: string;
  /** Bumped to force a re-render (e.g. after a theme switch). */
  renderKey: number;
}

type Viewport = 'desktop' | 'mobile';

/**
 * Live preview: page tab bar + sandboxed iframe showing the rendered HTML.
 * The iframe uses `sandbox="allow-same-origin"` (no scripts) and `srcDoc`.
 * Preview is explicitly approximate — the exported files are authoritative.
 */
export function Preview({ siteId, renderKey }: PreviewProps) {
  const [pages, setPages] = useState<RenderedPage[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activePath, setActivePath] = useState<string | null>(null);
  const [viewport, setViewport] = useState<Viewport>('desktop');

  useEffect(() => {
    let cancelled = false;
    setPages(null);
    setError(null);
    setActivePath(null);
    getApi()
      .preview.render(siteId)
      .then((result) => {
        if (cancelled) return;
        setPages(result);
        setActivePath(result[0]?.path ?? null);
      })
      .catch((e) => {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : 'Could not render the preview.');
      });
    return () => {
      cancelled = true;
    };
  }, [siteId, renderKey]);

  const activePage = pages?.find((p) => p.path === activePath) ?? null;

  return (
    <div className="preview">
      <div className="preview-toolbar">
        <div
          className="viewport-toggle"
          role="group"
          aria-label="Preview viewport"
        >
          <button
            type="button"
            className={`button${viewport === 'desktop' ? ' button-active' : ''}`}
            aria-pressed={viewport === 'desktop'}
            onClick={() => setViewport('desktop')}
          >
            Desktop
          </button>
          <button
            type="button"
            className={`button${viewport === 'mobile' ? ' button-active' : ''}`}
            aria-pressed={viewport === 'mobile'}
            onClick={() => setViewport('mobile')}
          >
            Mobile
          </button>
        </div>
        <p className="preview-disclaimer">
          Preview is approximate — the exported files are authoritative.
        </p>
      </div>

      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}
      {!pages && !error && <p className="empty-state">Rendering preview…</p>}
      {pages && pages.length === 0 && !error && (
        <p className="empty-state">No pages were rendered for this site.</p>
      )}
      {pages && pages.length > 0 && (
        <>
          <div className="tab-bar" role="tablist" aria-label="Preview pages">
            {pages.map((page) => (
              <button
                key={page.path}
                type="button"
                role="tab"
                aria-selected={page.path === activePath}
                className={`tab${page.path === activePath ? ' tab-active' : ''}`}
                onClick={() => setActivePath(page.path)}
              >
                {page.path}
              </button>
            ))}
          </div>
          <div className="preview-frame-wrap">
            {activePage && (
              <iframe
                key={activePage.path}
                title={`Preview of ${activePage.path}`}
                sandbox="allow-same-origin"
                srcDoc={activePage.html}
                className="preview-frame"
                style={{ width: viewport === 'mobile' ? '375px' : '100%' }}
                data-testid="preview-iframe"
              />
            )}
          </div>
        </>
      )}
    </div>
  );
}
