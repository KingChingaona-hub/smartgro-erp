import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from pathlib import Path
from backend.core.db_adapter import (
    load_branches,
    load_sales,
    load_customers,
    load_expenses,
    to_float,
)
from backend.admin.branch_data_manager import get_branch_data_path
import os


# ==============================
# EXPENSE COLUMN NORMALIZATION
# ==============================
_EXPENSE_DATE_ALIASES = [
    "date", "expense_date", "date_recorded", "created_at", "recorded_at",
    "transaction_date", "timestamp", "date_created", "entry_date",
]
_EXPENSE_AMOUNT_ALIASES = [
    "amount", "total", "value", "cost", "total_amount", "expense_amount",
    "price", "sum", "total_cost",
]
_EXPENSE_BRANCH_ALIASES = [
    "branch_id", "branch", "branch_code",
]


def _find_first_column(df, aliases):
    """Return the first column name (case-insensitive) present in the aliases list."""
    if df is None or df.empty:
        return None
    lower_map = {str(c).lower().strip(): c for c in df.columns}
    for alias in aliases:
        if alias in lower_map:
            return lower_map[alias]
    for col_lower, col_orig in lower_map.items():
        for alias in aliases:
            if alias in col_lower:
                return col_orig
    return None


def _normalize_expenses_df(df, source_label="", branch_id=None):
    """
    Normalise an expenses DataFrame so it always has:
      - a datetime column named 'date'
      - a numeric column named 'amount'
    Optionally filters rows to the given branch_id if a branch column exists.
    Returns (normalized_df, source_label, diagnostics_dict)
    """
    diagnostics = {
        "source": source_label,
        "rows_total": 0,
        "rows_branch": 0,
        "date_col": None,
        "amount_col": None,
        "branch_col": None,
        "error": None,
    }

    if df is None or df.empty:
        return pd.DataFrame(), source_label, diagnostics

    df = df.copy()

    date_col = _find_first_column(df, _EXPENSE_DATE_ALIASES)
    amount_col = _find_first_column(df, _EXPENSE_AMOUNT_ALIASES)
    branch_col = _find_first_column(df, _EXPENSE_BRANCH_ALIASES)

    diagnostics["date_col"] = date_col
    diagnostics["amount_col"] = amount_col
    diagnostics["branch_col"] = branch_col

    if date_col is None and amount_col is None:
        diagnostics["error"] = "No recognizable date or amount column."
        return pd.DataFrame(), source_label, diagnostics

    diagnostics["rows_total"] = len(df)

    # Coerce date
    if date_col is not None:
        df["date"] = pd.to_datetime(df[date_col], errors="coerce")
    else:
        df["date"] = pd.NaT

    # Coerce amount
    if amount_col is not None:
        df["amount"] = (
            df[amount_col]
            .astype(str)
            .str.replace(",", "", regex=False)
            .str.replace("$", "", regex=False)
            .str.replace(" ", "", regex=False)
        )
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
    else:
        df["amount"] = 0

    # Optional branch filter
    if branch_id is not None and branch_col is not None:
        try:
            df = df[
                df[branch_col].astype(str).str.strip() == str(branch_id).strip()
            ].copy()
        except Exception:
            pass

    diagnostics["rows_branch"] = len(df)
    return df, source_label, diagnostics


# ==============================
# MULTI-SOURCE EXPENSE LOADER
# ==============================
def _try_db_expenses_with_branch(branch_id):
    """Try load_expenses(branch_id) from db_adapter."""
    try:
        df = load_expenses(branch_id)
        if df is not None and not df.empty:
            return df, f"db load_expenses({branch_id})"
    except Exception as e:
        print(f"[branch_perf] load_expenses({branch_id}) failed: {e}")
    return None, None


def _try_db_expenses_global():
    """Try load_expenses() without a branch filter — we'll filter rows later."""
    try:
        df = load_expenses()
        if df is not None and not df.empty:
            return df, "db load_expenses() (global, will filter by branch col)"
    except Exception as e:
        print(f"[branch_perf] load_expenses() failed: {e}")
    return None, None


