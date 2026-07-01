# backend/modules/income_page.py
import streamlit as st
from backend.modules.income import record_income, load_income, get_monthly_income, get_income_by_source, delete_income
import pandas as pd


def income_page():
    """Income Management Page - FIXED: No infinite loop"""
    
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
                ]
            )

            description = st.text_input("Description *", placeholder="Brief description of income")
        
        with col2:
            amount = st.number_input("Amount ($) *", min_value=0.01, step=10.0, value=0.0)
            user = st.text_input("Recorded By", value=st.session_state.get("username", "System"), disabled=True)
        
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
                    st.session_state.income_recorded = True
                    st.session_state.income_message = message
                    st.session_state.income_success = True
                    st.success(f"✅ {message}")
                    st.balloons()
                    # DO NOT call st.rerun() - let the form handle it naturally
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
    
    # Get income by source for additional metrics
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
        
        # Bar chart
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
    # TABLE
    # ==============================
    st.markdown("---")
    st.subheader("📜 Income Records")
    
    df = load_income()

    if not df.empty:
        # Sort by date descending
        df_display = df.sort_values("date", ascending=False).copy()
        
        # Format date for display
        df_display["date"] = pd.to_datetime(df_display["date"]).dt.strftime("%Y-%m-%d %H:%M")
        
        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "amount": st.column_config.NumberColumn("Amount", format="$%.2f")
            }
        )
        
        # Delete record option
        with st.expander("🗑️ Delete Income Record"):
            st.warning("⚠️ This action cannot be undone")
            
            # Create a list of records to select from
            record_options = []
            for idx, row in df_display.iterrows():
                record_options.append(f"{row['date']} - {row['income_source']} - ${row['amount']:.2f}")
            
            if record_options:
                selected_record = st.selectbox("Select Record to Delete", record_options)
                
                if st.button("🗑️ Delete Selected Record", type="secondary", use_container_width=True):
                    # Find the index of the selected record
                    selected_idx = record_options.index(selected_record)
                    # Get the actual index from df
                    actual_idx = df_display.index[selected_idx]
                    
                    if delete_income(actual_idx):
                        st.success("✅ Record deleted successfully!")
                        st.rerun()
                    else:
                        st.error("❌ Failed to delete record")
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