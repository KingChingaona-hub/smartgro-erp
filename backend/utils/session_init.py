import streamlit as st

def init_session():

    # ==========================
    # CART SYSTEM
    # ==========================
    if "cart" not in st.session_state:
        st.session_state.cart = []

    if "receipt" not in st.session_state:
        st.session_state.receipt = ""
        
    if "shift_id" not in st.session_state:
        st.session_state.shift_id = None

    # ==========================
    # AUTH SYSTEM
    # ==========================
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if "username" not in st.session_state:
        st.session_state.username = ""

    if "role" not in st.session_state:
        st.session_state.role = ""

    # ==========================
    # BARCODE SCANNING CONTROL (STEP 2 ADDITION)
    # ==========================

    # stores last scanned barcode to prevent duplicates
    if "last_scan" not in st.session_state:
        st.session_state.last_scan = ""

    # optional: prevents rapid double-processing in same rerun
    if "scan_lock" not in st.session_state:
        st.session_state.scan_lock = False

    # optional: future enhancement (buffer for fast scanners)
    if "scan_buffer" not in st.session_state:
        st.session_state.scan_buffer = ""