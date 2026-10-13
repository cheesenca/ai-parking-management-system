import type {
  AuthUser,
  Member,
  ManagedUser,
  EntryLog,
  ZoneCapacity,
  ForecastDay,
  OccupancyPoint,
  PendingReview,
} from '@/types';

<<<<<<< HEAD
const BASE =
  typeof window !== 'undefined'
    ? `http://${process.env.NEXT_PUBLIC_BACKEND_HOST || 'localhost:8000'}`
    : `http://${process.env.NEXT_PUBLIC_BACKEND_HOST || 'localhost:8000'}`;
=======
// Both branches of the old ternary here produced the same string, so the
// `typeof window` check was dead code — simplified to the value itself.
const BASE = `http://${process.env.NEXT_PUBLIC_BACKEND_HOST || 'localhost:8000'}`;
>>>>>>> origin/master

export const TOKEN_KEY = 'aips_token';
export const USER_KEY  = 'aips_user';

export function getToken(): string {
  if (typeof window === 'undefined') return '';
  return sessionStorage.getItem(TOKEN_KEY) || '';
}

export function setToken(token: string) { 
  sessionStorage.setItem(TOKEN_KEY, token); 
}

export function clearSession() {
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(USER_KEY);
}

async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
  skipAuth = false,
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(token && !skipAuth ? { Authorization: `Bearer ${token}` } : {}),
    ...(init.headers as Record<string, string> | undefined),
  };
  const res = await fetch(`${BASE}${path}`, { ...init, headers });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const detail = (err as { detail?: unknown }).detail;
    let message: string;
    if (typeof detail === 'string' && detail) {
      message = detail;
    } else if (Array.isArray(detail)) {
      message = detail.map(d => (d && typeof d === 'object' && 'msg' in d ? String((d as { msg: unknown }).msg) : JSON.stringify(d))).join('; ');
    } else if (detail && typeof detail === 'object') {
      message = JSON.stringify(detail);
    } else {
      message = `HTTP ${res.status}`;
    }
    throw new Error(message);
  }

  if (res.status === 204) return undefined as unknown as T;
  return res.json() as Promise<T>;
}

