'use client';

import type { ZoneCapacity } from '@/lib/types';
import { ZONE_KEYS, ZONE_LABELS, statusFor, toISO, addDays, monthRange, type ZoneKey, type MergedRow } from '@/app/dashboard/Analytics';

interface Props {
  merged: MergedRow[];
  selectedDate: string;
  zones: ZoneCapacity[];
}

const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

function formatLong(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number);
  return `${d} ${MONTH_NAMES[m - 1]} ${y}`;
}

function isoWeek(iso: string): number {
  const [y, m, d] = iso.split('-').map(Number);
  const date = new Date(Date.UTC(y, m - 1, d));
  const dayNum = (date.getUTCDay() + 6) % 7; // Mon=0..Sun=6
  date.setUTCDate(date.getUTCDate() - dayNum + 3); // nearest Thursday
  const firstThursday = new Date(Date.UTC(date.getUTCFullYear(), 0, 4));
  const diff = date.getTime() - firstThursday.getTime();
  return 1 + Math.round(diff / (7 * 24 * 3600 * 1000));
}

function monthStartISO(y: number, m: number): string {
  return toISO(new Date(y, m, 1)); // m is 0-indexed here
}

type Priority = 'High' | 'Medium' | 'Low';
type Trend = 'Increase' | 'Decrease' | 'Stable';

