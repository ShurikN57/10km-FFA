from pathlib import Path

FILES=[Path('mobile.html'),Path('app base.html')]

for path in FILES:
    if not path.exists():
        continue
    text=path.read_text(encoding='utf-8')

    # Move full FFA ranking access into its own top card, before athlete search.
    search_open='''  <section class="card" id="ffaSearchCard" style="margin-bottom:12px">\n    <h2 style="margin:0 0 10px;font-size:16px">Rechercher un athlète FFA</h2>'''
    top_cards='''  <section class="card" id="ffaRankingAccessCard" style="margin-bottom:12px">\n    <h2 style="margin:0 0 10px;font-size:16px">Classement FFA</h2>\n    <button type="button" id="openFfaRanking" class="primary" style="width:100%">Voir le classement complet</button>\n  </section>\n\n  <section class="card" id="ffaSearchCard" style="margin-bottom:12px">\n    <h2 style="margin:0 0 10px;font-size:16px">Rechercher un athlète FFA</h2>'''
    if search_open in text and 'id="ffaRankingAccessCard"' not in text:
        text=text.replace(search_open,top_cards,1)

    # Remove the old ranking button from inside athlete search.
    text=text.replace('''    <button type="button" id="openFfaRanking" style="width:100%;margin-top:10px">Voir le classement complet</button>\n''','',1)

    # Remove visible paste block, retain hidden textarea for userscript/import64 pipeline.
    old_paste='''  <div class="card">\n    <button class="paste" id="pasteBtn" style="width:100%">📋 Coller le classement</button>\n    <textarea id="paste" placeholder="…ou colle ici manuellement (appui long → Coller)" style="margin-top:10px"></textarea>\n    <div class="toolbar">\n      <button id="clearRace">Effacer</button>\n    </div>\n    <div id="raceMsg" class="msg"></div>\n  </div>\n\n'''
    new_paste='''  <textarea id="paste" aria-hidden="true" tabindex="-1" style="display:none"></textarea>\n  <div id="raceMsg" class="msg" style="margin:0 0 8px;min-height:0"></div>\n\n'''
    if old_paste in text:
        text=text.replace(old_paste,new_paste,1)

    # Comparator controls: filters first, then Export + Effacer lower down.
    old_controls='''  <div class="toolbar" style="margin-top:0;margin-bottom:10px">\n    <button id="onlyFound">Trouvés</button>\n    <button id="onlyNo">Non trouvés</button>\n    <button id="export" class="primary">Export CSV</button>\n  </div>\n\n'''
    new_controls='''  <div class="toolbar" style="margin-top:0;margin-bottom:8px">\n    <button id="onlyFound">Trouvés</button>\n    <button id="onlyNo">Non trouvés</button>\n  </div>\n  <div class="toolbar" style="margin-top:0;margin-bottom:10px">\n    <button id="export" class="primary">Export CSV</button>\n    <button id="clearRace">Effacer</button>\n  </div>\n\n'''
    if old_controls in text:
        text=text.replace(old_controls,new_controls,1)

    # Native paste button no longer exists; guard its old handler so JS remains safe.
    old_handler='''$("pasteBtn").onclick=async()=>{\n  try{\n    const text=await navigator.clipboard.readText();\n    if(!text){ $("raceMsg").textContent="Presse-papier vide."; return; }\n    $("paste").value=text;\n    if(ffaReady) runPasteAnalysis(); else pendingAutoParse=true;\n  }catch(e){\n    $("raceMsg").textContent="Collage automatique impossible ("+(e&&e.message?e.message:e)+"). Fais un appui long dans la zone de texte ci-dessous → Coller.";\n  }\n};'''
    new_handler='''const _pasteBtn=$("pasteBtn");\nif(_pasteBtn) _pasteBtn.onclick=async()=>{\n  try{\n    const text=await navigator.clipboard.readText();\n    if(!text){ $("raceMsg").textContent="Presse-papier vide."; return; }\n    $("paste").value=text;\n    if(ffaReady) runPasteAnalysis(); else pendingAutoParse=true;\n  }catch(e){\n    $("raceMsg").textContent="Collage automatique impossible.";\n  }\n};'''
    if old_handler in text:
        text=text.replace(old_handler,new_handler,1)

    path.write_text(text,encoding='utf-8')
