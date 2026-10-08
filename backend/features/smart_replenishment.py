# backend/features/smart_replenishment.py
# Smart Replenishment — branch-aware.
#
# Branch scoping:
#     branch_id = None          -> session branch
#     branch_id = "HO"/"NAT"/.. -> that single branch
#     branch_id = "__ALL__"     -> aggregate across all branches (owner only)
#
# Auto-POs and replenishment logs gain a branch_id column; existing files
# auto-migrate.

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from pathlib import Path
import json
import re
import numpy as np

from backend.core.db_adapter import (
    load_products,
    load_sales,
    load_suppliers,
    load_purchases,
    load_branches,
)


# ==============================
# FILE PATHS
# ==============================
DATA_DIR = Path("data")
REPLENISHMENT_FILE = DATA_DIR / "replenishment_settings.json"
AUTO_PO_FILE = DATA_DIR / "auto_purchase_orders.csv"
REPLENISHMENT_LOG_FILE = DATA_DIR / "replenishment_logs.csv"

AUTO_PO_COLUMNS = [
    "po_number", "branch_id", "supplier", "product_name", "product_barcode",
    "quantity", "cost_price", "total_cost", "reorder_level", "current_stock",
    "reason", "status", "created_date", "approved_date", "approved_by", "notes",
]

REPLENISHMENT_LOG_COLUMNS = [
    "log_id", "date", "branch_id", "product_name", "barcode",
    "current_stock", "reorder_level", "recommended_qty",
    "action", "status", "notes",
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
            key="replenishment_branch_scope",
            help="Owners may plan replenishment per branch or view all.",
        )
        if choice == "All Branches":
            return ALL_BRANCHES, "All Branches"
        m = re.search(r"\(([^)]+)\)\s*$", choice)
        code = m.group(1).strip() if m else choice
        return code, choice

    session_branch = _resolve_branch(None)
    label = _branch_label(session_branch)
    st.info(f"Smart replenishment locked to your branch: **{label}**")
    return session_branch, label


# ==============================
# INITIALIZATION
# ==============================
def init_replenishment_files():
    """Initialize files and auto-migrate CSVs to include branch_id."""
    DATA_DIR.mkdir(exist_ok=True)

    if not REPLENISHMENT_FILE.exists():
        settings = {
            "auto_replenish": True,
            "reorder_point_multiplier": 1.5,
            "safety_stock_days": 7,
            "lead_time_days": 3,
            "max_order_quantity": 1000,
            "min_order_quantity": 10,
            "supplier_preference": "best_price",
            "auto_approve": False,
        }
        with open(REPLENISHMENT_FILE, "w") as f:
            json.dump(settings, f, indent=2)

    # Auto-PO file — insert branch_id after po_number if missing
    if not AUTO_PO_FILE.exists():
        pd.DataFrame(columns=AUTO_PO_COLUMNS).to_csv(AUTO_PO_FILE, index=False)
    else:
        try:
            existing = pd.read_csv(AUTO_PO_FILE)
            if "branch_id" not in existing.columns:
                existing.insert(1, "branch_id", "HO")
                existing = existing[[c for c in AUTO_PO_COLUMNS if c in existing.columns]]
                existing.to_csv(AUTO_PO_FILE, index=False)
        except Exception:
            pd.DataFrame(columns=AUTO_PO_COLUMNS).to_csv(AUTO_PO_FILE, index=False)

    # Log file — insert branch_id after date if missing
    if not REPLENISHMENT_LOG_FILE.exists():
        pd.DataFrame(columns=REPLENISHMENT_LOG_COLUMNS).to_csv(
            REPLENISHMENT_LOG_FILE, index=False
        )
    else:
        try:
            existing = pd.read_csv(REPLENISHMENT_LOG_FILE)
            if "branch_id" not in existing.columns:
                existing.insert(2, "branch_id", "HO")
                existing = existing[[c for c in REPLENISHMENT_LOG_COLUMNS if c in existing.columns]]
                existing.to_csv(REPLENISHMENT_LOG_FILE, index=False)
        except Exception:
            pd.DataFrame(columns=REPLENISHMENT_LOG_COLUMNS).to_csv(
                REPLENISHMENT_LOG_FILE, index=False
            )


