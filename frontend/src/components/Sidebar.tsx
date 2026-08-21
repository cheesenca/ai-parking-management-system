'use client'

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { useAuth } from '@/context/AuthContext';
import { apiGetPendingReviews } from '@/lib/backendApi';
import { ScanLine, ClipboardList, Users, UserCog, BarChart2, LogOut, Car, Crosshair, AlertCircle, ChevronDown } from 'lucide-react';

const navGroups = [
  {
    label: 'Operations',
    items: [
      { href: '/dashboard/tracker', label: 'Parking Tracer', icon: ScanLine, roles: ['Admin', 'Security'] },
      { href: '/dashboard/list', label: 'Parking List', icon: ClipboardList, roles: ['Admin', 'Security'] },
      { href: '/dashboard/pending-review', label: 'Pending Review', icon: AlertCircle, roles: ['Admin', 'Security'] },
    ],
  },
  {
    label: 'Management',
    items: [
      { href: '/dashboard/members', label: 'Members', icon: Users, roles: ['Admin'] },
      { href: '/dashboard/users', label: 'User Management', icon: UserCog, roles: ['Admin'] },
    ],
  },
  {
    label: 'Insights & Setup',
    items: [
      { href: '/dashboard/analytics', label: 'Analytics', icon: BarChart2, roles: ['Admin'] },
      { href: '/dashboard/calibration', label: 'Slot Calibration', icon: Crosshair, roles: ['Admin'] },
    ],
  },
];

export default function Sidebar({ mobileOpen = false, onClose }: { mobileOpen?: boolean; onClose?: () => void }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();
  const [pendingCount, setPendingCount] = useState(0);
  const [userMenuOpen, setUserMenuOpen] = useState(false);

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
  const groups = navGroups
    .map(g => ({ ...g, items: g.items.filter(n => user && n.roles.includes(user.role)) }))
    .filter(g => g.items.length > 0);

  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({});
  useEffect(() => {
    // Ensure the group containing the active route is expanded.
    const activeGroup = navGroups.find(g => g.items.some(i => i.href === pathname));
    if (activeGroup) setOpenGroups(prev => (prev[activeGroup.label] === false ? prev : { ...prev, [activeGroup.label]: true }));
  }, [pathname]);
  const isGroupOpen = (label: string) => openGroups[label] !== false; // default open
  const toggleGroup = (label: string) => setOpenGroups(prev => ({ ...prev, [label]: !isGroupOpen(label) }));

  const initials = user?.username ? user.username.slice(0, 2).toUpperCase() : '--';

  return (
    <aside className={`app-sidebar sb${mobileOpen ? ' mobile-open' : ''}`}>
      {/* Header */}
      <div className="sb-header">
        <div className="sb-brand">
          <div className="sb-brand-icon">
            <Car size={20} color="#fff" />
          </div>
          <div>
            <div className="sb-brand-name">AIPS</div>
            <div className="sb-brand-sub">AI Parking System</div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="sb-nav">
        {groups.map((group) => {
          const open = isGroupOpen(group.label);
          return (
            <div key={group.label} className="sb-nav-group">
              <button type="button" className="sb-nav-label sb-nav-group-toggle" onClick={() => toggleGroup(group.label)}>
                <span>{group.label}</span>
                <ChevronDown size={12} className={`sb-group-chevron${open ? ' open' : ''}`} />
              </button>
              <div className={`sb-nav-group-items${open ? ' open' : ''}`}>
                <div className="sb-nav-group-inner">
                  {group.items.map(item => {
                    const active = pathname === item.href;
                    const Icon = item.icon;
                    return (
                      <Link key={item.href} href={item.href} onClick={onClose} className={`sb-nav-item${active ? ' active' : ''}`}>
                        <span className="sb-nav-indicator" />
                        <Icon size={16} className="sb-nav-icon" />
                        <span className="sb-nav-label-text">{item.label}</span>
                        {item.href === '/dashboard/pending-review' && pendingCount > 0 && (
                          <span className="sb-badge">{pendingCount > 99 ? '99+' : pendingCount}</span>
                        )}
                      </Link>
                    );
                  })}
                </div>
              </div>
            </div>
          );
        })}
      </nav>

      {/* User footer */}
      <div className="sb-footer">
        {user && (
          <button className="sb-user-card" onClick={() => setUserMenuOpen(o => !o)}>
            <div className="sb-avatar">{initials}</div>
            <div className="sb-user-info">
              <div className="sb-user-name">{user.username}</div>
              <div className="sb-user-role">
                {user.role}{user.location ? ` · ${user.location.toUpperCase()}` : ''}
              </div>
            </div>
            <ChevronDown size={14} className={`sb-chevron${userMenuOpen ? ' open' : ''}`} />
          </button>
        )}
        {(userMenuOpen || !user) && (
          <button onClick={handleLogout} className="sb-logout-btn">
            <LogOut size={14} /> Sign Out
          </button>
        )}
      </div>
    </aside>
  );
}