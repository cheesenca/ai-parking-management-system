'use client'

export default function SlotMap({ slots }: { slots: any }) {
  const rate = slots.total ? Math.round((slots.occupied / slots.total) * 100) : 0;

  return (
    <div className="card" style={{ padding: 18 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div className="card-title">Live Slot Map</div>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: rate > 85 ? 'var(--danger-text)' : 'var(--muted)' }}>
          {slots.occupied}/{slots.total} occupied · {rate}%
        </span>
      </div>
      <div style={{ borderRadius: 10, overflow: 'hidden', border: '1px solid var(--border)', background: '#0E1726' }}>
        <svg viewBox={`0 0 ${slots.map.frame.w} ${slots.map.frame.h}`} style={{ width: '100%', display: 'block' }}>
          <rect x={0} y={0} width={slots.map.frame.w} height={slots.map.frame.h} fill="#0E1726" />
          {slots.map.background && (
            <image
              href={slots.map.background}
              x={0} y={0}
              width={slots.map.frame.w} height={slots.map.frame.h}
              preserveAspectRatio="xMidYMid slice"
              opacity={0.9}
            />
          )}
          {slots.map.slots.map((s: any) => {
            const occ = slots.slotStatus[s.id] === 'Occupied';
            const pts = s.polygon.map((p: any) => p.join(',')).join(' ');
            const cx = s.polygon.reduce((a: any, p: any) => a + p[0], 0) / s.polygon.length;
            const cy = s.polygon.reduce((a: any, p: any) => a + p[1], 0) / s.polygon.length;
            return (
              <g key={s.id}>
                <polygon points={pts}
                  fill={occ ? 'rgba(229,0,43,.45)' : 'rgba(21,154,114,.40)'}
                  stroke={occ ? '#E5002B' : '#22C58B'} strokeWidth={2} />
                <text x={cx} y={cy + 4} textAnchor="middle" fontSize={16} fontFamily="monospace"
                  fill="#fff" opacity={0.95} style={{ paintOrder: 'stroke', stroke: '#000', strokeWidth: 3 }}>{s.id}</text>
              </g>
            );
          })}
        </svg>
      </div>
      <div style={{ display: 'flex', gap: 16, marginTop: 10, justifyContent: 'center', fontSize: 11, color: 'var(--muted)', fontWeight: 600 }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span style={{ width: 10, height: 10, borderRadius: 3, background: 'rgba(21,154,114,.7)', border: '1px solid #22C58B' }} /> Available</span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span style={{ width: 10, height: 10, borderRadius: 3, background: 'rgba(229,0,43,.7)', border: '1px solid #E5002B' }} /> Occupied</span>
      </div>
    </div>
  );
}