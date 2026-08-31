from pathlib import Path

FILES=[Path('mobile.html'),Path('app base.html')]
for path in FILES:
    t=path.read_text(encoding='utf-8')

    old_html='''        <input id="ffaFullSearch" type="search" placeholder="Rechercher nom / prénom..." style="width:100%;margin-bottom:9px">\n        <div class="rank-filter-grid">\n          <select id="ffaFullSex"><option value="">Tous sexes</option><option value="M">Hommes</option><option value="F">Femmes</option></select>\n          <select id="ffaFullCategory"><option value="">Toutes catégories</option><option>CA</option><option>JU</option><option>ES</option><option>SE</option><option>M0</option><option>M1</option><option>M2</option><option>M3</option><option>M4</option><option>M5</option><option>M6</option><option>M7</option><option>M8</option><option>M9</option><option>M10</option></select>\n          <input id="ffaFullYear" inputmode="numeric" placeholder="Année naissance">\n          <input id="ffaFullMaxPb" inputmode="numeric" placeholder="PB max, ex 35:00">\n        </div>'''
    new_html='''        <div class="rank-filter-grid">\n          <input id="ffaFullSearch" type="search" placeholder="Rechercher nom / prénom...">\n          <input id="ffaFullYear" inputmode="numeric" placeholder="Année naissance">\n        </div>\n        <div class="rank-filter-grid">\n          <select id="ffaFullSex"><option value="">Tous sexes</option><option value="M">Hommes</option><option value="F">Femmes</option></select>\n          <select id="ffaFullCategory"><option value="">Toutes catégories</option><option>CA</option><option>JU</option><option>ES</option><option>SE</option><option>M0</option><option>M1</option><option>M2</option><option>M3</option><option>M4</option><option>M5</option><option>M6</option><option>M7</option><option>M8</option><option>M9</option><option>M10</option></select>\n        </div>\n        <div class="rank-filter-grid">\n          <input id="ffaFullMinPb" inputmode="numeric" placeholder="PB min, ex 30:00">\n          <input id="ffaFullMaxPb" inputmode="numeric" placeholder="PB max, ex 35:00">\n        </div>'''
    if old_html not in t:
        raise SystemExit(f'HTML filter block not found in {path}')
    t=t.replace(old_html,new_html,1)

    old_logic='''  const year=String($("ffaFullYear").value||"").trim();\n  const maxPb=parsePbLimit($("ffaFullMaxPb").value);\n  const plainGeneral=!sex && !cat && !year && maxPb==null && !q;'''
    new_logic='''  const year=String($("ffaFullYear").value||"").trim();\n  const minPb=parsePbLimit($("ffaFullMinPb").value);\n  const maxPb=parsePbLimit($("ffaFullMaxPb").value);\n  const plainGeneral=!sex && !cat && !year && minPb==null && maxPb==null && !q;'''
    if old_logic not in t:
        raise SystemExit(f'PB logic marker not found in {path}')
    t=t.replace(old_logic,new_logic,1)

    old_filter='''      if(rank==null) return false;\n      if(maxPb!=null && Number(p.pb_sec)>maxPb) return false;'''
    new_filter='''      if(rank==null) return false;\n      if(minPb!=null && Number(p.pb_sec)<minPb) return false;\n      if(maxPb!=null && Number(p.pb_sec)>maxPb) return false;'''
    if old_filter not in t:
        raise SystemExit(f'PB filtering marker not found in {path}')
    t=t.replace(old_filter,new_filter,1)

    old_events='''["ffaFullSearch","ffaFullSex","ffaFullCategory","ffaFullYear","ffaFullMaxPb"].forEach(id=>{\n  const el=$(id);\n  if(el) el.addEventListener(id==="ffaFullSearch"||id==="ffaFullYear"||id==="ffaFullMaxPb"?"input":"change",()=>renderFullFfaRanking(true));\n});'''
    new_events='''["ffaFullSearch","ffaFullSex","ffaFullCategory","ffaFullYear","ffaFullMinPb","ffaFullMaxPb"].forEach(id=>{\n  const el=$(id);\n  if(el) el.addEventListener(id==="ffaFullSearch"||id==="ffaFullYear"||id==="ffaFullMinPb"||id==="ffaFullMaxPb"?"input":"change",()=>renderFullFfaRanking(true));\n});'''
    if old_events not in t:
        raise SystemExit(f'Events marker not found in {path}')
    t=t.replace(old_events,new_events,1)

    old_reset='''  $("ffaFullCategory").value="";\n  $("ffaFullYear").value="";\n  $("ffaFullMaxPb").value="";'''
    new_reset='''  $("ffaFullCategory").value="";\n  $("ffaFullYear").value="";\n  $("ffaFullMinPb").value="";\n  $("ffaFullMaxPb").value="";'''
    if old_reset not in t:
        raise SystemExit(f'Reset marker not found in {path}')
    t=t.replace(old_reset,new_reset,1)

    path.write_text(t,encoding='utf-8')
