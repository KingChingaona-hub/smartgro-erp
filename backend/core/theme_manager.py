
"""
AZIEL INVESTMENTS ERP
Theme Manager
Professional themes with accessible colour contrast.

Includes visible and accessible Streamlit form buttons,
especially Login and other authentication buttons.
"""

import streamlit as st
import json
from pathlib import Path
from datetime import datetime


# ============================================================
# THEME CONFIGURATION
# ============================================================

THEME_FILE = Path("data/user_theme.json")


# ============================================================
# COLOUR PALETTES
# ============================================================

THEME_PALETTES = {

    "aziel_gold": {
        "name": "Aziel Gold",
        "description": "Signature corporate gold, white and navy.",
        "mode": "light",
        "primary": "#C69214",
        "secondary": "#F3C969",
        "background": "#FFFFFF",
        "surface": "#F7F8FA",
        "sidebar": "#F1F3F6",
        "text": "#202938",
        "muted": "#657184",
        "border": "#DCE1E8",
        "input": "#FFFFFF",
        "input_text": "#202938",
        "button_text": "#FFFFFF",
        "success": "#16834A",
        "warning": "#A96500",
        "danger": "#C0392B",
    },

    "ocean_blue": {
        "name": "Ocean Blue",
        "description": "Professional blue with clean white surfaces.",
        "mode": "light",
        "primary": "#1677C8",
        "secondary": "#55A9E8",
        "background": "#F8FBFF",
        "surface": "#FFFFFF",
        "sidebar": "#EAF3FC",
        "text": "#172B43",
        "muted": "#5F7187",
        "border": "#D5E2EF",
        "input": "#FFFFFF",
        "input_text": "#172B43",
        "button_text": "#FFFFFF",
        "success": "#16834A",
        "warning": "#A96500",
        "danger": "#C0392B",
    },

    "royal_purple": {
        "name": "Royal Purple",
        "description": "Elegant purple with soft backgrounds.",
        "mode": "light",
        "primary": "#7550A8",
        "secondary": "#A98BD1",
        "background": "#FBF9FE",
        "surface": "#FFFFFF",
        "sidebar": "#F1EBF8",
        "text": "#29213A",
        "muted": "#6F657F",
        "border": "#E2D9ED",
        "input": "#FFFFFF",
        "input_text": "#29213A",
        "button_text": "#FFFFFF",
        "success": "#16834A",
        "warning": "#A96500",
        "danger": "#C0392B",
    },

    "sunrise_orange": {
        "name": "Sunrise Orange",
        "description": "Warm orange, yellow and white.",
        "mode": "light",
        "primary": "#D96820",
        "secondary": "#F3B84B",
        "background": "#FFFCF8",
        "surface": "#FFFFFF",
        "sidebar": "#FFF1E5",
        "text": "#35251D",
        "muted": "#79675D",
        "border": "#EEDCCD",
        "input": "#FFFFFF",
        "input_text": "#35251D",
        "button_text": "#FFFFFF",
        "success": "#16834A",
        "warning": "#A96500",
        "danger": "#C0392B",
    },

    "emerald_green": {
        "name": "Emerald Green",
        "description": "Fresh green with professional neutral surfaces.",
        "mode": "light",
        "primary": "#16845B",
        "secondary": "#62B995",
        "background": "#F8FCFA",
        "surface": "#FFFFFF",
        "sidebar": "#EAF5EF",
        "text": "#19342A",
        "muted": "#60776B",
        "border": "#D6E7DD",
        "input": "#FFFFFF",
        "input_text": "#19342A",
        "button_text": "#FFFFFF",
        "success": "#16834A",
        "warning": "#A96500",
        "danger": "#C0392B",
    },

    "midnight_luxe": {
        "name": "Midnight Luxe",
        "description": "Deep navy, gold accents and bright readable text.",
        "mode": "dark",
        "primary": "#D6A83D",
        "secondary": "#F0CA75",
        "background": "#101827",
        "surface": "#192538",
        "sidebar": "#0C1422",
        "text": "#F5F7FB",
        "muted": "#B7C2D1",
        "border": "#344258",
        "input": "#25344A",
        "input_text": "#FFFFFF",
        "button_text": "#172033",
        "success": "#43C58A",
        "warning": "#F3BD55",
        "danger": "#FF7777",
    },
}


