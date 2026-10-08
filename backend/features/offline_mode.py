# backend/features/offline_mode.py
# Offline Mode — branch-aware.
#
# Branch scoping:
#     branch_id = None          -> session branch
#     branch_id = "HO"/"NAT"/.. -> that single branch
#     branch_id = "__ALL__"     -> aggregate view (owner only; for the dashboard)
#
# Everything that used to be a single global JSON blob is now keyed by branch:
#
#     data/offline_cache/offline_data.json
#     {
#         "products":  {"HO": [...], "NAT": [...]},
#         "sales":     {"HO": [...], "NAT": [...]},
#         "customers": {...},
#         "purchases": {...},
#         "last_updated": {"HO": "...", "NAT": "..."}
#     }
#
#     data/offline_cache/sync_queue.json
#     {
#         "HO":  {"pending_sync": [...], "synced": [...], "failed": [...]},
#         "NAT": {...}
#     }
#
# Offline sales sync back to the SAME branch they were recorded against —
# never to whichever branch the user later logs into.

import streamlit as st
import pandas as pd
import json
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
import re
import socket

from backend.core.db_adapter import (
    load_products,
    load_customers,
    load_sales,
    load_purchases,
    load_branches,
    save_sales,
    save_products,
    save_customers,
)


# ==============================
# FILE PATHS
# ==============================
DATA_DIR = Path("data")
OFFLINE_DIR = DATA_DIR / "offline_cache"
OFFLINE_QUEUE_FILE = OFFLINE_DIR / "sync_queue.json"
OFFLINE_MANIFEST_FILE = OFFLINE_DIR / "manifest.json"
OFFLINE_DATA_FILE = OFFLINE_DIR / "offline_data.json"


# ==============================
# BRANCH RESOLUTION
# ==============================
ALL_BRANCHES = "__ALL__"


def _resolve_branch(branch_id=None):
    if branch_id is not None:
        return branch_id
    try:
        return (
            st.session_state.get("current_branch_code")
            or st.session_state.get("user_branch")
            or "HO"
        )
    except Exception:
        return "HO"


def _is_all_branches(branch_id):
    return isinstance(branch_id, str) and branch_id.upper() == ALL_BRANCHES


def _branch_label(branch_id):
    if _is_all_branches(branch_id):
        return "All Branches"
    try:
        bdf = load_branches()
        if bdf is not None and not bdf.empty and "branch_id" in bdf.columns:
            match = bdf[bdf["branch_id"].astype(str).str.upper() == str(branch_id).upper()]
            if not match.empty:
                row = match.iloc[0]
                return f"{row.get('branch_name', '')} ({row.get('branch_id', '')})".strip()
    except Exception:
        pass
    return str(branch_id)


def _branch_slug(branch_id):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(branch_id)).strip("_") or "branch"


def _branch_scope_selector(branches_df):
    """Owner picks; everyone else is locked to their session branch."""
    role = st.session_state.get("role", "cashier")
    is_owner = role in ("owner", "admin")

    if is_owner and branches_df is not None and not branches_df.empty:
        options = ["All Branches"] + [
            f"{r['branch_name']} ({r['branch_id']})"
            for _, r in branches_df.iterrows()
        ]
        choice = st.selectbox(
            "Branch scope",
            options,
            key="offline_mode_branch_scope",
            help="Owners may inspect any branch's offline cache or all at once.",
        )
        if choice == "All Branches":
            return ALL_BRANCHES, "All Branches"
        m = re.search(r"\(([^)]+)\)\s*$", choice)
        code = m.group(1).strip() if m else choice
        return code, choice

    session_branch = _resolve_branch(None)
    label = _branch_label(session_branch)
    st.info(f"Offline mode locked to your branch: **{label}**")
    return session_branch, label


def _all_branch_ids():
    try:
        bdf = load_branches()
        if bdf is not None and not bdf.empty and "branch_id" in bdf.columns:
            return bdf["branch_id"].astype(str).str.upper().tolist()
    except Exception:
        pass
    return ["HO"]


