# backend/modules/floating_financials.py - FIXED VERSION (With proper column existence checks)

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
    
    # Gas Sales
    create_gas_sale,
    transfer_gas_to_pos,
    get_gas_sales,
    get_gas_sales_summary,
    get_daily_gas_summary,
    GAS_SALE_STATUSES
)
from backend.core.auth import can_access_feature
from backend.core.theme_manager import apply_page_theme
from backend.core.animations import show_toast, show_confetti, animated_metric


def floating_financials_page():
    """Main Floating Financials Dashboard"""
    
    # Apply theme
    apply_page_theme("floating_financials")
    
    st.title("Floating Financials")
    st.caption("Manage change, credits, and gas sales in one place")
    
    # Check permissions
    role = st.session_state.get("role", "cashier")
    if not can_access_feature(role, "floating_financials"):
        st.error("You don't have permission to access this page")
        return
    
    # ==============================
    # TABS
    # ==============================
    tab1, tab2, tab3 = st.tabs([
        "Change Management",
        "Credit Management",
        "Gas Sales Float"
    ])
    
    with tab1:
        change_management_tab()
    
    with tab2:
        credit_management_tab()
    
    with tab3:
        gas_sales_tab()


# ==============================
# CHANGE MANAGEMENT TAB
# ==============================

