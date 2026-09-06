from pathlib import Path

# --- mobile.html ---
p=Path('mobile.html')
s=p.read_text(encoding='utf-8')

css_anchor='''.distance-switch{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:0;margin:0 0 14px;padding:4px;background:rgba(25,30,39,.88);border:1px solid #3a4350;border-radius:18px;overflow:hidden}'''
css_repl='''.pwa-update-btn{display:none;width:100%;min-height:42px;margin:0 0 10px;border:1px solid #67a1ff!important;background:linear-gradient(180deg,#4c91ff,#3178e8)!important;color:#fff!important;border-radius:14px!important;font-size:13px!important;font-weight:850!important;box-shadow:0 7px 18px rgba(76,145,255,.22)}\n.pwa-update-btn.show{display:block}\n'''+css_anchor
if css_anchor not in s:
    raise SystemExit('CSS anchor not found')
s=s.replace(css_anchor,css_repl,1)

html_anchor='''<div class="wrap">\n  <div class="distance-switch" role="group" aria-label="Distance FFA">'''
html_repl='''<div class="wrap">\n  <button type="button" id="pwaUpdateBtn" class="pwa-update-btn">↻ MAJ disponible</button>\n  <div class="distance-switch" role="group" aria-label="Distance FFA">'''
if html_anchor not in s:
    raise SystemExit('HTML anchor not found')
s=s.replace(html_anchor,html_repl,1)

old='''if ('serviceWorker' in navigator && location.protocol === 'https:') {\n  window.addEventListener('load', () => navigator.serviceWorker.register('./sw.js?v=20260831g').catch(()=>{}));\n}'''
new='''if ('serviceWorker' in navigator && location.protocol === 'https:') {\n  window.addEventListener('load', async()=>{\n    const updateBtn=document.getElementById('pwaUpdateBtn');\n    let refreshing=false;\n    const showUpdate=()=>{ if(updateBtn) updateBtn.classList.add('show'); };\n    const hideUpdate=()=>{ if(updateBtn) updateBtn.classList.remove('show'); };\n    try{\n      const reg=await navigator.serviceWorker.register('./sw.js');\n      const watchWorker=worker=>{\n        if(!worker) return;\n        worker.addEventListener('statechange',()=>{\n          if(worker.state==='installed' && navigator.serviceWorker.controller) showUpdate();\n        });\n      };\n      if(reg.waiting && navigator.serviceWorker.controller) showUpdate();\n      reg.addEventListener('updatefound',()=>watchWorker(reg.installing));\n      if(updateBtn) updateBtn.addEventListener('click',()=>{\n        const worker=reg.waiting;\n        if(worker){\n          updateBtn.disabled=true;\n          updateBtn.textContent='Mise à jour…';\n          worker.postMessage({type:'SKIP_WAITING'});\n        }else{\n          reg.update().catch(()=>{});\n        }\n      });\n      navigator.serviceWorker.addEventListener('controllerchange',()=>{\n        if(refreshing) return;\n        refreshing=true;\n        hideUpdate();\n        location.reload();\n      });\n      // iOS peut laisser une PWA ouverte longtemps : contrôle au retour au premier plan\n      // et périodiquement, sans recharger l'application tant que l'utilisateur n'a pas choisi MAJ.\n      document.addEventListener('visibilitychange',()=>{ if(!document.hidden) reg.update().catch(()=>{}); });\n      setInterval(()=>reg.update().catch(()=>{}),60000);\n      reg.update().catch(()=>{});\n    }catch(e){}\n  });\n}'''
if old not in s:
    raise SystemExit('SW registration anchor not found')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')

# --- sw.js ---
sw=Path('sw.js')
t=sw.read_text(encoding='utf-8')
t=t.replace("const SHELL_CACHE='comparateur-ffa-shell-v9';","const SHELL_CACHE='comparateur-ffa-shell-v10';",1)
t=t.replace("self.addEventListener('install',e=>{self.skipWaiting()});","self.addEventListener('install',()=>{});",1)
msg="""\nself.addEventListener('message',e=>{\n  if(e.data && e.data.type==='SKIP_WAITING') self.skipWaiting();\n});\n"""
activate="self.addEventListener('activate',e=>{"
if msg.strip() not in t:
    if activate not in t: raise SystemExit('SW activate anchor not found')
    t=t.replace(activate,msg+'\n'+activate,1)
sw.write_text(t,encoding='utf-8')
print('patched mobile.html and sw.js')
