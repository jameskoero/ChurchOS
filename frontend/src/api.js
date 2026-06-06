import axios from 'axios';

const API = process.env.REACT_APP_API_URL || 'http://localhost:5000';

const api = axios.create({ baseURL: API });

api.interceptors.request.use(config => {
  const token = localStorage.getItem('access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  res => res,
  async err => {
    const original = err.config;
    if (err.response?.status === 401 && !original._retry) {
      original._retry = true;
      try {
        const refresh = localStorage.getItem('refresh_token');
        const res = await axios.post(`${API}/api/auth/refresh`, {},
          { headers: { Authorization: `Bearer ${refresh}` } });
        localStorage.setItem('access_token', res.data.access_token);
        original.headers.Authorization = `Bearer ${res.data.access_token}`;
        return api(original);
      } catch {
        localStorage.clear();
        window.location.href = '/login';
      }
    }
    return Promise.reject(err);
  }
);

export const authAPI = {
  login:   data => api.post('/api/auth/login',   data),
  refresh: ()   => api.post('/api/auth/refresh'),
  logout:  ()   => api.post('/api/auth/logout'),
};

export const membersAPI = {
  getAll:  (params) => api.get('/api/members',    { params }),
  getOne:  (id)     => api.get(`/api/members/${id}`),
  create:  (data)   => api.post('/api/members',   data),
  update:  (id, data) => api.put(`/api/members/${id}`, data),
  remove:  (id)     => api.delete(`/api/members/${id}`),
};

export const attendanceAPI = {
  getAll:  (params) => api.get('/api/attendance', { params }),
  create:  (data)   => api.post('/api/attendance', data),
};

export const financeAPI = {
  getAll:  (params) => api.get('/api/finance',    { params }),
  create:  (data)   => api.post('/api/finance',   data),
  stkPush: (data)   => api.post('/api/finance/mpesa/stk', data),
};

export const eventsAPI = {
  getAll:  (params) => api.get('/api/events',     { params }),
  create:  (data)   => api.post('/api/events',    data),
  update:  (id, data) => api.put(`/api/events/${id}`, data),
  remove:  (id)     => api.delete(`/api/events/${id}`),
};

export const usersAPI = {
  getAll:  ()       => api.get('/api/users'),
  create:  (data)   => api.post('/api/users',     data),
  update:  (id, data) => api.put(`/api/users/${id}`, data),
  remove:  (id)     => api.delete(`/api/users/${id}`),
};

export const dashboardAPI = {
  get: () => api.get('/api/dashboard'),
};

export const churchesAPI = {
  getAll:     ()        => api.get('/api/churches/'),
  getOne:     (id)      => api.get(`/api/churches/${id}`),
  create:     (data)    => api.post('/api/churches/', data),
  update:     (id, data) => api.put(`/api/churches/${id}`, data),
  remove:     (id)      => api.delete(`/api/churches/${id}`),
  constants:  ()        => api.get('/api/churches/constants'),
};

export default api;
