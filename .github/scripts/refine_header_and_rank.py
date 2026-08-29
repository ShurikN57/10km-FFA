from pathlib import Path

FILES=[Path('mobile.html'),Path('app base.html')]

for path in FILES:
    text=path.read_text(encoding='utf-8')

    # Header / base status styling
    old_header='''  <h1>Comparateur 10 km</h1>\n  <div class="sub" id="baseStatus">Chargement de la base FFA…</div>'''
    new_header='''  <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:14px">\n    <h1 style="margin:0">Comparateur 10 km</h1>\n    <div id="baseStatus" style="flex:0 0 auto;padding:5px 9px;border:1px solid var(--line);border-radius:999px;background:var(--panel);color:var(--muted);font-size:11px;font-weight:700;white-space:nowrap">Chargement…</div>\n  </div>'''
    if old_header not in text:
        raise SystemExit(f'{path}: header anchor not found')
    text=text.replace(old_header,new_header,1)

    # Compact empty gap in search card
    text=text.replace('''    <button type="button" id="openFfaRanking" style="width:100%;margin-top:9px">Voir le classement complet</button>''',
                      '''    <button type="button" id="openFfaRanking" style="width:100%;margin-top:6px">Voir le classement complet</button>''',1)

    # Rank formatting: number only, grouped thousands, wider/responsive rank column
    old_rank='''    const rankText=rank===1?"1er":rank+"e";'''
    new_rank='''    const rankText=Number(rank).toLocaleString("fr-FR");'''
    if old_rank not in text:
        raise SystemExit(f'{path}: rank text anchor not found')
    text=text.replace(old_rank,new_rank,1)

    old_row='''    return `<div style="display:grid;grid-template-columns:44px minmax(0,1fr) 76px;gap:6px;align-items:center;padding:9px 10px;border-bottom:1px solid var(--line)"><div style="font-weight:800;font-size:14px">${esc(rankText)}</div><div style="min-width:0"><div style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${link}</div><div class="small">${esc(meta)}</div></div><div style="text-align:right;font-weight:800">${esc(p.pb_chrono||"—")}</div></div>`;'''
    new_row='''    const rankSize=rank>=100000?"12px":rank>=10000?"13px":"14px";\n    return `<div style="display:grid;grid-template-columns:68px minmax(0,1fr) 72px;gap:6px;align-items:center;padding:9px 10px;border-bottom:1px solid var(--line)"><div style="font-weight:800;font-size:${rankSize};text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap">${esc(rankText)}</div><div style="min-width:0"><div style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${link}</div><div class="small">${esc(meta)}</div></div><div style="text-align:right;font-weight:800;white-space:nowrap">${esc(p.pb_chrono||"—")}</div></div>`;'''
    if old_row not in text:
        raise SystemExit(f'{path}: ranking row anchor not found')
    text=text.replace(old_row,new_row,1)

    # Base status compact text
    old_status='''  $("baseStatus").textContent="Base FFA : "+ffa.length+" profils chargés.";'''
    new_status='''  $("baseStatus").textContent=ffa.length.toLocaleString("fr-FR")+" profils";'''
    if old_status in text:
        text=text.replace(old_status,new_status,1)
    else:
        # desktop variant may use baseCount; leave unchanged if absent
        pass

    path.write_text(text,encoding='utf-8')
