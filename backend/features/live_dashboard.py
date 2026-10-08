# backend/features/live_dashboard.py
# Live Dashboard — branch-aware, auto-refreshing.
#
# Branch scoping:
#     branch_id = None          -> session branch
#     branch_id = "HO"/"NAT"/.. -> that single branch
#     branch_id = "__ALL__"     -> aggregate across all branches (owner only)

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
import re

from backend.core.db_adapter import (
    load_sales,
    load_products,
    load_purchases,
    load_branches,
)


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
            key="live_branch_scope",
            help="Owners may monitor any branch or all at once.",
        )
        if choice == "All Branches":
            return ALL_BRANCHES, "All Branches"
        m = re.search(r"\(([^)]+)\)\s*$", choice)
        code = m.group(1).strip() if m else choice
        return code, choice

    session_branch = _resolve_branch(None)
    label = _branch_label(session_branch)
    st.info(f"Live dashboard locked to your branch: **{label}**")
    return session_branch, label


# ==============================
# HELPERS
# ==============================
def find_column(df, possible_names, default=None):
    if df is None or df.empty:
        return default
    for name in possible_names:
        if name in df.columns:
            return name
    return default


def safe_float(value, default=0.0):
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value, default=0):
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# ==============================
# METRICS (scoped)
# ==============================
def get_default_metrics():
    today = datetime.now().date()
    return {
        "total_today": 0,
        "transactions_today": 0,
        "items_today": 0,
        "last_hour_amount": 0,
        "out_of_stock": 0,
        "low_stock": 0,
        "pending_purchases": 0,
        "current_time": datetime.now().strftime("%H:%M:%S"),
        "current_date": today.strftime("%Y-%m-%d"),
        "total_all_time": 0,
        "total_products": 0,
    }


def get_live_metrics(branch_id=None):
    branch_id = _resolve_branch(branch_id)

    try:
        sales_df = _load_scoped(load_sales, branch_id)
        products_df = _load_scoped(load_products, branch_id)
        purchases_df = _load_scoped(load_purchases, branch_id)
    except Exception as e:
        print(f"[live_dashboard] load error: {e}")
        return get_default_metrics()

    today = datetime.now().date()
    today_str = today.strftime("%Y-%m-%d")

    metrics = get_default_metrics()
    metrics["current_date"] = today_str

    # ---- Sales ----
    if sales_df is not None and not sales_df.empty:
        try:
            date_col = find_column(sales_df, ["sale_date", "date", "transaction_date", "created_at"])
            if date_col:
                sales_df = sales_df.copy()
                sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
                sales_df = sales_df.dropna(subset=[date_col])

                if not sales_df.empty:
                    total_col = find_column(sales_df, ["final_total", "total", "amount", "sale_amount"])
                    items_col = find_column(sales_df, ["items", "quantity", "qty", "item_count"])
                    receipt_col = find_column(sales_df, ["receipt_no", "receipt", "transaction_id", "order_id"])

                    today_sales = sales_df[sales_df[date_col].dt.date == today]

                    if total_col:
                        if receipt_col and not today_sales.empty:
                            receipt_totals = today_sales.groupby(receipt_col)[total_col].first()
                            metrics["total_today"] = safe_float(receipt_totals.sum())
                        else:
                            metrics["total_today"] = safe_float(today_sales[total_col].sum())

                    if receipt_col:
                        metrics["transactions_today"] = (
                            today_sales[receipt_col].nunique() if not today_sales.empty else 0
                        )
                    else:
                        metrics["transactions_today"] = len(today_sales)

                    if items_col:
                        metrics["items_today"] = (
                            safe_int(today_sales[items_col].sum()) if not today_sales.empty else 0
                        )

                    if total_col and receipt_col:
                        all_time_totals = sales_df.groupby(receipt_col)[total_col].first()
                        metrics["total_all_time"] = safe_float(all_time_totals.sum())
                    elif total_col:
                        metrics["total_all_time"] = safe_float(sales_df[total_col].sum())

                    one_hour_ago = datetime.now() - timedelta(hours=1)
                    last_hour_sales = sales_df[sales_df[date_col] >= one_hour_ago]

                    if total_col and receipt_col and not last_hour_sales.empty:
                        lh_totals = last_hour_sales.groupby(receipt_col)[total_col].first()
                        metrics["last_hour_amount"] = safe_float(lh_totals.sum())
                    elif total_col and not last_hour_sales.empty:
                        metrics["last_hour_amount"] = safe_float(last_hour_sales[total_col].sum())
        except Exception as e:
            print(f"[live_dashboard] sales processing error: {e}")

    # ---- Products ----
    if products_df is not None and not products_df.empty:
        try:
            metrics["total_products"] = len(products_df)
            stock_col = find_column(products_df, ["stock", "quantity", "inventory", "current_stock"])
            reorder_col = find_column(products_df, ["reorder_level", "min_stock", "threshold", "reorder_point"])

            if stock_col:
                products_df = products_df.copy()
                products_df[stock_col] = pd.to_numeric(products_df[stock_col], errors="coerce").fillna(0)
                metrics["out_of_stock"] = len(products_df[products_df[stock_col] == 0])

                if reorder_col:
                    products_df[reorder_col] = pd.to_numeric(
                        products_df[reorder_col], errors="coerce"
                    ).fillna(0)
                    metrics["low_stock"] = len(
                        products_df[
                            (products_df[stock_col] > 0)
                            & (products_df[stock_col] <= products_df[reorder_col])
                        ]
                    )
        except Exception as e:
            print(f"[live_dashboard] products processing error: {e}")

    # ---- Purchases ----
    if purchases_df is not None and not purchases_df.empty and "status" in purchases_df.columns:
        try:
            metrics["pending_purchases"] = len(
                purchases_df[
                    purchases_df["status"].str.upper().isin(
                        ["PENDING", "ORDERED", "PENDING APPROVAL"]
                    )
                ]
            )
        except Exception as e:
            print(f"[live_dashboard] purchases processing error: {e}")

    return metrics


