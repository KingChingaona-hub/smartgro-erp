# backend/modules/floating_financials.py - Updated with gas sales recording only (no pending/transfer)

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from backend.core.floating_financials import (
    # Change Management
    create_change_record,
    collect_change,
    get_change_records,
    get_change_summary,
    CHANGE_STATUSES,
    
    # Credit Management
    create_credit_record,
    record_credit_payment,
    get_credit_records,
    get_credit_summary,
    get_overdue_credits,
    CREDIT_TYPES,
    CREDIT_STATUSES,
    
    # Gas Sales - Recording only
    create_gas_sale,
    get_gas_sales,
    get_gas_sales_summary,
    get_daily_gas_summary
)
from backend.core.auth import can_access_feature
from backend.core.theme_manager import apply_page_theme
from backend.core.db_adapter import load_sales


# ==============================
# CUSTOMER AUTOCOMPLETE HELPERS
# ==============================

@st.cache_data(ttl=300)
def get_customer_suggestions():
    """Get unique customer names from sales data for autocomplete"""
    try:
        sales_df = load_sales()
        if sales_df.empty:
            return []
        
        customer_col = None
        for col in ["customer_name", "customer", "Customer"]:
            if col in sales_df.columns:
                customer_col = col
                break
        
        if not customer_col:
            return []
        
        customers = sales_df[customer_col].dropna().unique().tolist()
        customers = [str(c).strip() for c in customers if str(c).strip() and str(c).strip().lower() != "walk-in"]
        customers = sorted(set(customers))
        
        return customers
    except Exception as e:
        print(f"Error getting customer suggestions: {e}")
        return []


@st.cache_data(ttl=300)
def get_customer_phone_mapping():
    """Get customer name to phone mapping from sales data"""
    try:
        sales_df = load_sales()
        if sales_df.empty:
            return {}
        
        name_col = None
        phone_col = None
        
        for col in ["customer_name", "customer", "Customer"]:
            if col in sales_df.columns:
                name_col = col
                break
        
        for col in ["customer_phone", "phone", "Phone"]:
            if col in sales_df.columns:
                phone_col = col
                break
        
        if name_col and phone_col:
            mapping = {}
            for _, row in sales_df.iterrows():
                name = str(row.get(name_col, "")).strip()
                phone = str(row.get(phone_col, "")).strip()
                if name and name.lower() != "walk-in" and phone:
                    mapping[name] = phone
            return mapping
        
        return {}
    except Exception as e:
        print(f"Error getting customer phone mapping: {e}")
        return {}


def get_customer_name_input(key_suffix=""):
    """Get customer name input with autocomplete - simplified for mobile"""
    customer_suggestions = get_customer_suggestions()
    customer_phones = get_customer_phone_mapping()
    
    all_options = ["Walk-in"] + customer_suggestions if customer_suggestions else ["Walk-in"]
    
    current_name = st.session_state.get(f"customer_name_{key_suffix}", "Walk-in")
    
    is_new_customer = current_name not in all_options and current_name != "Walk-in" and current_name.strip()
    if is_new_customer:
        all_options.append(current_name)
    
    try:
        current_index = all_options.index(current_name) if current_name in all_options else 0
    except ValueError:
        current_index = 0
    
    selected_customer = st.selectbox(
        "Customer Name",
        options=all_options,
        index=current_index,
        key=f"customer_select_{key_suffix}"
    )
    
    new_customer_name = st.text_input(
        "Or type new customer name",
        placeholder="Enter new name...",
        key=f"new_customer_{key_suffix}"
    )
    
    if new_customer_name and new_customer_name.strip():
        selected_customer = new_customer_name.strip()
    
    auto_phone = ""
    if selected_customer != "Walk-in" and selected_customer in customer_phones:
        auto_phone = customer_phones[selected_customer]
    
    phone = st.text_input(
        "Phone",
        value=auto_phone,
        key=f"customer_phone_{key_suffix}",
        placeholder="Enter phone number"
    )
    
    return selected_customer, phone


# ==============================
# MAIN PAGE
# ==============================

