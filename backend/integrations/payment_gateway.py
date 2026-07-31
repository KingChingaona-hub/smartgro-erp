# backend/integrations/payment_gateway.py
# Payment Gateway Dashboard - Using REAL sales data with duplicate prevention

import streamlit as st
import pandas as pd
import hashlib
import secrets
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path
import qrcode
from io import BytesIO
import base64

from backend.core.db_adapter import (
    load_sales,
    load_customers,
    load_debtors,
    load_cash,
    get_cash_summary
)

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
# FILE PATHS
# ==============================
DATA_DIR = Path("data")
PAYMENT_FILE = DATA_DIR / "payments.csv"
ECO_CASH_FILE = DATA_DIR / "ecocash_transactions.csv"
CARD_FILE = DATA_DIR / "card_transactions.csv"


# ==============================
# INITIALIZATION
# ==============================
def init_payment_files():
    """Initialize payment-related files"""
    DATA_DIR.mkdir(exist_ok=True)
    
    if not PAYMENT_FILE.exists():
        df = pd.DataFrame(columns=[
            "payment_id", "receipt_no", "amount", "payment_method", "status",
            "reference", "transaction_id", "payment_date", "customer_name",
            "customer_phone", "branch_code", "processed_by"
        ])
        df.to_csv(PAYMENT_FILE, index=False)
    
    if not ECO_CASH_FILE.exists():
        df = pd.DataFrame(columns=[
            "transaction_id", "receipt_no", "amount", "customer_phone", 
            "merchant_code", "status", "request_date", "completion_date",
            "reference", "notes"
        ])
        df.to_csv(ECO_CASH_FILE, index=False)
    
    if not CARD_FILE.exists():
        df = pd.DataFrame(columns=[
            "transaction_id", "receipt_no", "amount", "card_type",
            "last_four", "status", "payment_date", "auth_code", "notes"
        ])
        df.to_csv(CARD_FILE, index=False)


# ==============================
# LOAD PAYMENTS FROM SALES - REAL DATA WITH DEDUPLICATION
# ==============================
def load_payments_from_sales(date_from=None, date_to=None):
    """Load REAL payments from sales data only - NO DUPLICATES"""
    
    sales_df = load_sales()
    
    if sales_df.empty:
        return pd.DataFrame()
    
    # Determine date column
    date_col = None
    for col in ["sale_date", "date", "transaction_date", "created_at"]:
        if col in sales_df.columns:
            date_col = col
            break
    
    if date_col:
        sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
        sales_df = sales_df.dropna(subset=[date_col])
        
        if date_from:
            sales_df = sales_df[sales_df[date_col] >= pd.to_datetime(date_from)]
        if date_to:
            sales_df = sales_df[sales_df[date_col] <= pd.to_datetime(date_to)]
    
    if sales_df.empty:
        return pd.DataFrame()
    
    # Find total column
    total_col = None
    for col in ["final_total", "total", "amount", "sale_amount"]:
        if col in sales_df.columns:
            total_col = col
            break
    
    if total_col is None:
        return pd.DataFrame()
    
    # Find receipt column for unique transactions
    receipt_col = None
    for col in ["receipt_no", "receipt", "transaction_id", "order_id"]:
        if col in sales_df.columns:
            receipt_col = col
            break
    
    # ============================================================
    # DEDUPLICATION: Use unique receipts to avoid duplicates
    # ============================================================
    if receipt_col:
        # Drop duplicates by receipt number (keep first occurrence)
        sales_df = sales_df.drop_duplicates(subset=[receipt_col], keep="first")
    
    # Create payment records from sales
    payments = []
    
    for _, sale in sales_df.iterrows():
        amount = to_float(sale.get(total_col, 0))
        
        # Skip zero amount transactions
        if amount <= 0:
            continue
        
        # Get receipt number
        receipt_no = str(sale.get(receipt_col, "")) if receipt_col else ""
        if not receipt_no or receipt_no == "nan":
            receipt_no = f"SALE{len(payments)+1:08d}"
        
        # Get payment method
        payment_method = "CASH"
        for col in ["payment_method", "payment_type", "payment"]:
            if col in sale.index:
                val = sale.get(col, "CASH")
                if val and str(val).strip() and str(val).strip() != "nan":
                    payment_method = str(val).strip().upper()
                    break
        
        # Get customer name
        customer_name = "Walk-in"
        for col in ["customer_name", "customer", "Customer"]:
            if col in sale.index:
                val = sale.get(col, "Walk-in")
                if val and str(val).strip() and str(val).strip() != "nan":
                    customer_name = str(val).strip()
                    break
        
        # Get customer phone
        customer_phone = ""
        for col in ["customer_phone", "phone", "Phone"]:
            if col in sale.index:
                val = sale.get(col, "")
                if val and str(val).strip() and str(val).strip() != "nan":
                    customer_phone = str(val).strip()
                    break
        
        # Get cashier
        cashier = "system"
        for col in ["cashier", "user", "username"]:
            if col in sale.index:
                val = sale.get(col, "system")
                if val and str(val).strip() and str(val).strip() != "nan":
                    cashier = str(val).strip()
                    break
        
        # Get sale date
        sale_date = sale.get(date_col, datetime.now()) if date_col else datetime.now()
        
        payments.append({
            "payment_id": f"PAY{len(payments)+1:08d}",
            "receipt_no": receipt_no,
            "amount": amount,
            "payment_method": payment_method,
            "status": "COMPLETED",
            "reference": receipt_no,
            "transaction_id": receipt_no,
            "payment_date": sale_date,
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "branch_code": "HO",
            "processed_by": cashier
        })
    
    if not payments:
        return pd.DataFrame()
    
    return pd.DataFrame(payments)


