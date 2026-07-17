# backend/core/theme.py

import streamlit as st
import json
from pathlib import Path
from datetime import datetime

# ==============================
# THEME CONFIGURATION FILE
# ==============================
THEME_FILE = Path("data/user_theme.json")

# ==============================
# AVAILABLE THEMES - FOR REFERENCE ONLY
# ==============================
AVAILABLE_THEMES = {
    "light": {
        "name": "Light Mode",
        "description": "Light background with dark text"
    },
    "dark": {
        "name": "Dark Mode",
        "description": "Dark background with light text"
    },
    "auto": {
        "name": "Auto (System)",
        "description": "Follows your system preference"
    }
}

# ==============================
# THEME PERSISTENCE
# ==============================
def save_theme_preference(theme_name):
    """Save theme preference to file"""
    try:
        THEME_FILE.parent.mkdir(exist_ok=True)
        with open(THEME_FILE, "w") as f:
            json.dump({"theme": theme_name, "updated": datetime.now().isoformat()}, f)
        return True
    except Exception as e:
        print(f"Error saving theme: {e}")
        return False

def load_theme_preference():
    """Load theme preference from file"""
    if THEME_FILE.exists():
        try:
            with open(THEME_FILE, "r") as f:
                data = json.load(f)
                theme = data.get("theme", "auto")
                return theme
        except:
            pass
    return "auto"

def get_current_theme():
    """Get current theme preference"""
    return st.session_state.get("current_theme", load_theme_preference())

def set_theme(theme_name):
    """Set theme preference"""
    if theme_name in AVAILABLE_THEMES:
        st.session_state.current_theme = theme_name
        save_theme_preference(theme_name)
        return True
    return False

# ==============================
# THEME SELECTOR - Uses Streamlit Native Theming
# ==============================
def theme_selector():
    """Theme selector using Streamlit's native theming"""
    st.sidebar.markdown("### Theme Settings")
    st.sidebar.caption("Choose your preferred theme")
    
    current_theme = get_current_theme()
    
    theme_options = list(AVAILABLE_THEMES.keys())
    theme_labels = [AVAILABLE_THEMES[t]['name'] for t in theme_options]
    
    label_to_key = {AVAILABLE_THEMES[t]['name']: t for t in theme_options}
    
    current_label = AVAILABLE_THEMES.get(current_theme, AVAILABLE_THEMES['auto'])['name']
    
    selected_label = st.sidebar.selectbox(
        "Select Theme",
        options=theme_labels,
        index=theme_labels.index(current_label) if current_label in theme_labels else 0,
        help="Choose your preferred theme. This controls how the app looks."
    )
    
    if selected_label:
        selected_key = label_to_key[selected_label]
        if selected_key != current_theme:
            set_theme(selected_key)
            st.sidebar.success(f"Theme set to: {selected_label}")
            st.rerun()
    
    st.sidebar.caption(f"Current: {AVAILABLE_THEMES.get(current_theme, AVAILABLE_THEMES['auto'])['name']}")
    st.sidebar.info("Theme applies using Streamlit's native theming.")
    
# ==============================
# NO THEME APPLICATION - Use Streamlit Defaults
# ==============================
def apply_no_theme():
    """
    Apply NO custom CSS - use Streamlit defaults.
    Streamlit's native theming handles everything.
    """
    pass  # Streamlit handles theming natively

def apply_theme(colors):
    """Apply NO theme - use Streamlit defaults"""
    pass

def apply_page_theme(page_name):
    """Apply NO theme - use Streamlit defaults"""
    pass

def apply_login_theme():
    """Apply NO theme - use Streamlit defaults"""
    pass

def apply_branch_selection_theme():
    """Apply NO theme - use Streamlit defaults"""
    pass

def get_page_theme(page_name):
    """Return default theme colors"""
    return AVAILABLE_THEMES["light"]["colors"] if "colors" in AVAILABLE_THEMES["light"] else {}