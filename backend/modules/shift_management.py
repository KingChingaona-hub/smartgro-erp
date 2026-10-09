# backend/modules/shift_management.py
# Branch-aware shift definitions + owner CRUD per branch.

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import re

from backend.core.db_adapter import (
    load_shifts, save_shifts, start_shift, end_shift,
    get_all_active_shifts, get_active_shifts_by_branch,
    get_current_branch, load_cash, get_cash_summary,
    load_sales, load_products, load_users, load_branches,
)
from backend.core.shift_definitions import (
    load_shift_definitions,
    add_shift_definition,
    update_shift_definition,
    delete_shift_definition,
    get_shift_names_for_branch,
    ensure_branch_has_defaults,
)

# ==============================
# CONSTANTS
# ==============================
COMPANY_NAME = "AZIEL INVESTMENTS"
COMPANY_ADDRESS = "Retreat Park, Harare"
COMPANY_PHONE = "+263 78 290 5853"
COMPANY_EMAIL = "info@azielinvestments.co.zw"

WHATSAPP_NUMBER = "263782905853"
EMAIL_NOTIFICATION = "kingtimothy495@gmail.com"


# ==============================
# SESSION CONTEXT HELPERS
# ==============================
def _get_session_branch():
    """
    Authoritative branch for the current session.
    Prefers `current_branch_code` over `user_branch`.
    """
    return (
        st.session_state.get("current_branch_code")
        or st.session_state.get("user_branch")
        or "HO"
    )


def _is_multi_branch_user():
    """True for owner / manager / admin."""
    return st.session_state.get("role", "cashier") in ("owner", "manager", "admin")


# ==============================
# SAFE TIME FORMATTERS
# ==============================
def safe_format_time(time_val):
    """
    Safely format a time value to string.

    Returns "N/A" for None, NaT, NaN, or anything that has no strftime
    and no sensible string representation. This is the single guard that
    prevents `NaTType does not support strftime` from crashing the page.
    """
    if time_val is None:
        return "N/A"

    # pandas NaT or numpy NaN
    try:
        if pd.isna(time_val):
            return "N/A"
    except Exception:
        pass

    if isinstance(time_val, pd.Timestamp):
        try:
            return time_val.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return "N/A"

    if isinstance(time_val, datetime):
        try:
            return time_val.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return "N/A"

    time_str = str(time_val)
    if not time_str or time_str.lower() == "nat":
        return "N/A"
    return time_str[:16] if time_str else "N/A"


def _fmt_time(value, fmt="%Y-%m-%d %H:%M"):
    """
    Format a datetime/Timestamp/string, returning "" for NaT/None/invalid.
    Used by tables so an open shift's empty end_time renders as blank
    instead of raising.
    """
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    if hasattr(value, "strftime"):
        try:
            return value.strftime(fmt)
        except Exception:
            return ""
    s = str(value)
    if not s or s.lower() == "nat":
        return ""
    return s[:16]


def _normalize_time(value, default="06:00"):
    """
    Accept common time formats and return a Postgres-friendly 'HH:MM'.

    Handles: '6.00', '6:00', '06:00', '0600', '6', 6, '6:0', '06:00:00'.
    Falls back to `default` if it can't parse.
    """
    if value is None:
        return default

    # If already a time object from st.time_input
    if hasattr(value, "strftime"):
        try:
            return value.strftime("%H:%M")
        except Exception:
            pass

    s = str(value).strip()
    if not s:
        return default

    # Drop seconds if present
    if s.count(":") == 2:
        s = s.rsplit(":", 1)[0]

    # Convert dots to colons: '6.00' -> '6:00'
    s = s.replace(".", ":")

    # If no separator at all, assume HHMM: '0600' -> '06:00'
    if ":" not in s:
        digits = re.sub(r"\D", "", s)
        if len(digits) == 3:      # '600' -> 6:00
            digits = "0" + digits
        if len(digits) == 4:      # '0600'
            s = f"{digits[:2]}:{digits[2:]}"
        else:
            return default

    try:
        hh, mm = s.split(":")[:2]
        hh = int(hh)
        mm = int(mm)
    except (ValueError, TypeError):
        return default

    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        return default

    return f"{hh:02d}:{mm:02d}"


# ==============================
# NOTIFICATION HELPERS
# ==============================
def send_whatsapp_message(phone_number, message):
    """Build a WhatsApp link for the given phone and message."""
    try:
        phone = phone_number.replace("+", "").replace(" ", "")
        if not phone.startswith("263"):
            phone = "263" + phone.lstrip("0")
        return f"https://wa.me/{phone}?text={message.replace(' ', '%20').replace(chr(10), '%0A')}"
    except Exception as e:
        print(f"Error sending WhatsApp: {e}")
        return None


