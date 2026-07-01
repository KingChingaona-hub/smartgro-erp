import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

from backend.core.db_adapter import (
    load_sales,
    load_products,
    save_products,
    get_current_branch,
    save_sales
)
from backend.modules.cash_register import record_cash_movement

# ==============================
# CONSTANTS & FILE PATHS
# ==============================
DATA_DIR = Path("data")
RETURNS_FILE = DATA_DIR / "returns.csv"
REFUNDS_FILE = DATA_DIR / "refunds.csv"
STORE_CREDIT_FILE = DATA_DIR / "store_credit.csv"

RETURN_COLUMNS = [
    "return_id", "receipt_no", "return_date", "customer_name", "customer_phone",
    "product_barcode", "product_name", "quantity_returned", "refund_amount",
    "return_reason", "condition", "status", "refund_method", "store_credit_id",
    "processed_by", "processed_date", "notes"
]

REFUND_COLUMNS = [
    "refund_id", "return_id", "receipt_no", "refund_date", "customer_name",
    "amount", "refund_method", "reference_no", "processed_by", "notes"
]

STORE_CREDIT_COLUMNS = [
    "credit_id", "customer_name", "customer_phone", "amount", "remaining_balance",
    "issued_date", "expiry_date", "status", "issued_by", "used_transactions"
]


# ==============================
# FILE OPERATIONS
# ==============================
def init_files():
    """Initialize all required CSV files"""
    DATA_DIR.mkdir(exist_ok=True)
    
    if not RETURNS_FILE.exists():
        pd.DataFrame(columns=RETURN_COLUMNS).to_csv(RETURNS_FILE, index=False)
    
    if not REFUNDS_FILE.exists():
        pd.DataFrame(columns=REFUND_COLUMNS).to_csv(REFUNDS_FILE, index=False)
    
    if not STORE_CREDIT_FILE.exists():
        pd.DataFrame(columns=STORE_CREDIT_COLUMNS).to_csv(STORE_CREDIT_FILE, index=False)


def load_returns():
    """Load returns data"""
    init_files()
    try:
        return pd.read_csv(RETURNS_FILE)
    except:
        return pd.DataFrame(columns=RETURN_COLUMNS)


def save_returns(df):
    """Save returns data"""
    df.to_csv(RETURNS_FILE, index=False)
    return True


def load_refunds():
    """Load refunds data"""
    init_files()
    try:
        return pd.read_csv(REFUNDS_FILE)
    except:
        return pd.DataFrame(columns=REFUND_COLUMNS)


def save_refunds(df):
    """Save refunds data"""
    df.to_csv(REFUNDS_FILE, index=False)
    return True


def load_store_credit():
    """Load store credit data"""
    init_files()
    try:
        return pd.read_csv(STORE_CREDIT_FILE)
    except:
        return pd.DataFrame(columns=STORE_CREDIT_COLUMNS)


def save_store_credit(df):
    """Save store credit data"""
    df.to_csv(STORE_CREDIT_FILE, index=False)
    return True


# ==============================
# CORE BUSINESS LOGIC
# ==============================
def find_sale_by_receipt(receipt_no):
    """Find a sale by receipt number"""
    sales_df = load_sales()
    if sales_df.empty:
        return None
    
    receipt_no = str(receipt_no).strip()
    
    if "receipt_no" not in sales_df.columns:
        return None
    
    # Try exact match
    matches = sales_df[sales_df["receipt_no"] == receipt_no]
    if not matches.empty:
        return matches
    
    # Try string match
    matches = sales_df[sales_df["receipt_no"].astype(str).str.strip() == receipt_no]
    if not matches.empty:
        return matches
    
    return None


def get_sale_items(receipt_no):
    """Get all items from a sale grouped by product"""
    sales_df = load_sales()
    receipt_no = str(receipt_no).strip()
    
    # Find all rows with this receipt
    sale_rows = sales_df[sales_df["receipt_no"] == receipt_no]
    if sale_rows.empty:
        sale_rows = sales_df[sales_df["receipt_no"].astype(str).str.strip() == receipt_no]
    
    if sale_rows.empty:
        return []
    
    # Group items by product
    grouped = {}
    for _, row in sale_rows.iterrows():
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


