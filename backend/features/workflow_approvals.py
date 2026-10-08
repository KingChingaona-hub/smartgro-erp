# backend/features/workflow_approvals.py
# Workflow Approvals — branch-aware.
#
# Branch scoping:
#     branch_id = None          -> session branch
#     branch_id = "HO"/"NAT"/.. -> that single branch
#     branch_id = "__ALL__"     -> aggregate view (owner only)
#
# Every row in approvals.csv and approval_history.csv carries a branch_code.
# Reads filter by the caller's scope; writes use the same scope resolution as
# auth.py and db_adapter. Approving a request that belongs to another branch
# is refused.

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import json
import re

from backend.core.db_adapter import (
    load_sales,
    load_products,
    load_purchases,
    load_branches,
)


# ==============================
# FILE PATHS
# ==============================
DATA_DIR = Path("data")
APPROVAL_FILE = DATA_DIR / "approvals.csv"
APPROVAL_SETTINGS_FILE = DATA_DIR / "approval_settings.json"
APPROVAL_HISTORY_FILE = DATA_DIR / "approval_history.csv"

APPROVAL_COLUMNS = [
    "approval_id", "type", "reference", "requested_by", "requested_date",
    "amount", "details", "status", "approved_by", "approved_date",
    "rejected_by", "rejected_date", "rejection_reason", "level", "branch_code",
]

APPROVAL_HISTORY_COLUMNS = [
    "history_id", "approval_id", "action", "performed_by", "timestamp",
    "comments", "old_status", "new_status", "branch_code",
]


# ==============================
# BRANCH RESOLUTION
# ==============================
ALL_BRANCHES = "__ALL__"


def _resolve_branch(branch_id=None):
    if branch_id is not None:
        return branch_id
    try:
        return (
            st.session_state.get("current_branch_code")
            or st.session_state.get("user_branch")
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


def _branch_slug(branch_id):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(branch_id)).strip("_").upper() or "HO"


def _branch_scope_selector(branches_df, key_suffix=""):
    role = st.session_state.get("role", "cashier")
    is_owner = role in ("owner", "admin")

    if is_owner and branches_df is not None and not branches_df.empty:
        options = ["All Branches"] + [
            f"{r['branch_name']} ({r['branch_id']})"
            for _, r in branches_df.iterrows()
        ]
        choice = st.selectbox(
            "Branch scope",
            options,
            key=f"approvals_branch_scope{key_suffix}",
            help="Owners may approve company-wide or one branch at a time.",
        )
        if choice == "All Branches":
            return ALL_BRANCHES, "All Branches"
        m = re.search(r"\(([^)]+)\)\s*$", choice)
        code = m.group(1).strip() if m else choice
        return code, choice

    session_branch = _resolve_branch(None)
    label = _branch_label(session_branch)
    st.info(f"Workflow approvals locked to your branch: **{label}**")
    return session_branch, label


# ==============================
# INITIALIZATION
# ==============================
def init_approval_files():
    """Initialize approval files, auto-migrating CSVs to include branch_code."""
    DATA_DIR.mkdir(exist_ok=True)

    # ---- Approvals ----
    if not APPROVAL_FILE.exists():
        pd.DataFrame(columns=APPROVAL_COLUMNS).to_csv(APPROVAL_FILE, index=False)
    else:
        try:
            existing = pd.read_csv(APPROVAL_FILE)
            if "branch_code" not in existing.columns:
                existing["branch_code"] = "HO"
                existing = existing[APPROVAL_COLUMNS]
                existing.to_csv(APPROVAL_FILE, index=False)
        except Exception:
            pd.DataFrame(columns=APPROVAL_COLUMNS).to_csv(APPROVAL_FILE, index=False)

    # ---- Settings ----
    if not APPROVAL_SETTINGS_FILE.exists():
        settings = {
            "purchase_order": {
                "enabled": True, "threshold": 1000, "levels": 2, "approvers": []
            },
            "discount": {
                "enabled": True, "threshold": 20, "levels": 1, "approvers": []
            },
            "credit_limit": {
                "enabled": True, "threshold": 500, "levels": 2, "approvers": []
            },
            "price_change": {
                "enabled": True, "threshold": 15, "levels": 1, "approvers": []
            },
            "bulk_discount": {
                "enabled": True, "threshold": 10, "levels": 2, "approvers": []
            },
        }
        with open(APPROVAL_SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=2)

    # ---- History ----
    if not APPROVAL_HISTORY_FILE.exists():
        pd.DataFrame(columns=APPROVAL_HISTORY_COLUMNS).to_csv(APPROVAL_HISTORY_FILE, index=False)
    else:
        try:
            existing = pd.read_csv(APPROVAL_HISTORY_FILE)
            if "branch_code" not in existing.columns:
                existing["branch_code"] = "HO"
                existing = existing[APPROVAL_HISTORY_COLUMNS]
                existing.to_csv(APPROVAL_HISTORY_FILE, index=False)
        except Exception:
            pd.DataFrame(columns=APPROVAL_HISTORY_COLUMNS).to_csv(APPROVAL_HISTORY_FILE, index=False)