def send_email_notification(to_email, subject, body):
    """Placeholder email sender — kept as in the original file."""
    try:
        print(f"Email would be sent to: {to_email}")
        print(f"Subject: {subject}")
        print(f"Body: {body}")
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False


# ==============================
# SHIFT REPORT
# ==============================
def generate_shift_report(shift_data, shift_summary):
    report = f"""
{'='*60}
{COMPANY_NAME} - SHIFT REPORT
{'='*60}

Shift ID: {shift_data.get('shift_id', 'N/A')}
Shift Name: {shift_data.get('shift_name', 'N/A')}
Cashier: {shift_data.get('cashier_name', 'N/A')}
Branch: {shift_data.get('branch_name', 'N/A')}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{'-'*40}
SHIFT SUMMARY
{'-'*40}
Start Time: {safe_format_time(shift_data.get('start_time'))}
End Time: {safe_format_time(shift_data.get('end_time', datetime.now()))}
Duration: {shift_summary.get('duration', 'N/A')}
Status: {shift_data.get('status', 'N/A')}

{'-'*40}
FINANCIAL SUMMARY
{'-'*40}
Opening Cash: ${shift_summary.get('opening_cash', 0):,.2f}
Total Revenue: ${shift_summary.get('total_revenue', 0):,.2f}
Total Profit: ${shift_summary.get('total_profit', 0):,.2f}
Cash Sales: ${shift_summary.get('cash_sales', 0):,.2f}
Credit Sales: ${shift_summary.get('credit_sales', 0):,.2f}
Debt Payments: ${shift_summary.get('debt_payments', 0):,.2f}
Expenses: ${shift_summary.get('expenses', 0):,.2f}

{'-'*40}
TRANSACTIONS
{'-'*40}
Total Transactions: {shift_summary.get('transactions', 0)}
Closing Cash: ${shift_summary.get('closing_cash', 0):,.2f}
Variance: ${shift_summary.get('variance', 0):,.2f}

{'-'*40}
NOTES
{'-'*40}
{shift_summary.get('notes', 'No notes')}

{'='*60}
End of Shift Report
{COMPANY_NAME} - {COMPANY_PHONE}
{'='*60}
"""
    return report


# ==============================
# BRANCH RESOLUTION FOR THIS PAGE
# ==============================
def _resolve_page_branch():
    """
    Decide which branch this page instance is looking at.

    - Owner / manager / admin: use the value of the branch selector stored
      in session state (defaults to their session branch).
    - Everyone else: their session branch, no selector.
    Returns (branch_id, branch_name, can_change).
    """
    session_branch = _get_session_branch()
    can_change = _is_multi_branch_user()

    if not can_change:
        return session_branch, _branch_name(session_branch), False

    selected = st.session_state.get("sm_selected_branch", session_branch)
    return selected, _branch_name(selected), True


def _branch_name(branch_id):
    try:
        df = load_branches()
        if df is None or df.empty:
            return branch_id
        match = df[df["branch_id"].astype(str).str.upper() == str(branch_id).upper()]
        if not match.empty:
            return match.iloc[0]["branch_name"]
    except Exception:
        pass
    return branch_id


