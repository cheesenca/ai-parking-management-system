'use client';

import { useState, useEffect, useMemo, useCallback } from 'react';
import type { EntryLog } from '@/types';
import { apiGetLogs } from '@/lib/backendApi';
import { useAuth } from '@/context/AuthContext';
import { ChevronLeft, ChevronRight, RefreshCw, LogIn, LogOut, ShieldAlert, Inbox } from 'lucide-react';

type Tab = 'Entry' | 'Exit' | 'Denied';
const PER_PAGE = 8;

function ConfBar({ score }: { score: number }) {
  const color = score >= 0.80 ? 'var(--teal)' : score >= 0.60 ? 'var(--amber)' : 'var(--red)';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
      <div style={{ flex: 1, height: 4, borderRadius: 2, background: 'var(--border)' }}>
        <div style={{ height: '100%', borderRadius: 2, width: `${score * 100}%`, background: color }} />
      </div>
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color, width: 32, textAlign: 'right', fontWeight: 600 }}>
        {(score * 100).toFixed(0)}%
      </span>
    </div>
  );
}

const authBadge = (m: EntryLog['auth_method']) =>
  m === 'AI_LPR' ? <span className="badge badge-red" style={{ fontSize: 10 }}>AI</span> :
  m === 'KPK_Scan' ? <span className="badge badge-navy" style={{ fontSize: 10 }}>KPK</span> :
                     <span className="badge badge-yellow"  style={{ fontSize: 10 }}>MANUAL</span>;

const catBadge = (c: string) => {
  const map: Record<string, string> = { Employee: 'badge-blue', Vendor: 'badge-navy', Visitor: 'badge-yellow' };
  return <span className={`badge ${map[c] || 'badge-blue'}`} style={{ fontSize: 10 }}>{c.slice(0, 3)}</span>;
};

