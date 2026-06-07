/* eslint-disable no-unused-vars, react-hooks/exhaustive-deps */
import React, { useState, useEffect, useCallback } from 'react';
import { membersAPI } from '../api';
import { useAuth } from '../contexts/AuthContext';

const STATUSES = ['active', 'inactive', 'transferred', 'deceased'];
const GENDERS = ['Male', 'Female'];
const MARITAL = ['Single', 'Married', 'Widowed', 'Divorced'];

const EMPTY_FORM = {
  first_name: '', last_name: '', email: '', phone: '', gender: '',
  date_of_birth: '', address: '', occupation: '', marital_status: '',
  next_of_kin: '', next_of_kin_phone: '', cell_group: '',
  baptism_date: '', date_joined: '', membership_status: 'active', notes: ''
};

function statusBadge(status) {
  const map = {
    active: 'badge-success', inactive: 'badge-warning',
    transferred: 'badge-info', deceased: 'badge-danger'
  };
  return <span className={`badge ${map[status] || 'badge-info'}`}>{status}</span>;
}

export default function Members() {
  const { can } = useAuth();
  const [members, setMembers] = useState([]);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('active');
  const [genderFilter, setGenderFilter] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [deleteConfirm, setDeleteConfirm] = useState(null);

  const fetchMembers = useCallback(() => {
    setLoading(true);
    membersAPI.getAll({
      page, per_page: 20,
      search, status: statusFilter, gender: genderFilter
    })
      .then(r => {
        setMembers(r.data.members);
        setTotal(r.data.total);
        setPages(r.data.pages);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [page, search, statusFilter, genderFilter]);

  useEffect(() => { fetchMembers(); }, [fetchMembers]);

  useEffect(() => { setPage(1); }, [search, statusFilter, genderFilter]);

  const openCreate = () => {
    setEditing(null);
    setForm(EMPTY_FORM);
    setError('');
    setShowModal(true);
  };

  const openEdit = (m) => {
    setEditing(m);
    setForm({
      first_name: m.first_name || '', last_name: m.last_name || '',
      email: m.email || '', phone: m.phone || '', gender: m.gender || '',
      date_of_birth: m.date_of_birth || '', address: m.address || '',
      occupation: m.occupation || '', marital_status: m.marital_status || '',
      next_of_kin: m.next_of_kin || '', next_of_kin_phone: m.next_of_kin_phone || '',
      cell_group: m.cell_group || '', baptism_date: m.baptism_date || '',
      date_joined: m.date_joined || '', membership_status: m.membership_status || 'active',
      notes: m.notes || ''
    });
    setError('');
    setShowModal(true);
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      if (editing) {
        await membersAPI.update(editing.id, form);
      } else {
        await membersAPI.create(form);
      }
      setShowModal(false);
      fetchMembers();
    } catch (err) {
      setError(err.response?.data?.error || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id) => {
    try {
      await membersAPI.delete(id);
      setDeleteConfirm(null);
      fetchMembers();
    } catch (err) {
      alert(err.response?.data?.error || 'Delete failed');
    }
  };

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <h1 style={{ fontFamily: 'var(--font-display)', fontSize: '1.5rem', color: 'var(--navy)' }}>Members</h1>
          <p style={{ color: 'var(--gray-600)', fontSize: '0.85rem' }}>Total: {total} records</p>
        </div>
        {can('write') && (
          <button className="btn btn-gold" onClick={openCreate}>+ Add Member</button>
        )}
      </div>

      {/* Filters */}
      <div className="card" style={{ marginBottom: '1rem', padding: '1rem' }}>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <input
            className="form-control"
            placeholder="Search name, ID, phone..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{ maxWidth: 280 }}
          />
          <select className="form-control" value={statusFilter} onChange={e => setStatusFilter(e.target.value)} style={{ maxWidth: 150 }}>
            <option value="">All Statuses</option>
            {STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          <select className="form-control" value={genderFilter} onChange={e => setGenderFilter(e.target.value)} style={{ maxWidth: 130 }}>
            <option value="">All Genders</option>
            {GENDERS.map(g => <option key={g} value={g}>{g}</option>)}
          </select>
          {(search || statusFilter !== 'active' || genderFilter) && (
            <button className="btn btn-outline btn-sm" onClick={() => { setSearch(''); setStatusFilter('active'); setGenderFilter(''); }}>
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="card" style={{ padding: 0 }}>
        <div className="table-wrapper">
          {loading ? (
            <div style={{ padding: '3rem', textAlign: 'center' }}>
              <div className="loader" style={{ width: 32, height: 32, borderWidth: 3, margin: '0 auto' }} />
            </div>
          ) : members.length === 0 ? (
            <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--gray-400)' }}>
              No members found
            </div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Name</th>
                  <th>Phone</th>
                  <th>Gender</th>
                  <th>Cell Group</th>
                  <th>Status</th>
                  <th>Joined</th>
                  {can('write') && <th>Actions</th>}
                </tr>
              </thead>
              <tbody>
                {members.map(m => (
                  <tr key={m.id}>
                    <td><span style={{ fontFamily: 'monospace', fontSize: '0.8rem', color: 'var(--gold)', fontWeight: 600 }}>{m.member_id}</span></td>
                    <td style={{ fontWeight: 500 }}>{m.full_name}</td>
                    <td>{m.phone || '—'}</td>
                    <td>{m.gender || '—'}</td>
                    <td>{m.cell_group || '—'}</td>
                    <td>{statusBadge(m.membership_status)}</td>
                    <td style={{ fontSize: '0.82rem', color: 'var(--gray-600)' }}>{m.date_joined || '—'}</td>
                    {can('write') && (
                      <td>
                        <div style={{ display: 'flex', gap: '0.4rem' }}>
                          <button className="btn btn-outline btn-sm" onClick={() => openEdit(m)}>Edit</button>
                          {can('delete') && (
                            <button className="btn btn-danger btn-sm" onClick={() => setDeleteConfirm(m)}>Del</button>
                          )}
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Pagination */}
        {pages > 1 && (
          <div className="pagination" style={{ borderTop: '1px solid var(--gray-200)' }}>
            <button className="page-btn" disabled={page === 1} onClick={() => setPage(p => p - 1)}>‹</button>
            {[...Array(pages)].map((_, i) => (
              <button key={i} className={`page-btn ${page === i + 1 ? 'active' : ''}`} onClick={() => setPage(i + 1)}>
                {i + 1}
              </button>
            ))}
            <button className="page-btn" disabled={page === pages} onClick={() => setPage(p => p + 1)}>›</button>
          </div>
        )}
      </div>

      {/* Add/Edit Modal */}
      {showModal && (
        <div className="modal-overlay">
          <div className="modal">
            <div className="modal-header">
              <span className="modal-title">{editing ? `Edit: ${editing.full_name}` : 'New Member'}</span>
              <button onClick={() => setShowModal(false)} style={{ background: 'none', border: 'none', fontSize: '1.2rem', cursor: 'pointer', color: 'var(--gray-400)' }}>✕</button>
            </div>
            <form onSubmit={handleSave}>
              <div className="modal-body">
                {error && <div className="alert alert-error"><span>⚠</span><span>{error}</span></div>}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                  <div className="form-group">
                    <label className="form-label">First Name *</label>
                    <input className="form-control" value={form.first_name} onChange={e => set('first_name', e.target.value)} required />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Last Name *</label>
                    <input className="form-control" value={form.last_name} onChange={e => set('last_name', e.target.value)} required />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Phone</label>
                    <input className="form-control" value={form.phone} onChange={e => set('phone', e.target.value)} />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Email</label>
                    <input className="form-control" type="email" value={form.email} onChange={e => set('email', e.target.value)} />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Gender</label>
                    <select className="form-control" value={form.gender} onChange={e => set('gender', e.target.value)}>
                      <option value="">Select</option>
                      {GENDERS.map(g => <option key={g}>{g}</option>)}
                    </select>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Date of Birth</label>
                    <input className="form-control" type="date" value={form.date_of_birth} onChange={e => set('date_of_birth', e.target.value)} />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Marital Status</label>
                    <select className="form-control" value={form.marital_status} onChange={e => set('marital_status', e.target.value)}>
                      <option value="">Select</option>
                      {MARITAL.map(m => <option key={m}>{m}</option>)}
                    </select>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Occupation</label>
                    <input className="form-control" value={form.occupation} onChange={e => set('occupation', e.target.value)} />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Cell Group</label>
                    <input className="form-control" value={form.cell_group} onChange={e => set('cell_group', e.target.value)} />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Status</label>
                    <select className="form-control" value={form.membership_status} onChange={e => set('membership_status', e.target.value)}>
                      {STATUSES.map(s => <option key={s}>{s}</option>)}
                    </select>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Date Joined</label>
                    <input className="form-control" type="date" value={form.date_joined} onChange={e => set('date_joined', e.target.value)} />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Baptism Date</label>
                    <input className="form-control" type="date" value={form.baptism_date} onChange={e => set('baptism_date', e.target.value)} />
                  </div>
                  <div className="form-group" style={{ gridColumn: '1/-1' }}>
                    <label className="form-label">Address</label>
                    <textarea className="form-control" value={form.address} onChange={e => set('address', e.target.value)} rows={2} />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Next of Kin</label>
                    <input className="form-control" value={form.next_of_kin} onChange={e => set('next_of_kin', e.target.value)} />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Next of Kin Phone</label>
                    <input className="form-control" value={form.next_of_kin_phone} onChange={e => set('next_of_kin_phone', e.target.value)} />
                  </div>
                  <div className="form-group" style={{ gridColumn: '1/-1' }}>
                    <label className="form-label">Notes</label>
                    <textarea className="form-control" value={form.notes} onChange={e => set('notes', e.target.value)} rows={2} />
                  </div>
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-outline" onClick={() => setShowModal(false)}>Cancel</button>
                <button type="submit" className="btn btn-gold" disabled={saving}>
                  {saving ? <><span className="loader" style={{ width: 14, height: 14 }} /> Saving...</> : (editing ? 'Update' : 'Create Member')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirm */}
      {deleteConfirm && (
        <div className="modal-overlay">
          <div className="modal" style={{ maxWidth: 380 }}>
            <div className="modal-header">
              <span className="modal-title">Confirm Delete</span>
            </div>
            <div className="modal-body">
              <p>Delete member <strong>{deleteConfirm.full_name}</strong> ({deleteConfirm.member_id})?</p>
              <p style={{ color: 'var(--danger)', fontSize: '0.85rem', marginTop: '0.5rem' }}>This action cannot be undone.</p>
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
