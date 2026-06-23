
// ==============================
// SERVICE WORKER FOR AZIEL INVESTMENTS ERP
// ==============================

const CACHE_NAME = 'aziel-erp-v1.0.0';
const STATIC_ASSETS = [
    '/',
    '/static/css/style.css',
    '/static/js/app.js',
    '/static/icons/icon-192x192.png',
    '/static/icons/icon-512x512.png'
];

// Install event - cache static assets
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                console.log('Caching static assets...');
                return cache.addAll(STATIC_ASSETS);
            })
            .then(() => {
                console.log('Static assets cached successfully');
                return self.skipWaiting();
            })
    );
});

// Activate event - clean old caches
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cacheName => {
                    if (cacheName !== CACHE_NAME) {
                        console.log('Deleting old cache:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        }).then(() => {
            console.log('Service Worker activated');
            return self.clients.claim();
        })
    );
});

// Fetch event - serve from cache or network
self.addEventListener('fetch', event => {
    const request = event.request;
    const url = new URL(request.url);
    
    // Skip cross-origin requests
    if (url.origin !== location.origin) {
        return;
    }
    
    // Use network-first strategy for API requests
    if (url.pathname.startsWith('/_stcore/') || url.pathname.startsWith('/api/')) {
        event.respondWith(
            fetch(request)
                .then(response => {
                    // Cache successful responses
                    if (response.ok) {
                        const clonedResponse = response.clone();
                        caches.open(CACHE_NAME).then(cache => {
                            cache.put(request, clonedResponse);
                        });
                    }
                    return response;
                })
                .catch(() => {
                    return caches.match(request);
                })
        );
        return;
    }
    
    // Use cache-first strategy for static assets
    event.respondWith(
        caches.match(request)
            .then(cachedResponse => {
                if (cachedResponse) {
                    // Return cached response and update in background
                    fetch(request).then(response => {
                        if (response.ok) {
                            caches.open(CACHE_NAME).then(cache => {
                                cache.put(request, response);
                            });
                        }
                    });
                    return cachedResponse;
                }
                return fetch(request).then(response => {
                    if (response.ok) {
                        const clonedResponse = response.clone();
                        caches.open(CACHE_NAME).then(cache => {
                            cache.put(request, clonedResponse);
                        });
                    }
                    return response;
                });
            })
    );
});

// Push notification handler
self.addEventListener('push', event => {
    let data = { title: 'Aziel Investments', body: 'You have a new notification', icon: '/static/icons/icon-192x192.png' };
    
    if (event.data) {
        try {
            data = event.data.json();
        } catch (e) {
            data.body = event.data.text();
        }
    }
    
    const options = {
        body: data.body,
        icon: data.icon || '/static/icons/icon-192x192.png',
        badge: '/static/icons/icon-192x192.png',
        vibrate: [200, 100, 200],
        data: {
            url: data.url || '/'
        },
        actions: [
            { action: 'open', title: 'Open App' },
            { action: 'dismiss', title: 'Dismiss' }
        ]
    };
    
    event.waitUntil(
        self.registration.showNotification(data.title || 'Aziel Investments', options)
    );
});

// Notification click handler
self.addEventListener('notificationclick', event => {
    event.notification.close();
    
    if (event.action === 'dismiss') {
        return;
    }
    
    const url = event.notification.data.url || '/';
    
    event.waitUntil(
        clients.matchAll({
            type: 'window',
            includeUncontrolled: true
        }).then(windowClients => {
            for (let client of windowClients) {
                if (client.url === url && 'focus' in client) {
                    return client.focus();
                }
            }
            if (clients.openWindow) {
                return clients.openWindow(url);
            }
        })
    );
});

// Online/Offline status
self.addEventListener('message', event => {
    if (event.data && event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
});

console.log('Service Worker initialized for Aziel Investments ERP');
