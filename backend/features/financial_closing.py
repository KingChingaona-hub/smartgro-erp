# backend/features/financial_closing.py
# Financial Closing — branch-aware.
#
# Branch scoping:
#     branch_id = None          -> session branch
#     branch_id = "HO"/"NAT"/.. -> that single branch
#     branch_id = "__ALL__"     -> aggregate across all branches (owner only)
#
# Backup uses pg_dump. Filesystem copies of data/*.csv are legacy and are NOT
# taken. If pg_dump is unavailable, create_backup() returns (False, msg) —
# callers must handle that before proceeding.

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from pathlib import Path
import re
import json
import shutil
import subprocess
import os
import socket
from urllib.parse import urlparse

from backend.core.db_adapter import (
    load_sales,
    load_expenses,
    load_purchases,
    load_products,
    load_customers,
    load_debtors,
    load_cash,
    load_shifts,
    load_branches,
    get_cash_summary,
    to_float,
    load_db_config,
)
from backend.modules.income import load_income
from backend.analytics.pl_engine import profit_loss_account
from backend.admin.security import log_audit


# ==============================
# FILE PATHS
# ==============================
DATA_DIR = Path("data")
CLOSING_DIR = DATA_DIR / "closing_reports"
BACKUP_DIR = DATA_DIR / "backups"


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


def _branch_scope_selector(branches_df, key_suffix=""):
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
            key=f"closing_branch_scope{key_suffix}",
            help="Owners may close company-wide or per branch.",
        )
        if choice == "All Branches":
            return ALL_BRANCHES, "All Branches"
        m = re.search(r"\(([^)]+)\)\s*$", choice)
        code = m.group(1).strip() if m else choice
        return code, choice

    session_branch = _resolve_branch(None)
    label = _branch_label(session_branch)
    st.info(f"Financial closing locked to your branch: **{label}**")
    return session_branch, label


# ==============================
# INITIALIZATION
# ==============================
def init_closing_files():
    CLOSING_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)


# ==============================
# PERIOD DATES
# ==============================
def get_period_dates(period_type, year, month=None, quarter=None):
    today = datetime.now()

    if period_type == "daily":
        start_date = today.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = today.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif period_type == "monthly":
        if month:
            start_date = datetime(year, month, 1)
            end_date = (
                datetime(year + 1, 1, 1) - timedelta(days=1)
                if month == 12 else datetime(year, month + 1, 1) - timedelta(days=1)
            )
        else:
            start_date = datetime(year, 1, 1)
            end_date = datetime(year, 12, 31)
    elif period_type == "quarterly":
        q_months = {1: [1, 2, 3], 2: [4, 5, 6], 3: [7, 8, 9], 4: [10, 11, 12]}
        start_month = q_months[quarter][0]
        end_month = q_months[quarter][2]
        start_date = datetime(year, start_month, 1)
        end_date = (
            datetime(year + 1, 1, 1) - timedelta(days=1)
            if end_month == 12 else datetime(year, end_month + 1, 1) - timedelta(days=1)
        )
    elif period_type == "yearly":
        start_date = datetime(year, 1, 1)
        end_date = datetime(year, 12, 31)
    else:
        start_date = today - timedelta(days=30)
        end_date = today

    if isinstance(end_date, datetime):
        end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)

    return start_date, end_date


# ==============================
# DEDUPLICATED SALES HELPER
# ==============================
def get_unduplicated_sales(sales_df, date_col=None, total_col=None, receipt_col=None):
    """Return unique receipts for revenue; original frame for profit and items."""
    if sales_df is None or sales_df.empty:
        return pd.DataFrame(), 0, 0, 0, 0

    if receipt_col and receipt_col in sales_df.columns:
        unique_receipts = sales_df.drop_duplicates(subset=[receipt_col])
        total_revenue = to_float(unique_receipts[total_col].sum()) if total_col in unique_receipts.columns else 0
        transaction_count = len(unique_receipts)

        if 'items' in sales_df.columns:
            items_sold = to_float(sales_df['items'].sum())
        elif 'item_count' in unique_receipts.columns:
            items_sold = to_float(unique_receipts['item_count'].sum())
        else:
            items_sold = len(sales_df)

        total_profit = to_float(sales_df['profit'].sum()) if 'profit' in sales_df.columns else 0

        return unique_receipts, total_revenue, total_profit, items_sold, transaction_count

    total_revenue = to_float(sales_df[total_col].sum()) if total_col in sales_df.columns else 0
    total_profit = to_float(sales_df['profit'].sum()) if 'profit' in sales_df.columns else 0
    items_sold = to_float(sales_df['items'].sum()) if 'items' in sales_df.columns else len(sales_df)
    transaction_count = len(sales_df)

    return sales_df, total_revenue, total_profit, items_sold, transaction_count


