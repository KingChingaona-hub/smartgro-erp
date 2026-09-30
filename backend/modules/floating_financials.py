# backend/modules/floating_financials.py
# Complete with Today/Previous split for gas sales
# FIXED: auto-merge visible immediately (cache cleared in core)
# ADDED: Write-Off for Changes and Bad Debts for Credits
# ADDED: Auto-flag overdue records at page load
# ADDED: Dedicated "Written Off Changes" and "Bad Debts" sections so you
#        can SEE the records after confirming, not just the counts.
# ADDED: Recovery collection / recovery payment inside the written-off and
#        bad debt sections. Full recovery DELETES the record so it disappears
#        from every view. Partial recovery keeps the record with an updated
#        reason showing what has been recovered so far.
# ADDED: Block new credit issuance to customers currently in bad debt.
#        Shows a red banner + live warning on the credit form.

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from backend.core.floating_financials import (
    # Change Management
    create_change_record,
    collect_change,
    write_off_change,
    recover_written_off_change,
    get_written_off_changes,
    get_change_records,
    get_change_summary,
    get_overdue_changes,
    CHANGE_STATUSES,

    # Credit Management
    create_credit_record,
    record_credit_payment,
    write_off_credit,
    recover_bad_debt_credit,
    get_bad_debt_credits,
    get_credit_records,
    get_credit_summary,
    get_overdue_credits,
    CREDIT_TYPES,
    CREDIT_STATUSES,

    # Bad debt blocking helpers
    is_customer_in_bad_debt,
    get_bad_debt_customers,

    # Auto write-off / bad debt
    auto_flag_overdue_records,
    BAD_DEBT_DAYS_THRESHOLD,

    # Gas Sales - Recording only
    create_gas_sale,
    get_gas_sales,
    get_gas_sales_summary,
)
from backend.core.auth import can_access_feature
from backend.core.theme_manager import apply_page_theme
from backend.core.db_adapter import load_sales


# ==============================
# CUSTOMER AUTOCOMPLETE HELPERS
# ==============================

@st.cache_data(ttl=300)
def get_customer_suggestions():
    try:
        sales_df = load_sales()
        if sales_df.empty:
            return []

        customer_col = None
        for col in ["customer_name", "customer", "Customer"]:
            if col in sales_df.columns:
                customer_col = col
                break

        if not customer_col:
            return []

        customers = sales_df[customer_col].dropna().unique().tolist()
        customers = [
            str(c).strip()
            for c in customers
            if str(c).strip() and str(c).strip().lower() != "walk-in"
        ]
        return sorted(set(customers))
    except Exception as e:
        print(f"Error getting customer suggestions: {e}")
        return []


@st.cache_data(ttl=300)
def get_customer_phone_mapping():
    try:
        sales_df = load_sales()
        if sales_df.empty:
            return {}

        name_col = None
        phone_col = None

        for col in ["customer_name", "customer", "Customer"]:
            if col in sales_df.columns:
                name_col = col
                break

        for col in ["customer_phone", "phone", "Phone"]:
            if col in sales_df.columns:
                phone_col = col
                break

        if name_col and phone_col:
            mapping = {}
            for _, row in sales_df.iterrows():
                name = str(row.get(name_col, "")).strip()
                phone = str(row.get(phone_col, "")).strip()
                if name and name.lower() != "walk-in" and phone:
                    mapping[name] = phone
            return mapping

        return {}
    except Exception as e:
        print(f"Error getting customer phone mapping: {e}")
        return {}


def get_customer_name_input(key_suffix=""):
    customer_suggestions = get_customer_suggestions()
    customer_phones = get_customer_phone_mapping()

    all_options = ["Walk-in"] + customer_suggestions if customer_suggestions else ["Walk-in"]

    current_name = st.session_state.get(f"customer_name_{key_suffix}", "Walk-in")

    is_new_customer = (
        current_name not in all_options
        and current_name != "Walk-in"
        and current_name.strip()
    )
    if is_new_customer:
        all_options.append(current_name)

    try:
        current_index = all_options.index(current_name) if current_name in all_options else 0
    except ValueError:
        current_index = 0

    selected_customer = st.selectbox(
        "Customer Name",
        options=all_options,
        index=current_index,
        key=f"customer_select_{key_suffix}",
    )

    new_customer_name = st.text_input(
        "Or type new customer name",
        placeholder="Enter new name...",
        key=f"new_customer_{key_suffix}",
    )

    if new_customer_name and new_customer_name.strip():
        selected_customer = new_customer_name.strip()

    auto_phone = ""
    if selected_customer != "Walk-in" and selected_customer in customer_phones:
        auto_phone = customer_phones[selected_customer]

    phone = st.text_input(
        "Phone",
        value=auto_phone,
        key=f"customer_phone_{key_suffix}",
        placeholder="Enter phone number",
    )

    return selected_customer, phone


# ==============================
# MAIN PAGE
# ==============================