# ============================================================
# AVAILABLE THEMES
# ============================================================

AVAILABLE_THEMES = {

    "aziel_gold": {
        "name": "Aziel Gold",
        "description": "Signature corporate theme."
    },

    "ocean_blue": {
        "name": "Ocean Blue",
        "description": "Professional blue theme."
    },

    "royal_purple": {
        "name": "Royal Purple",
        "description": "Elegant purple theme."
    },

    "sunrise_orange": {
        "name": "Sunrise Orange",
        "description": "Warm orange and yellow theme."
    },

    "emerald_green": {
        "name": "Emerald Green",
        "description": "Fresh green theme."
    },

    "midnight_luxe": {
        "name": "Midnight Luxe",
        "description": "Premium dark navy theme."
    },

    "auto": {
        "name": "Auto (Day/Night)",
        "description": "Automatically changes between light and dark."
    },

    # Legacy names retained for compatibility.
    "light": {
        "name": "Light Mode",
        "description": "Legacy light theme."
    },

    "dark": {
        "name": "Dark Mode",
        "description": "Legacy dark theme."
    },
}


THEME_OPTIONS = [
    "aziel_gold",
    "ocean_blue",
    "royal_purple",
    "sunrise_orange",
    "emerald_green",
    "midnight_luxe",
    "auto",
]


# ============================================================
# LEGACY THEME MAPPING
# ============================================================

def normalize_theme(theme_name):
    """Convert legacy theme names into supported palettes."""

    if theme_name == "light":
        return "aziel_gold"

    if theme_name == "dark":
        return "midnight_luxe"

    if theme_name in THEME_PALETTES:
        return theme_name

    if theme_name == "auto":
        return "auto"

    return "aziel_gold"


# ============================================================
# THEME PERSISTENCE
# ============================================================

def save_theme_preference(theme_name):
    """Save the selected theme to the theme configuration file."""

    try:
        if theme_name not in AVAILABLE_THEMES:
            return False

        THEME_FILE.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "theme": theme_name,
            "updated": datetime.now().isoformat()
        }

        with open(THEME_FILE, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4)

        return True

    except Exception as error:
        print(f"Error saving theme preference: {error}")
        return False


def load_theme_preference():
    """Load the saved theme preference."""

    try:
        if THEME_FILE.exists():

            with open(THEME_FILE, "r", encoding="utf-8") as file:
                data = json.load(file)

            theme = data.get("theme", "auto")

            if theme in AVAILABLE_THEMES:
                return theme

    except Exception as error:
        print(f"Error loading theme preference: {error}")

    return "auto"


# ============================================================
# CURRENT THEME
# ============================================================

def get_current_theme():
    """Return the current theme preference."""

    if "current_theme" not in st.session_state:
        st.session_state.current_theme = load_theme_preference()

    return st.session_state.current_theme


def set_theme(theme_name):
    """Set and save the selected theme."""

    if theme_name not in AVAILABLE_THEMES:
        return False

    st.session_state.current_theme = theme_name

    save_theme_preference(theme_name)

    return True


# ============================================================
# AUTOMATIC DAY/NIGHT THEME
# ============================================================

def get_auto_theme():
    """
    Select a theme based on the local system time.

    Day:   06:00 - 17:59
    Night: 18:00 - 05:59
    """

    current_hour = datetime.now().hour

    if current_hour >= 18 or current_hour < 6:
        return "midnight_luxe"

    return "aziel_gold"


# ============================================================
# RESOLVE ACTIVE THEME
# ============================================================

def get_active_theme():
    """Return the actual palette that should currently be displayed."""

    selected_theme = get_current_theme()

    if selected_theme == "auto":
        selected_theme = get_auto_theme()

    return normalize_theme(selected_theme)