# ==============================
# MAIN PAGE
# ==============================
def shift_management_page():
    """Main shift management page — branch-aware."""

    st.title("Shift Management")
    st.caption("Manage cashier shifts, track performance, and monitor activity")

    role = st.session_state.get("role", "cashier")
    user_branch = _get_session_branch()

    # ==========================================================
    # BRANCH SELECTOR (owners / managers only)
    # ==========================================================
    if _is_multi_branch_user():
        branches_df = load_branches()
        if branches_df is not None and not branches_df.empty:
            branch_ids = branches_df["branch_id"].tolist()
            branch_names = {b_id: _branch_name(b_id) for b_id in branch_ids}
            display_labels = [f"{branch_names[b]} ({b})" for b in branch_ids]

            default_id = st.session_state.get("sm_selected_branch", user_branch)
            default_idx = branch_ids.index(default_id) if default_id in branch_ids else 0

            col_a, col_b = st.columns([3, 2])
            with col_a:
                selected_label = st.selectbox(
                    "Viewing Branch",
                    options=display_labels,
                    index=default_idx,
                    key="sm_branch_selector",
                )
            chosen_id = branch_ids[display_labels.index(selected_label)]
            st.session_state["sm_selected_branch"] = chosen_id
            st.caption(f"You are viewing shifts for branch **{branch_names[chosen_id]}** ({chosen_id}).")

            # Ensure this branch has its default shift definitions seeded.
            # This is what makes the CRUD tab usable for branches that
            # currently have NO shifts at all.
            ensure_branch_has_defaults(chosen_id)
    else:
        st.caption(
            f"📍 You are viewing shifts for your branch: **{_branch_name(user_branch)}** ({user_branch})"
        )
        ensure_branch_has_defaults(user_branch)

    # Branch this page instance operates on
    page_branch_id, page_branch_name, can_change = _resolve_page_branch()

    # Load data — scoped by page branch
    shifts_df = load_shifts(branch_id=page_branch_id)
    if shifts_df is None:
        shifts_df = pd.DataFrame()

    active_shifts = get_active_shifts_by_branch(page_branch_id)
    if active_shifts is None:
        active_shifts = pd.DataFrame()

    # Session state
    if "show_end_shift" not in st.session_state:
        st.session_state.show_end_shift = False
    if "end_shift_id" not in st.session_state:
        st.session_state.end_shift_id = None
    if "shift_ended" not in st.session_state:
        st.session_state.shift_ended = False
    if "button_clicked" not in st.session_state:
        st.session_state.button_clicked = False
    if "shift_report" not in st.session_state:
        st.session_state.shift_report = None

    # ==========================================================
    # TABS
    # ==========================================================
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Active Shifts",
        "Shift History",
        "Shift Summary",
        "Shift Performance",
        "Manage Shifts",
    ])

    # ==========================================================
    # TAB 5: MANAGE SHIFTS  (owner / manager only)
    # ==========================================================
    with tab5:
        _manage_shifts_tab(page_branch_id, page_branch_name)

    # ==========================================================
    # SIDEBAR — Start Shift (owner / manager, scoped to page branch)
    # ==========================================================
    st.sidebar.header("Shift Controls")
    st.sidebar.info(f"**Branch:** {page_branch_name} ({page_branch_id})")
    st.sidebar.info(f"**Role:** {role.upper()}")

    if role in ("owner", "manager"):
        st.sidebar.subheader("Start New Shift")

        # Only show shift names that belong to THIS branch, and strip
        # any None / empty values so a bad seed can't render a broken form.
        branch_shift_names = [
            n for n in get_shift_names_for_branch(page_branch_id)
            if n and str(n).strip()
        ]

        if not branch_shift_names:
            st.sidebar.warning(
                f"No shift definitions found for branch **{page_branch_name}** "
                f"({page_branch_id}). Add shifts in the **Manage Shifts** tab first."
            )
        else:
            with st.sidebar.form(f"start_shift_form_{page_branch_id}"):
                shift_name = st.selectbox(
                    "Select Shift",
                    branch_shift_names,
                    key=f"shift_pick_{page_branch_id}",
                )

                cashier_username = st.text_input(
                    "Cashier Username",
                    value=st.session_state.get("username", ""),
                    key=f"cashier_username_{page_branch_id}",
                )
                cashier_name = st.text_input(
                    "Cashier Name",
                    value=st.session_state.get("full_name", ""),
                    key=f"cashier_name_{page_branch_id}",
                )
                manager_username = st.text_input(
                    "Manager Username",
                    value=st.session_state.get("username", ""),
                    key=f"manager_username_{page_branch_id}",
                )
                opening_cash = st.number_input(
                    "Opening Cash ($)", min_value=0.0, value=0.0, step=10.0,
                    key=f"opening_cash_{page_branch_id}",
                )

                submitted = st.form_submit_button("Start Shift", use_container_width=True)

                if submitted:
                    if not cashier_username or not cashier_name:
                        st.sidebar.error("Please enter cashier details")
                    else:
                        success, result, message = start_shift(
                            cashier_username,
                            cashier_name,
                            page_branch_id,
                            page_branch_name,
                            manager_username,
                            opening_cash,
                            shift_name,
                        )
                        if success:
                            st.sidebar.success(f"Shift started! ID: {result}")
                            st.rerun()
                        else:
                            st.sidebar.error(f"{message}")
    else:
        st.sidebar.info("Only managers and owners can start shifts.")
        st.sidebar.caption("Please ask your manager to start a shift.")

    # Sidebar list of active shifts for the page branch
    if not active_shifts.empty:
        st.sidebar.subheader("Active Shifts (this branch)")
        for _, shift in active_shifts.iterrows():
            start_time_str = safe_format_time(shift.get("start_time"))
            st.sidebar.info(
                f"**{shift.get('cashier_name', 'Unknown')}**\n"
                f"Shift: {shift.get('shift_id', 'N/A')}\n"
                f"Started: {start_time_str}\n"
                f"Opening: ${float(shift.get('opening_cash', 0) or 0):.2f}"
            )
    else:
        st.sidebar.info("No active shifts in this branch")

    # ==========================================================
    # TAB 1: ACTIVE SHIFTS
    # ==========================================================
    with tab1:
        _active_shifts_tab(active_shifts, page_branch_id, page_branch_name, role)

    # ==========================================================
    # TAB 2: SHIFT HISTORY
    # ==========================================================
    with tab2:
        _shift_history_tab(shifts_df, page_branch_id, page_branch_name)

    # ==========================================================
    # TAB 3: SHIFT SUMMARY
    # ==========================================================
    with tab3:
        _shift_summary_tab(shifts_df, page_branch_id, page_branch_name)

    # ==========================================================
    # TAB 4: SHIFT PERFORMANCE
    # ==========================================================
    with tab4:
        _shift_performance_tab(shifts_df, page_branch_id, page_branch_name)


