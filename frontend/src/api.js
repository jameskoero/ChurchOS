import axios from 'axios';
const BASE_URL = process.env.REACT_APP_API_URL || '/api';
const api = axios.create({baseURL:BASE_URL,timeout:15000,headers:{'Content-Type':'application/json'}});
api.interceptors.request.use(config => {
  const t = localStorage.getItem('access_token');
  if (t) config.headers.Authorization = `Bearer ${t}`;
  return config;
});
api.interceptors.response.use(res => res, async error => {
  const orig = error.config;
  if (error.response?.status===401 && !orig._retry && orig.url!=='/auth/login') {
    orig._retry = true;
    const rt = localStorage.getItem('refresh_token');
    if (rt) {
      try {
        const res = await axios.post(`${BASE_URL}/auth/refresh`,{},{headers:zAuthorization:`Bearer ${rt}`}});
        const nt = res.data.access_token;
        localStorage.setItem('access_token', nt);
        orig.headers.Authorization = `Bearer ${nt}`;
        return api(orig);
      } catch { localStorage.clear(); window.location.href='/login'; }
    } else { localStorage.clear(); window.location.href='/login'; }
  }
  return Promise.reject(error);
});
export const authAPI = {login:c => api.post('/auth/login',c),me:() => api.get('/auth/me'),changePassword:d => api.post('/auth/change-password',d)};
export const membersAPI = {getAll:p => api.get('/members/',{params:p}),getOne:id => api.get(`/members/${id}`),create:d => api.post('/members/',d),update:(id,d) => api.put(`/members/${id}`,d),delete:id => api.delete(`/members/${id}`),getSummary:() => api.get('/members/stats/summary'),getCellGroups:() => api.get('/members/cell-groups')};
export const attendanceAPI = {getAll:p => api.get('/attendance/',{params:p}),create:d => api.post('/attendance/',d),delete:id => api.delete(`/attendance/${id}`),getServiceTypes:() => api.get('/attendance/service-types'),getSummary:() => api.get('/attendance/stats/summary')};
export const financeAPI = {getAll:p => api.get('/finance/',{params:p}),create:d => api.post('/finance/',d),update:(id,d) => api.put(`/finance/${id}`,d),delete:id => api.delete(`/finance/${id}`),getSummary:p => api.get('/finance/summary',{params:p}),getTransactionTypes:() => api.get('/finance/transaction-types'),getCategories:() => api.get('/finance/categories')};
export const eventsAPI = {getAll:p => api.get('/events/',{params:p}),getUpcoming:() => api.get('/events/upcoming'),getOne:id => api.get(`/events/${id}`),create:d => api.post('/events/',d),update:(id,d) => api.put(`/events/${id}`,d),delete:id => api.delete(`/events/${id}`)};
export const usersAPI = {getAll:() => api.get('/users/'),create:d => api.post('/users/',d),update:(id,d) => api.put(`/users/${id}`,d),delete:id => api.delete(`/users/${id}`),getRoles:() => api.get('/users/roles')};
export const dashboardAPI = {getStats:() => api.get('/dashboard/stats')};
export const churchesAPI = {getAll:() => api.get('/churches/'),getOne:id => api.get(`/churches/${id}`),create:d => api.post('/churches/',d),update:(id,d) => api.put(`/churches/${id}`,d),delete:id => api.delete(`/churches/${id}`),getConstants:() => api.get('/churches/constants')};
export default api;
