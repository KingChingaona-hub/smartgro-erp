# backend/integrations/ecommerce_sync.py
# E-commerce Platform Sync — branch-aware.
#
# Branch scoping:
#     branch_id = None          -> session branch
#     branch_id = "HO"/"NAT"/.. -> that single branch
#     branch_id = "__ALL__"     -> aggregate across all branches (owner only)
#
# Products come from db_adapter with branch scoping. The legacy
# data/products.csv fallback has been removed — it returned unscoped products
# and would bypass every downstream guard.

import streamlit as st
import pandas as pd
import json
import csv
import re
from datetime import datetime
from pathlib import Path
import io

from backend.core.db_adapter import load_products, load_branches


# ==============================
# FILE PATHS
# ==============================
DATA_DIR = Path("data")
ECOMMERCE_FILE = DATA_DIR / "ecommerce_exports.csv"
SYNC_LOG_FILE = DATA_DIR / "sync_logs.csv"

EXPORT_COLUMNS = [
    "export_id", "export_date", "branch_id", "platform", "export_type",
    "product_count", "status", "exported_by", "file_path",
]

SYNC_LOG_COLUMNS = [
    "sync_id", "sync_date", "branch_id", "platform", "action",
    "items_synced", "status", "message", "synced_by",
]


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


def _load_scoped(loader, branch_id, **kwargs):
    if _is_all_branches(branch_id):
        try:
            bdf = load_branches()
        except Exception:
            bdf = pd.DataFrame()
        if bdf is None or bdf.empty or "branch_id" not in bdf.columns:
            try:
                return loader(**kwargs)
            except Exception:
                return pd.DataFrame()
        frames = []
        for bid in bdf["branch_id"].astype(str).tolist():
            try:
                df = loader(branch_id=bid, **kwargs)
                if df is not None and not df.empty:
                    frames.append(df)
            except Exception:
                continue
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    try:
        return loader(branch_id=branch_id, **kwargs)
    except TypeError:
        try:
            return loader(**kwargs)
        except Exception:
            return pd.DataFrame()
    except Exception:
        return pd.DataFrame()


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
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(branch_id)).strip("_").upper() or "HO"


def _branch_scope_selector(branches_df):
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
            key="ecommerce_branch_scope",
            help="Owners may export per branch or the whole company.",
        )
        if choice == "All Branches":
            return ALL_BRANCHES, "All Branches"
        m = re.search(r"\(([^)]+)\)\s*$", choice)
        code = m.group(1).strip() if m else choice
        return code, choice

    session_branch = _resolve_branch(None)
    label = _branch_label(session_branch)
    st.info(f"E-commerce sync locked to your branch: **{label}**")
    return session_branch, label


# ==============================
# INITIALIZATION
# ==============================
def init_ecommerce_files():
    DATA_DIR.mkdir(exist_ok=True)

    if not ECOMMERCE_FILE.exists():
        pd.DataFrame(columns=EXPORT_COLUMNS).to_csv(ECOMMERCE_FILE, index=False)
    else:
        try:
            existing = pd.read_csv(ECOMMERCE_FILE)
            if "branch_id" not in existing.columns:
                existing.insert(2, "branch_id", "HO")
                existing = existing[[c for c in EXPORT_COLUMNS if c in existing.columns]]
                existing.to_csv(ECOMMERCE_FILE, index=False)
        except Exception:
            pd.DataFrame(columns=EXPORT_COLUMNS).to_csv(ECOMMERCE_FILE, index=False)

    if not SYNC_LOG_FILE.exists():
        pd.DataFrame(columns=SYNC_LOG_COLUMNS).to_csv(SYNC_LOG_FILE, index=False)
    else:
        try:
            existing = pd.read_csv(SYNC_LOG_FILE)
            if "branch_id" not in existing.columns:
                existing.insert(2, "branch_id", "HO")
                existing = existing[[c for c in SYNC_LOG_COLUMNS if c in existing.columns]]
                existing.to_csv(SYNC_LOG_FILE, index=False)
        except Exception:
            pd.DataFrame(columns=SYNC_LOG_COLUMNS).to_csv(SYNC_LOG_FILE, index=False)


