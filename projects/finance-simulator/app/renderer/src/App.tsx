import { useState } from 'react';
import DebtsView from './components/DebtsView';
import IncomeView from './components/IncomeView';
import SimulatorView from './components/SimulatorView';
import { DISCLAIMER } from './types';
import { styles } from './styles';

type Tab = 'debts' | 'income' | 'simulator';

const TABS: Array<{ id: Tab; label: string }> = [
  { id: 'debts', label: 'Debts' },
  { id: 'income', label: 'Income' },
  { id: 'simulator', label: 'Simulator' },
];

export default function App() {
  const [tab, setTab] = useState<Tab>('simulator');

  return (
    <div style={styles.app}>
      <header style={styles.header}>
        <h1 style={styles.title}>Personal Finance Simulator</h1>
        <span style={styles.disclaimer}>{DISCLAIMER}</span>
        <nav style={styles.nav} aria-label="Main">
          {TABS.map((t) => (
            <button
              key={t.id}
              style={tab === t.id ? styles.tabActive : styles.tab}
              onClick={() => setTab(t.id)}
              aria-current={tab === t.id ? 'page' : undefined}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>
      <main style={styles.main}>
        {tab === 'debts' && <DebtsView />}
        {tab === 'income' && <IncomeView />}
        {tab === 'simulator' && <SimulatorView />}
      </main>
      <footer style={styles.footer}>
        {DISCLAIMER} · Offline tool — your data never leaves this machine.
      </footer>
    </div>
  );
}
