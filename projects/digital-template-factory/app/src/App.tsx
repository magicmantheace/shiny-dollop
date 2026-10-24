import { useState } from 'react';
import { Gallery } from './components/Gallery';
import { DocumentsList } from './components/DocumentsList';
import { Editor } from './components/Editor';

type View =
  | { kind: 'gallery' }
  | { kind: 'documents' }
  | { kind: 'editor'; docId: string };

/**
 * App shell: header navigation plus a three-view state machine
 * (gallery → editor, documents → editor). No routing library needed;
 * view state is local and keyboard-navigable via native buttons.
 */
export function App() {
  const [view, setView] = useState<View>({ kind: 'gallery' });

  function openDocument(docId: string) {
    setView({ kind: 'editor', docId });
  }

  return (
    <div className="app">
      <a href="#main" className="skip-link">
        Skip to main content
      </a>
      <header className="app-header">
        <div className="app-brand">
          <h1>Template Factory</h1>
          <p className="muted">Digital Product Template Factory</p>
        </div>
        <nav aria-label="Primary" className="app-nav">
          <button
            type="button"
            className={`btn btn-nav${view.kind === 'gallery' ? ' active' : ''}`}
            aria-current={view.kind === 'gallery' ? 'page' : undefined}
            onClick={() => setView({ kind: 'gallery' })}
          >
            Templates
          </button>
          <button
            type="button"
            className={`btn btn-nav${view.kind === 'documents' ? ' active' : ''}`}
            aria-current={view.kind === 'documents' ? 'page' : undefined}
            onClick={() => setView({ kind: 'documents' })}
          >
            My documents
          </button>
        </nav>
      </header>

      <main id="main" className="app-main">
        {view.kind === 'gallery' && <Gallery onOpenDocument={openDocument} />}
        {view.kind === 'documents' && (
          <DocumentsList onOpenDocument={openDocument} />
        )}
        {view.kind === 'editor' && (
          <Editor
            docId={view.docId}
            onBack={() => setView({ kind: 'documents' })}
          />
        )}
      </main>

      <footer className="app-footer">
        <p className="muted">
          Previews are approximate; exported files are authoritative.
        </p>
      </footer>
    </div>
  );
}