def floating_financials_page():
    apply_page_theme("floating_financials")

    st.title("Floating Financials")
    st.caption("Manage change, credits, and gas sales")

    role = st.session_state.get("role", "cashier")
    if not can_access_feature(role, "floating_financials"):
        st.error("You don't have permission to access this page")
        return

    # Auto-flag overdue records once per session
    if "auto_flag_done" not in st.session_state:
        with st.spinner("Checking for overdue records..."):
            flagged = auto_flag_overdue_records()
        st.session_state.auto_flag_done = True
        if flagged.get("changes_flagged", 0) or flagged.get("credits_flagged", 0):
            st.warning(
                f"Auto write-off complete: "
                f"{flagged.get('changes_flagged', 0)} change(s) and "
                f"{flagged.get('credits_flagged', 0)} credit(s) were overdue by more than "
                f"{BAD_DEBT_DAYS_THRESHOLD} days and have been flagged as Written Off / Bad Debt."
            )

    tab_names = ["Change Management", "Credit Management", "Gas Sales"]

    if "floating_tab" not in st.session_state:
        st.session_state.floating_tab = 0

    try:
        params = st.query_params
        if "tab" in params:
            tab_param = params.get("tab")
            if tab_param in tab_names:
                st.session_state.floating_tab = tab_names.index(tab_param)
    except Exception:
        pass

    tab1, tab2, tab3 = st.tabs(tab_names)

    with tab1:
        st.session_state.floating_tab = 0
        try:
            st.query_params["tab"] = "Change Management"
        except Exception:
            pass
        change_management_tab()

    with tab2:
        st.session_state.floating_tab = 1
        try:
            st.query_params["tab"] = "Credit Management"
        except Exception:
            pass
        credit_management_tab()

    with tab3:
        st.session_state.floating_tab = 2
        try:
            st.query_params["tab"] = "Gas Sales"
        except Exception:
            pass
        gas_sales_tab()


# ==============================
# CHANGE MANAGEMENT TAB
# ==============================

