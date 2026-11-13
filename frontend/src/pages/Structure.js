import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { governanceAPI } from '../api';
import { useAuth } from '../contexts/AuthContext';
import './dashboard.css';

const STATUS = { verified: 'verified', listed: 'listed', pending: 'waiting for approval' };

function Picker({ current, onChosen }) {
  const [q, setQ] = useState('');
  const [rows, setRows] = useState([]);
  const [other, setOther] = useState(false);
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const timer = useRef(null);
  const load = useCallback(search => {
    governanceAPI.denominations({ search }).then(r => setRows(r.data.denominations || [])).catch(() => setRows([]));
  }, []);
  useEffect(() => { load(''); }, [load]);
  const find = v => { setQ(v); clearTimeout(timer.current); timer.current = setTimeout(() => load(v.trim()), 250); };
  const choose = async d => {
    setError('');
    try { await governanceAPI.choose({ denomination_id: d.id }); onChosen(); }
    catch (err) { setError(err.response?.data?.error || 'Could not save.'); }
  };
  const ask = async () => {
    setError('');
    try { await governanceAPI.requestDenomination({ name: name.trim() }); setOther(false); setName(''); onChosen(); }
    catch (err) { setError(err.response?.data?.error || 'Could not save.'); }
  };
  return (
    <div style={{ display: 'grid', gap: '0.6rem' }}>
      <input className="form-control" placeholder="Search, for example Repentance, PAG or VOSH" value={q} onChange={e => find(e.target.value)} aria-label="Search denominations" />
      <ul className="cd-list" style={{ maxHeight: 320, overflowY: 'auto' }}>
        {rows.map(d => (
          <li key={d.id}>
            <button type="button" className="cd-item" style={{ width: '100%', border: 0, cursor: 'pointer', textAlign: 'left' }}
                    onClick={() => choose(d)} aria-pressed={current && current.id === d.id}>
              <span><b>{d.name}</b>{d.short_name ? ` (${d.short_name})` : ''}</span>
              <span className="cd-badge">{current && current.id === d.id ? 'selected' : STATUS[d.status] || d.status}</span>
            </button>
          </li>
        ))}
        {rows.length === 0 && <li className="cd-empty">No match. Use the option below.</li>}
      </ul>
      {!other ? (
        <button type="button" className="cd-act alt" onClick={() => setOther(true)}>My denomination or ministry is not listed</button>
      ) : (
        <div style={{ display: 'grid', gap: '0.5rem' }}>
          <input className="form-control" placeholder="Full name of your denomination or ministry" value={name} onChange={e => setName(e.target.value)} aria-label="Denomination name" />
          <p className="cd-hint">You can use it straight away. It is added to the list for other churches once approved.</p>
          <button type="button" className="cd-act" onClick={ask} disabled={name.trim().length < 3}>Use this name</button>
        </div>
      )}
      {error && <div className="cd-err" role="alert"><span>{error}</span></div>}
    </div>
  );
}

function OwnerReview() {
  const [rows, setRows] = useState([]);
  const [msg, setMsg] = useState('');
  const load = useCallback(() => { governanceAPI.pending().then(r => setRows(r.data.denominations || [])).catch(() => {}); }, []);
  useEffect(() => { load(); }, [load]);
  const act = async (d, status) => {
    setMsg('');
    try { await governanceAPI.review(d.id, { status }); load(); }
    catch (err) { setMsg(err.response?.data?.error || 'Could not save.'); }
  };
  if (!rows.length) return null;
  return (
    <section className="cd-card" style={{ marginBottom: '0.9rem' }} aria-labelledby="gv-review">
      <h2 className="cd-h" id="gv-review">Denominations waiting for you</h2>
      <p className="cd-hint">Approve adds the name to everyone's list. Mark verified only after seeing its registration certificate.</p>
      <ul className="cd-list">{rows.map(d => (
        <li key={d.id} className="cd-item" style={{ flexWrap: 'wrap', gap: '0.5rem' }}>
          <b>{d.name}</b>
          <span style={{ display: 'flex', gap: '0.4rem' }}>
            <button type="button" className="cd-act" style={{ minHeight: 40 }} onClick={() => act(d, 'listed')}>Approve</button>
            <button type="button" className="cd-act alt" style={{ minHeight: 40 }} onClick={() => act(d, 'verified')}>Verified</button>
            <button type="button" className="cd-call" onClick={() => act(d, 'rejected')}>Reject</button>
          </span>
        </li>
      ))}</ul>
      {msg && <div className="cd-err" role="alert"><span>{msg}</span></div>}
    </section>
  );
}