def floating_financials_page():
    """Main Floating Financials Dashboard - with table layouts"""
    
    apply_page_theme("floating_financials")
    
    st.title("Floating Financials")
    st.caption("Manage change, credits, and gas sales")
    
    role = st.session_state.get("role", "cashier")
    if not can_access_feature(role, "floating_financials"):
        st.error("You don't have permission to access this page")
        return
    
    tab_names = ["Change Management", "Credit Management", "Gas Sales"]
    
    if "floating_tab" not in st.session_state:
        st.session_state.floating_tab = 0
    
    try:
        params = st.query_params
        if "tab" in params:
            tab_param = params.get("tab")
            if tab_param in tab_names:
                st.session_state.floating_tab = tab_names.index(tab_param)
    except:
        pass
    
    tab1, tab2, tab3 = st.tabs(tab_names)
    
    with tab1:
        st.session_state.floating_tab = 0
        try:
            st.query_params["tab"] = "Change Management"
        except:
            pass
        change_management_tab()
    
    with tab2:
        st.session_state.floating_tab = 1
        try:
            st.query_params["tab"] = "Credit Management"
        except:
            pass
        credit_management_tab()
    
    with tab3:
        st.session_state.floating_tab = 2
        try:
            st.query_params["tab"] = "Gas Sales"
        except:
            pass
        gas_sales_tab()


# ==============================
# CHANGE MANAGEMENT TAB
# ==============================

def change_management_tab():
    """Change Management Tab - Table format with partial collection"""
    
    summary = get_change_summary()
    
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Change", f"${summary['total_change']:,.2f}")
    with col2:
        st.metric("Collected", f"${summary['total_collected']:,.2f}")
    with col3:
        st.metric("Balance", f"${summary['total_balance']:,.2f}")
    with col4:
        st.metric("Uncollected", f"{summary['uncollected_count']}")
    with col5:
        st.metric("Total", f"{summary['total_count']}")
    
    st.divider()
    
    # Record New Change
    with st.form("record_change_form"):
        st.markdown("### Record New Uncollected Change")
        
        customer_name, phone = get_customer_name_input("change")
        new_amount = st.number_input("Amount ($)", min_value=0.01, step=0.01, key="new_change_amount")
        new_desc = st.text_area("Description (Optional)", key="new_change_desc")
        
        if st.form_submit_button("Record Change", use_container_width=True):
            if not customer_name:
                st.error("Customer name is required")
            elif new_amount <= 0:
                st.error("Amount must be greater than 0")
            else:
                success, message, change_id = create_change_record(
                    customer_name=customer_name,
                    amount=new_amount,
                    description=new_desc,
                    phone=phone
                )
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
    
    st.divider()
    
    # Filters
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        filter_status = st.selectbox("Status", ["ALL"] + CHANGE_STATUSES, key="change_status_filter")
    with col2:
        filter_customer = st.text_input("Customer", key="change_customer_filter")
    with col3:
        filter_date_from = st.date_input("From", value=None, key="change_date_from")
    with col4:
        filter_date_to = st.date_input("To", value=None, key="change_date_to")
    
    @st.cache_data(ttl=60)
    def load_change_records(status, customer, date_from, date_to):
        return get_change_records(
            status=None if status == "ALL" else status,
            customer_name=customer if customer else None,
            date_from=date_from.strftime("%Y-%m-%d") if date_from else None,
            date_to=date_to.strftime("%Y-%m-%d") if date_to else None
        )
    
    df = load_change_records(filter_status, filter_customer, filter_date_from, filter_date_to)
    
    if df.empty:
        st.info("No change records found")
        return
    
    # Prepare data for table display
    df_display = df.copy()
    
    # Format dates
    date_col = None
    for col in ["created_at", "updated_at", "date"]:
        if col in df_display.columns:
            date_col = col
            break
    
    if date_col:
        df_display[date_col] = pd.to_datetime(df_display[date_col], errors="coerce")
        df_display["Date"] = df_display[date_col].dt.strftime("%Y-%m-%d %H:%M")
    else:
        df_display["Date"] = "N/A"
    
    # Add status label
    def get_status_label(status):
        if status == "COLLECTED":
            return "COLLECTED"
        elif status == "PARTIAL_COLLECTED":
            return "PARTIAL"
        else:
            return "UNCOLLECTED"
    
    df_display["Status"] = df_display["status"].apply(get_status_label)
    
    # Rename columns for display
    rename_map = {
        "customer_name": "Customer",
        "amount": "Amount",
        "amount_collected": "Collected",
        "balance": "Balance",
        "change_id": "ID"
    }
    
    df_display = df_display.rename(columns=rename_map)
    
    # Display as a single table
    st.markdown("### All Change Records")
    st.dataframe(
        df_display[["Date", "Customer", "Amount", "Collected", "Balance", "Status", "ID"]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
            "Collected": st.column_config.NumberColumn("Collected", format="$%.2f"),
            "Balance": st.column_config.NumberColumn("Balance", format="$%.2f"),
        }
    )
    
    # Collection section below the table
    st.markdown("### Collect Change")
    
    # Get uncollected or partially collected records
    uncollected_df = df[df["balance"] > 0]
    
    if uncollected_df.empty:
        st.info("All changes have been collected")
    else:
        # Create collection options
        collection_options = []
        for idx, row in uncollected_df.iterrows():
            customer = row.get("customer_name", "Unknown")
            amount = float(row.get("amount", 0))
            balance = float(row.get("balance", 0))
            change_id = row.get("change_id", "")
            display_text = f"{customer} - Balance: ${balance:.2f} (Total: ${amount:.2f})"
            collection_options.append(display_text)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            selected_option = st.selectbox(
                "Select Change to Collect",
                collection_options,
                key="collect_change_select"
            )
        
        if selected_option:
            selected_idx = collection_options.index(selected_option)
            selected_row = uncollected_df.iloc[selected_idx]
            change_id = selected_row.get("change_id", "")
            balance = float(selected_row.get("balance", 0))
            
            with col2:
                collect_amount = st.number_input(
                    "Amount to Collect ($)",
                    min_value=0.01,
                    max_value=balance,
                    value=balance,
                    step=0.01,
                    key="collect_amount_input"
                )
            
            with col3:
                if st.button("Collect Payment", use_container_width=True, key="collect_change_btn"):
                    if collect_amount > 0:
                        success, message = collect_change(
                            change_id=change_id,
                            amount=collect_amount
                        )
                        if success:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)
                    else:
                        st.error("Please enter an amount to collect")
    
    # Footer totals
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Change", f"${df['amount'].sum():,.2f}" if 'amount' in df.columns else "$0.00")
    with col2:
        st.metric("Total Collected", f"${df['amount_collected'].sum():,.2f}" if 'amount_collected' in df.columns else "$0.00")
    with col3:
        st.metric("Total Balance", f"${df['balance'].sum():,.2f}" if 'balance' in df.columns else "$0.00")