# ==============================
# PAYMENT SUMMARY - REAL DATA WITH DEDUPLICATION
# ==============================
def get_payment_summary(days=30):
    """Get payment summary from REAL sales data - NO DUPLICATES"""
    
    sales_df = load_sales()
    
    if sales_df.empty:
        return {
            "total_payments": 0,
            "total_amount": 0,
            "by_method": {},
            "recent_payments": pd.DataFrame(),
            "cash_vs_credit": {"CASH": 0, "CREDIT": 0, "OTHER": 0}
        }
    
    # Determine date column
    date_col = None
    for col in ["sale_date", "date", "transaction_date", "created_at"]:
        if col in sales_df.columns:
            date_col = col
            break
    
    if date_col:
        sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
        sales_df = sales_df.dropna(subset=[date_col])
        cutoff = datetime.now() - timedelta(days=days)
        sales_df = sales_df[sales_df[date_col] >= cutoff]
    
    # Find total column
    total_col = None
    for col in ["final_total", "total", "amount", "sale_amount"]:
        if col in sales_df.columns:
            total_col = col
            break
    
    if total_col is None:
        return {
            "total_payments": 0,
            "total_amount": 0,
            "by_method": {},
            "recent_payments": pd.DataFrame(),
            "cash_vs_credit": {"CASH": 0, "CREDIT": 0, "OTHER": 0}
        }
    
    # Find receipt column for unique transactions
    receipt_col = None
    for col in ["receipt_no", "receipt", "transaction_id", "order_id"]:
        if col in sales_df.columns:
            receipt_col = col
            break
    
    # ============================================================
    # DEDUPLICATION: Use unique receipts
    # ============================================================
    if receipt_col:
        # Drop duplicates by receipt number
        unique_sales = sales_df.drop_duplicates(subset=[receipt_col], keep="first")
        total_payments = len(unique_sales)
        total_amount = to_float(unique_sales[total_col].sum())
    else:
        total_payments = len(sales_df)
        total_amount = to_float(sales_df[total_col].sum())
    
    # By payment method
    payment_col = None
    for col in ["payment_method", "payment_type", "payment"]:
        if col in sales_df.columns:
            payment_col = col
            break
    
    by_method = {}
    if payment_col:
        if receipt_col:
            method_data = unique_sales.groupby(payment_col)[total_col].sum().apply(to_float).to_dict()
        else:
            method_data = sales_df.groupby(payment_col)[total_col].sum().apply(to_float).to_dict()
        by_method = method_data
    
    # Cash vs Credit breakdown
    cash_vs_credit = {"CASH": 0, "CREDIT": 0, "OTHER": 0}
    if payment_col:
        for method, amount in by_method.items():
            method_upper = method.upper()
            if "CASH" in method_upper:
                cash_vs_credit["CASH"] += amount
            elif "CREDIT" in method_upper:
                cash_vs_credit["CREDIT"] += amount
            else:
                cash_vs_credit["OTHER"] += amount
    
    # Recent payments
    if receipt_col:
        recent_sales = unique_sales.sort_values(date_col, ascending=False).head(10) if date_col else unique_sales.head(10)
    else:
        recent_sales = sales_df.sort_values(date_col, ascending=False).head(10) if date_col else sales_df.head(10)
    
    return {
        "total_payments": total_payments,
        "total_amount": total_amount,
        "by_method": by_method,
        "recent_payments": recent_sales,
        "cash_vs_credit": cash_vs_credit
    }


