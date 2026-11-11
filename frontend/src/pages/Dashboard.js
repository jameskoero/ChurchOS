import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts';
import { dashboardAPI, insightsAPI, churchesAPI } from '../api';
import { useAuth } from '../contexts/AuthContext';
import './dashboard.css';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const PASTORAL = ['admin', 'pastor', 'secretary'];
const MONEY = ['admin', 'treasurer', 'pastor'];
const PAYMENTS = ['admin', 'treasurer'];
const NAVY = '#1A2744';
const GOLD = '#D9A441';
const RED = '#B3261E';

const kes = n => new Intl.NumberFormat('en-KE').format(Math.round(n || 0));

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening';
}

function Kpi({ label, value, note, prefix }) {
  return (
    <div className="cd-card">
      <div className="cd-kpi-label">{label}</div>
      <div className="cd-kpi-value">{prefix && <small>{prefix}</small>}{value}</div>
      {note && <div className="cd-kpi-note">{note}</div>}
    </div>
  );
}

function Loading() {
  return (
    <div className="cd" aria-busy="true" aria-label="Loading dashboard">
      <div className="cd-skel" style={{ height: 44, width: '55%', marginBottom: 18 }} />
      <div className="cd-kpis">
        {[0, 1, 2, 3].map(i => <div key={i} className="cd-skel" style={{ height: 108 }} />)}
      </div>
      <div className="cd-skel" style={{ height: 260 }} />
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
  const [churchName, setChurchName] = useState('');
  const [care, setCare] = useState(null);
  const [words, setWords] = useState(null);
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    setFailed(false);
    dashboardAPI.getStats()
      .then(r => setStats(r.data))
      .catch(() => setFailed(true))
      .finally(() => setLoading(false));
    churchesAPI.getAll()
      .then(r => setChurchName(r.data.churches?.[0]?.name || ''))
      .catch(() => {});
    if (isPastoral) {
      insightsAPI.care().then(r => setCare(r.data)).catch(() => setCare(null));
    }
    if (seesMoney) {
      insightsAPI.summary().then(r => setWords(r.data.lines || [])).catch(() => setWords(null));
    }
  }, [isPastoral, seesMoney]);

  useEffect(() => { load(); }, [load]);

  if (loading) return <Loading />;
  if (failed || !stats) {
    return (
      <div className="cd">
        <div className="cd-err" role="alert">
          <span>The dashboard could not load. Check your connection and try again.</span>
          <button type="button" onClick={load}>Try again</button>
        </div>
      </div>
    );
  }

  const attendance = (stats.attendance_trend || []).map(d => ({ date: d.date.slice(5), Attendance: d.count }));
  const months = {};
  (stats.finance_trend || []).forEach(d => {
    const key = d.year * 100 + d.month;
    if (!months[key]) months[key] = { key, month: MONTHS[d.month - 1], Income: 0, Expenses: 0 };
    if (d.type === 'expense') months[key].Expenses += d.total;
    else months[key].Income += d.total;
  });
  const giving = Object.values(months).sort((a, b) => a.key - b.key);
  const attention = stats.attention || [];
  const inbox = attention.find(a => a.key === 'inbox');
  const firstName = (user?.full_name || user?.username || '').split(' ')[0];

  return (
    <div className="cd">
      <div className="cd-head">
        <div>
          <h1 className="cd-title">{greeting()}, <span>{firstName}</span></h1>
          <p className="cd-sub">{churchName || 'Your church'} · {new Date().toLocaleDateString('en-KE', { weekday: 'long', day: 'numeric', month: 'long' })}</p>
        </div>
        <div className="cd-actions">
          {isPastoral && <Link className="cd-act" to="/attendance">Mark attendance</Link>}
          {isPastoral && <Link className="cd-act alt" to="/members">Add a member</Link>}
          {seesPayments && <Link className="cd-act alt" to="/finance">Record giving</Link>}
          {seesPayments && (
            <Link className="cd-act alt" to="/payments">
              Payments{inbox ? <span className="cd-badge">{inbox.count}</span> : null}
            </Link>
          )}
          {isPastoral && <Link className="cd-act alt" to="/events">New event</Link>}
        </div>
      </div>

      <div className="cd-kpis">
        <Kpi label="Active members" value={stats.members?.total || 0}
             note={`${stats.members?.new_this_month || 0} joined this month`} />
        <Kpi label="Last Sunday" value={stats.attendance?.last_service || 0}
             note={`${stats.attendance?.this_month || 0} check-ins this month`} />
        {seesMoney && (
          <Kpi label="Giving this month" prefix="KES" value={kes(stats.finance?.monthly_income)}
               note={`Spent: KES ${kes(stats.finance?.monthly_expense)} · Net: KES ${kes(stats.finance?.monthly_net)}`} />
        )}
        <Kpi label="Coming up" value={stats.upcoming_events?.length || 0} note="events scheduled" />
      </div>

      <div className="cd-grid two">
        <section className="cd-card" aria-labelledby="cd-attn">
          <h2 className="cd-h" id="cd-attn">Needs your attention</h2>
          <p className="cd-hint">Tap an item to deal with it.</p>
          {attention.length === 0 ? (
            <p className="cd-ok">All clear. Nothing is waiting for you.</p>
          ) : (
            <ul className="cd-list">
              {attention.map(a => (
                <li key={a.key}>
                  <Link className={`cd-item cd-tone-${a.tone}`} to={a.to}>
                    <span>{a.label}</span>
                    <span className="cd-count">{a.count}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="cd-card" aria-labelledby="cd-events">
          <h2 className="cd-h" id="cd-events">Upcoming events</h2>
          <p className="cd-hint">The next five on the calendar.</p>
          {(stats.upcoming_events || []).length === 0 ? (
            <p className="cd-empty">No events yet. <Link to="/events">Add one</Link></p>
          ) : (
            <ul className="cd-list">
              {stats.upcoming_events.map(e => (
                <li key={e.id} className="cd-item">
                  <span><b>{e.title}</b></span>
                  <span style={{ color: 'var(--gray-600)', fontSize: '0.85rem' }}>
                    {new Date(e.start_date).toLocaleDateString('en-KE', { day: 'numeric', month: 'short' })}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <div className="cd-grid even">
        <section className="cd-card" aria-labelledby="cd-att">
          <h2 className="cd-h" id="cd-att">Sunday attendance</h2>
          <p className="cd-hint">The last eight weeks.</p>
          {attendance.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={attendance}>
                <CartesianGrid strokeDasharray="3 3" stroke="#ECE8DC" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                <Tooltip />
                <Line type="monotone" dataKey="Attendance" stroke={NAVY} strokeWidth={2.5} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <p className="cd-empty">No attendance recorded yet. <Link to="/attendance">Mark your first service</Link></p>
          )}
        </section>

        {seesMoney && (
          <section className="cd-card" aria-labelledby="cd-giv">
            <h2 className="cd-h" id="cd-giv">Giving and spending</h2>
            <p className="cd-hint">The last six months, in shillings.</p>
            {giving.length > 0 ? (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={giving}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#ECE8DC" />
                  <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip formatter={v => `KES ${kes(v)}`} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="Income" fill={GOLD} radius={[4, 4, 0, 0]} />
                  <Bar dataKey="Expenses" fill={RED} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="cd-empty">No giving recorded yet. <Link to="/finance">Record the first gift</Link></p>
            )}
          </section>
        )}
      </div>

      <div className="cd-grid even">
        {isPastoral && (
          <section className="cd-card" aria-labelledby="cd-care">
            <h2 className="cd-h" id="cd-care">Who to check on</h2>
            <p className="cd-hint">Regular members who have not been seen for a few weeks.</p>
            {care && care.members.length > 0 ? (
              <div>
                {care.members.slice(0, 5).map(m => (
                  <div className="cd-person" key={m.id}>
                    <div><b>{m.full_name}</b><span>Last seen {m.weeks_absent} weeks ago</span></div>
                    {m.phone && <a className="cd-call" href={`tel:${m.phone}`}>Call</a>}
                  </div>
                ))}
                {care.total > 5 && <p className="cd-method">{care.total - 5} more. Open Members to see everyone.</p>}
                <p className="cd-method">{care.method}</p>
              </div>
            ) : (
              <p className="cd-empty">Nobody has gone quiet. Names appear here once regular members miss four weeks in a row.</p>
            )}
          </section>
        )}

        {seesMoney && words && (
          <section className="cd-card" aria-labelledby="cd-words">
            <h2 className="cd-h" id="cd-words">This month in words</h2>
            <p className="cd-hint">Written from your own records. Nothing is estimated.</p>
            <ul className="cd-words">{words.map((line, i) => <li key={i}>{line}</li>)}</ul>
          </section>
        )}
      </div>
    </div>
  );
}
