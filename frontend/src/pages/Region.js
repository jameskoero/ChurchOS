import React, { useCallback, useEffect, useRef, useState } from 'react';
import { governanceAPI } from '../api';
import { useLabels, plural } from '../contexts/LabelsContext';
import './dashboard.css';
import './reports.css';

const kes = n => 'KES ' + new Intl.NumberFormat('en-KE').format(Math.round(n || 0));
const iso = d => d.toISOString().slice(0, 10);

function Members({ church, onClose, L }) {
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
      <button type="button" className="cd-call" style={{ marginTop: '0.8rem' }} onClick={onClose}>Back to all {plural(L.unit_label).toLowerCase()}</button>
    </section>
  );
}

function Report({ L }) {
  const today = new Date();
  const [from, setFrom] = useState(iso(new Date(today.getTime() - 30 * 86400000)));
  const [to, setTo] = useState(iso(today));
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const build = async () => {
    setError('');
    try { setData((await governanceAPI.report({ from, to })).data); }
    catch (err) { setData(null); setError(err.response?.data?.error || 'Could not build the report.'); }
  };
  return (
    <section className="cd-card" style={{ marginBottom: '0.9rem' }} aria-labelledby="rg-rep">
      <div className="no-print">
        <h2 className="cd-h" id="rg-rep">{L.region_label} report</h2>
        <p className="cd-hint">Totals for every {L.unit_label.toLowerCase()} in the {L.region_label.toLowerCase()}. Then tap Save as PDF and choose "Save as PDF" as the printer.</p>
        <div className="rp-controls">
          <label>From<input className="form-control" type="date" value={from} onChange={e => setFrom(e.target.value)} /></label>
          <label>To<input className="form-control" type="date" value={to} onChange={e => setTo(e.target.value)} /></label>
          <button type="button" className="cd-act" onClick={build}>Build report</button>
          {data && <button type="button" className="cd-act alt" onClick={() => window.print()}>Save as PDF</button>}
        </div>
        {error && <div className="cd-err" role="alert"><span>{error}</span></div>}
      </div>
      {data && (
        <div className="rp-sheet">
          <h2 className="rp-title">{data.region} · {L.region_label} report</h2>
          <p className="rp-sub">{data.from} to {data.to} · {L.region_leader_title}: {data.leader}</p>
          <div className="rp-totals">
            <div><span>Members</span><b>{data.totals.members}</b></div>
            <div><span>New members</span><b>{data.totals.new_members}</b></div>
            <div><span>People attending</span><b>{data.totals.people_attending}</b></div>
            <div><span>Giving in</span><b>{kes(data.totals.income)}</b></div>
            <div><span>Spent</span><b>{kes(data.totals.expense)}</b></div>
            <div><span>Net</span><b>{kes(data.totals.net)}</b></div>
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
            <thead><tr style={{ textAlign: 'left', borderBottom: '2px solid #0C1445' }}>
              <th>{L.unit_label}</th><th>Members</th><th>New</th><th>Attending</th><th>Giving in</th><th>Spent</th><th>Net</th>
            </tr></thead>
            <tbody>{data.churches.map(c => (
              <tr key={c.id} style={{ borderBottom: '1px solid #E1E5F2' }}>
                <td>{c.name}{c.is_seat ? ` (${L.seat_label})` : ''}</td><td>{c.members}</td><td>{c.new_members}</td>
                <td>{c.people_attending}</td><td>{kes(c.income)}</td><td>{kes(c.expense)}</td><td>{kes(c.net)}</td>
              </tr>
            ))}</tbody>
          </table>
          <p className="rp-sub" style={{ marginTop: 12 }}>Generated {data.generated_at}. Cancelled (voided) entries are not counted.</p>
        </div>
      )}
    </section>
  );
}

