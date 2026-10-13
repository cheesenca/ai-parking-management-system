'use client';

import { useEffect, useState } from 'react';
import { useAuth } from '@/context/AuthContext';
import { useRouter, usePathname } from 'next/navigation';
import { Menu } from 'lucide-react';
import Sidebar from '@/components/Sidebar';

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    setSidebarOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!loading && !user) router.replace('/');
  }, [user, loading, router]);

  if (loading) return <div style={{ minHeight: '100vh', background: 'var(--bg)' }} />;
  if (!user) return null;

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
        {children}
      </main>
    </div>
  );
}
