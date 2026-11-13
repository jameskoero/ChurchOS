import axios from 'axios';

const BASE_URL = process.env.REACT_APP_API_URL
  || 'https://churchos-yitr.onrender.com';

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' }
});

api.interceptors.request.use(config => {
  const t = localStorage.getItem('access_token');
  if (t) config.headers.Authorization = `Bearer ${t}`;
  return config;
});

function endSession() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem('user');
  if (window.location.pathname !== '/login') window.location.href = '/login';
}

// One refresh at a time. The server rotates refresh tokens, so two
// refresh calls in parallel would end the session.
let refreshing = null;

function refreshTokens() {
  if (!refreshing) {
    const used = localStorage.getItem('refresh_token');
    if (!used) return Promise.reject(new Error('no refresh token'));
    refreshing = axios.post(
      `${BASE_URL}/api/auth/refresh`, {},
      { headers: { Authorization: `Bearer ${used}` }, timeout: 15000 }
    ).then(res => {
      localStorage.setItem('access_token', res.data.access_token);
      if (res.data.refresh_token) {
        localStorage.setItem('refresh_token', res.data.refresh_token);
      }
      return res.data.access_token;
    }).catch(err => {
      // Another tab may already have rotated the token.
      const current = localStorage.getItem('refresh_token');
      const access = localStorage.getItem('access_token');
      if (current && current !== used && access) return access;
      throw err;
    }).finally(() => { refreshing = null; });
  }
  return refreshing;
}

api.interceptors.response.use(
  res => res,
  async error => {
    const orig = error.config || {};
    const url = orig.url || '';
    const isAuthCall = url.includes('/api/auth/login')
      || url.includes('/api/auth/refresh');
    if (error.response?.status === 401 && !orig._retry && !isAuthCall) {
      orig._retry = true;
      try {
        const token = await refreshTokens();
        orig.headers.Authorization = `Bearer ${token}`;
        return api(orig);
      } catch {
        endSession();
      }
    }
    return Promise.reject(error);
  }
);

export const authAPI = {
  login:          d  => api.post('/api/auth/login', d),
  // Tokens are read now, before the caller clears them.
  logout:         () => {
    const access = localStorage.getItem('access_token');
    const refresh = localStorage.getItem('refresh_token');
    if (!access) return Promise.resolve();
    return axios.post(
      `${BASE_URL}/api/auth/logout`, { refresh_token: refresh },
      { headers: { Authorization: `Bearer ${access}` }, timeout: 8000 }
    ).catch(() => {});
  },
  me:             () => api.get('/api/auth/me'),
  changePassword: d  => api.post('/api/auth/change-password', d).then(res => {
    if (res.data && res.data.access_token) {
      localStorage.setItem('access_token', res.data.access_token);
      localStorage.setItem('refresh_token', res.data.refresh_token);
    }
    return res;
  }),
};

export const membersAPI = {
  getAll:      p       => api.get('/api/members/', { params: p }),
  getOne:      id      => api.get(`/api/members/${id}`),
  create:      d       => api.post('/api/members/', d),
  update:      (id, d) => api.put(`/api/members/${id}`, d),
  delete:      id      => api.delete(`/api/members/${id}`),
  getSummary:  ()      => api.get('/api/members/stats/summary'),
};

export const attendanceAPI = {
  getAll:          p  => api.get('/api/attendance/', { params: p }),
  create:          d  => api.post('/api/attendance/', d),
  delete:          id => api.delete(`/api/attendance/${id}`),
  getServiceTypes: () => api.get('/api/attendance/service-types'),
  getSummary:      () => api.get('/api/attendance/stats/summary'),
};

export const financeAPI = {
  getAll:              p       => api.get('/api/finance/', { params: p }),
  create:              d       => api.post('/api/finance/', d),
  update:              (id, d) => api.put(`/api/finance/${id}`, d),
  delete:              id      => api.delete(`/api/finance/${id}`),
  verify:              id      => api.post(`/api/finance/${id}/verify`),
  getSummary:          p       => api.get('/api/finance/summary', { params: p }),
  getTransactionTypes: ()      => api.get('/api/finance/transaction-types'),
  getCategories:       ()      => api.get('/api/finance/categories'),
};

export const eventsAPI = {
  getAll:    p       => api.get('/api/events/', { params: p }),
  getOne:    id      => api.get(`/api/events/${id}`),
  create:    d       => api.post('/api/events/', d),
  update:    (id, d) => api.put(`/api/events/${id}`, d),
  delete:    id      => api.delete(`/api/events/${id}`),
  getUpcoming: ()   => api.get('/api/events/upcoming'),
};

export const usersAPI = {
  getAll:  ()      => api.get('/api/users/'),
  create:  d       => api.post('/api/users/', d),
  update:  (id, d) => api.put(`/api/users/${id}`, d),
  delete:  id      => api.delete(`/api/users/${id}`),
  getRoles: ()     => api.get('/api/users/roles'),
};