def process_return(receipt_no, items, reason, condition, refund_method, notes=""):
    """
    Process a return - main business logic
    Returns: (success, message, returned_products, total_refund)
    """
    init_files()
    
    # Load all data
    sales_df = load_sales()
    products_df = load_products()
    returns_df = load_returns()
    refunds_df = load_refunds()
    current_branch = get_current_branch()
    
    receipt_no = str(receipt_no).strip()
    
    # Verify sale exists
    original_sale = find_sale_by_receipt(receipt_no)
    if original_sale is None or original_sale.empty:
        return False, "Receipt not found", [], 0
    
    sale_row = original_sale.iloc[0]
    customer_name = sale_row.get("customer", sale_row.get("customer_name", "Walk-in Customer"))
    customer_phone = sale_row.get("customer_phone", sale_row.get("phone", ""))
    
    total_refund = 0
    return_ids = []
    returned_products = []
    
    # Process each returned item
    for item in items:
        qty = int(item["quantity"])
        price = float(item["price"])
        refund_amount = qty * price
        total_refund += refund_amount
        
        returned_products.append({
            "barcode": str(item.get("barcode", "")),
            "name": str(item.get("name", "")),
            "quantity": qty,
            "price": price
        })
        
        # Create return record
        return_id = f"RET{len(returns_df)+1:06d}"
        return_ids.append(return_id)
        
        new_return = pd.DataFrame([{
            "return_id": return_id,
            "receipt_no": receipt_no,
            "return_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "customer_name": str(customer_name),
            "customer_phone": str(customer_phone),
            "product_barcode": str(item.get("barcode", "")),
            "product_name": str(item.get("name", "")),
            "quantity_returned": qty,
            "refund_amount": refund_amount,
            "return_reason": reason,
            "condition": condition,
            "status": "COMPLETED",
            "refund_method": refund_method,
            "store_credit_id": "",
            "processed_by": st.session_state.get("username", "system"),
            "processed_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "notes": notes
        }])
        
        returns_df = pd.concat([returns_df, new_return], ignore_index=True)
        
        # Update stock - add returned quantity back
        barcode = str(item.get("barcode", ""))
        if barcode:
            idx = products_df[products_df["barcode"].astype(str) == barcode].index
            if len(idx) > 0:
                current_stock = float(products_df.loc[idx[0], "stock"])
                products_df.loc[idx[0], "stock"] = current_stock + qty
    
    # Create negative sale entry for return
    return_receipt = f"RET-{receipt_no}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    for product in returned_products:
        return_sale = pd.DataFrame([{
            "branch_id": current_branch,
            "sale_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "receipt_no": return_receipt,
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
    
    # Handle refund
    if refund_method == "STORE_CREDIT":
        credit_id = create_store_credit(customer_name, customer_phone, total_refund)
        for rid in return_ids:
            returns_df.loc[returns_df["return_id"] == rid, "store_credit_id"] = credit_id
    else:
        refund_id = f"REF{len(refunds_df)+1:06d}"
        new_refund = pd.DataFrame([{
            "refund_id": refund_id,
            "return_id": ",".join(return_ids),
            "receipt_no": receipt_no,
            "refund_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "customer_name": str(customer_name),
            "amount": total_refund,
            "refund_method": refund_method,
            "reference_no": f"REF-{receipt_no}",
            "processed_by": st.session_state.get("username", "system"),
            "notes": notes
        }])
        refunds_df = pd.concat([refunds_df, new_refund], ignore_index=True)
        
        if refund_method == "CASH":
            try:
                record_cash_movement(-total_refund, f"REFUND-{receipt_no}", "REFUND", st.session_state.get("shift_id", ""))
            except:
                pass
    
    # Save everything
    save_products(products_df)
    save_sales(sales_df)
    save_returns(returns_df)
    save_refunds(refunds_df)
    
    return True, "Return processed successfully", returned_products, total_refund


def create_store_credit(customer_name, customer_phone, amount, expiry_days=365):
    """Create store credit for customer"""
    credits_df = load_store_credit()
    
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
        "used_transactions": ""
    }])
    
    credits_df = pd.concat([credits_df, new_credit], ignore_index=True)
    save_store_credit(credits_df)
    
    return credit_id