def _try_csv(path: Path, label_prefix="csv"):
    try:
        if path.exists() and path.stat().st_size > 0:
            df = pd.read_csv(path)
            if not df.empty:
                return df, f"{label_prefix} ({path})"
    except Exception as e:
        print(f"[branch_perf] CSV read failed at {path}: {e}")
    return None, None


def _candidate_expense_paths(branch_id):
    """Build a list of likely CSV paths for this branch's expenses."""
    candidates = []

    # 1) Whatever branch_data_manager gives us
    try:
        candidates.append(get_branch_data_path(branch_id, "expenses.csv"))
    except Exception:
        pass

    # 2) Common layouts
    candidates.extend([
        Path("data") / str(branch_id) / "expenses.csv",
        Path("data") / "branches" / str(branch_id) / "expenses.csv",
        Path("data") / "branch_data" / str(branch_id) / "expenses.csv",
        Path("exports") / str(branch_id) / "expenses.csv",
    ])

    # 3) Glob for any expenses*.csv inside branch folders
    for base in [
        Path("data"),
        Path("data") / "branches",
        Path("data") / "branch_data",
        Path("exports"),
    ]:
        try:
            if base.exists():
                for p in base.glob(f"**/{branch_id}/expenses*.csv"):
                    candidates.append(p)
                for p in base.glob(f"**/{branch_id}*expenses*.csv"):
                    candidates.append(p)
        except Exception:
            continue

    return candidates


def _global_expense_paths():
    """Global expense CSVs that may contain a branch_id column."""
    return [
        Path("data") / "expenses.csv",
        Path("expenses.csv"),
        Path("exports") / "expenses.csv",
        Path("data") / "expenses" / "expenses.csv",
    ]


def load_branch_expenses_auto(branch_id):
    """
    Try every plausible source for this branch's expenses.
    Returns (normalized_df, source_label, diagnostics_dict).
    """
    # 1) Branch-scoped DB
    df, src = _try_db_expenses_with_branch(branch_id)
    if df is not None:
        norm, label, diag = _normalize_expenses_df(df, src, branch_id=branch_id)
        if not norm.empty:
            return norm, label, diag

    # 2) Branch-scoped CSV candidates
    for path in _candidate_expense_paths(branch_id):
        df, src = _try_csv(path, "csv (branch)")
        if df is not None:
            norm, label, diag = _normalize_expenses_df(df, src, branch_id=branch_id)
            if not norm.empty:
                return norm, label, diag

    # 3) Global DB (filter rows by branch col if present)
    df, src = _try_db_expenses_global()
    if df is not None:
        norm, label, diag = _normalize_expenses_df(df, src, branch_id=branch_id)
        if not norm.empty:
            return norm, label, diag

    # 4) Global CSVs (filter rows by branch col if present)
    for path in _global_expense_paths():
        df, src = _try_csv(path, "csv (global)")
        if df is not None:
            norm, label, diag = _normalize_expenses_df(df, src, branch_id=branch_id)
            if not norm.empty:
                return norm, label, diag

    # Nothing found — return empty with a diagnostic
    return pd.DataFrame(), "not found", {
        "source": "not found",
        "rows_total": 0,
        "rows_branch": 0,
        "date_col": None,
        "amount_col": None,
        "branch_col": None,
        "error": "No expense source returned data for this branch.",
    }


@st.cache_data(ttl=120, show_spinner=False)
def _cached_load_branch_expenses(branch_id: str, _refresh_token: int = 0):
    """
    Cached wrapper around the auto loader. We pass a refresh token so calling
    with a higher value busts the cache.
    """
    return load_branch_expenses_auto(branch_id)


def load_branch_expenses(branch_id):
    """
    Branch-scoped expense loader used by the rest of the page.
    Reads from the cached auto loader. Refresh button in the dashboard clears
    the cache and re-runs.
    """
    try:
        df, _src, _diag = _cached_load_branch_expenses(str(branch_id))
    except Exception:
        df, _src, _diag = load_branch_expenses_auto(branch_id)

    return df if df is not None else pd.DataFrame()


