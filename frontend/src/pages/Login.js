/* eslint-disable no-unused-vars, react-hooks/exhaustive-deps */
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export default function Login() {
  const [form, setForm] = useState({ username: '', password: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showPwd, setShowPwd] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(form.username, form.password);
      navigate('/');
    } catch (err) {
      setError(err.response?.data?.error || 'Login failed. Check credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, var(--navy) 0%, #1a2e48 60%, #0a1520 100%)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '1rem',
      position: 'relative',
      overflow: 'hidden'
    }}>
      {/* Decorative circles */}
      {[...Array(3)].map((_, i) => (
        <div key={i} style={{
          position: 'absolute',
          borderRadius: '50%',
          border: `1px solid rgba(201,168,76,${0.08 - i * 0.02})`,
          width: `${300 + i * 200}px`,
          height: `${300 + i * 200}px`,
          top: '50%', left: '50%',
          transform: 'translate(-50%, -50%)',
          pointerEvents: 'none'
        }} />
      ))}

      <div style={{
        background: 'rgba(255,255,255,0.97)',
        borderRadius: 'var(--radius-lg)',
        boxShadow: '0 24px 80px rgba(0,0,0,0.4)',
        padding: '2.5rem 2rem',
        width: '100%',
        maxWidth: 420,
        position: 'relative',
        animation: 'slideUp 0.3s ease',
      }}>
        {/* Logo area */}
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <div style={{
            width: 64, height: 64, borderRadius: '50%',
            background: 'var(--navy)', margin: '0 auto 1rem',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '1.5rem'
          }}>
            ✝
          </div>
          <h1 style={{
            fontFamily: 'var(--font-display)',
            color: 'var(--navy)',
            fontSize: '1.5rem',
            fontWeight: 700,
            marginBottom: '0.25rem'
          }}>
            ChurchOS
          </h1>
          <p style={{ color: 'var(--gray-600)', fontSize: '0.82rem' }}>
            Church Management Platform
          </p>
          <div style={{
            width: 40, height: 2, background: 'var(--gold)',
            margin: '0.75rem auto 0', borderRadius: 2
          }} />
        </div>

        {error && (
          <div className="alert alert-error" style={{ marginBottom: '1.25rem' }}>
            <span>⚠</span>
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Username or Email</label>
            <input
              className="form-control"
              type="text"
              value={form.username}
              onChange={e => setForm({ ...form, username: e.target.value })}
              placeholder="Enter username or email"
              autoFocus
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">Password</label>
            <div style={{ position: 'relative' }}>
              <input
                className="form-control"
                type={showPwd ? 'text' : 'password'}
                value={form.password}
                onChange={e => setForm({ ...form, password: e.target.value })}
                placeholder="Enter password"
                required
                style={{ paddingRight: '3rem' }}
              />
              <button
                type="button"
                onClick={() => setShowPwd(!showPwd)}
                style={{
                  position: 'absolute', right: '0.75rem', top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none', border: 'none', cursor: 'pointer',
                  color: 'var(--gray-400)', fontSize: '0.9rem'
                }}
              >
                {showPwd ? '🙈' : '👁'}
              </button>
            </div>
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            disabled={loading}
            style={{
              width: '100%',
              justifyContent: 'center',
              padding: '0.85rem',
              fontSize: '0.95rem',
              fontWeight: 600,
              marginTop: '0.5rem',
              background: loading ? 'var(--gray-400)' : 'var(--navy)'
            }}
          >
            {loading ? <><span className="loader" style={{ width: 16, height: 16 }} /> Signing in...</> : 'Sign In'}
          </button>
        </form>

        <p style={{
          textAlign: 'center',
          color: 'var(--gray-400)',
          fontSize: '0.75rem',
          marginTop: '1.5rem'
        }}>
          Authorized personnel only · ChurchOS
        </p>
      </div>
    </div>
  );
}