def change_management_tab():
    summary = get_change_summary()

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Change", f"${summary['total_change']:,.2f}")
    with col2:
        st.metric("Collected", f"${summary['total_collected']:,.2f}")
    with col3:
        st.metric("Balance", f"${summary['total_balance']:,.2f}")
    with col4:
        st.metric("Uncollected", f"{summary['uncollected_count']}")
    with col5:
        st.metric("Written Off", f"{summary.get('written_off_count', 0)}")

    st.divider()

    # ---------------- Overdue Changes (action required) ----------------
    overdue_changes = get_overdue_changes()
    if not overdue_changes.empty:
        with st.expander(
            f"Overdue Changes ({len(overdue_changes)}) - action required",
            expanded=False,
        ):
            st.caption(
                f"These changes have a due date in the past. Those overdue by more "
                f"than {BAD_DEBT_DAYS_THRESHOLD} days are automatically written off."
            )
            od_display = overdue_changes.copy()
            for col in ["amount", "amount_collected", "balance"]:
                if col in od_display.columns:
                    od_display[col] = pd.to_numeric(od_display[col], errors="coerce").fillna(0)

            if "days_overdue" in od_display.columns:
                od_display["Days Overdue"] = od_display["days_overdue"]

            od_display = od_display.rename(
                columns={
                    "customer_name": "Customer",
                    "description": "Description",
                    "balance": "Balance",
                    "expected_collection_date": "Due Date",
                    "change_id": "ID",
                }
            )
            cols = [
                c
                for c in [
                    "Customer",
                    "Description",
                    "Balance",
                    "Due Date",
                    "Days Overdue",
                    "ID",
                ]
                if c in od_display.columns
            ]
            st.dataframe(od_display[cols], use_container_width=True, hide_index=True)

            st.markdown("**Manually Write Off a Change**")
            wo_options = []
            for _, r in overdue_changes.iterrows():
                wo_options.append(
                    f"{r.get('customer_name', '?')} - "
                    f"${float(r.get('balance', 0)):.2f} - "
                    f"{r.get('change_id', '')}"
                )

            selected_wo = st.selectbox(
                "Select change to write off", wo_options, key="wo_change_select"
            )
            wo_reason = st.text_input(
                "Write-off reason",
                value="Overdue > 2 months",
                key="wo_change_reason",
            )
            if st.button("Write Off Selected Change", key="wo_change_btn"):
                if selected_wo:
                    idx = wo_options.index(selected_wo)
                    row = overdue_changes.iloc[idx]
                    ok, msg = write_off_change(
                        row.get("change_id"), wo_reason or "Written off"
                    )
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

    # ---------------- Written Off Changes (visible history + recovery) ----------------
    written_off_changes = get_written_off_changes()
    if not written_off_changes.empty:
        with st.expander(
            f"Written Off Changes ({len(written_off_changes)}) - click to view / recover",
            expanded=False,
        ):
            wo_display = written_off_changes.copy()
            for col in ["amount", "amount_collected", "balance"]:
                if col in wo_display.columns:
                    wo_display[col] = pd.to_numeric(wo_display[col], errors="coerce").fillna(0)

            if "written_off_at" in wo_display.columns:
                wo_display["Written Off At"] = pd.to_datetime(
                    wo_display["written_off_at"], errors="coerce"
                ).dt.strftime("%Y-%m-%d %H:%M")
            else:
                wo_display["Written Off At"] = "N/A"

            wo_display["Outstanding"] = (
                wo_display["amount"] - wo_display["amount_collected"]
            ).clip(lower=0)

            wo_display = wo_display.rename(
                columns={
                    "customer_name": "Customer",
                    "description": "Description",
                    "amount": "Original Amount",
                    "amount_collected": "Recovered",
                    "written_off_reason": "Reason",
                    "change_id": "ID",
                }
            )

            wo_cols = [
                c
                for c in [
                    "Written Off At",
                    "Customer",
                    "Description",
                    "Original Amount",
                    "Recovered",
                    "Outstanding",
                    "Reason",
                    "ID",
                ]
                if c in wo_display.columns
            ]

            st.dataframe(
                wo_display[wo_cols],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Original Amount": st.column_config.NumberColumn(
                        "Original Amount", format="$%.2f"
                    ),
                    "Recovered": st.column_config.NumberColumn(
                        "Recovered", format="$%.2f"
                    ),
                    "Outstanding": st.column_config.NumberColumn(
                        "Outstanding", format="$%.2f"
                    ),
                    "Description": st.column_config.TextColumn(
                        "Description", width="medium"
                    ),
                },
            )

            total_written_off_amount = (
                float(written_off_changes["amount"].sum())
                if "amount" in written_off_changes.columns
                else 0
            )
            st.caption(
                f"Total original value written off: "
                f"**${total_written_off_amount:,.2f}** across "
                f"**{len(written_off_changes)}** record(s)."
            )

            # ---------------- Recovery Collection ----------------
            st.markdown("---")
            st.markdown("**Recovery Collection**")
            st.caption(
                "If the customer comes back and collects a written-off change, "
                "record it here. A full recovery removes the row completely; "
                "a partial recovery keeps it visible with the amount noted."
            )

            rec_options = []
            for _, r in written_off_changes.iterrows():
                original = float(r.get("amount", 0) or 0)
                recovered = float(r.get("amount_collected", 0) or 0)
                outstanding = max(original - recovered, 0.0)
                rec_options.append(
                    f"{r.get('customer_name', '?')} - "
                    f"Outstanding: ${outstanding:.2f} - "
                    f"{r.get('change_id', '')}"
                )

            rec_col1, rec_col2, rec_col3 = st.columns([2, 1, 1])
            with rec_col1:
                selected_rec = st.selectbox(
                    "Select written-off change to recover",
                    rec_options,
                    key="rec_change_select",
                )
            with rec_col2:
                rec_amount = st.number_input(
                    "Amount Collected ($)",
                    min_value=0.01,
                    step=0.01,
                    value=0.01,
                    key="rec_change_amount",
                )
            with rec_col3:
                rec_note = st.text_input(
                    "Note (optional)",
                    value="Recovery collection",
                    key="rec_change_note",
                )

            if st.button(
                "Collect Recovery",
                key="rec_change_btn",
                use_container_width=True,
            ):
                if not selected_rec:
                    st.error("Please select a written-off change to recover")
                else:
                    idx = rec_options.index(selected_rec)
                    row = written_off_changes.iloc[idx]
                    change_id = row.get("change_id")
                    ok, msg = recover_written_off_change(
                        change_id, rec_amount, rec_note or "Recovery collection"
                    )
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

    st.divider()

    # ---------------- Record New Change ----------------
    with st.form("record_change_form"):
        st.markdown("### Record New Uncollected Change")
        st.caption(
            "If this customer already has an unpaid change, the amount will be MERGED "
            "into that existing row (single row per customer, description combined)."
        )

        customer_name, phone = get_customer_name_input("change")
        new_amount = st.number_input(
            "Amount ($)", min_value=0.01, step=0.01, key="new_change_amount"
        )
        new_desc = st.text_area(
            "Description (Required)",
            key="new_change_desc",
            placeholder="e.g., Customer overpaid by $X, Gas sale change, etc.",
        )
        new_expected = st.date_input(
            "Expected Collection Date (Optional)",
            value=None,
            key="new_change_expected",
        )

        if st.form_submit_button("Record Change", use_container_width=True):
            if not customer_name:
                st.error("Customer name is required")
            elif new_amount <= 0:
                st.error("Amount must be greater than 0")
            elif not new_desc or not new_desc.strip():
                st.error("Description is required")
            else:
                success, message, change_id = create_change_record(
                    customer_name=customer_name,
                    amount=new_amount,
                    description=new_desc,
                    phone=phone,
                    expected_collection_date=(
                        new_expected.strftime("%Y-%m-%d") if new_expected else None
                    ),
                )
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)

    st.divider()

    # ---------------- Filters + Main Table ----------------
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        filter_status = st.selectbox(
            "Status", ["ALL"] + CHANGE_STATUSES, key="change_status_filter"
        )
    with col2:
        filter_customer = st.text_input("Customer", key="change_customer_filter")
    with col3:
        filter_date_from = st.date_input("From", value=None, key="change_date_from")
    with col4:
        filter_date_to = st.date_input("To", value=None, key="change_date_to")

    df = get_change_records(
        status=None if filter_status == "ALL" else filter_status,
        customer_name=filter_customer if filter_customer else None,
        date_from=filter_date_from.strftime("%Y-%m-%d") if filter_date_from else None,
        date_to=filter_date_to.strftime("%Y-%m-%d") if filter_date_to else None,
    )

    if df.empty:
        st.info("No change records found for the selected filters")
        return

    df_display = df.copy()

    date_col = None
    for col in ["created_at", "updated_at", "date"]:
        if col in df_display.columns:
            date_col = col
            break

    if date_col:
        df_display[date_col] = pd.to_datetime(df_display[date_col], errors="coerce")
        df_display["Date"] = df_display[date_col].dt.strftime("%Y-%m-%d %H:%M")
    else:
        df_display["Date"] = "N/A"

    def get_status_label(status):
        if status == "COLLECTED":
            return "COLLECTED"
        elif status == "PARTIAL_COLLECTED":
            return "PARTIAL"
        elif status == "WRITTEN_OFF":
            return "WRITTEN OFF"
        else:
            return "UNCOLLECTED"

    df_display["Status"] = df_display["status"].apply(get_status_label)

    rename_map = {
        "customer_name": "Customer",
        "amount": "Amount",
        "amount_collected": "Collected",
        "balance": "Balance",
        "change_id": "ID",
        "description": "Description",
    }
    df_display = df_display.rename(columns=rename_map)

    st.markdown("### All Change Records")
    st.dataframe(
        df_display[
            ["Date", "Customer", "Description", "Amount", "Collected", "Balance", "Status", "ID"]
        ],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
            "Collected": st.column_config.NumberColumn("Collected", format="$%.2f"),
            "Balance": st.column_config.NumberColumn("Balance", format="$%.2f"),
            "Description": st.column_config.TextColumn("Description", width="medium"),
        },
    )

    # ---------------- Collection section ----------------
    st.markdown("### Collect Change")

    uncollected_df = df[
        (df["balance"] > 0) & (df["status"].isin(["UNCOLLECTED", "PARTIAL_COLLECTED"]))
    ]

    if uncollected_df.empty:
        st.info("All changes have been collected")
    else:
        collection_options = []
        for _, row in uncollected_df.iterrows():
            customer = row.get("customer_name", "Unknown")
            balance = float(row.get("balance", 0))
            description = row.get("description", "")
            desc_short = description[:30] + "..." if len(description) > 30 else description
            collection_options.append(
                f"{customer} - Balance: ${balance:.2f} ({desc_short})"
            )

        col1, col2, col3 = st.columns(3)

        with col1:
            selected_option = st.selectbox(
                "Select Change to Collect",
                collection_options,
                key="collect_change_select",
            )

        if selected_option:
            selected_idx = collection_options.index(selected_option)
            selected_row = uncollected_df.iloc[selected_idx]
            change_id = selected_row.get("change_id", "")
            balance = float(selected_row.get("balance", 0))
            description = selected_row.get("description", "")

            st.info(f"**Description:** {description}")

            with col2:
                collect_amount = st.number_input(
                    "Amount to Collect ($)",
                    min_value=0.01,
                    max_value=balance,
                    value=balance,
                    step=0.01,
                    key="collect_amount_input",
                )

            with col3:
                if st.button(
                    "Collect Payment",
                    use_container_width=True,
                    key="collect_change_btn",
                ):
                    if collect_amount > 0:
                        success, message = collect_change(
                            change_id=change_id, amount=collect_amount
                        )
                        if success:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)
                    else:
                        st.error("Please enter an amount to collect")

    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            "Total Change",
            f"${df['amount'].sum():,.2f}" if "amount" in df.columns else "$0.00",
        )
    with col2:
        st.metric(
            "Total Collected",
            f"${df['amount_collected'].sum():,.2f}"
            if "amount_collected" in df.columns
            else "$0.00",
        )
    with col3:
        st.metric(
            "Total Balance",
            f"${df['balance'].sum():,.2f}" if "balance" in df.columns else "$0.00",
        )