def get_customer_store_credit(phone):
    """Get available store credit for a customer"""
    credits_df = load_store_credit()
    if credits_df.empty:
        return 0
    
    active = credits_df[
        (credits_df["customer_phone"].astype(str) == str(phone)) &
        (credits_df["status"] == "ACTIVE") &
        (credits_df["remaining_balance"] > 0)
    ]
    
    return active["remaining_balance"].sum() if not active.empty else 0


def get_return_stats():
    """Get return statistics"""
    returns_df = load_returns()
    
    if returns_df.empty:
        return {
            "total": 0,
            "refund_amount": 0,
            "completed": 0,
            "pending": 0,
            "avg_value": 0
        }
    
    total = len(returns_df)
    refund = returns_df["refund_amount"].sum() if "refund_amount" in returns_df.columns else 0
    
    return {
        "total": total,
        "refund_amount": refund,
        "completed": total,
        "pending": 0,
        "avg_value": refund / total if total > 0 else 0
    }


def get_sample_receipts():
    """Get sample receipt numbers for testing"""
    sales_df = load_sales()
    if sales_df.empty:
        return []
    if "receipt_no" in sales_df.columns:
        return sales_df["receipt_no"].tail(10).tolist()
    return []


# ==============================
# UI COMPONENTS
# ==============================
def render_process_return_tab():
    """Render the Process Return tab"""
    
    st.markdown("## 🔄 Process Customer Return")
    st.caption("Enter the receipt number to find the original sale")
    
    receipt_no = st.text_input(
        "Receipt Number",
        placeholder="Enter receipt number from original sale",
        key="return_receipt_input"
    )
    
    col1, col2 = st.columns([3, 1])
    with col2:
        search_clicked = st.button("🔍 Search Receipt", use_container_width=True)
    
    # Reset session state for return items
    if "return_items" not in st.session_state:
        st.session_state.return_items = []
    if "return_found" not in st.session_state:
        st.session_state.return_found = False
    
    if receipt_no and search_clicked:
        original_sale = find_sale_by_receipt(receipt_no)
        
        if original_sale is None or original_sale.empty:
            st.error(f"❌ Receipt '{receipt_no}' not found.")
            st.session_state.return_found = False
            st.session_state.return_items = []
            
            sales_df = load_sales()
            if not sales_df.empty and "receipt_no" in sales_df.columns:
                st.info("Available receipt numbers in system:")
                for r in sales_df["receipt_no"].tail(5).tolist():
                    st.code(f"• {r}")
        else:
            sale_row = original_sale.iloc[0]
            st.session_state.return_found = True
            
            # Display sale info
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
            
            # Display items
            st.markdown("### Items from Original Sale")
            
            sale_items = get_sale_items(receipt_no)
            
            if not sale_items:
                st.error("Could not parse items from this sale.")
                st.session_state.return_items = []
            else:
                items_df = pd.DataFrame(sale_items)
                display_df = items_df[["name", "quantity", "price", "total"]].copy()
                display_df.columns = ["Product", "Quantity", "Price", "Total"]
                st.dataframe(display_df, use_container_width=True, hide_index=True)
                
                st.markdown("### Select Items to Return")
                
                # Allow user to select quantities
                selected_items = []
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
                            key=f"ret_qty_{idx}",
                            step=1,
                            label_visibility="collapsed"
                        )
                        if return_qty > 0:
                            st.write(f"Refund: ${return_qty * item['price']:.2f}")
                    
                    if return_qty > 0:
                        selected_items.append({
                            "barcode": item.get("barcode", ""),
                            "name": item['name'],
                            "quantity": return_qty,
                            "price": item['price']
                        })
                
                st.session_state.return_items = selected_items
                
                # Show return form if items selected
                if selected_items:
                    st.markdown("---")
                    st.markdown("### Return Details")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        reason = st.selectbox(
                            "Return Reason",
                            ["Damaged Product", "Wrong Item", "Changed Mind", "Defective", "Expired", "Other"],
                            key="return_reason"
                        )
                        condition = st.selectbox(
                            "Product Condition",
                            ["New/Unused", "Like New", "Used - Good", "Used - Fair", "Damaged"],
                            key="return_condition"
                        )
                    
                    with col2:
                        refund_method = st.selectbox(
                            "Refund Method",
                            ["CASH", "STORE_CREDIT", "CARD", "ECOCASH"],
                            key="return_method"
                        )
                        notes = st.text_area("Notes", placeholder="Additional information...", key="return_notes")
                    
                    total_refund = sum(item['quantity'] * item['price'] for item in selected_items)
                    st.info(f"💰 **Total Refund Amount: ${total_refund:.2f}**")
                    
                    if refund_method == "STORE_CREDIT":
                        st.info("💳 Store credit will be issued to customer for future purchases")
                    
                    # PROCESS RETURN BUTTON
                    if st.button("✅ PROCESS RETURN", type="primary", use_container_width=True):
                        with st.spinner("Processing return..."):
                            success, message, returned_products, refund_total = process_return(
                                receipt_no=receipt_no,
                                items=selected_items,
                                reason=reason,
                                condition=condition,
                                refund_method=refund_method,
                                notes=notes
                            )
                            
                            if success:
                                st.success(f"✅ {message}")
                                
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
    
    elif not receipt_no:
        st.info("🔍 Enter a receipt number and click 'Search Receipt' to begin processing a return")


