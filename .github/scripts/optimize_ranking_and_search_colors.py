from pathlib import Path

FILES=[Path('mobile.html'),Path('app base.html')]

for path in FILES:
    if not path.exists():
        continue
    text=path.read_text(encoding='utf-8')

    # --- Search results: rank blue in all modes; category blue only in Category mode ---
    old='''    const cat=currentFfaCategory(p);\n    const rank = ffaRankMode==="general" ? ffaGeneralRank.get(p) : ffaRankMode==="category" ? ffaCategoryRank.get(p) : ffaSexRank.get(p);\n    const rankText=rank ? (rank===1 ? "1er" : rank+"e") : "";\n    const scopeText=ffaRankMode==="category" ? (cat+(p.sexe||"")) : (p.sexe||"");\n    const meta=[p.annee_naissance||"année inconnue",scopeText,p.pb_chrono||"",rankText].filter(Boolean).join(" · ");\n    const action=url\n      ? `<a href="${esc(url)}" target="_blank" rel="noopener" style="color:var(--accent);font-weight:700;text-decoration:none;white-space:nowrap">Fiche FFA ↗</a>`\n      : `<span class="small" style="white-space:nowrap">Pas de fiche FFA</span>`;\n    return `<div style="display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px 11px;border-bottom:1px solid var(--line)"><div style="min-width:0"><div style="font-weight:700;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${name}</div><div class="small">${esc(meta)}</div></div>${action}</div>`;'''
    new='''    const cat=currentFfaCategory(p);\n    const rank = ffaRankMode==="general" ? ffaGeneralRank.get(p) : ffaRankMode==="category" ? ffaCategoryRank.get(p) : ffaSexRank.get(p);\n    const rankText=rank ? (rank===1 ? "1er" : Number(rank).toLocaleString("fr-FR")+"e") : "";\n    const metaParts=[];\n    metaParts.push(esc(p.annee_naissance||"année inconnue"));\n    if(p.sexe) metaParts.push(esc(p.sexe));\n    if(ffaRankMode==="category" && cat) metaParts.push(`<span style="color:var(--accent);font-weight:700">${esc(cat)}</span>`);\n    if(p.pb_chrono) metaParts.push(esc(p.pb_chrono));\n    if(rankText) metaParts.push(`<span style="color:var(--accent);font-weight:700">${esc(rankText)}</span>`);\n    const meta=metaParts.join(" · ");\n    const action=url\n      ? `<a href="${esc(url)}" target="_blank" rel="noopener" style="color:var(--accent);font-weight:700;text-decoration:none;white-space:nowrap">Fiche FFA ↗</a>`\n      : `<span class="small" style="white-space:nowrap">Pas de fiche FFA</span>`;\n    return `<div style="display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px 11px;border-bottom:1px solid var(--line)"><div style="min-width:0"><div style="font-weight:700;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${name}</div><div class="small">${meta}</div></div>${action}</div>`;'''
    if old in text:
        text=text.replace(old,new,1)

    # --- Full ranking performance: keep already-sorted default ranking and cache filtered scopes ---
    text=text.replace('''let ffaGeneralRank=new Map();\nlet ffaSexRank=new Map();\nlet ffaCategoryRank=new Map();''','''let ffaGeneralRank=new Map();\nlet ffaSexRank=new Map();\nlet ffaCategoryRank=new Map();\nlet ffaGeneralSorted=[];\nlet ffaScopeCache=new Map();''',1)

    old_build='''function buildFfaSexRanks(){\n  ffaGeneralRank=new Map();\n  ffaSexRank=new Map();\n  ffaCategoryRank=new Map();\n  const valid=ffa.filter(p=>Number.isFinite(Number(p.pb_sec)));\n  assignRanks(valid.slice(),ffaGeneralRank);\n  for(const sex of ["M","F"]){\n    assignRanks(valid.filter(p=>p.sexe===sex),ffaSexRank);\n  }\n  const groups=new Map();'''
    new_build='''function buildFfaSexRanks(){\n  ffaGeneralRank=new Map();\n  ffaSexRank=new Map();\n  ffaCategoryRank=new Map();\n  ffaScopeCache=new Map();\n  const valid=ffa.filter(p=>Number.isFinite(Number(p.pb_sec)));\n  ffaGeneralSorted=valid.slice();\n  assignRanks(ffaGeneralSorted,ffaGeneralRank);\n  ffaScopeCache.set("||",{rows:ffaGeneralSorted,ranks:ffaGeneralRank});\n  for(const sex of ["M","F"]){\n    const arr=valid.filter(p=>p.sexe===sex);\n    assignRanks(arr,ffaSexRank);\n    ffaScopeCache.set(sex+"||",{rows:arr,ranks:ffaSexRank});\n  }\n  const groups=new Map();'''
    if old_build in text:
        text=text.replace(old_build,new_build,1)

    old_scope='''function scopedFullRankMap(sex,cat,year){\n  const scope=ffa.filter(p=>{\n    if(!Number.isFinite(Number(p.pb_sec))) return false;\n    if(sex && p.sexe!==sex) return false;\n    if(cat && currentFfaCategory(p)!==cat) return false;\n    if(year && String(p.annee_naissance||"")!==year) return false;\n    return true;\n  });\n  const map=new Map();\n  assignRanks(scope,map);\n  return map;\n}'''
    new_scope='''function scopedFullRankData(sex,cat,year){\n  const key=[sex||"",cat||"",year||""].join("|");\n  const cached=ffaScopeCache.get(key);\n  if(cached) return cached;\n  const scope=ffa.filter(p=>{\n    if(!Number.isFinite(Number(p.pb_sec))) return false;\n    if(sex && p.sexe!==sex) return false;\n    if(cat && currentFfaCategory(p)!==cat) return false;\n    if(year && String(p.annee_naissance||"")!==year) return false;\n    return true;\n  });\n  const map=new Map();\n  assignRanks(scope,map);\n  const data={rows:scope,ranks:map};\n  ffaScopeCache.set(key,data);\n  return data;\n}'''
    if old_scope in text:
        text=text.replace(old_scope,new_scope,1)

    old_render='''  const maxPb=parsePbLimit($("ffaFullMaxPb").value);\n  const ranks=scopedFullRankMap(sex,cat,year);\n  let rows=ffa.filter(p=>{\n    const rank=ranks.get(p);\n    if(rank==null) return false;\n    if(maxPb!=null && Number(p.pb_sec)>maxPb) return false;\n    if(q){\n      const nk=p.name_key||nameKey(p.full_name||"");\n      const toks=q.split(" ").filter(Boolean);\n      if(!toks.every(t=>nk.includes(t))) return false;\n    }\n    return true;\n  });\n  rows.sort((a,b)=>{\n    const ra=ranks.get(a), rb=ranks.get(b);\n    return ra-rb || Number(a.pb_sec)-Number(b.pb_sec) || norm(a.full_name).localeCompare(norm(b.full_name));\n  });'''
    new_render='''  const maxPb=parsePbLimit($("ffaFullMaxPb").value);\n  const scopeData=scopedFullRankData(sex,cat,year);\n  const ranks=scopeData.ranks;\n  let rows=scopeData.rows;\n  if(maxPb!=null || q){\n    const toks=q ? q.split(" ").filter(Boolean) : [];\n    rows=rows.filter(p=>{\n      if(maxPb!=null && Number(p.pb_sec)>maxPb) return false;\n      if(toks.length){\n        const nk=p.name_key||nameKey(p.full_name||"");\n        if(!toks.every(t=>nk.includes(t))) return false;\n      }\n      return true;\n    });\n  }'''
    if old_render in text:
        text=text.replace(old_render,new_render,1)

    path.write_text(text,encoding='utf-8')