# ==============================
# LOAD / SAVE
# ==============================
def load_approvals(branch_id=None):
    """
    Load approvals scoped to a branch. `__ALL__` returns everything.
    Legacy rows without `branch_code` are auto-patched to "HO".
    """
    init_approval_files()
    try:
        df = pd.read_csv(APPROVAL_FILE)
    except Exception:
        return pd.DataFrame(columns=APPROVAL_COLUMNS)

    if "branch_code" not in df.columns:
        df["branch_code"] = "HO"

    if branch_id is None:
        return df
    branch_id = _resolve_branch(branch_id)
    if _is_all_branches(branch_id):
        return df
    return df[df["branch_code"].astype(str).str.upper() == str(branch_id).upper()].copy()


def save_approvals(df):
    df.to_csv(APPROVAL_FILE, index=False)


def load_approval_settings():
    init_approval_files()
    with open(APPROVAL_SETTINGS_FILE, "r") as f:
        return json.load(f)


def save_approval_settings(settings):
    with open(APPROVAL_SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)


def load_approval_history(branch_id=None):
    init_approval_files()
    try:
        df = pd.read_csv(APPROVAL_HISTORY_FILE)
    except Exception:
        return pd.DataFrame(columns=APPROVAL_HISTORY_COLUMNS)

    if "branch_code" not in df.columns:
        df["branch_code"] = "HO"

    if branch_id is None:
        return df
    branch_id = _resolve_branch(branch_id)
    if _is_all_branches(branch_id):
        return df
    return df[df["branch_code"].astype(str).str.upper() == str(branch_id).upper()].copy()


def save_approval_history(df):
    df.to_csv(APPROVAL_HISTORY_FILE, index=False)


# ==============================
# TOAST
# ==============================
def show_toast(message, type="info"):
    colors = {
        "info": "#4CAF50", "success": "#4CAF50",
        "warning": "#FF9800", "error": "#f44336",
    }
    icon = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌"}

    toast_html = f"""
    <div style="
        position: fixed; bottom: 20px; right: 20px;
        background-color: {colors.get(type, '#4CAF50')};
        color: white; padding: 12px 24px; border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        z-index: 9999; animation: slideIn 0.5s ease; max-width: 400px;
    ">
        <span style="font-size: 1.2rem; margin-right: 8px;">{icon.get(type, 'ℹ️')}</span>
        {message}
    </div>
    <style>
        @keyframes slideIn {{
            from {{ transform: translateX(100%); opacity: 0; }}
            to {{ transform: translateX(0); opacity: 1; }}
        }}
    </style>
    """
    st.markdown(toast_html, unsafe_allow_html=True)


