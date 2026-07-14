import streamlit as st
import pandas as pd
from datetime import datetime

from backend.analytics.debtors_engine import (
    get_credit_score, 
    get_blocked_customers, 
    get_debt_aging,
    load_debtors,
    get_aging_summary,
    get_recoverable_debt
)
from backend.analytics.debt_notifications import get_overdue_messages


def debt_intelligence_dashboard():
    """Credit Intelligence Dashboard - Complete View"""
    
    st.title("Credit Intelligence System")
    st.caption("AI-powered credit risk analysis and debt management")
    
    # Load data
    df = load_debtors()
    
    if df.empty:
        st.warning("No debt data available. Start by creating debt records.")
        return
    
    # ==============================
    # KEY METRICS
    # ==============================
    st.subheader("Credit Overview")
    
    total_outstanding = df["balance"].sum()
    total_debtors = len(df[df["balance"] > 0])
    avg_debt = total_outstanding / total_debtors if total_debtors > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Outstanding", f"${total_outstanding:,.2f}")
    with col2:
        st.metric("Active Debtors", total_debtors)
    with col3:
        st.metric("Avg Debt per Customer", f"${avg_debt:.2f}")
    with col4:
        aging_summary = get_aging_summary()
        overdue_90 = aging_summary.get("days_90_plus", 0)
        st.metric("90+ Days Overdue", f"${overdue_90:,.2f}")
    
    st.markdown("---")
    
    # ==============================
    # CREDIT SCORES
    # ==============================
    st.subheader("Credit Scores")
    
    credit_scores = get_credit_score()
    if not credit_scores.empty:
        # Show low credit scores first (highest risk)
        st.warning("Customers with low credit scores need attention")
        st.dataframe(
            credit_scores[["customer_name", "phone", "credit_score", "balance", "risk_level"]].head(20),
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
    # BLOCKED CUSTOMERS
    # ==============================
    st.subheader("Blocked Customers")
    
    blocked = get_blocked_customers(threshold=30)
    if not blocked.empty:
        st.error(f"{len(blocked)} customers are BLOCKED due to poor credit")
        st.dataframe(
            blocked[["customer_name", "phone", "credit_score", "balance", "risk_level"]],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.success("No blocked customers")
    
    st.markdown("---")
    
    # ==============================
    # DEBT AGING REPORT
    # ==============================
    st.subheader("Debt Aging Report")
    
    aging_df = get_debt_aging()
    if not aging_df.empty:
        # Summary by aging bucket
        aging_summary = aging_df.groupby("aging_bucket").agg({
            "balance": "sum",
            "customer_name": "count"
        }).reset_index()
        aging_summary.columns = ["Aging Bucket", "Total Balance", "Number of Customers"]
        
        st.dataframe(aging_summary, use_container_width=True, hide_index=True)
        
        # Recovery analysis
        recoverable = get_recoverable_debt()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Expected Recovery", f"${recoverable.get('expected_recovery', 0):,.2f}")
        with col2:
            st.metric("Expected Loss", f"${recoverable.get('expected_loss', 0):,.2f}")
        with col3:
            st.metric("Recovery Rate", f"{recoverable.get('recovery_rate', 0):.1f}%")
    else:
        st.info("No aging data available")
    
    st.markdown("---")
    
    # ==============================
    # OVERDUE NOTIFICATIONS
    # ==============================
    st.subheader("Overdue Notifications")
    
    messages = get_overdue_messages()
    
    if not messages.empty:
        st.warning(f"{len(messages)} overdue customers need attention")
        
        # Group by severity
        severity_colors = {
            "Gentle Reminder": "🟢",
            "Follow Up": "🟡",
            "URGENT": "🟠",
            "FINAL NOTICE": "🔴"
        }
        
        for _, msg in messages.iterrows():
            emoji = severity_colors.get(msg['severity'], "📢")
            st.info(f"{emoji} **{msg['customer']}** - {msg['severity']} - ${msg['balance']} - {msg['days_overdue']} days overdue")
        
        # Export messages
        csv = messages.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download Overdue Messages (CSV)",
            data=csv,
            file_name=f"overdue_messages_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    else:
        st.success("No overdue customers")
    
    st.markdown("---")
    
    # ==============================
    # RISK DISTRIBUTION CHART
    # ==============================
    st.subheader("Risk Distribution")
    
    if not df.empty and "risk_level" in df.columns:
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
                st.error(f"🚨 {len(critical)} CRITICAL risk debtors!")
                st.dataframe(critical[["customer_name", "balance"]], use_container_width=True, hide_index=True)
    
    st.markdown("---")
    
    # ==============================
    # EXPORT FULL REPORT
    # ==============================
    st.subheader("Export Credit Report")
    
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇ Download Full Credit Report (CSV)",
        data=csv,
        file_name=f"credit_report_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
        use_container_width=True
    )


# ==============================
# MAIN GUARD
# ==============================
if __name__ == "__main__":
    debt_intelligence_dashboard()