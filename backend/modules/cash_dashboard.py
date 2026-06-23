import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

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
    get_all_active_shifts
)


def cash_dashboard():
    """Enhanced Cash Register Dashboard with comprehensive features"""
    
    st.title("💰 Cash Register Management System")
    st.caption("Track shifts, manage cash flow, and control expenses")
    
    # ==============================
    # TABS
    # ==============================
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🔄 Shift Management",
        "📊 Today's Report",
        "💵 Cash Flow",
        "📝 Petty Cash",
        "🏦 Bank Deposits"
    ])
    
    # ==============================
    # TAB 1: SHIFT MANAGEMENT
    # ==============================
    with tab1:
        st.markdown("## 🔄 Shift Management")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.session_state.get("shift_id") is None:
                opening = st.number_input("Opening Cash Amount", min_value=0.0, value=0.0, step=50.0, key="opening_cash")
                
                if st.button("🟢 Start Shift", type="primary", use_container_width=True):
                    username = st.session_state.get("username", "system")
                    
                    # Get branch info
                    branch_id = st.session_state.get("user_branch", "HO")
                    branch_name = st.session_state.get("branch_name", "Head Office")
                    full_name = st.session_state.get("user_full_name", username)
                    
                    success, shift_id = start_shift(
                        cashier_username=username,
                        cashier_name=full_name,
                        branch_id=branch_id,
                        branch_name=branch_name,
                        manager_username=username,
                        opening_cash=opening
                    )
                    
                    if success:
                        st.session_state.shift_id = shift_id
                        set_opening_cash(opening, shift_id)
                        st.success(f"✅ Shift started successfully! Shift ID: {shift_id}")
                        st.rerun()
                    else:
                        st.error(f"❌ Failed to start shift: {shift_id}")
            else:
                st.info(f"🟢 Shift ACTIVE | ID: {st.session_state.shift_id}")
                
                summary = get_cash_summary(st.session_state.shift_id)
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Cash Sales", f"${summary['cash_sales']:.2f}")
                with col2:
                    st.metric("Credit Sales", f"${summary['credit_sales']:.2f}")
                with col3:
                    st.metric("Debt Payments", f"${summary['debt_payments']:.2f}")
        
        with col2:
            if st.session_state.get("shift_id") is not None:
                actual_cash = st.number_input("Actual Cash Counted", min_value=0.0, value=0.0, step=10.0, key="actual_cash")
                
                if st.button("🔴 Close Shift", type="secondary", use_container_width=True):
                    summary = get_cash_summary(st.session_state.shift_id)
                    
                    expected_cash = summary["opening_cash"] + summary["cash_sales"] + summary["debt_payments"] - summary["petty_cash"] - summary["deposits"] - summary["expenses"]
                    variance = actual_cash - expected_cash
                    
                    success, result = end_shift(
                        shift_id=st.session_state.shift_id,
                        closing_cash=actual_cash,
                        total_sales=summary["cash_sales"] + summary["credit_sales"],
                        profit=summary["cash_sales"] * 0.3,
                        transactions=summary["transactions_count"]
                    )
                    
                    if success:
                        record_closing_cash(actual_cash, st.session_state.shift_id)
                        
                        st.success(f"✅ Shift closed!")
                        st.info(f"Expected Cash: ${expected_cash:.2f}")
                        
                        if variance >= 0:
                            st.success(f"✅ Cash Surplus: ${variance:.2f}")
                        else:
                            st.error(f"⚠️ Cash Shortage: ${abs(variance):.2f}")
                        
                        st.session_state.shift_id = None
                        st.rerun()
                    else:
                        st.error(f"❌ Failed to close shift: {result}")
        
        # Shift history
        st.markdown("---")
        st.markdown("### 📋 Shift History")
        
        shifts_df = load_shifts()
        if not shifts_df.empty:
            display_shifts = shifts_df[["shift_id", "cashier_name", "start_time", "end_time", "opening_cash", "closing_cash", "cash_sales", "variance", "status"]].sort_values("start_time", ascending=False).head(10)
            st.dataframe(display_shifts, use_container_width=True, hide_index=True)
    
    # ==============================
    # TAB 2: TODAY'S REPORT
    # ==============================
    with tab2:
        st.markdown("## 📊 Today's Cash Report")
        
        today_report = get_daily_report()
        
        if today_report:
            # Key metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("💰 Cash Sales", f"${today_report['cash_sales']:.2f}")
            with col2:
                st.metric("📝 Credit Sales", f"${today_report['credit_sales']:.2f}")
            with col3:
                st.metric("💳 Debt Payments", f"${today_report['debt_payments']:.2f}")
            with col4:
                st.metric("💸 Petty Cash", f"${today_report['petty_cash']:.2f}")
            
            st.markdown("---")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric("Expected Cash", f"${today_report['expected_cash']:.2f}")
            with col2:
                st.metric("Actual Cash", f"${today_report['closing_cash']:.2f}")
            
            # Variance
            if abs(today_report['variance']) > 5:
                st.error(f"⚠️ Cash Variance: ${today_report['variance']:.2f} - Investigate!")
            else:
                st.success(f"✅ Cash Variance: ${today_report['variance']:.2f}")
            
            # Transaction details
            st.markdown("---")
            
            if today_report.get('cash_sales_list'):
                st.subheader("💰 Cash Sales Today")
                cash_df = pd.DataFrame(today_report['cash_sales_list'])
                st.dataframe(cash_df, use_container_width=True, hide_index=True)
            
            if today_report.get('credit_sales_list'):
                st.subheader("📝 Credit Sales Today")
                credit_df = pd.DataFrame(today_report['credit_sales_list'])
                st.dataframe(credit_df, use_container_width=True, hide_index=True)
                st.info(f"Total Credit Sales: ${today_report['credit_sales']:.2f}")
            
            if today_report.get('debt_payments_list'):
                st.subheader("💳 Debt Payments Received")
                debt_df = pd.DataFrame(today_report['debt_payments_list'])
                st.dataframe(debt_df, use_container_width=True, hide_index=True)
                st.success(f"Total Debt Collections: ${today_report['debt_payments']:.2f}")
            
            if today_report.get('petty_cash_list'):
                st.subheader("💸 Petty Cash Expenses")
                petty_df = pd.DataFrame(today_report['petty_cash_list'])
                st.dataframe(petty_df, use_container_width=True, hide_index=True)
        else:
            st.info("No transactions recorded today. Start a shift to begin.")
    
    # ==============================
    # TAB 3: CASH FLOW
    # ==============================
    with tab3:
        st.markdown("## 💵 Cash Flow Analysis")
        
        # Cash flow chart
        st.markdown("### 📈 Cash Flow Trend (Last 30 Days)")
        
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
        st.markdown("### 👥 Cashier Performance")
        
        cashier_perf = get_cashier_performance()
        if not cashier_perf.empty:
            st.dataframe(cashier_perf, use_container_width=True, hide_index=True)
        
        # Summary metrics
        st.markdown("---")
        st.markdown("### 📊 Summary Statistics")
        
        all_time = get_cash_summary()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Cash Sales (All Time)", f"${all_time['cash_sales']:,.2f}")
        with col2:
            st.metric("Total Credit Sales", f"${all_time['credit_sales']:,.2f}")
        with col3:
            st.metric("Total Debt Collections", f"${all_time['debt_payments']:,.2f}")
    
    # ==============================
    # TAB 4: PETTY CASH
    # ==============================
    with tab4:
        st.markdown("## 📝 Petty Cash Management")
        
        # Record petty cash expense
        st.markdown("### 💸 Record Petty Cash Expense")
        
        col1, col2 = st.columns(2)
        
        with col1:
            petty_desc = st.text_input("Description", key="petty_desc", placeholder="What was purchased?")
            petty_amount = st.number_input("Amount ($)", min_value=0.01, step=5.0, key="petty_amount")
        
        with col2:
            petty_category = st.selectbox("Category", ["Office Supplies", "Transport", "Refreshments", "Cleaning", "Maintenance", "Other"], key="petty_category")
            petty_notes = st.text_area("Notes", key="petty_notes")
        
        if st.button("💰 Record Petty Cash", key="record_petty"):
            if petty_desc and petty_amount > 0:
                record_petty_cash(
                    description=petty_desc,
                    amount=petty_amount,
                    category=petty_category,
                    shift_id=st.session_state.get("shift_id", ""),
                    approved_by=st.session_state.get("username", "system"),
                    notes=petty_notes
                )
                st.success(f"✅ Petty cash expense recorded: ${petty_amount:.2f}")
                st.rerun()
            else:
                st.error("Please enter description and amount")
        
        # Petty cash history
        st.markdown("---")
        st.markdown("### 📋 Petty Cash History")
        
        petty_df = load_petty_cash()
        if not petty_df.empty:
            st.dataframe(petty_df.sort_values("date", ascending=False), use_container_width=True, hide_index=True)
            
            # Summary
            total_petty = petty_df["amount"].sum()
            st.metric("Total Petty Cash Expenses", f"${total_petty:,.2f}")
    
    # ==============================
    # TAB 5: BANK DEPOSITS
    # ==============================
    with tab5:
        st.markdown("## 🏦 Bank Deposits")
        
        # Record bank deposit
        st.markdown("### 💵 Record Bank Deposit")
        
        col1, col2 = st.columns(2)
        
        with col1:
            deposit_amount = st.number_input("Amount to Deposit ($)", min_value=0.01, step=50.0, key="deposit_amount")
            deposit_bank = st.selectbox("Bank", ["CABS", "FBC", "POSB", "CBZ", "NMB", "Stanbic", "EcoBank", "Other"], key="deposit_bank")
        
        with col2:
            deposit_ref = st.text_input("Reference Number", key="deposit_ref", placeholder="Deposit slip number")
            deposit_notes = st.text_area("Notes", key="deposit_notes")
        
        if st.button("💰 Record Bank Deposit", key="record_deposit"):
            if deposit_amount > 0:
                record_bank_deposit(
                    amount=deposit_amount,
                    bank_name=deposit_bank,
                    shift_id=st.session_state.get("shift_id", ""),
                    reference_no=deposit_ref,
                    notes=deposit_notes
                )
                st.success(f"✅ Bank deposit recorded: ${deposit_amount:.2f} to {deposit_bank}")
                st.rerun()
            else:
                st.error("Please enter deposit amount")
        
        # Deposit history
        st.markdown("---")
        st.markdown("### 📋 Bank Deposit History")
        
        deposits_df = load_bank_deposits()
        if not deposits_df.empty:
            st.dataframe(deposits_df.sort_values("date", ascending=False), use_container_width=True, hide_index=True)
            
            total_deposits = deposits_df["amount"].sum()
            st.metric("Total Bank Deposits", f"${total_deposits:,.2f}")
    
    # ==============================
    # EXPORT REPORT
    # ==============================
    st.markdown("---")
    st.subheader("📥 Export Daily Report")
    
    if st.button("📄 Generate Daily Report", use_container_width=True):
        report = get_daily_report()
        
        if report:
            report_text = f"""
            {'='*50}
            AZIEL INVESTMENTS - DAILY CASH REPORT
            {'='*50}
            
            Date: {report['date']}
            
            {'-'*30}
            CASH SUMMARY
            {'-'*30}
            Opening Cash: ${report['opening_cash']:.2f}
            Cash Sales: +${report['cash_sales']:.2f}
            Debt Payments: +${report['debt_payments']:.2f}
            Petty Cash: -${report['petty_cash']:.2f}
            Bank Deposits: -${report['deposits']:.2f}
            Expenses: -${report['expenses']:.2f}
            
            Expected Cash: ${report['expected_cash']:.2f}
            Actual Cash: ${report['closing_cash']:.2f}
            Variance: ${report['variance']:.2f}
            
            {'-'*30}
            SALES BREAKDOWN
            {'-'*30}
            Cash Sales: ${report['cash_sales']:.2f}
            Credit Sales: ${report['credit_sales']:.2f}
            Total Revenue: ${report['cash_sales'] + report['credit_sales']:.2f}
            
            {'='*50}
            Generated by Aziel Investments ERP
            {'='*50}
            """
            
            st.download_button(
                label="⬇ Download Report (TXT)",
                data=report_text,
                file_name=f"cash_report_{datetime.now().strftime('%Y%m%d')}.txt",
                mime="text/plain"
            )
        else:
            st.error("No data for today")