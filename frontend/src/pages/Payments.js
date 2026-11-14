import React, { useCallback, useEffect, useRef, useState } from 'react';
import { accountsAPI, membersAPI, paymentsAPI } from '../api';
import { useAuth } from '../contexts/AuthContext';
import OwnMpesa from './OwnMpesa';
import './dashboard.css';

const TYPES = [['tithe', 'Tithe'], ['offering', 'Offering'], ['donation', 'Donation'], ['project_fund', 'Project fund']];
const WORDS = {
  pending: 'Waiting for the member to enter their M-Pesa PIN on their phone…',
  paid: 'Received. The gift is now in the ledger, waiting for a second person to verify.',
  cancelled: 'The member cancelled the prompt on their phone.',
  failed: 'The payment did not go through.',
  review: 'Money moved but the details did not match. Check the M-Pesa statement before recording it.',
  expired: 'No answer came in 15 minutes. Send the prompt again.',
};

function MemberPicker({ value, onPick }) {
  const [text, setText] = useState('');
  const [rows, setRows] = useState([]);
  const timer = useRef(null);

  const search = q => {
    setText(q);
    clearTimeout(timer.current);
    if (q.trim().length < 2) { setRows([]); return; }
    timer.current = setTimeout(() => {
      membersAPI.getAll({ search: q.trim(), per_page: 8 })
        .then(r => setRows(r.data.members || []))
        .catch(() => setRows([]));
    }, 300);
  };

  if (value) {
    return (
      <div className="cd-item">
        <span><b>{value.full_name}</b> <span style={{ color: 'var(--gray-600)' }}>{value.member_id}</span></span>
        <button type="button" className="cd-call" onClick={() => onPick(null)}>Change</button>
      </div>
    );
  }
  return (
    <div>
      <input className="form-control" placeholder="Type a name or member number" value={text}
             onChange={e => search(e.target.value)} aria-label="Find a member" />
      {rows.length > 0 && (
        <ul className="cd-list" style={{ marginTop: 6 }}>
          {rows.map(m => (
            <li key={m.id}>
              <button type="button" className="cd-item" style={{ width: '100%', border: 0, cursor: 'pointer', textAlign: 'left' }}
                      onClick={() => { onPick(m); setRows([]); setText(''); }}>
                <span><b>{m.full_name}</b></span><span style={{ color: 'var(--gray-600)' }}>{m.member_id}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function AskForPayment() {
  const [phone, setPhone] = useState('');
  const [amount, setAmount] = useState('');
  const [type, setType] = useState('tithe');
  const [member, setMember] = useState(null);
  const [sent, setSent] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!sent || sent.status !== 'pending') return undefined;
    const id = setInterval(() => {
      paymentsAPI.getRequest(sent.id).then(r => setSent(r.data)).catch(() => {});
    }, 4000);
    return () => clearInterval(id);
  }, [sent]);

  const submit = async e => {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      const body = { phone, amount: Number(amount), transaction_type: type };
      if (member) body.member_id = member.id;
      const res = await paymentsAPI.stk(body);
      setSent(res.data);
    } catch (err) {
      const data = err.response?.data;
      const missing = data?.missing?.length ? ` Missing: ${data.missing.join(', ')}.` : '';
      setError((data?.error || 'Could not send the request. Try again.') + missing);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="cd-card" aria-labelledby="pay-ask">
      <h2 className="cd-h" id="pay-ask">Ask for a payment</h2>
      <p className="cd-hint">The member gets an M-Pesa prompt on their phone and confirms with their PIN.</p>
      <form onSubmit={submit} style={{ display: 'grid', gap: '0.8rem' }}>
        <div className="form-group">
          <label className="form-label" htmlFor="pay-phone">Phone number</label>
          <input id="pay-phone" className="form-control" inputMode="tel" placeholder="0712 345 678"
                 value={phone} onChange={e => setPhone(e.target.value)} required />
        </div>
        <div className="form-group">
          <label className="form-label" htmlFor="pay-amount">Amount (KES)</label>
          <input id="pay-amount" className="form-control" inputMode="numeric" placeholder="500"
                 value={amount} onChange={e => setAmount(e.target.value.replace(/[^0-9]/g, ''))} required />
        </div>
        <div className="form-group">
          <label className="form-label" htmlFor="pay-type">What is it for</label>
          <select id="pay-type" className="form-control" value={type} onChange={e => setType(e.target.value)}>
            {TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label className="form-label">Member (optional)</label>
          <MemberPicker value={member} onPick={setMember} />
        </div>
        {error && <div className="cd-err" role="alert"><span>{error}</span></div>}
        <button className="cd-act" type="submit" disabled={busy}>{busy ? 'Sending…' : 'Send payment prompt'}</button>
      </form>
      {sent && (
        <div className="cd-item" style={{ marginTop: '1rem', alignItems: 'flex-start' }} role="status">
          <span>{WORDS[sent.status] || sent.status}
            {sent.mpesa_receipt && <><br /><b>Receipt {sent.mpesa_receipt}</b></>}
          </span>
          <span className="cd-count" style={{ fontSize: '0.95rem' }}>KES {sent.amount}</span>
        </div>
      )}
    </section>
  );
}

function InboxRow({ event, onDone }) {
  const [member, setMember] = useState(null);
  const [type, setType] = useState('tithe');
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');
  const open = event.status === 'unmatched';

  const act = async fn => {
    setError('');
    try { await fn(); onDone(); } catch (err) { setError(err.response?.data?.error || 'Could not save. Try again.'); }
  };

  return (
    <li className="cd-card" style={{ padding: '0.9rem 1rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.75rem' }}>
        <div>
          <b>KES {event.amount}</b> <span style={{ color: 'var(--gray-600)' }}>· {event.payer_name || 'Unknown payer'}</span>
          <div style={{ color: 'var(--gray-600)', fontSize: '0.85rem' }}>
            Account text: “{event.bill_ref || 'none'}” · {event.trans_id}
          </div>
        </div>
        {!open && <span className="cd-badge">{event.status}</span>}
      </div>
      {open && (
        <div style={{ display: 'grid', gap: '0.6rem', marginTop: '0.8rem' }}>
          <MemberPicker value={member} onPick={setMember} />
          <select className="form-control" value={type} onChange={e => setType(e.target.value)} aria-label="What is it for">
            {TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
          <button type="button" className="cd-act" disabled={!member}
                  onClick={() => act(() => paymentsAPI.match(event.id, { member_id: member.id, transaction_type: type }))}>
            Match to this member
          </button>
          <input className="form-control" placeholder="Not a church payment? Say why, then tap Ignore"
                 value={reason} onChange={e => setReason(e.target.value)} aria-label="Reason to ignore" />
          <button type="button" className="cd-act alt" disabled={!reason.trim()}
                  onClick={() => act(() => paymentsAPI.ignore(event.id, { reason: reason.trim() }))}>Ignore</button>
        </div>
      )}
      {error && <div className="cd-err" role="alert" style={{ marginTop: '0.6rem' }}><span>{error}</span></div>}
    </li>
  );
}

function Inbox() {
  const [status, setStatus] = useState('unmatched');
  const [data, setData] = useState({ events: [], unmatched: 0 });
  const [failed, setFailed] = useState(false);

  const load = useCallback(() => {
    setFailed(false);
    paymentsAPI.inbox({ status }).then(r => setData(r.data)).catch(() => setFailed(true));
  }, [status]);
  useEffect(() => { load(); }, [load]);

  return (
    <section className="cd-card" aria-labelledby="pay-inbox">
      <h2 className="cd-h" id="pay-inbox">Paybill inbox {data.unmatched > 0 && <span className="cd-badge">{data.unmatched}</span>}</h2>
      <p className="cd-hint">Payments sent to your Paybill. Most match a member by themselves; the rest wait here for you.</p>
      <div className="cd-actions" style={{ marginBottom: '0.9rem' }}>
        {['unmatched', 'matched', 'ignored'].map(s => (
          <button key={s} type="button" className={`cd-act ${status === s ? '' : 'alt'}`} onClick={() => setStatus(s)}>{s}</button>
        ))}
      </div>
      {failed && <div className="cd-err" role="alert"><span>Could not load the inbox.</span><button type="button" onClick={load}>Try again</button></div>}
      {!failed && data.events.length === 0 && <p className="cd-empty">Nothing here. Payments to your Paybill will appear as they arrive.</p>}
      <ul className="cd-list">
        {data.events.map(ev => <InboxRow key={ev.id} event={ev} onDone={load} />)}
      </ul>
    </section>
  );
}

const KINDS = [
  ['bank_paybill', 'Bank Paybill or bank till (for example Lipa na KCB)'],
  ['safaricom_paybill', 'Safaricom Paybill'],
  ['safaricom_till', 'Safaricom Till (Buy Goods)'],
  ['bank_account', 'Bank account only'],
];

function Accounts() {
  const { user } = useAuth();
  const blank = { kind: 'bank_paybill', label: '', business_no: '', account_no: '', bank_name: '', instructions: '' };
  const [rows, setRows] = useState([]);
  const [form, setForm] = useState(blank);
  const [error, setError] = useState('');
  const load = useCallback(() => {
    accountsAPI.list().then(r => setRows(r.data.accounts || [])).catch(() => setRows([]));
  }, []);
  useEffect(() => { load(); }, [load]);
  const isAdmin = user?.role === 'admin';
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const save = async e => {
    e.preventDefault();
    setError('');
    try {
      await accountsAPI.create(form);
      setForm(blank);
      load();
    } catch (err) {
      setError(err.response?.data?.error || 'Could not save. Try again.');
    }
  };
  const remove = async id => { try { await accountsAPI.remove(id); load(); } catch (err) { setError('Could not remove it.'); } };

  return (
    <section className="cd-card" style={{ marginBottom: '0.9rem' }} aria-labelledby="acc-h">
      <h2 className="cd-h" id="acc-h">Where this church receives money</h2>
      <p className="cd-hint">Members pay these. ChurchOS matches what arrives by member number.</p>
      {rows.length === 0 && <p className="cd-empty">No account saved yet.</p>}
      <ul className="cd-list">
        {rows.map(a => (
          <li key={a.id} className="cd-item" style={{ alignItems: 'flex-start' }}>
            <span>
              <b>{a.label}</b><br />
              {a.business_no && <span>Business no. {a.business_no}</span>}
              {a.account_no && <span> · Account {a.account_no}</span>}
              {a.bank_name && <span> · {a.bank_name}</span>}
              {a.instructions && <><br /><span style={{ color: 'var(--gray-600)' }}>{a.instructions}</span></>}
            </span>
            {isAdmin && <button type="button" className="cd-call" onClick={() => remove(a.id)}>Remove</button>}
          </li>
        ))}
      </ul>
      {isAdmin && (
        <form onSubmit={save} style={{ display: 'grid', gap: '0.6rem', marginTop: '1rem' }}>
          <select className="form-control" value={form.kind} onChange={e => set('kind', e.target.value)} aria-label="Kind of account">
            {KINDS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
          <input className="form-control" placeholder="Name, for example Migosi tithes" value={form.label} onChange={e => set('label', e.target.value)} required />
          <input className="form-control" inputMode="numeric" placeholder="Business or Till number" value={form.business_no} onChange={e => set('business_no', e.target.value)} />
          <input className="form-control" placeholder="Account number (what members type)" value={form.account_no} onChange={e => set('account_no', e.target.value)} />
          <input className="form-control" placeholder="Bank name (optional)" value={form.bank_name} onChange={e => set('bank_name', e.target.value)} />
          <input className="form-control" placeholder="Instructions for members (optional)" value={form.instructions} onChange={e => set('instructions', e.target.value)} />
          {error && <div className="cd-err" role="alert"><span>{error}</span></div>}
          <button className="cd-act alt" type="submit">Save account</button>
        </form>
      )}
    </section>
  );
}

function ImportStatement() {
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const pick = e => {
    const input = e.target;
    const file = input.files && input.files[0];
    if (!file) return;
    setError('');
    setResult(null);
    setBusy(true);
    const reader = new FileReader();
    reader.onload = async () => {
      try {
        const res = await accountsAPI.importStatement({ csv: String(reader.result) });
        setResult(res.data);
      } catch (err) {
        setError(err.response?.data?.error || 'Could not read that file.');
      } finally {
        setBusy(false);
        input.value = '';
      }
    };
    reader.onerror = () => { setError('Could not open the file.'); setBusy(false); };
    reader.readAsText(file);
  };

  return (
    <section className="cd-card" style={{ marginBottom: '0.9rem' }} aria-labelledby="imp-h">
      <h2 className="cd-h" id="imp-h">Import a statement</h2>
      <p className="cd-hint">Upload your bank or M-Pesa statement as a CSV file. Payments with a member number or phone number in the details are recorded; the rest wait in the inbox below. Importing the same file twice records nothing twice.</p>
      <input type="file" accept=".csv,text/csv,text/plain" onChange={pick} disabled={busy} aria-label="Statement file" />
      {busy && <p className="cd-hint">Reading the statement…</p>}
      {error && <div className="cd-err" role="alert" style={{ marginTop: '0.6rem' }}><span>{error}</span></div>}
      {result && (
        <div className="cd-item" style={{ marginTop: '0.8rem' }} role="status">
          <span>
            <b>{result.imported}</b> new · <b>{result.matched}</b> matched to members · <b>{result.unmatched}</b> waiting in the inbox ·
            {' '}{result.duplicates} already recorded · {result.skipped} skipped (not money in)
          </span>
        </div>
      )}
    </section>
  );
}

function SetupCheck() {
  const { user } = useAuth();
  const [status, setStatus] = useState(null);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    paymentsAPI.setup().then(r => setStatus(r.data)).catch(() => setStatus(null));
  }, []);

  const test = async () => {
    setBusy(true);
    setResult(null);
    try {
      const res = await paymentsAPI.testSetup();
      setResult({ ok: true, text: res.data.message });
    } catch (err) {
      setResult({ ok: false, text: err.response?.data?.error || 'The test could not run. Try again.' });
    } finally {
      setBusy(false);
    }
  };

  if (!status) return null;
  const items = [...status.missing.map(name => `Missing in Render: ${name}`), ...status.problems];
  return (
    <section className="cd-card" style={{ marginBottom: '0.9rem' }} aria-labelledby="pay-setup">
      <h2 className="cd-h" id="pay-setup">M-Pesa setup {status.configured
        ? <span className="cd-badge">ready · {status.environment}</span>
        : <span className="cd-badge">needs attention</span>}</h2>
      {status.configured ? (
        <p className="cd-hint">All settings are present. Use the test to confirm Safaricom accepts your keys.</p>
      ) : (
        <>
          <p className="cd-hint">Fix these in Render, under Environment, then reload this page.</p>
          <ul className="cd-list">{items.map(text => <li key={text} className="cd-item">{text}</li>)}</ul>
        </>
      )}
      {user?.role === 'admin' && status.missing.length === 0 && (
        <button type="button" className="cd-act alt" style={{ marginTop: '0.8rem' }} onClick={test} disabled={busy}>
          {busy ? 'Testing…' : 'Test connection to Safaricom'}
        </button>
      )}
      {result && (
        <div className={result.ok ? 'cd-item' : 'cd-err'} role="status" style={{ marginTop: '0.8rem' }}>
          <span>{result.text}</span>
        </div>
      )}
    </section>
  );
}

export default function Payments() {
  const { user } = useAuth();
  if (!['admin', 'treasurer'].includes(user?.role)) {
    return <div className="cd"><p className="cd-empty">Payments are handled by the treasurer and admin.</p></div>;
  }
  return (
    <div className="cd">
      <div className="cd-head">
        <div>
          <h1 className="cd-title">Payments</h1>
          <p className="cd-sub">Ask for M-Pesa payments and match what arrives on your Paybill.</p>
        </div>
      </div>
      <SetupCheck />
      <OwnMpesa />
      <Accounts />
      <ImportStatement />
      <div className="cd-grid even">
        <AskForPayment />
        <Inbox />
      </div>
    </div>
  );
}
