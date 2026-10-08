# backend/features/mobile_dashboard.py
# Mobile Dashboard — branch-aware.
#
# Branch scoping:
#     branch_id = None          -> session branch
#     branch_id = "HO"/"NAT"/.. -> that single branch
#     branch_id = "__ALL__"     -> aggregate across all branches (owner only)
#
# Every metric loader and every WhatsApp message carries its branch label so
# alerts cannot be mistaken for another branch's data.

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import re

from backend.core.db_adapter import (
    load_sales,
    load_products,
    load_purchases,
    load_shifts,
    load_cash,
    load_branches,
    get_all_active_shifts,
    to_float,
    get_active_shift_id,
)
from backend.utils.utils import get_whatsapp_link, generate_whatsapp_receipt
from backend.utils.phone_utils import validate_zimbabwe_phone


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
            key="mobile_branch_scope",
            help="Owners may inspect any branch on mobile.",
        )
        if choice == "All Branches":
            return ALL_BRANCHES, "All Branches"
        m = re.search(r"\(([^)]+)\)\s*$", choice)
        code = m.group(1).strip() if m else choice
        return code, choice

    session_branch = _resolve_branch(None)
    label = _branch_label(session_branch)
    st.info(f"Mobile dashboard locked to your branch: **{label}**")
    return session_branch, label


# ==============================
# MOBILE DEVICE DETECTION
# ==============================
def is_mobile():
    try:
        from streamlit import runtime
        if runtime.exists():
            ua = st.context.headers.get("User-Agent", "")
            keywords = ["Mobile", "Android", "iPhone", "iPad", "iPod", "BlackBerry", "Windows Phone"]
            return any(k in ua for k in keywords)
    except Exception:
        pass
    return False


def get_mobile_css():
    return """
    <style>
        @media only screen and (max-width: 768px) {
            .main .block-container { padding: 1rem !important; }
            h1 { font-size: 1.5rem !important; }
            h2 { font-size: 1.3rem !important; }
            .stMetric { text-align: center; }
            .stButton button {
                width: 100% !important;
                padding: 0.75rem !important;
                font-size: 1rem !important;
            }
            div[data-testid="column"] { padding: 0.25rem !important; }
        }
        .whatsapp-btn {
            background: #25D366; color: white; border: none;
            border-radius: 30px; padding: 12px 20px; cursor: pointer;
            font-weight: bold; text-decoration: none;
            display: inline-block; text-align: center; margin: 5px 0; width: 100%;
        }
        .whatsapp-btn:hover { background: #128C7E; transform: scale(1.02); transition: all 0.3s ease; }
        .alert-critical { background: linear-gradient(135deg, #ff6b6b 0%, #ee5a5a 100%); color: white; border-radius: 12px; padding: 12px; margin: 8px 0; }
        .alert-warning { background: linear-gradient(135deg, #ffd93d 0%, #f9ca24 100%); color: #333; border-radius: 12px; padding: 12px; margin: 8px 0; }
        .alert-info { background: linear-gradient(135deg, #6c5ce7 0%, #5b4cc9 100%); color: white; border-radius: 12px; padding: 12px; margin: 8px 0; }
        .stat-card {
            background: white; border-radius: 12px; padding: 15px;
            text-align: center; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin: 8px 0;
        }
        .stat-value { font-size: 1.8rem; font-weight: bold; color: #2d3436; }
        .stat-label { font-size: 0.8rem; color: #636e72; margin-top: 5px; }
        .branch-badge {
            display: inline-block; background: #eef2ff; color: #3730a3;
            padding: 4px 12px; border-radius: 20px; font-weight: bold;
            font-size: 0.85rem; margin: 6px 0;
        }
    </style>
    """


