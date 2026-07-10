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
    <div className="card" style={{ padding: 24 }}> {/* Padding diperbesar dari 18 ke 24 */}
      <div className="card-title" style={{ marginBottom: 18, fontSize: 14 }}>Available Slots by Category</div>
      
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 16 }}>
        {categories.map((cat) => {
          const info = slots.summary[cat] || { used: 0, total: 0, available: 0, rate_pct: 0 };
          return (
            <div key={cat} style={{ textAlign: 'center', padding: '18px 12px', borderRadius: 12, background: catBg(info.used, info.total), border: `1px solid ${catBorder(info.used, info.total)}` }}>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 28, fontWeight: 700, color: catColor(info.used, info.total) }}>{info.available}</div>
              <div style={{ fontSize: 12, fontWeight: 700, color: catColor(info.used, info.total), marginTop: 4 }}>{cat}</div>
              <div style={{ fontSize: 11, color: catColor(info.used, info.total), opacity: .8, marginTop: 2 }}>{info.used}/{info.total} used</div>
            </div>
          );
        })}
      </div>

      <div style={{ marginTop: 24, display: 'flex', flexDirection: 'column', gap: 14 }}>
        {categories.map((cat) => {
          const info = slots.summary[cat] || { used: 0, total: 0, available: 0, rate_pct: 0 };
          const pct = info.total ? Math.round((info.used / info.total) * 100) : 0;
          const color = pct > 85 ? 'var(--red)' : pct > 65 ? 'var(--amber)' : 'var(--teal)';
          return (
            <div key={cat}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--muted)', marginBottom: 6 }}>
                <span style={{ fontWeight: 600 }}>{cat}</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{pct}%</span>
              </div>
              {/* Progress bar dipertebal dari 5px menjadi 8px */}
              <div style={{ height: 8, borderRadius: 4, background: 'var(--border)' }}>
                <div style={{ height: '100%', borderRadius: 4, width: `${pct}%`, background: color, transition: 'width .5s' }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
