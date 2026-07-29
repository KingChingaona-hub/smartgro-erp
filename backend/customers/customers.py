# backend/customers/customer.py
import streamlit as st
import re
from datetime import datetime

from backend.core.db_adapter import record_customer_purchase, load_customers, load_sales


# ==============================
# HELPER FUNCTIONS
# ==============================

def normalize_phone(phone):
    """Normalize phone number for storage"""
    if not phone:
        return ""
    cleaned = re.sub(r'\D', '', str(phone))
    if cleaned.startswith('0'):
        cleaned = cleaned[1:]
    if cleaned.endswith('.0'):
        cleaned = cleaned[:-2]
    return cleaned


def normalize_phone_for_display(phone):
    """Convert phone to display format (with leading 0)"""
    if not phone:
        return ""
    cleaned = re.sub(r'\D', '', str(phone).replace('.0', ''))
    if len(cleaned) == 9:
        cleaned = '0' + cleaned
    return cleaned


def validate_phone(phone):
    """Validate Zimbabwe phone number"""
    if not phone:
        return False
    cleaned = re.sub(r'\D', '', str(phone))
    # Zimbabwe numbers: 9 digits (starting with 0) or 10 digits (starting with 263)
    if len(cleaned) == 9 and cleaned.startswith('0'):
        return True
    if len(cleaned) == 10 and cleaned.startswith('263'):
        return True
    return False


def get_customer_by_phone(phone, customers_df):
    """Find customer by phone number"""
    if customers_df is None or customers_df.empty:
        return None
    
    phone_col = None
    for col in ["phone", "customer_phone", "contact"]:
        if col in customers_df.columns:
            phone_col = col
            break
    
    if phone_col is None:
        return None
    
    search_phone = normalize_phone(phone)
    
    for idx, row in customers_df.iterrows():
        db_phone = str(row.get(phone_col, "")).strip()
        db_phone_clean = normalize_phone(db_phone)
        if db_phone_clean == search_phone:
            return row.to_dict()
    
    return None


def get_customer_by_name(name, customers_df):
    """Find customer by name"""
    if customers_df is None or customers_df.empty:
        return None
    
    name_col = None
    for col in ["customer_name", "name", "customer"]:
        if col in customers_df.columns:
            name_col = col
            break
    
    if name_col is None:
        return None
    
    search_name = name.strip().lower()
    
    for idx, row in customers_df.iterrows():
        db_name = str(row.get(name_col, "")).strip().lower()
        if search_name in db_name or db_name in search_name:
            return row.to_dict()
    
    return None


# ==============================
# CUSTOMER SESSION INIT
# ==============================
def init_customer_session():
    """Initialize customer session state"""
    if "customer_name" not in st.session_state:
        st.session_state.customer_name = ""
    
    if "customer_phone" not in st.session_state:
        st.session_state.customer_phone = ""
    
    if "customer_attached" not in st.session_state:
        st.session_state.customer_attached = False
    
    if "customer_id" not in st.session_state:
        st.session_state.customer_id = None
    
    if "customer_found" not in st.session_state:
        st.session_state.customer_found = False


