'use client'
import { type Category } from '@/lib/types';

export default function CategoryStats({ slots }: { slots: any }) {
  const catColor = (used: number, total: number) => {
    const pct = total ? used / total : 0;
    return pct > 0.85 ? 'var(--danger-text)' : pct > 0.65 ? 'var(--warn-text)' : 'var(--green-text)';
  };
  const catBg = (used: number, total: number) => {
    const pct = total ? used / total : 0;
    return pct > 0.85 ? 'var(--danger-bg)' : pct > 0.65 ? 'var(--warn-bg)' : 'var(--green-bg)';
  };
  const catBorder = (used: number, total: number) => {
    const pct = total ? used / total : 0;
    return pct > 0.85 ? 'var(--red-mid)' : pct > 0.65 ? '#FDE68A' : '#6EE7B7';
  };
  const categories: Category[] = ['Employee', 'Vendor', 'Visitor'];

  return (
    <div className="card" style={{ padding: 18 }}>
      <div className="card-title" style={{ marginBottom: 14 }}>Available Slots by Category</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 10 }}>
        {categories.map((cat) => {
          const info = slots.summary[cat] || { used: 0, total: 0, available: 0, rate_pct: 0 };
          return (
            <div key={cat} style={{ textAlign: 'center', padding: '14px 8px', borderRadius: 10, background: catBg(info.used, info.total), border: `1px solid ${catBorder(info.used, info.total)}` }}>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 22, fontWeight: 700, color: catColor(info.used, info.total) }}>{info.available}</div>
              <div style={{ fontSize: 11, fontWeight: 600, color: catColor(info.used, info.total), marginTop: 3 }}>{cat}</div>
              <div style={{ fontSize: 10, color: catColor(info.used, info.total), opacity: .75, marginTop: 1 }}>{info.used}/{info.total} used</div>
            </div>
          );
        })}
      </div>
      <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 8 }}>
        {categories.map((cat) => {
          const info = slots.summary[cat] || { used: 0, total: 0, available: 0, rate_pct: 0 };
          const pct = info.total ? Math.round((info.used / info.total) * 100) : 0;
          const color = pct > 85 ? 'var(--red)' : pct > 65 ? 'var(--amber)' : 'var(--teal)';
          return (
            <div key={cat}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--muted)', marginBottom: 3 }}>
                <span style={{ fontWeight: 600 }}>{cat}</span>
                <span style={{ fontFamily: 'var(--font-mono)' }}>{pct}%</span>
              </div>
              <div style={{ height: 5, borderRadius: 3, background: 'var(--border)' }}>
                <div style={{ height: '100%', borderRadius: 3, width: `${pct}%`, background: color, transition: 'width .5s' }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
