'use client'

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { useAuth } from '@/lib/AuthContext';
import { apiIsOnline, apiGetPendingReviews } from '@/lib/backendApi';
import { ScanLine, ClipboardList, Users, BarChart2, LogOut, Car, Crosshair, AlertCircle, X } from 'lucide-react';

const navItems = [
  { href: '/dashboard/tracker', label: 'Parking Tracer', icon: ScanLine, roles: ['Admin', 'Security'] },
  { href: '/dashboard/list', label: 'Parking List', icon: ClipboardList, roles: ['Admin', 'Security'] },
  { href: '/dashboard/pending-review', label: 'Pending Review', icon: AlertCircle, roles: ['Admin', 'Security'] },
  { href: '/dashboard/members', label: 'Members', icon: Users, roles: ['Admin'] },
  { href: '/dashboard/analytics',label: 'Analytics', icon: BarChart2, roles: ['Admin'] },
  { href: '/dashboard/calibration', label: 'Slot Calibration', icon: Crosshair, roles: ['Admin'] },
];

export default function Sidebar({ mobileOpen = false, onClose }: { mobileOpen?: boolean; onClose?: () => void }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  const [pendingCount, setPendingCount] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      const online = await apiIsOnline();
      if (!cancelled) setBackendOnline(online);
    };
    check();
    const interval = setInterval(check, 10_000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    const zone = user.role === 'Security' ? user.location ?? undefined : undefined;
    const check = async () => {
      try {
        const data = await apiGetPendingReviews({ zone, status: 'needs_review', page_size: 1 });
        if (!cancelled) setPendingCount(data.total);
      } catch {
        // backend offline — leave last-known count as is
      }
    };
    check();
    const interval = setInterval(check, 15_000);
    return () => { cancelled = true; clearInterval(interval); };
  }, [user]);

  const handleLogout = () => { logout(); router.push('/'); };
  const allowed = navItems.filter(n => user && n.roles.includes(user.role));

  return (
    <aside className={`app-sidebar${mobileOpen ? ' mobile-open' : ''}`}>
      {/* Header */}
      <div style={{
        background: 'linear-gradient(135deg, var(--red) 0%, var(--red-dark) 60%, var(--red-deep) 100%)',
        padding: '20px 20px 18px', position: 'relative',
      }}>
        <button
          onClick={onClose}
          className="app-sidebar-close"
          style={{
            position: 'absolute', top: 14, right: 14, background: 'rgba(255,255,255,.15)',
            border: '1px solid rgba(255,255,255,.3)', borderRadius: 8, color: '#fff',
            width: 28, height: 28, alignItems: 'center', justifyContent: 'center', cursor: 'pointer',
          }}
        >
          <X size={15} />
        </button>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
          <div style={{
            width: 34, height: 34, borderRadius: 9,
            background: 'rgba(255,255,255,.2)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            border: '1px solid rgba(255,255,255,.25)',
          }}>
            <Car size={17} color="#fff" />
          </div>
          <div>
            <div style={{ color: '#fff', fontWeight: 800, fontSize: 15, letterSpacing: '-0.01em' }}>AIPS</div>
            <div style={{ color: 'rgba(255,255,255,.65)', fontSize: 10, fontWeight: 500, letterSpacing: '.05em' }}>AI PARKING SYSTEM</div>
          </div>
        </div>
        <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
          <span
            className="pulse-dot"
            style={{ background: backendOnline ? '#4ade80' : backendOnline === false ? '#FCA5A5' : 'rgba(255,255,255,.4)' }}
          />
          <span style={{ color: 'rgba(255,255,255,.8)', fontSize: 10, fontWeight: 600, letterSpacing: '.05em' }}>
            {backendOnline === null ? 'CONNECTING…' : backendOnline ? 'LIVE MONITORING' : 'DEMO MODE'}
          </span>
        </div>
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, padding: '10px 10px' }}>
        <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '.08em', textTransform: 'uppercase', color: 'var(--muted2)', padding: '8px 10px 6px' }}>
          Menu
        </div>
        {allowed.map(item => {
          const active = pathname === item.href;
          return (
            <Link key={item.href} href={item.href} onClick={onClose} style={{
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '9px 12px', borderRadius: 9, marginBottom: 2,
              fontSize: 13, fontWeight: active ? 700 : 500,
              color: active ? 'var(--red)' : 'var(--text)',
              background: active ? 'var(--red-soft)' : 'transparent',
              border: active ? '1px solid var(--red-mid)' : '1px solid transparent',
              textDecoration: 'none', transition: 'all .15s',
            }}>
              <item.icon size={15} style={{ color: active ? 'var(--red)' : 'var(--muted)', flexShrink: 0 }} />
              {item.label}
              {item.href === '/dashboard/pending-review' && pendingCount > 0 && (
                <span style={{
                  marginLeft: 'auto', minWidth: 18, height: 18, padding: '0 5px', borderRadius: 9,
                  background: 'var(--red)', color: '#fff', fontSize: 10, fontWeight: 700,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  {pendingCount > 99 ? '99+' : pendingCount}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* User footer */}
      <div style={{ padding: '14px 14px', borderTop: '1px solid var(--border)' }}>
        {user && (
          <div style={{
            padding: '10px 12px', borderRadius: 9,
            background: 'var(--bg)', border: '1px solid var(--border)',
            marginBottom: 10,
          }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--ink)' }}>{user.username}</div>
            <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>
              {user.role}{user.location ? ` · ${user.location.toUpperCase()}` : ''}
            </div>
          </div>
        )}
        <button onClick={handleLogout} className="btn-secondary" style={{ width: '100%', justifyContent: 'center', fontSize: 12 }}>
          <LogOut size={13} /> Sign Out
        </button>
      </div>
    </aside>
  );
}
