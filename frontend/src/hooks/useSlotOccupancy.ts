import { useEffect, useState } from 'react';
import type { Zone } from '@/types';
import { apiGetLiveSlots } from '@/lib/backendApi';
import { PARKING_MAPS, type SlotStatus, type CategoryInfo } from '@/lib/slotData';
import type { ConnState } from '@/hooks/useLiveDetection';

const SLOT_HOST = process.env.NEXT_PUBLIC_SLOT_HOST || '';

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