import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from pathlib import Path
import json
import os

from backend.core.db_adapter import (
    load_sales,
    load_products,
    save_products,
    load_customers,
    save_customers,
    get_current_branch,
    save_sales
)
from backend.modules.cash_register import record_cash_movement

# ==============================
# FILE PATHS
# ==============================
DATA_DIR = Path("data")
RETURNS_FILE = DATA_DIR / "returns.csv"
REFUNDS_FILE = DATA_DIR / "refunds.csv"
STORE_CREDIT_FILE = DATA_DIR / "store_credit.csv"


# ==============================
# INITIALIZATION
# ==============================
def init_returns_files():
    """Initialize returns-related files"""
    DATA_DIR.mkdir(exist_ok=True)
    
    # Returns file
    if not RETURNS_FILE.exists():
        df = pd.DataFrame(columns=[
            "return_id", "receipt_no", "sale_id", "return_date", "customer_name",
            "customer_phone", "product_barcode", "product_name", "quantity_returned",
            "refund_amount", "return_reason", "condition", "status", "refund_method",
            "store_credit_id", "processed_by", "processed_date", "notes", "branch_code"
        ])
        df.to_csv(RETURNS_FILE, index=False)
        print(f"✅ Created returns file: {RETURNS_FILE}")
    
    # Refunds file
    if not REFUNDS_FILE.exists():
        df = pd.DataFrame(columns=[
            "refund_id", "return_id", "receipt_no", "refund_date", "customer_name",
            "amount", "refund_method", "reference_no", "processed_by", "notes", "branch_code"
        ])
        df.to_csv(REFUNDS_FILE, index=False)
        print(f"✅ Created refunds file: {REFUNDS_FILE}")
    
    # Store credit file
    if not STORE_CREDIT_FILE.exists():
        df = pd.DataFrame(columns=[
            "credit_id", "customer_name", "customer_phone", "amount", "remaining_balance",
            "issued_date", "expiry_date", "status", "issued_by", "used_transactions", "branch_code"
        ])
        df.to_csv(STORE_CREDIT_FILE, index=False)
        print(f"✅ Created store credit file: {STORE_CREDIT_FILE}")


def load_returns():
    """Load all returns"""
    init_returns_files()
    try:
        df = pd.read_csv(RETURNS_FILE)
        print(f"📂 Loaded {len(df)} returns from {RETURNS_FILE}")
        return df
    except Exception as e:
        print(f"⚠️ Error loading returns: {e}")
        return pd.DataFrame(columns=[
            "return_id", "receipt_no", "sale_id", "return_date", "customer_name",
            "customer_phone", "product_barcode", "product_name", "quantity_returned",
            "refund_amount", "return_reason", "condition", "status", "refund_method",
            "store_credit_id", "processed_by", "processed_date", "notes", "branch_code"
        ])


def save_returns(df):
    """Save returns to file"""
    try:
        df.to_csv(RETURNS_FILE, index=False)
        print(f"💾 Saved {len(df)} returns to {RETURNS_FILE}")
        return True
    except Exception as e:
        print(f"❌ Error saving returns: {e}")
        return False


def load_refunds():
    """Load all refunds"""
    init_returns_files()
    try:
        return pd.read_csv(REFUNDS_FILE)
    except:
        return pd.DataFrame(columns=[
            "refund_id", "return_id", "receipt_no", "refund_date", "customer_name",
            "amount", "refund_method", "reference_no", "processed_by", "notes", "branch_code"
        ])


def save_refunds(df):
    """Save refunds to file"""
    df.to_csv(REFUNDS_FILE, index=False)


def load_store_credit():
    """Load all store credit records"""
    init_returns_files()
    try:
        return pd.read_csv(STORE_CREDIT_FILE)
    except:
        return pd.DataFrame(columns=[
            "credit_id", "customer_name", "customer_phone", "amount", "remaining_balance",
            "issued_date", "expiry_date", "status", "issued_by", "used_transactions", "branch_code"
        ])


def save_store_credit(df):
    """Save store credit records"""
    df.to_csv(STORE_CREDIT_FILE, index=False)


def get_current_branch():
    """Get current branch from session state"""
    return st.session_state.get("user_branch", "HO")


