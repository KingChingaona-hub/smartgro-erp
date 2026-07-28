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
    add_expense_category
)


def expenses_page():
    """Expenses Management Page - FIXED: No infinite loops, proper category management"""
    
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
                ["CASH", "BANK TRANSFER", "CARD", "ECOCASH"],
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
                else:
                    st.error(f"Failed to record expense: {message}")
            else:
                st.error("Please enter description and amount")

    # ==============================
    # ADD NEW CATEGORY - FIXED
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
                            # Use rerun to refresh the page
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
    
    col1, col2 = st.columns(2)
    
    monthly_total = get_monthly_expenses()
    
    with col1:
        st.metric("This Month Expenses", f"${monthly_total:.2f}")
    
    df = load_expenses()
    if not df.empty:
        total_all = df["amount"].sum()
        with col2:
            st.metric("Total All Time", f"${total_all:,.2f}")
    
    # ==============================
    # TABLE & DELETE - FIXED
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
        
        st.dataframe(
            df_sorted[["date_display", "category", "description", "amount", "vendor", "payment_method"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "date_display": "Date",
                "amount": st.column_config.NumberColumn("Amount", format="$%.2f")
            }
        )
        
        # ==============================
        # DELETE RECORD - IMPROVED with unique key per record
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
                    display_text = f"{date_str} - {row['category']} - {row['description'][:25]}... - ${row['amount']:.2f}"
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
        
        # Export
        st.markdown("---")
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download Expenses CSV",
            data=csv,
            file_name=f"expenses_data_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True,
            key="download_expenses_csv"
        )
    else:
        st.info("No expenses recorded yet. Use the form above to add your first expense.")


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    expenses_page()