"""
Theme Manager for SmartGro ERP
Uses Streamlit's native theming system - no custom CSS
"""

import streamlit as st
import json
from pathlib import Path
from datetime import datetime

# ==============================
# THEME CONFIGURATION FILE
# ==============================
THEME_FILE = Path("data/user_theme.json")

# ==============================
# AVAILABLE THEMES
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

def get_auto_theme():
    """Get theme based on time of day"""
    current_hour = datetime.now().hour
    if current_hour >= 18 or current_hour < 6:
        return "dark"
    else:
        return "light"

# ==============================
# THEME APPLICATION - Uses Streamlit Native Theming
# ==============================
def apply_theme(colors=None):
    """
    Apply NO custom CSS - use Streamlit defaults.
    Streamlit's native theming handles everything.
    """
    pass  # Streamlit handles theming natively

def apply_no_theme():
    """Apply NO theme - use Streamlit defaults"""
    pass  # Streamlit handles theming natively

def apply_page_theme(page_name):
    """Apply NO theme - use Streamlit defaults"""
    pass

def apply_login_theme():
    """Apply NO theme to login page - use Streamlit defaults"""
    pass

def apply_branch_selection_theme():
    """Apply NO theme to branch selection page - use Streamlit defaults"""
    pass

def get_page_theme(page_name):
    """Return default theme - use Streamlit defaults"""
    return {}  # Return empty dict, use Streamlit defaults

# ==============================
# THEME SELECTOR
# ==============================
def theme_selector():
    """
    Theme selector using Streamlit's native theming.
    This allows users to choose their theme preference.
    """
    st.sidebar.markdown("### Theme Settings")
    st.sidebar.caption("Choose your preferred theme")
    
    current_theme = get_current_theme()
    
    # Get theme options
    theme_options = list(AVAILABLE_THEMES.keys())
    theme_labels = [AVAILABLE_THEMES[t]['name'] for t in theme_options]
    
    # Create a mapping from label to key
    label_to_key = {AVAILABLE_THEMES[t]['name']: t for t in theme_options}
    
    # Get current theme label
    current_label = AVAILABLE_THEMES.get(current_theme, AVAILABLE_THEMES['auto'])['name']
    
    # Theme selector
    selected_label = st.sidebar.selectbox(
        "Select Theme",
        options=theme_labels,
        index=theme_labels.index(current_label) if current_label in theme_labels else 0,
        help="Choose your preferred theme. This controls how the app looks."
    )
    
    # If theme changed, update it
    if selected_label:
        selected_key = label_to_key[selected_label]
        if selected_key != current_theme:
            set_theme(selected_key)
            st.sidebar.success(f"Theme set to: {selected_label}")
            st.rerun()
    
    # Show current theme info
    st.sidebar.caption(f"Current: {AVAILABLE_THEMES.get(current_theme, AVAILABLE_THEMES['auto'])['name']}")
    st.sidebar.info("Theme applies using Streamlit's native theming.")