# backend/core/branch_auth.py
# FIXED: no DB access at module import time (prevents circular ImportError on Streamlit Cloud).

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
    Safe to call anywhere — returns {} on any failure.
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
                    "parent": None,
                }
        return branches
    except Exception as e:
        print(f"[branch_auth] Error loading dynamic branches: {e}")
        return {}

# ==============================
# BRANCHES — EMPTY AT MODULE LOAD
# ==============================
# Do NOT call get_dynamic_branches() here.
# Doing so triggers the DB module load during import and can cause
# a circular ImportError (e.g. shift_manager -> branch_auth).
BRANCHES = {}


def _refresh_branches():
    """Populate BRANCHES on demand (called from branch_selection_page)."""
    global BRANCHES
    try:
        BRANCHES = get_dynamic_branches()
    except Exception as e:
        print(f"[branch_auth] _refresh_branches failed: {e}")
        BRANCHES = {}
    return BRANCHES


# ==============================
# SESSION BRANCH AUTHORITY
# ==============================
def set_session_branch(branch_code: str):
    branch_code = str(branch_code).strip().upper()
    branch_info = get_branch_info(branch_code)

    st.session_state["current_branch_code"] = branch_code
    st.session_state["current_branch_name"] = (
        branch_info["name"] if branch_info else branch_code
    )
    st.session_state["user_branch"] = branch_code
    st.session_state["current_branch"] = branch_code

    if branch_info:
        st.session_state["branch_package"] = branch_info.get("package", "Bronze")

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
# BRANCH VALIDATION (all dynamic)
# ==============================
def validate_branch_code(branch_code):
    return str(branch_code).upper() in get_dynamic_branches()


def get_branch_info(branch_code):
    return get_dynamic_branches().get(str(branch_code).upper(), None)


def verify_branch_password(branch_code, password):
    branch = get_branch_info(branch_code)
    if branch and branch.get("password") == password:
        return True
    return False


def is_branch_active(branch_code):
    branch = get_branch_info(branch_code)
    if branch:
        return branch.get("status", "Active") == "Active"
    return False


def get_branch_data_path(branch_code):
    branch_folder = Path("branch_data") / branch_code
    branch_folder.mkdir(parents=True, exist_ok=True)
    return branch_folder


def get_branch_display_name(branch_code):
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
    for key in [
        "current_branch_code", "current_branch_name",
        "branch_authenticated", "branch_selected",
        "user_branch", "current_branch", "branch_package",
    ]:
        st.session_state.pop(key, None)


# ==============================
# BRANCH SELECTION UI
# ==============================
def branch_selection_page():
    """Page for selecting and authenticating branch."""

    st.title("Branch Selection")
    st.markdown("---")

    # Refresh branches from DB every time this page loads
    branches = _refresh_branches()

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Available Branches")

        if not branches:
            st.warning(
                "No branches configured yet. Log in as the system owner "
                "and add a branch under **Branch Management**."
            )
        else:
            for code, info in branches.items():
                status_color = "#d32f2f" if info["status"] == "Terminated" else "#388e3c"
                status_text = info["status"].upper()
                st.markdown(
                    f"""
                    <div style='border:1px solid #ddd; border-radius:10px; padding:10px; margin:10px 0;'>
                        <strong>{info['name']}</strong>
                        <span style='float:right; font-size:12px; color:{status_color}; font-weight:bold;'>{status_text}</span><br>
                        Code: {code} | Level: {info['level']} | Pkg: {info['package']}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    with col2:
        st.markdown("### Login to Branch")

        branch_code = st.text_input(
            "Branch Code",
            placeholder="Enter branch code",
            key="branch_code_input",
        )
        branch_password = st.text_input(
            "Branch Password",
            type="password",
            placeholder="Enter branch password",
            key="branch_password_input",
        )

        if st.button("Branch Login", type="primary", use_container_width=True):
            if branch_code and branch_password:
                code_upper = branch_code.strip().upper()

                if validate_branch_code(code_upper):
                    branch_info = get_branch_info(code_upper)

                    if not is_branch_active(code_upper):
                        st.error(
                            "This branch's subscription has been terminated. "
                            "Please contact Aziel Investments support."
                        )
                    elif verify_branch_password(code_upper, branch_password):
                        set_session_branch(code_upper)
                        st.success(
                            f"Access granted to {get_branch_display_name(code_upper)}"
                        )
                        st.rerun()
                    else:
                        st.error("Invalid branch password")
                else:
                    st.error("Invalid branch code")
            else:
                st.error("Please enter branch code and password")