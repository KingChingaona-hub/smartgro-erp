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
    get_all_active_shifts,
    get_active_shift_for_branch,
    get_branch_active_shift_id,
    is_shift_active_in_branch,
    get_shift_stats
)


def cash_dashboard():
    """Enhanced Cash Register Dashboard with comprehensive features"""
    
    st.title("💰 Cash Register Management System")
    st.caption("Track shifts, manage cash flow, and control expenses")
    
    # Get current user and branch info
    username = st.session_state.get("username", "system")
    user_branch = st.session_state.get("user_branch", "HO")
    user_role = st.session_state.get("role", "cashier")
    full_name = st.session_state.get("user_full_name", username)
    
    # Check if user can manage shifts (manager, admin, owner)
    can_manage_shifts = user_role in ["owner", "manager", "admin"]
    
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
    # TAB 1: SHIFT MANAGEMENT - BRANCH LEVEL (FIXED)
    # ==============================
    with tab1:
        st.markdown("## 🔄 Shift Management")
        
        # Get the active shift for this branch
        active_shift = get_active_shift_for_branch(user_branch)
        is_shift_active = active_shift is not None
        shift_id = active_shift.get("shift_id") if is_shift_active else None
        
        # Display branch info
        st.info(f"📍 **Branch:** {user_branch} | **Role:** {user_role.upper()}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if not is_shift_active:
                # No active shift - show start shift button (only for authorized users)
                if can_manage_shifts:
                    st.markdown("### 🟢 Start New Shift")
                    st.caption("Only managers and owners can start shifts")
                    
                    opening = st.number_input(
                        "Opening Cash Amount", 
                        min_value=0.0, 
                        value=0.0, 
                        step=50.0, 
                        key="opening_cash_input"
                    )
                    
                    if st.button("🚀 Start Shift", type="primary", use_container_width=True):
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
                                
                                st.success(f"✅ Shift started successfully! Shift ID: {result}")
                                st.info(f"📌 Opening Cash: ${opening:.2f}")
                                st.rerun()
                            else:
                                st.error(f"❌ Failed to start shift: {message}")
                else:
                    st.warning("⛔ No active shift in your branch. Please ask your manager to start a shift.")
                    st.info("💡 Only managers and owners can start shifts.")
            else:
                # Active shift exists - show shift details
                st.markdown("### 🟢 Active Shift")
                
                start_time = active_shift.get("start_time")
                if hasattr(start_time, 'strftime'):
                    start_time_str = start_time.strftime("%Y-%m-%d %H:%M")
                else:
                    start_time_str = str(start_time) if start_time else "N/A"
                
                st.markdown(f"""
                **Shift ID:** `{active_shift.get('shift_id')}`  
                **Started by:** {active_shift.get('cashier_name', 'Unknown')}  
                **Start Time:** {start_time_str}  
                **Opening Cash:** ${active_shift.get('opening_cash', 0):.2f}  
                **Branch:** {active_shift.get('branch_name', user_branch)}
                """)
                
                # Show shift summary
                summary = get_cash_summary(shift_id)
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Cash Sales", f"${summary['cash_sales']:.2f}")
                with col2:
                    st.metric("Credit Sales", f"${summary['credit_sales']:.2f}")
                with col3:
                    st.metric("Debt Payments", f"${summary['debt_payments']:.2f}")
        
        with col2:
            if is_shift_active:
                # Only allow ending shift for authorized users
                if can_manage_shifts:
                    st.markdown("### 🔴 End Shift")
                    
                    actual_cash = st.number_input(
                        "Actual Cash Counted", 
                        min_value=0.0, 
                        value=0.0, 
                        step=10.0, 
                        key="actual_cash_input"
                    )
                    
                    notes = st.text_area("Shift Notes", placeholder="Any issues or comments...", key="shift_notes")
                    
                    if st.button("🔴 Close Shift", type="secondary", use_container_width=True):
                        with st.spinner("Closing shift..."):
                            summary = get_cash_summary(shift_id)
                            
                            expected_cash = (summary["opening_cash"] + 
                                           summary["cash_sales"] + 
                                           summary["debt_payments"] - 
                                           summary["petty_cash"] - 
                                           summary["deposits"] - 
                                           summary["expenses"])
                            variance = actual_cash - expected_cash
                            
                            success, result = end_shift(
                                shift_id=shift_id,
                                closing_cash=actual_cash,
                                total_sales=summary["cash_sales"] + summary["credit_sales"],
                                profit=summary["cash_sales"] * 0.3,
                                transactions=summary["transactions_count"],
                                notes=notes
                            )
                            
                            if success:
                                record_closing_cash(actual_cash, shift_id)
                                
                                st.success(f"✅ Shift closed!")
                                st.info(f"💰 Expected Cash: ${expected_cash:.2f}")
                                
                                if variance >= 0:
                                    st.success(f"✅ Cash Surplus: ${variance:.2f}")
                                else:
                                    st.error(f"⚠️ Cash Shortage: ${abs(variance):.2f}")
                                
                                # Clear session state
                                st.session_state.shift_id = None
                                st.session_state.active_shift_id = None
                                st.session_state.branch_shift_active = False
                                
                                st.rerun()
                            else:
                                st.error(f"❌ Failed to close shift: {result}")
                else:
                    st.info("💡 Only managers and owners can close shifts.")
                    st.caption("Please ask your manager to close the shift.")
        
        # Shift history - show all shifts for this branch
        st.markdown("---")
        st.markdown("### 📋 Shift History (This Branch)")
        
        shifts_df = load_shifts()
        if not shifts_df.empty:
            # Filter for this branch
            branch_shifts = shifts_df[shifts_df["branch_id"] == user_branch]
            
            if not branch_shifts.empty:
                display_shifts = branch_shifts[["shift_id", "cashier_name", "start_time", "end_time", "opening_cash", "closing_cash", "cash_sales", "variance", "status"]].sort_values("start_time", ascending=False).head(20)
                
                # Format timestamps
                for col in ["start_time", "end_time"]:
                    if col in display_shifts.columns:
                        display_shifts[col] = pd.to_datetime(display_shifts[col], errors="coerce")
                        display_shifts[col] = display_shifts[col].dt.strftime("%Y-%m-%d %H:%M")
                
                st.dataframe(display_shifts, use_container_width=True, hide_index=True)
                
                # Summary stats for this branch
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
        
        # Show all active shifts across branches (for managers/owners)
        if can_manage_shifts:
            st.markdown("---")
            st.markdown("### 🌐 All Active Shifts (All Branches)")
            
            all_active = get_all_active_shifts()
            if not all_active.empty:
                display_active = all_active[["shift_id", "branch_id", "branch_name", "cashier_name", "start_time", "opening_cash"]]
                st.dataframe(display_active, use_container_width=True, hide_index=True)
            else:
                st.info("No active shifts in any branch")
    
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
        
        # Use branch shift ID if available
        shift_to_use = st.session_state.get("shift_id") or st.session_state.get("active_shift_id") or ""
        
        if st.button("💰 Record Petty Cash", key="record_petty"):
            if petty_desc and petty_amount > 0:
                record_petty_cash(
                    description=petty_desc,
                    amount=petty_amount,
                    category=petty_category,
                    shift_id=shift_to_use,
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
        
        # Use branch shift ID if available
        shift_to_use = st.session_state.get("shift_id") or st.session_state.get("active_shift_id") or ""
        
        if st.button("💰 Record Bank Deposit", key="record_deposit"):
            if deposit_amount > 0:
                record_bank_deposit(
                    amount=deposit_amount,
                    bank_name=deposit_bank,
                    shift_id=shift_to_use,
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
            Branch: {user_branch}
            
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