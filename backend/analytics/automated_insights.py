# backend/analytics/automated_insights.py
"""
Automated Insights Digest
Daily/weekly AI-generated business summaries sent via email
Customers sourced from sales table as first priority

DEBT SOURCE: Floating Financials (floating_credits + floating_changes),
NOT the legacy debtors table.

INCOME: Sourced from its own recorded income table/CSV — NOT from sales revenue.
NET PROFIT: Income − Expenses, computed over the selected reporting period.
"""

import streamlit as st
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, date as date_type
import json
from pathlib import Path
import plotly.graph_objects as go
import plotly.utils
import json as json_lib
import warnings
warnings.filterwarnings('ignore')

from backend.core.db_adapter import (
    load_sales,
    load_products,
    load_customers,
    load_expenses,
    load_debtors,       # kept for backwards compatibility (not used for debt)
    load_purchases,
    to_float
)
from backend.integrations.email_reports import get_email_config, send_email
from backend.modules.expenses import load_expenses as load_expenses_direct

# ---- Debt comes from floating financials ----
from backend.core.floating_financials import (
    get_credit_summary,
    get_credit_records,
    get_bad_debt_credits,
    get_overdue_credits,
    get_change_summary,
    get_overdue_changes,
    get_written_off_changes,
)


# ==============================
# OPTIONAL INCOME LOADERS
# ==============================
# Try to import a dedicated income loader from the project. It's optional
# so this file still works if the income module hasn't been created yet.
_load_income_from_db = None
try:
    from backend.core.db_adapter import load_income as _load_income_from_db  # type: ignore
except Exception:
    try:
        from backend.modules.income import load_income as _load_income_from_db  # type: ignore
    except Exception:
        _load_income_from_db = None


# ==============================
# FILE PATHS
# ==============================
DATA_DIR = Path("data")
INSIGHTS_FILE = DATA_DIR / "insights_settings.json"
INSIGHTS_HISTORY_FILE = DATA_DIR / "insights_history.csv"
INCOME_FILE = DATA_DIR / "income.csv"


# ==============================
# GENERIC HELPERS
# ==============================

def safe_float(value, default=0.0):
    """Safely convert value to float"""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def get_date_column(df):
    """Find date column in dataframe"""
    if df is None or df.empty:
        return None
    for col in ["date", "sale_date", "transaction_date", "created_at"]:
        if col in df.columns:
            return col
    return None


def get_amount_column(df):
    """Find amount column"""
    if df is None or df.empty:
        return None
    for col in ["final_total", "total", "amount", "spent"]:
        if col in df.columns:
            return col
    return None


def get_receipt_column(df):
    """Find receipt number column"""
    if df is None or df.empty:
        return None
    for col in ["receipt_no", "receipt", "transaction_id"]:
        if col in df.columns:
            return col
    return None


def get_unique_id_column(df):
    """Find a unique identifier column"""
    if df is None or df.empty:
        return None
    for col in ["id", "expense_id", "income_id", "receipt_no", "transaction_id", "uuid"]:
        if col in df.columns:
            return col
    return None


def get_customer_column(df):
    """Find customer name column"""
    if df is None or df.empty:
        return None
    for col in ["customer_name", "customer", "Customer", "client", "buyer"]:
        if col in df.columns:
            return col
    return None


def deduplicate_dataframe(df, subset_cols=None):
    """Deduplicate a dataframe using the best available method."""
    if df is None or df.empty:
        return df

    df = df.copy()
    unique_col = get_unique_id_column(df)

    if unique_col:
        return df.drop_duplicates(subset=[unique_col])

    if subset_cols is None:
        subset_cols = []
        for col in ["date", "category", "amount", "description", "vendor", "source"]:
            if col in df.columns:
                subset_cols.append(col)

    if len(subset_cols) >= 2:
        return df.drop_duplicates(subset=subset_cols)

    return df


def get_customers_from_sales(sales_df):
    """Extract customers from sales data - PRIMARY SOURCE"""
    if sales_df is None or sales_df.empty:
        return pd.DataFrame()

    customer_col = get_customer_column(sales_df)
    if customer_col is None:
        return pd.DataFrame()

    customers = sales_df[customer_col].dropna().unique().tolist()
    customers = [
        str(c).strip()
        for c in customers
        if str(c).strip() and str(c).strip().lower() != "walk-in"
    ]

    if not customers:
        return pd.DataFrame()

    customer_data = []
    for name in customers:
        customer_sales = sales_df[
            sales_df[customer_col].astype(str).str.contains(name, case=False, na=False)
        ]

        phone = ""
        phone_col = None
        for col in ["customer_phone", "phone", "Phone"]:
            if col in sales_df.columns:
                phone_col = col
                break
        if phone_col and not customer_sales.empty:
            phone_rows = customer_sales[phone_col].dropna()
            if not phone_rows.empty:
                phone = str(phone_rows.iloc[0]).strip()

        total_spent = 0
        total_col = get_amount_column(sales_df)
        if total_col and not customer_sales.empty:
            total_spent = to_float(customer_sales[total_col].sum())

        date_col = get_date_column(sales_df)
        last_purchase = None
        if date_col and not customer_sales.empty:
            customer_sales[date_col] = pd.to_datetime(
                customer_sales[date_col], errors="coerce"
            )
            last_purchase = customer_sales[date_col].max()

        receipt_col = get_receipt_column(sales_df)
        total_orders = 0
        if receipt_col and not customer_sales.empty:
            total_orders = customer_sales[receipt_col].nunique()

        customer_data.append({
            "customer_name": name,
            "phone": phone,
            "total_spent": total_spent,
            "total_orders": total_orders,
            "last_purchase_date": last_purchase,
        })

    return pd.DataFrame(customer_data)


# ==============================
# INCOME LOADERS  (NEW)
# ==============================

