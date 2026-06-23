import streamlit as st
from backend.analytics.debtors_engine import get_credit_score, get_blocked_customers, get_debt_aging
from backend.analytics.debt_notifications import get_overdue_messages


def debt_intelligence_dashboard():

    st.title("🧠 Credit Intelligence System")

    st.subheader("📊 Credit Scores")
    st.dataframe(get_credit_score(), use_container_width=True)

    st.subheader("⛔ Blocked Customers")
    st.dataframe(get_blocked_customers(), use_container_width=True)

    st.subheader("📦 Debt Aging Report")
    st.dataframe(get_debt_aging(), use_container_width=True)

    st.subheader("📢 Overdue Notifications")

    messages = get_overdue_messages()

    if not messages.empty:
        st.dataframe(messages, use_container_width=True)
    else:
        st.info("No overdue customers")