# backend/features/barcode_scanner.py
# Barcode Scanner — branch-aware.
#
# Branch scoping:
#     branch_id = None          -> session branch
#     branch_id = "HO"/"NAT"/.. -> that single branch
#     branch_id = "__ALL__"     -> aggregate across all branches (owner only)
#
# The scan_history.csv gains a branch_id column; existing files auto-migrate.

import streamlit as st
import pandas as pd
import json
import re
from pathlib import Path
from datetime import datetime
from PIL import Image
import io
import base64

from backend.core.db_adapter import load_products, load_branches


# ==============================
# FILE PATHS
# ==============================
DATA_DIR = Path("data")
SCANNER_SETTINGS_FILE = DATA_DIR / "scanner_settings.json"
SCAN_HISTORY_FILE = DATA_DIR / "scan_history.csv"

SCAN_HISTORY_COLUMNS = [
    "scan_id", "timestamp", "branch_id", "barcode", "product_name",
    "scan_type", "quantity", "source", "status",
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
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(branch_id)).strip("_") or "branch"


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
            key="barcode_scanner_branch_scope",
            help="Owners may scan against any branch or view company-wide scan history.",
        )
        if choice == "All Branches":
            return ALL_BRANCHES, "All Branches"
        m = re.search(r"\(([^)]+)\)\s*$", choice)
        code = m.group(1).strip() if m else choice
        return code, choice

    session_branch = _resolve_branch(None)
    label = _branch_label(session_branch)
    st.info(f"Barcode scanner locked to your branch: **{label}**")
    return session_branch, label


# ==============================
# INITIALIZATION
# ==============================
def init_scanner_files():
    """Initialize scanner-related files. Auto-migrates scan_history to include branch_id."""
    DATA_DIR.mkdir(exist_ok=True)

    if not SCANNER_SETTINGS_FILE.exists():
        settings = {
            "enable_camera": True,
            "scan_mode": "manual",
            "scan_timeout": 5,
            "sound_enabled": True,
            "vibration_enabled": True,
            "bulk_mode": False,
            "scan_quality": "high",
            "auto_add_to_cart": False,
            "auto_add_to_inventory": False,
        }
        with open(SCANNER_SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=2)

    # Scan history — migrate if missing branch_id
    if not SCAN_HISTORY_FILE.exists():
        df = pd.DataFrame(columns=SCAN_HISTORY_COLUMNS)
        df.to_csv(SCAN_HISTORY_FILE, index=False)
    else:
        try:
            existing = pd.read_csv(SCAN_HISTORY_FILE)
            if "branch_id" not in existing.columns:
                existing.insert(2, "branch_id", "HO")
                existing.to_csv(SCAN_HISTORY_FILE, index=False)
        except Exception:
            df = pd.DataFrame(columns=SCAN_HISTORY_COLUMNS)
            df.to_csv(SCAN_HISTORY_FILE, index=False)


def load_scanner_settings():
    init_scanner_files()
    with open(SCANNER_SETTINGS_FILE, "r") as f:
        return json.load(f)


def save_scanner_settings(settings):
    with open(SCANNER_SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)


# ==============================
# LOGGING
# ==============================
def log_scan(barcode, product_name, scan_type, quantity, source, status, branch_id=None):
    """Log a scan, tagged with its branch. Auto-migrates old files."""
    init_scanner_files()
    branch_id = _resolve_branch(branch_id)

    try:
        df = pd.read_csv(SCAN_HISTORY_FILE)
        if "branch_id" not in df.columns:
            df.insert(2, "branch_id", "HO")
    except Exception:
        df = pd.DataFrame(columns=SCAN_HISTORY_COLUMNS)

    new_scan = pd.DataFrame([{
        "scan_id": f"SC{len(df)+1:08d}",
        "timestamp": datetime.now().isoformat(),
        "branch_id": branch_id,
        "barcode": barcode,
        "product_name": product_name,
        "scan_type": scan_type,
        "quantity": quantity,
        "source": source,
        "status": status,
    }])

    df = pd.concat([df, new_scan], ignore_index=True)
    df.to_csv(SCAN_HISTORY_FILE, index=False)


# ==============================
# BARCODE / QR RENDERERS
# ==============================
def generate_barcode_html(barcode, product_name="", branch_label=""):
    header = f'<div style="font-size: 12px; color: #666; margin-bottom: 8px;">{branch_label}</div>' if branch_label else ""
    html = f"""
    <div style="background: white; padding: 20px; border: 1px solid #ddd; border-radius: 8px; text-align: center;">
        {header}
        <div style="font-family: 'Courier New', monospace; font-size: 48px; letter-spacing: 2px; margin: 10px 0;">
            {'█' * len(str(barcode))}
        </div>
        <div style="font-size: 24px; font-weight: bold; margin: 10px 0;">
            {barcode}
        </div>
        <div style="font-size: 16px; color: #666;">
            {product_name}
        </div>
    </div>
    """
    return html


