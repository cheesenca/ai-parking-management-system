export type Zone = 'west' | 'east' | 'eastwest';
export type Category = 'Employee' | 'Vendor' | 'Visitor';
export type Position = 'IN' | 'OUT';
export type Role = 'Admin' | 'Security';

export interface Member {
  member_id: number;
  kpk_number: string;
  name: string;
  registered_plant: Zone;
  plate_1: string;
  plate_2?: string;
  vehicle_type_1: string;
  vehicle_type_2?: string;
  sim_exp: string;
  stnk_exp_1: string;
  category: Category;
  position: Position;
  last_in: string;
  last_out: string;
}

export interface AuthUser {
  username: string;
  role: Role;
  location: Zone | null;
}

export interface ManagedUser {
  admin_id: number;
  username: string;
  email: string;
  role: Role;
  location: Zone | null;
}

export interface ZoneCapacity {
  zone: Zone;
  zone_name: string;
  zone_id: number;
  employee: { 
    total: number; 
    used: number; 
    available: number;
  };
  vendor: { 
    total: number; 
    used: number; 
    available: number; 
  };
  visitor: { 
    total: number; 
    used: number; 
    available: number; 
  };
  total_capacity: number;
  total_occupied: number;
  total_available: number;
  overall_rate_pct: number;
}

export interface EntryLog {
  log_id: number;
  plate_detected: string;
  name: string;
  kpk: string;
  category: Category;
  zone: string;
  time_scan: string;
  event_type: 'Entry' | 'Exit' | 'Denied';
  confidence_score: number;
  conf_pct: string;
  auth_method: 'AI_LPR' | 'KPK_Scan' | 'Manual_Security';
}

export interface ForecastDay {
  date: string;
  predicted_demand: number;
  avg_occupancy_rate: number;
  peak_hour_start: string;
  peak_hour_end: string;
  employee: number;
  vendor: number;
  visitor: number;
}

export interface OccupancyPoint {
  timestamp: string;
  total_occupied: number;
  total_capacity: number;
  overall_rate_pct: number;
  employee_used: number;
  vendor_used: number;
  visitor_used: number;
}

export interface PendingReview {
  review_id: number;
  plate_guess: string | null;
  confidence: number;
  conf_pct: string;
  vehicle_type: string | null;
  event_type: 'entry' | 'exit';
  zone: string;
  status: 'queued' | 'auto_resolved' | 'needs_review' | 'reviewed' | 'dismissed';
  captured_at: string;
  resolved_at: string | null;
  image_base64: string | null;
}