def get_theme_colors(theme_name=None):
    """Return the colour palette for a selected or active theme."""

    if theme_name is None:
        theme_name = get_active_theme()

    if isinstance(theme_name, dict):
        return theme_name

    if theme_name == "auto":
        theme_name = get_auto_theme()

    theme_name = normalize_theme(theme_name)

    return THEME_PALETTES.get(
        theme_name,
        THEME_PALETTES["aziel_gold"]
    )


# ============================================================
# CSS THEME GENERATOR
# ============================================================

def generate_theme_css(colors):
    """Generate accessible CSS for the selected colour palette."""

    return f"""
    <style>

    /* ==========================================
       GLOBAL APPLICATION
    ========================================== */

    .stApp {{
        background-color: {colors['background']} !important;
        color: {colors['text']} !important;
    }}

    [data-testid="stAppViewContainer"] {{
        background-color: {colors['background']} !important;
    }}

    [data-testid="stMain"] {{
        background-color: {colors['background']} !important;
        color: {colors['text']} !important;
    }}

    .main .block-container {{
        background-color: {colors['background']};
        color: {colors['text']};
    }}

    /* ==========================================
       GENERAL TEXT
    ========================================== */

    .stMarkdown,
    .stMarkdown p,
    .stMarkdown li,
    .stMarkdown span,
    .stMarkdown label,
    .stCaption,
    [data-testid="stCaptionContainer"] {{
        color: {colors['text']};
    }}

    h1, h2, h3, h4, h5, h6 {{
        color: {colors['text']} !important;
    }}

    label,
    [data-testid="stWidgetLabel"] p,
    [data-testid="stWidgetLabel"] label {{
        color: {colors['text']} !important;
    }}

    small {{
        color: {colors['muted']};
    }}

    /* ==========================================
       SIDEBAR
    ========================================== */

    [data-testid="stSidebar"] {{
        background-color: {colors['sidebar']} !important;
    }}

    [data-testid="stSidebar"] > div:first-child {{
        background-color: {colors['sidebar']} !important;
    }}

    [data-testid="stSidebar"] * {{
        color: {colors['text']};
    }}

    [data-testid="stSidebar"] button {{
        border-color: {colors['border']};
    }}

    /* ==========================================
       INPUT FIELDS
    ========================================== */

    input,
    textarea,
    [data-baseweb="input"] input,
    [data-baseweb="textarea"] textarea {{
        background-color: {colors['input']} !important;
        color: {colors['input_text']} !important;
        border-color: {colors['border']} !important;
        -webkit-text-fill-color: {colors['input_text']} !important;
        caret-color: {colors['input_text']} !important;
    }}

    input::placeholder,
    textarea::placeholder {{
        color: {colors['muted']} !important;
        -webkit-text-fill-color: {colors['muted']} !important;
        opacity: 1 !important;
    }}

    [data-baseweb="input"],
    [data-baseweb="textarea"] {{
        background-color: {colors['input']} !important;
        border-color: {colors['border']} !important;
    }}

    /* ==========================================
       SELECT BOXES AND DROPDOWNS
    ========================================== */

    [data-baseweb="select"] > div {{
        background-color: {colors['input']} !important;
        border-color: {colors['border']} !important;
        color: {colors['input_text']} !important;
    }}

    [data-baseweb="select"] span {{
        color: {colors['input_text']} !important;
    }}

    [role="listbox"],
    [role="option"],
    [data-baseweb="popover"] {{
        background-color: {colors['surface']} !important;
        color: {colors['text']} !important;
    }}

    [role="option"] * {{
        color: {colors['text']} !important;
    }}

    /* ==========================================
       STANDARD BUTTONS
    ========================================== */

    .stButton > button,
    .stDownloadButton > button,
    .stLinkButton > a {{
        background-color: {colors['primary']} !important;
        color: {colors['button_text']} !important;
        border: 1px solid {colors['primary']} !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        opacity: 1 !important;
        visibility: visible !important;
    }}

    .stButton > button p,
    .stDownloadButton > button p,
    .stLinkButton > a p {{
        color: {colors['button_text']} !important;
    }}

    .stButton > button:hover,
    .stDownloadButton > button:hover,
    .stLinkButton > a:hover {{
        border-color: {colors['secondary']} !important;
        filter: brightness(1.08);
    }}

    /* ==========================================
       FORM SUBMIT BUTTONS
       IMPORTANT: LOGIN BUTTON VISIBILITY FIX
    ========================================== */

    [data-testid="stFormSubmitButton"] button,
    .stFormSubmitButton button,
    form button[type="submit"],
    [data-testid="stForm"] button[kind="primary"],
    [data-testid="stForm"] button[kind="secondary"] {{

        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;

        min-height: 42px !important;
        min-width: 110px !important;

        padding: 0.5rem 1.2rem !important;

        background-color: {colors['primary']} !important;
        color: {colors['button_text']} !important;

        border: 1px solid {colors['primary']} !important;
        border-radius: 8px !important;

        font-weight: 700 !important;
        font-size: 15px !important;

        opacity: 1 !important;
        visibility: visible !important;

        cursor: pointer !important;

        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.12) !important;
    }}

    /* Make sure text and icons inside Login buttons are visible. */

    [data-testid="stFormSubmitButton"] button *,
    .stFormSubmitButton button *,
    form button[type="submit"] * {{
        color: {colors['button_text']} !important;
        -webkit-text-fill-color: {colors['button_text']} !important;
        opacity: 1 !important;
        visibility: visible !important;
    }}

    /* Hover effect for form buttons. */

    [data-testid="stFormSubmitButton"] button:hover,
    .stFormSubmitButton button:hover,
    form button[type="submit"]:hover {{
        background-color: {colors['secondary']} !important;
        border-color: {colors['secondary']} !important;
        filter: brightness(1.04);
    }}

    /* Preserve readable text when a button is disabled. */

    [data-testid="stFormSubmitButton"] button:disabled,
    .stFormSubmitButton button:disabled,
    form button[type="submit"]:disabled {{
        opacity: 0.75 !important;
        visibility: visible !important;
        cursor: not-allowed !important;
    }}

    /* Keyboard focus visibility. */

    [data-testid="stFormSubmitButton"] button:focus-visible,
    .stFormSubmitButton button:focus-visible,
    form button[type="submit"]:focus-visible {{
        outline: 3px solid {colors['secondary']} !important;
        outline-offset: 3px !important;
    }}

    /* ==========================================
       METRICS
    ========================================== */

    [data-testid="stMetric"] {{
        background-color: {colors['surface']};
        border: 1px solid {colors['border']};
        padding: 12px;
        border-radius: 10px;
    }}

    [data-testid="stMetricLabel"] {{
        color: {colors['muted']} !important;
    }}

    [data-testid="stMetricValue"] {{
        color: {colors['text']} !important;
    }}

    [data-testid="stMetricDelta"] {{
        color: {colors['success']} !important;
    }}

    /* ==========================================
       TABLES
    ========================================== */

    [data-testid="stTable"] {{
        background-color: {colors['surface']} !important;
        color: {colors['text']} !important;
    }}

    [data-testid="stDataFrame"],
    [data-testid="stDataEditor"] {{
        background-color: {colors['surface']} !important;
        border: 1px solid {colors['border']};
        border-radius: 8px;
    }}

    /* ==========================================
       TABS
    ========================================== */

    [data-baseweb="tab-list"] {{
        border-bottom: 1px solid {colors['border']};
    }}

    [data-baseweb="tab"] {{
        color: {colors['text']} !important;
    }}

    [aria-selected="true"] {{
        color: {colors['primary']} !important;
        border-bottom-color: {colors['primary']} !important;
    }}

    /* ==========================================
       ALERTS
    ========================================== */

    [data-testid="stAlert"] {{
        border-radius: 8px;
    }}

    /* ==========================================
       LINKS
    ========================================== */

    a {{
        color: {colors['primary']} !important;
    }}

    /* ==========================================
       CHECKBOXES AND RADIO BUTTONS
    ========================================== */

    [data-testid="stCheckbox"] label,
    [data-testid="stRadio"] label {{
        color: {colors['text']} !important;
    }}

    /* ==========================================
       EXPANDERS
    ========================================== */

    [data-testid="stExpander"] {{
        background-color: {colors['surface']};
        border: 1px solid {colors['border']};
        border-radius: 8px;
    }}

    [data-testid="stExpander"] summary {{
        color: {colors['text']} !important;
    }}

    /* ==========================================
       DIVIDERS
    ========================================== */

    hr {{
        border-color: {colors['border']} !important;
    }}

    /* ==========================================
       SCROLLBARS
    ========================================== */

    * {{
        scrollbar-color: {colors['primary']} {colors['surface']};
    }}

    </style>
    """