# ==============================
# APPROVAL OPERATIONS
# ==============================
def create_approval_request(approval_type, reference, amount, details,
                            requested_by, branch_id=None):
    """Create an approval request tagged with the current branch."""
    branch_id = _resolve_branch(branch_id)
    if _is_all_branches(branch_id):
        return {
            "success": False,
            "approval_id": None,
            "status": "REFUSED",
            "message": "Cannot create an approval request against All Branches. Pick a specific branch.",
        }

    df = load_approvals(branch_id=ALL_BRANCHES)  # raw list to count ids
    settings = load_approval_settings()

    approval_id = f"APP{len(df)+1:08d}"
    level = settings.get(approval_type, {}).get("levels", 1)
    threshold = settings.get(approval_type, {}).get("threshold", 0)

    if amount <= threshold:
        new_approval = pd.DataFrame([{
            "approval_id": approval_id,
            "type": approval_type,
            "reference": reference,
            "requested_by": requested_by,
            "requested_date": datetime.now().isoformat(),
            "amount": amount,
            "details": details,
            "status": "AUTO_APPROVED",
            "approved_by": "System",
            "approved_date": datetime.now().isoformat(),
            "rejected_by": "",
            "rejected_date": "",
            "rejection_reason": "",
            "level": 0,
            "branch_code": _branch_slug(branch_id),
        }])
        df = pd.concat([df, new_approval], ignore_index=True)
        save_approvals(df)
        return {
            "success": True,
            "approval_id": approval_id,
            "status": "AUTO_APPROVED",
            "message": f"Auto-approved (below threshold) in {_branch_label(branch_id)}",
        }

    new_approval = pd.DataFrame([{
        "approval_id": approval_id,
        "type": approval_type,
        "reference": reference,
        "requested_by": requested_by,
        "requested_date": datetime.now().isoformat(),
        "amount": amount,
        "details": details,
        "status": "PENDING",
        "approved_by": "",
        "approved_date": "",
        "rejected_by": "",
        "rejected_date": "",
        "rejection_reason": "",
        "level": 1,
        "branch_code": _branch_slug(branch_id),
    }])
    df = pd.concat([df, new_approval], ignore_index=True)
    save_approvals(df)

    return {
        "success": True,
        "approval_id": approval_id,
        "status": "PENDING",
        "message": f"Approval request created for {_branch_label(branch_id)}.",
    }


def approve_request(approval_id, approved_by, comments="", branch_id=None):
    """Approve a request. Refuses if the request is outside the caller's branch."""
    branch_id = _resolve_branch(branch_id)

    df = load_approvals(branch_id=ALL_BRANCHES)
    idx = df[df["approval_id"] == approval_id].index
    if len(idx) == 0:
        return False, "Approval request not found"

    i = idx[0]
    row_branch = str(df.loc[i, "branch_code"]).upper()

    # Scope check
    if not _is_all_branches(branch_id) and row_branch != str(branch_id).upper():
        return False, (
            f"Refused: request belongs to {row_branch}, "
            f"your scope is {branch_id}."
        )

    if df.loc[i, "status"] not in ("PENDING", "PENDING_LEVEL_2"):
        return False, f"Request already {df.loc[i, 'status']}"

    settings = load_approval_settings()
    approval_type = df.loc[i, "type"]
    levels_needed = settings.get(approval_type, {}).get("levels", 1)
    current_level = df.loc[i, "level"]

    if current_level < levels_needed:
        df.loc[i, "level"] = current_level + 1
        df.loc[i, "status"] = "PENDING_LEVEL_2"
        save_approvals(df)
        log_approval_history(
            approval_id, "LEVEL_APPROVED", approved_by, comments,
            "PENDING", "PENDING_LEVEL_2", branch_code=row_branch,
        )
        return True, (
            f"Level {current_level + 1} approval completed for {_branch_label(row_branch)}. "
            f"{levels_needed - current_level - 1} more level(s) needed."
        )

    df.loc[i, "status"] = "APPROVED"
    df.loc[i, "approved_by"] = approved_by
    df.loc[i, "approved_date"] = datetime.now().isoformat()
    save_approvals(df)
    log_approval_history(
        approval_id, "APPROVED", approved_by, comments,
        "PENDING", "APPROVED", branch_code=row_branch,
    )
    return True, f"Request approved for {_branch_label(row_branch)}"