# ==============================
# CREDIT MANAGEMENT TAB
# ==============================

def credit_management_tab():
    """Credit Management Tab - Table format"""
    
    summary = get_credit_summary()
    
    overdue_df = get_overdue_credits(days=30)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Credit", f"${summary['total_credit']:,.2f}")
    with col2:
        st.metric("Total Paid", f"${summary['total_paid']:,.2f}")
    with col3:
        st.metric("Balance", f"${summary['total_balance']:,.2f}")
    with col4:
        st.metric("Active Loans", f"{summary['active_count']}")
    
    if not overdue_df.empty:
        st.error(f"WARNING: {len(overdue_df)} credit(s) are overdue!")
    
    st.divider()
    
    # Record New Credit
    with st.form("record_credit_form"):
        st.markdown("### Record New Credit/Loan")
        
        customer_name, phone = get_customer_name_input("credit")
        new_credit_amount = st.number_input("Amount ($)", min_value=0.01, step=0.01, key="new_credit_amount")
        new_credit_type = st.selectbox("Credit Type", CREDIT_TYPES, key="new_credit_type")
        new_credit_desc = st.text_area("Description", key="new_credit_desc")
        new_credit_repayment = st.date_input("Expected Repayment Date", 
                                            value=datetime.now() + timedelta(days=30),
                                            key="new_credit_repayment")
        
        if st.form_submit_button("Record Credit", use_container_width=True):
            if not customer_name:
                st.error("Customer/Person name is required")
            elif new_credit_amount <= 0:
                st.error("Amount must be greater than 0")
            else:
                success, message, credit_id = create_credit_record(
                    customer_name=customer_name,
                    amount=new_credit_amount,
                    credit_type=new_credit_type,
                    description=new_credit_desc,
                    phone=phone,
                    expected_repayment=new_credit_repayment.strftime("%Y-%m-%d") if new_credit_repayment else None
                )
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
    
    st.divider()
    
    # Filters
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        filter_credit_status = st.selectbox("Status", ["ALL"] + CREDIT_STATUSES, key="credit_status_filter")
    with col2:
        filter_credit_type = st.selectbox("Type", ["ALL"] + CREDIT_TYPES, key="credit_type_filter")
    with col3:
        filter_credit_customer = st.text_input("Customer", key="credit_customer_filter")
    with col4:
        filter_credit_date_from = st.date_input("From", value=None, key="credit_date_from")
    with col5:
        filter_credit_date_to = st.date_input("To", value=None, key="credit_date_to")
    
    @st.cache_data(ttl=60)
    def load_credit_records(status, credit_type, customer, date_from, date_to):
        return get_credit_records(
            status=None if status == "ALL" else status,
            credit_type=None if credit_type == "ALL" else credit_type,
            customer_name=customer if customer else None,
            date_from=date_from.strftime("%Y-%m-%d") if date_from else None,
            date_to=date_to.strftime("%Y-%m-%d") if date_to else None
        )
    
    df = load_credit_records(filter_credit_status, filter_credit_type, filter_credit_customer, filter_credit_date_from, filter_credit_date_to)
    
    if df.empty:
        st.info("No credit records found")
        return
    
    # Prepare data for table display
    df_display = df.copy()
    
    # Format dates
    date_col = None
    for col in ["created_at", "updated_at", "date"]:
        if col in df_display.columns:
            date_col = col
            break
    
    if date_col:
        df_display[date_col] = pd.to_datetime(df_display[date_col], errors="coerce")
        df_display["Date"] = df_display[date_col].dt.strftime("%Y-%m-%d %H:%M")
    else:
        df_display["Date"] = "N/A"
    
    # Calculate overdue status
    def get_overdue_status(row):
        status = row.get("status", "ACTIVE")
        expected = row.get("expected_repayment_date", "")
        if status in ["ACTIVE", "PARTIAL_PAID"] and expected:
            try:
                due_date = pd.to_datetime(expected)
                if due_date < datetime.now():
                    days = (datetime.now() - due_date).days
                    return f"OVERDUE ({days}d)"
            except:
                pass
        return status
    
    df_display["Status_Display"] = df_display.apply(get_overdue_status, axis=1)
    
    # Rename columns
    rename_map = {
        "customer_name": "Customer",
        "amount": "Amount",
        "amount_paid": "Paid",
        "balance": "Balance",
        "credit_type": "Type",
        "expected_repayment_date": "Due Date",
        "credit_id": "ID"
    }
    
    df_display = df_display.rename(columns=rename_map)
    
    # Display all records in a single table
    st.markdown("### All Credit Records")
    
    display_cols = ["Date", "Customer", "Amount", "Paid", "Balance", "Type", "Due Date", "Status_Display", "ID"]
    available_cols = [col for col in display_cols if col in df_display.columns]
    
    st.dataframe(
        df_display[available_cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
            "Paid": st.column_config.NumberColumn("Paid", format="$%.2f"),
            "Balance": st.column_config.NumberColumn("Balance", format="$%.2f"),
        }
    )
    
    # Payment section below the table
    st.markdown("### Record Payment")
    
    # Get credits with balance > 0
    active_credits = df[df["balance"] > 0]
    
    if active_credits.empty:
        st.info("All credits are fully paid")
    else:
        payment_options = []
        for idx, row in active_credits.iterrows():
            customer = row.get("customer_name", "Unknown")
            balance = float(row.get("balance", 0))
            amount = float(row.get("amount", 0))
            credit_id = row.get("credit_id", "")
            display_text = f"{customer} - Balance: ${balance:.2f} (Total: ${amount:.2f})"
            payment_options.append(display_text)
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            selected_payment = st.selectbox(
                "Select Credit to Pay",
                payment_options,
                key="credit_payment_select"
            )
        
        if selected_payment:
            selected_idx = payment_options.index(selected_payment)
            selected_row = active_credits.iloc[selected_idx]
            credit_id = selected_row.get("credit_id", "")
            balance = float(selected_row.get("balance", 0))
            
            with col2:
                payment_amount = st.number_input(
                    "Payment Amount ($)",
                    min_value=0.01,
                    max_value=balance,
                    value=balance,
                    step=0.01,
                    key="credit_payment_amount"
                )
            
            with col3:
                payment_method = st.selectbox(
                    "Payment Method",
                    ["CASH", "BANK", "MOBILE_MONEY", "ECOCASH"],
                    key="credit_payment_method"
                )
            
            with col4:
                if st.button("Record Payment", use_container_width=True, key="record_credit_payment"):
                    if payment_amount > 0:
                        success, message = record_credit_payment(
                            credit_id=credit_id,
                            amount=payment_amount,
                            payment_note="Payment recorded",
                            payment_method=payment_method
                        )
                        if success:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)
                    else:
                        st.error("Please enter a payment amount")
    
    # Footer totals
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Credit", f"${df['amount'].sum():,.2f}" if 'amount' in df.columns else "$0.00")
    with col2:
        st.metric("Total Paid", f"${df['amount_paid'].sum():,.2f}" if 'amount_paid' in df.columns else "$0.00")
    with col3:
        st.metric("Total Balance", f"${df['balance'].sum():,.2f}" if 'balance' in df.columns else "$0.00")


