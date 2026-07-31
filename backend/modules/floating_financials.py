# backend/modules/floating_financials.py - Table format with minimized reruns

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
    """Change Management Tab - Table format"""
    
    summary = get_change_summary()
    
    # Summary cards in a single row
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
        animated_metric("Total", f"{summary['total_count']}")
    
    st.divider()
    
    # Form for adding new change
    with st.form("record_change_form"):
        st.markdown("### Record New Uncollected Change")
        col1, col2 = st.columns(2)
        with col1:
            new_customer = st.text_input("Customer Name")
            new_amount = st.number_input("Amount ($)", min_value=0.01, step=0.01)
        with col2:
            new_phone = st.text_input("Phone (Optional)")
            new_desc = st.text_area("Description (Optional)")
        
        if st.form_submit_button("Record Change", use_container_width=True):
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
    
    # Display as table with columns
    # Prepare data for display
    display_data = []
    for _, row in df.iterrows():
        balance = float(row.get('balance', 0))
        status = row.get('status', 'UNCOLLECTED')
        
        # Status badge
        if status == "COLLECTED":
            status_display = "✅ COLLECTED"
        elif status == "PARTIAL_COLLECTED":
            status_display = "🟡 PARTIAL"
        else:
            status_display = "❌ UNCOLLECTED"
        
        display_data.append({
            "Customer": row.get('customer_name', 'Unknown'),
            "Amount": f"${float(row.get('amount', 0)):,.2f}",
            "Collected": f"${float(row.get('amount_collected', 0)):,.2f}",
            "Balance": f"${balance:,.2f}",
            "Status": status_display,
            "ID": row.get('change_id', 'N/A'),
            "Phone": row.get('phone', ''),
            "balance_raw": balance,
            "change_id_raw": row.get('change_id', '')
        })
    
    display_df = pd.DataFrame(display_data)
    
    # Show as table
    st.markdown("### Change Records")
    
    # Use columns for each row to allow action buttons
    for idx, row in display_df.iterrows():
        with st.container(border=True):
            col1, col2, col3, col4, col5, col6 = st.columns([1.5, 1, 1, 1, 1.2, 0.8])
            
            with col1:
                st.write(f"**{row['Customer']}**")
                st.caption(f"ID: {row['ID']}")
                if row['Phone']:
                    st.caption(f"📞 {row['Phone']}")
            
            with col2:
                st.write(row['Amount'])
            
            with col3:
                st.write(row['Collected'])
            
            with col4:
                st.write(row['Balance'])
            
            with col5:
                st.write(row['Status'])
            
            with col6:
                if row['balance_raw'] > 0:
                    with st.form(key=f"collect_form_{row['ID']}"):
                        if st.form_submit_button("Collect", use_container_width=True):
                            success, message = collect_change(
                                change_id=row['change_id_raw'],
                                amount=row['balance_raw']
                            )
                            if success:
                                show_toast(message, "success")
                                st.rerun()
                            else:
                                st.error(message)
    
    # Footer totals
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Change", f"${df['amount'].sum():,.2f}" if 'amount' in df.columns else "$0.00")
    with col2:
        st.metric("Total Collected", f"${df['amount_collected'].sum():,.2f}" if 'amount_collected' in df.columns else "$0.00")
    with col3:
        st.metric("Total Balance", f"${df['balance'].sum():,.2f}" if 'balance' in df.columns else "$0.00")