def get_branch_expense_diagnostics(branch_id):
    """Return (source, diagnostics) for the last load attempt for this branch."""
    try:
        _df, src, diag = _cached_load_branch_expenses(str(branch_id))
        return src, diag
    except Exception:
        _df, src, diag = load_branch_expenses_auto(branch_id)
        return src, diag


# ==============================
# LOAD BRANCH DATA (unchanged except expenses)
# ==============================
def load_branch_sales(branch_id):
    """Load sales data for a specific branch"""
    try:
        sales_df = load_sales(branch_id)
        if not sales_df.empty:
            if "date" in sales_df.columns:
                sales_df["date"] = pd.to_datetime(sales_df["date"], errors="coerce")
            if "total" not in sales_df.columns and "final_total" in sales_df.columns:
                sales_df["total"] = sales_df["final_total"]
            if "profit" not in sales_df.columns:
                sales_df["profit"] = 0
            if "items" not in sales_df.columns:
                sales_df["items"] = 1
            return sales_df
    except:
        pass

    file_path = get_branch_data_path(branch_id, "sales.csv")
    if not file_path.exists():
        return pd.DataFrame(columns=["date", "total", "profit", "items"])

    df = pd.read_csv(file_path)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    if "total" in df.columns:
        df["total"] = pd.to_numeric(df["total"], errors="coerce").fillna(0)
    if "profit" in df.columns:
        df["profit"] = pd.to_numeric(df["profit"], errors="coerce").fillna(0)
    if "items" in df.columns:
        df["items"] = pd.to_numeric(df["items"], errors="coerce").fillna(0)

    return df


def load_branch_customers(branch_id):
    """Load customers data for a specific branch"""
    try:
        customers_df = load_customers(branch_id)
        if not customers_df.empty:
            return customers_df
    except:
        pass

    file_path = get_branch_data_path(branch_id, "customers.csv")
    if not file_path.exists():
        return pd.DataFrame(columns=["customer_id", "customer_name", "total_spent"])

    df = pd.read_csv(file_path)
    if "total_spent" in df.columns:
        df["total_spent"] = pd.to_numeric(df["total_spent"], errors="coerce").fillna(0)

    return df


