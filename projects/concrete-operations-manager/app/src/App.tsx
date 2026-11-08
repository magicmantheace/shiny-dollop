import { useStore } from './store';
import type { View } from './store';
import { Toasts } from './components/Toasts';
import { Dashboard } from './views/Dashboard';
import { Customers } from './views/Customers';
import { Jobs } from './views/Jobs';
import { JobDetail } from './views/JobDetail';
import { Invoices, InvoiceDetail } from './views/Invoices';
import { Inventory } from './views/Inventory';
import { Settings } from './views/Settings';
import { Audit } from './views/Audit';

const NAV: { label: string; view: View['name'] }[] = [
  { label: 'Dashboard', view: 'dashboard' },
  { label: 'Customers', view: 'customers' },
  { label: 'Jobs', view: 'jobs' },
  { label: 'Invoices', view: 'invoices' },
  { label: 'Inventory', view: 'inventory' },
  { label: 'Settings', view: 'settings' },
  { label: 'Audit trail', view: 'audit' },
];

function activeNav(view: View): View['name'] {
  if (view.name === 'job') return 'jobs';
  if (view.name === 'invoice') return 'invoices';
  return view.name;
}

export default function App() {
  const { view, go, loading } = useStore();

  return (
    <div className="app-shell">
      <nav className="sidebar" aria-label="Main navigation">
        <h1>
          Concrete Ops
          <span className="sub">MVP · local-first</span>
        </h1>
        {NAV.map((n) => (
          <button
            key={n.view}
            className={`nav-btn ${activeNav(view) === n.view ? 'active' : ''}`}
            onClick={() => go({ name: n.view } as View)}
          >
            {n.label}
          </button>
        ))}
      </nav>
      <main className="main">
        {loading ? (
          <div className="empty">Loading…</div>
        ) : view.name === 'dashboard' ? (
          <Dashboard />
        ) : view.name === 'customers' ? (
          <Customers />
        ) : view.name === 'jobs' ? (
          <Jobs />
        ) : view.name === 'job' ? (
          <JobDetail jobId={view.jobId} />
        ) : view.name === 'invoices' ? (
          <Invoices />
        ) : view.name === 'invoice' ? (
          <InvoiceDetail invoiceId={view.invoiceId} />
        ) : view.name === 'inventory' ? (
          <Inventory />
        ) : view.name === 'settings' ? (
          <Settings />
        ) : (
          <Audit />
        )}
      </main>
      <Toasts />
    </div>
  );
}
