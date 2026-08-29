from pathlib import Path

FILES=[Path('mobile.html'),Path('app base.html')]

for path in FILES:
    if not path.exists():
        continue
    text=path.read_text(encoding='utf-8')

    # Supprime l'en-tête commun : chaque onglet commence directement par son propre titre.
    old_header='''  <header class="app-hero">\n    <h1>Comparateur 10 km</h1>\n    <div id="baseStatus" class="app-base">Chargement de la base FFA…</div>\n  </header>\n\n'''
    if old_header in text:
        text=text.replace(old_header,'',1)

    # Le compteur de base reste nécessaire au JS : on le conserve caché, hors interface.
    main_anchor='''  <main>\n'''
    if 'id="baseStatus"' not in text and main_anchor in text:
        text=text.replace(main_anchor,'''  <div id="baseStatus" aria-hidden="true" style="display:none">Chargement de la base FFA…</div>\n  <main>\n''',1)

    # Suppression de l'animation de changement d'onglet pour un passage instantané et stable sur iOS.
    text=text.replace('.tab-panel{display:none;animation:tabFade .18s ease}\n.tab-panel.active{display:block}\n@keyframes tabFade{from{opacity:.45;transform:translateY(4px)}to{opacity:1;transform:none}}',
                      '.tab-panel{display:none}\n.tab-panel.active{display:block}',1)

    # Un peu moins d'espace en haut maintenant que l'en-tête global a disparu.
    text=text.replace('padding:22px 18px 18px;\n  padding-top:calc(22px + env(safe-area-inset-top));',
                      'padding:16px 18px 18px;\n  padding-top:calc(16px + env(safe-area-inset-top));',1)

    # Changement d'onglet : remise immédiate en haut avant/après le changement de hauteur du document.
    old_switch='''function switchAppTab(tab){\n  if(!["classement","recherche","analyse"].includes(tab)) return;\n  activeAppTab=tab;\n  document.querySelectorAll("[data-app-panel]").forEach(p=>p.classList.toggle("active",p.getAttribute("data-app-panel")===tab));\n  document.querySelectorAll("[data-app-tab]").forEach(b=>b.classList.toggle("active",b.getAttribute("data-app-tab")===tab));\n  if(tab==="classement" && ffaReady && typeof renderFullFfaRanking==="function") renderFullFfaRanking(false);\n  if(tab==="recherche" && ffaReady && typeof renderFfaAthleteSearch==="function") renderFfaAthleteSearch();\n  window.scrollTo({top:0,behavior:"smooth"});\n}'''
    new_switch='''function switchAppTab(tab){\n  if(!["classement","recherche","analyse"].includes(tab)) return;\n  if(tab===activeAppTab) return;\n\n  // iOS conserve parfois la position de défilement de l'onglet précédent.\n  // On remonte instantanément avant de modifier la hauteur du contenu.\n  window.scrollTo(0,0);\n  document.documentElement.scrollTop=0;\n  document.body.scrollTop=0;\n\n  activeAppTab=tab;\n  document.querySelectorAll("[data-app-panel]").forEach(p=>p.classList.toggle("active",p.getAttribute("data-app-panel")===tab));\n  document.querySelectorAll("[data-app-tab]").forEach(b=>b.classList.toggle("active",b.getAttribute("data-app-tab")===tab));\n\n  if(tab==="classement" && ffaReady && typeof renderFullFfaRanking==="function") renderFullFfaRanking(false);\n  if(tab==="recherche" && ffaReady && typeof renderFfaAthleteSearch==="function") renderFfaAthleteSearch();\n\n  requestAnimationFrame(()=>{\n    window.scrollTo(0,0);\n    document.documentElement.scrollTop=0;\n    document.body.scrollTop=0;\n  });\n}'''
    if old_switch in text:
        text=text.replace(old_switch,new_switch,1)

    path.write_text(text,encoding='utf-8')
