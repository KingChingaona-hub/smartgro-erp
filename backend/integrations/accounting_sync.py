# backend/integrations/accounting_sync.py
# Accounting Software Sync — branch-aware.
#
# Branch scoping:
#     branch_id = None          -> session branch
#     branch_id = "HO"/"NAT"/.. -> that single branch
#     branch_id = "__ALL__"     -> aggregate across all branches (owner only)
#
# Every export method and every loader accepts branch_id. Owner gets a scope
# selector; non-owners are locked with a banner. ZIMRA exports include the
# branch name because they are legal filings.

import streamlit as st
import pandas as pd
import json
import csv
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
import io

from backend.core.db_adapter import (
    load_sales,
    load_expenses,
    load_purchases,
    load_customers,
    load_debtors,
    load_products,
    load_branches,
    to_float,
)
from backend.admin.security import get_audit_log


# ==============================
# FILE PATHS
# ==============================
DATA_DIR = Path("data")
EXPORT_DIR = Path("exports")
ACCOUNTING_FILE = DATA_DIR / "accounting_exports.csv"
EXPENSES_FILE = DATA_DIR / "expenses.csv"


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
            key="accounting_branch_scope",
            help="Owners may export one branch or the whole company.",
        )
        if choice == "All Branches":
            return ALL_BRANCHES, "All Branches"
        m = re.search(r"\(([^)]+)\)\s*$", choice)
        code = m.group(1).strip() if m else choice
        return code, choice

    session_branch = _resolve_branch(None)
    label = _branch_label(session_branch)
    st.info(f"Accounting sync locked to your branch: **{label}**")
    return session_branch, label


# ==============================
# INITIALIZATION
# ==============================
def init_accounting_files():
    DATA_DIR.mkdir(exist_ok=True)
    EXPORT_DIR.mkdir(exist_ok=True)

    if not ACCOUNTING_FILE.exists():
        pd.DataFrame(columns=[
            "export_id", "export_date", "branch_id", "export_type",
            "date_from", "date_to", "total_sales", "total_expenses",
            "total_profit", "exported_by", "file_path",
        ]).to_csv(ACCOUNTING_FILE, index=False)
    else:
        try:
            existing = pd.read_csv(ACCOUNTING_FILE)
            if "branch_id" not in existing.columns:
                existing.insert(2, "branch_id", "HO")
                existing.to_csv(ACCOUNTING_FILE, index=False)
        except Exception:
            pd.DataFrame(columns=[
                "export_id", "export_date", "branch_id", "export_type",
                "date_from", "date_to", "total_sales", "total_expenses",
                "total_profit", "exported_by", "file_path",
            ]).to_csv(ACCOUNTING_FILE, index=False)


def load_accounting_exports(branch_id=None):
    init_accounting_files()
    try:
        df = pd.read_csv(ACCOUNTING_FILE)
    except Exception:
        return pd.DataFrame(columns=[
            "export_id", "export_date", "branch_id", "export_type",
            "date_from", "date_to", "total_sales", "total_expenses",
            "total_profit", "exported_by", "file_path",
        ])

    if "branch_id" not in df.columns:
        df["branch_id"] = "HO"

    if branch_id is None:
        return df
    branch_id = _resolve_branch(branch_id)
    if _is_all_branches(branch_id):
        return df
    return df[df["branch_id"].astype(str).str.upper() == str(branch_id).upper()].copy()


def save_accounting_export(export_data):
    df = load_accounting_exports(branch_id=ALL_BRANCHES)
    df = pd.concat([df, pd.DataFrame([export_data])], ignore_index=True)
    df.to_csv(ACCOUNTING_FILE, index=False)