export default function ForecastReportPrint({ merged, selectedDate, zones }: Props) {
  const capacityOf = (zone: ZoneKey) => zones.find(z => z.zone === zone)?.total_capacity ?? 0;
  const today = toISO(new Date());
  const [y, m] = selectedDate.split('-').map(Number);
  const forecastYear = y;

  // ---- Daily perspective ----
  const dailyRow = merged.find(r => r.date === selectedDate);
  const dailyTotal = (dailyRow?.west?.demand ?? 0) + (dailyRow?.east?.demand ?? 0);
  const dailyEntries = dailyRow ? ZONE_KEYS.map(z => dailyRow[z]).filter((d): d is NonNullable<typeof d> => !!d) : [];
  const dailyAvgOcc = dailyEntries.length ? Math.round(dailyEntries.reduce((s, d) => s + d.rate, 0) / dailyEntries.length) : 0;
  const dailyFull = dailyEntries.filter(d => statusFor(d.rate) === 'Full').length;
  const dailyWarning = dailyEntries.filter(d => statusFor(d.rate) === 'Warning').length;
  const dailyCondition = dailyFull > 0 ? 'High Risk' : dailyWarning > 0 ? 'Needs Attention' : 'Stable';
  const dailyAction = dailyFull > 0
    ? 'Prepare overflow parking and prioritize areas with Full status.'
    : dailyWarning > 0
      ? 'Monitor areas with Warning status closely.'
      : 'No action needed — conditions are within normal range.';

  // ---- Weekly perspective ----
  const weekEnd = addDays(selectedDate, 6);
  const weekRows = merged.filter(r => r.date >= selectedDate && r.date <= weekEnd);
  const weekTotal = weekRows.reduce((s, r) => s + (r.west?.demand ?? 0) + (r.east?.demand ?? 0), 0);
  const weekEntries = weekRows.flatMap(r => ZONE_KEYS.map(z => r[z]).filter((d): d is NonNullable<typeof d> => !!d));
  const weekHigh = weekEntries.filter(d => statusFor(d.rate) === 'Full').length;
  const weekModerate = weekEntries.filter(d => statusFor(d.rate) === 'Warning').length;
  const weekGood = weekEntries.filter(d => statusFor(d.rate) === 'Normal').length;
  const weekCondition = weekHigh > 0 ? 'Needs Attention' : weekModerate > 0 ? 'Monitor' : 'Stable';
  const weekAction = weekHigh > 0
    ? 'Review High areas and adjust weekly parking allocation.'
    : weekModerate > 0
      ? 'Monitor Moderate areas during the week.'
      : 'Continue standard weekly monitoring.';

  // ---- Monthly perspective (selected month totals + next-7-month trend) ----
  const [monthStart, monthEnd] = monthRange(selectedDate);
  const monthRows = merged.filter(r => r.date >= monthStart && r.date <= monthEnd);
  const monthTotal = monthRows.reduce((s, r) => s + (r.west?.demand ?? 0) + (r.east?.demand ?? 0), 0);

  // Average available slots per zone per calendar month, for the next 7 months from selectedDate.
  // Derived from avg_occupancy_rate (a real snapshot percentage), not predicted_demand — demand
  // is a daily entry-count/flow metric that can exceed capacity many times over via turnover,
  // so "capacity - demand" would not actually mean "available slots".
  function avgAvailableForMonth(zone: ZoneKey, y0: number, m0: number): number | null {
    const start = monthStartISO(y0, m0);
    const end = monthRange(start)[1];
    const rows = merged.filter(r => r.date >= start && r.date <= end && r[zone]);
    if (rows.length === 0) return null;
    const cap = capacityOf(zone);
    return rows.reduce((s, r) => s + Math.max(0, cap * (1 - (r[zone]?.rate ?? 0) / 100)), 0) / rows.length;
  }
  function trendFor(prev: number | null, cur: number | null): Trend | null {
    if (prev === null || cur === null || prev === 0) return null;
    const pctChange = (cur - prev) / prev;
    if (pctChange > 0.05) return 'Increase';
    if (pctChange < -0.05) return 'Decrease';
    return 'Stable';
  }

  let monthIncrease = 0, monthDecrease = 0, monthStable = 0;
  const zoneMonthTrend: Record<ZoneKey, Trend | null> = { west: null, east: null, eastwest: null };
  for (const zone of ZONE_KEYS) {
    let prevAvg = avgAvailableForMonth(zone, y, m - 1);
    for (let i = 1; i <= 6; i++) {
      const idx = (m - 1) + i;
      const yy = y + Math.floor(idx / 12);
      const mm = idx % 12;
      const curAvg = avgAvailableForMonth(zone, yy, mm);
      const t = trendFor(prevAvg, curAvg);
      if (t === 'Increase') monthIncrease++;
      else if (t === 'Decrease') monthDecrease++;
      else if (t === 'Stable') monthStable++;
      if (i === 1) zoneMonthTrend[zone] = t; // trend into the immediate next month, used in the area table
      prevAvg = curAvg;
    }
  }
  const monthCondition = monthDecrease > 0 ? 'Planning Required' : 'Stable';
  const monthAction = monthDecrease > 0
    ? 'Review areas with decreasing availability for capacity planning.'
    : 'Maintain current capacity plan.';

  // ---- Area Attention Summary (per real zone) ----
  const areaRows = ZONE_KEYS.map(zone => {
    const dailyStatus = dailyRow?.[zone] ? statusFor(dailyRow[zone]!.rate) : 'Normal';
    const weekZoneEntries = weekRows.map(r => r[zone]).filter((d): d is NonNullable<typeof d> => !!d);
    const weekWorstRate = weekZoneEntries.length ? Math.max(...weekZoneEntries.map(d => d.rate)) : 0;
    const weekStatusRaw = statusFor(weekWorstRate);
    const weekStatus = weekStatusRaw === 'Full' ? 'High' : weekStatusRaw === 'Warning' ? 'Moderate' : 'Good';
    const monthlyTrend = zoneMonthTrend[zone] ?? 'Stable';

    const priority: Priority = dailyStatus === 'Full' || weekStatus === 'High'
      ? 'High'
      : dailyStatus === 'Warning' || weekStatus === 'Moderate'
        ? 'Medium'
        : 'Low';

    const reasons: string[] = [];
    if (dailyStatus === 'Full') reasons.push('Full condition in daily forecast');
    else if (dailyStatus === 'Warning') reasons.push('Warning condition in daily forecast');
    if (weekStatus === 'High') reasons.push('High weekly demand contribution');
    const reason = reasons.length ? reasons.join('; ') : 'Stable condition';

    const action = priority === 'High'
      ? 'Prioritize monitoring and prepare operational adjustment.'
      : priority === 'Medium'
        ? 'Monitor during peak period and review area usage.'
        : 'Continue standard monitoring.';

    return { zone, label: ZONE_LABELS[zone], priority, dailyStatus, weekStatus, monthlyTrend, reason, action };
  });
  const priorityAreaCount = areaRows.filter(a => a.priority === 'High').length;

  const priorityClass: Record<Priority, string> = { High: 'report-priority-high', Medium: 'report-priority-medium', Low: 'report-priority-low' };
  const dailyBadgeClass: Record<string, string> = { Full: 'status-full', Warning: 'status-warning', Normal: 'status-normal' };
  const weekBadgeClass: Record<string, string> = { High: 'status-full', Moderate: 'status-warning', Good: 'status-normal' };
  const trendBadgeClass: Record<Trend, string> = { Decrease: 'status-full', Increase: 'status-normal', Stable: 'status-warning' };

  return (
    <div className="report-only">
      <div className="report-page">
        <div className="report-header">
          <div>
            <div className="report-brand">PTMI PARKING MANAGEMENT</div>
            <h1>Parking Management Forecast Report</h1>
            <p>
              Forecast perspective anchored on the <strong>daily</strong> view, year {forecastYear}.
              Daily, weekly, and monthly perspectives are aligned to the same reference period.
            </p>
          </div>
          <div className="report-meta">
            <div><span>Report Date</span><strong>{formatLong(today)}</strong></div>
            <div><span>Forecast Year</span><strong>{forecastYear}</strong></div>
            <div><span>Report Type</span><strong>Management</strong></div>
          </div>
        </div>

        <h2>Executive Summary</h2>
        <div className="report-box">
          <ul>
            <li>Parking demand forecast shows {priorityAreaCount > 0 ? 'selected areas require operational monitoring' : 'all areas within normal operating range'}.</li>
            <li>Daily forecast is used for operational risk by identifying Full and Warning conditions.</li>
            <li>Weekly forecast is aligned with the selected report perspective to monitor area demand contribution.</li>
            <li>Monthly forecast is aligned with the selected report perspective to support capacity planning based on availability trend.</li>
          </ul>
          <div className="report-callout">
            Daily is for operational risk, weekly is for monitoring, and monthly is for capacity planning. Status labels differ in each perspective.
          </div>
        </div>

        <h2>Key Metrics</h2>
        <div className="report-metrics">
          <div className="report-metric-card">
            <span>Daily Forecast</span>
            <strong>{dailyTotal.toLocaleString()}</strong>
            <em>Predicted vehicles on selected date</em>
          </div>
          <div className="report-metric-card">
            <span>Weekly Forecast</span>
            <strong>{weekTotal.toLocaleString()}</strong>
            <em>Predicted vehicles on selected week</em>
          </div>
          <div className="report-metric-card">
            <span>Monthly Forecast</span>
            <strong>{monthTotal.toLocaleString()}</strong>
            <em>Predicted vehicles on selected month</em>
          </div>
          <div className="report-metric-card">
            <span>Priority Areas</span>
            <strong>{priorityAreaCount}</strong>
            <em>High priority area count</em>
          </div>
        </div>

        <h2>Forecast Perspective Summary</h2>
        <div className="report-perspectives">
          <div className="report-perspective-card">
            <h3>Daily Perspective</h3>
            <div className="report-kv"><span>Selected Date</span><strong>{formatLong(selectedDate)}</strong></div>
            <div className="report-kv"><span>Total Vehicles</span><strong>{dailyTotal.toLocaleString()}</strong></div>
            <div className="report-kv"><span>Avg. Occupancy</span><strong>{dailyAvgOcc}%</strong></div>
            <div className="report-kv"><span>Full Records</span><strong>{dailyFull}</strong></div>
            <div className="report-kv"><span>Warning Records</span><strong>{dailyWarning}</strong></div>
            <div className="report-kv"><span>Condition</span><strong>{dailyCondition}</strong></div>
            <p className="report-action">{dailyAction}</p>
            <p className="report-caption">Daily status focuses on immediate operational conditions.</p>
          </div>
          <div className="report-perspective-card">
            <h3>Weekly Perspective</h3>
            <div className="report-kv"><span>Selected Week</span><strong>W{isoWeek(selectedDate)}</strong></div>
            <div className="report-kv"><span>Total Vehicles</span><strong>{weekTotal.toLocaleString()}</strong></div>
            <div className="report-kv"><span>High Records</span><strong>{weekHigh}</strong></div>
            <div className="report-kv"><span>Moderate Records</span><strong>{weekModerate}</strong></div>
            <div className="report-kv"><span>Good Records</span><strong>{weekGood}</strong></div>
            <div className="report-kv"><span>Condition</span><strong>{weekCondition}</strong></div>
            <p className="report-action">{weekAction}</p>
            <p className="report-caption">Weekly status is based on area demand contribution.</p>
          </div>
          <div className="report-perspective-card">
            <h3>Monthly Perspective (Next 7 Months)</h3>
            <div className="report-kv"><span>Selected Month</span><strong>{MONTH_NAMES[m - 1]}</strong></div>
            <div className="report-kv"><span>Total Vehicles</span><strong>{monthTotal.toLocaleString()}</strong></div>
            <div className="report-kv"><span>Availability Increase Records</span><strong>{monthIncrease}</strong></div>
            <div className="report-kv"><span>Availability Decrease Records</span><strong>{monthDecrease}</strong></div>
            <div className="report-kv"><span>Stable Records</span><strong>{monthStable}</strong></div>
            <div className="report-kv"><span>Condition</span><strong>{monthCondition}</strong></div>
            <p className="report-action">{monthAction}</p>
            <p className="report-caption">Monthly trend compares available slots with the previous month.</p>
          </div>
        </div>

        <h2>Area Attention Summary</h2>
        <table className="report-table">
          <thead>
            <tr>
              <th>Area</th><th>Priority</th><th>Daily Status</th><th>Weekly Status</th>
              <th>Monthly Trend</th><th>Reason</th><th>Suggested Action</th>
            </tr>
          </thead>
          <tbody>
            {areaRows.map(a => (
              <tr key={a.zone}>
                <td>{a.label}</td>
                <td><span className={`status-badge ${priorityClass[a.priority]}`}>{a.priority}</span></td>
                <td><span className={`status-badge ${dailyBadgeClass[a.dailyStatus]}`}>{a.dailyStatus}</span></td>
                <td><span className={`status-badge ${weekBadgeClass[a.weekStatus]}`}>{a.weekStatus}</span></td>
                <td><span className={`status-badge ${trendBadgeClass[a.monthlyTrend]}`}>{a.monthlyTrend}</span></td>
                <td>{a.reason}</td>
                <td>{a.action}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="report-note">
          Note: Monthly Trend refers to the change in average available slots from the selected
          month to the following month. Increase/Decrease/Stable Records in the Monthly
          Perspective summarize the next 7-month window.
        </p>

        <h2>Management Recommendations</h2>
        <div className="report-box">
          <ul>
            <li>Prioritize monitoring for areas categorized as High Priority.</li>
            <li>Prepare overflow parking when daily forecast indicates Full or Warning conditions.</li>
            <li>Use weekly forecast to support operational monitoring and parking allocation.</li>
            <li>Use monthly availability trend to support capacity planning and management decision-making.</li>
            <li>Review forecast results regularly to improve parking management strategy.</li>
          </ul>
        </div>

        <div className="report-footer">
          <span>Generated by PTMI Parking Forecast System</span>
          <span>Daily • Weekly • Monthly Forecast Insight</span>
        </div>
      </div>
    </div>
  );
}