# ==========================================================
# TAB IMPLEMENTATIONS
# ==========================================================
def _active_shifts_tab(active_shifts, page_branch_id, page_branch_name, role):
    st.markdown(f"## Active Shifts — {page_branch_name}")

    if active_shifts is None or active_shifts.empty:
        st.info("No active shifts in this branch")
        return

    shift_options = []
    for _, shift in active_shifts.iterrows():
        sid = shift.get("shift_id")
        cashier = shift.get("cashier_name", "Unknown")
        start_str = safe_format_time(shift.get("start_time"))
        shift_options.append(f"{sid} - {cashier} - Started: {start_str}")

    selected_option = st.selectbox(
        "Select Active Shift",
        options=shift_options,
        key=f"active_shift_select_{page_branch_id}",
    )

    if not selected_option:
        return

    shift_id = selected_option.split(" - ")[0]
    match = active_shifts[active_shifts["shift_id"] == shift_id]
    if match.empty:
        st.warning("Selected shift no longer exists")
        return

    shift_data = match.iloc[0]

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Cashier", shift_data.get("cashier_name", "N/A"))
        st.metric("Shift ID", shift_data.get("shift_id", "N/A"))
    with col2:
        st.metric("Started", safe_format_time(shift_data.get("start_time")))
        st.metric("Opening Cash", f"${float(shift_data.get('opening_cash', 0) or 0):.2f}")
    with col3:
        st.metric("Status", f"{shift_data.get('status', 'N/A')}")

        if role in ("owner", "manager"):
            if st.button(
                "End This Shift",
                type="primary",
                use_container_width=True,
                key=f"end_shift_btn_{page_branch_id}_{shift_id}",
            ):
                st.session_state.end_shift_id = shift_id
                st.session_state.show_end_shift = True
                st.rerun()

    # End Shift dialog
    if (
        st.session_state.get("show_end_shift", False)
        and st.session_state.get("end_shift_id") == shift_id
        and role in ("owner", "manager")
    ):
        _end_shift_dialog(shift_data, shift_id, page_branch_id)

    # Quick stats
    st.markdown("### Active Shifts Summary")
    total_cashiers = len(active_shifts)
    total_opening = active_shifts["opening_cash"].sum() if "opening_cash" in active_shifts.columns else 0
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Active Cashiers", total_cashiers)
    with col2:
        st.metric("Total Opening Cash", f"${float(total_opening or 0):,.2f}")


