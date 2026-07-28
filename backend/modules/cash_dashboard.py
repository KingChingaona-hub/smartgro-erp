# backend/modules/cash_dashboard.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json

from backend.modules.cash_register import (
    load_cash,
    get_cash_summary,
    get_daily_report,
    get_cash_flow,
    get_cashier_performance,
    set_opening_cash,
    record_closing_cash,
    record_petty_cash,
    record_bank_deposit,
    load_petty_cash,
    load_bank_deposits
)
from backend.modules.shift_manager import (
    start_shift,
    end_shift,
    load_shifts,
    get_shift_summary,
    get_active_shifts_by_branch,
    get_all_active_shifts,
    get_active_shift_for_branch,
    get_branch_active_shift_id,
    is_shift_active_in_branch,
    get_shift_stats
)
from backend.core.db_adapter import load_sales, load_debtors, to_float
from backend.analytics.debtors_engine import load_debtors as load_debtors_data


# ==============================
# HELPER FUNCTIONS
# ==============================

def safe_float(value, default=0.0):
    """Safely convert value to float"""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def get_receipt_column(df):
    """Find receipt number column"""
    if df is None or df.empty:
        return None
    for col in ["receipt_no", "receipt", "transaction_id"]:
        if col in df.columns:
            return col
    return None


def get_amount_column(df):
    """Find amount column"""
    if df is None or df.empty:
        return None
    for col in ["final_total", "total", "amount", "spent"]:
        if col in df.columns:
            return col
    return None


def get_payment_method_column(df):
    """Find payment method column"""
    if df is None or df.empty:
        return None
    for col in ["payment_method", "payment_type", "payment"]:
        if col in df.columns:
            return col
    return None


def get_unduplicated_sales(sales_df):
    """Get unduplicated sales by receipt_no to avoid revenue duplication"""
    if sales_df is None or sales_df.empty:
        return pd.DataFrame()
    
    sales_df = sales_df.copy()
    receipt_col = get_receipt_column(sales_df)
    
    if receipt_col and receipt_col in sales_df.columns:
        return sales_df.drop_duplicates(subset=[receipt_col])
    
    return sales_df


def get_cash_sales_unduplicated(sales_df):
    """Get cash sales from unduplicated receipts"""
    if sales_df is None or sales_df.empty:
        return 0.0
    
    sales_undup = get_unduplicated_sales(sales_df)
    if sales_undup.empty:
        return 0.0
    
    payment_col = get_payment_method_column(sales_undup)
    amount_col = get_amount_column(sales_undup)
    
    if payment_col and amount_col:
        cash_sales = sales_undup[sales_undup[payment_col].str.upper().isin(["CASH", "ECOCASH"])]
        return safe_float(cash_sales[amount_col].sum())
    
    return 0.0


def get_credit_sales_unduplicated(sales_df):
    """Get credit sales from unduplicated receipts"""
    if sales_df is None or sales_df.empty:
        return 0.0
    
    sales_undup = get_unduplicated_sales(sales_df)
    if sales_undup.empty:
        return 0.0
    
    payment_col = get_payment_method_column(sales_undup)
    amount_col = get_amount_column(sales_undup)
    
    if payment_col and amount_col:
        credit_sales = sales_undup[sales_undup[payment_col].str.upper() == "CREDIT"]
        return safe_float(credit_sales[amount_col].sum())
    
    return 0.0


def get_debt_payments_unduplicated(debtors_df):
    """Get debt payments from debtors data (not from POS)"""
    if debtors_df is None or debtors_df.empty:
        return 0.0
    
    # Sum of amount_paid from debtors records
    if "amount_paid" in debtors_df.columns:
        return safe_float(debtors_df["amount_paid"].sum())
    
    return 0.0


def get_total_revenue_unduplicated(sales_df):
    """Get total revenue from unduplicated sales"""
    if sales_df is None or sales_df.empty:
        return 0.0
    
    sales_undup = get_unduplicated_sales(sales_df)
    if sales_undup.empty:
        return 0.0
    
    amount_col = get_amount_column(sales_undup)
    if amount_col:
        return safe_float(sales_undup[amount_col].sum())
    
    return 0.0


# ==============================
# CASH DASHBOARD
# ==============================