# ==============================
# COLUMN HELPERS
# ==============================
def _find_col(df, candidates, default=None):
    if df is None or df.empty:
        return default
    for c in candidates:
        if c in df.columns:
            return c
    return default


# ==============================
# PERIOD DATA (branch-scoped)
# ==============================
def get_period_data(period_type, year, month=None, quarter=None, branch_id=None):
    """
    Get financial data for a period. Every loader is scoped to branch_id
    (defaults to session branch).
    """
    branch_id = _resolve_branch(branch_id)
    start_date, end_date = get_period_dates(period_type, year, month, quarter)

    sales_df = _load_scoped(load_sales, branch_id)
    expenses_df = _load_scoped(load_expenses, branch_id)
    purchases_df = _load_scoped(load_purchases, branch_id)
    customers_df = _load_scoped(load_customers, branch_id)
    products_df = _load_scoped(load_products, branch_id)

    # ---- Income ----
    income_df = _load_scoped(load_income, branch_id) if not _is_all_branches(branch_id) else None
    if income_df is None:
        try:
            # load_income from modules.income accepts branch_id
            income_df = _load_scoped(load_income, branch_id)
        except Exception:
            income_df = pd.DataFrame()

    total_income = 0
    income_categories = {}

    if income_df is not None and not income_df.empty:
        date_col_inc = _find_col(income_df, ["date", "income_date", "created_at"])
        amount_col_inc = _find_col(income_df, ["amount", "total", "value"])
        category_col_inc = _find_col(income_df, ["category", "income_type", "type"])

        if date_col_inc and amount_col_inc:
            income_df = income_df.copy()
            income_df[date_col_inc] = pd.to_datetime(income_df[date_col_inc], errors="coerce")
            income_df = income_df.dropna(subset=[date_col_inc])

            period_income = income_df[
                (income_df[date_col_inc] >= start_date) & (income_df[date_col_inc] <= end_date)
            ]
            if not period_income.empty:
                total_income = to_float(period_income[amount_col_inc].sum())
                if category_col_inc:
                    cat = period_income.groupby(category_col_inc)[amount_col_inc].sum().to_dict()
                    income_categories = {str(k): to_float(v) for k, v in cat.items()}

    # ---- Sales ----
    date_col = _find_col(sales_df, ["sale_date", "date", "transaction_date", "created_at"])
    total_col = _find_col(sales_df, ["final_total", "total", "amount", "sale_amount"])
    receipt_col = _find_col(sales_df, ["receipt_no", "receipt", "transaction_id", "invoice_no"])

    total_revenue = 0
    total_profit = 0
    transaction_count = 0
    items_sold = 0

    if not sales_df.empty and date_col:
        sales_df = sales_df.copy()
        sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
        sales_df = sales_df.dropna(subset=[date_col])

        period_sales = sales_df[
            (sales_df[date_col] >= start_date) & (sales_df[date_col] <= end_date)
        ]
        if not period_sales.empty:
            _, total_revenue, total_profit, items_sold, transaction_count = get_unduplicated_sales(
                period_sales, date_col, total_col, receipt_col
            )

    # ---- Expenses ----
    total_expenses = 0
    expense_categories = {}

    if not expenses_df.empty:
        date_col_exp = _find_col(expenses_df, ["date", "expense_date", "created_at"])
        amount_col = _find_col(expenses_df, ["amount", "total", "value"])
        category_col = _find_col(expenses_df, ["category", "expense_type", "type"])

        if date_col_exp and amount_col:
            expenses_df = expenses_df.copy()
            expenses_df[date_col_exp] = pd.to_datetime(expenses_df[date_col_exp], errors="coerce")
            expenses_df = expenses_df.dropna(subset=[date_col_exp])

            period_expenses = expenses_df[
                (expenses_df[date_col_exp] >= start_date) & (expenses_df[date_col_exp] <= end_date)
            ]
            if not period_expenses.empty:
                total_expenses = to_float(period_expenses[amount_col].sum())
                if category_col:
                    cat = period_expenses.groupby(category_col)[amount_col].sum().to_dict()
                    expense_categories = {str(k): to_float(v) for k, v in cat.items()}

    # ---- Purchases ----
    total_purchases = 0
    if not purchases_df.empty:
        date_col_pur = _find_col(purchases_df, ["date_ordered", "date", "order_date"])
        if date_col_pur:
            purchases_df = purchases_df.copy()
            purchases_df[date_col_pur] = pd.to_datetime(purchases_df[date_col_pur], errors="coerce")
            period_purchases = purchases_df[
                (purchases_df[date_col_pur] >= start_date) & (purchases_df[date_col_pur] <= end_date)
            ]
            if "total_cost" in period_purchases.columns and not period_purchases.empty:
                total_purchases = to_float(period_purchases["total_cost"].sum())

    # ---- New customers ----
    new_customers = 0
    if not customers_df.empty:
        date_col_cust = _find_col(
            customers_df, ["created_at", "join_date", "date_joined", "last_purchase_date"]
        )
        if date_col_cust:
            customers_df = customers_df.copy()
            customers_df[date_col_cust] = pd.to_datetime(customers_df[date_col_cust], errors="coerce")
            new_customers = len(customers_df[customers_df[date_col_cust] >= start_date])
        else:
            new_customers = len(customers_df)

    return {
        "branch_id": branch_id,
        "branch_label": _branch_label(branch_id),
        "start_date": start_date,
        "end_date": end_date,
        "total_revenue": total_revenue,
        "total_income": total_income,
        "income_categories": income_categories,
        "total_expenses": total_expenses,
        "expense_categories": expense_categories,
        "total_purchases": total_purchases,
        "transaction_count": transaction_count,
        "items_sold": items_sold,
        "total_profit": total_profit,
        "new_customers": new_customers,
        "period_type": period_type,
        "year": year,
        "month": month,
        "quarter": quarter,
    }


