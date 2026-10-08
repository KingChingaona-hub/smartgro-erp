# backend/integrations/accounting_sync.py
import streamlit as st
import pandas as pd
import json
import csv
import os
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
    to_float
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
# INITIALIZATION
# ==============================
def init_accounting_files():
    """Initialize accounting export files"""
    DATA_DIR.mkdir(exist_ok=True)
    EXPORT_DIR.mkdir(exist_ok=True)
    
    if not ACCOUNTING_FILE.exists():
        df = pd.DataFrame(columns=[
            "export_id", "export_date", "export_type", "date_from", "date_to",
            "total_sales", "total_expenses", "total_profit", "exported_by", "file_path"
        ])
        df.to_csv(ACCOUNTING_FILE, index=False)


def load_accounting_exports():
    """Load accounting export history"""
    init_accounting_files()
    try:
        return pd.read_csv(ACCOUNTING_FILE)
    except:
        return pd.DataFrame(columns=[
            "export_id", "export_date", "export_type", "date_from", "date_to",
            "total_sales", "total_expenses", "total_profit", "exported_by", "file_path"
        ])


def save_accounting_export(export_data):
    """Save export record"""
    df = load_accounting_exports()
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
    """Return the first column name (case-insensitive) present in the aliases list."""
    if df is None or df.empty:
        return None
    lower_map = {str(c).lower().strip(): c for c in df.columns}
    for alias in aliases:
        if alias in lower_map:
            return lower_map[alias]
    # Fallback substring match
    for col_lower, col_orig in lower_map.items():
        for alias in aliases:
            if alias in col_lower:
                return col_orig
    return None


