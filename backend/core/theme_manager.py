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
        "icon": "☀️",
        "description": "Clean and bright - perfect for daytime",
        "colors": {
            "primary_color": "#6366F1",
            "primary_hover": "#4F46E5",
            "background_color": "#FFFFFF",
            "secondary_bg": "#F8F9FA",
            "text_color": "#1F2937",
            "text_secondary": "#6B7280",
            "border_color": "#E5E7EB",
            "card_bg": "#FFFFFF",
            "sidebar_bg": "#F3F4F6",
            "success": "#10B981",
            "warning": "#F59E0B",
            "error": "#EF4444",
            "info": "#3B82F6"
        }
    },
    "dark": {
        "name": "Dark Mode",
        "icon": "🌙",
        "description": "Easy on the eyes - great for nighttime",
        "colors": {
            "primary_color": "#8B5CF6",
            "primary_hover": "#7C3AED",
            "background_color": "#0F172A",
            "secondary_bg": "#1E293B",
            "text_color": "#F1F5F9",
            "text_secondary": "#94A3B8",
            "border_color": "#334155",
            "card_bg": "#1E293B",
            "sidebar_bg": "#1E293B",
            "success": "#10B981",
            "warning": "#F59E0B",
            "error": "#EF4444",
            "info": "#3B82F6"
        }
    },
    "high_contrast": {
        "name": "High Contrast",
        "icon": "♿",
        "description": "Maximum readability - accessibility focused",
        "colors": {
            "primary_color": "#FFD700",
            "primary_hover": "#FFC107",
            "background_color": "#000000",
            "secondary_bg": "#1A1A1A",
            "text_color": "#FFFFFF",
            "text_secondary": "#CCCCCC",
            "border_color": "#FFFFFF",
            "card_bg": "#1A1A1A",
            "sidebar_bg": "#000000",
            "success": "#00FF00",
            "warning": "#FFA500",
            "error": "#FF0000",
            "info": "#00BFFF"
        }
    },
    "ocean": {
        "name": "Ocean Blue",
        "icon": "🌊",
        "description": "Calming blue tones",
        "colors": {
            "primary_color": "#0077B6",
            "primary_hover": "#023E8A",
            "background_color": "#CAF0F8",
            "secondary_bg": "#ADE8F4",
            "text_color": "#03045E",
            "text_secondary": "#0077B6",
            "border_color": "#48CAE4",
            "card_bg": "#FFFFFF",
            "sidebar_bg": "#90E0EF",
            "success": "#00B4D8",
            "warning": "#FFB703",
            "error": "#FB8500",
            "info": "#0096C7"
        }
    },
    "forest": {
        "name": "Forest Green",
        "icon": "🌿",
        "description": "Natural and refreshing",
        "colors": {
            "primary_color": "#2E8B57",
            "primary_hover": "#1B5E20",
            "background_color": "#F1F8E9",
            "secondary_bg": "#DCEDC8",
            "text_color": "#1B5E20",
            "text_secondary": "#388E3C",
            "border_color": "#81C784",
            "card_bg": "#FFFFFF",
            "sidebar_bg": "#C8E6C9",
            "success": "#4CAF50",
            "warning": "#FFC107",
            "error": "#F44336",
            "info": "#2196F3"
        }
    },
    "sunset": {
        "name": "Sunset",
        "icon": "🌅",
        "description": "Warm and energetic",
        "colors": {
            "primary_color": "#FF6B35",
            "primary_hover": "#E85D04",
            "background_color": "#FFF3E0",
            "secondary_bg": "#FFE0B2",
            "text_color": "#4A2B0A",
            "text_secondary": "#E65100",
            "border_color": "#FFB74D",
            "card_bg": "#FFFFFF",
            "sidebar_bg": "#FFCC80",
            "success": "#66BB6A",
            "warning": "#FFA726",
            "error": "#EF5350",
            "info": "#42A5F5"
        }
    },
    "midnight": {
        "name": "Midnight",
        "icon": "🌃",
        "description": "Deep blue night theme",
        "colors": {
            "primary_color": "#00B4D8",
            "primary_hover": "#0077B6",
            "background_color": "#001F3F",
            "secondary_bg": "#003366",
            "text_color": "#E0E0E0",
            "text_secondary": "#A0A0A0",
            "border_color": "#007BFF",
            "card_bg": "#003366",
            "sidebar_bg": "#001F3F",
            "success": "#00FF88",
            "warning": "#FFB347",
            "error": "#FF4444",
            "info": "#00BFFF"
        }
    },
    "royal": {
        "name": "Royal Purple",
        "icon": "👑",
        "description": "Elegant and sophisticated",
        "colors": {
            "primary_color": "#9B59B6",
            "primary_hover": "#8E44AD",
            "background_color": "#F5F0FF",
            "secondary_bg": "#E8DAEF",
            "text_color": "#4A235A",
            "text_secondary": "#6C3483",
            "border_color": "#D2B4DE",
            "card_bg": "#FFFFFF",
            "sidebar_bg": "#E8DAEF",
            "success": "#2ECC71",
            "warning": "#F39C12",
            "error": "#E74C3C",
            "info": "#3498DB"
        }
    }
}

