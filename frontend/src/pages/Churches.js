import React, { useState, useEffect, useCallback } from 'react';
import { churchesAPI, governanceAPI } from '../api';
import { useAuth } from '../contexts/AuthContext';
import { KENYAN_COUNTIES, CHURCH_SIZES, PLAN_LABELS } from '../constants';

const EMPTY = { name: '', county: '', sub_county: '', size: '', phone: '', email: '', address: '', member_prefix: 'CHR',
                denomination_id: '', denomination_other: '',
                admin_full_name: '', admin_username: '', admin_email: '', admin_password: '' };
const PASSWORD_HINT = 'At least 10 characters, with letters and numbers';

function planBadge(plan) {
  const colors = { trial: '#6c757d', seed: '#12805C', growth: '#2339F5', parish: '#B54708', cathedral: '#6f42c1' };
  const info = PLAN_LABELS[plan] || {};
  return <span style={{ background: colors[plan] || '#6c757d', color: '#fff', padding: '2px 8px', borderRadius: 12,
    fontSize: '0.75rem', fontWeight: 600, textTransform: 'capitalize' }}>{info.label || plan}</span>;
}

function Field({ label, children, wide }) {
  return <div className="form-group" style={wide ? { gridColumn: '1/-1' } : undefined}><label className="form-label">{label}</label>{children}</div>;
}

function FirstAdmin({ church, onClose, onDone }) {
  const [f, setF] = useState({ full_name: '', username: '', email: '', password: '' });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const set = (k, v) => setF(x => ({ ...x, [k]: v }));
  const save = async e => {
    e.preventDefault(); setBusy(true); setError('');
    try { await churchesAPI.firstAdmin(church.id, f); onDone(); }
    catch (err) { setError(err.response?.data?.error || 'Could not save.'); }
    finally { setBusy(false); }
  };
  return (
    <div className="modal-overlay"><div className="modal" style={{ maxWidth: 520 }}>
      <div className="modal-header">
        <span className="modal-title">First admin for {church.name}</span>
        <button type="button" onClick={onClose} aria-label="Close" style={{ background: 'none', border: 'none', fontSize: '1.2rem', cursor: 'pointer' }}>x</button>
      </div>
      <form onSubmit={save}><div className="modal-body">
        <p style={{ color: 'var(--gray-600)', fontSize: '0.9rem', marginBottom: '0.8rem' }}>Usually the Senior Pastor. They sign in to {church.name} only, and add their own users after this. Give them the password privately.</p>
        {error && <div className="alert alert-error"><span>{error}</span></div>}
        <Field label="Full name" wide><input className="form-control" value={f.full_name} onChange={e => set('full_name', e.target.value)} /></Field>
        <Field label="Username *" wide><input className="form-control" value={f.username} required onChange={e => set('username', e.target.value)} /></Field>
        <Field label="Email *" wide><input className="form-control" type="email" value={f.email} required onChange={e => set('email', e.target.value)} /></Field>
        <Field label="Password *" wide><input className="form-control" type="password" value={f.password} required minLength={10} placeholder={PASSWORD_HINT} onChange={e => set('password', e.target.value)} /></Field>
      </div>
      <div className="modal-footer">
        <button type="button" className="btn btn-outline" onClick={onClose}>Cancel</button>
        <button type="submit" className="btn btn-gold" disabled={busy}>{busy ? 'Saving...' : 'Create admin'}</button>
      </div></form>
    </div></div>
  );
}

