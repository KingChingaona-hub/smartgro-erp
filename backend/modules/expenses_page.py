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
    delete_expense
)


def expenses_page():
    """Expenses Management Page - FIXED: No infinite loop"""
    
    st.title("💸 Business Expenses")
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

    # ==============================
    # DISPLAY MESSAGES FROM SESSION STATE
    # ==============================
    if st.session_state.expense_success and st.session_state.expense_message:
        st.success(f"✅ {st.session_state.expense_message}")
        st.balloons()
        st.session_state.expense_success = False
        st.session_state.expense_message = ""

    # ==============================
    # INPUT FORM
    # ==============================
    st.subheader("➕ Record Expense")
    
    categories = load_expense_categories()
    
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
        
        submitted = st.form_submit_button("💰 Record Expense", type="primary", use_container_width=True)

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
                    st.success(f"✅ {message}")
                    st.balloons()
                else:
                    st.error(f"❌ Failed to record expense: {message}")
            else:
                st.error("Please enter description and amount")

    # ==============================
    # SUMMARY
    # ==============================
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    monthly_total = get_monthly_expenses()
    
    with col1:
        st.metric("💰 This Month Expenses", f"${monthly_total:.2f}")
    
    df = load_expenses()
    if not df.empty:
        total_all = df["amount"].sum()
        with col2:
            st.metric("📊 Total All Time", f"${total_all:,.2f}")
    
    # ==============================
    # TABLE & DELETE
    # ==============================
    st.markdown("---")
    st.subheader("📋 Expenses Records")
    
    if not df.empty:
        # Create display version
        df_display = df.copy()
        df_display["date_display"] = pd.to_datetime(df_display["date"]).dt.strftime("%Y-%m-%d %H:%M")
        df_sorted = df_display.sort_values("date", ascending=False)
        
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
        # DELETE RECORD
        # ==============================
        with st.expander("🗑️ Delete Expense Record"):
            st.warning("⚠️ This action cannot be undone")
            
            if not df.empty:
                record_options = []
                record_data = []
                
                df_sorted_for_select = df.sort_values("date", ascending=False)
                
                for idx, row in df_sorted_for_select.iterrows():
                    date_str = pd.to_datetime(row["date"]).strftime("%Y-%m-%d %H:%M")
                    display_text = f"{date_str} - {row['category']} - ${row['amount']:.2f}"
                    record_options.append(display_text)
                    
                    record_data.append({
                        "date": row["date"],
                        "category": row["category"],
                        "amount": row["amount"],
                        "description": row.get("description", "")
                    })
                
                selected_record = st.selectbox(
                    "Select Record to Delete", 
                    record_options, 
                    key="delete_select"
                )
                
                if selected_record:
                    selected_idx = record_options.index(selected_record)
                    record_to_delete = record_data[selected_idx]
                    
                    st.info(f"⚠️ You are about to delete: {selected_record}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("🗑️ Confirm Delete", type="secondary", use_container_width=True):
                            success = delete_expense_by_id(
                                date_str=record_to_delete["date"],
                                category=record_to_delete["category"],
                                amount=record_to_delete["amount"],
                                description=record_to_delete["description"]
                            )
                            
                            if success:
                                st.success("✅ Expense record deleted successfully!")
                                st.rerun()
                            else:
                                st.error("❌ Failed to delete record. Please try again.")
                    
                    with col2:
                        if st.button("❌ Cancel", use_container_width=True):
                            st.info("Deletion cancelled")
        
        # Export
        st.markdown("---")
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download Expenses CSV",
            data=csv,
            file_name=f"expenses_data_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    else:
        st.info("No expenses recorded yet.")


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    expenses_page()