# ==============================
# PAGE-SPECIFIC THEMES
# ==============================
PAGE_THEMES = {
    "Stock Dashboard": "forest",
    "Inventory": "forest",
    "POS": "sunset",
    "Sales History": "ocean",
    "Sales Dashboard": "ocean",
    "Cash Dashboard": "sunset",
    "Purchases": "forest",
    "Purchases Dashboard": "forest",
    "Income": "ocean",
    "Income Dashboard": "ocean",
    "Expenses": "sunset",
    "Expenses Dashboard": "sunset",
    "P&L": "royal",
    "Customer Dashboard": "royal",
    "Retention Dashboard": "royal",
    "Segmentation Dashboard": "royal",
    "Lifecycle Dashboard": "royal",
    "Business Advisor": "royal",
    "Debtors": "sunset",
    "Debtors Dashboard": "sunset",
    "Reports Dashboard": "ocean",
    "Shift Management": "forest",
    "Branch Management": "forest",
    "Branch Performance": "ocean",
    "User Management": "royal",
    "Settings": "light",
    "Mobile Dashboard": "ocean",
    "Demand Forecasting": "royal",
    "Live Dashboard": "sunset",
    "Returns & Refunds": "sunset",
    "Returns Management": "sunset",
    "Barcode Generator": "forest",
    "Customer App": "royal",
    "Customer Insights": "royal",
    "Customer 360 View": "royal",
    "Security Dashboard": "dark",
    "Language Management": "ocean",
    "Offline Mode": "dark",
    "Financial Closing": "sunset",
    "Supplier Bidding": "forest"
}

# ==============================
# THEME PERSISTENCE
# ==============================
def save_theme_preference(theme_name):
    """Save user's theme preference"""
    try:
        THEME_FILE.parent.mkdir(exist_ok=True)
        with open(THEME_FILE, "w") as f:
            json.dump({"theme": theme_name, "updated": datetime.now().isoformat()}, f)
        return True
    except Exception as e:
        print(f"Error saving theme: {e}")
        return False


def load_theme_preference():
    """Load user's saved theme preference"""
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
    """Automatically select theme based on time of day"""
    current_hour = datetime.now().hour
    # 6 PM to 6 AM = dark mode
    if current_hour >= 18 or current_hour < 6:
        return "dark"
    else:
        return "light"