# ==============================
# CREDIT MANAGEMENT TAB
# ==============================

def credit_management_tab():
    summary = get_credit_summary()
    overdue_df = get_overdue_credits(days=30)
    bad_debt_customers_df = get_bad_debt_customers()

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Credit", f"${summary['total_credit']:,.2f}")
    with col2:
        st.metric("Total Paid", f"${summary['total_paid']:,.2f}")
    with col3:
        st.metric("Balance", f"${summary['total_balance']:,.2f}")
    with col4:
        st.metric("Active Loans", f"{summary['active_count']}")
    with col5:
        st.metric("Bad Debts", f"{summary.get('bad_debt_count', 0)}")

    # ---------------- Bad-debt customer block banner ----------------
    if not bad_debt_customers_df.empty:
        blocked_names = sorted(
            set(bad_debt_customers_df["customer_name"].astype(str).tolist())
        )
        st.error(
            "🚫 **Credit BLOCKED for the following customers (unresolved Bad Debt / Written Off):**\n\n"
            + ", ".join(f"**{n}**" for n in blocked_names)
            + "\n\nNew credit cannot be issued until their existing bad debt "
            "is fully recovered via the Recovery Payment section below."
        )

    if not overdue_df.empty:
        st.error(f"WARNING: {len(overdue_df)} credit(s) are overdue!")

    st.divider()

    # ---------------- Overdue Credits (action required) ----------------
    if not overdue_df.empty:
        with st.expander(
            f"Overdue Credits ({len(overdue_df)}) - action required",
            expanded=False,
        ):
            st.caption(
                f"Credits overdue by more than {BAD_DEBT_DAYS_THRESHOLD} days are "
                f"automatically flagged as Bad Debt."
            )
            od_display = overdue_df.copy()
            for col in ["amount", "amount_paid", "balance"]:
                if col in od_display.columns:
                    od_display[col] = pd.to_numeric(od_display[col], errors="coerce").fillna(0)

            if "days_overdue" in od_display.columns:
                od_display["Days Overdue"] = od_display["days_overdue"]

            od_display = od_display.rename(
                columns={
                    "customer_name": "Customer",
                    "description": "Description",
                    "balance": "Balance",
                    "expected_repayment_date": "Due Date",
                    "credit_id": "ID",
                }
            )
            cols = [
                c
                for c in [
                    "Customer",
                    "Description",
                    "Balance",
                    "Due Date",
                    "Days Overdue",
                    "ID",
                ]
                if c in od_display.columns
            ]
            st.dataframe(od_display[cols], use_container_width=True, hide_index=True)

            st.markdown("**Manually Write Off as Bad Debt**")
            wo_options = []
            for _, r in overdue_df.iterrows():
                wo_options.append(
                    f"{r.get('customer_name', '?')} - "
                    f"${float(r.get('balance', 0)):.2f} - "
                    f"{r.get('credit_id', '')}"
                )
            selected_wo = st.selectbox(
                "Select credit to write off", wo_options, key="wo_credit_select"
            )
            wo_reason = st.text_input(
                "Bad debt reason",
                value="Bad debt - overdue > 2 months",
                key="wo_credit_reason",
            )
            if st.button("Write Off Selected Credit", key="wo_credit_btn"):
                if selected_wo:
                    idx = wo_options.index(selected_wo)
                    row = overdue_df.iloc[idx]
                    ok, msg = write_off_credit(
                        row.get("credit_id"), wo_reason or "Bad debt"
                    )
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

    # ---------------- Bad Debts / Written Off Credits (visible + recovery) ----------------
    bad_debt_credits = get_bad_debt_credits()
    if not bad_debt_credits.empty:
        with st.expander(
            f"Bad Debts / Written Off Credits ({len(bad_debt_credits)}) - click to view / recover",
            expanded=False,
        ):
            bd_display = bad_debt_credits.copy()
            for col in ["amount", "amount_paid", "balance"]:
                if col in bd_display.columns:
                    bd_display[col] = pd.to_numeric(bd_display[col], errors="coerce").fillna(0)

            if "written_off_at" in bd_display.columns:
                bd_display["Written Off At"] = pd.to_datetime(
                    bd_display["written_off_at"], errors="coerce"
                ).dt.strftime("%Y-%m-%d %H:%M")
            else:
                bd_display["Written Off At"] = "N/A"

            bd_display["Outstanding"] = (
                bd_display["amount"] - bd_display["amount_paid"]
            ).clip(lower=0)

            bd_display = bd_display.rename(
                columns={
                    "customer_name": "Customer",
                    "description": "Description",
                    "amount": "Original Amount",
                    "amount_paid": "Paid",
                    "credit_type": "Type",
                    "status": "Status",
                    "written_off_reason": "Reason",
                    "credit_id": "ID",
                }
            )

            bd_cols = [
                c
                for c in [
                    "Written Off At",
                    "Customer",
                    "Description",
                    "Original Amount",
                    "Paid",
                    "Outstanding",
                    "Type",
                    "Status",
                    "Reason",
                    "ID",
                ]
                if c in bd_display.columns
            ]

            st.dataframe(
                bd_display[bd_cols],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Original Amount": st.column_config.NumberColumn(
                        "Original Amount", format="$%.2f"
                    ),
                    "Paid": st.column_config.NumberColumn("Paid", format="$%.2f"),
                    "Outstanding": st.column_config.NumberColumn(
                        "Outstanding", format="$%.2f"
                    ),
                    "Description": st.column_config.TextColumn(
                        "Description", width="medium"
                    ),
                },
            )

            total_bad_debt_amount = (
                float(bad_debt_credits["amount"].sum())
                if "amount" in bad_debt_credits.columns
                else 0
            )
            total_bad_debt_outstanding = (
                (
                    bad_debt_credits["amount"] - bad_debt_credits["amount_paid"]
                ).clip(lower=0).sum()
                if "amount" in bad_debt_credits.columns
                and "amount_paid" in bad_debt_credits.columns
                else 0
            )
            st.caption(
                f"Total original value: **${total_bad_debt_amount:,.2f}** — "
                f"total outstanding (still unrecovered): "
                f"**${total_bad_debt_outstanding:,.2f}** across "
                f"**{len(bad_debt_credits)}** record(s)."
            )

            # ---------------- Recovery Payment ----------------
            st.markdown("---")
            st.markdown("**Recovery Payment**")
            st.caption(
                "If the customer comes back and pays a bad-debt / written-off credit, "
                "record it here. A full payment removes the row completely; "
                "a partial payment keeps it visible with the amount noted. "
                "Once the balance reaches zero, the customer is automatically "
                "unblocked for new credit."
            )

            rec_options = []
            for _, r in bad_debt_credits.iterrows():
                original = float(r.get("amount", 0) or 0)
                paid = float(r.get("amount_paid", 0) or 0)
                outstanding = max(original - paid, 0.0)
                rec_options.append(
                    f"{r.get('customer_name', '?')} - "
                    f"Outstanding: ${outstanding:.2f} - "
                    f"{r.get('credit_id', '')}"
                )

            rec_col1, rec_col2, rec_col3, rec_col4 = st.columns([2, 1, 1, 1])
            with rec_col1:
                selected_rec = st.selectbox(
                    "Select bad debt to recover",
                    rec_options,
                    key="rec_credit_select",
                )
            with rec_col2:
                rec_amount = st.number_input(
                    "Payment Amount ($)",
                    min_value=0.01,
                    step=0.01,
                    value=0.01,
                    key="rec_credit_amount",
                )
            with rec_col3:
                rec_method = st.selectbox(
                    "Payment Method",
                    ["CASH", "BANK", "MOBILE_MONEY", "ECOCASH"],
                    key="rec_credit_method",
                )
            with rec_col4:
                rec_note = st.text_input(
                    "Note (optional)",
                    value="Recovery payment",
                    key="rec_credit_note",
                )

            if st.button(
                "Record Recovery Payment",
                key="rec_credit_btn",
                use_container_width=True,
            ):
                if not selected_rec:
                    st.error("Please select a bad debt to recover")
                else:
                    idx = rec_options.index(selected_rec)
                    row = bad_debt_credits.iloc[idx]
                    credit_id = row.get("credit_id")
                    ok, msg = recover_bad_debt_credit(
                        credit_id,
                        rec_amount,
                        payment_method=rec_method or "CASH",
                        note=rec_note or "Recovery payment",
                    )
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

    st.divider()

    # ---------------- Record New Credit ----------------
    with st.form("record_credit_form"):
        st.markdown("### Record New Credit/Loan")
        st.caption(
            "If this customer already has an active credit, the amount will be MERGED "
            "into that existing row (single row per customer, description combined). "
            "Customers with unresolved bad debt cannot receive new credit."
        )

        customer_name, phone = get_customer_name_input("credit")
        new_credit_amount = st.number_input(
            "Amount ($)", min_value=0.01, step=0.01, key="new_credit_amount"
        )
        new_credit_type = st.selectbox(
            "Credit Type", CREDIT_TYPES, key="new_credit_type"
        )
        new_credit_desc = st.text_area(
            "Description (Required)",
            key="new_credit_desc",
            placeholder="e.g., Loan for goods, Cash advance, etc.",
        )
        new_credit_repayment = st.date_input(
            "Expected Repayment Date",
            value=datetime.now() + timedelta(days=30),
            key="new_credit_repayment",
        )

        # Live block check (shows as soon as a bad-debt customer is picked)
        live_blocked, live_reason = (False, "")
        if customer_name and customer_name.strip():
            live_blocked, live_reason = is_customer_in_bad_debt(customer_name)
        if live_blocked:
            st.error(f"🚫 {live_reason}")
            st.caption(
                "The Record Credit button below will be blocked until this "
                "customer's bad debt is fully recovered."
            )

        submit = st.form_submit_button("Record Credit", use_container_width=True)

        if submit:
            if not customer_name:
                st.error("Customer/Person name is required")
            elif new_credit_amount <= 0:
                st.error("Amount must be greater than 0")
            elif not new_credit_desc or not new_credit_desc.strip():
                st.error("Description is required")
            else:
                success, message, credit_id = create_credit_record(
                    customer_name=customer_name,
                    amount=new_credit_amount,
                    credit_type=new_credit_type,
                    description=new_credit_desc,
                    phone=phone,
                    expected_repayment=(
                        new_credit_repayment.strftime("%Y-%m-%d")
                        if new_credit_repayment
                        else None
                    ),
                )
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)

    st.divider()

    # ---------------- Filters + Main Table ----------------
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        filter_credit_status = st.selectbox(
            "Status", ["ALL"] + CREDIT_STATUSES, key="credit_status_filter"
        )
    with col2:
        filter_credit_type = st.selectbox(
            "Type", ["ALL"] + CREDIT_TYPES, key="credit_type_filter"
        )
    with col3:
        filter_credit_customer = st.text_input(
            "Customer", key="credit_customer_filter"
        )
    with col4:
        filter_credit_date_from = st.date_input(
            "From", value=None, key="credit_date_from"
        )
    with col5:
        filter_credit_date_to = st.date_input(
            "To", value=None, key="credit_date_to"
        )

    df = get_credit_records(
        status=None if filter_credit_status == "ALL" else filter_credit_status,
        credit_type=None if filter_credit_type == "ALL" else filter_credit_type,
        customer_name=filter_credit_customer if filter_credit_customer else None,
        date_from=(
            filter_credit_date_from.strftime("%Y-%m-%d")
            if filter_credit_date_from
            else None
        ),
        date_to=(
            filter_credit_date_to.strftime("%Y-%m-%d")
            if filter_credit_date_to
            else None
        ),
    )

    if df.empty:
        st.info("No credit records found for the selected filters")
        return

    df_display = df.copy()

    date_col = None
    for col in ["created_at", "updated_at", "date"]:
        if col in df_display.columns:
            date_col = col
            break

    if date_col:
        df_display[date_col] = pd.to_datetime(df_display[date_col], errors="coerce")
        df_display["Date"] = df_display[date_col].dt.strftime("%Y-%m-%d %H:%M")
    else:
        df_display["Date"] = "N/A"

    def get_overdue_status(row):
        status = row.get("status", "ACTIVE")
        expected = row.get("expected_repayment_date", "")
        if status in ["ACTIVE", "PARTIAL_PAID"] and expected:
            try:
                due_date = pd.to_datetime(expected)
                if due_date < datetime.now():
                    days = (datetime.now() - due_date).days
                    return f"OVERDUE ({days}d)"
            except Exception:
                pass
        return status

    df_display["Status_Display"] = df_display.apply(get_overdue_status, axis=1)

    rename_map = {
        "customer_name": "Customer",
        "amount": "Amount",
        "amount_paid": "Paid",
        "balance": "Balance",
        "credit_type": "Type",
        "expected_repayment_date": "Due Date",
        "credit_id": "ID",
        "description": "Description",
    }
    df_display = df_display.rename(columns=rename_map)

    st.markdown("### All Credit Records")

    display_cols = [
        "Date",
        "Customer",
        "Description",
        "Amount",
        "Paid",
        "Balance",
        "Type",
        "Due Date",
        "Status_Display",
        "ID",
    ]
    available_cols = [col for col in display_cols if col in df_display.columns]

    st.dataframe(
        df_display[available_cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
            "Paid": st.column_config.NumberColumn("Paid", format="$%.2f"),
            "Balance": st.column_config.NumberColumn("Balance", format="$%.2f"),
            "Description": st.column_config.TextColumn("Description", width="medium"),
        },
    )

    # ---------------- Payment section ----------------
    st.markdown("### Record Payment")

    active_credits = df[
        (df["balance"] > 0) & (df["status"].isin(["ACTIVE", "PARTIAL_PAID"]))
    ]

    if active_credits.empty:
        st.info("All credits are fully paid")
    else:
        payment_options = []
        for _, row in active_credits.iterrows():
            customer = row.get("customer_name", "Unknown")
            balance = float(row.get("balance", 0))
            description = row.get("description", "")
            desc_short = description[:30] + "..." if len(description) > 30 else description
            payment_options.append(
                f"{customer} - Balance: ${balance:.2f} ({desc_short})"
            )

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            selected_payment = st.selectbox(
                "Select Credit to Pay", payment_options, key="credit_payment_select"
            )

        if selected_payment:
            selected_idx = payment_options.index(selected_payment)
            selected_row = active_credits.iloc[selected_idx]
            credit_id = selected_row.get("credit_id", "")
            balance = float(selected_row.get("balance", 0))
            description = selected_row.get("description", "")

            st.info(f"**Description:** {description}")

            with col2:
                payment_amount = st.number_input(
                    "Payment Amount ($)",
                    min_value=0.01,
                    max_value=balance,
                    value=balance,
                    step=0.01,
                    key="credit_payment_amount",
                )

            with col3:
                payment_method = st.selectbox(
                    "Payment Method",
                    ["CASH", "BANK", "MOBILE_MONEY", "ECOCASH"],
                    key="credit_payment_method",
                )

            with col4:
                if st.button(
                    "Record Payment",
                    use_container_width=True,
                    key="record_credit_payment",
                ):
                    if payment_amount > 0:
                        success, message = record_credit_payment(
                            credit_id=credit_id,
                            amount=payment_amount,
                            payment_note="Payment recorded",
                            payment_method=payment_method,
                        )
                        if success:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)
                    else:
                        st.error("Please enter a payment amount")

    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            "Total Credit",
            f"${df['amount'].sum():,.2f}" if "amount" in df.columns else "$0.00",
        )
    with col2:
        st.metric(
            "Total Paid",
            f"${df['amount_paid'].sum():,.2f}"
            if "amount_paid" in df.columns
            else "$0.00",
        )
    with col3:
        st.metric(
            "Total Balance",
            f"${df['balance'].sum():,.2f}" if "balance" in df.columns else "$0.00",
        )


