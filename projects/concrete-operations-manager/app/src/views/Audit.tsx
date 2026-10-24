import { useState } from 'react';
import { useStore } from '../store';
import { api, unwrap } from '../api';
import { friendlyError } from '../errorMessages';
import { formatDateTime } from '../format';
import type { AuditEntry } from '../../shared/types';

function summarize(e: AuditEntry): string {
  const id = `${e.entityType} #${e.entityId}`;
  switch (e.action) {
    case 'created': return `${id} created`;
    case 'updated': return `${id} updated`;
    case 'deleted': return `${id} deleted`;
    case 'pricing_updated': return `${id} pricing updated`;
    case 'draft_created': return `quote #${e.entityId} draft created`;
    case 'draft_updated': return `quote #${e.entityId} draft updated`;
    case 'draft_price_overridden': return `quote #${e.entityId} price overridden`;
    case 'issued': return `${id} issued`;
    case 'revision_started': return `quote #${e.entityId} revision started`;
    case 'draft_deleted': return `quote #${e.entityId} draft deleted`;
    case 'marked_paid': return `invoice #${e.entityId} marked paid`;
    case 'voided': return `invoice #${e.entityId} voided`;
    case 'delivered_finalized': return `pour #${e.entityId} delivered volume finalized`;
    case 'delivered_revised': return `pour #${e.entityId} delivered volume revised`;
    case 'estimate_updated': return `pour #${e.entityId} estimate updated`;
    case 'received': return `inventory receipt #${e.entityId} recorded`;
    case 'consumed': return `inventory consumption #${e.entityId} recorded`;
    case 'imported': return `calibration profile #${e.entityId} imported`;
    default: return `${id} — ${e.action.replace(/_/g, ' ')}`;
  }
}

function diffLines(before: string | null, after: string | null): string[] {
  if (!before && !after) return [];
  try {
    const b = before ? (JSON.parse(before) as Record<string, unknown>) : {};
    const a = after ? (JSON.parse(after) as Record<string, unknown>) : {};
    const keys = new Set([...Object.keys(b), ...Object.keys(a)]);
    const out: string[] = [];
    for (const k of keys) {
      const bv = JSON.stringify(b[k]);
      const av = JSON.stringify(a[k]);
      if (bv !== av) out.push(`${k}: ${bv ?? '∅'} → ${av ?? '∅'}`);
    }
    return out.slice(0, 12);
  } catch {
    return ['(detail stored as JSON)'];
  }
}

export function Audit() {
  const { audit, refresh, toast } = useStore();
  const [expanded, setExpanded] = useState<number | null>(null);
  const [filter, setFilter] = useState('');

  async function reload() {
    try {
      await refresh('audit');
    } catch (err) {
      toast('error', friendlyError(err));
    }
  }

  const filtered = filter.trim() === ''
    ? audit
    : audit.filter((e) =>
        `${e.entityType} ${e.entityId} ${e.action}`.toLowerCase().includes(filter.toLowerCase()),
      );

  return (
    <div>
      <div className="row spread">
        <h2 style={{ marginTop: 0 }}>Audit trail</h2>
        <div className="row">
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter (e.g. quote, invoice)"
          />
          <button className="small" onClick={() => { void api().audit.list({ limit: 100 }).then(unwrap).then(() => reload()); }}>
            Refresh
          </button>
        </div>
      </div>
      <div className="card">
        {filtered.length === 0 ? (
          <div className="empty">No audit entries yet.</div>
        ) : (
          <table className="data">
            <thead>
              <tr>
                <th>When</th>
                <th>Event</th>
                <th>Actor</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((e) => (
                <tr key={e.id}>
                  <td className="muted small-text" style={{ whiteSpace: 'nowrap' }}>{formatDateTime(e.createdAt)}</td>
                  <td>{summarize(e)}</td>
                  <td className="muted small-text">{e.actor}</td>
                  <td className="num">
                    <button className="small" onClick={() => setExpanded(expanded === e.id ? null : e.id)}>
                      {expanded === e.id ? 'Hide' : 'Detail'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {expanded !== null && (() => {
          const e = audit.find((x) => x.id === expanded);
          if (!e) return null;
          const diffs = diffLines(e.beforeJson, e.afterJson);
          return (
            <div className="card" style={{ marginTop: 12, background: 'var(--bg)' }}>
              <h3 style={{ marginTop: 0 }}>Before → after</h3>
              {diffs.length === 0 ? (
                <div className="muted">No field-level changes recorded.</div>
              ) : (
                <ul className="small-text mono">
                  {diffs.map((d, i) => (
                    <li key={i}>{d}</li>
                  ))}
                </ul>
              )}
            </div>
          );
        })()}
      </div>
    </div>
  );
}