def generate_qr_code_html(data):
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={data}"
    html = f"""
    <div style="background: white; padding: 20px; border: 1px solid #ddd; border-radius: 8px; text-align: center;">
        <img src="{qr_url}" alt="QR Code" style="max-width: 100%;">
        <div style="margin-top: 10px; font-size: 12px; color: #999;">
            Scan to view product info
        </div>
    </div>
    """
    return html


# ==============================
# DASHBOARD
# ==============================
def barcode_scanner_dashboard(branch_id=None):
    st.title("Barcode Scanner")
    st.caption("Scan barcodes with your camera, scan QR codes, and manage inventory — branch-scoped")

    role = st.session_state.get("role", "cashier")
    if role not in ["owner", "manager", "cashier"]:
        st.error("Access Denied. Only staff can access barcode scanner.")
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

    st.caption(f"Scanning against: **{branch_label}**")

    init_scanner_files()
    settings = load_scanner_settings()

    # Scoped product load
    products_df = _load_scoped(load_products, branch_id)

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Scanner", "Scan History", "Bulk Scanner", "Product Lookup", "Settings",
    ])

    # ==============================
    # TAB 1: SCANNER
    # ==============================
    with tab1:
        st.markdown("## Barcode Scanner")

        st.markdown("### Upload Barcode Image")
        st.caption("Take a photo or upload an image of the barcode")

        uploaded_file = st.file_uploader(
            "Upload barcode image",
            type=["png", "jpg", "jpeg", "gif", "bmp"],
            key=f"barcode_image_{branch_id}",
        )

        if uploaded_file:
            image = Image.open(uploaded_file)
            st.image(image, caption="Uploaded Image", width=300)

            st.markdown("### Enter the barcode from the image")
            manual_barcode = st.text_input(
                "Barcode Number",
                placeholder="e.g., 6001 or 1234567890",
                key=f"barcode_from_image_{branch_id}",
            )

            if manual_barcode and st.button("Lookup Barcode", type="primary",
                                            use_container_width=True,
                                            key=f"lookup_img_{branch_id}"):
                if products_df.empty:
                    st.error(f"No products loaded for {branch_label}.")
                else:
                    product = products_df[products_df["barcode"].astype(str) == manual_barcode]
                    if not product.empty:
                        product = product.iloc[0]
                        st.success(f"Product found: {product['name']}")

                        col1, col2 = st.columns(2)
                        with col1:
                            st.info(f"**Product:** {product['name']}")
                            st.info(f"**Price:** ${product['price']:.2f}")
                        with col2:
                            st.info(f"**Stock:** {product['stock']}")
                            st.info(f"**Category:** {product.get('category', 'N/A')}")

                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("Add to Cart", key=f"scan_add_cart_{branch_id}",
                                         use_container_width=True):
                                st.success(f"Added {product['name']} to cart!")
                                try:
                                    from backend.core.animations import show_toast
                                    show_toast(f"{product['name']} added to cart!", "success")
                                except Exception:
                                    pass
                        with col2:
                            if st.button("View Product", key=f"scan_view_product_{branch_id}",
                                         use_container_width=True):
                                st.info(f"Viewing {product['name']} in inventory")

                        st.markdown(
                            generate_barcode_html(manual_barcode, product["name"], branch_label),
                            unsafe_allow_html=True,
                        )

                        log_scan(manual_barcode, product["name"], "SCAN", 1,
                                 "IMAGE", "SUCCESS", branch_id=branch_id)
                    else:
                        st.error(f"Product with barcode '{manual_barcode}' not found in {branch_label}")

        st.markdown("---")
        st.markdown("### Or Enter Barcode Manually")

        manual_barcode2 = st.text_input(
            "Enter Barcode Number",
            placeholder="e.g., 6001 or 1234567890",
            key=f"manual_barcode_main_{branch_id}",
        )

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Lookup", use_container_width=True, key=f"lookup_manual_{branch_id}"):
                if manual_barcode2:
                    if products_df.empty:
                        st.error(f"No products loaded for {branch_label}.")
                    else:
                        product = products_df[products_df["barcode"].astype(str) == manual_barcode2]
                        if not product.empty:
                            product = product.iloc[0]
                            st.success(f"Product found: {product['name']}")

                            col1, col2 = st.columns(2)
                            with col1:
                                st.info(f"**Product:** {product['name']}")
                                st.info(f"**Price:** ${product['price']:.2f}")
                            with col2:
                                st.info(f"**Stock:** {product['stock']}")
                                st.info(f"**Category:** {product.get('category', 'N/A')}")

                            col1, col2 = st.columns(2)
                            with col1:
                                if st.button("Add to Cart", key=f"manual_add_cart_{branch_id}",
                                             use_container_width=True):
                                    st.success(f"Added {product['name']} to cart!")
                                    try:
                                        from backend.core.animations import show_toast
                                        show_toast(f"{product['name']} added to cart!", "success")
                                    except Exception:
                                        pass
                            with col2:
                                if st.button("Generate QR", key=f"manual_qr_{branch_id}",
                                             use_container_width=True):
                                    qr_html = generate_qr_code_html(manual_barcode2)
                                    st.markdown(qr_html, unsafe_allow_html=True)

                            log_scan(manual_barcode2, product["name"], "MANUAL", 1,
                                     "MANUAL", "SUCCESS", branch_id=branch_id)
                        else:
                            st.error(f"Product with barcode '{manual_barcode2}' not found in {branch_label}")
                else:
                    st.warning("Please enter a barcode")

        with col2:
            if manual_barcode2 and st.button("Generate QR", use_container_width=True,
                                             key=f"gen_qr_{branch_id}"):
                st.markdown(generate_qr_code_html(manual_barcode2), unsafe_allow_html=True)

    # ==============================
    # TAB 2: SCAN HISTORY
    # ==============================
    with tab2:
        st.markdown("## Scan History")

        if Path(SCAN_HISTORY_FILE).exists():
            df = pd.read_csv(SCAN_HISTORY_FILE)

            if not df.empty:
                if "timestamp" in df.columns:
                    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
                    df["timestamp"] = df["timestamp"].dt.strftime("%Y-%m-%d %H:%M")

                # Branch filter
                if "branch_id" in df.columns:
                    is_owner = role in ("owner", "admin")
                    if is_owner:
                        branches_present = sorted(df["branch_id"].dropna().unique().tolist())
                        filter_choice = st.selectbox(
                            "Filter by branch",
                            ["Current branch"] + branches_present + ["All branches"],
                            key=f"scan_history_branch_filter_{branch_id}",
                        )
                        if filter_choice == "Current branch":
                            df = df[df["branch_id"].astype(str).str.upper()
                                    == str(branch_id).upper()]
                        elif filter_choice == "All branches":
                            pass
                        else:
                            df = df[df["branch_id"] == filter_choice]
                    else:
                        # Non-owner: only their branch
                        df = df[df["branch_id"].astype(str).str.upper()
                                == str(branch_id).upper()]

                st.dataframe(df, use_container_width=True, hide_index=True)

                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Export Scan History (CSV)",
                    data=csv,
                    file_name=(
                        f"scan_history_{_branch_slug(branch_id)}_"
                        f"{datetime.now().strftime('%Y%m%d')}.csv"
                    ),
                    mime="text/csv",
                )
            else:
                st.info(f"No scan history for {branch_label}")
        else:
            st.info("No scan history found")

    # ==============================
    # TAB 3: BULK SCANNER
    # ==============================
    with tab3:
        st.markdown("## Bulk Barcode Scanner")
        st.caption(f"Scan multiple barcodes for stock take — {branch_label}")

        if settings.get("bulk_mode", False):
            st.info("Bulk scan mode is ACTIVE")
        else:
            st.warning("Bulk scan mode is INACTIVE. Enable in Settings.")

        bulk_barcodes = st.text_area(
            "Paste or type barcodes (one per line)",
            placeholder="6001\n6002\n6003\n1234567890",
            height=150,
            key=f"bulk_barcodes_{branch_id}",
        )

        if bulk_barcodes:
            barcodes = [b.strip() for b in bulk_barcodes.split("\n") if b.strip()]
            st.info(f"{len(barcodes)} barcodes to scan")

            if st.button("Scan All Barcodes", type="primary", use_container_width=True,
                         key=f"bulk_scan_{branch_id}"):
                results = []
                found = 0
                not_found = 0

                for barcode in barcodes:
                    if not products_df.empty:
                        product = products_df[products_df["barcode"].astype(str) == barcode]
                    else:
                        product = pd.DataFrame()

                    if not product.empty:
                        product = product.iloc[0]
                        results.append({
                            "Barcode": barcode,
                            "Product": product["name"],
                            "Price": product["price"],
                            "Stock": product["stock"],
                            "Status": "Found",
                        })
                        found += 1
                        log_scan(barcode, product["name"], "BULK", 1,
                                 "BULK", "SUCCESS", branch_id=branch_id)
                    else:
                        results.append({
                            "Barcode": barcode,
                            "Product": "Not Found",
                            "Price": "N/A",
                            "Stock": "N/A",
                            "Status": "Not Found",
                        })
                        not_found += 1

                results_df = pd.DataFrame(results)
                st.dataframe(results_df, use_container_width=True, hide_index=True)
                st.success(f"Found: {found} | Not Found: {not_found}")

                csv = results_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download Results (CSV)",
                    data=csv,
                    file_name=(
                        f"bulk_scan_{_branch_slug(branch_id)}_"
                        f"{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
                    ),
                    mime="text/csv",
                )

    # ==============================
    # TAB 4: PRODUCT LOOKUP
    # ==============================
    with tab4:
        st.markdown("## Product Lookup")
        st.caption(f"Searching within {branch_label}")

        search_term = st.text_input(
            "Search Product",
            placeholder="Name or barcode",
            key=f"lookup_search_{branch_id}",
        )

        if search_term and not products_df.empty:
            results = products_df[
                products_df["name"].str.contains(search_term, case=False)
                | products_df["barcode"].astype(str).str.contains(search_term, case=False)
            ]

            if not results.empty:
                st.dataframe(
                    results[["barcode", "name", "price", "stock", "category"]],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "price": st.column_config.NumberColumn("Price", format="$%.2f"),
                    },
                )

                selected_product = st.selectbox(
                    "Select product to generate barcode",
                    results["name"].tolist(),
                    key=f"lookup_select_{branch_id}",
                )
                if selected_product:
                    product = results[results["name"] == selected_product].iloc[0]
                    st.markdown(
                        generate_barcode_html(product["barcode"], product["name"], branch_label),
                        unsafe_allow_html=True,
                    )
                    st.markdown(generate_qr_code_html(product["barcode"]), unsafe_allow_html=True)
            else:
                st.warning(f"No products found in {branch_label}")
        elif search_term and products_df.empty:
            st.warning(f"No products loaded for {branch_label}")

    # ==============================
    # TAB 5: SETTINGS
    # ==============================
    with tab5:
        st.markdown("## Scanner Settings")
        st.caption("Scanner settings are shared across all branches.")

        col1, col2 = st.columns(2)

        with col1:
            enable_camera = st.checkbox("Enable Camera",
                                        value=settings.get("enable_camera", True),
                                        key=f"sc_enable_camera_{branch_id}")
            scan_mode = st.selectbox(
                "Scan Mode",
                ["auto", "manual", "continuous"],
                index=["auto", "manual", "continuous"].index(settings.get("scan_mode", "manual")),
                key=f"sc_scan_mode_{branch_id}",
            )
            scan_timeout = st.number_input(
                "Scan Timeout (seconds)",
                min_value=1, max_value=30,
                value=settings.get("scan_timeout", 5),
                key=f"sc_scan_timeout_{branch_id}",
            )

        with col2:
            sound_enabled = st.checkbox("Enable Sound",
                                        value=settings.get("sound_enabled", True),
                                        key=f"sc_sound_{branch_id}")
            vibration_enabled = st.checkbox("Enable Vibration",
                                            value=settings.get("vibration_enabled", True),
                                            key=f"sc_vib_{branch_id}")
            bulk_mode = st.checkbox("Enable Bulk Scan Mode",
                                    value=settings.get("bulk_mode", False),
                                    key=f"sc_bulk_{branch_id}")

        st.markdown("### Auto Actions")
        auto_add_cart = st.checkbox("Auto-add to Cart",
                                    value=settings.get("auto_add_to_cart", False),
                                    key=f"sc_auto_cart_{branch_id}")
        auto_add_inventory = st.checkbox("Auto-add to Inventory",
                                         value=settings.get("auto_add_to_inventory", False),
                                         key=f"sc_auto_inv_{branch_id}")

        if st.button("Save Scanner Settings", type="primary", use_container_width=True,
                     key=f"sc_save_{branch_id}"):
            settings.update({
                "enable_camera": enable_camera,
                "scan_mode": scan_mode,
                "scan_timeout": scan_timeout,
                "sound_enabled": sound_enabled,
                "vibration_enabled": vibration_enabled,
                "bulk_mode": bulk_mode,
                "auto_add_to_cart": auto_add_cart,
                "auto_add_to_inventory": auto_add_inventory,
            })
            save_scanner_settings(settings)
            st.success("Settings saved successfully!")
            try:
                from backend.core.animations import show_toast
                show_toast("Scanner settings updated!", "success")
            except Exception:
                pass


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    barcode_scanner_dashboard()