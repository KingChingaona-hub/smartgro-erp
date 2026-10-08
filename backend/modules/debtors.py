# backend/modules/debtors.py
# Debtors page, now sourced entirely from Floating Financials (floating_credits).
#
# Data source:
#   backend.core.floating_financials.get_credit_records / create_credit_record /
#   record_credit_payment / get_overdue_credits / get_credit_summary /
#   write_off_credit / recover_bad_debt_credit / is_customer_in_bad_debt
#
# Branch scope:
#   branch_id = None          -> session branch (via _get_session_branch)
#   branch_id = "HO"/"NAT"/.. -> that branch
#
# Amount-only debts: description is a free-text field on the credit row.
# No per-item child table — matches what floating_credits already stores.

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import base64
from io import BytesIO

from backend.core.db_adapter import (
    load_products,
    load_customers,
    load_branches,
)
from backend.core.floating_financials import (
    get_credit_records,
    get_credit_summary,
    get_overdue_credits,
    get_bad_debt_credits,
    create_credit_record,
    record_credit_payment,
    write_off_credit,
    recover_bad_debt_credit,
    is_customer_in_bad_debt,
    get_bad_debt_customers,
    CREDIT_TYPES,
    CREDIT_STATUSES,
)
from backend.utils.utils import generate_whatsapp_payment_reminder, get_whatsapp_link


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
    """Human-readable branch label for receipts and page headers."""
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


def _to_float(value, default=0.0):
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# ==============================
# CUSTOMER SUGGESTION HELPERS (branch-scoped)
# ==============================
def _get_customer_suggestions(branch_id):
    """Unique customer names for this branch, from customers table first, then credits."""
    customers = set()

    try:
        customers_df = load_customers(branch_id=branch_id)
        if customers_df is not None and not customers_df.empty:
            col = None
            for c in ["customer_name", "name", "customer"]:
                if c in customers_df.columns:
                    col = c
                    break
            if col:
                for n in customers_df[col].dropna().astype(str).tolist():
                    n = n.strip()
                    if n and n.lower() != "walk-in":
                        customers.add(n)
    except Exception:
        pass

    try:
        credits_df = get_credit_records(branch_id=branch_id)
        if credits_df is not None and not credits_df.empty and "customer_name" in credits_df.columns:
            for n in credits_df["customer_name"].dropna().astype(str).tolist():
                n = n.strip()
                if n and n.lower() != "walk-in":
                    customers.add(n)
    except Exception:
        pass

    return sorted(customers)


def _get_customer_phone_mapping(branch_id):
    """Map customer name -> phone for this branch, from customers table."""
    mapping = {}
    try:
        customers_df = load_customers(branch_id=branch_id)
        if customers_df is not None and not customers_df.empty:
            name_col = None
            phone_col = None
            for c in ["customer_name", "name", "customer"]:
                if c in customers_df.columns:
                    name_col = c
                    break
            for c in ["phone", "customer_phone"]:
                if c in customers_df.columns:
                    phone_col = c
                    break
            if name_col and phone_col:
                for _, row in customers_df.iterrows():
                    n = str(row.get(name_col, "")).strip()
                    p = str(row.get(phone_col, "")).strip()
                    if n and n.lower() != "walk-in" and p:
                        mapping[n] = p
    except Exception:
        pass
    return mapping


