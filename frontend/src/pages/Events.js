/* eslint-disable no-unused-vars, react-hooks/exhaustive-deps */
import React, { useState, useEffect, useCallback } from 'react';
import { eventsAPI } from '../api';
import { useAuth } from '../contexts/AuthContext';

const EVENT_TYPES = ['service', 'conference', 'outreach', 'meeting', 'youth', 'other'];
const STATUSES = ['upcoming', 'ongoing', 'completed', 'cancelled'];

const now = () => {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
};

const EMPTY_FORM = {
  title: '', description: '', event_type: 'service', location: '',
  start_date: now(), end_date: '', is_recurring: false,
  recurrence_pattern: '', max_attendees: '', status: 'upcoming'
};

function statusBadge(s) {
  const map = { upcoming: 'badge-info', ongoing: 'badge-success', completed: 'badge-navy', cancelled: 'badge-danger' };
  return <span className={`badge ${map[s] || 'badge-info'}`}>{s}</span>;
}

function typeBadge(t) {
  return <span className="badge badge-gold" style={{ fontSize: '0.7rem' }}>{t}</span>;
}

function EventCard({ event, onEdit, onDelete, canWrite }) {
  const start = new Date(event.start_date);
  return (
    <div className="card" style={{
      borderLeft: `4px solid ${event.status === 'cancelled' ? 'var(--danger)' : event.status === 'completed' ? 'var(--gray-400)' : 'var(--gold)'}`,
      display: 'flex', gap: '1rem', padding: '1rem',
      opacity: event.status === 'cancelled' ? 0.7 : 1
    }}>
      <div style={{
        minWidth: 50, height: 50, borderRadius: 10,
        background: 'var(--navy)', display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center', color: 'var(--gold)'
      }}>
        <span style={{ fontSize: '0.6rem', fontWeight: 700, letterSpacing: '0.05em' }}>
          {start.toLocaleDateString('en', { month: 'short' }).toUpperCase()}
        </span>
        <span style={{ fontSize: '1.3rem', fontWeight: 700, lineHeight: 1 }}>{start.getDate()}</span>
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '0.5rem' }}>
          <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--navy)', margin: 0 }}>{event.title}</h3>
          <div style={{ display: 'flex', gap: '0.4rem', flexShrink: 0 }}>
            {typeBadge(event.event_type)}
            {statusBadge(event.status)}
          </div>
        </div>
        {event.description && (
          <p style={{ fontSize: '0.82rem', color: 'var(--gray-600)', marginTop: '0.3rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {event.description}
          </p>
        )}
        <div style={{ display: 'flex', gap: '1rem', marginTop: '0.5rem', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '0.78rem', color: 'var(--gray-600)' }}>
            🕐 {start.toLocaleString('en-KE', { weekday: 'short', hour: '2-digit', minute: '2-digit' })}
          </span>
          {event.location && <span style={{ fontSize: '0.78rem', color: 'var(--gray-600)' }}>📍 {event.location}</span>}
          {event.max_attendees && <span style={{ fontSize: '0.78rem', color: 'var(--gray-600)' }}>👥 Max {event.max_attendees}</span>}
        </div>
      </div>
      {canWrite && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', flexShrink: 0 }}>
          <button className="btn btn-outline btn-sm" onClick={() => onEdit(event)}>Edit</button>
          <button className="btn btn-danger btn-sm" onClick={() => onDelete(event)}>Del</button>
        </div>
      )}
    </div>
  );
}

