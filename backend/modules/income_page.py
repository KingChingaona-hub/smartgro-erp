# backend/modules/income_page.py
import streamlit as st
from backend.modules.income import record_income, load_income, get_monthly_income, get_income_by_source, delete_income
import pandas as pd
from datetime import datetime


def income_page():
    """Income Management Page - FIXED: No infinite loops"""
    
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
        # Clear the message after displaying
        st.session_state.income_success = False
        st.session_state.income_message = ""
    
    # ==============================
    # INPUT FORM - NO st.rerun() inside
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
                    # Store in session state instead of calling st.rerun()
                    st.session_state.income_success = True
                    st.session_state.income_message = message
                    st.success(f"✅ {message}")
                    st.balloons()
                    # NO st.rerun() here - let the form naturally clear
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
    # TABLE
    # ==============================
    st.markdown("---")
    st.subheader("📜 Income Records")
    
    df = load_income()

    if not df.empty:
        df_display = df.sort_values("date", ascending=False).copy()
        df_display["date"] = pd.to_datetime(df_display["date"]).dt.strftime("%Y-%m-%d %H:%M")
        
        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "amount": st.column_config.NumberColumn("Amount", format="$%.2f")
            }
        )
        
        # ==============================
        # DELETE RECORD
        # ==============================
        with st.expander("🗑️ Delete Income Record"):
            st.warning("⚠️ This action cannot be undone")
            
            # Create a list of records to select from
            record_options = []
            record_indices = []
            for idx, row in df_display.iterrows():
                record_options.append(f"{row['date']} - {row['income_source']} - ${row['amount']:.2f}")
                record_indices.append(idx)
            
            if record_options:
                selected_record = st.selectbox(
                    "Select Record to Delete", 
                    record_options, 
                    key="delete_select"
                )
                
                selected_idx = record_options.index(selected_record) if selected_record else -1
                
                if st.button("🗑️ Delete Selected Record", type="secondary", use_container_width=True):
                    if selected_idx >= 0:
                        actual_idx = record_indices[selected_idx]
                        success = delete_income(actual_idx)
                        
                        if success:
                            st.success("✅ Income record deleted successfully!")
                            # Use rerun here - it's safe because it's not inside a form
                            st.rerun()
                        else:
                            st.error("❌ Failed to delete record")
                    else:
                        st.warning("Please select a record to delete")
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