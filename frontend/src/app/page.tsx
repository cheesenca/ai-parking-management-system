'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/AuthContext';
import { Eye, EyeOff, AlertCircle } from 'lucide-react';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    await new Promise(r => setTimeout(r, 400));
    const ok = await login(username, password);
    setLoading(false);
    if (ok) router.push('/dashboard/tracker');
    else setError('Invalid username or password.');
  };

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #E5002B 0%, #B80022 50%, #870019 100%)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 24, position: 'relative', overflow: 'hidden',
    }}>
      {/* Background circles */}
      {[
        { size: 500, top: -100, right: -100, opacity: 0.08 },
        { size: 300, bottom: -80, left: -80, opacity: 0.06 },
        { size: 200, top: '40%', left: '30%', opacity: 0.04 },
      ].map((c, i) => (
        <div key={i} style={{
          position: 'absolute',
          width: c.size, height: c.size, borderRadius: '50%',
          background: '#fff', opacity: c.opacity,
          top: c.top, right: c.right, bottom: c.bottom, left: c.left,
          pointerEvents: 'none',
        }} />
      ))}

      <div className="login-shell">
        {/* Left brand panel */}
        <div className="login-brand" style={{
          background: 'linear-gradient(160deg, rgba(255,255,255,.15) 0%, rgba(255,255,255,.05) 100%)',
          backdropFilter: 'blur(20px)',
          borderRight: '1px solid rgba(255,255,255,.15)',
          padding: '48px 40px',
          display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
        }}>
          <div>
            {/* Logo mark */}
            <div style={{ marginBottom: 40 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
                <div style={{
                  width: 44, height: 44, borderRadius: 12,
                  background: '#fff',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                    <rect x="2" y="2" width="9" height="9" rx="2" fill="#E5002B"/>
                    <rect x="13" y="2" width="9" height="9" rx="2" fill="#E5002B" opacity=".6"/>
                    <rect x="2" y="13" width="9" height="9" rx="2" fill="#E5002B" opacity=".6"/>
                    <rect x="13" y="13" width="9" height="9" rx="2" fill="#E5002B" opacity=".3"/>
                  </svg>
                </div>
                <div>
                  <div style={{ color: '#fff', fontWeight: 800, fontSize: 20, letterSpacing: '-0.02em' }}>AIPS</div>
                  <div style={{ color: 'rgba(255,255,255,.7)', fontSize: 11, fontWeight: 500 }}>AI PARKING SYSTEM</div>
                </div>
              </div>
            </div>

            <h1 style={{ color: '#fff', fontSize: 28, fontWeight: 800, letterSpacing: '-0.03em', lineHeight: 1.2, marginBottom: 12 }}>
              Smarter parking for PT. Mattel Indonesia
            </h1>
            <p style={{ color: 'rgba(255,255,255,.75)', fontSize: 13, lineHeight: 1.7 }}>
              AI-powered vehicle detection, license plate recognition, and predictive analytics — all in one platform.
            </p>
          </div>

          {/* Feature list */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginTop: 40 }}>
            {[
              { icon: '🎯', text: 'YOLOv8 real-time detection' },
              { icon: '🔤', text: 'EasyOCR plate recognition' },
              { icon: '📊', text: 'ARIMA/LSTM forecasting' },
              { icon: '⚡', text: 'Live WebSocket updates' },
            ].map(f => (
              <div key={f.text} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <span style={{ fontSize: 18 }}>{f.icon}</span>
                <span style={{ color: 'rgba(255,255,255,.85)', fontSize: 13, fontWeight: 500 }}>{f.text}</span>
              </div>
            ))}
          </div>

          <div style={{ marginTop: 40, color: 'rgba(255,255,255,.5)', fontSize: 11 }}>
            President University Capstone Design 2025
          </div>
        </div>

        {/* Right form panel */}
        <div style={{ flex: 1, background: '#fff', padding: '48px 44px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
          <div style={{ marginBottom: 32 }}>
            <h2 style={{ fontSize: 24, fontWeight: 800, color: 'var(--ink)', letterSpacing: '-0.02em', marginBottom: 6 }}>Welcome back</h2>
            <p style={{ fontSize: 13, color: 'var(--muted)' }}>Sign in to access the parking management dashboard.</p>
          </div>

          <form onSubmit={handleSubmit}>
            <div style={{ marginBottom: 16 }}>
              <label className="label" style={{ display: 'block', marginBottom: 7 }}>Username</label>
              <input
                className="input"
                type="text" value={username}
                onChange={e => setUsername(e.target.value)}
                placeholder="e.g. admin / westsec"
                required
              />
            </div>

            <div style={{ marginBottom: 24 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 7 }}>
                <label className="label" style={{ display: 'block' }}>Password</label>
                <Link href="/forgot-password" style={{ fontSize: 12, color: 'var(--red)', fontWeight: 600, textDecoration: 'none' }}>
                  Forgot password?
                </Link>
              </div>
              <div style={{ position: 'relative' }}>
                <input
                  className="input"
                  type={showPw ? 'text' : 'password'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="Password"
                  style={{ paddingRight: 44 }}
                  required
                />
                <button type="button" onClick={() => setShowPw(!showPw)} style={{
                  position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)',
                  background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer',
                  display: 'flex',
                }}>
                  {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {error && (
              <div style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '10px 14px', borderRadius: 9,
                background: 'var(--danger-bg)', border: '1px solid var(--red-mid)',
                color: 'var(--danger-text)', fontSize: 13, marginBottom: 16,
              }}>
                <AlertCircle size={14} />{error}
              </div>
            )}

            <button className="btn-primary" type="submit" disabled={loading}
              style={{ width: '100%', justifyContent: 'center', padding: '12px', opacity: loading ? .7 : 1 }}>
              {loading ? 'Signing in…' : 'Sign In'}
            </button>
          </form>

          <div style={{ marginTop: 28, textAlign: 'center', fontSize: 13, color: 'var(--muted)' }}>
            Don&apos;t have an account?{' '}
            <Link href="/register" style={{ color: 'var(--red)', fontWeight: 600, textDecoration: 'none' }}>
              Sign up
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
