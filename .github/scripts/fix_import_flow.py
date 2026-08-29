from pathlib import Path

# Patch mobile/app base import flow
for path in [Path('mobile.html'), Path('app base.html')]:
    if not path.exists():
        continue
    t=path.read_text(encoding='utf-8')

    old='''(function(){\n  function fromB64(s){ return decodeURIComponent(escape(atob(s))); }\n  function loadImport64(){\n    if(!location.hash.startsWith('#import64=')) return;\n    try{\n      const text=fromB64(location.hash.slice('#import64='.length));\n      $("paste").value=text;\n      history.replaceState(null,'',location.pathname+location.search);\n      if(ffaReady) runPasteAnalysis(); else pendingAutoParse=true;\n    }catch(e){\n      alert('Import : '+e.message);\n    }\n  }\n  window.addEventListener('load',loadImport64);\n  setTimeout(loadImport64,150);\n})();'''

    new='''(function(){\n  function fromB64(s){ return decodeURIComponent(escape(atob(s))); }\n  function loadImport64(){\n    if(!location.hash.startsWith('#import64=')) return;\n    try{\n      const text=fromB64(location.hash.slice('#import64='.length));\n      if(!text || text.trim().length<10) throw new Error('données importées vides');\n      $("paste").value=text;\n      // L'import doit toujours ouvrir immédiatement l'onglet Analyse.\n      switchAppTab("analyse");\n      history.replaceState(null,'',location.pathname+location.search);\n      if(ffaReady) runPasteAnalysis(); else pendingAutoParse=true;\n    }catch(e){\n      alert('Import : '+e.message);\n    }\n  }\n  // Cas 1 : ouverture/rechargement classique.\n  window.addEventListener('load',loadImport64);\n  // Cas 2 : Safari réutilise la page déjà ouverte et ne fait que changer le hash.\n  window.addEventListener('hashchange',loadImport64);\n  setTimeout(loadImport64,150);\n})();'''

    if old not in t:
        raise SystemExit(f'import block not found in {path}')
    t=t.replace(old,new,1)
    path.write_text(t,encoding='utf-8')

# Make root redirect preserve import hash reliably on Safari.
index=Path('index.html')
if index.exists():
    t=index.read_text(encoding='utf-8')
    index.write_text('''<!doctype html>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width,initial-scale=1">\n<script>\n  location.replace('./mobile.html' + location.search + location.hash);\n</script>\n<noscript><a href="./mobile.html">Ouvrir le comparateur</a></noscript>\n''',encoding='utf-8')
