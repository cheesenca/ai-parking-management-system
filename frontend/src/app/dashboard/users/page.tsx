'use client';
import { useState, useEffect, useCallback } from 'react';
import type { ManagedUser, Zone, Role } from '@/types';
import { useAuth } from '@/context/AuthContext';
import { apiGetUsers, apiCreateUser, apiUpdateUser, apiDeleteUser } from '@/lib/backendApi';
import { UserPlus, Pencil, Trash2, X, Check, ShieldCheck, RefreshCw, Eye, EyeOff, CheckCircle2 } from 'lucide-react';

type ModalType = 'add' | 'edit' | null;

interface FormState {
  username: string;
  email: string;
  password: string;
  role: Role;
  location: Zone;
}

const EMPTY_FORM: FormState = {
  username: '', email: '', password: '', role: 'Security', location: 'west',
};

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '9px 12px',
  borderRadius: 9,
  border: '1px solid var(--border)',
  background: 'var(--bg)',
  color: 'var(--ink)',
  fontSize: 13,
  outline: 'none',
  fontFamily: 'var(--font-body)',
  boxSizing: 'border-box',
};

const labelStyle: React.CSSProperties = {
  fontSize: 11,
  fontWeight: 700,
  color: 'var(--muted)',
  textTransform: 'uppercase',
  letterSpacing: '0.06em',
  marginBottom: 6,
  display: 'block',
};

const roleBadge: Record<Role, string> = {
  Admin: 'badge-navy',
  Security: 'badge-blue',
};

