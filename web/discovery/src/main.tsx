import React, {useEffect,useMemo,useRef,useState} from "react";
import {createRoot} from "react-dom/client";
import {Case,Requirement,ReviewHistory,Site,Source,DiscoveryClient,validUuid,BROWSER_COOKIE_MODE,discoverBrowserSession,logoutBrowserSession,TenantChoice} from "./api";
import "./style.css";

const UUID_EMPTY="00000000-0000-4000-8000-000000000000";
function App(){
  const [tenant,setTenant]=useState("");
  const [token,setToken]=useState("");
  const [csrfToken,setCsrfToken]=useState("");
  const [tenantChoices,setTenantChoices]=useState<TenantChoice[]>([]);
  const [cookieReady,setCookieReady]=useState(!BROWSER_COOKIE_MODE);
  const [connected,setConnected]=useState(false);
  const [cases,setCases]=useState<Case[]>([]);
  const [caseCursor,setCaseCursor]=useState<string|null>(null);
  const [selected,setSelected]=useState<Case|null>(null);
  const [requirements,setRequirements]=useState<Requirement[]>([]);
  const [reqCursor,setReqCursor]=useState<string|null>(null);
  const [activeReq,setActiveReq]=useState<Requirement|null>(null);
  const [history,setHistory]=useState<ReviewHistory|null>(null);
  const [sources,setSources]=useState<Source[]>([]);
  const [sourceCursor,setSourceCursor]=useState<string|null>(null);
  const [sites,setSites]=useState<Site[]>([]);
  const [siteCursor,setSiteCursor]=useState<string|null>(null);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [notice,setNotice]=useState("");
  const [search,setSearch]=useState("");
  const [showCreate,setShowCreate]=useState(false);
  const [newSite,setNewSite]=useState("");
  const [newLabel,setNewLabel]=useState("");
  const [newCompany,setNewCompany]=useState("OTHER");
  const [sourceLabel,setSourceLabel]=useState("");
  const [sourcePage,setSourcePage]=useState("1");
  const [reqText,setReqText]=useState("");
  const [classification,setClassification]=useState<"explicit"|"inferred"|"unverified">("unverified");
  const [chosenSource,setChosenSource]=useState("");
  const [decision,setDecision]=useState<"confirmed"|"rejected">("rejected");
  const [rationale,setRationale]=useState("");
  const [tab,setTab]=useState<"requirements"|"sources">("requirements");
  const pendingCreate=useRef<{key:string;body:string}|null>(null);
  const pendingSource=useRef<{id:string;body:string}|null>(null);
  const pendingRequirement=useRef<{id:string;body:string}|null>(null);
  const client=useMemo(()=>connected?new DiscoveryClient({tenantId:tenant,...(BROWSER_COOKIE_MODE?{csrfToken}:{token})}):null,[connected,tenant,token,csrfToken]);

  const resetCase=()=>{setSelected(null);setRequirements([]);setReqCursor(null);setActiveReq(null);setHistory(null);setSources([]);setSourceCursor(null);};
  function disconnect(){if(BROWSER_COOKIE_MODE && csrfToken){
      void logoutBrowserSession(csrfToken).catch(()=>setError("ログアウトに失敗しました。"));
    }
    setConnected(false);setToken("");setCsrfToken("");setTenantChoices([]);setCases([]);setSites([]);setSiteCursor(null);setCaseCursor(null);resetCase();setNotice("");setError("");pendingCreate.current=null;pendingSource.current=null;pendingRequirement.current=null;}
  async function run(task:()=>Promise<void>){
    if(busy)return;setBusy(true);setError("");setNotice("");
    try{await task();}catch(e){setError(e instanceof Error?e.message:"処理に失敗しました。");}
    finally{setBusy(false);}
  }
  async function loadCases(api:DiscoveryClient,cursor:string|null=null){
    const page=await api.cases(cursor);
    setCases(previous=>cursor?[...previous,...page.cases]:page.cases);
    setCaseCursor(page.next_cursor);
  }
  async function loadSites(api:DiscoveryClient,cursor:string|null=null){
    const page=await api.sites(cursor);
    setSites(previous=>cursor?[...previous,...page.sites]:page.sites);
    setSiteCursor(page.next_cursor);
  }
  async function loadSources(api:DiscoveryClient,caseId:string,cursor:string|null=null){
    const page=await api.sources(caseId,cursor);
    setSources(previous=>cursor?[...previous,...page.sources]:page.sources);
    setSourceCursor(page.next_cursor);
  }
  async function loadRequirements(api:DiscoveryClient,caseId:string,cursor:string|null=null){
    const page=await api.requirements(caseId,cursor);
    setRequirements(previous=>cursor?[...previous,...page.requirements]:page.requirements);
    setReqCursor(page.next_cursor);
  }
  useEffect(()=>{
    if(!BROWSER_COOKIE_MODE)return;
    let active=true;
    void discoverBrowserSession().then(session=>{
      if(!active)return;
      if(session){setTenantChoices(session.tenants);setCsrfToken(session.csrf_token);}
    }).catch(e=>{if(active)setError(e instanceof Error?e.message:"接続できません。");})
      .finally(()=>{if(active)setCookieReady(true);});
    return ()=>{active=false;};
  },[]);
  function connectCookieTenant(uid:string){
    if(!validUuid(uid)||!csrfToken)return;
    const api=new DiscoveryClient({tenantId:uid,csrfToken});
    void run(async()=>{
      await Promise.all([loadCases(api),loadSites(api)]);
      setTenant(uid);setConnected(true);resetCase();setNotice("接続しました。");
    });
  }
  function connect(){
    if(!validUuid(tenant)||!token.trim()){setError("Tenant UUID とセッショントークンを入力してください。");return;}
    const api=new DiscoveryClient({tenantId:tenant,token});
    void run(async()=>{
      await Promise.all([loadCases(api),loadSites(api)]);
      setConnected(true);
      resetCase();
      setNotice("接続しました。");
    });
  }
  function selectCase(item:Case){
    if(!client)return;
    void run(async()=>{
      await Promise.all([loadRequirements(client,item.id),loadSources(client,item.id)]);
      setSelected(item);setActiveReq(null);setHistory(null);pendingSource.current=null;pendingRequirement.current=null;
      setTab("requirements");
    });
  }
  function selectRequirement(item:Requirement){
    setActiveReq(item);setHistory(null);setRationale("");
    if(!client||!selected)return;
    void run(async()=>{
      try{const result=await client.history(selected.id,item.id);setHistory(result);}
      catch{setHistory(null);setNotice("審査履歴は管理権限がある場合のみ表示されます。");}
    });
  }
  function createCase(){
    if(!client||!validUuid(newSite)||!newLabel.trim()){setError("Site UUID と案件名を確認してください。");return;}
    const body=JSON.stringify({site:newSite,label:newLabel.trim(),company:newCompany});
    if(pendingCreate.current?.body!==body){
      pendingCreate.current={key:crypto.randomUUID().replaceAll("-",""),body};
    }
    const key=pendingCreate.current.key;
    void run(async()=>{
      const created=await client.createCase(newSite,newLabel,newCompany,key);
      await loadCases(client);
      setShowCreate(false);setNewLabel("");pendingCreate.current=null;
      const page=await client.cases();
      const found=page.cases.find(c=>c.id===created.case_id);
      if(found){setSelected(found);
        await Promise.all([loadRequirements(client,found.id),loadSources(client,found.id)]);
      }
      setNotice("調査案件を登録しました。");
    });
  }
  function addSource(){
    if(!client||!selected||!sourceLabel.trim()||Number(sourcePage)<1||!Number.isInteger(Number(sourcePage))){
      setError("資料名と1以上のページ番号を入力してください。");return;
    }
    const body=JSON.stringify({caseId:selected.id,label:sourceLabel.trim(),page:Number(sourcePage)});
    if(pendingSource.current?.body!==body) pendingSource.current={id:crypto.randomUUID(),body};
    const id=pendingSource.current.id;
    void run(async()=>{
      await client.addSource(selected.id,id,sourceLabel,Number(sourcePage));
      await loadSources(client,selected.id);
      pendingSource.current=null;
      setSourceLabel("");setSourcePage("1");setNotice("資料情報を登録しました。原本ファイルはアップロードされません。");
    });
  }
  function addRequirement(){
    if(!client||!selected||!reqText.trim()||(classification==="explicit"&&!validUuid(chosenSource))){
      setError("要件と出典を確認してください。明示的な要件には出典UUIDが必須です。");return;
    }
    const body=JSON.stringify({caseId:selected.id,statement:reqText.trim(),classification,source:chosenSource||null});
    if(pendingRequirement.current?.body!==body) pendingRequirement.current={id:crypto.randomUUID(),body};
    const id=pendingRequirement.current.id;
    void run(async()=>{
      await client.addRequirement(selected.id,id,reqText,classification,chosenSource||null);
      pendingRequirement.current=null;
      await loadRequirements(client,selected.id);
      setReqText("");setClassification("unverified");setChosenSource("");
      setNotice("要件を登録しました。承認はまだ行われていません。");
    });
  }
  function submitReview(){
    if(!client||!selected||!activeReq||!history||rationale.trim().length<8){
      setError("審査権限と8文字以上の理由を確認してください。");return;
    }
    void run(async()=>{
      await client.review(selected.id,activeReq.id,history.review_version,decision,rationale);
      const refreshed=await client.history(selected.id,activeReq.id);
      setHistory(refreshed);
      await loadRequirements(client,selected.id);
      setActiveReq({...activeReq,approval_state:refreshed.approval_state as Requirement["approval_state"]});
      setRationale("");setNotice("審査結果を保存しました。");
    });
  }
  const visible=cases.filter(c=>c.label.toLocaleLowerCase().includes(search.toLocaleLowerCase())
    ||c.company_code.toLowerCase().includes(search.toLowerCase()));
  const statusLabel:Record<string,string>={proposed:"未確認",confirmed:"確認済み",rejected:"却下"};
  const classLabel:Record<string,string>={explicit:"原本に明記",inferred:"推定",unverified:"未検証"};
  useEffect(()=>{if(!connected)return;const onVisibility=()=>{if(document.visibilityState==="hidden")setHistory(null);};
    document.addEventListener("visibilitychange",onVisibility);
    return()=>document.removeEventListener("visibilitychange",onVisibility);},[connected]);

  return <div className="app-shell">
    <header className="topbar">
      <div className="brand"><span className="brand-mark">S</span><span><strong>SME Partner</strong><small>Business Discovery Workspace</small></span></div>
      <span className="environment">研究用 / Pilot</span>
      {connected&&<div className="context"><small>Tenant</small><code>{tenant.slice(0,8)}…</code><button className="quiet" onClick={disconnect}>{BROWSER_COOKIE_MODE?"ログアウト":"接続解除"}</button></div>}
    </header>
    {!connected?<main className="login-layout"><div className="welcome">
      <span className="eyebrow">BUSINESS DISCOVERY</span><h1>事業課題を、根拠から整理する。</h1>
      <p>案件の登録、根拠資料の紐付け、要件の審査までを一つの画面で管理します。</p>
      <div className="info">この画面は研究用です。認可済みの同一オリジンAPIが必要です。顧客情報や本番トークンは投入しないでください。</div>
    </div>{BROWSER_COOKIE_MODE?<section className="login-card">
      <h2>事業所の選択</h2>
      {!cookieReady?<p role="status">セッションを確認しています…</p>:
        tenantChoices.length===0?<><p>ログインしてから利用可能な事業所を選択してください。</p>
          <a className="primary" href="/auth/oidc/start">安全にログインする</a></>:
        <><p>アクセスを許可された事業所を選択してください。</p>
          {tenantChoices.map(choice=><button className="case-button" type="button"
            key={choice.id} onClick={()=>connectCookieTenant(choice.id)}>
            <strong>{choice.label}</strong></button>)}</>}
      {error&&<p className="error" role="alert">{error}</p>}
    </section>:<form className="login-card" onSubmit={e=>{e.preventDefault();connect();}}>
      <h2>ワークスペースに接続</h2><p>Tenant と検証用セッションを指定します。</p>
      <label>Tenant UUID<input required value={tenant} onChange={e=>setTenant(e.target.value)} placeholder={UUID_EMPTY}/></label>
      <label>セッショントークン<input type="password" autoComplete="off" required value={token} onChange={e=>setToken(e.target.value)} placeholder="一時的な Bearer token"/></label>
      <button className="primary" disabled={busy} type="submit">接続する</button>
      <small className="muted">トークンはブラウザ内メモリにのみ保持し、保存しません。</small>
      {error&&<p className="error" role="alert">{error}</p>}
    </form>}</main>:
    <div className="workspace">
      <aside className="sidebar" aria-label="調査案件一覧">
        <div className="sidebar-title"><div><span className="eyebrow">WORKSPACE</span><h2>調査案件</h2></div><button className="primary small" onClick={()=>setShowCreate(v=>!v)}>＋ 新規</button></div>
        <label className="sr-only" htmlFor="case-search">案件を検索</label>
        <input id="case-search" className="search" value={search} onChange={e=>setSearch(e.target.value)} placeholder="案件を検索…"/>
        {showCreate&&<section className="create-card"><h3>新しい調査案件</h3>
          <label>対象拠点<select aria-label="対象拠点" value={newSite} onChange={e=>setNewSite(e.target.value)}>
            <option value="">拠点を選択してください</option>
            {sites.map(site=><option key={site.id} value={site.id}>{site.label}</option>)}
          </select></label>
          {siteCursor&&<button type="button" className="more" disabled={busy} onClick={()=>client&&void run(()=>loadSites(client,siteCursor))}>拠点をさらに読み込む</button>}
          {sites.length===0&&<p className="muted">作成権限のある拠点がありません。</p>}
          <label>案件名<input value={newLabel} onChange={e=>setNewLabel(e.target.value)} maxLength={200} placeholder="例：業務改善調査"/></label>
          <label>業種分類<select value={newCompany} onChange={e=>setNewCompany(e.target.value)}>
            <option value="OTHER">その他</option><option value="B">サロン</option><option value="J">シェアードサービス</option><option value="L">製造</option><option value="R">工業・技術</option>
          </select></label><button className="primary" disabled={busy} onClick={createCase}>登録する</button></section>}
        <div className="case-list">{visible.length===0?<p className="empty">表示できる案件がありません。</p>:
          visible.map(c=><button key={c.id} className={"case-button "+(selected?.id===c.id?"selected":"")} onClick={()=>selectCase(c)}>
            <span className="case-icon">{c.company_code.slice(0,1)}</span><span className="case-meta"><strong>{c.label}</strong><small>{c.company_code} · {c.status}</small></span></button>)}</div>
        {caseCursor&&<button className="more" disabled={busy} onClick={()=>client&&void run(()=>loadCases(client,caseCursor))}>さらに読み込む</button>}
        <div className="sidebar-foot">アクセス権に応じて表示されています。</div>
      </aside>
      <main className="work-content">
        {error&&<p className="error" role="alert">{error}</p>}
        {notice&&<p className="notice" role="status">{notice}</p>}
        {busy&&<p className="loading" role="status">処理しています…</p>}
        {!selected?<div className="blank-state"><span className="blank-icon">≡</span><h2>調査案件を選択</h2><p>左側から案件を開くか、新規登録してください。</p></div>:
        <><div className="page-heading"><div><span className="eyebrow">DISCOVERY / {selected.company_code}</span><h1>{selected.label}</h1>
          <p>根拠を残し、仮説と確定事項を区別します。</p></div><span className="tag">{selected.status}</span></div>
          <div className="stats"><div><small>表示中の要件</small><strong>{requirements.length}</strong></div>
            <div><small>確認済み</small><strong>{requirements.filter(r=>r.approval_state==="confirmed").length}</strong></div>
            <div><small>未確認</small><strong>{requirements.filter(r=>r.approval_state==="proposed").length}</strong></div></div>
          <div className="tabs" role="tablist" aria-label="詳細タブ">
            <button role="tab" aria-selected={tab==="requirements"} className={tab==="requirements"?"active":""} onClick={()=>setTab("requirements")}>要件管理</button>
            <button role="tab" aria-selected={tab==="sources"} className={tab==="sources"?"active":""} onClick={()=>setTab("sources")}>根拠資料を登録</button></div>
          {tab==="requirements"?<div className="main-split"><section className="panel">
            <div className="section-heading"><h2>業務要件</h2><span>{requirements.length} 件</span></div>
            <div className="requirements">{requirements.length===0?<p className="empty">要件はまだ登録されていません。</p>:
              requirements.map(r=><button key={r.id} className={"requirement "+(activeReq?.id===r.id?"active":"")} onClick={()=>selectRequirement(r)}>
                <span className={"evidence "+r.classification}>{classLabel[r.classification]}</span><strong>{r.statement}</strong>
                <span className="req-bottom"><small>{r.source?r.source.document_label+" · p."+r.source.page:"出典なし"}</small><span className={"state "+r.approval_state}>{statusLabel[r.approval_state]}</span></span></button>)}</div>
            {reqCursor&&<button className="more" disabled={busy} onClick={()=>client&&void run(()=>loadRequirements(client,selected.id,reqCursor))}>さらに読み込む</button>}
            <form className="quick-form" onSubmit={e=>{e.preventDefault();addRequirement();}}>
              <h3>＋ 要件を追加</h3>
              <label>課題・期待する成果<textarea value={reqText} onChange={e=>setReqText(e.target.value)} maxLength={4000} placeholder="確認した事実を具体的に記載…" rows={3}/></label>
              <label>根拠レベル<select value={classification} onChange={e=>setClassification(e.target.value as typeof classification)}>
                <option value="unverified">未検証</option><option value="inferred">推定</option><option value="explicit">原本に明記</option></select></label>
              <label>出典資料（明示の場合必須）<select aria-label="出典資料（明示の場合必須）" value={chosenSource} onChange={e=>setChosenSource(e.target.value)}>
                <option value="">出典なし</option>
                {sources.map(source=><option key={source.id} value={source.id}>{source.document_label} · p.{source.page}</option>)}
              </select></label>
              {sourceCursor&&<button type="button" className="more" disabled={busy} onClick={()=>client&&void run(()=>loadSources(client,selected.id,sourceCursor))}>出典をさらに読み込む</button>}
              <button className="primary" type="submit" disabled={busy}>要件を登録</button>
            </form></section>
            <aside className="detail panel">
              {activeReq?<><span className="eyebrow">REQUIREMENT DETAIL</span><h2>要件の確認</h2>
                <p className="detail-statement">{activeReq.statement}</p>
                <dl><dt>根拠分類</dt><dd>{classLabel[activeReq.classification]}</dd>
                  <dt>出典</dt><dd>{activeReq.source?activeReq.source.document_label+" · p."+activeReq.source.page:"未登録"}</dd>
                  <dt>現在の判断</dt><dd>{statusLabel[activeReq.approval_state]}</dd></dl>
                {history?<><h3>審査履歴</h3><p className="muted">バージョン {history.review_version}</p>
                  {history.reviews.length?history.reviews.map(r=><div className="history-item" key={r.version}><strong>{statusLabel[r.next_state]}</strong>
                    <p>{r.rationale}</p><small>担当: {r.reviewer_id.slice(0,8)}… · {new Date(r.reviewed_at).toLocaleString("ja-JP")}</small></div>):
                    <p className="empty">審査履歴はありません。</p>}
                  {history.approval_state==="proposed"&&<form className="review-form" onSubmit={e=>{e.preventDefault();submitReview();}}>
                    <h3>審査結果を登録</h3><label>判断<select value={decision} onChange={e=>setDecision(e.target.value as typeof decision)}>
                      <option value="rejected">却下</option>{activeReq.classification==="explicit"&&activeReq.source&&<option value="confirmed">確認済み</option>}</select></label>
                    <label>理由（8文字以上）<textarea rows={3} minLength={8} maxLength={2000} required value={rationale} onChange={e=>setRationale(e.target.value)}/></label>
                    <button className="primary" disabled={busy} type="submit">審査を保存</button>
                  </form>}</>:
                  <div className="info">審査履歴は管理権限がある場合のみ閲覧できます。</div>}
              </>:<div className="detail-placeholder"><h2>要件詳細</h2><p>中央の要件を選ぶと、根拠と審査履歴がここに表示されます。</p></div>}
            </aside></div>:
            <section className="panel sources-panel"><h2>根拠資料の登録</h2>
              <p>ファイル本体はアップロードしません。出典名、ページ番号、参照UUIDのみ登録します。</p>
              <form className="source-form" onSubmit={e=>{e.preventDefault();addSource();}}>
                <label>資料の表示名<input maxLength={200} required value={sourceLabel} onChange={e=>setSourceLabel(e.target.value)} placeholder="例：関係者インタビュー記録"/></label>
                <label>ページ番号<input type="number" min={1} required value={sourcePage} onChange={e=>setSourcePage(e.target.value)}/></label>
                <button className="primary" disabled={busy}>資料情報を登録</button></form>
              <h3>登録済み資料</h3>
              {sources.length===0?<p className="empty">登録済みの資料はありません。</p>:
                sources.map(source=><div className="source-row" key={source.id}><strong>{source.document_label}</strong><small>p.{source.page} · {source.id}</small>
                <button className="quiet" onClick={()=>{void navigator.clipboard?.writeText(source.id);}}>UUIDをコピー</button></div>)}
              {sourceCursor&&<button className="more" disabled={busy} onClick={()=>client&&void run(()=>loadSources(client,selected.id,sourceCursor))}>さらに読み込む</button>}
            </section>}
        </>}
      </main>
    </div>}
    <footer className="footer">SME Partner · Research pilot · 実顧客データの入力は禁止されています。</footer>
  </div>;
}
createRoot(document.getElementById("root")!).render(<React.StrictMode><App/></React.StrictMode>);
