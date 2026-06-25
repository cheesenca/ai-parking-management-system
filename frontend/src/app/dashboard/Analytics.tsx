'use client';
import { useState, useEffect, useCallback } from 'react';
import {
  AreaChart, 
  Area, 
  BarChart, 
  Bar,
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer, 
  Legend,
} from 'recharts';
import { RefreshCw, Download } from 'lucide-react';
import { apiForecastZones, apiForecastDashboard, apiOccupancyHistory } from '@/lib/backendApi';
import type { ZoneCapacity, ForecastDay, OccupancyPoint } from '@/lib/types';

export default function AnalyticsPage() {
  const [zones, setZones] = useState<ZoneCapacity[]>([]);
  const [selectedZoneId, setZoneId] = useState<number | null>(null);
  const [days, setDays] = useState(30);
  const [forecast, setForecast] = useState<ForecastDay[]>([]);
  const [history, setHistory] = useState<OccupancyPoint[]>([]);
  const [zoneSummary, setZoneSummary] = useState<ZoneCapacity | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    apiForecastZones()
      .then(data => {
        setZones(data);
        if (data.length > 0) setZoneId(data[0].zone_id);
      })
      .catch(e => setError((e as Error).message));
  }, []);

  const loadData = useCallback(async () => {
    if (selectedZoneId === null) return;
    setLoading(true); setError('');
    try {
      const [dash, hist] = await Promise.all([
        apiForecastDashboard(selectedZoneId, days),
        apiOccupancyHistory(selectedZoneId, days * 24),
      ]);
      setForecast(dash.data);
      setZoneSummary(dash.summary);
      setHistory(hist);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [selectedZoneId, days]);

  useEffect(() => { void loadData(); }, [loadData]);

  const dailyHistory = (() => {
    const map = new Map<string, OccupancyPoint[]>();
    history.forEach(h => {
      const day = h.timestamp.slice(0, 10);
      if (!map.has(day)) map.set(day, []);
      map.get(day)!.push(h);
    });
    return [...map.entries()].map(([date, pts]) => ({
      date,
      avg_rate: Math.round(pts.reduce((s, p) => s + p.overall_rate_pct, 0) / pts.length),
      employee: Math.round(pts.reduce((s, p) => s + p.employee_used, 0) / pts.length),
      vendor: Math.round(pts.reduce((s, p) => s + p.vendor_used, 0) / pts.length),
      visitor: Math.round(pts.reduce((s, p) => s + p.visitor_used, 0) / pts.length),
    }));
  })();

  const exportCSV = () => {
    const rows = [
      ['Date', 'Predicted', 'Avg Rate %', 'Employee', 'Vendor', 'Visitor', 'Peak Start', 'Peak End'],
      ...forecast.map(r => [r.date, r.predicted_demand, r.avg_occupancy_rate.toFixed(1), r.employee, r.vendor, r.visitor, r.peak_hour_start, r.peak_hour_end]),
    ];
    const csv = rows.map(r => r.join(',')).join('\n');
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
    a.download = `aips_forecast_zone${selectedZoneId}_${new Date().toISOString().slice(0,10)}.csv`;
    a.click();
  };

  const kpiColor = (rate: number) => rate >= 85 ? 'var(--red)' : rate >= 65 ? 'var(--amber)' : 'var(--teal)';
  const avgRate = forecast.length ? Math.round(forecast.reduce((s, r) => s + r.avg_occupancy_rate, 0) / forecast.length) : 0;
  const peakDemand = forecast.length ? Math.max(...forecast.map(r => r.predicted_demand)) : 0;

  return (
    <div style={{ padding: '28px 32px' }} className="fadein">
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 800, color: 'var(--ink)', letterSpacing: '-0.02em', marginBottom: 4 }}>Analytics & Forecast</h1>
          <p style={{ fontSize: 13, color: 'var(--muted)' }}>Predictive occupancy analytics powered by backend ML model</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={() => void loadData()} className="btn-secondary" style={{ fontSize: 12 }} disabled={loading}>
            <RefreshCw size={13} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
          </button>
          <button onClick={exportCSV} className="btn-secondary" style={{ fontSize: 12 }} disabled={!forecast.length}>
            <Download size={13} /> Export CSV
          </button>
        </div>
      </div>

      {error && (
        <div style={{ padding: '12px 16px', borderRadius: 10, background: 'var(--danger-bg)', border: '1px solid var(--red-mid)', color: 'var(--danger-text)', fontSize: 13, marginBottom: 20 }}>
          {error} — Ensure the backend is running and the AnalyticsData table already contains data.
        </div>
      )}

      {/* Controls */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 22, flexWrap: 'wrap' }}>
        <select value={selectedZoneId ?? ''} onChange={e => setZoneId(Number(e.target.value))}
          style={{ padding: '9px 12px', borderRadius: 9, border: '1px solid var(--border)', background: '#fff', color: 'var(--ink)', fontSize: 13, outline: 'none' }}>
          {zones.map(z => <option key={z.zone_id} value={z.zone_id}>{z.zone_name}</option>)}
        </select>
        {[7, 14, 30, 90].map(d => (
          <button key={d} onClick={() => setDays(d)} style={{
            padding: '9px 16px', borderRadius: 9, border: '1px solid', fontSize: 12, fontWeight: 700, cursor: 'pointer',
            borderColor: days === d ? 'var(--red)' : 'var(--border)',
            background: days === d ? 'var(--red)' : '#fff',
            color: days === d ? '#fff' : 'var(--text)',
          }}>{d}D</button>
        ))}
      </div>

      {/* KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 22 }}>
        {[
          { label: 'Avg Occupancy Rate', value: loading ? '—' : `${avgRate}%`, color: kpiColor(avgRate) },
          { label: 'Peak Demand', value: loading ? '—' : peakDemand.toString(), color: 'var(--ink)' },
          { label: 'Total Capacity', value: loading ? '—' : (zoneSummary?.total_capacity ?? '—').toString(), color: 'var(--ink)' },
          { label: 'Now Available', value: loading ? '—' : (zoneSummary?.total_available ?? '—').toString(), color: 'var(--teal)' },
        ].map(k => (
          <div key={k.label} className="card" style={{ padding: '16px 18px' }}>
            <div className="label" style={{ marginBottom: 8 }}>{k.label}</div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 26, fontWeight: 700, color: k.color }}>{k.value}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 22 }}>
        {/* Predicted Demand Chart */}
        <div className="card" style={{ padding: 20 }}>
          <div style={{ fontWeight: 800, fontSize: 13, marginBottom: 16 }}>Predicted Demand ({days}D)</div>
          {loading ? (
            <div style={{ height: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--muted)', fontSize: 13 }}>Memuat…</div>
          ) : forecast.length === 0 ? (
            <div style={{ height: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--muted)', fontSize: 13 }}>Belum ada data forecast di database.</div>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={forecast.slice(-30)} margin={{ top: 5, right: 5, left: -20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={d => d.slice(5)} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip formatter={(v) => [v, 'Predicted']} labelFormatter={d => d} />
                <Area type="monotone" dataKey="predicted_demand" stroke="#E5002B" fill="#E5002B22" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Category Breakdown Chart */}
        <div className="card" style={{ padding: 20 }}>
          <div style={{ fontWeight: 800, fontSize: 13, marginBottom: 16 }}>Category Breakdown (avg/day)</div>
          {loading ? (
            <div style={{ height: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--muted)', fontSize: 13 }}>Memuat…</div>
          ) : forecast.length === 0 ? (
            <div style={{ height: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--muted)', fontSize: 13 }}>Belum ada data.</div>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={forecast.slice(-14)} margin={{ top: 5, right: 5, left: -20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={d => d.slice(5)} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="employee" name="Employee" fill="#102A43" radius={[3,3,0,0]} />
                <Bar dataKey="vendor" name="Vendor" fill="#E5002B" radius={[3,3,0,0]} />
                <Bar dataKey="visitor" name="Visitor" fill="#F5A400" radius={[3,3,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Historical Occupancy */}
      {dailyHistory.length > 0 && (
        <div className="card" style={{ padding: 20, marginBottom: 22 }}>
          <div style={{ fontWeight: 800, fontSize: 13, marginBottom: 16 }}>Actual Occupancy Rate History (%)</div>
          <ResponsiveContainer width="100%" height={160}>
            <AreaChart data={dailyHistory} margin={{ top: 5, right: 5, left: -20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={d => d.slice(5)} />
              <YAxis tick={{ fontSize: 10 }} domain={[0, 100]} />
              <Tooltip formatter={(v) => [`${v}%`, 'Avg Rate']} />
              <Area type="monotone" dataKey="avg_rate" stroke="#159A72" fill="#159A7222" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Forecast Table */}
      <div className="card" style={{ overflow: 'hidden' }}>
        <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--border)', fontWeight: 800, fontSize: 12, letterSpacing: '.04em' }}>
          FORECAST DATA TABLE
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table className="data-table">
            <thead><tr>
              <th>Date</th><th>Predicted</th><th>Occ. Rate</th><th>Employee</th><th>Vendor</th><th>Visitor</th><th>Peak Hours</th><th>Status</th>
            </tr></thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={8} style={{ textAlign: 'center', padding: 32, color: 'var(--muted)' }}>Memuat…</td></tr>
              ) : forecast.length === 0 ? (
                <tr><td colSpan={8} style={{ textAlign: 'center', padding: 32, color: 'var(--muted)' }}>
                  No data available, run the ML forecasting pipeline to populate the AnalyticsData table.
                </td></tr>
              ) : forecast.map(r => {
                const rate = r.avg_occupancy_rate;
                const statusColor = rate >= 85 ? 'var(--red)' : rate >= 65 ? 'var(--amber)' : 'var(--teal)';
                const statusLabel = rate >= 85 ? 'High'       : rate >= 65 ? 'Moderate'     : 'Normal';
                return (
                  <tr key={r.date}>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{r.date}</td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 700 }}>{r.predicted_demand}</td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <div style={{ flex: 1, height: 4, borderRadius: 2, background: 'var(--border)' }}>
                          <div style={{ height: '100%', borderRadius: 2, width: `${Math.min(rate, 100)}%`, background: statusColor }} />
                        </div>
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: statusColor, fontWeight: 600, width: 36 }}>
                          {rate.toFixed(1)}%
                        </span>
                      </div>
                    </td>
                    <td>{r.employee}</td>
                    <td>{r.vendor}</td>
                    <td>{r.visitor}</td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>{r.peak_hour_start}–{r.peak_hour_end}</td>
                    <td>
                      <span style={{ fontSize: 11, fontWeight: 700, padding: '3px 8px', borderRadius: 6, background: `${statusColor}22`, color: statusColor, border: `1px solid ${statusColor}44` }}>
                        {statusLabel}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