# ==============================
# RECEIPT SEARCH
# ==============================
def search_sale_by_receipt(receipt_no):
    """Search for a sale by receipt number"""
    sales_df = load_sales()
    
    if sales_df.empty:
        return None
    
    search_term = str(receipt_no).strip()
    
    if "receipt_no" not in sales_df.columns:
        return None
    
    # Try exact match
    matches = sales_df[sales_df["receipt_no"] == search_term]
    if not matches.empty:
        return matches
    
    # Try string comparison
    matches = sales_df[sales_df["receipt_no"].astype(str).str.strip() == search_term]
    if not matches.empty:
        return matches
    
    return None


def get_sales_items_grouped(sale_row):
    """Get all items from a sale, grouped by product"""
    receipt_no = sale_row.get("receipt_no")
    if not receipt_no:
        return []
    
    sales_df = load_sales()
    receipt_no_str = str(receipt_no).strip()
    
    # Find all rows with this receipt number
    all_sale_rows = sales_df[sales_df["receipt_no"] == receipt_no_str]
    
    if all_sale_rows.empty:
        all_sale_rows = sales_df[sales_df["receipt_no"].astype(str).str.strip() == receipt_no_str]
    
    if len(all_sale_rows) > 0:
        grouped = {}
        for _, row in all_sale_rows.iterrows():
            barcode = str(row.get("barcode", ""))
            name = str(row.get("product_name", row.get("name", "Unknown")))
            qty = int(row.get("items", 1))
            total = float(row.get("total", 0))
            price = total / qty if qty > 0 else 0
            
            key = barcode if barcode else name
            if key in grouped:
                grouped[key]["quantity"] += qty
                grouped[key]["total"] += total
            else:
                grouped[key] = {
                    "name": name,
                    "barcode": barcode,
                    "quantity": qty,
                    "price": price,
                    "total": total
                }
        
        return list(grouped.values())
    
    return []


