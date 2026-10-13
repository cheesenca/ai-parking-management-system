'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
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
  };

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #E5002B 0%, #B80022 50%, #870019 100%)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 24, position: 'relative', overflow: 'hidden',
    }}>
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
        </div>
      </div>
    </div>
  );
}