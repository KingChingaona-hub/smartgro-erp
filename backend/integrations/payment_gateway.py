# backend/integrations/payment_gateway.py
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
# FILE PATHS
# ==============================
DATA_DIR = Path("data")
PAYMENT_FILE = DATA_DIR / "payments.csv"
ECO_CASH_FILE = DATA_DIR / "ecocash_transactions.csv"
CARD_FILE = DATA_DIR / "card_transactions.csv"


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


def load_payments():
    """Load all payments from database - REAL DATA"""
    df = load_cash()
    
    if df.empty:
        return pd.DataFrame()
    
    # Filter payment types
    payment_types = ["CASH_SALE", "CREDIT_SALE", "DEBT_PAYMENT", "DEPOSIT"]
    df = df[df["type"].isin(payment_types)]
    
    # Rename columns to match payment structure
    if not df.empty:
        df = df.copy()
        df["payment_id"] = df.index.astype(str)
        df["payment_method"] = df["payment_method"].fillna("CASH")
        df["status"] = "COMPLETED"
        df["payment_date"] = df["cash_date"]
        df["processed_by"] = df["cashier"].fillna("system")
        
        # Convert amount to float
        df["amount"] = df["amount"].apply(to_float)
    
    return df


def load_ecocash_transactions():
    """Load EcoCash transactions - REAL DATA"""
    # For now, return empty DataFrame until we have actual EcoCash integration
    # This would come from an API in production
    return pd.DataFrame(columns=[
        "transaction_id", "receipt_no", "amount", "customer_phone", 
        "merchant_code", "status", "request_date", "completion_date",
        "reference", "notes"
    ])


def load_card_transactions():
    """Load card transactions - REAL DATA"""
    # For now, return empty DataFrame until we have actual card integration
    return pd.DataFrame(columns=[
        "transaction_id", "receipt_no", "amount", "card_type",
        "last_four", "status", "payment_date", "auth_code", "notes"
    ])


def load_payments_from_sales(date_from=None, date_to=None):
    """Load REAL payments from sales data"""
    
    sales_df = load_sales()
    
    if sales_df.empty:
        return pd.DataFrame()
    
    # Determine date column
    date_col = "sale_date" if "sale_date" in sales_df.columns else "date" if "date" in sales_df.columns else None
    
    if date_col:
        sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
        
        if date_from:
            sales_df = sales_df[sales_df[date_col] >= pd.to_datetime(date_from)]
        if date_to:
            sales_df = sales_df[sales_df[date_col] <= pd.to_datetime(date_to)]
    
    # Create payment records from sales
    payments = []
    
    total_col = "final_total" if "final_total" in sales_df.columns else "total" if "total" in sales_df.columns else None
    customer_col = "customer" if "customer" in sales_df.columns else "customer_name" if "customer_name" in sales_df.columns else "Walk-in"
    phone_col = "customer_phone" if "customer_phone" in sales_df.columns else "phone" if "phone" in sales_df.columns else ""
    payment_col = "payment_method" if "payment_method" in sales_df.columns else "CASH"
    
    if total_col:
        for _, sale in sales_df.iterrows():
            payments.append({
                "payment_id": f"PAY{len(payments)+1:08d}",
                "receipt_no": str(sale.get("receipt_no", "")),
                "amount": to_float(sale.get(total_col, 0)),
                "payment_method": str(sale.get(payment_col, "CASH")),
                "status": "COMPLETED",
                "reference": str(sale.get("receipt_no", "")),
                "transaction_id": str(sale.get("receipt_no", "")),
                "payment_date": sale.get(date_col, datetime.now()),
                "customer_name": str(sale.get(customer_col, "Walk-in")),
                "customer_phone": str(sale.get(phone_col, "")),
                "branch_code": "HO",
                "processed_by": str(sale.get("cashier", "system"))
            })
    
    return pd.DataFrame(payments)