def credit_management_tab():
    """Credit Management Tab - Table format"""
    
    summary = get_credit_summary()
    
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        animated_metric("Total Credit", f"${summary['total_credit']:,.2f}")
    with col2:
        animated_metric("Total Paid", f"${summary['total_paid']:,.2f}")
    with col3:
        animated_metric("Balance", f"${summary['total_balance']:,.2f}")
    with col4:
        animated_metric("Active", f"{summary['active_count']}")
    with col5:
        animated_metric("Overdue", f"{summary['overdue_count']}")
    
    st.divider()
    
    # Form for adding new credit
    with st.form("record_credit_form"):
        st.markdown("### Record New Credit/Loan")
        col1, col2 = st.columns(2)
        with col1:
            new_credit_customer = st.text_input("Customer/Person Name")
            new_credit_amount = st.number_input("Amount ($)", min_value=0.01, step=0.01)
            new_credit_type = st.selectbox("Credit Type", CREDIT_TYPES)
        with col2:
            new_credit_phone = st.text_input("Phone (Optional)")
            new_credit_desc = st.text_area("Description")
            new_credit_repayment = st.date_input("Expected Repayment Date", 
                                                value=datetime.now() + timedelta(days=30))
        
        if st.form_submit_button("Record Credit", use_container_width=True):
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
    
    # Overdue alert
    overdue = get_overdue_credits(days=30)
    if not overdue.empty:
        st.warning(f"⚠️ {len(overdue)} credit(s) are overdue!")
    
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
    
    # Display as table
    st.markdown("### Credit Records")
    
    for _, row in df.iterrows():
        balance = float(row.get('balance', 0))
        status = row.get('status', 'ACTIVE')
        
        # Status badge
        if status == "PAID":
            status_display = "✅ PAID"
        elif status == "PARTIAL_PAID":
            status_display = "🟡 PARTIAL"
        elif status == "OVERDUE":
            status_display = "🔴 OVERDUE"
        elif status == "WRITTEN_OFF":
            status_display = "❌ WRITTEN OFF"
        else:
            status_display = "🟢 ACTIVE"
        
        with st.container(border=True):
            col1, col2, col3, col4, col5, col6 = st.columns([1.8, 1, 1, 1, 1.2, 0.8])
            
            with col1:
                st.write(f"**{row.get('customer_name', 'Unknown')}**")
                st.caption(f"ID: {row.get('credit_id', 'N/A')}")
                if row.get('phone'):
                    st.caption(f"📞 {row.get('phone')}")
                if row.get('credit_type'):
                    st.caption(f"🏷️ {row.get('credit_type').replace('_', ' ').title()}")
                if row.get('description'):
                    st.caption(f"📝 {row.get('description')}")
                if row.get('expected_repayment_date'):
                    st.caption(f"📅 Due: {row.get('expected_repayment_date')}")
            
            with col2:
                st.write(f"${float(row.get('amount', 0)):,.2f}")
            
            with col3:
                st.write(f"${float(row.get('amount_paid', 0)):,.2f}")
            
            with col4:
                st.write(f"${balance:,.2f}")
            
            with col5:
                st.write(status_display)
            
            with col6:
                if balance > 0:
                    if st.button(f"Pay", key=f"pay_credit_{row.get('credit_id')}"):
                        st.session_state[f"paying_credit_{row.get('credit_id')}"] = True
            
            # Payment form (shown when Pay clicked)
            if st.session_state.get(f"paying_credit_{row.get('credit_id')}", False):
                with st.container(border=True):
                    st.subheader(f"Record Payment for {row.get('customer_name')}")
                    with st.form(key=f"payment_form_{row.get('credit_id')}"):
                        col_a, col_b, col_c = st.columns(3)
                        with col_a:
                            payment_amount = st.number_input(
                                "Amount to Pay ($)",
                                min_value=0.01,
                                max_value=balance,
                                step=0.01,
                                key=f"pay_amount_{row.get('credit_id')}"
                            )
                        with col_b:
                            payment_method = st.selectbox(
                                "Payment Method",
                                ["CASH", "BANK", "MOBILE_MONEY", "ECOCASH"],
                                key=f"pay_method_{row.get('credit_id')}"
                            )
                        with col_c:
                            payment_note = st.text_input("Note", key=f"pay_note_{row.get('credit_id')}")
                        
                        col_d, col_e = st.columns(2)
                        with col_d:
                            if st.form_submit_button("Confirm Payment", use_container_width=True):
                                success, message = record_credit_payment(
                                    credit_id=row.get('credit_id'),
                                    amount=payment_amount,
                                    payment_note=payment_note,
                                    payment_method=payment_method
                                )
                                if success:
                                    show_toast(message, "success")
                                    st.session_state[f"paying_credit_{row.get('credit_id')}"] = False
                                    st.rerun()
                                else:
                                    st.error(message)
                        with col_e:
                            if st.form_submit_button("Cancel", use_container_width=True):
                                st.session_state[f"paying_credit_{row.get('credit_id')}"] = False
                                st.rerun()
    
    # Footer totals
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Credit", f"${df['amount'].sum():,.2f}" if 'amount' in df.columns else "$0.00")
    with col2:
        st.metric("Total Paid", f"${df['amount_paid'].sum():,.2f}" if 'amount_paid' in df.columns else "$0.00")
    with col3:
        st.metric("Total Balance", f"${df['balance'].sum():,.2f}" if 'balance' in df.columns else "$0.00")


