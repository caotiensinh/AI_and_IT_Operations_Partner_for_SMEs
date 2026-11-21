import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

type Tenant = {id: string; name: string};
type Asset = {id: string; site_id: string; name: string};
type Status = 'loading'|'ready'|'error';

async function api<T>(path: string): Promise<T> {
  const response = await fetch(path, {credentials: 'include', headers: {'Accept':'application/json'}});
  if (!response.ok) throw new Error(response.status === 401 ? 'Login required' : 'Request denied or unavailable');
  return response.json() as Promise<T>;
}

function Workspace() {
  const [tenants,setTenants]=useState<Tenant[]>([]);
  const [tenant,setTenant]=useState('');
  const [assets,setAssets]=useState<Asset[]>([]);
  const [status,setStatus]=useState<Status>('loading');
  const [error,setError]=useState('');
  const [view,setView]=useState<'overview'|'assets'>('overview');

  useEffect(() => {
    let active=true;
    api<{tenants:Tenant[]}>('/v1/me/tenants')
      .then(data=>{if(!active)return; setTenants(data.tenants); setTenant(data.tenants[0]?.id??''); if(!data.tenants.length)setStatus('error');})
      .catch(e=>{if(active){setStatus('error');setError(String(e));}});
    return ()=>{active=false;};
  },[]);
  useEffect(()=>{
    if(!tenant)return;
    let active=true;
    setStatus('loading');setError('');setAssets([]);
    api<{tenant_id:string;assets:Asset[]}>(`/v1/tenants/${encodeURIComponent(tenant)}/assets`)
      .then(data=>{if(active){setAssets(data.assets);setStatus('ready');}})
      .catch(e=>{if(active){setError(String(e));setStatus('error');}});
    return ()=>{active=false;};
  },[tenant]);

  return <div className="shell">
    <aside className="sidebar">
      <div className="logo"><span className="logoMark">S</span><span>SME Operations</span></div>
      <p className="navHint">WORKSPACE</p>
      <nav aria-label="Main navigation">
        <button className={view==='overview'?'active':''} onClick={()=>setView('overview')}>Overview</button>
        <button className={view==='assets'?'active':''} onClick={()=>setView('assets')}>Assets</button>
      </nav>
      <p className="sideFooter">Office AI · IT Operations · Vision AI · IoT</p>
    </aside>
    <div className="content">
      <header className="topbar">
        <div><small>OPERATIONS CONTROL</small><h1>{view==='overview'?'Overview':'Assets'}</h1></div>
        <label className="tenantPicker">Company
          <select aria-label="Select company" value={tenant} onChange={e=>setTenant(e.target.value)} disabled={!tenants.length}>
            {tenants.map(t=><option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </label>
      </header>
      <main id="main">
        {status==='loading'&&<section className="panel" role="status">Loading authorized workspace…</section>}
        {status==='error'&&<section className="panel error" role="alert"><h2>Unable to load workspace</h2><p>{error||'No company access is assigned.'}</p><a href="/auth/start">Sign in</a></section>}
        {status==='ready'&&<>
          <div className="intro"><h2>{view==='overview'?'Your operations at a glance':'Company assets'}</h2><p>Only resources authorized for the selected company are shown.</p></div>
          {view==='overview'&&<div className="metrics">
            <section className="panel metric"><span>Visible assets</span><strong>{assets.length}</strong><small>Scoped to your access</small></section>
            <section className="panel metric"><span>Enabled integrations</span><strong>—</strong><small>Not yet connected</small></section>
            <section className="panel metric"><span>Active incidents</span><strong>—</strong><small>No incident service attached</small></section>
          </div>}
          <section className="panel">
            <div className="panelTitle"><h3>Accessible assets</h3><span>{assets.length} items</span></div>
            {assets.length===0?<p className="empty">No assets are assigned to your current scope.</p>:
              <div className="tableWrap"><table><thead><tr><th>Asset name</th><th>Site ID</th><th>Asset ID</th></tr></thead>
                <tbody>{assets.map(a=><tr key={a.id}><td>{a.name}</td><td className="muted">{a.site_id}</td><td className="muted">{a.id}</td></tr>)}</tbody></table></div>}
          </section>
        </>}
      </main>
    </div>
    <nav className="mobileNav" aria-label="Mobile navigation">
      <button className={view==='overview'?'active':''} onClick={()=>setView('overview')}>Overview</button>
      <button className={view==='assets'?'active':''} onClick={()=>setView('assets')}>Assets</button>
    </nav>
  </div>;
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><Workspace/></React.StrictMode>);
