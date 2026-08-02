# backend/modules/expenses_page.py
import streamlit as st
import pandas as pd
from datetime import datetime
from backend.modules.expenses import (
    record_expense, 
    load_expenses, 
    get_monthly_expenses, 
    load_expense_categories,
    delete_expense_by_id,
    delete_expense,
    add_expense_category,
    debug_expenses_file,
    recover_from_backup,
    EXPENSES_FILE
)


def expenses_page():
    """Expenses Management Page - Fixed: Better data handling and debugging"""
    
    st.title("Business Expenses")
    st.caption("Record and track all business expenses")

    # ==============================
    # SESSION STATE INIT
    # ==============================
    if "expense_recorded" not in st.session_state:
        st.session_state.expense_recorded = False
    if "expense_message" not in st.session_state:
        st.session_state.expense_message = ""
    if "expense_success" not in st.session_state:
        st.session_state.expense_success = False
    if "category_added" not in st.session_state:
        st.session_state.category_added = False
    if "category_message" not in st.session_state:
        st.session_state.category_message = ""
    if "delete_success" not in st.session_state:
        st.session_state.delete_success = False
    if "delete_message" not in st.session_state:
        st.session_state.delete_message = ""

    # ==============================
    # DISPLAY MESSAGES FROM SESSION STATE
    # ==============================
    if st.session_state.expense_success and st.session_state.expense_message:
        st.success(f"{st.session_state.expense_message}")
        st.balloons()
        st.session_state.expense_success = False
        st.session_state.expense_message = ""
    
    if st.session_state.category_added and st.session_state.category_message:
        st.success(f"{st.session_state.category_message}")
        st.session_state.category_added = False
        st.session_state.category_message = ""
    
    if st.session_state.delete_success and st.session_state.delete_message:
        st.success(f"{st.session_state.delete_message}")
        st.session_state.delete_success = False
        st.session_state.delete_message = ""

    # ==============================
    # LOAD EXPENSES WITH DEBUG
    # ==============================
    df = load_expenses()
    
    # Debug info in sidebar
    with st.sidebar.expander("Expenses Debug Info"):
        st.write(f"**File path:** `{EXPENSES_FILE}`")
        st.write(f"**File exists:** {EXPENSES_FILE.exists()}")
        if EXPENSES_FILE.exists():
            st.write(f"**File size:** {EXPENSES_FILE.stat().st_size} bytes")
        st.write(f"**Records loaded:** {len(df)}")
        
        if not df.empty:
            st.write(f"**Date range:** {df['date'].min()} to {df['date'].max()}")
            st.write(f"**Total amount:** ${df['amount'].sum():,.2f}")
        
        # Show raw file content if small
        if EXPENSES_FILE.exists() and EXPENSES_FILE.stat().st_size < 5000:
            try:
                with open(EXPENSES_FILE, 'r') as f:
                    content = f.read()
                    st.text_area("Raw file content:", content, height=150)
            except:
                pass
        
        # Recovery option
        if st.button("Recover from Backup", use_container_width=True):
            success, message = recover_from_backup()
            if success:
                st.success(message)
                st.rerun()
            else:
                st.warning(message)

    # ==============================
    # LOAD CATEGORIES
    # ==============================
    categories = load_expense_categories()

    # ==============================
    # INPUT FORM
    # ==============================
    st.subheader("Record Expense")
    
    with st.form(key="expense_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            expense_type = st.selectbox(
                "Expense Type",
                ["Operational", "Capital", "Recurring", "One-time"],
                key="exp_type"
            )
            
            category = st.selectbox(
                "Category",
                categories,
                key="exp_category"
            )
            
            description = st.text_input(
                "Description *",
                placeholder="e.g., Monthly rent, Electricity bill...",
                key="exp_desc"
            )
        
        with col2:
            amount_input = st.number_input(
                "Amount ($) *",
                min_value=0.01,
                step=10.0,
                value=0.01,
                key="exp_amount"
            )
            
            vendor = st.text_input(
                "Vendor/Supplier",
                placeholder="e.g., ZESA, Econet, Landlord...",
                key="exp_vendor"
            )
            
            payment_method = st.selectbox(
                "Payment Method",
                ["CASH", "BANK TRANSFER", "CARD", "ECOCASH", "OTHER"],
                key="exp_payment"
            )
        
        notes = st.text_area(
            "Notes (optional)",
            placeholder="Additional details...",
            key="exp_notes"
        )
        
        submitted = st.form_submit_button("Record Expense", type="primary", use_container_width=True)

        if submitted:
            if description and amount_input > 0:
                success, message = record_expense(
                    expense_type=expense_type,
                    category=category,
                    description=description,
                    amount=float(amount_input),
                    vendor=vendor,
                    payment_method=payment_method,
                    user=st.session_state.get("username", "System"),
                    notes=notes
                )
                if success:
                    st.session_state.expense_success = True
                    st.session_state.expense_message = message
                    st.success(f"{message}")
                    st.balloons()
                    # Refresh the page to show new expense
                    st.rerun()
                else:
                    st.error(f"Failed to record expense: {message}")
            else:
                st.error("Please enter description and amount")

    # ==============================
    # ADD NEW CATEGORY
    # ==============================
    with st.expander("Add New Category"):
        with st.form(key="add_category_form", clear_on_submit=True):
            new_category = st.text_input(
                "New Category Name", 
                key="new_category_input",
                placeholder="Enter new category name..."
            )
            
            add_category_submitted = st.form_submit_button(
                "Add Category", 
                type="primary",
                use_container_width=True
            )
            
            if add_category_submitted:
                if new_category and new_category.strip():
                    if new_category.strip() not in categories:
                        success = add_expense_category(new_category.strip())
                        if success:
                            st.session_state.category_added = True
                            st.session_state.category_message = f"Category '{new_category.strip()}' added successfully!"
                            st.success(f"Category '{new_category.strip()}' added!")
                            st.rerun()
                        else:
                            st.error("Failed to add category. Please try again.")
                    else:
                        st.warning(f"Category '{new_category.strip()}' already exists!")
                else:
                    st.error("Please enter a category name")

    # ==============================
    # SUMMARY
    # ==============================
    st.markdown("---")
    st.subheader("Expense Summary")
    
    col1, col2, col3 = st.columns(3)
    
    monthly_total = get_monthly_expenses()
    
    with col1:
        st.metric("This Month Expenses", f"${monthly_total:.2f}")
    
    if not df.empty:
        total_all = df["amount"].sum()
        with col2:
            st.metric("Total All Time", f"${total_all:,.2f}")
        
        # Average expense
        avg_expense = df["amount"].mean()
        with col3:
            st.metric("Average Expense", f"${avg_expense:.2f}")
    else:
        with col2:
            st.metric("Total All Time", "$0.00")
        with col3:
            st.metric("Average Expense", "$0.00")
    
    # ==============================
    # TABLE & DELETE
    # ==============================
    st.markdown("---")
    st.subheader("Expenses Records")
    
    if not df.empty:
        # Create display version with proper formatting
        df_display = df.copy()
        df_display["date_display"] = pd.to_datetime(df_display["date"]).dt.strftime("%Y-%m-%d %H:%M")
        df_sorted = df_display.sort_values("date", ascending=False)
        
        # Reset index for display
        df_sorted = df_sorted.reset_index(drop=True)
        
        # Show record count
        st.caption(f"Showing {len(df_sorted)} expense records")
        
        # Display with better formatting
        display_columns = ["date_display", "category", "description", "amount", "vendor", "payment_method"]
        available_cols = [col for col in display_columns if col in df_sorted.columns]
        
        st.dataframe(
            df_sorted[available_cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                "date_display": "Date",
                "amount": st.column_config.NumberColumn("Amount", format="$%.2f")
            }
        )
        
        # ==============================
        # FILTER AND ANALYZE
        # ==============================
        with st.expander("Filter and Analyze"):
            col1, col2 = st.columns(2)
            
            with col1:
                # Filter by category
                all_categories = ["All"] + sorted(df["category"].unique().tolist())
                filter_category = st.selectbox("Filter by Category", all_categories, key="filter_category")
            
            with col2:
                # Filter by date range
                min_date = pd.to_datetime(df["date"]).min().date()
                max_date = pd.to_datetime(df["date"]).max().date()
                date_range = st.date_input(
                    "Date Range",
                    value=(min_date, max_date),
                    min_value=min_date,
                    max_value=max_date,
                    key="filter_date"
                )
            
            # Apply filters
            filtered_df = df.copy()
            if filter_category != "All":
                filtered_df = filtered_df[filtered_df["category"] == filter_category]
            
            if len(date_range) == 2:
                start_date, end_date = date_range
                filtered_df["date_only"] = pd.to_datetime(filtered_df["date"]).dt.date
                filtered_df = filtered_df[
                    (filtered_df["date_only"] >= start_date) & 
                    (filtered_df["date_only"] <= end_date)
                ]
                filtered_df = filtered_df.drop(columns=["date_only"])
            
            if not filtered_df.empty:
                st.write(f"**Filtered Results:** {len(filtered_df)} records, Total: ${filtered_df['amount'].sum():,.2f}")
                
                # Show filtered data
                filtered_display = filtered_df.copy()
                filtered_display["date_display"] = pd.to_datetime(filtered_display["date"]).dt.strftime("%Y-%m-%d %H:%M")
                st.dataframe(
                    filtered_display[["date_display", "category", "description", "amount", "vendor"]],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "date_display": "Date",
                        "amount": st.column_config.NumberColumn("Amount", format="$%.2f")
                    }
                )
                
                # Download filtered data
                csv_filtered = filtered_df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="Download Filtered Data (CSV)",
                    data=csv_filtered,
                    file_name=f"expenses_filtered_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        
        # ==============================
        # DELETE RECORD
        # ==============================
        with st.expander("Delete Expense Record"):
            st.warning("This action cannot be undone")
            
            if not df.empty:
                # Create a clean list of records for deletion
                df_for_delete = df.sort_values("date", ascending=False).reset_index(drop=True)
                
                # Create display options with unique IDs
                record_options = []
                record_indices = []
                
                for idx, row in df_for_delete.iterrows():
                    date_str = pd.to_datetime(row["date"]).strftime("%Y-%m-%d %H:%M")
                    desc = str(row["description"])[:25] + "..." if len(str(row["description"])) > 25 else str(row["description"])
                    display_text = f"{date_str} | {row['category']} | {desc} | ${row['amount']:.2f}"
                    record_options.append(display_text)
                    record_indices.append(idx)
                
                st.markdown("### Select Record to Delete")
                
                selected_display = st.selectbox(
                    "Choose a record to delete", 
                    record_options, 
                    key="delete_select_expense"
                )
                
                if selected_display:
                    selected_idx = record_options.index(selected_display)
                    actual_row = df_for_delete.iloc[selected_idx]
                    
                    # Show record details
                    st.info(f"""
                    **Record to delete:**
                    - **Date:** {pd.to_datetime(actual_row['date']).strftime('%Y-%m-%d %H:%M')}
                    - **Category:** {actual_row['category']}
                    - **Description:** {actual_row['description']}
                    - **Amount:** ${actual_row['amount']:.2f}
                    - **Vendor:** {actual_row.get('vendor', 'N/A')}
                    - **Payment Method:** {actual_row.get('payment_method', 'N/A')}
                    """)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("Confirm Delete", type="secondary", use_container_width=True, key="confirm_delete_expense"):
                            # Try both methods to ensure deletion
                            success = delete_expense_by_id(
                                date_str=actual_row["date"],
                                category=actual_row["category"],
                                amount=actual_row["amount"],
                                description=actual_row.get("description", ""),
                                expense_type=actual_row.get("expense_type", ""),
                                vendor=actual_row.get("vendor", "")
                            )
                            
                            # If first method fails, try by index
                            if not success:
                                success = delete_expense(actual_row.name)
                            
                            if success:
                                st.session_state.delete_success = True
                                st.session_state.delete_message = "Expense record deleted successfully!"
                                st.success("Expense record deleted successfully!")
                                st.rerun()
                            else:
                                st.error("Failed to delete record. Please refresh and try again.")
                    
                    with col2:
                        if st.button("Cancel", use_container_width=True, key="cancel_delete_expense"):
                            st.info("Deletion cancelled")
        
        # ==============================
        # EXPORT ALL DATA
        # ==============================
        st.markdown("---")
        col1, col2 = st.columns(2)
        
        with col1:
            # Export all data
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="Download All Expenses (CSV)",
                data=csv,
                file_name=f"expenses_all_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True,
                key="download_expenses_csv"
            )
        
        with col2:
            # Export summary by category
            if not df.empty:
                summary = df.groupby("category")["amount"].agg(["sum", "count", "mean"]).reset_index()
                summary.columns = ["Category", "Total", "Count", "Average"]
                summary["Total"] = summary["Total"].round(2)
                summary["Average"] = summary["Average"].round(2)
                summary = summary.sort_values("Total", ascending=False)
                
                csv_summary = summary.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="Download Summary by Category (CSV)",
                    data=csv_summary,
                    file_name=f"expenses_summary_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
    else:
        st.info("No expenses recorded yet. Use the form above to add your first expense.")
        
        # Show help
        with st.expander("How to record your first expense"):
            st.write("""
            1. Fill in the expense details in the form above
            2. Select the appropriate category or add a new one
            3. Enter the amount and description
            4. Click 'Record Expense' to save
            
            Tips:
            - Use clear descriptions for easy tracking
            - Select the correct category for better reporting
            - Add vendor details for future reference
            """)
    
    # ==============================
    # QUICK STATS
    # ==============================
    if not df.empty:
        st.markdown("---")
        st.subheader("Quick Stats")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            # Total number of expenses
            st.metric("Total Records", len(df))
        
        with col2:
            # Most common category
            top_category = df["category"].value_counts().index[0] if not df.empty else "N/A"
            st.metric("Top Category", top_category)
        
        with col3:
            # Largest expense
            largest = df["amount"].max() if not df.empty else 0
            st.metric("Largest Expense", f"${largest:.2f}")
        
        with col4:
            # Total spent
            total = df["amount"].sum() if not df.empty else 0
            st.metric("Total Spent", f"${total:,.2f}")


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    expenses_page()