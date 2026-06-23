# backend/customers/segmentation_dashboard.py
import streamlit as st
import plotly.express as px

from backend.core.db_adapter import (
    get_customer_segments,
    get_segment_summary,
    get_marketing_targets
)


def customers_segmentation_dashboard():
    """Customer Segmentation Dashboard"""

    st.title("🎯 Customer Segmentation & Marketing Engine")

    df = get_customer_segments()
    summary = get_segment_summary()
    targets, full_df = get_marketing_targets()

    if df.empty:
        st.warning("No customer data available.")
        return

    # ==============================
    # SEGMENT OVERVIEW
    # ==============================
    st.markdown("## 📊 Segment Distribution")

    fig = px.pie(
        summary,
        names="segment",
        values="count",
        title="Customer Segments Breakdown"
    )
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(summary)

    st.markdown("---")

    # ==============================
    # VIP CUSTOMERS
    # ==============================
    st.markdown("## 🟢 VIP Customers")

    vip = targets["vip"]

    if not vip.empty:
        st.dataframe(vip.sort_values("total_spent", ascending=False))

        st.success(f"Total VIP Customers: {len(vip)}")

    else:
        st.info("No VIP customers yet.")

    st.markdown("---")

    # ==============================
    # AT RISK CUSTOMERS
    # ==============================
    st.markdown("## ⚠ At Risk Customers")

    risk = targets["at_risk"]

    if not risk.empty:
        st.dataframe(risk.sort_values("total_spent", ascending=True))
        st.warning("These customers need promotions or re-engagement")
    else:
        st.success("No at-risk customers 🎉")

    st.markdown("---")

    # ==============================
    # NEW / LOW VALUE CUSTOMERS
    # ==============================
    st.markdown("## 🟡 New / Low Value Customers")

    new = targets["new"]

    if not new.empty:
        st.dataframe(new)

    # ==============================
    # INSIGHTS
    # ==============================
    st.markdown("---")
    st.markdown("## 🧠 Marketing Insights")

    vip_pct = len(vip) / len(df) * 100 if len(df) > 0 else 0
    risk_pct = len(risk) / len(df) * 100 if len(df) > 0 else 0

    st.metric("VIP Share", f"{vip_pct:.2f}%")
    st.metric("At Risk Share", f"{risk_pct:.2f}%")

    if risk_pct > 30:
        st.error("⚠ High churn risk — run promotions immediately")
    elif vip_pct > 20:
        st.success("✔ Strong loyal customer base")
    else:
        st.info("Growth stage business — focus on retention")