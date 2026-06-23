import streamlit as st


# ==============================
# CART STATE HANDLER
# ==============================
def get_cart():
    if "cart" not in st.session_state:
        st.session_state.cart = []
    return st.session_state.cart


def clear_cart():
    st.session_state.cart = []


# ==============================
# RECEIPT STATE
# ==============================
def set_receipt(text):
    st.session_state.receipt = text


def get_receipt():
    return st.session_state.get("receipt", "")


def set_last_receipt(text):
    st.session_state.last_receipt = text


def get_last_receipt():
    return st.session_state.get("last_receipt", "")