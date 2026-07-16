import { useEffect, useRef, useState } from 'react';
import type { Zone, Member } from '@/lib/types';
import { apiGetLiveSlots, getToken } from '@/lib/backendApi';
import { PARKING_MAPS, type SlotStatus, type CategoryInfo } from '@/lib/slotData';

const LPR_HOST = process.env.NEXT_PUBLIC_LPR_HOST  || '';
const SLOT_HOST = process.env.NEXT_PUBLIC_SLOT_HOST || '';

export type ConnState = 'live' | 'connecting' | 'disconnected' | 'simulated';

// Physical camera routing per zone. Only ONE slot-scanner camera exists
// today, so every zone points at device 0 - the backend enforces this same
// mapping server-side (ZONE_CAMERA_DEVICE in endpoints.py) so this value is
// really just for display/testing purposes. Once East Plant / East&West
// Plant get their own cameras, update both this map and its backend twin.
export const CAMERA_INDEX_BY_ZONE: Record<Zone, number> = {
  west: 0,
  east: 0,      // TODO: point to the East Plant camera device once installed
  eastwest: 0,  // TODO: point to the East&West Plant camera device once installed
};
export interface Detection {
  plate_detected: string;
  confidence: number;
  vehicle_type: string;
  event_type: 'entry' | 'exit';
  timestamp: string;
  status: 'detected' | 'low_confidence' | 'no_plate';
  member: Member | null;
}

export function useLiveDetection(opts: { cameraIndex?: number; gateType?: 'entry' | 'exit'; zone?: Zone; enabled?: boolean } = {}) {
  const { cameraIndex = 0, gateType, zone = 'west', enabled = true } = opts;
  const [conn, setConn] = useState<ConnState>('connecting');
  const [frame, setFrame] = useState<string | null>(null);
  const [latest, setLatest]  = useState<Detection | null>(null);
  const [scanCount, setScanCount] = useState(0);
  const [vehiclesInFrame, setVehiclesInFrame] = useState(0);
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
        try { ws.close(); } catch {}
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
          };
          const det: Detection = {
            plate_detected: d.plate_detected || '???',
            confidence: d.confidence ?? 0,
            vehicle_type: d.vehicle_type || 'car',
            event_type: d.event_type || 'entry',
            timestamp: d.timestamp || new Date().toISOString(),
            status: (d.status as Detection['status']) || 'detected',
            member: d.member || null,
          };
          setLatest(det);
          setScanCount(c => c + 1);
        }
      } catch { 

      }
    };

    ws.onerror = () => {
      clearTimeout(failTimer);
      if (!cancelled) setConn('disconnected');
    };

    ws.onclose = () => {
      clearTimeout(failTimer);
      if (!cancelled) setConn('disconnected');
    };

    return () => {
      cancelled = true;
      clearTimeout(failTimer);
      try { ws.close(); } catch {}
    };
  }, [cameraIndex, gateType, enabled]);

  return { conn, frame, latest, scanCount, vehiclesInFrame };
}

