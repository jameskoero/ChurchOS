import React, { useCallback, useEffect, useRef, useState } from 'react';
import { governanceAPI } from '../api';
import './dashboard.css';

const kes = n => 'KES ' + new Intl.NumberFormat('en-KE').format(Math.round(n || 0));

function Members({ church, onClose }) {
  const [data, setData] = useState(null);
  const [q, setQ] = useState('');
  const [page, setPage] = useState(1);
  const timer = useRef(null);
  const load = useCallback((search, p) => {
    governanceAPI.regionMembers(church.id, { search, page: p }).then(r => setData(r.data)).catch(() => setData(null));
  }, [church.id]);
  useEffect(() => { load('', 1); }, [load]);
  const find = v => { setQ(v); setPage(1); clearTimeout(timer.current); timer.current = setTimeout(() => load(v.trim(), 1), 300); };
  const go = p => { setPage(p); load(q.trim(), p); };
  return (
    <section className="cd-card" style={{ marginBottom: '0.9rem' }} aria-labelledby="rg-mem">
      <h2 className="cd-h" id="rg-mem">{church.name}: members</h2>
      <p className="cd-hint">Read-only. This look is recorded in {church.name}'s activity log.</p>
      <input className="form-control" placeholder="Find a member" value={q} onChange={e => find(e.target.value)} aria-label="Find a member" />
      {data && (
        <>
          <p className="cd-hint">{data.total} member{data.total === 1 ? '' : 's'}</p>
          <ul className="cd-list">{data.members.map(m => (
            <li key={m.member_id} className="cd-item" style={{ alignItems: 'flex-start' }}>
              <span><b>{m.full_name}</b> · {m.member_id}<br />{[m.phone, m.email, m.cell_group].filter(Boolean).join(' · ')}</span>
              <span className="cd-badge">{m.membership_status}</span>
            </li>
          ))}</ul>
          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.6rem' }}>
            {page > 1 && <button type="button" className="cd-act alt" onClick={() => go(page - 1)}>Previous</button>}
            {page * 50 < data.total && <button type="button" className="cd-act alt" onClick={() => go(page + 1)}>Next</button>}
          </div>
        </>
      )}
      <button type="button" className="cd-call" style={{ marginTop: '0.8rem' }} onClick={onClose}>Back to all churches</button>
    </section>
  );
}

export default function Region() {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [code, setCode] = useState('');
  const [note, setNote] = useState('');
  const [open, setOpen] = useState(null);
  const load = useCallback(() => {
    governanceAPI.myRegion().then(r => setData(r.data)).catch(err => setError(err.response?.data?.error || 'Could not load.'));
  }, []);
  useEffect(() => { load(); }, [load]);
  const invite = async () => {
    setNote(''); setError('');
    try { const r = await governanceAPI.invite({ code: code.trim() }); setNote(`Invitation sent to ${r.data.church}. Their admin must accept it.`); setCode(''); load(); }
    catch (err) { setError(err.response?.data?.error || 'Could not send the invitation.'); }
  };
  const remove = async c => {
    if (!window.confirm(`Remove ${c.name} from the region?`)) return;
    try { await governanceAPI.removeChurch(c.id); load(); } catch (err) { setError(err.response?.data?.error || 'Could not remove.'); }
  };

  if (!data) return <div className="cd">{error ? <div className="cd-err" role="alert"><span>{error}</span></div> : <p className="cd-empty">Loading…</p>}</div>;
  const t = data.totals;
  return (
    <div className="cd">
      <div className="cd-head"><div><h1 className="cd-title">{data.region.name}</h1><p className="cd-sub">Led by {data.region.leader} · last 30 days across {data.churches.length} church{data.churches.length === 1 ? '' : 'es'}</p></div></div>
      <div className="cd-grid even" style={{ marginBottom: '0.9rem' }}>
        <div className="cd-card"><p className="cd-hint">Members</p><b style={{ fontSize: '1.6rem' }}>{t.members}</b></div>
        <div className="cd-card"><p className="cd-hint">New members</p><b style={{ fontSize: '1.6rem' }}>{t.new_members_30d}</b></div>
        <div className="cd-card"><p className="cd-hint">People attending</p><b style={{ fontSize: '1.6rem' }}>{t.people_attending_30d}</b></div>
        <div className="cd-card"><p className="cd-hint">Giving</p><b style={{ fontSize: '1.6rem' }}>{kes(t.giving_30d)}</b></div>
      </div>
      {open ? <Members church={open} onClose={() => setOpen(null)} /> : (
        <section className="cd-card" style={{ marginBottom: '0.9rem' }} aria-labelledby="rg-ch">
          <h2 className="cd-h" id="rg-ch">Churches in the region</h2>
          <ul className="cd-list">{data.churches.map(c => (
            <li key={c.id} className="cd-card" style={{ padding: '0.9rem 1rem' }}>
              <div><b>{c.name}</b> · {c.code}{c.is_seat && <span className="cd-badge" style={{ marginLeft: 6 }}>seat</span>}</div>
              <p className="cd-hint">{c.members} members · {c.new_members_30d} new · {c.people_attending_30d} attending · {kes(c.giving_30d)} given (30 days)</p>
              <span style={{ display: 'flex', gap: '0.5rem' }}>
                <button type="button" className="cd-act alt" style={{ minHeight: 40 }} onClick={() => setOpen(c)}>Member list</button>
                {!c.is_seat && <button type="button" className="cd-call" onClick={() => remove(c)}>Remove</button>}
              </span>
            </li>
          ))}</ul>
        </section>
      )}
      <section className="cd-card" aria-labelledby="rg-inv">
        <h2 className="cd-h" id="rg-inv">Invite a church</h2>
        <p className="cd-hint">Ask the church's admin for the code on their Structure page, for example COS-0007. They must accept before you see anything.</p>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <input className="form-control" placeholder="COS-0007" value={code} onChange={e => setCode(e.target.value)} aria-label="Church code" />
          <button type="button" className="cd-act" onClick={invite} disabled={!code.trim()}>Invite</button>
        </div>
        {note && <p className="cd-item" role="status" style={{ marginTop: '0.6rem' }}><span>{note}</span></p>}
        {error && <div className="cd-err" role="alert" style={{ marginTop: '0.6rem' }}><span>{error}</span></div>}
        {data.invites.length > 0 && <ul className="cd-list" style={{ marginTop: '0.6rem' }}>{data.invites.map(i => (
          <li key={i.id} className="cd-item"><span>{i.church}</span><span className="cd-badge">{i.status}</span></li>
        ))}</ul>}
      </section>
    </div>
  );
}
