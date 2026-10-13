'use client';

import { Camera, ScanLine, Crosshair } from 'lucide-react';

interface SlotDetection {
  conn: 'live' | 'connecting' | 'disconnected' | 'simulated';
  frame: string | null;
  detections: number;
  occupied: number;
  available: number;
  calibrated?: boolean;
  calibrationActive?: boolean;
  lastError?: string | null;
}

export default function SlotDetectionCamera({ detection }: { detection: SlotDetection }) {
  const { conn, frame, detections, occupied, available, calibrated, calibrationActive, lastError } = detection;

  return (
    <div className="card" style={{ padding: 18 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12, gap: 8 }}>
        <div className="card-title">Slot Detection (YOLOv8)</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {calibrated && (
            <span style={{
              display: 'flex', alignItems: 'center', gap: 4,
              fontFamily: 'var(--font-mono)', fontSize: 10.5,
              color: calibrationActive ? 'var(--green-text)' : 'var(--muted)',
              background: calibrationActive ? 'var(--green-bg)' : 'var(--bg)',
              border: `1px solid ${calibrationActive ? '#6EE7B7' : 'var(--border)'}`,
              padding: '3px 9px', borderRadius: 6,
            }}>
              <Crosshair size={11} />
              {calibrationActive ? 'CALIBRATION ACTIVE' : 'AWAITING CAMERA ALIGNMENT'}
            </span>
          )}
          <span style={{
            fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--muted)',
            background: 'var(--bg)', border: '1px solid var(--border)', padding: '3px 9px', borderRadius: 6,
          }}>
            {detections} object{detections === 1 ? '' : 's'}
          </span>
        </div>
      </div>

      <div style={{
        position: 'relative', borderRadius: 10, overflow: 'hidden', border: '1px solid var(--border)',
        background: '#0B1220', aspectRatio: '16 / 9', marginBottom: 12,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        {frame ? (
          <img src={frame} alt="slot camera feed" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        ) : (
          <div style={{ textAlign: 'center', color: 'rgba(255,255,255,.5)' }}>
            <Camera size={34} style={{ marginBottom: 8 }} />
            <div style={{ fontSize: 12, fontFamily: 'var(--font-mono)' }}>
              {conn === 'connecting' ? 'CONNECTING TO CAMERA…' : conn === 'disconnected' ? 'CAMERA NOT CONNECTED' : 'AWAITING FRAMES'}
            </div>
            {conn === 'disconnected' && lastError && (
              <div style={{ fontSize: 11, marginTop: 6, color: 'var(--danger-text)', maxWidth: 280 }}>
                {lastError}
              </div>
            )}
          </div>
        )}
        {conn === 'live' && (
          <div style={{
            position: 'absolute', top: 8, left: 10, display: 'flex', alignItems: 'center', gap: 6,
            fontFamily: 'var(--font-mono)', fontSize: 10, color: 'rgba(255,255,255,.75)',
          }}>
            <ScanLine size={12} /> SCANNING SLOTS
          </div>
        )}
      </div>

      <div style={{ display: 'flex', gap: 10 }}>
        <div style={{
          flex: 1, textAlign: 'center', padding: '8px 6px', borderRadius: 8,
          background: 'var(--danger-bg)', border: '1px solid var(--red-mid)',
        }}>
          <div style={{ fontSize: 18, fontWeight: 800, color: 'var(--danger-text)', fontFamily: 'var(--font-mono)' }}>{occupied}</div>
          <div className="label" style={{ color: 'var(--danger-text)' }}>Occupied</div>
        </div>
        <div style={{
          flex: 1, textAlign: 'center', padding: '8px 6px', borderRadius: 8,
          background: 'var(--green-bg)', border: '1px solid #6EE7B7',
        }}>
          <div style={{ fontSize: 18, fontWeight: 800, color: 'var(--green-text)', fontFamily: 'var(--font-mono)' }}>{available}</div>
          <div className="label" style={{ color: 'var(--green-text)' }}>Available</div>
        </div>
      </div>
    </div>
  );
}
