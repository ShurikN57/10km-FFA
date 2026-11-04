// Incrémenter à chaque modification de l'app : c'est ce changement qui fait
// apparaître le bouton « MAJ disponible » (la CI le vérifie sur les PR).
const SHELL_CACHE='comparateur-ffa-shell-v16';

// Fichiers de l'app : servis depuis le cache (ouverture instantanée, même
// hors ligne) puis rafraîchis en arrière-plan pour la prochaine ouverture.
const SHELL_FILES=[
  './',
  './index.html',
  './mobile.html',
  './core.js',
  './manifest.webmanifest',
  './icons/apple-touch-icon.png',
  './icons/favicon-32x32.png',
  './icons/icon-192x192.png',
  './icons/icon-512x512.png'
];
const SHELL_PATHS=new Set(SHELL_FILES.map(f=>new URL(f,self.registration.scope).pathname));

// Bases FFA : jamais en Cache Storage (échecs mémoire et réponses
// incomplètes observés sur iOS/PWA avec les grosses bases gzip).
const isDataFile=pathname=>pathname.endsWith('.json.gz');

self.addEventListener('install',e=>{
  // cache:'reload' contourne le cache HTTP (10 min sur GitHub Pages) pour
  // enregistrer la version qui vient d'être publiée. Pas de skipWaiting :
  // la nouvelle version attend le clic sur « MAJ disponible ».
  e.waitUntil(caches.open(SHELL_CACHE).then(cache=>
    cache.addAll(SHELL_FILES.map(f=>new Request(f,{cache:'reload'})))
  ));
});

self.addEventListener('message',e=>{
  if(e.data && e.data.type==='SKIP_WAITING') self.skipWaiting();
});

self.addEventListener('activate',e=>{
  e.waitUntil((async()=>{
    for(const k of await caches.keys()) if(k!==SHELL_CACHE) await caches.delete(k);
    await self.clients.claim();
  })());
});

async function refreshShell(pathname){
  try{
    const res=await fetch(pathname,{cache:'no-store'});
    if(res.ok && res.type==='basic'){
      const cache=await caches.open(SHELL_CACHE);
      await cache.put(pathname,res);
    }
  }catch(e){}
}

self.addEventListener('fetch',e=>{
  if(e.request.method!=='GET') return;
  const url=new URL(e.request.url);
  // API Cloudflare et autres domaines : pas d'interception.
  if(url.origin!==self.location.origin) return;

  if(isDataFile(url.pathname)){
    e.respondWith(fetch(e.request,{cache:'no-store'}));
    return;
  }

  if(SHELL_PATHS.has(url.pathname)){
    // Cache d'abord, rafraîchissement en arrière-plan (stale-while-revalidate).
    e.respondWith((async()=>{
      const cached=await caches.match(url.pathname,{cacheName:SHELL_CACHE});
      // Les icônes ne changent pas : inutile de les retélécharger à chaque ouverture.
      const refresh=url.pathname.includes('/icons/') ? Promise.resolve() : refreshShell(url.pathname);
      if(cached){ e.waitUntil(refresh); return cached; }
      try{ return await fetch(e.request,{cache:'no-store'}); }
      catch(err){ return caches.match('./mobile.html',{cacheName:SHELL_CACHE}).then(r=>r||Response.error()); }
    })());
    return;
  }

  // Autres fichiers du site : réseau d'abord, cache en secours.
  e.respondWith(fetch(e.request,{cache:'no-store'}).catch(()=>caches.match(e.request,{ignoreSearch:true}).then(r=>r||Response.error())));
});