DATE_ALIASES = [
    "date", "income_date", "date_recorded", "created_at", "recorded_at",
    "transaction_date", "timestamp", "date_created", "entry_date",
]
AMOUNT_ALIASES = [
    "amount", "total", "value", "cost", "total_amount", "income_amount",
    "received", "sum", "total_income",
]
CATEGORY_ALIASES = [
    "category", "type", "income_type", "income_category", "source",
    "description_type", "kind", "group",
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


def _normalize_income_df(df, source_label=""):
    """
    Normalize an income DataFrame so it always has:
      - a datetime column named 'date'
      - a numeric column named 'amount'
      - a 'category'/'source' column if available
    """
    diagnostics = {
        "source": source_label,
        "rows": 0,
        "date_col": None,
        "amount_col": None,
        "category_col": None,
        "error": None,
    }

    if df is None or df.empty:
        return pd.DataFrame(), source_label, diagnostics

    df = df.copy()

    date_col = _find_first_column(df, DATE_ALIASES)
    amount_col = _find_first_column(df, AMOUNT_ALIASES)
    category_col = _find_first_column(df, CATEGORY_ALIASES)

    diagnostics["date_col"] = date_col
    diagnostics["amount_col"] = amount_col
    diagnostics["category_col"] = category_col

    if date_col is None and amount_col is None:
        diagnostics["error"] = "No recognizable date or amount column."
        return pd.DataFrame(), source_label, diagnostics

    if date_col is not None:
        df["date"] = pd.to_datetime(df[date_col], errors="coerce")
    else:
        df["date"] = pd.NaT

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

    if category_col is not None:
        df["category"] = df[category_col].astype(str)
    else:
        df["category"] = "Uncategorized"

    diagnostics["rows"] = len(df)
    return df, source_label, diagnostics


def _try_load_income_from_db():
    """Try loading income from the database adapter / income module."""
    if _load_income_from_db is None:
        return None, None
    try:
        df = _load_income_from_db()
        if df is not None and not df.empty:
            return df, "database (load_income)"
    except Exception as e:
        print(f"[insights] load_income() failed: {e}")
    return None, None


def _try_load_income_from_csv(path: Path):
    """Try loading income from a specific CSV path."""
    try:
        if path.exists() and path.stat().st_size > 0:
            df = pd.read_csv(path)
            if not df.empty:
                return df, f"csv ({path})"
    except Exception as e:
        print(f"[insights] income CSV read failed at {path}: {e}")
    return None, None


def _discover_income_csvs():
    """Search common locations for any income*.csv file."""
    candidates = []
    search_dirs = [DATA_DIR, Path("."), Path("exports"), Path("backend"), Path("database")]
    for d in search_dirs:
        try:
            if d.exists():
                for p in d.glob("income*.csv"):
                    candidates.append(p)
        except Exception:
            continue
    return candidates


def load_income_auto():
    """
    Load income from the first source that returns non-empty data.
    Returns:
        (normalized_df, source_label, diagnostics_dict)
    """
    # 1) Database / income module first
    df, src = _try_load_income_from_db()
    if df is not None:
        normalized, label, diag = _normalize_income_df(df, src)
        if not normalized.empty:
            return normalized, label, diag

    # 2) Known CSVs
    known_paths = [
        INCOME_FILE,
        Path("income.csv"),
        Path("exports") / "income.csv",
        DATA_DIR / "income" / "income.csv",
    ]
    for p in known_paths:
        df, src = _try_load_income_from_csv(p)
        if df is not None:
            normalized, label, diag = _normalize_income_df(df, src)
            if not normalized.empty:
                return normalized, label, diag

    # 3) Any income*.csv discovered
    for p in _discover_income_csvs():
        df, src = _try_load_income_from_csv(p)
        if df is not None:
            normalized, label, diag = _normalize_income_df(df, src)
            if not normalized.empty:
                return normalized, label, diag

    return pd.DataFrame(), "not found", {
        "source": "not found",
        "rows": 0,
        "date_col": None,
        "amount_col": None,
        "category_col": None,
        "error": "No income source returned data.",
    }


def income_in_period(income_df, date_from, date_to):
    """Filter income DataFrame to the selected period."""
    if income_df is None or income_df.empty:
        return pd.DataFrame()

    if "date" not in income_df.columns or "amount" not in income_df.columns:
        return income_df

    df = income_df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])

    start_dt = pd.to_datetime(date_from)
    end_dt = pd.to_datetime(date_to) + timedelta(days=1) - timedelta(seconds=1)

    return df[(df["date"] >= start_dt) & (df["date"] <= end_dt)]


def expenses_in_period(expenses_df, date_from, date_to):
    """Filter expenses DataFrame to the selected period."""
    if expenses_df is None or expenses_df.empty:
        return pd.DataFrame()

    date_col = get_date_column(expenses_df)
    if date_col is None:
        return expenses_df

    df = expenses_df.copy()
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])

    start_dt = pd.to_datetime(date_from)
    end_dt = pd.to_datetime(date_to) + timedelta(days=1) - timedelta(seconds=1)

    return df[(df[date_col] >= start_dt) & (df[date_col] <= end_dt)]


def sum_amount_column(df, amount_col_candidates=None):
    """Sum the first available amount column in a DataFrame."""
    if df is None or df.empty:
        return 0.0
    if amount_col_candidates is None:
        amount_col_candidates = ["amount", "total", "value", "expense_amount", "income_amount"]
    for col in amount_col_candidates:
        if col in df.columns:
            try:
                return safe_float(pd.to_numeric(df[col], errors="coerce").fillna(0).sum())
            except Exception:
                pass
    return 0.0


# ==============================
# FLOATING FINANCIALS DEBT HELPERS
# ==============================

def fetch_floating_debt_snapshot():
    """Pull debt metrics from Floating Financials."""
    snapshot = {
        "total_credit_balance": 0.0,
        "active_credit_count": 0,
        "partial_credit_count": 0,
        "total_credit_amount": 0.0,
        "total_credit_paid": 0.0,

        "total_change_balance": 0.0,
        "uncollected_change_count": 0,
        "partial_change_count": 0,
        "total_change_amount": 0.0,
        "total_change_collected": 0.0,

        "bad_debt_count": 0,
        "bad_debt_outstanding": 0.0,
        "bad_debt_original": 0.0,
        "written_off_changes_count": 0,
        "written_off_changes_outstanding": 0.0,
        "written_off_changes_original": 0.0,

        "overdue_credit_count": 0,
        "overdue_credit_balance": 0.0,
        "overdue_change_count": 0,
        "overdue_change_balance": 0.0,
    }

    # Credit summary
    try:
        cs = get_credit_summary() or {}
        snapshot["total_credit_amount"] = safe_float(cs.get("total_credit", 0))
        snapshot["total_credit_paid"] = safe_float(cs.get("total_paid", 0))
        snapshot["total_credit_balance"] = safe_float(cs.get("total_balance", 0))
        snapshot["active_credit_count"] = int(cs.get("active_count", 0) or 0)
        snapshot["partial_credit_count"] = int(cs.get("partial_count", 0) or 0)
    except Exception as e:
        print(f"[insights] get_credit_summary failed: {e}")

    # Change summary
    try:
        chs = get_change_summary() or {}
        snapshot["total_change_amount"] = safe_float(chs.get("total_change", 0))
        snapshot["total_change_collected"] = safe_float(chs.get("total_collected", 0))
        snapshot["total_change_balance"] = safe_float(chs.get("total_balance", 0))
        snapshot["uncollected_change_count"] = int(chs.get("uncollected_count", 0) or 0)
        snapshot["partial_change_count"] = int(chs.get("partial_count", 0) or 0)
    except Exception as e:
        print(f"[insights] get_change_summary failed: {e}")

    # Bad debt credits
    try:
        bd_df = get_bad_debt_credits()
        if bd_df is not None and not bd_df.empty:
            bd = bd_df.copy()
            bd["amount"] = pd.to_numeric(bd.get("amount"), errors="coerce").fillna(0)
            bd["amount_paid"] = pd.to_numeric(bd.get("amount_paid"), errors="coerce").fillna(0)
            bd["outstanding"] = (bd["amount"] - bd["amount_paid"]).clip(lower=0)
            open_bd = bd[bd["outstanding"] > 0]
            snapshot["bad_debt_count"] = int(len(open_bd))
            snapshot["bad_debt_original"] = safe_float(bd["amount"].sum())
            snapshot["bad_debt_outstanding"] = safe_float(open_bd["outstanding"].sum())
    except Exception as e:
        print(f"[insights] get_bad_debt_credits failed: {e}")

    # Written off changes
    try:
        wo_df = get_written_off_changes()
        if wo_df is not None and not wo_df.empty:
            wo = wo_df.copy()
            wo["amount"] = pd.to_numeric(wo.get("amount"), errors="coerce").fillna(0)
            wo["amount_collected"] = pd.to_numeric(wo.get("amount_collected"), errors="coerce").fillna(0)
            wo["outstanding"] = (wo["amount"] - wo["amount_collected"]).clip(lower=0)
            open_wo = wo[wo["outstanding"] > 0]
            snapshot["written_off_changes_count"] = int(len(open_wo))
            snapshot["written_off_changes_original"] = safe_float(wo["amount"].sum())
            snapshot["written_off_changes_outstanding"] = safe_float(open_wo["outstanding"].sum())
    except Exception as e:
        print(f"[insights] get_written_off_changes failed: {e}")

    # Overdue credits
    try:
        od_cr = get_overdue_credits()
        if od_cr is not None and not od_cr.empty:
            od_cr = od_cr.copy()
            od_cr["balance"] = pd.to_numeric(od_cr.get("balance"), errors="coerce").fillna(0)
            snapshot["overdue_credit_count"] = int(len(od_cr))
            snapshot["overdue_credit_balance"] = safe_float(od_cr["balance"].sum())
    except Exception as e:
        print(f"[insights] get_overdue_credits failed: {e}")

    # Overdue changes
    try:
        od_ch = get_overdue_changes()
        if od_ch is not None and not od_ch.empty:
            od_ch = od_ch.copy()
            od_ch["balance"] = pd.to_numeric(od_ch.get("balance"), errors="coerce").fillna(0)
            snapshot["overdue_change_count"] = int(len(od_ch))
            snapshot["overdue_change_balance"] = safe_float(od_ch["balance"].sum())
    except Exception as e:
        print(f"[insights] get_overdue_changes failed: {e}")

    return snapshot


