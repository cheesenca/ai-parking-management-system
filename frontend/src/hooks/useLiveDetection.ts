import { useEffect, useRef, useState } from 'react';
import type { Zone, Member } from '@/types';
import { getToken } from '@/lib/backendApi';

const LPR_HOST = process.env.NEXT_PUBLIC_LPR_HOST || '';

export type ConnState = 'live' | 'connecting' | 'disconnected' | 'simulated';
export const CAMERA_INDEX_BY_ZONE: Record<Zone, number> = {
  west: 1,
  east: 1,
  eastwest: 1,
};

export interface Detection {
  plate_detected: string;
  confidence: number;
  vehicle_type: string;
  event_type: 'entry' | 'exit';
  timestamp: string;
  status: 'detected' | 'low_confidence' | 'no_plate';
  member: Member | null;
  review_id?: number | null;
}

export function useLiveDetection(opts: { cameraIndex?: number; gateType?: 'entry' | 'exit'; zone?: Zone; enabled?: boolean } = {}) {
  const { cameraIndex = 0, gateType, zone = 'west', enabled = true } = opts;
  const [conn, setConn] = useState<ConnState>('connecting');
  const [frame, setFrame] = useState<string | null>(null);
  const [latest, setLatest]  = useState<Detection | null>(null);
  const [scanCount, setScanCount] = useState(0);
  const [vehiclesInFrame, setVehiclesInFrame] = useState(0);
  const [retryTick, setRetryTick] = useState(0);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!enabled) {
      setConn('disconnected');
      return;
    }

    if (!LPR_HOST) {
      setConn('disconnected');
      return;
    }

    let cancelled = false;
    let retryTimer: ReturnType<typeof setTimeout>;
    const q = new URLSearchParams({ camera_index: String(cameraIndex), zone });
    if (gateType) q.set('gate_type', gateType);

    const token = getToken();
    if (token) q.set('token', token);

    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    let ws: WebSocket;

    try {
      ws = new WebSocket(`${proto}://${LPR_HOST}/api/v1/ocr/ws/camera?${q.toString()}`);
    } catch {
      if (!cancelled) setConn('disconnected');
      return;
    }

    wsRef.current = ws;
    setConn('connecting');

    const failTimer = setTimeout(() => {
      if (ws.readyState !== WebSocket.OPEN) {
        try { 
          ws.close(); 
        } catch {
          //
        }
        if (!cancelled) setConn('disconnected');
      }
    }, 5000);

    ws.onopen = () => {
      clearTimeout(failTimer);
      if (!cancelled) setConn('live');
    };

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data as string);
        if (data.frame) setFrame(`data:image/jpeg;base64,${data.frame as string}`);
        if (Array.isArray(data.vehicles)) setVehiclesInFrame((data.vehicles as unknown[]).length);
        if (data.detection) {
          const d = data.detection as {
            plate_detected: string; confidence: number; vehicle_type: string;
            event_type: 'entry' | 'exit'; timestamp: string; status: string; member?: Member;
            review_id?: number | null;
          };
          const det: Detection = {
            plate_detected: d.plate_detected || '???',
            confidence: d.confidence ?? 0,
            vehicle_type: d.vehicle_type || 'car',
            event_type: d.event_type || 'entry',
            timestamp: d.timestamp || new Date().toISOString(),
            status: (d.status as Detection['status']) || 'detected',
            member: d.member || null,
            review_id: d.review_id ?? null,
          };
          setLatest(det);
          setScanCount(c => c + 1);
        }
      } catch { 
        //
      }
    };

    ws.onerror = () => {
      clearTimeout(failTimer);
      if (!cancelled) setConn('disconnected');
    };

    ws.onclose = () => {
      clearTimeout(failTimer);
      if (!cancelled) {
        setConn('disconnected');
        setFrame(null);
        retryTimer = setTimeout(() => setRetryTick(t => t + 1), 4000);
      }
    };

    return () => {
      cancelled = true;
      clearTimeout(failTimer);
      clearTimeout(retryTimer);
      try { ws.close(); } catch {}
    };
  }, [cameraIndex, gateType, enabled, retryTick]);

  return { conn, frame, latest, scanCount, vehiclesInFrame };
}