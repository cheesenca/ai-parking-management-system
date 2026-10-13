'use client'

import { type ConnState } from '@/hooks/useLiveDetection';
import { LucideIcon } from 'lucide-react';

export default function ConnPill({ label, state, icon: Icon }: { label: string; state: ConnState; icon: LucideIcon }) {
  const live = state === 'live';
  const color = live ? 'var(--green-text)' : state === 'simulated' ? 'var(--warn-text)' : 'var(--muted)';
  const bg = live ? 'var(--green-bg)' : state === 'simulated' ? 'var(--warn-bg)' : 'var(--bg)';
  const border = live ? '#6EE7B7' : state === 'simulated' ? '#FDE68A' : 'var(--border)';
  
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 12px', borderRadius: 99, background: bg, border: `1px solid ${border}` }}>
      <Icon size={12} style={{ color }} />
      <span style={{ fontSize: 10, fontWeight: 700, color, letterSpacing: '.04em' }}>{label}</span>
      <span style={{ fontSize: 10, fontWeight: 800, color }}>{live ? 'LIVE' : state === 'simulated' ? 'SIM' : '…'}</span>
    </div>
  );
}
