'use client';

import { use, useEffect, useState } from 'react';
import { useAuth } from '@/lib/AuthContext';
import { useRouter } from 'next/navigation';
import { Menu } from 'lucide-react';
import Sidebar from '@/components/Sidebar';
import TrackerPage from '@/app/dashboard/Tracker';
import ListPage from '@/app/dashboard/List';
import MembersPage from '@/app/dashboard/Member';
import AnalyticsPage from '@/app/dashboard/Analytics';
import CalibrationPage from '@/app/dashboard/Calibration';

const VIEWS: Record<string, React.ComponentType> = {
  tracker: TrackerPage,
  list: ListPage,
  members: MembersPage,
  analytics: AnalyticsPage,
  calibration: CalibrationPage,
};

export default function DashboardPage({
  params,
}: {
  params: Promise<{ slug?: string[] }>;
}) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const { slug } = use(params);
  const view = slug?.[0] ?? 'tracker';
  const View = VIEWS[view];
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    setSidebarOpen(false);
  }, [view]);

  useEffect(() => {
    if (!loading && !user) router.replace('/');
  }, [user, loading, router]);

  useEffect(() => {
    if (!View) router.replace('/dashboard/tracker');
  }, [View, router]);

  if (loading) return <div style={{ minHeight: '100vh', background: 'var(--bg)' }} />;
  if (!user || !View) return null;

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--bg)' }}>
      <Sidebar mobileOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className={`app-sidebar-backdrop${sidebarOpen ? ' visible' : ''}`} onClick={() => setSidebarOpen(false)} />
      <main className="app-main">
        <button
          onClick={() => setSidebarOpen(true)}
          className="app-hamburger"
          style={{
            alignItems: 'center', justifyContent: 'center', gap: 8, margin: '14px 0 0 14px',
            padding: '8px 14px', borderRadius: 9, border: '1px solid var(--border)',
            background: '#fff', color: 'var(--text)', fontSize: 12, fontWeight: 700, cursor: 'pointer',
          }}
        >
          <Menu size={15} /> Menu
        </button>
        <View />
      </main>
    </div>
  );
}
