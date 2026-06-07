/* eslint-disable no-unused-vars, react-hooks/exhaustive-deps */
import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { authAPI } from '../api';

export default function Profile() {
  const { user } = useAuth();
  const [pwdForm, setPwdForm] = useState({ current_password: '', new_password: '', confirm_password: '' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const handlePasswordChange = async (e) => {
    e.preventDefault();
    setError(''); setSuccess('');
    if (pwdForm.new_password !== pwdForm.confirm_password) {
      setError('New passwords do not match'); return;
    }
    if (pwdForm.new_password.length < 8) {
      setError('Password must be at least 8 characters'); return;
    }
    setSaving(true);
    try {
      await authAPI.changePassword({
        current_password: pwdForm.current_password,
        new_password: pwdForm.new_password
      });
      setSuccess('Password updated successfully');
      setPwdForm({ current_password: '', new_password: '', confirm_password: '' });
    } catch (err) {
      setError(err.response?.data?.error || 'Password change failed');
    } finally { setSaving(false); }
  };

  const ROLE_DESC = {
    admin: 'Full system access, user management',
    pastor: 'Read/write access + reports',
    secretary: 'Read/write members & attendance',
    treasurer: 'Finance management + reports',
    viewer: 'Read-only access'
  };

  return (
    <div style={{ maxWidth: 640 }}>
      <h1 style={{ fontFamily: 'var(--font-display)', fontSize: '1.5rem', color: 'var(--navy)', marginBottom: '1.5rem' }}>
        My Profile
      </h1>

      {/* Profile card */}
      <div className="card" style={{ marginBottom: '1.25rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem', marginBottom: '1.5rem' }}>
          <div style={{
            width: 64, height: 64, borderRadius: '50%',
            background: 'var(--navy)', display: 'flex', alignItems: 'center',
            justifyContent: 'center', color: 'var(--gold)', fontWeight: 700, fontSize: '1.5rem', flexShrink: 0
          }}>
            {(user?.username || 'U')[0].toUpperCase()}
          </div>
          <div>
            <h2 style={{ fontSize: '1.2rem', fontWeight: 600, color: 'var(--navy)' }}>
              {user?.full_name || user?.username}
            </h2>
            <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.3rem', flexWrap: 'wrap' }}>
              <span className="badge badge-navy" style={{ textTransform: 'capitalize' }}>{user?.role}</span>
              <span className="badge badge-success">{user?.is_active ? 'Active' : 'Inactive'}</span>
            </div>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
          {[
            { label: 'Username', value: user?.username },
            { label: 'Email', value: user?.email },
            { label: 'Role', value: user?.role },
            { label: 'Permissions', value: ROLE_DESC[user?.role] || '—' },
            { label: 'Account Created', value: user?.created_at ? new Date(user.created_at).toLocaleDateString('en-KE') : '—' },
            { label: 'Last Login', value: user?.last_login ? new Date(user.last_login).toLocaleString('en-KE') : 'This session' },
          ].map(item => (
            <div key={item.label}>
              <div style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--gray-600)', marginBottom: '0.25rem' }}>
                {item.label}
              </div>
              <div style={{ fontSize: '0.9rem', color: 'var(--navy)', wordBreak: 'break-all' }}>{item.value || '—'}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Change Password */}
      <div className="card">
        <h3 style={{ fontFamily: 'var(--font-display)', fontSize: '1.1rem', color: 'var(--navy)', marginBottom: '1.25rem' }}>
          Change Password
        </h3>
        {error && <div className="alert alert-error"><span>⚠</span><span>{error}</span></div>}
        {success && <div className="alert alert-success"><span>✓</span><span>{success}</span></div>}
        <form onSubmit={handlePasswordChange}>
          <div className="form-group">
            <label className="form-label">Current Password</label>
            <input className="form-control" type="password" value={pwdForm.current_password}
              onChange={e => setPwdForm(f => ({ ...f, current_password: e.target.value }))} required />
          </div>
          <div className="form-group">
            <label className="form-label">New Password</label>
            <input className="form-control" type="password" value={pwdForm.new_password}
              onChange={e => setPwdForm(f => ({ ...f, new_password: e.target.value }))} required minLength={8}
              placeholder="Min. 8 characters" />
          </div>
          <div className="form-group">
            <label className="form-label">Confirm New Password</label>
            <input className="form-control" type="password" value={pwdForm.confirm_password}
              onChange={e => setPwdForm(f => ({ ...f, confirm_password: e.target.value }))} required />
          </div>
          <button type="submit" className="btn btn-gold" disabled={saving} style={{ marginTop: '0.5rem' }}>
            {saving ? <><span className="loader" style={{ width: 14, height: 14 }} /> Updating...</> : 'Update Password'}
          </button>
        </form>
      </div>

      {/* System info */}
      <div className="card" style={{ marginTop: '1.25rem', background: 'var(--navy)', color: 'var(--white)' }}>
        <p style={{ color: 'var(--gold)', fontFamily: 'var(--font-display)', fontSize: '0.95rem', marginBottom: '0.5rem' }}>
          ChurchOS · Church Management Platform
        </p>
        <p style={{ fontSize: '0.78rem', color: 'rgba(255,255,255,0.5)', lineHeight: 1.6 }}>
          Church Digital Management System<br />
          Migosi Region, Kisumu, Kenya<br />
          Version 2.0.0 · Built with Flask + React
        </p>
      </div>
    </div>
  );
}