# ==============================
# LOAD / SAVE
# ==============================
def load_replenishment_settings():
    init_replenishment_files()
    with open(REPLENISHMENT_FILE, "r") as f:
        return json.load(f)


def save_replenishment_settings(settings):
    with open(REPLENISHMENT_FILE, "w") as f:
        json.dump(settings, f, indent=2)


def load_auto_po(branch_id=None):
    """
    Load auto-POs. Scoped when branch_id is set; __ALL__ returns everything.
    """
    init_replenishment_files()
    try:
        df = pd.read_csv(AUTO_PO_FILE)
    except Exception:
        return pd.DataFrame(columns=AUTO_PO_COLUMNS)

    if "branch_id" not in df.columns:
        df["branch_id"] = "HO"

    if branch_id is None:
        return df
    branch_id = _resolve_branch(branch_id)
    if _is_all_branches(branch_id):
        return df
    return df[df["branch_id"].astype(str).str.upper() == str(branch_id).upper()].copy()


def save_auto_po(df):
    df.to_csv(AUTO_PO_FILE, index=False)


def load_replenishment_logs(branch_id=None):
    init_replenishment_files()
    try:
        df = pd.read_csv(REPLENISHMENT_LOG_FILE)
    except Exception:
        return pd.DataFrame(columns=REPLENISHMENT_LOG_COLUMNS)

    if "branch_id" not in df.columns:
        df["branch_id"] = "HO"

    if branch_id is None:
        return df
    branch_id = _resolve_branch(branch_id)
    if _is_all_branches(branch_id):
        return df
    return df[df["branch_id"].astype(str).str.upper() == str(branch_id).upper()].copy()


def save_replenishment_logs(df):
    df.to_csv(REPLENISHMENT_LOG_FILE, index=False)


# ==============================
# COLUMN FINDERS
# ==============================
def find_date_column(df):
    if df is None or df.empty:
        return None
    for col in ["date", "sale_date", "transaction_date", "created_at", "order_date"]:
        if col in df.columns:
            return col
    return None


def find_product_column(df):
    if df is None or df.empty:
        return None
    for col in ["name", "product_name", "Product", "item_name"]:
        if col in df.columns:
            return col
    return None


def find_items_column(df):
    if df is None or df.empty:
        return None
    for col in ["items", "quantity", "qty", "item_count"]:
        if col in df.columns:
            return col
    return None


# ==============================
# REORDER CALCULATION
# ==============================
def calculate_reorder_quantity(product, settings, daily_sales_rate):
    """EOQ-based recommendation."""
    current_stock = float(product.get("stock", 0))
    reorder_level = float(product.get("reorder_level", 0))
    cost = float(product.get("cost", 0))

    if current_stock > reorder_level:
        return 0, None

    lead_time_days = settings.get("lead_time_days", 3)
    safety_stock_days = settings.get("safety_stock_days", 7)

    lead_time_demand = daily_sales_rate * lead_time_days
    safety_stock = daily_sales_rate * safety_stock_days

    annual_demand = daily_sales_rate * 365
    ordering_cost = 50
    holding_cost = cost * 0.25

    eoq = (
        np.sqrt((2 * annual_demand * ordering_cost) / holding_cost)
        if holding_cost > 0 else 0
    )

    recommended_qty = max(eoq, lead_time_demand + safety_stock - current_stock)
    min_qty = settings.get("min_order_quantity", 10)
    max_qty = settings.get("max_order_quantity", 1000)

    recommended_qty = max(min_qty, recommended_qty)
    recommended_qty = min(max_qty, recommended_qty)
    recommended_qty = int(np.ceil(recommended_qty / 10) * 10)

    return recommended_qty, {
        "lead_time_demand": lead_time_demand,
        "safety_stock": safety_stock,
        "eoq": eoq,
        "daily_sales": daily_sales_rate,
    }


