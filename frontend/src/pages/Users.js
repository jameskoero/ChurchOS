/* eslint-disable no-unused-vars, react-hooks/exhaustive-deps */
import React, { useState, useEffect } from 'react';
import { usersAPI } from '../api';
import { useAuth } from '../contexts/AuthContext';

const ROLES = ['admin', 'pastor', 'secretary', 'treasurer', 'viewer'];
const ROLE_DESC = {
  admin: 'Full system access, user management',
  pastor: 'Read/write access + reports',
  secretary: 'Read/write members & attendance',
  treasurer: 'Finance management + reports',
  viewer: 'Read-only access'
};

const EMPTY_FORM = { username: '', email: '', full_name: '', password: '', role: 'viewer', is_active: true };

function roleBadge(role) {
  const map = { admin: 'badge-danger', pastor: 'badge-gold', treasurer: 'badge-success', secretary: 'badge-info', viewer: 'badge-navy' };
  return <span className={`badge ${map[role] || 'badge-info'}`}>{role}</span>;
}

export default function Users() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [showPassword, setShowPassword] = useState(false);

  const fetchUsers = () => {
    setLoading(true);
    usersAPI.getAll()
      .then(r => setUsers(r.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchUsers(); }, []);

  const openCreate = () => {
    setEditing(null); setForm(EMPTY_FORM); setError(''); setShowPassword(false); setShowModal(true);
  };
  const openEdit = (u) => {
    setEditing(u);
    setForm({ username: u.username, email: u.email, full_name: u.full_name || '', password: '', role: u.role, is_active: u.is_active });
    setError(''); setShowPassword(false); setShowModal(true);
  };

  const handleSave = async (e) => {
    e.preventDefault(); setSaving(true); setError('');
    try {
      const payload = { ...form };
      if (!payload.password) delete payload.password; // don't send empty password on edit
      if (editing) await usersAPI.update(editing.id, payload);
      else await usersAPI.create(payload);
      setShowModal(false); fetchUsers();
    } catch (err) { setError(err.response?.data?.error || 'Save failed'); }
    finally { setSaving(false); }
  };

  const handleDelete = async (id) => {
    try { await usersAPI.delete(id); setDeleteConfirm(null); fetchUsers(); }
    catch (err) { alert(err.response?.data?.error || 'Delete failed'); }
  };

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <h1 style={{ fontFamily: 'var(--font-display)', fontSize: '1.5rem', color: 'var(--navy)' }}>User Management</h1>
          <p style={{ color: 'var(--gray-600)', fontSize: '0.85rem' }}>System access & role assignments</p>
        </div>
        <button className="btn btn-gold" onClick={openCreate}>+ Add User</button>
      </div>

      {/* Role guide */}
      <div className="card" style={{ marginBottom: '1.25rem', padding: '1rem' }}>
        <p style={{ fontSize: '0.78rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--gray-600)', marginBottom: '0.6rem' }}>Role Permissions</p>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          {ROLES.map(r => (
            <div key={r} style={{ fontSize: '0.78rem' }}>
              {roleBadge(r)}
              <span style={{ color: 'var(--gray-600)', marginLeft: '0.4rem' }}>{ROLE_DESC[r]}</span>
            </div>
          ))}
        </div>
      </div>

      {loading ? (
        <div style={{ padding: '3rem', textAlign: 'center' }}>
          <div className="loader" style={{ width: 32, height: 32, borderWidth: 3, margin: '0 auto' }} />
        </div>
      ) : (
        <div className="card" style={{ padding: 0 }}>
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>User</th>
                  <th>Username</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th>Last Login</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map(u => (
                  <tr key={u.id}>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                        <div style={{
                          width: 32, height: 32, borderRadius: '50%', background: 'var(--navy)',
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          color: 'var(--gold)', fontWeight: 700, fontSize: '0.85rem', flexShrink: 0
                        }}>
                          {(u.username || 'U')[0].toUpperCase()}
                        </div>
                        <span style={{ fontWeight: 500 }}>{u.full_name || u.username}</span>
                        {u.id === currentUser?.id && <span className="badge badge-gold" style={{ fontSize: '0.65rem' }}>You</span>}
                      </div>
                    </td>
                    <td style={{ fontFamily: 'monospace', fontSize: '0.85rem' }}>{u.username}</td>
                    <td style={{ fontSize: '0.85rem', color: 'var(--gray-600)' }}>{u.email}</td>
                    <td>{roleBadge(u.role)}</td>
                    <td>
                      <span className={`badge ${u.is_active ? 'badge-success' : 'badge-danger'}`}>
                        {u.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td style={{ fontSize: '0.82rem', color: 'var(--gray-600)' }}>
                      {u.last_login ? new Date(u.last_login).toLocaleDateString('en-KE') : 'Never'}
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: '0.4rem' }}>
                        <button className="btn btn-outline btn-sm" onClick={() => openEdit(u)}>Edit</button>
                        {u.id !== currentUser?.id && (
                          <button className="btn btn-danger btn-sm" onClick={() => setDeleteConfirm(u)}>Del</button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Modal */}
      {showModal && (
        <div className="modal-overlay">
          <div className="modal" style={{ maxWidth: 500 }}>
            <div className="modal-header">
              <span className="modal-title">{editing ? `Edit: ${editing.username}` : 'New User'}</span>
              <button onClick={() => setShowModal(false)} style={{ background: 'none', border: 'none', fontSize: '1.2rem', cursor: 'pointer', color: 'var(--gray-400)' }}>✕</button>
            </div>
            <form onSubmit={handleSave}>
              <div className="modal-body">
                {error && <div className="alert alert-error"><span>⚠</span><span>{error}</span></div>}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                  <div className="form-group">
                    <label className="form-label">Username *</label>
                    <input className="form-control" value={form.username} onChange={e => set('username', e.target.value)}
                      required disabled={!!editing} style={editing ? { background: 'var(--gray-100)' } : {}} />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Full Name</label>
                    <input className="form-control" value={form.full_name} onChange={e => set('full_name', e.target.value)} />
                  </div>
                  <div className="form-group" style={{ gridColumn: '1/-1' }}>
                    <label className="form-label">Email *</label>
                    <input className="form-control" type="email" value={form.email} onChange={e => set('email', e.target.value)} required />
                  </div>
                  <div className="form-group" style={{ gridColumn: '1/-1' }}>
                    <label className="form-label">{editing ? 'New Password (leave blank to keep)' : 'Password *'}</label>
                    <div style={{ position: 'relative' }}>
                      <input className="form-control" type={showPassword ? 'text' : 'password'}
                        value={form.password} onChange={e => set('password', e.target.value)}
                        required={!editing} minLength={8} style={{ paddingRight: '3rem' }}
                        placeholder="Min. 8 characters" />
                      <button type="button" onClick={() => setShowPassword(!showPassword)}
                        style={{ position: 'absolute', right: '0.75rem', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--gray-400)' }}>
                        {showPassword ? '🙈' : '👁'}
                      </button>
                    </div>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Role *</label>
                    <select className="form-control" value={form.role} onChange={e => set('role', e.target.value)} required>
                      {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
                    </select>
                    <small style={{ color: 'var(--gray-600)', fontSize: '0.75rem', marginTop: '0.3rem', display: 'block' }}>
                      {ROLE_DESC[form.role]}
                    </small>
                  </div>
                  <div className="form-group">
                    <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '1.5rem', cursor: 'pointer' }}>
                      <input type="checkbox" checked={form.is_active} onChange={e => set('is_active', e.target.checked)} />
                      <span style={{ fontSize: '0.875rem', fontWeight: 500 }}>Account active</span>
                    </label>
                  </div>
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-outline" onClick={() => setShowModal(false)}>Cancel</button>
                <button type="submit" className="btn btn-gold" disabled={saving}>
                  {saving ? <><span className="loader" style={{ width: 14, height: 14 }} /> Saving...</> : (editing ? 'Update User' : 'Create User')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {deleteConfirm && (
        <div className="modal-overlay">
          <div className="modal" style={{ maxWidth: 380 }}>
            <div className="modal-header"><span className="modal-title">Delete User?</span></div>
            <div className="modal-body">
              <p>Delete user <strong>{deleteConfirm.username}</strong>? This action cannot be undone.</p>
            </div>
            <div className="modal-footer">
              <button className="btn btn-outline" onClick={() => setDeleteConfirm(null)}>Cancel</button>
              <button className="btn btn-danger" onClick={() => handleDelete(deleteConfirm.id)}>Delete</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
