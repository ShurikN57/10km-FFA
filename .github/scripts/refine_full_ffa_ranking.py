from pathlib import Path

FILES=[Path('mobile.html'),Path('app base.html')]

OLD_MODE='''    <div style="display:flex;gap:6px;margin-bottom:8px">
      <button type="button" class="ffaFullModeBtn" data-mode="general" style="flex:1;padding:8px 5px;font-size:12px">Général</button>
      <button type="button" class="ffaFullModeBtn" data-mode="sex" style="flex:1;padding:8px 5px;font-size:12px">H/F</button>
      <button type="button" class="ffaFullModeBtn" data-mode="category" style="flex:1;padding:8px 5px;font-size:12px">Catégorie</button>
    </div>
'''

OLD_HEAD='''      <h2 style="margin:0;font-size:16px">Classement FFA complet</h2>
      <button type="button" id="closeFfaRanking" style="padding:7px 10px;font-size:12px">Fermer</button>'''
NEW_HEAD='''      <h2 style="margin:0;font-size:17px">Classement FFA</h2>
      <button type="button" id="closeFfaRanking" aria-label="Fermer" style="padding:5px 9px;font-size:12px;font-weight:600;opacity:.8">Fermer</button>'''

OLD_FILTER_END='''      <input id="ffaFullMaxPb" inputmode="numeric" placeholder="PB max, ex 35:00" style="width:100%;padding:10px;border-radius:9px;border:1px solid var(--line);background:var(--panel2);color:var(--text)">
    </div>
    <div id="ffaFullMsg" class="msg" style="margin:4px 0 8px"></div>'''
NEW_FILTER_END='''      <input id="ffaFullMaxPb" inputmode="numeric" placeholder="PB max, ex 35:00" style="width:100%;padding:10px;border-radius:9px;border:1px solid var(--line);background:var(--panel2);color:var(--text)">
    </div>
    <button type="button" id="ffaFullReset" style="width:100%;padding:8px 10px;margin-bottom:7px;font-size:12px;font-weight:600">Réinitialiser les filtres</button>
    <div id="ffaFullMsg" class="msg" style="margin:2px 0 8px"></div>'''

