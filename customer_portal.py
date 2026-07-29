# customer_portal.py
"""
Aziel Investments - Customer Portal
Completely independent entry point
"""

import streamlit as st
import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

# ==============================
# PAGE CONFIG - Clean customer view
# ==============================
st.set_page_config(
    page_title="Aziel Investments - Customer Portal",
    page_icon="🛍️",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ==============================
# HIDE ALL STREAMLIT ELEMENTS
# ==============================
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display: none;}
    .stAppHeader {display: none;}
    .stSidebar {display: none !important;}
    .st-emotion-cache-1r6slb0 {display: none !important;}
    .st-emotion-cache-1v0mbdj {display: none !important;}
    .st-emotion-cache-6qob1r {display: none !important;}
</style>
""", unsafe_allow_html=True)

# ==============================
# IMPORT CUSTOMER APP - ONLY
# ==============================
from backend.customers.customer_app import customer_app

if __name__ == "__main__":
    customer_app()