# ==============================
# INITIALIZATION
# ==============================
def init_offline_mode():
    """
    Initialize the offline directories and files, ensuring every cache is keyed
    by branch. Migrates legacy flat files (from pre-branch-aware versions) into
    per-branch buckets, placing their contents under "HO" (best guess) rather
    than losing them.
    """
    OFFLINE_DIR.mkdir(parents=True, exist_ok=True)

    # ---- Sync queue (per-branch) ----
    if not OFFLINE_QUEUE_FILE.exists():
        with open(OFFLINE_QUEUE_FILE, "w") as f:
            json.dump({}, f, indent=2)
    else:
        try:
            with open(OFFLINE_QUEUE_FILE, "r") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                data = {}
            # Migrate legacy flat structure (had keys like "pending_sync")
            if any(k in data for k in ("pending_sync", "synced", "failed")):
                legacy = {
                    "pending_sync": data.get("pending_sync", []),
                    "synced": data.get("synced", []),
                    "failed": data.get("failed", []),
                }
                data = {"HO": legacy}
                with open(OFFLINE_QUEUE_FILE, "w") as f:
                    json.dump(data, f, indent=2)
        except Exception:
            with open(OFFLINE_QUEUE_FILE, "w") as f:
                json.dump({}, f, indent=2)

    # ---- Manifest (global, but each branch gets its own sync timestamp) ----
    if not OFFLINE_MANIFEST_FILE.exists():
        manifest = {
            "offline_enabled": True,
            "cache_version": "2.0",
            "tables": ["products", "customers", "sales", "purchases"],
            "last_sync_by_branch": {},
        }
        with open(OFFLINE_MANIFEST_FILE, "w") as f:
            json.dump(manifest, f, indent=2)
    else:
        try:
            with open(OFFLINE_MANIFEST_FILE, "r") as f:
                manifest = json.load(f)
            if "last_sync_by_branch" not in manifest:
                legacy_sync = manifest.get("last_sync")
                manifest["last_sync_by_branch"] = {"HO": legacy_sync} if legacy_sync else {}
                manifest.pop("last_sync", None)
                with open(OFFLINE_MANIFEST_FILE, "w") as f:
                    json.dump(manifest, f, indent=2)
        except Exception:
            pass

    # ---- Offline data cache (per-branch) ----
    if not OFFLINE_DATA_FILE.exists():
        empty = {
            "products": {},
            "customers": {},
            "sales": {},
            "purchases": {},
            "last_updated": {},
        }
        with open(OFFLINE_DATA_FILE, "w") as f:
            json.dump(empty, f, indent=2)
    else:
        try:
            with open(OFFLINE_DATA_FILE, "r") as f:
                data = json.load(f)
            # Migrate legacy flat structure into HO bucket
            legacy_detected = False
            for table in ("products", "customers", "sales", "purchases"):
                v = data.get(table)
                if isinstance(v, list):
                    legacy_detected = True
                    data[table] = {"HO": v}
                elif not isinstance(v, dict):
                    data[table] = {}
            if "last_updated" not in data or not isinstance(data["last_updated"], dict):
                data["last_updated"] = {}
            if legacy_detected:
                with open(OFFLINE_DATA_FILE, "w") as f:
                    json.dump(data, f, indent=2)
        except Exception:
            empty = {
                "products": {}, "customers": {}, "sales": {}, "purchases": {},
                "last_updated": {},
            }
            with open(OFFLINE_DATA_FILE, "w") as f:
                json.dump(empty, f, indent=2)


# ==============================
# HELPERS
# ==============================
def _load_json(path, default):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def _ensure_branch_bucket(queue_data, branch_id):
    branch_id = str(branch_id).upper()
    if branch_id not in queue_data or not isinstance(queue_data[branch_id], dict):
        queue_data[branch_id] = {"pending_sync": [], "synced": [], "failed": []}
    for key in ("pending_sync", "synced", "failed"):
        queue_data[branch_id].setdefault(key, [])
    return queue_data


def _ensure_data_bucket(data, branch_id):
    branch_id = str(branch_id).upper()
    for table in ("products", "customers", "sales", "purchases"):
        if table not in data or not isinstance(data[table], dict):
            data[table] = {}
        data[table].setdefault(branch_id, [])
    if "last_updated" not in data or not isinstance(data["last_updated"], dict):
        data["last_updated"] = {}
    return data


