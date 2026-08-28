const C='comparateur-10k-v3-4';
self.addEventListener('install',e=>{self.skipWaiting()});
self.addEventListener('activate',e=>{e.waitUntil((async()=>{for(const k of await caches.keys())await caches.delete(k);await self.clients.claim()})())});
self.addEventListener('fetch',e=>{if(e.request.method==='GET')e.respondWith(fetch(e.request,{cache:'no-store'}).catch(()=>caches.match(e.request)))});
