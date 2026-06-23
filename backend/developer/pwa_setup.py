import streamlit as st
import json
from pathlib import Path
from datetime import datetime
import base64
import hashlib
import re
import shutil
from typing import Dict, Any, List, Optional, Tuple

# ==============================
# FILE PATHS
# ==============================
DATA_DIR = Path("data")
PWA_CONFIG_FILE = DATA_DIR / "pwa_config.json"
PWA_MANIFEST_FILE = Path("static") / "manifest.json"
PWA_SW_FILE = Path("static") / "sw.js"
PWA_ICONS_DIR = Path("static/icons")
PWA_VERSION_FILE = Path("static") / "version.json"
PWA_BACKUP_DIR = DATA_DIR / "pwa_backups"

# ==============================
# INITIALIZATION
# ==============================
def init_pwa_files():
    """Initialize PWA-related files"""
    DATA_DIR.mkdir(exist_ok=True)
    PWA_ICONS_DIR.mkdir(parents=True, exist_ok=True)
    PWA_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    Path("static").mkdir(exist_ok=True)
    
    # PWA Config - only create if doesn't exist
    if not PWA_CONFIG_FILE.exists():
        config = get_default_config()
        with open(PWA_CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
    
    # Generate manifest if it doesn't exist
    if not PWA_MANIFEST_FILE.exists():
        generate_manifest()
    
    # Generate service worker if it doesn't exist
    if not PWA_SW_FILE.exists():
        generate_service_worker()
    
    # Generate version file if it doesn't exist
    if not PWA_VERSION_FILE.exists():
        update_pwa_version()


def get_default_config() -> Dict[str, Any]:
    """Get default PWA configuration"""
    return {
        "enabled": True,
        "app_name": "SmartGro Retail",
        "app_short_name": "SmartGro",
        "app_description": "Smart Retail ERP System",
        "theme_color": "#6366F1",
        "background_color": "#FFFFFF",
        "display": "standalone",
        "orientation": "portrait",
        "start_url": "/",
        "scope": "/",
        "icon_sizes": [72, 96, 128, 144, 152, 192, 384, 512],
        "offline_enabled": True,
        "cache_strategy": "network_first",
        "offline_page": "/offline",
        "push_enabled": True,
        "vapid_public_key": "",
        "vapid_private_key": "",
        "auto_update": True,
        "update_interval": 3600,
        "splash_screen": True,
        "splash_screen_color": "#6366F1",
        "ios_enabled": True,
        "ios_icon_sizes": [180, 192, 512]
    }


def load_pwa_config() -> Dict[str, Any]:
    """Load PWA configuration"""
    if not PWA_CONFIG_FILE.exists():
        DATA_DIR.mkdir(exist_ok=True)
        config = get_default_config()
        with open(PWA_CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
    
    with open(PWA_CONFIG_FILE, "r") as f:
        return json.load(f)


def save_pwa_config(config: Dict[str, Any]) -> None:
    """Save PWA configuration"""
    # Validate before saving
    is_valid, message = validate_pwa_config(config)
    if not is_valid:
        raise ValueError(f"Invalid configuration: {message}")
    
    with open(PWA_CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def validate_pwa_config(config: Dict[str, Any]) -> Tuple[bool, str]:
    """Validate PWA configuration"""
    required_fields = ["app_name", "app_short_name", "theme_color"]
    for field in required_fields:
        if not config.get(field):
            return False, f"Missing required field: {field}"
    
    if len(config.get("app_name", "")) > 50:
        return False, "App name too long (max 50 characters)"
    
    if len(config.get("app_short_name", "")) > 20:
        return False, "Short name too long (max 20 characters)"
    
    if not config.get("theme_color", "").startswith("#"):
        return False, "Theme color must be a hex color code"
    
    return True, "Valid"


def show_toast(message: str, type: str = "info") -> None:
    """Show a toast notification using Streamlit"""
    if type == "success":
        st.success(f"✅ {message}")
    elif type == "error":
        st.error(f"❌ {message}")
    elif type == "warning":
        st.warning(f"⚠️ {message}")
    else:
        st.info(f"ℹ️ {message}")


# ==============================
# PWA VERSION MANAGEMENT
# ==============================
def update_pwa_version() -> str:
    """Update PWA version"""
    version_data = {
        "version": datetime.now().strftime("%Y.%m.%d.%H%M"),
        "updated": datetime.now().isoformat(),
        "build": hashlib.md5(str(datetime.now().timestamp()).encode()).hexdigest()[:8]
    }
    PWA_VERSION_FILE.write_text(json.dumps(version_data, indent=2))
    return version_data["version"]


def get_pwa_version() -> Dict[str, Any]:
    """Get current PWA version"""
    if PWA_VERSION_FILE.exists():
        return json.loads(PWA_VERSION_FILE.read_text())
    return {"version": "unknown", "updated": "unknown"}


# ==============================
# PWA BACKUP & RESTORE
# ==============================
def backup_pwa_config() -> Tuple[bool, str]:
    """Backup PWA configuration"""
    if not PWA_CONFIG_FILE.exists():
        return False, "No configuration to backup"
    
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = PWA_BACKUP_DIR / f"pwa_config_{timestamp}.json"
        shutil.copy(PWA_CONFIG_FILE, backup_file)
        
        # Keep only last 10 backups
        backups = sorted(PWA_BACKUP_DIR.glob("pwa_config_*.json"))
        if len(backups) > 10:
            for old_backup in backups[:-10]:
                old_backup.unlink()
        
        return True, f"Backup created: {backup_file.name}"
    except Exception as e:
        return False, f"Backup failed: {str(e)}"


def restore_pwa_config(backup_file: Optional[Path] = None) -> Tuple[bool, str]:
    """Restore PWA configuration from backup"""
    if not backup_file:
        # Get latest backup
        backups = sorted(PWA_BACKUP_DIR.glob("pwa_config_*.json"))
        if not backups:
            return False, "No backups found"
        backup_file = backups[-1]
    
    if not backup_file.exists():
        return False, f"Backup file not found: {backup_file}"
    
    try:
        shutil.copy(backup_file, PWA_CONFIG_FILE)
        return True, f"Restored from: {backup_file.name}"
    except Exception as e:
        return False, f"Restore failed: {str(e)}"


def clear_pwa_cache() -> Tuple[bool, str]:
    """Clear PWA cache files"""
    try:
        files_removed = 0
        
        # Remove manifest and service worker
        for file in [PWA_MANIFEST_FILE, PWA_SW_FILE, PWA_VERSION_FILE]:
            if file.exists():
                file.unlink()
                files_removed += 1
        
        # Remove icons
        if PWA_ICONS_DIR.exists():
            for icon in PWA_ICONS_DIR.glob("*.png"):
                icon.unlink()
                files_removed += 1
        
        # Reinitialize files
        init_pwa_files()
        
        return True, f"Cache cleared ({files_removed} files removed)"
    except Exception as e:
        return False, f"Failed to clear cache: {str(e)}"


# ==============================
# MANIFEST GENERATION
# ==============================
def generate_manifest() -> None:
    """Generate PWA manifest file"""
    config = load_pwa_config()
    
    manifest = {
        "name": config.get("app_name", "SmartGro Retail"),
        "short_name": config.get("app_short_name", "SmartGro"),
        "description": config.get("app_description", "Smart Retail ERP System"),
        "theme_color": config.get("theme_color", "#6366F1"),
        "background_color": config.get("background_color", "#FFFFFF"),
        "display": config.get("display", "standalone"),
        "orientation": config.get("orientation", "portrait"),
        "start_url": config.get("start_url", "/"),
        "scope": config.get("scope", "/"),
        "icons": [],
        "splash_pages": None,
        "categories": ["business", "productivity", "retail"],
        "lang": "en-US",
        "dir": "ltr"
    }
    
    # Generate icons
    for size in config.get("icon_sizes", [72, 96, 128, 144, 152, 192, 384, 512]):
        manifest["icons"].append({
            "src": f"/static/icons/icon-{size}x{size}.png",
            "sizes": f"{size}x{size}",
            "type": "image/png",
            "purpose": "any maskable"
        })
    
    # Write manifest
    PWA_MANIFEST_FILE.write_text(json.dumps(manifest, indent=2))


def safe_generate_manifest() -> Tuple[bool, str]:
    """Safely generate manifest with error handling"""
    try:
        generate_manifest()
        return True, "Manifest generated successfully"
    except Exception as e:
        return False, f"Error generating manifest: {str(e)}"


# ==============================
# SERVICE WORKER GENERATION
# ==============================
def generate_service_worker() -> None:
    """Generate service worker file"""
    config = load_pwa_config()
    version_info = get_pwa_version()
    
    sw_content = f"""
// ==============================
// Service Worker - SmartGro Retail
// Version: {version_info.get('version', '1.0.0')}
// Build: {version_info.get('build', 'unknown')}
// ==============================

const CACHE_NAME = 'smartgro-v{version_info.get('build', '1')}';
const STATIC_CACHE = 'smartgro-static-v{version_info.get('build', '1')}';
const DYNAMIC_CACHE = 'smartgro-dynamic-v{version_info.get('build', '1')}';

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
self.addEventListener('install', function(event) {{
    event.waitUntil(
        caches.open(STATIC_CACHE)
            .then(function(cache) {{
                console.log('Caching static files...');
                return cache.addAll(STATIC_FILES);
            }})
            .then(function() {{
                return self.skipWaiting();
            }})
    );
}});

// ==============================
// ACTIVATE
// ==============================
self.addEventListener('activate', function(event) {{
    event.waitUntil(
        caches.keys()
            .then(function(cacheNames) {{
                return Promise.all(
                    cacheNames
                        .filter(function(cacheName) {{
                            return cacheName !== STATIC_CACHE && 
                                   cacheName !== DYNAMIC_CACHE;
                        }})
                        .map(function(cacheName) {{
                            console.log('Deleting old cache:', cacheName);
                            return caches.delete(cacheName);
                        }})
                );
            }})
            .then(function() {{
                return self.clients.claim();
            }})
    );
}});

// ==============================
// FETCH - Network First Strategy
// ==============================
self.addEventListener('fetch', function(event) {{
    const url = new URL(event.request.url);
    
    // Skip non-GET requests and browser extensions
    if (event.request.method !== 'GET' || 
        url.protocol === 'chrome-extension:' ||
        url.protocol === 'chrome:' ||
        url.protocol === 'about:') {{
        return;
    }}
    
    // API calls - network first
    if (url.pathname.startsWith('/api/')) {{
        event.respondWith(networkFirst(event.request));
        return;
    }}
    
    // Static assets - cache first
    if (url.pathname.match(/\\.(css|js|png|jpg|jpeg|gif|svg|ico)$/)) {{
        event.respondWith(cacheFirst(event.request));
        return;
    }}
    
    // HTML pages - network first with cache fallback
    if (url.pathname.endsWith('/') || url.pathname.match(/\\.html$/)) {{
        event.respondWith(networkFirstWithCacheFallback(event.request));
        return;
    }}
    
    // Everything else - network first
    event.respondWith(networkFirst(event.request));
}});

// ==============================
// STRATEGIES
// ==============================

// Cache First Strategy
async function cacheFirst(request) {{
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {{
        return cachedResponse;
    }}
    try {{
        const networkResponse = await fetch(request);
        const cache = await caches.open(STATIC_CACHE);
        cache.put(request, networkResponse.clone());
        return networkResponse;
    }} catch (error) {{
        return new Response('Resource not found', {{ status: 404 }});
    }}
}}

// Network First Strategy
async function networkFirst(request) {{
    try {{
        const networkResponse = await fetch(request);
        const cache = await caches.open(DYNAMIC_CACHE);
        cache.put(request, networkResponse.clone());
        return networkResponse;
    }} catch (error) {{
        const cachedResponse = await caches.match(request);
        if (cachedResponse) {{
            return cachedResponse;
        }}
        return new Response('Network error', {{ status: 503 }});
    }}
}}

// Network First with Cache Fallback
async function networkFirstWithCacheFallback(request) {{
    try {{
        const networkResponse = await fetch(request);
        const cache = await caches.open(DYNAMIC_CACHE);
        cache.put(request, networkResponse.clone());
        return networkResponse;
    }} catch (error) {{
        const cachedResponse = await caches.match(request);
        if (cachedResponse) {{
            return cachedResponse;
        }}
        const offlineResponse = await caches.match('/offline');
        if (offlineResponse) {{
            return offlineResponse;
        }}
        return new Response('Offline', {{ status: 503 }});
    }}
}}

// ==============================
// PUSH NOTIFICATIONS
// ==============================
self.addEventListener('push', function(event) {{
    const data = event.data.json();
    const options = {{
        body: data.body || 'New notification',
        icon: '/static/icons/icon-192x192.png',
        badge: '/static/icons/icon-72x72.png',
        vibrate: [200, 100, 200],
        data: {{
            url: data.url || '/'
        }},
        actions: [
            {{
                action: 'open',
                title: 'Open App'
            }},
            {{
                action: 'dismiss',
                title: 'Dismiss'
            }}
        ]
    }};
    
    event.waitUntil(
        self.registration.showNotification(data.title || 'SmartGro', options)
    );
}});

self.addEventListener('notificationclick', function(event) {{
    event.notification.close();
    
    if (event.action === 'dismiss') {{
        return;
    }}
    
    const urlToOpen = event.notification.data?.url || '/';
    
    event.waitUntil(
        clients.matchAll({{
            type: 'window',
            includeUncontrolled: true
        }})
        .then(function(windowClients) {{
            for (let client of windowClients) {{
                if (client.url === urlToOpen && 'focus' in client) {{
                    return client.focus();
                }}
            }}
            if (clients.openWindow) {{
                return clients.openWindow(urlToOpen);
            }}
        }})
    );
}});

// ==============================
// BACKGROUND SYNC
// ==============================
self.addEventListener('sync', function(event) {{
    if (event.tag === 'sync-data') {{
        event.waitUntil(syncData());
    }}
}});

async function syncData() {{
    console.log('Syncing offline data...');
    
    // Sync pending requests
    try {{
        const cache = await caches.open(DYNAMIC_CACHE);
        const requests = await cache.keys();
        for (const request of requests) {{
            if (request.url.startsWith('/api/')) {{
                try {{
                    const response = await fetch(request);
                    if (response.ok) {{
                        await cache.delete(request);
                    }}
                }} catch (e) {{
                    console.log('Sync failed for:', request.url);
                }}
            }}
        }}
    }} catch (error) {{
        console.error('Sync error:', error);
    }}
}}
    """
    
    PWA_SW_FILE.write_text(sw_content)


# ==============================
# ICON GENERATION
# ==============================
def generate_icon_png(size: int, color: str = "#6366F1") -> bool:
    """Generate a simple PNG icon (placeholder)"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        
        # Create image
        img = Image.new('RGB', (size, size), color=color)
        draw = ImageDraw.Draw(img)
        
        # Draw border
        border_color = tuple(int(color[i:i+2], 16) for i in (1, 3, 5))
        border_color = tuple(int(c * 0.8) for c in border_color)
        draw.rectangle([0, 0, size-1, size-1], outline=border_color, width=2)
        
        # Draw text (if size is large enough)
        if size >= 128:
            try:
                font = ImageFont.truetype("arial.ttf", size // 4)
            except:
                font = ImageFont.load_default()
            
            text = "SG"
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            x = (size - text_width) // 2
            y = (size - text_height) // 2
            draw.text((x, y), text, fill="white", font=font)
        
        # Save
        img.save(PWA_ICONS_DIR / f"icon-{size}x{size}.png")
        return True
    except:
        return False


def generate_all_icons() -> int:
    """Generate all PWA icons"""
    config = load_pwa_config()
    generated = 0
    
    for size in config.get("icon_sizes", [72, 96, 128, 144, 152, 192, 384, 512]):
        icon_path = PWA_ICONS_DIR / f"icon-{size}x{size}.png"
        if not icon_path.exists():
            if generate_icon_png(size, config.get("theme_color", "#6366F1")):
                generated += 1
    
    # Generate iOS icons
    for size in config.get("ios_icon_sizes", [180, 192, 512]):
        icon_path = PWA_ICONS_DIR / f"apple-icon-{size}x{size}.png"
        if not icon_path.exists():
            if generate_icon_png(size, config.get("theme_color", "#6366F1")):
                generated += 1
    
    return generated


# ==============================
# META TAGS GENERATION
# ==============================
def generate_meta_tags() -> str:
    """Generate PWA meta tags for HTML"""
    config = load_pwa_config()
    version_info = get_pwa_version()
    
    tags = f"""
<!-- PWA Meta Tags -->
<meta name="application-name" content="{config.get('app_name', 'SmartGro Retail')}">
<meta name="apple-mobile-web-app-title" content="{config.get('app_short_name', 'SmartGro')}">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="theme-color" content="{config.get('theme_color', '#6366F1')}">
<meta name="msapplication-navbutton-color" content="{config.get('theme_color', '#6366F1')}">
<meta name="msapplication-TileColor" content="{config.get('theme_color', '#6366F1')}">
<meta name="msapplication-TileImage" content="/static/icons/icon-144x144.png">
<meta name="version" content="{version_info.get('version', '1.0.0')}">

<link rel="manifest" href="/static/manifest.json">
<link rel="apple-touch-icon" href="/static/icons/apple-icon-180x180.png">
<link rel="icon" type="image/png" sizes="32x32" href="/static/icons/icon-32x32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/static/icons/icon-16x16.png">
    """
    
    return tags


# ==============================
# PWA ANALYTICS
# ==============================
def get_pwa_analytics() -> Dict[str, Any]:
    """Get PWA usage analytics"""
    config = load_pwa_config()
    version_info = get_pwa_version()
    
    # Check if manifest is accessible
    manifest_accessible = PWA_MANIFEST_FILE.exists()
    
    # Check if service worker is registered
    sw_accessible = PWA_SW_FILE.exists()
    
    # Count icon files
    icon_count = len(list(PWA_ICONS_DIR.glob("*.png"))) if PWA_ICONS_DIR.exists() else 0
    
    # Check backups
    backup_count = len(list(PWA_BACKUP_DIR.glob("pwa_config_*.json"))) if PWA_BACKUP_DIR.exists() else 0
    
    return {
        "manifest": manifest_accessible,
        "service_worker": sw_accessible,
        "icons": icon_count,
        "enabled": config.get("enabled", True),
        "version": version_info.get("version", "unknown"),
        "build": version_info.get("build", "unknown"),
        "backups": backup_count,
        "last_updated": version_info.get("updated", "unknown")
    }


# ==============================
# PWA INSTALL PROMPT - FIXED (Hidden by default)
# ==============================
def pwa_install_prompt() -> str:
    """Generate PWA install prompt HTML - Hidden by default, shows when install is possible"""
    return """
    <style>
        #pwa-install-prompt {
            display: none;
            position: fixed;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 9999;
            background: white;
            padding: 15px 20px;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.2);
            max-width: 450px;
            width: 90%;
            border: 1px solid #e0e0e0;
            animation: slideUp 0.5s ease;
        }
        .pwa-prompt-content {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 15px;
        }
        .pwa-prompt-text {
            flex: 1;
        }
        .pwa-prompt-text strong {
            display: block;
            font-size: 1rem;
            color: #333;
        }
        .pwa-prompt-text span {
            font-size: 0.85rem;
            color: #666;
        }
        .pwa-prompt-btn {
            background: #6366F1;
            color: white;
            border: none;
            padding: 8px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: bold;
            white-space: nowrap;
            transition: background 0.3s ease;
        }
        .pwa-prompt-btn:hover {
            background: #4f52d9;
        }
        .pwa-prompt-close {
            background: none;
            border: none;
            font-size: 1.2rem;
            cursor: pointer;
            color: #999;
            padding: 0 5px;
            transition: color 0.3s ease;
        }
        .pwa-prompt-close:hover {
            color: #333;
        }
        @keyframes slideUp {
            from {
                transform: translateX(-50%) translateY(20px);
                opacity: 0;
            }
            to {
                transform: translateX(-50%) translateY(0);
                opacity: 1;
            }
        }
        @media (prefers-color-scheme: dark) {
            #pwa-install-prompt {
                background: #1e1e1e;
                border-color: #333;
            }
            .pwa-prompt-text strong {
                color: #eee;
            }
            .pwa-prompt-text span {
                color: #aaa;
            }
        }
    </style>
    <div id="pwa-install-prompt">
        <div class="pwa-prompt-content">
            <div class="pwa-prompt-text">
                <strong>📱 Install SmartGro App</strong>
                <span>Add to home screen for the best experience</span>
            </div>
            <button class="pwa-prompt-btn" onclick="installPWA()">Install</button>
            <button class="pwa-prompt-close" onclick="dismissInstallPrompt()">✕</button>
        </div>
    </div>
    <script>
    let deferredPrompt;
    
    window.addEventListener('beforeinstallprompt', (e) => {
        e.preventDefault();
        deferredPrompt = e;
        document.getElementById('pwa-install-prompt').style.display = 'block';
    });
    
    async function installPWA() {
        if (deferredPrompt) {
            deferredPrompt.prompt();
            const result = await deferredPrompt.userChoice;
            if (result.outcome === 'accepted') {
                document.getElementById('pwa-install-prompt').style.display = 'none';
            }
            deferredPrompt = null;
        } else {
            alert('📱 To install this app:\\n\\n' +
                  '📱 Android: Tap menu (⋮) → "Add to Home Screen"\\n' +
                  '📱 iPhone: Tap Share (⬆) → "Add to Home Screen"\\n' +
                  '💻 Desktop: Look for install icon in address bar');
        }
    }
    
    function dismissInstallPrompt() {
        document.getElementById('pwa-install-prompt').style.display = 'none';
    }
    
    window.addEventListener('appinstalled', (evt) => {
        document.getElementById('pwa-install-prompt').style.display = 'none';
        console.log('App installed successfully');
    });
    </script>
    """


# ==============================
# OFFLINE STATUS INDICATOR
# ==============================
def offline_status_indicator() -> str:
    """Generate offline status indicator HTML"""
    return """
    <div id="online-status" style="display: none; padding: 10px; border-radius: 5px; margin: 10px 0; background: #d4edda; color: #155724;">
        ✅ Online
    </div>
    <script>
    function updateOnlineStatus() {
        const statusDiv = document.getElementById('online-status');
        if (navigator.onLine) {
            statusDiv.style.display = 'block';
            statusDiv.innerHTML = '✅ Online';
            statusDiv.style.background = '#d4edda';
            statusDiv.style.color = '#155724';
            statusDiv.style.border = '1px solid #c3e6cb';
        } else {
            statusDiv.style.display = 'block';
            statusDiv.innerHTML = '📴 Offline - Some features may be limited';
            statusDiv.style.background = '#f8d7da';
            statusDiv.style.color = '#721c24';
            statusDiv.style.border = '1px solid #f5c6cb';
        }
    }
    
    window.addEventListener('online', updateOnlineStatus);
    window.addEventListener('offline', updateOnlineStatus);
    
    // Initial check
    updateOnlineStatus();
    </script>
    """


# ==============================
# PWA TESTING TOOLS
# ==============================
def pwa_test_tools() -> None:
    """PWA testing and validation tools"""
    st.markdown("### 🧪 PWA Testing Tools")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔍 Test Manifest", use_container_width=True):
            try:
                import requests
                response = requests.get("/static/manifest.json", timeout=5)
                if response.status_code == 200:
                    show_toast("✅ Manifest is accessible", "success")
                else:
                    show_toast(f"❌ Manifest returned status {response.status_code}", "error")
            except Exception as e:
                show_toast(f"❌ Cannot access manifest: {str(e)}", "error")
        
        if st.button("🔍 Test Service Worker", use_container_width=True):
            st.markdown("""
            <div id="sw-test-result" style="padding: 10px; border-radius: 5px; margin: 10px 0; background: #f8f9fa;">
                ⏳ Testing...
            </div>
            <script>
            if ('serviceWorker' in navigator) {
                navigator.serviceWorker.ready.then(reg => {
                    document.getElementById('sw-test-result').innerHTML = '✅ Service Worker Active';
                    document.getElementById('sw-test-result').style.background = '#d4edda';
                    document.getElementById('sw-test-result').style.color = '#155724';
                }).catch(err => {
                    document.getElementById('sw-test-result').innerHTML = '❌ Service Worker Error: ' + err.message;
                    document.getElementById('sw-test-result').style.background = '#f8d7da';
                    document.getElementById('sw-test-result').style.color = '#721c24';
                });
            } else {
                document.getElementById('sw-test-result').innerHTML = '❌ Service Worker not supported in this browser';
                document.getElementById('sw-test-result').style.background = '#f8d7da';
                document.getElementById('sw-test-result').style.color = '#721c24';
            }
            </script>
            """, unsafe_allow_html=True)
    
    with col2:
        if st.button("📊 Get Analytics", use_container_width=True):
            analytics = get_pwa_analytics()
            st.json(analytics)
        
        if st.button("🧹 Clear Cache", use_container_width=True):
            success, message = clear_pwa_cache()
            if success:
                show_toast(message, "success")
                st.rerun()
            else:
                show_toast(message, "error")


# ==============================
# PWA SHORTCUTS
# ==============================
def pwa_shortcuts() -> str:
    """Generate PWA keyboard shortcuts HTML"""
    return """
    <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 10px 0;">
        <h4>⌨️ Keyboard Shortcuts</h4>
        <table style="width: 100%; border-collapse: collapse;">
            <tr style="border-bottom: 1px solid #ddd;">
                <th style="padding: 8px; text-align: left;">Shortcut</th>
                <th style="padding: 8px; text-align: left;">Action</th>
            </tr>
            <tr>
                <td style="padding: 8px;"><kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>I</kbd></td>
                <td style="padding: 8px;">Install PWA</td>
            </tr>
            <tr>
                <td style="padding: 8px;"><kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>C</kbd></td>
                <td style="padding: 8px;">Clear Cache</td>
            </tr>
            <tr>
                <td style="padding: 8px;"><kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>R</kbd></td>
                <td style="padding: 8px;">Reload PWA</td>
            </tr>
            <tr>
                <td style="padding: 8px;"><kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>D</kbd></td>
                <td style="padding: 8px;">Toggle Developer Tools</td>
            </tr>
        </table>
    </div>
    """


# ==============================
# HTTPS CHECK
# ==============================
def check_https() -> str:
    """Check if app is running over HTTPS"""
    return """
    <div id="https-status" style="padding: 10px; border-radius: 5px; margin: 10px 0; background: #f8f9fa;">
        ⏳ Checking HTTPS...
    </div>
    <script>
    if (window.location.protocol === 'https:') {
        document.getElementById('https-status').innerHTML = '✅ HTTPS enabled';
        document.getElementById('https-status').style.background = '#d4edda';
        document.getElementById('https-status').style.color = '#155724';
    } else if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
        document.getElementById('https-status').innerHTML = '⚠️ Running locally - HTTPS not required for development';
        document.getElementById('https-status').style.background = '#fff3cd';
        document.getElementById('https-status').style.color = '#856404';
    } else {
        document.getElementById('https-status').innerHTML = '❌ HTTPS required for PWA features';
        document.getElementById('https-status').style.background = '#f8d7da';
        document.getElementById('https-status').style.color = '#721c24';
    }
    </script>
    """


# ==============================
# PWA SETUP DASHBOARD
# ==============================
def pwa_setup_dashboard():
    """PWA Setup Dashboard"""
    
    st.title("📱 PWA Setup")
    st.caption("Configure Progressive Web App settings")
    
    role = st.session_state.get("role", "cashier")
    
    if role not in ["owner", "manager", "developer"]:
        st.error("❌ Access Denied. PWA setup is for owners, managers, and developers only.")
        return
    
    # Initialize files
    DATA_DIR.mkdir(exist_ok=True)
    PWA_ICONS_DIR.mkdir(parents=True, exist_ok=True)
    PWA_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    Path("static").mkdir(exist_ok=True)
    
    config = load_pwa_config()
    
    # ==============================
    # TABS
    # ==============================
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "⚙️ Settings",
        "📱 App Info",
        "🖼️ Icons",
        "📋 Preview",
        "🧪 Testing",
        "💾 Backup"
    ])
    
    # ==============================
    # TAB 1: SETTINGS
    # ==============================
    with tab1:
        st.markdown("## ⚙️ PWA Settings")
        st.caption("Configure your Progressive Web App")
        
        # Display HTTPS status
        st.markdown(check_https(), unsafe_allow_html=True)
        
        # Display install prompt (hidden by default)
        st.markdown(pwa_install_prompt(), unsafe_allow_html=True)
        
        # Display online status
        st.markdown(offline_status_indicator(), unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            enabled = st.checkbox("Enable PWA", value=config.get("enabled", True))
            app_name = st.text_input("App Name", value=config.get("app_name", "SmartGro Retail"))
            app_short_name = st.text_input("Short Name", value=config.get("app_short_name", "SmartGro"))
            app_description = st.text_area("Description", value=config.get("app_description", "Smart Retail ERP System"))
            
            theme_color = st.color_picker("Theme Color", value=config.get("theme_color", "#6366F1"))
            background_color = st.color_picker("Background Color", value=config.get("background_color", "#FFFFFF"))
        
        with col2:
            display = st.selectbox(
                "Display Mode",
                ["standalone", "fullscreen", "minimal-ui", "browser"],
                index=["standalone", "fullscreen", "minimal-ui", "browser"].index(config.get("display", "standalone"))
            )
            orientation = st.selectbox(
                "Orientation",
                ["portrait", "landscape", "any"],
                index=["portrait", "landscape", "any"].index(config.get("orientation", "portrait"))
            )
            start_url = st.text_input("Start URL", value=config.get("start_url", "/"))
            scope = st.text_input("Scope", value=config.get("scope", "/"))
        
        st.markdown("### 🔧 Advanced Settings")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            offline_enabled = st.checkbox("Offline Support", value=config.get("offline_enabled", True))
            cache_strategy = st.selectbox(
                "Cache Strategy",
                ["network_first", "cache_first", "stale_while_revalidate"],
                index=["network_first", "cache_first", "stale_while_revalidate"].index(
                    config.get("cache_strategy", "network_first")
                )
            )
        
        with col2:
            push_enabled = st.checkbox("Push Notifications", value=config.get("push_enabled", True))
            auto_update = st.checkbox("Auto Update", value=config.get("auto_update", True))
            update_interval = st.number_input(
                "Update Interval (seconds)",
                min_value=60,
                max_value=86400,
                value=config.get("update_interval", 3600)
            )
        
        with col3:
            splash_screen = st.checkbox("Splash Screen", value=config.get("splash_screen", True))
            ios_enabled = st.checkbox("iOS Support", value=config.get("ios_enabled", True))
            splash_color = st.color_picker("Splash Screen Color", value=config.get("splash_screen_color", "#6366F1"))
        
        # Display shortcuts
        st.markdown(pwa_shortcuts(), unsafe_allow_html=True)
        
        if st.button("💾 Save PWA Settings", type="primary", use_container_width=True):
            try:
                config.update({
                    "enabled": enabled,
                    "app_name": app_name,
                    "app_short_name": app_short_name,
                    "app_description": app_description,
                    "theme_color": theme_color,
                    "background_color": background_color,
                    "display": display,
                    "orientation": orientation,
                    "start_url": start_url,
                    "scope": scope,
                    "offline_enabled": offline_enabled,
                    "cache_strategy": cache_strategy,
                    "push_enabled": push_enabled,
                    "auto_update": auto_update,
                    "update_interval": update_interval,
                    "splash_screen": splash_screen,
                    "splash_screen_color": splash_color,
                    "ios_enabled": ios_enabled
                })
                save_pwa_config(config)
                
                # Backup before regenerating
                backup_pwa_config()
                
                # Regenerate files
                generate_manifest()
                generate_service_worker()
                update_pwa_version()
                
                show_toast("PWA settings updated successfully!", "success")
                st.rerun()
            except ValueError as e:
                show_toast(str(e), "error")
            except Exception as e:
                show_toast(f"Error saving settings: {str(e)}", "error")
    
    # ==============================
    # TAB 2: APP INFO
    # ==============================
    with tab2:
        st.markdown("## 📱 App Information")
        st.caption("View and manage PWA app information")
        
        analytics = get_pwa_analytics()
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📋 App Details")
            st.markdown(f"**App Name:** {config.get('app_name', 'SmartGro Retail')}")
            st.markdown(f"**Short Name:** {config.get('app_short_name', 'SmartGro')}")
            st.markdown(f"**Description:** {config.get('app_description', 'Smart Retail ERP System')}")
            st.markdown(f"**Theme Color:** {config.get('theme_color', '#6366F1')}")
            st.markdown(f"**Background Color:** {config.get('background_color', '#FFFFFF')}")
            st.markdown(f"**Display Mode:** {config.get('display', 'standalone')}")
            st.markdown(f"**Orientation:** {config.get('orientation', 'portrait')}")
            st.markdown(f"**Version:** {analytics.get('version', 'unknown')}")
            st.markdown(f"**Build:** {analytics.get('build', 'unknown')}")
        
        with col2:
            st.markdown("### 📊 Status")
            status = "✅ Enabled" if config.get("enabled", True) else "❌ Disabled"
            st.markdown(f"**PWA Status:** {status}")
            st.markdown(f"**Manifest:** {'✅' if analytics.get('manifest', False) else '❌'}")
            st.markdown(f"**Service Worker:** {'✅' if analytics.get('service_worker', False) else '❌'}")
            st.markdown(f"**Icons:** {analytics.get('icons', 0)}")
            st.markdown(f"**Backups:** {analytics.get('backups', 0)}")
            st.markdown(f"**Offline Support:** {'✅' if config.get('offline_enabled', True) else '❌'}")
            st.markdown(f"**Push Notifications:** {'✅' if config.get('push_enabled', True) else '❌'}")
            st.markdown(f"**Auto Update:** {'✅' if config.get('auto_update', True) else '❌'}")
            st.markdown(f"**iOS Support:** {'✅' if config.get('ios_enabled', True) else '❌'}")
            st.markdown(f"**Splash Screen:** {'✅' if config.get('splash_screen', True) else '❌'}")
            
            st.markdown("### 🔗 URLs")
            st.markdown("**Manifest:**")
            st.code("/static/manifest.json", language="text")
            st.markdown("**Service Worker:**")
            st.code("/static/sw.js", language="text")
            st.markdown("**Version:**")
            st.code("/static/version.json", language="text")
        
        st.markdown("### 📱 Installation Instructions")
        st.markdown("""
        #### Android (Chrome)
        1. Open the app in Chrome
        2. Tap the menu button (⋮)
        3. Select "Add to Home Screen"
        4. Confirm the installation
        
        #### iOS (Safari)
        1. Open the app in Safari
        2. Tap the share button (⬆)
        3. Select "Add to Home Screen"
        4. Confirm the installation
        
        #### Desktop (Chrome/Edge)
        1. Open the app in Chrome/Edge
        2. Click the install icon (⊕) in the address bar
        3. Confirm the installation
        """)
        
        # Display version info
        st.markdown("### 📦 Version History")
        version_info = get_pwa_version()
        st.json(version_info)
    
    # ==============================
    # TAB 3: ICONS
    # ==============================
    with tab3:
        st.markdown("## 🖼️ PWA Icons")
        st.caption("Manage PWA icons")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📐 Icon Sizes")
            sizes = config.get("icon_sizes", [72, 96, 128, 144, 152, 192, 384, 512])
            st.json(sizes)
        
        with col2:
            st.markdown("### 🍎 iOS Icon Sizes")
            ios_sizes = config.get("ios_icon_sizes", [180, 192, 512])
            st.json(ios_sizes)
        
        st.markdown("### 🖼️ Generate Icons")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Generate All Icons", type="primary", use_container_width=True):
                try:
                    count = generate_all_icons()
                    if count > 0:
                        show_toast(f"{count} icons generated successfully!", "success")
                    else:
                        show_toast("All icons already exist!", "info")
                    st.rerun()
                except Exception as e:
                    show_toast(f"Error generating icons: {str(e)}", "error")
        
        with col2:
            if st.button("🧹 Clear All Icons", use_container_width=True):
                try:
                    if PWA_ICONS_DIR.exists():
                        for icon in PWA_ICONS_DIR.glob("*.png"):
                            icon.unlink()
                        show_toast("All icons cleared!", "success")
                        st.rerun()
                except Exception as e:
                    show_toast(f"Error clearing icons: {str(e)}", "error")
        
        st.markdown("### 📁 Icon Files")
        
        if PWA_ICONS_DIR.exists():
            icons = list(PWA_ICONS_DIR.glob("*.png"))
            if icons:
                cols = st.columns(4)
                for idx, icon in enumerate(icons[:12]):
                    with cols[idx % 4]:
                        st.image(str(icon), caption=icon.name, use_container_width=True)
                if len(icons) > 12:
                    st.caption(f"Showing 12 of {len(icons)} icons")
            else:
                st.info("No icons found. Click 'Generate All Icons' to create them.")
        else:
            st.info("Icons directory not found. Click 'Generate All Icons' to create it.")
        
        st.markdown("### 📤 Upload Custom Icons")
        
        uploaded_file = st.file_uploader("Upload icon (PNG only)", type=["png"])
        
        if uploaded_file:
            col1, col2 = st.columns(2)
            with col1:
                size = st.number_input("Icon Size (pixels)", min_value=16, max_value=1024, value=192)
            
            with col2:
                icon_name = st.selectbox(
                    "Icon Type",
                    ["Standard Icon", "Apple Icon"],
                    format_func=lambda x: "icon-{size}x{size}.png" if x == "Standard Icon" else "apple-icon-{size}x{size}.png"
                )
            
            if st.button("📤 Upload Icon", use_container_width=True):
                try:
                    if icon_name == "Standard Icon":
                        icon_path = PWA_ICONS_DIR / f"icon-{size}x{size}.png"
                    else:
                        icon_path = PWA_ICONS_DIR / f"apple-icon-{size}x{size}.png"
                    
                    icon_path.write_bytes(uploaded_file.getvalue())
                    show_toast(f"Icon uploaded: {icon_path.name}", "success")
                    st.rerun()
                except Exception as e:
                    show_toast(f"Error uploading icon: {str(e)}", "error")
    
    # ==============================
    # TAB 4: PREVIEW
    # ==============================
    with tab4:
        st.markdown("## 📋 PWA Preview")
        st.caption("Preview your PWA settings")
        
        # Display install prompt (hidden by default)
        st.markdown(pwa_install_prompt(), unsafe_allow_html=True)
        
        st.markdown("### 📱 App Preview")
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.markdown("#### App Icon")
            icon_path = PWA_ICONS_DIR / "icon-192x192.png"
            if icon_path.exists():
                st.image(str(icon_path), width=128)
            else:
                st.info("No icon found")
        
        with col2:
            st.markdown("#### App Details")
            st.markdown(f"**Name:** {config.get('app_name', 'SmartGro Retail')}")
            st.markdown(f"**Theme Color:** {config.get('theme_color', '#6366F1')}")
            st.markdown(f"**Background:** {config.get('background_color', '#FFFFFF')}")
            
            st.markdown("**Color Preview:**")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"""
                <div style="background: {config.get('theme_color', '#6366F1')}; 
                            padding: 20px; 
                            border-radius: 8px; 
                            text-align: center; 
                            color: white;">
                    Theme Color
                </div>
                """, unsafe_allow_html=True)
            with col2:
                st.markdown(f"""
                <div style="background: {config.get('background_color', '#FFFFFF')}; 
                            padding: 20px; 
                            border-radius: 8px; 
                            text-align: center; 
                            border: 1px solid #ddd;">
                    Background Color
                </div>
                """, unsafe_allow_html=True)
        
        st.markdown("### 📄 Manifest JSON")
        if PWA_MANIFEST_FILE.exists():
            manifest_data = json.loads(PWA_MANIFEST_FILE.read_text())
            st.json(manifest_data)
        else:
            st.info("Manifest not found")
        
        st.markdown("### 🔧 Service Worker")
        if PWA_SW_FILE.exists():
            sw_content = PWA_SW_FILE.read_text()
            with st.expander("View Service Worker Code"):
                st.code(sw_content, language="javascript")
        else:
            st.info("Service Worker not found")
        
        st.markdown("### 🏷️ Meta Tags")
        st.code(generate_meta_tags(), language="html")
        
        st.markdown("### 📱 PWA Status")
        analytics = get_pwa_analytics()
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Status", "✅ Active" if analytics.get('enabled', False) else "❌ Disabled")
        with col2:
            st.metric("Version", analytics.get('version', 'unknown'))
        with col3:
            st.metric("Icons", analytics.get('icons', 0))
        
        st.info("💡 To test the PWA, deploy the app and access it via HTTPS.")
    
    # ==============================
    # TAB 5: TESTING
    # ==============================
    with tab5:
        st.markdown("## 🧪 PWA Testing Tools")
        st.caption("Test and validate your PWA configuration")
        
        # HTTPS check
        st.markdown(check_https(), unsafe_allow_html=True)
        
        # Testing tools
        pwa_test_tools()
        
        st.markdown("### 📊 PWA Analytics")
        analytics = get_pwa_analytics()
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Manifest", "✅" if analytics.get('manifest', False) else "❌")
        with col2:
            st.metric("Service Worker", "✅" if analytics.get('service_worker', False) else "❌")
        with col3:
            st.metric("Icons", analytics.get('icons', 0))
        with col4:
            st.metric("Backups", analytics.get('backups', 0))
        
        st.markdown("### 🔧 Diagnostic Information")
        st.json({
            "config_file": str(PWA_CONFIG_FILE),
            "manifest_file": str(PWA_MANIFEST_FILE),
            "sw_file": str(PWA_SW_FILE),
            "icons_dir": str(PWA_ICONS_DIR),
            "backup_dir": str(PWA_BACKUP_DIR),
            "config_exists": PWA_CONFIG_FILE.exists(),
            "manifest_exists": PWA_MANIFEST_FILE.exists(),
            "sw_exists": PWA_SW_FILE.exists()
        })
    
    # ==============================
    # TAB 6: BACKUP
    # ==============================
    with tab6:
        st.markdown("## 💾 Backup & Restore")
        st.caption("Manage PWA configuration backups")
        
        # Backup section
        st.markdown("### 📤 Create Backup")
        if st.button("📤 Create Backup", type="primary", use_container_width=True):
            success, message = backup_pwa_config()
            if success:
                show_toast(message, "success")
                st.rerun()
            else:
                show_toast(message, "error")
        
        # Restore section
        st.markdown("### 📥 Restore Backup")
        
        backups = sorted(PWA_BACKUP_DIR.glob("pwa_config_*.json"), reverse=True)
        
        if backups:
            backup_options = [f"{b.name} ({datetime.fromtimestamp(b.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')})" for b in backups]
            selected_backup = st.selectbox("Select Backup to Restore", backup_options)
            
            if st.button("📥 Restore Selected Backup", use_container_width=True):
                try:
                    backup_index = backup_options.index(selected_backup)
                    backup_file = backups[backup_index]
                    success, message = restore_pwa_config(backup_file)
                    if success:
                        show_toast(message, "success")
                        st.rerun()
                    else:
                        show_toast(message, "error")
                except Exception as e:
                    show_toast(f"Error restoring backup: {str(e)}", "error")
        else:
            st.info("No backups found")
        
        # Clear cache section
        st.markdown("### 🧹 Maintenance")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🧹 Clear PWA Cache", use_container_width=True):
                success, message = clear_pwa_cache()
                if success:
                    show_toast(message, "success")
                    st.rerun()
                else:
                    show_toast(message, "error")
        
        with col2:
            if st.button("🔄 Reset to Default", use_container_width=True):
                try:
                    # Backup current config
                    backup_pwa_config()
                    
                    # Reset config
                    default_config = get_default_config()
                    save_pwa_config(default_config)
                    
                    # Regenerate files
                    generate_manifest()
                    generate_service_worker()
                    update_pwa_version()
                    
                    show_toast("Reset to default settings successfully!", "success")
                    st.rerun()
                except Exception as e:
                    show_toast(f"Error resetting: {str(e)}", "error")
        
        # List backups
        st.markdown("### 📋 Backup History")
        if backups:
            backup_data = []
            for backup in backups:
                backup_data.append({
                    "File": backup.name,
                    "Date": datetime.fromtimestamp(backup.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                    "Size": f"{backup.stat().st_size / 1024:.2f} KB"
                })
            st.dataframe(backup_data, use_container_width=True, hide_index=True)
        else:
            st.info("No backups available")


# ==============================
# PWA UTILITY FUNCTIONS
# ==============================
def get_pwa_meta_tags() -> str:
    """Get PWA meta tags for embedding in HTML"""
    return generate_meta_tags()


def get_pwa_config() -> Dict[str, Any]:
    """Get PWA configuration"""
    return load_pwa_config()


def is_pwa_enabled() -> bool:
    """Check if PWA is enabled"""
    config = load_pwa_config()
    return config.get("enabled", True)


def get_pwa_version_info() -> Dict[str, Any]:
    """Get PWA version information"""
    return get_pwa_version()


def get_pwa_install_prompt() -> str:
    """Get PWA install prompt HTML - Hidden by default"""
    return pwa_install_prompt()


def get_offline_status() -> str:
    """Get offline status indicator HTML"""
    return offline_status_indicator()


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    pwa_setup_dashboard()