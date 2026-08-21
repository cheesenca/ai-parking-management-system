'use client';

import { useState, useEffect, useMemo, useCallback, Fragment } from 'react';
import { AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { AlertTriangle, HelpCircle, FileText, X, Flame, ShieldAlert, ShieldCheck } from 'lucide-react';
import { apiForecastZones, apiForecastDashboard } from '@/lib/backendApi';
import type { ZoneCapacity, ForecastDay } from '@/types';
import ForecastReportPrint from '@/components/ForecastReportPrint';

export type ZoneKey = 'west' | 'east' | 'eastwest';
type Granularity = 'daily' | 'weekly' | 'monthly';

export const ZONE_KEYS: ZoneKey[] = ['west', 'east', 'eastwest'];
export const ZONE_LABELS: Record<ZoneKey, string> = { west: 'West', east: 'East', eastwest: 'East & West' };

export interface ZoneDay {
  demand: number;
  rate: number;
  employee: number;
  vendor: number;
  visitor: number;
  peakStart: string;
  peakEnd: string;
}
export type MergedRow = { date: string } & Partial<Record<ZoneKey, ZoneDay>>;

export function statusFor(rate: number): 'Normal' | 'Warning' | 'Full' {
  if (rate >= 90) return 'Full';
  if (rate >= 70) return 'Warning';
  return 'Normal';
}
const statusClass: Record<string, string> = {
  Normal: 'status-normal', Warning: 'status-warning', Full: 'status-full',
};

export function toISO(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}
export function addDays(iso: string, n: number): string {
  const [y, m, d] = iso.split('-').map(Number);
  return toISO(new Date(y, m - 1, d + n));
}
export function monthRange(iso: string): [string, string] {
  const [y, m] = iso.split('-').map(Number);
  return [toISO(new Date(y, m - 1, 1)), toISO(new Date(y, m, 0))];
}

const GRANULARITY_OPTIONS: { value: Granularity; label: string }[] = [
  { value: 'daily', label: 'Daily Forecast' },
  { value: 'weekly', label: 'Weekly Forecast' },
  { value: 'monthly', label: 'Monthly Forecast' },
];

export default function AnalyticsPage() {
  const [zones, setZones] = useState<ZoneCapacity[]>([]);
  const [merged, setMerged] = useState<MergedRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [refreshedAt, setRefreshedAt] = useState('');
  const [selectedDate, setSelectedDate] = useState(() => addDays(toISO(new Date()), 1));
  const [granularity, setGranularity] = useState<Granularity>('daily');
  const [alertDismissed, setAlertDismissed] = useState(false);
  const [guideOpen, setGuideOpen] = useState(false);

  useEffect(() => {
    apiForecastZones().then(setZones).catch(e => setError((e as Error).message));
  }, []);

  const zoneIds = useMemo(() => ({
    west: zones.find(z => z.zone === 'west')?.zone_id,
    east: zones.find(z => z.zone === 'east')?.zone_id,
    eastwest: zones.find(z => z.zone === 'eastwest')?.zone_id,
  }), [zones]);

  const capacityOf = useCallback((zone: ZoneKey) => zones.find(z => z.zone === zone)?.total_capacity ?? 0, [zones]);

  const loadData = useCallback(async () => {
    if (!zoneIds.west || !zoneIds.east || !zoneIds.eastwest) return;
    setLoading(true); setError('');
    try {
      const [w, e, ew] = await Promise.all([
        apiForecastDashboard(zoneIds.west, 365),
        apiForecastDashboard(zoneIds.east, 365),
        apiForecastDashboard(zoneIds.eastwest, 365),
      ]);
      const map = new Map<string, MergedRow>();
      const put = (zoneKey: ZoneKey, rows: ForecastDay[]) => {
        rows.forEach(r => {
          const row = map.get(r.date) ?? { date: r.date };
          row[zoneKey] = {
            demand: r.predicted_demand, rate: r.avg_occupancy_rate,
            employee: r.employee, vendor: r.vendor, visitor: r.visitor,
            peakStart: r.peak_hour_start, peakEnd: r.peak_hour_end,
          };
          map.set(r.date, row);
        });
      };
      put('west', w.data); put('east', e.data); put('eastwest', ew.data);
      setMerged([...map.values()].sort((a, b) => a.date.localeCompare(b.date)));
      setRefreshedAt(new Date().toLocaleString());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [zoneIds.west, zoneIds.east, zoneIds.eastwest]);

  useEffect(() => { void loadData(); }, [loadData]);

  const dailyRow = merged.find(r => r.date === selectedDate);
  const weekEnd = addDays(selectedDate, 6);
  const weekRows = merged.filter(r => r.date >= selectedDate && r.date <= weekEnd);
  const [monthStart, monthEnd] = monthRange(selectedDate);
  const monthRows = merged.filter(r => r.date >= monthStart && r.date <= monthEnd);

  const windowRows = useMemo(() => {
    switch (granularity) {
      case 'daily': return dailyRow ? [dailyRow] : [];
      case 'weekly': return weekRows;
      case 'monthly': return monthRows;
    }
  }, [granularity, dailyRow, weekRows, monthRows, merged, selectedDate]);

  const zoneDayEntries = windowRows.flatMap(r => ZONE_KEYS.map(z => r[z]).filter((d): d is ZoneDay => !!d));
  const avgOccupancy = zoneDayEntries.length
    ? Math.round(zoneDayEntries.reduce((s, d) => s + d.rate, 0) / zoneDayEntries.length)
    : 0;
  const riskEntries = zoneDayEntries.filter(d => statusFor(d.rate) !== 'Normal');
  const fullCount = zoneDayEntries.filter(d => statusFor(d.rate) === 'Full').length;
  const warningCount = riskEntries.length - fullCount;

  const dailyDemand = (dailyRow?.west?.demand ?? 0) + (dailyRow?.east?.demand ?? 0);

  const areaPerformanceData = ZONE_KEYS.map(z => ({
    zone: ZONE_LABELS[z],
    rate: dailyRow?.[z]?.rate ?? 0,
  }));

  const trendData = useMemo(() => {
    if (granularity !== 'monthly') {
      const bucketSpec: Record<'daily' | 'weekly', { size: number; count: number }> = {
        daily: { size: 1, count: 7 },
        weekly: { size: 7, count: 8 },
      };
      const { size, count } = bucketSpec[granularity];
      const forward = merged.filter(r => r.date >= selectedDate);
      const buckets: { date: string; demand: number }[] = [];
      for (let i = 0; i < forward.length && buckets.length < count; i += size) {
        const chunk = forward.slice(i, i + size);
        if (chunk.length < size) break;
        const demand = chunk.reduce((s, r) => s + (r.west?.demand ?? 0) + (r.east?.demand ?? 0), 0);
        buckets.push({ date: chunk[0].date, demand });
      }
      return buckets;
    }

    const forward = merged.filter(r => r.date >= selectedDate);
    const byMonth = new Map<string, { date: string; demand: number; count: number }>();
    for (const r of forward) {
      const key = r.date.slice(0, 7); // "YYYY-MM"
      const entry = byMonth.get(key) ?? { date: r.date, demand: 0, count: 0 };
      entry.demand += (r.west?.demand ?? 0) + (r.east?.demand ?? 0);
      entry.count += 1;
      byMonth.set(key, entry);
    }

    let buckets = [...byMonth.values()].sort((a, b) => a.date.localeCompare(b.date));

    if (buckets.length > 1) {
      const last = buckets[buckets.length - 1];
      const [, monthEnd] = monthRange(last.date);
      const daysInMonth = Number(monthEnd.slice(8, 10));
      const startDay = Number(last.date.slice(8, 10));
      const expectedCount = daysInMonth - startDay + 1;
      if (last.count < expectedCount) buckets = buckets.slice(0, -1);
    }

    return buckets.slice(0, 12).map(({ date, demand }) => ({ date, demand }));
  }, [merged, granularity, selectedDate]);

  const year = new Date(`${selectedDate}T00:00:00`).getFullYear();
  const recommendedAction = fullCount > 0
    ? 'Prepare overflow parking and prioritize full areas.'
    : warningCount > 0
      ? 'Monitor warning areas closely for the selected period.'
      : 'No immediate action needed — occupancy is within normal range.';

  return (
    <div className="kdash page-pad fadein">
      <div className="dashboard">
        {/* Topbar */}
        <div className="topbar">
          <div className="title-wrap">
            <h1>PTMI Parking Forecast Dashboard</h1>
            <p>Year {year} • Predictive Analytics</p>
          </div>
          <div className="top-controls">
            <div className="control-box">
              <input type="date" value={selectedDate} onChange={e => setSelectedDate(e.target.value)} />
            </div>
            <div className="control-box">
              <select value={granularity} onChange={e => setGranularity(e.target.value as Granularity)}>
                {GRANULARITY_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
            <button className="export-report-btn no-print" onClick={() => window.print()}>
              <FileText size={15} /> Export PDF
            </button>
            <button className="help-guide-btn no-print" onClick={() => setGuideOpen(true)}>
              <HelpCircle size={16} />
            </button>
          </div>
        </div>

        {error && (
          <div className="risk-alert" style={{ borderColor: 'var(--red-mid)', background: 'var(--danger-bg)' }}>
            <div className="risk-alert-left"><AlertTriangle /> <span>{error} — ensure the backend is running.</span></div>
          </div>
        )}

        {!error && !alertDismissed && riskEntries.length > 0 && (
          <div className="risk-alert">
            <div className="risk-alert-left">
              <AlertTriangle />
              <span>High Risk Alert: <strong>{riskEntries.length}</strong> warning/full records detected in selected period</span>
            </div>
            <button className="risk-alert-close" onClick={() => setAlertDismissed(true)}><X size={15} /></button>
          </div>
        )}

        {/* KPI row */}
        <div className="kpi-row">
          <div className={`kpi-card${granularity === 'daily' ? ' active-daily' : ''}`}>
            <div className="kpi-label">Daily Records</div>
            <div className="kpi-value">{loading ? '—' : dailyDemand.toLocaleString()}</div>
            <div className="kpi-sub">Selected day forecast</div>
          </div>
          <div className={`kpi-card${granularity === 'weekly' ? ' active-weekly' : ''}`}>
            <div className="kpi-label">Weekly Records</div>
            <div className="kpi-value">{loading ? '—' : weekRows.length}</div>
            <div className="kpi-sub">Weekly forecast rows</div>
          </div>
          <div className={`kpi-card${granularity === 'monthly' ? ' active-monthly' : ''}`}>
            <div className="kpi-label">Monthly Records</div>
            <div className="kpi-value">{loading ? '—' : monthRows.length}</div>
            <div className="kpi-sub">Monthly forecast rows</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Avg. Occupancy</div>
            <div className="kpi-value">{loading ? '—' : `${avgOccupancy}%`}</div>
            <div className="kpi-sub">Based on selected view</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Risk Areas</div>
            <div className="kpi-value">{loading ? '—' : riskEntries.length}</div>
            <div className="kpi-sub">Full / Warning status</div>
          </div>
        </div>

        {/* Upper grid: 2 charts */}
        <div className="main-content">
        <div className="upper-grid two">
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">Area Performance</h3>
              <span className="card-sub">Selected: {selectedDate}</span>
            </div>
            <div className="chart-area">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={areaPerformanceData} margin={{ top: 5, right: 5, left: -20, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--k-border)" />
                  <XAxis dataKey="zone" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} domain={[0, 100]} />
                  <Tooltip formatter={(v) => [`${v}%`, 'Occupancy']} />
                  <Bar dataKey="rate" fill="#F5A400" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="card area-card">
            <div className="card-header">
              <h3 className="card-title">Parking Occupancy Forecast Trend</h3>
              <span className="card-sub">{GRANULARITY_OPTIONS.find(o => o.value === granularity)?.label}</span>
            </div>
            <div className="chart-area">
              {trendData.length > 1 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={trendData} margin={{ top: 5, right: 5, left: -20, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--k-border)" />
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 10 }}
                      tickFormatter={d =>
                        granularity === 'monthly'
                          ? new Date(`${d}T00:00:00`).toLocaleDateString('en-US', { month: 'short', year: '2-digit' })
                          : d.slice(5)
                      }
                    />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip
                      formatter={(v) => [v, 'Predicted demand']}
                      labelFormatter={d =>
                        granularity === 'monthly'
                          ? new Date(`${d}T00:00:00`).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
                          : d
                      }
                    />
                    <Area type="monotone" dataKey="demand" stroke="#E5002B" fill="#E5002B22" strokeWidth={2} />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <div style={{ height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 6, color: 'var(--k-muted)' }}>
                  <div style={{ fontSize: 11, textAlign: 'center' }}>
                    Only one full {granularity} period exists in the current forecast horizon —
                    not enough data yet for a trend line.
                  </div>
                  {trendData.length === 1 && (
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: 11, color: 'var(--k-muted)' }}>{trendData[0].date}</div>
                      <div style={{ fontSize: 26, fontWeight: 800, color: 'var(--mattel-red)' }}>{trendData[0].demand.toLocaleString()}</div>
                      <div style={{ fontSize: 11 }}>predicted demand</div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Lower grid: insights + preview table */}
        <div className="lower-grid">
          <div className="card">
            <div className="card-header"><h3 className="card-title">Forecast Insights</h3></div>
            <div className="insight-list">
              <div className="insight-item">
                <div className="insight-icon blue"><Flame color="var(--mattel-red)" /></div>
                <div className="insight-text">
                  <strong>Full Area Count</strong>
                  <span>{fullCount} Full records in selected period</span>
                </div>
              </div>
              <div className="insight-item">
                <div className="insight-icon amber"><ShieldAlert color="var(--k-amber)" /></div>
                <div className="insight-text">
                  <strong>Warning Area Count</strong>
                  <span>{warningCount} Warning records in selected period</span>
                </div>
              </div>
              <div className="insight-item">
                <div className="insight-icon green"><ShieldCheck color="var(--k-teal)" /></div>
                <div className="insight-text">
                  <strong>Recommended Action</strong>
                  <span>{recommendedAction}</span>
                </div>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <h3 className="card-title">Forecast Preview (Next 7 Days)</h3>
              <span className="card-sub">Selected start date + 7 days</span>
            </div>
            <div className="preview-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Date</th><th>Total</th>
                    <th>West Av.</th><th>West St.</th>
                    <th>East Av.</th><th>East St.</th>
                    <th>E&amp;W Av.</th><th>E&amp;W St.</th>
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    <tr><td colSpan={8} style={{ textAlign: 'center', padding: 20 }}>Loading…</td></tr>
                  ) : weekRows.length === 0 ? (
                    <tr><td colSpan={8} style={{ textAlign: 'center', padding: 20 }}>No forecast data for this range.</td></tr>
                  ) : weekRows.map(r => {
                    const total = (r.west?.demand ?? 0) + (r.east?.demand ?? 0);
                    return (
                      <tr key={r.date}>
                        <td>{r.date}</td>
                        <td>{total.toLocaleString()}</td>
                        {ZONE_KEYS.map(z => {
                          const d = r[z];
                          const avail = d ? Math.max(0, Math.round(capacityOf(z) * (1 - d.rate / 100))) : 0;
                          const st = d ? statusFor(d.rate) : 'Normal';
                          return (
                            <Fragment key={z}>
                              <td>{d ? avail : '—'}</td>
                              <td><span className={`status-badge ${statusClass[st]}`}>{st}</span></td>
                            </Fragment>
                          );
                        })}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
        </div>

        <div className="footer">
          <span>Forecast horizon: next 365 days</span>
          <span>Data refreshed: {refreshedAt || '—'}</span>
        </div>
      </div>

      {guideOpen && (
        <div className="kdash-guide-overlay" onClick={() => setGuideOpen(false)}>
          <div className="kdash-guide-modal" onClick={e => e.stopPropagation()}>
            <div className="kdash-guide-header">
              <div>
                <h2>Dashboard Guide</h2>
                <p>How to read the parking forecast dashboard</p>
              </div>
              <button className="kdash-guide-close" onClick={() => setGuideOpen(false)}>×</button>
            </div>
            <div className="kdash-guide-body">
              <div className="kdash-guide-grid">
                <div className="kdash-guide-section">
                  <h3>Date &amp; Granularity</h3>
                  <p>Pick a start date, then choose Daily, Weekly, or Monthly to
                  change how the trend chart and KPI cards aggregate the forecast.</p>
                </div>
                <div className="kdash-guide-section">
                  <h3>Zones</h3>
                  <p>West and East are real, independently forecast zones. East &amp; West is a
                  combined view — its numbers are the sum of West and East, not a separate area.</p>
                </div>
                <div className="kdash-guide-section full">
                  <h3>Status badges</h3>
                  <div className="kdash-guide-badges">
                    <div className="kdash-guide-badge-row"><span className="status-badge status-normal">Normal</span> occupancy under 70%</div>
                    <div className="kdash-guide-badge-row"><span className="status-badge status-warning">Warning</span> occupancy 70–89%</div>
                    <div className="kdash-guide-badge-row"><span className="status-badge status-full">Full</span> occupancy 90% or above</div>
                  </div>
                </div>
              </div>
              <div className="kdash-guide-note">
                Forecasts are generated by a Prophet model retrained nightly on real entry/exit and
                occupancy history. Monthly horizons are naturally less precise than Daily/Weekly.
              </div>
            </div>
          </div>
        </div>
      )}

      <ForecastReportPrint merged={merged} selectedDate={selectedDate} zones={zones} />
    </div>
  );
}