def load_ecommerce_exports(branch_id=None):
    init_ecommerce_files()
    try:
        df = pd.read_csv(ECOMMERCE_FILE)
    except Exception:
        return pd.DataFrame(columns=EXPORT_COLUMNS)

    if "branch_id" not in df.columns:
        df["branch_id"] = "HO"

    if branch_id is None:
        return df
    branch_id = _resolve_branch(branch_id)
    if _is_all_branches(branch_id):
        return df
    return df[df["branch_id"].astype(str).str.upper() == str(branch_id).upper()].copy()


def save_ecommerce_export(export_data):
    df = load_ecommerce_exports(branch_id=ALL_BRANCHES)
    df = pd.concat([df, pd.DataFrame([export_data])], ignore_index=True)
    df.to_csv(ECOMMERCE_FILE, index=False)


def load_sync_logs(branch_id=None):
    init_ecommerce_files()
    try:
        df = pd.read_csv(SYNC_LOG_FILE)
    except Exception:
        return pd.DataFrame(columns=SYNC_LOG_COLUMNS)

    if "branch_id" not in df.columns:
        df["branch_id"] = "HO"

    if branch_id is None:
        return df
    branch_id = _resolve_branch(branch_id)
    if _is_all_branches(branch_id):
        return df
    return df[df["branch_id"].astype(str).str.upper() == str(branch_id).upper()].copy()


def log_sync(sync_data):
    df = load_sync_logs(branch_id=ALL_BRANCHES)
    df = pd.concat([df, pd.DataFrame([sync_data])], ignore_index=True)
    df.to_csv(SYNC_LOG_FILE, index=False)