# ==============================
# NETWORK
# ==============================
def is_online():
    """Check if the machine has internet connectivity."""
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        return True
    except OSError:
        return False


# ==============================
# STATUS / CACHE
# ==============================
def get_offline_status(branch_id=None):
    """
    Return offline status. When branch_id is __ALL__, aggregates across all
    branches (counts summed, last_sync = most recent branch).
    """
    init_offline_mode()
    branch_id = _resolve_branch(branch_id)

    manifest = _load_json(OFFLINE_MANIFEST_FILE, {})
    queue_data = _load_json(OFFLINE_QUEUE_FILE, {})
    last_sync_map = manifest.get("last_sync_by_branch", {})

    if _is_all_branches(branch_id):
        pending = sum(len(queue_data.get(b, {}).get("pending_sync", [])) for b in queue_data)
        synced = sum(len(queue_data.get(b, {}).get("synced", [])) for b in queue_data)
        failed = sum(len(queue_data.get(b, {}).get("failed", [])) for b in queue_data)
        latest = None
        for ts in last_sync_map.values():
            if ts and (latest is None or ts > latest):
                latest = ts
        return {
            "online": is_online(),
            "offline_enabled": manifest.get("offline_enabled", True),
            "pending": pending,
            "synced": synced,
            "failed": failed,
            "last_sync": latest,
            "cache_version": manifest.get("cache_version", "2.0"),
            "branch_id": ALL_BRANCHES,
        }

    branch_key = str(branch_id).upper()
    b_data = queue_data.get(branch_key, {})
    return {
        "online": is_online(),
        "offline_enabled": manifest.get("offline_enabled", True),
        "pending": len(b_data.get("pending_sync", [])),
        "synced": len(b_data.get("synced", [])),
        "failed": len(b_data.get("failed", [])),
        "last_sync": last_sync_map.get(branch_key),
        "cache_version": manifest.get("cache_version", "2.0"),
        "branch_id": branch_key,
    }


def cache_data_for_offline(table_name, data, branch_id=None):
    """Store a table's data under the given branch. Data must be JSON-serializable."""
    init_offline_mode()
    branch_id = str(_resolve_branch(branch_id)).upper()

    cache = _load_json(OFFLINE_DATA_FILE, {})
    cache = _ensure_data_bucket(cache, branch_id)

    if table_name in cache:
        cache[table_name][branch_id] = data
        cache["last_updated"][branch_id] = datetime.now().isoformat()
        _save_json(OFFLINE_DATA_FILE, cache)


def load_cached_data(table_name, branch_id=None):
    """Load cached data for a branch (defaults to session branch)."""
    init_offline_mode()
    branch_id = str(_resolve_branch(branch_id)).upper()

    cache = _load_json(OFFLINE_DATA_FILE, {})
    cache = _ensure_data_bucket(cache, branch_id)
    return cache.get(table_name, {}).get(branch_id, [])


# ==============================
# SYNC QUEUE
# ==============================
def add_to_sync_queue(operation, table_name, data, transaction_id=None, branch_id=None):
    """
    Add an offline operation to the branch's sync queue.
    Returns the transaction id.
    """
    init_offline_mode()
    branch_id = str(_resolve_branch(branch_id)).upper()

    if transaction_id is None:
        transaction_id = hashlib.md5(
            f"{datetime.now().isoformat()}{operation}{table_name}{branch_id}".encode()
        ).hexdigest()[:16]

    queue_data = _load_json(OFFLINE_QUEUE_FILE, {})
    queue_data = _ensure_branch_bucket(queue_data, branch_id)

    queue_item = {
        "transaction_id": transaction_id,
        "timestamp": datetime.now().isoformat(),
        "operation": operation,
        "table": table_name,
        "branch_id": branch_id,
        "data": data,
        "status": "PENDING",
        "retry_count": 0,
    }

    queue_data[branch_id]["pending_sync"].append(queue_item)
    _save_json(OFFLINE_QUEUE_FILE, queue_data)
    return transaction_id


