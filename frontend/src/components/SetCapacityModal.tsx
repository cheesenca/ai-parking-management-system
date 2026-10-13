'use client';

import { useState } from 'react';
import { X, Settings, Loader2 } from 'lucide-react';
import type { Zone, Category } from '@/types';
import { apiUpdateZoneCapacity } from '@/lib/backendApi';
import ModalPortal from './ModalPortal';

interface CategorySummary {
  used: number;
  total: number;
  available: number;
  rate_pct: number;
}

interface Props {
  zone: Zone;
  currentSummary: Record<string, CategorySummary>;
  onClose: () => void;
}

const CATEGORIES: { key: Category; field: 'employee_capacity' | 'vendor_capacity' | 'visitor_capacity' }[] = [
  { key: 'Employee', field: 'employee_capacity' },
  { key: 'Vendor', field: 'vendor_capacity' },
  { key: 'Visitor', field: 'visitor_capacity' },
];

export default function SetCapacityModal({ zone, currentSummary, onClose }: Props) {
  const [values, setValues] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};

    CATEGORIES.forEach(c => {
      init[c.key] = String(currentSummary[c.key]?.total ?? 0);
    });

    return init;
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const totalPreview = CATEGORIES.reduce((sum, c) => sum + (Number(values[c.key]) || 0), 0);

  const handleSave = async () => {
    setError(null);
    for (const c of CATEGORIES) {
      const n = Number(values[c.key]);
      if (!Number.isFinite(n) || n < 0) {
        setError(`${c.key} capacity must be a valid number ≥ 0`);
        return;
      }
    }

    setSaving(true);
    try {
      await apiUpdateZoneCapacity(zone, {
        employee_capacity: Number(values.Employee),
        vendor_capacity: Number(values.Vendor),
        visitor_capacity: Number(values.Visitor),
      });
      onClose();
      window.location.reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to update capacity');
    } finally {
      setSaving(false);
    }
  };

  return (
    <ModalPortal>
    <div
      className="mem-modal-overlay"
      style={{ background: 'rgba(0,0,0,0.45)' }}
      onClick={onClose}
    >
      <div
        className="card fadein"
        style={{ width: 420, maxWidth: '92vw', padding: 24 }}
        onClick={e => e.stopPropagation()}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Settings size={16} />
            <span className="card-title" style={{ fontSize: 15 }}>Set Capacity — {zone.toUpperCase()}</span>
          </div>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--muted)' }}
          >
            <X size={18} />
          </button>
        </div>

        <p style={{ fontSize: 12.5, color: 'var(--muted)', marginBottom: 18 }}>
          Set the total number of slots available for each category in this zone.
          Total capacity updates automatically.
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {CATEGORIES.map(c => (
            <div key={c.key}>
              <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--ink)', display: 'block', marginBottom: 6 }}>
                {c.key}
              </label>
              <input
                type="number"
                min={0}
                value={values[c.key]}
                onChange={e => setValues(v => ({ ...v, [c.key]: e.target.value }))}
                style={{
                  width: '100%', padding: '9px 12px', borderRadius: 9,
                  border: '1px solid var(--border)', background: 'var(--bg)',
                  color: 'var(--ink)', fontSize: 13, outline: 'none',
                  fontFamily: 'var(--font-mono)',
                }}
              />
            </div>
          ))}
        </div>

        <div style={{ marginTop: 16, padding: '10px 14px', borderRadius: 9, background: 'var(--bg)', border: '1px solid var(--border)', fontSize: 12.5, display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ color: 'var(--muted)' }}>Total capacity</span>
          <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700 }}>{totalPreview}</span>
        </div>

        {error && (
          <div style={{ marginTop: 12, fontSize: 12, color: 'var(--danger-text)' }}>{error}</div>
        )}

        <div style={{ display: 'flex', gap: 10, marginTop: 20 }}>
          <button
            className="btn-secondary"
            style={{ flex: 1, justifyContent: 'center', padding: '10px 0' }}
            onClick={onClose}
            disabled={saving}
          >
            Cancel
          </button>
          <button
            className="btn-primary"
            style={{ flex: 1, justifyContent: 'center', padding: '10px 0', display: 'flex', alignItems: 'center', gap: 6 }}
            onClick={handleSave}
            disabled={saving}
          >
            {saving && <Loader2 size={14} style={{ animation: 'spin 0.8s linear infinite' }} />}
            {saving ? 'Saving…' : 'Save Capacity'}
          </button>
        </div>
      </div>
    </div>
    </ModalPortal>
  );
}