# ==============================
# GAS SALES TAB - RECORDING ONLY
# ==============================

def gas_sales_tab():
    """Gas Sales Tab - Recording only, no pending/transfer features"""
    
    summary = get_gas_sales_summary()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total KGs Sold", f"{summary['total_kgs']:,.2f}")
    with col2:
        st.metric("Total Amount", f"${summary['total_amount']:,.2f}")
    with col3:
        st.metric("Total Sales", f"{summary['total_count']}")
    
    st.divider()
    
    # Record New Gas Sale
    with st.form("record_gas_form"):
        st.markdown("### Record Gas Sale")
        st.caption("Enter the amount paid and price per KG to calculate KGs sold")
        
        customer_name, phone = get_customer_name_input("gas")
        new_gas_price = st.number_input("Price per KG ($)", min_value=0.01, step=0.01, key="new_gas_price")
        new_gas_amount = st.number_input("Amount Customer Paid ($)", min_value=0.01, step=0.01, key="new_gas_amount")
        new_gas_desc = st.text_area("Description (Optional)", key="new_gas_desc")
        
        if new_gas_price > 0 and new_gas_amount > 0:
            calculated_kgs = new_gas_amount / new_gas_price
            st.info(f"Calculated KGs: **{calculated_kgs:.2f}** (${new_gas_price:.2f}/KG)")
        
        if st.form_submit_button("Record Gas Sale", use_container_width=True):
            if not customer_name:
                st.error("Customer name is required")
            elif new_gas_price <= 0:
                st.error("Price per KG must be greater than 0")
            elif new_gas_amount <= 0:
                st.error("Amount must be greater than 0")
            else:
                success, message, gas_sale_id = create_gas_sale(
                    customer_name=customer_name,
                    amount_paid=new_gas_amount,
                    price_per_kg=new_gas_price,
                    description=new_gas_desc
                )
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
    
    st.divider()
    
    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        filter_gas_customer = st.text_input("Customer", key="gas_customer_filter")
    with col2:
        filter_gas_date_from = st.date_input("From", value=None, key="gas_date_from")
    with col3:
        filter_gas_date_to = st.date_input("To", value=None, key="gas_date_to")
    
    @st.cache_data(ttl=60)
    def load_gas_records(customer, date_from, date_to):
        return get_gas_sales(
            customer_name=customer if customer else None,
            date_from=date_from.strftime("%Y-%m-%d") if date_from else None,
            date_to=date_to.strftime("%Y-%m-%d") if date_to else None
        )
    
    df = load_gas_records(filter_gas_customer, filter_gas_date_from, filter_gas_date_to)
    
    if df.empty:
        st.info("No gas sales records found")
        return
    
    # Prepare data for table display
    df_display = df.copy()
    
    # Format dates
    date_col = None
    for col in ["sale_date", "created_at", "date"]:
        if col in df_display.columns:
            date_col = col
            break
    
    if date_col:
        df_display[date_col] = pd.to_datetime(df_display[date_col], errors="coerce")
        df_display["Date"] = df_display[date_col].dt.strftime("%Y-%m-%d %H:%M")
    else:
        df_display["Date"] = "N/A"
    
    # Rename columns
    rename_map = {
        "customer_name": "Customer",
        "kgs": "KGs",
        "price_per_kg": "Price/KG",
        "total_amount": "Total",
        "gas_sale_id": "ID"
    }
    df_display = df_display.rename(columns=rename_map)
    
    # Display all records in a single table
    st.markdown("### All Gas Sales Records")
    
    display_cols = ["Date", "Customer", "KGs", "Price/KG", "Total", "ID"]
    available_cols = [col for col in display_cols if col in df_display.columns]
    
    st.dataframe(
        df_display[available_cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Total": st.column_config.NumberColumn("Total", format="$%.2f"),
            "Price/KG": st.column_config.NumberColumn("Price/KG", format="$%.2f"),
            "KGs": st.column_config.NumberColumn("KGs", format="%.2f"),
        }
    )
    
    # Footer totals
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total KGs", f"{df['kgs'].sum():,.2f}" if 'kgs' in df.columns else "0.00")
    with col2:
        st.metric("Total Amount", f"${df['total_amount'].sum():,.2f}" if 'total_amount' in df.columns else "$0.00")
    with col3:
        st.metric("Total Sales", len(df))