# ==============================
# PDF GENERATION
# ==============================
def generate_closing_report_pdf(data):
    """Generate a closing report PDF. Title includes the branch name."""
    from io import BytesIO
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import inch

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle(
        'CustomTitle', parent=styles['Heading1'], fontSize=15, alignment=1
    )

    if data["period_type"] == "daily":
        period_text = f"Daily Report — {data['start_date'].strftime('%Y-%m-%d')}"
    elif data["period_type"] == "monthly":
        period_text = f"Monthly Report — {data['start_date'].strftime('%B %Y')}"
    elif data["period_type"] == "quarterly":
        period_text = f"Quarterly Report — Q{data['quarter']} {data['year']}"
    else:
        period_text = f"Annual Report — {data['year']}"

    branch_label = data.get("branch_label", data.get("branch_id", "—"))

    story.append(Paragraph(f"AZIEL INVESTMENTS — {period_text}", title_style))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"<b>Branch:</b> {branch_label}", styles["Normal"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles["Normal"]
    ))
    story.append(Spacer(1, 16))

    summary_data = [
        ["Metric", "Value"],
        ["Branch", branch_label],
        ["Total Revenue", f"${data['total_revenue']:,.2f}"],
        ["Total Income", f"${data['total_income']:,.2f}"],
        ["Total Expenses", f"${data['total_expenses']:,.2f}"],
        ["Total Purchases", f"${data['total_purchases']:,.2f}"],
        ["Transactions", f"{data['transaction_count']:,}"],
        ["Items Sold", f"{data['items_sold']:,}"],
        ["New Customers", f"{data['new_customers']}"],
    ]

    table = Table(summary_data, colWidths=[3 * inch, 3 * inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
    ]))
    story.append(table)

    if data.get('income_categories'):
        story.append(Spacer(1, 20))
        story.append(Paragraph("Income by Category", styles['Heading2']))
        inc_data = [["Category", "Amount"]]
        for cat, amt in sorted(data['income_categories'].items(), key=lambda x: -x[1]):
            inc_data.append([cat, f"${amt:,.2f}"])
        inc_table = Table(inc_data, colWidths=[3 * inch, 3 * inch])
        inc_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        story.append(inc_table)

    if data.get('expense_categories'):
        story.append(Spacer(1, 20))
        story.append(Paragraph("Expenses by Category", styles['Heading2']))
        exp_data = [["Category", "Amount"]]
        for cat, amt in sorted(data['expense_categories'].items(), key=lambda x: -x[1]):
            exp_data.append([cat, f"${amt:,.2f}"])
        exp_table = Table(exp_data, colWidths=[3 * inch, 3 * inch])
        exp_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        story.append(exp_table)

    doc.build(story)
    buffer.seek(0)
    return buffer


