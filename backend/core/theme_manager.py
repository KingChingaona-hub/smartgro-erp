import streamlit as st
import json
from pathlib import Path
from datetime import datetime

# ==============================
# THEME CONFIGURATION FILE
# ==============================
THEME_FILE = Path("data/user_theme.json")

# ==============================
# AVAILABLE THEMES - PROPER CONTRAST
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
            "primary_color": "#000000",
            "primary_hover": "#333333",
            "input_bg": "#FFFFFF",
            "input_text": "#000000",
            "success": "#000000",
            "warning": "#000000",
            "error": "#000000",
            "info": "#000000"
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
            "card_bg": "#1A1A1A",
            "sidebar_bg": "#1A1A1A",
            "secondary_bg": "#222222",
            "text_secondary": "#AAAAAA",
            "primary_color": "#FFFFFF",
            "primary_hover": "#CCCCCC",
            "input_bg": "#FFFFFF",
            "input_text": "#000000",
            "success": "#FFFFFF",
            "warning": "#FFFFFF",
            "error": "#FFFFFF",
            "info": "#FFFFFF"
        }
    }
}

# ==============================
# PAGE-SPECIFIC THEMES
# ==============================
PAGE_THEMES = {
    "Stock Dashboard": "light",
    "Inventory": "light",
    "POS": "light",
    "Sales History": "light",
    "Sales Dashboard": "light",
    "Cash Dashboard": "light",
    "Purchases": "light",
    "Purchases Dashboard": "light",
    "Income": "light",
    "Income Dashboard": "light",
    "Expenses": "light",
    "Expenses Dashboard": "light",
    "P&L": "light",
    "Customer Dashboard": "light",
    "Retention Dashboard": "light",
    "Segmentation Dashboard": "light",
    "Lifecycle Dashboard": "light",
    "Business Advisor": "light",
    "Debtors": "light",
    "Debtors Dashboard": "light",
    "Reports Dashboard": "light",
    "Shift Management": "light",
    "Branch Management": "light",
    "Branch Performance": "light",
    "User Management": "light",
    "Settings": "light",
    "Mobile Dashboard": "light",
    "Demand Forecasting": "light",
    "Live Dashboard": "light",
    "Returns & Refunds": "light",
    "Returns Management": "light",
    "Barcode Generator": "light",
    "Customer App": "light",
    "Customer Insights": "light",
    "Customer 360 View": "light",
    "Security Dashboard": "dark",
    "Language Management": "light",
    "Offline Mode": "dark",
    "Financial Closing": "light",
    "Supplier Bidding": "light"
}

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
# THEME APPLICATION - FIXED WITH WHITE INPUTS
# ==============================
def apply_theme(colors):
    
    bg_color = colors.get("background_color", "#FFFFFF")
    text_color = colors.get("text_color", "#000000")
    border_color = colors.get("border_color", "#CCCCCC")
    card_bg = colors.get("card_bg", "#FFFFFF")
    sidebar_bg = colors.get("sidebar_bg", "#F0F0F0")
    secondary_bg = colors.get("secondary_bg", "#F5F5F5")
    text_secondary = colors.get("text_secondary", "#555555")
    
    input_bg = "#FFFFFF"
    input_text = "#000000"
    
    dropdown_bg = "#FFFFFF"
    dropdown_text = "#000000"
    dropdown_border = "#CCCCCC"
    
    # ========================================
    # FIXED BUTTON COLORS - PROPER CONTRAST
    # ========================================
    button_bg = text_color      # Button background = text color (black in light, white in dark)
    button_text = bg_color      # Button text = background color (white in light, black in dark)
    
    css = f"""
    <style>
        .stApp {{
            background-color: {bg_color} !important;
        }}
        
        .main .block-container {{
            background-color: {bg_color} !important;
        }}
        
        h1, h2, h3, h4, h5, h6 {{
            color: {text_color} !important;
        }}
        
        p, li, span, label, div, .stMarkdown, .stMarkdown p {{
            color: {text_color} !important;
        }}
        
        [data-testid="stSidebar"] {{
            background-color: {sidebar_bg} !important;
            border-right: 1px solid {border_color} !important;
        }}
        
        [data-testid="stSidebar"] .stMarkdown,
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] label {{
            color: {text_color} !important;
        }}
        
        [data-testid="stSidebar"] .stSelectbox label {{
            color: {text_color} !important;
        }}
        
        [data-testid="stExpander"],
        [data-testid="stMetric"] {{
            background-color: {card_bg} !important;
            border: 1px solid {border_color} !important;
            border-radius: 8px !important;
        }}
        
        [data-testid="stExpander"] summary p {{
            color: {text_color} !important;
        }}
        
        [data-testid="stMetricValue"] {{
            color: {text_color} !important;
            font-size: 1.8rem !important;
            font-weight: 600 !important;
        }}
        
        [data-testid="stMetricLabel"] {{
            color: {text_secondary} !important;
        }}
        
        /* ==============================
           BUTTONS - FIXED CONTRAST
           ============================== */
        
        .stButton > button {{
            background-color: {button_bg} !important;
            color: {button_text} !important;
            border: 2px solid {button_bg} !important;
            border-radius: 8px !important;
            padding: 10px 24px !important;
            font-weight: 600 !important;
            font-size: 16px !important;
            transition: all 0.3s ease !important;
            cursor: pointer !important;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1) !important;
        }}
        
        .stButton > button:hover {{
            opacity: 0.85 !important;
            transform: translateY(-2px) !important;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2) !important;
        }}
        
        .stButton > button:active {{
            transform: translateY(0px) !important;
        }}
        
        .stButton > button[kind="primary"] {{
            background-color: {button_bg} !important;
            color: {button_text} !important;
            border: 2px solid {button_bg} !important;
        }}
        
        .stButton > button[kind="secondary"] {{
            background-color: transparent !important;
            color: {button_bg} !important;
            border: 2px solid {button_bg} !important;
        }}
        
        .stButton > button[kind="secondary"]:hover {{
            background-color: {button_bg} !important;
            color: {button_text} !important;
        }}
        
        .stForm button[type="submit"] {{
            background-color: {button_bg} !important;
            color: {button_text} !important;
            border: 2px solid {button_bg} !important;
            border-radius: 8px !important;
            padding: 10px 24px !important;
            font-weight: 600 !important;
            font-size: 16px !important;
            transition: all 0.3s ease !important;
            cursor: pointer !important;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1) !important;
            width: 100% !important;
        }}
        
        .stForm button[type="submit"]:hover {{
            opacity: 0.85 !important;
            transform: translateY(-2px) !important;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2) !important;
        }}
        
        .stForm button[type="submit"]:active {{
            transform: translateY(0px) !important;
        }}
        
        .css-1v0mbdj, .css-1v0mbdj button,
        .st-emotion-cache-1v0mbdj, .st-emotion-cache-1v0mbdj button {{
            background-color: {button_bg} !important;
            color: {button_text} !important;
            border: 2px solid {button_bg} !important;
            border-radius: 8px !important;
            padding: 10px 24px !important;
            font-weight: 600 !important;
        }}
        
        /* ==============================
           DROPDOWNS
           ============================== */
        
        .stSelectbox div[data-baseweb="select"] {{
            background-color: {dropdown_bg} !important;
        }}
        
        .stSelectbox div[data-baseweb="select"] > div {{
            background-color: {dropdown_bg} !important;
            color: {dropdown_text} !important;
            border: 1px solid {dropdown_border} !important;
            border-radius: 8px !important;
            min-height: 38px !important;
        }}
        
        .stSelectbox div[data-baseweb="select"] > div > div {{
            background-color: {dropdown_bg} !important;
            color: {dropdown_text} !important;
        }}
        
        .stSelectbox div[data-baseweb="select"] > div > div > div {{
            color: {dropdown_text} !important;
            font-weight: 500 !important;
        }}
        
        .stSelectbox div[data-baseweb="select"] svg {{
            fill: {dropdown_text} !important;
        }}
        
        .stSelectbox div[data-baseweb="select"] ul {{
            background-color: {dropdown_bg} !important;
            border: 1px solid {dropdown_border} !important;
            border-radius: 8px !important;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15) !important;
            max-height: 300px !important;
            overflow-y: auto !important;
            padding: 4px 0 !important;
        }}
        
        .stSelectbox div[data-baseweb="select"] ul li {{
            color: {dropdown_text} !important;
            background-color: {dropdown_bg} !important;
            padding: 10px 14px !important;
            font-size: 14px !important;
            cursor: pointer !important;
            transition: all 0.2s ease !important;
            border-bottom: 1px solid {dropdown_border} !important;
        }}
        
        .stSelectbox div[data-baseweb="select"] ul li:last-child {{
            border-bottom: none !important;
        }}
        
        .stSelectbox div[data-baseweb="select"] ul li:hover {{
            background-color: {text_color} !important;
            color: {dropdown_bg} !important;
        }}
        
        .stSelectbox div[data-baseweb="select"] ul li[aria-selected="true"] {{
            background-color: {text_color} !important;
            color: {dropdown_bg} !important;
            font-weight: 600 !important;
        }}
        
        .stSelectbox div[data-baseweb="select"] ul li:focus {{
            outline: none !important;
            background-color: {text_color} !important;
            color: {dropdown_bg} !important;
        }}
        
        .stSelectbox label {{
            color: {text_color} !important;
            font-weight: 500 !important;
        }}
        
        [data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] > div {{
            background-color: {dropdown_bg} !important;
            color: {dropdown_text} !important;
            border-color: {dropdown_border} !important;
        }}
        
        [data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] ul {{
            background-color: {dropdown_bg} !important;
            border-color: {dropdown_border} !important;
        }}
        
        [data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] ul li {{
            color: {dropdown_text} !important;
            background-color: {dropdown_bg} !important;
            border-bottom: 1px solid {dropdown_border} !important;
        }}
        
        [data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] ul li:hover {{
            background-color: {text_color} !important;
            color: {dropdown_bg} !important;
        }}
        
        [data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] ul li[aria-selected="true"] {{
            background-color: {text_color} !important;
            color: {dropdown_bg} !important;
        }}
        
        .stSelectbox select {{
            background-color: {dropdown_bg} !important;
            color: {dropdown_text} !important;
        }}
        
        .stSelectbox option {{
            background-color: {dropdown_bg} !important;
            color: {dropdown_text} !important;
        }}
        
        .stMultiSelect div[data-baseweb="select"] ul {{
            background-color: {dropdown_bg} !important;
        }}
        
        .stMultiSelect div[data-baseweb="select"] ul li {{
            background-color: {dropdown_bg} !important;
            color: {dropdown_text} !important;
        }}
        
        .stMultiSelect div[data-baseweb="select"] ul li:hover {{
            background-color: {text_color} !important;
            color: {dropdown_bg} !important;
        }}
        
        /* ==============================
           INPUT FIELDS
           ============================== */
        
        .stTextInput > div > div > input,
        .stNumberInput > div > div > input,
        .stTextArea > div > div > textarea,
        .stDateInput > div > div > input,
        .stPasswordInput > div > div > input {{
            background-color: {input_bg} !important;
            color: {input_text} !important;
            border: 1px solid {border_color} !important;
            border-radius: 8px !important;
            padding: 10px 12px !important;
            font-size: 16px !important;
        }}
        
        .stTextInput > div > div > input::placeholder,
        .stNumberInput > div > div > input::placeholder,
        .stTextArea > div > div > textarea::placeholder,
        .stPasswordInput > div > div > input::placeholder {{
            color: #999999 !important;
        }}
        
        .stTextInput > div > div > input:focus,
        .stNumberInput > div > div > input:focus,
        .stTextArea > div > div > textarea:focus,
        .stPasswordInput > div > div > input:focus {{
            border-color: {text_color} !important;
            box-shadow: 0 0 0 3px {text_color}30 !important;
            outline: none !important;
        }}
        
        .stTextInput label,
        .stNumberInput label,
        .stSelectbox label,
        .stTextArea label,
        .stDateInput label,
        .stPasswordInput label {{
            color: {text_color} !important;
            font-weight: 500 !important;
        }}
        
        [data-testid="stSidebar"] .stTextInput > div > div > input,
        [data-testid="stSidebar"] .stNumberInput > div > div > input,
        [data-testid="stSidebar"] .stPasswordInput > div > div > input {{
            background-color: {input_bg} !important;
            color: {input_text} !important;
            border-color: {border_color} !important;
        }}
        
        /* ==============================
           DATA FRAMES
           ============================== */
        
        .stDataFrame {{
            background-color: {input_bg} !important;
        }}
        
        .dataframe {{
            background-color: {input_bg} !important;
            color: {input_text} !important;
            border-radius: 8px !important;
        }}
        
        .dataframe th {{
            background-color: {text_color} !important;
            color: {bg_color} !important;
            padding: 10px !important;
            border: 1px solid {border_color} !important;
        }}
        
        .dataframe td {{
            color: {input_text} !important;
            padding: 8px !important;
            border-bottom: 1px solid {border_color} !important;
            background-color: {input_bg} !important;
        }}
        
        .dataframe tr:nth-child(even) td {{
            background-color: {secondary_bg} !important;
        }}
        
        .dataframe tr:hover td {{
            background-color: {text_color}20 !important;
        }}
        
        /* ==============================
           TABS
           ============================== */
        
        .stTabs [data-baseweb="tab-list"] {{
            gap: 8px;
        }}
        
        .stTabs [data-baseweb="tab"] {{
            background-color: {secondary_bg} !important;
            border-radius: 8px !important;
            padding: 8px 16px !important;
            color: {text_color} !important;
            border: 1px solid {border_color} !important;
        }}
        
        .stTabs [aria-selected="true"] {{
            background-color: {text_color} !important;
            color: {bg_color} !important;
        }}
        
        /* ==============================
           ALERT MESSAGES
           ============================== */
        
        .stSuccess {{
            background-color: {input_bg} !important;
            border: 1px solid {border_color} !important;
            border-radius: 8px !important;
            color: {input_text} !important;
        }}
        
        .stWarning {{
            background-color: {input_bg} !important;
            border: 1px solid {border_color} !important;
            border-radius: 8px !important;
            color: {input_text} !important;
        }}
        
        .stError {{
            background-color: {input_bg} !important;
            border: 1px solid {border_color} !important;
            border-radius: 8px !important;
            color: {input_text} !important;
        }}
        
        .stInfo {{
            background-color: {input_bg} !important;
            border: 1px solid {border_color} !important;
            border-radius: 8px !important;
            color: {input_text} !important;
        }}
        
        .stCheckbox label,
        .stRadio label {{
            color: {text_color} !important;
        }}
        
        code {{
            background-color: {secondary_bg} !important;
            color: {text_color} !important;
            border-radius: 4px !important;
            padding: 2px 6px !important;
        }}
        
        hr {{
            border-color: {border_color} !important;
        }}
        
        a {{
            color: {text_color} !important;
        }}
        
        a:hover {{
            opacity: 0.7 !important;
        }}
        
        .stCaption {{
            color: {text_secondary} !important;
        }}
        
        .stProgress > div > div {{
            background-color: {text_color} !important;
        }}
        
        div[data-baseweb="slider"] {{
            background-color: {text_color} !important;
        }}
        
        div[data-baseweb="calendar"] {{
            background-color: {input_bg} !important;
            border: 1px solid {border_color} !important;
            border-radius: 8px !important;
        }}
        
        div[data-baseweb="calendar"] div {{
            color: {input_text} !important;
        }}
        
        div[data-baseweb="calendar"] button {{
            color: {input_text} !important;
        }}
        
        div[data-baseweb="calendar"] button:hover {{
            background-color: {text_color} !important;
            color: {input_bg} !important;
        }}
        
        .css-1v0mbdj {{
            background-color: {card_bg} !important;
            border-radius: 12px !important;
            padding: 40px !important;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1) !important;
        }}
        
        .stForm {{
            background-color: {card_bg} !important;
        }}
        
        .stPasswordInput button {{
            background: transparent !important;
            border: none !important;
            color: {text_color} !important;
        }}
        
        .stPasswordInput button:hover {{
            background: transparent !important;
            opacity: 0.7 !important;
        }}
    </style>
    """
    
    st.markdown(css, unsafe_allow_html=True)


