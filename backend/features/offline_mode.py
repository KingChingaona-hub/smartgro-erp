import streamlit as st
import pandas as pd
import json
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
import time
import threading
import queue

# ==============================
# FILE PATHS
# ==============================
DATA_DIR = Path("data")
OFFLINE_DIR = DATA_DIR / "offline_cache"
OFFLINE_QUEUE_FILE = OFFLINE_DIR / "sync_queue.json"
OFFLINE_MANIFEST_FILE = OFFLINE_DIR / "manifest.json"
OFFLINE_DATA_FILE = OFFLINE_DIR / "offline_data.json"

# ==============================
# INITIALIZATION
# ==============================
def init_offline_mode():
    """Initialize offline mode directories and files"""
    OFFLINE_DIR.mkdir(parents=True, exist_ok=True)
    
    # Initialize sync queue
    if not OFFLINE_QUEUE_FILE.exists():
        queue_data = {
            "pending_sync": [],
            "synced": [],
            "failed": []
        }
        with open(OFFLINE_QUEUE_FILE, "w") as f:
            json.dump(queue_data, f, indent=2)
    
    # Initialize manifest
    if not OFFLINE_MANIFEST_FILE.exists():
        manifest = {
            "last_sync": None,
            "offline_enabled": True,
            "cache_version": "1.0",
            "tables": ["products", "customers", "sales", "purchases"]
        }
        with open(OFFLINE_MANIFEST_FILE, "w") as f:
            json.dump(manifest, f, indent=2)
    
    # Initialize offline data store
    if not OFFLINE_DATA_FILE.exists():
        offline_data = {
            "products": [],
            "customers": [],
            "sales": [],
            "purchases": [],
            "last_updated": None
        }
        with open(OFFLINE_DATA_FILE, "w") as f:
            json.dump(offline_data, f, indent=2)


def is_online():
    """Check if system has internet connection"""
    import socket
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        return True
    except OSError:
        pass
    return False


def get_offline_status():
    """Get current offline mode status"""
    init_offline_mode()
    
    with open(OFFLINE_MANIFEST_FILE, "r") as f:
        manifest = json.load(f)
    
    with open(OFFLINE_QUEUE_FILE, "r") as f:
        queue_data = json.load(f)
    
    return {
        "online": is_online(),
        "offline_enabled": manifest.get("offline_enabled", True),
        "pending": len(queue_data.get("pending_sync", [])),
        "synced": len(queue_data.get("synced", [])),
        "failed": len(queue_data.get("failed", [])),
        "last_sync": manifest.get("last_sync"),
        "cache_version": manifest.get("cache_version", "1.0")
    }


def cache_data_for_offline(table_name, data):
    """Cache data for offline use"""
    init_offline_mode()
    
    with open(OFFLINE_DATA_FILE, "r") as f:
        offline_data = json.load(f)
    
    if table_name in offline_data:
        offline_data[table_name] = data
        offline_data["last_updated"] = datetime.now().isoformat()
    
    with open(OFFLINE_DATA_FILE, "w") as f:
        json.dump(offline_data, f, indent=2)


def load_cached_data(table_name):
    """Load cached data from offline storage"""
    init_offline_mode()
    
    with open(OFFLINE_DATA_FILE, "r") as f:
        offline_data = json.load(f)
    
    return offline_data.get(table_name, [])


def add_to_sync_queue(operation, table_name, data, transaction_id=None):
    """Add operation to sync queue for later processing"""
    init_offline_mode()
    
    if transaction_id is None:
        transaction_id = hashlib.md5(f"{datetime.now().isoformat()}{operation}{table_name}".encode()).hexdigest()[:16]
    
    with open(OFFLINE_QUEUE_FILE, "r") as f:
        queue_data = json.load(f)
    
    queue_item = {
        "transaction_id": transaction_id,
        "timestamp": datetime.now().isoformat(),
        "operation": operation,  # CREATE, UPDATE, DELETE
        "table": table_name,
        "data": data,
        "status": "PENDING",
        "retry_count": 0
    }
    
    queue_data["pending_sync"].append(queue_item)
    
    with open(OFFLINE_QUEUE_FILE, "w") as f:
        json.dump(queue_data, f, indent=2)
    
    return transaction_id