# ==============================
# INSIGHTS GENERATOR
# ==============================

class InsightsGenerator:
    """Generate automated business insights"""

    def __init__(self):
        self.insights = []
        self.metrics = {}
        self.recommendations = []
        self.alerts = []

    def generate_daily_insights(self, date_from=None, date_to=None):
        """
        Generate daily business insights.

        date_from / date_to : optional explicit period for the Net Profit
                              calculation. Defaults to last 30 days.
        """
        # Default period: last 30 days
        if date_to is None:
            date_to = datetime.now().date()
        if date_from is None:
            date_from = date_to - timedelta(days=30)

        # Normalize to date objects
        try:
            date_from = pd.to_datetime(date_from).date()
            date_to = pd.to_datetime(date_to).date()
        except Exception:
            date_from = datetime.now().date() - timedelta(days=30)
            date_to = datetime.now().date()

        # Save the period for the report
        self.report_period = {
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
        }

        # ------------------ Load data ------------------
        sales_df = load_sales()
        products_df = load_products()
        expenses_df = load_expenses_direct()

        # Debt from floating financials
        debt_snapshot = fetch_floating_debt_snapshot()

        # Income from its OWN recorded source
        income_df, income_source, income_diag = load_income_auto()

        customers_df = get_customers_from_sales(sales_df)
        if customers_df.empty:
            customers_df = load_customers()

        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)

        # Reset collections
        self.insights = []
        self.metrics = {}
        self.recommendations = []
        self.alerts = []

        # Keep the income source info around
        self.metrics["income_source"] = income_source
        self.metrics["income_rows_total"] = income_diag.get("rows", 0)
        self.metrics["income_date_col"] = income_diag.get("date_col")
        self.metrics["income_amount_col"] = income_diag.get("amount_col")

        # 1. Sales Insights
        sales_insights = self._analyze_sales(sales_df, today, yesterday, week_ago, month_ago)
        self.insights.extend(sales_insights)

        # 2. Product Insights
        product_insights = self._analyze_products(products_df, sales_df)
        self.insights.extend(product_insights)

        # 3. Customer Insights
        customer_insights = self._analyze_customers(customers_df, sales_df)
        self.insights.extend(customer_insights)

        # 4. Financial Insights (expenses + revenue + period income + net profit)
        financial_insights = self._analyze_financials(
            expenses_df, sales_df, income_df, date_from, date_to
        )
        self.insights.extend(financial_insights)

        # 5. Floating Financials debt insights
        debt_insights = self._analyze_floating_debt(debt_snapshot)
        self.insights.extend(debt_insights)

        # 6. Alerts
        self.alerts = self._generate_alerts(products_df, sales_df, debt_snapshot)

        return self._format_report()

    def _analyze_sales(self, sales_df, today, yesterday, week_ago, month_ago):
        """Analyze sales data - WITH DEDUPLICATION"""
        insights = []

        if sales_df.empty:
            return [{"type": "sales", "message": "No sales data available", "priority": "info"}]

        date_col = get_date_column(sales_df)
        amount_col = get_amount_column(sales_df)
        receipt_col = get_receipt_column(sales_df)

        if date_col is None or amount_col is None:
            return [{"type": "sales", "message": "Sales data incomplete", "priority": "info"}]

        sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
        sales_df = sales_df.dropna(subset=[date_col])

        if sales_df.empty:
            return [{"type": "sales", "message": "No valid sales dates", "priority": "info"}]

        if receipt_col and receipt_col in sales_df.columns:
            sales_df = sales_df.drop_duplicates(subset=[receipt_col])

        today_sales = sales_df[sales_df[date_col].dt.date == today]
        today_revenue = safe_float(today_sales[amount_col].sum()) if amount_col else 0
        today_transactions = len(today_sales)

        yesterday_sales = sales_df[sales_df[date_col].dt.date == yesterday]
        yesterday_revenue = safe_float(yesterday_sales[amount_col].sum()) if amount_col else 0

        week_sales = sales_df[sales_df[date_col] >= pd.Timestamp(week_ago)]
        week_revenue = safe_float(week_sales[amount_col].sum()) if amount_col else 0

        month_sales = sales_df[sales_df[date_col] >= pd.Timestamp(month_ago)]
        month_revenue = safe_float(month_sales[amount_col].sum()) if amount_col else 0

        self.metrics["today_revenue"] = today_revenue
        self.metrics["today_transactions"] = today_transactions
        self.metrics["yesterday_revenue"] = yesterday_revenue
        self.metrics["week_revenue"] = week_revenue
        self.metrics["month_revenue"] = month_revenue

        if today_revenue > 0:
            if yesterday_revenue > 0:
                growth = ((today_revenue - yesterday_revenue) / yesterday_revenue * 100)
                if growth > 20:
                    insights.append({
                        "type": "sales",
                        "message": f"Sales up {growth:.0f}% compared to yesterday",
                        "priority": "high",
                        "detail": f"Today: ${today_revenue:,.2f} vs Yesterday: ${yesterday_revenue:,.2f}"
                    })
                elif growth < -20:
                    insights.append({
                        "type": "sales",
                        "message": f"Sales down {abs(growth):.0f}% compared to yesterday",
                        "priority": "medium",
                        "detail": f"Today: ${today_revenue:,.2f} vs Yesterday: ${yesterday_revenue:,.2f}"
                    })
                else:
                    insights.append({
                        "type": "sales",
                        "message": f"Sales stable at ${today_revenue:,.2f} today",
                        "priority": "info",
                        "detail": f"{today_transactions} transactions today"
                    })
            else:
                insights.append({
                    "type": "sales",
                    "message": f"Today's sales: ${today_revenue:,.2f}",
                    "priority": "info",
                    "detail": f"{today_transactions} transactions today"
                })
        else:
            insights.append({
                "type": "sales",
                "message": "No sales recorded today",
                "priority": "warning",
                "detail": "Check if store is open and POS is working"
            })

        if week_revenue > 0:
            insights.append({
                "type": "sales",
                "message": f"Weekly sales: ${week_revenue:,.2f}",
                "priority": "info",
                "detail": "Last 7 days performance"
            })

        return insights

    def _analyze_products(self, products_df, sales_df):
        """Analyze product data"""
        insights = []

        if products_df.empty:
            return [{"type": "products", "message": "No products in inventory", "priority": "info"}]

        total_products = len(products_df)
        out_of_stock = len(products_df[products_df["stock"] == 0])

        reorder_col = None
        for col in ["reorder_level", "reorder_point", "min_stock"]:
            if col in products_df.columns:
                reorder_col = col
                break

        if reorder_col:
            low_stock = len(products_df[products_df["stock"] <= products_df[reorder_col]])
        else:
            low_stock = len(products_df[(products_df["stock"] > 0) & (products_df["stock"] < 5)])

        self.metrics["total_products"] = total_products
        self.metrics["out_of_stock"] = out_of_stock
        self.metrics["low_stock"] = low_stock

        if out_of_stock > 0:
            out_of_stock_products = products_df[products_df["stock"] == 0]["name"].head(3).tolist()
            names = ", ".join(out_of_stock_products)
            insights.append({
                "type": "products",
                "message": f"{out_of_stock} products out of stock",
                "priority": "critical",
                "detail": f"Affected: {names}" + ("..." if len(out_of_stock_products) > 3 else "")
            })

        if low_stock > 0:
            insights.append({
                "type": "products",
                "message": f"{low_stock} products low on stock",
                "priority": "high",
                "detail": "Place orders soon to avoid stockouts"
            })

        if out_of_stock == 0 and low_stock == 0:
            insights.append({
                "type": "products",
                "message": "All products in stock",
                "priority": "success",
                "detail": f"{total_products} products available"
            })

        if not sales_df.empty and "name" in sales_df.columns:
            receipt_col = get_receipt_column(sales_df)
            if receipt_col and receipt_col in sales_df.columns:
                sales_products = sales_df.drop_duplicates(subset=[receipt_col])
            else:
                sales_products = sales_df

            if "items" in sales_products.columns:
                top_products = sales_products.groupby("name")["items"].sum().nlargest(3)
                if not top_products.empty:
                    top_names = top_products.index.tolist()
                    insights.append({
                        "type": "products",
                        "message": f"Top selling products: {', '.join(top_names)}",
                        "priority": "info",
                        "detail": "Focus on these best-sellers"
                    })

        return insights

    def _analyze_customers(self, customers_df, sales_df):
        """Analyze customer data - USING CUSTOMERS FROM SALES"""
        insights = []

        if customers_df.empty:
            return [{"type": "customers", "message": "No customer data available (no sales with customer names)", "priority": "info"}]

        total_customers = len(customers_df)
        self.metrics["total_customers"] = total_customers

        if not sales_df.empty:
            customer_col = get_customer_column(sales_df)
            date_col = get_date_column(sales_df)

            if customer_col and date_col:
                sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
                month_ago = datetime.now() - timedelta(days=30)

                recent_sales = sales_df[sales_df[date_col] >= month_ago].copy()
                if not recent_sales.empty:
                    receipt_col = get_receipt_column(sales_df)
                    if receipt_col and receipt_col in recent_sales.columns:
                        recent_sales = recent_sales.drop_duplicates(subset=[receipt_col])

                    recent_customers = recent_sales[customer_col].dropna().unique()
                    recent_customers = [
                        str(c).strip()
                        for c in recent_customers
                        if str(c).strip().lower() != "walk-in"
                    ]

                    new_customers = len(recent_customers)
                    self.metrics["new_customers"] = new_customers

                    if new_customers > 0:
                        insights.append({
                            "type": "customers",
                            "message": f"{new_customers} active customers this month",
                            "priority": "info",
                            "detail": f"Total: {total_customers} customers"
                        })

        if not sales_df.empty:
            customer_col = get_customer_column(sales_df)

            if customer_col:
                receipt_col = get_receipt_column(sales_df)
                if receipt_col and receipt_col in sales_df.columns:
                    sales_customers = sales_df.drop_duplicates(subset=[receipt_col])
                else:
                    sales_customers = sales_df

                customer_counts = sales_customers.groupby(customer_col).size()
                customer_counts = customer_counts[customer_counts.index.str.lower() != "walk-in"]

                if not customer_counts.empty:
                    repeat_customers = len(customer_counts[customer_counts > 1])
                    self.metrics["repeat_customers"] = repeat_customers

                    if repeat_customers > 0:
                        retention_rate = (repeat_customers / len(customer_counts) * 100) if len(customer_counts) > 0 else 0
                        if retention_rate < 20:
                            insights.append({
                                "type": "customers",
                                "message": f"Low retention rate: {retention_rate:.1f}%",
                                "priority": "medium",
                                "detail": "Consider loyalty programs to improve retention"
                            })
                        else:
                            insights.append({
                                "type": "customers",
                                "message": f"Customer retention: {retention_rate:.1f}%",
                                "priority": "success",
                                "detail": f"{repeat_customers} repeat customers"
                            })
                    else:
                        insights.append({
                            "type": "customers",
                            "message": "No repeat customers yet",
                            "priority": "info",
                            "detail": "Focus on customer retention strategies"
                        })

        return insights

    def _analyze_financials(self, expenses_df, sales_df, income_df, date_from, date_to):
        """
        Analyze financial data for the SELECTED PERIOD.

        - Income is loaded from its own recorded source (income_df).
        - Expenses come from the expenses module.
        - Net Profit = Income − Expenses, for the selected period.
        - Sales revenue is kept as its own metric (total_revenue) and is NOT
          treated as income.
        """
        insights = []

        period_label = f"{date_from.isoformat()} → {date_to.isoformat()}"
        self.metrics["period_label"] = period_label
        self.metrics["net_profit_period_label"] = period_label

        # ---------- Income for the period (OWN SOURCE) ----------
        period_income_df = income_in_period(income_df, date_from, date_to)
        period_income = sum_amount_column(
            period_income_df, ["amount", "total", "value", "income_amount", "received"]
        )
        self.metrics["period_income"] = period_income
        self.metrics["total_income"] = period_income  # alias used by email/dashboard

        # Monthly income (last 30 days) for reference
        month_ago = datetime.now().date() - timedelta(days=30)
        today = datetime.now().date()
        month_income_df = income_in_period(income_df, month_ago, today)
        monthly_income = sum_amount_column(
            month_income_df, ["amount", "total", "value", "income_amount", "received"]
        )
        self.metrics["monthly_income"] = monthly_income

        # Income insight
        if period_income > 0:
            insights.append({
                "type": "income",
                "message": f"Income for period ({period_label}): ${period_income:,.2f}",
                "priority": "info",
                "detail": f"Sourced from: {self.metrics.get('income_source', 'unknown')}"
            })
        else:
            insights.append({
                "type": "income",
                "message": "No income recorded for the selected period",
                "priority": "info",
                "detail": f"Source checked: {self.metrics.get('income_source', 'unknown')}"
            })

        # ---------- Expenses for the period ----------
        period_expenses_df = expenses_in_period(expenses_df, date_from, date_to)
        period_expenses = sum_amount_column(
            period_expenses_df, ["amount", "total", "value", "expense_amount"]
        )

        # Fallback: if module returned nothing, try db_adapter
        if period_expenses == 0:
            try:
                from backend.core.db_adapter import load_expenses as load_expenses_core
                alt_expenses = load_expenses_core()
                if alt_expenses is not None and not alt_expenses.empty:
                    alt_period = expenses_in_period(alt_expenses, date_from, date_to)
                    period_expenses = sum_amount_column(
                        alt_period, ["amount", "total", "value", "expense_amount"]
                    )
            except Exception:
                pass

        self.metrics["period_expenses"] = period_expenses
        self.metrics["total_expenses"] = period_expenses  # keep old key working

        # Monthly expenses for reference
        month_expenses_df = expenses_in_period(expenses_df, month_ago, today)
        monthly_expenses = sum_amount_column(
            month_expenses_df, ["amount", "total", "value", "expense_amount"]
        )
        self.metrics["monthly_expenses"] = monthly_expenses

        if period_expenses > 0:
            insights.append({
                "type": "financial",
                "message": f"Expenses for period ({period_label}): ${period_expenses:,.2f}",
                "priority": "info",
                "detail": f"Monthly expenses: ${monthly_expenses:,.2f}"
            })
        else:
            insights.append({
                "type": "financial",
                "message": "No expenses recorded for the selected period",
                "priority": "info",
                "detail": "Start recording expenses in the Expenses module"
            })

        # ---------- Sales revenue (kept as its own metric, NOT income) ----------
        total_revenue = 0
        sales_undup = pd.DataFrame()

        if not sales_df.empty:
            amount_col = get_amount_column(sales_df)
            receipt_col = get_receipt_column(sales_df)

            if amount_col:
                if receipt_col and receipt_col in sales_df.columns:
                    sales_undup = sales_df.drop_duplicates(subset=[receipt_col])
                else:
                    sales_undup = sales_df.copy()
                    if "date" in sales_undup.columns:
                        sales_undup = sales_undup.drop_duplicates(subset=["date", amount_col])
                total_revenue = safe_float(sales_undup[amount_col].sum())

        self.metrics["total_revenue"] = total_revenue
        self.metrics["revenue_unique_receipts"] = len(sales_undup) if not sales_undup.empty else 0

        if total_revenue > 0:
            insights.append({
                "type": "sales",
                "message": f"Revenue (all-time): ${total_revenue:,.2f}",
                "priority": "info",
                "detail": f"Based on {len(sales_undup)} unique receipts"
            })

        # ---------- NET PROFIT for the selected period ----------
        net_profit = period_income - period_expenses
        self.metrics["net_profit"] = net_profit

        # Legacy keys — keep both "net_income" and "income" pointing to the
        # new, correctly-sourced value so any downstream code keeps working.
        self.metrics["net_income"] = net_profit
        self.metrics["income"] = period_income  # "income" now means the recorded income

        # Net profit insight
        if period_income > 0 or period_expenses > 0:
            if net_profit > 0:
                insights.append({
                    "type": "financial",
                    "message": f"Net profit for period ({period_label}): ${net_profit:,.2f}",
                    "priority": "success",
                    "detail": f"Income ${period_income:,.2f} − Expenses ${period_expenses:,.2f}"
                })
            elif net_profit < 0:
                insights.append({
                    "type": "financial",
                    "message": f"Net loss for period ({period_label}): ${abs(net_profit):,.2f}",
                    "priority": "high",
                    "detail": f"Income ${period_income:,.2f} − Expenses ${period_expenses:,.2f}"
                })
            else:
                insights.append({
                    "type": "financial",
                    "message": f"Net profit is $0 (break-even) for period ({period_label})",
                    "priority": "info",
                    "detail": f"Income ${period_income:,.2f} = Expenses ${period_expenses:,.2f}"
                })
        else:
            insights.append({
                "type": "financial",
                "message": "Net profit cannot be computed — no income or expenses in period",
                "priority": "info",
                "detail": f"Period: {period_label}"
            })

        return insights

    def _analyze_floating_debt(self, snapshot):
        """Analyze debt data coming from Floating Financials."""
        insights = []

        if not snapshot:
            return [{"type": "debt", "message": "No floating financials debt data available", "priority": "info"}]

        self.metrics["total_credit_balance"] = snapshot.get("total_credit_balance", 0.0)
        self.metrics["active_credit_count"] = snapshot.get("active_credit_count", 0)
        self.metrics["partial_credit_count"] = snapshot.get("partial_credit_count", 0)
        self.metrics["total_change_balance"] = snapshot.get("total_change_balance", 0.0)
        self.metrics["uncollected_change_count"] = snapshot.get("uncollected_change_count", 0)
        self.metrics["partial_change_count"] = snapshot.get("partial_change_count", 0)
        self.metrics["bad_debt_count"] = snapshot.get("bad_debt_count", 0)
        self.metrics["bad_debt_outstanding"] = snapshot.get("bad_debt_outstanding", 0.0)
        self.metrics["written_off_changes_count"] = snapshot.get("written_off_changes_count", 0)
        self.metrics["written_off_changes_outstanding"] = snapshot.get("written_off_changes_outstanding", 0.0)
        self.metrics["overdue_credit_count"] = snapshot.get("overdue_credit_count", 0)
        self.metrics["overdue_credit_balance"] = snapshot.get("overdue_credit_balance", 0.0)
        self.metrics["overdue_change_count"] = snapshot.get("overdue_change_count", 0)
        self.metrics["overdue_change_balance"] = snapshot.get("overdue_change_balance", 0.0)

        # Legacy-compatible keys
        self.metrics["total_debt"] = snapshot.get("total_credit_balance", 0.0)
        self.metrics["debtors_count"] = (
            int(snapshot.get("active_credit_count", 0) or 0)
            + int(snapshot.get("partial_credit_count", 0) or 0)
        )

        # Outstanding credit
        credit_balance = snapshot.get("total_credit_balance", 0.0)
        open_credit_count = (
            int(snapshot.get("active_credit_count", 0) or 0)
            + int(snapshot.get("partial_credit_count", 0) or 0)
        )
        if credit_balance > 0:
            insights.append({
                "type": "debt",
                "message": f"Outstanding credit: ${credit_balance:,.2f}",
                "priority": "medium" if credit_balance > 1000 else "info",
                "detail": f"{open_credit_count} open credit record(s) in Floating Financials"
            })
        else:
            insights.append({
                "type": "debt",
                "message": "No outstanding customer credit",
                "priority": "success",
                "detail": "All credits fully paid"
            })

        # Outstanding change
        change_balance = snapshot.get("total_change_balance", 0.0)
        open_change_count = (
            int(snapshot.get("uncollected_change_count", 0) or 0)
            + int(snapshot.get("partial_change_count", 0) or 0)
        )
        if change_balance > 0:
            insights.append({
                "type": "debt",
                "message": f"Uncollected change: ${change_balance:,.2f}",
                "priority": "info",
                "detail": f"{open_change_count} open change record(s) in Floating Financials"
            })

        # Bad debt credits
        bd_outstanding = snapshot.get("bad_debt_outstanding", 0.0)
        bd_count = snapshot.get("bad_debt_count", 0)
        if bd_count > 0:
            insights.append({
                "type": "debt",
                "message": f"{bd_count} bad-debt credit(s) still unrecovered (${bd_outstanding:,.2f})",
                "priority": "high",
                "detail": "See Bad Debts section in Floating Financials for recovery"
            })

        # Written-off changes
        wo_outstanding = snapshot.get("written_off_changes_outstanding", 0.0)
        wo_count = snapshot.get("written_off_changes_count", 0)
        if wo_count > 0:
            insights.append({
                "type": "debt",
                "message": f"{wo_count} written-off change(s) still unrecovered (${wo_outstanding:,.2f})",
                "priority": "medium",
                "detail": "See Written Off Changes section in Floating Financials"
            })

        # Overdue
        od_cr_count = snapshot.get("overdue_credit_count", 0)
        od_cr_balance = snapshot.get("overdue_credit_balance", 0.0)
        if od_cr_count > 0:
            insights.append({
                "type": "debt",
                "message": f"{od_cr_count} overdue credit(s) totalling ${od_cr_balance:,.2f}",
                "priority": "high",
                "detail": "Follow up with these customers"
            })

        od_ch_count = snapshot.get("overdue_change_count", 0)
        od_ch_balance = snapshot.get("overdue_change_balance", 0.0)
        if od_ch_count > 0:
            insights.append({
                "type": "debt",
                "message": f"{od_ch_count} overdue change(s) totalling ${od_ch_balance:,.2f}",
                "priority": "medium",
                "detail": "Collect or write off per Floating Financials policy"
            })

        return insights

    def _generate_alerts(self, products_df, sales_df, debt_snapshot):
        """Generate critical alerts (debt now comes from floating financials)"""
        alerts = []

        # Stock alerts
        if not products_df.empty:
            out_of_stock = len(products_df[products_df["stock"] == 0])
            if out_of_stock > 0:
                alerts.append({
                    "type": "stock",
                    "message": f"{out_of_stock} products out of stock",
                    "severity": "critical"
                })

        # Debt alerts — from floating financials
        if debt_snapshot:
            credit_balance = debt_snapshot.get("total_credit_balance", 0.0)
            if credit_balance > 1000:
                open_count = (
                    int(debt_snapshot.get("active_credit_count", 0) or 0)
                    + int(debt_snapshot.get("partial_credit_count", 0) or 0)
                )
                alerts.append({
                    "type": "debt",
                    "message": f"Outstanding customer credit exceeds $1,000 (${credit_balance:,.2f} across {open_count} record(s))",
                    "severity": "warning"
                })

            od_cr_count = debt_snapshot.get("overdue_credit_count", 0)
            if od_cr_count > 0:
                alerts.append({
                    "type": "debt",
                    "message": f"{od_cr_count} overdue credit(s) need follow-up",
                    "severity": "warning"
                })

            bd_count = debt_snapshot.get("bad_debt_count", 0)
            if bd_count > 0:
                alerts.append({
                    "type": "debt",
                    "message": f"{bd_count} bad-debt credit(s) unrecovered",
                    "severity": "warning"
                })

        # Net profit alert
        try:
            net_profit = self.metrics.get("net_profit", None)
            if net_profit is not None and net_profit < 0:
                alerts.append({
                    "type": "profit",
                    "message": f"Negative net profit for period: ${net_profit:,.2f} (expenses exceed income)",
                    "severity": "warning"
                })
        except Exception:
            pass

        # Sales alerts
        if not sales_df.empty:
            date_col = get_date_column(sales_df)
            receipt_col = get_receipt_column(sales_df)

            if date_col:
                sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
                today = datetime.now().date()

                if receipt_col and receipt_col in sales_df.columns:
                    today_sales = sales_df[sales_df[date_col].dt.date == today].drop_duplicates(subset=[receipt_col])
                else:
                    today_sales = sales_df[sales_df[date_col].dt.date == today]

                if today_sales.empty:
                    alerts.append({
                        "type": "sales",
                        "message": "No sales recorded today",
                        "severity": "warning"
                    })

        return alerts

    def _format_report(self):
        """Format insights into report"""
        return {
            "generated_at": datetime.now().isoformat(),
            "period": "daily",
            "report_period": getattr(self, "report_period", {}),
            "metrics": self.metrics,
            "insights": self.insights,
            "alerts": self.alerts,
            "summary": self._generate_summary()
        }

    def _generate_summary(self):
        """Generate executive summary"""
        summary = []

        high_count = sum(1 for i in self.insights if i.get("priority") == "high")
        medium_count = sum(1 for i in self.insights if i.get("priority") == "medium")

        if high_count > 0:
            summary.append(f"{high_count} high-priority insights require attention")
        if medium_count > 0:
            summary.append(f"{medium_count} medium-priority insights to review")

        if self.metrics:
            revenue = self.metrics.get("today_revenue", 0)
            if revenue > 0:
                summary.append(f"Today's revenue: ${revenue:,.2f}")
            else:
                summary.append("No sales recorded today")

            # Income line (from its own recorded source)
            period_income = self.metrics.get("period_income", 0.0)
            if period_income > 0:
                summary.append(f"Income: ${period_income:,.2f}")

            # Net profit line
            net_profit = self.metrics.get("net_profit", None)
            if net_profit is not None:
                if net_profit >= 0:
                    summary.append(f"Net profit: ${net_profit:,.2f}")
                else:
                    summary.append(f"Net loss: ${abs(net_profit):,.2f}")

            # Debt line
            credit_balance = self.metrics.get("total_credit_balance", 0.0)
            if credit_balance > 0:
                summary.append(f"Outstanding credit: ${credit_balance:,.2f}")

            bd_outstanding = self.metrics.get("bad_debt_outstanding", 0.0)
            if bd_outstanding > 0:
                summary.append(f"Bad debt unrecovered: ${bd_outstanding:,.2f}")

        if not summary:
            summary.append("All metrics look good")

        return " | ".join(summary)


