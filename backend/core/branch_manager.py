import pandas as pd
import streamlit as st
from pathlib import Path
from datetime import datetime

# ==============================
# FILE SETUP
# ==============================
DATA_DIR = Path("data")
BRANCH_DATA_DIR = Path("branch_data")
MASTER_BRANCHES_FILE = DATA_DIR / "master_branches.csv"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
BRANCH_DATA_DIR.mkdir(exist_ok=True)


# ==============================
# MASTER BRANCHES (System-wide)
# ==============================
MASTER_BRANCHES = [
    {"branch_id": "HO", "branch_name": "Head Office", "location": "Harare", "level": 1, "active": True},
    {"branch_id": "NAT", "branch_name": "National Branch", "location": "Harare", "level": 2, "active": True},
    {"branch_id": "PRO", "branch_name": "Provincial Branch", "location": "Bulawayo", "level": 3, "active": True},
    {"branch_id": "DIS", "branch_name": "District Branch", "location": "Mutare", "level": 4, "active": True},
    {"branch_id": "VIL", "branch_name": "Village Branch", "location": "Gweru", "level": 5, "active": True},
]


def init_master_branches():
    """Initialize master branches file if not exists"""
    if not MASTER_BRANCHES_FILE.exists():
        df = pd.DataFrame(MASTER_BRANCHES)
        df.to_csv(MASTER_BRANCHES_FILE, index=False)
        return df
    return pd.read_csv(MASTER_BRANCHES_FILE)


def load_branches():
    """Load all branches from master file - MAIN FUNCTION"""
    init_master_branches()
    return pd.read_csv(MASTER_BRANCHES_FILE)


def load_all_branches():
    """Load all branches from master file (alias for load_branches)"""
    return load_branches()


def get_branch_info(branch_id):
    """Get information for a specific branch"""
    df = load_branches()
    branch = df[df["branch_id"] == branch_id]
    if not branch.empty:
        return branch.iloc[0].to_dict()
    return None


def get_user_branch():
    """Get current user's branch from session"""
    return st.session_state.get("user_branch", None)


def set_user_branch(branch_id):
    """Set current user's branch in session"""
    st.session_state.user_branch = branch_id
    # Also update the current branch
    st.session_state.current_branch = branch_id


def get_current_branch():
    """Get current branch from session"""
    return st.session_state.get("current_branch", "HO")


def set_current_branch(branch_id):
    """Set current branch in session"""
    st.session_state.current_branch = branch_id
    # Also update user branch if not set
    if "user_branch" not in st.session_state:
        st.session_state.user_branch = branch_id


def branch_selector():
    """Display branch selector in sidebar"""
    branches = load_branches()
    current_branch = get_current_branch()
    
    branch_names = branches["branch_name"].tolist()
    branch_ids = branches["branch_id"].tolist()
    
    selected_idx = branch_ids.index(current_branch) if current_branch in branch_ids else 0
    selected_name = st.sidebar.selectbox(
        "🏢 Select Branch",
        branch_names,
        index=selected_idx,
        key="branch_selector"
    )
    
    selected_id = branches[branches["branch_name"] == selected_name]["branch_id"].iloc[0]
    if selected_id != current_branch:
        set_current_branch(selected_id)
        st.rerun()
    
    return selected_id, selected_name


def get_branch_display_name():
    """Get display name for current branch"""
    branch_id = get_current_branch()
    branch_info = get_branch_info(branch_id)
    if branch_info:
        return branch_info["branch_name"]
    return branch_id


def get_branch_level():
    """Get level of current branch"""
    branch_id = get_current_branch()
    branch_info = get_branch_info(branch_id)
    if branch_info:
        return branch_info["level"]
    return 0


def is_head_office():
    """Check if current branch is Head Office"""
    return get_current_branch() == "HO"


def add_branch(branch_name, location):
    """Add a new branch"""
    df = load_branches()
    new_id = f"BR{len(df)+1:03d}"
    new_branch = pd.DataFrame([{
        "branch_id": new_id,
        "branch_name": branch_name,
        "location": location,
        "level": len(df) + 1,
        "active": True
    }])
    df = pd.concat([df, new_branch], ignore_index=True)
    df.to_csv(MASTER_BRANCHES_FILE, index=False)
    return new_id


def update_branch(branch_id, **kwargs):
    """Update branch information"""
    df = load_branches()
    idx = df[df["branch_id"] == branch_id].index
    if len(idx) > 0:
        for key, value in kwargs.items():
            if key in df.columns:
                df.loc[idx[0], key] = value
        df.to_csv(MASTER_BRANCHES_FILE, index=False)
        return True
    return False


def delete_branch(branch_id):
    """Delete a branch"""
    if branch_id == "HO":
        return False, "Cannot delete Head Office branch"
    
    df = load_branches()
    df = df[df["branch_id"] != branch_id]
    df.to_csv(MASTER_BRANCHES_FILE, index=False)
    return True, "Branch deleted"


def get_active_branches():
    """Get only active branches"""
    df = load_branches()
    return df[df["active"] == True]


def get_branch_summary():
    """Get summary of all branches"""
    df = load_branches()
    if df.empty:
        return {
            "total_branches": 0,
            "active_branches": 0,
            "branch_list": []
        }
    
    return {
        "total_branches": len(df),
        "active_branches": len(df[df["active"] == True]),
        "branch_list": df.to_dict('records')
    }