# ==============================
# RECEIPT PRINTING (branch-aware header)
# ==============================
def generate_receipt_pdf_html(receipt_data):
    """Generate HTML for receipt printing with branch header."""

    branch_line = receipt_data.get("branch_name", "Head Office")
    receipt_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Payment Receipt</title>
        <style>
            @page {{ size: 80mm auto; margin: 0; }}
            @media print {{
                body {{ margin: 0; padding: 0; background: white; }}
                .no-print {{ display: none !important; }}
                .receipt-container {{ width: 100%; padding: 8mm; font-size: 10pt; }}
                .watermark {{ display: none; }}
            }}
            body {{
                font-family: 'Courier New', monospace;
                background: #f0f0f0;
                display: flex; justify-content: center; padding: 10px; margin: 0;
            }}
            .receipt-container {{
                background: white; width: 80mm; padding: 12px; border-radius: 4px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1); font-size: 10pt;
            }}
            .receipt-header {{ text-align: center; border-bottom: 2px solid #333; padding-bottom: 8px; margin-bottom: 8px; }}
            .receipt-header h2 {{ margin: 0; font-size: 16pt; color: #1a237e; }}
            .receipt-header p {{ margin: 2px 0; font-size: 8pt; color: #666; }}
            .receipt-details {{ border-bottom: 1px dashed #ccc; padding-bottom: 8px; margin-bottom: 8px; }}
            .receipt-details table {{ width: 100%; font-size: 9pt; }}
            .receipt-details td {{ padding: 2px 0; }}
            .receipt-details .label {{ color: #666; width: 45%; }}
            .receipt-details .value {{ font-weight: bold; text-align: right; width: 55%; }}
            .receipt-items {{ border-bottom: 1px dashed #ccc; padding-bottom: 8px; margin-bottom: 8px; }}
            .receipt-items table {{ width: 100%; font-size: 9pt; border-collapse: collapse; }}
            .receipt-items th {{ text-align: left; border-bottom: 1px solid #333; padding: 3px 0; font-size: 8pt; }}
            .receipt-items td {{ padding: 3px 0; font-size: 8pt; }}
            .receipt-total {{ border-bottom: 2px solid #333; padding-bottom: 8px; margin-bottom: 8px; }}
            .receipt-total table {{ width: 100%; font-size: 10pt; }}
            .receipt-total .total-label {{ font-weight: bold; }}
            .receipt-total .total-amount {{ font-weight: bold; font-size: 14pt; text-align: right; color: #1a237e; }}
            .receipt-footer {{ text-align: center; font-size: 8pt; color: #999; padding-top: 8px; border-top: 1px dashed #ccc; margin-top: 8px; }}
            .receipt-footer .thank-you {{ font-size: 12pt; font-weight: bold; color: #1a237e; margin: 5px 0; }}
            .status-paid {{ color: #2e7d32; font-weight: bold; font-size: 14pt; text-align: center; padding: 5px; background: #e8f5e9; border-radius: 4px; margin: 8px 0; }}
            .status-partial {{ color: #f57f17; font-weight: bold; font-size: 12pt; text-align: center; padding: 5px; background: #fff3e0; border-radius: 4px; margin: 8px 0; }}
            .print-btn {{ background: #1a237e; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; font-size: 12pt; margin: 5px 0; width: 100%; }}
            .print-btn:hover {{ background: #0d1445; }}
        </style>
    </head>
    <body>
        <div class="receipt-container" id="receipt">
            <div class="receipt-header">
                <h2>AZIEL INVESTMENTS</h2>
                <p>{branch_line}</p>
                <p>+263 78 290 5853</p>
                <p style="font-size: 7pt; color: #999; margin-top: 4px;">DEBT PAYMENT RECEIPT</p>
            </div>

            <div class="receipt-details">
                <table>
                    <tr><td class="label">Receipt No:</td><td class="value">{receipt_data.get('receipt_no', 'N/A')}</td></tr>
                    <tr><td class="label">Date:</td><td class="value">{receipt_data.get('date', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}</td></tr>
                    <tr><td class="label">Customer:</td><td class="value">{receipt_data.get('customer_name', 'N/A')}</td></tr>
                    <tr><td class="label">Phone:</td><td class="value">{receipt_data.get('phone', 'N/A')}</td></tr>
                    <tr><td class="label">Payment Method:</td><td class="value">{receipt_data.get('payment_method', 'CASH')}</td></tr>
                    <tr><td class="label">Credit ID:</td><td class="value">{receipt_data.get('credit_id', 'N/A')}</td></tr>
                </table>
            </div>

            <div class="receipt-items">
                <table>
                    <tr><th style="width: 60%;">Description</th><th style="width: 20%; text-align: right;">Amount</th></tr>
                    <tr><td>{receipt_data.get('description', 'Credit payment') or 'Credit payment'}</td><td style="text-align: right;">${receipt_data.get('amount_paid', 0):.2f}</td></tr>
                </table>
            </div>

            <div class="receipt-total">
                <table>
                    <tr><td class="total-label">Previous Balance:</td><td style="text-align: right;">${receipt_data.get('previous_balance', 0):.2f}</td></tr>
                    <tr><td class="total-label">Amount Paid:</td><td style="text-align: right; color: #2e7d32; font-weight: bold;">${receipt_data.get('amount_paid', 0):.2f}</td></tr>
                    {receipt_data.get('cash_tendered_row', '')}
                    {receipt_data.get('change_row', '')}
                    <tr style="border-top: 2px solid #333;"><td class="total-label">New Balance:</td><td class="total-amount">${receipt_data.get('new_balance', 0):.2f}</td></tr>
                </table>
            </div>

            <div class="{receipt_data.get('status_class', 'status-paid')}">
                {receipt_data.get('status_text', 'FULLY PAID - THANK YOU!')}
            </div>

            <div class="receipt-footer">
                <p class="thank-you">Thank you for your business!</p>
                <p>This is a computer-generated receipt</p>
                <p>{branch_line}</p>
                <p style="font-size: 7pt; color: #ccc; margin-top: 5px;">Receipt generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
        </div>

        <div style="text-align: center; margin-top: 15px; width: 80mm;">
            <button class="print-btn no-print" onclick="window.print()">Print Receipt</button>
            <br>
            <button class="print-btn no-print" style="background: #666;" onclick="window.location.href='/'">Close</button>
        </div>

        <script>
            window.onload = function() {{ setTimeout(function() {{ window.print(); }}, 600); }};
        </script>
    </body>
    </html>
    """
    return receipt_html


# ==============================
# DEBTORS PAGE (Floating Financials source)
# ==============================
def debtors_page():
    """Debtors Management — sourced from Floating Financials credits."""

    branch_id = _get_session_branch()
    branch_label = _branch_display_name(branch_id)

    st.title(f"Debtors Management - {branch_label}")
    st.caption("Customer credit and loans tracked via Floating Financials")

    # ---------------- SESSION STATE ----------------
    for k in ("payment_receipt", "receipt_data", "button_clicked", "debt_updated"):
        if k not in st.session_state:
            st.session_state[k] = None if "receipt" in k or "data" in k else False

    if st.session_state.get("debt_updated", False):
        st.cache_data.clear()
        st.session_state.debt_updated = False

    # ---------------- LOAD (branch-scoped) ----------------
    credits_df = get_credit_records(branch_id=branch_id)
    products_df = load_products(branch_id=branch_id)
    customers_df = load_customers(branch_id=branch_id)

    # Empty state
    if credits_df is None or credits_df.empty:
        st.info(
            f"No credit records found for branch **{branch_label}**. "
            f"Use the 'Create Debt' tab below to record the first one."
        )
        # Still show tabs — the Create Debt tab works without existing records
        _render_tabs(credits_df, products_df, branch_id, branch_label)
        return

    # ==============================
    # TABS
    # ==============================
    _render_tabs(credits_df, products_df, branch_id, branch_label)


def _render_tabs(credits_df, products_df, branch_id, branch_label):
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Create Debt",
        "Record Payment",
        "Overdue & Bad Debt",
        "Analytics",
        "All Credits",
    ])

    # ============================================================
    # TAB 1: CREATE DEBT
    # ============================================================
    with tab1:
        _create_debt_tab(products_df, branch_id, branch_label)

    # ============================================================
    # TAB 2: RECORD PAYMENT
    # ============================================================
    with tab2:
        _record_payment_tab(credits_df, branch_id, branch_label)

    # ============================================================
    # TAB 3: OVERDUE & BAD DEBT
    # ============================================================
    with tab3:
        _overdue_bad_debt_tab(branch_id, branch_label)

    # ============================================================
    # TAB 4: ANALYTICS
    # ============================================================
    with tab4:
        _analytics_tab(credits_df, branch_id, branch_label)

    # ============================================================
    # TAB 5: ALL CREDITS
    # ============================================================
    with tab5:
        _all_credits_tab(credits_df, branch_id, branch_label)

    # ============================================================
    # RECEIPT (if any)
    # ============================================================
    _render_receipt_section(branch_id, branch_label)


# ============================================================
# TAB 1: CREATE DEBT
# ============================================================
def _create_debt_tab(products_df, branch_id, branch_label):
    st.markdown(f"## Create New Debt — {branch_label}")
    st.caption(
        "Record a new credit / loan against this branch. "
        "Debt is amount-only with a text description."
    )

    customer_suggestions = _get_customer_suggestions(branch_id)
    customer_phones = _get_customer_phone_mapping(branch_id)

    with st.form("create_debt_form"):
        col1, col2 = st.columns(2)

        with col1:
            # Customer selection
            all_options = ["Walk-in"] + customer_suggestions if customer_suggestions else ["Walk-in"]
            selected_customer = st.selectbox("Customer Name *", all_options, key="debt_customer_select")
            new_customer_name = st.text_input(
                "Or type new customer name",
                placeholder="Leave blank to use dropdown above",
                key="debt_customer_typed",
            )
            customer_name = new_customer_name.strip() if new_customer_name and new_customer_name.strip() else selected_customer

            customer_phone = st.text_input(
                "Phone Number",
                value=customer_phones.get(customer_name, ""),
                key="debt_customer_phone",
                placeholder="0777123456",
            )

        with col2:
            amount = st.number_input("Amount ($) *", min_value=0.01, step=10.0, value=10.0, key="debt_amount")
            credit_type = st.selectbox("Credit Type", CREDIT_TYPES, key="debt_credit_type")
            expected_repayment = st.date_input(
                "Expected Repayment Date",
                value=datetime.now().date() + timedelta(days=30),
                key="debt_expected_date",
            )

        description = st.text_area(
            "Description *",
            placeholder="e.g., Loan for goods (20kg rice, 5kg sugar), Cash advance, etc.",
            key="debt_description",
        )

        # Live bad-debt block check
        live_blocked, live_reason = (False, "")
        if customer_name and customer_name.strip() and customer_name != "Walk-in":
            try:
                live_blocked, live_reason = is_customer_in_bad_debt(customer_name, branch_id=branch_id)
            except Exception:
                pass

        if live_blocked:
            st.error(f"🚫 {live_reason}")
            st.caption("Recording will be blocked until this customer's bad debt is recovered.")

        submitted = st.form_submit_button("Create Debt", type="primary", use_container_width=True)

        if submitted:
            if not customer_name or customer_name == "Walk-in":
                st.error("Customer name is required")
            elif amount <= 0:
                st.error("Amount must be greater than 0")
            elif not description or not description.strip():
                st.error("Description is required")
            else:
                success, message, credit_id = create_credit_record(
                    customer_name=customer_name,
                    amount=amount,
                    credit_type=credit_type,
                    description=description,
                    phone=customer_phone,
                    expected_repayment=expected_repayment.strftime("%Y-%m-%d") if expected_repayment else None,
                    branch_id=branch_id,
                )
                if success:
                    st.success(f"{message}")
                    st.session_state.debt_updated = True
                    st.rerun()
                else:
                    st.error(message)


# ============================================================
# TAB 2: RECORD PAYMENT
# ============================================================
def _record_payment_tab(credits_df, branch_id, branch_label):
    st.markdown(f"## Record Debt Payment — {branch_label}")
    st.caption("Record a partial or full payment against a customer's credit.")

    if credits_df is None or credits_df.empty:
        st.info("No credit records found in this branch. Create one first.")
        return

    # Only ACTIVE and PARTIAL_PAID
    active = credits_df[
        (credits_df["balance"] > 0)
        & (credits_df["status"].isin(["ACTIVE", "PARTIAL_PAID"]))
    ]

    if active.empty:
        st.success("All credits are fully paid in this branch.")
        return

    # Customer selection
    customers_with_debt = sorted(active["customer_name"].dropna().astype(str).unique().tolist())
    selected_customer = st.selectbox("Select Customer", customers_with_debt, key="pay_customer_select")

    if not selected_customer:
        return

    customer_credits = active[active["customer_name"] == selected_customer]

    total_borrowed = _to_float(customer_credits["amount"].sum())
    total_paid = _to_float(customer_credits["amount_paid"].sum())
    total_balance = _to_float(customer_credits["balance"].sum())

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Borrowed", f"${total_borrowed:,.2f}")
    with col2:
        st.metric("Total Paid", f"${total_paid:,.2f}")
    with col3:
        st.metric("Outstanding", f"${total_balance:,.2f}")

    st.markdown("### Credits for this Customer")

    # List the credits so the user picks which one to pay
    credit_options = []
    for _, row in customer_credits.iterrows():
        cid = row.get("credit_id", "N/A")
        bal = _to_float(row.get("balance", 0))
        desc = str(row.get("description", "") or "")
        desc_short = desc[:40] + "..." if len(desc) > 40 else desc
        credit_options.append(f"{cid} - Balance: ${bal:.2f} - {desc_short}")

    selected_credit_label = st.selectbox("Select Credit to Pay", credit_options, key="pay_credit_select")
    selected_idx = credit_options.index(selected_credit_label)
    selected_row = customer_credits.iloc[selected_idx]

    credit_id = selected_row.get("credit_id")
    credit_balance = _to_float(selected_row.get("balance", 0))
    credit_description = str(selected_row.get("description", "") or "")
    credit_phone = str(selected_row.get("phone", "") or "")

    st.info(f"**Description:** {credit_description or '(no description)'}")
    st.info(f"**Credit ID:** {credit_id}")

    col1, col2 = st.columns(2)
    with col1:
        pay_amount = st.number_input(
            "Payment Amount ($)",
            min_value=0.01,
            max_value=float(credit_balance),
            value=float(credit_balance),
            step=10.0,
            key="debt_pay_amount",
        )
        cash_tendered = st.number_input(
            "Cash Tendered ($)",
            min_value=0.0,
            step=10.0,
            key="debt_cash_tendered",
        )
    with col2:
        payment_method = st.selectbox(
            "Payment Method",
            ["CASH", "ECOCASH", "CARD", "BANK TRANSFER"],
            key="debt_payment_method",
        )
        payment_note = st.text_input(
            "Payment Reference / Note",
            placeholder="Receipt number, notes...",
            key="debt_payment_note",
        )

    # Change calculation
    change_debt = 0.0
    if cash_tendered > 0 and pay_amount > 0:
        if cash_tendered >= pay_amount:
            change_debt = cash_tendered - pay_amount
            st.success(f"Change to return: ${change_debt:.2f}")
        else:
            st.warning("Cash tendered is less than payment amount")

    if st.button("Record Payment", type="primary", key="record_debt_payment"):
        if st.session_state.get("button_clicked", False):
            return
        st.session_state.button_clicked = True

        if pay_amount <= 0:
            st.error("Enter a valid payment amount")
        elif pay_amount > credit_balance:
            st.error("Payment exceeds the outstanding balance on this credit")
        else:
            success, message = record_credit_payment(
                credit_id=credit_id,
                amount=pay_amount,
                payment_note=payment_note or "Debt payment",
                payment_method=payment_method,
            )

            if success:
                new_balance = credit_balance - pay_amount
                is_paid = new_balance <= 0

                st.success(f"{message}")
                st.session_state.debt_updated = True

                receipt_no = f"DEBTPAY-{branch_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

                receipt_data = {
                    "receipt_no": receipt_no,
                    "date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "customer_name": selected_customer,
                    "phone": credit_phone,
                    "credit_id": credit_id,
                    "description": credit_description,
                    "amount_paid": pay_amount,
                    "previous_balance": credit_balance,
                    "new_balance": max(new_balance, 0.0),
                    "payment_method": payment_method,
                    "cash_tendered": cash_tendered if cash_tendered > 0 else 0,
                    "change": change_debt if cash_tendered > 0 else 0,
                    "is_paid": is_paid,
                    "branch_name": branch_label,
                    "branch_id": branch_id,
                }

                if cash_tendered > 0:
                    receipt_data["cash_tendered_row"] = (
                        f'<tr><td class="total-label">Cash Tendered:</td>'
                        f'<td style="text-align: right;">${cash_tendered:.2f}</td></tr>'
                    )
                    receipt_data["change_row"] = (
                        f'<tr><td class="total-label">Change:</td>'
                        f'<td style="text-align: right; color: #2e7d32;">${change_debt:.2f}</td></tr>'
                    )
                else:
                    receipt_data["cash_tendered_row"] = ""
                    receipt_data["change_row"] = ""

                if is_paid:
                    receipt_data["status_text"] = "FULLY PAID - THANK YOU!"
                    receipt_data["status_class"] = "status-paid"
                else:
                    receipt_data["status_text"] = f"PARTIAL PAYMENT - Remaining: ${max(new_balance, 0.0):.2f}"
                    receipt_data["status_class"] = "status-partial"

                st.session_state.receipt_data = receipt_data
                st.session_state.payment_receipt = generate_receipt_pdf_html(receipt_data)

                st.session_state.button_clicked = False
                st.rerun()
            else:
                st.error(message)

        st.session_state.button_clicked = False


# ============================================================
# TAB 3: OVERDUE & BAD DEBT
# ============================================================
def _overdue_bad_debt_tab(branch_id, branch_label):
    st.markdown(f"## Overdue & Bad Debt — {branch_label}")

    overdue = get_overdue_credits(branch_id=branch_id)
    bad_debt = get_bad_debt_credits(branch_id=branch_id)
    blocked_customers = get_bad_debt_customers(branch_id=branch_id)

    # Blocked banner
    if blocked_customers is not None and not blocked_customers.empty:
        names = sorted(set(blocked_customers["customer_name"].astype(str).tolist()))
        st.error(
            "🚫 Credit BLOCKED for these customers (unresolved bad debt): "
            + ", ".join(f"**{n}**" for n in names)
        )

    # Overdue
    st.markdown("### Overdue Credits")
    if overdue is None or overdue.empty:
        st.success("No overdue credits in this branch.")
    else:
        st.warning(f"{len(overdue)} overdue credit(s) need attention.")
        od = overdue.copy()
        for c in ["amount", "amount_paid", "balance"]:
            if c in od.columns:
                od[c] = pd.to_numeric(od[c], errors="coerce").fillna(0)
        display = od.rename(columns={
            "customer_name": "Customer",
            "phone": "Phone",
            "balance": "Balance",
            "amount": "Amount",
            "amount_paid": "Paid",
            "expected_repayment_date": "Due Date",
            "days_overdue": "Days Overdue",
            "risk_level": "Risk",
            "credit_id": "ID",
        })
        cols = [c for c in ["Customer", "Phone", "Balance", "Days Overdue", "Due Date", "Risk", "ID"] if c in display.columns]
        st.dataframe(display[cols], use_container_width=True, hide_index=True)

    # Bad debt list
    st.markdown("---")
    st.markdown("### Bad Debt / Written Off Credits")

    if bad_debt is None or bad_debt.empty:
        st.info("No bad-debt or written-off credits in this branch.")
    else:
        bd = bad_debt.copy()
        for c in ["amount", "amount_paid", "balance"]:
            if c in bd.columns:
                bd[c] = pd.to_numeric(bd[c], errors="coerce").fillna(0)

        bd["Outstanding"] = (bd["amount"] - bd["amount_paid"]).clip(lower=0)

        display_bd = bd.rename(columns={
            "customer_name": "Customer",
            "phone": "Phone",
            "amount": "Original Amount",
            "amount_paid": "Paid",
            "status": "Status",
            "written_off_reason": "Reason",
            "credit_id": "ID",
        })
        cols = [c for c in ["Customer", "Phone", "Original Amount", "Paid", "Outstanding", "Status", "Reason", "ID"] if c in display_bd.columns]
        st.dataframe(
            display_bd[cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Original Amount": st.column_config.NumberColumn("Original Amount", format="$%.2f"),
                "Paid": st.column_config.NumberColumn("Paid", format="$%.2f"),
                "Outstanding": st.column_config.NumberColumn("Outstanding", format="$%.2f"),
            },
        )

        # Recovery payment
        st.markdown("### Recovery Payment")
        rec_options = []
        for _, r in bad_debt.iterrows():
            outstanding = max(_to_float(r.get("amount", 0)) - _to_float(r.get("amount_paid", 0)), 0.0)
            rec_options.append(
                f"{r.get('customer_name', '?')} - Outstanding: ${outstanding:.2f} - {r.get('credit_id', '')}"
            )

        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            selected_rec = st.selectbox("Select bad debt to recover", rec_options, key="debtors_rec_select")
        with col2:
            rec_amount = st.number_input("Amount ($)", min_value=0.01, step=10.0, value=10.0, key="debtors_rec_amount")
        with col3:
            rec_method = st.selectbox("Method", ["CASH", "BANK", "MOBILE_MONEY", "ECOCASH"], key="debtors_rec_method")

        if st.button("Record Recovery Payment", key="debtors_rec_btn"):
            idx = rec_options.index(selected_rec)
            row = bad_debt.iloc[idx]
            credit_id = row.get("credit_id")
            ok, msg = recover_bad_debt_credit(
                credit_id,
                rec_amount,
                payment_method=rec_method or "CASH",
                note="Recovery payment",
            )
            if ok:
                st.success(msg)
                st.session_state.debt_updated = True
                st.rerun()
            else:
                st.error(msg)


# ============================================================
# TAB 4: ANALYTICS
# ============================================================
def _analytics_tab(credits_df, branch_id, branch_label):
    st.markdown(f"## Debtors Analytics — {branch_label}")

    if credits_df is None or credits_df.empty:
        st.info("No credit data available for this branch.")
        return

    summary = get_credit_summary(branch_id=branch_id)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Credit", f"${summary.get('total_credit', 0):,.2f}")
    with col2:
        st.metric("Total Paid", f"${summary.get('total_paid', 0):,.2f}")
    with col3:
        st.metric("Outstanding", f"${summary.get('total_balance', 0):,.2f}")
    with col4:
        st.metric("Active Credits", summary.get("active_count", 0))

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Overdue", summary.get("overdue_count", 0))
    with col2:
        st.metric("Paid", summary.get("paid_count", 0))
    with col3:
        st.metric("Bad Debt", summary.get("bad_debt_count", 0))

    # Top debtors by outstanding balance
    st.markdown("### Top Debtors by Outstanding Balance")
    active = credits_df[credits_df["balance"] > 0] if "balance" in credits_df.columns else pd.DataFrame()

    if active.empty:
        st.info("No outstanding balances.")
    else:
        top = active.copy()
        top["balance"] = pd.to_numeric(top["balance"], errors="coerce").fillna(0)
        top = top.nlargest(10, "balance")[["customer_name", "phone", "balance", "status"]]
        top = top.rename(columns={
            "customer_name": "Customer",
            "phone": "Phone",
            "balance": "Outstanding",
            "status": "Status",
        })
        st.dataframe(
            top,
            use_container_width=True,
            hide_index=True,
            column_config={"Outstanding": st.column_config.NumberColumn("Outstanding", format="$%.2f")},
        )


# ============================================================
# TAB 5: ALL CREDITS
# ============================================================
def _all_credits_tab(credits_df, branch_id, branch_label):
    st.markdown(f"## All Credit Records — {branch_label}")

    if credits_df is None or credits_df.empty:
        st.info("No credit records found in this branch.")
        return

    col1, col2 = st.columns(2)
    with col1:
        status_filter = st.selectbox("Status", ["All"] + CREDIT_STATUSES, key="debtors_all_status")
    with col2:
        type_filter = st.selectbox("Credit Type", ["All"] + CREDIT_TYPES, key="debtors_all_type")

    filtered = credits_df.copy()
    if status_filter != "All":
        filtered = filtered[filtered["status"] == status_filter]
    if type_filter != "All":
        filtered = filtered[filtered["credit_type"] == type_filter]

    if filtered.empty:
        st.info("No credits match the filters.")
        return

    display = filtered.rename(columns={
        "credit_id": "ID",
        "customer_name": "Customer",
        "phone": "Phone",
        "description": "Description",
        "amount": "Amount",
        "amount_paid": "Paid",
        "balance": "Balance",
        "credit_type": "Type",
        "expected_repayment_date": "Due Date",
        "status": "Status",
    })

    cols = [c for c in ["ID", "Customer", "Phone", "Description", "Amount", "Paid", "Balance", "Type", "Due Date", "Status"] if c in display.columns]

    st.dataframe(
        display[cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
            "Paid": st.column_config.NumberColumn("Paid", format="$%.2f"),
            "Balance": st.column_config.NumberColumn("Balance", format="$%.2f"),
            "Description": st.column_config.TextColumn("Description", width="medium"),
        },
    )

    csv = filtered.to_csv(index=False).encode("utf-8")
    st.download_button(
        label=f"Download Credit Records (CSV) — {branch_id}",
        data=csv,
        file_name=f"credits_{branch_id}_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )


# ============================================================
# RECEIPT DISPLAY
# ============================================================
def _render_receipt_section(branch_id, branch_label):
    receipt_html = st.session_state.get("payment_receipt")
    receipt_data = st.session_state.get("receipt_data")

    if not receipt_html or not receipt_data:
        return

    st.markdown("---")
    st.subheader("PAYMENT RECEIPT")

    with st.expander("View Receipt", expanded=True):
        st.components.v1.html(receipt_html, height=700, scrolling=True)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            """
            <button onclick="window.print()" style="background: #1a237e; color: white; border: none;
            padding: 12px 24px; border-radius: 5px; cursor: pointer; font-size: 14px;
            width: 100%; margin: 5px 0;">Print Receipt</button>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        b64 = base64.b64encode(receipt_html.encode()).decode()
        href = (
            f'<a href="data:text/html;base64,{b64}" '
            f'download="receipt_{branch_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html" '
            f'style="display:block;text-align:center;background:#2e7d32;color:white;'
            f'padding:12px 24px;border-radius:5px;text-decoration:none;font-size:14px;margin:5px 0;">'
            f'Download Receipt (HTML)</a>'
        )
        st.markdown(href, unsafe_allow_html=True)

    with col3:
        if st.button("Close Receipt", key="debtors_close_receipt"):
            st.session_state.payment_receipt = None
            st.session_state.receipt_data = None
            st.rerun()

    st.caption("Click 'Print Receipt' to print or save as PDF")


# ==============================
# MAIN GUARD
# ==============================
if __name__ == "__main__":
    debtors_page()