export default function ParkingListPage() {
  const { user } = useAuth();
  const zone = user?.role === 'Security' ? user.location ?? undefined : undefined;
  const [logs, setLogs] = useState<EntryLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [tab, setTab] = useState<Tab>('Entry');
  const [page, setPage] = useState(1);

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await apiGetLogs(zone, 500);
      setLogs(data);
    } catch (e) {
      setError((e as Error).message || 'Failed to load log');
    } finally {
      setLoading(false);
    }
  }, [zone]);

  useEffect(() => { void fetchLogs(); }, [fetchLogs]);

  useEffect(() => {
    const t = setInterval(() => { void fetchLogs(); }, 15_000);
    return () => clearInterval(t);
  }, [fetchLogs]);

  const filtered = useMemo(() => logs.filter(l => l.event_type === tab), [logs, tab]);
  const totalPages = Math.max(1, Math.ceil(filtered.length / PER_PAGE));
  const paged = filtered.slice((page - 1) * PER_PAGE, page * PER_PAGE);
  const ins = useMemo(() => logs.filter(l => l.event_type === 'Entry'), [logs]);
  const outs = useMemo(() => logs.filter(l => l.event_type === 'Exit'), [logs]);
  const denied = useMemo(() => logs.filter(l => l.event_type === 'Denied'), [logs]);

  return (
    <div className="page-pad fadein">
      <div className="lst-header">
        <div>
          <h1 className="tr-title">Parking List</h1>
          <p className="tr-subtitle">Real-time vehicle entry and exit logs</p>
        </div>
        <button onClick={() => { void fetchLogs(); }} className="btn-secondary" style={{ fontSize: 12 }} disabled={loading}>
          <RefreshCw size={13} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} /> Refresh
        </button>
      </div>

      {error && (
        <div style={{ padding: '12px 16px', borderRadius: 10, background: 'var(--danger-bg)', border: '1px solid var(--red-mid)', color: 'var(--danger-text)', fontSize: 13, marginBottom: 16 }}>
          {error}
        </div>
      )}

      {/* Summary */}
      <div className="grid-3" style={{ gap: 14, marginBottom: 22 }}>
        {[
          { label: 'Total Entry', value: ins.length, icon: LogIn, cls: 'lst-sum-in' },
          { label: 'Total Exit', value: outs.length, icon: LogOut, cls: 'lst-sum-out' },
          { label: 'Denied', value: denied.length, icon: ShieldAlert, cls: 'lst-sum-denied' },
        ].map(s => {
          const Icon = s.icon;
          return (
            <div key={s.label} className={`lst-sum-card ${s.cls}`}>
              <div className="lst-sum-icon"><Icon size={16} /></div>
              <div>
                <div className="lst-sum-label">{s.label}</div>
                <div className="lst-sum-value">{loading ? '—' : s.value}</div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Tab */}
      <div className="lst-tabs">
        {(['Entry', 'Exit', 'Denied'] as Tab[]).map(t => (
          <button key={t} onClick={() => { setTab(t); setPage(1); }} className={`lst-tab-btn${tab === t ? ' active' : ''}`}>{t}</button>
        ))}
      </div>

      {/* Table */}
      <div className="card" style={{ overflow: 'hidden', marginBottom: 18 }}>
        <div className="lst-table-head">
          <span className={`lst-dot lst-dot-${tab.toLowerCase()}`} />
          <span className="lst-table-title">{tab.toUpperCase()} LOG</span>
          <span className="lst-table-count">{filtered.length} records</span>
        </div>

        {loading ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>Memuat log…</div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table lst-table">
              <thead><tr>
                <th>Plate</th><th>Name</th><th>KPK</th><th>Time</th><th>Zone</th><th>Cat.</th><th>Auth</th><th>Conf.</th>
              </tr></thead>
              <tbody>
                {paged.length === 0 ? (
                  <tr><td colSpan={8}>
                    <div className="lst-empty">
                      <Inbox size={22} />
                      <span>No data available</span>
                    </div>
                  </td></tr>
                ) : paged.map(l => (
                  <tr key={l.log_id}>
                    <td><span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 600 }}>{l.plate_detected}</span></td>
                    <td style={{ maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{l.name || '—'}</td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>{l.kpk || '—'}</td>
                    <td><span style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{l.time_scan}</span></td>
                    <td style={{ fontSize: 11, textTransform: 'uppercase' }}>{l.zone}</td>
                    <td>{catBadge(l.category || 'Visitor')}</td>
                    <td>{authBadge(l.auth_method)}</td>
                    <td style={{ minWidth: 80 }}><ConfBar score={l.confidence_score} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Pagination */}
      <div className="lst-pagination">
        <span style={{ fontSize: 12, color: 'var(--muted)' }}>
          Showing {Math.min((page - 1) * PER_PAGE + 1, filtered.length)}–{Math.min(page * PER_PAGE, filtered.length)} of {filtered.length}
        </span>
        <div style={{ display: 'flex', gap: 3 }}>
          <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} className="btn-secondary" style={{ padding: '5px 9px' }}>
            <ChevronLeft size={13} />
          </button>
          {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => i + 1).map(n => (
            <button key={n} onClick={() => setPage(n)} className={`lst-page-btn${page === n ? ' active' : ''}`}>{n}</button>
          ))}
          <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages} className="btn-secondary" style={{ padding: '5px 9px' }}>
            <ChevronRight size={13} />
          </button>
        </div>
      </div>

      {/* Denied events */}
      {!loading && denied.length > 0 && (
        <div className="lst-denied-panel">
          <div className="lst-denied-title">
            Access Denied Events — {denied.length} entries
          </div>
          {denied.slice(0, 5).map(l => (
            <div key={l.log_id} className="lst-denied-row">
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 700, color: 'var(--red)' }}>{l.plate_detected}</span>
              <span style={{ fontSize: 12, color: 'var(--muted)' }}>{l.zone?.toUpperCase()} · {l.time_scan}</span>
              <div style={{ flex: 1 }}><ConfBar score={l.confidence_score} /></div>
              <span style={{ fontSize: 12, color: 'var(--warn-text)', fontWeight: 600 }}>Manual verification needed</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}