export async function apiIsOnline(): Promise<boolean> {
  try {
    const res = await fetch(`${BASE}/health`, {
      cache: 'no-store',
      signal: AbortSignal.timeout(3000),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function apiLogin(
  username: string,
  password: string,
): Promise<AuthUser> {
  const data = await apiFetch<{ access_token: string; user: AuthUser }>(
    '/api/v1/auth/login',
    { method: 'POST', body: JSON.stringify({ username, password }) },
    true,
  );

  setToken(data.access_token);
  return data.user;
}

<<<<<<< HEAD
export async function apiForgotPassword(
  email: string,
  new_password: string,
): Promise<{ message: string }> {
  return apiFetch<{ message: string }>(
    '/api/v1/auth/forgot-password',
    { method: 'POST', body: JSON.stringify({ email, new_password }) },
=======
// Two-step reset flow, matching the backend change: requesting a reset no
// longer sets the password directly (that let anyone with an email take
// over an account). Step 1 issues a token, step 2 consumes it.
export async function apiRequestPasswordReset(
  email: string,
): Promise<{ message: string; token?: string; expires_in_minutes?: number }> {
  return apiFetch(
    '/api/v1/auth/forgot-password',
    { method: 'POST', body: JSON.stringify({ email }) },
    true,
  );
}

export async function apiConfirmPasswordReset(
  email: string,
  token: string,
  new_password: string,
): Promise<{ message: string }> {
  return apiFetch<{ message: string }>(
    '/api/v1/auth/reset-password',
    { method: 'POST', body: JSON.stringify({ email, token, new_password }) },
>>>>>>> origin/master
    true,
  );
}

export async function apiGetUsers(): Promise<ManagedUser[]> {
  return apiFetch<ManagedUser[]>('/api/v1/auth/users');
}

export async function apiCreateUser(data: {
  username: string;
  email: string;
  password: string;
  role: string;
  location?: string;
}): Promise<ManagedUser> {
  return apiFetch<ManagedUser>('/api/v1/auth/users', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function apiUpdateUser(
  admin_id: number,
  data: Partial<{ username: string; email: string; password: string; role: string; location: string }>,
): Promise<ManagedUser> {
  return apiFetch<ManagedUser>(`/api/v1/auth/users/${admin_id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function apiDeleteUser(admin_id: number): Promise<void> {
  return apiFetch<void>(`/api/v1/auth/users/${admin_id}`, { method: 'DELETE' });
}

export async function apiGetMembers(params?: {
  zone?: string;
  category?: string;
  search?: string;
  sort?: 'asc' | 'desc';
  page?: number;
  page_size?: number;
}): Promise<{ items: Member[]; total: number; page: number; page_size: number }> {
  const q = new URLSearchParams();
  if (params?.zone && params.zone !== 'All') q.set('zone', params.zone);
  if (params?.category && params.category !== 'All') q.set('category', params.category);
  if (params?.search) q.set('search', params.search);
  if (params?.sort) q.set('sort', params.sort);
  if (params?.page) q.set('page', String(params.page));
  if (params?.page_size) q.set('page_size', String(params.page_size));
  return apiFetch(`/api/v1/members?${q}`);
}

export async function apiCreateMember(data: Omit<Member, 'member_id' | 'position' | 'last_in' | 'last_out'>): Promise<Member> {
  return apiFetch<Member>('/api/v1/members', { method: 'POST', body: JSON.stringify(data) });
}

export async function apiUpdateMember(id: number, data: Partial<Member>): Promise<Member> {
  return apiFetch<Member>(`/api/v1/members/${id}`, { method: 'PUT', body: JSON.stringify(data) });
}

export async function apiDeleteMember(id: number): Promise<void> {
  return apiFetch<void>(`/api/v1/members/${id}`, { method: 'DELETE' });
}

export async function apiImportMembers(rows: Partial<Member>[]): Promise<{ created: number; errors: string[] }> {
  return apiFetch('/api/v1/members/import', { method: 'POST', body: JSON.stringify({ rows }) });
}

export async function apiGetLogs(
  zone?: string,
  limit = 100,
): Promise<EntryLog[]> {
  const q = new URLSearchParams({ limit: String(limit) });
  if (zone) q.set('zone', zone);
<<<<<<< HEAD
  
  try {
    return await apiFetch<EntryLog[]>(`/api/v1/slots/logs?${q}`);
  } catch (err) {
    return await apiFetch<EntryLog[]>(`/api/v1/slots/logs?${q}`);
  }
=======

  // Previously this retried the identical failing call once and just
  // re-threw the same error — removed, since apiFetch already surfaces a
  // clear error message for callers to handle.
  return apiFetch<EntryLog[]>(`/api/v1/slots/logs?${q}`);
>>>>>>> origin/master
}

export async function apiGetLiveSlots(zone: string) {
  return apiFetch<{
    zone: string;
    timestamp: string;
    slots: { id: string; status: string; category: string }[];
    category_summary: Record<string, { used: number; total: number; available: number; rate_pct: number }>;
    total_capacity: number;
    total_occupied: number;
    total_available: number;
    overall_rate_pct: number;
  }>(`/api/v1/slots/live?zone=${zone}`);
}

export interface CalibrationSlot {
  id: string;
  category: 'Employee' | 'Vendor' | 'Visitor';
  polygon: [number, number][];
}

export async function apiGetCalibrationDefaults(zoneKey: string): Promise<{
  zone: string;
  default_slots: { id: string; category: string }[];
  slots: CalibrationSlot[];
}> {
  return apiFetch(`/api/v1/slots/calibration/${zoneKey}/defaults`);
}

export async function apiGetCalibrationSnapshot(zoneKey: string): Promise<{
  zone: string;
  width: number;
  height: number;
  image: string; 
  default_slots: { id: string; category: string }[];
}> {
  return apiFetch(`/api/v1/slots/calibration/${zoneKey}/snapshot`);
}

export async function apiGetCalibration(zoneKey: string): Promise<{
  zone: string;
  slots: CalibrationSlot[];
  calibrated: boolean;
}> {
  return apiFetch(`/api/v1/slots/calibration/${zoneKey}`);
}

export async function apiSaveCalibration(zoneKey: string, slots: CalibrationSlot[], referenceImage?: string) {
  return apiFetch(`/api/v1/slots/calibration/${zoneKey}`, {
    method: 'POST',
    body: JSON.stringify({ slots, reference_image: referenceImage }),
  });
}

export async function apiUpdateZoneCapacity(
  zoneKey: string,
  data: { employee_capacity?: number; vendor_capacity?: number; visitor_capacity?: number },
): Promise<{
  zone: string;
  total_capacity: number;
  employee_capacity: number;
  vendor_capacity: number;
  visitor_capacity: number;
}> {
  return apiFetch(`/api/v1/slots/zones/${zoneKey}/capacity`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function apiManualApprovePlate(payload: {
  plate: string;
  zone: string;
  event_type: 'entry' | 'exit';
  timestamp: string;
  original_confidence?: number;
  review_id?: number;
}): Promise<{
  recorded: boolean;
  plate: string;
  classification: 'Member' | 'Visitor';
  member: Member | null;
}> {
  return apiFetch('/api/v1/ocr/manual-approve', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function apiGetPendingReviews(params?: {
  zone?: string;
  status?: string;
  page?: number;
  page_size?: number;
}): Promise<{ items: PendingReview[]; total: number; page: number; page_size: number }> {
  const q = new URLSearchParams();
  if (params?.zone) q.set('zone', params.zone);
  if (params?.status) q.set('status', params.status);
  if (params?.page) q.set('page', String(params.page));
  if (params?.page_size) q.set('page_size', String(params.page_size));
  return apiFetch(`/api/v1/ocr/pending-reviews?${q}`);
}

export async function apiDismissPendingReview(reviewId: number): Promise<{ dismissed: boolean; review_id: number }> {
  return apiFetch(`/api/v1/ocr/pending-reviews/${reviewId}/dismiss`, { method: 'POST' });
}

export async function apiForecastZones(): Promise<ZoneCapacity[]> {
  return apiFetch<ZoneCapacity[]>('/api/v1/forecast/zones');
}

export async function apiForecastDashboard(
  zone_id: number,
  days = 30,
): Promise<{ zone_id: number; zone_name: string; summary: ZoneCapacity; data: ForecastDay[] }> {
  return apiFetch(`/api/v1/forecast/dashboard/${zone_id}?days=${days}`);
}

export async function apiOccupancyHistory(
  zone_id: number,
  hours = 24,
): Promise<OccupancyPoint[]> {
  return apiFetch<OccupancyPoint[]>(`/api/v1/forecast/occupancy/history/${zone_id}?hours=${hours}`);
}