import React, { useEffect, useState } from 'react';
import { Outlet, NavLink, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { churchesAPI } from '../api';
import './layout.css';

const ICONS = {
  grid: 'M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z',
  people: 'M9 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7zM2.5 20c0-3.6 2.9-6 6.5-6s6.5 2.4 6.5 6M17 11a2.5 2.5 0 1 0 0-5M18 14.2c2.2.6 3.5 2.4 3.5 5.8',
  check: 'M4 12.5l5 5L20 6.5',
  coins: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 7v10M9.2 9.6c.6-.9 1.6-1.3 2.8-1.3 1.7 0 2.8.8 2.8 2s-1.1 1.7-2.8 2-2.8.8-2.8 2 1.1 2 2.8 2c1.2 0 2.2-.4 2.8-1.3',
  phone: 'M8 3h8a1.5 1.5 0 0 1 1.5 1.5v15A1.5 1.5 0 0 1 16 21H8a1.5 1.5 0 0 1-1.5-1.5v-15A1.5 1.5 0 0 1 8 3zM11 18h2',
  calendar: 'M4 6.5A2.5 2.5 0 0 1 6.5 4h11A2.5 2.5 0 0 1 20 6.5v11a2.5 2.5 0 0 1-2.5 2.5h-11A2.5 2.5 0 0 1 4 17.5zM4 10h16M8.5 2.8v3M15.5 2.8v3',
  church: 'M12 3v4M10 5h4M6 21V11l6-4 6 4v10M3 21h18M10 21v-5h4v5',
  key: 'M14.5 9.5a4 4 0 1 1-1.2 2.8L4 21v-3l2-2v-2h2l1.5-1.5',
  user: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4.5 21c0-4 3.4-6.5 7.5-6.5s7.5 2.5 7.5 6.5',
  menu: 'M4 7h16M4 12h16M4 17h16',
  close: 'M6 6l12 12M18 6L6 18',
};

function Icon({ name }) {
  return (
    <svg className="ly-ico" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={ICONS[name]} />
    </svg>
  );
}

const NAV = [
  { path: '/', label: 'Dashboard', icon: 'grid', exact: true },
  { path: '/members', label: 'Members', icon: 'people' },
  { path: '/attendance', label: 'Attendance', icon: 'check' },
  { path: '/finance', label: 'Finance', icon: 'coins', requiredRole: 'treasurer' },
  { path: '/payments', label: 'Payments', icon: 'phone', only: ['admin', 'treasurer'] },
  { path: '/events', label: 'Events', icon: 'calendar' },
  { path: '/churches', label: 'Churches', icon: 'church', requiredRole: 'admin' },
  { path: '/users', label: 'Users', icon: 'key', requiredRole: 'admin' },
];
const HIERARCHY = { admin: 5, pastor: 4, treasurer: 3, secretary: 2, viewer: 1 };

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const [churchName, setChurchName] = useState('');
  const [online, setOnline] = useState(typeof navigator === 'undefined' ? true : navigator.onLine);

  useEffect(() => {
    churchesAPI.getAll()
      .then(r => setChurchName(r.data.churches?.[0]?.name || ''))
      .catch(() => {});
  }, []);

  useEffect(() => { setOpen(false); }, [location.pathname]);

  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener('online', on);
    window.addEventListener('offline', off);
    return () => { window.removeEventListener('online', on); window.removeEventListener('offline', off); };
  }, []);

  const allowed = item => {
    if (item.only) return item.only.includes(user?.role);
    return !item.requiredRole || (HIERARCHY[user?.role] || 0) >= (HIERARCHY[item.requiredRole] || 0);
  };
  const initial = (user?.full_name || user?.username || 'U')[0].toUpperCase();
  const roleLabel = user?.is_platform_owner ? 'Platform owner' : user?.role;

  return (
    <div className="ly">
      <aside className={`ly-side${open ? ' open' : ''}`} aria-label="Main menu">
        <div className="ly-brand">
          <span className="ly-mark" aria-hidden="true">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#0C1445" strokeWidth="3" strokeLinecap="round"><path d="M12 3v18M5 10h14" /></svg>
          </span>
          <span className="ly-name">ChurchOS</span>
        </div>
        <div className="ly-church">
          <span className="ly-eyebrow">Church</span>
          <span className="ly-church-name">{churchName || 'Your church'}</span>
        </div>
        <nav className="ly-nav">
          {NAV.filter(allowed).map(item => (
            <NavLink key={item.path} to={item.path} end={item.exact}
                     className={({ isActive }) => `ly-link${isActive ? ' active' : ''}`}>
              <Icon name={item.icon} />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="ly-foot">
          <NavLink to="/profile" className="ly-me">
            <span className="ly-avatar">{initial}</span>
            <span className="ly-me-text">
              <span className="ly-me-name">{user?.full_name || user?.username}</span>
              <span className="ly-me-role">{roleLabel}</span>
            </span>
          </NavLink>
          <button type="button" className="ly-out" onClick={() => { logout(); navigate('/login'); }}>
            Sign out
          </button>
        </div>
      </aside>

      {open && <button type="button" className="ly-scrim" aria-label="Close menu" onClick={() => setOpen(false)} />}

      <div className="ly-main">
        <header className="ly-top">
          <button type="button" className="ly-burger" aria-label={open ? 'Close menu' : 'Open menu'}
                  onClick={() => setOpen(!open)}>
            <Icon name={open ? 'close' : 'menu'} />
          </button>
          <span className="ly-top-brand">ChurchOS</span>
          <span className="ly-top-right">
            <span className={`ly-status${online ? '' : ' off'}`}>
              <i aria-hidden="true" />{online ? 'Online' : 'Offline'}
            </span>
            <span className="ly-date">
              {new Date().toLocaleDateString('en-KE', { weekday: 'short', day: 'numeric', month: 'short' })}
            </span>
          </span>
        </header>
        <main className="ly-content"><Outlet /></main>
      </div>
    </div>
  );
}