def get_hourly_sales(branch_id=None):
    branch_id = _resolve_branch(branch_id)
    sales_df = _load_scoped(load_sales, branch_id)
    if sales_df is None or sales_df.empty:
        return pd.DataFrame()

    today = datetime.now().date()
    date_col = find_column(sales_df, ["sale_date", "date", "transaction_date", "created_at"])
    if not date_col:
        return pd.DataFrame()

    sales_df = sales_df.copy()
    sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
    sales_df = sales_df.dropna(subset=[date_col])
    if sales_df.empty:
        return pd.DataFrame()

    today_sales = sales_df[sales_df[date_col].dt.date == today]
    if today_sales.empty:
        return pd.DataFrame()

    total_col = find_column(sales_df, ["final_total", "total", "amount", "sale_amount"])
    if not total_col:
        return pd.DataFrame()

    receipt_col = find_column(sales_df, ["receipt_no", "receipt", "transaction_id", "order_id"])
    today_sales = today_sales.copy()
    today_sales["hour"] = today_sales[date_col].dt.hour

    if receipt_col:
        hourly_data = []
        for hour in range(24):
            hour_sales = today_sales[today_sales["hour"] == hour]
            if not hour_sales.empty:
                hour_totals = hour_sales.groupby(receipt_col)[total_col].first()
                hourly_data.append({"hour": hour, "total": safe_float(hour_totals.sum())})
            else:
                hourly_data.append({"hour": hour, "total": 0})
        return pd.DataFrame(hourly_data)

    hourly = today_sales.groupby("hour")[total_col].sum().reset_index()
    hourly.columns = ["hour", "total"]
    hourly = hourly.sort_values("hour")
    all_hours = pd.DataFrame({"hour": range(24)})
    return all_hours.merge(hourly, on="hour", how="left").fillna(0)


