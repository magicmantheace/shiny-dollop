import { useCallback, useState } from 'react';
import { ErrorBanner } from './components/ErrorBanner';
import { HistoryView } from './views/HistoryView';
import { ResultsView } from './views/ResultsView';
import { ScanView } from './views/ScanView';
import { StartView } from './views/StartView';
import type { ScanStartWarning } from './types';

export type View =
  | { name: 'start' }
  | { name: 'scan'; scanId: number; startWarning?: ScanStartWarning | undefined }
  | { name: 'results'; scanId: number }
  | { name: 'history' };

export function App() {
  const [view, setView] = useState<View>({ name: 'start' });
  const [error, setError] = useState<string | null>(null);

  const onError = useCallback((message: string) => {
    setError(message);
  }, []);

  const nav = (name: View['name']) => {
    setView((current) => {
      if (current.name === name) {
        return current;
      }
      if (name === 'start') {
        return { name: 'start' };
      }
      if (name === 'history') {
        return { name: 'history' };
      }
      // 'scan' and 'results' require a scanId; only entered via callbacks.
      return current;
    });
  };

  return (
    <div className="app">
      <header>
        <h1>PC Storage and Duplicate Finder</h1>
        <nav aria-label="Main">
          <button type="button" onClick={() => nav('start')} aria-current={view.name === 'start' ? 'page' : undefined}>
            New scan
          </button>
          <button
            type="button"
            onClick={() => nav('history')}
            aria-current={view.name === 'history' ? 'page' : undefined}
          >
            History
          </button>
        </nav>
      </header>

      <main>
        {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}
        {view.name === 'start' && (
          <StartView
            onScanStarted={(scanId: number, startWarning?: ScanStartWarning) =>
              setView({ name: 'scan', scanId, startWarning })
            }
            onError={onError}
          />
        )}
        {view.name === 'scan' && (
          <ScanView
            scanId={view.scanId}
            startWarning={view.startWarning}
            onViewResults={(scanId) => setView({ name: 'results', scanId })}
            onNewScan={() => setView({ name: 'start' })}
            onError={onError}
          />
        )}
        {view.name === 'results' && <ResultsView scanId={view.scanId} onError={onError} />}
        {view.name === 'history' && (
          <HistoryView onSelectScan={(scanId) => setView({ name: 'results', scanId })} onError={onError} />
        )}
      </main>
    </div>
  );
}
