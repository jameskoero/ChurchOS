import React, { useCallback, useEffect, useRef, useState } from 'react';
import { smsAPI } from '../api';
import { useAuth } from '../contexts/AuthContext';
import './dashboard.css';

const ALLOWED = ['admin', 'pastor', 'secretary'];
const PLAIN = /^[A-Za-z0-9 \n.,!?:;'"()\-/+&%@#*=<>_]*$/;
const tidy = t => t.replace(/[\u2018\u2019]/g, "'").replace(/[\u201c\u201d]/g, '"').replace(/[\u2013\u2014]/g, '-').replace(/\u2026/g, '...');
function parts(text) {
  const n = text.length;
  if (!n) return 0;
  if (PLAIN.test(text)) return n <= 160 ? 1 : Math.ceil(n / 153);
  return n <= 70 ? 1 : Math.ceil(n / 67);
}
const when = s => (s ? new Date(s + 'Z').toLocaleString('en-KE', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '');

function Setup() {
  const { user } = useAuth();
  const [s, setS] = useState(null);
  useEffect(() => { smsAPI.setup().then(r => setS(r.data)).catch(() => setS(null)); }, []);
  if (!s || user?.role !== 'admin') return null;
  const items = [...s.missing.map(n => `Missing in Render: ${n}`), ...s.problems];
  return (
    <section className="cd-card" style={{ marginBottom: '0.9rem' }} aria-labelledby="sms-setup">
      <h2 className="cd-h" id="sms-setup">SMS setup <span className="cd-badge">{s.configured ? `ready · ${s.environment}` : 'needs attention'}</span></h2>
      {s.environment === 'sandbox' && s.configured && <p className="cd-hint">Sandbox: messages go to Africa's Talking's simulator, not to real phones.</p>}
      {items.length > 0 && <ul className="cd-list">{items.map(t => <li key={t} className="cd-item">{t}</li>)}</ul>}
    </section>
  );
}

function People({ audience, picked, onPick, onChanged }) {
  const [q, setQ] = useState('');
  const [data, setData] = useState({ members: [], agreed: 0, total: 0 });
  const [error, setError] = useState('');
  const timer = useRef(null);
  const load = useCallback(search => {
    smsAPI.audience({ search }).then(r => setData(r.data)).catch(() => setError('Could not load members.'));
  }, []);
  useEffect(() => { load(''); }, [load]);
  const find = v => { setQ(v); clearTimeout(timer.current); timer.current = setTimeout(() => load(v.trim()), 300); };
  const flip = async m => {
    setError('');
    try { await smsAPI.consent({ member_id: m.id, agreed: !m.sms_ok }); load(q.trim()); onChanged(); }
    catch (err) { setError(err.response?.data?.error || 'Could not save.'); }
  };
  return (
    <section className="cd-card" style={{ marginBottom: '0.9rem' }} aria-labelledby="sms-people">
      <h2 className="cd-h" id="sms-people">Who agreed to SMS</h2>
      <p className="cd-hint">{data.agreed} of {data.total} active members agreed. Only tick a member after they have told you they want church messages.</p>
      <input className="form-control" placeholder="Find a member" value={q} onChange={e => find(e.target.value)} aria-label="Find a member" />
      {error && <div className="cd-err" role="alert" style={{ marginTop: '0.5rem' }}><span>{error}</span></div>}
      {data.members.length === 0 && <p className="cd-empty" style={{ marginTop: '0.6rem' }}>No active member matches that. Try just a first name or a member number.</p>}
      <ul className="cd-list" style={{ marginTop: '0.6rem' }}>
        {data.members.map(m => (
          <li key={m.id} className="cd-item" style={{ gap: '0.6rem', flexWrap: 'wrap' }}>
            <span><b>{m.full_name}</b> · {m.member_id}{!m.has_phone && ' · no valid phone'}</span>
            <span style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              {audience === 'selected' && m.sms_ok && (
                <label><input type="checkbox" checked={picked.includes(m.id)} onChange={() => onPick(m.id)} /> Send to</label>
              )}
              <button type="button" className={`cd-act ${m.sms_ok ? '' : 'alt'}`} style={{ minHeight: 40, padding: '0 14px' }}
                      onClick={() => flip(m)} aria-pressed={m.sms_ok}>{m.sms_ok ? 'Agreed' : 'Not agreed'}</button>
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function Messages() {
  const { user } = useAuth();
  const [audience, setAudience] = useState('all');
  const [picked, setPicked] = useState([]);
  const [message, setMessage] = useState('');
  const [numbers, setNumbers] = useState('');
  const [asked, setAsked] = useState(false);
  const [preview, setPreview] = useState(null);
  const [note, setNote] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [hist, setHist] = useState({ messages: [], used: 0, limit: 0 });

  const loadHistory = useCallback(() => {
    smsAPI.history().then(r => setHist(r.data)).catch(() => {});
  }, []);
  useEffect(() => { loadHistory(); }, [loadHistory]);

  if (!ALLOWED.includes(user?.role)) {
    return <div className="cd"><p className="cd-empty">Messages are for the admin, pastor and secretary.</p></div>;
  }
  const body = { message, audience, member_ids: picked, numbers, asked };
  const key = JSON.stringify(body);
  const fresh = preview && preview.key === key;
  const clean = tidy(message);

  const doPreview = async () => {
    setError(''); setNote(''); setBusy(true);
    try { setPreview({ key, ...(await smsAPI.preview(body)).data }); }
    catch (err) { setPreview(null); setError(err.response?.data?.error || 'Could not check the message.'); }
    finally { setBusy(false); }
  };
  const doSend = async () => {
    setError(''); setBusy(true);
    try {
      const res = await smsAPI.send({ ...body, confirm_count: preview.recipients });
      setNote(`Sent to ${res.data.accepted} member${res.data.accepted === 1 ? '' : 's'}${res.data.failed ? `, ${res.data.failed} could not be sent` : ''}. ${res.data.remaining} SMS parts left this month.`);
      setPreview(null); setMessage(''); setNumbers(''); setAsked(false); loadHistory();
    } catch (err) {
      const d = err.response?.data;
      setError(d?.error || 'Could not send. Nothing was lost; try again.');
      if (d?.code === 'CHANGED') setPreview(null);
    } finally { setBusy(false); }
  };

  return (
    <div className="cd">
      <div className="cd-head"><div><h1 className="cd-title">Messages</h1><p className="cd-sub">Send SMS to members who agreed to receive it.</p></div></div>
      <Setup />
      <People audience={audience} picked={picked} onPick={id => setPicked(p => (p.includes(id) ? p.filter(x => x !== id) : [...p, id]))} onChanged={() => setPreview(null)} />
      <section className="cd-card" style={{ marginBottom: '0.9rem' }} aria-labelledby="sms-write">
        <h2 className="cd-h" id="sms-write">Write a message</h2>
        <div style={{ display: 'grid', gap: '0.6rem' }}>
          <select className="form-control" value={audience} onChange={e => setAudience(e.target.value)} aria-label="Who to send to">
            <option value="all">Everyone who agreed</option>
            <option value="selected">Chosen members only ({picked.length} chosen)</option>
            <option value="numbers">Phone numbers I type</option>
          </select>
          {audience === 'numbers' && (
            <>
              <textarea className="form-control" rows={2} value={numbers} onChange={e => setNumbers(e.target.value)}
                        inputMode="tel" placeholder="Type one or more numbers, for example 0712 345 678, 0722 000 111" aria-label="Phone numbers" />
              <label style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-start' }}>
                <input type="checkbox" checked={asked} onChange={e => setAsked(e.target.checked)} style={{ marginTop: 4 }} />
                <span>The people with these numbers asked to receive this message. Anyone who replies STOP is never messaged again.</span>
              </label>
            </>
          )}
          <textarea className="form-control" rows={4} value={message} onChange={e => setMessage(e.target.value)} placeholder="For example: Service starts at 9am this Sunday. God bless you." aria-label="Message" />
          <p className="cd-hint">{clean.length} characters · {parts(clean)} SMS part{parts(clean) === 1 ? '' : 's'} each (up to 3). Each part is counted against your monthly limit.
            {audience !== 'numbers' && <>{' '}<button type="button" className="cd-call" onClick={() => setMessage(m => m + '{first_name}')}>Add {'{first_name}'}</button></>}</p>
          {error && <div className="cd-err" role="alert"><span>{error}</span></div>}
          {note && <div className="cd-item" role="status"><span>{note}</span></div>}
          <button type="button" className="cd-act" onClick={doPreview} disabled={busy || !message.trim() || (audience === 'numbers' && !numbers.trim())}>Check before sending</button>
          {fresh && (
            <div className="cd-card" role="status" style={{ padding: '0.9rem 1rem' }}>
              <p><b>{preview.recipients}</b> member{preview.recipients === 1 ? '' : 's'} will get this · {preview.total_parts} SMS parts in all.</p>
              <p className="cd-hint">This month: {preview.used} used of {preview.limit}. After this: {preview.remaining_after} left.
                {preview.skipped_no_phone > 0 && ` ${preview.skipped_no_phone} agreed but have no valid phone.`}
                {preview.opted_out > 0 && ` ${preview.opted_out} replied STOP and will be skipped.`}
                {preview.invalid_numbers && preview.invalid_numbers.length > 0 && ` Could not read: ${preview.invalid_numbers.join(', ')}.`}</p>
              <p className="cd-hint">Example: "{preview.sample}"</p>
              <button type="button" className="cd-act" onClick={doSend} disabled={busy || preview.remaining_after < 0}>{busy ? 'Sending…' : `Send to ${preview.recipients} now`}</button>
              {preview.remaining_after < 0 && <p className="cd-err" role="alert"><span>Over your monthly limit. Send fewer or upgrade.</span></p>}
            </div>
          )}
        </div>
      </section>
      <section className="cd-card" aria-labelledby="sms-hist">
        <h2 className="cd-h" id="sms-hist">Recent messages <span className="cd-badge">{hist.used} / {hist.limit} parts this month</span></h2>
        {hist.messages.length === 0 && <p className="cd-empty">Nothing sent yet.</p>}
        <ul className="cd-list">{hist.messages.slice(0, 30).map(m => (
          <li key={m.id} className="cd-item" style={{ alignItems: 'flex-start', gap: '0.6rem' }}>
            <span><b>{m.phone}</b> · {when(m.created_at)}<br /><span style={{ color: 'var(--gray-600)' }}>{m.body.slice(0, 80)}{m.body.length > 80 ? '…' : ''}</span>{m.detail && <><br /><span>{m.detail}</span></>}</span>
            <span className="cd-badge">{m.status}</span>
          </li>
        ))}</ul>
      </section>
    </div>
  );
}
