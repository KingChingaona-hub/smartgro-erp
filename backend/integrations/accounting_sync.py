# backend/integrations/accounting_sync.py
import streamlit as st
import pandas as pd
import json
import csv
from datetime import datetime, timedelta
from pathlib import Path
import io

from backend.core.db_adapter import (
    load_sales,
    load_expenses,
    load_purchases,
    load_customers,
    load_debtors,
    load_products
)
from backend.admin.security import get_audit_log

# ==============================
# FILE PATHS
# ==============================
DATA_DIR = Path("data")
EXPORT_DIR = Path("exports")
ACCOUNTING_FILE = DATA_DIR / "accounting_exports.csv"


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
    return pd.read_csv(ACCOUNTING_FILE)


def save_accounting_export(export_data):
    """Save export record"""
    df = load_accounting_exports()
    df = pd.concat([df, pd.DataFrame([export_data])], ignore_index=True)
    df.to_csv(ACCOUNTING_FILE, index=False)


# ==============================
# HELPER: Convert Decimal to float
# ==============================
def to_float(value):
    """Safely convert Decimal or any value to float"""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


# ==============================
# GET REAL SALES DATA
# ==============================
def get_sales_data(date_from, date_to):
    """Get REAL sales data with debugging"""
    
    sales_df = load_sales()
    
    print(f"📊 Loaded {len(sales_df)} sales records from database")
    
    if sales_df.empty:
        print("⚠️ No sales data found in database!")
        return pd.DataFrame()
    
    # Show columns for debugging
    print(f"📋 Sales columns: {list(sales_df.columns)}")
    
    # Determine date column
    date_col = None
    for col in ["sale_date", "date", "transaction_date", "created_at"]:
        if col in sales_df.columns:
            date_col = col
            break
    
    if date_col is None:
        print("⚠️ No date column found in sales data!")
        return pd.DataFrame()
    
    # Convert to datetime
    sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
    sales_df = sales_df.dropna(subset=[date_col])
    
    # Filter by date range
    filtered = sales_df[(sales_df[date_col] >= pd.to_datetime(date_from)) & 
                        (sales_df[date_col] <= pd.to_datetime(date_to))]
    
    print(f"📊 After date filter: {len(filtered)} records from {date_from} to {date_to}")
    
    return filtered


def get_expenses_data(date_from, date_to):
    """Get REAL expenses data"""
    
    expenses_df = load_expenses()
    
    if expenses_df.empty:
        return pd.DataFrame()
    
    date_col = "expense_date" if "expense_date" in expenses_df.columns else "date" if "date" in expenses_df.columns else None
    
    if date_col is None:
        return pd.DataFrame()
    
    expenses_df[date_col] = pd.to_datetime(expenses_df[date_col], errors="coerce")
    expenses_df = expenses_df.dropna(subset=[date_col])
    
    filtered = expenses_df[(expenses_df[date_col] >= pd.to_datetime(date_from)) & 
                           (expenses_df[date_col] <= pd.to_datetime(date_to))]
    
    return filtered


