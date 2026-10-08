# backend/analytics/debtors_dashboard.py
# Debtors Intelligence Dashboard — sourced entirely from Floating Financials.
#
# Data source:
#   backend.core.floating_financials.get_credit_records /
#   get_credit_summary / get_overdue_credits / get_bad_debt_credits
#
# Branch scope:
#   branch_id = None          -> session branch (via _get_session_branch)
#   branch_id = "HO"/"NAT"/.. -> that branch
#
# Analytics (credit scores, aging buckets, recovery, lifecycle) are computed
# in-page from the branch-scoped credit records. No CSV, no separate engine.

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

from backend.core.floating_financials import (
    get_credit_records,
    get_credit_summary,
    get_overdue_credits,
    get_bad_debt_credits,
)
from backend.core.db_adapter import load_branches


# ==============================
# SESSION BRANCH HELPERS
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


# ==============================
# SAFE CONVERTERS
# ==============================
def safe_float(value, default=0.0):
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value, default=0):
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# ==============================
# IN-PAGE ANALYTICS HELPERS
# ==============================
def _enrich_credits(credits_df):
    """
    Add computed columns to the credit records:
        days_overdue
        aging_bucket
        credit_score (0-100, higher = better)
        risk_level (LOW / MEDIUM / HIGH / CRITICAL / NONE)
    """
    if credits_df is None or credits_df.empty:
        return pd.DataFrame()

    df = credits_df.copy()

    for c in ["amount", "amount_paid", "balance"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    # Expected repayment date -> datetime
    if "expected_repayment_date" in df.columns:
        df["expected_dt"] = pd.to_datetime(df["expected_repayment_date"], errors="coerce")
    else:
        df["expected_dt"] = pd.NaT

    now = pd.Timestamp.now()

    def _days_overdue(row):
        if pd.isna(row["expected_dt"]):
            return 0
        if str(row.get("status", "")).upper() in ("PAID", "WRITTEN_OFF", "BAD_DEBT"):
            return 0
        d = (now - row["expected_dt"]).days
        return d if d > 0 else 0

    df["days_overdue"] = df.apply(_days_overdue, axis=1)

    def _aging_bucket(row):
        if row["balance"] <= 0:
            return "Paid"
        if str(row.get("status", "")).upper() in ("WRITTEN_OFF", "BAD_DEBT"):
            return "Bad Debt"
        if pd.isna(row["expected_dt"]):
            return "Unscheduled"
        d = row["days_overdue"]
        if d <= 0:
            return "Current"
        if d <= 30:
            return "1-30 Days Overdue"
        if d <= 60:
            return "31-60 Days Overdue"
        if d <= 90:
            return "61-90 Days Overdue"
        return "90+ Days (Critical)"

    df["aging_bucket"] = df.apply(_aging_bucket, axis=1)

    def _credit_score(row):
        """
        Simple, defensible credit score:
            start at 100
            - 0.5 per day overdue (cap 60)
            - 20 if ever written off / bad debt
            - 10 if partial-only status
            + up to 20 for paid ratio
        Clamped to [0, 100].
        """
        score = 100.0
        score -= min(60.0, row["days_overdue"] * 0.5)

        status = str(row.get("status", "")).upper()
        if status in ("WRITTEN_OFF", "BAD_DEBT"):
            score -= 20
        if status == "PARTIAL_PAID":
            score -= 10

        amount = row.get("amount", 0) or 0
        paid = row.get("amount_paid", 0) or 0
        if amount > 0:
            paid_ratio = paid / amount
            score += (paid_ratio - 0.5) * 40  # -20..+20

        return max(0.0, min(100.0, score))

    df["credit_score"] = df.apply(_credit_score, axis=1)

    def _risk(row):
        if str(row.get("status", "")).upper() in ("WRITTEN_OFF", "BAD_DEBT"):
            return "CRITICAL"
        if row["days_overdue"] >= 90:
            return "CRITICAL"
        if row["days_overdue"] >= 60:
            return "HIGH"
        if row["days_overdue"] >= 30:
            return "MEDIUM"
        if row["days_overdue"] > 0:
            return "LOW"
        return "NONE"

    df["risk_level"] = df.apply(_risk, axis=1)

    return df


# ==============================
# DASHBOARD
# ==============================
def debtors_dashboard():
    """Debtors Intelligence Dashboard — sourced from Floating Financials."""

    branch_id = _get_session_branch()
    branch_label = _branch_display_name(branch_id)

    st.title(f"Debtors Intelligence Dashboard - {branch_label}")
    st.caption("Analytics and insights for credit management")

    # Load credits (branch-scoped)
    raw_credits = get_credit_records(branch_id=branch_id)

    if raw_credits is None or raw_credits.empty:
        st.warning(
            f"No credit records found in branch **{branch_label}**. "
            f"Create a credit from the Debtors page to see insights."
        )
        return

    df = _enrich_credits(raw_credits)

    # ==============================
    # KEY METRICS
    # ==============================
    st.subheader("Key Metrics")

    total_outstanding = float(df["balance"].sum())
    total_principal = float(df["amount"].sum())
    total_paid = float(df["amount_paid"].sum())
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
    # STATUS BREAKDOWN
    # ==============================
    st.subheader("Payment Status Breakdown")

    if "status" in df.columns:
        status_counts = df["status"].value_counts().reset_index()
        status_counts.columns = ["Status", "Count"]

        col1, col2 = st.columns(2)
        with col1:
            st.dataframe(status_counts, use_container_width=True, hide_index=True)
        with col2:
            fully_paid = len(df[df["status"] == "PAID"])
            partial = len(df[df["status"] == "PARTIAL_PAID"])
            active = len(df[df["status"] == "ACTIVE"])
            bad_debt = len(df[df["status"].isin(["WRITTEN_OFF", "BAD_DEBT"])])
            total_debts = len(df)

            st.metric("Fully Paid", fully_paid,
                      delta=f"{fully_paid / total_debts * 100:.1f}%" if total_debts else "0%")
            st.metric("Partial", partial)
            st.metric("Active", active)
            st.metric("Bad Debt / Written Off", bad_debt)

    st.markdown("---")

    # ==============================
    # RISK BREAKDOWN
    # ==============================
    st.subheader("Risk Level Breakdown")

    risk_counts = df["risk_level"].value_counts().reset_index()
    risk_counts.columns = ["Risk Level", "Count"]

    risk_order = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "NONE"]
    risk_counts["Risk Level"] = pd.Categorical(risk_counts["Risk Level"], categories=risk_order, ordered=True)
    risk_counts = risk_counts.sort_values("Risk Level").dropna(subset=["Risk Level"])

    col1, col2 = st.columns(2)
    with col1:
        st.dataframe(risk_counts, use_container_width=True, hide_index=True)
    with col2:
        critical = df[df["risk_level"] == "CRITICAL"]
        if not critical.empty:
            st.error(f"{len(critical)} CRITICAL risk debtors need immediate attention!")
            st.dataframe(
                critical[["customer_name", "balance", "expected_repayment_date"]].head(10),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.success("No CRITICAL risk debtors")

    st.markdown("---")

    # ==============================
    # CREDIT SCORES
    # ==============================
    st.subheader("Credit Scores")
    st.caption("Computed in-page from outstanding balance, days overdue, and payment history")

    if "credit_score" in df.columns:
        score_df = df.sort_values("credit_score").head(20).copy()

        def color_score(val):
            if val <= 30:
                return "🔴"
            if val <= 50:
                return "🟠"
            if val <= 70:
                return "🟡"
            return "🟢"

        score_df["Score"] = score_df["credit_score"].apply(color_score)
        display_cols = ["customer_name", "Score", "credit_score", "balance", "risk_level"]
        display_cols = [c for c in display_cols if c in score_df.columns]

        st.dataframe(
            score_df[display_cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                "credit_score": st.column_config.ProgressColumn(
                    "Credit Score", min_value=0, max_value=100
                ),
                "Score": st.column_config.TextColumn("Status"),
            },
        )

    st.markdown("---")

    # ==============================
    # AGING
    # ==============================
    st.subheader("Debt Aging Report")

    aging_buckets = ["Current", "1-30 Days Overdue", "31-60 Days Overdue",
                     "61-90 Days Overdue", "90+ Days (Critical)", "Unscheduled", "Bad Debt"]

    aging_summary = df[df["balance"] > 0].groupby("aging_bucket").agg({
        "balance": "sum",
        "customer_name": "count",
    }).reindex(aging_buckets).fillna(0).reset_index()

    aging_summary.columns = ["Bucket", "Total Amount", "Debtors"]
    aging_summary = aging_summary[aging_summary["Debtors"] > 0]

    col1, col2 = st.columns(2)
    with col1:
        st.dataframe(aging_summary, use_container_width=True, hide_index=True)
    with col2:
        if not aging_summary.empty:
            max_amount = aging_summary["Total Amount"].max()
            if max_amount > 0:
                for _, row in aging_summary.iterrows():
                    bar_length = int((row["Total Amount"] / max_amount) * 30)
                    bar = "█" * bar_length
                    pct = (row["Total Amount"] / aging_summary["Total Amount"].sum() * 100) if aging_summary["Total Amount"].sum() > 0 else 0
                    st.write(f"{row['Bucket']}: {bar} ${row['Total Amount']:,.2f} ({pct:.1f}%)")

    # Recovery analysis
    st.markdown("---")
    st.subheader("Recovery Analysis")

    recoverable_balance = float(df[df["balance"] > 0]["balance"].sum())
    expected_recovery = 0.0
    expected_loss = 0.0

    for _, row in df.iterrows():
        bal = row.get("balance", 0) or 0
        if bal <= 0:
            continue
        risk = row.get("risk_level", "NONE")
        if risk == "CRITICAL":
            expected_recovery += bal * 0.3
            expected_loss += bal * 0.7
        elif risk == "HIGH":
            expected_recovery += bal * 0.6
            expected_loss += bal * 0.4
        elif risk == "MEDIUM":
            expected_recovery += bal * 0.85
            expected_loss += bal * 0.15
        else:
            expected_recovery += bal
            expected_loss += 0

    recovery_rate = (expected_recovery / recoverable_balance * 100) if recoverable_balance > 0 else 0

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Outstanding", f"${recoverable_balance:,.2f}")
    with col2:
        st.metric("Expected Recovery", f"${expected_recovery:,.2f}")
    with col3:
        st.metric("Recovery Rate", f"{recovery_rate:.1f}%")

    if expected_loss > 0:
        st.warning(f"Estimated Bad Debt Risk: ${expected_loss:,.2f}")
    else:
        st.success("No expected bad debt losses")

    st.markdown("---")

    # ==============================
    # OVERDUE
    # ==============================
    st.subheader("Overdue Debtors")

    overdue = df[df["days_overdue"] > 0].sort_values("days_overdue", ascending=False)

    if not overdue.empty:
        st.warning(f"{len(overdue)} customers with overdue payments")

        def get_urgency(days):
            if days >= 90:
                return "CRITICAL"
            if days >= 60:
                return "HIGH"
            if days >= 30:
                return "MEDIUM"
            return "LOW"

        overdue_display = overdue.copy()
        overdue_display["Urgency"] = overdue_display["days_overdue"].apply(get_urgency)

        cols = [c for c in [
            "customer_name", "balance", "expected_repayment_date",
            "risk_level", "days_overdue", "Urgency"
        ] if c in overdue_display.columns]

        st.dataframe(
            overdue_display[cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                "days_overdue": st.column_config.NumberColumn("Days Overdue", format="%d"),
            },
        )

        st.markdown("### Overdue Summary by Urgency")
        urgency_summary = overdue_display.groupby("Urgency").agg({
            "balance": "sum",
            "customer_name": "count",
        }).reset_index()
        urgency_summary.columns = ["Urgency", "Total Amount", "Customers"]
        st.dataframe(urgency_summary, use_container_width=True, hide_index=True)
    else:
        st.success("No overdue payments")

    st.markdown("---")

    # ==============================
    # CUSTOMER DETAIL
    # ==============================
    st.subheader("Customer Credit Details")
    st.caption("View detailed credit history per customer")

    customers_with_credit = df[df["balance"] > 0]["customer_name"].dropna().unique().tolist()
    all_customers = df["customer_name"].dropna().unique().tolist()
    customer_list = customers_with_credit + [c for c in all_customers if c not in customers_with_credit]

    if not customer_list:
        st.info("No customers found")
        return

    selected_customer = st.selectbox("Select Customer", customer_list)

    if selected_customer:
        cust_credits = df[df["customer_name"] == selected_customer]

        total_borrowed = cust_credits["amount"].sum()
        total_paid_cust = cust_credits["amount_paid"].sum()
        outstanding = cust_credits["balance"].sum()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Borrowed", f"${total_borrowed:.2f}")
        col2.metric("Total Paid", f"${total_paid_cust:.2f}")
        col3.metric("Outstanding", f"${outstanding:.2f}")
        progress = (total_paid_cust / total_borrowed * 100) if total_borrowed > 0 else 0
        col4.metric("Payment Progress", f"{progress:.1f}%")

        st.progress(min(progress / 100, 1.0), text=f"Payment Progress: {progress:.1f}%")

        st.markdown("### Individual Credits")

        for _, credit in cust_credits.iterrows():
            cid = credit.get("credit_id", "N/A")
            status = credit.get("status", "ACTIVE")
            balance = credit.get("balance", 0)
            desc = str(credit.get("description", "") or "")

            if balance <= 0:
                icon = "✅"
            elif status in ("WRITTEN_OFF", "BAD_DEBT"):
                icon = "🚫"
            elif credit.get("days_overdue", 0) > 0:
                icon = "🔴"
            elif status == "PARTIAL_PAID":
                icon = "🟡"
            else:
                icon = "📝"

            with st.expander(f"{icon} Credit ID: {cid} | Balance: ${balance:.2f} | Status: {status}"):
                col1, col2 = st.columns(2)

                with col1:
                    st.write(f"**Description:** {desc or '(no description)'}")
                    st.write(f"**Date Created:** {str(credit.get('created_at', 'N/A'))[:19]}")
                    st.write(f"**Expected Repayment:** {credit.get('expected_repayment_date', 'N/A')}")
                    st.write(f"**Credit Type:** {credit.get('credit_type', 'N/A')}")

                with col2:
                    st.write(f"**Original Amount:** ${safe_float(credit.get('amount', 0)):.2f}")
                    st.write(f"**Amount Paid:** ${safe_float(credit.get('amount_paid', 0)):.2f}")
                    st.write(f"**Remaining Balance:** ${safe_float(credit.get('balance', 0)):.2f}")
                    st.write(f"**Risk Level:** {credit.get('risk_level', 'N/A')}")
                    st.write(f"**Days Overdue:** {safe_int(credit.get('days_overdue', 0))}")
                    st.write(f"**Credit Score:** {safe_float(credit.get('credit_score', 0)):.0f}")

                if credit.get("written_off_reason"):
                    st.caption(f"**Written-off reason:** {credit.get('written_off_reason')}")

    st.markdown("---")

    # ==============================
    # TOP DEBTORS
    # ==============================
    st.subheader("Top Debtors by Outstanding Balance")

    top_debtors = df[df["balance"] > 0].nlargest(10, "balance")[
        [c for c in ["customer_name", "balance", "amount", "amount_paid", "risk_level", "status"] if c in df.columns]
    ]

    if not top_debtors.empty:
        st.dataframe(
            top_debtors,
            use_container_width=True,
            hide_index=True,
            column_config={
                "balance": st.column_config.NumberColumn("Outstanding", format="$%.2f"),
                "amount": st.column_config.NumberColumn("Total Debt", format="$%.2f"),
                "amount_paid": st.column_config.NumberColumn("Paid", format="$%.2f"),
            },
        )

    st.markdown("---")

    # ==============================
    # EXPORT
    # ==============================
    st.subheader("Export Data")

    col1, col2 = st.columns(2)
    with col1:
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label=f"Download Full Debtors Report (CSV) — {branch_id}",
            data=csv,
            file_name=f"debtors_report_{branch_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with col2:
        if not overdue.empty:
            csv_overdue = overdue.to_csv(index=False).encode("utf-8")
            st.download_button(
                label=f"Download Overdue Report (CSV) — {branch_id}",
                data=csv_overdue,
                file_name=f"overdue_report_{branch_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True,
            )

    # Refresh
    st.markdown("---")
    if st.button("Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


# ==============================
# MAIN GUARD
# ==============================
if __name__ == "__main__":
    debtors_dashboard()