def get_top_products_live(branch_id=None):
    branch_id = _resolve_branch(branch_id)
    sales_df = _load_scoped(load_sales, branch_id)
    if sales_df is None or sales_df.empty:
        return pd.DataFrame()

    today = datetime.now().date()
    date_col = find_column(sales_df, ["sale_date", "date", "transaction_date", "created_at"])
    product_col = find_column(sales_df, ["name", "product_name", "Product", "item_name"])
    if not date_col or not product_col:
        return pd.DataFrame()

    items_col = find_column(sales_df, ["items", "quantity", "qty", "item_count"])
    use_count = False
    if not items_col:
        items_col = product_col
        use_count = True

    sales_df = sales_df.copy()
    sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
    sales_df = sales_df.dropna(subset=[date_col])
    if sales_df.empty:
        return pd.DataFrame()

    today_sales = sales_df[sales_df[date_col].dt.date == today]
    if today_sales.empty:
        return pd.DataFrame()

    if use_count:
        top = today_sales.groupby(product_col).size().nlargest(5).reset_index()
        top.columns = ["name", "items"]
    else:
        top = today_sales.groupby(product_col)[items_col].sum().nlargest(5).reset_index()
        top.columns = ["name", "items"]
    return top


def get_recent_transactions(branch_id=None):
    branch_id = _resolve_branch(branch_id)
    sales_df = _load_scoped(load_sales, branch_id)
    if sales_df is None or sales_df.empty:
        return pd.DataFrame()

    date_col = find_column(sales_df, ["sale_date", "date", "transaction_date", "created_at"])
    if not date_col:
        return pd.DataFrame()

    sales_df = sales_df.copy()
    sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
    sales_df = sales_df.dropna(subset=[date_col])
    if sales_df.empty:
        return pd.DataFrame()

    sales_df = sales_df.sort_values(date_col, ascending=False)
    receipt_col = find_column(sales_df, ["receipt_no", "receipt", "transaction_id", "order_id"])

    if receipt_col:
        recent = sales_df.drop_duplicates(subset=[receipt_col]).head(10)
    else:
        recent = sales_df.head(10)

    col_mapping = {
        "receipt_no": "Receipt No",
        "receipt": "Receipt No",
        "transaction_id": "Receipt No",
        "customer": "Customer",
        "customer_name": "Customer",
        "total": "Amount",
        "final_total": "Amount",
        "amount": "Amount",
        "payment_method": "Payment",
        "payment_type": "Payment",
        "product_name": "Product",
        "name": "Product",
    }

    display_cols = []
    used = set()
    for db_col, disp in col_mapping.items():
        if db_col in recent.columns and db_col not in used:
            display_cols.append((db_col, disp))
            used.add(db_col)
            if len(display_cols) >= 5:
                break

    if not display_cols:
        return pd.DataFrame()

    result = pd.DataFrame()
    for db_col, disp in display_cols:
        result[disp] = recent[db_col].head(5).values

    if "Amount" in result.columns:
        result["Amount"] = result["Amount"].apply(
            lambda x: f"${safe_float(x):.2f}" if pd.notna(x) else "$0.00"
        )
    return result.head(5)


def get_sales_ticker(branch_id=None):
    branch_id = _resolve_branch(branch_id)
    sales_df = _load_scoped(load_sales, branch_id)
    if sales_df is None or sales_df.empty:
        return []

    date_col = find_column(sales_df, ["sale_date", "date", "transaction_date", "created_at"])
    product_col = find_column(sales_df, ["name", "product_name", "Product", "item_name"])
    total_col = find_column(sales_df, ["final_total", "total", "amount", "sale_amount"])
    receipt_col = find_column(sales_df, ["receipt_no", "receipt", "transaction_id", "order_id"])

    if not (date_col and product_col and total_col):
        return []

    sales_df = sales_df.copy()
    sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
    sales_df = sales_df.dropna(subset=[date_col])
    if sales_df.empty:
        return []

    if receipt_col:
        recent = (
            sales_df.drop_duplicates(subset=[receipt_col])
            .sort_values(date_col, ascending=False)
            .head(15)
        )
    else:
        recent = sales_df.sort_values(date_col, ascending=False).head(15)

    ticker_items = []
    for _, sale in recent.iterrows():
        product = str(sale.get(product_col, "Product"))[:30]
        amount = safe_float(sale.get(total_col, 0))
        ticker_items.append(f"Product: {product} - ${amount:.2f}")
    return ticker_items


