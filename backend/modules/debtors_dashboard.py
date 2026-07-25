import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

from backend.analytics.debtors_engine import (
    load_debtors,
    get_overdue_debtors,
    update_risk_levels,
    get_credit_score,
    get_debt_aging,
    get_debt_items,
    get_aging_summary,
    get_recoverable_debt,
    get_customer_debt_summary
)


def debtors_dashboard():
    """Debtors Intelligence Dashboard"""
    
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
    total_paid = df["amount_paid"].sum()
    collection_rate = ((total_principal - total_outstanding) / total_principal * 100) if total_principal > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Outstanding Debt", f"${total_outstanding:,.2f}")
    with col2:
        st.metric("Total Principal", f"${total_principal:,.2f}")
    with col3:
        st.metric("Collection Rate", f"{collection_rate:.1f}%")
    with col4:
        active_debtors = len(df[df["balance"] > 0])
        st.metric("Active Debtors", active_debtors)
    
    st.markdown("---")
    
    # ==============================
    # PAYMENT STATUS BREAKDOWN
    # ==============================
    st.subheader("Payment Status Breakdown")
    
    if "status" in df.columns:
        status_counts = df["status"].value_counts().reset_index()
        status_counts.columns = ["Status", "Count"]
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.dataframe(status_counts, use_container_width=True, hide_index=True)
        
        with col2:
            # Show fully paid vs partially paid
            fully_paid = len(df[df["status"] == "PAID"])
            partially_paid = len(df[df["status"] == "NOT PAID"])
            total_debts = len(df)
            
            st.metric("Fully Paid Debts", fully_paid, delta=f"{fully_paid/total_debts*100:.1f}%" if total_debts > 0 else "0%")
            st.metric("Partially Paid/Active", partially_paid, delta=f"{partially_paid/total_debts*100:.1f}%" if total_debts > 0 else "0%")
    
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
                st.dataframe(critical[["customer_name", "balance", "expected_repayment_date"]], 
                           use_container_width=True, hide_index=True)
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
        
        # Add color coding for credit scores
        def color_score(val):
            if val <= 30:
                return '🔴'
            elif val <= 50:
                return '🟠'
            elif val <= 70:
                return '🟡'
            else:
                return '🟢'
        
        display_df = credit_scores[["customer_name", "credit_score", "balance", "risk_level"]].head(20).copy()
        display_df["Score"] = display_df["credit_score"].apply(color_score)
        display_df = display_df[["customer_name", "Score", "credit_score", "balance", "risk_level"]]
        
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "credit_score": st.column_config.ProgressColumn("Credit Score", min_value=0, max_value=100),
                "Score": st.column_config.TextColumn("Status")
            }
        )
    else:
        st.info("No credit score data available")
    
    st.markdown("---")
    
    # ==============================
    # DEBT AGING
    # ==============================
    st.subheader("Debt Aging Report")
    
    aging_summary = get_aging_summary()
    
    if aging_summary:
        aging_data = pd.DataFrame([
            {"Bucket": "Current", "Amount": aging_summary.get("current", 0)},
            {"Bucket": "1-30 Days", "Amount": aging_summary.get("days_1_30", 0)},
            {"Bucket": "31-60 Days", "Amount": aging_summary.get("days_31_60", 0)},
            {"Bucket": "61-90 Days", "Amount": aging_summary.get("days_61_90", 0)},
            {"Bucket": "90+ Days", "Amount": aging_summary.get("days_90_plus", 0)}
        ])
        
        aging_data["Percentage"] = (aging_data["Amount"] / aging_data["Amount"].sum() * 100).fillna(0)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.dataframe(aging_data, use_container_width=True, hide_index=True)
        
        with col2:
            # Show aging chart as text-based bar chart
            max_amount = aging_data["Amount"].max()
            if max_amount > 0:
                for _, row in aging_data.iterrows():
                    bar_length = int((row["Amount"] / max_amount) * 30)
                    bar = "█" * bar_length
                    st.write(f"{row['Bucket']}: {bar} ${row['Amount']:,.2f} ({row['Percentage']:.1f}%)")
    
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
        recovery_rate = recoverable.get('recovery_rate', 0)
        st.metric("Recovery Rate", f"{recovery_rate:.1f}%")
    
    if recoverable.get('expected_loss', 0) > 0:
        st.warning(f"Estimated Bad Debt Risk: ${recoverable['expected_loss']:,.2f}")
    else:
        st.success("No expected bad debt losses")
    
    st.markdown("---")
    
    # ==============================
    # OVERDUE DEBTORS
    # ==============================
    st.subheader("Overdue Debtors")
    
    overdue = get_overdue_debtors()
    if not overdue.empty:
        st.warning(f"⚠️ {len(overdue)} customers with overdue payments")
        
        # Show urgency based on days overdue
        def get_urgency(days):
            if days >= 90:
                return "🔴 CRITICAL"
            elif days >= 60:
                return "🟠 HIGH"
            elif days >= 30:
                return "🟡 MEDIUM"
            else:
                return "🟢 LOW"
        
        overdue_display = overdue.copy()
        overdue_display["Urgency"] = overdue_display["days_overdue"].apply(get_urgency)
        
        st.dataframe(
            overdue_display[["customer_name", "balance", "expected_repayment_date", "risk_level", "days_overdue", "Urgency"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "days_overdue": st.column_config.NumberColumn("Days Overdue", format="%d"),
            }
        )
        
        # Show total overdue amount by urgency
        st.markdown("### Overdue Summary by Urgency")
        urgency_summary = overdue_display.groupby("Urgency").agg({
            "balance": "sum",
            "customer_name": "count"
        }).reset_index()
        urgency_summary.columns = ["Urgency", "Total Amount", "Customers"]
        
        st.dataframe(urgency_summary, use_container_width=True, hide_index=True)
        
    else:
        st.success("No overdue payments")
    
    st.markdown("---")
    
    # ==============================
    # CUSTOMER DEBT DETAILS
    # ==============================
    st.subheader("Customer Debt Details")
    st.caption("View detailed debt history including items borrowed and payment status")
    
    if not df.empty:
        # Get unique customers with outstanding balance first
        customers_with_debt = df[df["balance"] > 0]["customer_name"].unique().tolist()
        all_customers = df["customer_name"].unique().tolist()
        
        # Show customers with debt first in the list
        customer_list = customers_with_debt + [c for c in all_customers if c not in customers_with_debt]
        
        selected_customer = st.selectbox("Select Customer", customer_list)
        
        if selected_customer:
            customer_debts = df[df["customer_name"] == selected_customer]
            
            # Display customer summary
            total_borrowed = customer_debts["total_amount"].sum()
            total_paid = customer_debts["amount_paid"].sum()
            outstanding = customer_debts["balance"].sum()
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Borrowed", f"${total_borrowed:.2f}")
            col2.metric("Total Paid", f"${total_paid:.2f}")
            col3.metric("Outstanding", f"${outstanding:.2f}")
            
            # Payment progress
            progress = (total_paid / total_borrowed * 100) if total_borrowed > 0 else 0
            col4.metric("Payment Progress", f"{progress:.1f}%")
            
            st.progress(progress / 100, text=f"Payment Progress: {progress:.1f}%")
            
            # Show each debt with its items
            st.markdown("### Individual Debts")
            
            for _, debt in customer_debts.iterrows():
                debt_id_safe = str(debt['debt_id']).replace("-", "_")
                
                # Determine status color
                if debt['balance'] <= 0:
                    status_icon = "✅"
                    status_color = "green"
                elif debt['status'] == "OVERDUE":
                    status_icon = "🔴"
                    status_color = "red"
                elif debt['status'] == "PARTIAL":
                    status_icon = "🟡"
                    status_color = "orange"
                else:
                    status_icon = "📝"
                    status_color = "blue"
                
                with st.expander(f"{status_icon} Debt ID: {debt['debt_id']} | Balance: ${debt['balance']:.2f} | Status: {debt['status']}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**Date Borrowed:** {debt.get('date_borrowed', 'N/A')}")
                        st.write(f"**Expected Repayment:** {debt.get('expected_repayment_date', 'N/A')}")
                        st.write(f"**Total Amount:** ${debt['total_amount']:.2f}")
                        st.write(f"**Amount Paid:** ${debt['amount_paid']:.2f}")
                    
                    with col2:
                        st.write(f"**Remaining Balance:** ${debt['balance']:.2f}")
                        st.write(f"**Status:** {debt['status']}")
                        st.write(f"**Risk Level:** {debt['risk_level']}")
                        if debt.get('payment_plan') and debt['payment_plan'] != "None":
                            st.write(f"**Payment Plan:** {debt['payment_plan']}")
                            if debt.get('installment_amount'):
                                st.write(f"**Installment:** ${debt['installment_amount']:.2f}")
                    
                    # Get items for this debt
                    items = get_debt_items(debt['debt_id'])
                    if not items.empty:
                        st.write("**Items Taken:**")
                        # Add type column if available
                        if "type" in items.columns:
                            items["Type"] = items["type"].map({"inventory": "📦 Inventory", "non_inventory": "📝 Non-Inventory"})
                            display_cols = ["product_name", "type", "quantity", "unit_price", "total_price"]
                        else:
                            display_cols = ["product_name", "quantity", "unit_price", "total_price"]
                        
                        st.dataframe(
                            items[display_cols], 
                            use_container_width=True, 
                            hide_index=True,
                            column_config={
                                "unit_price": st.column_config.NumberColumn("Unit Price", format="$%.2f"),
                                "total_price": st.column_config.NumberColumn("Total", format="$%.2f")
                            }
                        )
                    else:
                        st.info("No items recorded for this debt")
                    
                    # Show payment history if available
                    if debt.get('payment_history'):
                        st.write("**Payment History:**")
                        payment_history = pd.DataFrame(debt['payment_history'])
                        st.dataframe(payment_history, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    
    # ==============================
    # TOP DEBTORS
    # ==============================
    st.subheader("Top Debtors by Outstanding Balance")
    
    top_debtors = df.nlargest(10, "balance")[["customer_name", "balance", "total_amount", "amount_paid", "risk_level", "status"]]
    
    if not top_debtors.empty:
        st.dataframe(
            top_debtors,
            use_container_width=True,
            hide_index=True,
            column_config={
                "balance": st.column_config.NumberColumn("Outstanding", format="$%.2f"),
                "total_amount": st.column_config.NumberColumn("Total Debt", format="$%.2f"),
                "amount_paid": st.column_config.NumberColumn("Paid", format="$%.2f")
            }
        )
    
    st.markdown("---")
    
    # ==============================
    # EXPORT DATA
    # ==============================
    st.subheader("Export Data")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Full debtors report
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download Full Debtors Report (CSV)",
            data=csv,
            file_name=f"debtors_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    with col2:
        # Overdue report
        if not overdue.empty:
            csv_overdue = overdue.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="Download Overdue Report (CSV)",
                data=csv_overdue,
                file_name=f"overdue_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
    
    # ==============================
    # REFRESH BUTTON
    # ==============================
    st.markdown("---")
    if st.button("Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


# ==============================
# MAIN GUARD
# ==============================
if __name__ == "__main__":
    debtors_dashboard()