import React, { useCallback, useEffect, useState } from 'react';
import { billingAPI } from '../api';
import { useAuth } from '../contexts/AuthContext';
import './dashboard.css';

const kes = n => 'KES ' + new Intl.NumberFormat('en-KE').format(Math.round(n || 0));
const day = s => (s ? new Date(s).toLocaleDateString('en-KE', { day: 'numeric', month: 'short', year: 'numeric' }) : '-');
const WORDS = {
  complimentary: 'Complimentary', trial: 'Free trial', active: 'Active',
  grace: 'Ended: grace period', locked: 'Ended: new records paused',
};

function Status({ data }) {
  return (
    <section className="cd-card" style={{ marginBottom: '0.9rem' }} aria-labelledby="bl-status">
      <h2 className="cd-h" id="bl-status">Your plan <span className="cd-badge">{WORDS[data.state] || data.state}</span></h2>
      <ul className="cd-list" style={{ marginTop: '0.6rem' }}>
        <li className="cd-item"><span>Plan</span><b style={{ textTransform: 'capitalize' }}>{data.plan}{data.price_kes ? ` · ${kes(data.price_kes)} a month` : ''}</b></li>
        <li className="cd-item"><span>Members</span><b>{data.members}{data.member_limit ? ` of ${data.member_limit}` : ' (no limit)'}</b></li>
        {data.ends && <li className="cd-item"><span>{data.state === 'grace' ? 'New records pause on' : 'Runs until'}</span><b>{day(data.ends)}{data.days_left !== null ? ` · ${data.days_left} days` : ''}</b></li>}
      </ul>
      {data.invoices_due.length > 0 && (
        <>
          <h3 className="cd-h" style={{ fontSize: '1rem', marginTop: '1rem' }}>To pay</h3>
          <ul className="cd-list">{data.invoices_due.map(i => (
            <li key={i.id} className="cd-item"><span>Invoice {i.id} · {i.plan}, {i.months} month{i.months > 1 ? 's' : ''}</span><b>{kes(i.amount)}</b></li>
          ))}</ul>
          <p className="cd-hint" style={{ marginTop: '0.6rem' }}>{data.pay_instructions || 'Ask the platform owner how to pay. Your plan updates as soon as the payment is confirmed.'}</p>
        </>
      )}
    </section>
  );
}

function InvoiceRow({ inv, onDone }) {
  const [method, setMethod] = useState('mpesa');
  const [reference, setReference] = useState('');
  const [error, setError] = useState('');
  const act = async fn => { setError(''); try { await fn(); onDone(); } catch (err) { setError(err.response?.data?.error || 'Could not save.'); } };
  return (
    <li className="cd-card" style={{ padding: '0.9rem 1rem' }}>
      <div><b>{inv.church_name || `Church ${inv.church_id}`}</b> · {inv.plan}, {inv.months} month{inv.months > 1 ? 's' : ''} · <b>{kes(inv.amount)}</b> <span className="cd-badge">{inv.status}</span></div>
      {inv.status === 'due' && (
        <div style={{ display: 'grid', gap: '0.5rem', marginTop: '0.6rem' }}>
          <select className="form-control" value={method} onChange={e => setMethod(e.target.value)} aria-label="Paid by">
            <option value="mpesa">M-Pesa</option><option value="bank">Bank</option><option value="cash">Cash</option>
          </select>
          <input className="form-control" placeholder="Payment reference, for example the M-Pesa code" value={reference} onChange={e => setReference(e.target.value)} />
          <button type="button" className="cd-act" disabled={!reference.trim()} onClick={() => act(() => billingAPI.markPaid(inv.id, { method, reference: reference.trim() }))}>Mark paid</button>
          <button type="button" className="cd-act alt" onClick={() => act(() => billingAPI.voidInvoice(inv.id))}>Void</button>
        </div>
      )}
      {error && <div className="cd-err" role="alert" style={{ marginTop: '0.5rem' }}><span>{error}</span></div>}
    </li>
  );
}