export default function Churches() {
  const { user } = useAuth();
  const [churches, setChurches] = useState([]);
  const [denoms, setDenoms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState(null);
  const [adminFor, setAdminFor] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [note, setNote] = useState('');
  const load = useCallback(() => {
    setLoading(true);
    churchesAPI.getAll().then(r => setChurches(r.data.churches)).catch(() => setChurches([])).finally(() => setLoading(false));
  }, []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    governanceAPI.denominations({}).then(r => setDenoms(r.data.denominations || [])).catch(() => setDenoms([]));
  }, []);
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const openCreate = () => { setEditing(null); setForm(EMPTY); setError(''); setShowModal(true); };
  const openEdit = c => {
    setEditing(c);
    setForm({ ...EMPTY, name: c.name || '', county: c.county || '', sub_county: c.sub_county || '', size: c.size || '',
              phone: c.phone || '', email: c.email || '', address: c.address || '', member_prefix: c.member_prefix || 'CHR' });
    setError(''); setShowModal(true);
  };
  const handleSave = async e => {
    e.preventDefault(); setSaving(true); setError('');
    const profile = { name: form.name, county: form.county, sub_county: form.sub_county, size: form.size,
                      phone: form.phone, email: form.email, address: form.address, member_prefix: form.member_prefix };
    try {
      if (editing) {
        await churchesAPI.update(editing.id, profile);
      } else {
        const body = { ...profile };
        if (form.denomination_id === 'other') body.denomination_other = form.denomination_other.trim();
        else if (form.denomination_id) body.denomination_id = Number(form.denomination_id);
        if (form.admin_username || form.admin_email || form.admin_password) {
          Object.assign(body, { admin_full_name: form.admin_full_name, admin_username: form.admin_username.trim(),
                                admin_email: form.admin_email.trim(), admin_password: form.admin_password });
        }
        await churchesAPI.create(body);
      }
      setShowModal(false); load();
    } catch (err) { setError(err.response?.data?.error || 'Save failed'); }
    finally { setSaving(false); }
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', gap: '1rem', flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ fontFamily: 'var(--font-display)', fontSize: '1.5rem', color: 'var(--navy)' }}>Churches</h1>
          <p style={{ color: 'var(--gray-600)', fontSize: '0.85rem' }}>{churches.length} registered</p>
        </div>
        <button className="btn btn-gold" onClick={openCreate}>+ Register Church</button>
      </div>
      {note && <div className="alert alert-success" role="status"><span>{note}</span></div>}
      <div className="card" style={{ padding: 0, overflowX: 'auto' }}>
        {loading ? (<div style={{ padding: '3rem', textAlign: 'center' }}><div className="loader" style={{ width: 32, height: 32, margin: '0 auto' }} /></div>) : (
        <table><thead><tr><th>Name</th><th>County</th><th>Denomination</th><th>Members</th><th>Plan</th><th>Actions</th></tr></thead>
        <tbody>{churches.map(c => (<tr key={c.id}>
          <td style={{ fontWeight: 600, color: 'var(--navy)' }}>{c.name}</td>
          <td>{c.county || '-'}</td>
          <td style={{ fontSize: '0.82rem' }}>{c.denomination || '-'}</td>
          <td>{c.member_count}</td><td>{planBadge(c.subscription_plan)}</td>
          <td style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
            <button className="btn btn-outline btn-sm" onClick={() => openEdit(c)}>Edit</button>
            {user?.is_platform_owner && c.id !== user?.church_id && (
              <button className="btn btn-outline btn-sm" onClick={() => { setNote(''); setAdminFor(c); }}>Add first admin</button>
            )}
          </td>
        </tr>))}</tbody></table>)}
      </div>
      {adminFor && <FirstAdmin church={adminFor} onClose={() => setAdminFor(null)}
                               onDone={() => { setNote(`Admin created for ${adminFor.name}. They can now sign in.`); setAdminFor(null); load(); }} />}
      {showModal && (
        <div className="modal-overlay"><div className="modal" style={{ maxWidth: 600 }}>
          <div className="modal-header">
            <span className="modal-title">{editing ? `Edit: ${editing.name}` : 'Register New Church'}</span>
            <button type="button" onClick={() => setShowModal(false)} aria-label="Close" style={{ background: 'none', border: 'none', fontSize: '1.2rem', cursor: 'pointer' }}>x</button>
          </div>
          <form onSubmit={handleSave}><div className="modal-body">
            {error && <div className="alert alert-error"><span>{error}</span></div>}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
              <Field label="Church name *" wide><input className="form-control" value={form.name} required onChange={e => set('name', e.target.value)} /></Field>
              <Field label="County">
                <select className="form-control" value={form.county} onChange={e => set('county', e.target.value)}>
                  <option value="">Select county</option>
                  {KENYAN_COUNTIES.map(c => <option key={c}>{c}</option>)}
                </select></Field>
              <Field label="Sub-county"><input className="form-control" value={form.sub_county} placeholder="e.g. Kisumu Central" onChange={e => set('sub_county', e.target.value)} /></Field>
              {!editing && (
                <Field label="Denomination" wide>
                  <select className="form-control" value={form.denomination_id} onChange={e => set('denomination_id', e.target.value)}>
                    <option value="">Choose later</option>
                    {denoms.map(d => <option key={d.id} value={d.id}>{d.name}{d.short_name ? ` (${d.short_name})` : ''}</option>)}
                    <option value="other">Other: not in this list</option>
                  </select>
                  {form.denomination_id === 'other' && (
                    <input className="form-control" style={{ marginTop: '0.5rem' }} value={form.denomination_other} required minLength={3}
                           placeholder="Full name of the denomination or ministry" onChange={e => set('denomination_other', e.target.value)} />
                  )}
                </Field>
              )}
              <Field label="Church size">
                <select className="form-control" value={form.size} onChange={e => set('size', e.target.value)}>
                  <option value="">Select size</option>
                  {CHURCH_SIZES.map(s => <option key={s}>{s}</option>)}
                </select></Field>
              <Field label="Member ID prefix"><input className="form-control" value={form.member_prefix} onChange={e => set('member_prefix', e.target.value.toUpperCase().slice(0, 6))} /></Field>
              <Field label="Phone"><input className="form-control" value={form.phone} onChange={e => set('phone', e.target.value)} /></Field>
              <Field label="Email"><input className="form-control" type="email" value={form.email} onChange={e => set('email', e.target.value)} /></Field>
              <Field label="Address" wide><textarea className="form-control" rows={2} value={form.address} onChange={e => set('address', e.target.value)} /></Field>
              <p style={{ gridColumn: '1/-1', color: 'var(--gray-600)', fontSize: '0.85rem' }}>M-Pesa Paybill, Till and bank accounts are added by the church itself on its Payments page, so each church's money stays its own.</p>
              {!editing && (
                <>
                  <h3 style={{ gridColumn: '1/-1', fontSize: '1rem', marginTop: '0.5rem' }}>First admin login (optional)</h3>
                  <p style={{ gridColumn: '1/-1', color: 'var(--gray-600)', fontSize: '0.85rem' }}>Usually the Senior Pastor. Leave blank to add later with "Add first admin".</p>
                  <Field label="Full name"><input className="form-control" value={form.admin_full_name} onChange={e => set('admin_full_name', e.target.value)} /></Field>
                  <Field label="Username"><input className="form-control" value={form.admin_username} onChange={e => set('admin_username', e.target.value)} /></Field>
                  <Field label="Email"><input className="form-control" type="email" value={form.admin_email} onChange={e => set('admin_email', e.target.value)} /></Field>
                  <Field label="Password"><input className="form-control" type="password" value={form.admin_password} minLength={10} placeholder={PASSWORD_HINT} onChange={e => set('admin_password', e.target.value)} /></Field>
                </>
              )}
            </div></div>
            <div className="modal-footer">
              <button type="button" className="btn btn-outline" onClick={() => setShowModal(false)}>Cancel</button>
              <button type="submit" className="btn btn-gold" disabled={saving}>{saving ? 'Saving...' : (editing ? 'Update' : 'Register church')}</button>
            </div></form>
        </div></div>)}
    </div>
  );
}
