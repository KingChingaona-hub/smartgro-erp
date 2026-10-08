# backend/modules/income_page.py
import streamlit as st
from backend.modules.income import (
    record_income,
    load_income,
    get_monthly_income,
    get_income_by_source,
    get_income_trend,
    get_total_income,
    delete_income,
    delete_income_by_id
)
import pandas as pd
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go


# ==============================
# SESSION BRANCH HELPER
# ==============================
def _get_session_branch():
    """
    Return the authoritative branch for the current session.
    Prefers `current_branch_code` (set by the branch-selection screen)
    over `user_branch` (which may be a stale default).
    """
    return (
        st.session_state.get("current_branch_code")
        or st.session_state.get("user_branch")
        or "HO"
    )


def _branch_display_name(branch_id):
    try:
        from backend.core.db_adapter import load_branches
        df = load_branches()
        if df is not None and not df.empty and "branch_id" in df.columns:
            match = df[df["branch_id"].astype(str).str.upper() == str(branch_id).upper()]
            if not match.empty:
                name = match.iloc[0].get("branch_name", "")
                if name:
                    return f"{name} ({branch_id})"
    except Exception:
        pass
    return str(branch_id)


def income_page():
    """Income Management Page - PostgreSQL-backed, branch-scoped"""

    branch_id = _get_session_branch()
    branch_label = _branch_display_name(branch_id)

    st.title(f"Business Income - {branch_label}")
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
    if "delete_success" not in st.session_state:
        st.session_state.delete_success = False
    if "delete_message" not in st.session_state:
        st.session_state.delete_message = ""

    # ==============================
    # DISPLAY MESSAGES FROM SESSION STATE
    # ==============================
    if st.session_state.income_success and st.session_state.income_message:
        st.success(f"{st.session_state.income_message}")
        st.balloons()
        st.session_state.income_success = False
        st.session_state.income_message = ""

    if st.session_state.delete_success and st.session_state.delete_message:
        st.success(f"{st.session_state.delete_message}")
        st.session_state.delete_success = False
        st.session_state.delete_message = ""

    # ==============================
    # LOAD INCOME (branch-scoped)
    # ==============================
    df = load_income(branch_id=branch_id)

    # Show current branch in sidebar
    with st.sidebar.expander("Income Info"):
        st.write(f"**Branch:** {branch_label}")
        st.write(f"**Records loaded:** {len(df)}")

        if not df.empty:
            st.write(f"**Date range:** {df['date'].min()} to {df['date'].max()}")
            st.write(f"**Total amount:** ${df['amount'].sum():,.2f}")

    # ==============================
    # INPUT FORM
    # ==============================
    st.subheader(f"Record Income — {branch_label}")

    with st.form(key=f"income_form_{branch_id}", clear_on_submit=True):
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
                key=f"income_source_select_{branch_id}",
            )

            description = st.text_input(
                "Description *",
                placeholder="Brief description of income",
                key=f"income_description_{branch_id}",
            )

        with col2:
            amount = st.number_input(
                "Amount ($) *",
                min_value=0.01,
                step=10.0,
                value=0.01,
                key=f"income_amount_{branch_id}",
            )
            user = st.text_input(
                "Recorded By",
                value=st.session_state.get("username", "System"),
                disabled=True,
                key=f"income_user_{branch_id}",
            )

        submitted = st.form_submit_button("Record Income", type="primary", use_container_width=True)

        if submitted:
            if amount <= 0:
                st.error("Please enter a valid amount greater than 0")
            elif not description:
                st.error("Please enter a description")
            else:
                success, message = record_income(
                    income_source,
                    description,
                    amount,
                    st.session_state.get("username", "System"),
                    branch_id=branch_id,
                )
                if success:
                    st.session_state.income_success = True
                    st.session_state.income_message = message
                    st.rerun()
                else:
                    st.error(f"Failed to record income: {message}")

    # ==============================
    # SUMMARY
    # ==============================
    st.markdown("---")

    col1, col2, col3, col4 = st.columns(4)

    monthly_total = get_monthly_income(branch_id=branch_id)
    total_income = get_total_income(branch_id=branch_id)

    with col1:
        st.metric("This Month Income", f"${monthly_total:.2f}")

    with col2:
        st.metric("Total Income All Time", f"${total_income:,.2f}")

    source_df = get_income_by_source(branch_id=branch_id)
    if not source_df.empty:
        with col3:
            top_source = source_df.iloc[0]["income_source"]
            top_amount = source_df.iloc[0]["amount"]
            st.metric("Top Source", f"{top_source}", delta=f"${top_amount:.2f}")

        with col4:
            st.metric("Total Sources", len(source_df))
    else:
        with col3:
            st.metric("Top Source", "N/A")
        with col4:
            st.metric("Total Sources", "0")

    st.markdown("---")

    # ==============================
    # INCOME BY SOURCE CHART
    # ==============================
    if not source_df.empty:
        st.subheader(f"Income by Source — {branch_label}")

        col1, col2 = st.columns(2)

        with col1:
            fig = px.pie(
                source_df,
                values="amount",
                names="income_source",
                title=f"Income Distribution by Source — {branch_label}",
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Set2,
            )
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            fig_bar = px.bar(
                source_df,
                x="income_source",
                y="amount",
                title=f"Income by Source — {branch_label}",
                color="amount",
                color_continuous_scale="Greens",
                text="amount",
            )
            fig_bar.update_traces(texttemplate="$%{text:.2f}", textposition="outside")
            fig_bar.update_layout(height=350)
            st.plotly_chart(fig_bar, use_container_width=True)

    # ==============================
    # INCOME TREND
    # ==============================
    st.markdown("---")
    st.subheader("Income Trend")

    trend_df = get_income_trend(12, branch_id=branch_id)

    if not trend_df.empty:
        fig_trend = px.line(
            trend_df,
            x="Month",
            y="Total Income",
            title=f"Monthly Income Trend (Last 12 Months) — {branch_label}",
            markers=True,
            line_shape="spline",
        )
        fig_trend.update_layout(height=350)
        st.plotly_chart(fig_trend, use_container_width=True)
    else:
        st.info("No income trend data available")

    # ==============================
    # TABLE & DELETE
    # ==============================
    st.markdown("---")
    st.subheader("Income Records")

    if not df.empty:
        df_display = df.copy()
        df_display["date_display"] = pd.to_datetime(df_display["date"]).dt.strftime("%Y-%m-%d %H:%M")
        df_sorted = df_display.sort_values("date", ascending=False)

        st.dataframe(
            df_sorted[["date_display", "income_source", "description", "amount", "user"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "date_display": "Date",
                "amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
            },
        )

        st.caption(f"Showing {len(df_sorted)} income records")

        # ==============================
        # DELETE RECORD
        # ==============================
        with st.expander("Delete Income Record"):
            st.warning("⚠️ This action cannot be undone")

            if not df.empty:
                record_options = []
                record_data = []

                df_sorted_for_select = df.sort_values("date", ascending=False)

                for idx, row in df_sorted_for_select.iterrows():
                    date_str = pd.to_datetime(row["date"]).strftime("%Y-%m-%d %H:%M")
                    desc = str(row["description"])[:25] + "..." if len(str(row["description"])) > 25 else str(row["description"])
                    display_text = f"{date_str} | {row['income_source']} | {desc} | ${row['amount']:.2f}"
                    record_options.append(display_text)

                    record_data.append({
                        "date": row["date"],
                        "income_source": row["income_source"],
                        "amount": row["amount"],
                        "description": row.get("description", ""),
                    })

                selected_record = st.selectbox(
                    "Select Record to Delete",
                    record_options,
                    key=f"delete_select_{branch_id}",
                )

                if selected_record:
                    selected_idx = record_options.index(selected_record)
                    record_to_delete = record_data[selected_idx]

                    st.info(f"""
                    **Record to delete:**
                    - **Date:** {pd.to_datetime(record_to_delete['date']).strftime('%Y-%m-%d %H:%M')}
                    - **Source:** {record_to_delete['income_source']}
                    - **Amount:** ${record_to_delete['amount']:.2f}
                    - **Description:** {record_to_delete['description']}
                    """)

                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(
                            "Confirm Delete",
                            type="secondary",
                            use_container_width=True,
                            key=f"confirm_delete_income_{branch_id}",
                        ):
                            success = delete_income_by_id(
                                date_str=record_to_delete["date"],
                                income_source=record_to_delete["income_source"],
                                amount=record_to_delete["amount"],
                                description=record_to_delete["description"],
                                branch_id=branch_id,
                            )

                            if success:
                                st.session_state.delete_success = True
                                st.session_state.delete_message = "Income record deleted successfully!"
                                st.rerun()
                            else:
                                st.error("Failed to delete record. Please try again.")

                    with col2:
                        if st.button(
                            "Cancel",
                            use_container_width=True,
                            key=f"cancel_delete_income_{branch_id}",
                        ):
                            st.info("Deletion cancelled")

    else:
        st.info("No income recorded yet. Use the form above to add your first income record.")

        with st.expander("How to record your first income"):
            st.write("""
            1. Fill in the income details in the form above
            2. Select the appropriate income source
            3. Enter the amount and description
            4. Click 'Record Income' to save

            Tips:
            - Use clear descriptions for easy tracking
            - Select the correct source for better reporting
            - All income data is permanently saved
            """)

    # ==============================
    # EXPORT
    # ==============================
    if not df.empty:
        st.markdown("---")
        st.subheader("Export Data")

        col1, col2 = st.columns(2)

        with col1:
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label=f"Download All Income Data (CSV) — {branch_id}",
                data=csv,
                file_name=f"income_data_{branch_id}_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True,
                key=f"download_income_csv_{branch_id}",
            )

        with col2:
            if not source_df.empty:
                csv_summary = source_df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label=f"Download Income Summary by Source (CSV) — {branch_id}",
                    data=csv_summary,
                    file_name=f"income_summary_{branch_id}_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key=f"download_income_summary_{branch_id}",
                )


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    income_page()