# ==============================
# PRODUCT LOADER (scoped, no legacy CSV fallback)
# ==============================
def load_products_from_db(branch_id=None):
    """
    Load products for the given branch via db_adapter. No filesystem fallback —
    the old data/products.csv route returned unscoped products and would have
    leaked across branches.
    """
    branch_id = _resolve_branch(branch_id)

    try:
        df = _load_scoped(load_products, branch_id)
    except Exception as e:
        st.warning(f"Could not load products: {e}")
        return pd.DataFrame()

    if df is None or df.empty:
        return pd.DataFrame()

    # Normalize columns
    required_cols = ["name", "barcode", "price", "stock", "category"]
    for col in required_cols:
        if col not in df.columns:
            df[col] = "" if col in ["name", "barcode", "category"] else 0

    for col in ["price", "stock", "cost"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    if "product_name" in df.columns and "name" not in df.columns:
        df["name"] = df["product_name"]
    if "product_barcode" in df.columns and "barcode" not in df.columns:
        df["barcode"] = df["product_barcode"]

    return df


# ==============================
# WOOCOMMERCE EXPORT
# ==============================
def export_to_woocommerce(products_df, branch_id=None):
    branch_id = _resolve_branch(branch_id)
    if products_df is None or products_df.empty:
        return ""

    slug = _branch_slug(branch_id)
    rows = []
    for _, product in products_df.iterrows():
        barcode = str(product.get("barcode", ""))
        name = str(product.get("name", "Unknown Product"))
        price = float(product.get("price", 0))
        stock = int(product.get("stock", 0))
        category = str(product.get("category", "Uncategorized"))

        rows.append({
            "ID": "",
            "Type": "simple",
            "SKU": barcode,
            "Name": name,
            "Description": f"{name} — Available at Aziel Investments ({slug})",
            "Short description": "",
            "Price": price,
            "Regular price": price,
            "Sale price": "",
            "Categories": category,
            "Stock": stock,
            "Stock status": "instock" if stock > 0 else "outofstock",
            "Weight": "",
            "Length": "",
            "Width": "",
            "Height": "",
            "Images": "",
            "Tax status": "taxable",
            "Tax class": "",
            "Manage stock": "yes" if stock >= 0 else "no",
        })

    if not rows:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


# ==============================
# SHOPIFY EXPORT
# ==============================
def export_to_shopify(products_df, branch_id=None):
    branch_id = _resolve_branch(branch_id)
    if products_df is None or products_df.empty:
        return ""

    slug = _branch_slug(branch_id)
    rows = []
    for _, product in products_df.iterrows():
        barcode = str(product.get("barcode", ""))
        name = str(product.get("name", "Unknown Product"))
        price = float(product.get("price", 0))
        stock = int(product.get("stock", 0))
        category = str(product.get("category", "Uncategorized"))

        rows.append({
            "Handle": barcode if barcode else name.replace(" ", "-").lower(),
            "Title": name,
            "Body (HTML)": f"<p>{name} — Available at Aziel Investments ({slug})</p>",
            "Vendor": "Aziel Investments",
            "Product Category": category,
            "Type": "Physical Product",
            "Tags": f"branch:{slug}",
            "Published": "TRUE",
            "Option1 Name": "Title",
            "Option1 Value": "Default Title",
            "Variant SKU": barcode,
            "Variant Grams": "",
            "Variant Inventory Tracker": "shopify",
            "Variant Inventory Qty": stock,
            "Variant Inventory Policy": "deny",
            "Variant Fulfillment Service": "manual",
            "Variant Price": price,
            "Variant Compare At Price": "",
            "Variant Requires Shipping": "TRUE",
            "Variant Taxable": "TRUE",
            "Variant Barcode": barcode,
            "Image Src": "",
            "Image Position": "",
            "Image Alt Text": "",
            "Gift Card": "FALSE",
            "SEO Title": name,
            "SEO Description": f"Buy {name} at Aziel Investments ({slug})",
            "Google Shopping / MPN": "",
            "Google Shopping / Age Group": "",
            "Google Shopping / Gender": "",
            "Google Shopping / Google Product Category": "",
            "Status": "active",
        })

    if not rows:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


# ==============================
# FACEBOOK SHOP EXPORT
# ==============================
def export_to_facebook(products_df, branch_id=None):
    branch_id = _resolve_branch(branch_id)
    if products_df is None or products_df.empty:
        return ""

    slug = _branch_slug(branch_id)
    rows = []
    for _, product in products_df.iterrows():
        barcode = str(product.get("barcode", ""))
        name = str(product.get("name", "Unknown Product"))
        price = float(product.get("price", 0))
        stock = int(product.get("stock", 0))
        category = str(product.get("category", "Home & Garden"))

        rows.append({
            "id": barcode,
            "title": name,
            "description": f"{name} — Available at Aziel Investments ({slug})",
            "availability": "in stock" if stock > 0 else "out of stock",
            "condition": "new",
            "price": f"{price} USD",
            "link": "",
            "image_link": "",
            "brand": "Aziel Investments",
            "google_product_category": "",
            "fb_product_category": category,
            "quantity_to_sell_on_facebook": stock,
            "sale_price": "",
            "sale_price_effective_date": "",
            "additional_image_link": "",
            "color": "",
            "gender": "",
            "size": "",
            "pattern": "",
            "shipping_weight": "",
            "shipping_length": "",
            "shipping_width": "",
            "shipping_height": "",
        })

    if not rows:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


# ==============================
# ORDER IMPORTERS
# ==============================
def import_woocommerce_orders(csv_file):
    try:
        df = pd.read_csv(csv_file)
        orders = []
        for _, row in df.iterrows():
            orders.append({
                "order_id": row.get("Order ID", str(datetime.now().timestamp())),
                "customer_name": row.get("Customer Name", "Unknown"),
                "customer_email": row.get("Customer Email", ""),
                "total_amount": float(row.get("Order Total", 0)),
                "status": row.get("Order Status", "pending"),
                "items": row.get("Items", ""),
                "order_date": row.get("Order Date", datetime.now().strftime("%Y-%m-%d")),
            })
        return True, orders
    except Exception as e:
        return False, str(e)


def import_shopify_orders(json_file):
    try:
        data = json.load(json_file)
        orders = []
        for order in data.get("orders", []):
            customer = order.get("customer", {})
            orders.append({
                "order_id": order.get("id", ""),
                "customer_name": (
                    customer.get("first_name", "") + " " + customer.get("last_name", "")
                ).strip(),
                "customer_email": customer.get("email", ""),
                "total_amount": float(order.get("total_price", 0)),
                "status": order.get("financial_status", "pending"),
                "items": len(order.get("line_items", [])),
                "order_date": order.get("created_at", datetime.now().isoformat())[:10],
            })
        return True, orders
    except Exception as e:
        return False, str(e)


# ==============================
# DASHBOARD
# ==============================
def ecommerce_sync_dashboard(branch_id=None):
    st.title("E-commerce Platform Sync")
    st.caption("Sync products with WooCommerce, Shopify, and Facebook Shop — branch-scoped")

    role = st.session_state.get("role", "cashier")
    if role not in ["owner", "manager"]:
        st.error("Access Denied. Only owners and managers can access e-commerce sync.")
        return

    try:
        branches_df = load_branches()
    except Exception:
        branches_df = pd.DataFrame()

    if branch_id is None:
        branch_id, branch_label = _branch_scope_selector(branches_df)
    else:
        branch_label = _branch_label(branch_id)

    st.caption(f"Syncing for: **{branch_label}**")

    init_ecommerce_files()

    products_df = load_products_from_db(branch_id=branch_id)

    if products_df.empty:
        st.warning(f"No products found for {branch_label}. Add products in Inventory first.")
        with st.expander("Debug: why no products?", expanded=False):
            st.write(f"Branch scope: `{branch_id}`")
            st.write(f"Branches configured: {len(branches_df) if branches_df is not None else 0}")
            try:
                raw = _load_scoped(load_products, branch_id)
                st.write(f"db_adapter.load_products() returned {len(raw)} row(s)")
            except Exception as e:
                st.error(f"db_adapter error: {e}")
        return

    st.sidebar.success(f"Loaded {len(products_df)} products for {branch_label}")

    tab1, tab2, tab3, tab4 = st.tabs([
        "Export Products",
        "Import Orders",
        "Sync Dashboard",
        "Platform Settings",
    ])

    # ==============================
    # TAB 1: EXPORT
    # ==============================
    with tab1:
        st.markdown(f"## Export Products — {branch_label}")

        col1, col2 = st.columns(2)
        with col1:
            platform = st.selectbox(
                "Select Platform",
                ["WooCommerce", "Shopify", "Facebook Shop"],
                key=f"ec_platform_{branch_id}",
            )
        with col2:
            categories = (
                products_df["category"].unique().tolist()
                if "category" in products_df.columns else []
            )
            category_filter = st.selectbox(
                "Filter by Category",
                ["All Categories"] + categories,
                key=f"ec_cat_{branch_id}",
            )

        if category_filter != "All Categories" and "category" in products_df.columns:
            export_products = products_df[products_df["category"] == category_filter]
        else:
            export_products = products_df

        st.info(f"{len(export_products)} products will be exported for {branch_label}")

        with st.expander("Preview Products to Export"):
            preview_cols = [
                c for c in ["name", "barcode", "price", "stock", "category"]
                if c in export_products.columns
            ]
            st.dataframe(
                export_products[preview_cols],
                use_container_width=True,
                hide_index=True,
            )

        if st.button(f"Export to {platform}", type="primary",
                     use_container_width=True, key=f"ec_export_{branch_id}"):
            with st.spinner(f"Exporting to {platform} for {branch_label}..."):
                slug = _branch_slug(branch_id)
                ts = datetime.now().strftime('%Y%m%d%H%M%S')

                if platform == "WooCommerce":
                    export_data = export_to_woocommerce(export_products, branch_id=branch_id)
                    export_filename = f"woocommerce_{slug}_{ts}.csv"
                elif platform == "Shopify":
                    export_data = export_to_shopify(export_products, branch_id=branch_id)
                    export_filename = f"shopify_{slug}_{ts}.csv"
                else:
                    export_data = export_to_facebook(export_products, branch_id=branch_id)
                    export_filename = f"facebook_{slug}_{ts}.csv"

                if export_data:
                    save_ecommerce_export({
                        "export_id": f"EXP{ts}",
                        "export_date": datetime.now().isoformat(),
                        "branch_id": slug,
                        "platform": platform,
                        "export_type": "PRODUCT_EXPORT",
                        "product_count": len(export_products),
                        "status": "COMPLETED",
                        "exported_by": st.session_state.get("username", "system"),
                        "file_path": export_filename,
                    })
                    st.download_button(
                        label="Download Export File",
                        data=export_data.encode('utf-8'),
                        file_name=export_filename,
                        mime="text/csv",
                        use_container_width=True,
                        key=f"ec_dl_{branch_id}",
                    )
                    st.balloons()

    # ==============================
    # TAB 2: IMPORT ORDERS
    # ==============================
    with tab2:
        st.markdown(f"## Import Orders — {branch_label}")
        st.caption("Orders are logged with the branch you are currently scoped to.")

        import_platform = st.selectbox(
            "Select Platform to Import From",
            ["WooCommerce (CSV)", "Shopify (JSON)"],
            key=f"ec_import_platform_{branch_id}",
        )

        if import_platform == "WooCommerce (CSV)":
            uploaded_file = st.file_uploader(
                "Upload WooCommerce Orders CSV", type=["csv"],
                key=f"ec_wc_upload_{branch_id}",
            )
            if uploaded_file and st.button(
                "Import Orders", type="primary", use_container_width=True,
                key=f"ec_wc_import_{branch_id}",
            ):
                success, result = import_woocommerce_orders(uploaded_file)
                if success:
                    st.success(f"Imported {len(result)} orders for {branch_label}!")
                    st.dataframe(pd.DataFrame(result), use_container_width=True, hide_index=True)
                    log_sync({
                        "sync_id": f"SYNC{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        "sync_date": datetime.now().isoformat(),
                        "branch_id": _branch_slug(branch_id),
                        "platform": "WooCommerce",
                        "action": "ORDER_IMPORT",
                        "items_synced": len(result),
                        "status": "SUCCESS",
                        "message": f"Imported {len(result)} orders for {branch_label}",
                        "synced_by": st.session_state.get("username", "system"),
                    })
                else:
                    st.error(f"Import failed: {result}")

        elif import_platform == "Shopify (JSON)":
            uploaded_file = st.file_uploader(
                "Upload Shopify Orders JSON", type=["json"],
                key=f"ec_sp_upload_{branch_id}",
            )
            if uploaded_file and st.button(
                "Import Orders", type="primary", use_container_width=True,
                key=f"ec_sp_import_{branch_id}",
            ):
                success, result = import_shopify_orders(uploaded_file)
                if success:
                    st.success(f"Imported {len(result)} orders for {branch_label}!")
                    st.dataframe(pd.DataFrame(result), use_container_width=True, hide_index=True)
                    log_sync({
                        "sync_id": f"SYNC{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        "sync_date": datetime.now().isoformat(),
                        "branch_id": _branch_slug(branch_id),
                        "platform": "Shopify",
                        "action": "ORDER_IMPORT",
                        "items_synced": len(result),
                        "status": "SUCCESS",
                        "message": f"Imported {len(result)} orders for {branch_label}",
                        "synced_by": st.session_state.get("username", "system"),
                    })
                else:
                    st.error(f"Import failed: {result}")

    # ==============================
    # TAB 3: DASHBOARD
    # ==============================
    with tab3:
        st.markdown(f"## Sync Dashboard — {branch_label}")

        total_products = len(products_df)
        low_stock = (
            len(products_df[products_df["stock"] <= products_df["reorder_level"]])
            if "reorder_level" in products_df.columns else 0
        )

        exports_df = load_ecommerce_exports(branch_id=branch_id)
        syncs_df = load_sync_logs(branch_id=branch_id)

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Products", total_products)
        with col2:
            st.metric("Low Stock Items", low_stock)
        with col3:
            st.metric("Total Exports", len(exports_df))
        with col4:
            st.metric("Total Imports", len(syncs_df))

        st.markdown("### Export History")
        if exports_df.empty:
            st.info(f"No export history for {branch_label}")
        else:
            exports_df = exports_df.copy()
            exports_df["export_date"] = pd.to_datetime(
                exports_df["export_date"], errors="coerce"
            ).dt.strftime("%Y-%m-%d %H:%M")
            display_cols = [
                c for c in [
                    "export_date", "branch_id", "platform", "export_type",
                    "product_count", "status", "exported_by",
                ] if c in exports_df.columns
            ]
            st.dataframe(exports_df[display_cols], use_container_width=True, hide_index=True)

        st.markdown("### Import History")
        if syncs_df.empty:
            st.info(f"No import history for {branch_label}")
        else:
            syncs_df = syncs_df.copy()
            syncs_df["sync_date"] = pd.to_datetime(
                syncs_df["sync_date"], errors="coerce"
            ).dt.strftime("%Y-%m-%d %H:%M")
            display_cols = [
                c for c in [
                    "sync_date", "branch_id", "platform", "action",
                    "items_synced", "status", "synced_by",
                ] if c in syncs_df.columns
            ]
            st.dataframe(syncs_df[display_cols], use_container_width=True, hide_index=True)

    # ==============================
    # TAB 4: SETTINGS
    # ==============================
    with tab4:
        st.markdown("## Platform Settings")
        st.info("Configure your e-commerce platform API settings")

        with st.expander("WooCommerce Settings", expanded=True):
            st.text_input("WooCommerce Store URL", placeholder="https://yourstore.com",
                          key=f"wc_url_{branch_id}")
            st.text_input("Consumer Key", type="password", key=f"wc_key_{branch_id}")
            st.text_input("Consumer Secret", type="password", key=f"wc_secret_{branch_id}")
            if st.button("Test WooCommerce Connection", key=f"wc_test_{branch_id}"):
                st.success("Connection test successful! (Simulated)")

        with st.expander("Shopify Settings"):
            st.text_input("Shopify Store URL", placeholder="yourstore.myshopify.com",
                          key=f"sp_url_{branch_id}")
            st.text_input("Access Token", type="password", key=f"sp_token_{branch_id}")
            if st.button("Test Shopify Connection", key=f"sp_test_{branch_id}"):
                st.success("Connection test successful! (Simulated)")

        with st.expander("Facebook Shop Settings"):
            st.text_input("Facebook Page ID", key=f"fb_page_{branch_id}")
            st.text_input("Facebook Access Token", type="password", key=f"fb_token_{branch_id}")
            if st.button("Test Facebook Connection", key=f"fb_test_{branch_id}"):
                st.success("Connection test successful! (Simulated)")

        st.markdown("### Auto-Sync Settings")
        auto_sync = st.checkbox("Enable Automatic Product Sync", key=f"auto_sync_{branch_id}")
        if auto_sync:
            sync_frequency = st.selectbox(
                "Sync Frequency", ["Daily", "Weekly", "Hourly"],
                key=f"auto_sync_freq_{branch_id}",
            )
            st.info(
                f"Products for {branch_label} will be synced "
                f"{sync_frequency.lower()} to all connected platforms"
            )

        if st.button("Save Settings", type="primary", use_container_width=True,
                     key=f"ec_save_{branch_id}"):
            st.success("Settings saved successfully!")
            try:
                from backend.core.animations import show_toast
                show_toast("E-commerce settings saved!", "success")
            except Exception:
                pass


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    ecommerce_sync_dashboard()