# ==============================
# BRANCH PERFORMANCE SUMMARY
# ==============================
def get_branch_summary(branch_id, period="daily", date=None):
    """Get branch performance summary for a specific period"""

    sales_df = load_branch_sales(branch_id)
    customers_df = load_branch_customers(branch_id)

    # NEW: multi-source expense loader (auto-discovery)
    expenses_df = load_branch_expenses(branch_id)

    if sales_df.empty:
        return {
            "branch_id": branch_id,
            "period": "N/A",
            "start_date": None,
            "end_date": None,
            "total_sales": 0,
            "total_profit": 0,
            "total_expenses": 0,
            "net_profit": 0,
            "total_customers": 0,
            "total_transactions": 0,
            "total_items": 0,
            "avg_transaction": 0,
            "profit_margin": 0,
            "daily_data": pd.DataFrame()
        }

    if date is None:
        date = datetime.now()

    if period == "daily":
        start_date = date.replace(hour=0, minute=0, second=0)
        end_date = date.replace(hour=23, minute=59, second=59)
        period_name = date.strftime("%Y-%m-%d")
    elif period == "weekly":
        start_date = date - timedelta(days=date.weekday())
        start_date = start_date.replace(hour=0, minute=0, second=0)
        end_date = start_date + timedelta(days=6)
        end_date = end_date.replace(hour=23, minute=59, second=59)
        period_name = f"Week {date.isocalendar()[1]}, {date.year}"
    elif period == "monthly":
        start_date = date.replace(day=1, hour=0, minute=0, second=0)
        if date.month == 12:
            end_date = date.replace(year=date.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_date = date.replace(month=date.month + 1, day=1) - timedelta(days=1)
        end_date = end_date.replace(hour=23, minute=59, second=59)
        period_name = date.strftime("%B %Y")
    elif period == "quarterly":
        quarter = (date.month - 1) // 3 + 1
        start_month = (quarter - 1) * 3 + 1
        start_date = date.replace(month=start_month, day=1, hour=0, minute=0, second=0)
        if start_month + 2 > 12:
            end_date = date.replace(year=date.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_date = date.replace(month=start_month + 2, day=1) + timedelta(days=31)
            end_date = end_date.replace(day=1) - timedelta(days=1)
        end_date = end_date.replace(hour=23, minute=59, second=59)
        period_name = f"Q{quarter} {date.year}"
    else:  # yearly
        start_date = date.replace(month=1, day=1, hour=0, minute=0, second=0)
        end_date = date.replace(month=12, day=31, hour=23, minute=59, second=59)
        period_name = str(date.year)

    # Filter sales by date range
    if "date" in sales_df.columns:
        filtered_sales = sales_df[(sales_df["date"] >= start_date) & (sales_df["date"] <= end_date)]
    else:
        filtered_sales = sales_df

    total_sales = to_float(filtered_sales["total"].sum()) if "total" in filtered_sales.columns else 0
    total_profit = to_float(filtered_sales["profit"].sum()) if "profit" in filtered_sales.columns else 0
    total_transactions = len(filtered_sales)
    total_items = to_float(filtered_sales["items"].sum()) if "items" in filtered_sales.columns else 0

    # Filter expenses by date range
    if not expenses_df.empty and "date" in expenses_df.columns:
        expenses_df = expenses_df.copy()
        expenses_df["date"] = pd.to_datetime(expenses_df["date"], errors="coerce")
        filtered_expenses = expenses_df[(expenses_df["date"] >= start_date) & (expenses_df["date"] <= end_date)]
        total_expenses = to_float(filtered_expenses["amount"].sum()) if "amount" in filtered_expenses.columns else 0
    else:
        total_expenses = 0

    net_profit = total_profit - total_expenses

    total_customers = len(customers_df) if not customers_df.empty else 0

    avg_transaction = total_sales / total_transactions if total_transactions > 0 else 0
    profit_margin = (total_profit / total_sales * 100) if total_sales > 0 else 0

    return {
        "branch_id": branch_id,
        "period": period_name,
        "start_date": start_date,
        "end_date": end_date,
        "total_sales": total_sales,
        "total_profit": total_profit,
        "total_expenses": total_expenses,
        "net_profit": net_profit,
        "total_customers": total_customers,
        "total_transactions": total_transactions,
        "total_items": total_items,
        "avg_transaction": avg_transaction,
        "profit_margin": profit_margin,
        "daily_data": filtered_sales if not filtered_sales.empty else pd.DataFrame()
    }


def get_all_branches_summary(period="monthly", selected_date=None):
    """Get performance summary for all branches"""

    branches_df = load_branches()
    summaries = []

    if selected_date is None:
        selected_date = datetime.now()

    for _, branch in branches_df.iterrows():
        branch_id = branch["branch_id"]
        branch_name = branch["branch_name"]

        summary = get_branch_summary(branch_id, period, selected_date)
        summary["branch_name"] = branch_name
        summary["location"] = branch.get("location", "")
        summaries.append(summary)

    return pd.DataFrame(summaries)


# ==============================
# BRANCH PERFORMANCE PAGE
# ==============================
def branch_performance_page():
    """Branch Performance Dashboard"""

    st.title("Branch Performance Dashboard")
    st.caption("Compare performance across all branches with detailed analytics")

    # ==============================
    # PERIOD SELECTOR
    # ==============================
    col1, col2, col3, col4 = st.columns([2, 2, 2, 1])

    with col1:
        period = st.selectbox(
            "Select Period",
            ["daily", "weekly", "monthly", "quarterly", "yearly"],
            format_func=lambda x: x.capitalize(),
            key="period_select"
        )

    with col2:
        if period == "daily":
            selected_date = st.date_input("Select Date", value=datetime.now().date(), key="date_select")
        elif period == "weekly":
            selected_date = st.date_input("Select Week", value=datetime.now().date(), key="week_select")
        elif period == "monthly":
            selected_date = st.date_input("Select Month", value=datetime.now().date(), key="month_select")
        elif period == "quarterly":
            selected_date = st.date_input("Select Quarter", value=datetime.now().date(), key="quarter_select")
        else:
            selected_date = st.date_input("Select Year", value=datetime.now().date(), key="year_select")

    with col3:
        view_type = st.selectbox(
            "View Type",
            ["Summary Table", "Comparison Chart", "Detailed Analytics"],
            key="view_type"
        )

    with col4:
        st.markdown("<br>", unsafe_allow_html=True)
        refresh_expenses = st.button("🔄 Refresh Expenses", use_container_width=True)

    if refresh_expenses:
        try:
            _cached_load_branch_expenses.clear()
            st.cache_data.clear()
        except Exception:
            pass

    selected_datetime = datetime.combine(selected_date, datetime.min.time())

    # ==============================
    # GET DATA
    # ==============================
    branches_df = load_branches()

    if branches_df.empty:
        st.warning("No branches found. Please add branches first.")
        return

    summary_df = get_all_branches_summary(period, selected_datetime)

    if summary_df.empty:
        st.warning("No data available for selected period")
        return

    if "period" not in summary_df.columns:
        summary_df["period"] = period.capitalize()

    # ==============================
    # EXPENSE SOURCE DIAGNOSTICS
    # ==============================
    with st.expander("📂 Expense source diagnostics", expanded=False):
        st.caption(
            "Shows where expense data was pulled for each branch. "
            "Click the 🔄 Refresh Expenses button above to force a re-read."
        )
        diag_rows = []
        for _, b in branches_df.iterrows():
            bid = b["branch_id"]
            src, diag = get_branch_expense_diagnostics(bid)
            diag_rows.append({
                "Branch": b["branch_name"],
                "Source": src,
                "Total rows": diag.get("rows_total", 0),
                "Branch rows": diag.get("rows_branch", 0),
                "Date col": str(diag.get("date_col")),
                "Amount col": str(diag.get("amount_col")),
                "Branch col": str(diag.get("branch_col")),
                "Error": diag.get("error") or "",
            })
        if diag_rows:
            st.dataframe(pd.DataFrame(diag_rows), use_container_width=True, hide_index=True)

    # ==============================
    # DISPLAY SUMMARY TABLE
    # ==============================
    if view_type == "Summary Table":
        st.markdown(f"## {period.capitalize()} Performance Summary")

        period_display = summary_df.iloc[0]["period"] if not summary_df.empty and "period" in summary_df.columns else selected_date.strftime("%Y-%m-%d")
        st.caption(f"Period: {period_display}")

        display_df = summary_df.copy()
        display_df["total_sales"] = display_df["total_sales"].apply(lambda x: f"${x:,.2f}")
        display_df["total_profit"] = display_df["total_profit"].apply(lambda x: f"${x:,.2f}")
        display_df["total_expenses"] = display_df["total_expenses"].apply(lambda x: f"${x:,.2f}")
        display_df["net_profit"] = display_df["net_profit"].apply(lambda x: f"${x:,.2f}")
        display_df["avg_transaction"] = display_df["avg_transaction"].apply(lambda x: f"${x:.2f}")
        display_df["profit_margin"] = display_df["profit_margin"].apply(lambda x: f"{x:.1f}%")

        display_cols = ["branch_name", "location", "total_sales", "total_profit",
                        "total_expenses", "net_profit", "total_transactions",
                        "total_items", "avg_transaction", "profit_margin"]

        available_cols = [col for col in display_cols if col in display_df.columns]

        st.dataframe(
            display_df[available_cols],
            use_container_width=True,
            hide_index=True
        )

        st.markdown("---")
        st.markdown("### Overall Totals")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Sales (All Branches)", f"${summary_df['total_sales'].sum():,.2f}")
        with col2:
            st.metric("Total Profit", f"${summary_df['total_profit'].sum():,.2f}")
        with col3:
            st.metric("Total Expenses", f"${summary_df['total_expenses'].sum():,.2f}")
        with col4:
            st.metric("Net Profit", f"${summary_df['net_profit'].sum():,.2f}")

    # ==============================
    # DISPLAY COMPARISON CHART
    # ==============================
    elif view_type == "Comparison Chart":
        st.markdown(f"## {period.capitalize()} Performance Comparison")

        col1, col2 = st.columns(2)

        with col1:
            fig_sales = px.bar(
                summary_df,
                x="branch_name",
                y="total_sales",
                title="Sales by Branch",
                color="total_sales",
                color_continuous_scale="Greens",
                text="total_sales"
            )
            fig_sales.update_traces(texttemplate="$%{text:.0f}", textposition="outside")
            fig_sales.update_layout(height=400)
            st.plotly_chart(fig_sales, use_container_width=True)

        with col2:
            fig_profit = px.bar(
                summary_df,
                x="branch_name",
                y="total_profit",
                title="Profit by Branch",
                color="total_profit",
                color_continuous_scale="Blues",
                text="total_profit"
            )
            fig_profit.update_traces(texttemplate="$%{text:.0f}", textposition="outside")
            fig_profit.update_layout(height=400)
            st.plotly_chart(fig_profit, use_container_width=True)

        # Expenses by branch (new)
        fig_expenses = px.bar(
            summary_df,
            x="branch_name",
            y="total_expenses",
            title="Expenses by Branch",
            color="total_expenses",
            color_continuous_scale="Oranges",
            text="total_expenses"
        )
        fig_expenses.update_traces(texttemplate="$%{text:.0f}", textposition="outside")
        fig_expenses.update_layout(height=400)
        st.plotly_chart(fig_expenses, use_container_width=True)

        fig_margin = px.bar(
            summary_df,
            x="branch_name",
            y="profit_margin",
            title="Profit Margin by Branch (%)",
            color="profit_margin",
            color_continuous_scale="Reds",
            text="profit_margin"
        )
        fig_margin.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig_margin.update_layout(height=400)
        st.plotly_chart(fig_margin, use_container_width=True)

        fig_trans = px.bar(
            summary_df,
            x="branch_name",
            y="total_transactions",
            title="Number of Transactions by Branch",
            color="total_transactions",
            color_continuous_scale="Purples",
            text="total_transactions"
        )
        fig_trans.update_traces(texttemplate="%{text}", textposition="outside")
        fig_trans.update_layout(height=400)
        st.plotly_chart(fig_trans, use_container_width=True)

    # ==============================
    # DISPLAY DETAILED ANALYTICS
    # ==============================
    else:
        st.markdown(f"## Detailed {period.capitalize()} Analytics")

        selected_branch = st.selectbox(
            "Select Branch for Detailed Analysis",
            summary_df["branch_name"].tolist(),
            key="detail_branch"
        )

        if selected_branch:
            branch_data = summary_df[summary_df["branch_name"] == selected_branch].iloc[0]
            branch_id = branch_data["branch_id"]

            detail_data = get_branch_summary(branch_id, period, selected_datetime)
            daily_df = detail_data["daily_data"]

            # Show expenses metric for this branch in the header
            st.markdown(f"### {selected_branch} — Expenses: ${detail_data['total_expenses']:,.2f}")

            src, diag = get_branch_expense_diagnostics(branch_id)
            st.caption(
                f"Expense source: **{src}** · "
                f"rows loaded: {diag.get('rows_total', 0)} · "
                f"rows for this branch: {diag.get('rows_branch', 0)} · "
                f"date col: {diag.get('date_col')} · "
                f"amount col: {diag.get('amount_col')}"
            )

            if not daily_df.empty:
                st.markdown(f"### {selected_branch} - {period.capitalize()} Sales Trend")

                if "date" in daily_df.columns:
                    daily_trend = daily_df.groupby(daily_df["date"].dt.date)["total"].sum().reset_index()
                    daily_trend.columns = ["Date", "Sales"]

                    fig_trend = px.line(
                        daily_trend,
                        x="Date",
                        y="Sales",
                        title=f"Sales Trend - {selected_branch}",
                        markers=True,
                        line_shape="spline"
                    )
                    fig_trend.update_layout(height=400)
                    st.plotly_chart(fig_trend, use_container_width=True)

                st.markdown(f"### Top Products - {selected_branch}")

                if "name" in daily_df.columns and "items" in daily_df.columns:
                    top_products = daily_df.groupby("name")["items"].sum().nlargest(10).reset_index()
                    if not top_products.empty:
                        fig_products = px.bar(
                            top_products,
                            x="items",
                            y="name",
                            orientation="h",
                            title="Top Selling Products",
                            color="items",
                            color_continuous_scale="Orange",
                            text="items"
                        )
                        fig_products.update_layout(height=400)
                        st.plotly_chart(fig_products, use_container_width=True)
                    else:
                        st.info("No product data available for this period")
                else:
                    st.info("Product data not available")

                if "payment_method" in daily_df.columns:
                    st.markdown(f"### Payment Methods - {selected_branch}")
                    payment_dist = daily_df["payment_method"].value_counts().reset_index()
                    payment_dist.columns = ["Method", "Count"]

                    fig_payment = px.pie(
                        payment_dist,
                        values="Count",
                        names="Method",
                        title="Payment Distribution",
                        hole=0.3
                    )
                    st.plotly_chart(fig_payment, use_container_width=True)
            else:
                st.info(f"No sales data for {selected_branch} in the selected period")

    # ==============================
    # EXPORT OPTIONS
    # ==============================
    st.markdown("---")
    st.subheader("Export Data")

    col1, col2 = st.columns(2)

    with col1:
        csv = summary_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download Performance Report (CSV)",
            data=csv,
            file_name=f"branch_performance_{period}_{selected_datetime.strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )

    with col2:
        if st.button("Generate Detailed Report", use_container_width=True):
            period_display = summary_df.iloc[0]["period"] if not summary_df.empty and "period" in summary_df.columns else selected_datetime.strftime("%Y-%m-%d")

            report_text = f"""
            {'='*60}
            AZIEL INVESTMENTS - BRANCH PERFORMANCE REPORT
            {'='*60}

            Period: {period.capitalize()}
            Date: {selected_datetime.strftime('%Y-%m-%d')}
            Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

            {'-'*40}
            SUMMARY
            {'-'*40}

            """

            for _, row in summary_df.iterrows():
                report_text += f"""
            Branch: {row['branch_name']} ({row.get('location', 'N/A')})
            - Total Sales: ${row['total_sales']:,.2f}
            - Total Profit: ${row['total_profit']:,.2f}
            - Total Expenses: ${row['total_expenses']:,.2f}
            - Net Profit: ${row['net_profit']:,.2f}
            - Transactions: {int(row['total_transactions'])}
            - Profit Margin: {row['profit_margin']:.1f}%

            """

            report_text += f"""
            {'='*60}
            GRAND TOTALS
            {'='*60}
            Total Sales (All Branches): ${summary_df['total_sales'].sum():,.2f}
            Total Profit: ${summary_df['total_profit'].sum():,.2f}
            Total Expenses: ${summary_df['total_expenses'].sum():,.2f}
            Total Net Profit: ${summary_df['net_profit'].sum():,.2f}
            {'='*60}
            """

            st.download_button(
                label="Download Report (TXT)",
                data=report_text,
                file_name=f"branch_report_{period}_{selected_datetime.strftime('%Y%m%d')}.txt",
                mime="text/plain"
            )


if __name__ == "__main__":
    branch_performance_page()