# ============================================================
# APPLY THEME
# ============================================================

def apply_theme(colors=None):
    """
    Apply the requested theme.

    Compatible with:
        apply_theme()
        apply_theme("dark")
        apply_theme("light")
        apply_theme("aziel_gold")
        apply_theme("midnight_luxe")
        apply_theme(custom_colour_dictionary)
    """

    if colors is None:
        selected_colors = get_theme_colors()

    elif isinstance(colors, dict):
        selected_colors = colors

    elif isinstance(colors, str):
        if colors == "auto":
            selected_colors = get_theme_colors(get_auto_theme())
        else:
            selected_colors = get_theme_colors(colors)

    else:
        selected_colors = get_theme_colors()

    css = generate_theme_css(selected_colors)

    st.markdown(css, unsafe_allow_html=True)


# ============================================================
# REMOVE CUSTOM THEME
# ============================================================

def apply_no_theme():
    """Remove custom styling and use Streamlit's default appearance."""

    st.markdown(
        """
        <style>
        .stApp {
            background-color: transparent;
        }
        </style>
        """,
        unsafe_allow_html=True
    )


# ============================================================
# PAGE THEME
# ============================================================

def apply_page_theme(page_name=None):
    """Apply the currently selected theme to an ERP page."""

    apply_theme(get_active_theme())