def load_ecocash_transactions():
    """Load EcoCash transactions"""
    if ECO_CASH_FILE.exists():
        return pd.read_csv(ECO_CASH_FILE)
    return pd.DataFrame(columns=[
        "transaction_id", "receipt_no", "amount", "customer_phone", 
        "merchant_code", "status", "request_date", "completion_date",
        "reference", "notes"
    ])


def load_card_transactions():
    """Load card transactions"""
    if CARD_FILE.exists():
        return pd.read_csv(CARD_FILE)
    return pd.DataFrame(columns=[
        "transaction_id", "receipt_no", "amount", "card_type",
        "last_four", "status", "payment_date", "auth_code", "notes"
    ])


# ==============================
# ECOCASH INTEGRATION (Simulated)
# ==============================
def generate_ecocash_payment_request(amount, customer_phone, receipt_no):
    """Generate EcoCash payment request (Simulated)"""
    
    transaction_id = f"ECO{datetime.now().strftime('%Y%m%d%H%M%S')}{secrets.randbelow(1000):03d}"
    merchant_code = "AZIEL001"
    
    payment_request = {
        "transaction_id": transaction_id,
        "amount": amount,
        "customer_phone": customer_phone,
        "merchant_code": merchant_code,
        "receipt_no": receipt_no,
        "timestamp": datetime.now().isoformat()
    }
    
    # Generate payment link (simulated)
    payment_link = f"https://pay.ecocash.co.zw/pay?txn={transaction_id}&amt={amount}&msisdn={customer_phone}"
    
    # Generate QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(payment_link)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    qr_base64 = base64.b64encode(buffered.getvalue()).decode()
    
    # Save transaction
    df = load_ecocash_transactions()
    new_transaction = pd.DataFrame([{
        "transaction_id": transaction_id,
        "receipt_no": receipt_no,
        "amount": amount,
        "customer_phone": customer_phone,
        "merchant_code": merchant_code,
        "status": "PENDING",
        "request_date": datetime.now().isoformat(),
        "completion_date": "",
        "reference": "",
        "notes": ""
    }])
    
    if df.empty:
        df = new_transaction
    else:
        df = pd.concat([df, new_transaction], ignore_index=True)
    
    df.to_csv(ECO_CASH_FILE, index=False)
    
    return {
        "success": True,
        "transaction_id": transaction_id,
        "payment_link": payment_link,
        "qr_code": qr_base64,
        "message": f"Payment request generated. Customer will receive a prompt on their phone."
    }


