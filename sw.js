const SHELL_CACHE='comparateur-ffa-shell-v9';

self.addEventListener('install',e=>{self.skipWaiting()});

self.addEventListener('activate',e=>{
  e.waitUntil((async()=>{
    // Purge les anciens caches de données : ils pouvaient contenir une réponse
    // partielle/corrompue sur iOS PWA lors du chargement des grosses bases gzip.
    for(const k of await caches.keys()) await caches.delete(k);
    await self.clients.claim();
  })());
});

self.addEventListener('fetch',e=>{
  if(e.request.method!=='GET') return;
  const url=new URL(e.request.url);

  if(url.pathname.endsWith('/ffa_base.json.gz') || url.pathname.endsWith('/ffa_5km_2024_2026.json.gz')){
    // Les bases FFA doivent toujours venir directement du réseau.
    // Ne pas les mettre en Cache Storage dans Safari/PWA : cela évite les
    // échecs mémoire et les réponses incomplètes sur iOS.
    e.respondWith(fetch(e.request,{cache:'no-store'}));
    return;
  }

  // App shell : réseau d'abord, cache uniquement en secours hors ligne.
  e.respondWith(fetch(e.request,{cache:'no-store'}).catch(()=>caches.match(e.request)));
});