def _end_shift_dialog(shift_data, shift_id, page_branch_id):
    with st.expander("End Shift", expanded=True):
        col1, col2 = st.columns(2)

        with col1:
            sales_df = load_sales(branch_id=page_branch_id)
            cash_df = load_cash(branch_id=page_branch_id)

            shift_sales = (
                sales_df[sales_df["shift_id"] == shift_id]
                if not sales_df.empty and "shift_id" in sales_df.columns
                else pd.DataFrame()
            )
            shift_cash = (
                cash_df[cash_df["shift_id"] == shift_id]
                if not cash_df.empty and "shift_id" in cash_df.columns
                else pd.DataFrame()
            )

            total_sales = (
                float(shift_sales["final_total"].sum())
                if not shift_sales.empty and "final_total" in shift_sales.columns else 0
            )
            total_transactions = len(shift_sales)
            total_profit = (
                float(shift_sales["profit"].sum())
                if not shift_sales.empty and "profit" in shift_sales.columns else 0
            )

            if not shift_cash.empty and "type" in shift_cash.columns:
                cash_sales = float(shift_cash[shift_cash["type"] == "CASH_SALE"]["amount"].sum())
                credit_sales = float(shift_cash[shift_cash["type"] == "CREDIT_SALE"]["amount"].sum())
                debt_payments = float(shift_cash[shift_cash["type"] == "DEBT_PAYMENT"]["amount"].sum())
                expenses = float(shift_cash[shift_cash["type"] == "EXPENSE"]["amount"].sum())
            else:
                cash_sales = credit_sales = debt_payments = expenses = 0.0

            st.metric("Total Sales", f"${total_sales:,.2f}")
            st.metric("Total Profit", f"${total_profit:,.2f}")
            st.metric("Transactions", total_transactions)

        with col2:
            closing_cash = st.number_input(
                "Closing Cash ($)",
                min_value=0.0,
                value=float(shift_data.get("opening_cash", 0) or 0),
                step=10.0,
                key=f"closing_cash_{page_branch_id}_{shift_id}",
            )
            notes = st.text_area(
                "Shift Notes",
                placeholder="Any issues or comments about this shift...",
                key=f"shift_notes_{page_branch_id}_{shift_id}",
            )

            if st.button(
                "Confirm End Shift",
                type="primary",
                use_container_width=True,
                key=f"confirm_end_shift_{page_branch_id}_{shift_id}",
            ):
                success, message = end_shift(
                    shift_id,
                    closing_cash,
                    total_sales,
                    total_profit,
                    total_transactions,
                    notes,
                    branch_id=page_branch_id,
                )
                if success:
                    shift_summary = {
                        "opening_cash": shift_data.get("opening_cash", 0),
                        "total_revenue": total_sales,
                        "total_profit": total_profit,
                        "cash_sales": cash_sales,
                        "credit_sales": credit_sales,
                        "debt_payments": debt_payments,
                        "expenses": expenses,
                        "transactions": total_transactions,
                        "closing_cash": closing_cash,
                        "variance": closing_cash - (
                            float(shift_data.get("opening_cash", 0) or 0) + cash_sales + debt_payments - expenses
                        ),
                        "duration": (
                            f"{safe_format_time(shift_data.get('start_time'))} - "
                            f"{datetime.now().strftime('%Y-%m-%d %H:%M')}"
                        ),
                        "notes": notes,
                    }

                    report = generate_shift_report(shift_data.to_dict(), shift_summary)
                    st.session_state.shift_report = report

                    whatsapp_message = f"""
SHIFT ENDED - {COMPANY_NAME}

Shift: {shift_data.get('shift_id')}
Cashier: {shift_data.get('cashier_name')}
Branch: {shift_data.get('branch_name', page_branch_id)}
Revenue: ${total_sales:,.2f}
Profit: ${total_profit:,.2f}
Transactions: {total_transactions}
Closing Cash: ${closing_cash:,.2f}

Full report attached.
"""
                    whatsapp_link = send_whatsapp_message(WHATSAPP_NUMBER, whatsapp_message)
                    if whatsapp_link:
                        st.success(f"WhatsApp notification ready: [Click to send]({whatsapp_link})")

                    send_email_notification(
                        EMAIL_NOTIFICATION,
                        f"Shift Report - {shift_data.get('shift_id')} ({page_branch_id})",
                        report,
                    )

                    st.balloons()
                    st.success(message)

                    with st.expander("View Shift Report", expanded=True):
                        st.text(report)

                    st.session_state.show_end_shift = False
                    st.session_state.end_shift_id = None
                    st.session_state.shift_ended = True
                    st.rerun()
                else:
                    st.error(message)