def verify_ecocash_payment(transaction_id):
    """Verify EcoCash payment status (Simulated)"""
    
    if not ECO_CASH_FILE.exists():
        return {"success": False, "status": "NOT_FOUND", "message": "Transaction not found"}
    
    df = pd.read_csv(ECO_CASH_FILE)
    transaction = df[df["transaction_id"] == transaction_id]
    
    if transaction.empty:
        return {"success": False, "status": "NOT_FOUND", "message": "Transaction not found"}
    
    current_status = transaction.iloc[0]["status"]
    
    if current_status == "PENDING":
        # Simulate payment verification
        time_since_request = (datetime.now() - pd.to_datetime(transaction.iloc[0]["request_date"])).seconds
        
        if time_since_request > 30:
            idx = transaction.index[0]
            df.loc[idx, "status"] = "COMPLETED"
            df.loc[idx, "completion_date"] = datetime.now().isoformat()
            df.loc[idx, "reference"] = f"REF{secrets.randbelow(10000):04d}"
            df.to_csv(ECO_CASH_FILE, index=False)
            
            return {
                "success": True, 
                "status": "COMPLETED", 
                "message": "Payment completed successfully",
                "reference": df.loc[idx, "reference"]
            }
        else:
            return {
                "success": False, 
                "status": "PENDING", 
                "message": "Payment pending. Please wait for customer to complete payment."
            }
    elif current_status == "COMPLETED":
        return {
            "success": True, 
            "status": "COMPLETED", 
            "message": "Payment already completed",
            "reference": transaction.iloc[0]["reference"]
        }
    else:
        return {"success": False, "status": current_status, "message": f"Payment status: {current_status}"}


