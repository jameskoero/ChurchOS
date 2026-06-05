import React, { useState, useEffect, useCallback } from 'react';
import { churchesAPI } from '../api';
import { KENYAN_COUNTIES, DENOMINATIONS, CHURCH_SIZES, PLAN_LABELS } from '../constants';
const EMPTY = {name:'',county:'',sub_county:'',denomination:'',
               size:'',paybill:'',till_number:'',phone:'',
               email:'',address:'',member_prefix:'CHR'};
function planBadge(plan) {
  const colors={trial:'#6c757d',seed:'#28a745',growth:'#007bff',parish:'#fd7e14',cathedral:'#6f42c1'};
  const info=PLAN_LABELS[plan]||{};
  return <span style={{background:colors[plan]||'#6c757d',color:'#fff',
    padding:'2px 8px',borderRadius:12,fontSize:'0.75rem',fontWeight:600,
    textTransform:'capitalize'}}>{info.label||plan}</span>;
}
export default function Churches() {
  const [churches,setChurches]=useState([]);
  const [loading,setLoading]=useState(true);
  const [showModal,setShowModal]=useState(false);
  const [editing,setEditing]=useState(null);
  const [form,setForm]=useState(EMPTY);
  const [saving,setSaving]=useState(false);
  const [error,setError]=useState('');
  const load=useCallback(()=>{
    setLoading(true);
    churchesAPI.getAll().then(r=>setChurches(r.data.churches)).catch(console.error).finally(()=>setLoading(false));
  },[]);
  useEffect(()=>{load();},[load]);
  const openCreate=()=>{setEditing(null);setForm(EMPTY);setError('');setShowModal(true);};
  const openEdit=c=>{setEditing(c);setForm({name:c.name||'',county:c.county||'',
    sub_county:c.sub_county||'',denomination:c.denomination||'',size:c.size||'',
    paybill:c.paybill||'',till_number:c.till_number||'',phone:c.phone||'',
    email:c.email||'',address:c.address||'',member_prefix:c.member_prefix||'CHR'});
    setError('');setShowModal(true);};
  const handleSave=async e=>{e.preventDefault();setSaving(true);setError('');
    try{if(editing)await churchesAPI.update(editing.id,form);
      else await churchesAPI.create(form);setShowModal(false);load();}
    catch(err){setError(err.response?.data?.error||'Save failed');}
    finally{setSaving(false);}}
  const set=(k,v)=>setForm(f=>({...f,[k]:v}));
  return (
    <div>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'1.5rem'}}>
        <div>
          <h1 style={{fontFamily:'var(--font-display)',fontSize:'1.5rem',color:'var(--navy)'}}>Churches</h1>
          <p style={{color:'var(--gray-600)',fontSize:'0.85rem'}}>{churches.length} registered</p>
        </div>
        <button className='btn btn-gold' onClick={openCreate}>+ Register Church</button>
      </div>
      <div className='card' style={{padding:0}}>
        {loading?(<div style={{padding:'3rem',textAlign:'center'}}><div className='loader' style={{width:32,height:32,margin:'0 auto'}}/></div>):(
        <table><thead><tr><th>Name</th><th>County</th><th>Denomination</th><th>Members</th><th>Plan</th><th>Actions</th></tr></thead>
        <tbody>{churches.map(c=>(<tr key={c.id}>
          <td style={{fontWeight:600,color:'var(--navy)'}}>{c.name}</td>
          <td>{c.county||'—'}</td>
          <td style={{fontSize:'0.82rem'}}>{c.denomination||'—'}</td>
          <td>{c.member_count}</td><td>{planBadge(c.subscription_plan)}</td>
          <td><button className='btn btn-outline btn-sm' onClick={()=>openEdit(c)}>Edit</button></td>
        </tr>))}</tbody></table>)}
      </div>
      {showModal&&(
        <div className='modal-overlay'><div className='modal' style={{maxWidth:600}}>
          <div className='modal-header'>
            <span className='modal-title'>{editing?`Edit: ${editing.name}`:'Register New Church'}</span>
            <button onClick={()=>setShowModal(false)} style={{background:'none',border:'none',fontSize:'1.2rem',cursor:'pointer'}}>x</button>
          </div>
          <form onSubmit={handleSave}><div className='modal-body'>
            {error&&<div className='alert alert-error'><span>{error}</span></div>}
            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'0.75rem'}}>
              <div className='form-group' style={{gridColumn:'1/-1'}}>
                <label className='form-label'>Church Name *</label>
                <input className='form-control' value={form.name} required onChange={e=>set('name',e.target.value)}/>
              </div>
              <div className='form-group'><label className='form-label'>County</label>
                <select className='form-control' value={form.county} onChange={e=>set('county',e.target.value)}>
                  <option value=''>Select county</option>
                  {KENYAN_COUNTIES.map(c=><option key={c}>{c}</option>)}
                </select></div>
              <div className='form-group'><label className='form-label'>Sub-County</label>
                <input className='form-control' value={form.sub_county} placeholder='e.g. Kisumu Central' onChange={e=>set('sub_county',e.target.value)}/></div>
              <div className='form-group'><label className='form-label'>Denomination</label>
                <select className='form-control' value={form.denomination} onChange={e=>set('denomination',e.target.value)}>
                  <option value=''>Select denomination</option>
                  {DENOMINATIONS.map(d=><option key={d}>{d}</option>)}
                </select></div>
              <div className='form-group'><label className='form-label'>Church Size</label>
                <select className='form-control' value={form.size} onChange={e=>set('size',e.target.value)}>
                  <option value=''>Select size</option>
                  {CHURCH_SIZES.map(s=><option key={s}>{s}</option>)}
                </select></div>
              <div className='form-group'><label className='form-label'>M-Pesa Paybill</label>
                <input className='form-control' value={form.paybill} placeholder='e.g. 247247' onChange={e=>set('paybill',e.target.value)}/></div>
              <div className='form-group'><label className='form-label'>M-Pesa Till</label>
                <input className='form-control' value={form.till_number} placeholder='e.g. 5678901' onChange={e=>set('till_number',e.target.value)}/></div>
              <div className='form-group'><label className='form-label'>Phone</label>
                <input className='form-control' value={form.phone} onChange={e=>set('phone',e.target.value)}/></div>
              <div className='form-group'><label className='form-label'>Email</label>
                <input className='form-control' type='email' value={form.email} onChange={e=>set('email',e.target.value)}/></div>
              <div className='form-group'><label className='form-label'>Member ID Prefix</label>
                <input className='form-control' value={form.member_prefix} onChange={e=>set('member_prefix',e.target.value.toUpperCase().slice(0,6))}/></div>
              <div className='form-group' style={{gridColumn:'1/-1'}}><label className='form-label'>Address</label>
                <textarea className='form-control' rows={2} value={form.address} onChange={e=>set('address',e.target.value)}/></div>
            </div></div>
            <div className='modal-footer'>
              <button type='button' className='btn btn-outline' onClick={()=>setShowModal(false)}>Cancel</button>
              <button type='submit' className='btn btn-gold' disabled={saving}>{saving?'Saving...':(editing?'Update':'Register Church')}</button>
            </div></form>
        </div></div>)}
    </div>
  );
}
