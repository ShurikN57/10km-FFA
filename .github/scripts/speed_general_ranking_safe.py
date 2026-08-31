from pathlib import Path

for path in [Path('mobile.html'), Path('app base.html')]:
    t=path.read_text(encoding='utf-8')

    old_vars='''let ffaGeneralRank=new Map();\nlet ffaSexRank=new Map();\nlet ffaCategoryRank=new Map();'''
    new_vars='''let ffaGeneralRank=new Map();\nlet ffaSexRank=new Map();\nlet ffaCategoryRank=new Map();\nlet ffaGeneralRows=[];'''
    if old_vars not in t:
        raise SystemExit(f'Variables marker not found in {path}')
    t=t.replace(old_vars,new_vars,1)

    old_build='''  const valid=ffa.filter(p=>Number.isFinite(Number(p.pb_sec)));\n  assignRanks(valid.slice(),ffaGeneralRank);'''
    new_build='''  const valid=ffa.filter(p=>Number.isFinite(Number(p.pb_sec)));\n  // Conserve une seule vue triée du classement général pour éviter\n  // de retrier les 527k profils à chaque ouverture de l'onglet.\n  ffaGeneralRows=valid.slice();\n  assignRanks(ffaGeneralRows,ffaGeneralRank);'''
    if old_build not in t:
        raise SystemExit(f'Build marker not found in {path}')
    t=t.replace(old_build,new_build,1)

    old_render='''  const maxPb=parsePbLimit($("ffaFullMaxPb").value);\n  const ranks=scopedFullRankMap(sex,cat,year);\n  let rows=ffa.filter(p=>{\n    const rank=ranks.get(p);\n    if(rank==null) return false;\n    if(maxPb!=null && Number(p.pb_sec)>maxPb) return false;\n    if(q){\n      const nk=p.name_key||nameKey(p.full_name||"");\n      const toks=q.split(" ").filter(Boolean);\n      if(!toks.every(t=>nk.includes(t))) return false;\n    }\n    return true;\n  });\n  rows.sort((a,b)=>{\n    const ra=ranks.get(a), rb=ranks.get(b);\n    return ra-rb || Number(a.pb_sec)-Number(b.pb_sec) || norm(a.full_name).localeCompare(norm(b.full_name));\n  });'''
    new_render='''  const maxPb=parsePbLimit($("ffaFullMaxPb").value);\n  const plainGeneral=!sex && !cat && !year && maxPb==null && !q;\n  let ranks, rows;\n  if(plainGeneral){\n    // Chemin rapide : classement général déjà trié au chargement.\n    ranks=ffaGeneralRank;\n    rows=ffaGeneralRows;\n  }else{\n    ranks=scopedFullRankMap(sex,cat,year);\n    const toks=q ? q.split(" ").filter(Boolean) : [];\n    rows=ffa.filter(p=>{\n      const rank=ranks.get(p);\n      if(rank==null) return false;\n      if(maxPb!=null && Number(p.pb_sec)>maxPb) return false;\n      if(toks.length){\n        const nk=p.name_key||nameKey(p.full_name||"");\n        if(!toks.every(t=>nk.includes(t))) return false;\n      }\n      return true;\n    });\n    rows.sort((a,b)=>{\n      const ra=ranks.get(a), rb=ranks.get(b);\n      return ra-rb || Number(a.pb_sec)-Number(b.pb_sec) || norm(a.full_name).localeCompare(norm(b.full_name));\n    });\n  }'''
    if old_render not in t:
        raise SystemExit(f'Render marker not found in {path}')
    t=t.replace(old_render,new_render,1)

    path.write_text(t,encoding='utf-8')
