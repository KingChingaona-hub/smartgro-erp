# backend/modules/floating_financials.py - True Table Format

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
    
    # === TRUE TABLE FORMAT ===
    st.markdown("### Change Records")
    
    # Create HTML table header
    header_html = """
    <style>
        .change-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }
        .change-table th {
            background: #f0f2f6;
            text-align: left;
            padding: 10px 8px;
            font-weight: 600;
            border-bottom: 2px solid #ddd;
        }
        .change-table td {
            padding: 10px 8px;
            border-bottom: 1px solid #eee;
            vertical-align: middle;
        }
        .change-table tr:hover {
            background: #f8f9fa;
        }
        .status-collected { color: green; font-weight: 600; }
        .status-partial { color: orange; font-weight: 600; }
        .status-uncollected { color: red; font-weight: 600; }
        .collect-btn {
            background: #4CAF50;
            color: white;
            border: none;
            padding: 6px 16px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 13px;
        }
        .collect-btn:hover {
            background: #45a049;
        }
        @media (max-width: 768px) {
            .change-table th, .change-table td {
                padding: 6px 4px;
                font-size: 12px;
            }
        }
    </style>
    <table class="change-table">
        <thead>
            <tr>
                <th>Customer</th>
                <th>Amount</th>
                <th>Collected</th>
                <th>Balance</th>
                <th>Status</th>
                <th style="text-align:center;">Action</th>
            </tr>
        </thead>
        <tbody>
    """
    
    # Build table rows
    rows_html = ""
    for _, row in df.iterrows():
        customer = row.get('customer_name', 'Unknown')
        change_id = row.get('change_id', 'N/A')
        amount = float(row.get('amount', 0))
        collected = float(row.get('amount_collected', 0))
        balance = float(row.get('balance', 0))
        status = row.get('status', 'UNCOLLECTED')
        
        # Status class
        if status == "COLLECTED":
            status_class = "status-collected"
            status_text = "✅ COLLECTED"
        elif status == "PARTIAL_COLLECTED":
            status_class = "status-partial"
            status_text = "🟡 PARTIAL"
        else:
            status_class = "status-uncollected"
            status_text = "❌ UNCOLLECTED"
        
        # Action button
        if balance > 0:
            action_btn = f'<form action="" method="post"><button type="submit" name="collect_{change_id}" class="collect-btn">Collect</button></form>'
        else:
            action_btn = "—"
        
        rows_html += f"""
            <tr>
                <td><strong>{customer}</strong><br><small style="color:#888;">{change_id[:12]}...</small></td>
                <td>${amount:,.2f}</td>
                <td>${collected:,.2f}</td>
                <td>${balance:,.2f}</td>
                <td class="{status_class}">{status_text}</td>
                <td style="text-align:center;">{action_btn}</td>
            </tr>
        """
    
    rows_html += """
        </tbody>
    </table>
    """
    
    # Render the table
    st.markdown(header_html + rows_html, unsafe_allow_html=True)
    
    # Handle collect button clicks (using session state)
    for _, row in df.iterrows():
        change_id = row.get('change_id', '')
        balance = float(row.get('balance', 0))
        if balance > 0:
            if st.button(f"Collect_{change_id}", key=f"collect_{change_id}", help="Collect this change"):
                success, message = collect_change(
                    change_id=change_id,
                    amount=balance
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
    
    overdue = get_overdue_credits(days=30)
    if not overdue.empty:
        st.warning(f"⚠️ {len(overdue)} credit(s) are overdue!")
    
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
    
    # === TRUE TABLE FORMAT ===
    st.markdown("### Credit Records")
    
    header_html = """
    <style>
        .credit-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }
        .credit-table th {
            background: #f0f2f6;
            text-align: left;
            padding: 10px 8px;
            font-weight: 600;
            border-bottom: 2px solid #ddd;
        }
        .credit-table td {
            padding: 10px 8px;
            border-bottom: 1px solid #eee;
            vertical-align: middle;
        }
        .credit-table tr:hover {
            background: #f8f9fa;
        }
        .status-paid { color: green; font-weight: 600; }
        .status-partial { color: orange; font-weight: 600; }
        .status-active { color: #2196F3; font-weight: 600; }
        .status-overdue { color: red; font-weight: 600; }
        .pay-btn {
            background: #2196F3;
            color: white;
            border: none;
            padding: 6px 16px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 13px;
        }
        .pay-btn:hover {
            background: #1976D2;
        }
        @media (max-width: 768px) {
            .credit-table th, .credit-table td {
                padding: 6px 4px;
                font-size: 12px;
            }
        }
    </style>
    <table class="credit-table">
        <thead>
            <tr>
                <th>Customer</th>
                <th>Amount</th>
                <th>Paid</th>
                <th>Balance</th>
                <th>Status</th>
                <th style="text-align:center;">Action</th>
            </tr>
        </thead>
        <tbody>
    """
    
    rows_html = ""
    for _, row in df.iterrows():
        customer = row.get('customer_name', 'Unknown')
        credit_id = row.get('credit_id', 'N/A')
        amount = float(row.get('amount', 0))
        paid = float(row.get('amount_paid', 0))
        balance = float(row.get('balance', 0))
        status = row.get('status', 'ACTIVE')
        
        if status == "PAID":
            status_class = "status-paid"
            status_text = "✅ PAID"
        elif status == "PARTIAL_PAID":
            status_class = "status-partial"
            status_text = "🟡 PARTIAL"
        elif status == "OVERDUE":
            status_class = "status-overdue"
            status_text = "🔴 OVERDUE"
        elif status == "WRITTEN_OFF":
            status_class = "status-overdue"
            status_text = "❌ WRITTEN OFF"
        else:
            status_class = "status-active"
            status_text = "🟢 ACTIVE"
        
        if balance > 0:
            action_btn = f'<form action="" method="post"><button type="submit" name="pay_{credit_id}" class="pay-btn">Pay</button></form>'
        else:
            action_btn = "—"
        
        rows_html += f"""
            <tr>
                <td><strong>{customer}</strong><br><small style="color:#888;">{credit_id[:12]}...</small></td>
                <td>${amount:,.2f}</td>
                <td>${paid:,.2f}</td>
                <td>${balance:,.2f}</td>
                <td class="{status_class}">{status_text}</td>
                <td style="text-align:center;">{action_btn}</td>
            </tr>
        """
    
    rows_html += """
        </tbody>
    </table>
    """
    
    st.markdown(header_html + rows_html, unsafe_allow_html=True)
    
    # Handle pay button clicks
    for _, row in df.iterrows():
        credit_id = row.get('credit_id', '')
        balance = float(row.get('balance', 0))
        if balance > 0:
            if st.button(f"Pay_{credit_id}", key=f"pay_credit_{credit_id}"):
                st.session_state[f"paying_credit_{credit_id}"] = True
    
    # Payment forms (shown when Pay clicked)
    for _, row in df.iterrows():
        credit_id = row.get('credit_id', '')
        if st.session_state.get(f"paying_credit_{credit_id}", False):
            with st.container(border=True):
                st.subheader(f"Record Payment for {row.get('customer_name')}")
                with st.form(key=f"payment_form_{credit_id}"):
                    col_a, col_b, col_c = st.columns(3)
                    with col_a:
                        payment_amount = st.number_input(
                            "Amount to Pay ($)",
                            min_value=0.01,
                            max_value=float(row.get('balance', 0)),
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
                        if st.form_submit_button("Confirm Payment", use_container_width=True):
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
                        if st.form_submit_button("Cancel", use_container_width=True):
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
            
            # Pending sales table
            st.markdown("#### Pending Sales")
            
            pending_html = """
            <style>
                .gas-table {
                    width: 100%;
                    border-collapse: collapse;
                    font-size: 14px;
                }
                .gas-table th {
                    background: #f0f2f6;
                    text-align: left;
                    padding: 10px 8px;
                    font-weight: 600;
                    border-bottom: 2px solid #ddd;
                }
                .gas-table td {
                    padding: 10px 8px;
                    border-bottom: 1px solid #eee;
                    vertical-align: middle;
                }
                .gas-table tr:hover {
                    background: #f8f9fa;
                }
                .transfer-btn {
                    background: #FF9800;
                    color: white;
                    border: none;
                    padding: 6px 16px;
                    border-radius: 4px;
                    cursor: pointer;
                    font-size: 13px;
                }
                .transfer-btn:hover {
                    background: #F57C00;
                }
                .transfer-all-btn {
                    background: #4CAF50;
                    color: white;
                    border: none;
                    padding: 10px 24px;
                    border-radius: 4px;
                    cursor: pointer;
                    font-size: 15px;
                    width: 100%;
                }
                .transfer-all-btn:hover {
                    background: #45a049;
                }
                @media (max-width: 768px) {
                    .gas-table th, .gas-table td {
                        padding: 6px 4px;
                        font-size: 12px;
                    }
                }
            </style>
            <table class="gas-table">
                <thead>
                    <tr>
                        <th>Customer</th>
                        <th>KGs</th>
                        <th>Price/KG</th>
                        <th>Total</th>
                        <th style="text-align:center;">Action</th>
                    </tr>
                </thead>
                <tbody>
            """
            
            rows_html = ""
            for _, row in all_pending.iterrows():
                customer = row.get('customer_name', 'Unknown')
                gas_sale_id = row.get('gas_sale_id', '')
                kgs = float(row.get('kgs', 0))
                price = float(row.get('price_per_kg', 0))
                total = float(row.get('total_amount', 0))
                
                rows_html += f"""
                    <tr>
                        <td><strong>{customer}</strong></td>
                        <td>{kgs:,.2f}</td>
                        <td>${price:,.2f}</td>
                        <td>${total:,.2f}</td>
                        <td style="text-align:center;">
                            <form action="" method="post">
                                <button type="submit" name="transfer_{gas_sale_id}" class="transfer-btn">Transfer</button>
                            </form>
                        </td>
                    </tr>
                """
            
            rows_html += """
                </tbody>
            </table>
            """
            
            st.markdown(pending_html + rows_html, unsafe_allow_html=True)
            
            # Handle individual transfer buttons
            for _, row in all_pending.iterrows():
                gas_sale_id = row.get('gas_sale_id', '')
                if st.button(f"Transfer_{gas_sale_id}", key=f"transfer_gas_{gas_sale_id}"):
                    success, message = transfer_gas_to_pos(
                        gas_sale_id=gas_sale_id,
                        transfer_note="Manual transfer"
                    )
                    if success:
                        show_toast(message, "success")
                        st.rerun()
                    else:
                        st.error(message)
            
            # Bulk transfer
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
    
    # All gas sales table
    st.markdown("### All Gas Sales Records")
    
    all_gas_html = """
    <style>
        .all-gas-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }
        .all-gas-table th {
            background: #f0f2f6;
            text-align: left;
            padding: 10px 8px;
            font-weight: 600;
            border-bottom: 2px solid #ddd;
        }
        .all-gas-table td {
            padding: 10px 8px;
            border-bottom: 1px solid #eee;
            vertical-align: middle;
        }
        .all-gas-table tr:hover {
            background: #f8f9fa;
        }
        .status-pending { color: orange; font-weight: 600; }
        .status-transferred { color: green; font-weight: 600; }
        .transfer-small-btn {
            background: #FF9800;
            color: white;
            border: none;
            padding: 4px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
        }
        .transfer-small-btn:hover {
            background: #F57C00;
        }
        @media (max-width: 768px) {
            .all-gas-table th, .all-gas-table td {
                padding: 6px 4px;
                font-size: 12px;
            }
        }
    </style>
    <table class="all-gas-table">
        <thead>
            <tr>
                <th>Customer</th>
                <th>KGs</th>
                <th>Price/KG</th>
                <th>Total</th>
                <th>Status</th>
                <th style="text-align:center;">Action</th>
            </tr>
        </thead>
        <tbody>
    """
    
    rows_html = ""
    for _, row in df.iterrows():
        customer = row.get('customer_name', 'Unknown')
        gas_sale_id = row.get('gas_sale_id', '')
        kgs = float(row.get('kgs', 0))
        price = float(row.get('price_per_kg', 0))
        total = float(row.get('total_amount', 0))
        status = row.get('status', 'PENDING')
        
        if status == "PENDING":
            status_class = "status-pending"
            status_text = "🟡 PENDING"
            action_btn = f'<form action="" method="post"><button type="submit" name="transfer_{gas_sale_id}" class="transfer-small-btn">Transfer</button></form>'
        elif status == "TRANSFERRED_TO_POS":
            status_class = "status-transferred"
            status_text = "✅ TRANSFERRED"
            action_btn = "—"
        else:
            status_class = "status-transferred"
            status_text = "✅ COMPLETED"
            action_btn = "—"
        
        rows_html += f"""
            <tr>
                <td><strong>{customer}</strong></td>
                <td>{kgs:,.2f}</td>
                <td>${price:,.2f}</td>
                <td>${total:,.2f}</td>
                <td class="{status_class}">{status_text}</td>
                <td style="text-align:center;">{action_btn}</td>
            </tr>
        """
    
    rows_html += """
        </tbody>
    </table>
    """
    
    st.markdown(all_gas_html + rows_html, unsafe_allow_html=True)
    
    # Handle transfer buttons
    for _, row in df.iterrows():
        gas_sale_id = row.get('gas_sale_id', '')
        status = row.get('status', 'PENDING')
        if status == "PENDING":
            if st.button(f"Transfer_{gas_sale_id}", key=f"transfer_all_gas_{gas_sale_id}"):
                success, message = transfer_gas_to_pos(
                    gas_sale_id=gas_sale_id,
                    transfer_note="Manual transfer"
                )
                if success:
                    show_toast(message, "success")
                    st.rerun()
                else:
                    st.error(message)
    
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total KGs", f"{df['kgs'].sum():,.2f}" if 'kgs' in df.columns else "0.00")
    with col2:
        st.metric("Total Amount", f"${df['total_amount'].sum():,.2f}" if 'total_amount' in df.columns else "$0.00")
    with col3:
        pending = len(df[df['status'] == 'PENDING']) if 'status' in df.columns else 0
        st.metric("Pending Transfers", pending)