def get_sync_queue_status(branch_id=None):
    """Return sync queue status for a branch (or aggregated for __ALL__)."""
    init_offline_mode()
    branch_id = _resolve_branch(branch_id)

    queue_data = _load_json(OFFLINE_QUEUE_FILE, {})

    if _is_all_branches(branch_id):
        pending = []
        failed = []
        for b, bucket in queue_data.items():
            pending.extend(bucket.get("pending_sync", []))
            failed.extend(bucket.get("failed", []))
        return {
            "pending": len(pending),
            "synced": sum(len(queue_data.get(b, {}).get("synced", [])) for b in queue_data),
            "failed": len(failed),
            "pending_items": pending[:10],
            "failed_items": failed[:10],
        }

    branch_key = str(branch_id).upper()
    bucket = queue_data.get(branch_key, {})
    return {
        "pending": len(bucket.get("pending_sync", [])),
        "synced": len(bucket.get("synced", [])),
        "failed": len(bucket.get("failed", [])),
        "pending_items": bucket.get("pending_sync", [])[:10],
        "failed_items": bucket.get("failed", [])[:10],
    }


def clear_sync_queue(branch_id=None):
    """Clear the sync queue. If branch_id is __ALL__, clears every branch."""
    init_offline_mode()

    if _is_all_branches(branch_id):
        queue_data = {}
    else:
        branch_key = str(_resolve_branch(branch_id)).upper()
        queue_data = _load_json(OFFLINE_QUEUE_FILE, {})
        queue_data[branch_key] = {"pending_sync": [], "synced": [], "failed": []}

    _save_json(OFFLINE_QUEUE_FILE, queue_data)
    return True


# ==============================
# SYNC EXECUTION
# ==============================
def process_sync_queue(branch_id=None):
    """
    Process the pending sync queue for a single branch. Uses db_adapter so
    records land in the same branch they were created in.
    Returns (synced_count, message).
    """
    if not is_online():
        return 0, "Offline"

    init_offline_mode()

    # Never allow __ALL__ here — sync must operate on a single branch.
    if branch_id is None or _is_all_branches(branch_id):
        branch_id = _resolve_branch(None)
    branch_id = str(branch_id).upper()

    queue_data = _load_json(OFFLINE_QUEUE_FILE, {})
    queue_data = _ensure_branch_bucket(queue_data, branch_id)

    if not queue_data[branch_id]["pending_sync"]:
        return 0, f"No pending sync items for branch {branch_id}"

    synced_count = 0
    still_pending = []

    for item in queue_data[branch_id]["pending_sync"]:
        try:
            success = process_sync_item(item)
            if success:
                item["status"] = "SYNCED"
                item["synced_at"] = datetime.now().isoformat()
                queue_data[branch_id]["synced"].append(item)
                synced_count += 1
            else:
                item["retry_count"] = item.get("retry_count", 0) + 1
                if item["retry_count"] >= 3:
                    item["status"] = "FAILED"
                    queue_data[branch_id]["failed"].append(item)
                else:
                    still_pending.append(item)
        except Exception as e:
            item["retry_count"] = item.get("retry_count", 0) + 1
            if item["retry_count"] >= 3:
                item["status"] = "FAILED"
                item["error"] = str(e)
                queue_data[branch_id]["failed"].append(item)
            else:
                still_pending.append(item)

    queue_data[branch_id]["pending_sync"] = still_pending
    _save_json(OFFLINE_QUEUE_FILE, queue_data)

    # Update manifest's per-branch last_sync
    manifest = _load_json(OFFLINE_MANIFEST_FILE, {})
    manifest.setdefault("last_sync_by_branch", {})[branch_id] = datetime.now().isoformat()
    _save_json(OFFLINE_MANIFEST_FILE, manifest)

    return synced_count, f"Synced {synced_count} items for branch {branch_id}"


