import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

from backend.modules.expenses import (
    load_expenses,
    load_expense_categories,
    record_expense,
    set_budget,
    get_budget_vs_actual,
    get_expense_summary_by_category,
    get_expense_trend,
    get_top_expenses,
    add_recurring_expense,
    process_recurring_expenses,
    add_expense_category
)


def expenses_dashboard():
    """Enhanced Expenses Dashboard with Budgeting and Analytics"""
    
    st.title("📊 Expenses Management Dashboard")
    st.caption("Track spending, manage budgets, and control costs")
    
    # ==============================
    # EXPENSE TABS
    # ==============================
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📝 Record Expense",
        "📊 Budget vs Actual",
        "📈 Expense Analytics",
        "🔄 Recurring Expenses",
        "📋 All Expenses"
    ])
    
    # ==============================
    # TAB 1: RECORD EXPENSE
    # ==============================
    with tab1:
        st.markdown("## 📝 Record New Expense")
        
        categories = load_expense_categories()
        
        col1, col2 = st.columns(2)
        
        with col1:
            expense_type = st.selectbox("Expense Type", ["Operational", "Capital", "Recurring", "One-time"], key="exp_type")
            category = st.selectbox("Category", categories, key="exp_category")
            description = st.text_input("Description *", key="exp_desc")
            amount = st.number_input("Amount ($) *", min_value=0.01, step=10.0, key="exp_amount")
        
        with col2:
            vendor = st.text_input("Vendor/Supplier", key="exp_vendor", placeholder="e.g., Econet, ZESA...")
            payment_method = st.selectbox("Payment Method", ["CASH", "BANK TRANSFER", "CARD", "ECOCASH"], key="exp_payment")
            department = st.selectbox("Department/Cost Center", ["General", "Sales", "Operations", "Admin"], key="exp_dept")
            notes = st.text_area("Notes", key="exp_notes", placeholder="Additional details...")
        
        # Add new category option
        with st.expander("➕ Add New Category"):
            new_category = st.text_input("New Category Name", key="new_category")
            if st.button("Add Category", key="add_category_btn"):
                if new_category:
                    add_expense_category(new_category)
                    st.success(f"Category '{new_category}' added!")
                    st.rerun()
        
        if st.button("💰 Record Expense", type="primary", use_container_width=True):
            if description and amount > 0:
                record_expense(
                    expense_type=expense_type,
                    category=category,
                    description=description,
                    amount=amount,
                    vendor=vendor,
                    payment_method=payment_method,
                    department=department,
                    notes=notes,
                    user=st.session_state.get("username", "System")
                )
                st.balloons()
                st.success(f"✅ Expense recorded: ${amount:.2f} - {description}")
                st.rerun()
            else:
                st.error("Please enter description and amount")
    
    # ==============================
    # TAB 2: BUDGET VS ACTUAL
    # ==============================
    with tab2:
        st.markdown("## 📊 Budget vs Actual Analysis")
        
        # Year/Month selection
        col1, col2 = st.columns(2)
        with col1:
            budget_year = st.number_input("Year", min_value=2020, max_value=2030, value=datetime.now().year, key="budget_year")
        with col2:
            budget_month = st.selectbox("Month", range(1, 13), index=datetime.now().month - 1, key="budget_month")
        
        # Budget input section
        st.markdown("### 🎯 Set Budget")
        
        categories = load_expense_categories()
        selected_cat = st.selectbox("Select Category", categories, key="budget_cat")
        budget_amount = st.number_input("Budget Amount ($)", min_value=0.0, step=100.0, key="budget_amount_input")
        
        if st.button("Set Budget", key="set_budget_btn"):
            set_budget(budget_year, budget_month, selected_cat, budget_amount)
            st.success(f"Budget set for {selected_cat}: ${budget_amount:.2f}")
        
        st.markdown("---")
        
        # Budget vs Actual Display
        st.markdown("### 📈 Budget Performance")
        
        budget_df = get_budget_vs_actual(budget_year, budget_month)
        
        if not budget_df.empty:
            # Key metrics
            total_budget = budget_df["budget_amount"].sum()
            total_actual = budget_df["actual_amount"].sum()
            total_variance = total_budget - total_actual
            variance_percent = (total_variance / total_budget * 100) if total_budget > 0 else 0
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Budget", f"${total_budget:,.2f}")
            with col2:
                st.metric("Total Actual", f"${total_actual:,.2f}")
            with col3:
                delta_color = "normal" if total_variance >= 0 else "inverse"
                st.metric("Variance", f"${total_variance:,.2f}", 
                         delta=f"{variance_percent:+.1f}%", 
                         delta_color=delta_color)
            
            # Show budget vs actual chart
            chart_df = budget_df[budget_df["budget_amount"] > 0].copy()
            
            if not chart_df.empty:
                fig = go.Figure()
                
                fig.add_trace(go.Bar(
                    x=chart_df["category"],
                    y=chart_df["budget_amount"],
                    name="Budget",
                    marker_color="#2ecc71"
                ))
                
                fig.add_trace(go.Bar(
                    x=chart_df["category"],
                    y=chart_df["actual_amount"],
                    name="Actual",
                    marker_color="#e74c3c"
                ))
                
                fig.update_layout(
                    title="Budget vs Actual by Category",
                    xaxis_title="Category",
                    yaxis_title="Amount ($)",
                    barmode="group",
                    height=400
                )
                
                st.plotly_chart(fig, use_container_width=True)
            
            # Detailed table
            st.markdown("### 📋 Detailed Budget vs Actual")
            
            display_df = budget_df[["category", "budget_amount", "actual_amount", "variance", "variance_percent", "status"]]
            display_df = display_df[display_df["budget_amount"] > 0]
            display_df = display_df.sort_values("variance_percent", ascending=True)
            
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            # Warnings for over-budget
            over_budget = budget_df[budget_df["variance"] < 0]
            if not over_budget.empty:
                st.warning(f"⚠️ {len(over_budget)} categories are over budget!")
                for _, row in over_budget.iterrows():
                    st.write(f"• {row['category']}: ${abs(row['variance']):.2f} over budget")
        else:
            st.info("No budget data available. Set budgets above.")
    
    # ==============================
    # TAB 3: EXPENSE ANALYTICS
    # ==============================
    with tab3:
        st.markdown("## 📈 Expense Analytics")
        
        # Date range filter
        col1, col2 = st.columns(2)
        with col1:
            filter_year = st.selectbox("Year", [2024, 2025, 2026], index=1, key="analytics_year")
        with col2:
            filter_month = st.selectbox("Month", ["All", 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], key="analytics_month")
        
        month_filter = None if filter_month == "All" else filter_month
        
        # Category breakdown
        st.markdown("### 📊 Expenses by Category")
        
        category_summary = get_expense_summary_by_category(filter_year, month_filter)
        
        if not category_summary.empty:
            fig_pie = px.pie(
                category_summary,
                values="Total Amount",
                names="Category",
                title="Expense Distribution by Category",
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            fig_pie.update_layout(height=400)
            st.plotly_chart(fig_pie, use_container_width=True)
            
            # Top categories bar chart
            fig_bar = px.bar(
                category_summary.head(10),
                x="Total Amount",
                y="Category",
                orientation="h",
                title="Top 10 Expense Categories",
                color="Total Amount",
                color_continuous_scale="Reds",
                text="Total Amount"
            )
            fig_bar.update_traces(texttemplate="$%{text:.0f}", textposition="outside")
            fig_bar.update_layout(height=400)
            st.plotly_chart(fig_bar, use_container_width=True)
        
        # Monthly trend
        st.markdown("### 📅 Expense Trend")
        
        trend_df = get_expense_trend(12)
        
        if not trend_df.empty:
            fig_trend = px.line(
                trend_df,
                x="Month",
                y="Total Expenses",
                title="Monthly Expense Trend (Last 12 Months)",
                markers=True,
                line_shape="spline"
            )
            fig_trend.update_layout(height=350)
            st.plotly_chart(fig_trend, use_container_width=True)
        
        # Top expenses
        st.markdown("### 🔝 Largest Expenses")
        
        top_expenses = get_top_expenses(10, filter_year, month_filter)
        
        if not top_expenses.empty:
            st.dataframe(
                top_expenses[["date", "description", "category", "amount", "vendor"]],
                use_container_width=True,
                hide_index=True
            )
    
    # ==============================
    # TAB 4: RECURRING EXPENSES
    # ==============================
    with tab4:
        st.markdown("## 🔄 Recurring Expenses")
        st.caption("Set up automatic recurring expenses (rent, subscriptions, salaries)")
        
        # Create recurring expense
        with st.expander("➕ Add Recurring Expense", expanded=True):
            col1, col2 = st.columns(2)
            
            with col1:
                rec_description = st.text_input("Description", key="rec_desc")
                rec_category = st.selectbox("Category", load_expense_categories(), key="rec_cat")
                rec_amount = st.number_input("Amount ($)", min_value=0.01, step=10.0, key="rec_amount")
            
            with col2:
                rec_frequency = st.selectbox("Frequency", ["Monthly", "Weekly", "Quarterly", "Yearly"], key="rec_freq")
                rec_day = st.number_input("Day of Month", min_value=1, max_value=28, value=1, key="rec_day")
                rec_vendor = st.text_input("Vendor", key="rec_vendor")
                rec_notes = st.text_area("Notes", key="rec_notes")
            
            if st.button("💾 Save Recurring Expense", key="save_recurring"):
                if rec_description and rec_amount > 0:
                    add_recurring_expense(
                        description=rec_description,
                        category=rec_category,
                        amount=rec_amount,
                        frequency=rec_frequency,
                        day_of_month=rec_day,
                        vendor=rec_vendor,
                        notes=rec_notes
                    )
                    st.success(f"Recurring expense '{rec_description}' added!")
                    st.rerun()
        
        # Process recurring expenses button
        st.markdown("---")
        
        if st.button("🔄 Process Due Recurring Expenses", key="process_recurring"):
            processed = process_recurring_expenses()
            if processed:
                st.success(f"✅ Processed {len(processed)} recurring expenses: {', '.join(processed)}")
            else:
                st.info("No recurring expenses due today")
        
        # Display existing recurring expenses
        from backend.modules.expenses import load_recurring_expenses
        recurring_df = load_recurring_expenses()
        
        if not recurring_df.empty:
            st.markdown("### 📋 Active Recurring Expenses")
            st.dataframe(
                recurring_df[["description", "category", "amount", "frequency", "day_of_month", "vendor", "active"]],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No recurring expenses set up")
    
    # ==============================
    # TAB 5: ALL EXPENSES
    # ==============================
    with tab5:
        st.markdown("## 📋 All Expense Records")
        
        expenses_df = load_expenses()
        
        if not expenses_df.empty:
            # Search and filter
            col1, col2, col3 = st.columns(3)
            
            with col1:
                search_term = st.text_input("Search", placeholder="Description, vendor...", key="search_expenses")
            
            with col2:
                cat_filter = st.selectbox("Category", ["All"] + load_expense_categories(), key="cat_filter")
            
            with col3:
                sort_by = st.selectbox("Sort By", ["Date (Newest)", "Amount (Highest)", "Amount (Lowest)"], key="sort_expenses")
            
            filtered_df = expenses_df.copy()
            
            if search_term:
                filtered_df = filtered_df[
                    filtered_df["description"].str.contains(search_term, case=False) |
                    filtered_df["vendor"].str.contains(search_term, case=False)
                ]
            
            if cat_filter != "All":
                filtered_df = filtered_df[filtered_df["category"] == cat_filter]
            
            if sort_by == "Amount (Highest)":
                filtered_df = filtered_df.sort_values("amount", ascending=False)
            elif sort_by == "Amount (Lowest)":
                filtered_df = filtered_df.sort_values("amount", ascending=True)
            else:
                filtered_df = filtered_df.sort_values("date", ascending=False)
            
            # Summary
            total_expenses = filtered_df["amount"].sum()
            st.metric("Total Expenses (Filtered)", f"${total_expenses:,.2f}")
            
            # Display table
            display_cols = ["date", "description", "category", "amount", "vendor", "payment_method"]
            available_cols = [col for col in display_cols if col in filtered_df.columns]
            
            st.dataframe(filtered_df[available_cols], use_container_width=True, hide_index=True)
            
            # Export
            csv = filtered_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Download Expenses (CSV)",
                data=csv,
                file_name=f"expenses_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        else:
            st.info("No expenses recorded yet")