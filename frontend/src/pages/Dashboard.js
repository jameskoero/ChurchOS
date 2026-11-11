import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts';
import { dashboardAPI, insightsAPI, churchesAPI } from '../api';
import { useAuth } from '../contexts/AuthContext';
import './home.css';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const PASTORAL = ['admin', 'pastor', 'secretary'];
const MONEY = ['admin', 'treasurer', 'pastor'];
const PAYMENTS = ['admin', 'treasurer'];
const COBALT = '#2339F5';
const NAVY = '#0C1445';

const kes = n => new Intl.NumberFormat('en-KE').format(Math.round(n || 0));

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening';
}

/** Two angular layers drawn from the real attendance counts. Null when there are fewer than two Sundays. */
function wave(values) {
  if (!values || values.length < 2) return null;
  const w = 1200;
  const h = 96;
  const max = Math.max(...values, 1);
  const step = w / (values.length - 1);
  const top = values.map((v, i) => [i * step, h - 26 - (v / max) * (h - 50)]);
  const area = pts => 'M' + pts.map(([x, y]) => `${x.toFixed(1)} ${y.toFixed(1)}`).join(' L') + ` L${w} ${h} L0 ${h} Z`;
  return { back: area(top), front: area(top.map(([x, y]) => [x, Math.min(h - 6, y + 20)])) };
}

function Kpi({ label, value, note, prefix }) {
  return (
    <div className="hm-card hm-kpi">
      <div className="hm-eyebrow">{label}</div>
      <div className="hm-kpi-value">{prefix && <small>{prefix}</small>}{value}</div>
      {note && <div className="hm-kpi-note">{note}</div>}
    </div>
  );
}

