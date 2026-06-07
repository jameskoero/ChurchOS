/* eslint-disable no-unused-vars, react-hooks/exhaustive-deps */
import React, { useState, useEffect, useCallback } from 'react';
import { attendanceAPI, membersAPI } from '../api';
import { useAuth } from '../contexts/AuthContext';

const TODAY = new Date().toISOString().split('T')[0];

export default function Attendance() {
  const { can } = useAuth();
  const [records, setRecords] = useState([]);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [serviceTypes, setServiceTypes] = useState([]);
  const [summary, setSummary] = useState(null);

  // Filters
  const [filterService, setFilterService] = useState('');
  const [filterDateFrom, setFilterDateFrom] = useState('');
  const [filterDateTo, setFilterDateTo] = useState('');

  // Mark attendance modal
  const [showModal, setShowModal] = useState(false);
  const [members, setMembers] = useState([]);
  const [memberSearch, setMemberSearch] = useState('');
  const [selectedMemberId, setSelectedMemberId] = useState('');
  const [markService, setMarkService] = useState('Sunday Morning');
  const [markDate, setMarkDate] = useState(TODAY);
  const [markNotes, setMarkNotes] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [deleteConfirm, setDeleteConfirm] = useState(null);

  const fetchRecords = useCallback(() => {
    setLoading(true);
    attendanceAPI.getAll({
      page, per_page: 25,
      service_type: filterService,
      date_from: filterDateFrom,
      date_to: filterDateTo,
    })
      .then(r => {
        setRecords(r.data.records);
        setTotal(r.data.total);
        setPages(r.data.pages);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [page, filterService, filterDateFrom, filterDateTo]);

  useEffect(() => { fetchRecords(); }, [fetchRecords]);
  useEffect(() => { setPage(1); }, [filterService, filterDateFrom, filterDateTo]);

  useEffect(() => {
    attendanceAPI.getServiceTypes().then(r => setServiceTypes(r.data));
    attendanceAPI.getSummary().then(r => setSummary(r.data)).catch(() => {});
  }, []);

  // Load members for dropdown when modal opens
  useEffect(() => {
    if (!showModal) return;
    membersAPI.getAll({ per_page: 200, status: 'active', search: memberSearch })
      .then(r => setMembers(r.data.members))
      .catch(console.error);
  }, [showModal, memberSearch]);

  const handleMark = async (e) => {
    e.preventDefault();
    if (!selectedMemberId) { setError('Please select a member'); return; }
    setSaving(true);
    setError('');
    try {
      await attendanceAPI.create({
        member_id: parseInt(selectedMemberId),
        service_type: markService,
        service_date: markDate,
        notes: markNotes
      });
      setShowModal(false);
      setSelectedMemberId('');
      setMemberSearch('');
      setMarkNotes('');
      fetchRecords();
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to mark attendance');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id) => {
    try {
      await attendanceAPI.delete(id);
      setDeleteConfirm(null);
      fetchRecords();
    } catch (err) {
      alert(err.response?.data?.error || 'Delete failed');
    }
  };

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <h1 style={{ fontFamily: 'var(--font-display)', fontSize: '1.5rem', color: 'var(--navy)' }}>Attendance</h1>
          <p style={{ color: 'var(--gray-600)', fontSize: '0.85rem' }}>Total records: {total}</p>
        </div>
        {can('write') && (
          <button className="btn btn-gold" onClick={() => { setError(''); setShowModal(true); }}>
            ✅ Mark Attendance
          </button>
        )}
      </div>

      {/* Summary Cards */}
      {summary && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '1rem', marginBottom: '1.25rem' }}>
          {[
            { label: 'This Month', value: summary.this_month_total, icon: '📆' },
            { label: 'Total Records', value: summary.total_records, icon: '📋' },
            { label: 'Top Attendee', value: summary.top_attendees?.[0]?.name?.split(' ')[0] || '—', icon: '🏆' },
          ].map(c => (
            <div key={c.label} className="card" style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '1rem' }}>
              <span style={{ fontSize: '1.5rem' }}>{c.icon}</span>
              <div>
                <div style={{ fontWeight: 700, fontSize: '1.2rem', color: 'var(--navy)' }}>{c.value}</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--gray-600)' }}>{c.label}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Filters */}
      <div className="card" style={{ marginBottom: '1rem', padding: '1rem' }}>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <select className="form-control" value={filterService} onChange={e => setFilterService(e.target.value)} style={{ maxWidth: 200 }}>
            <option value="">All Service Types</option>
            {serviceTypes.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          <input className="form-control" type="date" value={filterDateFrom} onChange={e => setFilterDateFrom(e.target.value)}
            style={{ maxWidth: 160 }} title="Date from" />
          <input className="form-control" type="date" value={filterDateTo} onChange={e => setFilterDateTo(e.target.value)}
            style={{ maxWidth: 160 }} title="Date to" />
          {(filterService || filterDateFrom || filterDateTo) && (
            <button className="btn btn-outline btn-sm" onClick={() => { setFilterService(''); setFilterDateFrom(''); setFilterDateTo(''); }}>
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
          ) : records.length === 0 ? (
            <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--gray-400)' }}>
              No attendance records found
            </div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Member</th>
                  <th>Member ID</th>
                  <th>Service</th>
                  <th>Notes</th>
                  {can('write') && <th>Actions</th>}
                </tr>
              </thead>
              <tbody>
                {records.map(r => (
                  <tr key={r.id}>
                    <td style={{ fontWeight: 500 }}>{r.service_date}</td>
                    <td>{r.member_name}</td>
                    <td><span style={{ fontFamily: 'monospace', fontSize: '0.8rem', color: 'var(--gold)', fontWeight: 600 }}>{r.member_code}</span></td>
                    <td><span className="badge badge-navy" style={{ fontSize: '0.72rem' }}>{r.service_type}</span></td>
                    <td style={{ color: 'var(--gray-600)', fontSize: '0.85rem' }}>{r.notes || '—'}</td>
                    {can('write') && (
                      <td>
                        <button className="btn btn-danger btn-sm" onClick={() => setDeleteConfirm(r)}>Del</button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {pages > 1 && (
          <div className="pagination" style={{ borderTop: '1px solid var(--gray-200)' }}>
            <button className="page-btn" disabled={page === 1} onClick={() => setPage(p => p - 1)}>‹</button>
            {[...Array(Math.min(pages, 7))].map((_, i) => (
              <button key={i} className={`page-btn ${page === i + 1 ? 'active' : ''}`} onClick={() => setPage(i + 1)}>{i + 1}</button>
            ))}
            <button className="page-btn" disabled={page === pages} onClick={() => setPage(p => p + 1)}>›</button>
          </div>
        )}
      </div>

      {/* Mark Attendance Modal */}
      {showModal && (
        <div className="modal-overlay">
          <div className="modal" style={{ maxWidth: 480 }}>
            <div className="modal-header">
              <span className="modal-title">Mark Attendance</span>
              <button onClick={() => setShowModal(false)} style={{ background: 'none', border: 'none', fontSize: '1.2rem', cursor: 'pointer', color: 'var(--gray-400)' }}>✕</button>
            </div>
            <form onSubmit={handleMark}>
              <div className="modal-body">
                {error && <div className="alert alert-error"><span>⚠</span><span>{error}</span></div>}

                <div className="form-group">
                  <label className="form-label">Service Date *</label>
                  <input className="form-control" type="date" value={markDate} onChange={e => setMarkDate(e.target.value)} required />
                </div>

                <div className="form-group">
                  <label className="form-label">Service Type *</label>
                  <select className="form-control" value={markService} onChange={e => setMarkService(e.target.value)} required>
                    {serviceTypes.map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label">Search Member</label>
                  <input className="form-control" placeholder="Type name to filter..." value={memberSearch}
                    onChange={e => setMemberSearch(e.target.value)} />
                </div>

                <div className="form-group">
                  <label className="form-label">Select Member *</label>
                  <select className="form-control" value={selectedMemberId}
                    onChange={e => setSelectedMemberId(e.target.value)} required size={6}
                    style={{ height: 'auto' }}>
                    <option value="">— Choose a member —</option>
                    {members.map(m => (
                      <option key={m.id} value={m.id}>
                        {m.full_name} · {m.member_id}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label">Notes</label>
                  <input className="form-control" value={markNotes} onChange={e => setMarkNotes(e.target.value)} placeholder="Optional note" />
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-outline" onClick={() => setShowModal(false)}>Cancel</button>
                <button type="submit" className="btn btn-gold" disabled={saving}>
                  {saving ? <><span className="loader" style={{ width: 14, height: 14 }} /> Saving...</> : 'Mark Present'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirm */}
      {deleteConfirm && (
        <div className="modal-overlay">
          <div className="modal" style={{ maxWidth: 360 }}>
            <div className="modal-header"><span className="modal-title">Remove Record?</span></div>
            <div className="modal-body">
              <p>Remove attendance for <strong>{deleteConfirm.member_name}</strong> on <strong>{deleteConfirm.service_date}</strong>?</p>
            </div>
            <div className="modal-footer">
              <button className="btn btn-outline" onClick={() => setDeleteConfirm(null)}>Cancel</button>
              <button className="btn btn-danger" onClick={() => handleDelete(deleteConfirm.id)}>Remove</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
