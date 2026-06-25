'use client';

import { use, useEffect } from 'react';
import { useAuth } from '@/lib/AuthContext';
import { useRouter } from 'next/navigation';
import Sidebar from '@/components/Sidebar';
import TrackerPage from '@/app/dashboard/Tracker';
import ListPage from '@/app/dashboard/List';
import MembersPage from '@/app/dashboard/Member';
import AnalyticsPage from '@/app/dashboard/Analytics';
 
const VIEWS: Record<string, React.ComponentType> = {
  tracker: TrackerPage,
  list: ListPage,
  members: MembersPage,
  analytics: AnalyticsPage,
};
 
export default function DashboardPage({
  params,
}: {
  params: Promise<{ slug?: string[] }>;
}) {
  const { user } = useAuth();
  const router = useRouter();
  const { slug } = use(params);
  const view = slug?.[0] ?? 'tracker';
  const View = VIEWS[view];
 
  useEffect(() => {
    if (!user) router.replace('/');
  }, [user, router]);
 
  useEffect(() => {
    if (!View) router.replace('/dashboard/tracker');
  }, [View, router]);
 
  if (!user || !View) return null;
 
  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--bg)' }}>
      <Sidebar />
      <main style={{ marginLeft: 224, flex: 1, minHeight: '100vh', overflow: 'auto' }}>
        <View />
      </main>
    </div>
  );
}
 