# ==============================
# INSIGHTS SETTINGS
# ==============================

def load_insights_settings():
    """Load insights settings"""
    if INSIGHTS_FILE.exists():
        try:
            with open(INSIGHTS_FILE, "r") as f:
                return json.load(f)
        except:
            pass

    return {
        "enabled": True,
        "frequency": "daily",
        "send_time": "08:00",
        "last_sent": None,
        "recipients": [],
        "include_sales": True,
        "include_products": True,
        "include_customers": True,
        "include_financial": True,
        "send_alerts": True,
        "period_days": 30,
    }


def save_insights_settings(settings):
    """Save insights settings"""
    INSIGHTS_FILE.parent.mkdir(exist_ok=True)
    with open(INSIGHTS_FILE, "w") as f:
        json.dump(settings, f, indent=2)


def log_insights_history(insights_data):
    """Log insights in history"""
    INSIGHTS_FILE.parent.mkdir(exist_ok=True)

    columns = [
        "timestamp", "period", "revenue", "income",
        "expenses", "net_profit", "transactions", "insights_count",
    ]
    if not INSIGHTS_HISTORY_FILE.exists():
        df = pd.DataFrame(columns=columns)
    else:
        df = pd.read_csv(INSIGHTS_HISTORY_FILE)
        # Ensure new columns exist for old files
        for c in columns:
            if c not in df.columns:
                df[c] = None

    metrics = insights_data.get("metrics", {})
    new_row = pd.DataFrame([{
        "timestamp": insights_data.get("generated_at", datetime.now().isoformat()),
        "period": insights_data.get("period", "daily"),
        "revenue": metrics.get("today_revenue", 0),
        "income": metrics.get("period_income", 0),
        "expenses": metrics.get("period_expenses", 0),
        "net_profit": metrics.get("net_profit", 0),
        "transactions": metrics.get("today_transactions", 0),
        "insights_count": len(insights_data.get("insights", [])),
    }])

    df = pd.concat([df, new_row], ignore_index=True)
    df.to_csv(INSIGHTS_HISTORY_FILE, index=False)


