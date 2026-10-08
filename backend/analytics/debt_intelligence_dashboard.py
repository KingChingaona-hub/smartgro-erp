# backend/analytics/debt_intelligence_dashboard.py
# Credit Intelligence Dashboard — branch-aware, on top of Floating Financials.
#
# Data source: backend.core.floating_financials
#   - floating_credits   (customer owes us)
#   - floating_changes   (we owe customer change)
#
# Branch scope:
#   branch_id = None            -> session branch
#   branch_id = "HO"/"NAT"/..   -> single branch
#   branch_id = "__ALL__"       -> aggregate across all branches (owner only)
#
# This replaces the legacy CSV-backed debtors_engine / debt_notifications stack.

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import re

from backend.core.db_adapter import load_branches

from backend.core.floating_financials import (
    get_credit_records,
    get_credit_summary,
    get_overdue_credits,
    get_bad_debt_credits,
    get_written_off_credits,
    get_change_records,
    get_change_summary,
    get_overdue_changes,
    get_written_off_changes,
)


# ==============================
# BRANCH RESOLUTION
# ==============================
ALL_BRANCHES = "__ALL__"


def _resolve_branch(branch_id=None):
    if branch_id is not None:
        return branch_id
    try:
        return (
            st.session_state.get("user_branch")
            or st.session_state.get("current_branch_code")
            or "HO"
        )
    except Exception:
        return "HO"


def _is_all_branches(branch_id):
    return isinstance(branch_id, str) and branch_id.upper() == ALL_BRANCHES


def _branch_label(branch_id):
    if _is_all_branches(branch_id):
        return "All Branches"
    try:
        bdf = load_branches()
        if bdf is not None and not bdf.empty and "branch_id" in bdf.columns:
            match = bdf[bdf["branch_id"].astype(str).str.upper() == str(branch_id).upper()]
            if not match.empty:
                row = match.iloc[0]
                return f"{row.get('branch_name', '')} ({row.get('branch_id', '')})".strip()
    except Exception:
        pass
    return str(branch_id)


def _filter_by_branch(df, branch_id):
    """Filter a floating_financials DataFrame by branch when the column exists."""
    if df is None or df.empty:
        return pd.DataFrame()
    if _is_all_branches(branch_id):
        return df
    if "branch_id" not in df.columns:
        return df  # older floating_financials didn't tag branch; assume caller scoped upstream
    return df[df["branch_id"].astype(str).str.upper() == str(branch_id).upper()].copy()


def _safe_records(getter, branch_id, **kwargs):
    """
    Call a floating_financials getter, trying branch_id first, then falling
    back to post-filtering. Never raises.
    """
    try:
        try:
            df = getter(branch_id=branch_id, **kwargs) if not _is_all_branches(branch_id) \
                else getter(**kwargs)
        except TypeError:
            df = getter(**kwargs)
            df = _filter_by_branch(df, branch_id)
        if df is None:
            return pd.DataFrame()
        return _filter_by_branch(df, branch_id)
    except Exception as e:
        print(f"[debt_intelligence] getter {getter.__name__} failed: {e}")
        return pd.DataFrame()


def _to_float(series_or_value, default=0.0):
    try:
        if isinstance(series_or_value, pd.Series):
            return pd.to_numeric(series_or_value, errors="coerce").fillna(0).astype(float)
        return float(series_or_value) if series_or_value is not None else default
    except (TypeError, ValueError):
        return default