# ==============================
# WHATSAPP MESSAGE BUILDERS (branch-tagged)
# ==============================
def get_whatsapp_alert_message(alert_type, data, branch_id=None):
    """Every message includes *Branch: <label>* so the recipient knows the scope."""
    branch_id = _resolve_branch(branch_id)
    label = _branch_label(branch_id)

    if alert_type == "stock_out":
        products = data.get("products", [])
        if not products:
            return None
        message = f"*STOCK OUT ALERT*\n\n*Branch: {label}*\n\n"
        message += "The following products are OUT OF STOCK:\n\n"
        for p in products[:5]:
            message += f"{p['name']}\n"
        if len(products) > 5:
            message += f"\n... and {len(products) - 5} more items\n"
        message += f"\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        message += "*Immediate action required!*\n"
        return message

    if alert_type == "low_stock":
        products = data.get("products", [])
        if not products:
            return None
        message = f"*LOW STOCK ALERT*\n\n*Branch: {label}*\n\n"
        message += "The following products need reordering:\n\n"
        for p in products[:5]:
            message += f"{p['name']}: {p['stock']} units left (Reorder at {p['reorder_level']})\n"
        if len(products) > 5:
            message += f"\n... and {len(products) - 5} more items\n"
        message += f"\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        return message

    if alert_type == "daily_summary":
        sales = data.get("sales", 0)
        profit = data.get("profit", 0)
        transactions = data.get("transactions", 0)
        top_product = data.get("top_product", "N/A")
        shift_id = data.get("shift_id", "N/A")

        message = f"*Daily Sales Summary*\n\n*Branch: {label}*\n\n"
        message += f"Date: {datetime.now().strftime('%Y-%m-%d')}\n"
        message += f"Total Sales: ${sales:,.2f}\n"
        message += f"Profit: ${profit:,.2f}\n"
        message += f"Transactions: {transactions}\n"
        message += f"Top Product: {top_product}\n"
        if shift_id != "N/A":
            message += f"Shift: {shift_id}\n"
        message += "\n*SmartGro ERP* - Aziel Investments"
        return message

    if alert_type == "purchase_approval":
        po_number = data.get("po_number", "")
        supplier = data.get("supplier", "")
        total = data.get("total", 0)
        items = data.get("items", [])

        message = f"*Purchase Order Approval Required*\n\n*Branch: {label}*\n\n"
        message += f"PO Number: {po_number}\n"
        message += f"Supplier: {supplier}\n"
        message += f"Total Value: ${total:,.2f}\n"
        message += f"Items: {len(items)}\n\n"
        message += f"Reply 'APPROVE {po_number}' to approve\n"
        message += f"Reply 'REJECT {po_number}' to reject"
        return message

    if alert_type == "shift_summary":
        shift_data = data.get("shift_data", {})
        shift_id = shift_data.get("shift_id", "N/A")
        cashier = shift_data.get("cashier_name", "N/A")
        revenue = shift_data.get("total_revenue", 0)
        profit = shift_data.get("profit", 0)
        transactions = shift_data.get("transactions", 0)
        cash_sales = shift_data.get("cash_sales", 0)
        credit_sales = shift_data.get("credit_sales", 0)

        message = f"*Shift Summary*\n\n*Branch: {label}*\n\n"
        message += f"Shift ID: {shift_id}\n"
        message += f"Cashier: {cashier}\n"
        message += f"Revenue: ${revenue:,.2f}\n"
        message += f"Profit: ${profit:,.2f}\n"
        message += f"Transactions: {transactions}\n"
        message += f"Cash Sales: ${cash_sales:,.2f}\n"
        message += f"Credit Sales: ${credit_sales:,.2f}\n"
        message += "\n*SmartGro ERP* - Aziel Investments"
        return message

    return None


def send_whatsapp_alert(phone, alert_type, data, branch_id=None):
    message = get_whatsapp_alert_message(alert_type, data, branch_id=branch_id)
    if message:
        return get_whatsapp_link(phone, message)
    return None


