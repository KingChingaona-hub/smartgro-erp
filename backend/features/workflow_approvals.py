import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import json
import secrets
from backend.core.db_adapter import load_sales, load_products, load_purchases

# ==============================
# FILE PATHS
# ==============================
DATA_DIR = Path("data")
APPROVAL_FILE = DATA_DIR / "approvals.csv"
APPROVAL_SETTINGS_FILE = DATA_DIR / "approval_settings.json"
APPROVAL_HISTORY_FILE = DATA_DIR / "approval_history.csv"

# ==============================
# INITIALIZATION
# ==============================
def init_approval_files():
    """Initialize approval-related files"""
    DATA_DIR.mkdir(exist_ok=True)
    
    # Approval requests
    if not APPROVAL_FILE.exists():
        df = pd.DataFrame(columns=[
            "approval_id", "type", "reference", "requested_by", "requested_date",
            "amount", "details", "status", "approved_by", "approved_date",
            "rejected_by", "rejected_date", "rejection_reason", "level", "branch_code"
        ])
        df.to_csv(APPROVAL_FILE, index=False)
    
    # Approval settings
    if not APPROVAL_SETTINGS_FILE.exists():
        settings = {
            "purchase_order": {
                "enabled": True,
                "threshold": 1000,
                "levels": 2,
                "approvers": []
            },
            "discount": {
                "enabled": True,
                "threshold": 20,  # Percentage
                "levels": 1,
                "approvers": []
            },
            "credit_limit": {
                "enabled": True,
                "threshold": 500,
                "levels": 2,
                "approvers": []
            },
            "price_change": {
                "enabled": True,
                "threshold": 15,  # Percentage
                "levels": 1,
                "approvers": []
            },
            "bulk_discount": {
                "enabled": True,
                "threshold": 10,  # Percentage
                "levels": 2,
                "approvers": []
            }
        }
        with open(APPROVAL_SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=2)
    
    # Approval history
    if not APPROVAL_HISTORY_FILE.exists():
        df = pd.DataFrame(columns=[
            "history_id", "approval_id", "action", "performed_by", "timestamp",
            "comments", "old_status", "new_status"
        ])
        df.to_csv(APPROVAL_HISTORY_FILE, index=False)


def load_approvals():
    """Load all approval requests"""
    init_approval_files()
    if APPROVAL_FILE.exists():
        return pd.read_csv(APPROVAL_FILE)
    return pd.DataFrame(columns=[
        "approval_id", "type", "reference", "requested_by", "requested_date",
        "amount", "details", "status", "approved_by", "approved_date",
        "rejected_by", "rejected_date", "rejection_reason", "level", "branch_code"
    ])


def save_approvals(df):
    """Save approval requests"""
    df.to_csv(APPROVAL_FILE, index=False)


def load_approval_settings():
    """Load approval settings"""
    init_approval_files()
    with open(APPROVAL_SETTINGS_FILE, "r") as f:
        return json.load(f)


def save_approval_settings(settings):
    """Save approval settings"""
    with open(APPROVAL_SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)


def load_approval_history():
    """Load approval history"""
    init_approval_files()
    if APPROVAL_HISTORY_FILE.exists():
        return pd.read_csv(APPROVAL_HISTORY_FILE)
    return pd.DataFrame(columns=[
        "history_id", "approval_id", "action", "performed_by", "timestamp",
        "comments", "old_status", "new_status"
    ])


def save_approval_history(df):
    """Save approval history"""
    df.to_csv(APPROVAL_HISTORY_FILE, index=False)


# ==============================
# TOAST NOTIFICATION
# ==============================
def show_toast(message, type="info"):
    """Display a toast notification"""
    colors = {
        "info": "#4CAF50",
        "success": "#4CAF50",
        "warning": "#FF9800",
        "error": "#f44336"
    }
    icon = {
        "info": "ℹ️",
        "success": "✅",
        "warning": "⚠️",
        "error": "❌"
    }
    
    toast_html = f"""
    <div style="
        position: fixed;
        bottom: 20px;
        right: 20px;
        background-color: {colors.get(type, '#4CAF50')};
        color: white;
        padding: 12px 24px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        z-index: 9999;
        animation: slideIn 0.5s ease;
        max-width: 400px;
    ">
        <span style="font-size: 1.2rem; margin-right: 8px;">{icon.get(type, 'ℹ️')}</span>
        {message}
    </div>
    <style>
        @keyframes slideIn {{
            from {{
                transform: translateX(100%);
                opacity: 0;
            }}
            to {{
                transform: translateX(0);
                opacity: 1;
            }}
        }}
    </style>
    """
    st.markdown(toast_html, unsafe_allow_html=True)


