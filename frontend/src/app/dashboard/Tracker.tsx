'use client';

import { useEffect, useState } from 'react';
import { useAuth } from '@/lib/AuthContext';
import type { Zone } from '@/lib/types';
import { useLiveDetection, useSlotOccupancy, useSlotDetection } from '@/lib/api';
import { Wifi, WifiOff, Cpu, Settings } from 'lucide-react';
import ConnPill from '@/components/ConnPill';
import LiveDetection from '@/components/LiveDetection';
import SlotDetectionCamera from '@/components/SlotDetectionCamera';
import SlotMap from '@/components/SlotMap';
import CategoryStats from '@/components/CategoryStats';
import SetCapacityModal from '@/components/SetCapacityModal';

const zoneOptions: { value: Zone; label: string }[] = [
  { value: 'west', label: 'West Plant' },
  { value: 'east', label: 'East Plant' },
];

// Set by start.bat's feature menu so a teammate without the slot-occupancy
// webcam yet can run LPR alone (and vice versa) without a dead camera feed
// retrying in the background. Defaults to enabled when unset, e.g. `npm run
// dev` outside start.bat.
const LPR_ENABLED = process.env.NEXT_PUBLIC_ENABLE_LPR !== 'false';
const OCCUPANCY_ENABLED = process.env.NEXT_PUBLIC_ENABLE_OCCUPANCY !== 'false';

export default function TrackerPage() {
  const { user } = useAuth();
  const defaultZone = (user?.location ?? 'west') as Zone;
  const [selectedZone, setSelectedZone] = useState<Zone>(defaultZone);
  const lpr = useLiveDetection({ cameraIndex: 0, enabled: LPR_ENABLED });
  const slots = useSlotOccupancy(selectedZone);
  const slotDetection = useSlotDetection(selectedZone, { cameraIndex: 1, enabled: OCCUPANCY_ENABLED });
  const [latestIn, setLatestIn] = useState('—');
  const [latestOut, setLatestOut] = useState('—');
  const [capacityModalOpen, setCapacityModalOpen] = useState(false);

  useEffect(() => {
    if (!lpr.latest) return;
    const t = new Date(lpr.latest.timestamp).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' });
    if (lpr.latest.event_type === 'entry') setLatestIn(t); else setLatestOut(t);
  }, [lpr.latest]);

  return (
    <div className="page-pad fadein">
      {/* HEADER UTAMA */}
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

      {/* 1. GRID KIRI & KANAN (Sejajar sampai Live Slot Map) */}
      <div className="grid-2" style={{ marginBottom: 20 }}>
        {/* KOLOM KIRI: Live Detection (YOLOv8 + EasyOCR) */}
        <div>
          <LiveDetection lpr={lpr} selectedZone={selectedZone} />
        </div>

        {/* KOLOM KANAN: Slot Camera, Post Location, dan Slot Map */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Slot Detection naik ke posisi paling atas di kolom kanan */}
          <SlotDetectionCamera detection={slotDetection} />
          
          {/* Post Location ditukar ke bawah Slot Detection */}
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

          {/* Peta Slot Parkir */}
          <SlotMap slots={slots} />
        </div>
      </div>

      {/* 2. BAGIAN BAWAH: Elemen yang Melebar Full-Width */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        {/* Available Slots by Category */}
        <CategoryStats slots={slots} />
        
        {/* Kartu Status & Set Capacity (Diperluas) */}
        <div className="card" style={{ padding: 24 }}> {/* Padding diperbesar */}
          <div className="grid-2" style={{ gap: 16 }}>
            <div style={{ padding: 18, borderRadius: 12, background: 'var(--green-bg)', border: '1px solid #6EE7B7' }}>
              <div className="label" style={{ color: 'var(--green-text)', marginBottom: 8, fontSize: 12 }}>Latest In</div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 24, fontWeight: 700, color: 'var(--green-text)' }}>{latestIn}</div>
            </div>
            <div style={{ padding: 18, borderRadius: 12, background: 'var(--danger-bg)', border: '1px solid var(--red-mid)' }}>
              <div className="label" style={{ color: 'var(--danger-text)', marginBottom: 8, fontSize: 12 }}>Latest Out</div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 24, fontWeight: 700, color: 'var(--danger-text)' }}>{latestOut}</div>
            </div>
          </div>
          {user?.role === 'Admin' && (
            <button
              className="btn-secondary"
              style={{ width: '100%', justifyContent: 'center', marginTop: 16, padding: '12px 0', fontSize: 13, fontWeight: 600 }}
              onClick={() => setCapacityModalOpen(true)}
            >
              <Settings size={15} /> Set Capacity
            </button>
          )}
        </div>
      </div>

      {capacityModalOpen && (
        <SetCapacityModal
          zone={selectedZone}
          currentSummary={slots.summary}
          onClose={() => setCapacityModalOpen(false)}
        />
      )}
    </div>
  );
}