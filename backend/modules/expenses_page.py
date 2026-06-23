import streamlit as st
import pandas as pd
from backend.modules.expenses import record_expense, load_expenses, get_monthly_expenses, load_expense_categories


def expenses_page():
    """Expenses Management Page"""
    
    st.title("💸 Business Expenses")
    st.caption("Record and track all business expenses")
    
    # ==============================
    # INPUT FORM
    # ==============================
    st.subheader("➕ Record Expense")
    
    # Load categories
    categories = load_expense_categories()
    
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
        # Ensure amount is a number
        amount_input = st.number_input(
            "Amount ($) *",
            min_value=0.01,
            step=10.0,
            format="%.2f",
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
    
    # Get username safely
    username = st.session_state.get("username", "System")
    if username == "admin" or not username:
        username = "System"
    
    if st.button("💰 Record Expense", type="primary", use_container_width=True):
        if description and amount_input > 0:
            try:
                record_expense(
                    expense_type=expense_type,
                    category=category,
                    description=description,
                    amount=float(amount_input),  # Ensure it's float
                    vendor=vendor,
                    payment_method=payment_method,
                    user=username,
                    notes=notes
                )
                st.balloons()
                st.success(f"✅ Expense recorded: ${amount_input:.2f} - {description}")
                st.rerun()
            except Exception as e:
                st.error(f"Error recording expense: {str(e)}")
        else:
            st.error("Please enter description and amount")

    # ==============================
    # SUMMARY
    # ==============================
    st.markdown("---")
    st.subheader("📊 Monthly Summary")
    
    monthly_total = get_monthly_expenses()
    st.metric("This Month Expenses", f"${monthly_total:.2f}")
    
    # ==============================
    # RECENT EXPENSES TABLE
    # ==============================
    st.markdown("---")
    st.subheader("📋 Recent Expenses")
    
    df = load_expenses()
    
    if not df.empty:
        # Convert amount to numeric for display
        if "amount" in df.columns:
            # Ensure amount is numeric, handle errors
            df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
        
        # Sort by date
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df = df.sort_values("date", ascending=False)
        
        # Display
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Total
        total_expenses = df["amount"].sum() if "amount" in df.columns else 0
        st.info(f"💰 Total Expenses (All Time): ${total_expenses:,.2f}")
        
        # Download button
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download Expenses CSV",
            data=csv,
            file_name="expenses_data.csv",
            mime="text/csv"
        )
    else:
        st.info("No expenses recorded yet.")