# ==============================
# EXPENSE COLUMN NORMALIZATION
# ==============================
DATE_ALIASES = [
    "date", "expense_date", "date_recorded", "created_at", "recorded_at",
    "transaction_date", "timestamp", "date_created", "entry_date",
]
AMOUNT_ALIASES = [
    "amount", "total", "value", "cost", "total_amount", "expense_amount",
    "price", "sum", "total_cost",
]
CATEGORY_ALIASES = [
    "category", "type", "expense_type", "expense_category", "description_type",
    "kind", "group",
]


def _find_first_column(df, aliases):
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


def _normalize_expenses_df(df, source_label=""):
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
            df[amount_col].astype(str)
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


# ==============================
# EXPENSE LOADERS (branch-scoped)
# ==============================
def _try_load_expenses_from_db(branch_id=None):
    branch_id = _resolve_branch(branch_id)
    try:
        df = _load_scoped(load_expenses, branch_id)
        if df is not None and not df.empty:
            return df, f"database (load_expenses, {branch_id})"
    except Exception as e:
        print(f"[accounting_sync] load_expenses({branch_id}) failed: {e}")
    return None, None


def load_expenses_auto(branch_id=None):
    """
    Load expenses for the branch (or __ALL__). CSV fallbacks only run for a
    specific branch; for __ALL__ we rely on db_adapter.
    """
    branch_id = _resolve_branch(branch_id)

    df, src = _try_load_expenses_from_db(branch_id=branch_id)
    if df is not None:
        normalized, label, diag = _normalize_expenses_df(df, src)
        if not normalized.empty:
            return normalized, label, diag

    # CSV fallbacks are disabled for __ALL__ — they can't be branch-scoped.
    if _is_all_branches(branch_id):
        return pd.DataFrame(), "not found", {
            "source": "not found", "rows": 0, "date_col": None,
            "amount_col": None, "category_col": None,
            "error": "No branch-scoped expenses found.",
        }

    known_paths = [
        EXPENSES_FILE,
        Path("expenses.csv"),
        EXPORT_DIR / "expenses.csv",
        DATA_DIR / "expenses" / "expenses.csv",
    ]
    for p in known_paths:
        try:
            if p.exists() and p.stat().st_size > 0:
                df_csv = pd.read_csv(p)
                if not df_csv.empty:
                    normalized, label, diag = _normalize_expenses_df(
                        df_csv, f"csv ({p})"
                    )
                    if not normalized.empty:
                        return normalized, label, diag
        except Exception as e:
            print(f"[accounting_sync] CSV read failed at {p}: {e}")

    return pd.DataFrame(), "not found", {
        "source": "not found", "rows": 0, "date_col": None,
        "amount_col": None, "category_col": None,
        "error": "No expense source returned data.",
    }


@st.cache_data(ttl=120, show_spinner=False)
def _cached_load_expenses_auto(branch_id):
    df, src, diag = load_expenses_auto(branch_id=branch_id)
    return df, src, diag


def get_expenses_source(branch_id=None, refresh: bool = False):
    branch_id = _resolve_branch(branch_id)
    if refresh:
        try:
            _cached_load_expenses_auto.clear()
        except Exception:
            pass
    return _cached_load_expenses_auto(branch_id)


def load_expenses_from_csv():
    """Backwards-compat helper — delegates to the multi-source loader."""
    df, _src, _diag = load_expenses_auto()
    return df


# ==============================
# SALES / EXPENSES FOR A PERIOD (scoped)
# ==============================
def get_sales_data(date_from, date_to, branch_id=None):
    """
    Sales for the period, scoped to a branch, deduplicated by receipt.
    """
    branch_id = _resolve_branch(branch_id)
    sales_df = _load_scoped(load_sales, branch_id)

    if sales_df is None or sales_df.empty:
        return pd.DataFrame()

    date_col = _find_first_column(sales_df, ["sale_date", "date", "transaction_date", "created_at"])
    if date_col is None:
        return pd.DataFrame()

    sales_df = sales_df.copy()
    sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
    sales_df = sales_df.dropna(subset=[date_col])

    start_dt = pd.to_datetime(date_from)
    end_dt = pd.to_datetime(date_to) + timedelta(days=1) - timedelta(seconds=1)

    filtered = sales_df[(sales_df[date_col] >= start_dt) & (sales_df[date_col] <= end_dt)]

    receipt_col = _find_first_column(filtered, ["receipt_no", "receipt", "transaction_id", "order_id"])
    if not filtered.empty and receipt_col:
        filtered = filtered.drop_duplicates(subset=[receipt_col])

    return filtered