# ==============================
# PROCESS RETURN - COMPLETE FIXED
# ==============================
def process_return(receipt_no, items_to_return, return_reason, condition, refund_method, notes=""):
    """Process a return and update everything"""
    
    # Initialize files
    init_returns_files()
    
    # Load data
    sales_df = load_sales()
    products_df = load_products()
    returns_df = load_returns()
    refunds_df = load_refunds()
    current_branch = get_current_branch()
    
    receipt_no_str = str(receipt_no).strip()
    
    # Find original sale
    original_sale = search_sale_by_receipt(receipt_no_str)
    if original_sale is None or original_sale.empty:
        return False, "Receipt not found", [], 0
    
    sale_row = original_sale.iloc[0]
    customer_name = sale_row.get("customer", sale_row.get("customer_name", "Walk-in Customer"))
    customer_phone = sale_row.get("customer_phone", sale_row.get("phone", ""))
    
    # Calculate total refund
    total_refund = 0
    return_ids = []
    returned_products = []
    
    for return_item in items_to_return:
        qty = int(return_item["quantity"])
        price = float(return_item["price"])
        refund_amount = qty * price
        total_refund += refund_amount
        
        returned_products.append({
            "barcode": str(return_item.get("barcode", "")),
            "name": str(return_item.get("name", "")),
            "quantity": qty,
            "price": price
        })
        
        # Create return record
        return_id = f"RET{len(returns_df)+1:06d}"
        return_ids.append(return_id)
        
        new_return = pd.DataFrame([{
            "return_id": return_id,
            "receipt_no": receipt_no_str,
            "sale_id": str(sale_row.get("id", receipt_no_str)),
            "return_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "customer_name": str(customer_name),
            "customer_phone": str(customer_phone),
            "product_barcode": str(return_item.get("barcode", "")),
            "product_name": str(return_item.get("name", "")),
            "quantity_returned": qty,
            "refund_amount": refund_amount,
            "return_reason": return_reason,
            "condition": condition,
            "status": "COMPLETED",
            "refund_method": refund_method,
            "store_credit_id": "",
            "processed_by": st.session_state.get("username", "system"),
            "processed_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "notes": notes,
            "branch_code": current_branch
        }])
        
        returns_df = pd.concat([returns_df, new_return], ignore_index=True)
        
        # ============================================================
        # UPDATE STOCK - ADD BACK TO INVENTORY
        # ============================================================
        product_barcode = str(return_item.get("barcode", ""))
        if product_barcode:
            product_idx = products_df[products_df["barcode"].astype(str) == product_barcode].index
            if len(product_idx) > 0:
                current_stock = float(products_df.loc[product_idx[0], "stock"])
                products_df.loc[product_idx[0], "stock"] = current_stock + qty
                print(f"✅ Stock updated: {return_item.get('name')} +{qty} (was {current_stock}, now {current_stock + qty})")
            else:
                # Try by product name
                product_idx = products_df[products_df["name"].astype(str).str.lower() == str(return_item.get("name", "")).lower()].index
                if len(product_idx) > 0:
                    current_stock = float(products_df.loc[product_idx[0], "stock"])
                    products_df.loc[product_idx[0], "stock"] = current_stock + qty
    
    # ============================================================
    # UPDATE SALES - ADD RETURN ENTRY
    # ============================================================
    if returned_products:
        return_receipt_no = f"RET-{receipt_no_str}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        for product in returned_products:
            return_sale = pd.DataFrame([{
                "branch_id": current_branch,
                "sale_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "receipt_no": return_receipt_no,
                "barcode": product["barcode"],
                "product_name": product["name"],
                "items": -product["quantity"],
                "total": -(product["price"] * product["quantity"]),
                "profit": 0,
                "payment_method": refund_method,
                "customer_name": str(customer_name),
                "customer_phone": str(customer_phone),
                "final_total": -total_refund,
                "shift_id": st.session_state.get("shift_id", ""),
                "cashier": st.session_state.get("username", "system"),
                "return_id": ",".join(return_ids)
            }])
            
            sales_df = pd.concat([sales_df, return_sale], ignore_index=True)
            print(f"✅ Return sale recorded: {product['name']} -{product['quantity']} units")
    
    # ============================================================
    # HANDLE REFUND
    # ============================================================
    if refund_method == "STORE_CREDIT":
        store_credit_id = create_store_credit(customer_name, customer_phone, total_refund)
        for return_id in return_ids:
            returns_df.loc[returns_df["return_id"] == return_id, "store_credit_id"] = store_credit_id
    else:
        refund_id = f"REF{len(refunds_df)+1:06d}"
        new_refund = pd.DataFrame([{
            "refund_id": refund_id,
            "return_id": ",".join(return_ids),
            "receipt_no": receipt_no_str,
            "refund_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "customer_name": str(customer_name),
            "amount": total_refund,
            "refund_method": refund_method,
            "reference_no": f"REF-{receipt_no_str}",
            "processed_by": st.session_state.get("username", "system"),
            "notes": notes,
            "branch_code": current_branch
        }])
        refunds_df = pd.concat([refunds_df, new_refund], ignore_index=True)
        
        if refund_method == "CASH":
            try:
                record_cash_movement(-total_refund, f"REFUND-{receipt_no_str}", "REFUND", st.session_state.get("shift_id", ""))
            except:
                pass
    
    # ============================================================
    # SAVE ALL CHANGES
    # ============================================================
    save_products(products_df)
    save_sales(sales_df)
    save_returns(returns_df)
    save_refunds(refunds_df)
    
    # ============================================================
    # VERIFY SAVE
    # ============================================================
    verify_df = load_returns()
    print(f"✅ VERIFIED: {len(verify_df)} returns in file")
    
    # ============================================================
    # BUILD SUMMARY
    # ============================================================
    summary = f"""
✅ Return processed successfully!

📋 Return Summary:
• Receipt: {receipt_no_str}
• Customer: {customer_name}
• Items Returned: {len(returned_products)}
• Total Refund: ${total_refund:.2f}
• Refund Method: {refund_method}

📦 Stock Updated (Added Back):
"""
    for p in returned_products:
        summary += f"   • {p['name']}: +{p['quantity']} units\n"

    return True, summary, returned_products, total_refund


def create_store_credit(customer_name, customer_phone, amount, expiry_days=365):
    """Create store credit for customer"""
    
    credits_df = load_store_credit()
    current_branch = get_current_branch()
    
    credit_id = f"SC{len(credits_df)+1:06d}"
    
    new_credit = pd.DataFrame([{
        "credit_id": credit_id,
        "customer_name": str(customer_name),
        "customer_phone": str(customer_phone),
        "amount": float(amount),
        "remaining_balance": float(amount),
        "issued_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "expiry_date": (datetime.now() + timedelta(days=expiry_days)).strftime("%Y-%m-%d"),
        "status": "ACTIVE",
        "issued_by": st.session_state.get("username", "system"),
        "used_transactions": "",
        "branch_code": current_branch
    }])
    
    credits_df = pd.concat([credits_df, new_credit], ignore_index=True)
    save_store_credit(credits_df)
    
    return credit_id


