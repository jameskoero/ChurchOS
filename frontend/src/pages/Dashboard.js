/* eslint-disable no-unused-vars, react-hooks/exhaustive-deps */
import React, { useEffect, useState } from 'react';
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts';
import { dashboardAPI } from '../api';
import { useAuth } from '../contexts/AuthContext';

const MONTH_NAMES = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

function StatCard({ title, value, sub, color = 'var(--navy)', icon }) {
  return (
    <div className="card" style={{ borderTop: `3px solid ${color}` }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <p style={{ fontSize: '0.78rem', color: 'var(--gray-600)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.5rem', fontWeight: 600 }}>
            {title}
          </p>
          <p style={{ fontSize: '1.9rem', fontWeight: 700, color: 'var(--navy)', fontFamily: 'var(--font-display)', lineHeight: 1 }}>
            {value}
          </p>
          {sub && <p style={{ fontSize: '0.78rem', color: 'var(--gray-600)', marginTop: '0.4rem' }}>{sub}</p>}
        </div>
        <div style={{
          width: 44, height: 44, borderRadius: 10,
          background: color + '18', display: 'flex',
          alignItems: 'center', justifyContent: 'center', fontSize: '1.2rem'
        }}>
          {icon}
        </div>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    dashboardAPI.getStats()
      .then(r => setStats(r.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 300 }}>
      <div className="loader" style={{ width: 36, height: 36, borderWidth: 3 }} />
    </div>
  );

  // Prepare attendance chart data
  const attendanceTrend = (stats?.attendance_trend || []).map(d => ({
    date: d.date,
    Attendance: d.count
  }));

  // Prepare finance chart data
  const financeMap = {};
  (stats?.finance_trend || []).forEach(d => {
    const key = `${MONTH_NAMES[d.month - 1]}`;
    if (!financeMap[key]) financeMap[key] = { month: key, Income: 0, Expenses: 0 };
    if (d.type === 'expense') financeMap[key].Expenses += d.total;
    else financeMap[key].Income += d.total;
  });
  const financeChartData = Object.values(financeMap);

  const fmt = (n) => new Intl.NumberFormat('en-KE').format(Math.round(n));

  return (
    <div>
      {/* Header */}
      <div style={{ marginBottom: '1.75rem' }}>
        <h1 style={{
          fontFamily: 'var(--font-display)',
          fontSize: '1.6rem',
          color: 'var(--navy)',
          marginBottom: '0.25rem'
        }}>
          Good {new Date().getHours() < 12 ? 'Morning' : new Date().getHours() < 17 ? 'Afternoon' : 'Evening'},{' '}
          <span style={{ color: 'var(--gold)' }}>{user?.full_name?.split(' ')[0] || user?.username}</span>
        </h1>
        <p style={{ color: 'var(--gray-600)', fontSize: '0.875rem' }}>
          Church Management Platform — Kisumu
        </p>
      </div>

      {/* KPI Cards */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
        gap: '1rem',
        marginBottom: '1.75rem'
      }}>
        <StatCard
          title="Active Members"
          value={stats?.members?.total || 0}
          sub={`+${stats?.members?.new_this_month || 0} this month`}
          color="var(--navy)"
          icon="👥"
        />
        <StatCard
          title="Last Service"
          value={stats?.attendance?.last_service || 0}
          sub={`${stats?.attendance?.this_month || 0} this month`}
          color="var(--gold)"
          icon="✅"
        />
        <StatCard
          title="Monthly Income"
          value={`KES ${fmt(stats?.finance?.monthly_income || 0)}`}
          sub={`Net: KES ${fmt(stats?.finance?.monthly_net || 0)}`}
          color="#28a745"
          icon="💰"
        />
        <StatCard
          title="Upcoming Events"
          value={stats?.upcoming_events?.length || 0}
          sub="Scheduled activities"
          color="#17a2b8"
          icon="📅"
        />
      </div>

      {/* Charts row */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: '1rem',
        marginBottom: '1.75rem'
      }}>
        {/* Attendance chart */}
        <div className="card">
          <h3 style={{ fontFamily: 'var(--font-display)', fontSize: '1rem', marginBottom: '1.25rem', color: 'var(--navy)' }}>
            Sunday Attendance Trend
          </h3>
          {attendanceTrend.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={attendanceTrend}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={d => d.slice(5)} />
                <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
                <Tooltip />
                <Line type="monotone" dataKey="Attendance" stroke="var(--gold)" strokeWidth={2} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ height: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--gray-400)' }}>
              No attendance data yet
            </div>
          )}
        </div>

        {/* Finance chart */}
        <div className="card">
          <h3 style={{ fontFamily: 'var(--font-display)', fontSize: '1rem', marginBottom: '1.25rem', color: 'var(--navy)' }}>
            Income vs Expenses (6 mo.)
          </h3>
          {financeChartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={financeChartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="month" tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip formatter={v => `KES ${fmt(v)}`} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="Income" fill="var(--gold)" radius={[4,4,0,0]} />
                <Bar dataKey="Expenses" fill="var(--danger)" radius={[4,4,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ height: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--gray-400)' }}>
              No finance data yet
            </div>
          )}
        </div>
      </div>

      {/* Gender + Upcoming events */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '1rem' }}>
        {/* Gender breakdown */}
        <div className="card">
          <h3 style={{ fontFamily: 'var(--font-display)', fontSize: '1rem', marginBottom: '1rem', color: 'var(--navy)' }}>
            Gender Split
          </h3>
          {[
            { label: 'Male', count: stats?.members?.male || 0, color: '#4A90D9', icon: '♂' },
            { label: 'Female', count: stats?.members?.female || 0, color: '#E57AA3', icon: '♀' },
          ].map(item => {
            const total = (stats?.members?.male || 0) + (stats?.members?.female || 0);
            const pct = total ? Math.round((item.count / total) * 100) : 0;
            return (
              <div key={item.label} style={{ marginBottom: '0.85rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                  <span style={{ fontSize: '0.875rem' }}>{item.icon} {item.label}</span>
                  <span style={{ fontSize: '0.875rem', fontWeight: 600 }}>{item.count} ({pct}%)</span>
                </div>
                <div style={{ height: 8, background: 'var(--gray-200)', borderRadius: 4, overflow: 'hidden' }}>
                  <div style={{ height: '100%', width: `${pct}%`, background: item.color, borderRadius: 4, transition: 'width 0.6s ease' }} />
                </div>
              </div>
            );
          })}
        </div>

        {/* Upcoming events */}
        <div className="card">
          <h3 style={{ fontFamily: 'var(--font-display)', fontSize: '1rem', marginBottom: '1rem', color: 'var(--navy)' }}>
            Upcoming Events
          </h3>
          {(stats?.upcoming_events || []).length === 0 ? (
            <p style={{ color: 'var(--gray-400)', fontSize: '0.875rem' }}>No upcoming events</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
              {stats.upcoming_events.map(event => (
                <div key={event.id} style={{
                  display: 'flex', alignItems: 'center', gap: '0.75rem',
                  padding: '0.65rem', background: 'var(--gray-100)', borderRadius: 'var(--radius)'
                }}>
                  <div style={{
                    minWidth: 44, height: 44, borderRadius: 8,
                    background: 'var(--navy)', display: 'flex', flexDirection: 'column',
                    alignItems: 'center', justifyContent: 'center',
                    color: 'var(--gold)'
                  }}>
                    <span style={{ fontSize: '0.65rem', fontWeight: 600 }}>
                      {new Date(event.start_date).toLocaleDateString('en', { month: 'short' }).toUpperCase()}
                    </span>
                    <span style={{ fontSize: '1.1rem', fontWeight: 700, lineHeight: 1 }}>
                      {new Date(event.start_date).getDate()}
                    </span>
                  </div>
                  <div>
                    <p style={{ fontWeight: 600, fontSize: '0.875rem' }}>{event.title}</p>
                    <p style={{ fontSize: '0.78rem', color: 'var(--gray-600)' }}>
                      {event.location || event.event_type}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