export function useSlotDetection(zone: Zone, opts: { cameraIndex?: number; enabled?: boolean } = {}) {
  const { cameraIndex = 0, enabled = true } = opts;
  const [conn, setConn] = useState<ConnState>('connecting');
  const [frame, setFrame] = useState<string | null>(null);
  const [detections, setDetections] = useState(0);
  const [occupied, setOccupied] = useState(0);
  const [available, setAvailable] = useState(0);
  const [calibrated, setCalibrated] = useState(false);
  const [calibrationActive, setCalibrationActive] = useState(false);
  const [retryTick, setRetryTick] = useState(0);
  const [lastError, setLastError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!enabled) {
      setConn('disconnected');
      return;
    }
    if (!SLOT_HOST) {
      setConn('disconnected');
      return;
    }

    let cancelled = false;
    let retryTimer: ReturnType<typeof setTimeout>;
    const q = new URLSearchParams({ zone, camera_index: String(cameraIndex) });

    const token = getToken();
    if (token) q.set('token', token);

    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    let ws: WebSocket;

    try {
      ws = new WebSocket(`${proto}://${SLOT_HOST}/api/v1/slots/ws/slots?${q.toString()}`);
    } catch {
      if (!cancelled) setConn('disconnected');
      return;
    }

    wsRef.current = ws;
    setConn('connecting');

    const failTimer = setTimeout(() => {
      if (ws.readyState !== WebSocket.OPEN) {
        try { ws.close(); } catch {}
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
        if (data.error) { if (!cancelled) { setConn('disconnected'); setLastError(String(data.error)); } return; }
        if (data.frame) setFrame(`data:image/jpeg;base64,${data.frame as string}`);
        if (typeof data.detections === 'number') setDetections(data.detections);
        if (typeof data.occupied === 'number') setOccupied(data.occupied);
        if (typeof data.available === 'number') setAvailable(data.available);
        if (typeof data.calibrated === 'boolean') setCalibrated(data.calibrated);
        if (typeof data.calibration_active === 'boolean') setCalibrationActive(data.calibration_active);
      } catch {

      }
    };

    ws.onerror = () => {
      clearTimeout(failTimer);
      if (!cancelled) {
        setConn('disconnected');
        // Don't leave a stale last-good frame on screen once the connection
        // drops - it can look like the (possibly calibrated) overlay is
        // still live when it's actually just a frozen old frame.
        setFrame(null);
        setDetections(0);
        setCalibrationActive(false);
      }
    };

    ws.onclose = () => {
      clearTimeout(failTimer);
      if (!cancelled) {
        setConn('disconnected');
        setFrame(null);
        setDetections(0);
        setCalibrationActive(false);
        // Auto-retry - camera/model init can be slow or momentarily busy
        // (e.g. briefly held by another process), so keep trying instead of
        // requiring a manual page refresh.
        retryTimer = setTimeout(() => setRetryTick(t => t + 1), 4000);
      }
    };

    return () => {
      cancelled = true;
      clearTimeout(failTimer);
      clearTimeout(retryTimer);
      try { ws.close(); } catch {}
    };
  }, [zone, cameraIndex, enabled, retryTick]);

  return { conn, frame, detections, occupied, available, calibrated, calibrationActive, lastError };
}

export function useSlotOccupancy(zone: Zone) {
  const map = PARKING_MAPS[zone];
  const [conn, setConn] = useState<ConnState>('connecting');
  const [slotStatus, setSlotStatus] = useState<Record<string, SlotStatus>>({});
  const [summary, setSummary] = useState<Record<string, CategoryInfo>>({});
  const [updatedAt, setUpdatedAt] = useState('');

  useEffect(() => {
    let cancelled = false;
    let poll: ReturnType<typeof setInterval> | null = null;

    if (!SLOT_HOST) {
      setConn('disconnected');
      return;
    }

    const fetchLive = async () => {
      try {
        const data = await apiGetLiveSlots(zone);
        if (cancelled) return;

        const next: Record<string, SlotStatus> = {};
        data.slots.forEach(s => { next[s.id] = s.status as SlotStatus; });

        setSlotStatus(next);
        setSummary(data.category_summary as unknown as Record<string, CategoryInfo>);
        setUpdatedAt(data.timestamp);
        setConn('live');
      } catch {
        if (!cancelled) setConn('disconnected');
      }
    };

    setConn('connecting');
    void fetchLive();
    poll = setInterval(() => { void fetchLive(); }, 2500);

    return () => {
      cancelled = true;
      if (poll) clearInterval(poll);
    };
  }, [zone]);

  const total = map.slots.length;
  const occupied = Object.values(slotStatus).filter(s => s === 'Occupied').length;

  return { conn, map, slotStatus, summary, updatedAt, total, occupied, available: total - occupied };
}