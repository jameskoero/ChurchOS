import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { checkinAPI } from '../api';
import { useAuth } from '../contexts/AuthContext';
import { clearRoster, loadQueue, loadRoster, newId, saveQueue, saveRoster } from '../lib/offlineStore';
import './checkin.css';

const TYPES = ['Sunday Morning', 'Sunday Evening', 'Wednesday Bible Study', 'Friday Prayer', 'Special Service', 'Youth Service', 'Other'];
const ALLOWED = ['admin', 'pastor', 'secretary'];
const SHOW = 60;

function todayLocal() {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 10);
}

export default function CheckIn() {
  const { user } = useAuth();
  const [type, setType] = useState('Sunday Morning');
  const [date, setDate] = useState(todayLocal());
  const [roster, setRoster] = useState(() => loadRoster());
  const [already, setAlready] = useState([]);
  const [queue, setQueue] = useState(() => loadQueue());
  const [online, setOnline] = useState(typeof navigator === 'undefined' ? true : navigator.onLine);
  const [text, setText] = useState('');
  const [syncing, setSyncing] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener('online', on);
    window.addEventListener('offline', off);
    return () => { window.removeEventListener('online', on); window.removeEventListener('offline', off); };
  }, []);

  const refresh = useCallback(() => {
    checkinAPI.roster({ service_date: date, service_type: type })
      .then(res => {
        const saved = { savedAt: Date.now(), members: res.data.members || [] };
        setRoster(saved);
        saveRoster(saved);
        setAlready(res.data.already || []);
      })
      .catch(() => { /* offline or sleeping server: keep the saved list */ });
  }, [date, type]);

  useEffect(() => { if (online) refresh(); }, [online, refresh]);

  const sync = useCallback(async () => {
    const current = loadQueue();
    if (!current.length) return;
    setSyncing(true);
    setMessage('');
    try {
      const res = await checkinAPI.sync({ records: current });
      const rejected = res.data.rejected || [];
      const done = new Set([...(res.data.done || []), ...rejected.map(r => r.client_id)]);
      const left = loadQueue().filter(q => !done.has(q.client_id));
      saveQueue(left);
      setQueue(left);
      let note = `${res.data.created} saved`;
      if (res.data.duplicates) note += `, ${res.data.duplicates} were already recorded`;
      if (rejected.length) note += `, ${rejected.length} could not be saved (${rejected[0].reason})`;
      setMessage(note + '.');
      refresh();
    } catch (err) {
      if (err.response) setMessage((err.response.data && err.response.data.error) || 'Could not sync. Your marks are still saved on this phone.');
      else setMessage('No connection. Your marks are still saved on this phone.');
    } finally {
      setSyncing(false);
    }
  }, [refresh]);

  useEffect(() => { if (online && loadQueue().length) sync(); }, [online]); // eslint-disable-line react-hooks/exhaustive-deps

  const pending = useMemo(
    () => new Set(queue.filter(q => q.service_date === date && q.service_type === type).map(q => q.member_id)),
    [queue, date, type]
  );
  const alreadySet = useMemo(() => new Set(already), [already]);

  const toggle = member => {
    if (alreadySet.has(member.id)) return;
    const existing = queue.find(q => q.member_id === member.id && q.service_date === date && q.service_type === type);
    const next = existing
      ? queue.filter(q => q !== existing)
      : [...queue, { client_id: newId(), member_id: member.id, service_type: type, service_date: date }];
    if (!saveQueue(next)) {
      setMessage('This phone has no room left to save marks. Sync now, then free some space.');
      return;
    }
    setQueue(next);
  };

  const shown = useMemo(() => {
    const q = text.trim().toLowerCase();
    const base = q
      ? roster.members.filter(m => m.full_name.toLowerCase().includes(q) || m.member_id.toLowerCase().includes(q))
      : roster.members;
    return base.slice(0, SHOW);
  }, [roster, text]);

  if (!ALLOWED.includes(user?.role)) {
    return <div className="cd"><p className="cd-empty">Check-in is for the admin, pastor and secretary.</p></div>;
  }

  const total = already.length + pending.size;
  return (
    <div className="cd ck">
      <div className="cd-head">
        <div>
          <h1 className="cd-title">Check-in</h1>
          <p className="cd-sub">Works with no signal. Marks wait on this phone and sync by themselves.</p>
        </div>
      </div>

      <div className={`ck-status${online ? '' : ' off'}`} role="status">
        <span><i aria-hidden="true" />{online ? 'Online' : 'Offline'}</span>
        <span>{queue.length > 0 ? `${queue.length} waiting to sync` : 'Everything is synced'}</span>
        {online && queue.length > 0 && <button type="button" className="cd-act alt" onClick={sync} disabled={syncing}>{syncing ? 'Syncing…' : 'Sync now'}</button>}
      </div>
      {message && <div className="cd-item" style={{ marginBottom: '0.8rem' }} role="status"><span>{message}</span></div>}

      <div className="ck-controls">
        <select className="form-control" value={type} onChange={e => setType(e.target.value)} aria-label="Service">
          {TYPES.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <input className="form-control" type="date" value={date} max={todayLocal()} onChange={e => setDate(e.target.value || todayLocal())} aria-label="Date" />
        <input className="form-control" placeholder="Find by name or member number" value={text} onChange={e => setText(e.target.value)} aria-label="Find a member" />
      </div>
      <p className="cd-hint">{total} present · {pending.size} new on this phone · {roster.members.length} members saved for offline use</p>

      {roster.members.length === 0 && (
        <p className="cd-empty">No member list on this phone yet. Open this page once with a connection and it will be saved.</p>
      )}
      <ul className="cd-list">
        {shown.map(m => {
          const isAlready = alreadySet.has(m.id);
          const isPending = pending.has(m.id);
          return (
            <li key={m.id}>
              <button type="button" className={`ck-row${isAlready || isPending ? ' on' : ''}`} aria-pressed={isAlready || isPending}
                      onClick={() => toggle(m)} disabled={isAlready}>
                <span className="ck-box" aria-hidden="true">{(isAlready || isPending) ? '\u2713' : ''}</span>
                <span className="ck-name"><b>{m.full_name}</b><span>{m.member_id}</span></span>
                <span className="ck-tag">{isAlready ? 'Recorded' : isPending ? 'On this phone' : ''}</span>
              </button>
            </li>
          );
        })}
      </ul>
      {roster.members.length > SHOW && !text.trim() && <p className="cd-hint">Showing the first {SHOW}. Type a name or number to find anyone.</p>}
      {roster.savedAt > 0 && (
        <button type="button" className="cd-call" style={{ marginTop: '1rem' }}
                onClick={() => { clearRoster(); setRoster({ savedAt: 0, members: [] }); }}>
          Remove the saved member list from this phone
        </button>
      )}
    </div>
  );
}
