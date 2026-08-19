'use client';

import { useState, useEffect, useCallback } from 'react';
import type { PendingReview } from '@/lib/types';
import type { Detection } from '@/lib/api';
import { apiGetPendingReviews } from '@/lib/backendApi';
import { useAuth } from '@/lib/AuthContext';
import { ChevronLeft, ChevronRight, RefreshCw, ImageOff } from 'lucide-react';
import ManualApprovalModal from '@/components/ManualApprovalModal';

const PAGE_SIZE = 8;

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

function toDetection(row: PendingReview): Detection {
  return {
    plate_detected: row.plate_guess || '???',
    confidence: row.confidence,
    vehicle_type: row.vehicle_type || 'car',
    event_type: row.event_type,
    timestamp: row.captured_at,
    status: row.plate_guess ? 'low_confidence' : 'no_plate',
    member: null,
  };
}

export default function PendingReviewPage() {
  const { user } = useAuth();
  const zone = user?.role === 'Security' ? user.location ?? undefined : undefined;
  const [rows, setRows] = useState<PendingReview[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [page, setPage] = useState(1);
  const [reviewing, setReviewing] = useState<PendingReview | null>(null);

  const fetchReviews = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await apiGetPendingReviews({ zone, status: 'needs_review', page, page_size: PAGE_SIZE });
      setRows(data.items);
      setTotal(data.total);
    } catch (e) {
      setError((e as Error).message || 'Failed to load pending reviews');
    } finally {
      setLoading(false);
    }
  }, [zone, page]);

  useEffect(() => { void fetchReviews(); }, [fetchReviews]);

  useEffect(() => {
    const t = setInterval(() => { void fetchReviews(); }, 15_000);
    return () => clearInterval(t);
  }, [fetchReviews]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const closeAndRefresh = () => {
    setReviewing(null);
    void fetchReviews();
  };

  return (
    <div className="page-pad fadein">
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 800, color: 'var(--ink)', letterSpacing: '-0.02em', marginBottom: 4 }}>Pending Review</h1>
          <p style={{ fontSize: 13, color: 'var(--muted)' }}>
            Low-confidence detections the automatic reread couldn&apos;t resolve — approve or dismiss each one.
          </p>
        </div>
        <button onClick={() => { void fetchReviews(); }} className="btn-secondary" style={{ fontSize: 12 }} disabled={loading}>
          <RefreshCw size={13} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} /> Refresh
        </button>
      </div>

      {error && (
        <div style={{ padding: '12px 16px', borderRadius: 10, background: 'var(--danger-bg)', border: '1px solid var(--red-mid)', color: 'var(--danger-text)', fontSize: 13, marginBottom: 16 }}>
          {error}
        </div>
      )}

      <div className="card" style={{ overflow: 'hidden', marginBottom: 18 }}>
        <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--amber)', display: 'inline-block' }} />
          <span style={{ fontWeight: 800, fontSize: 12, color: 'var(--ink)', letterSpacing: '.04em' }}>NEEDS REVIEW</span>
          <span style={{ marginLeft: 'auto', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--muted)' }}>{total} records</span>
        </div>

        {loading ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>Loading…</div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table">
              <thead><tr>
                <th>Image</th><th>Plate Guess</th><th>Vehicle</th><th>Zone</th><th>Direction</th><th>Captured</th><th>Conf.</th><th></th>
              </tr></thead>
              <tbody>
                {rows.length === 0 ? (
                  <tr><td colSpan={8} style={{ textAlign: 'center', padding: 32, color: 'var(--muted)' }}>Nothing waiting on review right now.</td></tr>
                ) : rows.map(r => (
                  <tr key={r.review_id}>
                    <td>
                      {r.image_base64 ? (
                        <img
                          src={`data:image/jpeg;base64,${r.image_base64}`}
                          alt="Captured plate"
                          style={{ width: 56, height: 40, objectFit: 'cover', borderRadius: 6, border: '1px solid var(--border)' }}
                        />
                      ) : (
                        <div style={{ width: 56, height: 40, borderRadius: 6, border: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--muted2)' }}>
                          <ImageOff size={14} />
                        </div>
                      )}
                    </td>
                    <td><span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 600 }}>{r.plate_guess || '???'}</span></td>
                    <td style={{ fontSize: 12, textTransform: 'capitalize' }}>{r.vehicle_type || '—'}</td>
                    <td style={{ fontSize: 11, textTransform: 'uppercase' }}>{r.zone}</td>
                    <td style={{ fontSize: 12 }}>{r.event_type === 'entry' ? '→ IN' : '← OUT'}</td>
                    <td><span style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{new Date(r.captured_at).toLocaleString()}</span></td>
                    <td style={{ minWidth: 80 }}><ConfBar score={r.confidence} /></td>
                    <td>
                      <button className="btn-primary" style={{ fontSize: 11, padding: '6px 12px' }} onClick={() => setReviewing(r)}>
                        Review
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 10, justifyContent: 'center', marginBottom: 20 }}>
        <span style={{ fontSize: 12, color: 'var(--muted)' }}>
          Showing {total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} of {total}
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

      {reviewing && (
        <ManualApprovalModal
          key={reviewing.review_id}
          detection={toDetection(reviewing)}
          zone={reviewing.zone as 'west' | 'east' | 'eastwest'}
          reviewId={reviewing.review_id}
          imageBase64={reviewing.image_base64}
          onClose={() => setReviewing(null)}
          onApproved={closeAndRefresh}
          onDismissed={closeAndRefresh}
        />
      )}
    </div>
  );
}
