# backend/modules/floating_financials.py - UPDATED VERSION

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
    
    apply_page_theme("floating_financials")
    
    st.title("Floating Financials")
    st.caption("Manage change, credits, and gas sales in one place")
    
    role = st.session_state.get("role", "cashier")
    if not can_access_feature(role, "floating_financials"):
        st.error("You don't have permission to access this page")
        return
    
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


def change_management_tab():
    """Change Management Tab"""
    
    summary = get_change_summary()
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        animated_metric("Total Change", f"${summary['total_change']:,.2f}")
    with col2:
        animated_metric("Collected", f"${summary['total_collected']:,.2f}")
    with col3:
        animated_metric("Balance", f"${summary['total_balance']:,.2f}")
    with col4:
        animated_metric("Uncollected", f"{summary['uncollected_count']}")
    with col5:
        animated_metric("Total Records", f"{summary['total_count']}")
    
    st.divider()
    
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
    
    df = get_change_records(
        status=None if filter_status == "ALL" else filter_status,
        customer_name=filter_customer if filter_customer else None,
        date_from=filter_date_from.strftime("%Y-%m-%d") if filter_date_from else None,
        date_to=filter_date_to.strftime("%Y-%m-%d") if filter_date_to else None
    )
    
    if df.empty:
        st.info("No change records found")
        return
    
    for _, row in df.iterrows():
        with st.container(border=True):
            customer_name = row.get('customer_name', 'Unknown')
            change_id = row.get('change_id', 'N/A')
            phone = row.get('phone', '')
            amount = float(row.get('amount', 0))
            amount_collected = float(row.get('amount_collected', 0))
            balance = float(row.get('balance', 0))
            status = row.get('status', 'UNCOLLECTED')
            
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
    
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Change", f"${df['amount'].sum():,.2f}" if 'amount' in df.columns else "$0.00")
    with col2:
        st.metric("Total Collected", f"${df['amount_collected'].sum():,.2f}" if 'amount_collected' in df.columns else "$0.00")
    with col3:
        st.metric("Total Balance", f"${df['balance'].sum():,.2f}" if 'balance' in df.columns else "$0.00")