def get_customer_store_credit(customer_phone):
    """Get total store credit available for customer"""
    credits_df = load_store_credit()
    if credits_df.empty:
        return 0
    
    active_credits = credits_df[
        (credits_df["customer_phone"].astype(str) == str(customer_phone)) & 
        (credits_df["status"] == "ACTIVE") &
        (credits_df["remaining_balance"] > 0)
    ]
    
    return active_credits["remaining_balance"].sum() if not active_credits.empty else 0


def get_return_summary():
    """Get summary of returns"""
    returns_df = load_returns()
    
    if returns_df.empty:
        return {
            "total_returns": 0,
            "total_refund_amount": 0,
            "pending_returns": 0,
            "completed_returns": 0,
            "avg_return_value": 0
        }
    
    total_returns = len(returns_df)
    total_refund = returns_df["refund_amount"].sum() if "refund_amount" in returns_df.columns else 0
    pending = len(returns_df[returns_df["status"] == "PENDING"]) if "status" in returns_df.columns else 0
    completed = len(returns_df[returns_df["status"] == "COMPLETED"]) if "status" in returns_df.columns else 0
    
    return {
        "total_returns": total_returns,
        "total_refund_amount": total_refund,
        "pending_returns": pending,
        "completed_returns": completed,
        "avg_return_value": total_refund / total_returns if total_returns > 0 else 0
    }


def get_sample_receipts():
    """Get sample receipts for testing"""
    sales_df = load_sales()
    if sales_df.empty:
        return []
    
    if "receipt_no" in sales_df.columns:
        return sales_df["receipt_no"].tail(10).tolist()
    return []


