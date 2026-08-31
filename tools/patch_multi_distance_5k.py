from pathlib import Path

p=Path('mobile.html')
s=p.read_text(encoding='utf-8')

def rep(old,new,label):
    global s
    if old not in s:
        raise SystemExit(f'ANCHOR NOT FOUND: {label}')
    s=s.replace(old,new,1)

rep('<meta name="apple-mobile-web-app-title" content="Comparateur 10K">','<meta name="apple-mobile-web-app-title" content="Comparateur FFA">','apple title')
rep('<title>Comparateur 10 km — mobile</title>','<title>Comparateur FFA — mobile</title>','html title')

css='''\n.distance-switch{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin:0 0 14px;padding:5px;background:rgba(25,30,39,.88);border:1px solid #3a4350;border-radius:18px}\n.distance-btn{min-height:44px;border:0!important;background:transparent!important;color:#c8ced8!important;border-radius:13px!important;font-size:14px!important;font-weight:800!important;padding:8px!important}\n.distance-btn.active{background:linear-gradient(180deg,#4c91ff,#3178e8)!important;color:#fff!important;box-shadow:0 5px 14px rgba(76,145,255,.20)}\n'''
rep('@media(max-width:390px){',css+'\n@media(max-width:390px){','distance css')

rep('<div class="wrap">\n  <div id="baseStatus" aria-hidden="true" style="display:none">Chargement de la base FFA…</div>', '''<div class="wrap">\n  <div class="distance-switch" role="group" aria-label="Distance FFA">\n    <button type="button" class="distance-btn" data-distance="5k">5 km</button>\n    <button type="button" class="distance-btn active" data-distance="10k">10 km</button>\n  </div>\n  <div id="baseStatus" aria-hidden="true" style="display:none">Chargement de la base FFA…</div>''','distance markup')

rep('<p>Consultez et filtrez le classement complet des 10 km.</p>','<p>Consultez et filtrez le classement complet des <span id="rankingDistanceLabel">10 km</span>.</p>','ranking label')

rep('const $ = id => document.getElementById(id);\n\nlet activeAppTab="recherche";', '''const $ = id => document.getElementById(id);\n\nconst FFA_DISTANCES={\n  "5k":{label:"5 km",file:"./ffa_5km_2024_2026.json.gz",export:"comparaison_ffa_5km.csv",minPb:"PB min, ex 15:00",maxPb:"PB max, ex 20:00"},\n  "10k":{label:"10 km",file:"./ffa_base.json.gz",export:"comparaison_ffa_10km.csv",minPb:"PB min, ex 30:00",maxPb:"PB max, ex 35:00"}\n};\nlet currentDistance=localStorage.getItem("comparateur_ffa_distance");\nif(!FFA_DISTANCES[currentDistance]) currentDistance="10k";\nlet ffaLoadToken=0;\n\nfunction updateDistanceUi(){\n  const cfg=FFA_DISTANCES[currentDistance];\n  document.querySelectorAll("[data-distance]").forEach(b=>b.classList.toggle("active",b.getAttribute("data-distance")===currentDistance));\n  const lab=$("rankingDistanceLabel"); if(lab) lab.textContent=cfg.label;\n  const min=$("ffaFullMinPb"), max=$("ffaFullMaxPb");\n  if(min) min.placeholder=cfg.minPb;\n  if(max) max.placeholder=cfg.maxPb;\n}\n\nlet activeAppTab="recherche";''','distance js vars')

rep('const STORAGE_KEY="comparateur10k_lastPaste";\nfunction saveLastPaste(text){ try{ localStorage.setItem(STORAGE_KEY,text); }catch(e){} }\nfunction loadLastPaste(){ try{ return localStorage.getItem(STORAGE_KEY)||""; }catch(e){ return ""; } }\nfunction clearLastPaste(){ try{ localStorage.removeItem(STORAGE_KEY); }catch(e){} }', '''function storageKey(){ return "comparateur_ffa_lastPaste_"+currentDistance; }\nfunction saveLastPaste(text){ try{ localStorage.setItem(storageKey(),text); }catch(e){} }\nfunction loadLastPaste(){ try{ return localStorage.getItem(storageKey())||""; }catch(e){ return ""; } }\nfunction clearLastPaste(){ try{ localStorage.removeItem(storageKey()); }catch(e){} }''','storage key')

