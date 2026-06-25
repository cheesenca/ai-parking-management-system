'use client'

import { useMemo, useState, useEffect } from 'react';
import { ScanLine, CheckCircle, XCircle, AlertTriangle, Camera } from 'lucide-react';
import { type Zone } from '@/lib/types';

type Status = 'idle' | 'scanning' | 'granted' | 'denied' | 'wrong_loc';

export default function LiveDetection({ lpr, selectedZone }: { lpr: any; selectedZone: Zone }) {
  const [verified, setVerified] = useState<number | null>(null);
  const det = lpr.latest;

  useEffect(() => {
    setVerified(null);
  }, [det]);

  const status: Status = useMemo(() => {
    if (!det) return 'idle';
    if (det.confidence < 0.7 || det.plate_detected === '???') return 'denied';
    if (det.member && det.member.registered_plant !== selectedZone &&
        det.member.registered_plant !== 'eastwest' && selectedZone !== 'eastwest') return 'wrong_loc';
    return 'granted';
  }, [det, selectedZone]);

  const statusConfig: Record<Status, { label: string; color: string; bg: string; border: string; icon: typeof Camera }> = {
    idle: { label: 'Awaiting Vehicle', color: 'var(--muted)', bg: 'var(--bg)', border: 'var(--border)', icon: Camera },
    scanning: { label: 'AI Scanning…', color: 'var(--amber)', bg: 'var(--warn-bg)', border: '#FDE68A', icon: ScanLine },
    granted: { label: 'Access Granted', color: 'var(--green-text)', bg: 'var(--green-bg)', border: '#6EE7B7', icon: CheckCircle },
    denied: { label: 'Manual Verification Needed', color: 'var(--danger-text)', bg: 'var(--danger-bg)', border: 'var(--red-mid)', icon: XCircle },
    wrong_loc: { label: 'Wrong Zone', color: 'var(--warn-text)', bg: 'var(--warn-bg)', border: '#FDE68A', icon: AlertTriangle },
  };

  const sc = statusConfig[status];
  const fields = [
    { label: 'Scan KPK', value: det?.member?.kpk_number },
    { label: 'Name', value: det?.member?.name },
    { label: 'Registered Plant', value: det?.member?.registered_plant?.toUpperCase() },
    { label: 'Plate License', value: det?.plate_detected, mono: true },
    { label: 'Vehicle Type', value: det?.vehicle_type ? det.vehicle_type.charAt(0).toUpperCase() + det.vehicle_type.slice(1) : undefined },
    { label: 'Category', value: det?.member?.category },
    { label: 'Direction', value: det ? (det.event_type === 'entry' ? '→ IN (Entry)' : '← OUT (Exit)') : undefined },
  ];

  return (
    <div className="card" style={{ padding: 24 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
        <div className="card-title">Live Detection (YOLOv8 + EasyOCR)</div>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--muted)', background: 'var(--bg)', border: '1px solid var(--border)', padding: '3px 9px', borderRadius: 6 }}>
          #{lpr.scanCount.toString().padStart(4, '0')}
        </span>
      </div>

      {/* Camera feed */}
      <div style={{ position: 'relative', borderRadius: 10, overflow: 'hidden', border: '1px solid var(--border)', background: '#0B1220', aspectRatio: '16 / 9', marginBottom: 16, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {lpr.frame ? (
          <img src={lpr.frame} alt="camera feed" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        ) : (
          <div style={{ textAlign: 'center', color: 'rgba(255,255,255,.5)' }}>
            <Camera size={34} style={{ marginBottom: 8 }} />
            <div style={{ fontSize: 12, fontFamily: 'var(--font-mono)' }}>
              {lpr.conn === 'simulated' ? 'SIMULATED FEED — no camera connected' : lpr.conn === 'connecting' ? 'CONNECTING TO CAMERA…' : 'AWAITING FRAMES'}
            </div>
          </div>
        )}
        <div style={{ position: 'absolute', left: 0, right: 0, top: '64%', height: 2, background: 'rgba(245,200,0,.85)' }} />
        <div style={{ position: 'absolute', top: 8, left: 10, fontFamily: 'var(--font-mono)', fontSize: 10, color: 'rgba(255,255,255,.7)' }}>
          GATE LINE · tracking {lpr.vehiclesInFrame} object{lpr.vehiclesInFrame === 1 ? '' : 's'}
        </div>
      </div>

      {/* Status bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '10px 14px', borderRadius: 10, marginBottom: 16, background: sc.bg, border: `1px solid ${sc.border}` }}>
        <sc.icon size={14} style={{ color: sc.color }} />
        <span style={{ fontSize: 13, fontWeight: 700, color: verified === lpr.scanCount ? 'var(--green-text)' : sc.color }}>{verified === lpr.scanCount ? 'Manually Verified' : sc.label}</span>
        {det && det.confidence > 0 && (
          <span style={{ marginLeft: 'auto', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--muted)' }}>
            {(det.confidence * 100).toFixed(0)}% conf.
          </span>
        )}
      </div>

      {/* Auto-filled fields */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {fields.map((f) => (
          <div key={f.label}>
            <div className="label" style={{ marginBottom: 5 }}>{f.label}</div>
            <div style={{
              padding: '8px 12px', borderRadius: 8,
              background: f.value ? 'var(--bg)' : 'var(--card2)',
              border: '1px solid var(--border)', fontSize: 13, minHeight: 34,
              display: 'flex', alignItems: 'center',
              fontFamily: f.mono ? 'var(--font-mono)' : 'var(--font-body)',
              fontWeight: f.mono ? 600 : 400,
              color: f.value ? 'var(--ink)' : 'var(--muted2)',
            }}>
              {f.value || '—'}
            </div>
          </div>
        ))}
      </div>

      {status === 'denied' && det && (
        <div style={{ display: 'flex', gap: 10, marginTop: 16 }}>
          <button className="btn-primary" style={{ flex: 1, justifyContent: 'center', background: 'var(--teal)' }} onClick={() => setVerified(lpr.scanCount)}>
            <CheckCircle size={14} /> Verify &amp; Admit
          </button>
          <button className="btn-secondary" onClick={() => setVerified(null)}>Reject</button>
        </div>
      )}
    </div>
  );
}
