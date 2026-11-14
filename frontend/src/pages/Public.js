import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { publicAPI, churchesAPI } from '../api';
import './public.css';

const CONTACT = process.env.REACT_APP_CONTACT_EMAIL || 'jmskoero@gmail.com';
const UPDATED = '14 November 2026';

function Shell({ children }) {
  return (
    <div className="pb">
      <header className="pb-top">
        <Link to="/login" className="pb-brand">ChurchOS</Link>
        <Link to="/login" className="pb-back">Sign in</Link>
      </header>
      <main className="pb-wrap">
        <div className="pb-card">{children}</div>
        <nav className="pb-links" aria-label="Legal">
          <Link to="/privacy">Privacy Policy</Link>
          <Link to="/terms">Terms of Use</Link>
          <Link to="/request">Request ChurchOS</Link>
        </nav>
      </main>
    </div>
  );
}

export function Privacy() {
  useEffect(() => { document.title = 'Privacy Policy · ChurchOS'; }, []);
  return (
    <Shell>
      <h1>Privacy Policy</h1>
      <p className="pb-meta">Last updated {UPDATED}</p>

      <h2>Who we are</h2>
      <p>ChurchOS is a church management service run by James Koero from Kisumu, Kenya. Contact: <a href={`mailto:${CONTACT}`}>{CONTACT}</a>.</p>

      <h2>Whose data is whose</h2>
      <ul>
        <li><b>Church records</b> (members, attendance, giving, events, messages): each church decides what to record and why. The church is the data controller. ChurchOS only stores and processes these records for the church.</li>
        <li><b>Account and request details</b> (the names, emails, phone numbers and passwords of people who sign in, and the details sent on the Request ChurchOS form): ChurchOS is the data controller.</li>
      </ul>

      <h2>What is handled</h2>
      <ul>
        <li>Sign-in accounts: name, username, email, role, and a scrambled (hashed) password. We never see or store your real password.</li>
        <li>Church records a church types in: member names, phone numbers, emails, addresses, family details, baptism and membership dates, attendance, giving, and SMS sent through the service.</li>
        <li>Payment references: M-Pesa codes, amounts and dates. ChurchOS does not hold church money.</li>
        <li>Security data: sign-in attempts, the network address of requests, and an activity log of who changed what.</li>
      </ul>
      <p>Church membership shows a person's religious belief. Kenyan law treats that as sensitive personal data, so churches must have the person's consent. ChurchOS lets a church record each member's consent and whether they agreed to be texted.</p>

      <h2>Why it is used</h2>
      <p>To run the service, keep it secure, send the messages a church asks us to send, bill churches for ChurchOS, and give support. We do not sell personal data, show adverts, or build profiles of people.</p>

      <h2>Who can see it</h2>
      <ul>
        <li>People in a church see only that church's records, and only what their role allows.</li>
        <li>A regional leader (for example a Bishop) sees the totals and a read-only member list of a church only after that church accepts the leader's invitation. Each look is written in that church's own activity log.</li>
        <li>No screen in ChurchOS lets the ChurchOS owner browse other churches' members. Technical access to the database is for running and repairing the service, not for reading church records.</li>
      </ul>

      <h2>Companies that help us run it</h2>
      <p>Render (server), Neon (database), Vercel (website), Africa's Talking (SMS), Safaricom (M-Pesa) and GitHub (code and encrypted backups). Some of these companies run servers outside Kenya, so data can be processed outside Kenya. We give each one only what its job needs.</p>

      <h2>How it is protected</h2>
      <ul>
        <li>Everything travels over HTTPS.</li>
        <li>Passwords are hashed, accounts lock after repeated wrong attempts, and sign-in attempts are rate limited.</li>
        <li>One church cannot reach another church's records.</li>
        <li>An activity log records who changed what and cannot be edited from inside the app.</li>
        <li>A backup of the database is made each night, encrypted, and kept for 14 days.</li>
      </ul>

      <h2>How long it is kept, and deleting it</h2>
      <p>Records are kept while the church's account is active. Money entries are cancelled (voided) rather than deleted so that a church's accounts stay honest. A church can export a member's details or erase them: erasing removes the personal details and keeps only totals that do not identify anyone. Older backups that still hold a copy expire within 14 days.</p>

      <h2>Your rights</h2>
      <p>Under the Kenya Data Protection Act, 2019 you may ask to see your data, correct it, delete it, object to its use, or withdraw consent. If you are a church member, ask your church first. For anything ChurchOS controls, write to <a href={`mailto:${CONTACT}`}>{CONTACT}</a>. You may also complain to the Office of the Data Protection Commissioner at <a href="https://www.odpc.go.ke" target="_blank" rel="noopener noreferrer">odpc.go.ke</a>.</p>

      <h2>Children</h2>
      <p>A church that records details of a child must have a parent or guardian's consent. That duty sits with the church.</p>

      <h2>Changes</h2>
      <p>If this policy changes, the date above changes. Churches are told of important changes.</p>
    </Shell>
  );
}

