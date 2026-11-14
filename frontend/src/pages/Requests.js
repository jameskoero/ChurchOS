import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { publicAPI } from '../api';
import './dashboard.css';

export default function Requests() {
  const [rows, setRows] = useState(null);
  const [status, setStatus] = useState('pending');
  const [error, setError] = useState('');
  const [msg, setMsg] = useState('');
  const load = useCallback(() => {
    publicAPI.list({ status }).then(r => setRows(r.data.requests || [])).catch(() => { setRows([]); setError('Could not load requests.'); });
  }, [status]);
  useEffect(() => { setRows(null); load(); }, [load]);
  const decide = async (row, action) => {
    setError(''); setMsg('');
    try {
      const res = await publicAPI.decide(row.id, { action });
      setMsg(action === 'approve' ? `${row.church_name} is set up on a 30-day trial. ${res.data.next}` : `${row.church_name} was declined.`);
      load();
    } catch (err) { setError(err.response?.data?.error || 'Could not save.'); }
  };
  return (
    <div className="cd">
      <h1 className="cd-title">Requests</h1>
      <p className="cd-hint">Churches that asked for ChurchOS. Phone the contact first, then approve. Approving makes the church; then add its first admin on the <Link to="/churches">Churches</Link> page.</p>
      <div className="cd-actions" style={{ marginBottom: '0.8rem' }}>
        {['pending', 'approved', 'declined'].map(s => (
          <button key={s} type="button" className={`cd-act${status === s ? '' : ' alt'}`} onClick={() => setStatus(s)}>{s[0].toUpperCase() + s.slice(1)}</button>
        ))}
      </div>
      {msg && <div className="cd-card" role="status" style={{ marginBottom: '0.8rem' }}>{msg}</div>}
      {error && <div className="cd-err" role="alert" style={{ marginBottom: '0.8rem' }}><span>{error}</span></div>}
      {rows === null ? <p className="cd-empty">Loading…</p> : rows.length === 0 ? <p className="cd-empty">No {status} requests.</p> : (
        <ul className="cd-list">
          {rows.map(r => (
            <li key={r.id} className="cd-card">
              <p><b>{r.church_name}</b>{r.county ? ` · ${r.county}` : ''}</p>
              <p className="cd-hint">{r.contact_name} · <a href={`tel:${r.phone}`}>{r.phone}</a>{r.email ? ` · ${r.email}` : ''}</p>
              <p className="cd-hint">{r.denomination || 'Denomination not given'}{r.members_estimate ? ` · about ${r.members_estimate} members` : ''}</p>
              {r.note && <p className="cd-hint">“{r.note}”</p>}
              {status === 'pending' && (
                <span style={{ display: 'flex', gap: '0.5rem' }}>
                  <button type="button" className="cd-act" onClick={() => decide(r, 'approve')}>Approve</button>
                  <button type="button" className="cd-act alt" onClick={() => decide(r, 'decline')}>Decline</button>
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
