import streamlit as st
import json
from pathlib import Path
from datetime import datetime

# ==============================
# THEME CONFIGURATION FILE
# ==============================
THEME_FILE = Path("data/user_theme.json")

# ==============================
# AVAILABLE THEMES - KEPT FOR REFERENCE ONLY
# ==============================
AVAILABLE_THEMES = {
    "light": {
        "name": "Light Mode",
        "icon": "☀️",
        "description": "Light background with dark text",
        "colors": {
            "background_color": "#FFFFFF",
            "text_color": "#000000",
            "border_color": "#CCCCCC",
            "card_bg": "#FFFFFF",
            "sidebar_bg": "#F0F0F0",
            "secondary_bg": "#F5F5F5",
            "text_secondary": "#555555",
            "primary_color": "#F2E1E1",
            "primary_hover": "#F12AE4",
            "input_bg": "#FFFFFF",
            "input_text": "#000000",
            "success": "#14EA8A",
            "warning": "#B5E312",
            "error": "#F71111",
            "info": "#1888EB"
        }
    },
    "dark": {
        "name": "Dark Mode",
        "icon": "🌙",
        "description": "Dark background with light text",
        "colors": {
            "background_color": "#0D0D0D",
            "text_color": "#FFFFFF",
            "border_color": "#444444",
            "card_bg": "#7222D4",
            "sidebar_bg": "#1A1A1A",
            "secondary_bg": "#C7AEAE",
            "text_secondary": "#AAAAAA",
            "primary_color": "#FFFFFF",
            "primary_hover": "#CCCCCC",
            "input_bg": "#FFFFFF",
            "input_text": "#BAB1B1",
            "success": "#FFFFFF",
            "warning": "#FFFFFF",
            "error": "#FFFFFF",
            "info": "#FFFFFF"
        }
    }
}

# ==============================
# PAGE-SPECIFIC THEMES - DISABLED
# ==============================
PAGE_THEMES = {}

# ==============================
# THEME PERSISTENCE
# ==============================
def save_theme_preference(theme_name):
    try:
        THEME_FILE.parent.mkdir(exist_ok=True)
        with open(THEME_FILE, "w") as f:
            json.dump({"theme": theme_name, "updated": datetime.now().isoformat()}, f)
        return True
    except Exception as e:
        print(f"Error saving theme: {e}")
        return False


def load_theme_preference():
    if THEME_FILE.exists():
        try:
            with open(THEME_FILE, "r") as f:
                data = json.load(f)
                theme = data.get("theme", "light")
                if theme in AVAILABLE_THEMES:
                    return theme
        except:
            pass
    return "light"


def get_auto_theme():
    current_hour = datetime.now().hour
    if current_hour >= 18 or current_hour < 6:
        return "dark"
    else:
        return "light"

# ==============================
# THEME APPLICATION - DISABLED, USE STREAMLIT DEFAULTS
# ==============================
def apply_theme(colors):
    """Apply NO theme - use Streamlit defaults"""
    pass  # Do nothing, use Streamlit defaults


def apply_no_theme():
    """Apply NO theme - use Streamlit defaults"""
    css = """
    <style>
        /* Reset all custom styling - use Streamlit defaults */
        .stApp {
            background-color: transparent !important;
        }
        .main .block-container {
            background-color: transparent !important;
        }
        /* Remove all custom overrides */
        .stSelectbox div[data-baseweb="select"] > div {
            background-color: transparent !important;
            color: inherit !important;
        }
        .stSelectbox div[data-baseweb="select"] ul {
            background-color: transparent !important;
        }
        .stSelectbox div[data-baseweb="select"] ul li {
            background-color: transparent !important;
            color: inherit !important;
        }
        .stTabs [data-baseweb="tab"] {
            background-color: transparent !important;
            color: inherit !important;
        }
        .stTabs [aria-selected="true"] {
            background-color: transparent !important;
            color: inherit !important;
        }
        .stButton > button {
            background-color: transparent !important;
            color: inherit !important;
            border: 1px solid #ddd !important;
        }
        .stForm button[type="submit"] {
            background-color: transparent !important;
            color: inherit !important;
            border: 1px solid #ddd !important;
        }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def get_page_theme(page_name):
    """Return default theme - DISABLED"""
    return AVAILABLE_THEMES["light"]["colors"]


def apply_page_theme(page_name):
    """Apply NO theme - use Streamlit defaults"""
    apply_no_theme()


def apply_login_theme():
    """Apply NO theme to login page - use Streamlit defaults"""
    apply_no_theme()


def apply_branch_selection_theme():
    """Apply NO theme to branch selection page - use Streamlit defaults"""
    apply_no_theme()


def theme_selector():
    """Theme selector - DISABLED, show message only"""
    st.sidebar.markdown("### Theme Settings")
    st.sidebar.info("Themes are temporarily disabled. Using default Streamlit styling.")
    
    # Still keep the theme preference for future use
    current_theme = st.session_state.get("current_theme", load_theme_preference())
    
    # Show current theme but don't allow changes
    st.sidebar.markdown(f"Current preference: **{AVAILABLE_THEMES.get(current_theme, AVAILABLE_THEMES['light'])['name']}**")
    st.sidebar.caption("Theme system will be re-enabled with fixed styling soon.")


def get_current_theme():
    return st.session_state.get("current_theme", load_theme_preference())


def set_theme(theme_name):
    """Set theme - DISABLED"""
    if theme_name in AVAILABLE_THEMES:
        st.session_state.current_theme = theme_name
        save_theme_preference(theme_name)
        return True
    return False