# ==============================
# SCOPED METRIC LOADERS
# ==============================
def get_todays_stats(branch_id=None):
    """Today's sales stats, scoped to branch_id."""
    branch_id = _resolve_branch(branch_id)
    sales_df = _load_scoped(load_sales, branch_id)

    empty_stats = {
        "sales": 0, "profit": 0, "transactions": 0, "items_sold": 0,
        "top_product": "N/A", "avg_transaction": 0, "shift_id": "N/A",
        "cash_sales": 0, "credit_sales": 0,
    }
    if sales_df is None or sales_df.empty:
        return empty_stats

    # Ensure date column
    if "date" not in sales_df.columns and "sale_date" in sales_df.columns:
        sales_df = sales_df.copy()
        sales_df["date"] = sales_df["sale_date"]
    if "date" not in sales_df.columns:
        return empty_stats

    today = datetime.now().strftime("%Y-%m-%d")
    sales_df = sales_df.copy()
    sales_df["date"] = pd.to_datetime(sales_df["date"], errors="coerce")
    today_sales = sales_df[sales_df["date"].dt.strftime("%Y-%m-%d") == today]
    if today_sales.empty:
        return empty_stats

    receipt_col = None
    for col in ["receipt_no", "receipt", "transaction_id", "order_id"]:
        if col in today_sales.columns:
            receipt_col = col
            break

    if receipt_col:
        unique_sales = today_sales.drop_duplicates(subset=[receipt_col])
        transactions = len(unique_sales)
    else:
        unique_sales = today_sales
        transactions = len(today_sales)

    total_sales = 0
    if receipt_col and "final_total" in today_sales.columns:
        receipt_totals = today_sales.groupby(receipt_col)["final_total"].first()
        total_sales = to_float(receipt_totals.sum())
    elif "final_total" in today_sales.columns:
        total_sales = to_float(unique_sales["final_total"].sum())
    elif "total" in today_sales.columns:
        total_sales = to_float(unique_sales["total"].sum())

    total_profit = 0
    if receipt_col and "profit" in today_sales.columns:
        receipt_profit = today_sales.groupby(receipt_col)["profit"].first()
        total_profit = to_float(receipt_profit.sum())
    elif "profit" in today_sales.columns:
        total_profit = to_float(unique_sales["profit"].sum())

    items_sold = 0
    if receipt_col and "items" in today_sales.columns:
        receipt_items = today_sales.groupby(receipt_col)["items"].first()
        items_sold = int(receipt_items.sum())
    elif "items" in today_sales.columns:
        items_sold = int(unique_sales["items"].sum())

    cash_sales = 0
    credit_sales = 0
    if receipt_col and "payment_method" in today_sales.columns and "final_total" in today_sales.columns:
        unique_with_payment = today_sales.drop_duplicates(subset=[receipt_col, "payment_method"])
        cash_mask = unique_with_payment["payment_method"] == "CASH"
        credit_mask = unique_with_payment["payment_method"] == "CREDIT"
        cash_sales = to_float(unique_with_payment[cash_mask]["final_total"].sum())
        credit_sales = to_float(unique_with_payment[credit_mask]["final_total"].sum())
    elif "payment_method" in today_sales.columns and "final_total" in today_sales.columns:
        cash_sales = to_float(unique_sales[unique_sales["payment_method"] == "CASH"]["final_total"].sum())
        credit_sales = to_float(unique_sales[unique_sales["payment_method"] == "CREDIT"]["final_total"].sum())

    top_product = "N/A"
    if "name" in today_sales.columns and "items" in today_sales.columns:
        if receipt_col:
            unique_for_products = today_sales.drop_duplicates(subset=[receipt_col, "name"])
            product_sales = unique_for_products.groupby("name")["items"].sum()
        else:
            product_sales = unique_sales.groupby("name")["items"].sum()
        if not product_sales.empty:
            top_product = product_sales.nlargest(1).index[0]

    shift_id = "N/A"
    if "shift_id" in today_sales.columns:
        if receipt_col:
            shift_ids = today_sales.drop_duplicates(subset=[receipt_col])["shift_id"].dropna().unique()
        else:
            shift_ids = unique_sales["shift_id"].dropna().unique()
        if len(shift_ids) > 0:
            shift_id = shift_ids[0]

    return {
        "sales": total_sales,
        "profit": total_profit,
        "transactions": transactions,
        "items_sold": items_sold,
        "top_product": top_product,
        "avg_transaction": total_sales / transactions if transactions > 0 else 0,
        "shift_id": shift_id,
        "cash_sales": cash_sales,
        "credit_sales": credit_sales,
    }


def get_weekly_stats(branch_id=None):
    branch_id = _resolve_branch(branch_id)
    sales_df = _load_scoped(load_sales, branch_id)
    empty = {"sales": 0, "profit": 0, "transactions": 0, "daily_average": 0}

    if sales_df is None or sales_df.empty:
        return empty

    if "date" not in sales_df.columns and "sale_date" in sales_df.columns:
        sales_df = sales_df.copy()
        sales_df["date"] = sales_df["sale_date"]
    if "date" not in sales_df.columns:
        return empty

    sales_df = sales_df.copy()
    sales_df["date"] = pd.to_datetime(sales_df["date"], errors="coerce")
    week_ago = datetime.now() - timedelta(days=7)
    week_sales = sales_df[sales_df["date"] >= week_ago]
    if week_sales.empty:
        return empty

    receipt_col = next(
        (c for c in ["receipt_no", "receipt", "transaction_id", "order_id"] if c in week_sales.columns),
        None,
    )

    if receipt_col and "final_total" in week_sales.columns:
        receipt_totals = week_sales.groupby(receipt_col)["final_total"].first()
        total_sales = to_float(receipt_totals.sum())
        transactions = len(receipt_totals)
    elif "final_total" in week_sales.columns:
        total_sales = to_float(week_sales["final_total"].sum())
        transactions = week_sales["receipt_no"].nunique() if "receipt_no" in week_sales.columns else len(week_sales)
    else:
        total_sales = to_float(week_sales["total"].sum())
        transactions = len(week_sales)

    if receipt_col and "profit" in week_sales.columns:
        receipt_profit = week_sales.groupby(receipt_col)["profit"].first()
        total_profit = to_float(receipt_profit.sum())
    elif "profit" in week_sales.columns:
        total_profit = to_float(week_sales["profit"].sum())
    else:
        total_profit = 0

    return {
        "sales": total_sales,
        "profit": total_profit,
        "transactions": transactions,
        "daily_average": total_sales / 7,
    }