def get_page_theme(page_name):
    theme_name = PAGE_THEMES.get(page_name, "light")
    theme_config = AVAILABLE_THEMES.get(theme_name, AVAILABLE_THEMES["light"])
    return theme_config["colors"]


def apply_page_theme(page_name):
    colors = get_page_theme(page_name)
    apply_theme(colors)


def apply_login_theme():
    login_colors = {
        "background_color": "#F5F5F5",
        "text_color": "#000000",
        "text_secondary": "#555555",
        "border_color": "#CCCCCC",
        "primary_color": "#000000",
        "primary_hover": "#333333",
        "card_bg": "#FFFFFF",
        "secondary_bg": "#F5F5F5",
        "sidebar_bg": "#F5F5F5",
        "input_bg": "#FFFFFF",
        "input_text": "#000000",
        "success": "#000000",
        "warning": "#000000",
        "error": "#000000",
        "info": "#000000"
    }
    apply_theme(login_colors)


def apply_branch_selection_theme():
    branch_colors = {
        "background_color": "#FFFFFF",
        "text_color": "#000000",
        "text_secondary": "#555555",
        "border_color": "#CCCCCC",
        "primary_color": "#000000",
        "primary_hover": "#333333",
        "card_bg": "#FFFFFF",
        "secondary_bg": "#F5F5F5",
        "sidebar_bg": "#F0F0F0",
        "input_bg": "#FFFFFF",
        "input_text": "#000000",
        "success": "#000000",
        "warning": "#000000",
        "error": "#000000",
        "info": "#000000"
    }
    apply_theme(branch_colors)