def reject_request(approval_id, rejected_by, reason, branch_id=None):
    """Reject a request. Refuses if the request is outside the caller's branch."""
    branch_id = _resolve_branch(branch_id)

    df = load_approvals(branch_id=ALL_BRANCHES)
    idx = df[df["approval_id"] == approval_id].index
    if len(idx) == 0:
        return False, "Approval request not found"

    i = idx[0]
    row_branch = str(df.loc[i, "branch_code"]).upper()

    if not _is_all_branches(branch_id) and row_branch != str(branch_id).upper():
        return False, (
            f"Refused: request belongs to {row_branch}, "
            f"your scope is {branch_id}."
        )

    if df.loc[i, "status"] not in ("PENDING", "PENDING_LEVEL_2"):
        return False, f"Request already {df.loc[i, 'status']}"

    df.loc[i, "status"] = "REJECTED"
    df.loc[i, "rejected_by"] = rejected_by
    df.loc[i, "rejected_date"] = datetime.now().isoformat()
    df.loc[i, "rejection_reason"] = reason
    save_approvals(df)
    log_approval_history(
        approval_id, "REJECTED", rejected_by, reason,
        "PENDING", "REJECTED", branch_code=row_branch,
    )
    return True, f"Request rejected for {_branch_label(row_branch)}"


def log_approval_history(approval_id, action, performed_by, comments,
                         old_status, new_status, branch_code=None):
    df = load_approval_history(branch_id=ALL_BRANCHES)
    new_row = pd.DataFrame([{
        "history_id": f"HIST{len(df)+1:08d}",
        "approval_id": approval_id,
        "action": action,
        "performed_by": performed_by,
        "timestamp": datetime.now().isoformat(),
        "comments": comments,
        "old_status": old_status,
        "new_status": new_status,
        "branch_code": str(branch_code or _resolve_branch(None)).upper(),
    }])
    df = pd.concat([df, new_row], ignore_index=True)
    save_approval_history(df)


# ==============================
# SUMMARY (scoped)
# ==============================
def get_approval_summary(branch_id=None):
    branch_id = _resolve_branch(branch_id)
    df = load_approvals(branch_id=branch_id)

    if df.empty:
        return {
            "pending": 0, "pending_level_2": 0, "approved": 0,
            "rejected": 0, "auto_approved": 0, "by_type": {}, "total": 0,
            "branch_id": branch_id,
        }

    pending = len(df[df["status"] == "PENDING"])
    pending_level_2 = len(df[df["status"] == "PENDING_LEVEL_2"])
    approved = len(df[df["status"] == "APPROVED"])
    rejected = len(df[df["status"] == "REJECTED"])
    auto_approved = len(df[df["status"] == "AUTO_APPROVED"])
    by_type = df["type"].value_counts().to_dict()

    return {
        "pending": pending + pending_level_2,
        "pending_level_2": pending_level_2,
        "approved": approved,
        "rejected": rejected,
        "auto_approved": auto_approved,
        "by_type": by_type,
        "total": len(df),
        "branch_id": branch_id,
    }


def get_approvals_by_type(branch_id=None):
    df = load_approvals(branch_id=branch_id)
    if df.empty:
        return {}
    return df.groupby(['type', 'status']).size().unstack(fill_value=0).to_dict()


