import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './contexts/AuthContext';
import Layout from './components/Layout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Members from './pages/Members';
import Attendance from './pages/Attendance';
import Finance from './pages/Finance';
import Events from './pages/Events';
import Churches from './pages/Churches';
import Users from './pages/Users';
import Profile from './pages/Profile';
function ProtectedRoute({children,requiredRole}) {
  const {user,loading} = useAuth();
  if (loading) return <div style={{display:'flex',alignItems:'center',
    justifyContent:'center',height:'100vh',background:'#0D1B2A'}}>
    <div className='loader' style={{width:40,height:40,borderWidth:3}}/></div>;
  if (!user) return <Navigate to='/login' replace/>;
  if (requiredRole) {
    const h={admin:5,pastor:4,treasurer:3,secretary:2,viewer:1};
    if ((h[user.role]||0)<(h[requiredRole]||0))
      return <Navigate to='/' replace/>;
  }
  return children;
}
export default function App() {
  const {user} = useAuth();
  return (
    <BrowserRouter>
      <Routes>
        <Route path='/login'
          element={user?<Navigate to='/' replace/>:<Login/>}/>
        <Route path='/'
          element={<ProtectedRoute><Layout/></ProtectedRoute>}>
          <Route index element={<Dashboard/>}/>
          <Route path='members' element={<Members/>}/>
          <Route path='attendance' element={<Attendance/>}/>
          <Route path='finance' element={
            <ProtectedRoute requiredRole='treasurer'>
              <Finance/>
            </ProtectedRoute>}/>
          <Route path='events' element={<Events/>}/>
          <Route path='churches' element={
            <ProtectedRoute requiredRole='admin'>
              <Churches/>
            </ProtectedRoute>}/>
          <Route path='users' element={
            <ProtectedRoute requiredRole='admin'>
              <Users/>
            </ProtectedRoute>}/>
          <Route path='profile' element={<Profile/>}/>
        </Route>
        <Route path='*' element={<Navigate to='/' replace/>}/>
      </Routes>
    </BrowserRouter>
  );
}
