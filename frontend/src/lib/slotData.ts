import type { Zone, Category } from './types';

export type SlotStatus = 'Occupied' | 'Available';

export interface SlotDef {
  id: string;
  category: Category;
  polygon: [number, number][];
}

export interface ParkingMap {
  zone: Zone;
  zone_label: string;
  camera_id: string;
  frame: { 
    w: number; 
    h: number; 
  };
  slots: SlotDef[];
  background?: string;
}

export interface CategoryInfo {
  used: number;
  total: number;
  available: number;
  rate_pct: number;
}

export interface ZoneUpdate {
  zone: Zone;
  timestamp: string;
  slots: { 
    id: string; 
    status: SlotStatus; 
    category: Category; 
  }[];
  category_summary: Record<Category, CategoryInfo>;
}

const FRAME = { 
  w: 960, 
  h: 540, 
};

function gridSlots(prefix: string, rows: { y: number; count: number; category: Category }[]): SlotDef[] {
  const slots: SlotDef[] = [];
  const marginX = 70;
  const gapX = 14;
  const slotH = 86;
  
  rows.forEach((row, rIdx) => {
    const usableW = FRAME.w - marginX * 2;
    const slotW = Math.floor((usableW - gapX * (row.count - 1)) / row.count);
    for (let i = 0; i < row.count; i++) {
      const x = marginX + i * (slotW + gapX), y = row.y;
      slots.push({
        id: `${prefix}${rIdx + 1}-${i + 1}`,
        category: row.category,
        polygon: [[x, y], [x + slotW, y], [x + slotW, y + slotH], [x, y + slotH]],
      });
    }
  });
  return slots;
}

export const PARKING_MAPS: Record<Zone, ParkingMap> = {
  west: {
    zone: 'west', zone_label: 'West Plant', camera_id: 'CAM_WEST_01', frame: FRAME,
    background: '/plant-maps/west.png', 
    slots: gridSlots('W', [
      { y: 60, count: 10, category: 'Employee' },
      { y: 170, count: 10, category: 'Employee' },
      { y: 300, count: 8, category: 'Vendor' },
      { y: 410, count: 5, category: 'Visitor' },
    ]),
  },
  east: {
    zone: 'east', zone_label: 'East Plant', camera_id: 'CAM_EAST_01', frame: FRAME,
    background: '/plant-maps/east.png', 
    slots: gridSlots('E', [
      { y: 60, count: 10, category: 'Employee' },
      { y: 170, count: 10, category: 'Employee' },
      { y: 300, count: 8, category: 'Vendor' },
      { y: 410, count: 5, category: 'Visitor' },
    ]),
  },
  eastwest: {
    zone: 'eastwest', zone_label: 'East & West Plant', camera_id: 'CAM_EW_01', frame: FRAME,
    background: '/plant-maps/eastwest.png',
    slots: gridSlots('EW', [
      { y: 80, count: 10, category: 'Employee' },
      { y: 210, count: 8, category: 'Vendor' },
      { y: 340, count: 5, category: 'Visitor' },
    ]),
  },
};

export const CAPACITY_CONFIG: Record<Zone, Record<Category, number>> = {
  west: { Employee: 100, Vendor: 20, Visitor: 10 },
  east: { Employee: 100, Vendor: 20, Visitor: 10 },
  eastwest: { Employee: 50, Vendor: 10, Visitor: 5 },
};

export function getCategorySummary(map: ParkingMap, slotStatus: Record<string, SlotStatus>): Record<Category, CategoryInfo> {
  const cfg = CAPACITY_CONFIG[map.zone];
  const occupiedByCat: Record<string, number> = {};

  map.slots.forEach(s => {
    if (slotStatus[s.id] === 'Occupied')
      occupiedByCat[s.category] = (occupiedByCat[s.category] || 0) + 1;
  });
  
  const summary = {} as Record<Category, CategoryInfo>;
  (Object.keys(cfg) as Category[]).forEach(cat => {
    const total = cfg[cat], used = occupiedByCat[cat] || 0;
    summary[cat] = { used, total, available: Math.max(0, total - used), rate_pct: total ? Math.round(used / total * 1000) / 10 : 0 };
  });
  return summary;
}