# ==============================
# DASHBOARD
# ==============================
def workflow_approvals_dashboard(branch_id=None):
    st.title("Workflow Approvals")
    st.caption("Multi-level approval workflows for purchases, discounts, and more — branch-scoped")

    role = st.session_state.get("role", "cashier")
    if role not in ["owner", "manager"]:
        st.error("Access Denied. Only owners and managers can access workflow approvals.")
        return

    try:
        branches_df = load_branches()
    except Exception:
        branches_df = pd.DataFrame()

    if branch_id is None:
        branch_id, branch_label = _branch_scope_selector(branches_df)
    else:
        branch_label = _branch_label(branch_id)

    st.caption(f"Viewing: **{branch_label}**")

    init_approval_files()

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Dashboard", "Pending Approvals", "All Requests", "History", "Settings",
    ])

    # ==============================
    # TAB 1: DASHBOARD
    # ==============================
    with tab1:
        st.markdown("## Approval Dashboard")

        summary = get_approval_summary(branch_id=branch_id)

        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Pending", summary.get("pending", 0))
        with col2:
            st.metric("Approved", summary.get("approved", 0))
        with col3:
            st.metric("Rejected", summary.get("rejected", 0))
        with col4:
            st.metric("Auto-Approved", summary.get("auto_approved", 0))
        with col5:
            st.metric("Total", summary.get("total", 0))

        if summary.get("pending", 0) > 0:
            st.warning(
                f"{summary['pending']} requests pending approval in {branch_label}"
            )

        if summary.get("by_type", {}):
            st.markdown("### Approval by Type")
            types_df = pd.DataFrame(
                list(summary["by_type"].items()), columns=["Type", "Count"]
            )
            st.bar_chart(types_df.set_index("Type"))

        st.markdown("### Recent Approvals")
        df = load_approvals(branch_id=branch_id)
        if not df.empty:
            recent = df.sort_values("requested_date", ascending=False).head(10)
            st.dataframe(
                recent[["approval_id", "type", "reference", "amount", "status",
                        "requested_by", "branch_code"]],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
                },
            )
        else:
            st.info(f"No approvals yet for {branch_label}")

    # ==============================
    # TAB 2: PENDING
    # ==============================
    with tab2:
        st.markdown(f"## Pending Approvals — {branch_label}")

        df = load_approvals(branch_id=branch_id)
        pending = df[df["status"].isin(["PENDING", "PENDING_LEVEL_2"])]

        if pending.empty:
            st.success(f"No pending approvals in {branch_label}!")
        else:
            st.info(f"{len(pending)} requests awaiting approval in {branch_label}")

            for _, approval in pending.iterrows():
                with st.container():
                    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])

                    with col1:
                        st.markdown(f"**{approval['type'].replace('_', ' ').title()}**")
                        st.caption(
                            f"ID: {approval['approval_id']} | Ref: {approval['reference']}"
                        )
                        st.caption(f"Branch: {approval['branch_code']}")
                        st.caption(f"Requested by: {approval['requested_by']}")
                        if approval['status'] == "PENDING_LEVEL_2":
                            st.warning("Level 2 Approval Required")

                    with col2:
                        st.metric("Amount", f"${approval['amount']:.2f}")

                    with col3:
                        st.caption(f"Level: {approval['level']}")
                        st.caption(f"Status: {approval['status']}")

                    with col4:
                        col_a, col_b = st.columns(2)
                        with col_a:
                            if st.button("✅",
                                         key=f"approve_{approval['approval_id']}_{branch_id}"):
                                success, message = approve_request(
                                    approval['approval_id'],
                                    st.session_state.get("username", "system"),
                                    "Approved",
                                    branch_id=branch_id,
                                )
                                if success:
                                    st.success(message)
                                    show_toast("Request approved!", "success")
                                    st.rerun()
                                else:
                                    st.error(message)

                        with col_b:
                            if st.button("❌",
                                         key=f"reject_{approval['approval_id']}_{branch_id}"):
                                reason = st.text_input(
                                    "Rejection Reason",
                                    key=f"reason_{approval['approval_id']}_{branch_id}",
                                )
                                if reason:
                                    success, message = reject_request(
                                        approval['approval_id'],
                                        st.session_state.get("username", "system"),
                                        reason,
                                        branch_id=branch_id,
                                    )
                                    if success:
                                        st.warning(message)
                                        show_toast("Request rejected", "warning")
                                        st.rerun()
                                    else:
                                        st.error(message)

                    st.markdown(f"**Details:** {approval['details']}")
                    st.markdown("---")

    # ==============================
    # TAB 3: ALL
    # ==============================
    with tab3:
        st.markdown("## All Approval Requests")
        st.caption(f"Scoped to {branch_label}")

        df = load_approvals(branch_id=branch_id)

        if df.empty:
            st.info(f"No approval requests for {branch_label}")
        else:
            col1, col2, col3 = st.columns(3)
            with col1:
                status_filter = st.selectbox(
                    "Status",
                    ["All", "PENDING", "PENDING_LEVEL_2", "APPROVED", "REJECTED", "AUTO_APPROVED"],
                    key=f"status_filter_{branch_id}",
                )
            with col2:
                type_filter = st.selectbox(
                    "Type", ["All"] + df["type"].unique().tolist(),
                    key=f"type_filter_{branch_id}",
                )
            with col3:
                date_filter = st.date_input("Date Range", value=None,
                                            key=f"date_filter_{branch_id}")

            filtered = df.copy()
            if status_filter != "All":
                filtered = filtered[filtered["status"] == status_filter]
            if type_filter != "All":
                filtered = filtered[filtered["type"] == type_filter]
            if date_filter:
                filtered["requested_date_dt"] = pd.to_datetime(
                    filtered["requested_date"]
                ).dt.date
                filtered = filtered[filtered["requested_date_dt"] == date_filter]

            st.dataframe(
                filtered,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
                },
            )

            csv = filtered.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Export Approvals (CSV)",
                data=csv,
                file_name=(
                    f"approvals_{_branch_slug(branch_id)}_"
                    f"{datetime.now().strftime('%Y%m%d')}.csv"
                ),
                mime="text/csv",
            )

    # ==============================
    # TAB 4: HISTORY
    # ==============================
    with tab4:
        st.markdown("## Approval History")
        st.caption(f"Scoped to {branch_label}")

        history_df = load_approval_history(branch_id=branch_id)

        if history_df.empty:
            st.info(f"No approval history for {branch_label}")
        else:
            col1, col2 = st.columns(2)
            with col1:
                action_filter = st.selectbox(
                    "Action", ["All"] + history_df["action"].unique().tolist(),
                    key=f"action_filter_{branch_id}",
                )
            with col2:
                performed_filter = st.text_input(
                    "Performed By (Username)", key=f"performed_filter_{branch_id}"
                )

            filtered = history_df.copy()
            if action_filter != "All":
                filtered = filtered[filtered["action"] == action_filter]
            if performed_filter:
                filtered = filtered[
                    filtered["performed_by"].str.contains(performed_filter, case=False)
                ]

            st.dataframe(filtered, use_container_width=True, hide_index=True)

    # ==============================
    # TAB 5: SETTINGS
    # ==============================
    with tab5:
        st.markdown("## Approval Settings")
        st.caption("Settings are shared across all branches.")

        settings = load_approval_settings()

        st.markdown("### Approval Rules")

        approval_types = ["purchase_order", "discount", "credit_limit",
                          "price_change", "bulk_discount"]
        type_labels = {
            "purchase_order": "Purchase Order",
            "discount": "Discount",
            "credit_limit": "Credit Limit",
            "price_change": "Price Change",
            "bulk_discount": "Bulk Discount",
        }

        for approval_type in approval_types:
            with st.expander(f"{type_labels.get(approval_type, approval_type)}"):
                col1, col2, col3 = st.columns(3)

                with col1:
                    enabled = st.checkbox(
                        "Enabled",
                        value=settings.get(approval_type, {}).get("enabled", True),
                        key=f"enabled_{approval_type}_{branch_id}",
                    )
                with col2:
                    threshold = st.number_input(
                        "Threshold",
                        min_value=0,
                        value=settings.get(approval_type, {}).get("threshold", 1000),
                        key=f"threshold_{approval_type}_{branch_id}",
                    )
                with col3:
                    levels = st.number_input(
                        "Approval Levels",
                        min_value=1, max_value=5,
                        value=settings.get(approval_type, {}).get("levels", 1),
                        key=f"levels_{approval_type}_{branch_id}",
                    )

                approvers = settings.get(approval_type, {}).get("approvers", [])
                approvers_input = st.text_input(
                    "Approvers (comma-separated usernames)",
                    value=", ".join(approvers),
                    key=f"approvers_{approval_type}_{branch_id}",
                    placeholder="admin, manager",
                )

                settings[approval_type]["enabled"] = enabled
                settings[approval_type]["threshold"] = threshold
                settings[approval_type]["levels"] = levels
                settings[approval_type]["approvers"] = [
                    x.strip() for x in approvers_input.split(",") if x.strip()
                ]

        if st.button("Save All Settings", type="primary", use_container_width=True,
                     key=f"save_settings_{branch_id}"):
            save_approval_settings(settings)
            st.success("Settings saved successfully!")
            show_toast("Approval settings updated!", "success")
            st.rerun()


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    workflow_approvals_dashboard()