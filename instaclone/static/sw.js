// PWA service worker — cache deck/cabinet + API stale-while-revalidate, slides cache-first
const CACHE = 'studyreel-v1';
const ASSETS = ['/deck','/cabinet','/static/deck.js','/static/cabinet.js','/static/style.css'];
self.addEventListener('install', e=>{
  e.waitUntil(caches.open(CACHE).then(c=>c.addAll(ASSETS).catch(()=>{})));
  self.skipWaiting();
});
self.addEventListener('activate', e=>{
  e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))));
  self.clients.claim();
});
self.addEventListener('fetch', e=>{
  const url = new URL(e.request.url);
  // API: network first, cache fallback, never cache POST /file
  if(url.pathname.startsWith('/api/v1/')){
    if(e.request.method !== 'GET'){
      return; // let POST go to network
    }
    e.respondWith(fetch(e.request).then(res=>{
      const clone=res.clone();
      caches.open(CACHE).then(c=>c.put(e.request, clone));
      return res;
    }).catch(()=>caches.match(e.request)));
    return;
  }
  // slides: cache first
  if(url.pathname.startsWith('/slides/')){
    e.respondWith(caches.match(e.request).then(cached=> cached || fetch(e.request).then(res=>{
      caches.open(CACHE).then(c=>c.put(e.request, res.clone()));
      return res;
    })));
    return;
  }
  // static assets: stale-while-revalidate
  e.respondWith(caches.match(e.request).then(cached=>{
    const fetchPromise = fetch(e.request).then(res=>{
      caches.open(CACHE).then(c=>c.put(e.request, res.clone()));
      return res;
    }).catch(()=>cached);
    return cached || fetchPromise;
  }));
});