function OwnerPanel() {
  const [rev, setRev] = useState(null);
  const [churches, setChurches] = useState([]);
  const [invoices, setInvoices] = useState([]);
  const [plans, setPlans] = useState([]);
  const [form, setForm] = useState({ church_id: '', plan: 'seed', months: 1 });
  const [error, setError] = useState('');
  const load = useCallback(() => {
    billingAPI.revenue().then(r => setRev(r.data)).catch(() => setRev(null));
    billingAPI.churches().then(r => setChurches(r.data.churches || [])).catch(() => setChurches([]));
    billingAPI.invoices().then(r => setInvoices(r.data.invoices || [])).catch(() => setInvoices([]));
    billingAPI.plans().then(r => setPlans((r.data || []).filter(p => p.price_kes > 0))).catch(() => setPlans([]));
  }, []);
  useEffect(() => { load(); }, [load]);
  const create = async e => {
    e.preventDefault();
    setError('');
    try { await billingAPI.createInvoice({ ...form, church_id: Number(form.church_id), months: Number(form.months) }); load(); }
    catch (err) { setError(err.response?.data?.error || 'Could not create the invoice.'); }
  };
  return (
    <>
      <section className="cd-card" style={{ marginBottom: '0.9rem' }} aria-labelledby="bl-rev">
        <h2 className="cd-h" id="bl-rev">Platform revenue</h2>
        {rev && (
          <ul className="cd-list" style={{ marginTop: '0.6rem' }}>
            <li className="cd-item"><span>Received so far</span><b>{kes(rev.total_paid)}</b></li>
            <li className="cd-item"><span>Waiting to be paid</span><b>{kes(rev.due_total)}</b></li>
            <li className="cd-item"><span>Churches</span><b>{Object.entries(rev.churches_by_state).map(([k, v]) => `${v} ${WORDS[k] || k}`).join(' · ') || '-'}</b></li>
          </ul>
        )}
      </section>
      <section className="cd-card" style={{ marginBottom: '0.9rem' }} aria-labelledby="bl-ch">
        <h2 className="cd-h" id="bl-ch">Churches</h2>
        <ul className="cd-list" style={{ marginTop: '0.6rem' }}>{churches.map(c => (
          <li key={c.id} className="cd-item"><span><b>{c.church}</b> · {c.plan} · {c.members}{c.member_limit ? `/${c.member_limit}` : ''} members</span><span className="cd-badge">{WORDS[c.state] || c.state}</span></li>
        ))}</ul>
        <form onSubmit={create} style={{ display: 'grid', gap: '0.5rem', marginTop: '1rem' }}>
          <h3 className="cd-h" style={{ fontSize: '1rem' }}>New invoice</h3>
          <select className="form-control" value={form.church_id} onChange={e => setForm({ ...form, church_id: e.target.value })} required aria-label="Church">
            <option value="">Choose a church</option>
            {churches.filter(c => c.state !== 'complimentary').map(c => <option key={c.id} value={c.id}>{c.church}</option>)}
          </select>
          <select className="form-control" value={form.plan} onChange={e => setForm({ ...form, plan: e.target.value })} aria-label="Plan">
            {plans.map(p => <option key={p.plan} value={p.plan}>{p.plan} · {kes(p.price_kes)} a month · up to {p.members} members</option>)}
          </select>
          <input className="form-control" type="number" min="1" max="12" value={form.months} onChange={e => setForm({ ...form, months: e.target.value })} aria-label="Months" />
          {error && <div className="cd-err" role="alert"><span>{error}</span></div>}
          <button type="submit" className="cd-act">Create invoice</button>
        </form>
      </section>
      <section className="cd-card" aria-labelledby="bl-inv">
        <h2 className="cd-h" id="bl-inv">Invoices</h2>
        {invoices.length === 0 && <p className="cd-empty">No invoices yet.</p>}
        <ul className="cd-list">{invoices.map(i => <InvoiceRow key={i.id} inv={i} onDone={load} />)}</ul>
      </section>
    </>
  );
}

export default function Billing() {
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => { billingAPI.status().then(r => setData(r.data)).catch(() => setFailed(true)); }, []);
  if (user?.role !== 'admin') return <div className="cd"><p className="cd-empty">Billing is handled by the church admin.</p></div>;
  return (
    <div className="cd">
      <div className="cd-head"><div><h1 className="cd-title">Billing</h1><p className="cd-sub">Your ChurchOS plan, limits and invoices.</p></div></div>
      {failed && <div className="cd-err" role="alert"><span>Could not load billing. Try again.</span></div>}
      {data && <Status data={data} />}
      {user?.is_platform_owner && <OwnerPanel />}
    </div>
  );
}