def apply_login_theme():
    """
    Apply the selected theme to the login page.

    Includes the form-submit button visibility styling
    required by Login and authentication forms.
    """

    apply_theme(get_active_theme())


def apply_branch_selection_theme():
    """Apply the selected theme to branch selection."""

    apply_theme(get_active_theme())


def get_page_theme(page_name=None):
    """Return the theme configuration for the active page."""

    active_theme = get_active_theme()

    return {
        **AVAILABLE_THEMES.get(
            active_theme,
            AVAILABLE_THEMES["aziel_gold"]
        ),
        "colors": get_theme_colors(active_theme)
    }


# ============================================================
# THEME SELECTOR
# ============================================================

def theme_selector():
    """
    Display the ERP theme selector in the sidebar.

    Offers six professional themes and automatic day/night mode.
    """

    st.sidebar.markdown("### 🎨 Theme Settings")

    st.sidebar.caption(
        "Personalise the appearance of AZIEL INVESTMENTS ERP."
    )

    current_theme = get_current_theme()

    if current_theme not in THEME_OPTIONS:
        current_theme = "auto"

    theme_labels = [
        AVAILABLE_THEMES[theme]["name"]
        for theme in THEME_OPTIONS
    ]

    label_to_key = {
        AVAILABLE_THEMES[theme]["name"]: theme
        for theme in THEME_OPTIONS
    }

    current_label = AVAILABLE_THEMES[current_theme]["name"]

    selected_label = st.sidebar.selectbox(
        "Choose your theme",
        options=theme_labels,
        index=theme_labels.index(current_label),
        key="aziel_theme_selector",
        help="Choose a theme for your ERP dashboard."
    )

    selected_key = label_to_key[selected_label]

    if selected_key != current_theme:

        if set_theme(selected_key):
            st.rerun()

    active_theme = get_active_theme()

    st.sidebar.caption(
        f"Selected: {AVAILABLE_THEMES[current_theme]['name']}"
    )

    if current_theme == "auto":

        st.sidebar.info(
            f"Automatic mode is currently using "
            f"{THEME_PALETTES[active_theme]['name']}."
        )

    else:

        st.sidebar.caption(
            THEME_PALETTES[active_theme]["description"]
        )
