from pathlib import Path

FILES=[Path('mobile.html'),Path('app base.html')]
for path in FILES:
    if not path.exists():
        continue
    text=path.read_text(encoding='utf-8')

    # Remove the extra large arrays/cache added for ranking performance.
    text=text.replace('''let ffaGeneralRank=new Map();\nlet ffaSexRank=new Map();\nlet ffaCategoryRank=new Map();\nlet ffaGeneralSorted=[];\nlet ffaScopeCache=new Map();''','''let ffaGeneralRank=new Map();\nlet ffaSexRank=new Map();\nlet ffaCategoryRank=new Map();''',1)

    old_build='''function buildFfaSexRanks(){\n  ffaGeneralRank=new Map();\n  ffaSexRank=new Map();\n  ffaCategoryRank=new Map();\n  ffaScopeCache=new Map();\n  const valid=ffa.filter(p=>Number.isFinite(Number(p.pb_sec)));\n  ffaGeneralSorted=valid.slice();\n  assignRanks(ffaGeneralSorted,ffaGeneralRank);\n  ffaScopeCache.set("||",{rows:ffaGeneralSorted,ranks:ffaGeneralRank});\n  for(const sex of ["M","F"]){\n    const arr=valid.filter(p=>p.sexe===sex);\n    assignRanks(arr,ffaSexRank);\n    ffaScopeCache.set(sex+"||",{rows:arr,ranks:ffaSexRank});\n  }\n  const groups=new Map();'''
    new_build='''function buildFfaSexRanks(){\n  ffaGeneralRank=new Map();\n  ffaSexRank=new Map();\n  ffaCategoryRank=new Map();\n  const valid=ffa.filter(p=>Number.isFinite(Number(p.pb_sec)));\n  assignRanks(valid.slice(),ffaGeneralRank);\n  for(const sex of ["M","F"]){\n    assignRanks(valid.filter(p=>p.sexe===sex),ffaSexRank);\n  }\n  const groups=new Map();'''
    if old_build in text:
        text=text.replace(old_build,new_build,1)

    old_scope='''function scopedFullRankData(sex,cat,year){\n  const key=[sex||"",cat||"",year||""].join("|");\n  const cached=ffaScopeCache.get(key);\n  if(cached) return cached;\n  const scope=ffa.filter(p=>{\n    if(!Number.isFinite(Number(p.pb_sec))) return false;\n    if(sex && p.sexe!==sex) return false;\n    if(cat && currentFfaCategory(p)!==cat) return false;\n    if(year && String(p.annee_naissance||"")!==year) return false;\n    return true;\n  });\n  const map=new Map();\n  assignRanks(scope,map);\n  const data={rows:scope,ranks:map};\n  ffaScopeCache.set(key,data);\n  return data;\n}'''
    new_scope='''function scopedFullRankMap(sex,cat,year){\n  const scope=ffa.filter(p=>{\n    if(!Number.isFinite(Number(p.pb_sec))) return false;\n    if(sex && p.sexe!==sex) return false;\n    if(cat && currentFfaCategory(p)!==cat) return false;\n    if(year && String(p.annee_naissance||"")!==year) return false;\n    return true;\n  });\n  const map=new Map();\n  assignRanks(scope,map);\n  return map;\n}'''
    if old_scope in text:
        text=text.replace(old_scope,new_scope,1)

    old_render='''  const maxPb=parsePbLimit($("ffaFullMaxPb").value);\n  const scopeData=scopedFullRankData(sex,cat,year);\n  const ranks=scopeData.ranks;\n  let rows=scopeData.rows;\n  if(maxPb!=null || q){\n    const toks=q ? q.split(" ").filter(Boolean) : [];\n    rows=rows.filter(p=>{\n      if(maxPb!=null && Number(p.pb_sec)>maxPb) return false;\n      if(toks.length){\n        const nk=p.name_key||nameKey(p.full_name||"");\n        if(!toks.every(t=>nk.includes(t))) return false;\n      }\n      return true;\n    });\n  }'''
    new_render='''  const maxPb=parsePbLimit($("ffaFullMaxPb").value);\n  const ranks=scopedFullRankMap(sex,cat,year);\n  let rows=ffa.filter(p=>{\n    const rank=ranks.get(p);\n    if(rank==null) return false;\n    if(maxPb!=null && Number(p.pb_sec)>maxPb) return false;\n    if(q){\n      const nk=p.name_key||nameKey(p.full_name||"");\n      const toks=q.split(" ").filter(Boolean);\n      if(!toks.every(t=>nk.includes(t))) return false;\n    }\n    return true;\n  });\n  rows.sort((a,b)=>{\n    const ra=ranks.get(a), rb=ranks.get(b);\n    return ra-rb || Number(a.pb_sec)-Number(b.pb_sec) || norm(a.full_name).localeCompare(norm(b.full_name));\n  });'''
    if old_render in text:
        text=text.replace(old_render,new_render,1)

    path.write_text(text,encoding='utf-8')
