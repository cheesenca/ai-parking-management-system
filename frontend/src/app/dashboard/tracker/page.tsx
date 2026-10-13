'use client';

import { useEffect, useState } from 'react';
import { useAuth } from '@/context/AuthContext';
import type { Zone } from '@/types';
import { useLiveDetection } from '@/hooks/useLiveDetection';
import { useSlotOccupancy } from '@/hooks/useSlotOccupancy';
import { useSlotDetection } from '@/hooks/useSlotDetection';
import { Wifi, WifiOff, Cpu, Settings, LogIn, LogOut, MapPin } from 'lucide-react';
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
      <div className="tr-header">
        <div>
          <h1 className="tr-title">Parking Tracker</h1>
          <p className="tr-subtitle">Live AI vehicle detection &amp; real-time slot vacancy at guard post</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <ConnPill label="LPR CAMERA" state={lpr.conn} icon={lpr.conn === 'live' ? Wifi : WifiOff} />
          <ConnPill label="SLOT SCANNER" state={slots.conn} icon={Cpu} />
        </div>
      </div>

      {/* 1. GRID KIRI & KANAN (Sejajar sampai Live Slot Map) */}
      <div className="grid-2" style={{ marginBottom: 20 }}>
        {/* KOLOM KIRI: Live Detection (YOLOv8 + EasyOCR) */}
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <LiveDetection lpr={lpr} selectedZone={selectedZone} />
        </div>

        {/* KOLOM KANAN: Slot Camera, Post Location, dan Slot Map */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Slot Detection naik ke posisi paling atas di kolom kanan */}
          <SlotDetectionCamera detection={slotDetection} />
          
          {/* Post Location ditukar ke bawah Slot Detection */}
          <div className="card tr-zone-card">
            <div className="label tr-zone-label"><MapPin size={12} /> Post Location</div>
            <div className="tr-zone-toggle">
              {zoneOptions.map(z => (
                <button
                  key={z.value}
                  type="button"
                  disabled={user?.role === 'Security'}
                  className={`tr-zone-btn${selectedZone === z.value ? ' active' : ''}`}
                  onClick={() => setSelectedZone(z.value)}
                >
                  {z.label}
                </button>
              ))}
            </div>
            {user?.role === 'Security' && (
              <p className="tr-zone-hint">Zone locked to assigned post.</p>
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
        <div className="card" style={{ padding: 24 }}>
          <div className="grid-2" style={{ gap: 16 }}>
            <div className="tr-stat-card tr-stat-in">
              <div className="tr-stat-icon"><LogIn size={16} /></div>
              <div>
                <div className="tr-stat-label">Latest In</div>
                <div className="tr-stat-value">{latestIn}</div>
              </div>
            </div>
            <div className="tr-stat-card tr-stat-out">
              <div className="tr-stat-icon"><LogOut size={16} /></div>
              <div>
                <div className="tr-stat-label">Latest Out</div>
                <div className="tr-stat-value">{latestOut}</div>
              </div>
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