export const dashboardAPI = {
  getStats: () => api.get('/api/dashboard/stats'),
};

export const churchesAPI = {
  getAll:     ()       => api.get('/api/churches/'),
  getOne:     id       => api.get(`/api/churches/${id}`),
  create:     d        => api.post('/api/churches/', d),
  update:     (id, d)  => api.put(`/api/churches/${id}`, d),
  delete:     id       => api.delete(`/api/churches/${id}`),
  constants:  ()       => api.get('/api/churches/constants'),
  firstAdmin: (id, d)  => api.post(`/api/churches/${id}/first-admin`, d),
};

export default api;

export const paymentsAPI = {
  stk:        d       => api.post('/api/payments/mpesa/stk', d),
  setup:      ()      => api.get('/api/payments/setup'),
  testSetup:  ()      => api.post('/api/payments/setup/test'),
  getRequest: id      => api.get(`/api/payments/requests/${id}`),
  inbox:      p       => api.get('/api/payments/inbox', { params: p }),
  match:      (id, d) => api.post(`/api/payments/inbox/${id}/match`, d),
  ignore:     (id, d) => api.post(`/api/payments/inbox/${id}/ignore`, d),
};
export const insightsAPI = {
  care:     p => api.get('/api/insights/care', { params: p }),
  giving:   () => api.get('/api/insights/giving'),
  forecast: () => api.get('/api/insights/forecast'),
  summary:  () => api.get('/api/insights/summary'),
};

export const healthAPI = {
  check: () => api.get('/api/health', { timeout: 60000 }),
};

export const accountsAPI = {
  list:            ()      => api.get('/api/accounts/'),
  create:          d       => api.post('/api/accounts/', d),
  remove:          id      => api.delete(`/api/accounts/${id}`),
  importStatement: d       => api.post('/api/accounts/import-statement', d, { timeout: 120000 }),
};

export const reportsAPI = {
  giving: p        => api.get('/api/reports/giving', { params: p }),
  member: (id, p)  => api.get(`/api/reports/member/${id}`, { params: p }),
};

export const billingAPI = {
  status:        ()      => api.get('/api/billing/status'),
  plans:         ()      => api.get('/api/billing/plans'),
  churches:      ()      => api.get('/api/billing/churches'),
  invoices:      p       => api.get('/api/billing/invoices', { params: p }),
  createInvoice: d       => api.post('/api/billing/invoices', d),
  markPaid:      (id, d) => api.post(`/api/billing/invoices/${id}/paid`, d),
  voidInvoice:   id      => api.post(`/api/billing/invoices/${id}/void`),
  revenue:       ()      => api.get('/api/billing/revenue'),
  payTo:         ()      => api.get('/api/billing/pay-to'),
  claim:         (id, d) => api.post(`/api/billing/invoices/${id}/claim`, d),
  settings:      ()      => api.get('/api/billing/settings'),
  saveSettings:  d       => api.put('/api/billing/settings', d),
  importStatement: d     => api.post('/api/billing/import-statement', d, { timeout: 120000 }),
};

export const checkinAPI = {
  roster: p => api.get('/api/checkin/roster', { params: p }),
  sync:   d => api.post('/api/checkin/sync', d, { timeout: 120000 }),
};

export const smsAPI = {
  setup:    ()  => api.get('/api/sms/setup'),
  audience: p   => api.get('/api/sms/audience', { params: p }),
  consent:  d   => api.post('/api/sms/consent', d),
  preview:  d   => api.post('/api/sms/preview', d),
  send:     d   => api.post('/api/sms/send', d, { timeout: 120000 }),
  history:  ()  => api.get('/api/sms/history'),
};

export const governanceAPI = {
  denominations:       p        => api.get('/api/governance/denominations', { params: p }),
  requestDenomination: d        => api.post('/api/governance/denominations/request', d),
  pending:             ()       => api.get('/api/governance/denominations/pending'),
  review:              (id, d)  => api.put(`/api/governance/denominations/${id}`, d),
  church:              ()       => api.get('/api/governance/church'),
  choose:              d        => api.put('/api/governance/church', d),
  leave:               ()       => api.post('/api/governance/church/leave'),
  createRegion:        d        => api.post('/api/governance/regions', d),
  myRegion:            ()       => api.get('/api/governance/regions/mine'),
  invite:              d        => api.post('/api/governance/regions/mine/invites', d),
  answer:              (id, a)  => api.post(`/api/governance/invites/${id}/${a}`),
  removeChurch:        id       => api.post(`/api/governance/regions/mine/churches/${id}/remove`),
  regionMembers:       (id, p)  => api.get(`/api/governance/regions/mine/churches/${id}/members`, { params: p }),
};
