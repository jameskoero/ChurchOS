import axios from 'axios';

const BASE_URL = process.env.REACT_APP_API_URL
  || 'https://churchos-yitr.onrender.com';

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' }
});

api.interceptors.request.use(config => {
  const t = localStorage.getItem('access_token');
  if (t) config.headers.Authorization = `Bearer ${t}`;
  return config;
});

api.interceptors.response.use(
  res => res,
  async error => {
    const orig = error.config;
    if (error.response?.status === 401 && !orig._retry
        && orig.url !== '/auth/login') {
      orig._retry = true;
      const rt = localStorage.getItem('refresh_token');
      if (rt) {
        try {
          const res = await axios.post(
            `${BASE_URL}/api/auth/refresh`, {},
            { headers: { Authorization: `Bearer ${rt}` } }
          );
          const nt = res.data.access_token;
          localStorage.setItem('access_token', nt);
          orig.headers.Authorization = `Bearer ${nt}`;
          return api(orig);
        } catch {
          localStorage.clear();
          window.location.href = '/login';
        }
      } else {
        localStorage.clear();
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export const authAPI = {
  login:          d  => api.post('/api/auth/login', d),
  refresh:        () => api.post('/api/auth/refresh'),
  logout:         () => api.post('/api/auth/logout'),
  me:             () => api.get('/api/auth/me'),
  changePassword: d  => api.post('/api/auth/change-password', d),
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
};

export default api;