function Loading() {
  return (
    <div className="hm" aria-busy="true" aria-label="Loading dashboard">
      <div className="hm-skel" style={{ height: 300, borderRadius: 28, marginBottom: 16 }} />
      <div className="hm-kpis">{[0, 1, 2, 3].map(i => <div key={i} className="hm-skel" style={{ height: 120 }} />)}</div>
    </div>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const role = user?.role;
  const isPastoral = PASTORAL.includes(role);
  const seesMoney = MONEY.includes(role);
  const seesPayments = PAYMENTS.includes(role);

  const [stats, setStats] = useState(null);
  const [care, setCare] = useState(null);
  const [words, setWords] = useState(null);
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [church, setChurch] = useState('');

  const load = useCallback(() => {
    setLoading(true);
    setFailed(false);
    dashboardAPI.getStats().then(r => setStats(r.data)).catch(() => setFailed(true)).finally(() => setLoading(false));
    churchesAPI.getAll().then(r => setChurch(r.data.churches?.[0]?.name || '')).catch(() => {});
    if (isPastoral) insightsAPI.care().then(r => setCare(r.data)).catch(() => setCare(null));
    if (seesMoney) insightsAPI.summary().then(r => setWords(r.data.lines || [])).catch(() => setWords(null));
  }, [isPastoral, seesMoney]);

  useEffect(() => { load(); }, [load]);

  if (loading) return <Loading />;
  if (failed || !stats) {
    return (
      <div className="hm">
        <div className="hm-err" role="alert">
          <span>The dashboard could not load. Check your connection and try again.</span>
          <button type="button" onClick={load}>Try again</button>
        </div>
      </div>
    );
  }

  const trend = stats.attendance_trend || [];
  const shape = wave(trend.map(d => d.count));
  const months = {};
  (stats.finance_trend || []).forEach(d => {
    const key = d.year * 100 + d.month;
    if (!months[key]) months[key] = { key, month: MONTHS[d.month - 1], Income: 0, Expenses: 0 };
    if (d.type === 'expense') months[key].Expenses += d.total;
    else months[key].Income += d.total;
  });
  const giving = Object.values(months).sort((a, b) => a.key - b.key);
  const attention = stats.attention || [];
  const firstName = (user?.full_name || user?.username || '').split(' ')[0];
  const lead = attention.length === 0
    ? 'Nothing is waiting for you today.'
    : `${attention.length} ${attention.length === 1 ? 'thing needs' : 'things need'} you today.`;
  const inbox = attention.find(a => a.key === 'inbox');

  return (
    <div className="hm">
      <section className="hm-hero" aria-labelledby="hm-hello">
        <div className="hm-hero-top">
          <span className="hm-chip">{new Date().toLocaleDateString('en-KE', { weekday: 'long', day: 'numeric', month: 'long' })}</span>
          {church && <span className="hm-chip hm-chip-soft">{church}</span>}
        </div>
        <h1 id="hm-hello" className="hm-hello">{greeting()},<br />{firstName}.</h1>
        <p className="hm-lead">{lead}</p>
        <div className="hm-actions">
          {isPastoral && <Link className="hm-pill hm-pill-y" to="/attendance">Mark attendance</Link>}
          {!isPastoral && seesPayments && <Link className="hm-pill hm-pill-y" to="/finance">Record giving</Link>}
          {isPastoral && <Link className="hm-pill hm-pill-w" to="/members">Add a member</Link>}
          {isPastoral && seesPayments && <Link className="hm-pill hm-pill-w" to="/finance">Record giving</Link>}
          {seesPayments && (
            <Link className="hm-pill hm-pill-w" to="/payments">
              Payments{inbox ? <span className="hm-count">{inbox.count}</span> : null}
            </Link>
          )}
          {isPastoral && <Link className="hm-pill hm-pill-w" to="/events">New event</Link>}
        </div>
        <div className="hm-wave" aria-hidden={!shape}>
          {shape ? (
            <>
              <svg viewBox="0 0 1200 96" preserveAspectRatio="none">
                <path d={shape.back} fill="#3D52F7" />
                <path d={shape.front} fill={NAVY} />
              </svg>
              <span className="hm-wave-note">Sunday attendance · last {trend.length} weeks</span>
            </>
          ) : (
            <svg viewBox="0 0 1200 96" preserveAspectRatio="none"><path d="M0 70 L1200 70 L1200 96 L0 96 Z" fill={NAVY} /></svg>
          )}
        </div>
      </section>

      <div className="hm-kpis">
        <Kpi label="Active members" value={stats.members?.total || 0} note={`${stats.members?.new_this_month || 0} joined this month`} />
        <Kpi label="Last Sunday" value={stats.attendance?.last_service || 0} note={`${stats.attendance?.this_month || 0} check-ins this month`} />
        {seesMoney && (
          <Kpi label="Giving this month" prefix="KES" value={kes(stats.finance?.monthly_income)}
               note={`Spent KES ${kes(stats.finance?.monthly_expense)} · Net KES ${kes(stats.finance?.monthly_net)}`} />
        )}
        <Kpi label="Coming up" value={stats.upcoming_events?.length || 0} note="events scheduled" />
      </div>

      <div className="hm-grid">
        <section className="hm-card" aria-labelledby="hm-attn">
          <h2 className="hm-h" id="hm-attn">Needs your attention</h2>
          <p className="hm-hint">Tap an item to deal with it.</p>
          {attention.length === 0 ? (
            <p className="hm-ok">All clear. Nothing is waiting for you.</p>
          ) : (
            <ul className="hm-list">
              {attention.map(a => (
                <li key={a.key}>
                  <Link className="hm-row" to={a.to}>
                    <span>{a.label}</span>
                    <span className="hm-count hm-count-lg">{a.count}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>

        {isPastoral && (
          <section className="hm-card" aria-labelledby="hm-care">
            <h2 className="hm-h" id="hm-care">Who to check on</h2>
            <p className="hm-hint">Regulars who have not been seen for a few weeks.</p>
            {care && care.members.length > 0 ? (
              <div>
                {care.members.slice(0, 5).map(m => (
                  <div className="hm-person" key={m.id}>
                    <span className="hm-avatar" aria-hidden="true">{m.full_name[0]}</span>
                    <div className="hm-person-text"><b>{m.full_name}</b><span>Last seen {m.weeks_absent} weeks ago</span></div>
                    {m.phone && <a className="hm-pill hm-pill-n hm-pill-sm" href={`tel:${m.phone}`}>Call</a>}
                  </div>
                ))}
                {care.total > 5 && <p className="hm-note">{care.total - 5} more in Members.</p>}
              </div>
            ) : (
              <p className="hm-empty">Nobody has gone quiet. Names appear here once regular members miss four weeks in a row.</p>
            )}
          </section>
        )}

        {seesMoney && words && words.length > 0 && (
          <section className="hm-card hm-dark" aria-labelledby="hm-words">
            <h2 className="hm-h" id="hm-words">This month in words</h2>
            <p className="hm-hint">Written from your own records. Nothing is estimated.</p>
            <ul className="hm-words">{words.map((line, i) => <li key={i}>{line}</li>)}</ul>
          </section>
        )}
      </div>

      <div className="hm-grid">
        {seesMoney && (
          <section className="hm-card" aria-labelledby="hm-giv">
            <h2 className="hm-h" id="hm-giv">Giving and spending</h2>
            <p className="hm-hint">The last six months, in shillings.</p>
            {giving.length > 0 ? (
              <ResponsiveContainer width="100%" height={230}>
                <BarChart data={giving}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E1E5F2" />
                  <XAxis dataKey="month" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip formatter={v => `KES ${kes(v)}`} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="Income" fill={COBALT} radius={[6, 6, 0, 0]} />
                  <Bar dataKey="Expenses" fill={NAVY} radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="hm-empty">No giving recorded yet. <Link to="/finance">Record the first gift</Link></p>
            )}
          </section>
        )}

        <section className="hm-card" aria-labelledby="hm-events">
          <h2 className="hm-h" id="hm-events">Upcoming events</h2>
          <p className="hm-hint">The next five on the calendar.</p>
          {(stats.upcoming_events || []).length === 0 ? (
            <p className="hm-empty">No events yet. <Link to="/events">Add one</Link></p>
          ) : (
            <ul className="hm-list">
              {stats.upcoming_events.map(e => (
                <li key={e.id} className="hm-row hm-row-static">
                  <span><b>{e.title}</b></span>
                  <span className="hm-when">{new Date(e.start_date).toLocaleDateString('en-KE', { day: 'numeric', month: 'short' })}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