def _shift_history_tab(shifts_df, page_branch_id, page_branch_name):
    st.markdown(f"## Shift History — {page_branch_name}")

    if shifts_df is None or shifts_df.empty:
        st.info(f"No shift history for branch {page_branch_name} yet.")
        return

    col1, col2, col3 = st.columns(3)

    with col1:
        date_range = st.date_input(
            "Date Range",
            value=(datetime.now() - timedelta(days=7), datetime.now()),
            key=f"shift_hist_date_range_{page_branch_id}",
        )

    with col2:
        if "cashier_name" in shifts_df.columns:
            cashiers = ["All"] + sorted(shifts_df["cashier_name"].dropna().unique().tolist())
        else:
            cashiers = ["All"]
        selected_cashier = st.selectbox(
            "Cashier", cashiers, key=f"shift_hist_cashier_{page_branch_id}"
        )

    with col3:
        selected_status = st.selectbox(
            "Status", ["All", "OPEN", "CLOSED"], key=f"shift_hist_status_{page_branch_id}"
        )

    filtered = shifts_df.copy()

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
        filtered["start_date"] = pd.to_datetime(
            filtered["start_time"], errors="coerce"
        ).dt.date
        filtered = filtered[
            (filtered["start_date"] >= start_date) & (filtered["start_date"] <= end_date)
        ]

    if selected_cashier != "All" and "cashier_name" in filtered.columns:
        filtered = filtered[filtered["cashier_name"] == selected_cashier]

    if selected_status != "All" and "status" in filtered.columns:
        filtered = filtered[filtered["status"] == selected_status]

    if filtered.empty:
        st.info("No shifts found matching the filters")
        return

    display = filtered.copy()

    # Safe formatting: NaT becomes ""
    for col in ("start_time", "end_time"):
        if col in display.columns:
            display[col] = display[col].apply(_fmt_time)

    display = display.rename(columns={
        "shift_id": "Shift ID",
        "shift_name": "Shift Name",
        "cashier_name": "Cashier",
        "cashier_username": "Username",
        "start_time": "Start Time",
        "end_time": "End Time",
        "opening_cash": "Opening Cash",
        "closing_cash": "Closing Cash",
        "total_revenue": "Revenue",
        "profit": "Profit",
        "transactions": "Transactions",
        "variance": "Variance",
        "status": "Status",
    })

    show_cols = ["Shift ID", "Shift Name", "Cashier", "Start Time", "End Time", "Revenue", "Transactions", "Status"]
    available_cols = [c for c in show_cols if c in display.columns]

    st.dataframe(
        display[available_cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Revenue": st.column_config.NumberColumn("Revenue", format="$%.2f"),
            "Opening Cash": st.column_config.NumberColumn("Opening Cash", format="$%.2f"),
            "Closing Cash": st.column_config.NumberColumn("Closing Cash", format="$%.2f"),
            "Variance": st.column_config.NumberColumn("Variance", format="$%.2f"),
            "Profit": st.column_config.NumberColumn("Profit", format="$%.2f"),
        },
    )

    st.markdown("### History Summary")
    total_shifts = len(filtered)
    total_revenue = float(filtered["total_revenue"].sum()) if "total_revenue" in filtered.columns else 0
    total_profit = float(filtered["profit"].sum()) if "profit" in filtered.columns else 0
    total_transactions = float(filtered["transactions"].sum()) if "transactions" in filtered.columns else 0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Shifts", total_shifts)
    with col2:
        st.metric("Total Revenue", f"${total_revenue:,.2f}")
    with col3:
        st.metric("Total Profit", f"${total_profit:,.2f}")
    with col4:
        st.metric("Transactions", f"{total_transactions:,.0f}")


def _shift_summary_tab(shifts_df, page_branch_id, page_branch_name):
    st.markdown(f"## Shift Summary — {page_branch_name}")
    st.caption(f"All figures below are for branch **{page_branch_name}** ({page_branch_id})")

    # Branch-scoped cash summary
    try:
        cash_summary = get_cash_summary(branch_id=page_branch_id)
    except TypeError:
        # Fallback for older db_adapter signatures that don't accept branch_id
        cash_summary = get_cash_summary()

    if cash_summary:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Opening Cash", f"${cash_summary.get('opening_cash', 0):,.2f}")
        with col2:
            st.metric("Cash Sales", f"${cash_summary.get('cash_sales', 0):,.2f}")
        with col3:
            st.metric("Credit Sales", f"${cash_summary.get('credit_sales', 0):,.2f}")
        with col4:
            st.metric("Total Revenue", f"${cash_summary.get('total_revenue', 0):,.2f}")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Expenses", f"${cash_summary.get('expenses', 0):,.2f}")
        with col2:
            st.metric("Deposits", f"${cash_summary.get('deposits', 0):,.2f}")
        with col3:
            st.metric("Transactions", cash_summary.get("transactions_count", 0))
        with col4:
            st.metric("Variance", f"${cash_summary.get('variance', 0):,.2f}")

    st.markdown("### Daily Shift Performance")

    if shifts_df is None or shifts_df.empty:
        st.info("No shift data for this branch yet")
        return

    copy = shifts_df.copy()
    copy["date"] = pd.to_datetime(copy["start_time"], errors="coerce").dt.date
    daily = copy.groupby("date").agg({
        "total_revenue": "sum",
        "profit": "sum",
        "transactions": "sum",
    }).reset_index()

    if daily.empty:
        st.info("No daily summary available")
        return

    fig = px.line(
        daily,
        x="date",
        y=["total_revenue", "profit"],
        title=f"Daily Revenue and Profit — {page_branch_name}",
        labels={"value": "Amount ($)", "date": "Date", "variable": "Metric"},
    )
    fig.update_layout(height=350)
    st.plotly_chart(fig, use_container_width=True)