# ==============================
# OVERDUE MESSAGE GENERATOR (replaces debt_notifications.py)
# ==============================
def get_overdue_messages(branch_id=None):
    """
    Generate overdue notification messages for credits and changes.
    Sourced from Floating Financials, scoped to a branch.
    """
    branch_id = _resolve_branch(branch_id)
    messages = []

    # ---- Overdue credits ----
    try:
        credits = _safe_records(get_overdue_credits, branch_id)
        if not credits.empty:
            now = pd.Timestamp.now()
            date_col = None
            for c in ["due_date", "expected_repayment_date", "due_on", "date_due"]:
                if c in credits.columns:
                    date_col = c
                    break
            if date_col:
                credits[date_col] = pd.to_datetime(credits[date_col], errors="coerce")
                for _, row in credits.iterrows():
                    due = row[date_col]
                    if pd.isna(due):
                        continue
                    days_overdue = int((now - due).days)
                    if days_overdue <= 0:
                        continue

                    balance = _to_float(row.get("balance", 0))
                    if balance <= 0:
                        continue

                    if days_overdue <= 7:
                        severity, emoji = "Gentle Reminder", "🔔"
                    elif days_overdue <= 30:
                        severity, emoji = "Follow Up", "⚠️"
                    elif days_overdue <= 60:
                        severity, emoji = "URGENT", "🚨"
                    else:
                        severity, emoji = "FINAL NOTICE", "⛔"

                    customer = str(row.get("customer_name", "Unknown"))
                    phone = str(row.get("phone", ""))
                    messages.append({
                        "type": "credit",
                        "customer": customer,
                        "phone": phone,
                        "balance": f"${balance:.2f}",
                        "balance_raw": balance,
                        "days_overdue": days_overdue,
                        "severity": severity,
                        "record_id": str(row.get("id", "")),
                        "message": (
                            f"{emoji} {severity}: Dear {customer}, "
                            f"your outstanding balance of ${balance:.2f} "
                            f"is overdue by {days_overdue} days. "
                            f"Please make payment immediately."
                        ),
                    })
    except Exception as e:
        print(f"[debt_intelligence] overdue credits error: {e}")

    # ---- Overdue changes ----
    try:
        changes = _safe_records(get_overdue_changes, branch_id)
        if not changes.empty:
            now = pd.Timestamp.now()
            date_col = None
            for c in ["due_date", "expected_collection_date", "due_on", "date_due"]:
                if c in changes.columns:
                    date_col = c
                    break
            if date_col:
                changes[date_col] = pd.to_datetime(changes[date_col], errors="coerce")
                for _, row in changes.iterrows():
                    due = row[date_col]
                    if pd.isna(due):
                        continue
                    days_overdue = int((now - due).days)
                    if days_overdue <= 0:
                        continue

                    balance = _to_float(row.get("balance", 0))
                    if balance <= 0:
                        continue

                    if days_overdue <= 7:
                        severity, emoji = "Gentle Reminder", "🔔"
                    elif days_overdue <= 30:
                        severity, emoji = "Follow Up", "⚠️"
                    elif days_overdue <= 60:
                        severity, emoji = "URGENT", "🚨"
                    else:
                        severity, emoji = "FINAL NOTICE", "⛔"

                    customer = str(row.get("customer_name", "Unknown"))
                    phone = str(row.get("phone", ""))
                    messages.append({
                        "type": "change",
                        "customer": customer,
                        "phone": phone,
                        "balance": f"${balance:.2f}",
                        "balance_raw": balance,
                        "days_overdue": days_overdue,
                        "severity": severity,
                        "record_id": str(row.get("id", "")),
                        "message": (
                            f"{emoji} {severity}: Dear {customer}, "
                            f"you have an uncollected change of ${balance:.2f} "
                            f"that is overdue by {days_overdue} days. "
                            f"Please collect it at your earliest convenience."
                        ),
                    })
    except Exception as e:
        print(f"[debt_intelligence] overdue changes error: {e}")

    if not messages:
        return pd.DataFrame()
    return pd.DataFrame(messages).sort_values("days_overdue", ascending=False)