export default function UsersPage() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<ManagedUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [saving, setSaving] = useState(false);
  const [modal, setModal] = useState<ModalType>(null);
  const [editUser, setEditUser] = useState<ManagedUser | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [formError, setFormError] = useState('');
  const [showPw, setShowPw] = useState(false);

  const fetchUsers = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const res = await apiGetUsers();
      setUsers(res);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void fetchUsers(); }, [fetchUsers]);

  const openAdd = () => { setForm(EMPTY_FORM); setFormError(''); setShowPw(false); setModal('add'); };
  const openEdit = (u: ManagedUser) => {
    setEditUser(u);
    setForm({ username: u.username, email: u.email, password: '', role: u.role, location: u.location || 'west' });
    setFormError(''); setShowPw(false); setModal('edit');
  };
  const closeModal = () => { setModal(null); setEditUser(null); setFormError(''); };

  const handleSave = async () => {
    if (!form.username || !form.email || (modal === 'add' && !form.password)) {
      setFormError('Username, Email, and Password are mandatory fields.');
      return;
    }
    if (form.password && form.password.length < 6) {
      setFormError('Password minimal 6 karakter.');
      return;
    }
    setSaving(true); setFormError('');
    try {
      if (modal === 'add') {
        await apiCreateUser({
          username: form.username,
          email: form.email,
          password: form.password,
          role: form.role,
          location: form.role === 'Admin' ? undefined : form.location,
        });
        setNotice(`Account "${form.username}" created successfully.`);
      } else if (modal === 'edit' && editUser) {
        const payload: Record<string, string> = {
          username: form.username,
          email: form.email,
          role: form.role,
        };
        if (form.role !== 'Admin') payload.location = form.location;
        if (form.password) payload.password = form.password;
        await apiUpdateUser(editUser.admin_id, payload);
        setNotice(`Account "${form.username}" updated successfully.`);
      }
      closeModal();
      void fetchUsers();
    } catch (e) {
      setFormError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (u: ManagedUser) => {
    if (!window.confirm(`Hapus akun "${u.username}"?`)) return;
    setSaving(true); setError('');
    try {
      await apiDeleteUser(u.admin_id);
      void fetchUsers();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <div className="page-pad fadein">
        {/* Header */}
        <div className="lst-header">
          <div>
            <h1 className="tr-title">User Management</h1>
            <p className="tr-subtitle">
              Manage Admin & Security accounts · {loading ? '…' : `${users.length} total`}
            </p>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={() => void fetchUsers()} className="btn-secondary" style={{ fontSize: 12 }} disabled={loading}>
              <RefreshCw size={13} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
            </button>
            <button onClick={openAdd} className="btn-primary" style={{ fontSize: 12 }}>
              <UserPlus size={13} /> Add Account
            </button>
          </div>
        </div>

        {notice && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '10px 14px', borderRadius: 9, background: 'var(--green-bg)',
            border: '1px solid #B7EBC6', color: 'var(--green-text)', fontSize: 13, marginBottom: 16,
          }}>
            <CheckCircle2 size={14} /> {notice}
          </div>
        )}

        {error && (
          <div style={{ padding: '10px 14px', borderRadius: 9, background: 'var(--danger-bg)', border: '1px solid var(--red-mid)', color: 'var(--danger-text)', fontSize: 13, marginBottom: 16 }}>
            {error}
          </div>
        )}

        <div style={{
          display: 'flex', alignItems: 'center', gap: 8, marginBottom: 18,
          padding: '10px 14px', borderRadius: 9, background: 'var(--card2)', border: '1px solid var(--border)',
          fontSize: 12.5, color: 'var(--muted)',
        }}>
          <ShieldCheck size={14} color="var(--red)" />
          Self-service Sign Up has been disabled for security. Only Admins can create or manage accounts here.
        </div>

        {/* Table */}
        <div className="card" style={{ overflow: 'hidden' }}>
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table lst-table">
              <thead>
                <tr>
                  <th>Username</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Plant</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr><td colSpan={5} style={{ textAlign: 'center', padding: 40, color: 'var(--muted)' }}>Memuat data…</td></tr>
                ) : users.length === 0 ? (
                  <tr><td colSpan={5}>
                    <div className="lst-empty">
                      <UserPlus size={22} />
                      <span>No accounts found.</span>
                    </div>
                  </td></tr>
                ) : users.map(u => (
                  <tr key={u.admin_id} style={{ opacity: saving ? 0.6 : 1 }}>
                    <td style={{ fontWeight: 600 }}>{u.username}{currentUser?.username === u.username && (
                      <span style={{ marginLeft: 8, fontSize: 10, fontWeight: 700, color: 'var(--muted)' }}>(you)</span>
                    )}</td>
                    <td style={{ fontSize: 12.5, color: 'var(--muted)' }}>{u.email}</td>
                    <td><span className={`badge ${roleBadge[u.role]}`}>{u.role}</span></td>
                    <td style={{ fontSize: 12.5 }}>{u.location ? u.location.toUpperCase() : '—'}</td>
                    <td>
                      <div style={{ display: 'flex', gap: 4 }}>
                        <button onClick={() => openEdit(u)} className="btn-secondary" style={{ padding: '4px 8px' }}><Pencil size={11} /></button>
                        <button
                          onClick={() => void handleDelete(u)}
                          className="btn-secondary"
                          style={{ padding: '4px 8px', color: 'var(--red)' }}
                          disabled={currentUser?.username === u.username}
                          title={currentUser?.username === u.username ? "You can't delete your own account" : 'Delete account'}
                        >
                          <Trash2 size={11} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Modal Add / Edit */}
      {modal && (
        <div className="mem-modal-overlay">
          <div className="mem-modal fadein" style={{ maxWidth: 460 }}>
            <div className="mem-modal-header">
              <h3 style={{ fontSize: 16, fontWeight: 800, color: 'var(--ink)', margin: 0 }}>
                {modal === 'add' ? '+ Add Account' : 'Edit Account'}
              </h3>
              <button onClick={closeModal} className="mem-modal-close">
                <X size={18} />
              </button>
            </div>

            <div style={{ padding: '24px' }}>
              {formError && (
                <div style={{ padding: '10px 14px', borderRadius: 9, background: 'var(--danger-bg)', border: '1px solid var(--red-mid)', color: 'var(--danger-text)', fontSize: 13, marginBottom: 16 }}>
                  {formError}
                </div>
              )}

              <div style={{ marginBottom: 16 }}>
                <label style={labelStyle}>Username</label>
                <input style={inputStyle} value={form.username}
                  onChange={e => setForm(p => ({ ...p, username: e.target.value }))}
                  placeholder="e.g. westsec2" />
              </div>

              <div style={{ marginBottom: 16 }}>
                <label style={labelStyle}>Email</label>
                <input style={inputStyle} type="email" value={form.email}
                  onChange={e => setForm(p => ({ ...p, email: e.target.value }))}
                  placeholder="name@company.com" />
              </div>

              <div className="grid-2" style={{ gap: 12, marginBottom: 16 }}>
                <div>
                  <label style={labelStyle}>Role</label>
                  <select style={inputStyle} value={form.role}
                    onChange={e => setForm(p => ({ ...p, role: e.target.value as Role }))}>
                    <option value="Security">Security</option>
                    <option value="Admin">Admin</option>
                  </select>
                </div>
                {form.role !== 'Admin' && (
                  <div>
                    <label style={labelStyle}>Plant</label>
                    <select style={inputStyle} value={form.location}
                      onChange={e => setForm(p => ({ ...p, location: e.target.value as Zone }))}>
                      <option value="west">West</option>
                      <option value="east">East</option>
                    </select>
                  </div>
                )}
              </div>

              <div>
                <label style={labelStyle}>{modal === 'add' ? 'Password' : 'New Password (optional)'}</label>
                <div style={{ position: 'relative' }}>
                  <input
                    style={{ ...inputStyle, paddingRight: 44 }}
                    type={showPw ? 'text' : 'password'}
                    value={form.password}
                    onChange={e => setForm(p => ({ ...p, password: e.target.value }))}
                    placeholder={modal === 'add' ? 'At least 6 characters' : 'Leave blank to keep current password'}
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
            </div>

            <div style={{
              display: 'flex', gap: 10, justifyContent: 'flex-end',
              padding: '16px 24px', borderTop: '1px solid var(--border)',
              flexShrink: 0,
            }}>
              <button onClick={closeModal} className="btn-secondary" style={{ fontSize: 13 }}>Cancel</button>
              <button onClick={() => void handleSave()} className="btn-primary" style={{ fontSize: 13 }} disabled={saving}>
                <Check size={13} /> {saving ? 'Saving…' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}