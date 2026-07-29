# customer_portal.py
"""
Aziel Investments - Customer Portal
Separate entry point for customer access
"""

import streamlit as st
import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

# Set page config for customer app - clean and simple
st.set_page_config(
    page_title="Aziel Investments - Customer Portal",
    page_icon="🛍️",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Hide Streamlit branding and sidebar for cleaner look
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display: none;}
    .stAppHeader {display: none;}
    .stSidebar {display: none !important;}
</style>
""", unsafe_allow_html=True)

# Import the customer app functions
from backend.customers.customer_app import customer_app

if __name__ == "__main__":
    customer_app()