def get_supplier_for_product(product_name, settings, branch_id=None):
    """
    Pick the best supplier for this product, considering only the current
    branch's purchase history (unless scope is __ALL__, in which case the
    union is used — which is what an owner would want for a group decision).
    """
    branch_id = _resolve_branch(branch_id)

    suppliers_df = _load_scoped(load_suppliers, branch_id)
    purchases_df = _load_scoped(load_purchases, branch_id)

    if suppliers_df is None or suppliers_df.empty:
        return None

    if purchases_df is not None and not purchases_df.empty and "product_name" in purchases_df.columns:
        product_purchases = purchases_df[purchases_df["product_name"] == product_name]
        if (
            not product_purchases.empty
            and "supplier" in product_purchases.columns
            and "cost_price" in product_purchases.columns
        ):
            try:
                best_supplier = product_purchases.groupby("supplier")["cost_price"].min().idxmin()
                return best_supplier
            except Exception:
                pass

    return suppliers_df.iloc[0]["name"] if "name" in suppliers_df.columns else None


def generate_auto_po(product, recommended_qty, supplier, settings, branch_id=None):
    """Build a single new row for auto_purchase_orders.csv."""
    branch_id = _resolve_branch(branch_id)
    branch_key = _branch_slug(branch_id)

    po_number = f"PO-AUTO-{branch_key}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    total_cost = float(product["cost"]) * recommended_qty
    auto_approve = settings.get("auto_approve", False)

    return pd.DataFrame([{
        "po_number": po_number,
        "branch_id": branch_key,
        "supplier": supplier,
        "product_name": product["name"],
        "product_barcode": product["barcode"],
        "quantity": recommended_qty,
        "cost_price": float(product["cost"]),
        "total_cost": total_cost,
        "reorder_level": product.get("reorder_level", 0),
        "current_stock": product.get("stock", 0),
        "reason": f"Auto-replenishment for {branch_key}: stock below reorder level",
        "status": "APPROVED" if auto_approve else "PENDING_APPROVAL",
        "created_date": datetime.now().isoformat(),
        "approved_date": datetime.now().isoformat() if auto_approve else "",
        "approved_by": "System" if auto_approve else "",
        "notes": f"[{branch_key}] Auto-generated. Recommended qty: {recommended_qty}",
    }])


# ==============================
# DAILY SALES RATE
# ==============================
def _daily_rate_map(sales_df):
    """
    Compute per-product daily sales rate from an already-scoped sales frame.
    """
    if sales_df is None or sales_df.empty:
        return {}

    date_col = find_date_column(sales_df)
    product_col = find_product_column(sales_df)
    items_col = find_items_column(sales_df)

    if not date_col or not product_col:
        return {}

    sales_df = sales_df.copy()
    sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
    sales_df = sales_df.dropna(subset=[date_col])
    if sales_df.empty:
        return {}

    cutoff = datetime.now() - timedelta(days=30)
    recent = sales_df[sales_df[date_col] >= cutoff]

    result = {}
    for product_name in sales_df[product_col].dropna().unique():
        prod_sales = recent[recent[product_col] == product_name]
        if items_col and items_col in prod_sales.columns:
            total_qty = pd.to_numeric(prod_sales[items_col], errors="coerce").fillna(0).sum()
        else:
            total_qty = len(prod_sales)
        result[product_name] = float(total_qty) / 30.0
    return result


