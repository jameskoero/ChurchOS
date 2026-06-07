/* eslint-disable no-unused-vars, react-hooks/exhaustive-deps */
import React, { useState, useEffect, useCallback } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts';
import { financeAPI, membersAPI } from '../api';
import { useAuth } from '../contexts/AuthContext';

const TODAY = new Date().toISOString().split('T')[0];
const PAYMENT_METHODS = ['cash', 'mpesa', 'bank', 'cheque'];
const PIE_COLORS = ['#C9A84C','#0D1B2A','#28A745','#17A2B8','#DC3545','#6C757D','#E2C270','#152234'];

const EMPTY_FORM = {
  transaction_type: 'offering', category: '', amount: '',
  description: '', member_id: '', payment_method: 'cash',
  mpesa_ref: '', transaction_date: TODAY, notes: '', verified: false
};

function typeBadge(type) {
  const map = {
    tithe: 'badge-gold', offering: 'badge-success', donation: 'badge-info',
    expense: 'badge-danger', project_fund: 'badge-navy', other: 'badge-warning'
  };
  return <span className={`badge ${map[type] || 'badge-info'}`}>{type}</span>;
}

const fmt = (n) => 'KES ' + new Intl.NumberFormat('en-KE').format(Math.round(n || 0));

export default function Finance() {
  // eslint-disable-next-line no-unused-vars
  const { can, user: _u } = useAuth();
  const [transactions, setTransactions] = useState([]);
  // eslint-disable-next-line no-unused-vars
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState(null);
  const [txTypes, setTxTypes] = useState([]);
  const [categories, setCategories] = useState([]);
  const [members, setMembers] = useState([]);

  // Filters
  const [filterType, setFilterType] = useState('');
  const [filterDateFrom, setFilterDateFrom] = useState('');
  const [filterDateTo, setFilterDateTo] = useState('');
  const [search, setSearch] = useState('');

  // Modal
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [activeTab, setActiveTab] = useState('transactions'); // transactions | charts

  const currentYear = new Date().getFullYear();

  const fetchTransactions = useCallback(() => {
    setLoading(true);
    financeAPI.getAll({ page, per_page: 25, type: filterType, date_from: filterDateFrom, date_to: filterDateTo, search })
      .then(r => { setTransactions(r.data.transactions); setTotal(r.data.total); setPages(r.data.pages); })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [page, filterType, filterDateFrom, filterDateTo, search]);

  const fetchSummary = useCallback(() => {
    financeAPI.getSummary({ year: currentYear }).then(r => setSummary(r.data)).catch(() => {});
  }, [currentYear]);

  useEffect(() => { fetchTransactions(); }, [fetchTransactions]);
  useEffect(() => { setPage(1); }, [filterType, filterDateFrom, filterDateTo, search]);
  useEffect(() => {
    fetchSummary();
    financeAPI.getTransactionTypes().then(r => setTxTypes(r.data));
    financeAPI.getCategories().then(r => setCategories(r.data));
    membersAPI.getAll({ per_page: 300, status: 'active' }).then(r => setMembers(r.data.members));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const openCreate = () => {
    setEditing(null); setForm(EMPTY_FORM); setError(''); setShowModal(true);
  };
  const openEdit = (tx) => {
    setEditing(tx);
    setForm({
      transaction_type: tx.transaction_type, category: tx.category || '',
      amount: tx.amount, description: tx.description || '',
      member_id: tx.member_id || '', payment_method: tx.payment_method || 'cash',
      mpesa_ref: tx.mpesa_ref || '', transaction_date: tx.transaction_date,
      notes: tx.notes || '', verified: tx.verified
    });
    setError(''); setShowModal(true);
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true); setError('');
    try {
      const payload = { ...form, amount: parseFloat(form.amount), member_id: form.member_id || null };
      if (editing) await financeAPI.update(editing.id, payload);
      else await financeAPI.create(payload);
      setShowModal(false);
      fetchTransactions();
      fetchSummary();
    } catch (err) {
      setError(err.response?.data?.error || 'Save failed');
    } finally { setSaving(false); }
  };

  const handleDelete = async (id) => {
    try { await financeAPI.delete(id); setDeleteConfirm(null); fetchTransactions(); fetchSummary(); }
    catch (err) { alert(err.response?.data?.error || 'Delete failed'); }
  };

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  // Chart data
  const MONTH_NAMES = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const monthlyMap = {};
  (summary?.monthly_breakdown || []).forEach(d => {
    const key = MONTH_NAMES[d.month - 1];
    if (!monthlyMap[key]) monthlyMap[key] = { month: key, Income: 0, Expenses: 0 };
    if (d.transaction_type === 'expense') monthlyMap[key].Expenses += d.total;
    else monthlyMap[key].Income += d.total;
  });
  const monthlyData = Object.values(monthlyMap);
  const pieData = (summary?.by_category || []).filter(c => c.total > 0).slice(0, 8);

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <h1 style={{ fontFamily: 'var(--font-display)', fontSize: '1.5rem', color: 'var(--navy)' }}>Finance</h1>
          <p style={{ color: 'var(--gray-600)', fontSize: '0.85rem' }}>KES · {currentYear}</p>
        </div>
        {can('manage_finance') && (
          <button className="btn btn-gold" onClick={openCreate}>+ New Transaction</button>
        )}
      </div>

      {/* Summary Cards */}
      {summary && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem', marginBottom: '1.25rem' }}>
          {[
            { label: 'Annual Income', value: fmt(summary.total_income), color: '#28a745', icon: '📈' },
            { label: 'Annual Expenses', value: fmt(summary.total_expense), color: '#dc3545', icon: '📉' },
            { label: 'Net Balance', value: fmt(summary.net), color: summary.net >= 0 ? '#28a745' : '#dc3545', icon: '💳' },
          ].map(c => (
            <div key={c.label} className="card" style={{ borderTop: `3px solid ${c.color}` }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--gray-600)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.4rem', fontWeight: 600 }}>{c.label}</div>
              <div style={{ fontSize: '1.35rem', fontWeight: 700, color: 'var(--navy)', fontFamily: 'var(--font-display)' }}>{c.value}</div>
            </div>
          ))}
        </div>
      )}

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
        {['transactions', 'charts'].map(tab => (
          <button key={tab} onClick={() => setActiveTab(tab)}
            className={`btn ${activeTab === tab ? 'btn-primary' : 'btn-outline'} btn-sm`}
            style={{ textTransform: 'capitalize' }}>
            {tab === 'charts' ? '📊 Charts' : '📋 Transactions'}
          </button>
        ))}
      </div>

      {activeTab === 'charts' ? (
        <div style={{ display: 'grid', gridTemplateColumns: '3fr 2fr', gap: '1rem' }}>
          <div className="card">
            <h3 style={{ fontFamily: 'var(--font-display)', fontSize: '1rem', marginBottom: '1.25rem' }}>Monthly Breakdown ({currentYear})</h3>
            {monthlyData.length > 0 ? (
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={monthlyData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="month" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} tickFormatter={v => `${(v/1000).toFixed(0)}K`} />
                  <Tooltip formatter={v => fmt(v)} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Bar dataKey="Income" fill="var(--gold)" radius={[4,4,0,0]} />
                  <Bar dataKey="Expenses" fill="var(--danger)" radius={[4,4,0,0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : <div style={{ height: 260, display:'flex', alignItems:'center', justifyContent:'center', color:'var(--gray-400)' }}>No data yet</div>}
          </div>
          <div className="card">
            <h3 style={{ fontFamily: 'var(--font-display)', fontSize: '1rem', marginBottom: '1.25rem' }}>By Category</h3>
            {pieData.length > 0 ? (
              <ResponsiveContainer width="100%" height={260}>
                <PieChart>
                  <Pie data={pieData} dataKey="total" nameKey="category" cx="50%" cy="50%" outerRadius={80} label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`} labelLine={false} fontSize={9}>
                    {pieData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                  </Pie>
                  <Tooltip formatter={v => fmt(v)} />
                </PieChart>
              </ResponsiveContainer>
            ) : <div style={{ height: 260, display:'flex', alignItems:'center', justifyContent:'center', color:'var(--gray-400)' }}>No data yet</div>}
          </div>
        </div>
      ) : (
        <>
          {/* Filters */}
          <div className="card" style={{ marginBottom: '1rem', padding: '1rem' }}>
            <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
              <input className="form-control" placeholder="Search ref, desc, M-Pesa..." value={search}
                onChange={e => setSearch(e.target.value)} style={{ maxWidth: 220 }} />
              <select className="form-control" value={filterType} onChange={e => setFilterType(e.target.value)} style={{ maxWidth: 160 }}>
                <option value="">All Types</option>
                {txTypes.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
              <input className="form-control" type="date" value={filterDateFrom} onChange={e => setFilterDateFrom(e.target.value)} style={{ maxWidth: 160 }} />
              <input className="form-control" type="date" value={filterDateTo} onChange={e => setFilterDateTo(e.target.value)} style={{ maxWidth: 160 }} />
              {(filterType || filterDateFrom || filterDateTo || search) && (
                <button className="btn btn-outline btn-sm" onClick={() => { setFilterType(''); setFilterDateFrom(''); setFilterDateTo(''); setSearch(''); }}>Clear</button>
              )}
            </div>
          </div>

          {/* Table */}
          <div className="card" style={{ padding: 0 }}>
            <div className="table-wrapper">
              {loading ? (
                <div style={{ padding: '3rem', textAlign: 'center' }}>
                  <div className="loader" style={{ width: 32, height: 32, borderWidth: 3, margin: '0 auto' }} />
                </div>
              ) : transactions.length === 0 ? (
                <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--gray-400)' }}>No transactions found</div>
              ) : (
                <table>
                  <thead>
                    <tr>
                      <th>Ref</th>
                      <th>Date</th>
                      <th>Type</th>
                      <th>Category</th>
                      <th>Amount (KES)</th>
                      <th>Member</th>
                      <th>Method</th>
                      <th>Verified</th>
                      {can('manage_finance') && <th>Actions</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {transactions.map(tx => (
                      <tr key={tx.id}>
                        <td><span style={{ fontFamily: 'monospace', fontSize: '0.78rem', color: 'var(--gold)', fontWeight: 600 }}>{tx.reference}</span></td>
                        <td style={{ fontSize: '0.85rem' }}>{tx.transaction_date}</td>
                        <td>{typeBadge(tx.transaction_type)}</td>
                        <td style={{ fontSize: '0.85rem', color: 'var(--gray-600)' }}>{tx.category || '—'}</td>
                        <td style={{ fontWeight: 700, color: tx.transaction_type === 'expense' ? 'var(--danger)' : 'var(--success)' }}>
                          {tx.transaction_type === 'expense' ? '−' : '+'}{new Intl.NumberFormat('en-KE').format(tx.amount)}
                        </td>
                        <td style={{ fontSize: '0.85rem' }}>{tx.member_name || '—'}</td>
                        <td><span className="badge badge-info" style={{ fontSize: '0.7rem' }}>{tx.payment_method}</span></td>
                        <td>{tx.verified ? <span style={{ color: 'var(--success)' }}>✓</span> : <span style={{ color: 'var(--gray-400)' }}>—</span>}</td>
                        {can('manage_finance') && (
                          <td>
                            <div style={{ display: 'flex', gap: '0.4rem' }}>
                              <button className="btn btn-outline btn-sm" onClick={() => openEdit(tx)}>Edit</button>
                              {can('delete') && <button className="btn btn-danger btn-sm" onClick={() => setDeleteConfirm(tx)}>Del</button>}
                            </div>
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
            {pages > 1 && (
              <div className="pagination" style={{ borderTop: '1px solid var(--gray-200)' }}>
                <button className="page-btn" disabled={page === 1} onClick={() => setPage(p => p - 1)}>‹</button>
                {[...Array(Math.min(pages, 7))].map((_, i) => (
                  <button key={i} className={`page-btn ${page === i + 1 ? 'active' : ''}`} onClick={() => setPage(i + 1)}>{i + 1}</button>
                ))}
                <button className="page-btn" disabled={page === pages} onClick={() => setPage(p => p + 1)}>›</button>
              </div>
            )}
          </div>
        </>
      )}

      {/* Modal */}
      {showModal && (
        <div className="modal-overlay">
          <div className="modal">
            <div className="modal-header">
              <span className="modal-title">{editing ? 'Edit Transaction' : 'New Transaction'}</span>
              <button onClick={() => setShowModal(false)} style={{ background: 'none', border: 'none', fontSize: '1.2rem', cursor: 'pointer', color: 'var(--gray-400)' }}>✕</button>
            </div>
            <form onSubmit={handleSave}>
              <div className="modal-body">
                {error && <div className="alert alert-error"><span>⚠</span><span>{error}</span></div>}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                  <div className="form-group">
                    <label className="form-label">Type *</label>
                    <select className="form-control" value={form.transaction_type} onChange={e => set('transaction_type', e.target.value)} required>
                      {txTypes.map(t => <option key={t} value={t}>{t}</option>)}
                    </select>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Category</label>
                    <select className="form-control" value={form.category} onChange={e => set('category', e.target.value)}>
                      <option value="">Select category</option>
                      {categories.map(c => <option key={c} value={c}>{c}</option>)}
                    </select>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Amount (KES) *</label>
                    <input className="form-control" type="number" step="0.01" min="0.01" value={form.amount}
                      onChange={e => set('amount', e.target.value)} required />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Transaction Date *</label>
                    <input className="form-control" type="date" value={form.transaction_date}
                      onChange={e => set('transaction_date', e.target.value)} required />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Payment Method</label>
                    <select className="form-control" value={form.payment_method} onChange={e => set('payment_method', e.target.value)}>
                      {PAYMENT_METHODS.map(m => <option key={m} value={m}>{m}</option>)}
                    </select>
                  </div>
                  <div className="form-group">
                    <label className="form-label">M-Pesa Ref</label>
                    <input className="form-control" value={form.mpesa_ref} onChange={e => set('mpesa_ref', e.target.value)}
                      placeholder="e.g. QHX4K8LM3N" />
                  </div>
                  <div className="form-group" style={{ gridColumn: '1/-1' }}>
                    <label className="form-label">Member (optional)</label>
                    <select className="form-control" value={form.member_id} onChange={e => set('member_id', e.target.value)}>
                      <option value="">Anonymous / General</option>
                      {members.map(m => <option key={m.id} value={m.id}>{m.full_name} · {m.member_id}</option>)}
                    </select>
                  </div>
                  <div className="form-group" style={{ gridColumn: '1/-1' }}>
                    <label className="form-label">Description</label>
                    <input className="form-control" value={form.description} onChange={e => set('description', e.target.value)} />
                  </div>
                  <div className="form-group" style={{ gridColumn: '1/-1' }}>
                    <label className="form-label">Notes</label>
                    <textarea className="form-control" value={form.notes} onChange={e => set('notes', e.target.value)} rows={2} />
                  </div>
                  <div className="form-group">
                    <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                      <input type="checkbox" checked={form.verified} onChange={e => set('verified', e.target.checked)} />
                      <span style={{ fontSize: '0.875rem', fontWeight: 500 }}>Mark as verified</span>
                    </label>
                  </div>
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-outline" onClick={() => setShowModal(false)}>Cancel</button>
                <button type="submit" className="btn btn-gold" disabled={saving}>
                  {saving ? <><span className="loader" style={{ width: 14, height: 14 }} /> Saving...</> : (editing ? 'Update' : 'Record Transaction')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {deleteConfirm && (
        <div className="modal-overlay">
          <div className="modal" style={{ maxWidth: 380 }}>
            <div className="modal-header"><span className="modal-title">Delete Transaction?</span></div>
            <div className="modal-body">
              <p>Delete <strong>{deleteConfirm.reference}</strong> ({fmt(deleteConfirm.amount)})?</p>
              <p style={{ color: 'var(--danger)', fontSize: '0.85rem', marginTop: '0.5rem' }}>This cannot be undone.</p>
            </div>
            <div className="modal-footer">
              <button className="btn btn-outline" onClick={() => setDeleteConfirm(null)}>Cancel</button>
              <button className="btn btn-danger" onClick={() => handleDelete(deleteConfirm.id)}>Delete</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
