import React, { useState } from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const NAV = [
  { path: '/', label: 'Dashboard', icon: '⬛', exact: true },
  { path: '/members', label: 'Members', icon: '👥' },
  { path: '/attendance', label: 'Attendance', icon: '✅' },
  { path: '/finance', label: 'Finance', icon: '💰', requiredRole: 'treasurer' },
  { path: '/events', label: 'Events', icon: '📅' },
  { path: '/users', label: 'Users', icon: '🔐', requiredRole: 'admin' },
];

const ROLE_HIERARCHY = { admin: 5, pastor: 4, treasurer: 3, secretary: 2, viewer: 1 };

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const canAccess = (requiredRole) => {
    if (!requiredRole) return true;
    return (ROLE_HIERARCHY[user?.role] || 0) >= (ROLE_HIERARCHY[requiredRole] || 0);
  };

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--gray-100)' }}>
      {/* Sidebar */}
      <aside style={{
        width: 240,
        background: 'var(--navy)',
        display: 'flex',
        flexDirection: 'column',
        position: 'fixed',
        top: 0, bottom: 0, left: 0,
        zIndex: 200,
        transform: sidebarOpen ? 'translateX(0)' : 'translateX(-100%)',
        transition: 'transform 0.25s ease',
        ...(window.innerWidth >= 900 ? { transform: 'translateX(0)' } : {})
      }}>
        {/* Brand */}
        <div style={{
          padding: '1.5rem 1.25rem 1rem',
          borderBottom: '1px solid rgba(255,255,255,0.08)'
        }}>
          <div style={{
            fontFamily: 'var(--font-display)',
            color: 'var(--gold)',
            fontSize: '1.2rem',
            fontWeight: 700,
            lineHeight: 1.2,
          }}>
            ChurchOS
          </div>
          <div style={{ color: 'rgba(255,255,255,0.45)', fontSize: '0.72rem', marginTop: 4 }}>
            Church Management V2
          </div>
        </div>

        {/* Nav */}
        <nav style={{ flex: 1, padding: '1rem 0.75rem', overflowY: 'auto' }}>
          {NAV.filter(item => canAccess(item.requiredRole)).map(item => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.exact}
              onClick={() => setSidebarOpen(false)}
              style={({ isActive }) => ({
                display: 'flex',
                alignItems: 'center',
                gap: '0.75rem',
                padding: '0.7rem 0.9rem',
                marginBottom: '0.2rem',
                borderRadius: 'var(--radius)',
                color: isActive ? 'var(--navy)' : 'rgba(255,255,255,0.65)',
                background: isActive ? 'var(--gold)' : 'transparent',
                textDecoration: 'none',
                fontSize: '0.9rem',
                fontWeight: isActive ? 600 : 400,
                transition: 'all 0.15s ease',
              })}
            >
              <span style={{ fontSize: '1rem' }}>{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>

        {/* User */}
        <div style={{
          padding: '1rem 1.25rem',
          borderTop: '1px solid rgba(255,255,255,0.08)'
        }}>
          <NavLink to="/profile" style={{ textDecoration: 'none' }}>
            <div style={{
              display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.75rem'
            }}>
              <div style={{
                width: 36, height: 36, borderRadius: '50%',
                background: 'var(--gold)', display: 'flex',
                alignItems: 'center', justifyContent: 'center',
                fontWeight: 700, color: 'var(--navy)', fontSize: '0.9rem'
              }}>
                {(user?.username || 'U')[0].toUpperCase()}
              </div>
              <div>
                <div style={{ color: 'var(--white)', fontSize: '0.85rem', fontWeight: 500 }}>
                  {user?.full_name || user?.username}
                </div>
                <div style={{
                  color: 'var(--gold)',
                  fontSize: '0.72rem',
                  textTransform: 'capitalize',
                  opacity: 0.8
                }}>
                  {user?.role}
                </div>
              </div>
            </div>
          </NavLink>
          <button
            onClick={handleLogout}
            style={{
              width: '100%', padding: '0.55rem', borderRadius: 'var(--radius)',
              background: 'rgba(220,53,69,0.15)', border: 'none',
              color: '#ff8a8a', cursor: 'pointer', fontSize: '0.85rem', fontWeight: 500,
              transition: 'var(--transition)'
            }}
            onMouseEnter={e => e.target.style.background = 'rgba(220,53,69,0.3)'}
            onMouseLeave={e => e.target.style.background = 'rgba(220,53,69,0.15)'}
          >
            Sign Out
          </button>
        </div>
      </aside>

      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          onClick={() => setSidebarOpen(false)}
          style={{
            position: 'fixed', inset: 0,
            background: 'rgba(0,0,0,0.5)',
            zIndex: 199,
            display: window.innerWidth >= 900 ? 'none' : 'block'
          }}
        />
      )}

      {/* Main content */}
      <div style={{
        flex: 1,
        marginLeft: window.innerWidth >= 900 ? 240 : 0,
        display: 'flex', flexDirection: 'column',
        minHeight: '100vh'
      }}>
        {/* Topbar */}
        <header style={{
          background: 'var(--white)',
          borderBottom: '1px solid var(--gray-200)',
          padding: '0.85rem 1.5rem',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          position: 'sticky', top: 0, zIndex: 100,
          boxShadow: '0 1px 6px rgba(0,0,0,0.06)'
        }}>
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              fontSize: '1.2rem', padding: '0.25rem',
              color: 'var(--navy)', display: window.innerWidth >= 900 ? 'none' : 'block'
            }}
          >
            ☰
          </button>
          <div style={{
            fontFamily: 'var(--font-display)',
            color: 'var(--navy)',
            fontSize: '1rem',
            display: window.innerWidth < 900 ? 'block' : 'none'
          }}>
            ChurchOS
          </div>
          <div style={{
            fontSize: '0.8rem', color: 'var(--gray-600)',
            display: 'flex', alignItems: 'center', gap: '0.5rem'
          }}>
            <span style={{
              width: 8, height: 8, borderRadius: '50%',
              background: 'var(--success)', display: 'inline-block'
            }} />
            {new Date().toLocaleDateString('en-KE', { weekday: 'short', year: 'numeric', month: 'short', day: 'numeric' })}
          </div>
        </header>

        {/* Page content */}
        <main style={{ flex: 1, padding: '1.5rem', maxWidth: 1280, width: '100%', margin: '0 auto' }}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
