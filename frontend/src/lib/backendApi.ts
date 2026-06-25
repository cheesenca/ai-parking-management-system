import type { AuthUser, Member, EntryLog, ZoneCapacity, ForecastDay, OccupancyPoint } from './types';

const BASE =
  typeof window !== 'undefined'
    ? `http://${process.env.NEXT_PUBLIC_BACKEND_HOST || 'localhost:8000'}`
    : `http://${process.env.NEXT_PUBLIC_BACKEND_HOST || 'localhost:8000'}`;

export const TOKEN_KEY = 'aips_token';
export const USER_KEY  = 'aips_user';

export function getToken(): string {
  if (typeof window === 'undefined') return '';
  return sessionStorage.getItem(TOKEN_KEY) || '';
}
export function setToken(token: string)  { sessionStorage.setItem(TOKEN_KEY, token); }
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
    throw new Error((err as { detail?: string }).detail || `HTTP ${res.status}`);
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
    '/api/auth/login',
    { method: 'POST', body: JSON.stringify({ username, password }) },
    true,
  );
  setToken(data.access_token);
  return data.user;
}

export async function apiGetMembers(params?: {
  zone?: string;
  category?: string;
  search?: string;
}): Promise<Member[]> {
  const q = new URLSearchParams();
  if (params?.zone && params.zone !== 'All')         q.set('zone', params.zone);
  if (params?.category && params.category !== 'All') q.set('category', params.category);
  if (params?.search)                                 q.set('search', params.search);
  return apiFetch<Member[]>(`/api/members?${q}`);
}

export async function apiCreateMember(data: Omit<Member, 'member_id' | 'position' | 'last_in' | 'last_out'>): Promise<Member> {
  return apiFetch<Member>('/api/members', { method: 'POST', body: JSON.stringify(data) });
}

export async function apiUpdateMember(id: number, data: Partial<Member>): Promise<Member> {
  return apiFetch<Member>(`/api/members/${id}`, { method: 'PUT', body: JSON.stringify(data) });
}

export async function apiDeleteMember(id: number): Promise<void> {
  return apiFetch<void>(`/api/members/${id}`, { method: 'DELETE' });
}

export async function apiImportMembers(rows: Partial<Member>[]): Promise<{ created: number; errors: string[] }> {
  return apiFetch('/api/members/import', { method: 'POST', body: JSON.stringify({ rows }) });
}

export async function apiGetLogs(
  zone?: string,
  limit = 100,
): Promise<EntryLog[]> {
  const q = new URLSearchParams({ limit: String(limit) });
  if (zone) q.set('zone', zone);
  return apiFetch<EntryLog[]>(`/api/slots/logs?${q}`);
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
  }>(`/api/slots/live?zone=${zone}`);
}

export async function apiForecastZones(): Promise<ZoneCapacity[]> {
  return apiFetch<ZoneCapacity[]>('/api/forecast/zones');
}

export async function apiForecastDashboard(
  zone_id: number,
  days = 30,
): Promise<{ zone_id: number; zone_name: string; summary: ZoneCapacity; data: ForecastDay[] }> {
  return apiFetch(`/api/forecast/dashboard/${zone_id}?days=${days}`);
}

export async function apiOccupancyHistory(
  zone_id: number,
  hours = 24,
): Promise<OccupancyPoint[]> {
  return apiFetch<OccupancyPoint[]>(`/api/forecast/occupancy/history/${zone_id}?hours=${hours}`);
}
