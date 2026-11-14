import React, { useCallback, useEffect, useState } from 'react';
import { smsLoginAPI } from '../api';
import { useAuth } from '../contexts/AuthContext';

export default function SmsLogin() {
  const { user } = useAuth();
  const [st, setSt] = useState(null);
  const [step, setStep] = useState('idle');          // idle | code
  const [form, setForm] = useState({ phone: '', password: '' });
  const [code, setCode] = useState('');
  const [challenge, setChallenge] = useState('');
  const [error, setError] = useState('');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => { smsLoginAPI.status().then(r => setSt(r.data)).catch(() => setSt(null)); }, []);
  useEffect(() => { load(); }, [load]);

  const run = async fn => {
    setError(''); setNote(''); setBusy(true);
    try { await fn(); } catch (err) { setError(err.response?.data?.error || 'Something went wrong. Try again.'); }
    finally { setBusy(false); }
  };
  const start = e => { e.preventDefault(); run(async () => {
    const r = await smsLoginAPI.start(form);
    setChallenge(r.data.challenge); setStep('code'); setNote(`A code was sent to ${r.data.phone_hint}.`);
  }); };
  const confirm = e => { e.preventDefault(); run(async () => {
    const r = await smsLoginAPI.confirm({ challenge, code });
    setStep('idle'); setCode(''); setForm({ phone: '', password: '' });
    setNote(r.data.pending
      ? 'Phone change received. It starts in 24 hours, and your old number has been told.'
      : 'SMS sign-in is on. From now on you will type a code after your password.');
    load();
  }); };
  const off = () => { if (!form.password) { setError('Type your password above, then tap Turn off.'); return; }
    run(async () => { await smsLoginAPI.disable({ password: form.password }); setForm({ phone: '', password: '' }); setNote('SMS sign-in is off.'); load(); }); };
  const platform = on => run(async () => { await smsLoginAPI.platform({ enabled: on }); load(); });

  if (!st) return null;
  const mine = st.mine || {};
  return (
    <div className="card" style={{ marginBottom: '1.25rem' }}>
      <h3 style={{ fontFamily: 'var(--font-display)', fontSize: '1.1rem', color: 'var(--navy)', marginBottom: '0.5rem' }}>SMS sign-in</h3>
      {error && <div className="alert alert-error" role="alert"><span>{error}</span></div>}
      {note && <div className="alert alert-success" role="status"><span>{note}</span></div>}

      {user?.is_platform_owner && (
        <p style={{ fontSize: '0.88rem', marginBottom: '0.8rem' }}>
          <b>Platform:</b> {st.platform_on ? 'on' : 'off'}.{' '}
          {st.forced_off && 'Forced off by the server setting SMS_LOGIN_FORCE_OFF. '}
          {!st.sms_ready && 'Needs live SMS (not sandbox) before it can be switched on. '}
          <button type="button" className="btn btn-outline btn-sm" disabled={busy || st.forced_off || (!st.platform_on && !st.sms_ready)}
                  onClick={() => platform(!st.platform_on)}>{st.platform_on ? 'Switch off for everyone' : 'Switch on'}</button>
        </p>
      )}

      {!st.platform_on ? (
        <p style={{ color: 'var(--gray-600)', fontSize: '0.9rem' }}>Not switched on yet. When it is, you can add a code sent to your phone as a second step after your password.</p>
      ) : step === 'code' ? (
        <form onSubmit={confirm}>
          <div className="form-group">
            <label className="form-label" htmlFor="sl-code">6-digit code</label>
            <input id="sl-code" className="form-control" inputMode="numeric" autoComplete="one-time-code" maxLength={6} required value={code} onChange={e => setCode(e.target.value.replace(/\D/g, ''))} />
          </div>
          <button type="submit" className="btn btn-gold" disabled={busy || code.length !== 6}>Confirm</button>
        </form>
      ) : (
        <form onSubmit={start}>
          {mine.enabled && <p style={{ fontSize: '0.9rem', marginBottom: '0.6rem' }}>On. Codes go to <b>{mine.phone_hint}</b>.{mine.pending_phone_hint && ` A change to ${mine.pending_phone_hint} starts after 24 hours.`}</p>}
          <div className="form-group">
            <label className="form-label" htmlFor="sl-phone">{mine.enabled ? 'Change phone' : 'Your mobile number'}</label>
            <input id="sl-phone" className="form-control" type="tel" inputMode="tel" placeholder="0712 345 678" value={form.phone} onChange={e => setForm({ ...form, phone: e.target.value })} />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="sl-pass">Your password</label>
            <input id="sl-pass" className="form-control" type="password" autoComplete="current-password" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} />
          </div>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <button type="submit" className="btn btn-gold" disabled={busy || !form.phone || !form.password}>{mine.enabled ? 'Send code to new phone' : 'Send me a code'}</button>
            {mine.enabled && <button type="button" className="btn btn-outline" disabled={busy} onClick={off}>Turn off</button>}
          </div>
          <p style={{ color: 'var(--gray-600)', fontSize: '0.82rem', marginTop: '0.6rem' }}>A code only protects you if your phone and SIM stay yours. Changing the phone takes 24 hours to start, and your old number is told at once.</p>
        </form>
      )}
    </div>
  );
}
