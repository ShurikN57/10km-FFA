from pathlib import Path

FILES=[Path('mobile.html'),Path('app base.html')]

for path in FILES:
    if not path.exists():
        continue
    text=path.read_text(encoding='utf-8')

    # 1) Actions secondaires : Coller + Export CSV, même teinte plus discrète
    text=text.replace(
        'button.primary { background:#2458a6; border-color:#3973cf }\nbutton.paste { background:#1f5c3f; border-color:#2c7a54 }',
        'button.primary, button.paste { background:#263448; border-color:#3a4a60; color:var(--text) }\nbutton.primary:active, button.paste:active { background:#30435c; border-color:#4a6280 }',
        1
    )

    # 2) Réduire l’espace vide sous les 3 boutons de recherche + rendre le compteur de pages plus discret
    style_anchor='.small { color:var(--muted); font-size:12px }'
    if style_anchor in text and '#ffaAthleteSearchMsg:empty' not in text:
        text=text.replace(style_anchor, style_anchor+'\n#ffaAthleteSearchMsg:empty { display:none }\n#ffaFullMsg { font-size:11px; color:#7f8997; min-height:0 }', 1)
    text=text.replace('id="openFfaRanking" style="width:100%;margin-top:6px"', 'id="openFfaRanking" style="width:100%;margin-top:10px"', 1)

    # 3) Rang centré + noms longs sur 2 lignes maximum
    text=text.replace(
        'font-weight:800;font-size:${rankSize};text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap',
        'font-weight:800;font-size:${rankSize};text-align:center;font-variant-numeric:tabular-nums;white-space:nowrap',
        1
    )
    text=text.replace(
        '<div style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${link}</div><div class="small">${esc(meta)}</div>',
        '<div style="overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;line-height:1.18">${link}</div><div class="small">${esc(meta)}</div>',
        1
    )

    # 4) État visuel des filtres Trouvés / Non trouvés / Tous
    old_render='''function render() {\n  const q=norm($("search").value);'''
    new_render='''function updateRaceFilterButtons(){\n  const found=$("onlyFound"), no=$("onlyNo");\n  if(!found||!no) return;\n  [found,no].forEach(b=>{ b.style.background=""; b.style.borderColor=""; });\n  if(showOnlyFound){ found.style.background="#2458a6"; found.style.borderColor="#3973cf"; }\n  if(showOnlyNo){ no.style.background="#2458a6"; no.style.borderColor="#3973cf"; }\n}\n\nfunction render() {\n  updateRaceFilterButtons();\n  const q=norm($("search").value);'''
    if old_render in text and 'function updateRaceFilterButtons()' not in text:
        text=text.replace(old_render,new_render,1)

    path.write_text(text,encoding='utf-8')