export default function Events() {
  const { can } = useAuth();
  const [events, setEvents] = useState([]);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState('upcoming');
  const [filterType, setFilterType] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [deleteConfirm, setDeleteConfirm] = useState(null);

  const fetchEvents = useCallback(() => {
    setLoading(true);
    eventsAPI.getAll({ page, per_page: 15, status: filterStatus, event_type: filterType })
      .then(r => { setEvents(r.data.events); setTotal(r.data.total); setPages(r.data.pages); })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [page, filterStatus, filterType]);

  useEffect(() => { fetchEvents(); }, [fetchEvents]);
  useEffect(() => { setPage(1); }, [filterStatus, filterType]);

  const openCreate = () => { setEditing(null); setForm(EMPTY_FORM); setError(''); setShowModal(true); };
  const openEdit = (ev) => {
    setEditing(ev);
    setForm({
      title: ev.title, description: ev.description || '', event_type: ev.event_type || 'service',
      location: ev.location || '',
      start_date: ev.start_date ? ev.start_date.slice(0, 16) : now(),
      end_date: ev.end_date ? ev.end_date.slice(0, 16) : '',
      is_recurring: ev.is_recurring || false,
      recurrence_pattern: ev.recurrence_pattern || '',
      max_attendees: ev.max_attendees || '',
      status: ev.status || 'upcoming'
    });
    setError(''); setShowModal(true);
  };

  const handleSave = async (e) => {
    e.preventDefault(); setSaving(true); setError('');
    try {
      const payload = { ...form, max_attendees: form.max_attendees ? parseInt(form.max_attendees) : null };
      if (editing) await eventsAPI.update(editing.id, payload);
      else await eventsAPI.create(payload);
      setShowModal(false); fetchEvents();
    } catch (err) { setError(err.response?.data?.error || 'Save failed'); }
    finally { setSaving(false); }
  };

  const handleDelete = async (id) => {
    try { await eventsAPI.delete(id); setDeleteConfirm(null); fetchEvents(); }
    catch (err) { alert(err.response?.data?.error || 'Delete failed'); }
  };

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <h1 style={{ fontFamily: 'var(--font-display)', fontSize: '1.5rem', color: 'var(--navy)' }}>Events</h1>
          <p style={{ color: 'var(--gray-600)', fontSize: '0.85rem' }}>Total: {total}</p>
        </div>
        {can('write') && <button className="btn btn-gold" onClick={openCreate}>+ New Event</button>}
      </div>

      {/* Filters */}
      <div className="card" style={{ marginBottom: '1rem', padding: '1rem' }}>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          <select className="form-control" value={filterStatus} onChange={e => setFilterStatus(e.target.value)} style={{ maxWidth: 160 }}>
            <option value="">All Statuses</option>
            {STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          <select className="form-control" value={filterType} onChange={e => setFilterType(e.target.value)} style={{ maxWidth: 160 }}>
            <option value="">All Types</option>
            {EVENT_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
          {(filterStatus !== 'upcoming' || filterType) && (
            <button className="btn btn-outline btn-sm" onClick={() => { setFilterStatus('upcoming'); setFilterType(''); }}>Reset</button>
          )}
        </div>
      </div>

      {loading ? (
        <div style={{ padding: '3rem', textAlign: 'center' }}>
          <div className="loader" style={{ width: 32, height: 32, borderWidth: 3, margin: '0 auto' }} />
        </div>
      ) : events.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '3rem', color: 'var(--gray-400)' }}>
          No events found
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {events.map(ev => (
            <EventCard key={ev.id} event={ev} onEdit={openEdit} onDelete={setDeleteConfirm} canWrite={can('write')} />
          ))}
        </div>
      )}

      {pages > 1 && (
        <div className="pagination" style={{ marginTop: '1rem' }}>
          <button className="page-btn" disabled={page === 1} onClick={() => setPage(p => p - 1)}>‹</button>
          {[...Array(Math.min(pages, 7))].map((_, i) => (
            <button key={i} className={`page-btn ${page === i + 1 ? 'active' : ''}`} onClick={() => setPage(i + 1)}>{i + 1}</button>
          ))}
          <button className="page-btn" disabled={page === pages} onClick={() => setPage(p => p + 1)}>›</button>
        </div>
      )}

      {/* Modal */}
      {showModal && (
        <div className="modal-overlay">
          <div className="modal">
            <div className="modal-header">
              <span className="modal-title">{editing ? 'Edit Event' : 'New Event'}</span>
              <button onClick={() => setShowModal(false)} style={{ background: 'none', border: 'none', fontSize: '1.2rem', cursor: 'pointer', color: 'var(--gray-400)' }}>✕</button>
            </div>
            <form onSubmit={handleSave}>
              <div className="modal-body">
                {error && <div className="alert alert-error"><span>⚠</span><span>{error}</span></div>}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                  <div className="form-group" style={{ gridColumn: '1/-1' }}>
                    <label className="form-label">Title *</label>
                    <input className="form-control" value={form.title} onChange={e => set('title', e.target.value)} required />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Event Type</label>
                    <select className="form-control" value={form.event_type} onChange={e => set('event_type', e.target.value)}>
                      {EVENT_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                    </select>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Status</label>
                    <select className="form-control" value={form.status} onChange={e => set('status', e.target.value)}>
                      {STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Start Date *</label>
                    <input className="form-control" type="datetime-local" value={form.start_date} onChange={e => set('start_date', e.target.value)} required />
                  </div>
                  <div className="form-group">
                    <label className="form-label">End Date</label>
                    <input className="form-control" type="datetime-local" value={form.end_date} onChange={e => set('end_date', e.target.value)} />
                  </div>
                  <div className="form-group" style={{ gridColumn: '1/-1' }}>
                    <label className="form-label">Location</label>
                    <input className="form-control" value={form.location} onChange={e => set('location', e.target.value)} placeholder="e.g. Main Altar, Migosi" />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Max Attendees</label>
                    <input className="form-control" type="number" min="1" value={form.max_attendees} onChange={e => set('max_attendees', e.target.value)} />
                  </div>
                  <div className="form-group">
                    <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '1.5rem', cursor: 'pointer' }}>
                      <input type="checkbox" checked={form.is_recurring} onChange={e => set('is_recurring', e.target.checked)} />
                      <span style={{ fontSize: '0.875rem', fontWeight: 500 }}>Recurring event</span>
                    </label>
                  </div>
                  {form.is_recurring && (
                    <div className="form-group" style={{ gridColumn: '1/-1' }}>
                      <label className="form-label">Recurrence Pattern</label>
                      <input className="form-control" value={form.recurrence_pattern} onChange={e => set('recurrence_pattern', e.target.value)} placeholder="e.g. Every Sunday" />
                    </div>
                  )}
                  <div className="form-group" style={{ gridColumn: '1/-1' }}>
                    <label className="form-label">Description</label>
                    <textarea className="form-control" value={form.description} onChange={e => set('description', e.target.value)} rows={3} />
                  </div>
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-outline" onClick={() => setShowModal(false)}>Cancel</button>
                <button type="submit" className="btn btn-gold" disabled={saving}>
                  {saving ? <><span className="loader" style={{ width: 14, height: 14 }} /> Saving...</> : (editing ? 'Update' : 'Create Event')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {deleteConfirm && (
        <div className="modal-overlay">
          <div className="modal" style={{ maxWidth: 380 }}>
            <div className="modal-header"><span className="modal-title">Delete Event?</span></div>
            <div className="modal-body"><p>Delete <strong>{deleteConfirm.title}</strong>? This cannot be undone.</p></div>
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