old='''setImportEnabled(false);\n$("baseStatus").textContent="Chargement de la base FFA…";\nasync function loadFfaRows(){\n  const r=await fetch("./ffa_base.json.gz");\n  if(!r.ok) throw new Error("HTTP "+r.status);\n  if(!("DecompressionStream" in window)) {\n    throw new Error("Décompression gzip non prise en charge par ce navigateur");\n  }\n  if(!r.body) throw new Error("Flux de la base FFA indisponible");\n  const stream=r.body.pipeThrough(new DecompressionStream("gzip"));\n  const text=await new Response(stream).text();\n  return JSON.parse(text);\n}\nloadFfaRows().then(rows=>{\n  ffa=buildFfaFromCompact(rows);\n  buildFfaSexRanks();\n  ffaReady=true;\n  $("baseStatus").textContent="Base FFA · "+ffa.length.toLocaleString("fr-FR")+" profils";\n  setImportEnabled(true);\n  if(pendingAutoParse){ pendingAutoParse=false; runPasteAnalysis(); }\n  else if(race.length){ compute(); }\n}).catch(err=>{\n  $("baseStatus").textContent="Erreur de chargement de la base FFA : "+(err&&err.message?err.message:err)+". Recharge la page.";\n});'''
new='''setImportEnabled(false);\nasync function loadFfaRows(distance){\n  const cfg=FFA_DISTANCES[distance];\n  const r=await fetch(cfg.file,{cache:"no-store"});\n  if(!r.ok) throw new Error("HTTP "+r.status);\n  if(!("DecompressionStream" in window)) throw new Error("Décompression gzip non prise en charge par ce navigateur");\n  if(!r.body) throw new Error("Flux de la base FFA indisponible");\n  const stream=r.body.pipeThrough(new DecompressionStream("gzip"));\n  const text=await new Response(stream).text();\n  const data=JSON.parse(text);\n  return Array.isArray(data) ? data : (Array.isArray(data.rows) ? data.rows : []);\n}\nasync function loadFfaDistance(distance){\n  if(!FFA_DISTANCES[distance]) return;\n  currentDistance=distance;\n  localStorage.setItem("comparateur_ffa_distance",currentDistance);\n  updateDistanceUi();\n  refreshRestoreButton();\n  const token=++ffaLoadToken;\n  ffaReady=false;\n  setImportEnabled(false);\n  ffa=[]; ffaGeneralRows=[]; ffaGeneralRank=new Map(); ffaSexRank=new Map(); ffaCategoryRank=new Map();\n  ffaFullPage=0;\n  $("baseStatus").textContent="Chargement de la base FFA "+FFA_DISTANCES[distance].label+"…";\n  try{\n    const rows=await loadFfaRows(distance);\n    if(token!==ffaLoadToken) return;\n    ffa=buildFfaFromCompact(rows);\n    buildFfaSexRanks();\n    ffaReady=true;\n    $("baseStatus").textContent="Base FFA "+FFA_DISTANCES[distance].label+" · "+ffa.length.toLocaleString("fr-FR")+" profils";\n    setImportEnabled(true);\n    if(activeAppTab==="classement") renderFullFfaRanking(true);\n    if(activeAppTab==="recherche") renderFfaAthleteSearch();\n    if(pendingAutoParse){ pendingAutoParse=false; runPasteAnalysis(); }\n    else if(race.length){ compute(); }\n  }catch(err){\n    if(token!==ffaLoadToken) return;\n    ffaReady=false;\n    $("baseStatus").textContent="Erreur de chargement de la base FFA "+FFA_DISTANCES[distance].label+" : "+(err&&err.message?err.message:err);\n    const msg=$("ffaAthleteSearchMsg"); if(msg) msg.textContent="Base "+FFA_DISTANCES[distance].label+" indisponible.";\n    const fmsg=$("ffaFullMsg"); if(fmsg) fmsg.textContent="Base "+FFA_DISTANCES[distance].label+" indisponible.";\n  }\n}\ndocument.querySelectorAll("[data-distance]").forEach(btn=>btn.addEventListener("click",()=>{\n  const d=btn.getAttribute("data-distance");\n  if(d!==currentDistance) loadFfaDistance(d);\n}));\nupdateDistanceUi();\nloadFfaDistance(currentDistance);'''
rep(old,new,'loader block')

rep('$("export").onclick=()=>exportResultCSV(result,"comparaison_ffa_10km.csv");','$("export").onclick=()=>exportResultCSV(result,FFA_DISTANCES[currentDistance].export);','dynamic export')

p.write_text(s,encoding='utf-8')

m=Path('manifest.webmanifest')
ms=m.read_text(encoding='utf-8')
ms=ms.replace('"name": "Comparateur 10 km FFA / GoTiming"','"name": "Comparateur FFA / GoTiming"')
ms=ms.replace('"short_name": "Comparateur 10K"','"short_name": "Comparateur FFA"')
m.write_text(ms,encoding='utf-8')

sw=Path('sw.js')
ss=sw.read_text(encoding='utf-8')
ss=ss.replace("const SHELL_CACHE='comparateur-10k-shell-v5';","const SHELL_CACHE='comparateur-ffa-shell-v6';")
ss=ss.replace("const DATA_CACHE='comparateur-10k-data-v1';","const DATA_CACHE='comparateur-ffa-data-v2';")
ss=ss.replace("if(url.pathname.endsWith('/ffa_base.json')){","if(url.pathname.endsWith('/ffa_base.json.gz') || url.pathname.endsWith('/ffa_5km_2024_2026.json.gz')){")
sw.write_text(ss,encoding='utf-8')

print('patched mobile.html, manifest.webmanifest, sw.js')