def get_expenses_data(date_from, date_to, expenses_df=None, branch_id=None):
    """Expenses for the period, scoped to a branch."""
    branch_id = _resolve_branch(branch_id)

    if expenses_df is None or expenses_df.empty:
        expenses_df, _src, _diag = get_expenses_source(branch_id=branch_id)

    if expenses_df is None or expenses_df.empty:
        return pd.DataFrame()

    if "date" not in expenses_df.columns or "amount" not in expenses_df.columns:
        return expenses_df

    expenses_df = expenses_df.copy()
    expenses_df["date"] = pd.to_datetime(expenses_df["date"], errors="coerce")
    expenses_df = expenses_df.dropna(subset=["date"])

    start_dt = pd.to_datetime(date_from)
    end_dt = pd.to_datetime(date_to) + timedelta(days=1) - timedelta(seconds=1)

    return expenses_df[(expenses_df["date"] >= start_dt) & (expenses_df["date"] <= end_dt)]


# ==============================
# COMMON EXPORT HELPERS
# ==============================
def _col(df, candidates, default=None):
    if df is None or df.empty:
        return default
    for c in candidates:
        if c in df.columns:
            return c
    return default


def _safe_branch_code(branch_id):
    if _is_all_branches(branch_id):
        return "ALL"
    return _branch_slug(branch_id)


def _fmt_date(value, fmt="%Y-%m-%d"):
    if value is None:
        return datetime.now().strftime(fmt)
    try:
        if hasattr(value, "strftime"):
            return value.strftime(fmt)
        return pd.to_datetime(value).strftime(fmt)
    except Exception:
        return datetime.now().strftime(fmt)


# ==============================
# QUICKBOOKS EXPORT
# ==============================
def export_to_quickbooks(sales_df, expenses_df, date_from, date_to, branch_id=None):
    branch_id = _resolve_branch(branch_id)
    label = _branch_label(branch_id)

    sales_export = []
    total_col = _col(sales_df, ["final_total", "total", "amount", "sale_amount"])
    date_col = _col(sales_df, ["sale_date", "date", "transaction_date"])
    customer_col = _col(sales_df, ["customer", "customer_name"]) or "Walk-in"
    receipt_col = _col(sales_df, ["receipt_no", "receipt", "transaction_id"])

    if sales_df is not None and not sales_df.empty and total_col:
        for _, sale in sales_df.iterrows():
            sales_export.append({
                "TRNSID": str(sale.get(receipt_col, "")) if receipt_col else "",
                "TRNSTYPE": "INVOICE",
                "DATE": _fmt_date(sale.get(date_col), "%m/%d/%Y"),
                "ACCNT": "Sales",
                "NAME": str(sale.get(customer_col, "Walk-in")),
                "AMOUNT": to_float(sale.get(total_col, 0)),
                "DOCNUM": str(sale.get(receipt_col, "")) if receipt_col else "",
                "MEMO": f"Sale of products [{_safe_branch_code(branch_id)}]",
                "PAID": to_float(sale.get(total_col, 0)),
            })

    if not sales_export:
        return ""

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["TRNSID", "TRNSTYPE", "DATE", "ACCNT", "NAME",
                    "AMOUNT", "DOCNUM", "MEMO", "PAID"],
    )
    writer.writeheader()
    writer.writerows(sales_export)
    return output.getvalue()


