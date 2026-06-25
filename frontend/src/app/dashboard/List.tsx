'use client';
import { useState, useEffect, useMemo, useCallback } from 'react';
import type { EntryLog } from '@/lib/types';
import { apiGetLogs } from '@/lib/backendApi';
import { useAuth } from '@/lib/AuthContext';
import { ChevronLeft, ChevronRight, RefreshCw } from 'lucide-react';

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
    <div style={{ padding: '28px 32px' }} className="fadein">
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 800, color: 'var(--ink)', letterSpacing: '-0.02em', marginBottom: 4 }}>Parking List</h1>
          <p style={{ fontSize: 13, color: 'var(--muted)' }}>Real-time vehicle entry and exit logs</p>
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
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14, marginBottom: 22 }}>
        {[
          { label: 'Total Entry', value: ins.length, color: 'var(--green-text)', bg: 'var(--green-bg)', border: '#6EE7B7' },
          { label: 'Total Exit', value: outs.length, color: 'var(--danger-text)', bg: 'var(--danger-bg)', border: 'var(--red-mid)' },
          { label: 'Denied', value: denied.length, color: 'var(--warn-text)', bg: 'var(--warn-bg)', border: '#FDE68A' },
        ].map(s => (
          <div key={s.label} style={{ padding: '16px 18px', borderRadius: 12, background: s.bg, border: `1px solid ${s.border}` }}>
            <div className="label" style={{ color: s.color, marginBottom: 6 }}>{s.label}</div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 26, fontWeight: 700, color: s.color }}>
              {loading ? '—' : s.value}
            </div>
          </div>
        ))}
      </div>

      {/* Tab */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 18, padding: 4, background: '#fff', border: '1px solid var(--border)', borderRadius: 10, width: 'fit-content', boxShadow: 'var(--shadow-sm)' }}>
        {(['Entry', 'Exit', 'Denied'] as Tab[]).map(t => (
          <button key={t} onClick={() => { setTab(t); setPage(1); }} style={{
            padding: '7px 18px', borderRadius: 8, border: 'none', fontSize: 13, fontWeight: 700,
            background: tab === t ? 'var(--red)' : 'transparent',
            color: tab === t ? '#fff' : 'var(--muted)', cursor: 'pointer',
          }}>{t}</button>
        ))}
      </div>

      {/* Table */}
      <div className="card" style={{ overflow: 'hidden', marginBottom: 18 }}>
        <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: tab === 'Entry' ? 'var(--teal)' : tab === 'Exit' ? 'var(--red)' : 'var(--amber)', display: 'inline-block' }} />
          <span style={{ fontWeight: 800, fontSize: 12, color: 'var(--ink)', letterSpacing: '.04em' }}>{tab.toUpperCase()} LOG</span>
          <span style={{ marginLeft: 'auto', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--muted)' }}>{filtered.length} records</span>
        </div>

        {loading ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>Memuat log…</div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table">
              <thead><tr>
                <th>Plate</th><th>Name</th><th>KPK</th><th>Time</th><th>Zone</th><th>Cat.</th><th>Auth</th><th>Conf.</th>
              </tr></thead>
              <tbody>
                {paged.length === 0 ? (
                  <tr><td colSpan={8} style={{ textAlign: 'center', padding: 32, color: 'var(--muted)' }}>Tidak ada data.</td></tr>
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
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, justifyContent: 'center', marginBottom: 20 }}>
        <span style={{ fontSize: 12, color: 'var(--muted)' }}>
          Showing {Math.min((page - 1) * PER_PAGE + 1, filtered.length)}–{Math.min(page * PER_PAGE, filtered.length)} of {filtered.length}
        </span>
        <div style={{ display: 'flex', gap: 3 }}>
          <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} className="btn-secondary" style={{ padding: '5px 9px' }}>
            <ChevronLeft size={13} />
          </button>
          {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => i + 1).map(n => (
            <button key={n} onClick={() => setPage(n)} style={{
              padding: '5px 11px', borderRadius: 7, border: '1px solid',
              borderColor: page === n ? 'var(--red)' : 'var(--border)',
              background: page === n ? 'var(--red)' : '#fff',
              color: page === n ? '#fff' : 'var(--text)',
              cursor: 'pointer', fontSize: 12, fontWeight: 700,
            }}>{n}</button>
          ))}
          <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages} className="btn-secondary" style={{ padding: '5px 9px' }}>
            <ChevronRight size={13} />
          </button>
        </div>
      </div>

      {/* Denied events */}
      {!loading && denied.length > 0 && (
        <div style={{ padding: '16px 18px', borderRadius: 12, background: 'var(--danger-bg)', border: '1px solid var(--red-mid)' }}>
          <div style={{ fontWeight: 800, fontSize: 13, color: 'var(--danger-text)', marginBottom: 12 }}>
            Access Denied Events — {denied.length} entries
          </div>
          {denied.slice(0, 5).map(l => (
            <div key={l.log_id} style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '9px 12px', borderRadius: 8, background: '#fff', border: '1px solid var(--red-mid)', marginBottom: 8 }}>
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
