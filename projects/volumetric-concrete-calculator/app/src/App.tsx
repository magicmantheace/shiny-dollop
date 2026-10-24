import { useCallback, useEffect, useState } from 'react';
import CalculatorView from './views/Calculator.js';
import ProfilesView from './views/Profiles.js';
import HistoryView from './views/History.js';

type View = 'calculator' | 'profiles' | 'history';

export interface Toast {
  id: number;
  text: string;
}

let toastId = 0;

export default function App() {
  const [view, setView] = useState<View>('calculator');
  const [toasts, setToasts] = useState<Toast[]>([]);

  const notify = useCallback((text: string) => {
    const id = ++toastId;
    setToasts((t) => [...t, { id, text }]);
    window.setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 5000);
  }, []);

  useEffect(() => {
    document.title = 'Volumetric Concrete Mix Calculator';
  }, []);

  return (
    <div className="shell">
      <nav className="nav" aria-label="Primary">
        <h1>Volumetric Concrete Mix Calculator</h1>
        <p className="sub">Estimates only — never structural, legal, or compliance claims.</p>
        <button aria-current={view === 'calculator' ? 'page' : undefined} onClick={() => setView('calculator')}>
          Calculator
        </button>
        <button aria-current={view === 'profiles' ? 'page' : undefined} onClick={() => setView('profiles')}>
          Calibration profiles
        </button>
        <button aria-current={view === 'history' ? 'page' : undefined} onClick={() => setView('history')}>
          History
        </button>
      </nav>
      <main className="main">
        {view === 'calculator' && <CalculatorView notify={notify} />}
        {view === 'profiles' && <ProfilesView notify={notify} />}
        {view === 'history' && <HistoryView notify={notify} />}
      </main>
      <div className="toasts" aria-live="polite">
        {toasts.map((t) => (
          <div className="toast" key={t.id}>
            {t.text}
          </div>
        ))}
      </div>
    </div>
  );
}
