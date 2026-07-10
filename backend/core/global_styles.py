# backend/core/global_styles.py

def get_global_styles():
    """Return global CSS styles for the application - FIXED for theme compatibility"""
    
    return """
    <style>
        /* ==============================
           SELECTBOX STYLING FIX
           ============================== */
        
        div[data-baseweb="select"] > div {
            background-color: #ffffff !important;
            color: #000000 !important;
            border: 1px solid #d0d0d0 !important;
            border-radius: 8px !important;
            min-height: 38px !important;
        }
        
        div[data-baseweb="select"] > div > div {
            background-color: #ffffff !important;
            color: #000000 !important;
        }
        
        div[data-baseweb="select"] > div > div > div {
            color: #000000 !important;
        }
        
        div[data-baseweb="select"] ul {
            background-color: #ffffff !important;
            border: 1px solid #d0d0d0 !important;
            border-radius: 8px !important;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15) !important;
            max-height: 300px !important;
            overflow-y: auto !important;
            padding: 4px 0 !important;
            z-index: 999999 !important;
        }
        
        div[data-baseweb="select"] ul li {
            color: #000000 !important;
            background-color: #ffffff !important;
            padding: 10px 16px !important;
            font-size: 14px !important;
            cursor: pointer !important;
            transition: all 0.2s ease !important;
            border-bottom: 1px solid #f0f0f0 !important;
            list-style: none !important;
        }
        
        div[data-baseweb="select"] ul li:last-child {
            border-bottom: none !important;
        }
        
        div[data-baseweb="select"] ul li:hover {
            background-color: #000000 !important;
            color: #ffffff !important;
        }
        
        div[data-baseweb="select"] ul li[aria-selected="true"] {
            background-color: #000000 !important;
            color: #ffffff !important;
            font-weight: 600 !important;
        }
        
        .stSelectbox label {
            color: #000000 !important;
            font-weight: 500 !important;
        }
        
        div[data-baseweb="select"] [data-testid="stSelectbox"] {
            background-color: #ffffff !important;
            color: #000000 !important;
        }
        
        /* ==============================
           SIDEBAR SELECTBOX
           ============================== */
        
        div[data-testid="stSidebar"] div[data-baseweb="select"] > div {
            background-color: #ffffff !important;
            color: #000000 !important;
            border-color: #d0d0d0 !important;
        }
        
        div[data-testid="stSidebar"] div[data-baseweb="select"] > div > div {
            background-color: #ffffff !important;
            color: #000000 !important;
        }
        
        div[data-testid="stSidebar"] div[data-baseweb="select"] ul {
            background-color: #ffffff !important;
            border-color: #d0d0d0 !important;
        }
        
        div[data-testid="stSidebar"] div[data-baseweb="select"] ul li {
            color: #000000 !important;
            background-color: #ffffff !important;
        }
        
        div[data-testid="stSidebar"] div[data-baseweb="select"] ul li:hover {
            background-color: #000000 !important;
            color: #ffffff !important;
        }
        
        /* ==============================
           MULTI-SELECT
           ============================== */
        
        div[data-baseweb="select"] [data-testid="stMultiSelect"] {
            background-color: #ffffff !important;
            color: #000000 !important;
        }
        
        div[data-baseweb="select"] [data-testid="stMultiSelect"] input {
            color: #000000 !important;
        }
        
        /* ==============================
           INPUT FIELDS
           ============================== */
        
        .stTextInput > div > div > input,
        .stNumberInput > div > div > input,
        .stTextArea > div > div > textarea,
        .stDateInput > div > div > input {
            background-color: #ffffff !important;
            color: #000000 !important;
            border: 1px solid #d0d0d0 !important;
            border-radius: 8px !important;
        }
        
        .stTextInput > div > div > input:focus,
        .stNumberInput > div > div > input:focus,
        .stTextArea > div > div > textarea:focus {
            border-color: #000000 !important;
            box-shadow: 0 0 0 2px rgba(0,0,0,0.1) !important;
            outline: none !important;
        }
        
        .stTextInput label,
        .stNumberInput label,
        .stSelectbox label,
        .stTextArea label,
        .stDateInput label {
            color: #000000 !important;
            font-weight: 500 !important;
        }
        
        /* ==============================
           SIDEBAR INPUTS
           ============================== */
        
        div[data-testid="stSidebar"] .stTextInput > div > div > input {
            background-color: #ffffff !important;
            color: #000000 !important;
            border-color: #d0d0d0 !important;
        }
        
        div[data-testid="stSidebar"] .stNumberInput > div > div > input {
            background-color: #ffffff !important;
            color: #000000 !important;
            border-color: #d0d0d0 !important;
        }
        
        /* ==============================
           DATAFRAME / TABLE
           ============================== */
        
        .dataframe {
            background-color: #ffffff !important;
            color: #000000 !important;
            border-radius: 10px !important;
            border: 1px solid #e5e7eb !important;
        }
        
        .dataframe th {
            background-color: #000000 !important;
            color: #ffffff !important;
            padding: 10px !important;
            font-weight: 600 !important;
            border: 1px solid #333333 !important;
        }
        
        .dataframe td {
            color: #000000 !important;
            padding: 8px !important;
            border: 1px solid #e5e7eb !important;
            background-color: #ffffff !important;
        }
        
        .dataframe tr:nth-child(even) {
            background-color: #f8f9fa !important;
        }
        
        .dataframe tr:nth-child(even) td {
            background-color: #f8f9fa !important;
        }
        
        .dataframe tr:hover td {
            background-color: #f0f0f0 !important;
        }
        
        /* ==============================
           BUTTONS - COMPLETELY REMOVED
           All button styles are now controlled by theme_manager.py
           ============================== */
        
        /* ==============================
           ALERT MESSAGES
           ============================== */
        
        .stSuccess {
            background-color: #d4edda !important;
            border-left: 4px solid #28a745 !important;
            border-radius: 8px !important;
            padding: 12px !important;
            color: #155724 !important;
        }
        
        .stWarning {
            background-color: #fff3cd !important;
            border-left: 4px solid #ffc107 !important;
            border-radius: 8px !important;
            padding: 12px !important;
            color: #856404 !important;
        }
        
        .stError {
            background-color: #f8d7da !important;
            border-left: 4px solid #dc3545 !important;
            border-radius: 8px !important;
            padding: 12px !important;
            color: #721c24 !important;
        }
        
        .stInfo {
            background-color: #d1ecf1 !important;
            border-left: 4px solid #17a2b8 !important;
            border-radius: 8px !important;
            padding: 12px !important;
            color: #0c5460 !important;
        }
        
        /* ==============================
           METRICS
           ============================== */
        
        [data-testid="stMetricValue"] {
            font-size: 1.8rem !important;
            font-weight: 600 !important;
        }
        
        [data-testid="stMetricLabel"] {
            font-size: 0.9rem !important;
        }
        
        /* ==============================
           TABS
           ============================== */
        
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px !important;
        }
        
        .stTabs [data-baseweb="tab"] {
            background-color: #f8f9fa !important;
            border-radius: 8px !important;
            padding: 8px 16px !important;
            border: 1px solid #e5e7eb !important;
            transition: all 0.3s ease !important;
        }
        
        .stTabs [aria-selected="true"] {
            background-color: #000000 !important;
            color: #ffffff !important;
            border-color: #000000 !important;
        }
        
        /* ==============================
           EXPANDER
           ============================== */
        
        [data-testid="stExpander"] {
            background-color: #ffffff !important;
            border: 1px solid #e5e7eb !important;
            border-radius: 12px !important;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05) !important;
        }
        
        [data-testid="stExpander"] summary {
            padding: 8px 12px !important;
        }
        
        /* ==============================
           SIDEBAR
           ============================== */
        
        [data-testid="stSidebar"] {
            background-color: #f3f4f6 !important;
            border-right: 1px solid #e5e7eb !important;
        }
        
        [data-testid="stSidebar"] .stMarkdown,
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] label {
            color: #1F2937 !important;
        }
        
        /* ==============================
           CODE BLOCKS
           ============================== */
        
        code {
            background-color: #f8f9fa !important;
            border-radius: 4px !important;
            padding: 2px 6px !important;
            font-size: 0.9em !important;
        }
        
        pre code {
            background-color: #1e1e2e !important;
            color: #f8f9fa !important;
            padding: 12px !important;
            border-radius: 8px !important;
            display: block !important;
        }
        
        /* ==============================
           CHECKBOX & RADIO
           ============================== */
        
        .stCheckbox label,
        .stRadio label {
            color: #1F2937 !important;
        }
        
        /* ==============================
           PROGRESS BAR
           ============================== */
        
        .stProgress > div > div {
            border-radius: 10px !important;
        }
        
        .stProgress > div {
            background-color: #e5e7eb !important;
            border-radius: 10px !important;
        }
        
        /* ==============================
           CAPTION
           ============================== */
        
        .stCaption {
            color: #6B7280 !important;
            font-size: 0.85rem !important;
        }
        
        /* ==============================
           HORIZONTAL RULE
           ============================== */
        
        hr {
            border-color: #e5e7eb !important;
            margin: 1rem 0 !important;
        }
        
        /* ==============================
           LINKS
           ============================== */
        
        a {
            text-decoration: none !important;
        }
        
        a:hover {
            text-decoration: underline !important;
        }
        
        /* ==============================
           IMAGE CONTAINER
           ============================== */
        
        .stImage {
            border-radius: 8px !important;
        }
    </style>
    """