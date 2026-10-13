import { useEffect, useRef, useState } from 'react';
import type { Zone } from '@/types';
import { getToken } from '@/lib/backendApi';
import type { ConnState } from '@/hooks/useLiveDetection';

const SLOT_HOST = process.env.NEXT_PUBLIC_SLOT_HOST || '';

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