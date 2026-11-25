# backend/core/branch_auth.py
# UPDATED: Dynamic branch loading from DB, status checks, package binding.

import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime

# ==============================
# DYNAMIC BRANCH LOADING
# ==============================
def get_dynamic_branches():
    """
    Loads branches from the database dynamically.
    Returns a dictionary formatted like the old hardcoded BRANCHES.
    """
    try:
        from backend.core.db_adapter import load_branches
        df = load_branches()
        branches = {}
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                code = str(row.get("branch_id", "")).strip().upper()
                if not code:
                    continue
                branches[code] = {
                    "code": code,
                    "name": row.get("branch_name", code),
                    "level": row.get("level", 1),
                    "password": str(row.get("branch_password", "admin123")),
                    "status": row.get("status", "Active"),
                    "package": row.get("package", "Bronze"),
                    "parent": None
                }
        return branches
    except Exception as e:
        print(f"[branch_auth] Error loading dynamic branches: {e}")
        return {}

# Fallback dictionary (empty, but prevents import errors if DB is down)
BRANCHES = get_dynamic_branches()

# ==============================
# SESSION BRANCH AUTHORITY
# ==============================
def set_session_branch(branch_code: str):
    """
    Make this branch code the authoritative branch for the whole session.
    """
    branch_code = str(branch_code).strip().upper()
    
    # Get the dynamic info
    branch_info = get_branch_info(branch_code)
    
    # Canonical keys used across the app
    st.session_state["current_branch_code"] = branch_code
    st.session_state["current_branch_name"] = branch_info["name"] if branch_info else branch_code
    st.session_state["user_branch"] = branch_code
    st.session_state["current_branch"] = branch_code
    
    # ADDED: Bind the package to the session so menus can filter
    if branch_info:
        st.session_state["branch_package"] = branch_info.get("package", "Bronze")

    # Ensure the session is flagged as branch-authenticated
    st.session_state["branch_authenticated"] = True
    st.session_state["branch_selected"] = True


def get_session_branch() -> str:
    return (
        st.session_state.get("user_branch")
        or st.session_state.get("current_branch_code")
        or "HO"
    )


def assert_branch_locked() -> bool:
    return bool(st.session_state.get("branch_authenticated"))


# ==============================
# BRANCH VALIDATION (UPDATED TO USE DB)
# ==============================
def validate_branch_code(branch_code):
    """Check if branch code is valid (Dynamic)"""
    branches = get_dynamic_branches()
    return str(branch_code).upper() in branches


def get_branch_info(branch_code):
    """Get branch information (Dynamic)"""
    branches = get_dynamic_branches()
    return branches.get(str(branch_code).upper(), None)


def verify_branch_password(branch_code, password):
    """Verify branch password (Dynamic)"""
    branch = get_branch_info(branch_code)
    if branch and branch.get("password") == password:
        return True
    return False


def is_branch_active(branch_code):
    """Check if branch subscription is Active"""
    branch = get_branch_info(branch_code)
    if branch:
        return branch.get("status", "Active") == "Active"
    return False


def get_branch_data_path(branch_code):
    branch_folder = Path("branch_data") / branch_code
    branch_folder.mkdir(parents=True, exist_ok=True)
    return branch_folder


def get_branch_display_name(branch_code):
    """Get display name for branch (Dynamic)"""
    branch = get_branch_info(branch_code)
    return branch["name"] if branch else str(branch_code).upper()


# ==============================
# BRANCH SESSION MANAGEMENT
# ==============================
def set_current_branch(branch_code):
    set_session_branch(branch_code)


def get_current_branch():
    return st.session_state.get("current_branch_code", None)


def get_current_branch_name():
    return st.session_state.get("current_branch_name", "Unknown")


def clear_branch_session():
    keys_to_clear = [
        "current_branch_code", "current_branch_name", "branch_authenticated", 
        "branch_selected", "user_branch", "current_branch", "branch_package"
    ]
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]


# ==============================
# BRANCH SELECTION UI
# ==============================
def branch_selection_page():
    """Page for selecting and authenticating branch"""
    
    st.title("Branch Selection")
    st.markdown("---")
    
    # Fetch fresh branches every time the page loads
    branches = get_dynamic_branches()

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Available Branches")
        
        if not branches:
            st.warning("No branches configured in the system yet. Please contact support.")
        else:
            for code, info in branches.items():
                # Visual indicator for terminated branches
                status_color = "#d32f2f" if info['status'] == "Terminated" else "#388e3c"
                status_text = info['status'].upper()
                
                st.markdown(f"""
                <div style='border:1px solid #ddd; border-radius:10px; padding:10px; margin:10px 0;'>
                    <strong>{info['name']}</strong> 
                    <span style='float:right; font-size:12px; color:{status_color}; font-weight:bold;'>{status_text}</span><br>
                    Code: {code} | Level: {info['level']} | Pkg: {info['package']}
                </div>
                """, unsafe_allow_html=True)

    with col2:
        st.markdown("### Login to Branch")

        branch_code = st.text_input(
            "Branch Code",
            placeholder="Enter branch code",
            key="branch_code_input"
        )
        branch_password = st.text_input(
            "Branch Password",
            type="password",
            placeholder="Enter branch password",
            key="branch_password_input"
        )

        if st.button("Branch Login", type="primary", use_container_width=True):
            if branch_code and branch_password:
                code_upper = branch_code.strip().upper()
                
                # 1. Validate Code
                if validate_branch_code(code_upper):
                    branch_info = get_branch_info(code_upper)
                    
                    # 2. Check if Terminated
                    if not is_branch_active(code_upper):
                        st.error("This branch's subscription has been terminated. Please contact Aziel Investments support.")
                    
                    # 3. Verify Password
                    elif verify_branch_password(code_upper, branch_password):
                        set_session_branch(code_upper)
                        st.success(f"Access granted to {get_branch_display_name(code_upper)}")
                        st.rerun()
                    else:
                        st.error("Invalid branch password")
                else:
                    st.error("Invalid branch code")
            else:
                st.error("Please enter branch code and password")