# ==============================
# PASTEL PARTNER EXPORT
# ==============================
def export_to_pastel(sales_df, expenses_df, date_from, date_to, branch_id=None):
    branch_id = _resolve_branch(branch_id)
    total_col = _col(sales_df, ["final_total", "total", "amount", "sale_amount"])
    date_col = _col(sales_df, ["sale_date", "date", "transaction_date"])
    customer_col = _col(sales_df, ["customer", "customer_name"]) or "Walk-in"
    receipt_col = _col(sales_df, ["receipt_no", "receipt", "transaction_id"])

    sales_export = []
    if sales_df is not None and not sales_df.empty and total_col:
        for _, sale in sales_df.iterrows():
            sales_export.append({
                "Transaction Date": _fmt_date(sale.get(date_col)),
                "Account Reference": str(sale.get(receipt_col, "")) if receipt_col else "",
                "Account Name": str(sale.get(customer_col, "Walk-in")),
                "Sales Amount": to_float(sale.get(total_col, 0)),
                "Tax Amount": 0,
                "Total Amount": to_float(sale.get(total_col, 0)),
                "Payment Method": str(sale.get("payment_method", "CASH")),
                "Description": f"Sale receipt {sale.get(receipt_col, '') if receipt_col else ''} [{_safe_branch_code(branch_id)}]",
                "Branch": _safe_branch_code(branch_id),
            })
    if not sales_export:
        return ""
    return pd.DataFrame(sales_export).to_csv(index=False)


# ==============================
# XERO EXPORT
# ==============================
def export_to_xero(sales_df, expenses_df, date_from, date_to, branch_id=None):
    branch_id = _resolve_branch(branch_id)
    total_col = _col(sales_df, ["final_total", "total", "amount", "sale_amount"])
    date_col = _col(sales_df, ["sale_date", "date", "transaction_date"])
    customer_col = _col(sales_df, ["customer", "customer_name"]) or "Walk-in"
    receipt_col = _col(sales_df, ["receipt_no", "receipt", "transaction_id"])

    sales_export = []
    if sales_df is not None and not sales_df.empty and total_col:
        for _, sale in sales_df.iterrows():
            sales_export.append({
                "InvoiceDate": _fmt_date(sale.get(date_col)),
                "InvoiceNumber": str(sale.get(receipt_col, "")) if receipt_col else "",
                "ContactName": str(sale.get(customer_col, "Walk-in")),
                "TotalAmount": to_float(sale.get(total_col, 0)),
                "PaymentMethod": str(sale.get("payment_method", "CASH")),
                "Description": f"Sale receipt {sale.get(receipt_col, '') if receipt_col else ''} [{_safe_branch_code(branch_id)}]",
                "Branch": _safe_branch_code(branch_id),
            })
    if not sales_export:
        return ""
    return pd.DataFrame(sales_export).to_csv(index=False)


# ==============================
# SAGE ONE EXPORT
# ==============================
def export_to_sage(sales_df, expenses_df, date_from, date_to, branch_id=None):
    branch_id = _resolve_branch(branch_id)
    total_col = _col(sales_df, ["final_total", "total", "amount", "sale_amount"])
    date_col = _col(sales_df, ["sale_date", "date", "transaction_date"])
    receipt_col = _col(sales_df, ["receipt_no", "receipt", "transaction_id"])

    sales_export = []
    if sales_df is not None and not sales_df.empty and total_col:
        for _, sale in sales_df.iterrows():
            sales_export.append({
                "Date": _fmt_date(sale.get(date_col)),
                "Reference": str(sale.get(receipt_col, "")) if receipt_col else "",
                "Amount": to_float(sale.get(total_col, 0)),
                "Payment Method": str(sale.get("payment_method", "CASH")),
                "Branch": _safe_branch_code(branch_id),
            })
    if not sales_export:
        return ""
    return pd.DataFrame(sales_export).to_csv(index=False)


