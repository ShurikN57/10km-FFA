const SHELL_CACHE='comparateur-ffa-shell-v7';
const DATA_CACHE='comparateur-ffa-data-v3';

self.addEventListener('install',e=>{self.skipWaiting()});

self.addEventListener('activate',e=>{
  e.waitUntil((async()=>{
    // Ne purge que les caches d'app shell obsolètes ; la base FFA en cache reste.
    for(const k of await caches.keys()){
      if(k!==DATA_CACHE && k!==SHELL_CACHE) await caches.delete(k);
    }
    await self.clients.claim();
  })());
});

self.addEventListener('fetch',e=>{
  if(e.request.method!=='GET') return;
  const url=new URL(e.request.url);

  if(url.pathname.endsWith('/ffa_base.json.gz') || url.pathname.endsWith('/ffa_5km_2024_2026.json.gz')){
    // Base FFA (grosse) : sert le cache immédiatement si présent, et le
    // rafraîchit en tâche de fond pour la prochaine visite.
    e.respondWith((async()=>{
      const cache=await caches.open(DATA_CACHE);
      const cached=await cache.match(e.request);
      const refresh=fetch(e.request).then(resp=>{
        if(resp && resp.ok) cache.put(e.request, resp.clone());
        return resp;
      }).catch(()=>null);
      return cached || (await refresh) || Response.error();
    })());
    return;
  }

  // Reste de l'app (HTML/JS) : toujours le réseau pour avoir les derniers
  // correctifs, avec repli sur le cache seulement si hors ligne.
  e.respondWith(fetch(e.request,{cache:'no-store'}).catch(()=>caches.match(e.request)));
});