# ==============================
# APPROVAL FUNCTIONS
# ==============================
def create_approval_request(approval_type, reference, amount, details, requested_by):
    """Create a new approval request"""
    
    df = load_approvals()
    settings = load_approval_settings()
    
    approval_id = f"APP{len(df)+1:08d}"
    level = settings.get(approval_type, {}).get("levels", 1)
    threshold = settings.get(approval_type, {}).get("threshold", 0)
    
    # Determine if approval is needed based on threshold
    if amount <= threshold:
        # Auto-approve if below threshold
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
            "branch_code": st.session_state.get("current_branch", "HO")
        }])
        
        df = pd.concat([df, new_approval], ignore_index=True)
        save_approvals(df)
        
        return {
            "success": True,
            "approval_id": approval_id,
            "status": "AUTO_APPROVED",
            "message": "Auto-approved - below threshold"
        }
    else:
        # Needs approval
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
            "branch_code": st.session_state.get("current_branch", "HO")
        }])
        
        df = pd.concat([df, new_approval], ignore_index=True)
        save_approvals(df)
        
        return {
            "success": True,
            "approval_id": approval_id,
            "status": "PENDING",
            "message": "Approval request created. Waiting for approval."
        }


def approve_request(approval_id, approved_by, comments=""):
    """Approve an approval request"""
    
    df = load_approvals()
    idx = df[df["approval_id"] == approval_id].index
    
    if len(idx) == 0:
        return False, "Approval request not found"
    
    i = idx[0]
    
    if df.loc[i, "status"] != "PENDING":
        return False, f"Request already {df.loc[i, 'status']}"
    
    settings = load_approval_settings()
    approval_type = df.loc[i, "type"]
    levels_needed = settings.get(approval_type, {}).get("levels", 1)
    current_level = df.loc[i, "level"]
    
    if current_level < levels_needed:
        # Needs higher level approval
        df.loc[i, "level"] = current_level + 1
        df.loc[i, "status"] = "PENDING_LEVEL_2"
        save_approvals(df)
        
        # Log history
        log_approval_history(approval_id, "LEVEL_APPROVED", approved_by, comments, "PENDING", "PENDING_LEVEL_2")
        
        return True, f"Level {current_level + 1} approval completed. {levels_needed - current_level - 1} more level(s) needed."
    else:
        # Fully approved
        df.loc[i, "status"] = "APPROVED"
        df.loc[i, "approved_by"] = approved_by
        df.loc[i, "approved_date"] = datetime.now().isoformat()
        save_approvals(df)
        
        # Log history
        log_approval_history(approval_id, "APPROVED", approved_by, comments, "PENDING", "APPROVED")
        
        return True, "Request approved successfully"


def reject_request(approval_id, rejected_by, reason):
    """Reject an approval request"""
    
    df = load_approvals()
    idx = df[df["approval_id"] == approval_id].index
    
    if len(idx) == 0:
        return False, "Approval request not found"
    
    i = idx[0]
    
    if df.loc[i, "status"] != "PENDING" and df.loc[i, "status"] != "PENDING_LEVEL_2":
        return False, f"Request already {df.loc[i, 'status']}"
    
    df.loc[i, "status"] = "REJECTED"
    df.loc[i, "rejected_by"] = rejected_by
    df.loc[i, "rejected_date"] = datetime.now().isoformat()
    df.loc[i, "rejection_reason"] = reason
    save_approvals(df)
    
    # Log history
    log_approval_history(approval_id, "REJECTED", rejected_by, reason, "PENDING", "REJECTED")
    
    return True, "Request rejected"


def log_approval_history(approval_id, action, performed_by, comments, old_status, new_status):
    """Log approval history"""
    
    df = load_approval_history()
    
    new_history = pd.DataFrame([{
        "history_id": f"HIST{len(df)+1:08d}",
        "approval_id": approval_id,
        "action": action,
        "performed_by": performed_by,
        "timestamp": datetime.now().isoformat(),
        "comments": comments,
        "old_status": old_status,
        "new_status": new_status
    }])
    
    df = pd.concat([df, new_history], ignore_index=True)
    save_approval_history(df)