def cash_dashboard():
    """Enhanced Cash Register Dashboard with comprehensive features"""
    
    st.title("Cash Register Management System")
    st.caption("Track shifts, manage cash flow, and control expenses")
    
    # Get current user and branch info
    username = st.session_state.get("username", "system")
    user_branch = st.session_state.get("user_branch", "HO")
    user_role = st.session_state.get("role", "cashier")
    full_name = st.session_state.get("user_full_name", username)
    
    # Check if user can manage shifts (manager, admin, owner)
    can_manage_shifts = user_role in ["owner", "manager", "admin"]
    
    # Load data once for all tabs
    sales_df = load_sales()
    debtors_df = load_debtors_data()
    
    # Get unduplicated data
    sales_undup = get_unduplicated_sales(sales_df)
    amount_col = get_amount_column(sales_undup)
    payment_col = get_payment_method_column(sales_undup)
    
    # ==============================
    # TABS
    # ==============================
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Shift Management",
        "Today's Report",
        "Cash Flow",
        "Petty Cash",
        "Bank Deposits"
    ])
    
    # ==============================
    # TAB 1: SHIFT MANAGEMENT
    # ==============================
    with tab1:
        st.markdown("## Shift Management")
        
        # Get the active shift for this branch
        active_shift = get_active_shift_for_branch(user_branch)
        is_shift_active = active_shift is not None
        shift_id = active_shift.get("shift_id") if is_shift_active else None
        shift_name = active_shift.get("shift_name", "N/A") if is_shift_active else "N/A"
        
        # Display branch info
        st.info(f"**Branch:** {user_branch} | **Role:** {user_role.upper()}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if not is_shift_active:
                if can_manage_shifts:
                    st.markdown("### Start New Shift")
                    
                    opening = st.number_input(
                        "Opening Cash Amount", 
                        min_value=0.0, 
                        value=0.0, 
                        step=50.0, 
                        key="opening_cash_input"
                    )
                    
                    if st.button("Start Shift", type="primary", use_container_width=True):
                        with st.spinner("Starting shift..."):
                            success, result, message = start_shift(
                                cashier_username=username,
                                cashier_name=full_name,
                                branch_id=user_branch,
                                branch_name=st.session_state.get("branch_name", "Head Office"),
                                manager_username=username,
                                opening_cash=opening
                            )
                            
                            if success:
                                set_opening_cash(opening, result)
                                st.session_state.shift_id = result
                                st.session_state.active_shift_id = result
                                st.session_state.active_shift_branch = user_branch
                                st.session_state.branch_shift_active = True
                                
                                st.success(f"Shift started successfully! Shift ID: {result}")
                                st.info(f"Opening Cash: ${opening:.2f}")
                                st.rerun()
                            else:
                                st.error(f"Failed to start shift: {message}")
                else:
                    st.warning("No active shift in your branch. Please ask your manager to start a shift.")
                    st.info("Only managers and owners can start shifts.")
            else:
                st.markdown("### Active Shift")
                
                start_time = active_shift.get("start_time")
                if hasattr(start_time, 'strftime'):
                    start_time_str = start_time.strftime("%Y-%m-%d %H:%M")
                else:
                    start_time_str = str(start_time) if start_time else "N/A"
                
                st.markdown(f"""
                **Shift Name:** `{shift_name}`  
                **Shift ID:** `{shift_id}`  
                **Started by:** {active_shift.get('cashier_name', 'Unknown')}  
                **Start Time:** {start_time_str}  
                **Opening Cash:** ${active_shift.get('opening_cash', 0):.2f}  
                **Branch:** {active_shift.get('branch_name', user_branch)}
                """)
                
                # Show shift summary with unduplicated data
                summary = get_cash_summary(shift_id)
                
                # Get unduplicated cash and credit sales
                cash_sales = get_cash_sales_unduplicated(sales_undup)
                credit_sales = get_credit_sales_unduplicated(sales_undup)
                debt_payments = get_debt_payments_unduplicated(debtors_df)
                total_revenue = get_total_revenue_unduplicated(sales_undup)
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Cash Sales", f"${cash_sales:.2f}")
                with col2:
                    st.metric("Credit Sales", f"${credit_sales:.2f}")
                with col3:
                    st.metric("Debt Payments", f"${debt_payments:.2f}")
        
        with col2:
            if is_shift_active:
                if can_manage_shifts:
                    st.markdown("### End Shift")
                    
                    actual_cash = st.number_input(
                        "Actual Cash Counted", 
                        min_value=0.0, 
                        value=0.0, 
                        step=10.0, 
                        key="actual_cash_input"
                    )
                    
                    notes = st.text_area("Shift Notes", placeholder="Any issues or comments...", key="shift_notes")
                    
                    if st.button("Close Shift", type="secondary", use_container_width=True):
                        with st.spinner("Closing shift..."):
                            # Get unduplicated data for closing
                            cash_sales = get_cash_sales_unduplicated(sales_undup)
                            debt_payments = get_debt_payments_unduplicated(debtors_df)
                            
                            expected_cash = (active_shift.get('opening_cash', 0) + 
                                           cash_sales + 
                                           debt_payments)
                            
                            variance = actual_cash - expected_cash
                            
                            success, result = end_shift(
                                shift_id=shift_id,
                                closing_cash=actual_cash,
                                total_sales=cash_sales + get_credit_sales_unduplicated(sales_undup),
                                profit=cash_sales * 0.3,
                                transactions=len(sales_undup) if not sales_undup.empty else 0,
                                notes=notes
                            )
                            
                            if success:
                                record_closing_cash(actual_cash, shift_id)
                                
                                st.success(f"Shift closed!")
                                st.info(f"Expected Cash: ${expected_cash:.2f}")
                                
                                if variance >= 0:
                                    st.success(f"Cash Surplus: ${variance:.2f}")
                                else:
                                    st.error(f"Cash Shortage: ${abs(variance):.2f}")
                                
                                st.session_state.shift_id = None
                                st.session_state.active_shift_id = None
                                st.session_state.branch_shift_active = False
                                st.rerun()
                            else:
                                st.error(f"Failed to close shift: {result}")
                else:
                    st.info("Only managers and owners can close shifts.")
        
        # Shift history
        st.markdown("---")
        st.markdown("### Shift History (This Branch)")
        
        shifts_df = load_shifts()
        if not shifts_df.empty:
            branch_shifts = shifts_df[shifts_df["branch_id"] == user_branch]
            
            if not branch_shifts.empty:
                display_cols = ["shift_id", "shift_name", "cashier_name", "start_time", "end_time", "opening_cash", "closing_cash", "cash_sales", "variance", "status"]
                available_cols = [col for col in display_cols if col in branch_shifts.columns]
                
                display_shifts = branch_shifts[available_cols].sort_values("start_time", ascending=False).head(20)
                
                for col in ["start_time", "end_time"]:
                    if col in display_shifts.columns:
                        display_shifts[col] = pd.to_datetime(display_shifts[col], errors="coerce")
                        display_shifts[col] = display_shifts[col].dt.strftime("%Y-%m-%d %H:%M")
                
                st.dataframe(display_shifts, use_container_width=True, hide_index=True)
                
                total_shifts = len(branch_shifts)
                total_revenue = branch_shifts["total_revenue"].sum() if "total_revenue" in branch_shifts.columns else 0
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Shifts", total_shifts)
                with col2:
                    st.metric("Total Revenue", f"${total_revenue:,.2f}")
                with col3:
                    active_count = len(branch_shifts[branch_shifts["status"] == "OPEN"])
                    st.metric("Active Shifts", active_count)
            else:
                st.info("No shift history found for this branch")
        else:
            st.info("No shift records found")
    
    # ==============================
    # TAB 2: TODAY'S REPORT
    # ==============================
    with tab2:
        st.markdown("## Today's Cash Report")
        st.caption("All revenue metrics based on unduplicated sales data")
        
        today_report = get_daily_report()
        
        # Get unduplicated data for today
        if not sales_undup.empty and amount_col:
            today = datetime.now().date()
            date_col = None
            for col in ["sale_date", "date", "transaction_date"]:
                if col in sales_undup.columns:
                    date_col = col
                    break
            
            if date_col:
                sales_undup[date_col] = pd.to_datetime(sales_undup[date_col], errors="coerce")
                today_sales = sales_undup[sales_undup[date_col].dt.date == today]
                
                today_cash_sales = 0
                today_credit_sales = 0
                today_total_revenue = 0
                
                if not today_sales.empty:
                    amount_col_today = get_amount_column(today_sales)
                    payment_col_today = get_payment_method_column(today_sales)
                    
                    if amount_col_today:
                        today_total_revenue = safe_float(today_sales[amount_col_today].sum())
                        
                        if payment_col_today:
                            cash_sales_df = today_sales[today_sales[payment_col_today].str.upper().isin(["CASH", "ECOCASH"])]
                            today_cash_sales = safe_float(cash_sales_df[amount_col_today].sum()) if not cash_sales_df.empty else 0
                            
                            credit_sales_df = today_sales[today_sales[payment_col_today].str.upper() == "CREDIT"]
                            today_credit_sales = safe_float(credit_sales_df[amount_col_today].sum()) if not credit_sales_df.empty else 0
            else:
                today_cash_sales = 0
                today_credit_sales = 0
                today_total_revenue = 0
        else:
            today_cash_sales = 0
            today_credit_sales = 0
            today_total_revenue = 0
        
        # Today's debt payments from debtors
        today_debt_payments = 0
        if not debtors_df.empty and "amount_paid" in debtors_df.columns and "repayment_date" in debtors_df.columns:
            debtors_df["repayment_date"] = pd.to_datetime(debtors_df["repayment_date"], errors="coerce")
            today_debt_payments = safe_float(debtors_df[debtors_df["repayment_date"].dt.date == today]["amount_paid"].sum())
        
        # Key metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Cash Sales", f"${today_cash_sales:.2f}")
        with col2:
            st.metric("Credit Sales", f"${today_credit_sales:.2f}")
        with col3:
            st.metric("Debt Payments", f"${today_debt_payments:.2f}")
        with col4:
            st.metric("Total Revenue", f"${today_total_revenue:.2f}")
        
        st.markdown("---")
        
        # Show transaction details
        if not sales_undup.empty:
            st.subheader("Today's Transactions")
            date_col = None
            for col in ["sale_date", "date", "transaction_date"]:
                if col in sales_undup.columns:
                    date_col = col
                    break
            
            if date_col:
                sales_undup[date_col] = pd.to_datetime(sales_undup[date_col], errors="coerce")
                today_sales_display = sales_undup[sales_undup[date_col].dt.date == today]
                
                if not today_sales_display.empty:
                    display_cols = []
                    if "receipt_no" in today_sales_display.columns:
                        display_cols.append("receipt_no")
                    if "customer_name" in today_sales_display.columns:
                        display_cols.append("customer_name")
                    if amount_col and amount_col in today_sales_display.columns:
                        display_cols.append(amount_col)
                    if payment_col and payment_col in today_sales_display.columns:
                        display_cols.append(payment_col)
                    
                    if display_cols:
                        st.dataframe(today_sales_display[display_cols], use_container_width=True, hide_index=True)
                    
                    st.info(f"Total Transactions: {len(today_sales_display)}")
                else:
                    st.info("No transactions today")
        
        if today_report:
            # Variance
            st.markdown("---")
            col1, col2 = st.columns(2)
            
            with col1:
                expected_cash = today_report.get('opening_cash', 0) + today_cash_sales + today_debt_payments
                st.metric("Expected Cash", f"${expected_cash:.2f}")
            with col2:
                actual_cash = today_report.get('closing_cash', 0)
                st.metric("Actual Cash", f"${actual_cash:.2f}")
            
            variance = actual_cash - expected_cash
            if abs(variance) > 5:
                st.error(f"Cash Variance: ${variance:.2f} - Investigate!")
            else:
                st.success(f"Cash Variance: ${variance:.2f}")
        else:
            st.info("No cash register data for today.")
    
    # ==============================
    # TAB 3: CASH FLOW
    # ==============================
    with tab3:
        st.markdown("## Cash Flow Analysis")
        st.caption("Revenue based on unduplicated sales data")
        
        # Cash flow chart
        st.markdown("### Cash Flow Trend (Last 30 Days)")
        
        cash_flow_df = get_cash_flow(30)
        
        if not cash_flow_df.empty:
            fig = px.bar(
                cash_flow_df,
                x="Date",
                y="Net Cash Flow",
                title="Daily Net Cash Flow",
                color="Net Cash Flow",
                color_continuous_scale="RdYlGn",
                text="Net Cash Flow"
            )
            fig.update_traces(texttemplate="$%{text:.0f}", textposition="outside")
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        
        # Cashier performance
        st.markdown("### Cashier Performance")
        
        cashier_perf = get_cashier_performance()
        if not cashier_perf.empty:
            st.dataframe(cashier_perf, use_container_width=True, hide_index=True)
        
        # Summary metrics with unduplicated data
        st.markdown("---")
        st.markdown("### Summary Statistics (Unduplicated)")
        
        total_cash_sales = get_cash_sales_unduplicated(sales_undup)
        total_credit_sales = get_credit_sales_unduplicated(sales_undup)
        total_debt_payments = get_debt_payments_unduplicated(debtors_df)
        total_revenue = get_total_revenue_unduplicated(sales_undup)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Cash Sales", f"${total_cash_sales:,.2f}")
        with col2:
            st.metric("Total Credit Sales", f"${total_credit_sales:,.2f}")
        with col3:
            st.metric("Total Debt Collections", f"${total_debt_payments:,.2f}")
        
        st.info(f"**Total Revenue (Unduplicated):** ${total_revenue:,.2f}")
    
    # ==============================
    # TAB 4: PETTY CASH
    # ==============================
    with tab4:
        st.markdown("## Petty Cash Management")
        
        # Record petty cash expense
        st.markdown("### Record Petty Cash Expense")
        
        col1, col2 = st.columns(2)
        
        with col1:
            petty_desc = st.text_input("Description", key="petty_desc", placeholder="What was purchased?")
            petty_amount = st.number_input("Amount ($)", min_value=0.01, step=5.0, key="petty_amount")
        
        with col2:
            petty_category = st.selectbox("Category", ["Office Supplies", "Transport", "Refreshments", "Cleaning", "Maintenance", "Other"], key="petty_category")
            petty_notes = st.text_area("Notes", key="petty_notes")
        
        shift_to_use = st.session_state.get("shift_id") or st.session_state.get("active_shift_id") or ""
        
        if st.button("Record Petty Cash", key="record_petty"):
            if petty_desc and petty_amount > 0:
                record_petty_cash(
                    description=petty_desc,
                    amount=petty_amount,
                    category=petty_category,
                    shift_id=shift_to_use,
                    approved_by=st.session_state.get("username", "system"),
                    notes=petty_notes
                )
                st.success(f"Petty cash expense recorded: ${petty_amount:.2f}")
                st.rerun()
            else:
                st.error("Please enter description and amount")
        
        # Petty cash history
        st.markdown("---")
        st.markdown("### Petty Cash History")
        
        petty_df = load_petty_cash()
        if not petty_df.empty:
            st.dataframe(petty_df.sort_values("date", ascending=False), use_container_width=True, hide_index=True)
            
            total_petty = petty_df["amount"].sum()
            st.metric("Total Petty Cash Expenses", f"${total_petty:,.2f}")
    
    # ==============================
    # TAB 5: BANK DEPOSITS
    # ==============================
    with tab5:
        st.markdown("## Bank Deposits")
        
        # Record bank deposit
        st.markdown("### Record Bank Deposit")
        
        col1, col2 = st.columns(2)
        
        with col1:
            deposit_amount = st.number_input("Amount to Deposit ($)", min_value=0.01, step=50.0, key="deposit_amount")
            deposit_bank = st.selectbox("Bank", ["CABS", "FBC", "POSB", "CBZ", "NMB", "Stanbic", "EcoBank", "Other"], key="deposit_bank")
        
        with col2:
            deposit_ref = st.text_input("Reference Number", key="deposit_ref", placeholder="Deposit slip number")
            deposit_notes = st.text_area("Notes", key="deposit_notes")
        
        shift_to_use = st.session_state.get("shift_id") or st.session_state.get("active_shift_id") or ""
        
        if st.button("Record Bank Deposit", key="record_deposit"):
            if deposit_amount > 0:
                record_bank_deposit(
                    amount=deposit_amount,
                    bank_name=deposit_bank,
                    shift_id=shift_to_use,
                    reference_no=deposit_ref,
                    notes=deposit_notes
                )
                st.success(f"Bank deposit recorded: ${deposit_amount:.2f} to {deposit_bank}")
                st.rerun()
            else:
                st.error("Please enter deposit amount")
        
        # Deposit history
        st.markdown("---")
        st.markdown("### Bank Deposit History")
        
        deposits_df = load_bank_deposits()
        if not deposits_df.empty:
            st.dataframe(deposits_df.sort_values("date", ascending=False), use_container_width=True, hide_index=True)
            
            total_deposits = deposits_df["amount"].sum()
            st.metric("Total Bank Deposits", f"${total_deposits:,.2f}")
    
    # ==============================
    # EXPORT REPORT
    # ==============================
    st.markdown("---")
    st.subheader("Export Daily Report")
    
    if st.button("Generate Daily Report", use_container_width=True):
        today = datetime.now().date()
        date_col = None
        for col in ["sale_date", "date", "transaction_date"]:
            if col in sales_undup.columns:
                date_col = col
                break
        
        today_cash_sales = 0
        today_credit_sales = 0
        today_total_revenue = 0
        
        if not sales_undup.empty and date_col and amount_col:
            sales_undup[date_col] = pd.to_datetime(sales_undup[date_col], errors="coerce")
            today_sales = sales_undup[sales_undup[date_col].dt.date == today]
            
            if not today_sales.empty:
                today_total_revenue = safe_float(today_sales[amount_col].sum())
                
                if payment_col:
                    cash_sales_df = today_sales[today_sales[payment_col].str.upper().isin(["CASH", "ECOCASH"])]
                    today_cash_sales = safe_float(cash_sales_df[amount_col].sum()) if not cash_sales_df.empty else 0
                    
                    credit_sales_df = today_sales[today_sales[payment_col].str.upper() == "CREDIT"]
                    today_credit_sales = safe_float(credit_sales_df[amount_col].sum()) if not credit_sales_df.empty else 0
        
        # Today's debt payments
        today_debt_payments = 0
        if not debtors_df.empty and "amount_paid" in debtors_df.columns and "repayment_date" in debtors_df.columns:
            debtors_df["repayment_date"] = pd.to_datetime(debtors_df["repayment_date"], errors="coerce")
            today_debt_payments = safe_float(debtors_df[debtors_df["repayment_date"].dt.date == today]["amount_paid"].sum())
        
        report = get_daily_report()
        
        report_text = f"""
{'='*50}
AZIEL INVESTMENTS - DAILY CASH REPORT
{'='*50}

Date: {today.strftime('%Y-%m-%d')}
Branch: {user_branch}

{'-'*30}
CASH SUMMARY (UNDUPLICATED)
{'-'*30}
Cash Sales: ${today_cash_sales:.2f}
Credit Sales: ${today_credit_sales:.2f}
Debt Payments: ${today_debt_payments:.2f}
Total Revenue: ${today_total_revenue:.2f}

{'-'*30}
TRANSACTIONS
{'-'*30}
"""
        
        if not sales_undup.empty and date_col:
            sales_undup[date_col] = pd.to_datetime(sales_undup[date_col], errors="coerce")
            today_sales_count = len(sales_undup[sales_undup[date_col].dt.date == today])
            report_text += f"Total Transactions: {today_sales_count}\n"
        
        if report:
            report_text += f"""
{'-'*30}
CASH REGISTER
{'-'*30}
Opening Cash: ${report.get('opening_cash', 0):.2f}
Expected Cash: ${report.get('opening_cash', 0) + today_cash_sales + today_debt_payments:.2f}
Actual Cash: ${report.get('closing_cash', 0):.2f}
Variance: ${report.get('closing_cash', 0) - (report.get('opening_cash', 0) + today_cash_sales + today_debt_payments):.2f}
"""
        
        report_text += f"""
{'-'*50}
Generated by Aziel Investments ERP
{'-'*50}
"""
        
        st.download_button(
            label="Download Report (TXT)",
            data=report_text,
            file_name=f"cash_report_{today.strftime('%Y%m%d')}.txt",
            mime="text/plain"
        )


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    cash_dashboard()