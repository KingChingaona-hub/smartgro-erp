
// ==============================
// Service Worker - SmartGro Retail
// Version: unknown
// Build: unknown
// ==============================

const CACHE_NAME = 'smartgro-v1';
const STATIC_CACHE = 'smartgro-static-v1';
const DYNAMIC_CACHE = 'smartgro-dynamic-v1';

// Files to cache
const STATIC_FILES = [
    '/',
    '/index.html',
    '/offline',
    '/static/manifest.json',
    '/static/style.css',
    '/static/app.js'
];

// ==============================
// INSTALL
// ==============================
self.addEventListener('install', function(event) {
    event.waitUntil(
        caches.open(STATIC_CACHE)
            .then(function(cache) {
                console.log('Caching static files...');
                return cache.addAll(STATIC_FILES);
            })
            .then(function() {
                return self.skipWaiting();
            })
    );
});

// ==============================
// ACTIVATE
// ==============================
self.addEventListener('activate', function(event) {
    event.waitUntil(
        caches.keys()
            .then(function(cacheNames) {
                return Promise.all(
                    cacheNames
                        .filter(function(cacheName) {
                            return cacheName !== STATIC_CACHE && 
                                   cacheName !== DYNAMIC_CACHE;
                        })
                        .map(function(cacheName) {
                            console.log('Deleting old cache:', cacheName);
                            return caches.delete(cacheName);
                        })
                );
            })
            .then(function() {
                return self.clients.claim();
            })
    );
});

// ==============================
// FETCH - Network First Strategy
// ==============================
self.addEventListener('fetch', function(event) {
    const url = new URL(event.request.url);
    
    // Skip non-GET requests and browser extensions
    if (event.request.method !== 'GET' || 
        url.protocol === 'chrome-extension:' ||
        url.protocol === 'chrome:' ||
        url.protocol === 'about:') {
        return;
    }
    
    // API calls - network first
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(networkFirst(event.request));
        return;
    }
    
    // Static assets - cache first
    if (url.pathname.match(/\.(css|js|png|jpg|jpeg|gif|svg|ico)$/)) {
        event.respondWith(cacheFirst(event.request));
        return;
    }
    
    // HTML pages - network first with cache fallback
    if (url.pathname.endsWith('/') || url.pathname.match(/\.html$/)) {
        event.respondWith(networkFirstWithCacheFallback(event.request));
        return;
    }
    
    // Everything else - network first
    event.respondWith(networkFirst(event.request));
});

// ==============================
// STRATEGIES
// ==============================

// Cache First Strategy
async function cacheFirst(request) {
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
        return cachedResponse;
    }
    try {
        const networkResponse = await fetch(request);
        const cache = await caches.open(STATIC_CACHE);
        cache.put(request, networkResponse.clone());
        return networkResponse;
    } catch (error) {
        return new Response('Resource not found', { status: 404 });
    }
}

// Network First Strategy
async function networkFirst(request) {
    try {
        const networkResponse = await fetch(request);
        const cache = await caches.open(DYNAMIC_CACHE);
        cache.put(request, networkResponse.clone());
        return networkResponse;
    } catch (error) {
        const cachedResponse = await caches.match(request);
        if (cachedResponse) {
            return cachedResponse;
        }
        return new Response('Network error', { status: 503 });
    }
}

// Network First with Cache Fallback
async function networkFirstWithCacheFallback(request) {
    try {
        const networkResponse = await fetch(request);
        const cache = await caches.open(DYNAMIC_CACHE);
        cache.put(request, networkResponse.clone());
        return networkResponse;
    } catch (error) {
        const cachedResponse = await caches.match(request);
        if (cachedResponse) {
            return cachedResponse;
        }
        const offlineResponse = await caches.match('/offline');
        if (offlineResponse) {
            return offlineResponse;
        }
        return new Response('Offline', { status: 503 });
    }
}

// ==============================
// PUSH NOTIFICATIONS
// ==============================
self.addEventListener('push', function(event) {
    const data = event.data.json();
    const options = {
        body: data.body || 'New notification',
        icon: '/static/icons/icon-192x192.png',
        badge: '/static/icons/icon-72x72.png',
        vibrate: [200, 100, 200],
        data: {
            url: data.url || '/'
        },
        actions: [
            {
                action: 'open',
                title: 'Open App'
            },
            {
                action: 'dismiss',
                title: 'Dismiss'
            }
        ]
    };
    
    event.waitUntil(
        self.registration.showNotification(data.title || 'SmartGro', options)
    );
});

self.addEventListener('notificationclick', function(event) {
    event.notification.close();
    
    if (event.action === 'dismiss') {
        return;
    }
    
    const urlToOpen = event.notification.data?.url || '/';
    
    event.waitUntil(
        clients.matchAll({
            type: 'window',
            includeUncontrolled: true
        })
        .then(function(windowClients) {
            for (let client of windowClients) {
                if (client.url === urlToOpen && 'focus' in client) {
                    return client.focus();
                }
            }
            if (clients.openWindow) {
                return clients.openWindow(urlToOpen);
            }
        })
    );
});

// ==============================
// BACKGROUND SYNC
// ==============================
self.addEventListener('sync', function(event) {
    if (event.tag === 'sync-data') {
        event.waitUntil(syncData());
    }
});

async function syncData() {
    console.log('Syncing offline data...');
    
    // Sync pending requests
    try {
        const cache = await caches.open(DYNAMIC_CACHE);
        const requests = await cache.keys();
        for (const request of requests) {
            if (request.url.startsWith('/api/')) {
                try {
                    const response = await fetch(request);
                    if (response.ok) {
                        await cache.delete(request);
                    }
                } catch (e) {
                    console.log('Sync failed for:', request.url);
                }
            }
        }
    } catch (error) {
        console.error('Sync error:', error);
    }
}
    