# backend/modules/shift_management.py
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px

from backend.core.db_adapter import (
    load_shifts, save_shifts, 
    get_all_active_shifts, get_active_shifts_by_branch,
    get_current_branch, load_cash, get_cash_summary,
    load_sales, load_products
)
from backend.modules.shift_manager import (
    start_shift, end_shift, 
    get_active_shift_for_branch,
    get_branch_active_shift_id,
    is_shift_active_in_branch,
    get_shift_stats,
    get_shift_summary,
    get_cashier_shift_history
)


def shift_management_page():
    """Main shift management page - Branch Level (FIXED - No infinite loop)"""
    
    st.title("🕐 Shift Management")
    st.caption("Manage branch shifts, track performance, and monitor activity")
    
    # Get current user and branch info
    username = st.session_state.get("username", "system")
    full_name = st.session_state.get("user_full_name", username)
    user_branch = st.session_state.get("user_branch", "HO")
    user_role = st.session_state.get("role", "cashier")
    branch_name = st.session_state.get("branch_name", "Head Office")
    
    # Check if user can manage shifts (manager, admin, owner)
    can_manage_shifts = user_role in ["owner", "manager", "admin"]
    
    # Get the active shift for this branch
    active_shift = get_active_shift_for_branch(user_branch)
    is_shift_active = active_shift is not None
    shift_id = active_shift.get("shift_id") if is_shift_active else None
    
    # ==============================
    # SIDEBAR - Shift Controls (FIXED - No auto-rerun)
    # ==============================
    st.sidebar.header("🔄 Shift Controls")
    st.sidebar.info(f"📍 **Branch:** {user_branch}")
    st.sidebar.info(f"👤 **Role:** {user_role.upper()}")
    
    # Active shift status in sidebar
    if is_shift_active:
        st.sidebar.success(f"🟢 Shift ACTIVE")
        st.sidebar.caption(f"ID: {shift_id[:12]}...")
        st.sidebar.caption(f"Started by: {active_shift.get('cashier_name', 'Unknown')}")
        st.sidebar.caption(f"Opening Cash: ${active_shift.get('opening_cash', 0):.2f}")
    else:
        st.sidebar.warning("🔴 No Active Shift")
        if can_manage_shifts:
            st.sidebar.info("💡 Start a shift using the form below")
    
    # Start a new shift (only for authorized users)
    if can_manage_shifts:
        st.sidebar.subheader("📌 Start New Branch Shift")
        st.sidebar.caption("Start a shift for this branch")
        
        with st.sidebar.form("start_shift_form"):
            cashier_username = st.text_input("Cashier Username", value=username)
            cashier_name = st.text_input("Cashier Name", value=full_name)
            manager_username = st.text_input("Manager Username", value=username)
            opening_cash = st.number_input("Opening Cash ($)", min_value=0.0, value=0.0, step=10.0)
            
            submitted = st.form_submit_button("🚀 Start Shift", use_container_width=True)
            
            if submitted:
                if not cashier_username or not cashier_name:
                    st.sidebar.error("Please enter cashier details")
                else:
                    success, result, message = start_shift(
                        cashier_username=cashier_username,
                        cashier_name=cashier_name,
                        branch_id=user_branch,
                        branch_name=branch_name,
                        manager_username=manager_username,
                        opening_cash=opening_cash
                    )
                    if success:
                        st.sidebar.success(f"✅ Shift started! ID: {result}")
                        st.sidebar.info(f"📌 Opening Cash: ${opening_cash:.2f}")
                        # Update session state
                        st.session_state.active_shift_id = result
                        st.session_state.branch_shift_active = True
                        # Use st.rerun() here - it's safe because it's outside the form
                        st.rerun()
                    else:
                        st.sidebar.error(f"❌ {message}")
    else:
        st.sidebar.info("ℹ️ Only managers and owners can start shifts.")
        st.sidebar.caption("Please ask your manager to start a shift.")
    
    # Display active shifts in sidebar (all branches)
    all_active_shifts = get_all_active_shifts()
    if not all_active_shifts.empty:
        st.sidebar.subheader("🟢 Active Shifts (All Branches)")
        for _, shift in all_active_shifts.iterrows():
            start_time = shift.get('start_time')
            if hasattr(start_time, 'strftime'):
                start_time_str = start_time.strftime("%Y-%m-%d %H:%M")
            else:
                start_time_str = str(start_time)[:16] if start_time else "N/A"
            
            st.sidebar.info(
                f"**{shift.get('cashier_name', 'Unknown')}**\n"
                f"Branch: {shift.get('branch_id', 'N/A')}\n"
                f"Shift: {shift.get('shift_id', 'N/A')[:12]}...\n"
                f"Started: {start_time_str}\n"
                f"Opening: ${shift.get('opening_cash', 0):.2f}"
            )
    
    # ==============================
    # MAIN CONTENT - Tabs
    # ==============================
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Active Shifts",
        "📈 Shift History",
        "💰 Shift Summary",
        "📋 Shift Performance"
    ])
    
    # ==============================
    # TAB 1: ACTIVE SHIFTS - BRANCH LEVEL (FIXED)
    # ==============================
    with tab1:
        st.markdown("## 🟢 Active Shifts")
        
        if all_active_shifts.empty:
            st.info("No active shifts at the moment")
        else:
            # Show current branch shift prominently
            if is_shift_active:
                st.markdown("### 🏢 Your Branch Active Shift")
                st.success(f"""
                ✅ **Shift ACTIVE in {branch_name}**
                - **Shift ID:** {shift_id}
                - **Started by:** {active_shift.get('cashier_name', 'Unknown')}
                - **Start Time:** {active_shift.get('start_time')}
                - **Opening Cash:** ${active_shift.get('opening_cash', 0):.2f}
                """)
                
                if can_manage_shifts:
                    if st.button("🛑 End This Shift", type="primary", use_container_width=True):
                        st.session_state.end_shift_id = shift_id
                        st.session_state.show_end_shift = True
                        st.rerun()
                
                # End Shift Dialog
                if st.session_state.get("show_end_shift", False) and st.session_state.get("end_shift_id") == shift_id:
                    with st.expander("📝 End Shift", expanded=True):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            # Get shift metrics
                            sales_df = load_sales()
                            cash_df = load_cash()
                            
                            # Calculate metrics for this shift
                            shift_sales = sales_df[sales_df["shift_id"] == shift_id] if not sales_df.empty else pd.DataFrame()
                            shift_cash = cash_df[cash_df["shift_id"] == shift_id] if not cash_df.empty else pd.DataFrame()
                            
                            total_sales = shift_sales["final_total"].sum() if not shift_sales.empty else 0
                            total_transactions = len(shift_sales)
                            total_profit = shift_sales["profit"].sum() if not shift_sales.empty else 0
                            cash_sales = shift_cash[shift_cash["type"] == "CASH_SALE"]["amount"].sum() if not shift_cash.empty else 0
                            credit_sales = shift_cash[shift_cash["type"] == "CREDIT_SALE"]["amount"].sum() if not shift_cash.empty else 0
                            debt_payments = shift_cash[shift_cash["type"] == "DEBT_PAYMENT"]["amount"].sum() if not shift_cash.empty else 0
                            expenses = shift_cash[shift_cash["type"] == "EXPENSE"]["amount"].sum() if not shift_cash.empty else 0
                            
                            st.metric("💰 Total Sales", f"${total_sales:,.2f}")
                            st.metric("📈 Total Profit", f"${total_profit:,.2f}")
                            st.metric("📊 Transactions", f"{total_transactions}")
                        
                        with col2:
                            closing_cash = st.number_input(
                                "Closing Cash ($)",
                                min_value=0.0,
                                value=float(active_shift.get("opening_cash", 0) + cash_sales + debt_payments - expenses),
                                step=10.0
                            )
                            
                            notes = st.text_area("Shift Notes", placeholder="Any issues or comments about this shift...")
                            
                            if st.button("✅ Confirm End Shift", type="primary", use_container_width=True):
                                success, message = end_shift(
                                    shift_id,
                                    closing_cash,
                                    total_sales,
                                    total_profit,
                                    total_transactions,
                                    notes
                                )
                                if success:
                                    st.success(f"✅ {message}")
                                    st.session_state.show_end_shift = False
                                    st.session_state.end_shift_id = None
                                    st.session_state.active_shift_id = None
                                    st.session_state.branch_shift_active = False
                                    st.rerun()
                                else:
                                    st.error(f"❌ {message}")
            else:
                st.warning("⚠️ No active shift in your branch")
                if can_manage_shifts:
                    st.info("💡 Start a shift using the form in the sidebar.")
            
            st.markdown("---")
            
            # Show all active shifts across branches
            st.markdown("### 🌐 All Active Shifts (All Branches)")
            
            # Convert to display format
            shift_display = []
            shift_ids = []
            
            for idx, row in all_active_shifts.iterrows():
                shift_id_val = row.get('shift_id')
                cashier_name = row.get('cashier_name', 'Unknown')
                branch = row.get('branch_id', 'N/A')
                start_time = row.get('start_time')
                
                # Convert time to string safely
                if hasattr(start_time, 'strftime'):
                    time_str = start_time.strftime("%Y-%m-%d %H:%M")
                else:
                    time_str = str(start_time) if start_time else "N/A"
                
                shift_display.append(f"{shift_id_val} - {cashier_name} - {branch} - Started: {time_str}")
                shift_ids.append(shift_id_val)
            
            if shift_display:
                selected_display = st.selectbox(
                    "Select Shift to View Details",
                    options=shift_display,
                    key="active_shift_select"
                )
                
                if selected_display:
                    shift_id_val = selected_display.split(" - ")[0]
                    shift = all_active_shifts[all_active_shifts["shift_id"] == shift_id_val]
                    
                    if not shift.empty:
                        shift_data = shift.iloc[0]
                        
                        # Display shift details
                        col1, col2, col3 = st.columns(3)
                        
                        start_time = shift_data.get('start_time')
                        if hasattr(start_time, 'strftime'):
                            start_time_str = start_time.strftime("%Y-%m-%d %H:%M")
                        else:
                            start_time_str = str(start_time) if start_time else "N/A"
                        
                        with col1:
                            st.metric("🧑‍💼 Cashier", shift_data.get('cashier_name', 'N/A'))
                            st.metric("🆔 Shift ID", shift_data.get('shift_id', 'N/A'))
                        
                        with col2:
                            st.metric("📅 Started", start_time_str)
                            st.metric("🏢 Branch", shift_data.get('branch_id', 'N/A'))
                        
                        with col3:
                            st.metric("💰 Opening Cash", f"${shift_data.get('opening_cash', 0):.2f}")
                            st.metric("📊 Status", f"🟢 {shift_data.get('status', 'OPEN')}")
            
            # Quick stats
            if not all_active_shifts.empty:
                st.markdown("### 📊 Active Shifts Summary")
                
                total_cashiers = len(all_active_shifts)
                total_opening = all_active_shifts["opening_cash"].sum() if "opening_cash" in all_active_shifts.columns else 0
                total_branches = all_active_shifts["branch_id"].nunique() if "branch_id" in all_active_shifts.columns else 0
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("👥 Active Cashiers", total_cashiers)
                with col2:
                    st.metric("💰 Total Opening Cash", f"${total_opening:,.2f}")
                with col3:
                    st.metric("🏢 Active Branches", total_branches)
    
    # ==============================
    # TAB 2: SHIFT HISTORY - BRANCH SPECIFIC
    # ==============================
    with tab2:
        st.markdown("## 📈 Shift History")
        st.caption(f"Showing shifts for branch: {user_branch}")
        
        # Filters
        col1, col2, col3 = st.columns(3)
        
        with col1:
            date_range = st.date_input(
                "Date Range",
                value=(datetime.now() - timedelta(days=7), datetime.now())
            )
        
        with col2:
            # Get cashiers for this branch
            all_cashiers = []
            if not shifts_df.empty and "cashier_name" in shifts_df.columns and "branch_id" in shifts_df.columns:
                branch_cashiers = shifts_df[shifts_df["branch_id"] == user_branch]
                all_cashiers = ["All"] + sorted(branch_cashiers["cashier_name"].unique().tolist())
            selected_cashier = st.selectbox("Cashier", all_cashiers if all_cashiers else ["All"])
        
        with col3:
            statuses = ["All", "OPEN", "CLOSED"]
            selected_status = st.selectbox("Status", statuses)
        
        # Filter shifts
        filtered_shifts = shifts_df.copy()
        
        if not filtered_shifts.empty:
            # Filter by branch
            if "branch_id" in filtered_shifts.columns:
                filtered_shifts = filtered_shifts[filtered_shifts["branch_id"] == user_branch]
            
            # Date filter
            if isinstance(date_range, tuple) and len(date_range) == 2:
                start_date, end_date = date_range
                filtered_shifts["start_date"] = pd.to_datetime(filtered_shifts["start_time"]).dt.date
                filtered_shifts = filtered_shifts[
                    (filtered_shifts["start_date"] >= start_date) & 
                    (filtered_shifts["start_date"] <= end_date)
                ]
            
            # Cashier filter
            if selected_cashier != "All" and "cashier_name" in filtered_shifts.columns:
                filtered_shifts = filtered_shifts[filtered_shifts["cashier_name"] == selected_cashier]
            
            # Status filter
            if selected_status != "All" and "status" in filtered_shifts.columns:
                filtered_shifts = filtered_shifts[filtered_shifts["status"] == selected_status]
            
            if not filtered_shifts.empty:
                # Display shifts table
                display_df = filtered_shifts.copy()
                
                # Format datetime columns
                for col in ["start_time", "end_time"]:
                    if col in display_df.columns:
                        display_df[col] = pd.to_datetime(display_df[col])
                        display_df[col] = display_df[col].dt.strftime("%Y-%m-%d %H:%M")
                
                # Rename columns for display
                display_columns = {
                    "shift_id": "Shift ID",
                    "cashier_name": "Cashier",
                    "cashier_username": "Username",
                    "start_time": "Start Time",
                    "end_time": "End Time",
                    "opening_cash": "Opening Cash",
                    "closing_cash": "Closing Cash",
                    "total_revenue": "Revenue",
                    "profit": "Profit",
                    "transactions": "Transactions",
                    "variance": "Variance",
                    "status": "Status"
                }
                
                display_df = display_df.rename(columns=display_columns)
                
                # Select columns to show
                show_cols = ["Shift ID", "Cashier", "Start Time", "End Time", "Revenue", "Transactions", "Status"]
                available_cols = [col for col in show_cols if col in display_df.columns]
                
                st.dataframe(
                    display_df[available_cols],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Revenue": st.column_config.NumberColumn("Revenue", format="$%.2f"),
                        "Opening Cash": st.column_config.NumberColumn("Opening Cash", format="$%.2f"),
                        "Closing Cash": st.column_config.NumberColumn("Closing Cash", format="$%.2f"),
                        "Variance": st.column_config.NumberColumn("Variance", format="$%.2f"),
                        "Profit": st.column_config.NumberColumn("Profit", format="$%.2f")
                    }
                )
                
                # Summary stats
                st.markdown("### 📊 History Summary")
                
                total_shifts = len(filtered_shifts)
                total_revenue = filtered_shifts["total_revenue"].sum() if "total_revenue" in filtered_shifts.columns else 0
                total_profit = filtered_shifts["profit"].sum() if "profit" in filtered_shifts.columns else 0
                total_transactions = filtered_shifts["transactions"].sum() if "transactions" in filtered_shifts.columns else 0
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("📊 Total Shifts", total_shifts)
                with col2:
                    st.metric("💰 Total Revenue", f"${total_revenue:,.2f}")
                with col3:
                    st.metric("📈 Total Profit", f"${total_profit:,.2f}")
                with col4:
                    st.metric("🛒 Transactions", f"{total_transactions:,.0f}")
            else:
                st.info("No shifts found matching the filters")
        else:
            st.info("No shift history available")
    
    # ==============================
    # TAB 3: SHIFT SUMMARY - BRANCH LEVEL
    # ==============================
    with tab3:
        st.markdown("## 💰 Shift Summary")
        st.caption(f"Summary for branch: {user_branch}")
        
        # Get cash summary for this branch
        cash_summary = get_cash_summary()
        
        if cash_summary:
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("💰 Opening Cash", f"${cash_summary.get('opening_cash', 0):,.2f}")
            with col2:
                st.metric("💵 Cash Sales", f"${cash_summary.get('cash_sales', 0):,.2f}")
            with col3:
                st.metric("💳 Credit Sales", f"${cash_summary.get('credit_sales', 0):,.2f}")
            with col4:
                st.metric("📊 Total Revenue", f"${cash_summary.get('total_revenue', 0):,.2f}")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("💸 Expenses", f"${cash_summary.get('expenses', 0):,.2f}")
            with col2:
                st.metric("🏦 Deposits", f"${cash_summary.get('deposits', 0):,.2f}")
            with col3:
                st.metric("📋 Transactions", cash_summary.get('transactions_count', 0))
            with col4:
                st.metric("📊 Variance", f"${cash_summary.get('variance', 0):,.2f}")
        
        # Daily trend - branch specific
        st.markdown("### 📈 Daily Shift Performance")
        
        if not shifts_df.empty:
            # Filter by branch
            branch_shifts = shifts_df[shifts_df["branch_id"] == user_branch] if "branch_id" in shifts_df.columns else shifts_df
            
            if not branch_shifts.empty:
                # Create a copy to avoid modifying the original
                shifts_copy = branch_shifts.copy()
                shifts_copy["date"] = pd.to_datetime(shifts_copy["start_time"]).dt.date
                daily_summary = shifts_copy.groupby("date").agg({
                    "total_revenue": "sum",
                    "profit": "sum",
                    "transactions": "sum"
                }).reset_index()
                
                if not daily_summary.empty:
                    fig = px.line(
                        daily_summary,
                        x="date",
                        y=["total_revenue", "profit"],
                        title=f"Daily Revenue and Profit - {user_branch}",
                        labels={"value": "Amount ($)", "date": "Date", "variable": "Metric"}
                    )
                    fig.update_layout(height=350)
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No shift data available for this branch")
    
    # ==============================
    # TAB 4: SHIFT PERFORMANCE - BRANCH LEVEL
    # ==============================
    with tab4:
        st.markdown("## 📋 Shift Performance")
        st.caption(f"Performance for branch: {user_branch}")
        
        if not shifts_df.empty and "cashier_name" in shifts_df.columns:
            # Filter by branch
            branch_shifts = shifts_df[shifts_df["branch_id"] == user_branch] if "branch_id" in shifts_df.columns else shifts_df
            
            if not branch_shifts.empty:
                # Cashier performance
                cashier_performance = branch_shifts.groupby("cashier_name").agg({
                    "shift_id": "count",
                    "total_revenue": "sum",
                    "profit": "sum",
                    "transactions": "sum"
                }).reset_index()
                
                cashier_performance.columns = ["Cashier", "Shifts", "Total Revenue", "Total Profit", "Transactions"]
                cashier_performance["Avg Revenue/Shift"] = cashier_performance["Total Revenue"] / cashier_performance["Shifts"]
                cashier_performance["Avg Profit/Shift"] = cashier_performance["Total Profit"] / cashier_performance["Shifts"]
                
                # Sort by revenue
                cashier_performance = cashier_performance.sort_values("Total Revenue", ascending=False)
                
                # Display
                st.markdown("### 🏆 Cashier Performance Ranking")
                
                st.dataframe(
                    cashier_performance,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Cashier": "Cashier",
                        "Shifts": "Shifts",
                        "Total Revenue": st.column_config.NumberColumn("Total Revenue", format="$%.2f"),
                        "Total Profit": st.column_config.NumberColumn("Total Profit", format="$%.2f"),
                        "Transactions": "Transactions",
                        "Avg Revenue/Shift": st.column_config.NumberColumn("Avg Revenue/Shift", format="$%.2f"),
                        "Avg Profit/Shift": st.column_config.NumberColumn("Avg Profit/Shift", format="$%.2f")
                    }
                )
                
                # Visualization
                col1, col2 = st.columns(2)
                
                with col1:
                    fig = px.bar(
                        cashier_performance.head(10),
                        x="Cashier",
                        y="Total Revenue",
                        title=f"Top Cashiers by Revenue - {user_branch}",
                        color="Total Revenue",
                        color_continuous_scale="Greens",
                        text="Total Revenue"
                    )
                    fig.update_traces(texttemplate="$%{text:.2f}", textposition="outside")
                    fig.update_layout(height=350)
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    fig = px.bar(
                        cashier_performance.head(10),
                        x="Cashier",
                        y="Transactions",
                        title=f"Top Cashiers by Transactions - {user_branch}",
                        color="Transactions",
                        color_continuous_scale="Blues",
                        text="Transactions"
                    )
                    fig.update_traces(texttemplate="%{text}", textposition="outside")
                    fig.update_layout(height=350)
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No performance data available for this branch")
        else:
            st.info("No performance data available")


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    shift_management_page()