# ==============================
# REAL BACKUP (pg_dump)
# ==============================
def _pg_dump_available() -> bool:
    return shutil.which("pg_dump") is not None


def create_backup(branch_id=None, include_branches_table=True):
    """
    Create a real database backup using pg_dump.

    If branch_id is a single code, we do a full pg_dump of the whole DB and
    keep it as-is (pg_dump doesn't natively support per-table-row filters).
    A helper README inside the backup directory records the branch the owner
    was scoped to, so the archived file carries the context.

    Returns (ok: bool, path_or_message: Path | str).
    """
    init_closing_files()

    if not _pg_dump_available():
        return False, "pg_dump not found on PATH. Install PostgreSQL client tools."

    try:
        cfg = load_db_config()
    except Exception as e:
        return False, f"Could not load DB config: {e}"

    branch_id = _resolve_branch(branch_id)
    scope = "all" if _is_all_branches(branch_id) else _branch_slug(branch_id)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"backup_{scope}_{timestamp}"
    backup_path = BACKUP_DIR / backup_name
    backup_path.mkdir(exist_ok=True)

    dump_file = backup_path / "database.sql"

    env = os.environ.copy()
    if cfg.get("password"):
        env["PGPASSWORD"] = str(cfg["password"])

    cmd = [
        "pg_dump",
        "-h", str(cfg.get("host", "localhost")),
        "-p", str(cfg.get("port", 5432)),
        "-U", str(cfg.get("user", "postgres")),
        "-d", str(cfg.get("database", "smartgro")),
        "-F", "p",       # plain SQL
        "-f", str(dump_file),
    ]

    try:
        result = subprocess.run(
            cmd, env=env, capture_output=True, text=True, timeout=600
        )
        if result.returncode != 0:
            shutil.rmtree(backup_path, ignore_errors=True)
            return False, f"pg_dump failed: {result.stderr.strip()[:300]}"
    except FileNotFoundError:
        shutil.rmtree(backup_path, ignore_errors=True)
        return False, "pg_dump executable not found"
    except subprocess.TimeoutExpired:
        shutil.rmtree(backup_path, ignore_errors=True)
        return False, "pg_dump timed out after 10 minutes"
    except Exception as e:
        shutil.rmtree(backup_path, ignore_errors=True)
        return False, f"Error running pg_dump: {e}"

    # Stamp the scope
    try:
        (backup_path / "README.txt").write_text(
            f"Database backup created by financial_closing.create_backup()\n"
            f"Scope at time of backup: {branch_id}\n"
            f"Created: {datetime.now().isoformat()}\n"
            f"Note: pg_dump captures the full database; per-branch scoping is\n"
            f"documentation only, not a partial restore target.\n"
        )
    except Exception:
        pass

    return True, backup_path


# ==============================
# CLOSING OPERATIONS
# ==============================
def perform_daily_close(branch_id=None):
    """Perform end-of-day closing for a branch."""
    init_closing_files()
    branch_id = _resolve_branch(branch_id)
    label = _branch_label(branch_id)

    ok, backup_path = create_backup(branch_id=branch_id)
    if not ok:
        # Continue without backup, but warn loudly
        st.warning(f"Backup skipped: {backup_path}")
        backup_path = None

    data = get_period_data("daily", datetime.now().year, datetime.now().month, branch_id=branch_id)
    pdf = generate_closing_report_pdf(data)

    report_path = CLOSING_DIR / (
        f"daily_close_{_branch_slug(branch_id)}_{datetime.now().strftime('%Y%m%d')}.pdf"
    )
    with open(report_path, "wb") as f:
        f.write(pdf.getvalue())

    log_audit(
        st.session_state.get("username", "system"),
        "DAILY_CLOSE",
        f"Daily closing for {label}. Report: {report_path.name}"
        + (f", Backup: {backup_path}" if backup_path else ", Backup skipped"),
    )
    return True, report_path, backup_path