# ==============================
# GAS SALES TAB
# ==============================

def gas_sales_tab():
    all_records = get_gas_sales()
    today = datetime.now().date()

    today_df = pd.DataFrame()
    previous_df = pd.DataFrame()
    today_total_kgs = 0
    today_total_amount = 0
    today_count = 0
    previous_total_kgs = 0
    previous_total_amount = 0
    previous_count = 0
    overall_total_kgs = 0
    overall_total_amount = 0
    overall_count = 0

    if not all_records.empty:
        date_col = None
        for col in ["sale_date", "created_at", "date"]:
            if col in all_records.columns:
                date_col = col
                break

        if date_col:
            all_records[date_col] = pd.to_datetime(
                all_records[date_col], errors="coerce"
            )
            all_records = all_records.dropna(subset=[date_col])

            if not all_records.empty:
                if "kgs" in all_records.columns:
                    all_records["kgs"] = pd.to_numeric(
                        all_records["kgs"], errors="coerce"
                    ).fillna(0)
                if "total_amount" in all_records.columns:
                    all_records["total_amount"] = pd.to_numeric(
                        all_records["total_amount"], errors="coerce"
                    ).fillna(0)

                all_records["is_today"] = all_records[date_col].dt.date == today

                today_df = all_records[all_records["is_today"]].copy()
                previous_df = all_records[~all_records["is_today"]].copy()

                if not today_df.empty:
                    today_total_kgs = (
                        float(today_df["kgs"].sum())
                        if "kgs" in today_df.columns
                        else 0
                    )
                    today_total_amount = (
                        float(today_df["total_amount"].sum())
                        if "total_amount" in today_df.columns
                        else 0
                    )
                    today_count = len(today_df)

                if not previous_df.empty:
                    previous_total_kgs = (
                        float(previous_df["kgs"].sum())
                        if "kgs" in previous_df.columns
                        else 0
                    )
                    previous_total_amount = (
                        float(previous_df["total_amount"].sum())
                        if "total_amount" in previous_df.columns
                        else 0
                    )
                    previous_count = len(previous_df)

                overall_total_kgs = (
                    float(all_records["kgs"].sum())
                    if "kgs" in all_records.columns
                    else 0
                )
                overall_total_amount = (
                    float(all_records["total_amount"].sum())
                    if "total_amount" in all_records.columns
                    else 0
                )
                overall_count = len(all_records)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total KGs Sold", f"{overall_total_kgs:,.2f}")
    with col2:
        st.metric("Total Amount", f"${overall_total_amount:,.2f}")
    with col3:
        st.metric("Total Sales", f"{overall_count}")

    st.divider()

    with st.form("record_gas_form"):
        st.markdown("### Record Gas Sale")
        st.caption("Enter the amount paid and price per KG to calculate KGs sold")

        customer_name, phone = get_customer_name_input("gas")
        new_gas_price = st.number_input(
            "Price per KG ($)", min_value=0.01, step=0.01, key="new_gas_price"
        )
        new_gas_amount = st.number_input(
            "Amount Customer Paid ($)",
            min_value=0.01,
            step=0.01,
            key="new_gas_amount",
        )
        new_gas_desc = st.text_area("Description (Optional)", key="new_gas_desc")

        if new_gas_price > 0 and new_gas_amount > 0:
            calculated_kgs = new_gas_amount / new_gas_price
            st.info(
                f"Calculated KGs: **{calculated_kgs:.2f}** (${new_gas_price:.2f}/KG)"
            )

        if st.form_submit_button("Record Gas Sale", use_container_width=True):
            if not customer_name:
                st.error("Customer name is required")
            elif new_gas_price <= 0:
                st.error("Price per KG must be greater than 0")
            elif new_gas_amount <= 0:
                st.error("Amount must be greater than 0")
            else:
                success, message, gas_sale_id = create_gas_sale(
                    customer_name=customer_name,
                    amount_paid=new_gas_amount,
                    price_per_kg=new_gas_price,
                    description=new_gas_desc,
                )
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)

    st.divider()

    col1, col2, col3 = st.columns(3)
    with col1:
        filter_gas_customer = st.text_input(
            "Filter by Customer", key="gas_customer_filter"
        )
    with col2:
        filter_gas_date_from = st.date_input("From", value=None, key="gas_date_from")
    with col3:
        filter_gas_date_to = st.date_input("To", value=None, key="gas_date_to")

    df = get_gas_sales(
        customer_name=filter_gas_customer if filter_gas_customer else None,
        date_from=(
            filter_gas_date_from.strftime("%Y-%m-%d")
            if filter_gas_date_from
            else None
        ),
        date_to=(
            filter_gas_date_to.strftime("%Y-%m-%d") if filter_gas_date_to else None
        ),
    )

    if df.empty:
        st.info("No gas sales records found")
        return

    df_display = df.copy()

    date_col = None
    for col in ["sale_date", "created_at", "date"]:
        if col in df_display.columns:
            date_col = col
            break

    if date_col:
        df_display[date_col] = pd.to_datetime(df_display[date_col], errors="coerce")
        df_display = df_display.dropna(subset=[date_col])
        df_display["Date"] = df_display[date_col].dt.strftime("%Y-%m-%d %H:%M")
        df_display["is_today"] = df_display[date_col].dt.date == today
    else:
        df_display["Date"] = "N/A"
        df_display["is_today"] = False

    if "kgs" in df_display.columns:
        df_display["kgs"] = pd.to_numeric(df_display["kgs"], errors="coerce").fillna(0)
    if "total_amount" in df_display.columns:
        df_display["total_amount"] = pd.to_numeric(
            df_display["total_amount"], errors="coerce"
        ).fillna(0)

    today_df_filtered = df_display[df_display["is_today"]].copy()
    previous_df_filtered = df_display[~df_display["is_today"]].copy()

    rename_map = {
        "customer_name": "Customer",
        "kgs": "KGs",
        "price_per_kg": "Price/KG",
        "total_amount": "Total",
        "gas_sale_id": "ID",
    }

    display_cols = ["Date", "Customer", "KGs", "Price/KG", "Total", "ID"]

    st.markdown("### Today's Records")

    if not today_df_filtered.empty:
        today_total_kgs_display = (
            float(today_df_filtered["kgs"].sum())
            if "kgs" in today_df_filtered.columns
            else 0
        )
        today_total_amount_display = (
            float(today_df_filtered["total_amount"].sum())
            if "total_amount" in today_df_filtered.columns
            else 0
        )
        today_count_display = len(today_df_filtered)

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Today's KGs", f"{today_total_kgs_display:,.2f}")
        with col2:
            st.metric("Today's Amount", f"${today_total_amount_display:,.2f}")
        with col3:
            st.metric("Today's Sales", f"{today_count_display}")

        today_display = today_df_filtered.rename(columns=rename_map)
        st.dataframe(
            today_display[display_cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Total": st.column_config.NumberColumn("Total", format="$%.2f"),
                "Price/KG": st.column_config.NumberColumn(
                    "Price/KG", format="$%.2f"
                ),
                "KGs": st.column_config.NumberColumn("KGs", format="%.2f"),
            },
        )
    else:
        st.info("No gas sales recorded for today")

    st.markdown("---")
    st.markdown("### Previous Records")

    if not previous_df_filtered.empty:
        prev_total_kgs_display = (
            float(previous_df_filtered["kgs"].sum())
            if "kgs" in previous_df_filtered.columns
            else 0
        )
        prev_total_amount_display = (
            float(previous_df_filtered["total_amount"].sum())
            if "total_amount" in previous_df_filtered.columns
            else 0
        )
        prev_count_display = len(previous_df_filtered)

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Previous KGs", f"{prev_total_kgs_display:,.2f}")
        with col2:
            st.metric("Previous Amount", f"${prev_total_amount_display:,.2f}")
        with col3:
            st.metric("Previous Sales", f"{prev_count_display}")

        previous_display = previous_df_filtered.rename(columns=rename_map)
        st.dataframe(
            previous_display[display_cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Total": st.column_config.NumberColumn("Total", format="$%.2f"),
                "Price/KG": st.column_config.NumberColumn(
                    "Price/KG", format="$%.2f"
                ),
                "KGs": st.column_config.NumberColumn("KGs", format="%.2f"),
            },
        )
    else:
        st.info("No previous gas sales records")

    st.markdown("---")
    st.markdown("### Overall Summary")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total KGs", f"{overall_total_kgs:,.2f}")
    with col2:
        st.metric("Total Amount", f"${overall_total_amount:,.2f}")
    with col3:
        st.metric("Total Sales", f"{overall_count}")