def theme_selector():
    st.sidebar.markdown("### 🎨 Theme Settings")
    
    current_theme = st.session_state.get("current_theme", load_theme_preference())
    
    auto_switch = st.sidebar.checkbox(
        "🌓 Auto-switch (Day/Night)",
        value=st.session_state.get("auto_switch_theme", False),
        key="auto_switch_checkbox",
        help="Automatically switches to Dark Mode at night and Light Mode during the day"
    )
    st.session_state.auto_switch_theme = auto_switch
    
    if auto_switch:
        auto_theme = get_auto_theme()
        if auto_theme != current_theme:
            st.session_state.current_theme = auto_theme
            colors = AVAILABLE_THEMES[auto_theme]["colors"]
            apply_theme(colors)
            save_theme_preference(auto_theme)
            st.rerun()
        
        st.sidebar.info(f"🌓 Auto theme active: {AVAILABLE_THEMES[auto_theme]['icon']} {AVAILABLE_THEMES[auto_theme]['name']}")
        
        if st.sidebar.button("🎨 Manual Override", use_container_width=True):
            st.session_state.auto_switch_theme = False
            st.rerun()
    else:
        theme_options = list(AVAILABLE_THEMES.keys())
        theme_labels = [f"{AVAILABLE_THEMES[t]['icon']} {AVAILABLE_THEMES[t]['name']}" for t in theme_options]
        
        current_index = theme_options.index(current_theme) if current_theme in theme_options else 0
        
        selected_label = st.sidebar.selectbox(
            "Select Theme",
            theme_labels,
            index=current_index,
            key="theme_selector"
        )
        
        selected_theme = theme_options[theme_labels.index(selected_label)]
        
        if selected_theme != current_theme:
            st.session_state.current_theme = selected_theme
            colors = AVAILABLE_THEMES[selected_theme]["colors"]
            apply_theme(colors)
            save_theme_preference(selected_theme)
            st.rerun()
    
    with st.sidebar.expander("🎨 Theme Preview"):
        theme = AVAILABLE_THEMES.get(current_theme, AVAILABLE_THEMES["light"])
        colors = theme["colors"]
        bg = colors.get("background_color", "#FFFFFF")
        text = colors.get("text_color", "#000000")
        border = colors.get("border_color", "#CCCCCC")
        
        st.markdown(f"""
        <div style="background: {bg}; padding: 12px; border-radius: 10px; border: 1px solid {border};">
            <p style="color: {text};"><strong>■ Text Color</strong></p>
            <p style="color: {text}; background: {bg}; padding: 4px; border: 1px solid {text};">
                <strong>■ Border Color</strong>
            </p>
            <div style="background: {text}; color: {bg}; padding: 4px; border-radius: 4px;">
                <strong>■ Background Color</strong>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    st.sidebar.markdown("---")


def get_current_theme():
    return st.session_state.get("current_theme", load_theme_preference())


def set_theme(theme_name):
    if theme_name in AVAILABLE_THEMES:
        st.session_state.current_theme = theme_name
        colors = AVAILABLE_THEMES[theme_name]["colors"]
        apply_theme(colors)
        save_theme_preference(theme_name)
        return True
    return False