def gas_sales_tab():
    """Gas Sales Float Tab - Table format"""
    
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
    
    # Form for adding new gas sale
    with st.form("record_gas_form"):
        st.markdown("### Record New Gas Sale")
        col1, col2 = st.columns(2)
        with col1:
            new_gas_customer = st.text_input("Customer Name")
            new_gas_price = st.number_input("Price per KG ($)", min_value=0.01, step=0.01)
            new_gas_amount = st.number_input("Amount Customer Pays ($)", min_value=0.01, step=0.01)
        with col2:
            new_gas_desc = st.text_area("Description (Optional)")
            if new_gas_price > 0 and new_gas_amount > 0:
                calculated_kgs = new_gas_amount / new_gas_price
                st.info(f"Calculated KGs: **{calculated_kgs:.2f}** (${new_gas_price:.2f}/KG)")
            else:
                st.info("Enter price and amount to calculate KGs")
        
        if st.form_submit_button("Record Gas Sale", use_container_width=True):
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
    
    # Transfer section - ALL pending sales
    with st.expander("Transfer Gas to POS (All Pending)", expanded=True):
        all_pending = get_gas_sales(status="PENDING")
        
        if all_pending.empty:
            st.info("No pending gas sales to transfer")
        else:
            total_pending_kgs = all_pending['kgs'].sum() if 'kgs' in all_pending.columns else 0
            total_pending_amount = all_pending['total_amount'].sum() if 'total_amount' in all_pending.columns else 0
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Pending KGs", f"{total_pending_kgs:,.2f}")
            with col2:
                st.metric("Total Pending Amount", f"${total_pending_amount:,.2f}")
            with col3:
                st.metric("Pending Transactions", len(all_pending))
            
            # Show pending sales as table
            st.markdown("#### Pending Sales")
            for _, row in all_pending.iterrows():
                with st.container(border=True):
                    col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1.2, 0.8])
                    with col1:
                        st.write(f"**{row.get('customer_name', 'Unknown')}**")
                        st.caption(f"Date: {row.get('sale_date', '')[:10] if row.get('sale_date') else ''}")
                    with col2:
                        st.write(f"{float(row.get('kgs', 0)):,.2f} KGs")
                    with col3:
                        st.write(f"${float(row.get('price_per_kg', 0)):,.2f}/KG")
                    with col4:
                        st.write(f"${float(row.get('total_amount', 0)):,.2f}")
                    with col5:
                        with st.form(key=f"transfer_form_{row.get('gas_sale_id')}"):
                            if st.form_submit_button("Transfer", use_container_width=True):
                                success, message = transfer_gas_to_pos(
                                    gas_sale_id=row.get('gas_sale_id'),
                                    transfer_note="Manual transfer"
                                )
                                if success:
                                    show_toast(message, "success")
                                    st.rerun()
                                else:
                                    st.error(message)
            
            # Bulk transfer button
            with st.form("transfer_all_gas_form"):
                pos_receipt = st.text_input("POS Receipt Number (Optional)")
                transfer_note = st.text_area("Transfer Note")
                if st.form_submit_button("Transfer All Pending to POS", use_container_width=True):
                    success_count = 0
                    for _, sale in all_pending.iterrows():
                        gas_sale_id = sale.get('gas_sale_id', '')
                        if gas_sale_id:
                            success, message = transfer_gas_to_pos(
                                gas_sale_id=gas_sale_id,
                                pos_receipt_no=pos_receipt,
                                transfer_note=transfer_note or "Bulk transfer"
                            )
                            if success:
                                success_count += 1
                    
                    if success_count > 0:
                        show_toast(f"{success_count} gas sales transferred!", "success")
                        st.rerun()
                    else:
                        st.error("Failed to transfer gas sales")
    
    st.divider()
    
    # Today's summary
    with st.expander("Today's Gas Sales Summary", expanded=False):
        today = datetime.now().strftime("%Y-%m-%d")
        today_sales = get_gas_sales(date_from=today, date_to=today)
        
        if today_sales.empty:
            st.info("No gas sales today")
        else:
            today_pending = today_sales[today_sales['status'] == "PENDING"] if 'status' in today_sales.columns else pd.DataFrame()
            today_transferred = today_sales[today_sales['status'] == "TRANSFERRED_TO_POS"] if 'status' in today_sales.columns else pd.DataFrame()
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Today's Total", f"${today_sales['total_amount'].sum():,.2f}" if 'total_amount' in today_sales.columns else "$0.00")
            with col2:
                st.metric("Today's Pending", f"{len(today_pending)}")
            with col3:
                st.metric("Today's Transferred", f"{len(today_transferred)}")
            
            # Show today's sales as table
            for _, row in today_sales.iterrows():
                with st.container(border=True):
                    col1, col2, col3, col4, col5 = st.columns([1.5, 1, 1, 1.2, 1])
                    with col1:
                        st.write(f"**{row.get('customer_name', 'Unknown')}**")
                    with col2:
                        st.write(f"{float(row.get('kgs', 0)):,.2f} KGs")
                    with col3:
                        st.write(f"${float(row.get('price_per_kg', 0)):,.2f}/KG")
                    with col4:
                        st.write(f"${float(row.get('total_amount', 0)):,.2f}")
                    with col5:
                        status = row.get('status', 'PENDING')
                        if status == "PENDING":
                            st.warning("PENDING")
                        else:
                            st.success("TRANSFERRED")
    
    st.divider()
    
    # Filters for viewing all sales
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        filter_gas_status = st.selectbox("Status", ["ALL"] + GAS_SALE_STATUSES, key="gas_status_filter")
    with col2:
        filter_gas_customer = st.text_input("Customer", key="gas_customer_filter")
    with col3:
        filter_gas_date_from = st.date_input("From", value=None, key="gas_date_from")
    with col4:
        filter_gas_date_to = st.date_input("To", value=None, key="gas_date_to")
    
    @st.cache_data(ttl=60)
    def load_gas_sales(status, customer, date_from, date_to):
        return get_gas_sales(
            status=None if status == "ALL" else status,
            customer_name=customer if customer else None,
            date_from=date_from.strftime("%Y-%m-%d") if date_from else None,
            date_to=date_to.strftime("%Y-%m-%d") if date_to else None
        )
    
    df = load_gas_sales(filter_gas_status, filter_gas_customer, filter_gas_date_from, filter_gas_date_to)
    
    if df.empty:
        st.info("No gas sales records found")
        return
    
    # Display all sales as table
    st.markdown("### All Gas Sales Records")
    for _, row in df.iterrows():
        with st.container(border=True):
            col1, col2, col3, col4, col5, col6 = st.columns([1.8, 1, 1, 1, 1.2, 0.8])
            
            with col1:
                st.write(f"**{row.get('customer_name', 'Unknown')}**")
                st.caption(f"ID: {row.get('gas_sale_id', 'N/A')}")
                if row.get('sale_date'):
                    st.caption(f"📅 {row.get('sale_date')[:10]}")
                if row.get('description'):
                    st.caption(f"📝 {row.get('description')}")
            
            with col2:
                st.write(f"{float(row.get('kgs', 0)):,.2f} KGs")
            
            with col3:
                st.write(f"${float(row.get('price_per_kg', 0)):,.2f}")
            
            with col4:
                st.write(f"${float(row.get('total_amount', 0)):,.2f}")
            
            with col5:
                status = row.get('status', 'PENDING')
                if status == "PENDING":
                    st.warning("PENDING")
                elif status == "TRANSFERRED_TO_POS":
                    st.success("TRANSFERRED")
                else:
                    st.info("COMPLETED")
            
            with col6:
                if status == "PENDING":
                    with st.form(key=f"transfer_gas_{row.get('gas_sale_id')}"):
                        if st.form_submit_button("Transfer", use_container_width=True):
                            success, message = transfer_gas_to_pos(
                                gas_sale_id=row.get('gas_sale_id'),
                                transfer_note="Manual transfer"
                            )
                            if success:
                                show_toast(message, "success")
                                st.rerun()
                            else:
                                st.error(message)
    
    # Footer totals
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total KGs", f"{df['kgs'].sum():,.2f}" if 'kgs' in df.columns else "0.00")
    with col2:
        st.metric("Total Amount", f"${df['total_amount'].sum():,.2f}" if 'total_amount' in df.columns else "$0.00")
    with col3:
        pending = len(df[df['status'] == 'PENDING']) if 'status' in df.columns else 0
        st.metric("Pending Transfers", pending)