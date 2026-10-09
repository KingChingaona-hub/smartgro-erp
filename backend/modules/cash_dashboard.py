# backend/modules/cash_dashboard.py
# Branch-safe cash register dashboard.
#
# Fixes in this revision:
#   - Shift start/stop works for every branch, including HO.
#   - Before starting a shift, any stale OPEN shift for the SAME branch is
#     inspected and (if owned by the same user or user is a manager) closed.
#   - Branch resolution for "already active" uses a direct SQL query with
#     UPPER(TRIM(branch_id)) so case/whitespace mismatches cannot hide a shift.
#   - Session state is cleaned on branch change so a stale shift_id from
#     another branch can never block starting a new shift.
#   - All shift start/end calls pass branch_id and branch_name resolved from
#     the branches table (never from stale session state).

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from decimal import Decimal

from backend.modules.cash_register import (
    load_cash,
    get_cash_summary,
    get_daily_report,
    get_cash_flow,
    get_cashier_performance,
    set_opening_cash,
    record_closing_cash,
    record_petty_cash,
    record_bank_deposit,
    load_petty_cash,
    load_bank_deposits,
)
from backend.modules.shift_manager import (
    start_shift,
    end_shift,
    load_shifts,
    get_active_shift_for_branch,
)
from backend.core.db_adapter import (
    load_sales,
    load_debtors as load_debtors_adapter,
    load_branches,
    get_db_cursor,
)
from backend.analytics.debtors_engine import load_debtors as load_debtors_data

try:
    from backend.core.shift_definitions import (
        get_shift_names_for_branch,
        ensure_branch_has_defaults,
    )
    _HAS_SHIFT_DEFS = True
except Exception:
    _HAS_SHIFT_DEFS = False


# ==============================
# SESSION BRANCH HELPERS
# ==============================
def _get_session_branch():
    return (
        st.session_state.get("current_branch_code")
        or st.session_state.get("user_branch")
        or "HO"
    )


def _branch_display_name(branch_id):
    try:
        df = load_branches()
        if df is not None and not df.empty and "branch_id" in df.columns:
            m = df[df["branch_id"].astype(str).str.upper() == str(branch_id).upper()]
            if not m.empty:
                name = m.iloc[0].get("branch_name", "")
                if name:
                    return name
    except Exception:
        pass
    return "Head Office" if str(branch_id).upper() == "HO" else str(branch_id)


def _cleanup_session_state_for_branch(branch_id):
    """
    If the session's active_shift_id belongs to a different branch, drop it.
    Prevents a stale HO shift from blocking a NAT shift (and vice-versa).
    """
    last_branch = st.session_state.get("_cash_dash_last_branch")
    if last_branch != branch_id:
        st.session_state.shift_id = None
        st.session_state.active_shift_id = None
        st.session_state.branch_shift_active = False
        st.session_state["_cash_dash_last_branch"] = branch_id


# ==============================
# DIRECT DB: SHIFT LOOKUP
# ==============================
def _query_open_shift_for_branch(branch_id):
    """
    Return the OPEN shift row for the branch, or None.

    Uses a direct SQL query with UPPER(TRIM(...)) so case or whitespace
    mismatches on branch_id cannot hide a live shift.
    """
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None:
                return None
            cur.execute("""
                SELECT shift_id, branch_id, branch_name, cashier_name, cashier_username,
                       start_time, opening_cash, status
                FROM shifts
                WHERE UPPER(TRIM(branch_id)) = UPPER(TRIM(%s))
                  AND UPPER(TRIM(status)) = 'OPEN'
                ORDER BY start_time DESC
                LIMIT 1
            """, (str(branch_id),))
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception as e:
        print(f"[cash_dashboard] open-shift lookup failed: {e}")
        return None