def _normalize_expenses_df(df, source_label=""):
    """
    Normalize an expenses DataFrame so it always has:
      - a datetime column named 'date'
      - a numeric column named 'amount'
      - a 'category' column (if available)
    Returns (normalized_df, source_label, diagnostics_dict)
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

    # Coerce date
    if date_col is not None:
        df["date"] = pd.to_datetime(df[date_col], errors="coerce")
    else:
        # Try to derive from index or leave NaT
        df["date"] = pd.NaT

    # Coerce amount
    if amount_col is not None:
        # Remove commas & currency symbols before numeric conversion
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

    # Category
    if category_col is not None:
        df["category"] = df[category_col].astype(str)
    else:
        df["category"] = "Uncategorized"

    diagnostics["rows"] = len(df)

    return df, source_label, diagnostics


# ==============================
# EXPENSE LOADERS - MULTI-SOURCE
# ==============================
def _try_load_expenses_from_db():
    """Try loading expenses from the database adapter."""
    try:
        df = load_expenses()
        if df is not None and not df.empty:
            return df, "database (load_expenses)"
    except Exception as e:
        print(f"[accounting_sync] load_expenses() failed: {e}")
    return None, None


def _try_load_expenses_from_csv(path: Path):
    """Try loading expenses from a specific CSV path."""
    try:
        if path.exists() and path.stat().st_size > 0:
            df = pd.read_csv(path)
            if not df.empty:
                return df, f"csv ({path})"
    except Exception as e:
        print(f"[accounting_sync] CSV read failed at {path}: {e}")
    return None, None


def _discover_expense_csvs():
    """Search common locations for any expenses*.csv file."""
    candidates = []
    search_dirs = [DATA_DIR, Path("."), EXPORT_DIR, Path("backend"), Path("database")]
    for d in search_dirs:
        try:
            if d.exists():
                for p in d.glob("expenses*.csv"):
                    candidates.append(p)
        except Exception:
            continue
    return candidates


def load_expenses_auto():
    """
    Load expenses from the first source that returns non-empty data.
    Returns:
        (normalized_df, source_label, diagnostics_dict)
    """
    # 1) Database first
    df, src = _try_load_expenses_from_db()
    if df is not None:
        normalized, label, diag = _normalize_expenses_df(df, src)
        if not normalized.empty:
            return normalized, label, diag

    # 2) Known CSVs
    known_paths = [
        EXPENSES_FILE,
        Path("expenses.csv"),
        EXPORT_DIR / "expenses.csv",
        DATA_DIR / "expenses" / "expenses.csv",
    ]
    for p in known_paths:
        df, src = _try_load_expenses_from_csv(p)
        if df is not None:
            normalized, label, diag = _normalize_expenses_df(df, src)
            if not normalized.empty:
                return normalized, label, diag

    # 3) Any expenses*.csv discovered
    for p in _discover_expense_csvs():
        df, src = _try_load_expenses_from_csv(p)
        if df is not None:
            normalized, label, diag = _normalize_expenses_df(df, src)
            if not normalized.empty:
                return normalized, label, diag

    # Nothing found
    return pd.DataFrame(), "not found", {
        "source": "not found",
        "rows": 0,
        "date_col": None,
        "amount_col": None,
        "category_col": None,
        "error": "No expense source returned data.",
    }


@st.cache_data(ttl=120, show_spinner=False)
def _cached_load_expenses_auto():
    """
    Cached version of the auto-loader. Returns serializable payload:
        (df, source_label, diagnostics_dict)
    """
    df, src, diag = load_expenses_auto()
    return df, src, diag


def get_expenses_source(refresh: bool = False):
    """Return (df, source_label, diagnostics) using the cache unless refresh=True."""
    if refresh:
        try:
            _cached_load_expenses_auto.clear()
        except Exception:
            pass
    return _cached_load_expenses_auto()


def load_expenses_from_csv():
    """
    Kept for backwards compatibility. Now delegates to the multi-source loader.
    """
    df, _src, _diag = load_expenses_auto()
    return df


# ==============================
# GET REAL SALES DATA - FIXED WITH DEDUPLICATION
# ==============================
def get_sales_data(date_from, date_to):
    """
    Get sales data for the period - WITH DEDUPLICATION
    Uses drop_duplicates on receipt_no to avoid revenue duplication
    """
    
    sales_df = load_sales()
    
    if sales_df.empty:
        return pd.DataFrame()
    
    date_col = None
    for col in ["sale_date", "date", "transaction_date", "created_at"]:
        if col in sales_df.columns:
            date_col = col
            break
    
    if date_col is None:
        return pd.DataFrame()
    
    sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
    sales_df = sales_df.dropna(subset=[date_col])
    
    start_dt = pd.to_datetime(date_from)
    end_dt = pd.to_datetime(date_to) + timedelta(days=1) - timedelta(seconds=1)
    
    filtered = sales_df[(sales_df[date_col] >= start_dt) & (sales_df[date_col] <= end_dt)]
    
    # DEDUPLICATE BY RECEIPT_NO TO AVOID REVENUE DUPLICATION
    if not filtered.empty and "receipt_no" in filtered.columns:
        filtered = filtered.drop_duplicates(subset=["receipt_no"])
    
    return filtered


def get_expenses_data(date_from, date_to, expenses_df=None):
    """
    Get expenses data for the period.

    If expenses_df is provided (from the multi-source loader), it will be
    filtered directly. Otherwise, it falls back to the auto loader.
    """
    if expenses_df is None or expenses_df.empty:
        expenses_df, _src, _diag = get_expenses_source()

    if expenses_df.empty:
        return pd.DataFrame()

    if "date" not in expenses_df.columns or "amount" not in expenses_df.columns:
        return expenses_df

    # Ensure date is a datetime (it already is from the normalizer)
    try:
        expenses_df = expenses_df.copy()
        expenses_df["date"] = pd.to_datetime(expenses_df["date"], errors="coerce")
        expenses_df = expenses_df.dropna(subset=["date"])
    except Exception:
        pass

    start_dt = pd.to_datetime(date_from)
    end_dt = pd.to_datetime(date_to) + timedelta(days=1) - timedelta(seconds=1)

    filtered = expenses_df[
        (expenses_df["date"] >= start_dt) & (expenses_df["date"] <= end_dt)
    ]
    return filtered


# ==============================
# QUICKBOOKS EXPORT
# ==============================
def export_to_quickbooks(sales_df, expenses_df, date_from, date_to):
    """Export data to QuickBooks Online format (IIF)"""
    
    sales_export = []
    
    total_col = "final_total" if "final_total" in sales_df.columns else "total" if "total" in sales_df.columns else None
    date_col = "sale_date" if "sale_date" in sales_df.columns else "date" if "date" in sales_df.columns else None
    customer_col = "customer" if "customer" in sales_df.columns else "customer_name" if "customer_name" in sales_df.columns else "Walk-in"
    
    if not sales_df.empty and total_col:
        for _, sale in sales_df.iterrows():
            sale_date = sale.get(date_col, datetime.now())
            if hasattr(sale_date, 'strftime'):
                date_str = sale_date.strftime("%m/%d/%Y")
            else:
                date_str = datetime.now().strftime("%m/%d/%Y")
            
            sales_export.append({
                "TRNSID": str(sale.get("receipt_no", "")),
                "TRNSTYPE": "INVOICE",
                "DATE": date_str,
                "ACCNT": "Sales",
                "NAME": str(sale.get(customer_col, "Walk-in")),
                "AMOUNT": to_float(sale.get(total_col, 0)),
                "DOCNUM": str(sale.get("receipt_no", "")),
                "MEMO": f"Sale of products",
                "PAID": to_float(sale.get(total_col, 0))
            })
    
    if not sales_export:
        return ""
    
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["TRNSID", "TRNSTYPE", "DATE", "ACCNT", "NAME", "AMOUNT", "DOCNUM", "MEMO", "PAID"])
    writer.writeheader()
    writer.writerows(sales_export)
    
    return output.getvalue()


# ==============================
# PASTEL PARTNER EXPORT
# ==============================
def export_to_pastel(sales_df, expenses_df, date_from, date_to):
    """Export to Pastel Partner format"""
    
    total_col = "final_total" if "final_total" in sales_df.columns else "total" if "total" in sales_df.columns else None
    date_col = "sale_date" if "sale_date" in sales_df.columns else "date" if "date" in sales_df.columns else None
    customer_col = "customer" if "customer" in sales_df.columns else "customer_name" if "customer_name" in sales_df.columns else "Walk-in"
    
    sales_export = []
    
    if not sales_df.empty and total_col:
        for _, sale in sales_df.iterrows():
            sale_date = sale.get(date_col, datetime.now())
            if hasattr(sale_date, 'strftime'):
                date_str = sale_date.strftime("%Y-%m-%d")
            else:
                date_str = datetime.now().strftime("%Y-%m-%d")
            
            sales_export.append({
                "Transaction Date": date_str,
                "Account Reference": str(sale.get("receipt_no", "")),
                "Account Name": str(sale.get(customer_col, "Walk-in")),
                "Sales Amount": to_float(sale.get(total_col, 0)),
                "Tax Amount": 0,
                "Total Amount": to_float(sale.get(total_col, 0)),
                "Payment Method": str(sale.get("payment_method", "CASH")),
                "Description": f"Sale receipt {sale.get('receipt_no', '')}"
            })
    
    if not sales_export:
        return ""
    
    df = pd.DataFrame(sales_export)
    return df.to_csv(index=False)


# ==============================
# XERO EXPORT
# ==============================
def export_to_xero(sales_df, expenses_df, date_from, date_to):
    """Export to Xero format"""
    
    total_col = "final_total" if "final_total" in sales_df.columns else "total" if "total" in sales_df.columns else None
    date_col = "sale_date" if "sale_date" in sales_df.columns else "date" if "date" in sales_df.columns else None
    customer_col = "customer" if "customer" in sales_df.columns else "customer_name" if "customer_name" in sales_df.columns else "Walk-in"
    
    sales_export = []
    
    if not sales_df.empty and total_col:
        for _, sale in sales_df.iterrows():
            sale_date = sale.get(date_col, datetime.now())
            if hasattr(sale_date, 'strftime'):
                date_str = sale_date.strftime("%Y-%m-%d")
            else:
                date_str = datetime.now().strftime("%Y-%m-%d")
            
            sales_export.append({
                "InvoiceDate": date_str,
                "InvoiceNumber": str(sale.get("receipt_no", "")),
                "ContactName": str(sale.get(customer_col, "Walk-in")),
                "TotalAmount": to_float(sale.get(total_col, 0)),
                "PaymentMethod": str(sale.get("payment_method", "CASH")),
                "Description": f"Sale receipt {sale.get('receipt_no', '')}"
            })
    
    if not sales_export:
        return ""
    
    df = pd.DataFrame(sales_export)
    return df.to_csv(index=False)


# ==============================
# SAGE ONE EXPORT
# ==============================
def export_to_sage(sales_df, expenses_df, date_from, date_to):
    """Export to Sage One format"""
    
    total_col = "final_total" if "final_total" in sales_df.columns else "total" if "total" in sales_df.columns else None
    date_col = "sale_date" if "sale_date" in sales_df.columns else "date" if "date" in sales_df.columns else None
    
    sales_export = []
    
    if not sales_df.empty and total_col:
        for _, sale in sales_df.iterrows():
            sale_date = sale.get(date_col, datetime.now())
            if hasattr(sale_date, 'strftime'):
                date_str = sale_date.strftime("%Y-%m-%d")
            else:
                date_str = datetime.now().strftime("%Y-%m-%d")
            
            sales_export.append({
                "Date": date_str,
                "Reference": str(sale.get("receipt_no", "")),
                "Amount": to_float(sale.get(total_col, 0)),
                "Payment Method": str(sale.get("payment_method", "CASH"))
            })
    
    if not sales_export:
        return ""
    
    df = pd.DataFrame(sales_export)
    return df.to_csv(index=False)


# ==============================
# ZIMRA E-FILING EXPORT
# ==============================
def export_to_zimra(sales_df, date_from, date_to):
    """Export to ZIMRA e-filing format - Uses unduplicated revenue"""
    
    total_col = "final_total" if "final_total" in sales_df.columns else "total" if "total" in sales_df.columns else None
    
    total_sales = to_float(sales_df[total_col].sum()) if total_col and not sales_df.empty else 0
    vat_amount = total_sales * 0.15
    vat_exclusive = total_sales / 1.15 if total_sales > 0 else 0
    
    date_from_str = date_from.strftime("%Y-%m-%d") if hasattr(date_from, 'strftime') else str(date_from)
    date_to_str = date_to.strftime("%Y-%m-%d") if hasattr(date_to, 'strftime') else str(date_to)
    
    zimra_data = {
        "Period Start": date_from_str,
        "Period End": date_to_str,
        "Total Sales (Excl VAT)": vat_exclusive,
        "VAT Output": vat_amount,
        "Total Sales (Incl VAT)": total_sales,
        "VAT Input": 0,
        "Net VAT Payable": vat_amount,
        "Return Date": datetime.now().strftime("%Y-%m-%d")
    }
    
    df = pd.DataFrame([zimra_data])
    return df.to_csv(index=False)


# ==============================
# AUDIT TRAIL EXPORT
# ==============================
def export_audit_trail(audit_df, date_from, date_to):
    """Export audit trail"""
    
    if audit_df.empty:
        return ""
    
    audit_export = audit_df[["timestamp", "user", "action", "details", "ip_address", "branch"]].copy()
    audit_export["timestamp"] = pd.to_datetime(audit_export["timestamp"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    
    return audit_export.to_csv(index=False)


# ==============================
# ACCOUNTING DASHBOARD
# ==============================
def accounting_sync_dashboard():
    """Accounting Software Sync Dashboard with REAL data"""
    
    st.title("Accounting Software Sync")
    st.caption("Export REAL data to QuickBooks, Pastel, Xero, Sage, and ZIMRA")
    
    role = st.session_state.get("role", "cashier")
    
    if role not in ["owner", "manager"]:
        st.error("Access Denied. Only owners and managers can access accounting sync.")
        return
    
    init_accounting_files()
    
    # ==============================
    # DATE RANGE SELECTION
    # ==============================
    st.markdown("### Select Export Period")
    
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        date_from = st.date_input("From Date", datetime.now() - timedelta(days=30))
    with col2:
        date_to = st.date_input("To Date", datetime.now())
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        refresh_expenses = st.button("🔄 Refresh Expenses", use_container_width=True)
    
    # ==============================
    # LOAD REAL DATA
    # ==============================
    with st.spinner("Loading data..."):
        sales_df = get_sales_data(date_from, date_to)

        all_expenses_df, expenses_source, expenses_diag = get_expenses_source(
            refresh=refresh_expenses
        )
        expenses_df = get_expenses_data(date_from, date_to, all_expenses_df)
    
    # ==============================
    # EXPENSES SOURCE DIAGNOSTICS
    # ==============================
    with st.expander(f"📂 Expense source: {expenses_source}", expanded=False):
        if all_expenses_df is None or all_expenses_df.empty:
            st.warning(
                "No expenses could be loaded from any source. "
                "Checked: database (`load_expenses`), `data/expenses.csv`, "
                "`expenses.csv`, `exports/expenses.csv`, and any `expenses*.csv` "
                "in `data/`, project root, `exports/`, `backend/`, `database/`."
            )
            if expenses_diag.get("error"):
                st.caption(f"Reason: {expenses_diag['error']}")
        else:
            diag_col1, diag_col2, diag_col3, diag_col4 = st.columns(4)
            with diag_col1:
                st.metric("Source", expenses_source.split("(")[0].strip()[:20])
            with diag_col2:
                st.metric("Total Rows Loaded", expenses_diag.get("rows", 0))
            with diag_col3:
                st.metric("Date Column", str(expenses_diag.get("date_col")))
            with diag_col4:
                st.metric("Amount Column", str(expenses_diag.get("amount_col")))

            if "category" in all_expenses_df.columns:
                categories_preview = (
                    all_expenses_df["category"]
                    .astype(str)
                    .value_counts()
                    .head(10)
                )
                st.caption("Top expense categories detected:")
                st.dataframe(
                    categories_preview.rename_axis("Category").reset_index(name="Count"),
                    use_container_width=True,
                    hide_index=True,
                )

            st.caption(
                f"Rows in selected period ({date_from} → {date_to}): "
                f"**{len(expenses_df)}**"
            )
    
    # ==============================
    # CALCULATE REAL METRICS
    # ==============================
    total_col = "final_total" if "final_total" in sales_df.columns else "total" if "total" in sales_df.columns else None
    profit_col = "profit" if "profit" in sales_df.columns else None
    
    total_sales = to_float(sales_df[total_col].sum()) if total_col and not sales_df.empty else 0
    total_expenses = to_float(expenses_df["amount"].sum()) if "amount" in expenses_df.columns and not expenses_df.empty else 0
    total_profit = to_float(sales_df[profit_col].sum()) if profit_col and not sales_df.empty else 0
    transaction_count = len(sales_df)
    
    # ==============================
    # DISPLAY REAL METRICS
    # ==============================
    st.markdown("### Period Summary")
    
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
                "Audit Trail (CSV)"
            ]
        )
    
    with col2:
        include_expenses = st.checkbox("Include Expenses", value=True)
    
    # ==============================
    # GENERATE EXPORT
    # ==============================
    if st.button("Generate Export File", type="primary", use_container_width=True):
        if sales_df.empty and export_format != "Audit Trail (CSV)":
            st.error("No sales data found for the selected period. Please add sales or change the date range.")
        else:
            with st.spinner("Generating export file..."):
                
                export_data = None
                export_filename = None
                
                if export_format == "QuickBooks (IIF)":
                    export_data = export_to_quickbooks(sales_df, expenses_df if include_expenses else pd.DataFrame(), date_from, date_to)
                    export_filename = f"quickbooks_export_{date_from.strftime('%Y%m%d')}_{date_to.strftime('%Y%m%d')}.iif"
                    if export_data:
                        st.success(f"QuickBooks export generated! {transaction_count} transactions, Revenue: ${total_sales:,.2f}")
                    else:
                        st.error("No data to export for QuickBooks")
                
                elif export_format == "Pastel Partner (CSV)":
                    export_data = export_to_pastel(sales_df, expenses_df if include_expenses else pd.DataFrame(), date_from, date_to)
                    export_filename = f"pastel_export_{date_from.strftime('%Y%m%d')}_{date_to.strftime('%Y%m%d')}.csv"
                    if export_data:
                        st.success(f"Pastel Partner export generated! {transaction_count} transactions, Revenue: ${total_sales:,.2f}")
                    else:
                        st.error("No data to export for Pastel")
                
                elif export_format == "Xero (CSV)":
                    export_data = export_to_xero(sales_df, expenses_df if include_expenses else pd.DataFrame(), date_from, date_to)
                    export_filename = f"xero_export_{date_from.strftime('%Y%m%d')}_{date_to.strftime('%Y%m%d')}.csv"
                    if export_data:
                        st.success(f"Xero export generated! {transaction_count} transactions, Revenue: ${total_sales:,.2f}")
                    else:
                        st.error("No data to export for Xero")
                
                elif export_format == "Sage One (CSV)":
                    export_data = export_to_sage(sales_df, expenses_df if include_expenses else pd.DataFrame(), date_from, date_to)
                    export_filename = f"sage_export_{date_from.strftime('%Y%m%d')}_{date_to.strftime('%Y%m%d')}.csv"
                    if export_data:
                        st.success(f"Sage One export generated! {transaction_count} transactions, Revenue: ${total_sales:,.2f}")
                    else:
                        st.error("No data to export for Sage")
                
                elif export_format == "ZIMRA e-filing (CSV)":
                    export_data = export_to_zimra(sales_df, date_from, date_to)
                    export_filename = f"zimra_export_{date_from.strftime('%Y%m%d')}_{date_to.strftime('%Y%m%d')}.csv"
                    if export_data:
                        st.success(f"ZIMRA e-filing export generated! Revenue: ${total_sales:,.2f}")
                    else:
                        st.error("No data to export for ZIMRA")
                
                elif export_format == "Audit Trail (CSV)":
                    audit_df = get_audit_log(365)
                    export_data = export_audit_trail(audit_df, date_from, date_to)
                    export_filename = f"audit_trail_{date_from.strftime('%Y%m%d')}_{date_to.strftime('%Y%m%d')}.csv"
                    st.success("Audit trail export generated!")
                
                if export_data:
                    # Save export record
                    export_record = {
                        "export_id": f"EXP{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        "export_date": datetime.now().isoformat(),
                        "export_type": export_format,
                        "date_from": date_from.isoformat(),
                        "date_to": date_to.isoformat(),
                        "total_sales": total_sales,
                        "total_expenses": total_expenses,
                        "total_profit": total_profit,
                        "exported_by": st.session_state.get("username", "system"),
                        "file_path": str(EXPORT_DIR / export_filename)
                    }
                    save_accounting_export(export_record)
                    
                    # Download button
                    st.download_button(
                        label="Download Export File",
                        data=export_data.encode('utf-8') if isinstance(export_data, str) else export_data,
                        file_name=export_filename,
                        mime="text/csv",
                        use_container_width=True
                    )
                    
                    st.balloons()
    
    # ==============================
    # EXPORT HISTORY
    # ==============================
    st.markdown("---")
    st.markdown("### Export History")
    
    exports_df = load_accounting_exports()
    if not exports_df.empty:
        exports_df["export_date"] = pd.to_datetime(exports_df["export_date"])
        exports_df["export_date"] = exports_df["export_date"].dt.strftime("%Y-%m-%d %H:%M")
        
        st.dataframe(
            exports_df[["export_date", "export_type", "date_from", "date_to", "total_sales", "exported_by"]].head(10),
            use_container_width=True,
            hide_index=True,
            column_config={
                "total_sales": st.column_config.NumberColumn("Total Sales", format="$%.2f")
            }
        )
    else:
        st.info("No export history yet")


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    accounting_sync_dashboard()