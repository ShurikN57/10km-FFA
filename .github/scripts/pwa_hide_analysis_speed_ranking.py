from pathlib import Path

FILES=[Path('mobile.html'),Path('app base.html')]
for path in FILES:
    if not path.exists():
        continue
    t=path.read_text(encoding='utf-8')

    # 1) Full dark background in standalone/PWA, including short pages.
    t=t.replace('html { -webkit-text-size-adjust:100%; }','html { -webkit-text-size-adjust:100%; background:#05070b; min-height:100%; }',1)
    t=t.replace('''body{\n  background:radial-gradient(circle at 50% -12%,#121a27 0,#080b11 28%,#05070b 55%);\n  padding-bottom:calc(106px + env(safe-area-inset-bottom));\n}''','''body{\n  background:radial-gradient(circle at 50% -12%,#121a27 0,#080b11 28%,#05070b 55%);\n  min-height:100vh;\n  min-height:100dvh;\n  padding-bottom:calc(106px + env(safe-area-inset-bottom));\n}''',1)

    # 2) Keep only one lightweight sorted reference array for instant general ranking.
    t=t.replace('''let ffaGeneralRank=new Map();\nlet ffaSexRank=new Map();\nlet ffaCategoryRank=new Map();''','''let ffaGeneralRank=new Map();\nlet ffaSexRank=new Map();\nlet ffaCategoryRank=new Map();\nlet ffaGeneralOrder=[];\nlet ffaCategoryRanksReady=false;''',1)

    old_build='''function buildFfaSexRanks(){\n  ffaGeneralRank=new Map();\n  ffaSexRank=new Map();\n  ffaCategoryRank=new Map();\n  const valid=ffa.filter(p=>Number.isFinite(Number(p.pb_sec)));\n  assignRanks(valid.slice(),ffaGeneralRank);\n  for(const sex of ["M","F"]){\n    assignRanks(valid.filter(p=>p.sexe===sex),ffaSexRank);\n  }\n  const groups=new Map();\n  for(const p of valid){\n    const cat=currentFfaCategory(p);\n    if(!cat||!p.sexe) continue;\n    const key=cat+"|"+p.sexe;\n    if(!groups.has(key)) groups.set(key,[]);\n    groups.get(key).push(p);\n  }\n  for(const arr of groups.values()) assignRanks(arr,ffaCategoryRank);\n}'''
    new_build='''function buildFfaSexRanks(){\n  ffaGeneralRank=new Map();\n  ffaSexRank=new Map();\n  ffaCategoryRank=new Map();\n  ffaCategoryRanksReady=false;\n  const valid=ffa.filter(p=>Number.isFinite(Number(p.pb_sec)));\n  ffaGeneralOrder=valid.slice();\n  assignRanks(ffaGeneralOrder,ffaGeneralRank);\n  for(const sex of ["M","F"]){\n    assignRanks(valid.filter(p=>p.sexe===sex),ffaSexRank);\n  }\n}\nfunction ensureFfaCategoryRanks(){\n  if(ffaCategoryRanksReady) return;\n  ffaCategoryRank=new Map();\n  const groups=new Map();\n  for(const p of ffa){\n    if(!Number.isFinite(Number(p.pb_sec))) continue;\n    const cat=currentFfaCategory(p);\n    if(!cat||!p.sexe) continue;\n    const key=cat+"|"+p.sexe;\n    if(!groups.has(key)) groups.set(key,[]);\n    groups.get(key).push(p);\n  }\n  for(const arr of groups.values()) assignRanks(arr,ffaCategoryRank);\n  ffaCategoryRanksReady=true;\n}'''
    if old_build in t:
        t=t.replace(old_build,new_build,1)

    t=t.replace('''    const rank = ffaRankMode==="general" ? ffaGeneralRank.get(p) : ffaRankMode==="category" ? ffaCategoryRank.get(p) : ffaSexRank.get(p);''','''    if(ffaRankMode==="category") ensureFfaCategoryRanks();\n    const rank = ffaRankMode==="general" ? ffaGeneralRank.get(p) : ffaRankMode==="category" ? ffaCategoryRank.get(p) : ffaSexRank.get(p);''',1)

    old_render='''  const maxPb=parsePbLimit($("ffaFullMaxPb").value);\n  const ranks=scopedFullRankMap(sex,cat,year);\n  let rows=ffa.filter(p=>{\n    const rank=ranks.get(p);\n    if(rank==null) return false;\n    if(maxPb!=null && Number(p.pb_sec)>maxPb) return false;\n    if(q){\n      const nk=p.name_key||nameKey(p.full_name||"");\n      const toks=q.split(" ").filter(Boolean);\n      if(!toks.every(t=>nk.includes(t))) return false;\n    }\n    return true;\n  });\n  rows.sort((a,b)=>{\n    const ra=ranks.get(a), rb=ranks.get(b);\n    return ra-rb || Number(a.pb_sec)-Number(b.pb_sec) || norm(a.full_name).localeCompare(norm(b.full_name));\n  });'''
    new_render='''  const maxPb=parsePbLimit($("ffaFullMaxPb").value);\n  const plainGeneral=!sex && !cat && !year;\n  const ranks=plainGeneral ? ffaGeneralRank : scopedFullRankMap(sex,cat,year);\n  let rows;\n  if(plainGeneral && maxPb==null && !q){\n    // Chemin rapide : le classement général est déjà trié au chargement.\n    rows=ffaGeneralOrder;\n  }else{\n    const source=plainGeneral ? ffaGeneralOrder : ffa;\n    const toks=q ? q.split(" ").filter(Boolean) : [];\n    rows=source.filter(p=>{\n      const rank=ranks.get(p);\n      if(rank==null) return false;\n      if(maxPb!=null && Number(p.pb_sec)>maxPb) return false;\n      if(toks.length){\n        const nk=p.name_key||nameKey(p.full_name||"");\n        if(!toks.every(tok=>nk.includes(tok))) return false;\n      }\n      return true;\n    });\n    if(!plainGeneral){\n      rows.sort((a,b)=>{\n        const ra=ranks.get(a), rb=ranks.get(b);\n        return ra-rb || Number(a.pb_sec)-Number(b.pb_sec) || norm(a.full_name).localeCompare(norm(b.full_name));\n      });\n    }\n  }'''
    if old_render in t:
        t=t.replace(old_render,new_render,1)

    # 3) Hide Analyse only when installed as standalone PWA; keep browser/Safari unchanged.
    marker='''document.querySelectorAll("[data-app-tab]").forEach(btn=>btn.addEventListener("click",()=>switchAppTab(btn.getAttribute("data-app-tab"))));'''
    addition='''document.querySelectorAll("[data-app-tab]").forEach(btn=>btn.addEventListener("click",()=>switchAppTab(btn.getAttribute("data-app-tab"))));\n\nconst isStandalonePwa = window.matchMedia?.("(display-mode: standalone)")?.matches || window.navigator.standalone===true;\nif(isStandalonePwa){\n  const analyseTab=document.querySelector('[data-app-tab="analyse"]');\n  const analysePanel=document.querySelector('[data-app-panel="analyse"]');\n  if(analyseTab) analyseTab.style.display="none";\n  if(analysePanel) analysePanel.style.display="none";\n  const tabbar=document.querySelector(".app-tabbar");\n  if(tabbar) tabbar.style.gridTemplateColumns="repeat(2,1fr)";\n}'''
    if marker in t and 'const isStandalonePwa' not in t:
        t=t.replace(marker,addition,1)

    # If the user opens Classement before the FFA base is fully ready, render it automatically as soon as loading finishes.
    old_ready='''  if(pendingAutoParse){ pendingAutoParse=false; runPasteAnalysis(); }\n  else if(race.length){ compute(); }'''
    new_ready='''  if(pendingAutoParse){ pendingAutoParse=false; runPasteAnalysis(); }\n  else if(race.length){ compute(); }\n  if(activeAppTab==="classement") renderFullFfaRanking(false);\n  else if(activeAppTab==="recherche") renderFfaAthleteSearch();'''
    if old_ready in t and 'if(activeAppTab==="classement") renderFullFfaRanking(false);' not in t:
        t=t.replace(old_ready,new_ready,1)

    path.write_text(t,encoding='utf-8')