# ==============================
# DASHBOARD
# ==============================
def smart_replenishment_dashboard(branch_id=None):
    st.title("Smart Replenishment")
    st.caption("AI-powered automatic purchase order generation — branch-scoped")

    role = st.session_state.get("role", "cashier")
    if role not in ["owner", "manager"]:
        st.error("Access Denied. Only owners and managers can access smart replenishment.")
        return

    try:
        branches_df = load_branches()
    except Exception:
        branches_df = pd.DataFrame()

    if branch_id is None:
        branch_id, branch_label = _branch_scope_selector(branches_df)
    else:
        branch_label = _branch_label(branch_id)

    st.caption(f"Planning for: **{branch_label}**")

    init_replenishment_files()

    products_df = _load_scoped(load_products, branch_id)
    sales_df = _load_scoped(load_sales, branch_id)
    suppliers_df = _load_scoped(load_suppliers, branch_id)
    settings = load_replenishment_settings()

    if products_df is None or products_df.empty:
        st.warning(f"No products found for {branch_label}.")
        return

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Dashboard",
        "Replenishment Recommendations",
        "Auto Purchase Orders",
        "Settings",
        "Replenishment Logs",
    ])

    # ==============================
    # TAB 1: DASHBOARD
    # ==============================
    with tab1:
        st.markdown(f"## Replenishment Dashboard — {branch_label}")

        daily_rate = _daily_rate_map(sales_df)

        products_df = products_df.copy()
        products_df["stock"] = pd.to_numeric(products_df["stock"], errors="coerce").fillna(0)
        products_df["reorder_level"] = pd.to_numeric(
            products_df["reorder_level"], errors="coerce"
        ).fillna(0)

        needs = []
        for _, product in products_df.iterrows():
            current_stock = float(product["stock"])
            reorder_level = float(product["reorder_level"])
            rate = daily_rate.get(product["name"], 0)
            if current_stock <= reorder_level and rate > 0:
                needs.append({
                    "Product": product["name"],
                    "Barcode": product["barcode"],
                    "Current Stock": current_stock,
                    "Reorder Level": reorder_level,
                    "Daily Sales": rate,
                    "Days of Stock": current_stock / rate if rate > 0 else 0,
                    "Category": product.get("category", "Uncategorized"),
                })

        needs_df = pd.DataFrame(needs)

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Needs Replenishment", len(needs_df))
        with col2:
            st.metric("Total Products", len(products_df))
        with col3:
            st.metric("Total Stock Units", f"{products_df['stock'].sum():,.0f}")
        with col4:
            low_stock = len(products_df[products_df["stock"] <= products_df["reorder_level"]])
            st.metric("Low Stock Items", low_stock)

        if not needs_df.empty:
            st.markdown("### Products Needing Replenishment")
            st.dataframe(
                needs_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Days of Stock": st.column_config.NumberColumn("Days of Stock", format="%.1f"),
                    "Daily Sales": st.column_config.NumberColumn("Daily Sales", format="%.1f"),
                },
            )
            fig = px.bar(
                needs_df, x="Product", y="Days of Stock",
                title=f"Days of Stock Remaining — {branch_label}",
                color="Days of Stock", color_continuous_scale="RdYlGn_r",
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.success(f"All products in {branch_label} have sufficient stock")

    # ==============================
    # TAB 2: RECOMMENDATIONS
    # ==============================
    with tab2:
        st.markdown(f"## Replenishment Recommendations — {branch_label}")

        if _is_all_branches(branch_id):
            st.warning(
                "Generating POs from All Branches would create one PO per product "
                "across the whole company. Pick a specific branch to generate POs."
            )

        daily_rate = _daily_rate_map(sales_df)

        recommendations = []
        for _, product in products_df.iterrows():
            current_stock = float(product["stock"])
            reorder_level = float(product["reorder_level"])
            rate = daily_rate.get(product["name"], 0)
            if current_stock <= reorder_level and rate > 0:
                recommended_qty, details = calculate_reorder_quantity(product, settings, rate)
                if recommended_qty > 0:
                    supplier = get_supplier_for_product(
                        product["name"], settings, branch_id=branch_id
                    )
                    recommendations.append({
                        "Product": product["name"],
                        "Barcode": product["barcode"],
                        "Current Stock": current_stock,
                        "Reorder Level": reorder_level,
                        "Daily Sales": rate,
                        "Recommended Qty": recommended_qty,
                        "Suggested Supplier": supplier or "No supplier found",
                        "Estimated Cost": recommended_qty * float(product["cost"]),
                        "Priority": "High" if current_stock < reorder_level * 0.3 else "Medium",
                    })

        recommendations_df = pd.DataFrame(recommendations)

        if recommendations_df.empty:
            st.success(f"No replenishment recommendations for {branch_label} at this time")
        else:
            st.info(
                f"Found {len(recommendations_df)} products needing replenishment in "
                f"{branch_label}"
            )
            st.dataframe(
                recommendations_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Estimated Cost": st.column_config.Column("Estimated Cost", format="$%.2f"),
                },
            )

            if _is_all_branches(branch_id):
                st.info("Switch to a specific branch to generate POs from these recommendations.")
            else:
                if st.button("Generate Purchase Orders for All",
                             type="primary", use_container_width=True,
                             key=f"gen_all_po_{branch_id}"):
                    po_count = 0
                    po_df = load_auto_po(branch_id=ALL_BRANCHES)
                    logs_df = load_replenishment_logs(branch_id=ALL_BRANCHES)
                    branch_key = _branch_slug(branch_id)

                    for _, rec in recommendations_df.iterrows():
                        product_row = products_df[products_df["barcode"] == rec["Barcode"]]
                        if product_row.empty:
                            continue
                        product = product_row.iloc[0]
                        supplier = rec["Suggested Supplier"]
                        if supplier and supplier != "No supplier found":
                            new_po = generate_auto_po(
                                product, rec["Recommended Qty"], supplier, settings,
                                branch_id=branch_id,
                            )
                            po_df = pd.concat([po_df, new_po], ignore_index=True)
                            po_count += 1

                            new_log = pd.DataFrame([{
                                "log_id": f"LOG{len(logs_df)+1:08d}",
                                "date": datetime.now().isoformat(),
                                "branch_id": branch_key,
                                "product_name": rec["Product"],
                                "barcode": rec["Barcode"],
                                "current_stock": rec["Current Stock"],
                                "reorder_level": rec["Reorder Level"],
                                "recommended_qty": rec["Recommended Qty"],
                                "action": "PO_GENERATED",
                                "status": "SUCCESS",
                                "notes": f"[{branch_key}] Auto PO created for {rec['Recommended Qty']} units",
                            }])
                            logs_df = pd.concat([logs_df, new_log], ignore_index=True)

                    save_auto_po(po_df)
                    save_replenishment_logs(logs_df)
                    st.success(f"Generated {po_count} purchase orders for {branch_label}!")
                    st.rerun()

    # ==============================
    # TAB 3: AUTO POs
    # ==============================
    with tab3:
        st.markdown("## Auto Purchase Orders")

        po_df = load_auto_po(branch_id=branch_id)

        if po_df.empty:
            st.info(f"No auto purchase orders for {branch_label}")
        else:
            if not _is_all_branches(branch_id):
                status_filter = st.selectbox(
                    "Filter by Status",
                    ["All", "PENDING_APPROVAL", "APPROVED", "REJECTED", "COMPLETED"],
                    key=f"po_status_{branch_id}",
                )
                filtered = po_df.copy()
                if status_filter != "All":
                    filtered = filtered[filtered["status"] == status_filter]
            else:
                filtered = po_df

            st.dataframe(
                filtered,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "total_cost": st.column_config.NumberColumn("Total Cost", format="$%.2f"),
                },
            )

            if not _is_all_branches(branch_id):
                pending = po_df[po_df["status"] == "PENDING_APPROVAL"]
                if not pending.empty:
                    st.markdown("### Pending Approvals")
                    selected_po = st.selectbox(
                        "Select PO to Review",
                        pending["po_number"].tolist(),
                        key=f"po_review_{branch_id}",
                    )
                    po_data = pending[pending["po_number"] == selected_po].iloc[0]

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.info(f"**Product:** {po_data['product_name']}")
                    with col2:
                        st.info(f"**Quantity:** {po_data['quantity']}")
                    with col3:
                        st.info(f"**Total Cost:** ${po_data['total_cost']:.2f}")

                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("Approve", use_container_width=True,
                                     key=f"po_approve_{selected_po}_{branch_id}"):
                            all_pos = load_auto_po(branch_id=ALL_BRANCHES)
                            idx = all_pos[all_pos["po_number"] == selected_po].index
                            if len(idx) > 0:
                                all_pos.loc[idx[0], "status"] = "APPROVED"
                                all_pos.loc[idx[0], "approved_date"] = datetime.now().isoformat()
                                all_pos.loc[idx[0], "approved_by"] = st.session_state.get(
                                    "username", "system"
                                )
                                save_auto_po(all_pos)
                                st.success(f"PO {selected_po} approved for {branch_label}!")
                                st.rerun()
                    with col2:
                        if st.button("Reject", use_container_width=True,
                                     key=f"po_reject_{selected_po}_{branch_id}"):
                            all_pos = load_auto_po(branch_id=ALL_BRANCHES)
                            idx = all_pos[all_pos["po_number"] == selected_po].index
                            if len(idx) > 0:
                                all_pos.loc[idx[0], "status"] = "REJECTED"
                                save_auto_po(all_pos)
                                st.warning(f"PO {selected_po} rejected")
                                st.rerun()

    # ==============================
    # TAB 4: SETTINGS
    # ==============================
    with tab4:
        st.markdown("## Replenishment Settings")
        st.caption("Settings are shared across all branches.")

        settings = load_replenishment_settings()

        col1, col2 = st.columns(2)
        with col1:
            auto_replenish = st.checkbox(
                "Enable Auto-Replenishment",
                value=settings.get("auto_replenish", True),
                key=f"rep_auto_{branch_id}",
            )
            reorder_point = st.number_input(
                "Reorder Point Multiplier", min_value=1.0, max_value=3.0,
                value=float(settings.get("reorder_point_multiplier", 1.5)), step=0.1,
                key=f"rep_reorder_{branch_id}",
            )
            safety_stock = st.number_input(
                "Safety Stock (Days)", min_value=1, max_value=30,
                value=int(settings.get("safety_stock_days", 7)),
                key=f"rep_safety_{branch_id}",
            )
        with col2:
            lead_time = st.number_input(
                "Supplier Lead Time (Days)", min_value=1, max_value=30,
                value=int(settings.get("lead_time_days", 3)),
                key=f"rep_lead_{branch_id}",
            )
            min_order = st.number_input(
                "Minimum Order Quantity", min_value=1, max_value=100,
                value=int(settings.get("min_order_quantity", 10)),
                key=f"rep_min_{branch_id}",
            )
            max_order = st.number_input(
                "Maximum Order Quantity", min_value=10, max_value=10000,
                value=int(settings.get("max_order_quantity", 1000)),
                key=f"rep_max_{branch_id}",
            )

        auto_approve = st.checkbox(
            "Auto-Approve Purchase Orders",
            value=settings.get("auto_approve", False),
            key=f"rep_autoappr_{branch_id}",
        )
        supplier_pref = st.selectbox(
            "Supplier Selection Preference",
            ["best_price", "best_rating", "fastest_delivery"],
            index=["best_price", "best_rating", "fastest_delivery"].index(
                settings.get("supplier_preference", "best_price")
            ),
            key=f"rep_pref_{branch_id}",
        )

        if st.button("Save Settings", type="primary", use_container_width=True,
                     key=f"rep_save_{branch_id}"):
            settings.update({
                "auto_replenish": auto_replenish,
                "reorder_point_multiplier": reorder_point,
                "safety_stock_days": safety_stock,
                "lead_time_days": lead_time,
                "min_order_quantity": min_order,
                "max_order_quantity": max_order,
                "auto_approve": auto_approve,
                "supplier_preference": supplier_pref,
            })
            save_replenishment_settings(settings)
            st.success("Settings saved successfully!")
            st.rerun()

    # ==============================
    # TAB 5: LOGS
    # ==============================
    with tab5:
        st.markdown("## Replenishment Logs")

        logs_df = load_replenishment_logs(branch_id=branch_id)

        if logs_df.empty:
            st.info(f"No replenishment logs for {branch_label}")
        else:
            if "date" in logs_df.columns:
                logs_df = logs_df.copy()
                logs_df["date"] = pd.to_datetime(logs_df["date"], errors="coerce")
                logs_df["date"] = logs_df["date"].dt.strftime("%Y-%m-%d %H:%M")

            st.dataframe(logs_df, use_container_width=True, hide_index=True)

            csv = logs_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Export Logs (CSV)",
                data=csv,
                file_name=(
                    f"replenishment_logs_{_branch_slug(branch_id)}_"
                    f"{datetime.now().strftime('%Y%m%d')}.csv"
                ),
                mime="text/csv",
            )


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    smart_replenishment_dashboard()