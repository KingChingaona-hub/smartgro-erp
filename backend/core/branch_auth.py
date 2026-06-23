import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime

# ==============================
# BRANCH CODES AND CONFIGURATION
# ==============================
BRANCHES = {
    "HO": {
        "code": "HO",
        "name": "Head Office",
        "level": 1,
        "password": "ho123",
        "parent": None
    },
    "NAT": {
        "code": "NAT",
        "name": "National Branch",
        "level": 2,
        "password": "nat123",
        "parent": "HO"
    },
    "PRO": {
        "code": "PRO",
        "name": "Provincial Branch",
        "level": 3,
        "password": "pro123",
        "parent": "NAT"
    },
    "DIS": {
        "code": "DIS",
        "name": "District Branch",
        "level": 4,
        "password": "dis123",
        "parent": "PRO"
    },
    "VIL": {
        "code": "VIL",
        "name": "Village Branch",
        "level": 5,
        "password": "vil123",
        "parent": "DIS"
    }
}


# ==============================
# BRANCH VALIDATION
# ==============================
def validate_branch_code(branch_code):
    """Check if branch code is valid"""
    return branch_code in BRANCHES


def get_branch_info(branch_code):
    """Get branch information"""
    return BRANCHES.get(branch_code, None)


def verify_branch_password(branch_code, password):
    """Verify branch password"""
    branch = BRANCHES.get(branch_code)
    if branch and branch["password"] == password:
        return True
    return False


def get_branch_data_path(branch_code):
    """Get data path for specific branch"""
    branch_folder = Path("branch_data") / branch_code
    branch_folder.mkdir(parents=True, exist_ok=True)
    return branch_folder


def get_branch_display_name(branch_code):
    """Get display name for branch"""
    branch = BRANCHES.get(branch_code)
    return branch["name"] if branch else branch_code


# ==============================
# BRANCH SESSION MANAGEMENT
# ==============================
def set_current_branch(branch_code):
    """Set current branch in session"""
    st.session_state.current_branch_code = branch_code
    st.session_state.current_branch_name = get_branch_display_name(branch_code)


def get_current_branch():
    """Get current branch code"""
    return st.session_state.get("current_branch_code", None)


def get_current_branch_name():
    """Get current branch name"""
    return st.session_state.get("current_branch_name", "Unknown")


def clear_branch_session():
    """Clear branch session data"""
    if "current_branch_code" in st.session_state:
        del st.session_state.current_branch_code
    if "current_branch_name" in st.session_state:
        del st.session_state.current_branch_name
    if "branch_authenticated" in st.session_state:
        del st.session_state.branch_authenticated


# ==============================
# BRANCH SELECTION UI
# ==============================
def branch_selection_page():
    """Page for selecting and authenticating branch"""
    
    st.title("🏢 Branch Selection")
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Available Branches")
        
        # Display all branches
        for code, info in BRANCHES.items():
            st.markdown(f"""
            <div style='border:1px solid #ddd; border-radius:10px; padding:10px; margin:10px 0;'>
                <strong>{info['name']}</strong><br>
                Code: {code}<br>
                Level: {info['level']}
            </div>
            """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("### Login to Branch")
        
        branch_code = st.text_input("Branch Code", placeholder="Enter branch code (HO, NAT, PRO, DIS, VIL)", key="branch_code_input")
        branch_password = st.text_input("Branch Password", type="password", placeholder="Enter branch password", key="branch_password_input")
        
        if st.button("🔐 Access Branch", type="primary", use_container_width=True):
            if branch_code and branch_password:
                if validate_branch_code(branch_code.upper()):
                    if verify_branch_password(branch_code.upper(), branch_password):
                        set_current_branch(branch_code.upper())
                        st.session_state.branch_authenticated = True
                        st.success(f"✅ Access granted to {get_branch_display_name(branch_code.upper())}")
                        st.rerun()
                    else:
                        st.error("❌ Invalid branch password")
                else:
                    st.error(f"❌ Invalid branch code. Valid codes: {', '.join(BRANCHES.keys())}")
            else:
                st.error("Please enter branch code and password")
        
        st.markdown("---")
        st.caption("Demo Branch Credentials:")
        for code, info in BRANCHES.items():
            st.caption(f"{info['name']} ({code}): {info['password']}")