function RegionSms({ L }) {
  const [text, setText] = useState('');
  const [plan, setPlan] = useState(null);
  const [msg, setMsg] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const check = async () => {
    setError(''); setMsg(''); setPlan(null);
    try { setPlan((await governanceAPI.smsPreview({ message: text })).data); }
    catch (err) { setError(err.response?.data?.error || 'Could not check the message.'); }
  };
  const send = async () => {
    setBusy(true); setError('');
    try {
      const r = (await governanceAPI.smsSend({ message: text, confirm_count: plan.recipients })).data;
      setMsg(`Sent: ${r.accepted} accepted, ${r.failed} failed. ${r.remaining} message parts left this month.`);
      setPlan(null); setText('');
    } catch (err) { setError(err.response?.data?.error || 'Could not send.'); }
    finally { setBusy(false); }
  };
  return (
    <section className="cd-card" style={{ marginBottom: '0.9rem' }} aria-labelledby="rg-sms">
      <h2 className="cd-h" id="rg-sms">Message the {L.region_label.toLowerCase()}</h2>
      <p className="cd-hint">Goes to members who agreed to SMS, in {plural(L.unit_label).toLowerCase()} whose admin switched on regional messages (Structure page). Paid from this {L.seat_label}'s SMS allowance.</p>
      <textarea className="form-control" rows={4} maxLength={480} value={text} onChange={e => { setText(e.target.value); setPlan(null); }} aria-label="Message" placeholder="Write the message" />
      <button type="button" className="cd-act" style={{ marginTop: '0.6rem' }} onClick={check} disabled={!text.trim()}>Check who will get it</button>
      {plan && (
        <div className="cd-card" style={{ marginTop: '0.6rem' }}>
          <p><b>{plan.recipients}</b> members · {plan.total_parts} message parts ({plan.remaining_after} left after)</p>
          <ul className="cd-list">{Object.entries(plan.by_church).map(([n, c]) => <li key={n} className="cd-item"><span>{n}</span><span className="cd-badge">{c}</span></li>)}</ul>
          <button type="button" className="cd-act" style={{ marginTop: '0.6rem' }} onClick={send} disabled={busy || plan.remaining_after < 0}>{busy ? 'Sending…' : `Send to ${plan.recipients} members`}</button>
        </div>
      )}
      {msg && <p className="cd-item" role="status" style={{ marginTop: '0.6rem' }}><span>{msg}</span></p>}
      {error && <div className="cd-err" role="alert" style={{ marginTop: '0.6rem' }}><span>{error}</span></div>}
    </section>
  );
}

export default function Region() {
  const { labels: L } = useLabels();
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
    if (!window.confirm(`Remove ${c.name} from the ${L.region_label.toLowerCase()}?`)) return;
    try { await governanceAPI.removeChurch(c.id); load(); } catch (err) { setError(err.response?.data?.error || 'Could not remove.'); }
  };

  if (!data) return <div className="cd">{error ? <div className="cd-err" role="alert"><span>{error}</span></div> : <p className="cd-empty">Loading…</p>}</div>;
  const t = data.totals;
  const unit = L.unit_label.toLowerCase();
  const n = data.churches.length;
  return (
    <div className="cd">
      <div className="cd-head no-print"><div><h1 className="cd-title">{data.region.name}</h1><p className="cd-sub">Led by {data.region.leader} · last 30 days across {n} {n === 1 ? unit : plural(unit)}</p></div></div>
      <div className="cd-grid even no-print" style={{ marginBottom: '0.9rem' }}>
        <div className="cd-card"><p className="cd-hint">Members</p><b style={{ fontSize: '1.6rem' }}>{t.members}</b></div>
        <div className="cd-card"><p className="cd-hint">New members</p><b style={{ fontSize: '1.6rem' }}>{t.new_members_30d}</b></div>
        <div className="cd-card"><p className="cd-hint">People attending</p><b style={{ fontSize: '1.6rem' }}>{t.people_attending_30d}</b></div>
        <div className="cd-card"><p className="cd-hint">Giving</p><b style={{ fontSize: '1.6rem' }}>{kes(t.giving_30d)}</b></div>
      </div>
      {open ? <Members church={open} L={L} onClose={() => setOpen(null)} /> : (
        <section className="cd-card no-print" style={{ marginBottom: '0.9rem' }} aria-labelledby="rg-ch">
          <h2 className="cd-h" id="rg-ch">{plural(L.unit_label)} in the {L.region_label.toLowerCase()}</h2>
          <ul className="cd-list">{data.churches.map(c => (
            <li key={c.id} className="cd-card" style={{ padding: '0.9rem 1rem' }}>
              <div><b>{c.name}</b> · {c.code}{c.is_seat && <span className="cd-badge" style={{ marginLeft: 6 }}>{L.seat_label}</span>}</div>
              <p className="cd-hint">{c.members} members · {c.new_members_30d} new · {c.people_attending_30d} attending · {kes(c.giving_30d)} given (30 days){!c.is_seat && ` · regional messages ${c.regional_sms ? 'on' : 'off'}`}</p>
              <span style={{ display: 'flex', gap: '0.5rem' }}>
                <button type="button" className="cd-act alt" style={{ minHeight: 40 }} onClick={() => setOpen(c)}>Member list</button>
                {!c.is_seat && <button type="button" className="cd-call" onClick={() => remove(c)}>Remove</button>}
              </span>
            </li>
          ))}</ul>
        </section>
      )}
      <Report L={L} />
      <div className="no-print"><RegionSms L={L} /></div>
      <section className="cd-card no-print" aria-labelledby="rg-inv">
        <h2 className="cd-h" id="rg-inv">Invite another {unit}</h2>
        <p className="cd-hint">Ask the {unit}'s admin for the code on their Structure page, for example COS-0007. They must accept before you see anything.</p>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <input className="form-control" placeholder="COS-0007" value={code} onChange={e => setCode(e.target.value)} aria-label={`${L.unit_label} code`} />
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
