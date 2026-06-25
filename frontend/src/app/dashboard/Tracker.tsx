'use client';
import { useEffect, useState } from 'react';
import { useAuth } from '@/lib/AuthContext';
import type { Zone } from '@/lib/types';
import { useLiveDetection, useSlotOccupancy } from '@/lib/api';
import { Wifi, WifiOff, Cpu, Settings } from 'lucide-react';
import ConnPill from '@/components/ConnPill';
import LiveDetection from '@/components/LiveDetection';
import SlotMap from '@/components/SlotMap';
import CategoryStats from '@/components/CategoryStats';

const zoneOptions: { value: Zone; label: string }[] = [
  { value: 'west', label: 'West Plant' },
  { value: 'east', label: 'East Plant' },
  { value: 'eastwest', label: 'East & West Plant' },
];

export default function TrackerPage() {
  const { user } = useAuth();
  const defaultZone = (user?.location ?? 'west') as Zone;
  const [selectedZone, setSelectedZone] = useState<Zone>(defaultZone);
  const lpr = useLiveDetection({ cameraIndex: 0, enabled: true });
  const slots = useSlotOccupancy(selectedZone);
  const [latestIn, setLatestIn] = useState('—');
  const [latestOut, setLatestOut] = useState('—');

  useEffect(() => {
    if (!lpr.latest) return;
    const t = new Date(lpr.latest.timestamp).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' });
    if (lpr.latest.event_type === 'entry') setLatestIn(t); else setLatestOut(t);
  }, [lpr.latest]);

  const connBanner = (conn: string, label: string) =>
    conn === 'disconnected' ? (
      <div style={{ padding: '8px 14px', borderRadius: 8, background: 'var(--danger-bg)', border: '1px solid var(--red-mid)', fontSize: 12, color: 'var(--danger-text)', marginBottom: 8 }}>
        {label} Not connected — check the host configuration in the environment variable.
      </div>
    ) : null;

  return (
    <div style={{ padding: '28px 32px' }} className="fadein">
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 24, gap: 12, flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 800, color: 'var(--ink)', letterSpacing: '-0.02em', marginBottom: 4 }}>Parking Tracker</h1>
          <p style={{ fontSize: 13, color: 'var(--muted)' }}>Live AI vehicle detection &amp; real-time slot vacancy at guard post</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <ConnPill label="LPR CAMERA" state={lpr.conn} icon={lpr.conn === 'live' ? Wifi : WifiOff} />
          <ConnPill label="SLOT SCANNER" state={slots.conn} icon={Cpu} />
        </div>
      </div>

      {connBanner(lpr.conn, 'LPR Camera (NEXT_PUBLIC_LPR_HOST)')}
      {connBanner(slots.conn, 'Slot Scanner (NEXT_PUBLIC_SLOT_HOST)')}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        <LiveDetection lpr={lpr} selectedZone={selectedZone} />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="card" style={{ padding: 18 }}>
            <div className="label" style={{ marginBottom: 8 }}>Post Location</div>
            <select
              value={selectedZone}
              onChange={e => setSelectedZone(e.target.value as Zone)}
              disabled={user?.role === 'Security'}
              style={{ width: '100%', padding: '9px 12px', borderRadius: 9, border: '1px solid var(--border)', background: 'var(--bg)', color: 'var(--ink)', fontSize: 13, outline: 'none', fontFamily: 'var(--font-body)', fontWeight: 600, cursor: user?.role === 'Security' ? 'not-allowed' : 'pointer' }}
            >
              {zoneOptions.map(z => <option key={z.value} value={z.value}>{z.label}</option>)}
            </select>
            {user?.role === 'Security' && (
              <p style={{ fontSize: 11, color: 'var(--muted)', marginTop: 6 }}>Zone locked to assigned post.</p>
            )}
          </div>
          <SlotMap slots={slots} />
          <CategoryStats slots={slots} />
          <div className="card" style={{ padding: 18 }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div style={{ padding: 12, borderRadius: 9, background: 'var(--green-bg)', border: '1px solid #6EE7B7' }}>
                <div className="label" style={{ color: 'var(--green-text)', marginBottom: 6 }}>Latest In</div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 20, fontWeight: 700, color: 'var(--green-text)' }}>{latestIn}</div>
              </div>
              <div style={{ padding: 12, borderRadius: 9, background: 'var(--danger-bg)', border: '1px solid var(--red-mid)' }}>
                <div className="label" style={{ color: 'var(--danger-text)', marginBottom: 6 }}>Latest Out</div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 20, fontWeight: 700, color: 'var(--danger-text)' }}>{latestOut}</div>
              </div>
            </div>
            {user?.role === 'Admin' && (
              <button className="btn-secondary" style={{ width: '100%', justifyContent: 'center', marginTop: 12, fontSize: 12 }}>
                <Settings size={13} /> Set Capacity
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