export function Terms() {
  useEffect(() => { document.title = 'Terms of Use · ChurchOS'; }, []);
  return (
    <Shell>
      <h1>Terms of Use</h1>
      <p className="pb-meta">Last updated {UPDATED}</p>

      <h2>1. The service</h2>
      <p>ChurchOS helps a church keep member records, attendance, giving, events, messages and reports. It is run by James Koero from Kisumu, Kenya (“ChurchOS”, “we”).</p>

      <h2>2. Who may use it</h2>
      <p>A church signs up through a person with authority to act for it. That person is responsible for who the church gives logins to, and for what they do.</p>

      <h2>3. Free trial, then paying</h2>
      <p>Every church starts with a 30-day free trial. After a trial or a paid period ends there are 7 more days to renew. After that, adding or changing records pauses until the church renews. Existing records can still be read and exported. Plans and prices are shown on the Billing page inside ChurchOS.</p>

      <h2>4. How to pay ChurchOS</h2>
      <p>Pay only to the Paybill, Till or bank account shown on your own Billing page, using your ChurchOS code (it starts with COS-). ChurchOS will never ask for your password or your M-Pesa PIN.</p>

      <h2>5. Church money stays with the church</h2>
      <p>ChurchOS does not receive, hold or move church money. Offerings and tithes go straight to the church's own account. ChurchOS only records them and, where a church has set it up, matches them to members.</p>

      <h2>6. Your responsibilities</h2>
      <ul>
        <li>Record only what you have a lawful reason and, where needed, the person's consent to record.</li>
        <li>Keep passwords private and remove logins for people who leave.</li>
        <li>Send messages only to people who agreed to receive them.</li>
        <li>Do not misuse the service: no attacks, no attempts to reach another church's records, no unlawful content.</li>
      </ul>

      <h2>7. Your data</h2>
      <p>Records you enter remain the church's. You can export them. If your account closes, we return or delete the records when you ask. See the <Link to="/privacy">Privacy Policy</Link>.</p>

      <h2>8. Availability</h2>
      <p>We work to keep ChurchOS running and back it up each night, but it may be unavailable at times and we cannot promise it will never lose data. Keep your own exports of important records.</p>

      <h2>9. Responsibility</h2>
      <p>To the extent Kenyan law allows, ChurchOS is provided as it is, and we are not liable for indirect or consequential loss. Nothing here limits a right you have by law.</p>

      <h2>10. Suspending or ending</h2>
      <p>A church may stop using ChurchOS at any time. We may suspend an account that breaks these terms or is not paid, after telling the church where we can.</p>

      <h2>11. Law</h2>
      <p>These terms are governed by the laws of Kenya.</p>

      <h2>12. Changes and contact</h2>
      <p>If these terms change, the date above changes and churches are told of important changes. Questions: <a href={`mailto:${CONTACT}`}>{CONTACT}</a>.</p>
    </Shell>
  );
}