def _shift_performance_tab(shifts_df, page_branch_id, page_branch_name):
    st.markdown(f"## Shift Performance — {page_branch_name}")

    if shifts_df is None or shifts_df.empty or "cashier_name" not in shifts_df.columns:
        st.info("No performance data for this branch")
        return

    cashier_perf = shifts_df.groupby("cashier_name").agg({
        "shift_id": "count",
        "total_revenue": "sum",
        "profit": "sum",
        "transactions": "sum",
    }).reset_index()

    cashier_perf.columns = ["Cashier", "Shifts", "Total Revenue", "Total Profit", "Transactions"]
    cashier_perf["Avg Revenue/Shift"] = cashier_perf["Total Revenue"] / cashier_perf["Shifts"].replace(0, 1)
    cashier_perf["Avg Profit/Shift"] = cashier_perf["Total Profit"] / cashier_perf["Shifts"].replace(0, 1)
    cashier_perf = cashier_perf.sort_values("Total Revenue", ascending=False)

    st.markdown("### Cashier Performance Ranking")

    st.dataframe(
        cashier_perf,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Total Revenue": st.column_config.NumberColumn("Total Revenue", format="$%.2f"),
            "Total Profit": st.column_config.NumberColumn("Total Profit", format="$%.2f"),
            "Avg Revenue/Shift": st.column_config.NumberColumn("Avg Revenue/Shift", format="$%.2f"),
            "Avg Profit/Shift": st.column_config.NumberColumn("Avg Profit/Shift", format="$%.2f"),
        },
    )

    col1, col2 = st.columns(2)
    with col1:
        fig = px.bar(
            cashier_perf.head(10),
            x="Cashier", y="Total Revenue",
            title=f"Top Cashiers by Revenue — {page_branch_name}",
            color="Total Revenue", color_continuous_scale="Greens",
            text="Total Revenue",
        )
        fig.update_traces(texttemplate="$%{text:.2f}", textposition="outside")
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = px.bar(
            cashier_perf.head(10),
            x="Cashier", y="Transactions",
            title=f"Top Cashiers by Transactions — {page_branch_name}",
            color="Transactions", color_continuous_scale="Blues",
            text="Transactions",
        )
        fig.update_traces(texttemplate="%{text}", textposition="outside")
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)