# ==============================
# ZIMRA E-FILING EXPORT
# ==============================
def export_to_zimra(sales_df, date_from, date_to, branch_id=None):
    """
    ZIMRA e-filing format, scoped to a branch.

    The export includes a Branch row because VAT registrations can be per-branch.
    """
    branch_id = _resolve_branch(branch_id)
    label = _branch_label(branch_id)

    total_col = _col(sales_df, ["final_total", "total", "amount", "sale_amount"])
    total_sales = (
        to_float(pd.to_numeric(sales_df[total_col], errors="coerce").fillna(0).sum())
        if total_col and sales_df is not None and not sales_df.empty else 0
    )

    vat_amount = total_sales * 0.15
    vat_exclusive = total_sales / 1.15 if total_sales > 0 else 0

    date_from_str = _fmt_date(date_from)
    date_to_str = _fmt_date(date_to)

    zimra_data = {
        "Branch": label,
        "Period Start": date_from_str,
        "Period End": date_to_str,
        "Total Sales (Excl VAT)": vat_exclusive,
        "VAT Output": vat_amount,
        "Total Sales (Incl VAT)": total_sales,
        "VAT Input": 0,
        "Net VAT Payable": vat_amount,
        "Return Date": datetime.now().strftime("%Y-%m-%d"),
    }

    return pd.DataFrame([zimra_data]).to_csv(index=False)


# ==============================
# AUDIT TRAIL EXPORT
# ==============================
def export_audit_trail(audit_df, date_from, date_to, branch_id=None):
    branch_id = _resolve_branch(branch_id)
    if audit_df is None or audit_df.empty:
        return ""

    cols = ["timestamp", "user", "action", "details", "ip_address", "branch"]
    available = [c for c in cols if c in audit_df.columns]
    audit_export = audit_df[available].copy()

    # Filter to the current branch when a `branch` column exists.
    if "branch" in audit_export.columns and not _is_all_branches(branch_id):
        audit_export = audit_export[
            audit_export["branch"].astype(str).str.upper() == str(branch_id).upper()
        ]

    if "timestamp" in audit_export.columns:
        audit_export["timestamp"] = pd.to_datetime(
            audit_export["timestamp"], errors="coerce"
        ).dt.strftime("%Y-%m-%d %H:%M:%S")

    return audit_export.to_csv(index=False)


