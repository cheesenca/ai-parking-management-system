'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
<<<<<<< HEAD
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
    else setError('Invalid username or password');
=======
import { Eye, EyeOff, AlertCircle, CheckCircle2 } from 'lucide-react';

export default function ForgotPasswordPage() {
  // Step 1: email -> request a reset token. Step 2: token + new password -> confirm.
  // This two-step flow replaces the old single-step one, which reset the
  // password directly just from a known email (an account-takeover hole).
  const [step, setStep] = useState<1 | 2>(1);
  const [email, setEmail] = useState('');
  const [token, setToken] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);
  const { requestPasswordReset, confirmPasswordReset } = useAuth();
  const router = useRouter();

  const handleRequestToken = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setLoading(true);
    const res = await requestPasswordReset(email);
    setLoading(false);

    if (res.ok) {
      setSuccess(res.message || 'If the email is registered, a reset code has been sent.');
      // Demo-only: no email service is wired up yet, so the backend returns
      // the token directly and we prefill it here. Remove this once a real
      // email send exists — the token should never reach the browser then.
      if (res.token) setToken(res.token);
      setStep(2);
    } else {
      setError(res.message || 'Gagal meminta reset password. Silakan coba lagi.');
    }
  };

  const handleConfirmReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (newPassword !== confirmPassword) {
      setError('Password baru dan konfirmasi tidak sama.');
      return;
    }
    if (newPassword.length < 6) {
      setError('Password minimal 6 karakter.');
      return;
    }
    if (!token) {
      setError('Masukkan kode reset yang dikirim ke email Anda.');
      return;
    }

    setLoading(true);
    const res = await confirmPasswordReset(email, token, newPassword);
    setLoading(false);

    if (res.ok) {
      setSuccess(res.message || 'Password berhasil direset. Mengarahkan ke halaman login…');
      setTimeout(() => router.push('/'), 1500);
    } else {
      setError(res.message || 'Gagal mereset password. Silakan coba lagi.');
    }
>>>>>>> origin/master
  };

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #E5002B 0%, #B80022 50%, #870019 100%)',
<<<<<<< HEAD
      display: 'flex', 
      alignItems: 'center', 
      justifyContent: 'center',
      padding: 24, 
      position: 'relative', 
      overflow: 'hidden',
    }}>
      {/* Background circles */}
=======
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 24, position: 'relative', overflow: 'hidden',
    }}>
>>>>>>> origin/master
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

<<<<<<< HEAD
      <div className="login-shell fadein">
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
              { icon: '📊', text: 'Prophet forecasting' },
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
                <Link href="/auth/forgot-password" style={{ fontSize: 12, color: 'var(--red)', fontWeight: 600, textDecoration: 'none' }}>
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
              <div className="fadein" style={{
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

          <div style={{
            marginTop: 28, display: 'flex', alignItems: 'center', gap: 8,
            fontSize: 12, color: 'var(--muted2)',
          }}>
            <span style={{ flex: 1, height: 1, background: 'var(--border)' }} />
            Accounts are provisioned by an administrator
            <span style={{ flex: 1, height: 1, background: 'var(--border)' }} />
          </div>
=======
      <div className="fadein" style={{
        width: '100%', maxWidth: 420, borderRadius: 20, overflow: 'hidden',
        boxShadow: '0 32px 80px rgba(0,0,0,.25)', position: 'relative',
        background: '#fff', padding: '44px 40px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 28 }}>
          <div style={{
            width: 40, height: 40, borderRadius: 10,
            background: 'var(--red)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <rect x="2" y="2" width="9" height="9" rx="2" fill="#fff"/>
              <rect x="13" y="2" width="9" height="9" rx="2" fill="#fff" opacity=".6"/>
              <rect x="2" y="13" width="9" height="9" rx="2" fill="#fff" opacity=".6"/>
              <rect x="13" y="13" width="9" height="9" rx="2" fill="#fff" opacity=".3"/>
            </svg>
          </div>
          <div>
            <div style={{ fontWeight: 800, fontSize: 16, color: 'var(--ink)' }}>AIPS</div>
            <div style={{ fontSize: 11, color: 'var(--muted)', fontWeight: 500 }}>AI PARKING SYSTEM</div>
          </div>
        </div>

        <h2 style={{ fontSize: 22, fontWeight: 800, color: 'var(--ink)', letterSpacing: '-0.02em', marginBottom: 6 }}>
          {step === 1 ? 'Reset your password' : 'Enter reset code'}
        </h2>
        <p style={{ fontSize: 13, color: 'var(--muted)', marginBottom: 28 }}>
          {step === 1
            ? 'Enter your registered email to receive a reset code.'
            : 'Enter the code sent to your email and choose a new password.'}
        </p>

        {step === 1 && (
        <form onSubmit={handleRequestToken}>
          <div style={{ marginBottom: 16 }}>
            <label className="label" style={{ display: 'block', marginBottom: 7 }}>Email</label>
            <input
              className="input" type="email" value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="name@company.com"
              required
            />
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
            {loading ? 'Sending…' : 'Send Reset Code'}
          </button>
        </form>
        )}

        {step === 2 && (
        <form onSubmit={handleConfirmReset}>
          <div style={{ marginBottom: 16 }}>
            <label className="label" style={{ display: 'block', marginBottom: 7 }}>Reset Code</label>
            <input
              className="input" type="text" value={token}
              onChange={e => setToken(e.target.value)}
              placeholder="Paste the code from your email"
              required
            />
          </div>

          <div style={{ marginBottom: 16 }}>
            <label className="label" style={{ display: 'block', marginBottom: 7 }}>New Password</label>
            <div style={{ position: 'relative' }}>
              <input
                className="input"
                type={showPw ? 'text' : 'password'}
                value={newPassword}
                onChange={e => setNewPassword(e.target.value)}
                placeholder="At least 6 characters"
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

          <div style={{ marginBottom: 24 }}>
            <label className="label" style={{ display: 'block', marginBottom: 7 }}>Confirm New Password</label>
            <input
              className="input"
              type={showPw ? 'text' : 'password'}
              value={confirmPassword}
              onChange={e => setConfirmPassword(e.target.value)}
              placeholder="Repeat new password"
              required
            />
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

          {success && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '10px 14px', borderRadius: 9,
              background: '#EAF9EF', border: '1px solid #B7EBC6',
              color: '#1A7F3C', fontSize: 13, marginBottom: 16,
            }}>
              <CheckCircle2 size={14} />{success}
            </div>
          )}

          <button className="btn-primary" type="submit" disabled={loading}
            style={{ width: '100%', justifyContent: 'center', padding: '12px', opacity: loading ? .7 : 1 }}>
            {loading ? 'Resetting…' : 'Reset Password'}
          </button>
        </form>
        )}

        <div style={{ marginTop: 24, textAlign: 'center', fontSize: 13, color: 'var(--muted)' }}>
          Remembered your password?{' '}
          <Link href="/" style={{ color: 'var(--red)', fontWeight: 600, textDecoration: 'none' }}>
            Back to Sign in
          </Link>
>>>>>>> origin/master
        </div>
      </div>
    </div>
  );
}