# ==============================
# PAYMENT SUMMARY - REAL DATA
# ==============================
def get_payment_summary(days=30):
    """Get payment summary from REAL data"""
    
    sales_df = load_sales()
    
    if sales_df.empty:
        return {
            "total_payments": 0,
            "total_amount": 0,
            "by_method": {},
            "recent_payments": pd.DataFrame()
        }
    
    # Determine date column
    date_col = "sale_date" if "sale_date" in sales_df.columns else "date" if "date" in sales_df.columns else None
    
    if date_col:
        sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
        cutoff = datetime.now() - timedelta(days=days)
        sales_df = sales_df[sales_df[date_col] >= cutoff]
    
    total_col = "final_total" if "final_total" in sales_df.columns else "total" if "total" in sales_df.columns else None
    
    if total_col is None:
        return {
            "total_payments": 0,
            "total_amount": 0,
            "by_method": {},
            "recent_payments": pd.DataFrame()
        }
    
    # Calculate totals
    total_amount = to_float(sales_df[total_col].sum())
    total_payments = len(sales_df)
    
    # By payment method
    payment_col = "payment_method" if "payment_method" in sales_df.columns else None
    by_method = {}
    if payment_col:
        by_method = sales_df.groupby(payment_col)[total_col].sum().apply(to_float).to_dict()
    
    # Recent payments
    recent_payments = sales_df.sort_values(date_col, ascending=False).head(10) if date_col else sales_df.head(10)
    
    return {
        "total_payments": total_payments,
        "total_amount": total_amount,
        "by_method": by_method,
        "recent_payments": recent_payments
    }


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
    
    # Save to CSV (since we don't have a table yet)
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
# PAYMENT DASHBOARD - REAL DATA
# ==============================
def payment_dashboard():
    """Payment Gateway Dashboard with REAL data"""
    
    st.title("💳 Payment Gateway Dashboard")
    st.caption("Manage payments, view transaction history, and process refunds")
    
    role = st.session_state.get("role", "cashier")
    
    if role not in ["owner", "manager"]:
        st.error("❌ Access Denied. Only owners and managers can access payment dashboard.")
        return
    
    init_payment_files()
    
    # ==============================
    # TABS
    # ==============================
    tab1, tab2, tab3 = st.tabs([
        "📊 Payment Summary",
        "📜 Transaction History",
        "⚙️ Gateway Settings"
    ])
    
    # ==============================
    # TAB 1: PAYMENT SUMMARY - REAL DATA
    # ==============================
    with tab1:
        st.markdown("## 📊 Payment Summary")
        
        # Get REAL data
        summary = get_payment_summary(30)
        payments_df = load_payments_from_sales()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("💰 Total Payments", f"${summary['total_amount']:,.2f}")
        with col2:
            st.metric("📊 Total Transactions", summary["total_payments"])
        with col3:
            avg = summary['total_amount'] / summary['total_payments'] if summary['total_payments'] > 0 else 0
            st.metric("💳 Avg Transaction", f"${avg:.2f}")
        
        st.markdown("### 💳 Payment Methods Breakdown")
        
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
            st.markdown("### 📋 Recent Payments")
            display_cols = ["receipt_no", "customer", "total", "payment_method", "date"]
            available_cols = [col for col in display_cols if col in summary["recent_payments"].columns]
            
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
        st.markdown("## 📜 Transaction History")
        
        # Get REAL data
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
                st.info(f"💰 Total Transactions: ${to_float(total_amount):,.2f} | Count: {len(payments_df)}")
                
                # Export
                csv = payments_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Export Transactions (CSV)",
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
        st.markdown("## ⚙️ Gateway Settings")
        
        st.info("🔧 Payment gateway configuration")
        st.markdown("""
        **Available Payment Gateways:**
        - ✅ Cash (Physical)
        - ✅ EcoCash (Mobile Money) - Coming Soon
        - ✅ Card Payments (Visa/Mastercard) - Coming Soon
        - ✅ Bank Transfer - Coming Soon
        - 🔜 PayNow (Coming Soon)
        - 🔜 InnBucks (Coming Soon)
        """)
        
        # Show current payment stats from REAL data
        sales_df = load_sales()
        if not sales_df.empty:
            st.markdown("### 📊 Current Payment Statistics")
            
            total_col = "final_total" if "final_total" in sales_df.columns else "total" if "total" in sales_df.columns else None
            payment_col = "payment_method" if "payment_method" in sales_df.columns else None
            
            if total_col and payment_col:
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Total Sales (All Time)", f"${to_float(sales_df[total_col].sum()):,.2f}")
                with col2:
                    st.metric("Total Transactions", len(sales_df))
                
                # Payment method distribution
                st.markdown("### 📊 Payment Method Distribution")
                method_dist = sales_df.groupby(payment_col)[total_col].sum().apply(to_float)
                st.dataframe(
                    method_dist.reset_index().rename(columns={payment_col: "Method", total_col: "Amount"}),
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Amount": st.column_config.NumberColumn("Amount", format="$%.2f")
                    }
                )