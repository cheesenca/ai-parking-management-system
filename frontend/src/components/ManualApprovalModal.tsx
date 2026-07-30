'use client';
import { useState } from 'react';
import { X, ShieldCheck, Loader2 } from 'lucide-react';
import type { Zone } from '@/lib/types';
import type { Detection } from '@/lib/api';
import { apiManualApprovePlate } from '@/lib/backendApi';
import ModalPortal from './ModalPortal';

interface Props {
  detection: Detection;
  zone: Zone;
  onClose: () => void;
  onApproved: (classification: 'Member' | 'Visitor') => void;
}

export default function ManualApprovalModal({ detection, zone, onClose, onApproved }: Props) {
  const [plate, setPlate] = useState(detection.plate_detected === '???' ? '' : detection.plate_detected);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleApprove = async () => {
    setError(null);
    if (!plate.trim()) {
      setError('Enter the license plate before approving');
      return;
    }
    setSaving(true);
    try {
      const result = await apiManualApprovePlate({
        plate,
        zone,
        event_type: detection.event_type,
        timestamp: detection.timestamp,
        original_confidence: detection.confidence,
      });
      onApproved(result.classification);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to record manual approval');
    } finally {
      setSaving(false);
    }
  };

  return (
    <ModalPortal>
    <div
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
      }}
    >
      <div className="card" style={{ width: 420, maxWidth: '92vw', padding: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <ShieldCheck size={16} />
            <span className="card-title" style={{ fontSize: 15 }}>Manual Verification Needed</span>
          </div>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--muted)' }}
          >
            <X size={18} />
          </button>
        </div>

        <p style={{ fontSize: 12.5, color: 'var(--muted)', marginBottom: 18 }}>
          The AI read this plate with low confidence ({(detection.confidence * 100).toFixed(0)}%).
          Correct it if needed, then approve to record it — it will be checked against registered members.
        </p>

        <div>
          <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--ink)', display: 'block', marginBottom: 6 }}>
            License Plate
          </label>
          <input
            type="text"
            value={plate}
            onChange={e => setPlate(e.target.value.toUpperCase())}
            placeholder="e.g. B 1234 ABC"
            style={{
              width: '100%', padding: '9px 12px', borderRadius: 9,
              border: '1px solid var(--border)', background: 'var(--bg)',
              color: 'var(--ink)', fontSize: 13, outline: 'none',
              fontFamily: 'var(--font-mono)', fontWeight: 600,
            }}
          />
        </div>

        <div style={{ marginTop: 16, padding: '10px 14px', borderRadius: 9, background: 'var(--bg)', border: '1px solid var(--border)', fontSize: 12.5, display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ color: 'var(--muted)' }}>Direction</span>
          <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700 }}>
            {detection.event_type === 'entry' ? '→ IN (Entry)' : '← OUT (Exit)'}
          </span>
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
            Reject
          </button>
          <button
            className="btn-primary"
            style={{ flex: 1, justifyContent: 'center', padding: '10px 0', display: 'flex', alignItems: 'center', gap: 6 }}
            onClick={handleApprove}
            disabled={saving}
          >
            {saving && <Loader2 size={14} style={{ animation: 'spin 0.8s linear infinite' }} />}
            {saving ? 'Recording…' : 'Approve & Record'}
          </button>
        </div>
      </div>
    </div>
    </ModalPortal>
  );
}