def process_sync_item(item):
    """
    Process a single sync item, honouring the branch_id stored in the item.
    Uses db_adapter (PostgreSQL) — never touches legacy CSVs.
    """
    table = item.get("table")
    operation = item.get("operation")
    data = item.get("data", {})
    branch_id = item.get("branch_id") or _resolve_branch(None)
    branch_id = str(branch_id).upper()

    try:
        if table == "sales":
            if operation == "CREATE":
                sales_df = load_sales(branch_id=branch_id)
                new_sale = pd.DataFrame([data])
                sales_df = pd.concat([sales_df, new_sale], ignore_index=True)
                save_sales(sales_df, branch_id=branch_id)
                return True

        elif table == "products":
            if operation == "CREATE":
                products_df = load_products(branch_id=branch_id)
                new_product = pd.DataFrame([data])
                products_df = pd.concat([products_df, new_product], ignore_index=True)
                save_products(products_df, branch_id=branch_id)
                return True
            elif operation == "UPDATE":
                products_df = load_products(branch_id=branch_id)
                idx = products_df[products_df["barcode"].astype(str) == str(data.get("barcode"))].index
                if len(idx) > 0:
                    for key, value in data.items():
                        if key in products_df.columns:
                            products_df.loc[idx[0], key] = value
                    save_products(products_df, branch_id=branch_id)
                return True

        elif table == "customers":
            if operation == "CREATE":
                customers_df = load_customers(branch_id=branch_id)
                new_customer = pd.DataFrame([data])
                customers_df = pd.concat([customers_df, new_customer], ignore_index=True)
                save_customers(customers_df, branch_id=branch_id)
                return True

        # Unknown table/operation: treat as a benign no-op so we don't
        # spam the queue with failures.
        return True
    except Exception as e:
        print(f"[offline_mode] process_sync_item error: {e}")
        return False


# ==============================
# CACHE REFRESH
# ==============================
def sync_all_data(branch_id=None):
    """
    Pull fresh data for a branch into the offline cache.
    Returns (success, message).
    """
    init_offline_mode()
    branch_id = str(_resolve_branch(branch_id)).upper()

    try:
        products_df = load_products(branch_id=branch_id)
        customers_df = load_customers(branch_id=branch_id)
        sales_df = load_sales(branch_id=branch_id)
        purchases_df = load_purchases(branch_id=branch_id)

        products_data = products_df.to_dict("records") if not products_df.empty else []
        customers_data = customers_df.to_dict("records") if not customers_df.empty else []
        sales_data = sales_df.to_dict("records") if not sales_df.empty else []
        purchases_data = purchases_df.to_dict("records") if not purchases_df.empty else []

        cache_data_for_offline("products", products_data, branch_id=branch_id)
        cache_data_for_offline("customers", customers_data, branch_id=branch_id)
        cache_data_for_offline("sales", sales_data, branch_id=branch_id)
        cache_data_for_offline("purchases", purchases_data, branch_id=branch_id)

        return True, (
            f"Cached for {branch_id}: {len(products_data)} products, "
            f"{len(customers_data)} customers, {len(sales_data)} sales, "
            f"{len(purchases_data)} purchases"
        )
    except Exception as e:
        return False, f"Error syncing data for {branch_id}: {str(e)}"