def credit_management_tab():
    """Credit Management Tab"""
    
    summary = get_credit_summary()
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        animated_metric("Total Credit", f"${summary['total_credit']:,.2f}")
    with col2:
        animated_metric("Total Paid", f"${summary['total_paid']:,.2f}")
    with col3:
        animated_metric("Balance", f"${summary['total_balance']:,.2f}")
    with col4:
        animated_metric("Active Loans", f"{summary['active_count']}")
    with col5:
        animated_metric("Overdue", f"{summary['overdue_count']}")
    
    st.divider()
    
    with st.expander("Record New Credit/Loan", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            new_credit_customer = st.text_input("Customer/Person Name", key="new_credit_customer")
            new_credit_amount = st.number_input("Amount ($)", min_value=0.01, step=0.01, key="new_credit_amount")
            new_credit_type = st.selectbox("Credit Type", CREDIT_TYPES, key="new_credit_type")
        
        with col2:
            new_credit_phone = st.text_input("Phone (Optional)", key="new_credit_phone")
            new_credit_desc = st.text_area("Description", key="new_credit_desc")
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
    
    overdue = get_overdue_credits(days=30)
    if not overdue.empty:
        st.warning(f"{len(overdue)} credit(s) are overdue!")
    
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
    
    for _, row in df.iterrows():
        with st.container(border=True):
            customer_name = row.get('customer_name', 'Unknown')
            credit_id = row.get('credit_id', 'N/A')
            phone = row.get('phone', '')
            credit_type = row.get('credit_type', 'OTHER')
            description = row.get('description', '')
            expected_repayment = row.get('expected_repayment_date', '')
            amount = float(row.get('amount', 0))
            amount_paid = float(row.get('amount_paid', 0))
            balance = float(row.get('balance', 0))
            status = row.get('status', 'ACTIVE')
            
            col1, col2, col3, col4, col5, col6 = st.columns([2, 1.2, 1.2, 1.2, 1.2, 0.8])
            
            with col1:
                st.markdown(f"**{customer_name}**")
                st.caption(f"ID: {credit_id}")
                if phone:
                    st.caption(f"Phone: {phone}")
                if credit_type:
                    st.caption(f"Type: {credit_type.replace('_', ' ').title()}")
                if description:
                    st.caption(f"Desc: {description}")
                if expected_repayment:
                    st.caption(f"Due: {expected_repayment}")
            
            with col2:
                st.metric("Amount", f"${amount:,.2f}")
            
            with col3:
                st.metric("Paid", f"${amount_paid:,.2f}")
            
            with col4:
                st.metric("Balance", f"${balance:,.2f}")
            
            with col5:
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
                    if st.button(f"Pay", key=f"pay_credit_{credit_id}"):
                        st.session_state[f"paying_credit_{credit_id}"] = True
                        st.rerun()
            
            if st.session_state.get(f"paying_credit_{credit_id}", False):
                with st.container(border=True):
                    st.subheader(f"Record Payment for {customer_name}")
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
                            ["CASH", "BANK", "MOBILE_MONEY", "ECOCASH"],
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
                                st.session_state[f"paying_credit_{credit_id}"] = False
                                st.rerun()
                            else:
                                st.error(message)
                    
                    with col_e:
                        if st.button(f"Cancel", key=f"cancel_pay_{credit_id}", use_container_width=True):
                            st.session_state[f"paying_credit_{credit_id}"] = False
                            st.rerun()
    
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Credit", f"${df['amount'].sum():,.2f}" if 'amount' in df.columns else "$0.00")
    with col2:
        st.metric("Total Paid", f"${df['amount_paid'].sum():,.2f}" if 'amount_paid' in df.columns else "$0.00")
    with col3:
        st.metric("Total Balance", f"${df['balance'].sum():,.2f}" if 'balance' in df.columns else "$0.00")


def gas_sales_tab():
    """Gas Sales Float Tab - User enters amount, system calculates KGs"""
    
    summary = get_gas_sales_summary()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        animated_metric("Total KGs", f"{summary['total_kgs']:,.2f}")
    with col2:
        animated_metric("Total Amount", f"${summary['total_amount']:,.2f}")
    with col3:
        animated_metric("Pending", f"{summary['pending_count']}")
    with col4:
        animated_metric("Transferred", f"{summary['transferred_count']}")
    
    st.divider()
    
    with st.expander("Record New Gas Sale", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            new_gas_customer = st.text_input("Customer Name", key="new_gas_customer")
            new_gas_price = st.number_input("Price per KG ($)", min_value=0.01, step=0.01, key="new_gas_price")
            new_gas_amount = st.number_input("Amount Customer Pays ($)", min_value=0.01, step=0.01, key="new_gas_amount")
        
        with col2:
            new_gas_desc = st.text_area("Description (Optional)", key="new_gas_desc")
            
            # Auto-calculate KGs
            if new_gas_price > 0 and new_gas_amount > 0:
                calculated_kgs = new_gas_amount / new_gas_price
                st.info(f"Calculated KGs: **{calculated_kgs:.2f}** (${new_gas_price:.2f}/KG)")
            else:
                st.info("Enter price and amount to calculate KGs")
        
        if st.button("Record Gas Sale", key="btn_record_gas", use_container_width=True):
            if not new_gas_customer:
                st.error("Customer name is required")
            elif new_gas_price <= 0:
                st.error("Price per KG must be greater than 0")
            elif new_gas_amount <= 0:
                st.error("Amount must be greater than 0")
            else:
                success, message, gas_sale_id = create_gas_sale(
                    customer_name=new_gas_customer,
                    amount_paid=new_gas_amount,
                    price_per_kg=new_gas_price,
                    description=new_gas_desc
                )
                
                if success:
                    show_toast(message, "success")
                    st.rerun()
                else:
                    st.error(message)
    
    st.divider()
    
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
            
            pending_sales = daily_summary['all_sales']
            if not pending_sales.empty and 'status' in pending_sales.columns:
                pending_sales = pending_sales[pending_sales['status'] == "PENDING"]
                if not pending_sales.empty:
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
                if pending_sales.empty:
                    st.warning("No pending sales to transfer")
                else:
                    success_count = 0
                    for _, sale in pending_sales.iterrows():
                        gas_sale_id = sale.get('gas_sale_id', '')
                        if gas_sale_id:
                            success, message = transfer_gas_to_pos(
                                gas_sale_id=gas_sale_id,
                                pos_receipt_no=pos_receipt,
                                transfer_note=transfer_note or f"Daily transfer - {today}"
                            )
                            if success:
                                success_count += 1
                    
                    if success_count > 0:
                        show_toast(f"{success_count} gas sales transferred!", "success")
                        st.rerun()
                    else:
                        st.error("Failed to transfer gas sales")
    
    st.divider()
    
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
    
    df = get_gas_sales(
        status=None if filter_gas_status == "ALL" else filter_gas_status,
        customer_name=filter_gas_customer if filter_gas_customer else None,
        date_from=filter_gas_date_from.strftime("%Y-%m-%d") if filter_gas_date_from else None,
        date_to=filter_gas_date_to.strftime("%Y-%m-%d") if filter_gas_date_to else None
    )
    
    if df.empty:
        st.info("No gas sales records found")
        return
    
    for _, row in df.iterrows():
        with st.container(border=True):
            customer_name = row.get('customer_name', 'Unknown')
            gas_sale_id = row.get('gas_sale_id', 'N/A')
            description = row.get('description', '')
            kgs = float(row.get('kgs', 0))
            price_per_kg = float(row.get('price_per_kg', 0))
            total_amount = float(row.get('total_amount', 0))
            status = row.get('status', 'PENDING')
            
            col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1.5, 1])
            
            with col1:
                st.markdown(f"**{customer_name}**")
                st.caption(f"ID: {gas_sale_id}")
                if description:
                    st.caption(f"Desc: {description}")
            
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
    
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total KGs", f"{df['kgs'].sum():,.2f}" if 'kgs' in df.columns else "0.00")
    with col2:
        st.metric("Total Amount", f"${df['total_amount'].sum():,.2f}" if 'total_amount' in df.columns else "$0.00")
    with col3:
        pending = len(df[df['status'] == 'PENDING']) if 'status' in df.columns else 0
        st.metric("Pending Transfers", pending)