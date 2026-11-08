import { useState } from 'react';
import BackupView from './components/BackupView';
import NoteDetailView from './components/NoteDetailView';
import NoteFormView from './components/NoteFormView';
import NotesListView from './components/NotesListView';
import { styles } from './styles';

type View =
  | { name: 'list' }
  | { name: 'detail'; id: string }
  | { name: 'new' }
  | { name: 'backup' };

type Tab = 'notes' | 'new' | 'backup';

const TABS: Array<{ id: Tab; label: string }> = [
  { id: 'notes', label: 'Notes' },
  { id: 'new', label: 'New note' },
  { id: 'backup', label: 'Backup' },
];

export default function App() {
  const [view, setView] = useState<View>({ name: 'list' });

  const activeTab: Tab =
    view.name === 'new' ? 'new' : view.name === 'backup' ? 'backup' : 'notes';

  const goTab = (tab: Tab) => {
    if (tab === 'notes') setView({ name: 'list' });
    else if (tab === 'new') setView({ name: 'new' });
    else setView({ name: 'backup' });
  };

  return (
    <div style={styles.app}>
      <header style={styles.header}>
        <h1 style={styles.title}>Personal Knowledge Vault</h1>
        <span style={styles.tagline}>Offline · source-linked · reviewable</span>
        <nav style={styles.nav} aria-label="Main">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              style={activeTab === t.id ? styles.tabActive : styles.tab}
              onClick={() => goTab(t.id)}
              aria-current={activeTab === t.id ? 'page' : undefined}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>
      <main style={styles.main}>
        {view.name === 'list' && (
          <NotesListView onOpenNote={(id) => setView({ name: 'detail', id })} />
        )}
        {view.name === 'detail' && (
          <NoteDetailView
            key={view.id}
            id={view.id}
            onBack={() => setView({ name: 'list' })}
            onOpenNote={(id) => setView({ name: 'detail', id })}
          />
        )}
        {view.name === 'new' && (
          <NoteFormView onCreated={(id) => setView({ name: 'detail', id })} />
        )}
        {view.name === 'backup' && <BackupView />}
      </main>
      <footer style={styles.footer}>
        Local-first knowledge vault — all data stays on this machine. New notes enter
        as candidates until reviewed.
      </footer>
    </div>
  );
}