# ==============================
# EMAIL REPORT GENERATOR
# ==============================

def generate_insights_email_html(insights_data):
    """Generate HTML email for insights"""

    metrics = insights_data.get("metrics", {})
    insights = insights_data.get("insights", [])
    alerts = insights_data.get("alerts", [])
    report_period = insights_data.get("report_period", {})
    period_label = metrics.get("period_label", "")

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Business Insights - Aziel Investments</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
                background: #f4f4f4;
            }}
            .container {{
                max-width: 700px;
                margin: 0 auto;
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            .header {{
                text-align: center;
                border-bottom: 3px solid #6366F1;
                padding-bottom: 20px;
                margin-bottom: 25px;
            }}
            .header h1 {{
                color: #1a1a2e;
                margin: 0;
                font-size: 24px;
            }}
            .header p {{
                color: #666;
                margin: 5px 0 0 0;
                font-size: 14px;
            }}
            .metric-grid {{
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 15px;
                margin-bottom: 25px;
            }}
            .metric-card {{
                background: #f8f9fa;
                padding: 15px;
                border-radius: 8px;
                text-align: center;
                border: 1px solid #e5e7eb;
            }}
            .metric-value {{
                font-size: 22px;
                font-weight: bold;
                color: #1a1a2e;
            }}
            .metric-label {{
                font-size: 12px;
                color: #6B7280;
                margin-top: 5px;
            }}
            .insight-item {{
                padding: 12px 15px;
                margin: 8px 0;
                border-radius: 8px;
                border-left: 4px solid #6366F1;
                background: #f8f9fa;
            }}
            .insight-critical {{
                border-left-color: #ef4444;
                background: #fef2f2;
            }}
            .insight-high {{
                border-left-color: #f59e0b;
                background: #fffbeb;
            }}
            .insight-medium {{
                border-left-color: #3b82f6;
                background: #eff6ff;
            }}
            .insight-info {{
                border-left-color: #10b981;
                background: #ecfdf5;
            }}
            .alert-item {{
                padding: 12px 15px;
                margin: 8px 0;
                border-radius: 8px;
                background: #fef2f2;
                border: 1px solid #fca5a5;
                color: #991b1b;
            }}
            .footer {{
                text-align: center;
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #e5e7eb;
                color: #6B7280;
                font-size: 12px;
            }}
            .summary {{
                background: #f0fdf4;
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 20px;
                border: 1px solid #bbf7d0;
                color: #166534;
            }}
            .period {{
                text-align: center;
                color: #4B5563;
                font-size: 13px;
                margin-bottom: 15px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>SmartGro ERP Insights</h1>
                <p>Business Intelligence Report</p>
                <p style="font-size: 12px; color: #999;">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
    """

    if period_label:
        html += f"""
            <div class="period">Reporting period: <strong>{period_label}</strong></div>
        """

    if insights_data.get("summary"):
        html += f"""
            <div class="summary">
                <strong>Executive Summary</strong><br>
                {insights_data.get("summary")}
            </div>
        """

    if alerts:
        html += """
            <h3 style="color: #991b1b;">Alerts</h3>
        """
        for alert in alerts:
            html += f"""
                <div class="alert-item">
                    <strong>{alert.get('message', 'Alert')}</strong>
                </div>
            """

    if metrics:
        html += """
            <h3>Key Metrics</h3>
            <div class="metric-grid">
        """

        # Period-based metrics + debt metrics
        metric_display = [
            ("Today's Revenue", f"${metrics.get('today_revenue', 0):,.2f}"),
            ("Transactions", f"{metrics.get('today_transactions', 0)}"),
            ("Period Income", f"${metrics.get('period_income', 0):,.2f}"),
            ("Period Expenses", f"${metrics.get('period_expenses', 0):,.2f}"),
            ("Net Profit (period)", f"${metrics.get('net_profit', 0):,.2f}"),
            ("Total Revenue (all-time)", f"${metrics.get('total_revenue', 0):,.2f}"),
            ("Products", f"{metrics.get('total_products', 0)}"),
            ("Customers", f"{metrics.get('total_customers', 0)}"),
            ("Low Stock", f"{metrics.get('low_stock', 0)}"),
            ("Outstanding Credit", f"${metrics.get('total_credit_balance', 0):,.2f}"),
            ("Bad Debt Unrecovered", f"${metrics.get('bad_debt_outstanding', 0):,.2f}"),
            ("Uncollected Changes", f"${metrics.get('total_change_balance', 0):,.2f}"),
        ]

        for label, value in metric_display:
            html += f"""
                <div class="metric-card">
                    <div class="metric-value">{value}</div>
                    <div class="metric-label">{label}</div>
                </div>
            """

        html += """
            </div>
        """

    if insights:
        html += """
            <h3>Insights</h3>
        """

        for insight in insights:
            priority = insight.get("priority", "info")
            if priority == "critical":
                priority_class = "insight-critical"
            elif priority == "high":
                priority_class = "insight-high"
            elif priority == "medium":
                priority_class = "insight-medium"
            else:
                priority_class = "insight-info"

            detail = insight.get("detail", "")
            html += f"""
                <div class="insight-item {priority_class}">
                    <strong>{insight.get('message', '')}</strong>
                    {f'<br><span style="font-size: 13px; color: #6B7280;">{detail}</span>' if detail else ''}
                </div>
            """

    html += f"""
            <div class="footer">
                <p>SmartGro ERP System • Aziel Investments</p>
                <p>This report is automatically generated. For support, contact +263 78 290 5853</p>
                <p>© {datetime.now().year} Aziel Investments. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """

    return html


# ==============================
# SEND INSIGHTS
# ==============================

def send_insights_email(insights_data, recipient=None):
    """Send insights email to recipient"""

    settings = load_insights_settings()

    if not settings.get("enabled", True):
        return False, "Insights are disabled"

    recipients = recipient if recipient else settings.get("recipients", [])
    if isinstance(recipients, str):
        recipients = [recipients]

    if not recipients:
        return False, "No recipients configured"

    subject = f"SmartGro Insights - {datetime.now().strftime('%Y-%m-%d')}"
    body = generate_insights_email_html(insights_data)

    success_count = 0
    for email in recipients:
        if email and email.strip():
            success, message = send_email(
                recipient=email.strip(),
                subject=subject,
                body=body
            )
            if success:
                success_count += 1

    if success_count > 0:
        settings["last_sent"] = datetime.now().isoformat()
        save_insights_settings(settings)
        log_insights_history(insights_data)
        return True, f"Sent to {success_count} recipient(s)"

    return False, "Failed to send to any recipient"


def send_daily_insights(date_from=None, date_to=None):
    """Send daily insights to all recipients"""
    generator = InsightsGenerator()
    insights_data = generator.generate_daily_insights(date_from=date_from, date_to=date_to)
    return send_insights_email(insights_data)


def send_test_insights_email(email, date_from=None, date_to=None):
    """Send a test insights email"""
    generator = InsightsGenerator()
    insights_data = generator.generate_daily_insights(date_from=date_from, date_to=date_to)
    return send_insights_email(insights_data, email)


# ==============================
# INSIGHTS DASHBOARD
# ==============================

def automated_insights_dashboard():
    """Automated Insights Digest Dashboard"""

    st.title("Automated Insights Digest")
    st.caption("Daily/weekly AI-generated business summaries sent via email")

    role = st.session_state.get("role", "cashier")

    if role not in ["owner", "manager"]:
        st.error("Access Denied. Only owners and managers can access insights digest.")
        return

    settings = load_insights_settings()

    tab1, tab2, tab3 = st.tabs([
        "Generate Insights",
        "Settings",
        "History"
    ])

    # ==============================
    # TAB 1: GENERATE INSIGHTS
    # ==============================
    with tab1:
        st.markdown("## Generate Business Insights")
        st.caption(
            "Debt is sourced from Floating Financials. Income is sourced from its own "
            "recorded table/CSV. Net Profit = Income − Expenses for the selected period."
        )

        # Period selector for Net Profit
        col1, col2, col3 = st.columns([2, 2, 1])
        default_days = int(settings.get("period_days", 30))
        with col1:
            date_from = st.date_input(
                "Period From",
                value=datetime.now().date() - timedelta(days=default_days),
                key="insights_date_from",
            )
        with col2:
            date_to = st.date_input(
                "Period To",
                value=datetime.now().date(),
                key="insights_date_to",
            )
        with col3:
            st.markdown("<br>", unsafe_allow_html=True)
            refresh_income = st.button("🔄 Refresh Income", use_container_width=True)

        if refresh_income:
            try:
                st.cache_data.clear()
            except Exception:
                pass

        if st.button("Generate Today's Insights", type="primary", use_container_width=True):
            with st.spinner("Generating insights..."):
                generator = InsightsGenerator()
                insights_data = generator.generate_daily_insights(
                    date_from=date_from, date_to=date_to
                )

                st.session_state.current_insights = insights_data
                st.success("Insights generated!")
                st.balloons()

        if "current_insights" in st.session_state:
            insights_data = st.session_state.current_insights

            if insights_data.get("summary"):
                st.info(f"{insights_data.get('summary')}")

            period_label = insights_data.get("metrics", {}).get("period_label", "")
            if period_label:
                st.caption(f"Reporting period: **{period_label}**")

            alerts = insights_data.get("alerts", [])
            if alerts:
                st.markdown("### Alerts")
                for alert in alerts:
                    st.error(f"**{alert.get('message', 'Alert')}**")

            metrics = insights_data.get("metrics", {})
            if metrics:
                st.markdown("### Key Metrics")

                # Row 1: Sales / ops
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Today's Revenue", f"${metrics.get('today_revenue', 0):,.2f}")
                with col2:
                    st.metric("Transactions", metrics.get('today_transactions', 0))
                with col3:
                    st.metric("Products", metrics.get('total_products', 0))
                with col4:
                    st.metric("Customers", metrics.get('total_customers', 0))

                # Row 2: Income / Expenses / Net Profit / Low Stock
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Period Income", f"${metrics.get('period_income', 0):,.2f}")
                with col2:
                    st.metric("Period Expenses", f"${metrics.get('period_expenses', 0):,.2f}")
                with col3:
                    net_profit = metrics.get('net_profit', 0)
                    st.metric("Net Profit (period)", f"${net_profit:,.2f}")
                with col4:
                    st.metric("Low Stock", metrics.get('low_stock', 0))

                # Row 3: Revenue + debt metrics
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Revenue (all-time)", f"${metrics.get('total_revenue', 0):,.2f}")
                with col2:
                    st.metric("Outstanding Credit", f"${metrics.get('total_credit_balance', 0):,.2f}")
                with col3:
                    st.metric("Bad Debt Unrecovered", f"${metrics.get('bad_debt_outstanding', 0):,.2f}")
                with col4:
                    st.metric("Uncollected Changes", f"${metrics.get('total_change_balance', 0):,.2f}")

                # Row 4: Overdue
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Overdue Credits", metrics.get('overdue_credit_count', 0))
                with col2:
                    st.metric("Overdue Changes", metrics.get('overdue_change_count', 0))

                # Income source diagnostics
                with st.expander(
                    f"📂 Income source: {metrics.get('income_source', 'unknown')}",
                    expanded=False,
                ):
                    ic1, ic2, ic3 = st.columns(3)
                    with ic1:
                        st.metric("Rows Loaded", metrics.get("income_rows_total", 0))
                    with ic2:
                        st.metric("Date Column", str(metrics.get("income_date_col")))
                    with ic3:
                        st.metric("Amount Column", str(metrics.get("income_amount_col")))

            insights = insights_data.get("insights", [])
            if insights:
                st.markdown("### Insights")
                for insight in insights:
                    priority = insight.get("priority", "info")
                    icon = {
                        "critical": "[CRITICAL]",
                        "high": "[HIGH]",
                        "medium": "[MEDIUM]",
                        "info": "[INFO]",
                        "success": "[OK]"
                    }.get(priority, "[INFO]")

                    if priority in ["critical", "high"]:
                        st.error(f"{icon} **{insight.get('message', '')}**")
                        if insight.get("detail"):
                            st.caption(insight.get("detail"))
                    elif priority == "medium":
                        st.warning(f"{icon} **{insight.get('message', '')}**")
                        if insight.get("detail"):
                            st.caption(insight.get("detail"))
                    else:
                        st.info(f"{icon} **{insight.get('message', '')}**")
                        if insight.get("detail"):
                            st.caption(insight.get("detail"))

            st.markdown("---")
            st.markdown("### Send Report")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("Send to Configured Recipients", type="primary", use_container_width=True):
                    with st.spinner("Sending..."):
                        success, message = send_insights_email(insights_data)
                        if success:
                            st.success(f"{message}")
                        else:
                            st.error(f"{message}")

            with col2:
                recipient = st.text_input("Send to specific email", placeholder="email@example.com")
                if recipient and st.button("Send Test Email", use_container_width=True):
                    with st.spinner("Sending..."):
                        success, message = send_test_insights_email(
                            recipient, date_from=date_from, date_to=date_to
                        )
                        if success:
                            st.success(f"{message}")
                        else:
                            st.error(f"{message}")

    # ==============================
    # TAB 2: SETTINGS
    # ==============================
    with tab2:
        st.markdown("## Insights Settings")

        col1, col2 = st.columns(2)

        with col1:
            enabled = st.checkbox("Enable Automated Insights", value=settings.get("enabled", True))
            frequency = st.selectbox(
                "Frequency",
                ["daily", "weekly"],
                index=["daily", "weekly"].index(settings.get("frequency", "daily"))
            )
            send_time = st.time_input(
                "Send Time",
                value=datetime.strptime(settings.get("send_time", "08:00"), "%H:%M").time()
            )
            period_days = st.number_input(
                "Default Period (days)",
                min_value=1,
                max_value=365,
                value=int(settings.get("period_days", 30)),
                step=1,
            )

        with col2:
            include_sales = st.checkbox("Include Sales Insights", value=settings.get("include_sales", True))
            include_products = st.checkbox("Include Product Insights", value=settings.get("include_products", True))
            include_customers = st.checkbox("Include Customer Insights", value=settings.get("include_customers", True))
            include_financial = st.checkbox("Include Financial Insights", value=settings.get("include_financial", True))
            send_alerts = st.checkbox("Send Critical Alerts", value=settings.get("send_alerts", True))

        st.markdown("---")
        st.markdown("### Recipients")

        recipients_text = st.text_area(
            "Recipient Emails (one per line)",
            value="\n".join(settings.get("recipients", [])),
            height=100,
            placeholder="manager@example.com\nowner@example.com"
        )

        if st.button("Save Settings", type="primary", use_container_width=True):
            recipients = [r.strip() for r in recipients_text.split("\n") if r.strip()]

            settings.update({
                "enabled": enabled,
                "frequency": frequency,
                "send_time": send_time.strftime("%H:%M"),
                "recipients": recipients,
                "include_sales": include_sales,
                "include_products": include_products,
                "include_customers": include_customers,
                "include_financial": include_financial,
                "send_alerts": send_alerts,
                "period_days": int(period_days),
            })

            save_insights_settings(settings)
            st.success("Settings saved successfully!")
            st.rerun()

        st.markdown("---")
        if st.button("Send Test Insights Email", use_container_width=True):
            with st.spinner("Generating and sending..."):
                generator = InsightsGenerator()
                insights_data = generator.generate_daily_insights()
                success, message = send_insights_email(insights_data)
                if success:
                    st.success(f"{message}")
                else:
                    st.error(f"{message}")

    # ==============================
    # TAB 3: HISTORY
    # ==============================
    with tab3:
        st.markdown("## Insights History")

        if INSIGHTS_HISTORY_FILE.exists():
            history_df = pd.read_csv(INSIGHTS_HISTORY_FILE)

            if not history_df.empty:
                history_df["timestamp"] = pd.to_datetime(history_df["timestamp"])
                history_df["date"] = history_df["timestamp"].dt.strftime("%Y-%m-%d %H:%M")

                display_cols = ["date", "period", "revenue"]
                if "income" in history_df.columns:
                    display_cols.append("income")
                if "expenses" in history_df.columns:
                    display_cols.append("expenses")
                if "net_profit" in history_df.columns:
                    display_cols.append("net_profit")
                display_cols.extend(["transactions", "insights_count"])
                display_cols = [c for c in display_cols if c in history_df.columns]

                st.dataframe(
                    history_df[display_cols].tail(30),
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "revenue": st.column_config.NumberColumn("Revenue", format="$%.2f"),
                        "income": st.column_config.NumberColumn("Income", format="$%.2f"),
                        "expenses": st.column_config.NumberColumn("Expenses", format="$%.2f"),
                        "net_profit": st.column_config.NumberColumn("Net Profit", format="$%.2f"),
                    }
                )

                if len(history_df) > 1:
                    fig = go.Figure()

                    if "revenue" in history_df.columns:
                        fig.add_trace(go.Scatter(
                            x=history_df["timestamp"],
                            y=history_df["revenue"],
                            mode="lines+markers",
                            name="Revenue",
                            line=dict(color="#6366F1", width=2)
                        ))

                    if "income" in history_df.columns:
                        fig.add_trace(go.Scatter(
                            x=history_df["timestamp"],
                            y=history_df["income"],
                            mode="lines+markers",
                            name="Income",
                            line=dict(color="#10B981", width=2)
                        ))

                    if "net_profit" in history_df.columns:
                        fig.add_trace(go.Scatter(
                            x=history_df["timestamp"],
                            y=history_df["net_profit"],
                            mode="lines+markers",
                            name="Net Profit",
                            line=dict(color="#F59E0B", width=2)
                        ))

                    fig.update_layout(
                        title="Revenue, Income & Net Profit Trend",
                        xaxis_title="Date",
                        yaxis_title="Amount ($)",
                        height=300
                    )
                    st.plotly_chart(fig, use_container_width=True)

                csv = history_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download History (CSV)",
                    data=csv,
                    file_name=f"insights_history_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            else:
                st.info("No history data available")
        else:
            st.info("No history data available")


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    automated_insights_dashboard()