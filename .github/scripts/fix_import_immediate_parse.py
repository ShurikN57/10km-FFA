from pathlib import Path

for path in [Path('mobile.html'), Path('app base.html')]:
    if not path.exists():
        continue
    t=path.read_text(encoding='utf-8')
    old='''      const text=fromB64(location.hash.slice('#import64='.length));\n      if(!text || text.trim().length<10) throw new Error('données importées vides');\n      $("paste").value=text;\n      switchAppTab("analyse");\n      history.replaceState(null,'',location.pathname+location.search);\n      if(ffaReady) runPasteAnalysis(); else pendingAutoParse=true;'''
    new='''      const text=fromB64(location.hash.slice('#import64='.length));\n      if(!text || text.trim().length<10) throw new Error('données importées vides');\n      $("paste").value=text;\n      switchAppTab("analyse");\n\n      // Parse l'import immédiatement, sans attendre le chargement complet\n      // de la base FFA. Cela remplit Analyse tout de suite sur Safari.\n      let parsed=parseUtmbPastedText(text);\n      let source=parsed.length ? "UTMB" : "texte";\n      if(!parsed.length) parsed=parsePlainText(text);\n      if(!parsed.length && /<table/i.test(text)) parsed=parseHTML(text);\n      race=parsed;\n      result=[];\n      $("raceMsg").textContent=parsed.length\n        ? parsed.length+" participants détectés ("+source+"). Chargement des correspondances FFA…"\n        : "Aucun participant reconnu.";\n      if(parsed.length) saveLastPaste(text);\n      render();\n\n      history.replaceState(null,'',location.pathname+location.search);\n      // Si la base est déjà prête, calcule immédiatement. Sinon le .then()\n      // de loadFfaRows() calculera automatiquement grâce à race.length.\n      if(ffaReady && parsed.length) compute();'''
    if old in t:
        t=t.replace(old,new,1)
        path.write_text(t,encoding='utf-8')
