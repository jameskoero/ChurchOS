/* eslint-disable no-unused-vars, react-hooks/exhaustive-deps */
import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { healthAPI } from '../api';
import './login.css';

export default function Login() {
  const [form, setForm] = useState({ username: '', password: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showPwd, setShowPwd] = useState(false);
  const [step, setStep] = useState(null);       // set when the server asks for an SMS code
  const [code, setCode] = useState('');
  const [server, setServer] = useState('waking');   // waking | ready | down

  // The free server sleeps when idle; start waking it as soon as this page opens.
  useEffect(() => {
    let live = true;
    healthAPI.check()
      .then(() => live && setServer('ready'))
      .catch(() => live && setServer('down'));
    return () => { live = false; };
  }, []);
  const { login, verifyCode } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const result = await login(form.username, form.password);
      if (result && result.needs_code) { setStep(result); setCode(''); return; }
      navigate('/');
    } catch (err) {
      if (err.response?.data?.error) {
        setError(err.response.data.error);
      } else {
        setServer('down');
        setError('The server did not answer. It may still be waking up: wait 30 seconds, then tap Sign in again.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleCode = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await verifyCode(step.challenge, code);
      navigate('/');
    } catch (err) {
      const text = err.response?.data?.error;
      setError(text || 'The server did not answer. Wait 30 seconds and try again.');
      if (err.response?.status === 401 || err.response?.status === 429) { setStep(null); setCode(''); }
    } finally {
      setLoading(false);
    }
  };

  if (step) {
    return (
      <div className="lg">
        <div className="lg-hero">
          <span className="lg-brand">ChurchOS</span>
          <h1 className="lg-title">One more step.</h1>
          <p className="lg-sub">We sent a 6-digit code to {step.phone_hint}.</p>
        </div>
        <form className="lg-card" onSubmit={handleCode}>
          <h2 className="lg-h">Enter code</h2>
          {error && <div className="lg-error" role="alert">{error}</div>}
          <label className="lg-label" htmlFor="lg-code">6-digit code</label>
          <input id="lg-code" className="lg-input" inputMode="numeric" autoComplete="one-time-code" autoFocus required maxLength={6}
                 value={code} onChange={e => setCode(e.target.value.replace(/\D/g, ''))} />
          <button type="submit" className="lg-go" disabled={loading || code.length !== 6}>{loading ? 'Checking…' : 'Sign in'}</button>
          <p className="lg-foot">The code lasts 5 minutes. <button type="button" className="lg-show" style={{ position: 'static', transform: 'none' }} onClick={() => { setStep(null); setError(''); }}>Start again</button></p>
        </form>
      </div>
    );
  }

  return (
    <div className="lg">
      <div className="lg-hero">
        <span className="lg-brand">
          <span className="lg-mark" aria-hidden="true">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#0C1445" strokeWidth="3" strokeLinecap="round"><path d="M12 3v18M5 10h14" /></svg>
          </span>
          ChurchOS
        </span>
        <h1 className="lg-title">Run your church<br />with clarity.</h1>
        <p className="lg-sub">Members, attendance, giving and payments in one place.</p>
      </div>

      <form className="lg-card" onSubmit={handleSubmit}>
        <h2 className="lg-h">Sign in</h2>
        {server === 'waking' && <div className="lg-note" role="status">Connecting to the server. This can take up to a minute after a quiet spell.</div>}
        {error && <div className="lg-error" role="alert">{error}</div>}

        <label className="lg-label" htmlFor="lg-user">Username or email</label>
        <input id="lg-user" className="lg-input" type="text" autoComplete="username" autoFocus required
               value={form.username} onChange={e => setForm({ ...form, username: e.target.value })} />

        <label className="lg-label" htmlFor="lg-pass">Password</label>
        <div className="lg-pass">
          <input id="lg-pass" className="lg-input" type={showPwd ? 'text' : 'password'} autoComplete="current-password" required
                 value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} />
          <button type="button" className="lg-show" onClick={() => setShowPwd(!showPwd)}>{showPwd ? 'Hide' : 'Show'}</button>
        </div>

        <button type="submit" className="lg-go" disabled={loading}>{loading ? 'Signing in…' : 'Sign in'}</button>
        <p className="lg-foot">Authorised people only.</p>
        <p className="lg-foot"><Link to="/request">Request ChurchOS for your church</Link></p>
        <p className="lg-foot"><Link to="/privacy">Privacy Policy</Link> · <Link to="/terms">Terms of Use</Link></p>
      </form>
    </div>
  );
}