def perform_monthly_close(year, month, branch_id=None):
    """Perform month-end closing for a branch."""
    init_closing_files()
    branch_id = _resolve_branch(branch_id)
    label = _branch_label(branch_id)

    ok, backup_path = create_backup(branch_id=branch_id)
    if not ok:
        st.warning(f"Backup skipped: {backup_path}")
        backup_path = None

    data = get_period_data("monthly", year, month, branch_id=branch_id)
    pdf = generate_closing_report_pdf(data)

    report_path = CLOSING_DIR / (
        f"monthly_close_{_branch_slug(branch_id)}_{year}_{month:02d}.pdf"
    )
    with open(report_path, "wb") as f:
        f.write(pdf.getvalue())

    log_audit(
        st.session_state.get("username", "system"),
        "MONTHLY_CLOSE",
        f"Monthly closing for {label} ({year}-{month:02d}). Report: {report_path.name}"
        + (f", Backup: {backup_path}" if backup_path else ", Backup skipped"),
    )
    return True, report_path, backup_path


# ==============================
# TAX REPORT (scoped)
# ==============================
def generate_tax_report(year, tax_period="annual", branch_id=None):
    """Generate ZIMRA tax report. Scoped to a single branch (or __ALL__)."""
    branch_id = _resolve_branch(branch_id)
    label = _branch_label(branch_id)

    start_date = datetime(year, 1, 1)
    end_date = datetime(year, 12, 31)

    sales_df = _load_scoped(load_sales, branch_id)
    expenses_df = _load_scoped(load_expenses, branch_id)
    income_df = _load_scoped(load_income, branch_id)

    # Sales (unduplicated)
    date_col = _find_col(sales_df, ["sale_date", "date", "transaction_date"])
    total_col = _find_col(sales_df, ["final_total", "total", "amount"])
    receipt_col = _find_col(sales_df, ["receipt_no", "receipt", "transaction_id"])

    total_sales = 0
    if not sales_df.empty and date_col and total_col:
        sales_df = sales_df.copy()
        sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
        period_sales = sales_df[(sales_df[date_col] >= start_date) & (sales_df[date_col] <= end_date)]
        if not period_sales.empty:
            if receipt_col and receipt_col in period_sales.columns:
                unique_receipts = period_sales.drop_duplicates(subset=[receipt_col])
                total_sales = to_float(unique_receipts[total_col].sum())
            else:
                total_sales = to_float(period_sales[total_col].sum())

    # Income
    total_income = 0
    if not income_df.empty:
        d = _find_col(income_df, ["date", "income_date"])
        a = _find_col(income_df, ["amount", "total"])
        if d and a:
            income_df = income_df.copy()
            income_df[d] = pd.to_datetime(income_df[d], errors="coerce")
            period = income_df[(income_df[d] >= start_date) & (income_df[d] <= end_date)]
            if not period.empty:
                total_income = to_float(period[a].sum())

    # Expenses
    total_expenses = 0
    if not expenses_df.empty:
        d = _find_col(expenses_df, ["date", "expense_date"])
        a = _find_col(expenses_df, ["amount", "total"])
        if d and a:
            expenses_df = expenses_df.copy()
            expenses_df[d] = pd.to_datetime(expenses_df[d], errors="coerce")
            period = expenses_df[(expenses_df[d] >= start_date) & (expenses_df[d] <= end_date)]
            if not period.empty:
                total_expenses = to_float(period[a].sum())

    taxable_income = total_income - total_expenses
    tax_rate = 0.25
    tax_due = taxable_income * tax_rate if taxable_income > 0 else 0

    return f"""
{'='*60}
AZIEL INVESTMENTS — ZIMRA TAX REPORT
{'='*60}

Branch: {label}
Tax Period: {tax_period.upper()} {year}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{'-'*40}
INCOME STATEMENT
{'-'*40}
Total Sales (Revenue): ${total_sales:,.2f}
Total Income: ${total_income:,.2f}
Total Expenses: ${total_expenses:,.2f}
{'-'*40}
Taxable Income: ${taxable_income:,.2f}

{'-'*40}
TAX CALCULATION
{'-'*40}
Tax Rate: 25%
Tax Due: ${tax_due:,.2f}

{'-'*40}
{'='*60}
This report is generated automatically by SmartGro ERP System
For official ZIMRA filing, please consult with your accountant.
{'='*60}
"""