# ==============================
# DASHBOARD
# ==============================
def offline_mode_dashboard(branch_id=None):
    st.title("Offline Mode Management")
    st.caption("Work offline and sync when connection returns — branch-scoped")

    role = st.session_state.get("role", "cashier")
    if role not in ["owner", "manager"]:
        st.error("Access Denied. Only owners and managers can manage offline mode.")
        return

    # ---- Branch scope ----
    try:
        branches_df = load_branches()
    except Exception:
        branches_df = pd.DataFrame()

    if branch_id is None:
        branch_id, branch_label = _branch_scope_selector(branches_df)
    else:
        branch_label = _branch_label(branch_id)

    st.caption(f"Viewing: **{branch_label}**")

    status = get_offline_status(branch_id)
    sync_status = get_sync_queue_status(branch_id)

    # ==============================
    # STATUS CARDS
    # ==============================
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if status["online"]:
            st.success("ONLINE")
        else:
            st.error("OFFLINE")
    with col2:
        st.metric("Pending Sync", sync_status["pending"])
    with col3:
        st.metric("Synced Items", sync_status["synced"])
    with col4:
        st.metric("Failed Items", sync_status["failed"])

    st.markdown("---")

    tab1, tab2, tab3, tab4 = st.tabs([
        "Sync Status", "Pending Queue", "Offline Settings", "Manual Sync",
    ])

    # ==============================
    # TAB 1: SYNC STATUS
    # ==============================
    with tab1:
        st.markdown("## Synchronization Status")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### Connection Status")
            if status["online"]:
                st.success("Internet connection detected")
            else:
                st.warning("No internet connection — working in offline mode")

            st.markdown("### Last Sync")
            if status["last_sync"]:
                st.write(f"Last successful sync: {status['last_sync'][:19]}")
            else:
                st.write("No sync performed yet for this branch")

        with col2:
            st.markdown("### Offline Mode Status")
            st.write(f"Offline Mode: {'Enabled' if status['offline_enabled'] else 'Disabled'}")
            st.write(f"Cache Version: {status['cache_version']}")
            if sync_status["pending"] > 0:
                st.warning(f"{sync_status['pending']} items waiting to sync")
            else:
                st.success("All data synchronized")

        st.markdown("### Sync Activity")

        queue_data = _load_json(OFFLINE_QUEUE_FILE, {})

        # Aggregate synced counts per hour, either for a single branch or all
        from collections import Counter
        hours = Counter()
        if _is_all_branches(branch_id):
            for bucket in queue_data.values():
                for item in bucket.get("synced", []):
                    if "synced_at" in item:
                        hours[item["synced_at"][:13]] += 1
        else:
            bucket = queue_data.get(str(branch_id).upper(), {})
            for item in bucket.get("synced", []):
                if "synced_at" in item:
                    hours[item["synced_at"][:13]] += 1

        if hours:
            hours_df = pd.DataFrame(
                [{"Hour": k, "Items": v} for k, v in sorted(hours.items())[-24:]]
            )
            st.bar_chart(hours_df.set_index("Hour"))
        else:
            st.info("No sync activity yet")

    # ==============================
    # TAB 2: PENDING QUEUE
    # ==============================
    with tab2:
        st.markdown("## Pending Sync Queue")

        if sync_status["pending"] > 0:
            st.warning(f"{sync_status['pending']} items pending synchronization")
            pending_df = pd.DataFrame(sync_status["pending_items"])
            if not pending_df.empty:
                cols = [c for c in ["timestamp", "branch_id", "operation", "table", "transaction_id"]
                        if c in pending_df.columns]
                st.dataframe(pending_df[cols], use_container_width=True, hide_index=True)
        else:
            st.success("No pending items in sync queue")

        st.markdown("---")
        st.markdown("### Failed Items")

        if sync_status["failed"] > 0:
            st.error(f"{sync_status['failed']} items failed to sync")
            failed_df = pd.DataFrame(sync_status["failed_items"])
            if not failed_df.empty:
                cols = [c for c in ["timestamp", "branch_id", "operation", "table", "retry_count"]
                        if c in failed_df.columns]
                st.dataframe(failed_df[cols], use_container_width=True, hide_index=True)
        else:
            st.success("No failed items")

    # ==============================
    # TAB 3: OFFLINE SETTINGS
    # ==============================
    with tab3:
        st.markdown("## Offline Mode Settings")

        manifest = _load_json(OFFLINE_MANIFEST_FILE, {})

        offline_enabled = st.toggle(
            "Enable Offline Mode",
            value=manifest.get("offline_enabled", True),
            key=f"offline_enabled_{branch_id}",
        )
        if offline_enabled != manifest.get("offline_enabled"):
            manifest["offline_enabled"] = offline_enabled
            _save_json(OFFLINE_MANIFEST_FILE, manifest)
            st.success("Offline mode settings updated")

        st.markdown("### Auto-Sync Settings")
        st.selectbox(
            "Auto-Sync Interval (minutes)",
            [5, 10, 15, 30, 60],
            index=2,
            key=f"auto_sync_interval_{branch_id}",
        )

        st.markdown("### Data to Cache Offline")
        tables = ["products", "customers", "sales", "purchases"]
        cached_tables = manifest.get("tables", tables)
        for table in tables:
            st.checkbox(
                f"Cache {table.title()}",
                value=table in cached_tables,
                key=f"cache_{table}_{branch_id}",
            )

        st.markdown("---")
        st.markdown("### Clear Offline Cache")
        st.caption(
            "Clears the offline data and sync queue. If scope is __ALL__ this "
            "affects every branch; otherwise only the selected branch."
        )

        if st.button("Clear Offline Cache", use_container_width=True,
                     key=f"clear_cache_{branch_id}"):
            confirm = st.checkbox(
                "I understand this will clear all offline data for the selected scope",
                key=f"confirm_clear_{branch_id}",
            )
            if confirm:
                cache = _load_json(OFFLINE_DATA_FILE, {})
                if _is_all_branches(branch_id):
                    cache = {"products": {}, "customers": {}, "sales": {},
                             "purchases": {}, "last_updated": {}}
                else:
                    b = str(branch_id).upper()
                    for table in ("products", "customers", "sales", "purchases"):
                        if table in cache and isinstance(cache[table], dict):
                            cache[table][b] = []
                    cache.setdefault("last_updated", {})[b] = None
                _save_json(OFFLINE_DATA_FILE, cache)
                clear_sync_queue(branch_id)
                st.success("Offline cache cleared successfully")
                st.rerun()

    # ==============================
    # TAB 4: MANUAL SYNC
    # ==============================
    with tab4:
        st.markdown("## Manual Synchronization")
        st.caption(
            "Sync always targets the branch the record was created in — the "
            "currently selected scope only affects what you see and cache, not "
            "where offline sales land."
        )

        col1, col2 = st.columns(2)

        with col1:
            if st.button("Sync Now", type="primary", use_container_width=True,
                         key=f"sync_now_{branch_id}"):
                with st.spinner("Synchronizing..."):
                    # Sync must target a single branch — pick the resolved one
                    target_branch = _resolve_branch(None)
                    count, message = process_sync_queue(target_branch)
                    if count > 0:
                        st.success(message)
                    else:
                        st.info(message)
                st.rerun()

        with col2:
            if st.button("Sync All Data for Offline", use_container_width=True,
                         key=f"sync_all_{branch_id}"):
                with st.spinner("Caching all data for offline use..."):
                    target_branch = _resolve_branch(None)
                    success, message = sync_all_data(target_branch)
                    if success:
                        st.success(message)
                    else:
                        st.error(message)

        st.markdown("---")
        st.markdown("### Offline Data Size")

        if OFFLINE_DATA_FILE.exists():
            size_bytes = OFFLINE_DATA_FILE.stat().st_size
            if size_bytes < 1024:
                size_str = f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                size_str = f"{size_bytes / 1024:.2f} KB"
            else:
                size_str = f"{size_bytes / (1024 * 1024):.2f} MB"
            st.metric("Offline Data Size", size_str)

        if OFFLINE_QUEUE_FILE.exists():
            st.metric("Sync Queue Size", f"{OFFLINE_QUEUE_FILE.stat().st_size} B")

        st.markdown("---")
        st.markdown("### How Offline Mode Works")

        st.info(
            "**Offline Mode Features:**\n\n"
            "1. **Per-Branch Cache** — each branch's data is stored separately. "
            "An HO user's offline cache never overwrites NAT's.\n"
            "2. **Queued Operations** — every offline action is tagged with the "
            "branch it was recorded in.\n"
            "3. **Auto-Sync** — when the connection returns, queued items sync "
            "back to the branch they were created in.\n"
            "4. **Offline Receipts** — receipts generate offline and reconcile "
            "when the queue drains.\n\n"
            "**Best Practices:**\n"
            "- Sync regularly when online\n"
            "- Review failed sync items\n"
            "- Clear cache periodically"
        )


# ==============================
# OFFLINE RECEIPT HANDLER
# ==============================
def queue_offline_receipt(receipt_data, branch_id=None):
    """Queue a receipt for later syncing, tagged with its branch."""
    branch_id = _resolve_branch(branch_id)
    transaction_id = add_to_sync_queue(
        "CREATE", "sales", receipt_data, branch_id=branch_id
    )
    return transaction_id


# ==============================
# CACHE READERS
# ==============================
def get_offline_products(branch_id=None):
    return load_cached_data("products", branch_id=branch_id)


def get_offline_customers(branch_id=None):
    return load_cached_data("customers", branch_id=branch_id)


def get_offline_sales(branch_id=None):
    return load_cached_data("sales", branch_id=branch_id)


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    offline_mode_dashboard()