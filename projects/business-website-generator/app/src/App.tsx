import { useState } from 'react';
import { SiteList } from './components/SiteList';
import { SiteWorkspace } from './components/SiteWorkspace';
import './styles.css';

type View = { kind: 'dashboard' } | { kind: 'site'; id: string };

export function App() {
  const [view, setView] = useState<View>({ kind: 'dashboard' });

  return (
    <div className="app">
      <a href="#main" className="skip-link">
        Skip to main content
      </a>
      <header className="app-header">
        <h1>Small Business Website Generator</h1>
      </header>
      <main id="main" className="app-main" tabIndex={-1}>
        {view.kind === 'dashboard' ? (
          <SiteList onOpen={(id) => setView({ kind: 'site', id })} />
        ) : (
          <SiteWorkspace siteId={view.id} onBack={() => setView({ kind: 'dashboard' })} />
        )}
      </main>
    </div>
  );
}
