import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

from backend.modules.income import load_income, get_monthly_income


def income_dashboard():

    st.title("📊 Income Dashboard")

    df = load_income()

    if df.empty:
        st.warning("No income recorded yet.")
        return

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["month"] = df["date"].dt.strftime("%Y-%m")

    current_month = df["month"].max()
    month_df = df[df["month"] == current_month]

    total_income = month_df["amount"].sum()

    # ==============================
    # METRICS
    # ==============================
    st.markdown("## 💰 Monthly Income Overview")

    col1, col2 = st.columns(2)

    col1.metric("Total Income", f"${total_income:.2f}")
    col2.metric("Records", len(month_df))

    st.markdown("---")

    # ==============================
    # SOURCE BREAKDOWN
    # ==============================
    st.subheader("📂 Income by Source")

    source_df = month_df.groupby("income_source")["amount"].sum()

    fig1, ax1 = plt.subplots()
    source_df.plot(kind="bar", ax=ax1)
    ax1.set_ylabel("Amount")
    ax1.set_title("Income Sources")

    st.pyplot(fig1)

    # ==============================
    # PIE CHART
    # ==============================
    st.subheader("📊 Income Distribution")

    fig2, ax2 = plt.subplots()
    source_df.plot(kind="pie", autopct="%1.1f%%", ax=ax2)
    ax2.set_ylabel("")

    st.pyplot(fig2)

    # ==============================
    # TABLE
    # ==============================
    st.subheader("📜 Income Records")

    st.dataframe(month_df.sort_values("date", ascending=False), use_container_width=True)