export default function Structure() {
  const { user } = useAuth();
  const [info, setInfo] = useState(null);
  const [changing, setChanging] = useState(false);
  const [regionName, setRegionName] = useState('');
  const [error, setError] = useState('');
  const load = useCallback(() => { governanceAPI.church().then(r => setInfo(r.data)).catch(() => setError('Could not load.')); }, []);
  useEffect(() => { load(); }, [load]);
  const isAdmin = user?.role === 'admin';
  const L = info?.labels || {};

  const createRegion = async () => {
    setError('');
    try { await governanceAPI.createRegion({ name: regionName.trim() }); setRegionName(''); load(); }
    catch (err) { setError(err.response?.data?.error || 'Could not create the region.'); }
  };
  const answer = async (id, action) => {
    setError('');
    try { await governanceAPI.answer(id, action); load(); }
    catch (err) { setError(err.response?.data?.error || 'Could not save.'); }
  };
  const leave = async () => {
    if (!window.confirm('Leave this region? The regional leader will stop seeing your totals and member list.')) return;
    try { await governanceAPI.leave(); load(); } catch (err) { setError(err.response?.data?.error || 'Could not leave.'); }
  };

  if (!info) return <div className="cd">{error ? <p className="cd-err"><span>{error}</span></p> : <p className="cd-empty">Loading…</p>}</div>;
  return (
    <div className="cd">
      <div className="cd-head"><div><h1 className="cd-title">Structure</h1><p className="cd-sub">Your denomination, your {(L.region_label || 'region').toLowerCase()}, and who oversees it.</p></div></div>
      {user?.is_platform_owner && <OwnerReview />}

      <section className="cd-card" style={{ marginBottom: '0.9rem' }} aria-labelledby="gv-den">
        <h2 className="cd-h" id="gv-den">Denomination</h2>
        {info.denomination && !changing ? (
          <>
            <p><b>{info.denomination.name}</b> <span className="cd-badge">{STATUS[info.denomination.status] || info.denomination.status}</span></p>
            <p className="cd-hint">Wording used: {L.region_label} led by a {L.region_leader_title}; each {L.unit_label} led by a {L.unit_leader_title}; the seat is the {L.seat_label}.</p>
            {isAdmin && <button type="button" className="cd-call" onClick={() => setChanging(true)}>Change</button>}
          </>
        ) : isAdmin ? (
          <Picker current={info.denomination} onChosen={() => { setChanging(false); load(); }} />
        ) : <p className="cd-empty">Your admin has not chosen a denomination yet.</p>}
      </section>

      <section className="cd-card" style={{ marginBottom: '0.9rem' }} aria-labelledby="gv-region">
        <h2 className="cd-h" id="gv-region">{L.region_label || 'Region'}</h2>
        <p className="cd-hint">This church's code: <b>{info.church_code}</b>. Give it to your {L.region_leader_title || 'regional leader'} so they can invite you.</p>
        {info.region ? (
          <>
            <p><b>{info.region.name}</b> · {L.region_leader_title}: {info.region.leader || 'not set'}{info.is_seat && <> · <span className="cd-badge">{L.seat_label}</span></>}</p>
            <p className="cd-hint">The {L.region_leader_title} can see this {(L.unit_label || 'church').toLowerCase()}'s totals and member list, read-only. Each look is recorded in your activity log.</p>
            {info.leads_region && <Link className="cd-act" to="/region">Open the {L.region_label} overview</Link>}
            {isAdmin && !info.is_seat && <button type="button" className="cd-call" style={{ marginTop: '0.6rem' }} onClick={leave}>Leave this {L.region_label.toLowerCase()}</button>}
          </>
        ) : (
          <>
            {info.invites.map(i => (
              <div key={i.id} className="cd-card" style={{ padding: '0.9rem 1rem', marginBottom: '0.6rem' }}>
                <p><b>{i.region.name}</b> invites this church to join. {L.region_leader_title}: {i.region.leader}.</p>
                <p className="cd-hint">If you accept, the {L.region_leader_title} will see your totals and your member list (names, phone numbers, emails), read-only. Your money, records and M-Pesa stay yours. You can leave later.</p>
                {isAdmin && (
                  <span style={{ display: 'flex', gap: '0.5rem' }}>
                    <button type="button" className="cd-act" onClick={() => answer(i.id, 'accept')}>Accept</button>
                    <button type="button" className="cd-act alt" onClick={() => answer(i.id, 'decline')}>Decline</button>
                  </span>
                )}
              </div>
            ))}
            {isAdmin && info.denomination && (
              <div style={{ display: 'grid', gap: '0.5rem', marginTop: '0.6rem' }}>
                <p className="cd-hint">Lead a {L.region_label.toLowerCase()} from this church (it becomes the {L.seat_label}):</p>
                <input className="form-control" placeholder={`Name, for example Migosi ${L.region_label}`} value={regionName} onChange={e => setRegionName(e.target.value)} aria-label="Region name" />
                <button type="button" className="cd-act" onClick={createRegion} disabled={regionName.trim().length < 3}>Create {L.region_label.toLowerCase()}</button>
              </div>
            )}
          </>
        )}
        {error && <div className="cd-err" role="alert" style={{ marginTop: '0.6rem' }}><span>{error}</span></div>}
      </section>
    </div>
  );
}