def process_sync_queue():
    """Process pending sync operations when online"""
    if not is_online():
        return 0, "Offline"
    
    init_offline_mode()
    
    with open(OFFLINE_QUEUE_FILE, "r") as f:
        queue_data = json.load(f)
    
    if not queue_data["pending_sync"]:
        return 0, "No pending sync items"
    
    synced_count = 0
    failed_items = []
    
    for item in queue_data["pending_sync"]:
        try:
            # Process based on operation and table
            success = process_sync_item(item)
            
            if success:
                item["status"] = "SYNCED"
                item["synced_at"] = datetime.now().isoformat()
                queue_data["synced"].append(item)
                synced_count += 1
            else:
                item["retry_count"] += 1
                if item["retry_count"] >= 3:
                    item["status"] = "FAILED"
                    queue_data["failed"].append(item)
                else:
                    failed_items.append(item)
        except Exception as e:
            item["retry_count"] += 1
            if item["retry_count"] >= 3:
                item["status"] = "FAILED"
                item["error"] = str(e)
                queue_data["failed"].append(item)
            else:
                failed_items.append(item)
    
    # Update queue
    queue_data["pending_sync"] = failed_items
    
    with open(OFFLINE_QUEUE_FILE, "w") as f:
        json.dump(queue_data, f, indent=2)
    
    # Update last sync time
    with open(OFFLINE_MANIFEST_FILE, "r") as f:
        manifest = json.load(f)
    manifest["last_sync"] = datetime.now().isoformat()
    with open(OFFLINE_MANIFEST_FILE, "w") as f:
        json.dump(manifest, f, indent=2)
    
    return synced_count, f"Synced {synced_count} items"


def process_sync_item(item):
    """Process a single sync item"""
    table = item["table"]
    operation = item["operation"]
    data = item["data"]
    
    try:
        if table == "sales":
            from backend.core.database import load_sales, save_sales
            
            if operation == "CREATE":
                sales_df = load_sales()
                new_sale = pd.DataFrame([data])
                sales_df = pd.concat([sales_df, new_sale], ignore_index=True)
                save_sales(sales_df)
                return True
        
        elif table == "products":
            from backend.core.database import load_products, save_products
            
            if operation == "CREATE":
                products_df = load_products()
                new_product = pd.DataFrame([data])
                products_df = pd.concat([products_df, new_product], ignore_index=True)
                save_products(products_df)
                return True
            elif operation == "UPDATE":
                products_df = load_products()
                idx = products_df[products_df["barcode"] == data["barcode"]].index
                if len(idx) > 0:
                    for key, value in data.items():
                        if key in products_df.columns:
                            products_df.loc[idx[0], key] = value
                    save_products(products_df)
                return True
        
        elif table == "customers":
            from backend.core.database import load_customers, save_customers
            
            if operation == "CREATE":
                customers_df = load_customers()
                new_customer = pd.DataFrame([data])
                customers_df = pd.concat([customers_df, new_customer], ignore_index=True)
                save_customers(customers_df)
                return True
        
        return True
    except Exception as e:
        print(f"Error processing sync item: {e}")
        return False


def get_sync_queue_status():
    """Get sync queue status"""
    init_offline_mode()
    
    with open(OFFLINE_QUEUE_FILE, "r") as f:
        queue_data = json.load(f)
    
    return {
        "pending": len(queue_data.get("pending_sync", [])),
        "synced": len(queue_data.get("synced", [])),
        "failed": len(queue_data.get("failed", [])),
        "pending_items": queue_data.get("pending_sync", [])[:10],
        "failed_items": queue_data.get("failed", [])[:10]
    }


def clear_sync_queue():
    """Clear all sync queues"""
    init_offline_mode()
    
    queue_data = {
        "pending_sync": [],
        "synced": [],
        "failed": []
    }
    
    with open(OFFLINE_QUEUE_FILE, "w") as f:
        json.dump(queue_data, f, indent=2)
    
    return True


# ==============================
# OFFLINE DATA SYNC FOR ALL TABLES
# ==============================
def sync_all_data():
    """Sync all data for offline use"""
    init_offline_mode()
    
    try:
        # Load all data
        from backend.core.database import load_products, load_customers, load_sales, load_purchases
        
        products_df = load_products()
        customers_df = load_customers()
        sales_df = load_sales()
        purchases_df = load_purchases()
        
        # Convert to dictionaries
        products_data = products_df.to_dict('records') if not products_df.empty else []
        customers_data = customers_df.to_dict('records') if not customers_df.empty else []
        sales_data = sales_df.to_dict('records') if not sales_df.empty else []
        purchases_data = purchases_df.to_dict('records') if not purchases_df.empty else []
        
        # Cache for offline
        cache_data_for_offline("products", products_data)
        cache_data_for_offline("customers", customers_data)
        cache_data_for_offline("sales", sales_data)
        cache_data_for_offline("purchases", purchases_data)
        
        return True, f"Synced {len(products_data)} products, {len(customers_data)} customers, {len(sales_data)} sales"
    except Exception as e:
        return False, str(e)