def render_store_credit_tab():
    """Render the Store Credit tab"""
    
    st.markdown("## 💳 Store Credit Management")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Issue Store Credit")
        
        customer = st.text_input("Customer Name", key="sc_name")
        phone = st.text_input("Customer Phone", key="sc_phone")
        amount = st.number_input("Credit Amount ($)", min_value=0.01, step=10.0, key="sc_amount")
        expiry = st.number_input("Expiry (days)", min_value=1, max_value=730, value=365, key="sc_expiry")
        notes = st.text_area("Notes", key="sc_notes")
        
        if st.button("💰 Issue Store Credit", type="primary", use_container_width=True):
            if customer and phone and amount > 0:
                credit_id = create_store_credit(customer, phone, amount, expiry)
                st.success(f"✅ Store credit issued! ID: {credit_id}")
                st.rerun()
            else:
                st.error("Please fill all required fields")
    
    with col2:
        st.markdown("### Check Store Credit Balance")
        
        check_phone = st.text_input("Customer Phone", key="sc_check_phone")
        
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


def render_return_analytics_tab():
    """Render the Return Analytics tab"""
    
    st.markdown("## 📊 Return Analytics")
    
    stats = get_return_stats()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📦 Total Returns", stats["total"])
    with col2:
        st.metric("💰 Total Refunded", f"${stats['refund_amount']:,.2f}")
    with col3:
        st.metric("⏳ Pending", stats["pending"])
    with col4:
        st.metric("📊 Avg Return", f"${stats['avg_value']:.2f}")
    
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


def render_return_history_tab():
    """Render the Return History tab"""
    
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
# MAIN DASHBOARD
# ==============================
def returns_management_dashboard():
    """Main Returns and Refunds Management Dashboard"""
    
    st.title("🔄 Returns & Refunds Management")
    st.caption("Process customer returns, manage store credit, and track warranties")
    
    # Security check
    role = st.session_state.get("role", "cashier")
    if role not in ["owner", "manager"]:
        st.error("❌ Access Denied. Only managers and owners can process returns.")
        return
    
    # Initialize files
    init_files()
    
    # Show sample receipts for testing
    sample_receipts = get_sample_receipts()
    if sample_receipts:
        with st.expander("📋 Recent Receipt Numbers (for testing)"):
            for r in sample_receipts[:5]:
                st.code(f"• {r}")
    
    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "🔄 Process Return",
        "💰 Store Credit",
        "📊 Return Analytics",
        "📜 Return History"
    ])
    
    with tab1:
        render_process_return_tab()
    
    with tab2:
        render_store_credit_tab()
    
    with tab3:
        render_return_analytics_tab()
    
    with tab4:
        render_return_history_tab()


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    returns_management_dashboard()