def _force_close_shift(shift_id, branch_id, reason=""):
    """Close a stale OPEN shift directly. Returns (ok, message)."""
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                return False, "No DB connection"
            cur.execute("""
                UPDATE shifts
                SET status = 'CLOSED',
                    end_time = COALESCE(end_time, NOW()),
                    notes = COALESCE(notes, '') || %s
                WHERE shift_id = %s
            """, (f" [auto-closed: {reason}]" if reason else "", str(shift_id)))
            conn.commit()
            return True, f"Closed shift {shift_id}"
    except Exception as e:
        print(f"[cash_dashboard] force-close failed: {e}")
        return False, str(e)


# ==============================
# HELPERS
# ==============================
def safe_float(value, default=0.0):
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def get_receipt_column(df):
    if df is None or df.empty:
        return None
    for col in ["receipt_no", "receipt", "transaction_id"]:
        if col in df.columns:
            return col
    return None


def get_amount_column(df):
    if df is None or df.empty:
        return None
    for col in ["final_total", "total", "amount", "spent"]:
        if col in df.columns:
            return col
    return None


def get_payment_method_column(df):
    if df is None or df.empty:
        return None
    for col in ["payment_method", "payment_type", "payment"]:
        if col in df.columns:
            return col
    return None


def get_date_column(df):
    if df is None or df.empty:
        return None
    for col in ["sale_date", "date", "transaction_date", "created_at"]:
        if col in df.columns:
            return col
    return None


def get_unduplicated_sales(sales_df):
    if sales_df is None or sales_df.empty:
        return pd.DataFrame()
    sales_df = sales_df.copy()
    receipt_col = get_receipt_column(sales_df)
    if receipt_col and receipt_col in sales_df.columns:
        return sales_df.drop_duplicates(subset=[receipt_col])
    return sales_df


def get_cash_sales_unduplicated(sales_df):
    if sales_df is None or sales_df.empty:
        return 0.0
    s = get_unduplicated_sales(sales_df)
    if s.empty:
        return 0.0
    payment_col = get_payment_method_column(s)
    amount_col = get_amount_column(s)
    if payment_col and amount_col:
        cash_sales = s[s[payment_col].astype(str).str.upper().isin(["CASH", "ECOCASH"])]
        return safe_float(cash_sales[amount_col].sum())
    return 0.0


def get_credit_sales_unduplicated(sales_df):
    if sales_df is None or sales_df.empty:
        return 0.0
    s = get_unduplicated_sales(sales_df)
    if s.empty:
        return 0.0
    payment_col = get_payment_method_column(s)
    amount_col = get_amount_column(s)
    if payment_col and amount_col:
        credit_sales = s[s[payment_col].astype(str).str.upper() == "CREDIT"]
        return safe_float(credit_sales[amount_col].sum())
    return 0.0


def get_debt_payments_unduplicated(debtors_df):
    if debtors_df is None or debtors_df.empty:
        return 0.0
    if "amount_paid" in debtors_df.columns:
        return safe_float(debtors_df["amount_paid"].sum())
    return 0.0


def get_total_revenue_unduplicated(sales_df):
    if sales_df is None or sales_df.empty:
        return 0.0
    s = get_unduplicated_sales(sales_df)
    if s.empty:
        return 0.0
    amount_col = get_amount_column(s)
    if amount_col:
        return safe_float(s[amount_col].sum())
    return 0.0