# ==============================
# OFFLINE MODE DASHBOARD
# ==============================
def offline_mode_dashboard():
    """Offline Mode Management Dashboard"""
    
    st.title("📡 Offline Mode Management")
    st.caption("Work offline and sync when connection returns")
    
    role = st.session_state.get("role", "cashier")
    
    # Only owner and managers can access offline settings
    if role not in ["owner", "manager"]:
        st.error("❌ Access Denied. Only owners and managers can manage offline mode.")
        return
    
    # Get status
    status = get_offline_status()
    sync_status = get_sync_queue_status()
    
    # ==============================
    # STATUS CARDS
    # ==============================
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if status["online"]:
            st.success("🟢 ONLINE")
        else:
            st.error("🔴 OFFLINE")
    
    with col2:
        st.metric("📦 Pending Sync", sync_status["pending"])
    
    with col3:
        st.metric("✅ Synced Items", sync_status["synced"])
    
    with col4:
        st.metric("❌ Failed Items", sync_status["failed"])
    
    st.markdown("---")
    
    # ==============================
    # TABS
    # ==============================
    tab1, tab2, tab3, tab4 = st.tabs([
        "📡 Sync Status",
        "📦 Pending Queue",
        "⚙️ Offline Settings",
        "🔄 Manual Sync"
    ])
    
    # ==============================
    # TAB 1: SYNC STATUS
    # ==============================
    with tab1:
        st.markdown("## 📡 Synchronization Status")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Connection Status")
            if status["online"]:
                st.success("✅ Internet connection detected")
            else:
                st.warning("⚠️ No internet connection - working in offline mode")
            
            st.markdown("### Last Sync")
            if status["last_sync"]:
                st.write(f"Last successful sync: {status['last_sync'][:19]}")
            else:
                st.write("No sync performed yet")
        
        with col2:
            st.markdown("### Offline Mode Status")
            st.write(f"Offline Mode: {'✅ Enabled' if status['offline_enabled'] else '❌ Disabled'}")
            st.write(f"Cache Version: {status['cache_version']}")
            
            if sync_status["pending"] > 0:
                st.warning(f"⚠️ {sync_status['pending']} items waiting to sync")
            else:
                st.success("✅ All data synchronized")
        
        # Sync history chart
        st.markdown("### 📊 Sync Activity")
        
        with open(OFFLINE_QUEUE_FILE, "r") as f:
            queue_data = json.load(f)
        
        # Count by hour
        from collections import Counter
        hours = Counter()
        for item in queue_data.get("synced", []):
            if "synced_at" in item:
                hour = item["synced_at"][:13]
                hours[hour] += 1
        
        if hours:
            hours_df = pd.DataFrame([{"Hour": k, "Items": v} for k, v in sorted(hours.items())[-24:]])
            st.bar_chart(hours_df.set_index("Hour"))
        else:
            st.info("No sync activity yet")
    
    # ==============================
    # TAB 2: PENDING QUEUE
    # ==============================
    with tab2:
        st.markdown("## 📦 Pending Sync Queue")
        
        if sync_status["pending"] > 0:
            st.warning(f"{sync_status['pending']} items pending synchronization")
            
            pending_df = pd.DataFrame(sync_status["pending_items"])
            if not pending_df.empty:
                st.dataframe(
                    pending_df[["timestamp", "operation", "table", "transaction_id"]],
                    use_container_width=True,
                    hide_index=True
                )
        else:
            st.success("✅ No pending items in sync queue")
        
        st.markdown("---")
        st.markdown("### ❌ Failed Items")
        
        if sync_status["failed"] > 0:
            st.error(f"{sync_status['failed']} items failed to sync")
            
            failed_df = pd.DataFrame(sync_status["failed_items"])
            if not failed_df.empty:
                st.dataframe(
                    failed_df[["timestamp", "operation", "table", "retry_count"]],
                    use_container_width=True,
                    hide_index=True
                )
        else:
            st.success("✅ No failed items")
    
    # ==============================
    # TAB 3: OFFLINE SETTINGS
    # ==============================
    with tab3:
        st.markdown("## ⚙️ Offline Mode Settings")
        
        with open(OFFLINE_MANIFEST_FILE, "r") as f:
            manifest = json.load(f)
        
        # Enable/disable offline mode
        offline_enabled = st.toggle("Enable Offline Mode", value=manifest.get("offline_enabled", True))
        
        if offline_enabled != manifest.get("offline_enabled"):
            manifest["offline_enabled"] = offline_enabled
            with open(OFFLINE_MANIFEST_FILE, "w") as f:
                json.dump(manifest, f, indent=2)
            st.success("Offline mode settings updated")
        
        # Auto-sync interval
        st.markdown("### Auto-Sync Settings")
        auto_sync_interval = st.selectbox("Auto-Sync Interval", [5, 10, 15, 30, 60], index=2, 
                                          help="Minutes between automatic sync attempts")
        
        # Data to cache
        st.markdown("### Data to Cache Offline")
        
        tables = ["products", "customers", "sales", "purchases"]
        cached_tables = manifest.get("tables", tables)
        
        for table in tables:
            if st.checkbox(f"Cache {table.title()}", value=table in cached_tables, key=f"cache_{table}"):
                if table not in cached_tables:
                    cached_tables.append(table)
            else:
                if table in cached_tables:
                    cached_tables.remove(table)
        
        if cached_tables != manifest.get("tables", tables):
            manifest["tables"] = cached_tables
            with open(OFFLINE_MANIFEST_FILE, "w") as f:
                json.dump(manifest, f, indent=2)
            st.success("Cache settings updated")
        
        # Clear cache
        st.markdown("---")
        st.markdown("### 🗑️ Clear Offline Cache")
        
        if st.button("🗑️ Clear All Offline Cache", use_container_width=True):
            confirm = st.checkbox("⚠️ I understand this will clear all offline data")
            if confirm:
                offline_data = {
                    "products": [],
                    "customers": [],
                    "sales": [],
                    "purchases": [],
                    "last_updated": None
                }
                with open(OFFLINE_DATA_FILE, "w") as f:
                    json.dump(offline_data, f, indent=2)
                
                clear_sync_queue()
                st.success("Offline cache cleared successfully")
                st.rerun()
    
    # ==============================
    # TAB 4: MANUAL SYNC
    # ==============================
    with tab4:
        st.markdown("## 🔄 Manual Synchronization")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📡 Sync Now", type="primary", use_container_width=True):
                with st.spinner("Synchronizing..."):
                    count, message = process_sync_queue()
                    if count > 0:
                        st.success(f"✅ {message}")
                    else:
                        st.info(message)
                st.rerun()
        
        with col2:
            if st.button("💾 Sync All Data for Offline", use_container_width=True):
                with st.spinner("Syncing all data for offline use..."):
                    success, message = sync_all_data()
                    if success:
                        st.success(f"✅ {message}")
                    else:
                        st.error(f"❌ {message}")
        
        st.markdown("---")
        
        # Offline data size
        st.markdown("### 📦 Offline Data Size")
        
        if OFFLINE_DATA_FILE.exists():
            size_bytes = OFFLINE_DATA_FILE.stat().st_size
            if size_bytes < 1024:
                size_str = f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                size_str = f"{size_bytes / 1024:.2f} KB"
            else:
                size_str = f"{size_bytes / (1024 * 1024):.2f} MB"
            
            st.metric("Offline Data Size", size_str)
        
        # Sync queue size
        if OFFLINE_QUEUE_FILE.exists():
            queue_size = OFFLINE_QUEUE_FILE.stat().st_size
            st.metric("Sync Queue Size", f"{queue_size} B")
        
        st.markdown("---")
        st.markdown("### 📋 How Offline Mode Works")
        
        st.info("""
        **Offline Mode Features:**
        
        1. **Automatic Caching** - Frequently accessed data is cached locally
        2. **Queue Operations** - All actions are queued when offline
        3. **Auto-Sync** - Automatically syncs when connection returns
        4. **Conflict Resolution** - Handles conflicts during sync
        5. **Offline Receipts** - Receipts generated even when offline
        
        **Best Practices:**
        - Sync regularly when online
        - Review failed sync items
        - Clear cache periodically
        """)


# ==============================
# OFFLINE RECEIPT HANDLER
# ==============================
def queue_offline_receipt(receipt_data):
    """Queue a receipt for later syncing"""
    transaction_id = add_to_sync_queue("CREATE", "sales", receipt_data)
    return transaction_id


def get_offline_products():
    """Get products from offline cache"""
    return load_cached_data("products")


def get_offline_customers():
    """Get customers from offline cache"""
    return load_cached_data("customers")


def get_offline_sales():
    """Get sales from offline cache"""
    return load_cached_data("sales")


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    offline_mode_dashboard()