# ==============================
# THEME APPLICATION
# ==============================
def apply_theme(colors):
    """Apply theme CSS to the Streamlit app"""
    
    css = f"""
    <style>
        /* Global Styles */
        .stApp {{
            background-color: {colors.get("background_color", "#FFFFFF")};
        }}
        
        .main .block-container {{
            background-color: {colors.get("background_color", "#FFFFFF")};
        }}
        
        /* Headers */
        h1, h2, h3, h4, h5, h6 {{
            color: {colors.get("text_color", "#1F2937")} !important;
        }}
        
        /* Text */
        p, li, span, label, div {{
            color: {colors.get("text_color", "#1F2937")};
        }}
        
        .stMarkdown p, .stMarkdown li {{
            color: {colors.get("text_color", "#1F2937")};
        }}
        
        /* Sidebar */
        [data-testid="stSidebar"] {{
            background-color: {colors.get("sidebar_bg", "#F3F4F6")};
            border-right: 1px solid {colors.get("border_color", "#E5E7EB")};
        }}
        
        [data-testid="stSidebar"] .stMarkdown,
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] label {{
            color: {colors.get("text_color", "#1F2937")} !important;
        }}
        
        /* Cards / Expanders / Metrics */
        [data-testid="stExpander"],
        [data-testid="stMetric"] {{
            background-color: {colors.get("card_bg", "#FFFFFF")};
            border: 1px solid {colors.get("border_color", "#E5E7EB")};
            border-radius: 12px;
        }}
        
        [data-testid="stExpander"] summary p {{
            color: {colors.get("text_color", "#1F2937")} !important;
        }}
        
        [data-testid="stMetricValue"] {{
            color: {colors.get("primary_color", "#6366F1")} !important;
            font-size: 1.8rem !important;
            font-weight: 600 !important;
        }}
        
        [data-testid="stMetricLabel"] {{
            color: {colors.get("text_secondary", "#6B7280")} !important;
        }}
        
        /* Buttons */
        .stButton > button {{
            background: linear-gradient(135deg, {colors.get("primary_color", "#6366F1")} 0%, {colors.get("primary_hover", "#4F46E5")} 100%);
            color: white !important;
            border: none;
            border-radius: 8px;
            padding: 8px 16px;
            font-weight: 500;
            transition: all 0.3s ease;
        }}
        
        .stButton > button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            opacity: 0.9;
        }}
        
        /* Input Fields */
        .stTextInput > div > div > input,
        .stNumberInput > div > div > input,
        .stSelectbox > div > div,
        .stTextArea > div > div > textarea,
        .stDateInput > div > div > input {{
            background-color: {colors.get("card_bg", "#FFFFFF")};
            color: {colors.get("text_color", "#1F2937")};
            border: 1px solid {colors.get("border_color", "#E5E7EB")};
            border-radius: 8px;
        }}
        
        .stTextInput > div > div > input:focus,
        .stNumberInput > div > div > input:focus,
        .stTextArea > div > div > textarea:focus {{
            border-color: {colors.get("primary_color", "#6366F1")};
            box-shadow: 0 0 0 2px {colors.get("primary_color", "#6366F1")}20;
        }}
        
        .stTextInput label,
        .stNumberInput label,
        .stSelectbox label,
        .stTextArea label,
        .stDateInput label {{
            color: {colors.get("text_color", "#1F2937")} !important;
            font-weight: 500;
        }}
        
        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {{
            gap: 8px;
        }}
        
        .stTabs [data-baseweb="tab"] {{
            background-color: {colors.get("secondary_bg", "#F8F9FA")};
            border-radius: 8px;
            padding: 8px 16px;
            color: {colors.get("text_color", "#1F2937")};
            border: 1px solid {colors.get("border_color", "#E5E7EB")};
        }}
        
        .stTabs [aria-selected="true"] {{
            background-color: {colors.get("primary_color", "#6366F1")};
            color: white !important;
        }}
        
        /* DataFrames */
        .stDataFrame {{
            background-color: {colors.get("card_bg", "#FFFFFF")};
        }}
        
        .dataframe {{
            background-color: {colors.get("card_bg", "#FFFFFF")};
            color: {colors.get("text_color", "#1F2937")};
            border-radius: 10px;
        }}
        
        .dataframe th {{
            background-color: {colors.get("primary_color", "#6366F1")} !important;
            color: white !important;
            padding: 10px !important;
        }}
        
        .dataframe td {{
            color: {colors.get("text_color", "#1F2937")} !important;
            padding: 8px !important;
        }}
        
        /* Alert Messages */
        .stSuccess {{
            background-color: {colors.get("success", "#10B981")}20;
            border-left: 4px solid {colors.get("success", "#10B981")};
            border-radius: 8px;
        }}
        
        .stWarning {{
            background-color: {colors.get("warning", "#F59E0B")}20;
            border-left: 4px solid {colors.get("warning", "#F59E0B")};
            border-radius: 8px;
        }}
        
        .stError {{
            background-color: {colors.get("error", "#EF4444")}20;
            border-left: 4px solid {colors.get("error", "#EF4444")};
            border-radius: 8px;
        }}
        
        .stInfo {{
            background-color: {colors.get("info", "#3B82F6")}20;
            border-left: 4px solid {colors.get("info", "#3B82F6")};
            border-radius: 8px;
        }}
        
        /* Progress Bar */
        .stProgress > div > div {{
            background-color: {colors.get("primary_color", "#6366F1")};
        }}
        
        /* Checkbox & Radio */
        .stCheckbox label,
        .stRadio label {{
            color: {colors.get("text_color", "#1F2937")} !important;
        }}
        
        /* Select Dropdown */
        div[data-baseweb="select"] > div {{
            background-color: {colors.get("card_bg", "#FFFFFF")};
            border-color: {colors.get("border_color", "#E5E7EB")};
        }}
        
        /* Code Blocks */
        code {{
            background-color: {colors.get("secondary_bg", "#F8F9FA")};
            color: {colors.get("primary_color", "#6366F1")};
            border-radius: 4px;
            padding: 2px 6px;
        }}
        
        /* Horizontal Rule */
        hr {{
            border-color: {colors.get("border_color", "#E5E7EB")};
        }}
        
        /* Links */
        a {{
            color: {colors.get("primary_color", "#6366F1")};
        }}
        
        a:hover {{
            color: {colors.get("primary_hover", "#4F46E5")};
        }}
        
        /* Caption */
        .stCaption {{
            color: {colors.get("text_secondary", "#6B7280")} !important;
        }}
    </style>
    """
    
    st.markdown(css, unsafe_allow_html=True)


