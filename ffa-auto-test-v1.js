(async()=>{
  const DB='FFA_BILANS_AUTO_V1', STORE='pages', YEAR='2025', EVENT='295', LABEL='Marathon', MAXP=3;
  const sleep=ms=>new Promise(r=>setTimeout(r,ms));
  const C=s=>String(s||'').replace(/\s+/g,' ').trim();
  const sec=s=>{let m=C(s).match(/(?:(\d{1,2})h)?\s*(\d{1,3})['’]\s*(\d{2})/);if(m)return +(m[1]||0)*3600+(+m[2])*60+(+m[3]);m=C(s).match(/\b(\d{1,2}):(\d{2}):(\d{2})\b/);return m?+m[1]*3600+(+m[2])*60+(+m[3]):null};
  const bid=u=>{const m=String(u||'').match(/\/athletes\/(\d+)/i);return m?m[1]:''};
  const by=i=>{const m=C(i).match(/\/\s*(\d{2,4})\b/);if(!m)return'';let y=+m[1];if(y<100)y=y>=30?1900+y:2000+y;return String(y)};
  const openDb=()=>new Promise((ok,no)=>{const q=indexedDB.open(DB,1);q.onupgradeneeded=()=>{const d=q.result;if(!d.objectStoreNames.contains(STORE))d.createObjectStore(STORE,{keyPath:'key'})};q.onsuccess=()=>ok(q.result);q.onerror=()=>no(q.error)});
  const u0=new URL(location.href);
  if(!/^(www\.)?athle\.fr$/i.test(u0.hostname)||u0.searchParams.get('frmbase')!=='bilans'){alert("Ouvre d'abord une page FFA Bilans sur athle.fr puis relance le favori.");return}
  const overlay=document.createElement('div');
  overlay.style='position:fixed;z-index:2147483647;right:20px;bottom:20px;width:410px;max-width:92vw;background:#111;color:#fff;padding:16px;border-radius:12px;font:14px system-ui;box-shadow:0 8px 30px #0008';
  overlay.innerHTML='<b>TEST FFA Marathon 2025 H/F</b><div id="ffa_test_txt" style="margin-top:8px;white-space:pre-line">Préparation…</div><button id="ffa_test_stop" style="margin-top:10px;padding:8px 12px">Arrêter</button>';
  document.body.appendChild(overlay);
  const txt=overlay.querySelector('#ffa_test_txt');let stop=false;overlay.querySelector('#ffa_test_stop').onclick=()=>stop=true;
  const parse=(html,page,url,sex)=>{const d=new DOMParser().parseFromString(html,'text/html'),out=[];for(const tr of d.querySelectorAll('tr')){const td=[...tr.children].filter(x=>x.tagName==='TD');if(td.length<9)continue;const place=C(td[0].innerText),raw=C(td[1].innerText),name=C(td[2].innerText),ps=sec(raw);if(!name||ps==null||!(/^(\d+|-)$/).test(place))continue;const a=td[2].querySelector('a[href*="/athletes/"]'),fu=a?new URL(a.getAttribute('href'),location.origin).href:'',infos=C(td[6].innerText);out.push({performance:raw,name,club:C(td[3].innerText),ligue:C(td[4].innerText),departement:C(td[5].innerText),infos,date:C(td[7].innerText),lieu:C(td[8].innerText),performance_sec:ps,birth_year:by(infos),athlete_ffa_id:bid(fu),ffa_url:fu,year:YEAR,sex,event:EVENT,discipline:LABEL,page,source_url:url})}return out};
  const fetchPage=async url=>{for(let a=1;a<=5;a++){try{const r=await fetch(url,{credentials:'include',cache:'no-store'});if(!r.ok)throw new Error('HTTP '+r.status);return await r.text()}catch(e){txt.textContent='Erreur réseau — essai '+a+'/5';await sleep(1200*a)}}throw new Error('Échec après 5 essais')};
  const db=await openDb();
  const get=k=>new Promise(ok=>{const t=db.transaction(STORE,'readonly').objectStore(STORE).get(k);t.onsuccess=()=>ok(t.result);t.onerror=()=>ok(null)});
  const put=o=>new Promise((ok,no)=>{const t=db.transaction(STORE,'readwrite');t.objectStore(STORE).put(o);t.oncomplete=ok;t.onerror=()=>no(t.error)});
  try{
    for(const SEX of ['M','F']){
      if(stop)break;
      const sexLabel=SEX==='M'?'Hommes':'Femmes';
      const base=new URL(u0.href);
      Object.entries({frmbase:'bilans',frmmode:'1',frmespace:'0',frmannee:YEAR,frmepreuve:EVENT,frmsexe:SEX,frmcategorie:'',frmdepartement:'',frmligue:'',frmnationalite:'',frmvent:'VR',frmamaxi:'',frmposition:'0'}).forEach(([k,v])=>base.searchParams.set(k,v));
      txt.textContent='Marathon 2025 '+sexLabel+'\nDétection des pages…';
      const firstText=await fetchPage(base.href);
      let total=null,m=firstText.match(/Page\s*>\s*0*1\s*\/\s*0*(\d+)\s*</i);if(!m)m=firstText.match(/Page[^0-9]*0*1\s*\/\s*0*(\d+)/i);if(m)total=+m[1];if(!total){const nums=[...firstText.matchAll(/frmposition=(\d+)/gi)].map(x=>+x[1]);if(nums.length)total=Math.max(...nums)+1}if(!total||total<1)throw new Error('Nombre de pages indétectable pour '+sexLabel);
      const target=Math.min(total,MAXP);
      const firstRows=parse(firstText,0,base.href,SEX);if(!firstRows.length)throw new Error('Page 1 non reconnue pour '+sexLabel);
      await put({key:[YEAR,SEX,EVENT,0].join('|'),year:YEAR,sex:SEX,event:EVENT,discipline:LABEL,page:0,rows:firstRows,collectedAt:new Date().toISOString(),test:true});
      let done=1,totalRows=firstRows.length;
      for(let p=1;p<target&&!stop;p++){
        const key=[YEAR,SEX,EVENT,p].join('|'),old=await get(key);
        if(old&&old.test){done++;totalRows+=Array.isArray(old.rows)?old.rows.length:0;continue}
        const u=new URL(base.href);u.searchParams.set('frmposition',String(p));
        txt.textContent='Marathon 2025 '+sexLabel+'\nPage '+(p+1)+'/'+target+'…\n'+done+'/'+target+' pages enregistrées';
        const pageText=await fetchPage(u.href),rows=parse(pageText,p,u.href,SEX);if(!rows.length)throw new Error('0 ligne reconnue page '+(p+1)+' '+sexLabel);
        await put({key,year:YEAR,sex:SEX,event:EVENT,discipline:LABEL,page:p,rows,collectedAt:new Date().toISOString(),test:true});
        done++;totalRows+=rows.length;await sleep(300);
      }
      txt.textContent='Marathon 2025 '+sexLabel+' terminé\n'+done+'/'+target+' pages · '+totalRows+' lignes';
    }
    if(stop) txt.textContent+='\n\nArrêt demandé. Relance pour reprendre.';
    else {txt.textContent='TEST TERMINÉ ✓\nMarathon 2025 H/F\n3 pages max par bilan.';alert('Test Marathon 2025 H/F terminé.');}
  } finally {db.close();}
})().catch(e=>alert('Test FFA : '+(e&&e.message?e.message:e)));
