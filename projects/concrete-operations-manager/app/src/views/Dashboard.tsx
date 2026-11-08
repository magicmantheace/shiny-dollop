import { useStore } from '../store';
import { formatCents } from '../format';

export function Dashboard() {
  const { customers, jobs, invoices, stock, go } = useStore();
  const openInvoices = invoices.filter((i) => i.status === 'issued');
  const openTotal = openInvoices.reduce((s, i) => s + i.totalCents, 0);
  const lowStock = stock.filter((s) => s.onHandKg < 500);

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Dashboard</h2>
      <div className="row" style={{ alignItems: 'stretch' }}>
        <div className="card grow">
          <h3 style={{ marginTop: 0 }}>Customers</h3>
          <div style={{ fontSize: 28 }}>{customers.length}</div>
          <button className="small" onClick={() => go({ name: 'customers' })}>
            Manage
          </button>
        </div>
        <div className="card grow">
          <h3 style={{ marginTop: 0 }}>Jobs</h3>
          <div style={{ fontSize: 28 }}>{jobs.length}</div>
          <button className="small" onClick={() => go({ name: 'jobs' })}>
            Manage
          </button>
        </div>
        <div className="card grow">
          <h3 style={{ marginTop: 0 }}>Open invoices</h3>
          <div style={{ fontSize: 28 }}>{openInvoices.length}</div>
          <div className="muted">{formatCents(openTotal)} outstanding</div>
          <div style={{ marginTop: 8 }}>
            <button className="small" onClick={() => go({ name: 'invoices' })}>
              View
            </button>
          </div>
        </div>
      </div>

      <div className="card">
        <h2>Inventory watch</h2>
        {stock.length === 0 ? (
          <div className="empty">No materials tracked yet.</div>
        ) : (
          <table className="data">
            <thead>
              <tr>
                <th>Material</th>
                <th className="num">On hand</th>
              </tr>
            </thead>
            <tbody>
              {stock.map((s) => (
                <tr key={s.materialId}>
                  <td>{s.name}</td>
                  <td className="num">
                    {s.onHandKg.toLocaleString()} {s.unit}
                    {lowStock.some((l) => l.materialId === s.materialId) && (
                      <span className="badge superseded" style={{ marginLeft: 8 }}>
                        low
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div style={{ marginTop: 8 }}>
          <button className="small" onClick={() => go({ name: 'inventory' })}>
            Open inventory
          </button>
        </div>
      </div>
    </div>
  );
}