# ==============================
# DASHBOARD
# ==============================
def debt_intelligence_dashboard():
    """Credit Intelligence Dashboard — branch-scoped, backed by Floating Financials."""
    st.title("Credit Intelligence System")
    st.caption("AI-powered credit risk analysis and debt management — branch-scoped")

    role = st.session_state.get("role", "cashier")

    # ---- Branch scope ----
    try:
        branches_df = load_branches()
    except Exception:
        branches_df = pd.DataFrame()

    is_owner = role in ("owner", "admin")

    if is_owner and branches_df is not None and not branches_df.empty:
        branch_options = ["All Branches"] + [
            f"{r['branch_name']} ({r['branch_id']})" for _, r in branches_df.iterrows()
        ]
        choice = st.selectbox(
            "Branch scope",
            branch_options,
            key="debt_intel_branch_scope",
            help="Owners may analyze company-wide or one branch at a time.",
        )
        if choice == "All Branches":
            branch_id = ALL_BRANCHES
            branch_label = "All Branches"
        else:
            m = re.search(r"\(([^)]+)\)\s*$", choice)
            branch_id = m.group(1).strip() if m else choice
            branch_label = choice
    else:
        branch_id = _resolve_branch(None)
        branch_label = _branch_label(branch_id)
        st.info(f"Credit Intelligence locked to your branch: **{branch_label}**")

    st.caption(f"Analysis scope: **{branch_label}**")
    st.markdown("---")

    # ---- Load scoped records ----
    credits_df = _safe_records(get_credit_records, branch_id)
    changes_df = _safe_records(get_change_records, branch_id) if "get_change_records" in globals() \
        else pd.DataFrame()

    # Fallback: some floating_financials builds expose changes only via summary
    if changes_df.empty:
        try:
            summary_changes = get_change_summary() or {}
        except Exception:
            summary_changes = {}
    else:
        summary_changes = {}

    if credits_df.empty and changes_df.empty and not summary_changes:
        st.warning(f"No credit or change records found for {branch_label}.")
        return

    # ==============================
    # KEY METRICS
    # ==============================
    st.subheader("Credit Overview")
    st.caption(f"Branch: **{branch_label}**")

    if not credits_df.empty:
        if "balance" in credits_df.columns:
            credits_df["balance"] = _to_float(credits_df["balance"])
        else:
            credits_df["balance"] = 0.0

        if "amount" in credits_df.columns:
            credits_df["amount"] = _to_float(credits_df["amount"])
        if "amount_paid" in credits_df.columns:
            credits_df["amount_paid"] = _to_float(credits_df["amount_paid"])

        open_credits = credits_df[credits_df["balance"] > 0]
        total_outstanding = float(open_credits["balance"].sum())
        total_debtors = len(open_credits)
        avg_debt = total_outstanding / total_debtors if total_debtors > 0 else 0
    else:
        total_outstanding = 0.0
        total_debtors = 0
        avg_debt = 0.0

    # Changes balance
    if not changes_df.empty and "balance" in changes_df.columns:
        changes_df["balance"] = _to_float(changes_df["balance"])
        open_changes = changes_df[changes_df["balance"] > 0]
        total_change_balance = float(open_changes["balance"].sum())
        open_change_count = len(open_changes)
    elif summary_changes:
        total_change_balance = float(summary_changes.get("total_balance", 0) or 0)
        open_change_count = int(summary_changes.get("uncollected_count", 0) or 0)
    else:
        total_change_balance = 0.0
        open_change_count = 0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Outstanding Credit", f"${total_outstanding:,.2f}")
    with col2:
        st.metric("Active Debtors", total_debtors)
    with col3:
        st.metric("Avg Debt / Debtor", f"${avg_debt:.2f}")
    with col4:
        st.metric("Uncollected Change", f"${total_change_balance:,.2f}")
        if open_change_count:
            st.caption(f"{open_change_count} open change record(s)")

    st.markdown("---")

    # ==============================
    # OVERDUE
    # ==============================
    st.subheader("Overdue Notifications")
    st.caption(f"Branch: **{branch_label}**")

    overdue_credits = _safe_records(get_overdue_credits, branch_id)
    overdue_changes = _safe_records(get_overdue_changes, branch_id)

    messages = get_overdue_messages(branch_id)

    if not messages.empty:
        st.warning(f"{len(messages)} overdue record(s) need attention in {branch_label}")

        severity_colors = {
            "Gentle Reminder": "🟢",
            "Follow Up": "🟡",
            "URGENT": "🟠",
            "FINAL NOTICE": "🔴",
        }
        for _, msg in messages.iterrows():
            emoji = severity_colors.get(msg["severity"], "📢")
            record_type = msg.get("type", "credit")
            prefix = "Credit" if record_type == "credit" else "Change"
            st.info(
                f"{emoji} **{msg['customer']}** — {msg['severity']} — "
                f"{msg['balance']} — {msg['days_overdue']} days overdue ({prefix})"
            )

        csv = messages.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download Overdue Messages (CSV)",
            data=csv,
            file_name=(
                f"overdue_messages_"
                f"{re.sub(r'[^A-Za-z0-9_-]+', '_', str(branch_id))}_"
                f"{datetime.now().strftime('%Y%m%d')}.csv"
            ),
            mime="text/csv",
        )
    else:
        st.success(f"No overdue records in {branch_label}")

    st.markdown("---")

    # ==============================
    # BAD DEBT + WRITTEN OFF
    # ==============================
    st.subheader("Recovery Analysis")
    st.caption(f"Branch: **{branch_label}**")

    bad_debt = _safe_records(get_bad_debt_credits, branch_id)
    written_off = _safe_records(get_written_off_credits, branch_id) \
        if "get_written_off_credits" in globals() else pd.DataFrame()
    written_off_changes = _safe_records(get_written_off_changes, branch_id)

    total_bad_debt = 0.0
    total_written_off = 0.0

    if not bad_debt.empty and "amount" in bad_debt.columns and "amount_paid" in bad_debt.columns:
        bad_debt = bad_debt.copy()
        bad_debt["amount"] = _to_float(bad_debt["amount"])
        bad_debt["amount_paid"] = _to_float(bad_debt["amount_paid"])
        bad_debt["outstanding"] = (bad_debt["amount"] - bad_debt["amount_paid"]).clip(lower=0)
        total_bad_debt = float(bad_debt["outstanding"].sum())

    if not written_off.empty and "amount" in written_off.columns:
        written_off = written_off.copy()
        written_off["amount"] = _to_float(written_off["amount"])
        if "amount_paid" in written_off.columns:
            written_off["amount_paid"] = _to_float(written_off["amount_paid"])
            written_off["outstanding"] = (
                written_off["amount"] - written_off["amount_paid"]
            ).clip(lower=0)
        else:
            written_off["outstanding"] = written_off["amount"]
        total_written_off = float(written_off["outstanding"].sum())

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Bad Debt Outstanding", f"${total_bad_debt:,.2f}")
    with col2:
        st.metric("Written-Off Credits", f"${total_written_off:,.2f}")
    with col3:
        total_at_risk = total_outstanding + total_change_balance
        st.metric("Total At-Risk Balance", f"${total_at_risk:,.2f}")

    st.markdown("---")

    # ==============================
    # TOP DEBTORS
    # ==============================
    if not credits_df.empty and "balance" in credits_df.columns:
        st.subheader("Top Debtors by Outstanding Balance")
        st.caption(f"Branch: **{branch_label}**")

        name_col = "customer_name" if "customer_name" in credits_df.columns else None
        phone_col = "phone" if "phone" in credits_df.columns else None

        if name_col:
            top = credits_df[credits_df["balance"] > 0].nlargest(10, "balance")
            display_cols = [name_col, "balance"]
            if phone_col:
                display_cols.insert(1, phone_col)

            st.dataframe(
                top[display_cols],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "customer_name": "Customer",
                    "phone": "Phone",
                    "balance": st.column_config.NumberColumn("Balance", format="$%.2f"),
                },
            )

        st.markdown("---")

    # ==============================
    # EXPORT
    # ==============================
    st.subheader("Export Credit Report")
    st.caption(f"Branch: **{branch_label}**")

    branch_slug = re.sub(r"[^A-Za-z0-9_-]+", "_", str(branch_id)).strip("_") or "branch"

    if not credits_df.empty:
        csv = credits_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download Credit Report (CSV)",
            data=csv,
            file_name=f"credit_report_{branch_slug}_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    if not changes_df.empty:
        csv_changes = changes_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download Changes Report (CSV)",
            data=csv_changes,
            file_name=f"changes_report_{branch_slug}_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True,
        )


# ==============================
# MAIN GUARD
# ==============================
if __name__ == "__main__":
    debt_intelligence_dashboard()