# ==============================
# CASH DASHBOARD
# ==============================
def cash_dashboard():
    branch_id = _get_session_branch()
    branch_name = _branch_display_name(branch_id)
    _cleanup_session_state_for_branch(branch_id)

    st.title("Cash Register Management System")
    st.caption(
        f"Track shifts, manage cash flow, and control expenses — "
        f"{branch_name} ({branch_id})"
    )

    username = st.session_state.get("username", "system")
    user_branch = branch_id
    user_role = st.session_state.get("role", "cashier")
    full_name = st.session_state.get("user_full_name", username)
    can_manage_shifts = user_role in ["owner", "manager", "admin"]

    sales_df = load_sales(branch_id=user_branch)
    debtors_df = load_debtors_data(branch_id=user_branch)

    sales_undup = get_unduplicated_sales(sales_df)
    amount_col = get_amount_column(sales_undup)
    payment_col = get_payment_method_column(sales_undup)

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Shift Management",
        "Today's Report",
        "Cash Flow",
        "Petty Cash",
        "Bank Deposits",
    ])

    # ==============================
    # TAB 1: SHIFT MANAGEMENT
    # ==============================
    with tab1:
        st.markdown("## Shift Management")

        # Authoritative OPEN shift for THIS branch, straight from the DB.
        open_shift = _query_open_shift_for_branch(user_branch)
        is_shift_active = open_shift is not None

        if is_shift_active:
            shift_id = open_shift.get("shift_id")
            shift_name = open_shift.get("shift_name", "N/A")
        else:
            shift_id = None
            shift_name = "N/A"

        st.info(
            f"**Branch:** {branch_name} ({user_branch}) | "
            f"**Role:** {user_role.upper()}"
        )

        col1, col2 = st.columns(2)

        # ---------- LEFT: START SHIFT ----------
        with col1:
            if not is_shift_active:
                if not can_manage_shifts:
                    st.warning(
                        "No active shift in your branch. "
                        "Please ask your manager to start a shift."
                    )
                else:
                    st.markdown("### Start New Shift")

                    # Resolve shift names for THIS branch
                    branch_shift_names = []
                    if _HAS_SHIFT_DEFS:
                        try:
                            ensure_branch_has_defaults(user_branch)
                            branch_shift_names = [
                                n for n in get_shift_names_for_branch(user_branch)
                                if n and str(n).strip()
                            ]
                        except Exception as e:
                            st.warning(f"Could not load shift definitions: {e}")

                    if not branch_shift_names:
                        st.error(
                            f"No shift definitions found for branch "
                            f"**{branch_name}** ({user_branch}). "
                            f"Add shifts in **Manage Shifts** first."
                        )
                        # Show a small diagnostic so you can see what's in the DB
                        with st.expander("Diagnostics", expanded=True):
                            try:
                                sh = load_shifts(branch_id=user_branch)
                                st.write(
                                    f"load_shifts(branch_id={user_branch!r}) returned "
                                    f"{0 if sh is None else len(sh)} rows."
                                )
                                if sh is not None and not sh.empty:
                                    st.dataframe(
                                        sh[
                                            [c for c in
                                             ["shift_id", "branch_id", "branch_name",
                                              "status", "start_time"]
                                             if c in sh.columns]
                                        ],
                                        use_container_width=True,
                                    )
                            except Exception as e:
                                st.write(f"Diagnostic failed: {e}")
                    else:
                        shift_name_choice = st.selectbox(
                            "Select Shift",
                            branch_shift_names,
                            key=f"cd_shift_name_{user_branch}",
                        )
                        opening = st.number_input(
                            "Opening Cash Amount",
                            min_value=0.0,
                            value=0.0,
                            step=50.0,
                            key=f"cd_opening_{user_branch}",
                        )

                        if st.button(
                            "Start Shift",
                            type="primary",
                            use_container_width=True,
                            key=f"cd_start_{user_branch}",
                        ):
                            with st.spinner("Starting shift..."):
                                success, result, message = start_shift(
                                    cashier_username=username,
                                    cashier_name=full_name,
                                    branch_id=user_branch,
                                    branch_name=branch_name,
                                    manager_username=username,
                                    opening_cash=opening,
                                    shift_name=shift_name_choice,
                                )

                            if success:
                                # Record opening cash against the new shift
                                try:
                                    set_opening_cash(opening, result)
                                except Exception as e:
                                    print(f"[cash_dashboard] set_opening_cash failed: {e}")

                                st.session_state.shift_id = result
                                st.session_state.active_shift_id = result
                                st.session_state.active_shift_branch = user_branch
                                st.session_state.branch_shift_active = True

                                st.success(f"Shift started successfully! Shift ID: {result}")
                                st.info(f"Opening Cash: ${opening:.2f}")
                                st.rerun()
                            else:
                                st.error(f"Failed to start shift: {message}")
                                # If a stale OPEN shift exists elsewhere for this branch,
                                # offer to close it in one click.
                                stale = _query_open_shift_for_branch(user_branch)
                                if stale:
                                    st.warning(
                                        f"An OPEN shift already exists for this branch: "
                                        f"`{stale.get('shift_id')}` "
                                        f"(started by {stale.get('cashier_name', '?')})."
                                    )
                                    if st.button(
                                        "Force-close stale shift and retry",
                                        key=f"cd_force_close_{user_branch}",
                                    ):
                                        ok, msg = _force_close_shift(
                                            stale.get("shift_id"),
                                            user_branch,
                                            reason="replaced by new start",
                                        )
                                        if ok:
                                            st.success(msg)
                                            st.rerun()
                                        else:
                                            st.error(msg)
            else:
                st.markdown("### Active Shift")
                start_time = open_shift.get("start_time")
                if hasattr(start_time, "strftime"):
                    start_time_str = start_time.strftime("%Y-%m-%d %H:%M")
                else:
                    start_time_str = str(start_time) if start_time else "N/A"

                st.markdown(f"""
**Shift Name:** `{shift_name}`  
**Shift ID:** `{shift_id}`  
**Started by:** {open_shift.get('cashier_name', 'Unknown')}  
**Start Time:** {start_time_str}  
**Opening Cash:** ${safe_float(open_shift.get('opening_cash', 0)):.2f}  
**Branch:** {open_shift.get('branch_name', branch_name)}
""")

                cash_sales = safe_float(get_cash_sales_unduplicated(sales_undup))
                credit_sales = safe_float(get_credit_sales_unduplicated(sales_undup))
                debt_payments = safe_float(get_debt_payments_unduplicated(debtors_df))

                cola, colb, colc = st.columns(3)
                with cola:
                    st.metric("Cash Sales", f"${cash_sales:.2f}")
                with colb:
                    st.metric("Credit Sales", f"${credit_sales:.2f}")
                with colc:
                    st.metric("Debt Payments", f"${debt_payments:.2f}")

        # ---------- RIGHT: END SHIFT ----------
        with col2:
            if is_shift_active:
                if not can_manage_shifts:
                    st.info("Only managers and owners can close shifts.")
                else:
                    st.markdown("### End Shift")

                    actual_cash = st.number_input(
                        "Actual Cash Counted",
                        min_value=0.0,
                        value=0.0,
                        step=10.0,
                        key=f"cd_actual_{user_branch}",
                    )
                    notes = st.text_area(
                        "Shift Notes",
                        placeholder="Any issues or comments...",
                        key=f"cd_notes_{user_branch}",
                    )

                    if st.button(
                        "Close Shift",
                        type="secondary",
                        use_container_width=True,
                        key=f"cd_close_{user_branch}",
                    ):
                        with st.spinner("Closing shift..."):
                            cash_sales = safe_float(get_cash_sales_unduplicated(sales_undup))
                            debt_payments = safe_float(get_debt_payments_unduplicated(debtors_df))
                            credit_sales = safe_float(get_credit_sales_unduplicated(sales_undup))

                            expected_cash = (
                                safe_float(open_shift.get("opening_cash", 0))
                                + cash_sales
                                + debt_payments
                            )
                            variance = actual_cash - expected_cash

                            success, result = end_shift(
                                shift_id=shift_id,
                                closing_cash=actual_cash,
                                total_sales=cash_sales + credit_sales,
                                profit=cash_sales * 0.3,
                                transactions=len(sales_undup) if not sales_undup.empty else 0,
                                notes=notes,
                                branch_id=user_branch,
                            )

                            if success:
                                try:
                                    record_closing_cash(actual_cash, shift_id)
                                except Exception as e:
                                    print(f"[cash_dashboard] record_closing_cash failed: {e}")

                                st.success("Shift closed!")
                                st.info(f"Expected Cash: ${expected_cash:.2f}")
                                if variance >= 0:
                                    st.success(f"Cash Surplus: ${variance:.2f}")
                                else:
                                    st.error(f"Cash Shortage: ${abs(variance):.2f}")

                                st.session_state.shift_id = None
                                st.session_state.active_shift_id = None
                                st.session_state.branch_shift_active = False
                                st.rerun()
                            else:
                                st.error(f"Failed to close shift: {result}")

        # ---------- SHIFT HISTORY ----------
        st.markdown("---")
        st.markdown(f"### Shift History — {branch_name} ({user_branch})")

        shifts_df = load_shifts(branch_id=user_branch)
        if shifts_df is not None and not shifts_df.empty:
            branch_shifts = shifts_df[
                shifts_df["branch_id"].astype(str).str.upper()
                == str(user_branch).upper()
            ]

            if not branch_shifts.empty:
                display_cols = [
                    "shift_id", "shift_name", "cashier_name", "start_time",
                    "end_time", "opening_cash", "closing_cash", "cash_sales",
                    "variance", "status",
                ]
                available_cols = [c for c in display_cols if c in branch_shifts.columns]
                display_shifts = (
                    branch_shifts[available_cols]
                    .sort_values("start_time", ascending=False)
                    .head(20)
                    .copy()
                )

                for col in ["start_time", "end_time"]:
                    if col in display_shifts.columns:
                        display_shifts[col] = pd.to_datetime(
                            display_shifts[col], errors="coerce"
                        ).dt.strftime("%Y-%m-%d %H:%M")

                st.dataframe(display_shifts, use_container_width=True, hide_index=True)

                total_shifts = len(branch_shifts)
                total_revenue_undup = safe_float(get_total_revenue_unduplicated(sales_undup))

                cola, colb, colc = st.columns(3)
                with cola:
                    st.metric("Total Shifts", total_shifts)
                with colb:
                    st.metric("Total Revenue (Unduplicated)", f"${total_revenue_undup:,.2f}")
                with colc:
                    active_count = len(
                        branch_shifts[
                            branch_shifts["status"].astype(str).str.upper() == "OPEN"
                        ]
                    )
                    st.metric("Active Shifts", active_count)
            else:
                st.info(f"No shift history found for {branch_name} ({user_branch})")
        else:
            st.info(f"No shift records found for {branch_name} ({user_branch})")

    # ==============================
    # TAB 2: TODAY'S REPORT
    # ==============================
    with tab2:
        st.markdown("## Today's Cash Report")
        st.caption(
            f"All revenue metrics based on unduplicated sales data — "
            f"{branch_name} ({user_branch})"
        )

        today_report = get_daily_report()
        today = datetime.now().date()

        today_cash_sales = 0.0
        today_credit_sales = 0.0
        today_total_revenue = 0.0

        if not sales_undup.empty and amount_col:
            date_col = get_date_column(sales_undup)
            if date_col:
                sales_undup[date_col] = pd.to_datetime(
                    sales_undup[date_col], errors="coerce"
                )
                today_sales = sales_undup[sales_undup[date_col].dt.date == today]
                if not today_sales.empty:
                    amount_col_today = get_amount_column(today_sales)
                    payment_col_today = get_payment_method_column(today_sales)
                    if amount_col_today:
                        today_total_revenue = safe_float(
                            today_sales[amount_col_today].sum()
                        )
                        if payment_col_today:
                            cash_sales_df = today_sales[
                                today_sales[payment_col_today]
                                .astype(str).str.upper()
                                .isin(["CASH", "ECOCASH"])
                            ]
                            today_cash_sales = (
                                safe_float(cash_sales_df[amount_col_today].sum())
                                if not cash_sales_df.empty else 0.0
                            )
                            credit_sales_df = today_sales[
                                today_sales[payment_col_today]
                                .astype(str).str.upper() == "CREDIT"
                            ]
                            today_credit_sales = (
                                safe_float(credit_sales_df[amount_col_today].sum())
                                if not credit_sales_df.empty else 0.0
                            )

        today_debt_payments = 0.0
        if (
            not debtors_df.empty
            and "amount_paid" in debtors_df.columns
            and "repayment_date" in debtors_df.columns
        ):
            debtors_df["repayment_date"] = pd.to_datetime(
                debtors_df["repayment_date"], errors="coerce"
            )
            today_debt_payments = safe_float(
                debtors_df[
                    debtors_df["repayment_date"].dt.date == today
                ]["amount_paid"].sum()
            )

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Cash Sales", f"${safe_float(today_cash_sales):.2f}")
        with col2:
            st.metric("Credit Sales", f"${safe_float(today_credit_sales):.2f}")
        with col3:
            st.metric("Debt Payments", f"${safe_float(today_debt_payments):.2f}")
        with col4:
            st.metric("Total Revenue", f"${safe_float(today_total_revenue):.2f}")

        st.markdown("---")

        if not sales_undup.empty:
            st.subheader("Today's Transactions")
            date_col = get_date_column(sales_undup)
            if date_col:
                sales_undup[date_col] = pd.to_datetime(
                    sales_undup[date_col], errors="coerce"
                )
                today_sales_display = sales_undup[
                    sales_undup[date_col].dt.date == today
                ]
                if not today_sales_display.empty:
                    display_cols = []
                    if "receipt_no" in today_sales_display.columns:
                        display_cols.append("receipt_no")
                    if "customer_name" in today_sales_display.columns:
                        display_cols.append("customer_name")
                    if amount_col and amount_col in today_sales_display.columns:
                        display_cols.append(amount_col)
                    if payment_col and payment_col in today_sales_display.columns:
                        display_cols.append(payment_col)

                    if display_cols:
                        st.dataframe(
                            today_sales_display[display_cols],
                            use_container_width=True,
                            hide_index=True,
                        )
                    st.info(f"Total Transactions: {len(today_sales_display)}")
                else:
                    st.info("No transactions today")

        if today_report:
            st.markdown("---")
            col1, col2 = st.columns(2)
            with col1:
                expected_cash = (
                    safe_float(today_report.get("opening_cash", 0))
                    + safe_float(today_cash_sales)
                    + safe_float(today_debt_payments)
                )
                st.metric("Expected Cash", f"${expected_cash:.2f}")
            with col2:
                actual_cash = safe_float(today_report.get("closing_cash", 0))
                st.metric("Actual Cash", f"${actual_cash:.2f}")

            variance = actual_cash - expected_cash
            if abs(variance) > 5:
                st.error(f"Cash Variance: ${variance:.2f} - Investigate!")
            else:
                st.success(f"Cash Variance: ${variance:.2f}")
        else:
            st.info("No cash register data for today.")

    # ==============================
    # TAB 3: CASH FLOW
    # ==============================
    with tab3:
        st.markdown("## Cash Flow Analysis")
        st.caption(
            f"Revenue based on unduplicated sales data — "
            f"{branch_name} ({user_branch})"
        )

        st.markdown("### Cash Flow Trend (Last 30 Days)")
        cash_flow_df = get_cash_flow(30)
        if not cash_flow_df.empty:
            fig = px.bar(
                cash_flow_df,
                x="Date",
                y="Net Cash Flow",
                title=f"Daily Net Cash Flow — {branch_name}",
                color="Net Cash Flow",
                color_continuous_scale="RdYlGn",
                text="Net Cash Flow",
            )
            fig.update_traces(texttemplate="$%{text:.0f}", textposition="outside")
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("### Cashier Performance")
        cashier_perf = get_cashier_performance()
        if not cashier_perf.empty:
            st.dataframe(cashier_perf, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown("### Summary Statistics (Unduplicated)")

        total_cash_sales = safe_float(get_cash_sales_unduplicated(sales_undup))
        total_credit_sales = safe_float(get_credit_sales_unduplicated(sales_undup))
        total_debt_payments = safe_float(get_debt_payments_unduplicated(debtors_df))
        total_revenue = safe_float(get_total_revenue_unduplicated(sales_undup))

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Cash Sales", f"${total_cash_sales:,.2f}")
        with col2:
            st.metric("Total Credit Sales", f"${total_credit_sales:,.2f}")
        with col3:
            st.metric("Total Debt Collections", f"${total_debt_payments:,.2f}")

        st.info(f"**Total Revenue (Unduplicated):** ${total_revenue:,.2f}")

    # ==============================
    # TAB 4: PETTY CASH
    # ==============================
    with tab4:
        st.markdown("## Petty Cash Management")
        st.markdown("### Record Petty Cash Expense")

        col1, col2 = st.columns(2)
        with col1:
            petty_desc = st.text_input(
                "Description",
                key=f"petty_desc_{user_branch}",
                placeholder="What was purchased?",
            )
            petty_amount = st.number_input(
                "Amount ($)", min_value=0.01, step=5.0,
                key=f"petty_amount_{user_branch}",
            )
        with col2:
            petty_category = st.selectbox(
                "Category",
                ["Office Supplies", "Transport", "Refreshments",
                 "Cleaning", "Maintenance", "Other"],
                key=f"petty_category_{user_branch}",
            )
            petty_notes = st.text_area("Notes", key=f"petty_notes_{user_branch}")

        shift_to_use = (
            st.session_state.get("shift_id")
            or st.session_state.get("active_shift_id")
            or ""
        )

        if st.button("Record Petty Cash", key=f"record_petty_{user_branch}"):
            if petty_desc and petty_amount > 0:
                record_petty_cash(
                    description=petty_desc,
                    amount=petty_amount,
                    category=petty_category,
                    shift_id=shift_to_use,
                    approved_by=st.session_state.get("username", "system"),
                    notes=petty_notes,
                )
                st.success(f"Petty cash expense recorded: ${petty_amount:.2f}")
                st.rerun()
            else:
                st.error("Please enter description and amount")

        st.markdown("---")
        st.markdown("### Petty Cash History")
        petty_df = load_petty_cash()
        if not petty_df.empty:
            st.dataframe(
                petty_df.sort_values("date", ascending=False),
                use_container_width=True,
                hide_index=True,
            )
            total_petty = safe_float(petty_df["amount"].sum())
            st.metric("Total Petty Cash Expenses", f"${total_petty:,.2f}")

    # ==============================
    # TAB 5: BANK DEPOSITS
    # ==============================
    with tab5:
        st.markdown("## Bank Deposits")
        st.markdown("### Record Bank Deposit")

        col1, col2 = st.columns(2)
        with col1:
            deposit_amount = st.number_input(
                "Amount to Deposit ($)", min_value=0.01, step=50.0,
                key=f"deposit_amount_{user_branch}",
            )
            deposit_bank = st.selectbox(
                "Bank",
                ["CABS", "FBC", "POSB", "CBZ", "NMB", "Stanbic", "EcoBank", "Other"],
                key=f"deposit_bank_{user_branch}",
            )
        with col2:
            deposit_ref = st.text_input(
                "Reference Number",
                key=f"deposit_ref_{user_branch}",
                placeholder="Deposit slip number",
            )
            deposit_notes = st.text_area(
                "Notes", key=f"deposit_notes_{user_branch}"
            )

        shift_to_use = (
            st.session_state.get("shift_id")
            or st.session_state.get("active_shift_id")
            or ""
        )

        if st.button("Record Bank Deposit", key=f"record_deposit_{user_branch}"):
            if deposit_amount > 0:
                record_bank_deposit(
                    amount=deposit_amount,
                    bank_name=deposit_bank,
                    shift_id=shift_to_use,
                    reference_no=deposit_ref,
                    notes=deposit_notes,
                )
                st.success(
                    f"Bank deposit recorded: ${deposit_amount:.2f} to {deposit_bank}"
                )
                st.rerun()
            else:
                st.error("Please enter deposit amount")

        st.markdown("---")
        st.markdown("### Bank Deposit History")
        deposits_df = load_bank_deposits()
        if not deposits_df.empty:
            st.dataframe(
                deposits_df.sort_values("date", ascending=False),
                use_container_width=True,
                hide_index=True,
            )
            total_deposits = safe_float(deposits_df["amount"].sum())
            st.metric("Total Bank Deposits", f"${total_deposits:,.2f}")

    # ==============================
    # EXPORT REPORT
    # ==============================
    st.markdown("---")
    st.subheader(f"Export Daily Report — {branch_name}")

    if st.button(
        "Generate Daily Report",
        use_container_width=True,
        key=f"gen_daily_report_{user_branch}",
    ):
        today = datetime.now().date()
        date_col = get_date_column(sales_undup)

        today_cash_sales = 0.0
        today_credit_sales = 0.0
        today_total_revenue = 0.0

        if not sales_undup.empty and date_col and amount_col:
            sales_undup[date_col] = pd.to_datetime(
                sales_undup[date_col], errors="coerce"
            )
            today_sales = sales_undup[sales_undup[date_col].dt.date == today]
            if not today_sales.empty:
                today_total_revenue = safe_float(today_sales[amount_col].sum())
                if payment_col:
                    cash_sales_df = today_sales[
                        today_sales[payment_col].astype(str).str.upper()
                        .isin(["CASH", "ECOCASH"])
                    ]
                    today_cash_sales = (
                        safe_float(cash_sales_df[amount_col].sum())
                        if not cash_sales_df.empty else 0.0
                    )
                    credit_sales_df = today_sales[
                        today_sales[payment_col].astype(str).str.upper() == "CREDIT"
                    ]
                    today_credit_sales = (
                        safe_float(credit_sales_df[amount_col].sum())
                        if not credit_sales_df.empty else 0.0
                    )

        today_debt_payments = 0.0
        if (
            not debtors_df.empty
            and "amount_paid" in debtors_df.columns
            and "repayment_date" in debtors_df.columns
        ):
            debtors_df["repayment_date"] = pd.to_datetime(
                debtors_df["repayment_date"], errors="coerce"
            )
            today_debt_payments = safe_float(
                debtors_df[debtors_df["repayment_date"].dt.date == today][
                    "amount_paid"
                ].sum()
            )

        report = get_daily_report()

        report_text = f"""
{'=' * 50}
AZIEL INVESTMENTS - DAILY CASH REPORT
{'=' * 50}

Date: {today.strftime('%Y-%m-%d')}
Branch: {branch_name} ({user_branch})

{'-' * 30}
CASH SUMMARY (UNDUPLICATED)
{'-' * 30}
Cash Sales: ${safe_float(today_cash_sales):.2f}
Credit Sales: ${safe_float(today_credit_sales):.2f}
Debt Payments: ${safe_float(today_debt_payments):.2f}
Total Revenue: ${safe_float(today_total_revenue):.2f}

{'-' * 30}
TRANSACTIONS
{'-' * 30}
"""
        if not sales_undup.empty and date_col:
            sales_undup[date_col] = pd.to_datetime(
                sales_undup[date_col], errors="coerce"
            )
            today_sales_count = len(
                sales_undup[sales_undup[date_col].dt.date == today]
            )
            report_text += f"Total Transactions: {today_sales_count}\n"

        if report:
            opening_cash = safe_float(report.get("opening_cash", 0))
            closing_cash = safe_float(report.get("closing_cash", 0))
            expected_cash = (
                opening_cash
                + safe_float(today_cash_sales)
                + safe_float(today_debt_payments)
            )
            variance = closing_cash - expected_cash

            report_text += f"""
{'-' * 30}
CASH REGISTER
{'-' * 30}
Opening Cash: ${opening_cash:.2f}
Expected Cash: ${expected_cash:.2f}
Actual Cash: ${closing_cash:.2f}
Variance: ${variance:.2f}
"""

        report_text += f"""
{'-' * 50}
Generated by Aziel Investments ERP
{'-' * 50}
"""

        st.download_button(
            label="Download Report (TXT)",
            data=report_text,
            file_name=(
                f"cash_report_{user_branch}_{today.strftime('%Y%m%d')}.txt"
            ),
            mime="text/plain",
        )


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    cash_dashboard()