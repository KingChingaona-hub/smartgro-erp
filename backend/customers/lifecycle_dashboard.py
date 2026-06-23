# backend/customers/lifecycle_dashboard.py
import streamlit as st
import plotly.express as px

from backend.core.db_adapter import get_customer_actions


def customers_lifecycle_dashboard():
    """Customer Lifecycle Dashboard"""

    st.title("🔄 Customer Lifecycle & Action Engine")

    df = get_customer_actions()

    if df.empty:
        st.warning("No customer data available.")
        return

    # ==============================
    # LIFECYCLE OVERVIEW
    # ==============================
    st.markdown("## 📊 Lifecycle Distribution")

    summary = df["lifecycle_stage"].value_counts().reset_index()
    summary.columns = ["stage", "count"]

    fig = px.pie(
        summary,
        names="stage",
        values="count",
        title="Customer Lifecycle Breakdown"
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # ==============================
    # FULL CUSTOMER TABLE
    # ==============================
    st.markdown("## 👥 Customer Lifecycle Table")

    st.dataframe(
        df[[
            "customer_name",
            "phone",
            "total_spent",
            "total_orders",
            "days_since_last_purchase",
            "lifecycle_stage",
            "recommended_action"
        ]].sort_values("total_spent", ascending=False)
    )

    st.markdown("---")

    # ==============================
    # STRATEGIC INSIGHTS
    # ==============================
    st.markdown("## 🧠 Business Actions")

    at_risk = len(df[df["lifecycle_stage"] == "At Risk"])
    loyal = len(df[df["lifecycle_stage"] == "Loyal"])

    st.metric("At Risk Customers", at_risk)
    st.metric("Loyal Customers", loyal)

    if at_risk > loyal:
        st.error("⚠ You are losing customers faster than you retain them")
    else:
        st.success("✔ Healthy customer lifecycle balance")