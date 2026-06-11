/* ================================================================
   SocialPulse Dashboard — Complete Interactive JS  v2
   6 Tabs · Time Presets · Post Performance · AI Insights
   ================================================================ */

const API_BASE    = window.location.origin;
const REFRESH_MS  = 5 * 60_000;   // 5-min refresh (API calls are slow)
const OVERVIEW_LIMIT = 20;         // fast load; 50 for post-performance

const PC = {
  facebook_posts:  { bar:'rgba(66,103,178,.80)',  line:'#7a9df0', name:'Facebook',  cls:'fb' },
  instagram_posts: { bar:'rgba(225,48,108,.75)',   line:'#f093fb', name:'Instagram', cls:'ig' },
  youtube_videos:  { bar:'rgba(255,64,64,.75)',    line:'#ff8080', name:'YouTube',   cls:'yt' },
};
const PLAT_COLORS = { facebook:'#4267B2', instagram:'#E1306C', youtube:'#FF4040' };

/* ── Plotly base layout ─────────────────────────────────────────── */
function darkLayout(extra = {}) {
  return {
    paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)',
    font:{ family:'Inter,sans-serif', color:'#9898c0', size:12 },
    xaxis:{ gridcolor:'rgba(255,255,255,.05)', zerolinecolor:'rgba(255,255,255,.04)', tickfont:{size:11,color:'#9898c0'}, linecolor:'rgba(255,255,255,.03)' },
    yaxis:{ gridcolor:'rgba(255,255,255,.05)', zerolinecolor:'rgba(255,255,255,.04)', tickfont:{size:11,color:'#9898c0'}, linecolor:'rgba(255,255,255,.03)' },
    legend:{ bgcolor:'rgba(255,255,255,.03)', bordercolor:'rgba(255,255,255,.06)', borderwidth:1, font:{color:'#c0c0e0',size:12}, orientation:'h', y:-0.22 },
    margin:{ l:52, r:18, t:18, b:68 },
    hoverlabel:{ bgcolor:'#10102a', bordercolor:'rgba(102,126,234,.4)', font:{color:'#fff',size:13,family:'Inter,sans-serif'} },
    ...extra,
  };
}

/* ── Utilities ──────────────────────────────────────────────────── */
const $   = id  => document.getElementById(id);
const $$  = sel => document.querySelectorAll(sel);
const fmtNum  = n => n == null ? '—' : n >= 1e6 ? (n/1e6).toFixed(2)+'M' : n >= 1e3 ? (n/1e3).toFixed(1)+'K' : String(n||0);
const pretty  = s => ({facebook_posts:'Facebook',instagram_posts:'Instagram',youtube_videos:'YouTube'}[s]||s);
const fmtKey  = k => k.replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase());
const chipCls = s => ({facebook_posts:'chip-fb',instagram_posts:'chip-ig',youtube_videos:'chip-yt'}[s]||'');
const today   = () => new Date().toISOString().slice(0,10);
const daysAgo = n => { const d=new Date(); d.setDate(d.getDate()-n); return d.toISOString().slice(0,10); };
const truncate= (s,n=40) => s?.length>n ? s.slice(0,n)+'…' : (s||'—');

/* ── State ──────────────────────────────────────────────────────── */
let activeTab      = 'overview';
let activePlatform = 'all';
let activeDays     = 30;
let isFetchingRefresh = false;   // ONLY blocks auto-refresh loops, NOT tab switching
let tabAbortCtrl   = null;       // abort controller per tab fetch
let countdownSec   = REFRESH_MS/1000;
let countdownTimer = null;
let refreshTimer   = null;
let ppPlatform     = 'facebook';

/* ── Animated counter ───────────────────────────────────────────── */
function animCounter(el, target, dur=900) {
  if (!el) return;
  const ease = t => 1-Math.pow(1-t,3);
  const start = performance.now();
  const step = now => {
    const p = Math.min((now-start)/dur,1);
    el.textContent = fmtNum(Math.round(ease(p)*target));
    if (p<1) requestAnimationFrame(step);
    else el.textContent = fmtNum(target);
  };
  requestAnimationFrame(step);
}

/* ── Clock ──────────────────────────────────────────────────────── */
function startClock() {
  const el = $('liveClock');
  const tick = () => el && (el.textContent = new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',second:'2-digit'}));
  tick(); setInterval(tick, 1000);
}

/* ── Loading overlay (for slow full-page load only) ─────────────── */
function showLoadingOverlay(v, msg='Loading…') {
  const el = $('loadingOverlay');
  const m  = $('loadingMsg');
  if (el) el.style.display = v?'flex':'none';
  if (m&&v) m.textContent = msg;
}

/* ── Per-card inline spinner ─────────────────────────────────────── */
function makeSpinner(label='Loading…') {
  return `<div class="placeholder-msg"><div class="ph-ring"></div><p>${label}</p></div>`;
}

/* ── Arc countdown ──────────────────────────────────────────────── */
const ARC = 94.2;
function updateArc(sec) {
  const total = REFRESH_MS/1000;
  const c = $('arcCircle'); const l = $('countdown');
  if (c) c.style.strokeDashoffset = ARC*(1-sec/total);
  if (l) l.textContent = sec>=60 ? Math.ceil(sec/60)+'m' : sec;
}
function resetCountdown() {
  clearInterval(countdownTimer); clearTimeout(refreshTimer);
  countdownSec = REFRESH_MS/1000;
  updateArc(countdownSec);
  const lr = $('lastRefreshed'); if (lr) lr.textContent = new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});
  countdownTimer = setInterval(()=>{
    if (countdownSec > 0) {
      countdownSec--;
      updateArc(countdownSec);
    }
    if (countdownSec <= 0) {
      clearInterval(countdownTimer);
      if (!isFetchingRefresh) {
        refreshTimer = setTimeout(()=>loadTab(activeTab), 0);
      }
    }
  },1000);
}

/* ── Refresh button ─────────────────────────────────────────────── */
function initRefresh() {
  $('refreshBtn')?.addEventListener('click', ()=>{
    if (!isFetchingRefresh) loadTab(activeTab, true);
  });
  resetCountdown();
}

/* ── Time range bar ─────────────────────────────────────────────── */
function initTimeRange() {
  $$('.tr-btn').forEach(btn => {
    btn.addEventListener('click', ()=>{
      $$('.tr-btn').forEach(b=>b.classList.remove('active'));
      btn.classList.add('active');
      const days = btn.dataset.days;
      if (days === 'custom') {
        activeDays = 0;
        $('customRange').style.display = 'flex';
        const tf=$('dateFrom'),tt=$('dateTo');
        if(tf&&!tf.value) tf.value=daysAgo(30);
        if(tt&&!tt.value) tt.value=today();
      } else {
        activeDays = parseInt(days);
        $('customRange').style.display = 'none';
        loadTab(activeTab);
      }
    });
  });
  $('dateFrom')?.addEventListener('change', ()=>loadTab(activeTab));
  $('dateTo')?.addEventListener('change',   ()=>loadTab(activeTab));
  const tf=$('dateFrom'), tt=$('dateTo');
  if(tf) tf.value = daysAgo(30);
  if(tt) tt.value = today();
}
function getDateRange() {
  if (activeDays>0) return { start:daysAgo(activeDays), end:today() };
  return { start:$('dateFrom')?.value||daysAgo(30), end:$('dateTo')?.value||today() };
}

/* ── Tabs ───────────────────────────────────────────────────────── */
const TAB_META = {
  overview:           { title:'Overview',             sub:'All platforms · Live data' },
  postperformance:    { title:'Post Performance',     sub:'Engagement analytics per post' },
  weekly:             { title:'Weekly Analysis',      sub:'Engagement by week' },
  monthly:            { title:'Monthly Analysis',     sub:'Month-over-month trends' },
  trend:              { title:'Trend Analysis',       sub:'Daily breakdown' },
  aiinsights:         { title:'AI Insights',          sub:'Data-driven intelligence' },
  besttime:           { title:'Best Posting Time',    sub:'Optimal hours & days to publish' },
  platformcomparison: { title:'Platform Comparison',  sub:'Side-by-side metrics across platforms' },
  reachanalysis:      { title:'Reach Analysis',       sub:'Reach, impressions & visibility trends' },
  recentposts:        { title:'Recent Post Analysis', sub:'Latest content across all platforms' },
};

function initTabs() {
  $$('.tab-btn').forEach(btn=>{
    btn.addEventListener('click', ()=>{
      const newTab = btn.dataset.tab;
      if (newTab === activeTab) return;

      // abort any in-flight request
      if (tabAbortCtrl) { tabAbortCtrl.abort(); tabAbortCtrl = null; }

      $$('.tab-btn').forEach(b=>b.classList.remove('active'));
      btn.classList.add('active');
      activeTab = newTab;
      updateTitle();
      $('sidebar')?.classList.remove('open');
      loadTab(activeTab);
    });
  });
}
function updateTitle() {
  const m = TAB_META[activeTab]||{};
  const t=$('pageTitle'); if(t) t.textContent = m.title||activeTab;
  const s=$('pageSub');   if(s) s.textContent = m.sub||'';
}

/* ── Platform select ────────────────────────────────────────────── */
function initPlatformSelector() {
  $('platformSelect')?.addEventListener('change', e=>{ activePlatform=e.target.value; loadTab(activeTab); });
}

