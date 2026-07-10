'use client';
import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/AuthContext';
import { Eye, EyeOff, AlertCircle, CheckCircle2 } from 'lucide-react';

export default function RegisterPage() {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [role, setRole] = useState('Security');
  const [location, setLocation] = useState('west');
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);
  const { register } = useAuth();
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (password !== confirmPassword) {
      setError('Password dan konfirmasi password tidak sama.');
      return;
    }
    if (password.length < 6) {
      setError('Password minimal 6 karakter.');
      return;
    }

    setLoading(true);
    const res = await register({
      username,
      email,
      password,
      role,
      location: role === 'Admin' ? undefined : location,
    });
    setLoading(false);

    if (res.ok) {
      setSuccess('Registrasi berhasil! Mengarahkan ke halaman login…');
      setTimeout(() => router.push('/'), 1200);
    } else {
      setError(res.message || 'Registrasi gagal. Silakan coba lagi.');
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

      <div style={{
        width: '100%', maxWidth: 460, borderRadius: 20, overflow: 'hidden',
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
          Create an account
        </h2>
        <p style={{ fontSize: 13, color: 'var(--muted)', marginBottom: 28 }}>
          Sign up to get access to the parking management dashboard.
        </p>

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 16 }}>
            <label className="label" style={{ display: 'block', marginBottom: 7 }}>Username</label>
            <input
              className="input" type="text" value={username}
              onChange={e => setUsername(e.target.value)}
              placeholder="e.g. westsec2"
              required
            />
          </div>

          <div style={{ marginBottom: 16 }}>
            <label className="label" style={{ display: 'block', marginBottom: 7 }}>Email</label>
            <input
              className="input" type="email" value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="name@company.com"
              required
            />
          </div>

          <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
            <div style={{ flex: 1 }}>
              <label className="label" style={{ display: 'block', marginBottom: 7 }}>Role</label>
              <select
                className="input" value={role}
                onChange={e => setRole(e.target.value)}
              >
                <option value="Security">Security</option>
                <option value="Admin">Admin</option>
              </select>
            </div>
            {role !== 'Admin' && (
              <div style={{ flex: 1 }}>
                <label className="label" style={{ display: 'block', marginBottom: 7 }}>Plant</label>
                <select
                  className="input" value={location}
                  onChange={e => setLocation(e.target.value)}
                >
                  <option value="west">West</option>
                  <option value="east">East</option>
                </select>
              </div>
            )}
          </div>

          <div style={{ marginBottom: 16 }}>
            <label className="label" style={{ display: 'block', marginBottom: 7 }}>Password</label>
            <div style={{ position: 'relative' }}>
              <input
                className="input"
                type={showPw ? 'text' : 'password'}
                value={password}
                onChange={e => setPassword(e.target.value)}
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
            <label className="label" style={{ display: 'block', marginBottom: 7 }}>Confirm Password</label>
            <input
              className="input"
              type={showPw ? 'text' : 'password'}
              value={confirmPassword}
              onChange={e => setConfirmPassword(e.target.value)}
              placeholder="Repeat password"
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
            {loading ? 'Creating account…' : 'Sign Up'}
          </button>
        </form>

        <div style={{ marginTop: 24, textAlign: 'center', fontSize: 13, color: 'var(--muted)' }}>
          Already have an account?{' '}
          <Link href="/" style={{ color: 'var(--red)', fontWeight: 600, textDecoration: 'none' }}>
            Sign in
          </Link>
        </div>
      </div>
    </div>
  );
}
