import { useState } from 'react';
import { styles } from './styles';
import ItemsView from './components/ItemsView';
import ItemDetailView from './components/ItemDetailView';
import WarrantiesView from './components/WarrantiesView';
import BackupView from './components/BackupView';

type Tab = 'items' | 'warranties' | 'backup';

export default function App() {
  const [tab, setTab] = useState<Tab>('items');
  const [selectedItemId, setSelectedItemId] = useState<string | null>(null);

  // In the packaged Electron app this is always injected by the preload script.
  // When running the renderer standalone (dev/tests), show a plain error instead
  // of crashing on undefined.
  if (typeof window === 'undefined' || !window.inv) {
    return (
      <div style={styles.app}>
        <div style={styles.main}>
          <div style={styles.errorBox}>
            The backend bridge (window.inv) is not available. This UI must run inside the
            Electron app where the preload script injects it.
          </div>
        </div>
      </div>
    );
  }

  function goToItem(id: string) {
    setSelectedItemId(id);
    setTab('items');
  }

  function renderBody() {
    if (selectedItemId) {
      return <ItemDetailView itemId={selectedItemId} onBack={() => setSelectedItemId(null)} />;
    }
    if (tab === 'warranties') return <WarrantiesView onSelectItem={goToItem} />;
    if (tab === 'backup') return <BackupView />;
    return <ItemsView onSelectItem={goToItem} />;
  }

  return (
    <div style={styles.app}>
      <header style={styles.header}>
        <h1 style={styles.title}>Household Inventory</h1>
        <nav style={styles.nav} aria-label="Main">
          <button
            style={tab === 'items' ? styles.tabActive : styles.tab}
            onClick={() => { setTab('items'); setSelectedItemId(null); }}
            aria-current={tab === 'items' ? 'page' : undefined}
          >
            Items
          </button>
          <button
            style={tab === 'warranties' ? styles.tabActive : styles.tab}
            onClick={() => { setTab('warranties'); setSelectedItemId(null); }}
            aria-current={tab === 'warranties' ? 'page' : undefined}
          >
            Warranties
          </button>
          <button
            style={tab === 'backup' ? styles.tabActive : styles.tab}
            onClick={() => { setTab('backup'); setSelectedItemId(null); }}
            aria-current={tab === 'backup' ? 'page' : undefined}
          >
            Backup
          </button>
        </nav>
      </header>
      <main style={styles.main}>{renderBody()}</main>
      <footer style={styles.footer}>
        Offline household inventory — items, receipts, warranties, and backups stay on this computer.
      </footer>
    </div>
  );
}