# ==============================
# CUSTOMER CAPTURE FORM (POS SIDE)
# ==============================
def customer_capture_form():
    """
    Enhanced customer capture form for POS
    Returns: (customer_attached, customer_data)
    """
    
    st.markdown("## Customer Details")
    st.caption("Enter customer details or search by phone")
    
    # Load customers for lookup
    try:
        customers_df = load_customers()
    except:
        customers_df = pd.DataFrame()
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Phone input with lookup
        phone_input = st.text_input(
            "Phone Number",
            value=st.session_state.customer_phone,
            placeholder="e.g., 0782905853",
            key="customer_phone_input"
        )
        
        # Lookup button
        if st.button("Lookup Customer", key="lookup_customer_btn"):
            if phone_input and validate_phone(phone_input):
                customer = get_customer_by_phone(phone_input, customers_df)
                if customer:
                    name = customer.get("customer_name", customer.get("name", ""))
                    st.session_state.customer_name = name
                    st.session_state.customer_phone = phone_input
                    st.session_state.customer_found = True
                    st.success(f"Customer found: {name}")
                    st.rerun()
                else:
                    st.warning("Customer not found. Please enter name to register.")
                    st.session_state.customer_found = False
            else:
                st.error("Please enter a valid phone number")
    
    with col2:
        name_input = st.text_input(
            "Customer Name",
            value=st.session_state.customer_name,
            placeholder="John Doe",
            key="customer_name_input"
        )
    
    # Show customer found status
    if st.session_state.customer_found:
        st.info(f"📋 Existing customer: {st.session_state.customer_name}")
    
    # Attach button
    col1, col2 = st.columns(2)
    
    with col1:
        attach = st.button("Attach Customer", type="primary", use_container_width=True)
    
    with col2:
        if st.button("Clear", use_container_width=True):
            reset_customer()
            st.rerun()
    
    if attach:
        if name_input.strip() == "":
            st.error("Customer name is required")
            return False, None
        
        if phone_input.strip() == "":
            st.error("Phone number is required")
            return False, None
        
        if not validate_phone(phone_input):
            st.error("Please enter a valid Zimbabwe phone number (e.g., 0782905853)")
            return False, None
        
        # Store in session
        st.session_state.customer_name = name_input.strip().title()
        st.session_state.customer_phone = normalize_phone(phone_input)
        st.session_state.customer_attached = True
        
        # Try to find existing customer
        customer = get_customer_by_phone(phone_input, customers_df)
        if customer:
            st.session_state.customer_id = customer.get("customer_id", "")
            st.session_state.customer_found = True
            st.success(f"Customer attached: {name_input} ({phone_input})")
        else:
            st.session_state.customer_found = False
            st.success(f"New customer attached: {name_input} ({phone_input})")
        
        return True, {
            "name": st.session_state.customer_name,
            "phone": st.session_state.customer_phone,
            "id": st.session_state.customer_id,
            "is_existing": st.session_state.customer_found
        }
    
    # Return current state
    if st.session_state.customer_attached:
        return True, {
            "name": st.session_state.customer_name,
            "phone": st.session_state.customer_phone,
            "id": st.session_state.customer_id,
            "is_existing": st.session_state.customer_found
        }
    
    return False, None


# ==============================
# SIMPLE CUSTOMER CAPTURE (Quick POS)
# ==============================
def quick_customer_capture():
    """
    Simplified customer capture for quick POS
    Returns: (customer_name, customer_phone)
    """
    
    st.markdown("### Quick Customer")
    
    col1, col2 = st.columns(2)
    
    with col1:
        name = st.text_input(
            "Name",
            value=st.session_state.customer_name,
            placeholder="Customer name",
            key="quick_customer_name"
        )
    
    with col2:
        phone = st.text_input(
            "Phone",
            value=st.session_state.customer_phone,
            placeholder="Phone number",
            key="quick_customer_phone"
        )
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Attach", type="primary", use_container_width=True):
            if name.strip() and phone.strip():
                st.session_state.customer_name = name.strip().title()
                st.session_state.customer_phone = normalize_phone(phone)
                st.session_state.customer_attached = True
                st.success(f"Customer: {name}")
                st.rerun()
            else:
                st.error("Name and phone required")
    
    with col2:
        if st.button("Walk-in", use_container_width=True):
            reset_customer()
            st.session_state.customer_attached = True
            st.info("Walk-in customer")
            st.rerun()
    
    if st.session_state.customer_attached:
        display_phone = normalize_phone_for_display(st.session_state.customer_phone)
        if st.session_state.customer_name:
            st.success(f"👤 {st.session_state.customer_name} ({display_phone})")
        else:
            st.info("🚶 Walk-in customer")
    
    return st.session_state.customer_name, st.session_state.customer_phone


# ==============================
# RESET CUSTOMER AFTER SALE
# ==============================
def reset_customer():
    """Reset customer session"""
    st.session_state.customer_name = ""
    st.session_state.customer_phone = ""
    st.session_state.customer_attached = False
    st.session_state.customer_id = None
    st.session_state.customer_found = False


