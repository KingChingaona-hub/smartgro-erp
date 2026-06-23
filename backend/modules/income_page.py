import streamlit as st
from backend.modules.income import record_income, load_income, get_monthly_income


def income_page():

    st.title("💰 Business Income")

    # ==============================
    # INPUT FORM
    # ==============================
    st.subheader("➕ Record Income")

    income_source = st.selectbox(
        "Income Source",
        [
            "Sales Adjustment",
            "Delivery Fees",
            "Service Income",
            "Commission",
            "Asset Sale",
            "Other"
        ]
    )

    description = st.text_input("Description")

    amount = st.number_input("Amount", min_value=0.0)

    if st.button("Add Income"):

        if amount <= 0:
            st.error("Enter valid amount")
        else:
            record_income(
                income_source,
                description,
                amount,
                st.session_state.get("username", "System")
            )
            st.success("Income recorded")
            st.rerun()

    # ==============================
    # SUMMARY
    # ==============================
    st.markdown("---")

    monthly_total = get_monthly_income()

    st.metric("This Month Income", f"${monthly_total:.2f}")

    # ==============================
    # TABLE
    # ==============================
    df = load_income()

    if not df.empty:
        st.dataframe(df.sort_values("date", ascending=False), use_container_width=True)
    else:
        st.info("No income recorded yet.")