/* ── Mobile menu ────────────────────────────────────────────────── */
function initMenuToggle() {
  const btn=$('menuToggle'), sb=$('sidebar');
  if(btn&&sb) {
    btn.addEventListener('click', ()=>sb.classList.toggle('open'));
    document.addEventListener('click', e=>{ if(sb.classList.contains('open')&&!sb.contains(e.target)&&e.target!==btn) sb.classList.remove('open'); });
  }
}

/* ── Sidebar pills ──────────────────────────────────────────────── */
function setSidebarPills(fb, ig, yt) {
  if(fb!=null && $('sp-fb-val')) $('sp-fb-val').textContent = fmtNum(fb);
  if(ig!=null && $('sp-ig-val')) $('sp-ig-val').textContent = fmtNum(ig);
  if(yt!=null && $('sp-yt-val')) $('sp-yt-val').textContent = fmtNum(yt);
}
function setTabPill(id, val) {
  const el=$(id); if(!el) return;
  if(val) { el.textContent=val; el.classList.add('visible'); } else el.classList.remove('visible');
}

/* ── API fetch with abort support ───────────────────────────────── */
async function api(path, params={}, signal=null) {
  const url = new URL(path, API_BASE);
  Object.entries(params).forEach(([k,v])=>v!=null&&url.searchParams.set(k,v));
  const opts = signal ? { signal } : {};
  const r = await fetch(url, opts);
  if(!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

/* ── Main dispatcher ─────────────────────────────────────────────── */
async function loadTab(tab, forceRefresh=false) {
  // abort any ongoing tab fetch
  if (tabAbortCtrl) tabAbortCtrl.abort();
  tabAbortCtrl = new AbortController();
  const signal = tabAbortCtrl.signal;

  isFetchingRefresh = true;
  $('refreshBtn')?.classList.add('spinning');

  try {
    switch(tab) {
      case 'overview':            await loadOverview(signal);           break;
      case 'postperformance':     await loadPostPerformance(signal);    break;
      case 'weekly':              await loadWeekly(signal);             break;
      case 'monthly':             await loadMonthly(signal);            break;
      case 'trend':               await loadTrend(signal);              break;
      case 'aiinsights':          await loadAIInsights(signal);         break;
      case 'besttime':            await loadBestTime(signal);           break;
      case 'platformcomparison':  await loadPlatformComparison(signal); break;
      case 'reachanalysis':       await loadReachAnalysis(signal);      break;
      case 'recentposts':         await loadRecentPosts(signal);        break;
    }
    if (forceRefresh) resetCountdown();
  } catch(err) {
    if (err.name === 'AbortError') return; // tab switched, ignore
    console.error(err);
    const ca=$('chartArea');
    if (ca) ca.innerHTML = `<div class="error-msg">⚠️ ${err.message}</div>`;
  } finally {
    isFetchingRefresh = false;
    $('refreshBtn')?.classList.remove('spinning');
  }
}

/* ================================================================
   OVERVIEW
   ================================================================ */
async function loadOverview(signal) {
  const ca=$('chartArea');
  ca.innerHTML = `<div class="overview-grid" id="og"></div>`;
  const grid=$('og');

  const [fbR, igR, ytR] = await Promise.allSettled([
    api('/facebook/posts',  {limit:OVERVIEW_LIMIT}, signal),
    api('/instagram/posts', {limit:OVERVIEW_LIMIT}, signal),
    api('/youtube/videos',  {limit:OVERVIEW_LIMIT}, signal),
  ]);

  const plats = [
    { key:'facebook',  lbl:'Facebook',  emoji:'📘', cls:'fb-card', icls:'fb-icon', engKey:'total_engagement', d:fbR.status==='fulfilled'?fbR.value:null, err:fbR.reason },
    { key:'instagram', lbl:'Instagram', emoji:'📸', cls:'ig-card', icls:'ig-icon', engKey:'total_interactions',d:igR.status==='fulfilled'?igR.value:null, err:igR.reason },
    { key:'youtube',   lbl:'YouTube',   emoji:'▶️', cls:'yt-card', icls:'yt-icon', engKey:null,               d:ytR.status==='fulfilled'?ytR.value:null, err:ytR.reason },
  ];

  const dVals=[],dLbls=[],dClrs=['#4267B2','#E1306C','#FF4040'];
  let totEng=0;

  plats.forEach((p,idx)=>{
    const card=document.createElement('div');
    card.className=`kpi-card ${p.cls}`;
    const posts=p.d?.data||[];
    const count=p.d?.count||posts.length;

    if(p.d&&!p.d.error){
      const followers=p.d.fan_count||p.d.followers_count||p.d.subscriber_count||0;
      const eng=posts.reduce((s,x)=>s+(p.engKey?x[p.engKey]||0:((x.like_count||0)+(x.comment_count||0))),0);
      const avg=count>0?Math.round(eng/count):0;
      totEng+=eng; dVals.push(eng); dLbls.push(p.lbl);
      const barPct=Math.min(100,followers>0?Math.min((eng/(followers*0.1))*100,100):30);
      card.innerHTML=`
        <div class="kpi-top">
          <div class="kpi-icon-wrap ${p.icls}">${p.emoji}</div>
          <span class="kpi-status">● Live</span>
        </div>
        <div class="kpi-label">${p.lbl}</div>
        <div class="kpi-value" id="kv-${p.key}">0</div>
        <div class="kpi-sub">Total Engagement</div>
        <div class="kpi-divider"></div>
        <div class="kpi-stats">
          <div class="kpi-row"><span class="kpi-row-key">Posts fetched</span><span class="kpi-row-val">${count}</span></div>
          <div class="kpi-row"><span class="kpi-row-key">Followers</span><span class="kpi-row-val">${fmtNum(followers)}</span></div>
          <div class="kpi-row"><span class="kpi-row-key">Avg / post</span><span class="kpi-row-val">${fmtNum(avg)}</span></div>
        </div>
        <div class="kpi-bar-track"><div class="kpi-bar-fill" style="width:0%" id="bar-${p.key}"></div></div>`;
      grid.appendChild(card);
      requestAnimationFrame(()=>{
        animCounter($(`kv-${p.key}`),eng);
        setTimeout(()=>{ const b=$(`bar-${p.key}`); if(b) b.style.width=barPct+'%'; },100);
      });
      if(p.key==='facebook') setSidebarPills(followers,null,null);
      if(p.key==='instagram') setSidebarPills(null,followers,null);
      if(p.key==='youtube') setSidebarPills(null,null,followers);
    } else {
      card.innerHTML=`
        <div class="kpi-top"><div class="kpi-icon-wrap ${p.icls}">${p.emoji}</div><span class="kpi-status error">✕ Error</span></div>
        <div class="kpi-label">${p.lbl}</div>
        <div class="kpi-error"><div class="kpi-error-icon">⚠️</div><span>${p.d?.error||'API unavailable'}</span></div>`;
      grid.appendChild(card);
    }
  });

  setTabPill('pill-overview', plats.filter(p=>p.d&&!p.d.error).length+'/3');

  // Donut chart
  if(dVals.length){
    const dw=document.createElement('div');
    dw.className='kpi-card donut-card';
    dw.innerHTML=`<div class="chart-header"><span class="chart-title">Engagement Share</span><span class="chart-badge">${fmtNum(totEng)} total</span></div><div id="donutChart" style="min-height:260px"></div>`;
    grid.appendChild(dw);
    setTimeout(()=>{
      Plotly.newPlot('donutChart',[{
        values:dVals, labels:dLbls, type:'pie', hole:.62,
        marker:{colors:dClrs,line:{color:'#080812',width:3}},
        textinfo:'none',
        hovertemplate:'<b>%{label}</b><br>%{value:,} engagements<br>%{percent}<extra></extra>',
        pull:[.04,.04,.04],
      }],{
        ...darkLayout(),showlegend:true,
        legend:{bgcolor:'rgba(0,0,0,0)',font:{color:'#c0c0e0',size:13},orientation:'h',x:.5,xanchor:'center',y:-.08},
        margin:{l:10,r:10,t:10,b:45},height:275,
        annotations:[{x:.5,y:.5,xref:'paper',yref:'paper',text:'<b>'+fmtNum(totEng)+'</b>',showarrow:false,font:{size:20,color:'#f0f0ff',family:'Space Grotesk,sans-serif'}}],
      },{responsive:true,displayModeBar:false});
    },80);
  }

  // Render sparklines for each platform that loaded
  plats.forEach(p=>{
    if(!p.d||p.d.error||!p.d.data?.length) return;
    const posts=[...p.d.data].slice(0,15);
    const sparkId=`spark-${p.key}`;
    const sDiv=document.createElement('div');
    sDiv.className='chart-card full-width';
    sDiv.style.gridColumn='1/-1';
    sDiv.innerHTML=`<div class="chart-header"><span class="chart-title">${p.lbl} — Recent Engagement</span><span class="chart-badge">Last ${posts.length} posts</span></div><div id="${sparkId}" class="plotly-container"></div>`;
    grid.appendChild(sDiv);
    const engVals=posts.map(x=>p.engKey?x[p.engKey]||0:(x.like_count||0)+(x.comment_count||0));
    const dates=posts.map(x=>x.date||x.created_time_display||x.published_at||'');
    const clr=PLAT_COLORS[p.key]||'#667eea';
    setTimeout(()=>{
      Plotly.newPlot(sparkId,[{
        x:dates, y:engVals, type:'scatter', mode:'lines+markers',
        name:p.lbl,
        line:{color:clr,width:3,shape:'spline',smoothing:.8},
        marker:{size:8,color:clr,line:{color:'#080812',width:2}},
        fill:'tozeroy', fillcolor:clr+'18',
        hovertemplate:'<b>%{x}</b><br>Engagement: <b>%{y:,}</b><extra></extra>',
      }],{
        ...darkLayout({height:220,xaxis:{...darkLayout().xaxis,tickangle:-25,tickfont:{size:10}},
          yaxis:{...darkLayout().yaxis,title:{text:'Engagements',font:{color:'#6666a0',size:11}}},
          margin:{l:56,r:16,t:12,b:60}}),
      },{responsive:true,displayModeBar:false});
    },120);
  });
}

/* ================================================================
   POST PERFORMANCE
   ================================================================ */
async function loadPostPerformance(signal) {
  const ca=$('chartArea');
  ca.innerHTML=`
    <div class="pp-platform-tabs">
      <button class="pp-tab fb-tab${ppPlatform==='facebook'?' active':''}" data-plat="facebook">📘 Facebook</button>
      <button class="pp-tab ig-tab${ppPlatform==='instagram'?' active':''}" data-plat="instagram">📸 Instagram</button>
      <button class="pp-tab yt-tab${ppPlatform==='youtube'?' active':''}" data-plat="youtube">▶️ YouTube</button>
    </div>
    <div id="ppContent">${makeSpinner('Fetching posts…')}</div>`;

  $$('.pp-tab').forEach(btn=>btn.addEventListener('click', async ()=>{
    $$('.pp-tab').forEach(b=>b.classList.remove('active'));
    btn.classList.add('active');
    ppPlatform=btn.dataset.plat;
    await renderPlatformPerformance(ppPlatform, signal);
  }));

  await renderPlatformPerformance(ppPlatform, signal);
}

async function renderPlatformPerformance(plat, signal) {
  const cont=$('ppContent');
  if (cont) cont.innerHTML=makeSpinner('Loading data…');
  try {
    let posts=[];
    const color = PLAT_COLORS[plat];

    if(plat==='facebook'){
      const r=await api('/facebook/posts',{limit:50},signal);
      posts=(r.data||[]).map(p=>({...p,
        _eng:p.total_engagement||0,
        _label:truncate(p.message||p.story||'',38),
        _reach:p.post_reach||0,
        _date:p.created_time_display||p.date||'',
        _reactions:p.reactions||0,_comments:p.comments||0,_shares:p.shares||0,
        _impressions:p.post_impressions||0,
      }));
    } else if(plat==='instagram'){
      const r=await api('/instagram/posts',{limit:50},signal);
      posts=(r.data||[]).map(p=>({...p,
        _eng:p.total_interactions||0,
        _label:truncate(p.caption||'',38),
        _reach:p.reach||0,
        _date:p.created_time||'',
        _likes:p.like_count||0,_comments:p.comments_count||0,_saved:p.saved||0,
        _impressions:p.impressions||0,
      }));
    } else {
      const r=await api('/youtube/videos',{limit:50},signal);
      posts=(r.data||[]).map(p=>({...p,
        _eng:(p.like_count||0)+(p.comment_count||0),
        _label:truncate(p.title||'',38),
        _reach:p.view_count||0,
        _date:p.published_at||'',
        _views:p.view_count||0,_likes:p.like_count||0,_comments:p.comment_count||0,
        _er:p.view_count>0?((p.like_count||0)+(p.comment_count||0))/p.view_count*100:0,
      }));
    }

    if(!posts.length){ cont.innerHTML='<div class="empty-state"><div class="empty-state-icon">📭</div><p>No data available for this platform</p></div>'; return; }

    const sorted=[...posts].sort((a,b)=>b._eng-a._eng);
    const top3=sorted.slice(0,3);
    const top10=sorted.slice(0,10);

    const rankCls=['gold','silver','bronze'];
    const rankLabel=['#1','#2','#3'];
    const cardsHtml=top3.map((p,i)=>`
      <div class="top-post-card">
        <span class="tp-rank ${rankCls[i]}">${rankLabel[i]}</span>
        <div class="tp-meta">${p._date}</div>
        <div class="tp-value">${fmtNum(p._eng)}</div>
        <div class="tp-label">Engagements</div>
        <div class="tp-excerpt">${p._label}</div>
        ${p.permalink_url||p.permalink?`<a class="tp-link" href="${p.permalink_url||p.permalink}" target="_blank">View post ↗</a>`:''}
      </div>`).join('');

    cont.innerHTML=`
      <div class="top-posts-row">${cardsHtml}</div>
      <div class="pp-charts-grid">
        <div class="chart-card"><div class="chart-header"><span class="chart-title">Top 10 Posts by Engagement</span><span class="chart-badge">${posts.length} total</span></div><div id="ppBar" class="plotly-container"></div></div>
        <div class="chart-card"><div class="chart-header"><span class="chart-title">${plat==='youtube'?'Views':'Reach'} vs Engagement</span></div><div id="ppScatter" class="plotly-container"></div></div>
      </div>
      <div class="charts-2col">
        <div class="chart-card"><div class="chart-header"><span class="chart-title">${plat==='facebook'?'Reactions · Comments · Shares':plat==='instagram'?'Likes · Comments · Saved':'Views · Likes · Comments'}</span></div><div id="ppBreakdown" class="plotly-container"></div></div>
        <div class="chart-card"><div class="chart-header"><span class="chart-title">${plat==='youtube'?'Engagement Rate by Video':'Reach & Impressions Timeline'}</span></div><div id="ppTimeline" class="plotly-container"></div></div>
      </div>`;

    setTabPill('pill-postperformance', posts.length);
    const opts={responsive:true,displaylogo:false,modeBarButtonsToRemove:['lasso2d','select2d']};
    const DL=darkLayout({height:320,margin:{l:52,r:18,t:12,b:60}});

    // Horizontal bar — top 10
    Plotly.newPlot('ppBar',[{
      x:top10.map(p=>p._eng), y:top10.map(p=>p._label),
      type:'bar', orientation:'h',
      marker:{color:top10.map((_,i)=>color+(i===0?'ff':i<3?'cc':'88')),line:{width:0}},
      hovertemplate:'<b>%{y}</b><br>%{x:,} engagements<extra></extra>',
    }],{...DL,xaxis:{...DL.xaxis,title:{text:'Engagements',font:{color:'#6666a0',size:11}}},yaxis:{...DL.yaxis,autorange:'reversed',tickfont:{size:10},tickmode:'linear'}},opts);

    // Scatter — reach vs eng
    Plotly.newPlot('ppScatter',[{
      x:posts.map(p=>p._reach), y:posts.map(p=>p._eng),
      text:posts.map(p=>p._label),
      mode:'markers',
      marker:{size:posts.map(p=>Math.max(6,Math.min(20,p._eng/Math.max(...posts.map(q=>q._eng),1)*20))),
        color:posts.map(p=>p._eng),colorscale:[[0,'rgba(102,126,234,.35)'],[1,color]],
        showscale:false,opacity:.82,line:{color:'#080812',width:1}},
      hovertemplate:'<b>%{text}</b><br>Reach: %{x:,}<br>Engagement: %{y:,}<extra></extra>',
    }],{...DL,xaxis:{...DL.xaxis,title:{text:plat==='youtube'?'Views':'Reach',font:{color:'#6666a0',size:11}}},yaxis:{...DL.yaxis,title:{text:'Engagement',font:{color:'#6666a0',size:11}}}},opts);

    // Breakdown grouped bar
    if(plat==='facebook'){
      const x=top10.map(p=>p._label);
      Plotly.newPlot('ppBreakdown',[
        {x,y:top10.map(p=>p._reactions),name:'Reactions',type:'bar',marker:{color:'rgba(66,103,178,.85)'}},
        {x,y:top10.map(p=>p._comments),name:'Comments',type:'bar',marker:{color:'rgba(122,157,240,.85)'}},
        {x,y:top10.map(p=>p._shares),name:'Shares',type:'bar',marker:{color:'rgba(79,172,254,.85)'}},
      ],{...DL,barmode:'group',xaxis:{...DL.xaxis,tickangle:-28,tickfont:{size:9}},yaxis:{...DL.yaxis,title:{text:'Count',font:{color:'#6666a0',size:11}}}},opts);

      const ts=[...posts].sort((a,b)=>a._date.localeCompare(b._date));
      Plotly.newPlot('ppTimeline',[
        {x:ts.map(p=>p._date),y:ts.map(p=>p._reach),name:'Reach',mode:'lines+markers',line:{color:'#4267B2',width:2.5,shape:'spline'},fill:'tozeroy',fillcolor:'rgba(66,103,178,.07)',marker:{size:6}},
        {x:ts.map(p=>p._date),y:ts.map(p=>p._impressions),name:'Impressions',mode:'lines+markers',line:{color:'#7a9df0',width:2,shape:'spline'},marker:{size:5}},
      ],{...DL,yaxis:{...DL.yaxis,title:{text:'Count',font:{color:'#6666a0',size:11}}},xaxis:{...DL.xaxis,tickangle:-25,tickfont:{size:10}}},opts);

    } else if(plat==='instagram'){
      const x=top10.map(p=>p._label);
      Plotly.newPlot('ppBreakdown',[
        {x,y:top10.map(p=>p._likes),name:'Likes',type:'bar',marker:{color:'rgba(225,48,108,.85)'}},
        {x,y:top10.map(p=>p._comments),name:'Comments',type:'bar',marker:{color:'rgba(240,147,251,.85)'}},
        {x,y:top10.map(p=>p._saved),name:'Saved',type:'bar',marker:{color:'rgba(249,206,52,.85)'}},
      ],{...DL,barmode:'group',xaxis:{...DL.xaxis,tickangle:-28,tickfont:{size:9}},yaxis:{...DL.yaxis,title:{text:'Count',font:{color:'#6666a0',size:11}}}},opts);

      const ts=[...posts].sort((a,b)=>a._date.localeCompare(b._date));
      Plotly.newPlot('ppTimeline',[
        {x:ts.map(p=>p._date),y:ts.map(p=>p._impressions),name:'Impressions',mode:'lines+markers',line:{color:'#f093fb',width:2.5,shape:'spline'},fill:'tozeroy',fillcolor:'rgba(225,48,108,.07)',marker:{size:6}},
        {x:ts.map(p=>p._date),y:ts.map(p=>p._reach),name:'Reach',mode:'lines+markers',line:{color:'#ee2a7b',width:2,shape:'spline'},marker:{size:5}},
      ],{...DL,yaxis:{...DL.yaxis,title:{text:'Count',font:{color:'#6666a0',size:11}}},xaxis:{...DL.xaxis,tickangle:-25,tickfont:{size:10}}},opts);

    } else { // youtube
      const x=top10.map(p=>p._label);
      Plotly.newPlot('ppBreakdown',[
        {x,y:top10.map(p=>p._views),name:'Views',type:'bar',marker:{color:'rgba(255,64,64,.85)'}},
        {x,y:top10.map(p=>p._likes),name:'Likes',type:'bar',marker:{color:'rgba(255,136,136,.85)'}},
        {x,y:top10.map(p=>p._comments),name:'Comments',type:'bar',marker:{color:'rgba(255,200,200,.85)'}},
      ],{...DL,barmode:'group',xaxis:{...DL.xaxis,tickangle:-28,tickfont:{size:9}},yaxis:{...DL.yaxis,title:{text:'Count',font:{color:'#6666a0',size:11}}}},opts);

      const er=[...posts].sort((a,b)=>b._er-a._er).slice(0,10);
      Plotly.newPlot('ppTimeline',[{
        x:er.map(p=>parseFloat(p._er.toFixed(3))),y:er.map(p=>p._label),
        type:'bar',orientation:'h',
        marker:{color:er.map((_,i)=>`rgba(255,64,64,${1-i*0.06})`),line:{width:0}},
        hovertemplate:'%{y}<br>%{x:.3f}% rate<extra></extra>',
      }],{...DL,xaxis:{...DL.xaxis,title:{text:'Engagement Rate (%)',font:{color:'#6666a0',size:11}}},yaxis:{...DL.yaxis,autorange:'reversed',tickfont:{size:9}}},opts);
    }

  } catch(err) {
    if (err.name==='AbortError') return;
    if (cont) cont.innerHTML=`<div class="error-msg">⚠️ ${err.message}</div>`;
  }
}

/* ================================================================
   WEEKLY
   ================================================================ */
async function loadWeekly(signal) {
  $('chartArea').innerHTML=makeSpinner('Loading weekly data…');
  const {start,end}=getDateRange();
  const d=await api('/analysis/weekly',{start_date:start,end_date:end,platform:activePlatform},signal);
  const rows=d.data||[];
  setTabPill('pill-weekly', rows.length||null);
  if(!rows.length){$('chartArea').innerHTML=emptyState('No weekly data for selected range');return;}
  const srcs=[...new Set(rows.map(r=>r.source))];
  renderDualChart('Weekly Engagement',buildBar(rows,srcs,'week','total_engagement'),'Avg Engagement Rate %',buildLine(rows,srcs,'week','avg_engagement_rate'),rows,'Week');
}

/* ================================================================
   MONTHLY
   ================================================================ */
async function loadMonthly(signal) {
  $('chartArea').innerHTML=makeSpinner('Loading monthly data…');
  const {start,end}=getDateRange();
  const d=await api('/analysis/monthly',{start_date:start,end_date:end,platform:activePlatform},signal);
  const rows=d.data||[];
  setTabPill('pill-monthly', rows.length||null);
  if(!rows.length){$('chartArea').innerHTML=emptyState('No monthly data for selected range');return;}
  const srcs=[...new Set(rows.map(r=>r.source))];
  renderDualChart('Monthly Engagement',buildBar(rows,srcs,'month','total_engagement'),'Avg Engagement Rate %',buildLine(rows,srcs,'month','avg_engagement_rate'),rows,'Month');
}

/* ================================================================
   TREND
   ================================================================ */
async function loadTrend(signal) {
  $('chartArea').innerHTML=makeSpinner('Loading trend data…');
  const {start,end}=getDateRange();
  const d=await api('/trend',{start_date:start,end_date:end,platform:activePlatform},signal);
  const rows=d.data||[];
  setTabPill('pill-trend', rows.length||null);
  if(!rows.length){$('chartArea').innerHTML=emptyState('No trend data for selected range');return;}
  const srcs=[...new Set(rows.map(r=>r.source))];
  renderDualChart('Daily Engagement',buildBar(rows,srcs,'date','total_engagement'),'Daily Rate %',buildLine(rows,srcs,'date','avg_engagement_rate'),rows,'Date');
}

/* ── Trace builders ─────────────────────────────────────────────── */
function buildBar(rows,srcs,xk,yk){
  return srcs.map(s=>{
    const f=rows.filter(r=>r.source===s).sort((a,b)=>(a[xk]||'').localeCompare(b[xk]||''));
    const c=PC[s]||{bar:'rgba(150,150,255,.7)',name:s};
    return{x:f.map(r=>r[xk]),y:f.map(r=>r[yk]||0),name:c.name,type:'bar',
      marker:{color:c.bar,line:{width:0}},
      hovertemplate:`<b>%{x}</b><br>${fmtKey(yk)}: <b>%{y:,}</b><extra>${c.name}</extra>`};
  });
}
function buildLine(rows,srcs,xk,yk){
  return srcs.map(s=>{
    const f=rows.filter(r=>r.source===s).sort((a,b)=>(a[xk]||'').localeCompare(b[xk]||''));
    const c=PC[s]||{line:'#aaa',name:s};
    return{x:f.map(r=>r[xk]),y:f.map(r=>r[yk]||0),name:c.name,type:'scatter',mode:'lines+markers',
      marker:{size:8,color:c.line,symbol:'circle',line:{color:'#080812',width:2}},
      line:{color:c.line,width:3,shape:'spline',smoothing:.8},fill:'tozeroy',fillcolor:c.line+'14',
      hovertemplate:`<b>%{x}</b><br>${fmtKey(yk)}: <b>%{y:.3f}</b><extra>${c.name}</extra>`};
  });
}

function renderDualChart(bt,btr,lt,ltr,rows,xl='') {
  $('chartArea').innerHTML=`
    <div class="charts-2col">
      <div class="chart-card"><div class="chart-header"><span class="chart-title">${bt}</span><span class="chart-badge">${btr.length} source${btr.length!==1?'s':''}</span></div><div id="barChart" class="plotly-container"></div></div>
      <div class="chart-card"><div class="chart-header"><span class="chart-title">${lt}</span></div><div id="lineChart" class="plotly-container"></div></div>
    </div>
    <div class="chart-card full-width"><div class="chart-header"><span class="chart-title">Data Table</span><span class="chart-badge">${rows.length} rows</span></div><div class="table-scroll" id="dataTable"></div></div>`;
  const o={responsive:true,displaylogo:false,modeBarButtonsToRemove:['lasso2d','select2d']};
  const DL=darkLayout({height:340,xaxis:{...darkLayout().xaxis,title:{text:xl,font:{color:'#6666a0',size:11}}},yaxis:{...darkLayout().yaxis,title:{text:'Engagement',font:{color:'#6666a0',size:11}}}});
  Plotly.newPlot('barChart',btr,{...DL,barmode:'group',bargap:.25,bargroupgap:.08},o);
  Plotly.newPlot('lineChart',ltr,{...DL,yaxis:{...DL.yaxis,title:{text:'Rate (%)',font:{color:'#6666a0',size:11}}}},o);
  renderTable(rows);
}

function renderTable(rows) {
  const c=$('dataTable'); if(!c||!rows.length) return;
  const keys=Object.keys(rows[0]);
  let h='<table><thead><tr>'+keys.map(k=>`<th>${fmtKey(k)}</th>`).join('')+'</tr></thead><tbody>';
  rows.slice(0,120).forEach(row=>{
    h+='<tr>';
    keys.forEach(k=>{
      let v=row[k];
      if(k==='source') h+=`<td><span class="platform-chip ${chipCls(v)}">${pretty(v)}</span></td>`;
      else if(typeof v==='number') h+=`<td>${v%1!==0?v.toFixed(3):v.toLocaleString()}</td>`;
      else h+=`<td>${v??'—'}</td>`;
    });
    h+='</tr>';
  });
  c.innerHTML=h+'</tbody></table>';
}

/* ================================================================
   AI INSIGHTS
   ================================================================ */
async function loadAIInsights(signal) {
  const ca=$('chartArea');
  ca.innerHTML=`
    <div class="ai-hero" id="aiHero">
      <div class="health-ring">
        <svg width="100" height="100" viewBox="0 0 100 100">
          <circle cx="50" cy="50" r="42" fill="none" stroke="rgba(255,255,255,.05)" stroke-width="6"/>
          <circle id="healthArc" cx="50" cy="50" r="42" fill="none" stroke="url(#hg)" stroke-width="6"
            stroke-dasharray="263.9" stroke-dashoffset="263.9" stroke-linecap="round" transform="rotate(-90 50 50)"/>
          <defs><linearGradient id="hg" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="#43e97b"/><stop offset="100%" stop-color="#38f9d7"/></linearGradient></defs>
        </svg>
        <div class="health-ring-label"><span class="health-score-num" id="healthNum">—</span><span class="health-score-sub">Score</span></div>
      </div>
      <div class="ai-hero-text">
        <div class="ai-hero-title">AI-Powered Insights</div>
        <div class="ai-hero-sub">Analysing Facebook, Instagram & YouTube data to surface actionable intelligence from your live API data.</div>
        <div class="ai-hero-stats">
          <div class="ai-stat"><span class="ai-stat-val" id="ai-s-plat">—</span><span class="ai-stat-lbl">Active Platforms</span></div>
          <div class="ai-stat"><span class="ai-stat-val" id="ai-s-aud">—</span><span class="ai-stat-lbl">Total Audience</span></div>
          <div class="ai-stat"><span class="ai-stat-val" id="ai-s-cont">—</span><span class="ai-stat-lbl">Content Pieces</span></div>
          <div class="ai-stat"><span class="ai-stat-val" id="ai-s-rate">—</span><span class="ai-stat-lbl">Eng. Rate</span></div>
        </div>
      </div>
      <button class="ai-regenerate" id="aiRegenBtn">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M23 4v6h-6"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
        Regenerate
      </button>
    </div>
    <div class="insights-grid" id="insightsGrid">${makeSpinner('Analysing your data…')}</div>`;

  $('aiRegenBtn')?.addEventListener('click', async ()=>{
    const btn=$('aiRegenBtn');
    btn.classList.add('spinning'); btn.disabled=true;
    await renderInsights(signal);
    btn.classList.remove('spinning'); btn.disabled=false;
  });

  await renderInsights(signal);
}

async function renderInsights(signal) {
  const grid=$('insightsGrid');
  if(grid) grid.innerHTML=makeSpinner('Analysing…');
  try {
    const data = await api('/ai-insights',{},signal);
    const { insights=[], summary={} } = data;

    // Hero stats
    const hn=$('healthNum'); if(hn) animCounter(hn,summary.health_score||0,800);
    const arc=$('healthArc');
    if(arc){
      const score=summary.health_score||0;
      const full=263.9;
      setTimeout(()=>{ arc.style.transition='stroke-dashoffset 1.5s cubic-bezier(.4,0,.2,1)'; arc.style.strokeDashoffset=full*(1-score/100); },80);
    }
    if($('ai-s-plat')) $('ai-s-plat').textContent=summary.active_platforms||'—';
    if($('ai-s-aud'))  { const el=$('ai-s-aud'); if(el) animCounter(el,summary.total_audience||0); }
    if($('ai-s-cont')) $('ai-s-cont').textContent=summary.total_content||'—';
    if($('ai-s-rate')) $('ai-s-rate').textContent=(summary.overall_engagement_rate||0).toFixed(4)+'%';

    setTabPill('pill-aiinsights', insights.length||null);

    if(!grid) return;
    if(!insights.length){ grid.innerHTML='<div class="empty-state"><div class="empty-state-icon">🤔</div><p>No insights yet — check API connectivity</p></div>'; return; }

    grid.innerHTML='';
    insights.forEach((ins,i)=>{
      const card=document.createElement('div');
      card.className=`insight-card ${ins.type||'info'}`;
      card.style.animationDelay=`${i*0.07}s`;
      const platBadge=`<span class="ic-platform-badge ${ins.platform==='all'?'all':ins.platform}">${(ins.platform||'all').charAt(0).toUpperCase()+(ins.platform||'all').slice(1)}</span>`;
      card.innerHTML=`
        <div class="ic-header">
          <div class="ic-icon">${ins.icon||'💡'}</div>
          <div class="ic-meta">${platBadge}<div class="ic-title">${ins.title}</div></div>
          <div class="ic-type-dot ${ins.type||'info'}"></div>
        </div>
        <div class="ic-metric">
          <span class="ic-metric-val">${ins.metric||'—'}</span>
          <span class="ic-metric-lbl">${ins.metric_label||''}</span>
        </div>
        <div class="ic-body">
          <p class="ic-desc">${ins.description}</p>
          ${ins.chart_data?`<div class="ic-mini-chart" id="mc-${i}"></div>`:''}
          ${ins.post_url?`<a class="ic-link" href="${ins.post_url}" target="_blank">View post ↗</a>`:''}
        </div>`;
      grid.appendChild(card);
      if(ins.chart_data&&ins.chart_type) {
        setTimeout(()=>renderMiniChart(`mc-${i}`,ins.chart_data,ins.chart_type,ins.platform), 80+i*35);
      }
    });
  } catch(err) {
    if(err.name==='AbortError') return;
    if(grid) grid.innerHTML=`<div class="error-msg">⚠️ ${err.message}</div>`;
  }
}

function renderMiniChart(id, data, type, plat) {
  const el=$(id); if(!el||!data?.labels?.length) return;
  const color=({facebook:'#4267B2',instagram:'#E1306C',youtube:'#FF4040',all:'#667eea'})[plat]||'#667eea';
  const base={paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',
    font:{family:'Inter,sans-serif',color:'#9898c0',size:10},
    xaxis:{gridcolor:'rgba(255,255,255,.04)',tickfont:{size:9,color:'#6666a0'},linecolor:'transparent',nticks:6},
    yaxis:{gridcolor:'rgba(255,255,255,.04)',tickfont:{size:9,color:'#6666a0'},linecolor:'transparent'},
    margin:{l:30,r:6,t:6,b:26},showlegend:false,height:92};
  try{
    if(type==='bar'){
      Plotly.newPlot(id,[{x:data.labels,y:data.values,type:'bar',marker:{color,opacity:.8,line:{width:0}},hoverinfo:'x+y'}],base,{responsive:true,displayModeBar:false,staticPlot:true});
    } else if(type==='donut'){
      Plotly.newPlot(id,[{values:data.values,labels:data.labels,type:'pie',hole:.55,
        marker:{colors:['#4267B2','#E1306C','#FF4040','#667eea'],line:{color:'#080812',width:2}},
        textinfo:'none',hoverinfo:'label+percent'}],
        {...base,margin:{l:0,r:0,t:0,b:0},height:92},{responsive:true,displayModeBar:false,staticPlot:true});
    } else if(type==='line'){
      Plotly.newPlot(id,[{x:data.labels,y:data.values,type:'scatter',mode:'lines',
        line:{color,width:2,shape:'spline'},fill:'tozeroy',fillcolor:color+'18',hoverinfo:'x+y'}],base,{responsive:true,displayModeBar:false,staticPlot:true});
    }
  } catch(e){ /* skip if Plotly fails on mini chart */ }
}

/* ── Helpers ────────────────────────────────────────────────────── */
function emptyState(msg){
  return `<div class="chart-card"><div class="empty-state"><div class="empty-state-icon">📭</div><p>${msg}</p></div></div>`;
}

/* ================================================================
   BEST POSTING TIME
   ================================================================ */
async function loadBestTime(signal) {
  const ca = $('chartArea');
  ca.innerHTML = `
    <div class="bpt-platform-tabs">
      <button class="bpt-tab active" data-plat="facebook">📘 Facebook</button>
      <button class="bpt-tab" data-plat="instagram">📸 Instagram</button>
      <button class="bpt-tab" data-plat="youtube">▶️ YouTube</button>
    </div>
    <div id="bptContent">${makeSpinner('Analysing your best posting times…')}</div>`;

  let bptPlat = 'facebook';
  let bptData = null;

  async function renderBPT(plat) {
    const cont = $('bptContent');
    if (cont) cont.innerHTML = makeSpinner('Computing…');
    try {
      if (!bptData) bptData = await api('/analysis/best-time', {}, signal);
      const platData = bptData?.platforms?.[plat];
      if (!platData) { cont.innerHTML = emptyState('No timing data for this platform'); return; }

      const byDay = platData.by_day || {};
      const byHour = platData.by_hour || {};
      const heatmap = platData.heatmap || {};
      const days  = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];
      const color = { facebook:'#4267B2', instagram:'#E1306C', youtube:'#FF4040' }[plat];

      // Build best day/hour callouts
      const bestDay  = Object.entries(byDay).sort((a,b)=>b[1]-a[1])[0];
      const bestHour = Object.entries(byHour).sort((a,b)=>b[1]-a[1])[0];
      const h = bestHour ? parseInt(bestHour[0]) : null;
      const hourLabel = h != null ? (h===0?'12 AM':h<12?h+' AM':h===12?'12 PM':(h-12)+' PM') : '—';

      cont.innerHTML = `
        <div class="bpt-callouts">
          <div class="bpt-callout" style="--cc:${color}">
            <div class="bptc-icon">📅</div>
            <div class="bptc-body">
              <div class="bptc-label">Best Day to Post</div>
              <div class="bptc-value">${bestDay?bestDay[0]:'—'}</div>
              <div class="bptc-sub">${bestDay?fmtNum(Math.round(bestDay[1]))+' avg engagements':''}</div>
            </div>
          </div>
          <div class="bpt-callout" style="--cc:${color}">
            <div class="bptc-icon">🕐</div>
            <div class="bptc-body">
              <div class="bptc-label">Best Hour to Post</div>
              <div class="bptc-value">${hourLabel}</div>
              <div class="bptc-sub">${bestHour?fmtNum(Math.round(bestHour[1]))+' avg engagements':''}</div>
            </div>
          </div>
          <div class="bpt-callout" style="--cc:${color}">
            <div class="bptc-icon">📊</div>
            <div class="bptc-body">
              <div class="bptc-label">Days Analysed</div>
              <div class="bptc-value">${Object.keys(byDay).length}</div>
              <div class="bptc-sub">days with posts</div>
            </div>
          </div>
        </div>
        <div class="charts-2col">
          <div class="chart-card">
            <div class="chart-header"><span class="chart-title">📅 Engagement by Day of Week</span><span class="chart-badge">avg per day</span></div>
            <div id="bptDayChart" class="plotly-container"></div>
          </div>
          <div class="chart-card">
            <div class="chart-header"><span class="chart-title">🕐 Engagement by Hour of Day</span><span class="chart-badge">avg per hour</span></div>
            <div id="bptHourChart" class="plotly-container"></div>
          </div>
        </div>
        <div class="chart-card full-width">
          <div class="chart-header"><span class="chart-title">🔥 Engagement Heatmap — Day × Hour</span><span class="chart-badge">intensity = avg engagement</span></div>
          <div id="bptHeatmap" style="min-height:340px"></div>
        </div>`;

      const opts = {responsive:true, displaylogo:false, modeBarButtonsToRemove:['lasso2d','select2d']};
      const DL = darkLayout({height:300, margin:{l:60,r:18,t:12,b:60}});

      // Day bar chart
      const dayVals = days.map(d => byDay[d]||0);
      Plotly.newPlot('bptDayChart', [{
        x: days, y: dayVals, type: 'bar',
        marker: { color: dayVals.map(v => {
          const mx = Math.max(...dayVals,1);
          const alpha = 0.35 + 0.65*(v/mx);
          return color + Math.round(alpha*255).toString(16).padStart(2,'0');
        }), line:{width:0} },
        hovertemplate: '<b>%{x}</b><br>Avg: <b>%{y:,.0f}</b> engagements<extra></extra>',
      }], {...DL, xaxis:{...DL.xaxis,tickangle:-20}, yaxis:{...DL.yaxis,title:{text:'Avg Engagement',font:{color:'#6666a0',size:11}}}}, opts);

      // Hour line chart
      const hours = Array.from({length:24},(_,i)=>i);
      const hourVals = hours.map(h => byHour[String(h)]||0);
      const hourLabels = hours.map(h => h===0?'12am':h<12?h+'am':h===12?'12pm':(h-12)+'pm');
      Plotly.newPlot('bptHourChart', [{
        x: hourLabels, y: hourVals, type: 'scatter', mode: 'lines+markers',
        line: {color, width:3, shape:'spline', smoothing:.8},
        marker: {size:7, color, line:{color:'#080812',width:1.5}},
        fill: 'tozeroy', fillcolor: color+'22',
        hovertemplate: '<b>%{x}</b><br>Avg: <b>%{y:,.0f}</b><extra></extra>',
      }], {...DL, xaxis:{...DL.xaxis,tickangle:-35,nticks:12}, yaxis:{...DL.yaxis,title:{text:'Avg Engagement',font:{color:'#6666a0',size:11}}}}, opts);

      // Heatmap
      const hDays  = heatmap.days  || days;
      const hHours = (heatmap.hours||[]).map(h => h===0?'12am':h<12?h+'am':h===12?'12pm':(h-12)+'pm');
      const hVals  = heatmap.values || [];
      Plotly.newPlot('bptHeatmap', [{
        z: hVals, x: hHours, y: hDays, type: 'heatmap',
        colorscale: [[0,'rgba(8,8,18,0.3)'],[0.4,color+'44'],[0.7,color+'99'],[1,color]],
        showscale: true,
        colorbar: {tickfont:{color:'#9898c0',size:10}, outlinewidth:0, bgcolor:'rgba(0,0,0,0)'},
        hovertemplate: '<b>%{y} @ %{x}</b><br>Avg Engagement: <b>%{z:,.0f}</b><extra></extra>',
      }], {
        ...darkLayout({height:340, margin:{l:90,r:60,t:12,b:60}}),
        xaxis:{...darkLayout().xaxis,tickangle:-40,tickfont:{size:9}},
        yaxis:{...darkLayout().yaxis,tickfont:{size:11}},
      }, opts);

      setTabPill('pill-besttime', bestDay?bestDay[0]:null);
    } catch(err) {
      if (err.name==='AbortError') return;
      const cont=$('bptContent');
      if (cont) cont.innerHTML = `<div class="error-msg">⚠️ ${err.message}</div>`;
    }
  }

  $$('.bpt-tab').forEach(btn => btn.addEventListener('click', () => {
    $$('.bpt-tab').forEach(b=>b.classList.remove('active'));
    btn.classList.add('active');
    bptPlat = btn.dataset.plat;
    renderBPT(bptPlat);
  }));

  await renderBPT(bptPlat);
}

/* ================================================================
   PLATFORM COMPARISON
   ================================================================ */
async function loadPlatformComparison(signal) {
  const ca = $('chartArea');
  ca.innerHTML = makeSpinner('Comparing platforms…');
  try {
    const data = await api('/analysis/platform-comparison', {}, signal);
    const m = data.metrics || {};
    const plats = ['facebook','instagram','youtube'];
    const labels = ['Facebook','Instagram','YouTube'];
    const colors  = ['#4267B2','#E1306C','#FF4040'];
    const emojis  = ['📘','📸','▶️'];

    // Stat cards
    const statKeys = [
      { key:'followers',       label:'Followers/Subscribers', icon:'👥', fmt:fmtNum },
      { key:'posts',           label:'Posts Analysed',        icon:'📝', fmt:v=>v },
      { key:'total_engagement',label:'Total Engagement',      icon:'❤️', fmt:fmtNum },
      { key:'avg_engagement',  label:'Avg Engagement/Post',   icon:'📊', fmt:v=>fmtNum(Math.round(v)) },
      { key:'engagement_rate', label:'Engagement Rate',       icon:'🎯', fmt:v=>v.toFixed(4)+'%' },
      { key:'avg_reach',       label:'Avg Reach/Post',        icon:'📡', fmt:v=>fmtNum(Math.round(v)) },
    ];

    const cardsHtml = plats.map((p,i) => {
      const d = m[p];
      if (!d) return `<div class="pc-platform-card" style="--pc:${colors[i]}"><div class="pc-platform-head">${emojis[i]} ${labels[i]}</div><div class="pc-no-data">No data</div></div>`;
      const statsHtml = statKeys.map(sk => `
        <div class="pc-stat-row">
          <span class="pc-stat-icon">${sk.icon}</span>
          <span class="pc-stat-label">${sk.label}</span>
          <span class="pc-stat-val">${sk.fmt(d[sk.key]||0)}</span>
        </div>`).join('');
      return `
        <div class="pc-platform-card" style="--pc:${colors[i]}">
          <div class="pc-platform-head">${emojis[i]} <span>${labels[i]}</span>
            <span class="pc-live-dot">● Live</span>
          </div>
          ${statsHtml}
        </div>`;
    }).join('');

    ca.innerHTML = `
      <div class="pc-cards-row">${cardsHtml}</div>
      <div class="charts-2col">
        <div class="chart-card">
          <div class="chart-header"><span class="chart-title">🕸️ Multi-Metric Radar</span><span class="chart-badge">normalised scores</span></div>
          <div id="pcRadar" style="min-height:380px"></div>
        </div>
        <div class="chart-card">
          <div class="chart-header"><span class="chart-title">📊 Total Engagement Comparison</span><span class="chart-badge">all platforms</span></div>
          <div id="pcBar" class="plotly-container"></div>
        </div>
      </div>
      <div class="charts-2col">
        <div class="chart-card">
          <div class="chart-header"><span class="chart-title">🎯 Engagement Rate (%)</span></div>
          <div id="pcRate" class="plotly-container"></div>
        </div>
        <div class="chart-card">
          <div class="chart-header"><span class="chart-title">📡 Avg Reach per Post</span></div>
          <div id="pcReach" class="plotly-container"></div>
        </div>
      </div>`;

    const opts = {responsive:true,displaylogo:false,modeBarButtonsToRemove:['lasso2d','select2d']};
    const DL = darkLayout({height:320,margin:{l:52,r:18,t:12,b:60}});

    // Radar
    const radarMetrics = ['Total Engagement','Avg Engagement','Engagement Rate','Avg Reach','Posts'];
    const radarKeys    = ['total_engagement','avg_engagement','engagement_rate','avg_reach','posts'];
    const radarTraces  = plats.map((p,i) => {
      const d = m[p] || {};
      const maxVals = radarKeys.map(k => Math.max(...plats.map(pp=>(m[pp]||{})[k]||0),1));
      const vals = radarKeys.map((k,j) => (d[k]||0)/maxVals[j]*100);
      return {
        type:'scatterpolar', r:[...vals,vals[0]], theta:[...radarMetrics,radarMetrics[0]],
        fill:'toself', name:labels[i],
        line:{color:colors[i],width:2}, fillcolor:colors[i]+'28',
        hovertemplate:'<b>'+labels[i]+'</b><br>%{theta}: %{r:.1f}%<extra></extra>',
      };
    });
    Plotly.newPlot('pcRadar', radarTraces, {
      ...darkLayout({height:380,margin:{l:30,r:30,t:40,b:30}}),
      polar:{
        bgcolor:'rgba(0,0,0,0)',
        radialaxis:{gridcolor:'rgba(255,255,255,.07)',tickfont:{size:9,color:'#6666a0'},ticksuffix:'%',range:[0,105]},
        angularaxis:{gridcolor:'rgba(255,255,255,.07)',tickfont:{size:11,color:'#c0c0e0'}},
      },
      showlegend:true,
      legend:{bgcolor:'rgba(0,0,0,0)',font:{color:'#c0c0e0',size:12},orientation:'h',x:.5,xanchor:'center',y:-.06},
    }, opts);

    // Bar — total engagement
    const engVals = plats.map(p=>(m[p]||{}).total_engagement||0);
    Plotly.newPlot('pcBar', [{
      x:labels, y:engVals, type:'bar',
      marker:{color:colors, opacity:.85, line:{width:0}},
      hovertemplate:'<b>%{x}</b><br>%{y:,} total<extra></extra>',
      text:engVals.map(fmtNum), textposition:'outside', textfont:{color:'#c0c0e0',size:11},
    }], {...DL, yaxis:{...DL.yaxis,title:{text:'Total Engagement',font:{color:'#6666a0',size:11}}}}, opts);

    // Engagement rate
    const rateVals = plats.map(p=>(m[p]||{}).engagement_rate||0);
    Plotly.newPlot('pcRate', [{
      x:labels, y:rateVals, type:'bar',
      marker:{color:colors.map((c,i)=>c+(rateVals[i]===Math.max(...rateVals)?'ff':'99')), line:{width:0}},
      hovertemplate:'<b>%{x}</b><br>%{y:.4f}%<extra></extra>',
      text:rateVals.map(v=>v.toFixed(4)+'%'), textposition:'outside', textfont:{color:'#c0c0e0',size:11},
    }], {...DL, yaxis:{...DL.yaxis,title:{text:'Engagement Rate (%)',font:{color:'#6666a0',size:11}}}}, opts);

    // Reach
    const reachVals = plats.map(p=>(m[p]||{}).avg_reach||0);
    Plotly.newPlot('pcReach', [{
      x:labels, y:reachVals, type:'bar',
      marker:{color:colors, opacity:.75, line:{width:0}},
      hovertemplate:'<b>%{x}</b><br>Avg reach: %{y:,.0f}<extra></extra>',
      text:reachVals.map(v=>fmtNum(Math.round(v))), textposition:'outside', textfont:{color:'#c0c0e0',size:11},
    }], {...DL, yaxis:{...DL.yaxis,title:{text:'Avg Reach / Post',font:{color:'#6666a0',size:11}}}}, opts);

    setTabPill('pill-platformcomparison','3 platforms');
  } catch(err) {
    if (err.name==='AbortError') return;
    ca.innerHTML = `<div class="error-msg">⚠️ ${err.message}</div>`;
  }
}

/* ================================================================
   REACH ANALYSIS
   ================================================================ */
async function loadReachAnalysis(signal) {
  const ca = $('chartArea');
  ca.innerHTML = makeSpinner('Loading reach data…');
  try {
    const data = await api('/analysis/reach', {}, signal);
    const timeline = data.timeline || [];
    const summaries = data.summaries || {};
    const plats = ['facebook','instagram','youtube'];
    const labels = ['Facebook','Instagram','YouTube'];
    const colors  = ['#4267B2','#E1306C','#FF4040'];

    if (!timeline.length) { ca.innerHTML = emptyState('No reach data available'); return; }

    // Summary stat cards
    const sumCards = plats.map((p,i) => {
      const s = summaries[p] || {};
      return `
        <div class="ra-sum-card" style="--rc:${colors[i]}">
          <div class="ra-sum-head">${['📘','📸','▶️'][i]} ${labels[i]}</div>
          <div class="ra-sum-grid">
            <div class="ra-sum-kpi"><span class="ra-sum-val">${fmtNum(s.total_reach||0)}</span><span class="ra-sum-lbl">Total Reach</span></div>
            <div class="ra-sum-kpi"><span class="ra-sum-val">${fmtNum(s.total_impressions||0)}</span><span class="ra-sum-lbl">Impressions</span></div>
            <div class="ra-sum-kpi"><span class="ra-sum-val">${(s.reach_to_impression_ratio||0).toFixed(1)}%</span><span class="ra-sum-lbl">Reach/Imp Ratio</span></div>
            <div class="ra-sum-kpi"><span class="ra-sum-val">${(s.engagement_to_reach_ratio||0).toFixed(3)}%</span><span class="ra-sum-lbl">Eng/Reach Ratio</span></div>
          </div>
        </div>`;
    }).join('');

    ca.innerHTML = `
      <div class="ra-sum-row">${sumCards}</div>
      <div class="chart-card full-width">
        <div class="chart-header"><span class="chart-title">📡 Reach Over Time — All Platforms</span><span class="chart-badge">${timeline.length} posts</span></div>
        <div id="raTimeline" style="min-height:340px"></div>
      </div>
      <div class="charts-2col">
        <div class="chart-card">
          <div class="chart-header"><span class="chart-title">🔍 Reach vs Impressions</span><span class="chart-badge">scatter</span></div>
          <div id="raScatter" class="plotly-container"></div>
        </div>
        <div class="chart-card">
          <div class="chart-header"><span class="chart-title">📊 Total Reach Distribution</span><span class="chart-badge">by platform</span></div>
          <div id="raDonut" class="plotly-container"></div>
        </div>
      </div>
      <div class="chart-card full-width">
        <div class="chart-header"><span class="chart-title">⚡ Engagement-to-Reach Funnel</span><span class="chart-badge">conversion rates</span></div>
        <div id="raFunnel" style="min-height:320px"></div>
      </div>`;

    const opts = {responsive:true,displaylogo:false,modeBarButtonsToRemove:['lasso2d','select2d']};
    const DL = darkLayout({height:340,margin:{l:60,r:18,t:12,b:60}});

    // Timeline — reach per platform
    const timeTraces = plats.map((p,i) => {
      const rows = timeline.filter(r=>r.platform===p).slice(-30);
      return {
        x: rows.map(r=>r.date), y: rows.map(r=>r.reach),
        name: labels[i], type:'scatter', mode:'lines+markers',
        line:{color:colors[i],width:2.5,shape:'spline',smoothing:.8},
        marker:{size:6,color:colors[i],line:{color:'#080812',width:1}},
        fill:'tozeroy', fillcolor:colors[i]+'14',
        hovertemplate:'<b>%{x}</b><br>Reach: <b>%{y:,}</b><extra>'+labels[i]+'</extra>',
      };
    });
    Plotly.newPlot('raTimeline', timeTraces, {
      ...DL,
      yaxis:{...DL.yaxis,title:{text:'Reach',font:{color:'#6666a0',size:11}}},
      xaxis:{...DL.xaxis,tickangle:-25,tickfont:{size:10}},
    }, opts);

    // Scatter — reach vs impressions
    const scatterTraces = plats.map((p,i) => {
      const rows = timeline.filter(r=>r.platform===p);
      return {
        x:rows.map(r=>r.reach), y:rows.map(r=>r.impressions),
        name:labels[i], mode:'markers',
        marker:{size:9,color:colors[i],opacity:.75,line:{color:'#080812',width:1}},
        hovertemplate:'Reach: %{x:,}<br>Impressions: %{y:,}<extra>'+labels[i]+'</extra>',
      };
    });
    Plotly.newPlot('raScatter', scatterTraces, {
      ...DL,
      xaxis:{...DL.xaxis,title:{text:'Reach',font:{color:'#6666a0',size:11}}},
      yaxis:{...DL.yaxis,title:{text:'Impressions',font:{color:'#6666a0',size:11}}},
    }, opts);

    // Donut — total reach share
    const reachTotals = plats.map(p=>(summaries[p]||{}).total_reach||0);
    Plotly.newPlot('raDonut', [{
      values:reachTotals, labels, type:'pie', hole:.6,
      marker:{colors,line:{color:'#080812',width:3}},
      textinfo:'none',
      hovertemplate:'<b>%{label}</b><br>%{value:,} reach<br>%{percent}<extra></extra>',
      pull:[.04,.04,.04],
    }], {
      ...darkLayout({height:340,margin:{l:10,r:10,t:10,b:40}}),showlegend:true,
      legend:{bgcolor:'rgba(0,0,0,0)',font:{color:'#c0c0e0',size:12},orientation:'h',x:.5,xanchor:'center',y:-.06},
      annotations:[{x:.5,y:.5,xref:'paper',yref:'paper',text:'<b>'+fmtNum(reachTotals.reduce((a,b)=>a+b,0))+'</b>',showarrow:false,font:{size:18,color:'#f0f0ff',family:'Space Grotesk,sans-serif'}}],
    }, opts);

    // Funnel — impressions → reach → engagement
    const funnelTraces = plats.map((p,i) => {
      const s = summaries[p] || {};
      return {
        type:'funnel', name:labels[i],
        y:['Impressions','Reach','Engagement'],
        x:[s.total_impressions||0, s.total_reach||0, s.total_engagement||0],
        marker:{color:colors[i], opacity:.82},
        textinfo:'value+percent initial',
        hoverinfo:'name+x+percent initial',
      };
    });
    Plotly.newPlot('raFunnel', funnelTraces, {
      ...darkLayout({height:320,margin:{l:120,r:80,t:12,b:40}}),
      funnelmode:'group',
      showlegend:true,
      legend:{bgcolor:'rgba(0,0,0,0)',font:{color:'#c0c0e0',size:12},orientation:'h',x:.5,xanchor:'center',y:-.05},
    }, opts);

    setTabPill('pill-reachanalysis', timeline.length);
  } catch(err) {
    if (err.name==='AbortError') return;
    ca.innerHTML = `<div class="error-msg">⚠️ ${err.message}</div>`;
  }
}

/* ================================================================
   RECENT POST ANALYSIS
   ================================================================ */
async function loadRecentPosts(signal) {
  const ca = $('chartArea');
  ca.innerHTML = makeSpinner('Fetching recent posts…');
  try {
    const data = await api('/analysis/recent-posts', {limit:15}, signal);
    const posts = data.posts || [];
    const colors  = {facebook:'#4267B2', instagram:'#E1306C', youtube:'#FF4040'};
    const emojis  = {facebook:'📘', instagram:'📸', youtube:'▶️'};
    const platLabel = {facebook:'Facebook', instagram:'Instagram', youtube:'YouTube'};

    if (!posts.length) { ca.innerHTML = emptyState('No recent posts available'); return; }

    setTabPill('pill-recentposts', posts.length);

    // Post cards
    const cardsHtml = posts.slice(0,12).map((p,i) => {
      const clr = colors[p.platform]||'#667eea';
      const emoji = emojis[p.platform]||'📄';
      const lbl = platLabel[p.platform]||p.platform;
      const mediaTag = p.media_type ? `<span class="rp-media-badge">${p.media_type}</span>` : '';
      return `
        <div class="rp-post-card" style="--pc:${clr}" id="rp-card-${i}">
          <div class="rp-card-top">
            <div class="rp-platform-pill" style="background:${clr}22;border:1px solid ${clr}44;color:${clr}">${emoji} ${lbl}</div>
            ${mediaTag}
            <span class="rp-date">${p.date} ${p.time?p.time.slice(0,5):''}</span>
          </div>
          <div class="rp-content">${p.content ? `<p class="rp-excerpt">${p.content.slice(0,120)}${p.content.length>120?'…':''}</p>` : '<p class="rp-no-content">No caption</p>'}</div>
          <div class="rp-metrics">
            <div class="rp-metric"><span class="rp-mv">${fmtNum(p.engagement)}</span><span class="rp-ml">Engagement</span></div>
            <div class="rp-metric"><span class="rp-mv">${fmtNum(p.reach)}</span><span class="rp-ml">Reach</span></div>
            <div class="rp-metric"><span class="rp-mv">${fmtNum(p.reactions)}</span><span class="rp-ml">❤️</span></div>
            <div class="rp-metric"><span class="rp-mv">${fmtNum(p.comments)}</span><span class="rp-ml">💬</span></div>
          </div>
          <div class="rp-bar-track"><div class="rp-bar-fill" style="width:0%;background:${clr}" id="rp-bar-${i}"></div></div>
          ${p.url?`<a class="rp-link" href="${p.url}" target="_blank">View post ↗</a>`:''}
        </div>`;
    }).join('');

    // Charts
    const sorted = [...posts].sort((a,b)=>b.engagement-a.engagement);
    const top12 = sorted.slice(0,12);

    ca.innerHTML = `
      <div class="rp-cards-grid">${cardsHtml}</div>
      <div class="charts-2col">
        <div class="chart-card">
          <div class="chart-header"><span class="chart-title">🏆 Top Posts by Engagement</span><span class="chart-badge">${posts.length} posts</span></div>
          <div id="rpBar" class="plotly-container"></div>
        </div>
        <div class="chart-card">
          <div class="chart-header"><span class="chart-title">📅 Engagement Over Time</span><span class="chart-badge">all platforms</span></div>
          <div id="rpTimeline" class="plotly-container"></div>
        </div>
      </div>
      <div class="charts-2col">
        <div class="chart-card">
          <div class="chart-header"><span class="chart-title">📊 Reactions vs Comments vs Shares</span></div>
          <div id="rpBreakdown" class="plotly-container"></div>
        </div>
        <div class="chart-card">
          <div class="chart-header"><span class="chart-title">🥧 Engagement Share by Platform</span></div>
          <div id="rpPie" class="plotly-container"></div>
        </div>
      </div>`;

    // Animate bar fills
    const maxEng = Math.max(...posts.map(p=>p.engagement),1);
    requestAnimationFrame(() => {
      posts.slice(0,12).forEach((p,i) => {
        const b = $(`rp-bar-${i}`);
        if (b) setTimeout(()=>b.style.width=(p.engagement/maxEng*100)+'%',80+i*40);
      });
    });

    const opts = {responsive:true,displaylogo:false,modeBarButtonsToRemove:['lasso2d','select2d']};
    const DL = darkLayout({height:320,margin:{l:52,r:18,t:12,b:60}});

    // Horizontal bar — top 12
    Plotly.newPlot('rpBar', [{
      x: top12.map(p=>p.engagement),
      y: top12.map(p=>`${emojis[p.platform]||'📄'} ${p.content.slice(0,28)||p.date}`),
      type:'bar', orientation:'h',
      marker:{color:top12.map(p=>colors[p.platform]||'#667eea'), opacity:.85, line:{width:0}},
      hovertemplate:'<b>%{y}</b><br>Engagement: <b>%{x:,}</b><extra></extra>',
    }], {...DL,xaxis:{...DL.xaxis,title:{text:'Engagement',font:{color:'#6666a0',size:11}}},yaxis:{...DL.yaxis,autorange:'reversed',tickfont:{size:10}}}, opts);

    // Timeline
    ['facebook','instagram','youtube'].forEach((p,i) => {
      const rows = [...posts].filter(r=>r.platform===p).sort((a,b)=>a.date.localeCompare(b.date));
      if (!rows.length) return;
    });
    const timeTraces = ['facebook','instagram','youtube'].map((p,i) => {
      const rows = [...posts].filter(r=>r.platform===p).sort((a,b)=>a.date.localeCompare(b.date));
      return {
        x:rows.map(r=>r.date+' '+r.time.slice(0,5)),
        y:rows.map(r=>r.engagement),
        name:platLabel[p], type:'scatter', mode:'lines+markers',
        line:{color:colors[p],width:2.5,shape:'spline'},
        marker:{size:7,color:colors[p],line:{color:'#080812',width:1}},
        hovertemplate:'<b>%{x}</b><br>%{y:,}<extra>'+platLabel[p]+'</extra>',
      };
    });
    Plotly.newPlot('rpTimeline', timeTraces, {
      ...DL,
      yaxis:{...DL.yaxis,title:{text:'Engagement',font:{color:'#6666a0',size:11}}},
      xaxis:{...DL.xaxis,tickangle:-30,tickfont:{size:10}},
    }, opts);

    // Breakdown grouped bar
    Plotly.newPlot('rpBreakdown', [
      {name:'Reactions', x:top12.map(p=>p.content.slice(0,22)||p.date), y:top12.map(p=>p.reactions), type:'bar', marker:{color:'rgba(102,126,234,.85)',line:{width:0}}},
      {name:'Comments',  x:top12.map(p=>p.content.slice(0,22)||p.date), y:top12.map(p=>p.comments),  type:'bar', marker:{color:'rgba(240,147,251,.85)',line:{width:0}}},
      {name:'Shares',    x:top12.map(p=>p.content.slice(0,22)||p.date), y:top12.map(p=>p.shares),    type:'bar', marker:{color:'rgba(79,172,254,.85)',line:{width:0}}},
    ], {...DL, barmode:'group', xaxis:{...DL.xaxis,tickangle:-35,tickfont:{size:8}}}, opts);

    // Pie by platform
    const platEngs = ['facebook','instagram','youtube'].map(p=>posts.filter(r=>r.platform===p).reduce((s,r)=>s+r.engagement,0));
    Plotly.newPlot('rpPie', [{
      values:platEngs, labels:['Facebook','Instagram','YouTube'], type:'pie', hole:.55,
      marker:{colors:['#4267B2','#E1306C','#FF4040'],line:{color:'#080812',width:3}},
      textinfo:'label+percent',
      hovertemplate:'<b>%{label}</b><br>%{value:,}<br>%{percent}<extra></extra>',
    }], {
      ...darkLayout({height:320,margin:{l:10,r:10,t:10,b:40}}),showlegend:false,
    }, opts);

  } catch(err) {
    if (err.name==='AbortError') return;
    ca.innerHTML = `<div class="error-msg">⚠️ ${err.message}</div>`;
  }
}

/* ================================================================
   BOOT
   ================================================================ */
document.addEventListener('DOMContentLoaded', ()=>{
  startClock();
  initTabs();
  initPlatformSelector();
  initTimeRange();
  initMenuToggle();
  initRefresh();
  updateTitle();
  // Initial load — use full-page loading overlay only for very first load
  showLoadingOverlay(true,'Loading your dashboard');
  loadTab('overview').finally(()=>showLoadingOverlay(false));
});