# ==============================
# FINALIZE CUSTOMER SALE
# ==============================
def finalize_customer_sale(cart, total, receipt_no):
    """
    Finalize sale with customer data
    Records customer purchase in database
    """
    if not st.session_state.customer_attached:
        # If no customer attached, record as walk-in
        customer_name = "Walk-in"
        customer_phone = ""
    else:
        customer_name = st.session_state.customer_name or "Walk-in"
        customer_phone = st.session_state.customer_phone or ""
    
    if not cart:
        st.error("Cannot finalize empty cart")
        return False
    
    try:
        record_customer_purchase(
            customer_name=customer_name,
            phone=customer_phone,
            cart=cart,
            total=total,
            receipt_no=receipt_no
        )
        
        # Reset after successful recording
        reset_customer()
        return True
        
    except Exception as e:
        st.error(f"Error recording purchase: {str(e)}")
        return False


# ==============================
# CUSTOMER SUMMARY WIDGET
# ==============================
def show_customer_summary():
    """
    Display current customer summary in sidebar or header
    """
    
    if st.session_state.customer_attached:
        name = st.session_state.customer_name or "Walk-in"
        phone = st.session_state.customer_phone or ""
        display_phone = normalize_phone_for_display(phone) if phone else "N/A"
        
        st.info(f"""
        👤 **Customer:** {name}
        📱 **Phone:** {display_phone}
        {f"🆔 **ID:** {st.session_state.customer_id}" if st.session_state.customer_id else ""}
        """)
    else:
        st.warning("🚶 No customer attached (Walk-in sale)")


# ==============================
# CUSTOMER HISTORY VIEWER
# ==============================
def show_customer_history(phone, sales_df):
    """
    Show customer purchase history
    """
    if sales_df is None or sales_df.empty:
        st.info("No purchase history available")
        return
    
    phone_col = None
    for col in ["customer_phone", "phone", "customer_phone_str"]:
        if col in sales_df.columns:
            phone_col = col
            break
    
    if phone_col is None:
        st.info("No customer phone column found")
        return
    
    search_phone = normalize_phone(phone)
    sales_df["phone_str"] = sales_df[phone_col].astype(str)
    
    customer_sales = sales_df[sales_df["phone_str"].str.contains(search_phone, na=False)]
    
    if customer_sales.empty:
        st.info("No purchase history for this customer")
        return
    
    st.markdown("### Purchase History")
    
    display_cols = []
    
    date_col = None
    for col in ["date", "sale_date", "transaction_date"]:
        if col in customer_sales.columns:
            date_col = col
            break
    
    if date_col:
        display_cols.append(date_col)
        customer_sales[date_col] = pd.to_datetime(customer_sales[date_col], errors="coerce")
        customer_sales[date_col] = customer_sales[date_col].dt.strftime("%Y-%m-%d %H:%M")
    
    receipt_col = None
    for col in ["receipt_no", "receipt", "transaction_id"]:
        if col in customer_sales.columns:
            receipt_col = col
            break
    
    if receipt_col:
        display_cols.append(receipt_col)
    
    amount_col = None
    for col in ["final_total", "total", "amount"]:
        if col in customer_sales.columns:
            amount_col = col
            break
    
    if amount_col:
        display_cols.append(amount_col)
        customer_sales[amount_col] = customer_sales[amount_col].apply(to_float)
    
    if "items" in customer_sales.columns:
        display_cols.append("items")
    
    if display_cols:
        st.dataframe(
            customer_sales[display_cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                amount_col: st.column_config.NumberColumn("Amount", format="$%.2f") if amount_col else None
            } if amount_col else {}
        )
    
    # Summary
    total_spent = customer_sales[amount_col].sum() if amount_col else 0
    total_orders = len(customer_sales)
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Orders", total_orders)
    with col2:
        st.metric("Total Spent", f"${total_spent:,.2f}")


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    # Test the customer capture form
    st.title("Customer Module Test")
    
    init_customer_session()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Full Customer Capture")
        customer_capture_form()
    
    with col2:
        st.subheader("Quick Customer Capture")
        quick_customer_capture()
    
    st.markdown("---")
    show_customer_summary()
    
    if st.button("Reset Customer"):
        reset_customer()
        st.rerun()