def get_monthly_stats(branch_id=None):
    branch_id = _resolve_branch(branch_id)
    sales_df = _load_scoped(load_sales, branch_id)
    empty = {"sales": 0, "profit": 0, "transactions": 0}

    if sales_df is None or sales_df.empty:
        return empty

    if "date" not in sales_df.columns and "sale_date" in sales_df.columns:
        sales_df = sales_df.copy()
        sales_df["date"] = sales_df["sale_date"]
    if "date" not in sales_df.columns:
        return empty

    sales_df = sales_df.copy()
    sales_df["date"] = pd.to_datetime(sales_df["date"], errors="coerce")
    current_month = datetime.now().strftime("%Y-%m")
    month_sales = sales_df[sales_df["date"].dt.strftime("%Y-%m") == current_month]
    if month_sales.empty:
        return empty

    receipt_col = next(
        (c for c in ["receipt_no", "receipt", "transaction_id", "order_id"] if c in month_sales.columns),
        None,
    )

    if receipt_col and "final_total" in month_sales.columns:
        receipt_totals = month_sales.groupby(receipt_col)["final_total"].first()
        total_sales = to_float(receipt_totals.sum())
        transactions = len(receipt_totals)
    elif "final_total" in month_sales.columns:
        total_sales = to_float(month_sales["final_total"].sum())
        transactions = month_sales["receipt_no"].nunique() if "receipt_no" in month_sales.columns else len(month_sales)
    else:
        total_sales = to_float(month_sales["total"].sum())
        transactions = len(month_sales)

    if receipt_col and "profit" in month_sales.columns:
        receipt_profit = month_sales.groupby(receipt_col)["profit"].first()
        total_profit = to_float(receipt_profit.sum())
    elif "profit" in month_sales.columns:
        total_profit = to_float(month_sales["profit"].sum())
    else:
        total_profit = 0

    return {"sales": total_sales, "profit": total_profit, "transactions": transactions}


def get_shift_summary(branch_id=None):
    branch_id = _resolve_branch(branch_id)
    shifts_df = _load_scoped(load_shifts, branch_id)

    if shifts_df is None or shifts_df.empty:
        return {
            "active_shift": None, "total_shifts": 0,
            "total_revenue": 0, "total_profit": 0, "total_transactions": 0,
        }

    active_shifts = shifts_df[shifts_df["status"] == "OPEN"]
    active_shift = active_shifts.iloc[0].to_dict() if not active_shifts.empty else None
    closed = shifts_df[shifts_df["status"] == "CLOSED"]

    return {
        "active_shift": active_shift,
        "total_shifts": len(shifts_df),
        "active_shifts": len(active_shifts),
        "closed_shifts": len(closed),
        "total_revenue": to_float(shifts_df["total_revenue"].sum()) if "total_revenue" in shifts_df.columns else 0,
        "total_profit": to_float(shifts_df["profit"].sum()) if "profit" in shifts_df.columns else 0,
        "total_transactions": int(shifts_df["transactions"].sum()) if "transactions" in shifts_df.columns else 0,
    }


def get_stock_alerts(branch_id=None):
    branch_id = _resolve_branch(branch_id)
    products_df = _load_scoped(load_products, branch_id)

    if products_df is None or products_df.empty:
        return {"critical": [], "warning": []}

    critical = products_df[products_df["stock"] == 0].to_dict('records')
    warning = products_df[
        (products_df["stock"] > 0)
        & (products_df["stock"] <= products_df["reorder_level"])
    ].to_dict('records')

    return {"critical": critical, "warning": warning}