# ==============================
# DASHBOARD
# ==============================
def live_dashboard(branch_id=None):
    st.title("Live Command Center")
    st.caption("Real-time business metrics — auto-refreshes every 10 seconds")

    try:
        branches_df = load_branches()
    except Exception:
        branches_df = pd.DataFrame()

    if branch_id is None:
        branch_id, branch_label = _branch_scope_selector(branches_df)
    else:
        branch_label = _branch_label(branch_id)

    st.caption(f"Monitoring: **{branch_label}**")

    # ---- Auto-refresh (namespaced by branch) ----
    refresh_key = f"live_last_refresh_{branch_id}"
    rerun_key = f"live_is_rerunning_{branch_id}"

    if refresh_key not in st.session_state:
        st.session_state[refresh_key] = time.time()

    current_time = time.time()
    time_since = current_time - st.session_state[refresh_key]

    if time_since >= 10 and not st.session_state.get(rerun_key, False):
        st.session_state[refresh_key] = current_time
        st.session_state[rerun_key] = True
        st.rerun()

    if st.session_state.get(rerun_key, False):
        st.session_state[rerun_key] = False

    remaining = max(0, 10 - int(time_since))
    st.info(f"Auto-refreshing in {remaining} seconds…")

    # ---- Metrics ----
    metrics = get_live_metrics(branch_id=branch_id)

    st.markdown(f"## Live Metrics — {branch_label}")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            "Today's Sales",
            f"${metrics['total_today']:,.2f}",
            delta=f"+${metrics['last_hour_amount']:.0f} last hour",
        )
    with col2:
        st.metric("Transactions", f"{metrics['transactions_today']}")
    with col3:
        st.metric("Items Sold", f"{metrics['items_today']}")
    with col4:
        st.metric("Last Updated", metrics["current_time"], help=f"Date: {metrics['current_date']}")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("All-Time Sales", f"${metrics.get('total_all_time', 0):,.2f}")
    with col2:
        st.metric("Total Products", f"{metrics.get('total_products', 0)}")
    with col3:
        st.metric(
            "Out of Stock",
            f"{metrics['out_of_stock']}",
            delta="WARNING" if metrics['out_of_stock'] > 0 else "OK",
        )
    with col4:
        st.metric(
            "Low Stock",
            f"{metrics['low_stock']}",
            delta="WARNING" if metrics['low_stock'] > 0 else "OK",
        )

    st.markdown("---")

    # ---- Alerts ----
    col1, col2, col3 = st.columns(3)
    with col1:
        if metrics['out_of_stock'] > 0:
            st.error(f"{metrics['out_of_stock']} products OUT OF STOCK in {branch_label}!")
        else:
            st.success(f"No out of stock items in {branch_label}")
    with col2:
        if metrics['low_stock'] > 0:
            st.warning(f"{metrics['low_stock']} products low on stock in {branch_label}")
        else:
            st.success("Stock levels healthy")
    with col3:
        if metrics['pending_purchases'] > 0:
            st.info(f"{metrics['pending_purchases']} pending purchase orders in {branch_label}")
        else:
            st.success("No pending orders")

    st.markdown("---")

    # ---- Charts ----
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("## Top Products Today")
        top_products = get_top_products_live(branch_id=branch_id)
        if not top_products.empty:
            fig = px.bar(
                top_products, x="items", y="name", orientation="h",
                title=f"Best Sellers Today — {branch_label}",
                color="items", color_continuous_scale="Viridis", text="items",
            )
            fig.update_traces(texttemplate="%{text}", textposition="outside")
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info(f"No sales recorded today in {branch_label}")

    with col2:
        st.markdown("## Hourly Sales")
        hourly = get_hourly_sales(branch_id=branch_id)
        if not hourly.empty and hourly["total"].sum() > 0:
            fig = px.line(
                hourly, x="hour", y="total",
                title=f"Sales by Hour Today — {branch_label}",
                markers=True, line_shape="spline",
            )
            fig.update_layout(height=350, xaxis_title="Hour of Day", yaxis_title="Sales Amount ($)")
            fig.update_traces(fill="tozeroy", fillcolor="rgba(46, 204, 113, 0.2)")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info(f"No hourly data available for {branch_label}")

    st.markdown("---")

    st.markdown("## Recent Transactions")
    recent = get_recent_transactions(branch_id=branch_id)
    if not recent.empty:
        st.dataframe(recent, use_container_width=True, hide_index=True)
    else:
        st.info(f"No recent transactions in {branch_label}")

    st.markdown("---")

    # ---- Quick actions ----
    st.markdown("## Quick Actions")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("Go to POS", use_container_width=True, key=f"live_pos_{branch_id}"):
            st.session_state.current_page = "POS"
            st.rerun()
    with col2:
        if st.button("Check Stock", use_container_width=True, key=f"live_stock_{branch_id}"):
            st.session_state.current_page = "Stock Dashboard"
            st.rerun()
    with col3:
        if st.button("View Purchases", use_container_width=True, key=f"live_purch_{branch_id}"):
            st.session_state.current_page = "Purchases"
            st.rerun()
    with col4:
        if st.button("Refresh Now", use_container_width=True, key=f"live_refresh_{branch_id}"):
            st.cache_data.clear()
            st.session_state[refresh_key] = 0
            st.rerun()

    # ---- Ticker ----
    st.markdown("---")
    st.markdown("## Live Sales Ticker")
    ticker_items = get_sales_ticker(branch_id=branch_id)
    if ticker_items:
        ticker_html = f"""
        <div style="background: linear-gradient(90deg, #1a1a2e, #16213e); padding: 15px; border-radius: 10px; overflow: hidden; white-space: nowrap; position: relative;">
            <div style="display: inline-block; animation: scrollTicker 20s linear infinite; white-space: nowrap;">
                {'  &nbsp;&nbsp;  &nbsp;&nbsp; '.join(ticker_items)}
            </div>
        </div>
        <style>
            @keyframes scrollTicker {{
                0% {{ transform: translateX(100%); }}
                100% {{ transform: translateX(-100%); }}
            }}
        </style>
        """
        st.markdown(ticker_html, unsafe_allow_html=True)
    else:
        st.info("No recent sales to display")

    # ---- Daily target gauge ----
    st.markdown("---")
    st.markdown("## Daily Sales Target")

    daily_target = 300
    if daily_target > 0:
        progress_percentage = min(100, (metrics['total_today'] / daily_target) * 100)
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=metrics['total_today'],
            title={"text": f"{branch_label} — Target: ${daily_target:,.2f}"},
            delta={"reference": daily_target},
            gauge={
                "axis": {"range": [0, daily_target * 1.2]},
                "bar": {"color": "darkgreen" if progress_percentage >= 100 else "orange"},
                "steps": [
                    {"range": [0, daily_target * 0.5], "color": "lightgray"},
                    {"range": [daily_target * 0.5, daily_target], "color": "gray"},
                ],
                "threshold": {"line": {"color": "red", "width": 4}, "thickness": 0.75, "value": daily_target},
            },
        ))
        fig_gauge.update_layout(height=250)
        st.plotly_chart(fig_gauge, use_container_width=True)
        st.progress(min(1.0, progress_percentage / 100))
        st.caption(f"Progress: {min(100, progress_percentage):.1f}% of daily target")
    else:
        st.info("Daily target not configured")

    st.caption(
        "This dashboard auto-refreshes every 10 seconds. Data is scoped to "
        f"**{branch_label}**."
    )


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    live_dashboard()