def get_approval_summary():
    """Get approval summary statistics"""
    
    df = load_approvals()
    
    if df.empty:
        return {
            "pending": 0,
            "pending_level_2": 0,
            "approved": 0,
            "rejected": 0,
            "auto_approved": 0,
            "by_type": {},
            "total": 0
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
        "total": len(df)
    }


def get_approvals_by_type():
    """Get approval counts grouped by type"""
    df = load_approvals()
    
    if df.empty:
        return {}
    
    return df.groupby(['type', 'status']).size().unstack(fill_value=0).to_dict()


# ==============================
# WORKFLOW APPROVALS DASHBOARD
# ==============================
def workflow_approvals_dashboard():
    """Workflow Approvals Dashboard"""
    
    st.title("✅ Workflow Approvals")
    st.caption("Multi-level approval workflows for purchases, discounts, credit limits, and more")
    
    role = st.session_state.get("role", "cashier")
    
    if role not in ["owner", "manager"]:
        st.error("❌ Access Denied. Only owners and managers can access workflow approvals.")
        return
    
    init_approval_files()
    
    # ==============================
    # TABS
    # ==============================
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Dashboard",
        "📝 Pending Approvals",
        "📋 All Requests",
        "📜 History",
        "⚙️ Settings"
    ])
    
    # ==============================
    # TAB 1: DASHBOARD
    # ==============================
    with tab1:
        st.markdown("## 📊 Approval Dashboard")
        
        summary = get_approval_summary()
        
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("⏳ Pending", summary.get("pending", 0))
        with col2:
            st.metric("✅ Approved", summary.get("approved", 0))
        with col3:
            st.metric("❌ Rejected", summary.get("rejected", 0))
        with col4:
            st.metric("🤖 Auto-Approved", summary.get("auto_approved", 0))
        with col5:
            st.metric("📊 Total", summary.get("total", 0))
        
        if summary.get("pending", 0) > 0:
            st.warning(f"⚠️ {summary['pending']} requests pending approval")
        
        # Approval by type
        if summary.get("by_type", {}):
            st.markdown("### 📊 Approval by Type")
            types_df = pd.DataFrame(list(summary["by_type"].items()), columns=["Type", "Count"])
            st.bar_chart(types_df.set_index("Type"))
        
        # Recent approvals
        st.markdown("### 📋 Recent Approvals")
        df = load_approvals()
        if not df.empty:
            recent = df.sort_values("requested_date", ascending=False).head(10)
            st.dataframe(
                recent[["approval_id", "type", "reference", "amount", "status", "requested_by"]],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "amount": st.column_config.NumberColumn("Amount", format="$%.2f")
                }
            )
    
    # ==============================
    # TAB 2: PENDING APPROVALS
    # ==============================
    with tab2:
        st.markdown("## 📝 Pending Approvals")
        
        df = load_approvals()
        pending = df[df["status"].isin(["PENDING", "PENDING_LEVEL_2"])]
        
        if not pending.empty:
            st.info(f"📋 {len(pending)} requests awaiting approval")
            
            for _, approval in pending.iterrows():
                with st.container():
                    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
                    
                    with col1:
                        st.markdown(f"**{approval['type'].replace('_', ' ').title()}**")
                        st.caption(f"ID: {approval['approval_id']} | Ref: {approval['reference']}")
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
                            if st.button("✅", key=f"approve_{approval['approval_id']}"):
                                success, message = approve_request(
                                    approval['approval_id'],
                                    st.session_state.get("username", "system"),
                                    "Approved"
                                )
                                if success:
                                    st.success(message)
                                    show_toast("Request approved!", "success")
                                    st.rerun()
                                else:
                                    st.error(message)
                        
                        with col_b:
                            if st.button("❌", key=f"reject_{approval['approval_id']}"):
                                reason = st.text_input("Rejection Reason", key=f"reason_{approval['approval_id']}")
                                if reason:
                                    success, message = reject_request(
                                        approval['approval_id'],
                                        st.session_state.get("username", "system"),
                                        reason
                                    )
                                    if success:
                                        st.warning(message)
                                        show_toast("Request rejected", "warning")
                                        st.rerun()
                                    else:
                                        st.error(message)
                    
                    st.markdown(f"**Details:** {approval['details']}")
                    st.markdown("---")
        else:
            st.success("✅ No pending approvals!")
    
    # ==============================
    # TAB 3: ALL REQUESTS
    # ==============================
    with tab3:
        st.markdown("## 📋 All Approval Requests")
        
        df = load_approvals()
        
        if not df.empty:
            # Filters
            col1, col2, col3 = st.columns(3)
            with col1:
                status_filter = st.selectbox("Status", ["All", "PENDING", "PENDING_LEVEL_2", "APPROVED", "REJECTED", "AUTO_APPROVED"])
            with col2:
                type_filter = st.selectbox("Type", ["All"] + df["type"].unique().tolist())
            with col3:
                date_filter = st.date_input("Date Range", value=None)
            
            filtered_df = df.copy()
            
            if status_filter != "All":
                filtered_df = filtered_df[filtered_df["status"] == status_filter]
            
            if type_filter != "All":
                filtered_df = filtered_df[filtered_df["type"] == type_filter]
            
            if date_filter:
                filtered_df["requested_date_dt"] = pd.to_datetime(filtered_df["requested_date"]).dt.date
                filtered_df = filtered_df[filtered_df["requested_date_dt"] == date_filter]
            
            st.dataframe(
                filtered_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "amount": st.column_config.NumberColumn("Amount", format="$%.2f")
                }
            )
            
            # Export
            csv = filtered_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Export Approvals (CSV)",
                data=csv,
                file_name=f"approvals_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        else:
            st.info("No approval requests found")
    
    # ==============================
    # TAB 4: HISTORY
    # ==============================
    with tab4:
        st.markdown("## 📜 Approval History")
        
        history_df = load_approval_history()
        
        if not history_df.empty:
            # Filters
            col1, col2 = st.columns(2)
            with col1:
                action_filter = st.selectbox("Action", ["All"] + history_df["action"].unique().tolist())
            with col2:
                performed_filter = st.text_input("Performed By (Username)")
            
            filtered_history = history_df.copy()
            
            if action_filter != "All":
                filtered_history = filtered_history[filtered_history["action"] == action_filter]
            
            if performed_filter:
                filtered_history = filtered_history[filtered_history["performed_by"].str.contains(performed_filter, case=False)]
            
            st.dataframe(
                filtered_history,
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No approval history found")
    
    # ==============================
    # TAB 5: SETTINGS
    # ==============================
    with tab5:
        st.markdown("## ⚙️ Approval Settings")
        
        settings = load_approval_settings()
        
        st.markdown("### 📋 Approval Rules")
        
        approval_types = ["purchase_order", "discount", "credit_limit", "price_change", "bulk_discount"]
        type_labels = {
            "purchase_order": "Purchase Order",
            "discount": "Discount",
            "credit_limit": "Credit Limit",
            "price_change": "Price Change",
            "bulk_discount": "Bulk Discount"
        }
        
        for approval_type in approval_types:
            with st.expander(f"⚙️ {type_labels.get(approval_type, approval_type)}"):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    enabled = st.checkbox(
                        "Enabled",
                        value=settings.get(approval_type, {}).get("enabled", True),
                        key=f"enabled_{approval_type}"
                    )
                
                with col2:
                    threshold = st.number_input(
                        "Threshold",
                        min_value=0,
                        value=settings.get(approval_type, {}).get("threshold", 1000),
                        key=f"threshold_{approval_type}",
                        help=f"Auto-approve below this {'amount' if approval_type != 'discount' else '%'}"
                    )
                
                with col3:
                    levels = st.number_input(
                        "Approval Levels",
                        min_value=1,
                        max_value=5,
                        value=settings.get(approval_type, {}).get("levels", 1),
                        key=f"levels_{approval_type}"
                    )
                
                # Approvers
                approvers = settings.get(approval_type, {}).get("approvers", [])
                approvers_input = st.text_input(
                    "Approvers (comma-separated usernames)",
                    value=", ".join(approvers),
                    key=f"approvers_{approval_type}",
                    placeholder="admin, manager"
                )
                
                # Update settings for this type
                settings[approval_type]["enabled"] = enabled
                settings[approval_type]["threshold"] = threshold
                settings[approval_type]["levels"] = levels
                settings[approval_type]["approvers"] = [x.strip() for x in approvers_input.split(",") if x.strip()]
        
        if st.button("💾 Save All Settings", type="primary", use_container_width=True):
            save_approval_settings(settings)
            st.success("✅ Settings saved successfully!")
            show_toast("Approval settings updated!", "success")
            st.rerun()


if __name__ == "__main__":
    workflow_approvals_dashboard()