def get_page_theme(page_name):
    """Get theme colors for specific page"""
    theme_name = PAGE_THEMES.get(page_name, "light")
    theme_config = AVAILABLE_THEMES.get(theme_name, AVAILABLE_THEMES["light"])
    return theme_config["colors"]


def apply_page_theme(page_name):
    """Apply theme based on current page"""
    colors = get_page_theme(page_name)
    apply_theme(colors)


def apply_login_theme():
    """Apply professional login page theme"""
    login_colors = {
        "background_color": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
        "text_color": "#FFFFFF",
        "text_secondary": "rgba(255,255,255,0.8)",
        "border_color": "rgba(255,255,255,0.2)",
        "primary_color": "#FF6584",
        "primary_hover": "#FF85A4",
        "card_bg": "rgba(255,255,255,0.1)",
        "secondary_bg": "rgba(255,255,255,0.05)",
        "sidebar_bg": "#1E1E2E",
        "success": "#10B981",
        "warning": "#F59E0B",
        "error": "#EF4444",
        "info": "#3B82F6"
    }
    
    css = f"""
    <style>
        .stApp {{
            background: {login_colors["background_color"]};
        }}
        h1, h2, h3, h4, h5, h6, p, label, span {{
            color: {login_colors["text_color"]} !important;
        }}
        .stForm {{
            background: {login_colors["card_bg"]};
            border-radius: 20px;
            padding: 35px;
            backdrop-filter: blur(10px);
            border: 1px solid {login_colors["border_color"]};
        }}
        .stTextInput > div > div > input {{
            background: white !important;
            color: #1f2937 !important;
            border-radius: 30px !important;
            padding: 12px 20px !important;
            border: none !important;
        }}
        .stButton > button {{
            background: linear-gradient(135deg, {login_colors["primary_color"]} 0%, {login_colors["primary_hover"]} 100%) !important;
            color: white !important;
            border-radius: 30px !important;
            padding: 12px 30px !important;
            font-weight: bold !important;
            width: 100% !important;
        }}
        .stButton > button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(255,101,132,0.4);
        }}
        .stCaption {{
            color: {login_colors["text_secondary"]} !important;
        }}
        hr {{
            border-color: {login_colors["border_color"]};
        }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def apply_branch_selection_theme():
    """Apply pure white theme for branch selection"""
    branch_colors = {
        "background_color": "#FFFFFF",
        "text_color": "#1a1a2e",
        "text_secondary": "#666666",
        "border_color": "#e0e0e0",
        "primary_color": "#6366F1",
        "primary_hover": "#4F46E5",
        "card_bg": "#FFFFFF",
        "secondary_bg": "#F8F9FA",
        "sidebar_bg": "#F3F4F6",
        "success": "#10B981",
        "warning": "#F59E0B",
        "error": "#EF4444",
        "info": "#3B82F6"
    }
    apply_theme(branch_colors)


# ==============================
# THEME SELECTOR WIDGET
# ==============================
def theme_selector():
    """Display theme selector in sidebar"""
    st.sidebar.markdown("### 🎨 Theme Settings")
    
    # Get current theme
    current_theme = st.session_state.get("current_theme", load_theme_preference())
    
    # Auto-switch option
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
        # Theme selection dropdown
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
    
    # Theme preview
    with st.sidebar.expander("🎨 Theme Preview"):
        theme = AVAILABLE_THEMES.get(current_theme, AVAILABLE_THEMES["light"])
        colors = theme["colors"]
        st.markdown(f"""
        <div style="background: {colors['card_bg']}; padding: 12px; border-radius: 10px; border: 1px solid {colors['border_color']};">
            <p style="color: {colors['primary_color']};"><strong>■ Primary Color</strong></p>
            <p style="color: {colors['success']};"><strong>■ Success Color</strong></p>
            <p style="color: {colors['warning']};"><strong>■ Warning Color</strong></p>
            <p style="color: {colors['error']};"><strong>■ Error Color</strong></p>
        </div>
        """, unsafe_allow_html=True)
    
    st.sidebar.markdown("---")


def get_current_theme():
    """Get current theme name"""
    return st.session_state.get("current_theme", load_theme_preference())


def set_theme(theme_name):
    """Set and apply a theme programmatically"""
    if theme_name in AVAILABLE_THEMES:
        st.session_state.current_theme = theme_name
        colors = AVAILABLE_THEMES[theme_name]["colors"]
        apply_theme(colors)
        save_theme_preference(theme_name)
        return True
    return False