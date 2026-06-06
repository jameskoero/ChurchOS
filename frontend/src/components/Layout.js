import React, { useState, useEffect } from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { churchesAPI } from '../api';
const NAV = [
  {path:'/',label:'Dashboard',icon:'\u2b1b',exact:true},
  {path:'/members',label:'Members',icon:'\ud83d\udc65'},
  {path:'/attendance',label:'Attendance',icon:'\u2705'},
  {path:'/finance',label:'Finance',icon:'\ud83d\udcb0',requiredRole:'treasurer'},
  {path:'/events',label:'Events',icon:'\ud83d\udcc5'},
  {path:'/churches',label:'Churches',icon:'\u26ea',requiredRole:'admin'},
  {path:'/users',label:'Users',icon:'\ud83d\udd10',requiredRole:'admin'},
];
const H={admin:5,pastor:4,treasurer:3,secretary:2,viewer:1};
export default function Layout() {
  const {user,logout}=useAuth();
  const navigate=useNavigate();
  const [sidebarOpen,setSidebarOpen]=useState(false);
  const [churchName,setChurchName]=useState('Church Management Platform');
  useEffect(()=>{
    churchesAPI.getAll().then(r=>{if(r.data.churches?.[0])setChurchName(r.data.churches[0].name);}).catch(()=>{});
  },[]);
  const canAccess=role=>!role||(H[user?.role]||0)>=(H[role]||0);
  return (
    <div style={{display:'flex',minHeight:'100vh',background:'var(--gray-100)'}}>
      <aside style={{width:240,background:'var(--navy)',display:'flex',flexDirection:'column',
        position:'fixed',top:0,bottom:0,left:0,zIndex:200,
        transform:sidebarOpen?'translateX(0)':'translateX(-100%)',
        transition:'transform 0.25s ease',
        ...(window.innerWidth>=900?{transform:'translateX(0)'}:{})}}>
        <div style={{padding:'1.5rem 1.25rem 1rem',borderBottom:'1px solid rgba(255,255,255,0.08)'}}>
          <div style={{fontFamily:'var(--font-display)',color:'var(--gold)',fontSize:'1.2rem',fontWeight:700}}>ChurchOS</div>
          <div style={{color:'rgba(255,255,255,0.55)',fontSize:'0.72rem',marginTop:4}}>{churchName}</div>
        </div>
        <nav style={{flex:1,padding:'1rem 0.75rem',overflowY:'auto'}}>
          {NAV.filter(i=>canAccess(i.requiredRole)).map(item=>(
            <NavLink key={item.path} to={item.path} end={item.exact} onClick={()=>setSidebarOpen(false)}
              style={({isActive})=>({display:'flex',alignItems:'center',gap:'0.75rem',
                padding:'0.7rem 0.9rem',marginBottom:'0.2rem',borderRadius:'var(--radius)',
                textDecoration:'none',fontSize:'0.9rem',
                color:isActive?'var(--navy)':'rgba(255,255,255,0.65)',
                background:isActive?'var(--gold)':'transparent',
                fontWeight:isActive?600:400,transition:'all 0.15s ease'})}>
              <span style={{fontSize:'1rem'}}>{item.icon}</span>{item.label}
            </NavLink>
          ))}
        </nav>
        <div style={{padding:'1rem 1.25rem',borderTop:'1px solid rgba(255,255,255,0.08)'}}>
          <NavLink to='/profile' style={{textDecoration:'none'}}>
            <div style={{display:'flex',alignItems:'center',gap:'0.75rem',marginBottom:'0.75rem'}}>
              <div style={{width:36,height:36,borderRadius:'50%',background:'var(--gold)',
                display:'flex',alignItems:'center',justifyContent:'center',
                fontWeight:700,color:'var(--navy)',fontSize:'0.9rem'}}>
                {(user?.username||'U')[0].toUpperCase()}
              </div>
              <div>
                <div style={{color:'var(--white)',fontSize:'0.85rem',fontWeight:500}}>{user?.full_name||user?.username}</div>
                <div style={{color:'var(--gold)',fontSize:'0.72rem',textTransform:'capitalize',opacity:0.8}}>{user?.role}</div>
              </div>
            </div>
          </NavLink>
          <button onClick={()=>{logout();navigate('/login');}}
            style={{width:'100%',padding:'0.55rem',borderRadius:'var(--radius)',
              background:'rgba(220,53,69,0.15)',border:'none',color:'#ff8a8a',
              cursor:'pointer',fontSize:'0.85rem',fontWeight:500}}
            onMouseEnter={e=>e.target.style.background='rgba(220,53,69,0.3)'}
            onMouseLeave={e=>e.target.style.background='rgba(220,53,69,0.15)'}>Sign Out</button>
        </div>
      </aside>
      {sidebarOpen&&(<div onClick={()=>setSidebarOpen(false)}
        style={{position:'fixed',inset:0,background:'rgba(0,0,0,0.5)',zIndex:199,
          display:window.innerWidth>=900?'none':'block'}}/>)}
      <div style={{flex:1,marginLeft:window.innerWidth>=900?240:0,display:'flex',flexDirection:'column',minHeight:'100vh'}}>
        <header style={{background:'var(--white)',borderBottom:'1px solid var(--gray-200)',
          padding:'0.85rem 1.5rem',display:'flex',alignItems:'center',justifyContent:'space-between',
          position:'sticky',top:0,zIndex:100,boxShadow:'0 1px 6px rgba(0,0,0,0.06)'}}>
          <button onClick={()=>setSidebarOpen(!sidebarOpen)}
            style={{background:'none',border:'none',cursor:'pointer',fontSize:'1.2rem',
              color:'var(--navy)',display:window.innerWidth>=900?'none':'block'}}>&#9776;</button>
          <div style={{fontFamily:'var(--font-display)',color:'var(--navy)',
            display:window.innerWidth<900?'block':'none'}}>ChurchOS</div>
          <div style={{fontSize:'0.8rem',color:'var(--gray-600)',display:'flex',alignItems:'center',gap:'0.5rem'}}>
            <span style={{width:8,height:8,borderRadius:'50%',background:'var(--success)',display:'inline-block'}}/>
            {new Date().toLocaleDateString('en-KE',{weekday:'short',year:'numeric',month:'short',day:'numeric'})}
          </div>
        </header>
        <main style={{flex:1,padding:'1.5rem',maxWidth:1280,width:'100%',margin:'0 auto'}}><Outlet/></main>
      </div>
    </div>
  );
}
