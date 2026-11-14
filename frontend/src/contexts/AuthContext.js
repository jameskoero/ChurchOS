import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { authAPI } from '../api';
import { clearRoster } from '../lib/offlineStore';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const stored = localStorage.getItem('user');
    const token = localStorage.getItem('access_token');
    if (stored && token) {
      try {
        setUser(JSON.parse(stored));
      } catch {
        localStorage.removeItem('user');
      }
    }
    setLoading(false);
  }, []);

  const finish = useCallback(data => {
    const { access_token, refresh_token, user: userData } = data;
    localStorage.setItem('access_token', access_token);
    localStorage.setItem('refresh_token', refresh_token);
    localStorage.setItem('user', JSON.stringify(userData));
    setUser(userData);
    return userData;
  }, []);

  // When SMS sign-in is on for this person, the server asks for a code instead of signing in.
  const login = useCallback(async (username, password) => {
    const res = await authAPI.login({ username, password });
    if (res.data.needs_code) {
      return { needs_code: true, challenge: res.data.challenge, phone_hint: res.data.phone_hint };
    }
    return finish(res.data);
  }, [finish]);

  const verifyCode = useCallback(async (challenge, code) => {
    const res = await authAPI.verifyCode({ challenge, code });
    return finish(res.data);
  }, [finish]);

  const logout = useCallback(() => {
    authAPI.logout();
    clearRoster();   // the saved member list must not stay on a phone after sign-out
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
    setUser(null);
  }, []);

  const can = useCallback((action) => {
    if (!user) return false;
    const permissions = {
      admin:     ['read', 'write', 'delete', 'manage_users', 'manage_finance', 'reports'],
      pastor:    ['read', 'write', 'reports'],
      secretary: ['read', 'write'],
      treasurer: ['read', 'write', 'manage_finance', 'reports'],
      viewer:    ['read']
    };
    return (permissions[user.role] || []).includes(action);
  }, [user]);

  return (
    <AuthContext.Provider value={{ user, loading, login, verifyCode, logout, can }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