NEW_JS=r'''let ffaFullPage=0;
const FFA_FULL_PAGE_SIZE=100;
function parsePbLimit(v){
  v=String(v||"").trim().replace("'",":").replace('"','');
  if(!v) return null;
  if(/^\d+$/.test(v)) return Number(v)*60;
  const m=v.match(/^(\d{1,2})[:h](\d{1,2})$/i);
  return m ? Number(m[1])*60+Number(m[2]) : null;
}
function scopedFullRankMap(sex,cat,year){
  const scope=ffa.filter(p=>{
    if(!Number.isFinite(Number(p.pb_sec))) return false;
    if(sex && p.sexe!==sex) return false;
    if(cat && currentFfaCategory(p)!==cat) return false;
    if(year && String(p.annee_naissance||"")!==year) return false;
    return true;
  });
  const map=new Map();
  assignRanks(scope,map);
  return map;
}
function renderFullFfaRanking(resetPage=false){
  if(resetPage) ffaFullPage=0;
  const box=$("ffaFullResults"), msg=$("ffaFullMsg");
  if(!box||!msg) return;
  if(!ffaReady){ msg.textContent="Base FFA en cours de chargement…"; return; }
  const q=norm($("ffaFullSearch").value||"");
  const sex=$("ffaFullSex").value;
  const cat=$("ffaFullCategory").value;
  const year=String($("ffaFullYear").value||"").trim();
  const maxPb=parsePbLimit($("ffaFullMaxPb").value);
  const ranks=scopedFullRankMap(sex,cat,year);
  let rows=ffa.filter(p=>{
    const rank=ranks.get(p);
    if(rank==null) return false;
    if(maxPb!=null && Number(p.pb_sec)>maxPb) return false;
    if(q){
      const nk=p.name_key||nameKey(p.full_name||"");
      const toks=q.split(" ").filter(Boolean);
      if(!toks.every(t=>nk.includes(t))) return false;
    }
    return true;
  });
  rows.sort((a,b)=>{
    const ra=ranks.get(a), rb=ranks.get(b);
    return ra-rb || Number(a.pb_sec)-Number(b.pb_sec) || norm(a.full_name).localeCompare(norm(b.full_name));
  });
  const pages=Math.max(1,Math.ceil(rows.length/FFA_FULL_PAGE_SIZE));
  if(ffaFullPage>=pages) ffaFullPage=pages-1;
  const start=ffaFullPage*FFA_FULL_PAGE_SIZE;
  const slice=rows.slice(start,start+FFA_FULL_PAGE_SIZE);
  msg.textContent=rows.length.toLocaleString("fr-FR")+" athlète"+(rows.length>1?"s":"")+" · page "+(ffaFullPage+1)+"/"+pages;
  box.innerHTML=slice.length ? slice.map(p=>{
    const rank=ranks.get(p);
    const rankText=rank===1?"1er":rank+"e";
    const url=getFfaProfileUrl(p);
    const catText=currentFfaCategory(p);
    const link=url ? `<a href="${esc(url)}" target="_blank" rel="noopener" style="color:var(--accent);text-decoration:none;font-weight:700">${esc(p.full_name||"")}</a>` : `<b>${esc(p.full_name||"")}</b>`;
    const meta=[p.annee_naissance||"—",p.sexe||"",catText].filter(Boolean).join(" · ");
    return `<div style="display:grid;grid-template-columns:44px minmax(0,1fr) 76px;gap:6px;align-items:center;padding:9px 10px;border-bottom:1px solid var(--line)"><div style="font-weight:800;font-size:14px">${esc(rankText)}</div><div style="min-width:0"><div style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${link}</div><div class="small">${esc(meta)}</div></div><div style="text-align:right;font-weight:800">${esc(p.pb_chrono||"—")}</div></div>`;
  }).join("") : `<div class="msg" style="padding:12px">Aucun athlète avec ces filtres.</div>`;
  $("ffaFullPrev").disabled=ffaFullPage<=0;
  $("ffaFullNext").disabled=ffaFullPage>=pages-1;
}
const _openFfaRanking=$("openFfaRanking");
if(_openFfaRanking) _openFfaRanking.addEventListener("click",()=>{
  $("ffaRankingCard").style.display="block";
  renderFullFfaRanking(true);
  $("ffaRankingCard").scrollIntoView({behavior:"smooth",block:"start"});
});
const _closeFfaRanking=$("closeFfaRanking");
if(_closeFfaRanking) _closeFfaRanking.addEventListener("click",()=>{$("ffaRankingCard").style.display="none";});
["ffaFullSearch","ffaFullSex","ffaFullCategory","ffaFullYear","ffaFullMaxPb"].forEach(id=>{
  const el=$(id);
  if(el) el.addEventListener(id==="ffaFullSearch"||id==="ffaFullYear"||id==="ffaFullMaxPb"?"input":"change",()=>renderFullFfaRanking(true));
});
const _ffaFullReset=$("ffaFullReset");
if(_ffaFullReset) _ffaFullReset.addEventListener("click",()=>{
  $("ffaFullSearch").value="";
  $("ffaFullSex").value="";
  $("ffaFullCategory").value="";
  $("ffaFullYear").value="";
  $("ffaFullMaxPb").value="";
  renderFullFfaRanking(true);
});
const _ffaFullPrev=$("ffaFullPrev"); if(_ffaFullPrev) _ffaFullPrev.addEventListener("click",()=>{if(ffaFullPage>0){ffaFullPage--;renderFullFfaRanking(false);}});
const _ffaFullNext=$("ffaFullNext"); if(_ffaFullNext) _ffaFullNext.addEventListener("click",()=>{ffaFullPage++;renderFullFfaRanking(false);});
'''

for path in FILES:
    text=path.read_text(encoding='utf-8')
    if OLD_MODE not in text:
        raise SystemExit(f'{path}: full ranking mode buttons not found')
    text=text.replace(OLD_MODE,'',1)
    if OLD_HEAD not in text:
        raise SystemExit(f'{path}: heading not found')
    text=text.replace(OLD_HEAD,NEW_HEAD,1)
    if OLD_FILTER_END not in text:
        raise SystemExit(f'{path}: filter block not found')
    text=text.replace(OLD_FILTER_END,NEW_FILTER_END,1)
    start=text.find('let ffaFullMode="sex";')
    end=text.find('const _ffaAthleteSearch=$("ffaAthleteSearch");', start)
    if start<0 or end<0:
        raise SystemExit(f'{path}: full ranking JS block not found')
    text=text[:start]+NEW_JS+text[end:]
    path.write_text(text,encoding='utf-8')
