import streamlit as st
import pandas as pd
from datetime import datetime

from backend.analytics.debtors_engine import (
    load_debtors,
    get_overdue_debtors,
    update_risk_levels,
    get_credit_score,
    get_debt_aging,
    get_debt_items,
    get_aging_summary,
    get_recoverable_debt
)


def debtors_dashboard():
    """Debtors Analytics Dashboard"""
    
    st.title("Debtors Intelligence Dashboard")
    st.caption("Analytics and insights for credit management")
    
    # Update risk levels on load
    update_risk_levels()
    df = load_debtors()
    
    if df.empty:
        st.warning("No debtor data available. Add debt records first.")
        return
    
    # ==============================
    # KEY METRICS
    # ==============================
    st.subheader("Key Metrics")
    
    total_outstanding = df["balance"].sum()
    total_principal = df["total_amount"].sum()
    collection_rate = ((total_principal - total_outstanding) / total_principal * 100) if total_principal > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Outstanding Debt", f"${total_outstanding:,.2f}")
    with col2:
        st.metric("Total Principal", f"${total_principal:,.2f}")
    with col3:
        st.metric("Collection Rate", f"{collection_rate:.1f}%")
    with col4:
        st.metric("Active Debtors", len(df[df["balance"] > 0]))
    
    st.markdown("---")
    
    # ==============================
    # RISK BREAKDOWN
    # ==============================
    st.subheader("Risk Level Breakdown")
    
    if "risk_level" in df.columns:
        risk_counts = df["risk_level"].value_counts().reset_index()
        risk_counts.columns = ["Risk Level", "Count"]
        
        # Order risk levels
        risk_order = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "NONE"]
        risk_counts["Risk Level"] = pd.Categorical(risk_counts["Risk Level"], categories=risk_order, ordered=True)
        risk_counts = risk_counts.sort_values("Risk Level")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.dataframe(risk_counts, use_container_width=True, hide_index=True)
        
        with col2:
            # Critical risks
            critical = df[df["risk_level"] == "CRITICAL"]
            if not critical.empty:
                st.error(f"{len(critical)} CRITICAL risk debtors need immediate attention!")
                st.dataframe(critical[["customer_name", "balance", "expected_repayment_date"]], use_container_width=True, hide_index=True)
            else:
                st.success("No CRITICAL risk debtors")
    else:
        st.info("No risk level data available")
    
    st.markdown("---")
    
    # ==============================
    # CREDIT SCORES
    # ==============================
    st.subheader("Credit Scores")
    
    credit_scores = get_credit_score()
    if not credit_scores.empty and "credit_score" in credit_scores.columns:
        # Show low credit scores first (highest risk)
        st.caption("Customers with lowest credit scores (highest risk) appear first")
        st.dataframe(
            credit_scores[["customer_name", "credit_score", "balance", "risk_level"]].head(20),
            use_container_width=True,
            hide_index=True,
            column_config={
                "credit_score": st.column_config.ProgressColumn("Credit Score", min_value=0, max_value=100)
            }
        )
    else:
        st.info("No credit score data available")
    
    st.markdown("---")
    
    # ==============================
    # DEBT AGING
    # ==============================
    st.subheader("Debt Aging Report")
    
    aging_df = get_debt_aging()
    if not aging_df.empty and "aging_bucket" in aging_df.columns:
        aging_summary = aging_df.groupby("aging_bucket").agg({
            "balance": "sum",
            "customer_name": "count"
        }).reset_index()
        aging_summary.columns = ["Aging Bucket", "Total Balance", "Number of Customers"]
        
        st.dataframe(aging_summary, use_container_width=True, hide_index=True)
        
        # Recovery analysis
        st.markdown("---")
        st.subheader("Recovery Analysis")
        
        recoverable = get_recoverable_debt()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Outstanding", f"${recoverable.get('total_outstanding', 0):,.2f}")
        with col2:
            st.metric("Expected Recovery", f"${recoverable.get('expected_recovery', 0):,.2f}")
        with col3:
            st.metric("Recovery Rate", f"{recoverable.get('recovery_rate', 0):.1f}%")
        
        if recoverable.get('expected_loss', 0) > 0:
            st.warning(f"Estimated Bad Debt Risk: ${recoverable['expected_loss']:,.2f}")
    else:
        st.info("No aging data available")
    
    st.markdown("---")
    
    # ==============================
    # OVERDUE DEBTORS
    # ==============================
    st.subheader("Overdue Debtors")
    
    overdue = get_overdue_debtors()
    if not overdue.empty:
        st.warning(f"{len(overdue)} customers with overdue payments")
        st.dataframe(
            overdue[["customer_name", "balance", "expected_repayment_date", "risk_level", "days_overdue"]],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.success("No overdue payments")
    
    st.markdown("---")
    
    # ==============================
    # CUSTOMER DEBT DETAILS
    # ==============================
    st.subheader("Customer Debt Details")
    
    if not df.empty:
        selected_customer = st.selectbox("Select Customer", df["customer_name"].tolist())
        
        if selected_customer:
            customer_debts = df[df["customer_name"] == selected_customer]
            
            # Display customer summary
            total_borrowed = customer_debts["total_amount"].sum()
            total_paid = customer_debts["amount_paid"].sum()
            outstanding = customer_debts["balance"].sum()
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Borrowed", f"${total_borrowed:.2f}")
            col2.metric("Total Paid", f"${total_paid:.2f}")
            col3.metric("Outstanding", f"${outstanding:.2f}")
            
            # Show each debt with its items
            for _, debt in customer_debts.iterrows():
                with st.expander(f"Debt ID: {debt['debt_id']} | Date: {debt['date_borrowed'][:10] if isinstance(debt['date_borrowed'], str) else str(debt['date_borrowed'])[:10]} | Balance: ${debt['balance']:.2f}"):
                    st.write(f"**Expected Repayment:** {debt['expected_repayment_date']}")
                    st.write(f"**Status:** {debt['status']}")
                    st.write(f"**Risk Level:** {debt['risk_level']}")
                    
                    # Get items for this debt
                    items = get_debt_items(debt['debt_id'])
                    if not items.empty:
                        st.write("**Items Taken:**")
                        st.dataframe(items[["product_name", "quantity", "unit_price", "total_price"]], use_container_width=True, hide_index=True)
    
    st.markdown("---")
    
    # ==============================
    # EXPORT DATA
    # ==============================
    st.subheader("Export Data")
    
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download Debtors Report (CSV)",
        data=csv,
        file_name=f"debtors_report_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
        use_container_width=True
    )


# ==============================
# MAIN GUARD
# ==============================
if __name__ == "__main__":
    debtors_dashboard()