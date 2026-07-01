# backend/modules/income_page.py
import streamlit as st
from backend.modules.income import record_income, load_income, get_monthly_income, get_income_by_source, delete_income, delete_income_by_id
import pandas as pd
from datetime import datetime


def income_page():
    """Income Management Page - FIXED: Proper delete using unique identifiers"""
    
    st.title("💰 Business Income")
    st.caption("Record and track all business income")

    # ==============================
    # SESSION STATE INIT
    # ==============================
    if "income_recorded" not in st.session_state:
        st.session_state.income_recorded = False
    if "income_message" not in st.session_state:
        st.session_state.income_message = ""
    if "income_success" not in st.session_state:
        st.session_state.income_success = False

    # ==============================
    # DISPLAY MESSAGES FROM SESSION STATE
    # ==============================
    if st.session_state.income_success and st.session_state.income_message:
        st.success(f"✅ {st.session_state.income_message}")
        st.balloons()
        st.session_state.income_success = False
        st.session_state.income_message = ""

    # ==============================
    # INPUT FORM
    # ==============================
    st.subheader("➕ Record Income")

    with st.form(key="income_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            income_source = st.selectbox(
                "Income Source *",
                [
                    "Sales Adjustment",
                    "Delivery Fees",
                    "Service Income",
                    "Commission",
                    "Asset Sale",
                    "Interest Income",
                    "Rental Income",
                    "Other"
                ],
                key="income_source_select"
            )

            description = st.text_input(
                "Description *", 
                placeholder="Brief description of income",
                key="income_description"
            )
        
        with col2:
            amount = st.number_input(
                "Amount ($) *", 
                min_value=0.01, 
                step=10.0, 
                value=0.01,
                key="income_amount"
            )
            user = st.text_input(
                "Recorded By", 
                value=st.session_state.get("username", "System"), 
                disabled=True,
                key="income_user"
            )
        
        submitted = st.form_submit_button("💰 Record Income", type="primary", use_container_width=True)

        if submitted:
            if amount <= 0:
                st.error("❌ Please enter a valid amount greater than 0")
            elif not description:
                st.error("❌ Please enter a description")
            else:
                success, message = record_income(
                    income_source,
                    description,
                    amount,
                    st.session_state.get("username", "System")
                )
                if success:
                    st.session_state.income_success = True
                    st.session_state.income_message = message
                    st.success(f"✅ {message}")
                    st.balloons()
                else:
                    st.error(f"❌ Failed to record income: {message}")

    # ==============================
    # SUMMARY
    # ==============================
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    
    monthly_total = get_monthly_income()
    
    with col1:
        st.metric("💰 This Month Income", f"${monthly_total:.2f}")
    
    source_df = get_income_by_source()
    if not source_df.empty:
        with col2:
            top_source = source_df.iloc[0]["income_source"]
            top_amount = source_df.iloc[0]["amount"]
            st.metric("🏆 Top Source", f"{top_source}", delta=f"${top_amount:.2f}")
        
        with col3:
            st.metric("📊 Total Sources", len(source_df))
    
    st.markdown("---")
    
    # ==============================
    # INCOME BY SOURCE CHART
    # ==============================
    if not source_df.empty:
        st.subheader("📊 Income by Source")
        
        import plotly.express as px
        
        fig = px.pie(
            source_df,
            values="amount",
            names="income_source",
            title="Income Distribution by Source",
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Set2
        )
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)
        
        fig_bar = px.bar(
            source_df,
            x="income_source",
            y="amount",
            title="Income by Source",
            color="amount",
            color_continuous_scale="Greens",
            text="amount"
        )
        fig_bar.update_traces(texttemplate="$%{text:.2f}", textposition="outside")
        fig_bar.update_layout(height=350)
        st.plotly_chart(fig_bar, use_container_width=True)

    # ==============================
    # TABLE & DELETE - FIXED
    # ==============================
    st.markdown("---")
    st.subheader("📜 Income Records")
    
    df = load_income()

    if not df.empty:
        # Create display version
        df_display = df.copy()
        df_display["date_display"] = pd.to_datetime(df_display["date"]).dt.strftime("%Y-%m-%d %H:%M")
        df_sorted = df_display.sort_values("date", ascending=False)
        
        st.dataframe(
            df_sorted[["date_display", "income_source", "description", "amount", "user"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "date_display": "Date",
                "amount": st.column_config.NumberColumn("Amount", format="$%.2f")
            }
        )
        
        # ==============================
        # DELETE RECORD - FIXED: Use delete_income_by_id
        # ==============================
        with st.expander("🗑️ Delete Income Record"):
            st.warning("⚠️ This action cannot be undone")
            
            if not df.empty:
                # Create a list of records to select from with unique identifiers
                record_options = []
                record_data = []  # Store the actual data for deletion
                
                df_sorted_for_select = df.sort_values("date", ascending=False)
                
                for idx, row in df_sorted_for_select.iterrows():
                    date_str = pd.to_datetime(row["date"]).strftime("%Y-%m-%d %H:%M")
                    display_text = f"{date_str} - {row['income_source']} - ${row['amount']:.2f}"
                    record_options.append(display_text)
                    
                    # Store the unique identifier data
                    record_data.append({
                        "date": row["date"],
                        "income_source": row["income_source"],
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
                    
                    # Show what will be deleted
                    st.info(f"⚠️ You are about to delete: {selected_record}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("🗑️ Confirm Delete", type="secondary", use_container_width=True):
                            # Use the safer delete_by_id method
                            success = delete_income_by_id(
                                date_str=record_to_delete["date"],
                                income_source=record_to_delete["income_source"],
                                amount=record_to_delete["amount"],
                                description=record_to_delete["description"]
                            )
                            
                            if success:
                                st.success("✅ Income record deleted successfully!")
                                st.rerun()
                            else:
                                st.error("❌ Failed to delete record. Please try again.")
                    
                    with col2:
                        if st.button("❌ Cancel", use_container_width=True):
                            st.info("Deletion cancelled")
    else:
        st.info("No income recorded yet.")
    
    # ==============================
    # EXPORT
    # ==============================
    if not df.empty:
        st.markdown("---")
        st.subheader("📥 Export Data")
        
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download Income Data (CSV)",
            data=csv,
            file_name=f"income_data_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    income_page()