def change_management_tab():
    """Change Management Tab - Track uncollected change"""
    
    # ==============================
    # SUMMARY CARDS
    # ==============================
    summary = get_change_summary()
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        animated_metric("Total Change", f"${summary['total_change']:,.2f}")
    with col2:
        animated_metric("Collected", f"${summary['total_collected']:,.2f}")
    with col3:
        balance = summary['total_balance']
        animated_metric("Balance", f"${balance:,.2f}")
    with col4:
        uncollected = summary['uncollected_count']
        animated_metric("Uncollected", f"{uncollected}")
    with col5:
        animated_metric("Total Records", f"{summary['total_count']}")
    
    st.divider()
    
    # ==============================
    # CREATE NEW CHANGE
    # ==============================
    with st.expander("Record New Uncollected Change", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            new_customer = st.text_input("Customer Name", key="new_change_customer")
            new_amount = st.number_input("Amount ($)", min_value=0.01, step=0.01, key="new_change_amount")
        
        with col2:
            new_phone = st.text_input("Phone (Optional)", key="new_change_phone")
            new_desc = st.text_area("Description (Optional)", key="new_change_desc")
        
        if st.button("Record Change", key="btn_record_change", use_container_width=True):
            if not new_customer:
                st.error("Customer name is required")
            elif new_amount <= 0:
                st.error("Amount must be greater than 0")
            else:
                success, message, change_id = create_change_record(
                    customer_name=new_customer,
                    amount=new_amount,
                    description=new_desc,
                    phone=new_phone
                )
                
                if success:
                    show_toast("Change recorded successfully!", "success")
                    show_confetti()
                    st.rerun()
                else:
                    st.error(message)
    
    st.divider()
    
    # ==============================
    # FILTERS
    # ==============================
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        filter_status = st.selectbox(
            "Status Filter",
            ["ALL"] + CHANGE_STATUSES,
            key="change_status_filter"
        )
    
    with col2:
        filter_customer = st.text_input("Customer Name", key="change_customer_filter")
    
    with col3:
        filter_date_from = st.date_input("Date From", value=None, key="change_date_from")
    
    with col4:
        filter_date_to = st.date_input("Date To", value=None, key="change_date_to")
    
    # ==============================
    # CHANGE LIST
    # ==============================
    df = get_change_records(
        status=None if filter_status == "ALL" else filter_status,
        customer_name=filter_customer if filter_customer else None,
        date_from=filter_date_from.strftime("%Y-%m-%d") if filter_date_from else None,
        date_to=filter_date_to.strftime("%Y-%m-%d") if filter_date_to else None
    )
    
    if df.empty:
        st.info("No change records found")
        return
    
    # ==============================
    # DISPLAY CHANGE RECORDS
    # ==============================
    for _, row in df.iterrows():
        with st.container(border=True):
            # Safely get values with defaults - check if columns exist
            customer_name = row.get('customer_name', 'Unknown') if 'customer_name' in df.columns else 'Unknown'
            change_id = row.get('change_id', 'N/A') if 'change_id' in df.columns else 'N/A'
            phone = row.get('phone', '') if 'phone' in df.columns else ''
            amount = float(row.get('amount', 0)) if 'amount' in df.columns else 0
            amount_collected = float(row.get('amount_collected', 0)) if 'amount_collected' in df.columns else 0
            balance = float(row.get('balance', 0)) if 'balance' in df.columns else 0
            status = row.get('status', 'UNCOLLECTED') if 'status' in df.columns else 'UNCOLLECTED'
            collection_count = row.get('collection_count', 0) if 'collection_count' in df.columns else 0
            
            col1, col2, col3, col4, col5 = st.columns([2, 1.5, 1.5, 1.5, 1])
            
            with col1:
                st.markdown(f"**{customer_name}**")
                st.caption(f"ID: {change_id}")
                if phone:
                    st.caption(f"Phone: {phone}")
            
            with col2:
                st.metric("Amount", f"${amount:,.2f}")
            
            with col3:
                st.metric("Collected", f"${amount_collected:,.2f}")
            
            with col4:
                st.metric("Balance", f"${balance:,.2f}")
                
                # Status badge
                if status == "COLLECTED":
                    st.success("COLLECTED")
                elif status == "PARTIAL_COLLECTED":
                    st.warning("PARTIAL")
                else:
                    st.error("UNCOLLECTED")
            
            with col5:
                if balance > 0:
                    if st.button(f"Collect", key=f"collect_{change_id}"):
                        success, message = collect_change(
                            change_id=change_id,
                            amount=balance
                        )
                        if success:
                            show_toast(message, "success")
                            st.rerun()
                        else:
                            st.error(message)
                
                if st.button(f"History", key=f"history_{change_id}"):
                    st.session_state[f"show_collections_{change_id}"] = True
            
            # Show collection history
            if st.session_state.get(f"show_collections_{change_id}", False):
                st.caption("Collection History")
                st.info(f"Total collections: {collection_count}")
                if st.button(f"Hide", key=f"hide_{change_id}"):
                    st.session_state[f"show_collections_{change_id}"] = False
    
    # ==============================
    # TOTAL SUMMARY
    # ==============================
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        amount_sum = df['amount'].sum() if 'amount' in df.columns else 0
        st.metric("Total Change", f"${amount_sum:,.2f}")
    with col2:
        collected_sum = df['amount_collected'].sum() if 'amount_collected' in df.columns else 0
        st.metric("Total Collected", f"${collected_sum:,.2f}")
    with col3:
        balance_sum = df['balance'].sum() if 'balance' in df.columns else 0
        st.metric("Total Balance", f"${balance_sum:,.2f}")


# ==============================
# CREDIT MANAGEMENT TAB
# ==============================

def credit_management_tab():
    """Credit Management Tab - Track temporary credits/loans"""
    
    # ==============================
    # SUMMARY CARDS
    # ==============================
    summary = get_credit_summary()
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        animated_metric("Total Credit", f"${summary['total_credit']:,.2f}")
    with col2:
        animated_metric("Total Paid", f"${summary['total_paid']:,.2f}")
    with col3:
        balance = summary['total_balance']
        animated_metric("Balance", f"${balance:,.2f}")
    with col4:
        active = summary['active_count']
        animated_metric("Active Loans", f"{active}")
    with col5:
        overdue = summary['overdue_count']
        animated_metric("Overdue", f"{overdue}")
    
    st.divider()
    
    # ==============================
    # CREATE NEW CREDIT
    # ==============================
    with st.expander("Record New Credit/Loan", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            new_credit_customer = st.text_input("Customer/Person Name", key="new_credit_customer")
            new_credit_amount = st.number_input("Amount ($)", min_value=0.01, step=0.01, key="new_credit_amount")
            new_credit_type = st.selectbox("Credit Type", CREDIT_TYPES, key="new_credit_type")
        
        with col2:
            new_credit_phone = st.text_input("Phone (Optional)", key="new_credit_phone")
            new_credit_desc = st.text_area("Description (e.g., what was borrowed)", key="new_credit_desc")
            new_credit_repayment = st.date_input("Expected Repayment Date", key="new_credit_repayment", 
                                                value=datetime.now() + timedelta(days=30))
        
        if st.button("Record Credit", key="btn_record_credit", use_container_width=True):
            if not new_credit_customer:
                st.error("Customer/Person name is required")
            elif new_credit_amount <= 0:
                st.error("Amount must be greater than 0")
            else:
                success, message, credit_id = create_credit_record(
                    customer_name=new_credit_customer,
                    amount=new_credit_amount,
                    credit_type=new_credit_type,
                    description=new_credit_desc,
                    phone=new_credit_phone,
                    expected_repayment=new_credit_repayment.strftime("%Y-%m-%d") if new_credit_repayment else None
                )
                
                if success:
                    show_toast("Credit recorded successfully!", "success")
                    show_confetti()
                    st.rerun()
                else:
                    st.error(message)
    
    st.divider()
    
    # ==============================
    # FILTERS
    # ==============================
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        filter_credit_status = st.selectbox(
            "Status Filter",
            ["ALL"] + CREDIT_STATUSES,
            key="credit_status_filter"
        )
    
    with col2:
        filter_credit_type = st.selectbox(
            "Type Filter",
            ["ALL"] + CREDIT_TYPES,
            key="credit_type_filter"
        )
    
    with col3:
        filter_credit_customer = st.text_input("Customer Name", key="credit_customer_filter")
    
    with col4:
        filter_credit_date_from = st.date_input("Date From", value=None, key="credit_date_from")
    
    with col5:
        filter_credit_date_to = st.date_input("Date To", value=None, key="credit_date_to")
    
    # ==============================
    # OVERDUE CREDITS ALERT
    # ==============================
    overdue = get_overdue_credits(days=30)
    if not overdue.empty:
        st.warning(f"{len(overdue)} credit(s) are overdue! Check the list below.")
    
    # ==============================
    # CREDIT LIST
    # ==============================
    df = get_credit_records(
        status=None if filter_credit_status == "ALL" else filter_credit_status,
        credit_type=None if filter_credit_type == "ALL" else filter_credit_type,
        customer_name=filter_credit_customer if filter_credit_customer else None,
        date_from=filter_credit_date_from.strftime("%Y-%m-%d") if filter_credit_date_from else None,
        date_to=filter_credit_date_to.strftime("%Y-%m-%d") if filter_credit_date_to else None
    )
    
    if df.empty:
        st.info("No credit records found")
        return
    
    # ==============================
    # DISPLAY CREDIT RECORDS
    # ==============================
    for _, row in df.iterrows():
        with st.container(border=True):
            # Safely get values with defaults - check if columns exist
            customer_name = row.get('customer_name', 'Unknown') if 'customer_name' in df.columns else 'Unknown'
            credit_id = row.get('credit_id', 'N/A') if 'credit_id' in df.columns else 'N/A'
            phone = row.get('phone', '') if 'phone' in df.columns else ''
            credit_type = row.get('credit_type', 'OTHER') if 'credit_type' in df.columns else 'OTHER'
            description = row.get('description', '') if 'description' in df.columns else ''
            expected_repayment = row.get('expected_repayment_date', '') if 'expected_repayment_date' in df.columns else ''
            amount = float(row.get('amount', 0)) if 'amount' in df.columns else 0
            amount_paid = float(row.get('amount_paid', 0)) if 'amount_paid' in df.columns else 0
            balance = float(row.get('balance', 0)) if 'balance' in df.columns else 0
            status = row.get('status', 'ACTIVE') if 'status' in df.columns else 'ACTIVE'
            payment_count = row.get('payment_count', 0) if 'payment_count' in df.columns else 0
            
            col1, col2, col3, col4, col5, col6 = st.columns([2, 1.2, 1.2, 1.2, 1.2, 0.8])
            
            with col1:
                st.markdown(f"**{customer_name}**")
                st.caption(f"ID: {credit_id}")
                if phone:
                    st.caption(f"Phone: {phone}")
                if credit_type:
                    st.caption(f"Type: {credit_type.replace('_', ' ').title()}")
                if description:
                    st.caption(f"Description: {description}")
                if expected_repayment:
                    st.caption(f"Due: {expected_repayment}")
            
            with col2:
                st.metric("Amount", f"${amount:,.2f}")
            
            with col3:
                st.metric("Paid", f"${amount_paid:,.2f}")
            
            with col4:
                st.metric("Balance", f"${balance:,.2f}")
            
            with col5:
                # Status badge
                if status == "PAID":
                    st.success("PAID")
                elif status == "PARTIAL_PAID":
                    st.warning("PARTIAL")
                elif status == "OVERDUE":
                    st.error("OVERDUE")
                elif status == "WRITTEN_OFF":
                    st.error("WRITTEN OFF")
                else:
                    st.info("ACTIVE")
            
            with col6:
                if balance > 0:
                    if st.button(f"Pay", key=f"pay_credit_{credit_id}", help="Record Payment"):
                        st.session_state[f"pay_credit_{credit_id}"] = True
                
                if st.button(f"History", key=f"history_credit_{credit_id}", help="View History"):
                    st.session_state[f"show_credit_history_{credit_id}"] = True
            
            # ==============================
            # PAYMENT MODAL
            # ==============================
            if st.session_state.get(f"pay_credit_{credit_id}", False):
                with st.expander(f"Record Payment for {customer_name}", expanded=True):
                    col_a, col_b, col_c = st.columns(3)
                    with col_a:
                        payment_amount = st.number_input(
                            "Amount to Pay ($)",
                            min_value=0.01,
                            max_value=float(balance),
                            step=0.01,
                            key=f"pay_amount_{credit_id}"
                        )
                    with col_b:
                        payment_method = st.selectbox(
                            "Payment Method",
                            ["CASH", "BANK", "MOBILE_MONEY", "ECO_CASH"],
                            key=f"pay_method_{credit_id}"
                        )
                    with col_c:
                        payment_note = st.text_input("Note", key=f"pay_note_{credit_id}")
                    
                    col_d, col_e = st.columns(2)
                    with col_d:
                        if st.button(f"Confirm Payment", key=f"confirm_pay_{credit_id}", use_container_width=True):
                            success, message = record_credit_payment(
                                credit_id=credit_id,
                                amount=payment_amount,
                                payment_note=payment_note,
                                payment_method=payment_method
                            )
                            if success:
                                show_toast(message, "success")
                                st.session_state[f"pay_credit_{credit_id}"] = False
                                st.rerun()
                            else:
                                st.error(message)
                    with col_e:
                        if st.button(f"Cancel", key=f"cancel_pay_{credit_id}", use_container_width=True):
                            st.session_state[f"pay_credit_{credit_id}"] = False
                            st.rerun()
            
            # ==============================
            # PAYMENT HISTORY
            # ==============================
            if st.session_state.get(f"show_credit_history_{credit_id}", False):
                st.caption(f"Payment History for {customer_name}")
                st.info(f"Total payments: {payment_count}")
                if st.button(f"Hide History", key=f"hide_credit_history_{credit_id}"):
                    st.session_state[f"show_credit_history_{credit_id}"] = False
    
    # ==============================
    # TOTAL SUMMARY
    # ==============================
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        amount_sum = df['amount'].sum() if 'amount' in df.columns else 0
        st.metric("Total Credit", f"${amount_sum:,.2f}")
    with col2:
        paid_sum = df['amount_paid'].sum() if 'amount_paid' in df.columns else 0
        st.metric("Total Paid", f"${paid_sum:,.2f}")
    with col3:
        balance_sum = df['balance'].sum() if 'balance' in df.columns else 0
        st.metric("Total Balance", f"${balance_sum:,.2f}")


# ==============================
# GAS SALES TAB
# ==============================

def gas_sales_tab():
    """Gas Sales Float Tab - Track gas sales before POS transfer"""
    
    # ==============================
    # SUMMARY CARDS
    # ==============================
    summary = get_gas_sales_summary()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        animated_metric("Total KGs", f"{summary['total_kgs']:,.2f}")
    with col2:
        animated_metric("Total Amount", f"${summary['total_amount']:,.2f}")
    with col3:
        pending = summary['pending_count']
        animated_metric("Pending", f"{pending}")
    with col4:
        animated_metric("Transferred", f"{summary['transferred_count']}")
    
    st.divider()
    
    # ==============================
    # RECORD NEW GAS SALE
    # ==============================
    with st.expander("Record New Gas Sale", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            new_gas_customer = st.text_input("Customer Name", key="new_gas_customer")
            new_gas_kgs = st.number_input("KGs", min_value=0.01, step=0.01, key="new_gas_kgs")
            new_gas_price = st.number_input("Price per KG ($)", min_value=0.01, step=0.01, key="new_gas_price")
        
        with col2:
            new_gas_desc = st.text_area("Description (Optional)", key="new_gas_desc")
        
        if st.button("Record Gas Sale", key="btn_record_gas", use_container_width=True):
            if not new_gas_customer:
                st.error("Customer name is required")
            elif new_gas_kgs <= 0:
                st.error("KGs must be greater than 0")
            elif new_gas_price <= 0:
                st.error("Price must be greater than 0")
            else:
                success, message, gas_sale_id = create_gas_sale(
                    customer_name=new_gas_customer,
                    kgs=new_gas_kgs,
                    price_per_kg=new_gas_price,
                    description=new_gas_desc
                )
                
                if success:
                    show_toast("Gas sale recorded successfully!", "success")
                    st.rerun()
                else:
                    st.error(message)
    
    st.divider()
    
    # ==============================
    # DAILY TRANSFER SECTION
    # ==============================
    with st.expander("Transfer Gas to POS (Daily)", expanded=True):
        today = datetime.now().strftime("%Y-%m-%d")
        daily_summary = get_daily_gas_summary(date=today)
        
        st.markdown(f"### Daily Summary - {today}")
        
        if daily_summary['transactions'] == 0:
            st.info("No pending gas sales to transfer today")
        else:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total KGs", f"{daily_summary['total_kgs']:,.2f}")
            with col2:
                st.metric("Total Amount", f"${daily_summary['total_amount']:,.2f}")
            with col3:
                st.metric("Transactions", daily_summary['transactions'])
            
            # Show pending sales
            all_sales = daily_summary['all_sales']
            if not all_sales.empty and 'status' in all_sales.columns:
                pending_sales = all_sales[all_sales['status'] == "PENDING"]
                if not pending_sales.empty:
                    # Only show columns that exist
                    display_cols = []
                    for col in ['customer_name', 'kgs', 'price_per_kg', 'total_amount']:
                        if col in pending_sales.columns:
                            display_cols.append(col)
                    if display_cols:
                        st.dataframe(
                            pending_sales[display_cols],
                            use_container_width=True,
                            hide_index=True
                        )
            
            pos_receipt = st.text_input("POS Receipt Number (Optional)", key="pos_receipt_transfer")
            transfer_note = st.text_area("Transfer Note", key="transfer_note")
            
            if st.button("Transfer All Pending to POS", key="btn_transfer_all", use_container_width=True):
                if all_sales.empty:
                    st.warning("No pending sales to transfer")
                else:
                    pending_sales = all_sales[all_sales['status'] == "PENDING"] if 'status' in all_sales.columns else pd.DataFrame()
                    if pending_sales.empty:
                        st.warning("No pending sales to transfer")
                    else:
                        success_count = 0
                        for _, sale in pending_sales.iterrows():
                            gas_sale_id = sale.get('gas_sale_id', '') if 'gas_sale_id' in pending_sales.columns else ''
                            if gas_sale_id:
                                success, message = transfer_gas_to_pos(
                                    gas_sale_id=gas_sale_id,
                                    pos_receipt_no=pos_receipt,
                                    transfer_note=transfer_note or f"Daily transfer - {today}"
                                )
                                if success:
                                    success_count += 1
                        
                        if success_count > 0:
                            show_toast(f"{success_count} gas sales transferred to POS successfully!", "success")
                            st.rerun()
                        else:
                            st.error("Failed to transfer gas sales")
    
    st.divider()
    
    # ==============================
    # FILTERS
    # ==============================
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        filter_gas_status = st.selectbox(
            "Status Filter",
            ["ALL"] + GAS_SALE_STATUSES,
            key="gas_status_filter"
        )
    
    with col2:
        filter_gas_customer = st.text_input("Customer Name", key="gas_customer_filter")
    
    with col3:
        filter_gas_date_from = st.date_input("Date From", value=None, key="gas_date_from")
    
    with col4:
        filter_gas_date_to = st.date_input("Date To", value=None, key="gas_date_to")
    
    # ==============================
    # GAS SALES LIST
    # ==============================
    df = get_gas_sales(
        status=None if filter_gas_status == "ALL" else filter_gas_status,
        customer_name=filter_gas_customer if filter_gas_customer else None,
        date_from=filter_gas_date_from.strftime("%Y-%m-%d") if filter_gas_date_from else None,
        date_to=filter_gas_date_to.strftime("%Y-%m-%d") if filter_gas_date_to else None
    )
    
    if df.empty:
        st.info("No gas sales records found")
        return
    
    # ==============================
    # DISPLAY GAS SALES
    # ==============================
    for _, row in df.iterrows():
        with st.container(border=True):
            # Safely get values with defaults - check if columns exist
            customer_name = row.get('customer_name', 'Unknown') if 'customer_name' in df.columns else 'Unknown'
            gas_sale_id = row.get('gas_sale_id', 'N/A') if 'gas_sale_id' in df.columns else 'N/A'
            description = row.get('description', '') if 'description' in df.columns else ''
            kgs = float(row.get('kgs', 0)) if 'kgs' in df.columns else 0
            price_per_kg = float(row.get('price_per_kg', 0)) if 'price_per_kg' in df.columns else 0
            total_amount = float(row.get('total_amount', 0)) if 'total_amount' in df.columns else 0
            status = row.get('status', 'PENDING') if 'status' in df.columns else 'PENDING'
            
            col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1.5, 1])
            
            with col1:
                st.markdown(f"**{customer_name}**")
                st.caption(f"ID: {gas_sale_id}")
                if description:
                    st.caption(f"Description: {description}")
            
            with col2:
                st.metric("KGs", f"{kgs:,.2f}")
            
            with col3:
                st.metric("Price/KG", f"${price_per_kg:,.2f}")
            
            with col4:
                st.metric("Total", f"${total_amount:,.2f}")
            
            with col5:
                if status == "PENDING":
                    st.warning("PENDING")
                    if st.button(f"Transfer", key=f"transfer_gas_{gas_sale_id}"):
                        success, message = transfer_gas_to_pos(
                            gas_sale_id=gas_sale_id,
                            transfer_note="Manual transfer"
                        )
                        if success:
                            show_toast(message, "success")
                            st.rerun()
                        else:
                            st.error(message)
                elif status == "TRANSFERRED_TO_POS":
                    st.success("TRANSFERRED")
                else:
                    st.info("COMPLETED")
    
    # ==============================
    # TOTAL SUMMARY
    # ==============================
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        kgs_sum = df['kgs'].sum() if 'kgs' in df.columns else 0
        st.metric("Total KGs", f"{kgs_sum:,.2f}")
    with col2:
        amount_sum = df['total_amount'].sum() if 'total_amount' in df.columns else 0
        st.metric("Total Amount", f"${amount_sum:,.2f}")
    with col3:
        if 'status' in df.columns:
            pending = len(df[df['status'] == 'PENDING'])
        else:
            pending = 0
        st.metric("Pending Transfers", pending)