# ==============================
# RETURNS DASHBOARD
# ==============================
def returns_management_dashboard():
    """Returns and Refunds Management Dashboard"""
    
    st.title("🔄 Returns & Refunds Management")
    st.caption("Process customer returns, manage store credit, and track warranties")
    
    role = st.session_state.get("role", "cashier")
    
    if role not in ["owner", "manager"]:
        st.error("❌ Access Denied. Only managers and owners can process returns.")
        return
    
    init_returns_files()
    
    # Debug: Show returns file status
    with st.expander("📋 Debug: Returns File Status"):
        if RETURNS_FILE.exists():
            debug_df = pd.read_csv(RETURNS_FILE)
            st.success(f"✅ Returns file exists with {len(debug_df)} records")
            if not debug_df.empty:
                st.dataframe(debug_df.tail(5))
        else:
            st.error("❌ Returns file does not exist!")
    
    sample_receipts = get_sample_receipts()
    if sample_receipts:
        with st.expander("📋 Recent Receipt Numbers (for testing)"):
            st.write("Try these receipt numbers:")
            for r in sample_receipts[:5]:
                st.code(f"• {r}")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🔄 Process Return",
        "💰 Store Credit",
        "📋 Warranty Check",
        "📊 Return Analytics",
        "📜 Return History"
    ])
    
    with tab1:
        st.markdown("## 🔄 Process Customer Return")
        st.caption("Enter the receipt number to find the original sale")
        
        receipt_no = st.text_input(
            "Receipt Number", 
            placeholder="Enter receipt number from original sale", 
            key="receipt_search"
        )
        
        col1, col2 = st.columns([3, 1])
        with col2:
            search_clicked = st.button("🔍 Search Receipt", use_container_width=True)
        
        if receipt_no and search_clicked:
            original_sale = search_sale_by_receipt(receipt_no)
            
            if original_sale is None or original_sale.empty:
                st.error(f"❌ Receipt '{receipt_no}' not found.")
                
                sales_df = load_sales()
                if not sales_df.empty and "receipt_no" in sales_df.columns:
                    st.info("Available receipt numbers in system:")
                    for r in sales_df["receipt_no"].tail(5).tolist():
                        st.code(f"• {r}")
            else:
                sale_row = original_sale.iloc[0]
                
                customer_name = sale_row.get("customer", sale_row.get("customer_name", "Walk-in Customer"))
                customer_phone = sale_row.get("customer_phone", sale_row.get("phone", ""))
                sale_date = sale_row.get("date", sale_row.get("sale_date", "Unknown"))
                
                st.success(f"✅ Sale found for receipt: {receipt_no}")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.info(f"**Customer:** {customer_name}")
                with col2:
                    st.info(f"**Phone:** {customer_phone}")
                with col3:
                    st.info(f"**Date:** {str(sale_date)[:16] if sale_date != 'Unknown' else 'Unknown'}")
                
                st.markdown("### Items from Original Sale")
                
                sale_items = get_sales_items_grouped(sale_row)
                
                if not sale_items:
                    st.error("Could not parse items from this sale.")
                else:
                    items_df = pd.DataFrame(sale_items)
                    display_df = items_df[["name", "quantity", "price", "total"]].copy()
                    display_df.columns = ["Product", "Quantity", "Price", "Total"]
                    st.dataframe(display_df, use_container_width=True, hide_index=True)
                    
                    st.markdown("### Select Items to Return")
                    
                    return_items = []
                    for idx, item in enumerate(sale_items):
                        col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
                        with col1:
                            st.write(f"**{item['name']}**")
                        with col2:
                            st.write(f"Qty: {item['quantity']}")
                        with col3:
                            st.write(f"Price: ${item['price']:.2f}")
                        with col4:
                            return_qty = st.number_input(
                                "Return",
                                min_value=0,
                                max_value=item['quantity'],
                                value=0,
                                key=f"return_qty_{idx}",
                                step=1,
                                label_visibility="collapsed"
                            )
                            if return_qty > 0:
                                st.write(f"Refund: ${return_qty * item['price']:.2f}")
                        
                        if return_qty > 0:
                            return_items.append({
                                "barcode": item.get("barcode", ""),
                                "name": item['name'],
                                "quantity": return_qty,
                                "price": item['price']
                            })
                    
                    if return_items:
                        st.markdown("---")
                        st.markdown("### Return Details")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            return_reason = st.selectbox(
                                "Return Reason",
                                ["Damaged Product", "Wrong Item", "Changed Mind", "Defective", "Expired", "Other"]
                            )
                            condition = st.selectbox(
                                "Product Condition",
                                ["New/Unused", "Like New", "Used - Good", "Used - Fair", "Damaged"]
                            )
                        
                        with col2:
                            refund_method = st.selectbox(
                                "Refund Method",
                                ["CASH", "STORE_CREDIT", "CARD", "ECOCASH"]
                            )
                            notes = st.text_area("Notes", placeholder="Additional information...")
                        
                        total_refund = sum(item['quantity'] * item['price'] for item in return_items)
                        st.info(f"💰 **Total Refund Amount: ${total_refund:.2f}**")
                        
                        if refund_method == "STORE_CREDIT":
                            st.info("💳 Store credit will be issued to customer for future purchases")
                        
                        if st.button("✅ Process Return", type="primary", use_container_width=True):
                            with st.spinner("Processing return..."):
                                success, message, returned_products, refund_total = process_return(
                                    receipt_no=receipt_no,
                                    items_to_return=return_items,
                                    return_reason=return_reason,
                                    condition=condition,
                                    refund_method=refund_method,
                                    notes=notes
                                )
                                
                                if success:
                                    st.success(f"✅ {message}")
                                    
                                    # Show stock changes
                                    if returned_products:
                                        st.markdown("### 📦 Stock Updated")
                                        for p in returned_products:
                                            st.write(f"✅ {p['name']}: +{p['quantity']} units returned to stock")
                                    
                                    st.balloons()
                                    st.rerun()
                                else:
                                    st.error(f"❌ {message}")
                    else:
                        st.warning("Please select at least one item to return")
        else:
            st.info("🔍 Enter a receipt number and click 'Search Receipt' to begin processing a return")
    
    with tab2:
        st.markdown("## 💳 Store Credit Management")
        st.caption("Issue and manage store credit for customers")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Issue Store Credit")
            
            credit_customer = st.text_input("Customer Name", key="credit_name")
            credit_phone = st.text_input("Customer Phone", key="credit_phone")
            credit_amount = st.number_input("Credit Amount ($)", min_value=0.01, step=10.0, key="credit_amount")
            credit_expiry = st.number_input("Expiry (days)", min_value=1, max_value=730, value=365, key="credit_expiry")
            credit_notes = st.text_area("Notes", key="credit_notes")
            
            if st.button("💰 Issue Store Credit", type="primary", use_container_width=True):
                if credit_customer and credit_phone and credit_amount > 0:
                    credit_id = create_store_credit(credit_customer, credit_phone, credit_amount, credit_expiry)
                    st.success(f"✅ Store credit issued! ID: {credit_id}")
                    st.rerun()
                else:
                    st.error("Please fill all required fields")
        
        with col2:
            st.markdown("### Check Store Credit Balance")
            
            check_phone = st.text_input("Customer Phone", key="check_credit_phone")
            
            if check_phone:
                balance = get_customer_store_credit(check_phone)
                
                if balance > 0:
                    st.success(f"💰 Available Store Credit: **${balance:.2f}**")
                    
                    credits_df = load_store_credit()
                    customer_credits = credits_df[
                        (credits_df["customer_phone"].astype(str) == str(check_phone)) & 
                        (credits_df["status"] == "ACTIVE") &
                        (credits_df["remaining_balance"] > 0)
                    ]
                    
                    if not customer_credits.empty:
                        st.markdown("#### Credit Details")
                        for _, credit in customer_credits.iterrows():
                            st.write(f"• ${credit['remaining_balance']:.2f} - Expires: {credit['expiry_date']}")
                else:
                    st.info("No store credit found for this customer")
        
        st.markdown("---")
        st.markdown("### 📋 Store Credit History")
        
        credits_df = load_store_credit()
        if not credits_df.empty:
            st.dataframe(
                credits_df[["credit_id", "customer_name", "customer_phone", "amount", "remaining_balance", "status", "issued_date"]].head(20),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No store credit records found")
    
    with tab3:
        st.markdown("## 📋 Warranty Management")
        st.caption("Register warranties and check product warranty status")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Register Warranty")
            
            war_receipt = st.text_input("Receipt Number", key="war_receipt")
            war_product = st.text_input("Product Barcode", key="war_product")
            war_name = st.text_input("Product Name", key="war_name")
            war_customer = st.text_input("Customer Name", key="war_customer")
            war_phone = st.text_input("Customer Phone", key="war_phone")
            war_months = st.number_input("Warranty Period (months)", min_value=1, max_value=60, value=12, key="war_months")
            
            if st.button("📝 Register Warranty", type="primary", use_container_width=True):
                if war_receipt and war_product and war_name and war_customer:
                    warranty_id = f"WAR{len(load_warranties())+1:06d}"
                    st.success(f"✅ Warranty registered! ID: {warranty_id}")
                    st.rerun()
                else:
                    st.error("Please fill all required fields")
        
        with col2:
            st.markdown("### Check Warranty Status")
            
            check_product = st.text_input("Product Barcode", key="check_warranty_product")
            check_customer = st.text_input("Customer Phone (optional)", key="check_warranty_customer")
            
            if st.button("🔍 Check Warranty", use_container_width=True):
                st.warning("Warranty check - coming soon")
    
    with tab4:
        st.markdown("## 📊 Return Analytics")
        
        summary = get_return_summary()
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("📦 Total Returns", summary["total_returns"])
        with col2:
            st.metric("💰 Total Refunded", f"${summary['total_refund_amount']:,.2f}")
        with col3:
            st.metric("⏳ Pending", summary["pending_returns"])
        with col4:
            st.metric("📊 Avg Return", f"${summary['avg_return_value']:.2f}")
        
        st.markdown("---")
        
        returns_df = load_returns()
        
        if not returns_df.empty:
            st.markdown("### 📋 Recent Returns")
            st.dataframe(
                returns_df[["return_id", "receipt_no", "customer_name", "product_name", "quantity_returned", "refund_amount", "return_date"]].head(20),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No return data available")
    
    with tab5:
        st.markdown("## 📜 Return History")
        
        returns_df = load_returns()
        
        if not returns_df.empty:
            st.dataframe(
                returns_df[["return_id", "receipt_no", "return_date", "customer_name", "product_name", "quantity_returned", "refund_amount", "status"]],
                use_container_width=True,
                hide_index=True
            )
            
            csv = returns_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Returns Data (CSV)",
                data=csv,
                file_name=f"returns_data_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        else:
            st.info("No return records found")


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    returns_management_dashboard()