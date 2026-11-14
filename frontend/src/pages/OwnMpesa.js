import React, { useCallback, useEffect, useState } from 'react';
import { ownMpesaAPI } from '../api';
import { useAuth } from '../contexts/AuthContext';
import './dashboard.css';

const EMPTY = { shortcode: '', env: 'sandbox', consumer_key: '', consumer_secret: '', passkey: '' };

// A church connects its OWN Safaricom Paybill or Till so payments go straight to its own account.
// The keys are write-only: once saved they are never shown again.
export default function OwnMpesa() {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const [info, setInfo] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [busy, setBusy] = useState('');
  const [note, setNote] = useState(null);

  const load = useCallback(() => {
    ownMpesaAPI.status().then(r => {
      setInfo(r.data);
      if (r.data.own) setForm(f => ({ ...f, shortcode: r.data.own.shortcode, env: r.data.own.env }));
    }).catch(() => setInfo(null));
  }, []);
  useEffect(() => { load(); }, [load]);

  const run = async (name, call, okText) => {
    setBusy(name);
    setNote(null);
    try {
      const res = await call();
      setNote({ ok: true, text: okText || res.data.message || 'Done.' });
      load();
      return res;
    } catch (err) {
      setNote({ ok: false, text: err.response?.data?.error || 'That did not work. Try again.' });
    } finally {
      setBusy('');
    }
    return null;
  };

  const save = async e => {
    e.preventDefault();
    const res = await run('save', () => ownMpesaAPI.save(form), 'Saved. Now test the keys.');
    if (res) setForm(f => ({ ...f, consumer_key: '', consumer_secret: '', passkey: '' }));
  };
  const remove = () => {
    if (!window.confirm('Remove your own M-Pesa setup? Payment prompts stop using it.')) return;
    run('remove', () => ownMpesaAPI.remove(), 'Removed.');
  };

  if (!info) return null;
  const own = info.own;
  const blockers = [...info.missing.map(n => `Missing in Render: ${n}`), ...info.problems];
  const set = key => e => setForm({ ...form, [key]: e.target.value });

  return (
    <section className="cd-card" style={{ marginBottom: '0.9rem' }} aria-labelledby="pay-own">
      <h2 className="cd-h" id="pay-own">Your church's own M-Pesa {own
        ? <span className="cd-badge">{own.enabled ? `on · ${own.env}` : 'saved · off'}</span>
        : <span className="cd-badge">not connected</span>}</h2>
      <p className="cd-hint">
        Connect your church's own Safaricom Paybill or Till. Members then pay straight into your church's account and
        ChurchOS only records it. This needs a Paybill or Till in your church's name and Daraja keys from the Safaricom
        developer portal. It cannot be used with a shared bank Paybill.
      </p>
      {blockers.length > 0 && (
        <>
          <p className="cd-hint">The server owner must fix these first:</p>
          <ul className="cd-list">{blockers.map(t => <li key={t} className="cd-item">{t}</li>)}</ul>
        </>
      )}
      {isAdmin && blockers.length === 0 && (
        <form onSubmit={save} style={{ marginTop: '0.6rem' }} autoComplete="off">
          <div className="form-group">
            <label className="form-label" htmlFor="om-code">Paybill or Till number</label>
            <input id="om-code" className="form-control" inputMode="numeric" value={form.shortcode} onChange={set('shortcode')} required />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="om-env">Mode</label>
            <select id="om-env" className="form-control" value={form.env} onChange={set('env')}>
              <option value="sandbox">Testing (sandbox)</option>
              <option value="live">Live (real money)</option>
            </select>
          </div>
          {[['consumer_key', 'Consumer Key'], ['consumer_secret', 'Consumer Secret'], ['passkey', 'Passkey']].map(([key, label]) => (
            <div className="form-group" key={key}>
              <label className="form-label" htmlFor={`om-${key}`}>{label}</label>
              <input id={`om-${key}`} className="form-control" type="password" autoComplete="new-password"
                     placeholder={own?.keys_saved ? 'Saved. Leave empty to keep it' : ''}
                     value={form[key]} onChange={set(key)} required={!own?.keys_saved} />
            </div>
          ))}
          <p className="cd-hint">Keys are stored encrypted and are never shown again, not even to you.</p>
          <button className="cd-act" type="submit" disabled={!!busy}>{busy === 'save' ? 'Saving…' : 'Save keys'}</button>
        </form>
      )}
      {isAdmin && own && blockers.length === 0 && (
        <div style={{ marginTop: '0.9rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button type="button" className="cd-act alt" disabled={!!busy}
                  onClick={() => run('test', () => ownMpesaAPI.test())}>
            {busy === 'test' ? 'Testing…' : own.verified_at ? 'Test again' : '1. Test keys'}
          </button>
          <button type="button" className="cd-act alt" disabled={!!busy || !own.verified_at || (own.env === 'live' && !!own.c2b_registered_at)}
                  onClick={() => run('reg', () => ownMpesaAPI.registerC2b(), 'Safaricom will now send payment notices here.')}>
            {busy === 'reg' ? 'Registering…' : own.c2b_registered_at ? 'Addresses registered' : '2. Register payment notices'}
          </button>
          <button type="button" className="cd-act" disabled={!!busy || !own.verified_at}
                  onClick={() => run('on', () => ownMpesaAPI.enable({ enabled: !own.enabled }), own.enabled ? 'Switched off.' : 'Switched on.')}>
            {own.enabled ? 'Switch off' : '3. Switch on'}
          </button>
          <button type="button" className="cd-act alt" disabled={!!busy} onClick={remove}>Remove</button>
        </div>
      )}
      {note && (
        <div className={note.ok ? 'cd-item' : 'cd-err'} role="status" style={{ marginTop: '0.8rem' }}>
          <span>{note.text}</span>
        </div>
      )}
    </section>
  );
}
