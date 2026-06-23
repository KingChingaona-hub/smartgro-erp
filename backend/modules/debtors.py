import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

from backend.core.db_adapter import load_products
from backend.analytics.debtors_engine import (
    load_debtors,
    create_debt_with_items,
    get_overdue_debtors,
    update_risk_levels,
    record_debt_payment,
    get_debt_items,
    get_customer_debt_summary,
    get_aging_summary,
    get_recoverable_debt,
    generate_reminders,
    update_credit_limit
)
from backend.utils.utils import generate_whatsapp_payment_reminder, get_whatsapp_link


def debtors_page():
    """Enhanced Debtors Management Page"""
    
    st.title("⏱️ Debtors Management System")
    st.caption("Track customer credit, manage payments, and reduce bad debt")
    
    # Update risk levels on load
    update_risk_levels()
    df = load_debtors()
    products_df = load_products()
    
    # ==============================
    # SESSION STATE FOR DEBT CART
    # ==============================
    if "debt_cart" not in st.session_state:
        st.session_state.debt_cart = []
    
    if "payment_receipt" not in st.session_state:
        st.session_state.payment_receipt = None
    
    # ==============================
    # TABS FOR DIFFERENT FUNCTIONS
    # ==============================
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "➕ Create Debt",
        "💰 Record Payment",
        "⚠️ Overdue & Reminders",
        "📊 Aging Report",
        "📋 All Debtors"
    ])
    
    # ==============================
    # TAB 1: CREATE DEBT
    # ==============================
    with tab1:
        st.markdown("## ➕ Create New Debt")
        st.caption("Select products and create a debt record")
        
        # Customer Information
        col1, col2 = st.columns(2)
        
        with col1:
            customer_name = st.text_input("Customer Name *", key="debt_customer_name")
            customer_phone = st.text_input("Phone Number *", key="debt_customer_phone")
        
        with col2:
            credit_limit = st.number_input("Credit Limit ($)", min_value=0.0, value=500.0, step=50.0, key="debt_credit_limit")
            due_date = st.date_input("Expected Repayment Date", min_value=datetime.now().date(), key="debt_due_date")
        
        # Payment Plan Options
        st.markdown("### 📅 Payment Plan (Optional)")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            payment_plan = st.selectbox("Payment Plan", ["None", "Weekly", "Monthly"], key="debt_payment_plan")
        
        with col2:
            installment_amount = st.number_input("Installment Amount ($)", min_value=0.0, value=0.0, step=10.0, key="debt_installment_amount")
        
        with col3:
            if payment_plan != "None":
                next_payment = st.date_input("Next Payment Date", min_value=datetime.now().date(), key="debt_next_payment")
            else:
                next_payment = ""
        
        st.markdown("---")
        
        # Product Selection for Debt
        st.markdown("### 📦 Select Products")
        
        # Search and select product
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            search = st.text_input("Search Product", key="debt_search", placeholder="Type product name or barcode...")
            
            filtered_products = products_df.copy()
            if search:
                filtered_products = products_df[
                    products_df["name"].str.contains(search, case=False) |
                    products_df["barcode"].astype(str).str.contains(search, case=False)
                ]
            
            if not filtered_products.empty:
                selected_product = st.selectbox("Select Product", filtered_products["name"].tolist(), key="debt_product_select")
            else:
                selected_product = None
        
        with col2:
            if selected_product:
                product = filtered_products[filtered_products["name"] == selected_product].iloc[0]
                product_stock = int(product["stock"])
                
                # FIX: Only show quantity input if stock > 0, otherwise disable
                if product_stock > 0:
                    debt_qty = st.number_input("Quantity", min_value=1, max_value=product_stock, value=1, key="debt_qty")
                else:
                    st.error(f"⚠️ {product['name']} is OUT OF STOCK")
                    debt_qty = 1
            else:
                product_stock = 0
                debt_qty = 1
        
        with col3:
            if selected_product and product_stock > 0:
                if st.button("➕ Add to Debt", key="add_debt_item"):
                    if product_stock >= debt_qty:
                        st.session_state.debt_cart.append({
                            "barcode": product["barcode"],
                            "name": product["name"],
                            "price": float(product["price"]),
                            "quantity": debt_qty,
                            "total": float(product["price"]) * debt_qty
                        })
                        st.success(f"Added {debt_qty} x {product['name']}")
                        st.rerun()
                    else:
                        st.error(f"Only {product_stock} units available")
        
        # Manual item entry
        st.markdown("### ✏️ Manual Item (Non-Inventory)")
        
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            manual_item = st.text_input("Item Description", placeholder="Service fee, delivery charge...", key="manual_item_desc")
        
        with col2:
            manual_amount = st.number_input("Amount ($)", min_value=0.0, step=5.0, key="manual_item_amount")
        
        with col3:
            if st.button("➕ Add Manual", key="add_manual_debt_item"):
                if manual_item and manual_amount > 0:
                    st.session_state.debt_cart.append({
                        "barcode": f"MANUAL-{len(st.session_state.debt_cart)}",
                        "name": f"[MANUAL] {manual_item}",
                        "price": float(manual_amount),
                        "quantity": 1,
                        "total": float(manual_amount)
                    })
                    st.success(f"Added manual item: {manual_item}")
                    st.rerun()
        
        # Display Debt Cart
        if st.session_state.debt_cart:
            st.markdown("---")
            st.markdown("### 🧾 Debt Items Cart")
            
            cart_df = pd.DataFrame(st.session_state.debt_cart)
            st.dataframe(cart_df[["name", "quantity", "price", "total"]], use_container_width=True, hide_index=True)
            
            debt_total = cart_df["total"].sum()
            st.info(f"💰 **TOTAL DEBT AMOUNT: ${debt_total:.2f}**")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🗑️ Clear Cart", use_container_width=True, key="clear_debt_cart"):
                    st.session_state.debt_cart = []
                    st.rerun()
            
            with col2:
                notes = st.text_area("Notes (optional)", key="debt_notes")
            
            if st.button("📝 Create Debt Record", type="primary", use_container_width=True):
                if not customer_name:
                    st.error("Customer name is required")
                elif not st.session_state.debt_cart:
                    st.error("Please add at least one item")
                else:
                    success, result = create_debt_with_items(
                        customer_name=customer_name,
                        phone=customer_phone,
                        items_list=st.session_state.debt_cart,
                        total_amount=debt_total,
                        expected_date=str(due_date),
                        notes=notes,
                        credit_limit=credit_limit,
                        payment_plan=payment_plan,
                        installment_amount=installment_amount,
                        installment_frequency=payment_plan,
                        next_payment_date=str(next_payment) if payment_plan != "None" else ""
                    )
                    
                    if success:
                        st.balloons()
                        st.success(f"✅ Debt created successfully! Debt ID: {result}")
                        st.info(f"💰 Total Amount: ${debt_total:.2f}")
                        st.info(f"📅 Expected Repayment: {due_date}")
                        if credit_limit > 0:
                            st.info(f"💳 Credit Limit: ${credit_limit:.2f}")
                        st.session_state.debt_cart = []
                        st.rerun()
                    else:
                        st.error(f"❌ Failed: {result}")
    
    # ==============================
    # TAB 2: RECORD PAYMENT
    # ==============================
    with tab2:
        st.markdown("## 💰 Record Debt Payment")
        
        if df.empty:
            st.info("No debt records found")
        else:
            selected_customer = st.selectbox("Select Customer", df["customer_name"].tolist(), key="pay_customer_select")
            
            if selected_customer:
                customer_debts = df[df["customer_name"] == selected_customer]
                
                # Display summary
                total_borrowed = customer_debts["total_amount"].sum()
                total_paid = customer_debts["amount_paid"].sum()
                total_balance = customer_debts["balance"].sum()
                credit_limit_val = customer_debts["credit_limit"].iloc[0] if not customer_debts.empty and "credit_limit" in customer_debts.columns else 0
                
                st.markdown("### 📊 Customer Summary")
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Borrowed", f"${total_borrowed:,.2f}")
                with col2:
                    st.metric("Total Paid", f"${total_paid:,.2f}")
                with col3:
                    st.metric("Outstanding", f"${total_balance:,.2f}")
                with col4:
                    credit_available = max(0, credit_limit_val - total_balance)
                    st.metric("Credit Available", f"${credit_available:,.2f}")
                
                # Individual debts
                st.markdown("### 📋 Individual Debts")
                
                for idx, (_, debt) in enumerate(customer_debts.iterrows()):
                    debt_id_safe = str(debt['debt_id']).replace("-", "_")
                    with st.expander(f"Debt ID: {debt['debt_id']} | Balance: ${debt['balance']:.2f} | Due: {debt['expected_repayment_date']}"):
                        items = get_debt_items(debt['debt_id'])
                        if not items.empty:
                            st.dataframe(items[["product_name", "quantity", "unit_price", "total_price"]], use_container_width=True, hide_index=True)
                
                # Payment input
                st.markdown("---")
                st.markdown("### 💵 Payment Details")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    pay_amount = st.number_input("Payment Amount ($)", min_value=0.01, step=10.0, key="debt_pay_amount")
                    cash_tendered = st.number_input("Cash Tendered ($)", min_value=0.0, step=10.0, key="debt_cash_tendered")
                
                with col2:
                    payment_note = st.text_input("Payment Reference", placeholder="Receipt number, notes...", key="debt_payment_note")
                
                # Calculate change
                change_debt = 0
                if cash_tendered > 0 and pay_amount > 0:
                    if cash_tendered >= pay_amount:
                        change_debt = cash_tendered - pay_amount
                        st.success(f"💰 Change to return: ${change_debt:.2f}")
                    else:
                        st.warning(f"Cash tendered is less than payment amount")
                
                if pay_amount > total_balance:
                    st.error(f"Payment amount exceeds outstanding balance (${total_balance:.2f})")
                
                if st.button("💰 Record Payment", type="primary", use_container_width=True, key="record_debt_payment"):
                    if pay_amount <= 0:
                        st.error("Enter valid payment amount")
                    elif pay_amount > total_balance:
                        st.error("Payment exceeds balance")
                    else:
                        receipt_no = f"DEBTPAY-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                        
                        success = record_debt_payment(
                            selected_customer,
                            pay_amount,
                            st.session_state.get("shift_id", ""),
                            receipt_no
                        )
                        
                        if success:
                            new_balance = total_balance - pay_amount
                            
                            st.balloons()
                            st.success(f"✅ Payment of ${pay_amount:.2f} recorded")
                            
                            # Generate receipt
                            receipt_text = f"""
                            {'='*40}
                            AZIEL INVESTMENTS
                            DEBT PAYMENT RECEIPT
                            {'='*40}
                            Receipt No: {receipt_no}
                            Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                            Customer: {selected_customer}
                            {'-'*40}
                            Previous Balance: ${total_balance:.2f}
                            Amount Paid: ${pay_amount:.2f}
                            """
                            
                            if cash_tendered > 0:
                                receipt_text += f"Cash Tendered: ${cash_tendered:.2f}\n"
                                receipt_text += f"Change: ${change_debt:.2f}\n"
                            
                            receipt_text += f"""
                            {'-'*40}
                            New Balance: ${new_balance:.2f}
                            {'='*40}
                            {'FULLY PAID! THANK YOU!' if new_balance <= 0 else f'Remaining: ${new_balance:.2f}'}
                            {'='*40}
                            """
                            
                            st.session_state.payment_receipt = receipt_text
                            st.rerun()
    
    # ==============================
    # TAB 3: OVERDUE & REMINDERS
    # ==============================
    with tab3:
        st.markdown("## ⚠️ Overdue Debtors & Reminders")
        
        overdue = get_overdue_debtors()
        
        if not overdue.empty:
            st.warning(f"🚨 {len(overdue)} customers with overdue payments")
            
            total_overdue = overdue["balance"].sum()
            st.metric("Total Overdue Amount", f"${total_overdue:,.2f}")
            
            st.dataframe(
                overdue[["customer_name", "phone", "balance", "days_overdue", "expected_repayment_date", "risk_level"]],
                use_container_width=True,
                hide_index=True
            )
            
            st.markdown("---")
            st.markdown("### 📢 Send Payment Reminders")
            
            reminders = generate_reminders()
            
            for idx, reminder in enumerate(reminders):
                debt_id_safe = str(reminder.get('debt_id', idx)).replace("-", "_")
                with st.expander(f"📱 {reminder['customer_name']} - {reminder['days_overdue']} days overdue"):
                    st.write(f"**Balance:** ${reminder['balance']:.2f}")
                    st.write(f"**Message:** {reminder['message']}")
                    
                    # Generate WhatsApp message
                    whatsapp_msg = generate_whatsapp_payment_reminder(
                        reminder['customer_name'],
                        reminder['balance'],
                        reminder.get('expected_repayment_date', 'N/A'),
                        reminder['days_overdue']
                    )
                    
                    whatsapp_link = get_whatsapp_link(reminder['phone'], whatsapp_msg)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if whatsapp_link:
                            st.markdown(f"""
                            <a href="{whatsapp_link}" target="_blank">
                                <button style="background: #25D366; color: white; border: none; 
                                               border-radius: 30px; padding: 8px 16px; 
                                               cursor: pointer; font-weight: bold;">
                                    📱 Send WhatsApp Reminder
                                </button>
                            </a>
                            """, unsafe_allow_html=True)
                        else:
                            st.warning("No valid phone number")
                    
                    with col2:
                        if st.button(f"📧 Send SMS", key=f"sms_reminder_{idx}_{debt_id_safe}"):
                            st.info("SMS integration - message would be sent")
        else:
            st.success("✅ No overdue payments! All debts are current.")
    
    # ==============================
    # TAB 4: AGING REPORT
    # ==============================
    with tab4:
        st.markdown("## 📊 Debt Aging Report")
        
        aging_summary = get_aging_summary()
        recoverable = get_recoverable_debt()
        
        # Aging buckets visualization
        st.markdown("### 📈 Aging Buckets")
        
        aging_data = pd.DataFrame([
            {"Bucket": "Current", "Amount": aging_summary.get("current", 0)},
            {"Bucket": "1-30 Days", "Amount": aging_summary.get("days_1_30", 0)},
            {"Bucket": "31-60 Days", "Amount": aging_summary.get("days_31_60", 0)},
            {"Bucket": "61-90 Days", "Amount": aging_summary.get("days_61_90", 0)},
            {"Bucket": "90+ Days", "Amount": aging_summary.get("days_90_plus", 0)}
        ])
        
        st.dataframe(aging_data, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        # Recovery analysis
        st.markdown("### 💰 Recovery Analysis")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Outstanding", f"${recoverable.get('total_outstanding', 0):,.2f}")
        with col2:
            st.metric("Expected Recovery", f"${recoverable.get('expected_recovery', 0):,.2f}")
        with col3:
            st.metric("Recovery Rate", f"{recoverable.get('recovery_rate', 0):.1f}%")
        
        if recoverable.get('expected_loss', 0) > 0:
            st.warning(f"⚠️ Estimated Bad Debt Risk: ${recoverable['expected_loss']:,.2f}")
    
    # ==============================
    # TAB 5: ALL DEBTORS
    # ==============================
    with tab5:
        st.markdown("## 📋 Complete Debtors List")
        
        if not df.empty:
            total_debt = df["balance"].sum()
            total_principal = df["total_amount"].sum()
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Outstanding", f"${total_debt:,.2f}")
            col2.metric("Total Principal", f"${total_principal:,.2f}")
            col3.metric("Active Debtors", len(df[df["balance"] > 0]))
            
            # Filter options
            col1, col2 = st.columns(2)
            with col1:
                status_filter = st.selectbox("Filter by Status", ["All", "NOT PAID", "PAID"], key="debtor_status_filter")
            with col2:
                risk_filter = st.selectbox("Filter by Risk", ["All", "LOW", "MEDIUM", "HIGH", "CRITICAL"], key="debtor_risk_filter")
            
            filtered_df = df.copy()
            if status_filter != "All":
                filtered_df = filtered_df[filtered_df["status"] == status_filter]
            if risk_filter != "All":
                filtered_df = filtered_df[filtered_df["risk_level"] == risk_filter]
            
            display_cols = ["debt_id", "customer_name", "phone", "total_amount", "balance", "expected_repayment_date", "status", "risk_level"]
            available_cols = [col for col in display_cols if col in filtered_df.columns]
            
            st.dataframe(filtered_df[available_cols], use_container_width=True, hide_index=True)
            
            # Export
            csv = filtered_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Download Debtors Report (CSV)",
                data=csv,
                file_name=f"debtors_report_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        else:
            st.info("No debt records found")
    
    # ==============================
    # DISPLAY PAYMENT RECEIPT
    # ==============================
    if st.session_state.payment_receipt:
        st.markdown("---")
        st.subheader("🧾 PAYMENT RECEIPT")
        st.text_area("Receipt Preview", st.session_state.payment_receipt, height=300)
        
        if st.button("❌ Close Receipt", key="close_payment_receipt"):
            st.session_state.payment_receipt = None
            st.rerun()