def get_pending_purchases(branch_id=None):
    branch_id = _resolve_branch(branch_id)
    purchases_df = _load_scoped(load_purchases, branch_id)

    if purchases_df is None or purchases_df.empty:
        return []

    pending = purchases_df[purchases_df["status"] == "PENDING"]
    pending_pos = pending.groupby("po_number").agg({
        "supplier": "first",
        "total_cost": "sum",
        "product_name": "count",
    }).reset_index()

    return pending_pos.to_dict('records')


# ==============================
# DASHBOARD
# ==============================
def mobile_dashboard(branch_id=None):
    st.markdown(get_mobile_css(), unsafe_allow_html=True)

    st.title("SmartGro Mobile")
    st.caption("Real-time business insights at your fingertips — branch-scoped")

    try:
        branches_df = load_branches()
    except Exception:
        branches_df = pd.DataFrame()

    if branch_id is None:
        branch_id, branch_label = _branch_scope_selector(branches_df)
    else:
        branch_label = _branch_label(branch_id)

    # Persistent badge so users always know the scope
    st.markdown(
        f'<div class="branch-badge">Viewing: {branch_label}</div>',
        unsafe_allow_html=True,
    )

    nav_options = ["Dashboard", "Alerts", "WhatsApp", "Reports", "Shifts"]
    nav_cols = st.columns(len(nav_options))
    if "mobile_tab" not in st.session_state:
        st.session_state.mobile_tab = "Dashboard"

    for idx, option in enumerate(nav_options):
        with nav_cols[idx]:
            if st.button(option, key=f"nav_{option}_{branch_id}",
                         use_container_width=True):
                st.session_state.mobile_tab = option

    st.markdown("---")

    # ==============================
    # DASHBOARD
    # ==============================
    if st.session_state.mobile_tab == "Dashboard":
        st.markdown("## Today's Overview")

        stats = get_todays_stats(branch_id=branch_id)
        weekly = get_weekly_stats(branch_id=branch_id)
        monthly = get_monthly_stats(branch_id=branch_id)
        shift_summary = get_shift_summary(branch_id=branch_id)

        active_shift = shift_summary.get("active_shift")
        if active_shift:
            st.info(
                f"Active Shift in {branch_label}: "
                f"{active_shift.get('shift_id', 'N/A')} — "
                f"{active_shift.get('cashier_name', 'Unknown')}"
            )
        else:
            st.warning(f"No active shift in {branch_label}")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-value">${stats['sales']:,.0f}</div>
                <div class="stat-label">Today's Sales — {branch_label}</div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-value">${stats['profit']:,.0f}</div>
                <div class="stat-label">Today's Profit — {branch_label}</div>
            </div>
            """, unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-value">{stats['transactions']}</div>
                <div class="stat-label">Transactions</div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-value">{stats['items_sold']}</div>
                <div class="stat-label">Items Sold</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("## Period Summary")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Weekly Sales", f"${weekly['sales']:,.0f}",
                      delta=f"${weekly['daily_average']:,.0f}/day")
        with col2:
            st.metric("Weekly Profit", f"${weekly['profit']:,.0f}")
        with col3:
            st.metric("Monthly Sales", f"${monthly['sales']:,.0f}")

        alerts = get_stock_alerts(branch_id=branch_id)
        if alerts["critical"] or alerts["warning"]:
            st.markdown(f"## Stock Alerts — {branch_label}")
            if alerts["critical"]:
                st.markdown(f"""
                <div class="alert-critical">
                    <strong>{len(alerts['critical'])} products OUT OF STOCK in {branch_label}</strong><br>
                    Immediate action required!
                </div>
                """, unsafe_allow_html=True)
            if alerts["warning"]:
                st.markdown(f"""
                <div class="alert-warning">
                    <strong>{len(alerts['warning'])} products low on stock in {branch_label}</strong><br>
                    Reorder soon to avoid stockouts.
                </div>
                """, unsafe_allow_html=True)

        if stats['top_product'] != "N/A":
            st.markdown(f"""
            <div class="alert-info">
                <strong>Top Selling Today in {branch_label}</strong><br>
                {stats['top_product']}
            </div>
            """, unsafe_allow_html=True)

        pending = get_pending_purchases(branch_id=branch_id)
        if pending:
            st.markdown(f"## Pending Approvals — {branch_label}")
            for po in pending[:3]:
                st.markdown(f"""
                <div class="stat-card">
                    <strong>PO: {po['po_number']}</strong><br>
                    Supplier: {po['supplier']}<br>
                    Value: ${po['total_cost']:,.2f}<br>
                    Items: {po['product_name']}
                </div>
                """, unsafe_allow_html=True)

    # ==============================
    # ALERTS
    # ==============================
    elif st.session_state.mobile_tab == "Alerts":
        st.markdown(f"## Real-time Alerts — {branch_label}")

        alerts = get_stock_alerts(branch_id=branch_id)

        if alerts["critical"]:
            st.markdown("### Critical Alerts")
            for product in alerts["critical"]:
                st.error(f"**{product['name']}** — OUT OF STOCK in {branch_label}. Reorder immediately.")

        if alerts["warning"]:
            st.markdown("### Warning Alerts")
            for product in alerts["warning"][:10]:
                st.warning(
                    f"**{product['name']}** — Only {product['stock']} units left "
                    f"(Reorder at {product['reorder_level']}) in {branch_label}"
                )

        if not alerts["critical"] and not alerts["warning"]:
            st.success(f"No active alerts in {branch_label}! All stock levels are healthy.")

        pending = get_pending_purchases(branch_id=branch_id)
        if pending:
            st.markdown("### Pending Approvals")
            for po in pending:
                with st.expander(f"PO: {po['po_number']} — {po['supplier']}"):
                    st.write(f"**Branch:** {branch_label}")
                    st.write(f"**Total Value:** ${po['total_cost']:,.2f}")
                    st.write(f"**Items:** {po['product_name']}")

                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("Approve", key=f"approve_{po['po_number']}_{branch_id}"):
                            st.success(f"PO {po['po_number']} approved for {branch_label}!")
                    with col2:
                        if st.button("Reject", key=f"reject_{po['po_number']}_{branch_id}"):
                            st.warning(f"PO {po['po_number']} rejected")

    # ==============================
    # WHATSAPP
    # ==============================
    elif st.session_state.mobile_tab == "WhatsApp":
        st.markdown("## WhatsApp Notifications")
        st.caption(f"Receive real-time alerts for {branch_label}")

        phone = st.text_input(
            "Your WhatsApp Number",
            placeholder="0782905853",
            help="Enter Zimbabwe phone number",
            key=f"wa_phone_{branch_id}",
        )

        if phone:
            valid, standardized, msg = validate_zimbabwe_phone(phone)
            if valid:
                st.success(f"Valid number: {standardized}")

                st.markdown("### Select Alerts to Receive")
                col1, col2 = st.columns(2)
                with col1:
                    stock_out_alerts = st.checkbox("Stock Out Alerts", value=True,
                                                   key=f"wa_so_{branch_id}")
                    low_stock_alerts = st.checkbox("Low Stock Alerts", value=True,
                                                   key=f"wa_ls_{branch_id}")
                with col2:
                    daily_summary = st.checkbox("Daily Sales Summary", value=True,
                                                key=f"wa_ds_{branch_id}")
                    shift_summary_alert = st.checkbox("Shift Summary", value=True,
                                                      key=f"wa_ss_{branch_id}")

                if st.button("Send Test WhatsApp Message", use_container_width=True,
                             key=f"wa_test_{branch_id}"):
                    test_message = (
                        f"*SmartGro ERP Test*\n\n*Branch: {branch_label}*\n\n"
                        "Your WhatsApp alerts are configured.\n\n"
                        "You will receive notifications for:\n"
                    )
                    if stock_out_alerts:
                        test_message += "- Stock out alerts\n"
                    if low_stock_alerts:
                        test_message += "- Low stock alerts\n"
                    if daily_summary:
                        test_message += "- Daily sales summary\n"
                    if shift_summary_alert:
                        test_message += "- Shift summaries\n"
                    test_message += f"\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

                    link = get_whatsapp_link(standardized, test_message)
                    if link:
                        st.markdown(
                            f'<a href="{link}" target="_blank"><button class="whatsapp-btn">'
                            f"Send Test Message</button></a>",
                            unsafe_allow_html=True,
                        )

                if st.button("Save Alert Settings", type="primary", use_container_width=True,
                             key=f"wa_save_{branch_id}"):
                    st.session_state.whatsapp_number = standardized
                    st.session_state.alert_prefs = {
                        "stock_out": stock_out_alerts,
                        "low_stock": low_stock_alerts,
                        "daily_summary": daily_summary,
                        "shift_summary": shift_summary_alert,
                    }
                    st.success("Alert settings saved!")
            else:
                st.error(msg)

        st.markdown("---")
        st.markdown("### Quick WhatsApp Actions")

        col1, col2 = st.columns(2)
        with col1:
            stats = get_todays_stats(branch_id=branch_id)
            summary_msg = get_whatsapp_alert_message("daily_summary", stats, branch_id=branch_id)
            if summary_msg:
                link = get_whatsapp_link(phone if phone else "0772123456", summary_msg)
                if link:
                    st.markdown(
                        f'<a href="{link}" target="_blank"><button class="whatsapp-btn">'
                        f"Send Daily Summary</button></a>",
                        unsafe_allow_html=True,
                    )

        with col2:
            alerts = get_stock_alerts(branch_id=branch_id)
            if alerts["critical"]:
                stock_msg = get_whatsapp_alert_message(
                    "stock_out", {"products": alerts["critical"]}, branch_id=branch_id
                )
                if stock_msg:
                    link = get_whatsapp_link(phone if phone else "0772123456", stock_msg)
                    if link:
                        st.markdown(
                            f'<a href="{link}" target="_blank"><button class="whatsapp-btn">'
                            f"Send Stock Alert</button></a>",
                            unsafe_allow_html=True,
                        )

    # ==============================
    # REPORTS
    # ==============================
    elif st.session_state.mobile_tab == "Reports":
        st.markdown(f"## Mobile Reports — {branch_label}")

        report_type = st.selectbox(
            "Select Report",
            ["Today's Sales", "Weekly Sales", "Monthly Sales", "Low Stock Report", "Pending Orders"],
            key=f"report_type_{branch_id}",
        )

        if report_type == "Today's Sales":
            stats = get_todays_stats(branch_id=branch_id)
            st.markdown(f"""
            ### Sales Summary — {branch_label}
            | Metric | Value |
            |--------|-------|
            | Total Sales | ${stats['sales']:,.2f} |
            | Total Profit | ${stats['profit']:,.2f} |
            | Transactions | {stats['transactions']} |
            | Items Sold | {stats['items_sold']} |
            | Avg Transaction | ${stats['avg_transaction']:.2f} |
            | Top Product | {stats['top_product']} |
            | Cash Sales | ${stats['cash_sales']:,.2f} |
            | Credit Sales | ${stats['credit_sales']:,.2f} |
            | Shift ID | {stats['shift_id']} |
            """)

            share_msg = (
                f"*Daily Sales Report*\n\n*Branch: {branch_label}*\n\n"
                f"Date: {datetime.now().strftime('%Y-%m-%d')}\n"
                f"Sales: ${stats['sales']:,.2f}\n"
                f"Profit: ${stats['profit']:,.2f}\n"
                f"Transactions: {stats['transactions']}\n"
                f"Top Product: {stats['top_product']}\n"
            )

            if st.button("Share via WhatsApp", use_container_width=True,
                         key=f"share_wa_{branch_id}"):
                phone = st.session_state.get("whatsapp_number", "0782905853")
                link = get_whatsapp_link(phone, share_msg)
                if link:
                    st.markdown(
                        f'<a href="{link}" target="_blank"><button class="whatsapp-btn">'
                        f"Share Report</button></a>",
                        unsafe_allow_html=True,
                    )

        elif report_type == "Weekly Sales":
            stats = get_weekly_stats(branch_id=branch_id)
            st.markdown(f"""
            ### Weekly Sales Summary — {branch_label}
            | Metric | Value |
            |--------|-------|
            | Total Sales | ${stats['sales']:,.2f} |
            | Total Profit | ${stats['profit']:,.2f} |
            | Transactions | {stats['transactions']} |
            | Daily Average | ${stats['daily_average']:.2f} |
            """)

        elif report_type == "Monthly Sales":
            stats = get_monthly_stats(branch_id=branch_id)
            st.markdown(f"""
            ### Monthly Sales Summary — {branch_label}
            | Metric | Value |
            |--------|-------|
            | Total Sales | ${stats['sales']:,.2f} |
            | Total Profit | ${stats['profit']:,.2f} |
            | Transactions | {stats['transactions']} |
            """)

        elif report_type == "Low Stock Report":
            alerts = get_stock_alerts(branch_id=branch_id)
            if alerts["warning"]:
                st.markdown(f"### Low Stock Items — {branch_label}")
                for product in alerts["warning"]:
                    st.write(
                        f"- **{product['name']}**: {product['stock']} units "
                        f"(Reorder at {product['reorder_level']})"
                    )
            else:
                st.success(f"No low stock items in {branch_label}")

        elif report_type == "Pending Orders":
            pending = get_pending_purchases(branch_id=branch_id)
            if pending:
                for po in pending:
                    st.markdown(f"""
                    **PO: {po['po_number']}**  
                    Branch: {branch_label}  
                    Supplier: {po['supplier']}  
                    Value: ${po['total_cost']:,.2f}  
                    Items: {po['product_name']}  
                    ---
                    """)
            else:
                st.info(f"No pending orders in {branch_label}")

    # ==============================
    # SHIFTS
    # ==============================
    elif st.session_state.mobile_tab == "Shifts":
        st.markdown(f"## Shift Management — {branch_label}")

        shift_summary = get_shift_summary(branch_id=branch_id)

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Shifts", shift_summary["total_shifts"])
        with col2:
            st.metric("Active Shifts", shift_summary.get("active_shifts", 0))
        with col3:
            st.metric("Closed Shifts", shift_summary.get("closed_shifts", 0))

        st.markdown("---")

        shifts_df = _load_scoped(load_shifts, branch_id)
        if shifts_df is not None and not shifts_df.empty:
            active_shifts = shifts_df[shifts_df["status"] == "OPEN"]
            if not active_shifts.empty:
                st.markdown("### Active Shifts")
                for _, shift in active_shifts.iterrows():
                    with st.expander(
                        f"Shift: {shift['shift_id']} — {shift.get('cashier_name', 'Unknown')}"
                    ):
                        st.write(f"**Branch:** {branch_label}")
                        st.write(f"**Cashier:** {shift.get('cashier_name', 'N/A')}")
                        st.write(f"**Started:** {shift.get('start_time', 'N/A')}")
                        st.write(f"**Opening Cash:** ${to_float(shift.get('opening_cash', 0)):,.2f}")
                        st.write(f"**Current Revenue:** ${to_float(shift.get('total_revenue', 0)):,.2f}")
                        st.write(f"**Transactions:** {int(shift.get('transactions', 0))}")

            closed_shifts = shifts_df[shifts_df["status"] == "CLOSED"]
            if not closed_shifts.empty:
                st.markdown("### Recent Closed Shifts")
                for _, shift in closed_shifts.head(10).iterrows():
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.write(f"**{shift.get('shift_id', 'N/A')}**")
                    with col2:
                        st.write(f"Cashier: {shift.get('cashier_name', 'N/A')}")
                    with col3:
                        st.write(f"Revenue: ${to_float(shift.get('total_revenue', 0)):,.2f}")
        else:
            st.info(f"No shifts recorded for {branch_label}")

    st.markdown("---")
    if st.button("Refresh Data", use_container_width=True, key=f"refresh_{branch_id}"):
        st.cache_data.clear()
        st.rerun()


# ==============================
# AUTO ALERTS (background hook — not called from this module)
# ==============================
def send_auto_whatsapp_alerts(branch_id=None):
    """
    Optional background hook. Call from a scheduler with an explicit branch_id.
    Sending alerts when branch_id is __ALL__ is refused — alerts must be per-branch.
    """
    branch_id = _resolve_branch(branch_id)
    if _is_all_branches(branch_id):
        return

    settings = st.session_state.get("alert_prefs", {})
    phone = st.session_state.get("whatsapp_number", "")
    if not phone or not settings:
        return

    alerts = get_stock_alerts(branch_id=branch_id)

    if settings.get("stock_out", False) and alerts["critical"]:
        msg = get_whatsapp_alert_message("stock_out", {"products": alerts["critical"]},
                                          branch_id=branch_id)
        if msg:
            print(f"[{branch_id}] Would send stock alert to {phone}")

    if settings.get("low_stock", False) and alerts["warning"]:
        msg = get_whatsapp_alert_message("low_stock", {"products": alerts["warning"]},
                                          branch_id=branch_id)
        if msg:
            print(f"[{branch_id}] Would send low stock alert to {phone}")

    if settings.get("daily_summary", False):
        stats = get_todays_stats(branch_id=branch_id)
        if stats["sales"] > 0:
            msg = get_whatsapp_alert_message("daily_summary", stats, branch_id=branch_id)
            if msg:
                print(f"[{branch_id}] Would send daily summary to {phone}")


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    mobile_dashboard()