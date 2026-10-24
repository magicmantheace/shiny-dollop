import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { api, unwrap } from './api';
import { friendlyError } from './errorMessages';
import type {
  AuditEntry,
  Customer,
  InventoryMaterial,
  Invoice,
  Job,
  StockEntry,
  TaxRate,
} from '../shared/types';

export type View =
  | { name: 'dashboard' }
  | { name: 'customers' }
  | { name: 'jobs' }
  | { name: 'job'; jobId: number }
  | { name: 'invoices' }
  | { name: 'invoice'; invoiceId: number }
  | { name: 'inventory' }
  | { name: 'settings' }
  | { name: 'audit' };

export interface Toast {
  id: number;
  kind: 'info' | 'success' | 'error';
  text: string;
}

interface StoreState {
  view: View;
  go: (view: View) => void;
  customers: Customer[];
  jobs: Job[];
  invoices: Invoice[];
  materials: InventoryMaterial[];
  stock: StockEntry[];
  taxRates: TaxRate[];
  settings: Record<string, string>;
  audit: AuditEntry[];
  loading: boolean;
  refresh: (scope?: 'all' | 'audit') => Promise<void>;
  toast: (kind: Toast['kind'], text: string) => void;
  toasts: Toast[];
  dismissToast: (id: number) => void;
}

const StoreContext = createContext<StoreState | null>(null);

let toastSeq = 1;

export function StoreProvider({ children }: { children: React.ReactNode }) {
  const [view, setView] = useState<View>({ name: 'dashboard' });
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [materials, setMaterials] = useState<InventoryMaterial[]>([]);
  const [stock, setStock] = useState<StockEntry[]>([]);
  const [taxRates, setTaxRates] = useState<TaxRate[]>([]);
  const [settings, setSettings] = useState<Record<string, string>>({});
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [toasts, setToasts] = useState<Toast[]>([]);

  const dismissToast = useCallback((id: number) => {
    setToasts((t) => t.filter((x) => x.id !== id));
  }, []);

  const toast = useCallback(
    (kind: Toast['kind'], text: string) => {
      const id = toastSeq++;
      setToasts((t) => [...t, { id, kind, text }]);
      window.setTimeout(() => dismissToast(id), kind === 'error' ? 9000 : 4500);
    },
    [dismissToast],
  );

  const refresh = useCallback(
    async (scope: 'all' | 'audit' = 'all') => {
      const a = api();
      try {
        if (scope === 'all') {
          setLoading(true);
          const [c, j, inv, m, s, t, st] = await Promise.all([
            a.customers.list().then(unwrap),
            a.jobs.list().then(unwrap),
            a.invoices.list().then(unwrap),
            a.inventory.materials().then(unwrap),
            a.inventory.stock().then(unwrap),
            a.taxRates.list().then(unwrap),
            a.settings.get().then(unwrap),
          ]);
          setCustomers(c);
          setJobs(j);
          setInvoices(inv);
          setMaterials(m);
          setStock(s);
          setTaxRates(t);
          setSettings(st);
        }
        const au = await a.audit.list({ limit: 100 }).then(unwrap);
        setAudit(au);
      } catch (err) {
        toast('error', friendlyError(err));
      } finally {
        setLoading(false);
      }
    },
    [toast],
  );

  useEffect(() => {
    void refresh('all');
  }, [refresh]);

  const go = useCallback((v: View) => {
    setView(v);
    window.scrollTo(0, 0);
  }, []);

  const state = useMemo<StoreState>(
    () => ({
      view,
      go,
      customers,
      jobs,
      invoices,
      materials,
      stock,
      taxRates,
      settings,
      audit,
      loading,
      refresh,
      toast,
      toasts,
      dismissToast,
    }),
    [view, go, customers, jobs, invoices, materials, stock, taxRates, settings, audit, loading, refresh, toast, toasts, dismissToast],
  );

  return <StoreContext.Provider value={state}>{children}</StoreContext.Provider>;
}

export function useStore(): StoreState {
  const s = useContext(StoreContext);
  if (!s) throw new Error('useStore must be used inside StoreProvider');
  return s;
}