# ==============================
# QUICKBOOKS EXPORT - REAL DATA
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
# ZIMRA E-FILING EXPORT
# ==============================
def export_to_zimra(sales_df, date_from, date_to):
    """Export to ZIMRA e-filing format"""
    
    total_col = "final_total" if "final_total" in sales_df.columns else "total" if "total" in sales_df.columns else None
    
    total_sales = to_float(sales_df[total_col].sum()) if total_col and not sales_df.empty else 0
    vat_amount = total_sales * 0.15
    vat_exclusive = total_sales
    
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
# ACCOUNTING DASHBOARD - WITH DEBUGGING
# ==============================
def accounting_sync_dashboard():
    """Accounting Software Sync Dashboard with REAL data"""
    
    st.title("📊 Accounting Software Sync")
    st.caption("Export REAL data to QuickBooks, Pastel, Xero, Sage, and ZIMRA")
    
    role = st.session_state.get("role", "cashier")
    
    if role not in ["owner", "manager"]:
        st.error("❌ Access Denied. Only owners and managers can access accounting sync.")
        return
    
    init_accounting_files()
    
    # ==============================
    # DATE RANGE SELECTION
    # ==============================
    st.markdown("### 📅 Select Export Period")
    
    col1, col2 = st.columns(2)
    with col1:
        date_from = st.date_input("From Date", datetime.now() - timedelta(days=30))
    with col2:
        date_to = st.date_input("To Date", datetime.now())
    
    # ==============================
    # LOAD REAL DATA
    # ==============================
    with st.spinner("Loading data from database..."):
        sales_df = get_sales_data(date_from, date_to)
        expenses_df = get_expenses_data(date_from, date_to)
    
    # ==============================
    # DEBUG: Show what was loaded
    # ==============================
    with st.expander("🔧 Debug Info (Click to expand)"):
        st.write(f"**Sales records found:** {len(sales_df)}")
        st.write(f"**Sales columns:** {list(sales_df.columns) if not sales_df.empty else 'No data'}")
        st.write(f"**Expenses records found:** {len(expenses_df)}")
        if not sales_df.empty:
            st.write("**Sample Sales Data:**")
            st.dataframe(sales_df.head(3))
    
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
    st.markdown("### 📊 Period Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("💰 Total Sales", f"${total_sales:,.2f}")
    with col2:
        st.metric("📉 Total Expenses", f"${total_expenses:,.2f}")
    with col3:
        st.metric("📈 Total Profit", f"${total_profit:,.2f}")
    with col4:
        st.metric("📊 Transactions", transaction_count)
    
    # Show if no data found
    if total_sales == 0 and transaction_count == 0:
        st.warning("⚠️ No sales data found for the selected period. Try expanding the date range or adding some sales first.")
    
    st.markdown("---")
    
    # ==============================
    # EXPORT OPTIONS
    # ==============================
    st.markdown("### 📤 Export to Accounting Software")
    
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
    if st.button("📥 Generate Export File", type="primary", use_container_width=True):
        if sales_df.empty and export_format != "Audit Trail (CSV)":
            st.error("❌ No sales data found for the selected period. Please add sales or change the date range.")
        else:
            with st.spinner("Generating export file with REAL data..."):
                
                export_data = None
                export_filename = None
                
                if export_format == "QuickBooks (IIF)":
                    export_data = export_to_quickbooks(sales_df, expenses_df if include_expenses else pd.DataFrame(), date_from, date_to)
                    export_filename = f"quickbooks_export_{date_from.strftime('%Y%m%d')}_{date_to.strftime('%Y%m%d')}.iif"
                    if export_data:
                        st.success(f"✅ QuickBooks export generated! {transaction_count} transactions, Revenue: ${total_sales:,.2f}")
                    else:
                        st.error("❌ No data to export for QuickBooks")
                
                elif export_format == "Pastel Partner (CSV)":
                    export_data = export_to_pastel(sales_df, expenses_df if include_expenses else pd.DataFrame(), date_from, date_to)
                    export_filename = f"pastel_export_{date_from.strftime('%Y%m%d')}_{date_to.strftime('%Y%m%d')}.csv"
                    if export_data:
                        st.success(f"✅ Pastel Partner export generated! {transaction_count} transactions, Revenue: ${total_sales:,.2f}")
                    else:
                        st.error("❌ No data to export for Pastel")
                
                elif export_format == "Xero (CSV)":
                    export_data = export_to_xero(sales_df, expenses_df if include_expenses else pd.DataFrame(), date_from, date_to)
                    export_filename = f"xero_export_{date_from.strftime('%Y%m%d')}_{date_to.strftime('%Y%m%d')}.csv"
                    if export_data:
                        st.success(f"✅ Xero export generated! {transaction_count} transactions, Revenue: ${total_sales:,.2f}")
                    else:
                        st.error("❌ No data to export for Xero")
                
                elif export_format == "Sage One (CSV)":
                    export_data = export_to_sage(sales_df, expenses_df if include_expenses else pd.DataFrame(), date_from, date_to)
                    export_filename = f"sage_export_{date_from.strftime('%Y%m%d')}_{date_to.strftime('%Y%m%d')}.csv"
                    if export_data:
                        st.success(f"✅ Sage One export generated! {transaction_count} transactions, Revenue: ${total_sales:,.2f}")
                    else:
                        st.error("❌ No data to export for Sage")
                
                elif export_format == "ZIMRA e-filing (CSV)":
                    export_data = export_to_zimra(sales_df, date_from, date_to)
                    export_filename = f"zimra_export_{date_from.strftime('%Y%m%d')}_{date_to.strftime('%Y%m%d')}.csv"
                    if export_data:
                        st.success(f"✅ ZIMRA e-filing export generated! Revenue: ${total_sales:,.2f}")
                    else:
                        st.error("❌ No data to export for ZIMRA")
                
                elif export_format == "Audit Trail (CSV)":
                    audit_df = get_audit_log(365)
                    export_data = export_audit_trail(audit_df, date_from, date_to)
                    export_filename = f"audit_trail_{date_from.strftime('%Y%m%d')}_{date_to.strftime('%Y%m%d')}.csv"
                    st.success("✅ Audit trail export generated!")
                
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
                        label="💾 Download Export File",
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
    st.markdown("### 📋 Export History")
    
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