# ==========================================================
# TAB 5: MANAGE SHIFTS (owner / manager only)
# ==========================================================
def _manage_shifts_tab(page_branch_id, page_branch_name):
    """
    Full CRUD for shift definitions in the selected branch.
    """
    st.markdown("## Manage Shifts")
    st.caption(
        "Add, edit, or remove shift definitions for the branch shown above. "
        "Only owners and managers can make changes here."
    )

    role = st.session_state.get("role", "cashier")

    defs_df = load_shift_definitions(branch_id=page_branch_id, include_inactive=True)

    if defs_df is None:
        defs_df = pd.DataFrame()

    # ---------- VIEW (everyone who can reach this tab) ----------
    st.markdown(f"### Current Shifts — {page_branch_name}")
    if defs_df.empty:
        st.info(
            f"No shift definitions yet for **{page_branch_name}** ({page_branch_id}). "
            "Use the **➕ Add New Shift** form below, or click **Seed Default Shifts** "
            "to create the standard ALPHA–ECHO set."
        )
        if role in ("owner", "manager"):
            if st.button(
                "➕ Seed Default Shifts (ALPHA–ECHO)",
                key=f"seed_defaults_{page_branch_id}",
                use_container_width=True,
            ):
                try:
                    ensure_branch_has_defaults(page_branch_id)
                    st.success(f"Default shifts seeded for {page_branch_name}.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to seed defaults: {e}")
    else:
        view = defs_df.copy()
        view["active"] = view["active"].apply(lambda x: "Active" if x else "Inactive")
        view = view.rename(columns={
            "shift_name": "Shift Name",
            "display_name": "Display Name",
            "start_time": "Start",
            "end_time": "End",
            "active": "Status",
            "sort_order": "Order",
        })
        cols = [c for c in ["Shift Name", "Display Name", "Start", "End", "Status", "Order"] if c in view.columns]
        st.dataframe(view[cols], use_container_width=True, hide_index=True)

    # ---------- CRUD (owner / manager only) ----------
    if role not in ("owner", "manager"):
        st.info("Only owners and managers can add, edit, or remove shift definitions.")
        return

    st.markdown("---")

    # -------- ADD --------
    with st.expander("➕ Add New Shift", expanded=defs_df.empty):
        with st.form(f"add_shift_def_form_{page_branch_id}", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                new_shift_name = st.text_input(
                    "Shift Name *",
                    placeholder="e.g., FOXTROT",
                    key=f"new_shift_name_{page_branch_id}",
                ).strip().upper()
                new_display = st.text_input(
                    "Display Name",
                    placeholder="e.g., Foxtrot Shift (16:00 - 22:00)",
                    key=f"new_display_{page_branch_id}",
                )
                new_sort = st.number_input(
                    "Sort Order",
                    min_value=0, max_value=999, value=99, step=1,
                    key=f"new_sort_{page_branch_id}",
                )
            with col2:
                new_start_time = st.time_input(
                    "Start Time",
                    value=datetime.strptime("06:00", "%H:%M").time(),
                    key=f"new_start_{page_branch_id}",
                )
                new_end_time = st.time_input(
                    "End Time",
                    value=datetime.strptime("18:00", "%H:%M").time(),
                    key=f"new_end_{page_branch_id}",
                )
                new_start = _normalize_time(new_start_time, default="06:00")
                new_end = _normalize_time(new_end_time, default="18:00")

            add_btn = st.form_submit_button("Add Shift", type="primary", use_container_width=True)

            if add_btn:
                if not new_shift_name:
                    st.error("Shift Name is required")
                elif not new_start or not new_end:
                    st.error("Start Time and End Time are required")
                else:
                    ok, msg = add_shift_definition(
                        branch_id=page_branch_id,
                        shift_name=new_shift_name,
                        display_name=new_display or f"{new_shift_name} Shift",
                        start_time=new_start,
                        end_time=new_end,
                        sort_order=int(new_sort),
                    )
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

    # -------- EDIT --------
    if not defs_df.empty:
        active_defs = defs_df[defs_df["active"] == True] if "active" in defs_df.columns else defs_df
        options = [
            f"{row['shift_name']} — {row['display_name'] or ''} (id {row['id']})"
            for _, row in active_defs.iterrows()
        ]

        with st.expander("✏️ Edit Shift", expanded=False):
            if not options:
                st.info("No active shifts to edit.")
            else:
                selected_label = st.selectbox(
                    "Select Shift to Edit", options,
                    key=f"sm_edit_select_{page_branch_id}",
                )
                idx = options.index(selected_label)
                row = active_defs.iloc[idx]

                with st.form(f"edit_shift_def_form_{page_branch_id}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        new_disp = st.text_input(
                            "Display Name",
                            value=row["display_name"] or "",
                            key=f"edit_disp_{page_branch_id}_{row['id']}",
                        )
                        new_sort_order = st.number_input(
                            "Sort Order", min_value=0, max_value=999,
                            value=int(row["sort_order"] or 0), step=1,
                            key=f"edit_sort_{page_branch_id}_{row['id']}",
                        )
                    with col2:
                        new_start_str = str(row["start_time"])[:5] if row["start_time"] else "06:00"
                        new_end_str = str(row["end_time"])[:5] if row["end_time"] else "12:00"
                        try:
                            _start_default = datetime.strptime(new_start_str, "%H:%M").time()
                        except Exception:
                            _start_default = datetime.strptime("06:00", "%H:%M").time()
                        try:
                            _end_default = datetime.strptime(new_end_str, "%H:%M").time()
                        except Exception:
                            _end_default = datetime.strptime("18:00", "%H:%M").time()

                        new_start_time = st.time_input(
                            "Start Time",
                            value=_start_default,
                            key=f"edit_start_{page_branch_id}_{row['id']}",
                        )
                        new_end_time = st.time_input(
                            "End Time",
                            value=_end_default,
                            key=f"edit_end_{page_branch_id}_{row['id']}",
                        )
                        new_start = _normalize_time(new_start_time, default=_start_default.strftime("%H:%M"))
                        new_end = _normalize_time(new_end_time, default=_end_default.strftime("%H:%M"))

                    update_btn = st.form_submit_button("Save Changes", type="primary", use_container_width=True)

                    if update_btn:
                        ok, msg = update_shift_definition(
                            definition_id=int(row["id"]),
                            display_name=new_disp,
                            start_time=new_start,
                            end_time=new_end,
                            active=True,
                            sort_order=int(new_sort_order),
                        )
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

        # -------- DELETE (soft) --------
        with st.expander("🗑️ Delete Shift", expanded=False):
            if not options:
                st.info("No active shifts to delete.")
            else:
                del_label = st.selectbox(
                    "Select Shift to Delete", options,
                    key=f"sm_del_select_{page_branch_id}",
                )
                del_idx = options.index(del_label)
                del_row = active_defs.iloc[del_idx]

                st.warning(
                    f"You are about to remove **{del_row['shift_name']}** from "
                    f"**{page_branch_name}**. Existing shift history is not affected."
                )
                confirm = st.checkbox(
                    "I understand this will hide the shift from new shift starts",
                    key=f"sm_delete_confirm_{page_branch_id}",
                )

                if st.button(
                    "Confirm Delete",
                    use_container_width=True,
                    key=f"sm_delete_btn_{page_branch_id}",
                ):
                    if not confirm:
                        st.error("Please tick the confirmation checkbox.")
                    else:
                        ok, msg = delete_shift_definition(int(del_row["id"]))
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)


# ==============================
# MAIN GUARD
# ==============================
if __name__ == "__main__":
    shift_management_page()