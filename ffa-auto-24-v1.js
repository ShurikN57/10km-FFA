(async()=>{
'use strict';

const DB='FFA_BILANS_AUTO_V2';
const STORE='pages';
const YEARS=['2024','2025','2026'];
const SEXES=['M','F'];
const DISTANCES=[
  {key:'5k',label:'5 km',event:'252',file:'ffa_5km_2024_2026.json.gz'},
  {key:'10k',label:'10 km',event:'261',file:'ffa_10km_2024_2026.json.gz'},
  {key:'semi',label:'Semi-marathon',event:'271',file:'ffa_semi_2024_2026.json.gz'},
  {key:'marathon',label:'Marathon',event:'295',file:'ffa_marathon_2024_2026.json.gz'}
];
const MODE=window.__FFA_AUTO_MODE||'collect';
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const clean=s=>String(s||'').replace(/\s+/g,' ').trim();

function openDb(){
  return new Promise((ok,no)=>{
    const q=indexedDB.open(DB,1);
    q.onupgradeneeded=()=>{
      const d=q.result;
      if(!d.objectStoreNames.contains(STORE)) d.createObjectStore(STORE,{keyPath:'key'});
    };
    q.onsuccess=()=>ok(q.result);
    q.onerror=()=>no(q.error);
  });
}
function getAll(db){
  return new Promise((ok,no)=>{
    const q=db.transaction(STORE,'readonly').objectStore(STORE).getAll();
    q.onsuccess=()=>ok(q.result||[]);
    q.onerror=()=>no(q.error);
  });
}
function getOne(db,key){
  return new Promise(ok=>{
    const q=db.transaction(STORE,'readonly').objectStore(STORE).get(key);
    q.onsuccess=()=>ok(q.result||null);
    q.onerror=()=>ok(null);
  });
}
function putOne(db,obj){
  return new Promise((ok,no)=>{
    const tx=db.transaction(STORE,'readwrite');
    tx.objectStore(STORE).put(obj);
    tx.oncomplete=ok;
    tx.onerror=()=>no(tx.error);
  });
}
function overlay(){
  let root=document.getElementById('ffa_auto_overlay');
  if(root) root.remove();
  root=document.createElement('div');
  root.id='ffa_auto_overlay';
  root.style='position:fixed;z-index:2147483647;right:18px;bottom:18px;width:430px;max-width:92vw;background:#111;color:#fff;padding:16px;border-radius:12px;font:14px system-ui;box-shadow:0 8px 30px #0008';
  root.innerHTML='<b>FFA — collecte automatique 24 bilans</b><div id="ffa_auto_txt" style="margin-top:8px;white-space:pre-line;max-height:52vh;overflow:auto">Préparation…</div><button id="ffa_auto_stop" style="margin-top:10px;padding:8px 12px">Arrêter</button>';
  document.body.appendChild(root);
  return {root,txt:root.querySelector('#ffa_auto_txt'),stop:root.querySelector('#ffa_auto_stop')};
}
function parseRows(html,page,url){
  const d=new DOMParser().parseFromString(html,'text/html');
  const out=[];
  for(const tr of d.querySelectorAll('tr')){
    const td=[...tr.children].filter(x=>x.tagName==='TD');
    if(td.length<9) continue;
    const place=clean(td[0].innerText);
    const performance=clean(td[1].innerText);
    const name=clean(td[2].innerText);
    if(!name||!performance||!/^(?:\d+|-)$/.test(place)) continue;
    out.push([
      performance,
      name,
      clean(td[3].innerText),
      clean(td[4].innerText),
      clean(td[5].innerText),
      clean(td[6].innerText),
      clean(td[7].innerText),
      clean(td[8].innerText)
    ]);
  }
  return out;
}
async function fetchText(url,txt){
  for(let a=1;a<=5;a++){
    try{
      const r=await fetch(url,{credentials:'include',cache:'no-store'});
      if(!r.ok) throw new Error('HTTP '+r.status);
      return await r.text();
    }catch(e){
      if(txt) txt.textContent='Erreur réseau — tentative '+a+'/5';
      await sleep(1200*a);
    }
  }
  throw new Error('Échec réseau après 5 tentatives');
}
function detectTotalPages(html){
  let m=html.match(/Page\s*>\s*0*1\s*\/\s*0*(\d+)\s*</i);
  if(!m) m=html.match(/Page[^0-9]*0*1\s*\/\s*0*(\d+)/i);
  if(m) return +m[1];
  const nums=[...html.matchAll(/frmposition=(\d+)/gi)].map(x=>+x[1]);
  return nums.length?Math.max(...nums)+1:null;
}
function baseUrlFromLocation(){
  const u=new URL(location.href);
  if(!/^(www\.)?athle\.fr$/i.test(u.hostname)||u.searchParams.get('frmbase')!=='bilans'){
    throw new Error("Ouvre d'abord une page FFA Bilans sur athle.fr.");
  }
  return u;
}
function applyDatasetParams(base,dist,year,sex,pos){
  const u=new URL(base.href);
  u.searchParams.set('frmpostback','true');
  u.searchParams.set('frmbase','bilans');
  u.searchParams.set('frmmode','1');
  u.searchParams.set('frmespace','0');
  u.searchParams.set('frmannee',year);
  u.searchParams.set('frmepreuve',dist.event);
  u.searchParams.set('frmsexe',sex);
  u.searchParams.set('frmcategorie','');
  u.searchParams.set('frmdepartement','');
  u.searchParams.set('frmligue','');
  u.searchParams.set('frmnationalite','');
  u.searchParams.set('frmvent','VR');
  u.searchParams.set('frmamaxi','');
  u.searchParams.set('frmposition',String(pos));
  return u;
}
async function downloadGzip(obj,name){
  if(typeof CompressionStream==='undefined') throw new Error('CompressionStream indisponible dans ce navigateur.');
  const text=JSON.stringify(obj);
  const stream=new Blob([text],{type:'application/json'}).stream().pipeThrough(new CompressionStream('gzip'));
  const gz=await new Response(stream).blob();
  const a=document.createElement('a');
  a.href=URL.createObjectURL(gz);
  a.download=name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(()=>URL.revokeObjectURL(a.href),2000);
}

async function runCollect(){
  const base=baseUrlFromLocation();
  const ui=overlay();
  let stopped=false;
  ui.stop.onclick=()=>{stopped=true;};
  const db=await openDb();

  try{
    const combos=[];
    for(const dist of DISTANCES) for(const year of YEARS) for(const sex of SEXES) combos.push({dist,year,sex});
    let comboIndex=0;

    for(const c of combos){
      comboIndex++;
      if(stopped) break;
      const sexLabel=c.sex==='M'?'Hommes':'Femmes';
      const prefix=`${comboIndex}/24 · ${c.dist.label} · ${c.year} · ${sexLabel}`;
      const firstUrl=applyDatasetParams(base,c.dist,c.year,c.sex,0);
      ui.txt.textContent=prefix+'\nDétection du nombre de pages…';

      const firstHtml=await fetchText(firstUrl.href,ui.txt);
      const total=detectTotalPages(firstHtml);
      if(!total||total<1) throw new Error(prefix+' : nombre de pages indétectable.');

      const firstKey=[c.year,c.sex,c.dist.event,0].join('|');
      const old0=await getOne(db,firstKey);
      let done=0,rowsCount=0;

      if(old0){
        done++;
        rowsCount+=Array.isArray(old0.rows)?old0.rows.length:0;
      }else{
        const rows=parseRows(firstHtml,0,firstUrl.href);
        if(!rows.length) throw new Error(prefix+' : page 1 non reconnue.');
        await putOne(db,{key:firstKey,year:c.year,sex:c.sex,event:c.dist.event,distance:c.dist.key,label:c.dist.label,page:0,total_pages:total,rows,collected_at:new Date().toISOString()});
        done++;
        rowsCount+=rows.length;
      }

      for(let p=1;p<total&&!stopped;p++){
        const key=[c.year,c.sex,c.dist.event,p].join('|');
        const old=await getOne(db,key);
        if(old){
          done++;
          rowsCount+=Array.isArray(old.rows)?old.rows.length:0;
          ui.txt.textContent=prefix+`\n${done}/${total} pages déjà présentes · ${rowsCount} lignes`;
          continue;
        }
        const u=applyDatasetParams(base,c.dist,c.year,c.sex,p);
        ui.txt.textContent=prefix+`\nPage ${p+1}/${total}…\n${done}/${total} pages · ${rowsCount} lignes`;
        const html=await fetchText(u.href,ui.txt);
        const rows=parseRows(html,p,u.href);
        if(!rows.length) throw new Error(prefix+` : 0 ligne reconnue page ${p+1}.`);
        await putOne(db,{key,year:c.year,sex:c.sex,event:c.dist.event,distance:c.dist.key,label:c.dist.label,page:p,total_pages:total,rows,collected_at:new Date().toISOString()});
        done++;
        rowsCount+=rows.length;
        await sleep(250);
      }
    }

    ui.txt.textContent=stopped
      ? 'Collecte arrêtée.\nRelance le même favori pour reprendre automatiquement.'
      : 'COLLECTE TERMINÉE ✓\nLes 24 bilans sont enregistrés.\nLance maintenant le favori ÉTAT puis EXPORT .JSON.GZ.';
    if(!stopped) alert('Collecte FFA terminée : 24 bilans.');
  } finally {
    db.close();
  }
}

async function runStatus(){
  const db=await openDb();
  try{
    const all=await getAll(db);
    const lines=[];
    let okCount=0;
    for(const dist of DISTANCES){
      for(const year of YEARS){
        for(const sex of SEXES){
          const a=all.filter(x=>String(x.event)===dist.event&&String(x.year)===year&&x.sex===sex);
          const total=a.length?Number(a[0].total_pages||0):0;
          const rows=a.reduce((n,x)=>n+(Array.isArray(x.rows)?x.rows.length:0),0);
          const ok=total>0&&a.length===total;
          if(ok) okCount++;
          lines.push(`${ok?'✓':'•'} ${dist.label} ${year} ${sex} : ${a.length}/${total||'?'} pages · ${rows} lignes`);
        }
      }
    }
    alert(`ÉTAT FFA — ${okCount}/24 bilans complets\n\n`+lines.join('\n'));
  } finally {
    db.close();
  }
}

async function runExport(){
  const db=await openDb();
  try{
    const all=await getAll(db);
    const schema=['Performance','Nom','Club','Ligue','Dep.','Infos','Date','Lieu'];

    for(const dist of DISTANCES){
      const datasets=[];
      for(const year of YEARS){
        for(const sex of SEXES){
          const pages=all
            .filter(x=>String(x.event)===dist.event&&String(x.year)===year&&x.sex===sex)
            .sort((a,b)=>Number(a.page)-Number(b.page));
          if(!pages.length) throw new Error(`${dist.label} ${year} ${sex} : aucune donnée.`);
          const total=Number(pages[0].total_pages||0);
          if(!total||pages.length!==total) throw new Error(`${dist.label} ${year} ${sex} incomplet : ${pages.length}/${total||'?'} pages.`);
          const rows=pages.flatMap(p=>Array.isArray(p.rows)?p.rows:[]);
          datasets.push({year:Number(year),sex,rows});
        }
      }

      const payload={
        generated_at:new Date().toISOString(),
        distance:dist.label,
        event:dist.event,
        schema,
        datasets
      };
      await downloadGzip(payload,dist.file);
      await sleep(700);
    }
    alert('Export terminé : 4 fichiers .json.gz générés.');
  } finally {
    db.close();
  }
}

if(MODE==='collect') await runCollect();
else if(MODE==='status') await runStatus();
else if(MODE==='export') await runExport();
else throw new Error('Mode inconnu : '+MODE);

})().catch(e=>alert('FFA AUTO : '+(e&&e.message?e.message:e)));