# ==============================
# DASHBOARD
# ==============================
def financial_closing_dashboard(branch_id=None):
    st.title("Automated Financial Closing")
    st.caption("End-of-day, month-end, and year-end closing with real data — branch-scoped")

    role = st.session_state.get("role", "cashier")
    if role not in ["owner", "manager"]:
        st.error("Access Denied. Only owners and managers can perform financial closing.")
        return

    try:
        branches_df = load_branches()
    except Exception:
        branches_df = pd.DataFrame()

    if branch_id is None:
        branch_id, branch_label = _branch_scope_selector(branches_df)
    else:
        branch_label = _branch_label(branch_id)

    st.caption(f"Closing on behalf of: **{branch_label}**")

    init_closing_files()

    if not _pg_dump_available():
        st.warning(
            "pg_dump is not available on this system. Backups will be skipped. "
            "Install PostgreSQL client tools to enable them."
        )

    tab1, tab2, tab3, tab4 = st.tabs([
        "Daily Closing", "Month-End Closing", "Tax Reports", "Closing History",
    ])

    # ==============================
    # TAB 1: DAILY CLOSING
    # ==============================
    with tab1:
        st.markdown("## End-of-Day Closing")
        st.caption(f"Close {branch_label}'s transactions for today")

        today_data = get_period_data(
            "daily", datetime.now().year, datetime.now().month, branch_id=branch_id
        )

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Revenue", f"${today_data['total_revenue']:,.2f}")
        with col2:
            st.metric("Total Income", f"${today_data['total_income']:,.2f}")
        with col3:
            st.metric("Total Expenses", f"${today_data['total_expenses']:,.2f}")
        with col4:
            st.metric("Transactions", today_data['transaction_count'])

        st.markdown("---")
        st.warning(
            "Performing daily closing will create a pg_dump backup and generate a closing report "
            f"for **{branch_label}**."
        )

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Perform Daily Closing", type="primary", use_container_width=True,
                         key=f"daily_close_{branch_id}"):
                with st.spinner("Performing daily closing..."):
                    success, report_path, backup_path = perform_daily_close(branch_id=branch_id)
                    if success:
                        st.success(f"Daily closing completed for {branch_label}!")
                        st.info(f"Report: {report_path}")
                        if backup_path:
                            st.info(f"Backup: {backup_path}")
                        with open(report_path, "rb") as f:
                            st.download_button(
                                label="Download Closing Report (PDF)",
                                data=f,
                                file_name=report_path.name,
                                mime="application/pdf",
                                key=f"daily_close_dl_{branch_id}",
                            )
                    else:
                        st.error("Daily closing failed")

        with col2:
            closing_files = sorted(
                CLOSING_DIR.glob(f"daily_close_{_branch_slug(branch_id)}_*.pdf")
            )
            if closing_files:
                latest = max(closing_files, key=lambda x: x.stat().st_mtime)
                st.info(f"Last closing: {latest.name}")
            else:
                st.info(f"No prior closings for {branch_label}")

    # ==============================
    # TAB 2: MONTH-END CLOSING
    # ==============================
    with tab2:
        st.markdown("## Month-End Closing")
        st.caption(f"Close {branch_label}'s transactions for a month")

        col1, col2 = st.columns(2)
        with col1:
            close_year = st.number_input(
                "Year", min_value=2020, max_value=2030,
                value=datetime.now().year, key=f"mc_year_{branch_id}",
            )
        with col2:
            close_month = st.selectbox(
                "Month", range(1, 13), index=datetime.now().month - 1,
                key=f"mc_month_{branch_id}",
            )

        month_data = get_period_data("monthly", close_year, close_month, branch_id=branch_id)

        st.markdown("### Month Summary")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Revenue", f"${month_data['total_revenue']:,.2f}")
        with col2:
            st.metric("Total Income", f"${month_data['total_income']:,.2f}")
        with col3:
            st.metric("Total Expenses", f"${month_data['total_expenses']:,.2f}")
        with col4:
            st.metric("Transactions", month_data['transaction_count'])

        st.markdown("---")
        st.warning(
            f"Month-end closing will create a pg_dump backup and generate a report "
            f"for **{branch_label}** ({close_year}-{close_month:02d})."
        )

        if st.button("Perform Month-End Closing", type="primary", use_container_width=True,
                     key=f"monthly_close_{branch_id}"):
            with st.spinner("Performing month-end closing..."):
                success, report_path, backup_path = perform_monthly_close(
                    close_year, close_month, branch_id=branch_id
                )
                if success:
                    st.success(f"Month-end closing completed for {branch_label}!")
                    st.info(f"Report: {report_path}")
                    if backup_path:
                        st.info(f"Backup: {backup_path}")
                    with open(report_path, "rb") as f:
                        st.download_button(
                            label="Download Monthly Report (PDF)",
                            data=f,
                            file_name=report_path.name,
                            mime="application/pdf",
                            key=f"monthly_close_dl_{branch_id}",
                        )
                else:
                    st.error("Month-end closing failed")

    # ==============================
    # TAB 3: TAX REPORTS
    # ==============================
    with tab3:
        st.markdown("## Tax Reports (ZIMRA Format)")
        st.caption(f"Tax report for {branch_label}")

        col1, col2 = st.columns(2)
        with col1:
            tax_year = st.number_input(
                "Tax Year", min_value=2020, max_value=2030,
                value=datetime.now().year, key=f"tax_year_{branch_id}",
            )
        with col2:
            tax_period = st.selectbox(
                "Tax Period", ["Annual", "Quarterly"],
                key=f"tax_period_{branch_id}",
            )

        if st.button("Generate Tax Report", type="primary", use_container_width=True,
                     key=f"tax_report_{branch_id}"):
            with st.spinner("Generating tax report..."):
                tax_report = generate_tax_report(
                    tax_year, tax_period.lower(), branch_id=branch_id
                )
                st.text_area("Tax Report Preview", tax_report, height=400,
                             key=f"tax_preview_{branch_id}")
                st.download_button(
                    label="Download Tax Report (TXT)",
                    data=tax_report,
                    file_name=(
                        f"zimra_tax_report_{_branch_slug(branch_id)}_"
                        f"{tax_year}_{tax_period.lower()}.txt"
                    ),
                    mime="text/plain",
                    key=f"tax_dl_{branch_id}",
                )

        st.markdown("---")
        st.info(
            "**Tax Information:**\n"
            "- Corporate Tax Rate: 25%\n"
            "- VAT Rate: 15% (if applicable)\n"
            "- Filing deadlines: Check with ZIMRA for current deadlines\n\n"
            "**Note:** This report is for informational purposes. Please consult your accountant for official filing."
        )

    # ==============================
    # TAB 4: CLOSING HISTORY
    # ==============================
    with tab4:
        st.markdown("## Closing History")

        # Filter to the current scope by default
        pattern = "*" if _is_all_branches(branch_id) else f"*_{_branch_slug(branch_id)}_*"
        reports = sorted(CLOSING_DIR.glob(f"*{pattern}*.pdf") if pattern != "*" else CLOSING_DIR.glob("*.pdf"))

        if reports:
            reports_data = []
            for r in reports:
                reports_data.append({
                    "Filename": r.name,
                    "Size": f"{r.stat().st_size / 1024:.1f} KB",
                    "Modified": datetime.fromtimestamp(r.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                })

            df = pd.DataFrame(reports_data)
            st.dataframe(df, use_container_width=True, hide_index=True)

            selected = st.selectbox("Select Report to Download",
                                    [r["Filename"] for r in reports_data],
                                    key=f"closing_select_{branch_id}")
            if selected:
                path = CLOSING_DIR / selected
                with open(path, "rb") as f:
                    st.download_button(
                        label="Download Selected Report",
                        data=f,
                        file_name=selected,
                        mime="application/pdf",
                        key=f"closing_dl_{branch_id}",
                    )
        else:
            st.info(f"No closing reports found for {branch_label}")

        st.markdown("### Backup History")

        backups = [b for b in BACKUP_DIR.iterdir() if b.is_dir()]
        # Show only current scope, unless owner is on All
        if not _is_all_branches(branch_id):
            backups = [b for b in backups if f"_{_branch_slug(branch_id)}_" in b.name]

        if backups:
            backup_data = [
                {
                    "Backup Name": b.name,
                    "Created": datetime.fromtimestamp(b.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                    "Includes": "database.sql" if (b / "database.sql").exists() else "(incomplete)",
                }
                for b in backups
            ]
            st.dataframe(pd.DataFrame(backup_data), use_container_width=True, hide_index=True)
        else:
            st.info(f"No backups found for {branch_label}")


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    financial_closing_dashboard()