# ==============================
# PAYMENT DASHBOARD - REAL DATA WITH DEDUPLICATION
# ==============================
def payment_dashboard():
    """Payment Gateway Dashboard with REAL data - NO DUPLICATES"""
    
    st.title("Payment Gateway Dashboard")
    st.caption("Manage payments, view transaction history, and process refunds")
    
    role = st.session_state.get("role", "cashier")
    
    if role not in ["owner", "manager"]:
        st.error("Access Denied. Only owners and managers can access payment dashboard.")
        return
    
    init_payment_files()
    
    # ==============================
    # TABS
    # ==============================
    tab1, tab2, tab3 = st.tabs([
        "Payment Summary",
        "Transaction History",
        "Gateway Settings"
    ])
    
    # ==============================
    # TAB 1: PAYMENT SUMMARY - REAL DATA
    # ==============================
    with tab1:
        st.markdown("## Payment Summary")
        
        # Get REAL data with deduplication
        summary = get_payment_summary(30)
        payments_df = load_payments_from_sales()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Payments", f"${summary['total_amount']:,.2f}")
        with col2:
            st.metric("Total Transactions", summary["total_payments"])
        with col3:
            avg = summary['total_amount'] / summary['total_payments'] if summary['total_payments'] > 0 else 0
            st.metric("Avg Transaction", f"${avg:.2f}")
        
        # Cash vs Credit breakdown
        st.markdown("### Cash vs Credit Breakdown")
        cash_vs_credit = summary.get("cash_vs_credit", {"CASH": 0, "CREDIT": 0, "OTHER": 0})
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Cash Sales", f"${cash_vs_credit['CASH']:,.2f}")
        with col2:
            st.metric("Credit Sales", f"${cash_vs_credit['CREDIT']:,.2f}")
        with col3:
            st.metric("Other Payments", f"${cash_vs_credit['OTHER']:,.2f}")
        
        st.markdown("### Payment Methods Breakdown")
        
        if summary["by_method"]:
            methods_df = pd.DataFrame(list(summary["by_method"].items()), columns=["Method", "Amount"])
            st.bar_chart(methods_df.set_index("Method"))
            
            # Show actual numbers
            st.dataframe(
                methods_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Amount": st.column_config.NumberColumn("Amount", format="$%.2f")
                }
            )
        else:
            st.info("No payment data available. Complete some sales first.")
        
        # Show recent payments
        if not summary["recent_payments"].empty:
            st.markdown("### Recent Payments")
            display_cols = ["receipt_no", "customer_name", "total", "payment_method", "date"]
            available_cols = []
            for col in display_cols:
                if col in summary["recent_payments"].columns:
                    available_cols.append(col)
                elif col == "receipt_no" and "receipt" in summary["recent_payments"].columns:
                    available_cols.append("receipt")
                elif col == "customer_name" and "customer" in summary["recent_payments"].columns:
                    available_cols.append("customer")
            
            if available_cols:
                st.dataframe(
                    summary["recent_payments"][available_cols],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "total": st.column_config.NumberColumn("Amount", format="$%.2f")
                    }
                )
    
    # ==============================
    # TAB 2: TRANSACTION HISTORY - REAL DATA
    # ==============================
    with tab2:
        st.markdown("## Transaction History")
        
        # Get REAL data with deduplication
        payments_df = load_payments_from_sales()
        
        if not payments_df.empty:
            # Date filter
            col1, col2 = st.columns(2)
            with col1:
                date_from = st.date_input("From Date", datetime.now() - timedelta(days=30))
            with col2:
                date_to = st.date_input("To Date", datetime.now())
            
            # Filter by date
            if "payment_date" in payments_df.columns:
                payments_df["payment_date"] = pd.to_datetime(payments_df["payment_date"])
                payments_df = payments_df[
                    (payments_df["payment_date"] >= pd.to_datetime(date_from)) &
                    (payments_df["payment_date"] <= pd.to_datetime(date_to))
                ]
            
            # Display
            display_cols = ["payment_date", "receipt_no", "customer_name", "amount", "payment_method", "status"]
            available_cols = [col for col in display_cols if col in payments_df.columns]
            
            if available_cols:
                st.dataframe(
                    payments_df[available_cols],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
                        "payment_date": st.column_config.DatetimeColumn("Date", format="YYYY-MM-DD HH:mm")
                    }
                )
                
                # Summary
                total_amount = payments_df["amount"].sum() if "amount" in payments_df.columns else 0
                st.info(f"Total Transactions: ${to_float(total_amount):,.2f} | Count: {len(payments_df)}")
                
                # Export
                csv = payments_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Export Transactions (CSV)",
                    data=csv,
                    file_name=f"payments_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
        else:
            st.info("No transactions found. Complete some sales first.")
    
    # ==============================
    # TAB 3: GATEWAY SETTINGS
    # ==============================
    with tab3:
        st.markdown("## Gateway Settings")
        
        st.info("Payment gateway configuration")
        st.markdown("""
        **Available Payment Gateways:**
        - Cash (Physical)
        - EcoCash (Mobile Money) - Coming Soon
        - Card Payments (Visa/Mastercard) - Coming Soon
        - Bank Transfer - Coming Soon
        - PayNow (Coming Soon)
        - InnBucks (Coming Soon)
        """)
        
        # Show current payment stats from REAL data
        sales_df = load_sales()
        if not sales_df.empty:
            st.markdown("### Current Payment Statistics")
            
            total_col = None
            for col in ["final_total", "total", "amount", "sale_amount"]:
                if col in sales_df.columns:
                    total_col = col
                    break
            
            receipt_col = None
            for col in ["receipt_no", "receipt", "transaction_id", "order_id"]:
                if col in sales_df.columns:
                    receipt_col = col
                    break
            
            if total_col:
                # Use unique receipts for total
                if receipt_col:
                    unique_sales = sales_df.drop_duplicates(subset=[receipt_col], keep="first")
                    total_amount = to_float(unique_sales[total_col].sum())
                    total_count = len(unique_sales)
                else:
                    total_amount = to_float(sales_df[total_col].sum())
                    total_count = len(sales_df)
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Total Sales (All Time)", f"${total_amount:,.2f}")
                with col2:
                    st.metric("Total Transactions", total_count)
                
                # Payment method distribution
                payment_col = None
                for col in ["payment_method", "payment_type", "payment"]:
                    if col in sales_df.columns:
                        payment_col = col
                        break
                
                if payment_col:
                    st.markdown("### Payment Method Distribution")
                    if receipt_col:
                        method_dist = unique_sales.groupby(payment_col)[total_col].sum().apply(to_float)
                    else:
                        method_dist = sales_df.groupby(payment_col)[total_col].sum().apply(to_float)
                    
                    st.dataframe(
                        method_dist.reset_index().rename(columns={payment_col: "Method", total_col: "Amount"}),
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Amount": st.column_config.NumberColumn("Amount", format="$%.2f")
                        }
                    )