const EMPTY = { church_name: '', contact_name: '', phone: '', email: '', county: '', denomination: '',
  members_estimate: '', note: '', website: '', agree: false };

export function RequestChurch() {
  const [form, setForm] = useState(EMPTY);
  const [counties, setCounties] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [done, setDone] = useState(false);
  useEffect(() => { document.title = 'Request ChurchOS for your church'; }, []);
  useEffect(() => {
    churchesAPI.constants().then(r => setCounties(r.data.counties || [])).catch(() => {});
  }, []);
  const set = key => e => setForm({ ...form, [key]: e.target.type === 'checkbox' ? e.target.checked : e.target.value });
  const submit = async e => {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      await publicAPI.request({ ...form, members_estimate: form.members_estimate ? Number(form.members_estimate) : 0 });
      setDone(true);
    } catch (err) {
      setError(err.response?.data?.error || 'The server did not answer. It may be waking up: wait 30 seconds and try again.');
    } finally { setBusy(false); }
  };
  if (done) {
    return (
      <Shell>
        <h1>Request received</h1>
        <div className="pb-ok" role="status">Thank you. We will call or message you on the number you gave to confirm the church before anything is set up. Your church starts with a 30-day free trial.</div>
      </Shell>
    );
  }
  return (
    <Shell>
      <h1>Request ChurchOS</h1>
      <p>Tell us about your church. We confirm by phone, then set you up with a 30-day free trial.</p>
      <form onSubmit={submit}>
        <label className="pb-label" htmlFor="rq-church">Church name</label>
        <input id="rq-church" className="pb-input" required minLength={3} maxLength={120} value={form.church_name} onChange={set('church_name')} />
        <label className="pb-label" htmlFor="rq-name">Your name</label>
        <input id="rq-name" className="pb-input" required maxLength={80} autoComplete="name" value={form.contact_name} onChange={set('contact_name')} />
        <label className="pb-label" htmlFor="rq-phone">Your mobile number</label>
        <input id="rq-phone" className="pb-input" required type="tel" inputMode="tel" autoComplete="tel" placeholder="0712 345 678" value={form.phone} onChange={set('phone')} />
        <label className="pb-label" htmlFor="rq-email">Email (optional)</label>
        <input id="rq-email" className="pb-input" type="email" autoComplete="email" value={form.email} onChange={set('email')} />
        <label className="pb-label" htmlFor="rq-county">County</label>
        <select id="rq-county" className="pb-input" value={form.county} onChange={set('county')}>
          <option value="">Choose county</option>
          {counties.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <label className="pb-label" htmlFor="rq-den">Denomination or ministry</label>
        <input id="rq-den" className="pb-input" maxLength={160} placeholder="For example Ministry of Repentance and Holiness" value={form.denomination} onChange={set('denomination')} />
        <label className="pb-label" htmlFor="rq-size">About how many members? (optional)</label>
        <input id="rq-size" className="pb-input" type="number" inputMode="numeric" min="0" value={form.members_estimate} onChange={set('members_estimate')} />
        <label className="pb-label" htmlFor="rq-note">Anything we should know? (optional)</label>
        <textarea id="rq-note" className="pb-input" maxLength={500} value={form.note} onChange={set('note')} />
        <div className="pb-hp" aria-hidden="true">
          <label htmlFor="rq-web">Leave this empty</label>
          <input id="rq-web" tabIndex={-1} autoComplete="off" value={form.website} onChange={set('website')} />
        </div>
        <label className="pb-check">
          <input type="checkbox" checked={form.agree} onChange={set('agree')} />
          <span>I act for this church and accept the <Link to="/terms">Terms of Use</Link> and <Link to="/privacy">Privacy Policy</Link>.</span>
        </label>
        {error && <div className="pb-err" role="alert">{error}</div>}
        <button type="submit" className="pb-go" disabled={busy || !form.agree}>{busy ? 'Sending…' : 'Send request'}</button>
      </form>
    </Shell>
  );
}