# ==============================
# DASHBOARD
# ==============================
def accounting_sync_dashboard(branch_id=None):
    st.title("Accounting Software Sync")
    st.caption("Export real data to QuickBooks, Pastel, Xero, Sage, and ZIMRA — branch-scoped")

    role = st.session_state.get("role", "cashier")
    if role not in ["owner", "manager"]:
        st.error("Access Denied. Only owners and managers can access accounting sync.")
        return

    try:
        branches_df = load_branches()
    except Exception:
        branches_df = pd.DataFrame()

    if branch_id is None:
        branch_id, branch_label = _branch_scope_selector(branches_df)
    else:
        branch_label = _branch_label(branch_id)

    st.caption(f"Exporting for: **{branch_label}**")

    init_accounting_files()

    # ==============================
    # DATE RANGE
    # ==============================
    st.markdown("### Select Export Period")
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        date_from = st.date_input(
            "From Date", datetime.now() - timedelta(days=30),
            key=f"acct_from_{branch_id}",
        )
    with col2:
        date_to = st.date_input(
            "To Date", datetime.now(),
            key=f"acct_to_{branch_id}",
        )
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        refresh_expenses = st.button(
            "Refresh Expenses", use_container_width=True,
            key=f"acct_refresh_{branch_id}",
        )

    # ==============================
    # LOAD DATA (scoped)
    # ==============================
    with st.spinner("Loading data..."):
        sales_df = get_sales_data(date_from, date_to, branch_id=branch_id)
        all_expenses_df, expenses_source, expenses_diag = get_expenses_source(
            branch_id=branch_id, refresh=refresh_expenses
        )
        expenses_df = get_expenses_data(
            date_from, date_to, all_expenses_df, branch_id=branch_id
        )

    # ==============================
    # EXPENSES DIAGNOSTICS
    # ==============================
    with st.expander(f"Expense source: {expenses_source}", expanded=False):
        if all_expenses_df is None or all_expenses_df.empty:
            st.warning(f"No expenses could be loaded for {branch_label}.")
            if expenses_diag.get("error"):
                st.caption(f"Reason: {expenses_diag['error']}")
        else:
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("Source", expenses_source.split("(")[0].strip()[:20])
            with c2:
                st.metric("Total Rows Loaded", expenses_diag.get("rows", 0))
            with c3:
                st.metric("Date Column", str(expenses_diag.get("date_col")))
            with c4:
                st.metric("Amount Column", str(expenses_diag.get("amount_col")))
            st.caption(
                f"Rows in selected period ({date_from} → {date_to}): **{len(expenses_df)}**"
            )

    # ==============================
    # REAL METRICS (scoped)
    # ==============================
    total_col = _col(sales_df, ["final_total", "total", "amount", "sale_amount"])
    profit_col = _col(sales_df, ["profit", "gross_profit"])

    total_sales = (
        to_float(pd.to_numeric(sales_df[total_col], errors="coerce").fillna(0).sum())
        if total_col and sales_df is not None and not sales_df.empty else 0
    )
    total_expenses = (
        to_float(pd.to_numeric(expenses_df["amount"], errors="coerce").fillna(0).sum())
        if "amount" in expenses_df.columns and not expenses_df.empty else 0
    )
    total_profit = (
        to_float(pd.to_numeric(sales_df[profit_col], errors="coerce").fillna(0).sum())
        if profit_col and sales_df is not None and not sales_df.empty else 0
    )
    transaction_count = len(sales_df)

    st.markdown(f"### Period Summary — {branch_label}")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Sales", f"${total_sales:,.2f}")
    with col2:
        st.metric("Total Expenses", f"${total_expenses:,.2f}")
    with col3:
        st.metric("Total Profit", f"${total_profit:,.2f}")
    with col4:
        st.metric("Transactions", transaction_count)

    st.markdown("---")

    # ==============================
    # EXPORT OPTIONS
    # ==============================
    st.markdown("### Export to Accounting Software")

    col1, col2 = st.columns(2)
    with col1:
        export_format = st.selectbox(
            "Select Export Format",
            [
                "QuickBooks (IIF)",
                "Pastel Partner (CSV)",
                "Xero (CSV)",
                "Sage One (CSV)",
                "ZIMRA e-filing (CSV)",
                "Audit Trail (CSV)",
            ],
            key=f"acct_format_{branch_id}",
        )
    with col2:
        include_expenses = st.checkbox(
            "Include Expenses", value=True, key=f"acct_inc_exp_{branch_id}"
        )

    # ==============================
    # GENERATE EXPORT
    # ==============================
    if st.button("Generate Export File", type="primary", use_container_width=True,
                 key=f"acct_gen_{branch_id}"):
        if sales_df.empty and export_format != "Audit Trail (CSV)":
            st.error(f"No sales data for the selected period in {branch_label}.")
        else:
            with st.spinner(f"Generating {export_format} for {branch_label}..."):
                export_data = None
                export_filename = None
                slug = _safe_branch_code(branch_id)
                exp_arg = expenses_df if include_expenses else pd.DataFrame()

                if export_format == "QuickBooks (IIF)":
                    export_data = export_to_quickbooks(
                        sales_df, exp_arg, date_from, date_to, branch_id=branch_id
                    )
                    export_filename = (
                        f"quickbooks_{slug}_{date_from.strftime('%Y%m%d')}_"
                        f"{date_to.strftime('%Y%m%d')}.iif"
                    )
                elif export_format == "Pastel Partner (CSV)":
                    export_data = export_to_pastel(
                        sales_df, exp_arg, date_from, date_to, branch_id=branch_id
                    )
                    export_filename = (
                        f"pastel_{slug}_{date_from.strftime('%Y%m%d')}_"
                        f"{date_to.strftime('%Y%m%d')}.csv"
                    )
                elif export_format == "Xero (CSV)":
                    export_data = export_to_xero(
                        sales_df, exp_arg, date_from, date_to, branch_id=branch_id
                    )
                    export_filename = (
                        f"xero_{slug}_{date_from.strftime('%Y%m%d')}_"
                        f"{date_to.strftime('%Y%m%d')}.csv"
                    )
                elif export_format == "Sage One (CSV)":
                    export_data = export_to_sage(
                        sales_df, exp_arg, date_from, date_to, branch_id=branch_id
                    )
                    export_filename = (
                        f"sage_{slug}_{date_from.strftime('%Y%m%d')}_"
                        f"{date_to.strftime('%Y%m%d')}.csv"
                    )
                elif export_format == "ZIMRA e-filing (CSV)":
                    export_data = export_to_zimra(
                        sales_df, date_from, date_to, branch_id=branch_id
                    )
                    export_filename = (
                        f"zimra_{slug}_{date_from.strftime('%Y%m%d')}_"
                        f"{date_to.strftime('%Y%m%d')}.csv"
                    )
                elif export_format == "Audit Trail (CSV)":
                    audit_df = get_audit_log(365)
                    export_data = export_audit_trail(
                        audit_df, date_from, date_to, branch_id=branch_id
                    )
                    export_filename = (
                        f"audit_trail_{slug}_{date_from.strftime('%Y%m%d')}_"
                        f"{date_to.strftime('%Y%m%d')}.csv"
                    )

                if export_data:
                    save_accounting_export({
                        "export_id": f"EXP{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        "export_date": datetime.now().isoformat(),
                        "branch_id": slug,
                        "export_type": export_format,
                        "date_from": date_from.isoformat(),
                        "date_to": date_to.isoformat(),
                        "total_sales": total_sales,
                        "total_expenses": total_expenses,
                        "total_profit": total_profit,
                        "exported_by": st.session_state.get("username", "system"),
                        "file_path": str(EXPORT_DIR / export_filename),
                    })

                    st.success(
                        f"{export_format} export ready for {branch_label}: "
                        f"{transaction_count} transactions, Revenue: ${total_sales:,.2f}"
                    )

                    st.download_button(
                        label="Download Export File",
                        data=(
                            export_data.encode('utf-8')
                            if isinstance(export_data, str) else export_data
                        ),
                        file_name=export_filename,
                        mime="text/csv",
                        use_container_width=True,
                        key=f"acct_dl_{branch_id}",
                    )
                    st.balloons()
                else:
                    st.error(f"No data to export for {export_format} in {branch_label}")

    # ==============================
    # EXPORT HISTORY (scoped)
    # ==============================
    st.markdown("---")
    st.markdown("### Export History")

    exports_df = load_accounting_exports(branch_id=branch_id)
    if exports_df.empty:
        st.info(f"No export history for {branch_label}")
    else:
        exports_df = exports_df.copy()
        if "export_date" in exports_df.columns:
            exports_df["export_date"] = pd.to_datetime(
                exports_df["export_date"], errors="coerce"
            ).dt.strftime("%Y-%m-%d %H:%M")

        display_cols = [
            c for c in [
                "export_date", "branch_id", "export_type",
                "date_from", "date_to", "total_sales", "exported_by",
            ] if c in exports_df.columns
        ]
        st.dataframe(
            exports_df[display_cols].head(20),
            use_container_width=True,
            hide_index=True,
            column_config={
                "total_sales": st.column_config.NumberColumn("Total Sales", format="$%.2f"),
            },
        )


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    accounting_sync_dashboard()